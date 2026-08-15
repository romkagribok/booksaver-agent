from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from booksaver.domain.browser_resilience import (
    DomJourney,
    DomStepId,
    TerminalBrowserReason,
)
from booksaver.domain.dom_incident import (
    DeliveryState,
    DomDriftFingerprint,
    DomDriftOccurrence,
    IncidentBudgetState,
    IncidentProviderState,
    IncidentSeverity,
    IncidentSourceProvenance,
    IncidentState,
    StructuralDigest,
)
from booksaver.domain.model_policy import ModelRole
from booksaver.infrastructure.persistence.dom_incident import (
    SqliteDomIncidentRepository,
)
from booksaver.infrastructure.persistence.sqlite_store import SqliteStore

NOW = datetime(2026, 8, 13, 3, 0, tzinfo=UTC)
FINGERPRINT = "1" * 64
STRUCTURAL_DIGEST = "2" * 64


def _occurrence(
    observed_at: datetime = NOW,
    *,
    provenance: IncidentSourceProvenance = IncidentSourceProvenance.SONNET_ASSISTED,
) -> DomDriftOccurrence:
    return DomDriftOccurrence(
        fingerprint=DomDriftFingerprint(FINGERPRINT),
        journey=DomJourney.ACCOUNT_INVENTORY,
        step_id=DomStepId.INVENTORY_SCOPE,
        terminal_reason=(
            TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED
            if provenance is IncidentSourceProvenance.CODE_MAINTENANCE_REQUIRED
            else TerminalBrowserReason.UNRESOLVED_AMBIGUITY
        ),
        verifier_category="inventory_scope_unknown",
        structural_digest=StructuralDigest(STRUCTURAL_DIGEST),
        model_roles=(ModelRole.CLASSIFICATION, ModelRole.RECOVERY),
        provenance=provenance,
        provider_state=IncidentProviderState.COMPLETED,
        budget_state=IncidentBudgetState.WITHIN_LIMIT,
        recovered=False,
        observed_at=observed_at,
    )


