from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet

from booksaver.domain.browser_resilience import (
    DomJourney,
    DomStepId,
    TerminalBrowserReason,
)
from booksaver.domain.dom_incident import (
    DiagnosticBundle,
    DiagnosticModelAttempt,
    DomDriftFingerprint,
    DomDriftOccurrence,
    EvidenceState,
    IncidentBudgetState,
    IncidentProviderState,
    IncidentSourceProvenance,
    StructuralDigest,
)
from booksaver.domain.model_policy import (
    OPUS_5_MODEL,
    SONNET_5_MODEL,
    EscalationTrigger,
    ModelAttemptOutcome,
    ModelProvider,
    ModelRole,
    ReservationStatus,
)
from booksaver.infrastructure.crypto.fernet_key_store import FernetKeyStore
from booksaver.infrastructure.persistence.dom_incident import SqliteDomIncidentRepository
from booksaver.infrastructure.persistence.encrypted_diagnostics import (
    DIAGNOSTIC_RETENTION,
    EncryptedDiagnosticStore,
)
from booksaver.infrastructure.persistence.sqlite_store import SqliteStore

NOW = datetime(2026, 8, 13, 4, 0, tzinfo=UTC)


def _key_store() -> FernetKeyStore:
    return FernetKeyStore(
        secret_key=Fernet.generate_key().decode("ascii"),
        purpose="DOM-drift diagnostic",
    )


def _open_incident(store: SqliteStore) -> uuid.UUID:
    result = SqliteDomIncidentRepository(store).correlate(
        DomDriftOccurrence(
            fingerprint=DomDriftFingerprint("a" * 64),
            journey=DomJourney.PRICE_SEARCH,
            step_id=DomStepId.PRICE_OFFER_EXTRACTION,
            terminal_reason=TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED,
            verifier_category="offer_structure_unknown",
            structural_digest=StructuralDigest("b" * 64),
            model_roles=(ModelRole.EXTRACTION, ModelRole.DIAGNOSTIC),
            provenance=IncidentSourceProvenance.CODE_MAINTENANCE_REQUIRED,
            provider_state=IncidentProviderState.COMPLETED,
            budget_state=IncidentBudgetState.WITHIN_LIMIT,
            recovered=False,
            observed_at=NOW,
        )
    )
    return result.incident.incident_id


def _bundle(incident_id: uuid.UUID, user_id: int = 7) -> DiagnosticBundle:
    return DiagnosticBundle(
        incident_id=incident_id,
        source_user_ids=(user_id,),
        structural_roles=("main", "property_card", "room_rate"),
        action_outcomes=("click_verified", "extraction_ambiguous"),
        terminal_reason=TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED,
        model_roles=(ModelRole.EXTRACTION, ModelRole.DIAGNOSTIC),
        provider_state=IncidentProviderState.COMPLETED,
        budget_state=IncidentBudgetState.WITHIN_LIMIT,
        created_at=NOW,
        model_attempts=(
            DiagnosticModelAttempt(
                ordinal=1,
                provider=ModelProvider.ANTHROPIC,
                model=SONNET_5_MODEL,
                role=ModelRole.EXTRACTION,
                trigger=EscalationTrigger.INITIAL_AMBIGUOUS,
                outcome=ModelAttemptOutcome.QUALITY_FAILED,
                status=ReservationStatus.CHARGED,
                input_tokens=123,
                output_tokens=45,
                latency_ms=678,
                reserved_micro_usd=900,
                charged_micro_usd=800,
            ),
            DiagnosticModelAttempt(
                ordinal=2,
                provider=ModelProvider.ANTHROPIC,
                model=OPUS_5_MODEL,
                role=ModelRole.DIAGNOSTIC,
                trigger=EscalationTrigger.UNRESOLVED_LOW_CONFIDENCE,
                outcome=ModelAttemptOutcome.DIAGNOSED,
                status=ReservationStatus.CHARGED,
                input_tokens=234,
                output_tokens=56,
                latency_ms=789,
                reserved_micro_usd=1900,
                charged_micro_usd=1800,
            ),
        ),
        structural_image=b"safe-structural-png",
    )


