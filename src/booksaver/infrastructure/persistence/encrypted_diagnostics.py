"""Ciphertext-only SQLite storage for short-lived DOM incident diagnostics."""

from __future__ import annotations

import base64
import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from booksaver.domain.browser_resilience import TerminalBrowserReason
from booksaver.domain.dom_incident import (
    DiagnosticBundle,
    DiagnosticInspection,
    DiagnosticModelAttempt,
    DiagnosticPurgeResult,
    EvidenceState,
    IncidentBudgetState,
    IncidentProviderState,
)
from booksaver.domain.errors import SecretKeyError
from booksaver.domain.model_policy import (
    EscalationTrigger,
    ModelAttemptOutcome,
    ModelProvider,
    ModelRole,
    ReservationStatus,
)
from booksaver.infrastructure.crypto.fernet_key_store import FernetKeyStore

from .sqlite_store import SqliteStore

DIAGNOSTIC_RETENTION = timedelta(days=7)
MAX_DIAGNOSTIC_CIPHERTEXT_BYTES = 1024 * 1024
MAX_DIAGNOSTIC_PLAINTEXT_BYTES = 768 * 1024


def _utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be a timezone-aware UTC datetime")
    return value.astimezone(UTC)


class EncryptedDiagnosticStore:
    """Persist one bounded Fernet envelope per content-free incident."""

    def __init__(
        self,
        store: SqliteStore,
        key_store: FernetKeyStore | None = None,
    ) -> None:
        self._store = store
        self._key_store = key_store or FernetKeyStore(purpose="DOM-drift diagnostic")

    @contextmanager
    def _immediate(self) -> Iterator[sqlite3.Connection]:
        conn = self._store.conn
        if conn.in_transaction:
            raise RuntimeError("diagnostic operations require a clean transaction")
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()

    def put(self, bundle: DiagnosticBundle) -> EvidenceState:
        """Encrypt before touching SQLite; never persist a plaintext fallback."""
        payload = self._serialize(bundle)
        if len(payload) > MAX_DIAGNOSTIC_PLAINTEXT_BYTES:
            self._set_state(bundle.incident_id, EvidenceState.OVERSIZED)
            return EvidenceState.OVERSIZED
        try:
            ciphertext = self._key_store.encrypt(payload.decode("utf-8"))
        except SecretKeyError:
            self._set_state(bundle.incident_id, EvidenceState.UNAVAILABLE)
            return EvidenceState.UNAVAILABLE
        if len(ciphertext) > MAX_DIAGNOSTIC_CIPHERTEXT_BYTES:
            self._set_state(bundle.incident_id, EvidenceState.OVERSIZED)
            return EvidenceState.OVERSIZED

        created_at = _utc(bundle.created_at, "created_at")
        expires_at = created_at + DIAGNOSTIC_RETENTION
        with self._immediate() as conn:
            exists = conn.execute(
                "SELECT 1 FROM dom_drift_incidents WHERE incident_id = ?",
                (str(bundle.incident_id),),
            ).fetchone()
            if exists is None:
                raise KeyError(f"Unknown DOM-drift incident {bundle.incident_id}")
            conn.execute(
                """
                INSERT INTO dom_drift_diagnostics (
                    incident_id, envelope_version, ciphertext, byte_size,
                    created_at, expires_at, evidence_state
                ) VALUES (?, ?, ?, ?, ?, ?, 'available')
                ON CONFLICT(incident_id) DO NOTHING
                """,
                (
                    str(bundle.incident_id),
                    bundle.version,
                    ciphertext,
                    len(ciphertext),
                    created_at.isoformat(),
                    expires_at.isoformat(),
                ),
            )
            conn.execute(
                "UPDATE dom_drift_incidents SET evidence_state = 'available' "
                "WHERE incident_id = ?",
                (str(bundle.incident_id),),
            )
        return EvidenceState.AVAILABLE

    def inspect(self, incident_id: uuid.UUID, now: datetime) -> DiagnosticInspection:
        instant = _utc(now, "now")
        incident = self._store.conn.execute(
            "SELECT evidence_state FROM dom_drift_incidents WHERE incident_id = ?",
            (str(incident_id),),
        ).fetchone()
        if incident is None:
            raise KeyError(f"Unknown DOM-drift incident {incident_id}")
        row = self._store.conn.execute(
            "SELECT * FROM dom_drift_diagnostics WHERE incident_id = ?",
            (str(incident_id),),
        ).fetchone()
        if row is None:
            return DiagnosticInspection(EvidenceState(incident["evidence_state"]))
        if instant >= datetime.fromisoformat(row["expires_at"]):
            self._delete_and_mark((str(incident_id),), EvidenceState.EXPIRED)
            return DiagnosticInspection(EvidenceState.EXPIRED)
        try:
            plaintext = self._key_store.decrypt(bytes(row["ciphertext"]))
        except SecretKeyError:
            self._set_state(incident_id, EvidenceState.UNDECRYPTABLE)
            return DiagnosticInspection(EvidenceState.UNDECRYPTABLE)
        try:
            bundle = self._deserialize(plaintext)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeError):
            self._set_state(incident_id, EvidenceState.CORRUPT)
            return DiagnosticInspection(EvidenceState.CORRUPT)
        if bundle.incident_id != incident_id:
            self._set_state(incident_id, EvidenceState.CORRUPT)
            return DiagnosticInspection(EvidenceState.CORRUPT)
        return DiagnosticInspection(EvidenceState.AVAILABLE, bundle)

    def purge_expired(self, now: datetime) -> int:
        instant = _utc(now, "now")
        rows = self._store.conn.execute(
            "SELECT incident_id FROM dom_drift_diagnostics WHERE expires_at <= ?",
            (instant.isoformat(),),
        ).fetchall()
        ids = tuple(str(row["incident_id"]) for row in rows)
        self._delete_and_mark(ids, EvidenceState.EXPIRED)
        return len(ids)

    def purge_for_user(self, user_id: int, now: datetime) -> DiagnosticPurgeResult:
        if user_id < 1:
            raise ValueError("user_id must be positive")
        instant = _utc(now, "now")
        rows = self._store.conn.execute(
            "SELECT incident_id, ciphertext, expires_at FROM dom_drift_diagnostics"
        ).fetchall()
        matching: list[str] = []
        unverifiable: list[str] = []
        for row in rows:
            incident_id = str(row["incident_id"])
            if instant >= datetime.fromisoformat(row["expires_at"]):
                unverifiable.append(incident_id)
                continue
            try:
                plaintext = self._key_store.decrypt(bytes(row["ciphertext"]))
                bundle = self._deserialize(plaintext)
            except (
                KeyError,
                TypeError,
                ValueError,
                SecretKeyError,
                json.JSONDecodeError,
                UnicodeError,
            ):
                # Private source linkage cannot be verified. Conservatively
                # delete it rather than risk retaining evidence for this user.
                unverifiable.append(incident_id)
                continue
            if user_id in bundle.source_user_ids:
                matching.append(incident_id)

        all_ids = tuple(dict.fromkeys((*matching, *unverifiable)))
        self._delete_and_mark(all_ids, EvidenceState.PURGED)
        return DiagnosticPurgeResult(
            deleted_matching=len(set(matching)),
            deleted_unverifiable=len(set(unverifiable) - set(matching)),
        )

    def _set_state(self, incident_id: uuid.UUID, state: EvidenceState) -> None:
        cursor = self._store.conn.execute(
            "UPDATE dom_drift_incidents SET evidence_state = ? WHERE incident_id = ?",
            (state.value, str(incident_id)),
        )
        self._store.conn.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Unknown DOM-drift incident {incident_id}")

    def _delete_and_mark(self, ids: tuple[str, ...], state: EvidenceState) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self._immediate() as conn:
            conn.execute(
                f"DELETE FROM dom_drift_diagnostics WHERE incident_id IN ({placeholders})",
                ids,
            )
            conn.execute(
                f"UPDATE dom_drift_incidents SET evidence_state = ? "
                f"WHERE incident_id IN ({placeholders})",
                (state.value, *ids),
            )

    @staticmethod
    def _serialize(bundle: DiagnosticBundle) -> bytes:
        document = {
            "version": bundle.version,
            "incident_id": str(bundle.incident_id),
            "source_user_ids": list(bundle.source_user_ids),
            "structural_roles": list(bundle.structural_roles),
            "action_outcomes": list(bundle.action_outcomes),
            "terminal_reason": bundle.terminal_reason.value,
            "model_roles": [role.value for role in bundle.model_roles],
            "model_attempts": [
                {
                    "ordinal": attempt.ordinal,
                    "provider": attempt.provider.value,
                    "model": attempt.model,
                    "role": attempt.role.value,
                    "trigger": attempt.trigger.value,
                    "outcome": (
                        attempt.outcome.value if attempt.outcome is not None else None
                    ),
                    "status": attempt.status.value,
                    "input_tokens": attempt.input_tokens,
                    "output_tokens": attempt.output_tokens,
                    "latency_ms": attempt.latency_ms,
                    "reserved_micro_usd": attempt.reserved_micro_usd,
                    "charged_micro_usd": attempt.charged_micro_usd,
                }
                for attempt in bundle.model_attempts
            ],
            "provider_state": bundle.provider_state.value,
            "budget_state": bundle.budget_state.value,
            "created_at": bundle.created_at.astimezone(UTC).isoformat(),
            "structural_image": (
                base64.b64encode(bundle.structural_image).decode("ascii")
                if bundle.structural_image is not None
                else None
            ),
        }
        return json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")

    @staticmethod
    def _deserialize(plaintext: str) -> DiagnosticBundle:
        document = json.loads(plaintext)
        if not isinstance(document, dict):
            raise ValueError("diagnostic envelope must be an object")
        image = document["structural_image"]
        structural_image = (
            base64.b64decode(image, validate=True) if image is not None else None
        )
        raw_attempts = document.get("model_attempts", [])
        if not isinstance(raw_attempts, list):
            raise ValueError("diagnostic model attempts must be an array")
        model_attempts = tuple(
            EncryptedDiagnosticStore._deserialize_attempt(item)
            for item in raw_attempts
        )
        return DiagnosticBundle(
            version=int(document["version"]),
            incident_id=uuid.UUID(str(document["incident_id"])),
            source_user_ids=tuple(int(item) for item in document["source_user_ids"]),
            structural_roles=tuple(str(item) for item in document["structural_roles"]),
            action_outcomes=tuple(str(item) for item in document["action_outcomes"]),
            terminal_reason=TerminalBrowserReason(document["terminal_reason"]),
            model_roles=tuple(ModelRole(item) for item in document["model_roles"]),
            model_attempts=model_attempts,
            provider_state=IncidentProviderState(document["provider_state"]),
            budget_state=IncidentBudgetState(document["budget_state"]),
            created_at=datetime.fromisoformat(document["created_at"]),
            structural_image=structural_image,
        )

    @staticmethod
    def _deserialize_attempt(document: object) -> DiagnosticModelAttempt:
        if not isinstance(document, dict):
            raise ValueError("diagnostic model attempt must be an object")
        outcome = document["outcome"]
        return DiagnosticModelAttempt(
            ordinal=int(document["ordinal"]),
            provider=ModelProvider(document["provider"]),
            model=str(document["model"]),
            role=ModelRole(document["role"]),
            trigger=EscalationTrigger(document["trigger"]),
            outcome=ModelAttemptOutcome(outcome) if outcome is not None else None,
            status=ReservationStatus(document["status"]),
            input_tokens=(
                int(document["input_tokens"])
                if document["input_tokens"] is not None
                else None
            ),
            output_tokens=(
                int(document["output_tokens"])
                if document["output_tokens"] is not None
                else None
            ),
            latency_ms=(
                int(document["latency_ms"])
                if document["latency_ms"] is not None
                else None
            ),
            reserved_micro_usd=int(document["reserved_micro_usd"]),
            charged_micro_usd=(
                int(document["charged_micro_usd"])
                if document["charged_micro_usd"] is not None
                else None
            ),
        )
