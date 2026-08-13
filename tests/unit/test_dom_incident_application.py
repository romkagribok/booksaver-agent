from __future__ import annotations

from contextlib import nullcontext
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from booksaver.application.dom_incident import (
    DomIncidentLifecycleWorker,
    DomIncidentRecorder,
    IncidentRecordResult,
    build_incident_draft,
    diagnostic_attempts_from_audit,
    dom_drift_fingerprint,
    is_dom_incident_eligible,
    model_roles_from_attempts,
    owner_incident_notice,
    structural_digest,
)
from booksaver.domain.browser_resilience import (
    DiagnosisProvenance,
    DomJourney,
    DomStepId,
    OperatorAction,
    TerminalBrowserDiagnosis,
    TerminalBrowserReason,
)
from booksaver.domain.dom_incident import (
    DeliveryFailureCode,
    DeliveryState,
    DomDriftIncident,
    EvidenceState,
    IncidentAlert,
    IncidentBudgetState,
    IncidentProviderState,
    IncidentSeverity,
    IncidentSourceProvenance,
    IncidentState,
)
from booksaver.domain.model_policy import (
    ModelAttemptAudit,
    ModelRole,
    ReservationStatus,
    UsdAmount,
)

NOW = datetime(2026, 8, 13, 3, 0, tzinfo=UTC)


def _attempt(ordinal: int, role: ModelRole) -> ModelAttemptAudit:
    return ModelAttemptAudit(
        reservation_id=f"reservation-{ordinal}",
        job_id="job-1",
        ordinal=ordinal,
        provider="anthropic",
        model="claude-sonnet-5",
        role=role.value,
        trigger="initial_ambiguous",
        outcome="completed",
        status=ReservationStatus.CHARGED,
        reserved_cost=UsdAmount(1),
        charged_cost=UsdAmount(1),
        usage=None,
        latency_ms=1,
    )


def _diagnosis(
    reason: TerminalBrowserReason,
    provenance: DiagnosisProvenance,
) -> TerminalBrowserDiagnosis:
    action = (
        OperatorAction.MAINTAIN_CODE
        if reason
        in {
            TerminalBrowserReason.UNSUPPORTED_PAGE,
            TerminalBrowserReason.UNRESOLVED_AMBIGUITY,
            TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED,
        }
        else OperatorAction.CONNECT
        if reason is TerminalBrowserReason.AUTHENTICATION_REQUIRED
        else OperatorAction.NONE
    )
    return TerminalBrowserDiagnosis(
        reason=reason,
        step_id=DomStepId.INVENTORY_SCOPE,
        provenance=provenance,
        confidence=1.0,
        evidence=frozenset(),
        operator_action=action,
        code_maintenance_required=(
            reason is TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED
        ),
    )


def _draft():
    draft = build_incident_draft(
        journey=DomJourney.ACCOUNT_INVENTORY,
        diagnosis=_diagnosis(
            TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED,
            DiagnosisProvenance.SONNET_DIAGNOSED,
        ),
        verifier_category="inventory_scope_unknown",
        structural_roles=("main", "list", "reservation_card"),
        model_attempts=(
            _attempt(1, ModelRole.CLASSIFICATION),
            _attempt(2, ModelRole.DIAGNOSTIC),
        ),
        provider_state=IncidentProviderState.COMPLETED,
        budget_state=IncidentBudgetState.WITHIN_LIMIT,
        observed_at=NOW,
        source_user_ids=(42,),
        action_outcomes=("no_progress",),
    )
    assert draft is not None
    return draft


def _incident(draft=None) -> DomDriftIncident:
    draft = draft or _draft()
    occurrence = draft.occurrence
    return DomDriftIncident(
        incident_id=uuid4(),
        fingerprint=occurrence.fingerprint,
        journey=occurrence.journey,
        step_id=occurrence.step_id,
        terminal_reason=occurrence.terminal_reason,
        verifier_category=occurrence.verifier_category,
        structural_digest=occurrence.structural_digest,
        model_roles=occurrence.model_roles,
        provider_state=occurrence.provider_state,
        budget_state=occurrence.budget_state,
        provenance=occurrence.provenance,
        state=IncidentState.OPEN,
        severity=IncidentSeverity.MAINTENANCE_REQUIRED,
        recovered=occurrence.recovered,
        occurrence_count=2,
        window_occurrence_count=2,
        first_observed_at=NOW,
        last_observed_at=NOW,
        opened_at=NOW,
        resolved_at=None,
        alert_suppressed_until=NOW + timedelta(hours=6),
        evidence_state=EvidenceState.PENDING,
    )