def test_maintenance_diagnosis_opens_immediately_and_deduplicates_alert(tmp_path: Path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        repo = SqliteDomIncidentRepository(store)
        first = repo.correlate(
            _occurrence(
                provenance=IncidentSourceProvenance.CODE_MAINTENANCE_REQUIRED
            )
        )
        second = repo.correlate(
            _occurrence(
                NOW + timedelta(minutes=1),
                provenance=IncidentSourceProvenance.CODE_MAINTENANCE_REQUIRED,
            )
        )

        assert first.incident.state is IncidentState.OPEN
        assert first.incident.severity is IncidentSeverity.MAINTENANCE_REQUIRED
        assert first.alert is not None
        assert second.incident.incident_id == first.incident.incident_id
        assert second.incident.occurrence_count == 2
        assert second.alert is None
        assert store.conn.execute("SELECT COUNT(*) FROM dom_drift_alerts").fetchone()[0] == 1


def test_model_free_server_contract_maintenance_opens_immediately(tmp_path: Path) -> None:
    occurrence = DomDriftOccurrence(
        fingerprint=DomDriftFingerprint("3" * 64),
        journey=DomJourney.REMOTE_AUTH,
        step_id=DomStepId.REMOTE_AUTH_SESSION_CAPTURE,
        terminal_reason=TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED,
        verifier_category="remote_auth_server_contract_v1",
        structural_digest=StructuralDigest("4" * 64),
        model_roles=(),
        provenance=IncidentSourceProvenance.CODE_MAINTENANCE_REQUIRED,
        provider_state=IncidentProviderState.NOT_ATTEMPTED,
        budget_state=IncidentBudgetState.NOT_APPLICABLE,
        recovered=False,
        observed_at=NOW,
    )

    with SqliteStore(tmp_path / "booksaver.db") as store:
        result = SqliteDomIncidentRepository(store).correlate(occurrence)

    assert result.incident.state is IncidentState.OPEN
    assert result.incident.model_roles == ()
    assert result.alert is not None


def test_assisted_drift_opens_on_second_identical_occurrence_within_six_hours(
    tmp_path: Path,
) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        repo = SqliteDomIncidentRepository(store)
        first = repo.correlate(_occurrence())
        second = repo.correlate(_occurrence(NOW + timedelta(hours=5, minutes=59)))

        assert first.incident.state is IncidentState.OBSERVING
        assert first.alert is None
        assert second.incident.state is IncidentState.OPEN
        assert second.incident.window_occurrence_count == 2
        assert second.alert is not None


def test_occurrences_outside_window_do_not_reach_initial_threshold(tmp_path: Path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        repo = SqliteDomIncidentRepository(store)
        repo.correlate(_occurrence())
        second = repo.correlate(_occurrence(NOW + timedelta(hours=6)))

        assert second.incident.state is IncidentState.OBSERVING
        assert second.incident.window_occurrence_count == 1
        assert second.alert is None


def test_deterministic_success_resolves_and_suppresses_pending_alert(tmp_path: Path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        repo = SqliteDomIncidentRepository(store)
        result = repo.correlate(
            _occurrence(
                provenance=IncidentSourceProvenance.CODE_MAINTENANCE_REQUIRED
            )
        )
        assert result.alert is not None

        count = repo.resolve_deterministic_success(
            DomJourney.ACCOUNT_INVENTORY,
            DomStepId.INVENTORY_SCOPE,
            NOW + timedelta(minutes=1),
        )
        resolved = repo.get_incident(result.incident.incident_id)
        alert_state = store.conn.execute(
            "SELECT delivery_state FROM dom_drift_alerts WHERE alert_id = ?",
            (str(result.alert.alert_id),),
        ).fetchone()[0]

        assert count == 1
        assert resolved is not None and resolved.state is IncidentState.RESOLVED
        assert alert_state == DeliveryState.SUPPRESSED.value


def test_claim_is_transactional_and_restart_state_is_durable(tmp_path: Path) -> None:
    db_path = tmp_path / "booksaver.db"
    with SqliteStore(db_path) as store:
        repo = SqliteDomIncidentRepository(store)
        result = repo.correlate(
            _occurrence(
                provenance=IncidentSourceProvenance.CODE_MAINTENANCE_REQUIRED
            )
        )
        assert result.alert is not None
        claimed = repo.claim_next_alert(NOW)
        assert claimed is not None
        assert claimed.delivery_state is DeliveryState.IN_FLIGHT
        assert claimed.attempt_count == 1
        assert repo.claim_next_alert(NOW) is None

    with SqliteStore(db_path) as store:
        repo = SqliteDomIncidentRepository(store)
        assert repo.claim_next_alert(NOW) is None
        assert repo.recover_stale_claims(NOW + timedelta(minutes=1)) == 1
        row = store.conn.execute(
            "SELECT delivery_state FROM dom_drift_alerts WHERE alert_id = ?",
            (str(result.alert.alert_id),),
        ).fetchone()
        assert row[0] == DeliveryState.DELIVERY_UNKNOWN.value


def test_simultaneous_occurrences_share_one_incident_and_one_alert(tmp_path: Path) -> None:
    db_path = tmp_path / "booksaver.db"
    with SqliteStore(db_path):
        pass

    def record(offset: int) -> str:
        with SqliteStore(db_path) as store:
            result = SqliteDomIncidentRepository(store).correlate(
                _occurrence(
                    NOW + timedelta(milliseconds=offset),
                    provenance=IncidentSourceProvenance.CODE_MAINTENANCE_REQUIRED,
                )
            )
            return str(result.incident.incident_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        incident_ids = tuple(executor.map(record, (0, 1)))

    with SqliteStore(db_path) as store:
        assert len(set(incident_ids)) == 1
        assert store.conn.execute(
            "SELECT COUNT(*) FROM dom_drift_incidents"
        ).fetchone()[0] == 1
        assert store.conn.execute("SELECT COUNT(*) FROM dom_drift_alerts").fetchone()[0] == 1
        assert store.conn.execute(
            "SELECT occurrence_count FROM dom_drift_incidents"
        ).fetchone()[0] == 2


def test_simultaneous_claimers_cannot_claim_the_same_alert(tmp_path: Path) -> None:
    db_path = tmp_path / "booksaver.db"
    with SqliteStore(db_path) as store:
        SqliteDomIncidentRepository(store).correlate(
            _occurrence(
                provenance=IncidentSourceProvenance.CODE_MAINTENANCE_REQUIRED
            )
        )

    def claim(_: int) -> str | None:
        with SqliteStore(db_path) as store:
            alert = SqliteDomIncidentRepository(store).claim_next_alert(NOW)
            return str(alert.alert_id) if alert is not None else None

    with ThreadPoolExecutor(max_workers=2) as executor:
        claimed = tuple(executor.map(claim, (0, 1)))

    assert sum(value is not None for value in claimed) == 1


def test_fingerprint_cannot_be_reused_for_different_safe_classifier_fields(
    tmp_path: Path,
) -> None:
    import pytest

    with SqliteStore(tmp_path / "booksaver.db") as store:
        repo = SqliteDomIncidentRepository(store)
        repo.correlate(_occurrence())
        conflicting = DomDriftOccurrence(
            fingerprint=DomDriftFingerprint(FINGERPRINT),
            journey=DomJourney.PRICE_SEARCH,
            step_id=DomStepId.PRICE_SEARCH_RESULTS,
            terminal_reason=TerminalBrowserReason.UNRESOLVED_AMBIGUITY,
            verifier_category="search_results_unknown",
            structural_digest=StructuralDigest(STRUCTURAL_DIGEST),
            model_roles=(ModelRole.CLASSIFICATION, ModelRole.RECOVERY),
            provenance=IncidentSourceProvenance.SONNET_ASSISTED,
            provider_state=IncidentProviderState.COMPLETED,
            budget_state=IncidentBudgetState.WITHIN_LIMIT,
            recovered=False,
            observed_at=NOW + timedelta(minutes=1),
        )

        with pytest.raises(ValueError, match="fingerprint"):
            repo.correlate(conflicting)

        assert store.conn.execute(
            "SELECT occurrence_count FROM dom_drift_incidents"
        ).fetchone()[0] == 1
