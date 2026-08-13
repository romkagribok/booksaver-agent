from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from booksaver.application.account_sync import SynchronizeBookingAccount
from booksaver.application.browser_resilience import DOM_STEP_REGISTRY
from booksaver.application.dom_incident import build_incident_draft, is_dom_incident_eligible
from booksaver.application.model_policy import BrowserJobCostBudget, SpendLedger
from booksaver.application.ports import AgentBrain, InventoryInterpreter
from booksaver.application.savings_pipeline import NotificationDispatcher, SavingsPipeline
from booksaver.application.user_sessions import (
    AuthenticatedSessionProvider,
    UserSessionRepository,
)
from booksaver.domain.account_sync import (
    AccountReservation,
    InventoryCompleteness,
    InventoryDiscoveryResult,
    InventoryRecoveryAudit,
    InventoryRecoveryOutcome,
    SynchronizationFailureCode,
    SynchronizationReport,
    SynchronizationTrigger,
)
from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    AgentBudget,
    AgentHistoryOutcome,
    AgentStopReason,
    AgentTurnContext,
    BudgetExceeded,
    CheckTrace,
    TraceKind,
)
from booksaver.domain.browser_resilience import (
    DomJourney,
    DomStepId,
    TerminalBrowserDiagnosis,
    TerminalBrowserReason,
)
from booksaver.domain.check_result import CheckResult, FailureCode, FailureReason
from booksaver.domain.dom_incident import (
    IncidentBudgetState,
    IncidentDraft,
    IncidentProviderState,
)
from booksaver.domain.errors import UserKeyInvalidError
from booksaver.domain.model_policy import (
    AdmissionDecision,
    BrowserJobKind,
    CostReconciliation,
    ModelAttemptAudit,
    ModelCostEstimator,
    ModelStopReason,
    ReconciliationRequest,
    ReservationRequest,
    UsdAmount,
)
from booksaver.domain.models import Booking, Config
from booksaver.domain.schedule import (
    ScheduledAdmission,
    ScheduleSettings,
    SlotIdentity,
)
from booksaver.domain.user_session import SessionUnavailableReason, UserSessionHealth
from booksaver.infrastructure.browser.booking_account_inventory import (
    BookingComAccountInventorySource,
)
from booksaver.infrastructure.notifications.routing import (
    OwnerBookingNotifierResolver,
    resolve_telegram_chat_id,
)
from booksaver.infrastructure.notifications.telegram_notifier import TelegramNotifier
from booksaver.infrastructure.persistence.encrypted_session_store import (
    EncryptedUserSessionRepository,
)
from booksaver.infrastructure.persistence.model_policy import SqliteSpendLedger
from booksaver.infrastructure.persistence.scheduled_check_slots import (
    SqliteScheduledCheckSlotRepository,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteAccountReservationRepository,
    SqliteBookingRepository,
    SqliteCheckHistoryRepository,
    SqliteCheckTraceRepository,
    SqliteSavingsRepository,
    SqliteStore,
    SqliteUserRepository,
)
from booksaver.monitor.browser_agent import BrowserAgent
from booksaver.monitor.failure_tracker import FailureTracker
from booksaver.monitor.search_check_job import BookingComSearchMonitor
from booksaver.monitor.session_manager import SessionManager
from booksaver.monitor.trace import TraceRecorder
from booksaver.monitor.user_limits import (
    DailyCounter,
    build_check_plan,
    users_needing_capped_notice,
)

logger = logging.getLogger(__name__)

LLMFactoryBuilder = Callable[[Config, Any], Any]
NotifierBuilder = Callable[[Config], list[Any]]
InvalidKeyNotifier = Callable[[Any, list[Any]], None]
BrowserFactory = Callable[[], AbstractContextManager[Any]]
AuthRequiredNotifier = Callable[[int], None]
InventorySynchronizer = Callable[
    [SqliteStore, Any, int, SynchronizationTrigger], SynchronizationReport
]
IncidentRecorderFactory = Callable[[], AbstractContextManager[Any]]

_INCIDENT_STRUCTURAL_ROLE_ALIASES = {"input": "textbox"}
_INCIDENT_STRUCTURAL_ROLES = frozenset(
    {
        "page",
        "main",
        "list",
        "listitem",
        "button",
        "link",
        "dialog",
        "form",
        "textbox",
        "checkbox",
        "table",
        "row",
    }
)
_INCIDENT_HISTORY_OUTCOMES = frozenset(outcome.value for outcome in AgentHistoryOutcome)
_MAX_INCIDENT_EVIDENCE_ITEMS = 128


@dataclass(frozen=True, slots=True)
class _SanitizedIncidentEvidence:
    """Browser-lifetime evidence safe to carry across the cleanup boundary."""

    structural_roles: tuple[str, ...] = ()
    action_outcomes: tuple[str, ...] = ()


class _InventoryLLMUsage:
    def __init__(self) -> None:
        self.actual_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.action_count = 0
        self.providers: set[str] = set()
        self.models: set[str] = set()
        self.roles: set[str] = set()
        self.prompt_versions: set[str] = set()

    def record_delegate_call(self, delegate: Any, *, default_role: str) -> None:
        """Capture bounded provider metadata after one attempted call."""
        for attribute, target in (
            ("provider", self.providers),
            ("model", self.models),
            ("role", self.roles),
            ("prompt_version", self.prompt_versions),
        ):
            value = getattr(delegate, attribute, None)
            if isinstance(value, str) and value:
                target.add(_audit_machine_code(value))
        self.roles.add(default_role)
        if not self.providers:
            self.providers.add("unreported")
        if not self.models:
            self.models.add("unreported")
        if not self.prompt_versions:
            self.prompt_versions.add("unversioned")
        provider_usage = getattr(delegate, "last_usage", None)
        if provider_usage is None:
            return
        self.input_tokens += _bounded_usage_count(getattr(provider_usage, "input_tokens", 0))
        self.output_tokens += _bounded_usage_count(getattr(provider_usage, "output_tokens", 0))

    def record_action(self, _action: AgentAction) -> None:
        self.action_count += 1


def _audit_machine_code(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())[:100]
    if not normalized or not normalized[0].isalnum():
        return "unreported"
    return normalized


def _bounded_usage_count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return min(max(0, value), 100_000_000)


class _LazyCountedInventoryBrain:
    """Resolve caller capability only after deterministic inventory has failed."""

    def __init__(
        self,
        factory: Any,
        user_id: int,
        counter: DailyCounter,
        limit: int,
        usage: _InventoryLLMUsage,
    ) -> None:
        self._factory = factory
        self._user_id = user_id
        self._counter = counter
        self._limit = limit
        self._usage = usage
        self._delegate: AgentBrain | None = None

    def decide(self, context: AgentTurnContext) -> AgentAction:
        if self._delegate is None:
            method = getattr(self._factory, "agent_brain_for_user", None)
            if method is None:
                raise RuntimeError("user-scoped navigation agent is unavailable")
            self._delegate = method(self._user_id, role="navigation_agent")
            if self._delegate is None:
                raise RuntimeError("user-scoped navigation agent is unavailable")
        if not self._counter.try_increment(self._user_id, self._limit):
            return AgentAction(
                AgentActionType.GIVE_UP,
                value="daily LLM allowance exhausted",
                stop_reason=AgentStopReason.BUDGET_EXHAUSTED,
            )
        self._usage.actual_calls += 1
        try:
            return self._delegate.decide(context)
        finally:
            self._usage.record_delegate_call(self._delegate, default_role="navigation_agent")