class _Correlation:
    def __init__(self, incident: DomDriftIncident, alert: IncidentAlert | None = None):
        self.incident = incident
        self.alert = alert


class _Incidents:
    def __init__(self, incident: DomDriftIncident, alerts=()):
        self.incident = incident
        self.alerts = list(alerts)
        self.evidence_states = []
        self.failed = []
        self.delivered = []
        self.recovered = 0

    def correlate(self, occurrence):
        return _Correlation(self.incident)

    def resolve_deterministic_success(self, journey, step_id, observed_at):
        return 1

    def claim_next_alert(self, now):
        return self.alerts.pop(0) if self.alerts else None

    def mark_alert_delivered(self, alert_id, delivered_at):
        self.delivered.append((alert_id, delivered_at))
        return True

    def mark_alert_failed(self, alert_id, failure_code, next_attempt_at):
        self.failed.append((alert_id, failure_code, next_attempt_at))
        return True

    def recover_stale_claims(self, claimed_before):
        self.recovered += 1
        return 2

    def set_evidence_state(self, incident_id, evidence_state):
        self.evidence_states.append((incident_id, evidence_state))
        self.incident = replace(self.incident, evidence_state=evidence_state)
        return True

    def get_incident(self, incident_id):
        return self.incident if incident_id == self.incident.incident_id else None


class _Diagnostics:
    def __init__(self):
        self.bundles = []
        self.purge_calls = []

    def put(self, bundle):
        self.bundles.append(bundle)
        return EvidenceState.AVAILABLE

    def purge_expired(self, now):
        self.purge_calls.append(now)
        return 3


class _Notifier:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.notices = []

    def send(self, notice):
        self.notices.append(notice)
        if self.error is not None:
            raise self.error


def test_predictable_failure_is_rejected_before_diagnostic_processing() -> None:
    diagnosis = _diagnosis(
        TerminalBrowserReason.AUTHENTICATION_REQUIRED,
        DiagnosisProvenance.DETERMINISTIC,
    )

    assert not is_dom_incident_eligible(diagnosis)
    assert (
        build_incident_draft(
            journey=DomJourney.ACCOUNT_INVENTORY,
            diagnosis=diagnosis,
            verifier_category="would not be safe text",
            structural_roles=("https://private.example/path?token=secret",),
            model_attempts=(),
            provider_state=IncidentProviderState.NOT_ATTEMPTED,
            budget_state=IncidentBudgetState.NOT_APPLICABLE,
            observed_at=NOW,
        )
        is None
    )


def test_maintenance_draft_is_content_free_and_source_independent() -> None:
    first = _draft()
    second = build_incident_draft(
        journey=first.occurrence.journey,
        diagnosis=_diagnosis(
            TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED,
            DiagnosisProvenance.SONNET_DIAGNOSED,
        ),
        verifier_category=first.occurrence.verifier_category,
        structural_roles=("main", "list", "reservation_card"),
        model_attempts=(
            _attempt(1, ModelRole.CLASSIFICATION),
            _attempt(2, ModelRole.DIAGNOSTIC),
        ),
        provider_state=IncidentProviderState.COMPLETED,
        budget_state=IncidentBudgetState.WITHIN_LIMIT,
        observed_at=NOW,
        source_user_ids=(99,),
    )

    assert second is not None
    assert first.occurrence.fingerprint == second.occurrence.fingerprint
    assert (
        first.occurrence.provenance
        is IncidentSourceProvenance.CODE_MAINTENANCE_REQUIRED
    )
    assert first.diagnostic_bundle is not None
    assert first.diagnostic_bundle.incident_id == UUID(int=0)
    assert first.diagnostic_bundle.source_user_ids == (42,)


def test_opus_assisted_success_creates_a_recovered_occurrence() -> None:
    draft = build_incident_draft(
        journey=DomJourney.ACCOUNT_INVENTORY,
        diagnosis=_diagnosis(
            TerminalBrowserReason.POSTCONDITION_SATISFIED,
            DiagnosisProvenance.OPUS_RECOVERED,
        ),
        verifier_category="inventory_scope_verified",
        structural_roles=("main", "list"),
        model_attempts=(
            _attempt(1, ModelRole.RECOVERY),
            replace(_attempt(2, ModelRole.RECOVERY), model="claude-opus-5"),
        ),
        provider_state=IncidentProviderState.COMPLETED,
        budget_state=IncidentBudgetState.WITHIN_LIMIT,
        observed_at=NOW,
    )

    assert draft is not None
    assert draft.occurrence.recovered
    assert draft.occurrence.provenance is IncidentSourceProvenance.OPUS_ASSISTED