def test_bundle_is_ciphertext_only_and_round_trips_locally(tmp_path: Path) -> None:
    key_store = _key_store()
    with SqliteStore(tmp_path / "booksaver.db") as store:
        incident_id = _open_incident(store)
        diagnostics = EncryptedDiagnosticStore(store, key_store)
        bundle = _bundle(incident_id)

        assert diagnostics.put(bundle) is EvidenceState.AVAILABLE
        row = store.conn.execute(
            "SELECT ciphertext, byte_size, created_at, expires_at "
            "FROM dom_drift_diagnostics WHERE incident_id = ?",
            (str(incident_id),),
        ).fetchone()
        stored = bytes(row["ciphertext"])
        inspection = diagnostics.inspect(incident_id, NOW)

        assert b"property_card" not in stored
        assert b"safe-structural-png" not in stored
        assert b"source_user_ids" not in stored
        assert row["byte_size"] == len(stored)
        assert datetime.fromisoformat(row["expires_at"]) == NOW + timedelta(days=7)
        assert inspection.evidence_state is EvidenceState.AVAILABLE
        assert inspection.bundle == bundle


def test_plaintext_attempt_projection_omits_ledger_ids_and_provider_payloads(
    tmp_path: Path,
) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        incident_id = _open_incident(store)
        bundle = _bundle(incident_id)
        plaintext = EncryptedDiagnosticStore._serialize(bundle)

    assert b"reservation_id" not in plaintext
    assert b"job_id" not in plaintext
    assert b"prompt" not in plaintext
    assert b"response" not in plaintext
    assert b"exception" not in plaintext
    assert b"claude-sonnet-5" in plaintext
    assert b'"input_tokens":123' in plaintext


def test_first_bundle_is_immutable_when_incident_aggregates_users(tmp_path: Path) -> None:
    key_store = _key_store()
    with SqliteStore(tmp_path / "booksaver.db") as store:
        incident_id = _open_incident(store)
        diagnostics = EncryptedDiagnosticStore(store, key_store)
        diagnostics.put(_bundle(incident_id, user_id=7))
        diagnostics.put(_bundle(incident_id, user_id=8))

        inspection = diagnostics.inspect(incident_id, NOW)
        assert inspection.bundle is not None
        assert inspection.bundle.source_user_ids == (7,)
        assert store.conn.execute(
            "SELECT COUNT(*) FROM dom_drift_diagnostics"
        ).fetchone()[0] == 1


def test_exact_seven_day_boundary_deletes_evidence(tmp_path: Path) -> None:
    key_store = _key_store()
    with SqliteStore(tmp_path / "booksaver.db") as store:
        incident_id = _open_incident(store)
        diagnostics = EncryptedDiagnosticStore(store, key_store)
        diagnostics.put(_bundle(incident_id))

        before = diagnostics.inspect(
            incident_id, NOW + DIAGNOSTIC_RETENTION - timedelta(microseconds=1)
        )
        at_boundary = diagnostics.inspect(incident_id, NOW + DIAGNOSTIC_RETENTION)

        assert before.evidence_state is EvidenceState.AVAILABLE
        assert at_boundary.evidence_state is EvidenceState.EXPIRED
        assert store.conn.execute(
            "SELECT COUNT(*) FROM dom_drift_diagnostics"
        ).fetchone()[0] == 0


def test_startup_style_expiry_purge_marks_incident_without_removing_audit(
    tmp_path: Path,
) -> None:
    key_store = _key_store()
    with SqliteStore(tmp_path / "booksaver.db") as store:
        incident_id = _open_incident(store)
        diagnostics = EncryptedDiagnosticStore(store, key_store)
        diagnostics.put(_bundle(incident_id))

        assert diagnostics.purge_expired(NOW + DIAGNOSTIC_RETENTION) == 1
        incident = SqliteDomIncidentRepository(store).get_incident(incident_id)
        assert incident is not None
        assert incident.evidence_state is EvidenceState.EXPIRED