class _LazyCountedInventoryInterpreter:
    def __init__(
        self,
        factory: Any,
        user_id: int,
        counter: DailyCounter,
        limit: int,
        usage: _InventoryLLMUsage,
    ) -> None:
        self._factory = factory
        self._user_id = user_id
        self._counter = counter
        self._limit = limit
        self._usage = usage
        self._delegate: InventoryInterpreter | None = None

    def interpret(self, page_text: str, source_url: str) -> tuple[Any, ...]:
        if self._delegate is None:
            method = getattr(self._factory, "inventory_interpreter_for_user", None)
            if method is None:
                raise RuntimeError("user-scoped inventory interpreter is unavailable")
            self._delegate = method(self._user_id, role="inventory_interpreter")
            if self._delegate is None:
                raise RuntimeError("user-scoped inventory interpreter is unavailable")
        if not self._counter.try_increment(self._user_id, self._limit):
            raise BudgetExceeded("daily LLM allowance exhausted")
        self._usage.actual_calls += 1
        try:
            return self._delegate.interpret(page_text, source_url)
        finally:
            self._usage.record_delegate_call(self._delegate, default_role="inventory_interpreter")


class _UnavailableLegacySessionRepository:
    """Null object preventing accidental daemon fallback to legacy global cookies."""

    def load(self, _platform: Any) -> None:
        return None

    def save(self, _session: Any) -> None:
        raise RuntimeError("Legacy global session writes are disabled in the daemon")


class _DailyCappedSpendLedger:
    """Retain the legacy per-user call ceiling behind persistent USD admission."""

    def __init__(
        self,
        ledger: SpendLedger,
        counter: DailyCounter,
        user_id: int,
        limit: int,
    ) -> None:
        self._ledger = ledger
        self._counter = counter
        self._user_id = user_id
        self._limit = limit

    def reserve_call(self, request: ReservationRequest) -> AdmissionDecision:
        # CheckCoordinator serializes all provider work, so the read followed
        # by persistent admission and increment cannot race another job.
        if self._counter.count(self._user_id) >= self._limit:
            return AdmissionDecision(denied_reason=ModelStopReason.DAILY_COST_LIMIT)
        decision = self._ledger.reserve_call(request)
        if decision.reservation is not None and decision.reservation.was_new:
            self._counter.increment(self._user_id)
        return decision

    def reconcile_call(self, request: ReconciliationRequest) -> CostReconciliation:
        return self._ledger.reconcile_call(request)

    def list_attempts(self, job_id: str) -> tuple[ModelAttemptAudit, ...]:
        return self._ledger.list_attempts(job_id)


@dataclass(frozen=True)
class AdaptiveBrowserJobContext:
    local_user_id: int
    runtime: Any
    budget: BrowserJobCostBudget

    @property
    def calls_used(self) -> int:
        return len(self.budget.ordered_attempts())

    def record_usage(self, usage: _InventoryLLMUsage) -> None:
        attempts = self.budget.ordered_attempts()
        usage.actual_calls = len(attempts)
        for attempt in attempts:
            usage.providers.add(attempt.provider)
            usage.models.add(attempt.model)
            usage.roles.add(attempt.role)
            usage.prompt_versions.add(
                {
                    "recovery": "booking-browser-recovery-v3",
                    "interpretation": "booking-inventory-interpretation-v1",
                    "extraction": "booking-offer-extraction-v1",
                    "classification": "booking-page-state-v1",
                    "diagnostic": "booking-browser-diagnostic-v1",
                }.get(attempt.role, "adaptive-model-policy-v1")
            )
            if attempt.usage is not None:
                usage.input_tokens += attempt.usage.input_tokens
                usage.output_tokens += attempt.usage.output_tokens


@dataclass(frozen=True)
class AdaptiveBrowserJobAdmission:
    context: AdaptiveBrowserJobContext | None = None
    stop_reason: ModelStopReason | None = None

    def __post_init__(self) -> None:
        if (self.context is None) == (self.stop_reason is None):
            raise ValueError("adaptive browser-job admission requires context or stop")


class ImmediateAdmission(Enum):
    ACCEPTED = "accepted"
    BUSY = "busy"
    STOPPING = "stopping"


class ImmediateCompletionKind(Enum):
    RESULT = "result"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ImmediateCompletion:
    kind: ImmediateCompletionKind
    result: CheckResult | None = None
    property_name: str | None = None
    unavailable_detail: str | None = None


@dataclass(frozen=True)
class InventoryCompletion:
    report: SynchronizationReport | None
    reservations: tuple[AccountReservation, ...] = ()


