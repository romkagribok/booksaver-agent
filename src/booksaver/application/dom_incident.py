"""Application policy for content-free DOM-drift incident operations.

The browser layer may call :func:`build_incident_draft` while its sanitized
structural observation is still available.  Persistence and notification are
deliberately performed later, after browser cleanup, through the small ports in
this module.  Predictable failures never produce a draft.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from booksaver.domain.browser_resilience import (
    DiagnosisProvenance,
    DomJourney,
    DomStepId,
    TerminalBrowserDiagnosis,
    TerminalBrowserReason,
)
from booksaver.domain.dom_incident import (
    DeliveryFailureCode,
    DiagnosticBundle,
    DiagnosticModelAttempt,
    DomDriftFingerprint,
    DomDriftIncident,
    DomDriftOccurrence,
    EvidenceState,
    IncidentAlert,
    IncidentBudgetState,
    IncidentDraft,
    IncidentProviderState,
    IncidentSourceProvenance,
    OwnerIncidentNotice,
    StructuralDigest,
)
from booksaver.domain.model_policy import (
    EscalationTrigger,
    ModelAttemptAudit,
    ModelAttemptOutcome,
    ModelProvider,
    ModelRole,
)

logger = logging.getLogger(__name__)

_ZERO_UUID = UUID(int=0)
_ELIGIBLE_DIAGNOSED_REASONS = frozenset(
    {
        TerminalBrowserReason.UNSUPPORTED_PAGE,
        TerminalBrowserReason.UNRESOLVED_AMBIGUITY,
        TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED,
    }
)
_MODEL_DIAGNOSIS_PROVENANCE = frozenset(
    {
        DiagnosisProvenance.SONNET_DIAGNOSED,
        DiagnosisProvenance.OPUS_DIAGNOSED,
    }
)
_RETRY_DELAYS = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=30),
)


@dataclass(frozen=True, slots=True)
class CorrelationResult:
    incident: DomDriftIncident
    alert: IncidentAlert | None = None


class DomIncidentRepository(Protocol):
    def correlate(self, occurrence: DomDriftOccurrence) -> CorrelationResult: ...

    def resolve_deterministic_success(
        self, journey: DomJourney, step_id: DomStepId, observed_at: datetime
    ) -> int: ...

    def claim_next_alert(self, now: datetime) -> IncidentAlert | None: ...

    def mark_alert_delivered(self, alert_id: UUID, delivered_at: datetime) -> bool: ...

    def mark_alert_failed(
        self,
        alert_id: UUID,
        failure_code: DeliveryFailureCode,
        next_attempt_at: datetime | None,
    ) -> bool: ...

    def recover_stale_claims(self, claimed_before: datetime) -> int: ...

    def set_evidence_state(
        self, incident_id: UUID, evidence_state: EvidenceState
    ) -> bool: ...

    def get_incident(self, incident_id: UUID) -> DomDriftIncident | None: ...


class DiagnosticEvidenceStore(Protocol):
    def put(self, bundle: DiagnosticBundle) -> EvidenceState: ...

    def purge_expired(self, now: datetime) -> int: ...


class OwnerIncidentNotifier(Protocol):
    def send(self, notice: OwnerIncidentNotice) -> None: ...


class IncidentRepositoryFactory(Protocol):
    def __call__(self) -> AbstractContextManager[DomIncidentRepository]: ...


class DiagnosticStoreFactory(Protocol):
    def __call__(self) -> AbstractContextManager[DiagnosticEvidenceStore]: ...


@dataclass(frozen=True, slots=True)
class IncidentRecordResult:
    incident: DomDriftIncident
    alert: IncidentAlert | None
    evidence_state: EvidenceState


@dataclass(frozen=True, slots=True)
class IncidentLifecycleResult:
    stale_claims_recovered: int = 0
    evidence_expired: int = 0
    alerts_delivered: int = 0
    alerts_rescheduled: int = 0
    alerts_failed: int = 0


class OwnerIncidentDeliveryError(RuntimeError):
    """Typed delivery failure without provider response or source content."""

    def __init__(self, failure_code: DeliveryFailureCode) -> None:
        self.failure_code = failure_code
        super().__init__(failure_code.value)


def _safe_code(value: str, field: str) -> str:
    # Domain constructors perform the final check.  This local guard keeps
    # hashing functions from accepting arbitrary strings before construction.
    if not value or len(value) > 128 or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789._:-" for character in value
    ):
        raise ValueError(f"{field} must be a bounded machine code")
    if not value[0].isalnum() or value[0].isupper():
        raise ValueError(f"{field} must be a bounded machine code")
    return value


def structural_digest(structural_roles: Sequence[str]) -> StructuralDigest:
    """Digest an ordered, sanitized structural vocabulary without page text."""

    roles = tuple(_safe_code(role, "structural role") for role in structural_roles)
    if len(roles) > 128:
        raise ValueError("structural role count exceeds its bound")
    canonical = json.dumps(roles, separators=(",", ":"), ensure_ascii=True)
    return StructuralDigest(hashlib.sha256(canonical.encode("ascii")).hexdigest())


def dom_drift_fingerprint(
    *,
    journey: DomJourney,
    step_id: DomStepId,
    terminal_reason: TerminalBrowserReason,
    verifier_category: str,
    digest: StructuralDigest,
    model_roles: Sequence[ModelRole],
) -> DomDriftFingerprint:
    """Create the deployment-wide, user-independent correlation key."""

    verifier = _safe_code(verifier_category, "verifier_category")
    roles = tuple(model_roles)
    if not roles or any(not isinstance(role, ModelRole) for role in roles):
        raise ValueError("fingerprint requires ordered model roles")
    if len(set(roles)) != len(roles):
        raise ValueError("fingerprint model roles must be unique")
    canonical = json.dumps(
        {
            "journey": journey.value,
            "model_roles": [role.value for role in roles],
            "step": step_id.value,
            "structural_digest": digest.value,
            "terminal_class": terminal_reason.value,
            "verifier_category": verifier,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return DomDriftFingerprint(hashlib.sha256(canonical.encode("ascii")).hexdigest())


def model_roles_from_attempts(
    attempts: Sequence[ModelAttemptAudit],
) -> tuple[ModelRole, ...]:
    """Project Bolt 041's ordered safe audit into distinct roles tried."""

    if not attempts:
        raise ValueError("incident evidence requires at least one model attempt")
    roles: list[ModelRole] = []
    previous_ordinal = 0
    for attempt in attempts:
        if attempt.ordinal <= previous_ordinal:
            raise ValueError("model attempts must be in strictly increasing ordinal order")
        previous_ordinal = attempt.ordinal
        try:
            role = ModelRole(attempt.role)
        except ValueError as exc:
            raise ValueError("model attempt role must use the closed vocabulary") from exc
        if role not in roles:
            roles.append(role)
    return tuple(roles)