def test_missing_or_wrong_key_never_falls_back_to_plaintext(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("BOOKSAVER_SECRET_KEY", raising=False)
    with SqliteStore(tmp_path / "missing.db") as store:
        incident_id = _open_incident(store)
        diagnostics = EncryptedDiagnosticStore(store)
        assert diagnostics.put(_bundle(incident_id)) is EvidenceState.UNAVAILABLE
        assert store.conn.execute(
            "SELECT COUNT(*) FROM dom_drift_diagnostics"
        ).fetchone()[0] == 0

    with SqliteStore(tmp_path / "wrong.db") as store:
        incident_id = _open_incident(store)
        EncryptedDiagnosticStore(store, _key_store()).put(_bundle(incident_id))
        wrong = EncryptedDiagnosticStore(store, _key_store())
        inspection = wrong.inspect(incident_id, NOW)
        assert inspection.evidence_state is EvidenceState.UNDECRYPTABLE
        assert store.conn.execute(
            "SELECT COUNT(*) FROM dom_drift_diagnostics"
        ).fetchone()[0] == 1


def test_oversize_is_explicit_and_stores_no_ciphertext(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "booksaver.infrastructure.persistence.encrypted_diagnostics."
        "MAX_DIAGNOSTIC_PLAINTEXT_BYTES",
        10,
    )
    with SqliteStore(tmp_path / "booksaver.db") as store:
        incident_id = _open_incident(store)
        diagnostics = EncryptedDiagnosticStore(store, _key_store())
        assert diagnostics.put(_bundle(incident_id)) is EvidenceState.OVERSIZED
        assert store.conn.execute(
            "SELECT COUNT(*) FROM dom_drift_diagnostics"
        ).fetchone()[0] == 0


def test_user_purge_deletes_matching_and_all_undecryptable_evidence(
    tmp_path: Path,
) -> None:
    key_store = _key_store()
    with SqliteStore(tmp_path / "booksaver.db") as store:
        matching_id = _open_incident(store)
        diagnostics = EncryptedDiagnosticStore(store, key_store)
        diagnostics.put(_bundle(matching_id, user_id=7))

        # A second incident with a distinct fingerprint supplies ciphertext
        # encrypted under a now-unavailable key.
        occurrence = replace(
            DomDriftOccurrence(
                fingerprint=DomDriftFingerprint("c" * 64),
                journey=DomJourney.ACCOUNT_INVENTORY,
                step_id=DomStepId.INVENTORY_DETAIL,
                terminal_reason=TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED,
                verifier_category="inventory_detail_unknown",
                structural_digest=StructuralDigest("d" * 64),
                model_roles=(ModelRole.RECOVERY,),
                provenance=IncidentSourceProvenance.CODE_MAINTENANCE_REQUIRED,
                provider_state=IncidentProviderState.COMPLETED,
                budget_state=IncidentBudgetState.WITHIN_LIMIT,
                recovered=False,
                observed_at=NOW,
            )
        )
        other_id = SqliteDomIncidentRepository(store).correlate(occurrence).incident.incident_id
        EncryptedDiagnosticStore(store, _key_store()).put(_bundle(other_id, user_id=9))

        result = diagnostics.purge_for_user(7, NOW)

        assert result.deleted_matching == 1
        assert result.deleted_unverifiable == 1
        assert store.conn.execute(
            "SELECT COUNT(*) FROM dom_drift_diagnostics"
        ).fetchone()[0] == 0
        assert store.conn.execute(
            "SELECT COUNT(*) FROM dom_drift_incidents"
        ).fetchone()[0] == 2