def test_ordered_model_roles_are_part_of_fingerprint() -> None:
    digest = structural_digest(("main", "list"))
    common = dict(
        journey=DomJourney.ACCOUNT_INVENTORY,
        step_id=DomStepId.INVENTORY_SCOPE,
        terminal_reason=TerminalBrowserReason.UNRESOLVED_AMBIGUITY,
        verifier_category="inventory_scope_unknown",
        digest=digest,
    )

    first = dom_drift_fingerprint(
        **common, model_roles=(ModelRole.CLASSIFICATION, ModelRole.DIAGNOSTIC)
    )
    second = dom_drift_fingerprint(
        **common, model_roles=(ModelRole.DIAGNOSTIC, ModelRole.CLASSIFICATION)
    )

    assert first != second


def test_ordered_attempt_audit_projects_distinct_roles_without_model_names() -> None:
    attempts = (
        _attempt(1, ModelRole.RECOVERY),
        replace(_attempt(2, ModelRole.RECOVERY), model="claude-opus-5"),
        replace(_attempt(3, ModelRole.DIAGNOSTIC), model="claude-opus-5"),
    )

    assert model_roles_from_attempts(attempts) == (
        ModelRole.RECOVERY,
        ModelRole.DIAGNOSTIC,
    )


def test_diagnostic_attempt_projection_strips_ledger_and_source_fields() -> None:
    audit = replace(
        _attempt(1, ModelRole.RECOVERY),
        reservation_id="reservation-secret",
        job_id="job-secret",
    )

    projected = diagnostic_attempts_from_audit((audit,))[0]

    names = {field.name for field in fields(projected)}
    assert "reservation_id" not in names
    assert "job_id" not in names
    assert "prompt" not in names
    assert "response" not in names
    assert projected.ordinal == 1
    assert projected.role is ModelRole.RECOVERY


def test_diagnostic_attempt_projection_rejects_unapproved_model() -> None:
    audit = replace(_attempt(1, ModelRole.RECOVERY), model="fable")

    with pytest.raises(ValueError, match="approved model identity"):
        diagnostic_attempts_from_audit((audit,))


def test_recorder_assigns_incident_id_before_encrypted_evidence_put() -> None:
    draft = _draft()
    incident = _incident(draft)
    incidents = _Incidents(incident)
    diagnostics = _Diagnostics()

    result = DomIncidentRecorder(
        incidents=incidents, diagnostics=diagnostics
    ).record(draft)

    assert isinstance(result, IncidentRecordResult)
    assert result.evidence_state is EvidenceState.AVAILABLE
    assert diagnostics.bundles[0].incident_id == incident.incident_id
    assert diagnostics.bundles[0].source_user_ids == (42,)


def test_lifecycle_recovers_once_purges_daily_and_retries_without_error_text(
    caplog,
) -> None:
    incident = _incident()
    alert = IncidentAlert(
        alert_id=uuid4(),
        incident_id=incident.incident_id,
        generation=1,
        severity=IncidentSeverity.MAINTENANCE_REQUIRED,
        delivery_state=DeliveryState.IN_FLIGHT,
        attempt_count=1,
        next_attempt_at=None,
        claimed_at=NOW,
        delivered_at=None,
        failure_code=None,
    )
    incidents = _Incidents(incident, alerts=(alert,))
    diagnostics = _Diagnostics()
    worker = DomIncidentLifecycleWorker(
        incident_repository_factory=lambda: nullcontext(incidents),
        diagnostic_store_factory=lambda: nullcontext(diagnostics),
        notifier=_Notifier(RuntimeError("private provider response")),
    )

    first = worker.run_once(NOW)
    second = worker.run_once(NOW + timedelta(hours=1))

    assert first.stale_claims_recovered == 2
    assert first.evidence_expired == 3
    assert first.alerts_rescheduled == 1
    assert second.stale_claims_recovered == 0
    assert second.evidence_expired == 0
    assert incidents.recovered == 1
    assert diagnostics.purge_calls == [NOW]
    assert incidents.failed == [
        (
            alert.alert_id,
            DeliveryFailureCode.TRANSPORT_UNAVAILABLE,
            NOW + timedelta(minutes=1),
        )
    ]
    assert "private provider response" not in caplog.text


def test_owner_notice_is_a_closed_projection() -> None:
    incident = _incident()

    notice = owner_incident_notice(incident)

    assert notice.incident_id == incident.incident_id
    assert notice.category is TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED
    assert notice.occurrence_count == 2
    assert notice.model_roles == incident.model_roles