def diagnostic_attempts_from_audit(
    attempts: Sequence[ModelAttemptAudit],
) -> tuple[DiagnosticModelAttempt, ...]:
    """Strip ledger identifiers and retain only bounded operational evidence."""

    # Reuse the ordinal/role checks before projecting any fields.
    model_roles_from_attempts(attempts)
    projected: list[DiagnosticModelAttempt] = []
    for attempt in attempts:
        try:
            provider = ModelProvider(attempt.provider)
            role = ModelRole(attempt.role)
            trigger = EscalationTrigger(attempt.trigger)
            outcome = (
                ModelAttemptOutcome(attempt.outcome)
                if attempt.outcome is not None
                else None
            )
        except ValueError as exc:
            raise ValueError(
                "model attempt metadata must use the closed diagnostic vocabulary"
            ) from exc
        usage = attempt.usage
        projected.append(
            DiagnosticModelAttempt(
                ordinal=attempt.ordinal,
                provider=provider,
                model=attempt.model,
                role=role,
                trigger=trigger,
                outcome=outcome,
                status=attempt.status,
                input_tokens=usage.input_tokens if usage is not None else None,
                output_tokens=usage.output_tokens if usage is not None else None,
                latency_ms=attempt.latency_ms,
                reserved_micro_usd=attempt.reserved_cost.micro_usd,
                charged_micro_usd=(
                    attempt.charged_cost.micro_usd
                    if attempt.charged_cost is not None
                    else None
                ),
            )
        )
    return tuple(projected)


def incident_provenance(
    diagnosis: TerminalBrowserDiagnosis,
) -> IncidentSourceProvenance | None:
    """Return incident provenance only for ambiguous/model-assisted outcomes.

    The allowlist is intentionally narrow.  All exact authentication, MFA,
    bot-wall, provider, budget, time, observation, safety, business, and
    infrastructure outcomes are excluded without an explanation-only call.
    """

    if diagnosis.reason is TerminalBrowserReason.POSTCONDITION_SATISFIED:
        if diagnosis.provenance is DiagnosisProvenance.SONNET_RECOVERED:
            return IncidentSourceProvenance.SONNET_ASSISTED
        if diagnosis.provenance is DiagnosisProvenance.OPUS_RECOVERED:
            return IncidentSourceProvenance.OPUS_ASSISTED
    if (
        diagnosis.reason in _ELIGIBLE_DIAGNOSED_REASONS
        and diagnosis.provenance in _MODEL_DIAGNOSIS_PROVENANCE
    ):
        if diagnosis.reason is TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED:
            return IncidentSourceProvenance.CODE_MAINTENANCE_REQUIRED
        return IncidentSourceProvenance.MODEL_DIAGNOSED
    return None


