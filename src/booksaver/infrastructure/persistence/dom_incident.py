"""SQLite persistence for content-free DOM-drift incidents and owner alerts."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from booksaver.application.dom_incident import CorrelationResult
from booksaver.domain.browser_resilience import (
    DomJourney,
    DomStepId,
    TerminalBrowserReason,
)
from booksaver.domain.dom_incident import (
    DeliveryFailureCode,
    DeliveryState,
    DomDriftFingerprint,
    DomDriftIncident,
    DomDriftOccurrence,
    EvidenceState,
    IncidentAlert,
    IncidentBudgetState,
    IncidentProviderState,
    IncidentSeverity,
    IncidentSourceProvenance,
    IncidentState,
    StructuralDigest,
)
from booksaver.domain.model_policy import ModelRole

from .sqlite_store import SqliteStore

CORRELATION_WINDOW = timedelta(hours=6)


SqliteCorrelationResult = CorrelationResult


@dataclass(frozen=True, slots=True)
class SqliteIncidentStatusProjection:
    open_incidents: int
    pending_alerts: int
    failed_alerts: int
    unavailable_evidence: int


def _utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be a timezone-aware UTC datetime")
    return value.astimezone(UTC)


def _optional_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None


class SqliteDomIncidentRepository:
    """Restart-safe incident correlation and durable alert lifecycle."""

    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    @contextmanager
    def _immediate(self) -> Iterator[sqlite3.Connection]:
        conn = self._store.conn
        if conn.in_transaction:
            raise RuntimeError("incident operations require a clean transaction")
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()

    def correlate(self, occurrence: DomDriftOccurrence) -> SqliteCorrelationResult:
        observed_at = _utc(occurrence.observed_at, "observed_at")
        with self._immediate() as conn:
            row = conn.execute(
                "SELECT * FROM dom_drift_incidents WHERE fingerprint = ?",
                (occurrence.fingerprint.value,),
            ).fetchone()
            immediate = (
                occurrence.provenance
                is IncidentSourceProvenance.CODE_MAINTENANCE_REQUIRED
            )
            if row is None:
                incident_id = uuid.uuid4()
                state = IncidentState.OPEN if immediate else IncidentState.OBSERVING
                severity = (
                    IncidentSeverity.MAINTENANCE_REQUIRED
                    if immediate
                    else IncidentSeverity.OBSERVING
                )
                opened_at = observed_at if immediate else None
                conn.execute(
                    """
                    INSERT INTO dom_drift_incidents (
                        incident_id, fingerprint, journey, registered_step,
                        terminal_class, verifier_category, structural_digest,
                        model_roles_json, provider_state, budget_state, provenance,
                        state, severity, recovered, occurrence_count,
                        window_occurrence_count, window_started_at,
                        first_observed_at, last_observed_at, opened_at, resolved_at,
                        alert_suppressed_until, evidence_state
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1,
                              ?, ?, ?, ?, NULL, NULL, ?)
                    """,
                    (
                        str(incident_id),
                        occurrence.fingerprint.value,
                        occurrence.journey.value,
                        occurrence.step_id.value,
                        occurrence.terminal_reason.value,
                        occurrence.verifier_category,
                        occurrence.structural_digest.value,
                        json.dumps(
                            [role.value for role in occurrence.model_roles],
                            separators=(",", ":"),
                        ),
                        occurrence.provider_state.value,
                        occurrence.budget_state.value,
                        occurrence.provenance.value,
                        state.value,
                        severity.value,
                        int(occurrence.recovered),
                        observed_at.isoformat(),
                        observed_at.isoformat(),
                        observed_at.isoformat(),
                        opened_at.isoformat() if opened_at is not None else None,
                        EvidenceState.PENDING.value,
                    ),
                )
            else:
                incident_id = uuid.UUID(row["incident_id"])
                static_identity = (
                    row["journey"],
                    row["registered_step"],
                    row["terminal_class"],
                    row["verifier_category"],
                    row["structural_digest"],
                    row["model_roles_json"],
                )
                proposed_identity = (
                    occurrence.journey.value,
                    occurrence.step_id.value,
                    occurrence.terminal_reason.value,
                    occurrence.verifier_category,
                    occurrence.structural_digest.value,
                    json.dumps(
                        [role.value for role in occurrence.model_roles],
                        separators=(",", ":"),
                    ),
                )
                if static_identity != proposed_identity:
                    raise ValueError(
                        "an incident fingerprint cannot identify different classifier fields"
                    )
                window_start = datetime.fromisoformat(row["window_started_at"])
                first_observed = datetime.fromisoformat(row["first_observed_at"])
                last_observed = datetime.fromisoformat(row["last_observed_at"])
                # Concurrent callers can acquire SQLite's write lock in either
                # order. Correlation is event-time based, not lock-order based.
                effective_first = min(first_observed, observed_at)
                effective_last = max(last_observed, observed_at)
                in_window = (
                    effective_last - min(window_start, observed_at) < CORRELATION_WINDOW
                )
                window_count = int(row["window_occurrence_count"]) + 1 if in_window else 1
                effective_window_start = (
                    min(window_start, observed_at) if in_window else observed_at
                )
                should_open = immediate or window_count >= 2
                state = IncidentState.OPEN if should_open else IncidentState(row["state"])
                severity = (
                    IncidentSeverity.MAINTENANCE_REQUIRED
                    if should_open
                    else IncidentSeverity(row["severity"])
                )
                opened_at = _optional_time(row["opened_at"])
                if should_open and opened_at is None:
                    opened_at = observed_at
                conn.execute(
                    """
                    UPDATE dom_drift_incidents
                    SET provider_state = ?, budget_state = ?, provenance = ?,
                        state = ?, severity = ?, recovered = ?,
                        occurrence_count = occurrence_count + 1,
                        window_occurrence_count = ?, window_started_at = ?,
                        first_observed_at = ?, last_observed_at = ?,
                        opened_at = ?, resolved_at = NULL
                    WHERE incident_id = ?
                    """,
                    (
                        occurrence.provider_state.value,
                        occurrence.budget_state.value,
                        occurrence.provenance.value,
                        state.value,
                        severity.value,
                        int(occurrence.recovered),
                        window_count,
                        effective_window_start.isoformat(),
                        effective_first.isoformat(),
                        effective_last.isoformat(),
                        opened_at.isoformat() if opened_at is not None else None,
                        str(incident_id),
                    ),
                )

            alert = self._maybe_create_alert(conn, incident_id, observed_at)
            updated = conn.execute(
                "SELECT * FROM dom_drift_incidents WHERE incident_id = ?",
                (str(incident_id),),
            ).fetchone()
            assert updated is not None
            return SqliteCorrelationResult(self._incident(updated), alert)

    def _maybe_create_alert(
        self,
        conn: sqlite3.Connection,
        incident_id: uuid.UUID,
        observed_at: datetime,
    ) -> IncidentAlert | None:
        row = conn.execute(
            "SELECT * FROM dom_drift_incidents WHERE incident_id = ?",
            (str(incident_id),),
        ).fetchone()
        assert row is not None
        if row["state"] != IncidentState.OPEN.value:
            return None
        suppressed_until = _optional_time(row["alert_suppressed_until"])
        last = conn.execute(
            "SELECT * FROM dom_drift_alerts WHERE incident_id = ? "
            "ORDER BY generation DESC LIMIT 1",
            (str(incident_id),),
        ).fetchone()
        severity_changed = last is not None and last["severity"] != row["severity"]
        if suppressed_until is not None and observed_at < suppressed_until and not severity_changed:
            return None
        generation = int(last["generation"]) + 1 if last is not None else 1
        alert_id = uuid.uuid4()
        conn.execute(
            """
            INSERT INTO dom_drift_alerts (
                alert_id, incident_id, generation, severity, delivery_state,
                attempt_count, next_attempt_at, claimed_at, delivered_at,
                failure_code, created_at
            ) VALUES (?, ?, ?, ?, ?, 0, ?, NULL, NULL, NULL, ?)
            """,
            (
                str(alert_id),
                str(incident_id),
                generation,
                row["severity"],
                DeliveryState.PENDING.value,
                observed_at.isoformat(),
                observed_at.isoformat(),
            ),
        )
        conn.execute(
            "UPDATE dom_drift_incidents SET alert_suppressed_until = ? "
            "WHERE incident_id = ?",
            ((observed_at + CORRELATION_WINDOW).isoformat(), str(incident_id)),
        )
        alert_row = conn.execute(
            "SELECT * FROM dom_drift_alerts WHERE alert_id = ?", (str(alert_id),)
        ).fetchone()
        assert alert_row is not None
        return self._alert(alert_row)

    def resolve_deterministic_success(
        self,
        journey: DomJourney,
        step_id: DomStepId,
        observed_at: datetime,
    ) -> int:
        observed = _utc(observed_at, "observed_at")
        with self._immediate() as conn:
            rows = conn.execute(
                "SELECT incident_id FROM dom_drift_incidents "
                "WHERE journey = ? AND registered_step = ? AND state != 'resolved'",
                (journey.value, step_id.value),
            ).fetchall()
            ids = tuple(row["incident_id"] for row in rows)
            if not ids:
                return 0
            placeholders = ",".join("?" for _ in ids)
            conn.execute(
                f"UPDATE dom_drift_incidents SET state = 'resolved', resolved_at = ? "
                f"WHERE incident_id IN ({placeholders})",
                (observed.isoformat(), *ids),
            )
            conn.execute(
                f"UPDATE dom_drift_alerts SET delivery_state = 'suppressed', "
                f"next_attempt_at = NULL WHERE incident_id IN ({placeholders}) "
                "AND delivery_state IN ('pending', 'retryable_failed')",
                ids,
            )
            return len(ids)

    def claim_next_alert(self, now: datetime) -> IncidentAlert | None:
        instant = _utc(now, "now")
        with self._immediate() as conn:
            row = conn.execute(
                "SELECT * FROM dom_drift_alerts WHERE delivery_state IN "
                "('pending', 'retryable_failed') AND next_attempt_at <= ? "
                "ORDER BY next_attempt_at, created_at LIMIT 1",
                (instant.isoformat(),),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE dom_drift_alerts SET delivery_state = 'in_flight', "
                "attempt_count = attempt_count + 1, claimed_at = ?, next_attempt_at = NULL "
                "WHERE alert_id = ?",
                (instant.isoformat(), row["alert_id"]),
            )
            claimed = conn.execute(
                "SELECT * FROM dom_drift_alerts WHERE alert_id = ?", (row["alert_id"],)
            ).fetchone()
            assert claimed is not None
            return self._alert(claimed)

    def mark_alert_delivered(self, alert_id: uuid.UUID, delivered_at: datetime) -> bool:
        instant = _utc(delivered_at, "delivered_at")
        with self._immediate() as conn:
            cursor = conn.execute(
                "UPDATE dom_drift_alerts SET delivery_state = 'delivered', "
                "delivered_at = ?, failure_code = NULL WHERE alert_id = ? "
                "AND delivery_state = 'in_flight'",
                (instant.isoformat(), str(alert_id)),
            )
            return cursor.rowcount == 1

    def mark_alert_failed(
        self,
        alert_id: uuid.UUID,
        failure_code: DeliveryFailureCode,
        next_attempt_at: datetime | None,
    ) -> bool:
        next_time = (
            _utc(next_attempt_at, "next_attempt_at") if next_attempt_at is not None else None
        )
        state = DeliveryState.RETRYABLE_FAILED if next_time is not None else DeliveryState.FAILED
        with self._immediate() as conn:
            cursor = conn.execute(
                "UPDATE dom_drift_alerts SET delivery_state = ?, next_attempt_at = ?, "
                "failure_code = ? WHERE alert_id = ? AND delivery_state = 'in_flight'",
                (
                    state.value,
                    next_time.isoformat() if next_time is not None else None,
                    failure_code.value,
                    str(alert_id),
                ),
            )
            return cursor.rowcount == 1

    def recover_stale_claims(self, claimed_before: datetime) -> int:
        cutoff = _utc(claimed_before, "claimed_before")
        with self._immediate() as conn:
            cursor = conn.execute(
                "UPDATE dom_drift_alerts SET delivery_state = 'delivery_unknown', "
                "next_attempt_at = NULL, failure_code = NULL "
                "WHERE delivery_state = 'in_flight' AND claimed_at < ?",
                (cutoff.isoformat(),),
            )
            return cursor.rowcount

    def set_evidence_state(
        self, incident_id: uuid.UUID, evidence_state: EvidenceState
    ) -> bool:
        cursor = self._store.conn.execute(
            "UPDATE dom_drift_incidents SET evidence_state = ? WHERE incident_id = ?",
            (evidence_state.value, str(incident_id)),
        )
        self._store.conn.commit()
        return cursor.rowcount == 1

    def get_incident(self, incident_id: uuid.UUID) -> DomDriftIncident | None:
        row = self._store.conn.execute(
            "SELECT * FROM dom_drift_incidents WHERE incident_id = ?",
            (str(incident_id),),
        ).fetchone()
        return self._incident(row) if row is not None else None

    def list_incidents(self, limit: int = 50) -> tuple[DomDriftIncident, ...]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        rows = self._store.conn.execute(
            "SELECT * FROM dom_drift_incidents "
            "ORDER BY last_observed_at DESC, incident_id LIMIT ?", (limit,)
        ).fetchall()
        return tuple(self._incident(row) for row in rows)

    def status_projection(self) -> SqliteIncidentStatusProjection:
        row = self._store.conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM dom_drift_incidents WHERE state = 'open') open_count,
                (SELECT COUNT(*) FROM dom_drift_alerts
                 WHERE delivery_state IN (
                    'pending', 'retryable_failed', 'in_flight'
                 )) pending_count,
                (SELECT COUNT(*) FROM dom_drift_alerts
                 WHERE delivery_state = 'failed') failed_count,
                (SELECT COUNT(*) FROM dom_drift_incidents
                 WHERE evidence_state IN (
                    'unavailable', 'corrupt', 'undecryptable', 'oversized'
                 )) unavailable_count
            """
        ).fetchone()
        assert row is not None
        return SqliteIncidentStatusProjection(
            open_incidents=int(row["open_count"]),
            pending_alerts=int(row["pending_count"]),
            failed_alerts=int(row["failed_count"]),
            unavailable_evidence=int(row["unavailable_count"]),
        )

    @staticmethod
    def _incident(row: sqlite3.Row) -> DomDriftIncident:
        return DomDriftIncident(
            incident_id=uuid.UUID(row["incident_id"]),
            fingerprint=DomDriftFingerprint(row["fingerprint"]),
            journey=DomJourney(row["journey"]),
            step_id=DomStepId(row["registered_step"]),
            terminal_reason=TerminalBrowserReason(row["terminal_class"]),
            verifier_category=row["verifier_category"],
            structural_digest=StructuralDigest(row["structural_digest"]),
            model_roles=tuple(ModelRole(item) for item in json.loads(row["model_roles_json"])),
            provider_state=IncidentProviderState(row["provider_state"]),
            budget_state=IncidentBudgetState(row["budget_state"]),
            provenance=IncidentSourceProvenance(row["provenance"]),
            state=IncidentState(row["state"]),
            severity=IncidentSeverity(row["severity"]),
            recovered=bool(row["recovered"]),
            occurrence_count=int(row["occurrence_count"]),
            window_occurrence_count=int(row["window_occurrence_count"]),
            first_observed_at=datetime.fromisoformat(row["first_observed_at"]),
            last_observed_at=datetime.fromisoformat(row["last_observed_at"]),
            opened_at=_optional_time(row["opened_at"]),
            resolved_at=_optional_time(row["resolved_at"]),
            alert_suppressed_until=_optional_time(row["alert_suppressed_until"]),
            evidence_state=EvidenceState(row["evidence_state"]),
        )

    @staticmethod
    def _alert(row: sqlite3.Row) -> IncidentAlert:
        failure = row["failure_code"]
        return IncidentAlert(
            alert_id=uuid.UUID(row["alert_id"]),
            incident_id=uuid.UUID(row["incident_id"]),
            generation=int(row["generation"]),
            severity=IncidentSeverity(row["severity"]),
            delivery_state=DeliveryState(row["delivery_state"]),
            attempt_count=int(row["attempt_count"]),
            next_attempt_at=_optional_time(row["next_attempt_at"]),
            claimed_at=_optional_time(row["claimed_at"]),
            delivered_at=_optional_time(row["delivered_at"]),
            failure_code=DeliveryFailureCode(failure) if failure is not None else None,
        )