class CheckCoordinator:
    """The daemon's single admission and execution boundary for live checks.

    Scheduler and Telegram threads share this instance. The non-blocking gate
    deliberately rejects overlap instead of queuing stale browser work.
    """

    def __init__(
        self,
        config: Config,
        stop_event: threading.Event,
        *,
        llm_factory_builder: LLMFactoryBuilder,
        notifier_builder: NotifierBuilder,
        invalid_key_notifier: InvalidKeyNotifier,
        browser_factory: BrowserFactory | None = None,
        checks_today: DailyCounter | None = None,
        llm_calls_today: DailyCounter | None = None,
        capped_notice_sent_today: DailyCounter | None = None,
        session_repository: UserSessionRepository | None = None,
        auth_required_notifier: AuthRequiredNotifier | None = None,
        inventory_synchronizer: InventorySynchronizer | None = None,
        incident_recorder_factory: IncidentRecorderFactory | None = None,
        execution_gate: threading.Lock | None = None,
    ) -> None:
        self._config = config
        self._db_path = config.data_directory.path / "booksaver.db"
        self._stop_event = stop_event
        self._llm_factory_builder = llm_factory_builder
        self._notifier_builder = notifier_builder
        self._invalid_key_notifier = invalid_key_notifier
        self._browser_factory = browser_factory or self._default_browser_factory
        self._session_repository = session_repository or EncryptedUserSessionRepository(
            config.data_directory
        )
        self._auth_required_notifier = auth_required_notifier
        self._inventory_synchronizer = inventory_synchronizer
        self._incident_recorder_factory = incident_recorder_factory
        self._checks_today = checks_today or DailyCounter()
        self._llm_calls_today = llm_calls_today or DailyCounter()
        self._capped_notice_sent_today = capped_notice_sent_today or DailyCounter()
        self._execution_gate = execution_gate or threading.Lock()
        self._job_local = threading.local()

    @property
    def checks_today(self) -> dict[int, int]:
        return self._checks_today.snapshot()

    @property
    def llm_calls_today(self) -> dict[int, int]:
        return self._llm_calls_today.snapshot()

    def set_auth_required_notifier(self, notifier: AuthRequiredNotifier | None) -> None:
        self._auth_required_notifier = notifier

    @contextmanager
    def _adaptive_job_scope(
        self,
        store: SqliteStore,
        user_id: int,
        job_kind: BrowserJobKind,
    ) -> Iterator[None]:
        previous = getattr(self._job_local, "adaptive", None)
        self._job_local.adaptive = self._build_adaptive_job_context(
            store,
            user_id,
            job_kind,
        )
        try:
            yield
        finally:
            self._job_local.adaptive = previous

    def _build_adaptive_job_context(
        self,
        store: SqliteStore,
        user_id: int,
        job_kind: BrowserJobKind,
    ) -> AdaptiveBrowserJobContext | None:
        daily_limit = self._config.limits_settings.max_llm_calls_per_user_per_day
        if self._llm_calls_today.count(user_id) >= daily_limit:
            return None
        factory = self._llm_factory_builder(self._config, store)
        key_ref_method = getattr(factory, "caller_key_ref_for_user", None)
        runtime_method = getattr(factory, "adaptive_runtime_for_user", None)
        if not callable(key_ref_method) or not callable(runtime_method):
            return None
        key_ref = key_ref_method(user_id)
        if key_ref is None:
            return None
        ledger = _DailyCappedSpendLedger(
            SqliteSpendLedger(store),
            self._llm_calls_today,
            user_id,
            daily_limit,
        )
        settings = self._config.agent_settings
        budget = BrowserJobCostBudget(
            job_id=f"{job_kind.value}-{uuid.uuid4().hex}",
            job_kind=job_kind,
            caller_key_ref=key_ref,
            ledger=ledger,
            estimator=ModelCostEstimator(),
            job_limit=UsdAmount(settings.max_job_cost_micro_usd),
            day_limit=UsdAmount(settings.max_deployment_daily_cost_micro_usd),
            preserve_opus_diagnostic=(settings.reserve_opus_diagnostic_for_ambiguous_episode),
        )
        runtime = runtime_method(user_id, budget)
        if runtime is None:
            return None
        return AdaptiveBrowserJobContext(
            local_user_id=user_id,
            runtime=runtime,
            budget=budget,
        )

    def _current_adaptive_job(self) -> AdaptiveBrowserJobContext | None:
        current = getattr(self._job_local, "adaptive", None)
        return current if isinstance(current, AdaptiveBrowserJobContext) else None

    @contextmanager
    def adaptive_runtime_scope_for_telegram_user(
        self,
        telegram_user_id: int,
        job_kind: BrowserJobKind = BrowserJobKind.REMOTE_AUTH,
    ) -> Iterator[AdaptiveBrowserJobAdmission]:
        """Expose one store-backed runtime scope for remote-auth composition.

        The runner must keep this context open for the whole admitted attempt;
        doing so maps Telegram identity to the local caller once and keeps one
        budget available to every ambiguous classification in that attempt.
        """
        with SqliteStore(self._db_path) as store:
            user = SqliteUserRepository(store).get_by_telegram_id(telegram_user_id)
            if user is None or not user.is_active:
                yield AdaptiveBrowserJobAdmission(stop_reason=ModelStopReason.CALLER_REVOKED)
                return
            if self._llm_calls_today.count(user.user_id) >= (
                self._config.limits_settings.max_llm_calls_per_user_per_day
            ):
                yield AdaptiveBrowserJobAdmission(stop_reason=ModelStopReason.DAILY_COST_LIMIT)
                return
            with self._adaptive_job_scope(store, user.user_id, job_kind):
                current = self._current_adaptive_job()
                if current is None:
                    yield AdaptiveBrowserJobAdmission(
                        stop_reason=ModelStopReason.PROVIDER_AUTHENTICATION
                    )
                else:
                    yield AdaptiveBrowserJobAdmission(context=current)

    def _record_post_browser_incidents(
        self,
        *,
        user_id: int,
        adaptive_job: AdaptiveBrowserJobContext | None,
        inventory_report: SynchronizationReport | None = None,
        check_result: CheckResult | None = None,
        evidence: _SanitizedIncidentEvidence | None = None,
    ) -> None:
        """Persist only sanitized incident material after browser cleanup."""
        if self._incident_recorder_factory is None:
            return
        try:
            drafts, resolved_steps = self._incident_handoffs(
                user_id=user_id,
                adaptive_job=adaptive_job,
                inventory_report=inventory_report,
                check_result=check_result,
                evidence=evidence,
            )
            if not drafts and not resolved_steps:
                return
            with self._incident_recorder_factory() as recorder:
                for journey, step_id, observed_at in resolved_steps:
                    try:
                        recorder.resolve_deterministic_success(
                            journey=journey,
                            step_id=step_id,
                            observed_at=observed_at,
                        )
                    except Exception:
                        logger.warning("DOM incident deterministic resolution failed")
                for draft in drafts:
                    recorder.record_safely(draft)
        except Exception:
            # Incident construction/factory/persistence is operationally
            # secondary and must never alter the completed caller result.
            logger.warning("DOM incident post-browser handoff failed")

    @staticmethod
    def _capture_incident_evidence(
        *,
        browser: Any,
        adaptive_job: AdaptiveBrowserJobContext | None,
        inventory_report: SynchronizationReport | None = None,
        check_result: CheckResult | None = None,
        check_trace: CheckTrace | None = None,
    ) -> _SanitizedIncidentEvidence:
        """Capture an allowlisted structural/action projection before close.

        The observation itself, page text, labels, element references, URLs,
        screenshots, and trace details never cross this boundary.
        """
        if adaptive_job is None:
            return _SanitizedIncidentEvidence()
        try:
            attempts = adaptive_job.budget.ordered_attempts()
        except Exception:
            logger.warning("DOM incident model-attempt evidence capture failed")
            return _SanitizedIncidentEvidence()
        if not attempts:
            return _SanitizedIncidentEvidence()
        diagnoses = CheckCoordinator._incident_diagnoses(
            inventory_report=inventory_report,
            check_result=check_result,
        )
        if not any(is_dom_incident_eligible(diagnosis) for diagnosis in diagnoses):
            return _SanitizedIncidentEvidence()

        structural_roles: list[str] = []
        try:
            observation = browser.observe()
            for element in getattr(observation, "elements", ()):
                role = getattr(element, "role", None)
                if not isinstance(role, str):
                    continue
                normalized = role.strip().casefold()
                normalized = _INCIDENT_STRUCTURAL_ROLE_ALIASES.get(normalized, normalized)
                if normalized in _INCIDENT_STRUCTURAL_ROLES:
                    structural_roles.append(normalized)
                if len(structural_roles) == _MAX_INCIDENT_EVIDENCE_ITEMS:
                    break
        except Exception:
            # Evidence collection is secondary and must not change a completed
            # browser outcome. An empty structural digest remains a valid signal.
            logger.warning("DOM incident structural-role capture failed")

        action_outcomes: list[str] = []

        def _append(value: str) -> None:
            if value not in action_outcomes and len(action_outcomes) < _MAX_INCIDENT_EVIDENCE_ITEMS:
                action_outcomes.append(value)

        def _consume_event(kind: str, fields: dict[str, Any]) -> None:
            if kind == TraceKind.AGENT_BLOCKED.value:
                _append("blocked")
                return
            if kind != TraceKind.AGENT_OUTCOME.value:
                return
            outcome = fields.get("outcome")
            if isinstance(outcome, str) and outcome in _INCIDENT_HISTORY_OUTCOMES:
                _append(outcome)
            if fields.get("verified") is True:
                _append("verified")
            stop_reason = fields.get("stop_reason")
            if stop_reason == AgentStopReason.NO_PROGRESS.value:
                _append("no_progress")
            elif stop_reason == AgentStopReason.UNSAFE_ACTION.value:
                _append("blocked")

        audit = inventory_report.recovery_audit if inventory_report is not None else None
        if audit is not None:
            for inventory_event in audit.trace:
                event_fields = inventory_event.as_dict()
                kind = event_fields.pop("kind", "")
                if isinstance(kind, str):
                    _consume_event(kind, event_fields)
            if audit.action_count and not action_outcomes:
                _append("executed")
            if audit.outcome is InventoryRecoveryOutcome.BLOCKED:
                _append("blocked")
            elif audit.outcome is InventoryRecoveryOutcome.GAVE_UP:
                _append("no_progress")

        if check_trace is not None:
            for check_event in check_trace.events:
                if check_event.kind not in {
                    TraceKind.AGENT_OUTCOME,
                    TraceKind.AGENT_BLOCKED,
                }:
                    continue
                try:
                    parsed = json.loads(check_event.detail)
                except (TypeError, ValueError, json.JSONDecodeError):
                    parsed = {}
                fields = parsed if isinstance(parsed, dict) else {}
                _consume_event(check_event.kind.value, fields)

        for diagnosis in diagnoses:
            if not is_dom_incident_eligible(diagnosis):
                continue
            _append(
                "verified"
                if diagnosis.reason is TerminalBrowserReason.POSTCONDITION_SATISFIED
                else "no_progress"
            )
        return _SanitizedIncidentEvidence(
            structural_roles=tuple(structural_roles),
            action_outcomes=tuple(action_outcomes),
        )

    @staticmethod
    def _load_check_trace_for_evidence(
        store: SqliteStore,
        result: CheckResult,
    ) -> CheckTrace | None:
        try:
            return SqliteCheckTraceRepository(store).get(result.check_id)
        except Exception:
            logger.warning("DOM incident check-trace evidence capture failed")
            return None

    @staticmethod
    def _incident_diagnoses(
        *,
        inventory_report: SynchronizationReport | None,
        check_result: CheckResult | None,
    ) -> tuple[TerminalBrowserDiagnosis, ...]:
        if inventory_report is not None:
            return (
                *inventory_report.assisted_diagnoses,
                *(
                    (inventory_report.terminal_diagnosis,)
                    if inventory_report.terminal_diagnosis
                    else ()
                ),
            )
        if check_result is not None:
            return (
                *check_result.assisted_diagnoses,
                *((check_result.terminal_diagnosis,) if check_result.terminal_diagnosis else ()),
            )
        return ()

    @staticmethod
    def _incident_handoffs(
        *,
        user_id: int,
        adaptive_job: AdaptiveBrowserJobContext | None,
        inventory_report: SynchronizationReport | None,
        check_result: CheckResult | None,
        evidence: _SanitizedIncidentEvidence | None = None,
    ) -> tuple[
        tuple[IncidentDraft, ...],
        tuple[tuple[DomJourney, DomStepId, datetime], ...],
    ]:
        attempts = adaptive_job.budget.ordered_attempts() if adaptive_job is not None else ()
        diagnoses = CheckCoordinator._incident_diagnoses(
            inventory_report=inventory_report,
            check_result=check_result,
        )
        resolved_candidates: tuple[DomStepId, ...] = ()
        observed_at = datetime.now(UTC)
        if inventory_report is not None:
            if inventory_report.succeeded:
                from booksaver.application.browser_resilience import (
                    ACCOUNT_INVENTORY_DOM_STEPS,
                )

                resolved_candidates = ACCOUNT_INVENTORY_DOM_STEPS
        elif check_result is not None:
            observed_at = check_result.checked_at.astimezone(UTC)
            if check_result.failure_reason is None:
                from booksaver.application.browser_resilience import PRICE_SEARCH_DOM_STEPS

                resolved_candidates = PRICE_SEARCH_DOM_STEPS

        evidence = evidence or _SanitizedIncidentEvidence()
        assisted_steps = {diagnosis.step_id for diagnosis in diagnoses}
        drafts: list[IncidentDraft] = []
        if attempts:
            provider_state = (
                IncidentProviderState.FAILED
                if any(attempt.outcome == "provider_failed" for attempt in attempts)
                else IncidentProviderState.COMPLETED
            )
            for diagnosis in diagnoses:
                definition = DOM_STEP_REGISTRY.definition(diagnosis.step_id)
                budget_state = (
                    IncidentBudgetState.EXHAUSTED
                    if diagnosis.model_stop_reason
                    in {
                        ModelStopReason.JOB_COST_LIMIT,
                        ModelStopReason.DAILY_COST_LIMIT,
                    }
                    else IncidentBudgetState.WITHIN_LIMIT
                )
                draft = build_incident_draft(
                    journey=definition.journey,
                    diagnosis=diagnosis,
                    verifier_category=definition.deterministic_postcondition,
                    structural_roles=evidence.structural_roles,
                    model_attempts=attempts,
                    provider_state=provider_state,
                    budget_state=budget_state,
                    observed_at=observed_at,
                    source_user_ids=(user_id,),
                    action_outcomes=evidence.action_outcomes,
                )
                if draft is not None:
                    drafts.append(draft)

        resolved = tuple(
            (
                DOM_STEP_REGISTRY.definition(step_id).journey,
                step_id,
                observed_at,
            )
            for step_id in resolved_candidates
            if step_id not in assisted_steps
        )
        return tuple(drafts), resolved

    def _default_browser_factory(self) -> AbstractContextManager[Any]:
        from booksaver.infrastructure.browser.playwright_adapter import (
            PlaywrightInteractiveBrowser,
        )

        return PlaywrightInteractiveBrowser(
            headless=True,
            mobile_settings=self._config.mobile_web_settings,
        )

    def run_scheduled(self) -> None:
        """Run the legacy all-user batch used by compatibility tests and tooling.

        Production scheduling enters through :meth:`run_scheduled_slot`, which
        claims one durable, user-scoped opportunity after acquiring the shared
        browser gate.
        """
        if self._stop_event.is_set():
            return
        if not self._execution_gate.acquire(blocking=False):
            logger.info("Scheduled check tick skipped: another check is already running")
            return
        try:
            if not self._stop_event.is_set():
                self._run_scheduled_locked()
        finally:
            self._execution_gate.release()

    def run_scheduled_slot(
        self,
        identity: SlotIdentity,
        settings: ScheduleSettings,
        now: datetime,
    ) -> ScheduledAdmission:
        """Claim and run one durable user-scoped schedule slot synchronously."""
        if self._stop_event.is_set():
            return ScheduledAdmission.STOPPING
        if not self._execution_gate.acquire(blocking=False):
            return ScheduledAdmission.BUSY

        try:
            if self._stop_event.is_set():
                return ScheduledAdmission.STOPPING
            with SqliteStore(self._db_path) as store:
                claimed = SqliteScheduledCheckSlotRepository(store).claim(
                    identity,
                    now,
                    settings.missed_run_grace,
                    settings.minimum_spacing,
                )
            if claimed is None:
                return ScheduledAdmission.STALE
            try:
                with SqliteStore(self._db_path) as store:
                    with self._adaptive_job_scope(
                        store,
                        identity.user_id,
                        BrowserJobKind.SCHEDULED_SLOT,
                    ):
                        self._run_scheduled_user_locked(store, identity.user_id)
            finally:
                # Terminalize through a fresh connection so an unexpected
                # browser/persistence transaction cannot strand this slot in
                # RUNNING until the next process restart.
                with SqliteStore(self._db_path) as store:
                    SqliteScheduledCheckSlotRepository(store).complete(identity, datetime.now(UTC))
            return ScheduledAdmission.COMPLETED
        finally:
            self._execution_gate.release()

    def request_immediate(
        self,
        telegram_user_id: int,
        booking_id: str,
        on_complete: Callable[[ImmediateCompletion], None],
    ) -> ImmediateAdmission:
        """Admit one background check without blocking Telegram polling."""
        if self._stop_event.is_set():
            return ImmediateAdmission.STOPPING
        if not self._execution_gate.acquire(blocking=False):
            return ImmediateAdmission.BUSY

        worker = threading.Thread(
            target=self._run_immediate_worker,
            args=(telegram_user_id, booking_id, on_complete),
            name=f"booksaver-checknow-{booking_id[:8]}",
            daemon=True,
        )
        try:
            worker.start()
        except Exception:
            self._execution_gate.release()
            raise
        return ImmediateAdmission.ACCEPTED

    def request_inventory(
        self,
        telegram_user_id: int,
        on_complete: Callable[[InventoryCompletion], None] | None = None,
        *,
        trigger: SynchronizationTrigger = SynchronizationTrigger.BOOKINGS,
    ) -> ImmediateAdmission:
        """Synchronize one caller's complete account inventory in the background."""
        if self._stop_event.is_set():
            return ImmediateAdmission.STOPPING
        if not self._execution_gate.acquire(blocking=False):
            return ImmediateAdmission.BUSY
        callback = on_complete or (lambda _completion: None)
        worker = threading.Thread(
            target=self._run_inventory_worker,
            args=(telegram_user_id, trigger, callback),
            name=f"booksaver-inventory-{telegram_user_id}",
            daemon=True,
        )
        try:
            worker.start()
        except Exception:
            self._execution_gate.release()
            raise
        return ImmediateAdmission.ACCEPTED

    def _run_inventory_worker(
        self,
        telegram_user_id: int,
        trigger: SynchronizationTrigger,
        on_complete: Callable[[InventoryCompletion], None],
    ) -> None:
        completion = InventoryCompletion(None)
        try:
            if self._stop_event.is_set():
                return
            with SqliteStore(self._db_path) as store:
                user = SqliteUserRepository(store).get_by_telegram_id(telegram_user_id)
                if user is None or not user.is_active:
                    return
                with self._adaptive_job_scope(
                    store,
                    user.user_id,
                    BrowserJobKind.BOOKINGS_SYNC,
                ):
                    adaptive_job = self._current_adaptive_job()
                    with self._browser_factory() as browser:
                        report = self._synchronize_user(store, browser, user.user_id, trigger)
                        evidence = self._capture_incident_evidence(
                            browser=browser,
                            adaptive_job=adaptive_job,
                            inventory_report=report,
                        )
                    self._record_post_browser_incidents(
                        user_id=user.user_id,
                        adaptive_job=adaptive_job,
                        inventory_report=report,
                        evidence=evidence,
                    )
                reservations = tuple(
                    SqliteAccountReservationRepository(store).list_for_user(user.user_id)
                )
                completion = InventoryCompletion(report, reservations)
        except Exception:
            logger.exception(
                "Booking.com inventory synchronization failed for Telegram user %s",
                telegram_user_id,
            )
            try:
                with SqliteStore(self._db_path) as store:
                    user = SqliteUserRepository(store).get_by_telegram_id(telegram_user_id)
                    if user is not None and user.is_active:
                        reservations = tuple(
                            SqliteAccountReservationRepository(store).list_for_user(user.user_id)
                        )
                        completion = InventoryCompletion(
                            SynchronizationReport(
                                run_id=str(uuid.uuid4()),
                                completeness=InventoryCompleteness.FAILED,
                                discovered=0,
                                eligible=0,
                                ineligible=0,
                                failure_code=SynchronizationFailureCode.UNKNOWN,
                                failure_detail=(
                                    "Booking.com reservation refresh was unavailable due to "
                                    "an unexpected error. The last safe inventory was preserved."
                                ),
                            ),
                            reservations,
                        )
            except Exception:
                logger.warning(
                    "Could not load preserved inventory after synchronization failure",
                    exc_info=True,
                )
        finally:
            self._execution_gate.release()
            try:
                with SqliteStore(self._db_path) as store:
                    current = SqliteUserRepository(store).get_by_telegram_id(telegram_user_id)
                    may_deliver = current is not None and current.is_active
            except Exception:
                may_deliver = False
                logger.warning(
                    "Could not re-authorize inventory synchronization callback",
                    exc_info=True,
                )
            if not may_deliver:
                return
            try:
                on_complete(completion)
            except Exception:
                logger.warning(
                    "Inventory synchronization completion callback failed",
                    exc_info=True,
                )

    def _run_immediate_worker(
        self,
        telegram_user_id: int,
        booking_id: str,
        on_complete: Callable[[ImmediateCompletion], None],
    ) -> None:
        completion = ImmediateCompletion(ImmediateCompletionKind.UNAVAILABLE)
        try:
            if self._stop_event.is_set():
                return
            with SqliteStore(self._db_path) as store:
                users = SqliteUserRepository(store)
                user = users.get_by_telegram_id(telegram_user_id)
                if user is None or not user.is_active:
                    return
                bookings = SqliteBookingRepository(store)
                with self._adaptive_job_scope(
                    store,
                    user.user_id,
                    BrowserJobKind.CHECK_NOW,
                ):
                    adaptive_job = self._current_adaptive_job()
                    report: SynchronizationReport | None = None
                    result: CheckResult | None = None
                    inventory_evidence = _SanitizedIncidentEvidence()
                    check_evidence = _SanitizedIncidentEvidence()
                    try:
                        with self._browser_factory() as browser:
                            try:
                                report = self._synchronize_user(
                                    store,
                                    browser,
                                    user.user_id,
                                    SynchronizationTrigger.CHECK_NOW,
                                )
                                inventory_evidence = self._capture_incident_evidence(
                                    browser=browser,
                                    adaptive_job=adaptive_job,
                                    inventory_report=report,
                                )
                            except Exception:
                                logger.exception(
                                    "Immediate inventory synchronization failed for user %s",
                                    user.user_id,
                                )
                                completion = ImmediateCompletion(
                                    ImmediateCompletionKind.UNAVAILABLE,
                                    unavailable_detail=(
                                        "Booking.com reservations could not be refreshed. "
                                        "Try /bookings again shortly."
                                    ),
                                )
                                return
                            if report.completeness is not InventoryCompleteness.COMPLETE:
                                completion = ImmediateCompletion(
                                    ImmediateCompletionKind.UNAVAILABLE,
                                    unavailable_detail=(
                                        report.failure_detail
                                        or "Booking.com reservation refresh was incomplete."
                                    ),
                                )
                                return
                            booking = bookings.get_by_id(booking_id)
                            if (
                                booking is None
                                or bookings.get_owner_user_id(booking_id) != user.user_id
                                or all(
                                    active.booking_id != booking_id
                                    for active in bookings.list_active_for_user(user.user_id)
                                )
                            ):
                                return
                            if not self._checks_today.try_increment(
                                user.user_id,
                                self._config.limits_settings.max_checks_per_user_per_day,
                            ):
                                result = self._limit_result(booking, "Immediate check skipped")
                                SqliteCheckHistoryRepository(store).add(result)
                                self._send_capped_notice(store, user.user_id)
                            elif self._stop_event.is_set():
                                return
                            else:
                                try:
                                    result = self._run_booking(
                                        store, browser, user.user_id, booking
                                    )
                                except Exception as exc:
                                    logger.exception(
                                        "Immediate browser execution failed for booking %s",
                                        booking_id,
                                    )
                                    result = CheckResult.failure(
                                        booking.booking_id,
                                        datetime.now(UTC),
                                        FailureReason(
                                            FailureCode.NAVIGATION_ERROR,
                                            f"Could not start the live browser check: {exc}",
                                        ),
                                    )
                                    SqliteCheckHistoryRepository(store).add(result)
                                if result is not None:
                                    check_evidence = self._capture_incident_evidence(
                                        browser=browser,
                                        adaptive_job=adaptive_job,
                                        check_result=result,
                                        check_trace=self._load_check_trace_for_evidence(
                                            store, result
                                        ),
                                    )
                    finally:
                        self._record_post_browser_incidents(
                            user_id=user.user_id,
                            adaptive_job=adaptive_job,
                            inventory_report=report,
                            evidence=inventory_evidence,
                        )
                        self._record_post_browser_incidents(
                            user_id=user.user_id,
                            adaptive_job=adaptive_job,
                            check_result=result,
                            evidence=check_evidence,
                        )

                # A check may take minutes. Re-authorize and re-resolve at
                # completion so revocation/deletion during navigation does
                # not disclose its result through the callback.
                current_user = users.get_by_telegram_id(telegram_user_id)
                current_booking = bookings.get_by_id(booking_id)
                if (
                    current_user is not None
                    and current_user.is_active
                    and current_booking is not None
                    and bookings.get_owner_user_id(booking_id) == current_user.user_id
                ):
                    completion = ImmediateCompletion(
                        ImmediateCompletionKind.RESULT,
                        result=result,
                        property_name=current_booking.property.name,
                    )
        except Exception:
            logger.exception("Immediate check worker failed for booking %s", booking_id)
        finally:
            self._execution_gate.release()
            try:
                on_complete(completion)
            except Exception:
                logger.warning("Immediate check completion callback failed", exc_info=True)

    def _run_scheduled_locked(self) -> None:
        with SqliteStore(self._db_path) as store:
            users = SqliteUserRepository(store)
            bookings = SqliteBookingRepository(store)
            active_users = users.list_active()
            bookings_by_user: dict[int, list[Booking]] = {}
            for user in active_users:
                if self._stop_event.is_set():
                    return
                has_account_inventory = (
                    store.conn.execute(
                        "SELECT 1 FROM account_reservations WHERE user_id = ? LIMIT 1",
                        (user.user_id,),
                    ).fetchone()
                    is not None
                )
                if not bookings.list_all_for_user(user.user_id) and not has_account_inventory:
                    try:
                        if (
                            self._session_repository.status(user.user_id).health
                            is not UserSessionHealth.READY
                        ):
                            continue
                    except Exception:
                        logger.warning(
                            "Could not resolve session status for user %s",
                            user.user_id,
                            exc_info=True,
                        )
                        continue
                try:
                    with self._browser_factory() as browser:
                        report = self._synchronize_user(
                            store,
                            browser,
                            user.user_id,
                            SynchronizationTrigger.SCHEDULED,
                        )
                    self._record_post_browser_incidents(
                        user_id=user.user_id,
                        adaptive_job=self._current_adaptive_job(),
                        inventory_report=report,
                    )
                except Exception:
                    logger.exception(
                        "Scheduled inventory synchronization failed for user %s",
                        user.user_id,
                    )
                    continue
                if report.completeness is InventoryCompleteness.COMPLETE:
                    bookings_by_user[user.user_id] = bookings.list_active_for_user(user.user_id)
            plan = build_check_plan(
                users=active_users,
                bookings_by_user=bookings_by_user,
                checks_today=self._checks_today.snapshot(),
                max_checks_per_user_per_day=(
                    self._config.limits_settings.max_checks_per_user_per_day
                ),
            )
            history = SqliteCheckHistoryRepository(store)
            for user_id, booking in plan.skipped:
                if not self._is_active_user(store, user_id):
                    continue
                history.add(self._limit_result(booking, "Scheduled check skipped"))
            for user_id in users_needing_capped_notice(
                plan.capped_user_ids, self._capped_notice_sent_today
            ):
                self._send_capped_notice(store, user_id, already_marked=True)

            if not plan.ordered or self._stop_event.is_set():
                return
            for user_id, booking in plan.ordered:
                if self._stop_event.is_set():
                    break
                # The plan is a snapshot. Re-read access immediately before
                # reserving allowance or opening browser work so revocation
                # while an earlier queued booking runs takes effect now.
                if not self._is_active_user(store, user_id):
                    continue
                if not self._checks_today.try_increment(
                    user_id,
                    self._config.limits_settings.max_checks_per_user_per_day,
                ):
                    history.add(self._limit_result(booking, "Scheduled check skipped"))
                    continue
                # A context is deliberately single-booking: cookies for one
                # Telegram user can never survive into another user's check.
                with self._browser_factory() as browser:
                    result = self._run_booking(store, browser, user_id, booking)
                self._record_post_browser_incidents(
                    user_id=user_id,
                    adaptive_job=self._current_adaptive_job(),
                    check_result=result,
                )
                if (
                    self._auth_required_notifier is not None
                    and result.failure_reason is not None
                    and result.failure_reason.code is FailureCode.AUTH_REQUIRED
                ):
                    try:
                        self._auth_required_notifier(user_id)
                    except Exception:
                        logger.warning(
                            "Could not issue Booking.com reconnect notice for user %s",
                            user_id,
                        )

    def _run_scheduled_user_locked(self, store: SqliteStore, user_id: int) -> None:
        """Synchronize and check bookings for exactly one still-active user."""
        users = SqliteUserRepository(store)
        user = users.get_by_id(user_id)
        if user is None or not user.is_active or self._stop_event.is_set():
            return

        bookings = SqliteBookingRepository(store)
        has_account_inventory = (
            store.conn.execute(
                "SELECT 1 FROM account_reservations WHERE user_id = ? LIMIT 1",
                (user_id,),
            ).fetchone()
            is not None
        )
        if not bookings.list_all_for_user(user_id) and not has_account_inventory:
            try:
                if self._session_repository.status(user_id).health is not UserSessionHealth.READY:
                    return
            except Exception:
                logger.warning(
                    "Could not resolve session status for user %s",
                    user_id,
                    exc_info=True,
                )
                return

        try:
            with self._browser_factory() as browser:
                report = self._synchronize_user(
                    store,
                    browser,
                    user_id,
                    SynchronizationTrigger.SCHEDULED,
                )
                inventory_evidence = self._capture_incident_evidence(
                    browser=browser,
                    adaptive_job=self._current_adaptive_job(),
                    inventory_report=report,
                )
            self._record_post_browser_incidents(
                user_id=user_id,
                adaptive_job=self._current_adaptive_job(),
                inventory_report=report,
                evidence=inventory_evidence,
            )
        except Exception:
            logger.exception(
                "Scheduled inventory synchronization failed for user %s",
                user_id,
            )
            return
        if report.completeness is not InventoryCompleteness.COMPLETE:
            return

        active_bookings = bookings.list_active_for_user(user_id)
        plan = build_check_plan(
            users=[user],
            bookings_by_user={user_id: active_bookings},
            checks_today=self._checks_today.snapshot(),
            max_checks_per_user_per_day=(self._config.limits_settings.max_checks_per_user_per_day),
        )
        history = SqliteCheckHistoryRepository(store)
        for skipped_user_id, booking in plan.skipped:
            if self._is_active_user(store, skipped_user_id):
                history.add(self._limit_result(booking, "Scheduled check skipped"))
        for capped_user_id in users_needing_capped_notice(
            plan.capped_user_ids, self._capped_notice_sent_today
        ):
            self._send_capped_notice(store, capped_user_id, already_marked=True)

        for planned_user_id, booking in plan.ordered:
            if self._stop_event.is_set() or not self._is_active_user(store, planned_user_id):
                break
            if not self._checks_today.try_increment(
                planned_user_id,
                self._config.limits_settings.max_checks_per_user_per_day,
            ):
                history.add(self._limit_result(booking, "Scheduled check skipped"))
                continue
            with self._browser_factory() as browser:
                result = self._run_booking(
                    store,
                    browser,
                    planned_user_id,
                    booking,
                )
                check_evidence = self._capture_incident_evidence(
                    browser=browser,
                    adaptive_job=self._current_adaptive_job(),
                    check_result=result,
                    check_trace=self._load_check_trace_for_evidence(store, result),
                )
            self._record_post_browser_incidents(
                user_id=planned_user_id,
                adaptive_job=self._current_adaptive_job(),
                check_result=result,
                evidence=check_evidence,
            )
            if (
                self._auth_required_notifier is not None
                and result.failure_reason is not None
                and result.failure_reason.code is FailureCode.AUTH_REQUIRED
            ):
                self._notify_auth_required(planned_user_id)

    def _synchronize_user(
        self,
        store: SqliteStore,
        browser: Any,
        user_id: int,
        trigger: SynchronizationTrigger,
    ) -> SynchronizationReport:
        if self._inventory_synchronizer is not None:
            return self._inventory_synchronizer(store, browser, user_id, trigger)
        users = SqliteUserRepository(store)
        provider = AuthenticatedSessionProvider(users, self._session_repository)
        resolution = provider.resolve(user_id)
        repository = SqliteAccountReservationRepository(store)
        if not resolution.is_ready or resolution.snapshot is None:
            reason = (
                resolution.unavailable_reason.value
                if resolution.unavailable_reason is not None
                else "unavailable"
            )
            report = repository.reconcile(
                user_id=user_id,
                run_id=str(uuid.uuid4()),
                trigger=trigger,
                session_revision=f"unavailable:{reason}",
                result=InventoryDiscoveryResult.failed(
                    SynchronizationFailureCode.AUTH_REQUIRED,
                    f"Booking.com session is {reason}.",
                ),
                observed_at=datetime.now(UTC),
            )
            self._notify_auth_required(user_id)
            return report

        snapshot = resolution.snapshot
        browser.restore_cookies(snapshot.cookies)
        trace_recorder = TraceRecorder("inventory")
        synchronization_started = time.monotonic()
        daily_limit = self._config.limits_settings.max_llm_calls_per_user_per_day
        remaining_llm = max(
            0,
            daily_limit - self._llm_calls_today.count(user_id),
        )
        usage = _InventoryLLMUsage()
        budget = AgentBudget(self._config.agent_settings)
        adaptive_job = self._current_adaptive_job()
        source: BookingComAccountInventorySource
        if remaining_llm == 0:
            source = BookingComAccountInventorySource(
                check_time=budget.check_time,
                recovery_unavailable_detail=(
                    "Daily LLM allowance is exhausted; the deterministic inventory "
                    "result was preserved."
                ),
            )
        elif adaptive_job is not None:
            settings = replace(
                self._config.agent_settings,
                max_llm_calls=min(
                    self._config.agent_settings.max_llm_calls,
                    remaining_llm,
                ),
            )
            budget = AgentBudget(settings)

            def _adaptive_recovery_factory(guarded_browser: Any) -> BrowserAgent:
                return BrowserAgent(
                    guarded_browser,
                    adaptive_job.runtime.agent_brain(),
                    budget,
                    trace_recorder,
                    recovery_policy=settings.recovery_policy,
                    page_state_resolver=adaptive_job.runtime.page_state_resolver(),
                )

            source = BookingComAccountInventorySource(
                recovery_factory=_adaptive_recovery_factory,
                interpreter_factory=adaptive_job.runtime.inventory_interpreter,
                check_time=budget.check_time,
                llm_calls_used=lambda: adaptive_job.calls_used,
                action_observer=usage.record_action,
            )
        else:
            factory = self._llm_factory_builder(self._config, store)
            settings = replace(
                self._config.agent_settings,
                max_llm_calls=min(
                    self._config.agent_settings.max_llm_calls,
                    remaining_llm,
                ),
            )
            budget = AgentBudget(settings)
            brain = _LazyCountedInventoryBrain(
                factory,
                user_id,
                self._llm_calls_today,
                daily_limit,
                usage,
            )
            interpreter = _LazyCountedInventoryInterpreter(
                factory,
                user_id,
                self._llm_calls_today,
                daily_limit,
                usage,
            )

            def _recovery_factory(guarded_browser: Any) -> BrowserAgent:
                return BrowserAgent(
                    guarded_browser,
                    brain,
                    budget,
                    trace_recorder,
                    recovery_policy=settings.recovery_policy,
                )

            source = BookingComAccountInventorySource(
                recovery_factory=_recovery_factory,
                interpreter=interpreter,
                consume_interpreter_call=budget.consume_llm_call,
                check_time=budget.check_time,
                llm_calls_used=lambda: usage.actual_calls,
                action_observer=usage.record_action,
            )
        try:
            report = SynchronizeBookingAccount(source, repository).execute(
                browser=browser,
                user_id=user_id,
                trigger=trigger,
                session_revision=snapshot.metadata.revision_id,
            )
        except UserKeyInvalidError:
            result = InventoryDiscoveryResult(
                observations=(),
                completeness=InventoryCompleteness.FAILED,
                failure_code=SynchronizationFailureCode.USER_KEY_INVALID,
                failure_detail=(
                    "Your personal LLM key could not be used. Send /setkey to replace "
                    "it, or /deletekey to use the shared key."
                ),
                recovery_outcome=InventoryRecoveryOutcome.UNAVAILABLE,
                recovery_step="inventory_llm_key",
                recovery_detail="Caller-scoped LLM key resolution failed closed.",
                llm_calls_used=usage.actual_calls,
            )
            report = repository.reconcile(
                user_id=user_id,
                run_id=str(uuid.uuid4()),
                trigger=trigger,
                session_revision=snapshot.metadata.revision_id,
                result=result,
                observed_at=datetime.now(UTC),
            )
            report = replace(
                report,
                recovery_outcome=result.recovery_outcome,
                recovery_step=result.recovery_step,
                recovery_detail=result.recovery_detail,
                llm_calls_used=result.llm_calls_used,
                terminal_diagnosis=result.terminal_diagnosis,
            )
        if adaptive_job is not None:
            adaptive_job.record_usage(usage)
        duration_seconds = time.monotonic() - synchronization_started
        if report.recovery_outcome is not InventoryRecoveryOutcome.NOT_NEEDED:
            audit = InventoryRecoveryAudit.from_operational_events(
                outcome=report.recovery_outcome,
                step=report.recovery_step,
                providers=tuple(sorted(usage.providers)),
                models=tuple(sorted(usage.models)),
                roles=tuple(sorted(usage.roles)),
                prompt_versions=tuple(sorted(usage.prompt_versions)),
                llm_calls_used=usage.actual_calls,
                input_tokens=min(usage.input_tokens, 100_000_000),
                output_tokens=min(usage.output_tokens, 100_000_000),
                action_count=usage.action_count,
                duration_ms=min(3_600_000, max(0, round(duration_seconds * 1000))),
                operational_events=trace_recorder.export_operational_events(),
            )
            try:
                repository.attach_recovery_audit(
                    user_id=user_id,
                    run_id=report.run_id,
                    audit=audit,
                )
                report = replace(report, recovery_audit=audit)
            except Exception:
                logger.warning(
                    "Could not persist inventory recovery audit run=%s",
                    report.run_id,
                    exc_info=True,
                )
        logger.info(
            "Booking.com inventory synchronization user=%s trigger=%s "
            "run=%s completeness=%s recovery=%s step=%s llm_calls=%s "
            "actions=%s input_tokens=%s output_tokens=%s duration_ms=%s "
            "providers=%s models=%s roles=%s prompts=%s",
            user_id,
            trigger.value,
            report.run_id,
            report.completeness.value,
            report.recovery_outcome.value,
            report.recovery_step or "none",
            report.llm_calls_used,
            usage.action_count,
            usage.input_tokens,
            usage.output_tokens,
            max(0, round(duration_seconds * 1000)),
            ",".join(sorted(usage.providers)) or "none",
            ",".join(sorted(usage.models)) or "none",
            ",".join(sorted(usage.roles)) or "none",
            ",".join(sorted(usage.prompt_versions)) or "none",
        )
        if report.failure_code is SynchronizationFailureCode.AUTH_REQUIRED:
            provider.mark_reauth_required(user_id, snapshot.metadata.revision_id)
            self._notify_auth_required(user_id)
        else:
            try:
                if browser.is_authenticated():
                    provider.refresh(
                        user_id,
                        snapshot.metadata.revision_id,
                        browser.get_cookies(),
                        datetime.now(UTC),
                    )
            except Exception:
                logger.warning(
                    "Could not refresh the synchronized Booking.com session for user %s",
                    user_id,
                    exc_info=True,
                )
        return report

    def _notify_auth_required(self, user_id: int) -> None:
        if self._auth_required_notifier is None:
            return
        try:
            self._auth_required_notifier(user_id)
        except Exception:
            logger.warning("Could not issue Booking.com reconnect notice for user %s", user_id)

    def _run_booking(
        self, store: SqliteStore, browser: Any, user_id: int, booking: Booking
    ) -> CheckResult:
        history = SqliteCheckHistoryRepository(store)
        users = SqliteUserRepository(store)
        provider = AuthenticatedSessionProvider(users, self._session_repository)
        resolution = provider.resolve(user_id)
        if not resolution.is_ready or resolution.snapshot is None:
            result = self._session_unavailable_result(
                users, user_id, booking, resolution.unavailable_reason
            )
            history.add(result)
            SqliteCheckTraceRepository(store).add(TraceRecorder(booking.booking_id).finish(result))
            return result
        snapshot = resolution.snapshot
        remaining_llm = max(
            0,
            self._config.limits_settings.max_llm_calls_per_user_per_day
            - self._llm_calls_today.count(user_id),
        )
        settings = self._config.agent_settings
        if remaining_llm:
            settings = replace(settings, max_llm_calls=min(settings.max_llm_calls, remaining_llm))
        adaptive_job = self._current_adaptive_job()
        monitor = BookingComSearchMonitor(
            browser=browser,
            # Kept only for the legacy run_all_active API; owner-bound daemon
            # execution below never resolves or falls back to this global state.
            session_manager=SessionManager(_UnavailableLegacySessionRepository()),
            check_history=history,
            booking_repo=SqliteBookingRepository(store),
            failure_tracker=FailureTracker(history),
            llm_factory=(
                None if adaptive_job is not None else self._llm_factory_builder(self._config, store)
            ),
            adaptive_runtime_factory=(
                (lambda _booking: adaptive_job.runtime) if adaptive_job is not None else None
            ),
            agent_settings=settings,
            trace_repo=SqliteCheckTraceRepository(store),
            snapshot_writer=None,
            mobile_profile_id=self._config.mobile_web_settings.profile_id,
        )
        monitor.set_llm_enabled(remaining_llm > 0)
        result = monitor.run_authenticated(booking, snapshot)
        used = min(monitor.last_llm_calls_used, remaining_llm)
        if used and adaptive_job is None:
            self._llm_calls_today.increment(user_id, by=used)

        if (
            result.failure_reason is not None
            and result.failure_reason.code is FailureCode.AUTH_REQUIRED
        ):
            provider.mark_reauth_required(user_id, snapshot.metadata.revision_id)
        else:
            try:
                if browser.is_authenticated():
                    provider.refresh(
                        user_id,
                        snapshot.metadata.revision_id,
                        browser.get_cookies(),
                        datetime.now(UTC),
                    )
            except Exception:
                logger.warning(
                    "Could not refresh the encrypted Booking.com session for user %s",
                    user_id,
                    exc_info=True,
                )

        # The browser monitor owns durable check-history persistence. Re-read
        # access after that potentially long operation and suppress every
        # user-visible post-check effect if the booking owner was revoked.
        if not self._is_active_user(store, user_id):
            return result

        resolver = OwnerBookingNotifierResolver(
            booking_repo=SqliteBookingRepository(store),
            user_repo=SqliteUserRepository(store),
            owner_notifiers=self._notifier_builder(self._config),
            telegram_bot_settings=self._config.telegram_bot_settings,
            telegram_bot_token=os.environ.get("BOOKSAVER_TELEGRAM_BOT_TOKEN"),
        )
        SavingsPipeline(
            booking_repo=SqliteBookingRepository(store),
            savings_repo=SqliteSavingsRepository(store),
            dispatcher=NotificationDispatcher(resolver=resolver),
        ).process([result])
        self._invalid_key_notifier(SqliteUserRepository(store), [result])
        return result

    @staticmethod
    def _session_unavailable_result(
        users: SqliteUserRepository,
        user_id: int,
        booking: Booking,
        reason: SessionUnavailableReason | None,
    ) -> CheckResult:
        user = users.get_by_id(user_id)
        target = (
            str(user.telegram_user_id)
            if user is not None and user.telegram_user_id is not None
            else "<TELEGRAM_USER_ID>"
        )
        label = reason.value if reason is not None else "unavailable"
        return CheckResult.failure(
            booking.booking_id,
            datetime.now(UTC),
            FailureReason(
                code=FailureCode.AUTH_REQUIRED,
                detail=(
                    f"This user's Booking.com session is {label}. Send /connect in the "
                    "private Telegram chat to sign in again. The operator may use "
                    "`booksaver auth import <file> "
                    f"--telegram-user-id {target}` only as recovery. No public-price or "
                    "owner-session fallback was used."
                ),
            ),
        )

    @staticmethod
    def _is_active_user(store: SqliteStore, user_id: int) -> bool:
        user = SqliteUserRepository(store).get_by_id(user_id)
        return user is not None and user.is_active

    @staticmethod
    def _limit_result(booking: Booking, prefix: str) -> CheckResult:
        return CheckResult.failure(
            booking.booking_id,
            datetime.now(UTC),
            FailureReason(
                code=FailureCode.USER_CHECK_LIMIT_REACHED,
                detail=f"{prefix}: daily per-user check limit reached.",
            ),
        )

    def _send_capped_notice(
        self, store: SqliteStore, user_id: int, *, already_marked: bool = False
    ) -> None:
        user = SqliteUserRepository(store).get_by_id(user_id)
        if user is None or not user.is_active:
            return
        if not already_marked:
            due = users_needing_capped_notice([user_id], self._capped_notice_sent_today)
            if not due:
                return
        chat_id = resolve_telegram_chat_id(user, self._config.telegram_bot_settings)
        token = os.environ.get("BOOKSAVER_TELEGRAM_BOT_TOKEN")
        if chat_id is None or not token:
            return
        try:
            TelegramNotifier(bot_token=token, chat_id=str(chat_id)).send(
                "BookSaver: daily check limit reached",
                "You've reached today's limit of "
                f"{self._config.limits_settings.max_checks_per_user_per_day} price "
                "checks. Checks will resume tomorrow.",
            )
        except Exception:
            logger.warning("Failed to send daily-limit notice to user %s", user_id)