def is_dom_incident_eligible(diagnosis: TerminalBrowserDiagnosis) -> bool:
    return incident_provenance(diagnosis) is not None


def build_incident_draft(
    *,
    journey: DomJourney,
    diagnosis: TerminalBrowserDiagnosis,
    verifier_category: str,
    structural_roles: Sequence[str],
    provider_state: IncidentProviderState,
    budget_state: IncidentBudgetState,
    observed_at: datetime,
    model_attempts: Sequence[ModelAttemptAudit] = (),
    model_roles: Sequence[ModelRole] = (),
    source_user_ids: Sequence[int] = (),
    action_outcomes: Sequence[str] = (),
    structural_image: bytes | None = None,
) -> IncidentDraft | None:
    """Build a sanitized draft, or ``None`` for every predictable outcome."""

    provenance = incident_provenance(diagnosis)
    if provenance is None:
        return None
    if model_attempts and model_roles:
        raise ValueError("provide ordered model attempts or model roles, not both")
    diagnostic_attempts = (
        diagnostic_attempts_from_audit(model_attempts) if model_attempts else ()
    )
    roles = (
        tuple(dict.fromkeys(attempt.role for attempt in diagnostic_attempts))
        if diagnostic_attempts
        else tuple(model_roles)
    )
    if not roles:
        raise ValueError("incident evidence requires at least one model role")
    structures = tuple(structural_roles)
    digest = structural_digest(structures)
    occurrence = DomDriftOccurrence(
        fingerprint=dom_drift_fingerprint(
            journey=journey,
            step_id=diagnosis.step_id,
            terminal_reason=diagnosis.reason,
            verifier_category=verifier_category,
            digest=digest,
            model_roles=roles,
        ),
        journey=journey,
        step_id=diagnosis.step_id,
        terminal_reason=diagnosis.reason,
        verifier_category=verifier_category,
        structural_digest=digest,
        model_roles=roles,
        provenance=provenance,
        provider_state=provider_state,
        budget_state=budget_state,
        recovered=diagnosis.provenance
        in {
            DiagnosisProvenance.SONNET_RECOVERED,
            DiagnosisProvenance.OPUS_RECOVERED,
        },
        observed_at=observed_at,
    )
    bundle = None
    if source_user_ids:
        bundle = DiagnosticBundle(
            incident_id=_ZERO_UUID,
            source_user_ids=tuple(source_user_ids),
            structural_roles=structures,
            action_outcomes=tuple(action_outcomes),
            terminal_reason=diagnosis.reason,
            model_roles=roles,
            provider_state=provider_state,
            budget_state=budget_state,
            created_at=observed_at,
            model_attempts=diagnostic_attempts,
            structural_image=structural_image,
        )
    elif action_outcomes or structural_image is not None:
        raise ValueError("diagnostic evidence requires encrypted source linkage")
    return IncidentDraft(occurrence=occurrence, diagnostic_bundle=bundle)


def owner_incident_notice(incident: DomDriftIncident) -> OwnerIncidentNotice:
    """Project an incident into the closed owner-notification vocabulary."""

    return OwnerIncidentNotice(
        incident_id=incident.incident_id,
        journey=incident.journey,
        step_id=incident.step_id,
        category=incident.terminal_reason,
        recovered=incident.recovered,
        occurrence_count=incident.occurrence_count,
        model_roles=incident.model_roles,
        provider_state=incident.provider_state,
        budget_state=incident.budget_state,
        evidence_state=incident.evidence_state,
    )


class DomIncidentRecorder:
    """Correlate a post-cleanup draft and persist at most one encrypted bundle."""

    def __init__(
        self,
        *,
        incidents: DomIncidentRepository,
        diagnostics: DiagnosticEvidenceStore,
    ) -> None:
        self._incidents = incidents
        self._diagnostics = diagnostics

    def record(self, draft: IncidentDraft) -> IncidentRecordResult:
        correlated = self._incidents.correlate(draft.occurrence)
        incident = correlated.incident
        evidence_state = incident.evidence_state
        if draft.diagnostic_bundle is None:
            if evidence_state is EvidenceState.PENDING:
                self._incidents.set_evidence_state(
                    incident.incident_id, EvidenceState.UNAVAILABLE
                )
                evidence_state = EvidenceState.UNAVAILABLE
        elif evidence_state is EvidenceState.PENDING:
            bundle = replace(draft.diagnostic_bundle, incident_id=incident.incident_id)
            try:
                evidence_state = self._diagnostics.put(bundle)
            except Exception:
                # Diagnostics are best-effort and must never change a completed
                # caller result.  Do not include exception text in the log.
                self._incidents.set_evidence_state(
                    incident.incident_id, EvidenceState.UNAVAILABLE
                )
                evidence_state = EvidenceState.UNAVAILABLE
                logger.warning(
                    "DOM incident diagnostic persistence failed for incident %s",
                    incident.incident_id,
                )
        return IncidentRecordResult(incident, correlated.alert, evidence_state)

    def record_safely(self, draft: IncidentDraft) -> IncidentRecordResult | None:
        """Post-cleanup sink boundary that never alters caller completion."""

        try:
            return self.record(draft)
        except Exception:
            # The draft contains no persisted identifier until correlation, so
            # log only a fixed event rather than source or exception content.
            logger.warning("DOM incident post-cleanup recording failed")
            return None

    def resolve_deterministic_success(
        self, *, journey: DomJourney, step_id: DomStepId, observed_at: datetime
    ) -> int:
        return self._incidents.resolve_deterministic_success(
            journey, step_id, observed_at
        )


class DomIncidentLifecycleWorker:
    """Retry owner alerts and enforce evidence retention outside browser work."""

    def __init__(
        self,
        *,
        incident_repository_factory: IncidentRepositoryFactory,
        diagnostic_store_factory: DiagnosticStoreFactory,
        notifier: OwnerIncidentNotifier,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        stale_claim_after: timedelta = timedelta(minutes=5),
        maintenance_interval: timedelta = timedelta(days=1),
        max_alerts_per_run: int = 20,
    ) -> None:
        if stale_claim_after <= timedelta(0):
            raise ValueError("stale_claim_after must be positive")
        if maintenance_interval <= timedelta(0):
            raise ValueError("maintenance_interval must be positive")
        if max_alerts_per_run < 1:
            raise ValueError("max_alerts_per_run must be positive")
        self._incident_repository_factory = incident_repository_factory
        self._diagnostic_store_factory = diagnostic_store_factory
        self._notifier = notifier
        self._now = now
        self._stale_claim_after = stale_claim_after
        self._maintenance_interval = maintenance_interval
        self._max_alerts_per_run = max_alerts_per_run
        self._started = False
        self._last_maintenance: datetime | None = None

    def run_once(self, now: datetime | None = None) -> IncidentLifecycleResult:
        instant = now or self._now()
        expired = 0
        if (
            self._last_maintenance is None
            or instant - self._last_maintenance >= self._maintenance_interval
        ):
            with self._diagnostic_store_factory() as diagnostics:
                expired = diagnostics.purge_expired(instant)
            self._last_maintenance = instant

        with self._incident_repository_factory() as incidents:
            stale = 0
            if not self._started:
                stale = incidents.recover_stale_claims(
                    instant - self._stale_claim_after
                )
                self._started = True

            delivered = rescheduled = failed = 0
            for _ in range(self._max_alerts_per_run):
                alert = incidents.claim_next_alert(instant)
                if alert is None:
                    break
                incident = incidents.get_incident(alert.incident_id)
                if incident is None:
                    incidents.mark_alert_failed(
                        alert.alert_id, DeliveryFailureCode.PROVIDER_REJECTED, None
                    )
                    failed += 1
                    continue
                try:
                    self._notifier.send(owner_incident_notice(incident))
                except OwnerIncidentDeliveryError as exc:
                    failure_code = exc.failure_code
                except Exception:
                    # Provider response and exception text are never logged.
                    failure_code = DeliveryFailureCode.TRANSPORT_UNAVAILABLE
                else:
                    incidents.mark_alert_delivered(alert.alert_id, instant)
                    delivered += 1
                    continue

                next_attempt = self._next_attempt(alert.attempt_count, instant)
                terminal_code = (
                    failure_code
                    if next_attempt is not None
                    else DeliveryFailureCode.RETRIES_EXHAUSTED
                )
                incidents.mark_alert_failed(
                    alert.alert_id, terminal_code, next_attempt
                )
                if next_attempt is None:
                    failed += 1
                else:
                    rescheduled += 1
                logger.warning(
                    "Owner DOM incident alert delivery failed for incident %s (%s)",
                    alert.incident_id,
                    terminal_code.value,
                )

        return IncidentLifecycleResult(
            stale_claims_recovered=stale,
            evidence_expired=expired,
            alerts_delivered=delivered,
            alerts_rescheduled=rescheduled,
            alerts_failed=failed,
        )

    @staticmethod
    def _next_attempt(attempt_count: int, now: datetime) -> datetime | None:
        if attempt_count < 1 or attempt_count > len(_RETRY_DELAYS):
            return None
        return now + _RETRY_DELAYS[attempt_count - 1]

    def run(self, stop_event: threading.Event, *, poll_seconds: float = 5.0) -> None:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        while not stop_event.is_set():
            try:
                self.run_once()
            except Exception:
                # The lifecycle is isolated from browser cleanup and the daemon
                # supervisor; log no source/provider exception detail.
                logger.error("DOM incident lifecycle iteration failed")
            stop_event.wait(poll_seconds)
