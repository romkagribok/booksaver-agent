from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from booksaver.application.browser_executor import (
    AgenticPriceExecutionService,
    InMemorySessionLeaseBroker,
    OwnerBoundAgenticPriceCheck,
)
from booksaver.application.browser_resilience import DOM_STEP_REGISTRY
from booksaver.application.inventory_executor import (
    InventoryExecutionService,
    OwnerBoundAgenticInventoryExecution,
)
from booksaver.application.ports import InventoryBrowserExecutor, PriceBrowserExecutor
from booksaver.application.savings_pipeline import NotificationDispatcher, SavingsPipeline
from booksaver.application.user_sessions import (
    AuthenticatedSessionProvider,
    UserSessionRepository,
)
from booksaver.daemon.desktop_trial import run_desktop_trial
from booksaver.domain.account_sync import (
    AccountReservation,
    InventoryCompleteness,
    InventoryDiscoveryResult,
    SynchronizationFailureCode,
    SynchronizationReport,
    SynchronizationTrigger,
)
from booksaver.domain.agentic_qualification import (
    AgenticCanaryCheck,
    CriticalAgenticViolation,
)
from booksaver.domain.browser_executor import (
    MAX_COMPUTER_USE_ACTIONS,
    MAX_EXECUTOR_ACTIONS,
    MAX_EXECUTOR_SECONDS,
    MAX_JOB_COST_MICRO_USD,
    ExecutionLimits,
    ExecutionUsage,
    ExecutorSafetyViolation,
    PriceExecutionStatus,
)
from booksaver.domain.browser_resilience import (
    DomJourney,
    DomStepId,
    TerminalBrowserDiagnosis,
)
from booksaver.domain.check_result import CheckResult, FailureCode, FailureReason
from booksaver.domain.inventory_executor import (
    MAX_INVENTORY_ACTIONS,
    MAX_INVENTORY_SECONDS,
    InventoryExecutionLimits,
    InventoryExecutionStatus,
    KnownInventoryReservation,
)
from booksaver.domain.model_policy import BrowserJobKind, UsdAmount
from booksaver.domain.models import Booking, Config
from booksaver.domain.monitoring_stall import (
    is_monitored,
    recovery_message,
    stall_message,
    stall_reason,
)
from booksaver.domain.schedule import (
    ScheduledAdmission,
    ScheduleSettings,
    SlotIdentity,
)
from booksaver.domain.session_maintenance import (
    MAINTENANCE_TIMEOUT,
    SessionMaintenanceCleanupError,
    SessionMaintenanceRun,
    SessionMaintenanceStatus,
    SessionNotice,
    SessionVerificationOutcome,
    SessionVerificationResult,
    as_utc,
)
from booksaver.domain.user import User
from booksaver.domain.user_session import (
    SessionUnavailableReason,
    UserSessionHealth,
    UserSessionSnapshot,
)
from booksaver.infrastructure.notifications.routing import (
    OwnerBookingNotifierResolver,
    resolve_telegram_chat_id,
)
from booksaver.infrastructure.notifications.telegram_notifier import TelegramNotifier
from booksaver.infrastructure.persistence.encrypted_session_store import (
    EncryptedUserSessionRepository,
)
from booksaver.infrastructure.persistence.monitoring_stall import SqliteMonitoringStallRepository
from booksaver.infrastructure.persistence.scheduled_check_slots import (
    SqliteScheduledCheckSlotRepository,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    InventoryExecutionMetrics,
    SqliteAccountReservationRepository,
    SqliteAgenticDisclosureConsentRepository,
    SqliteAgenticQualificationRepository,
    SqliteBookingRepository,
    SqliteCheckHistoryRepository,
    SqliteCheckTraceRepository,
    SqliteInventoryExecutionMetricsRepository,
    SqliteSavingsRepository,
    SqliteStore,
    SqliteUserRepository,
)
from booksaver.monitor.failure_tracker import FailureTracker
from booksaver.monitor.search_check_job import BookingComSearchMonitor
from booksaver.monitor.trace import TraceRecorder
from booksaver.monitor.user_limits import (
    DailyCounter,
    build_check_plan,
    users_needing_capped_notice,
)

logger = logging.getLogger(__name__)

NotifierBuilder = Callable[[Config], list[Any]]
BrowserFactory = Callable[[], AbstractContextManager[Any]]
AuthRequiredNotifier = Callable[[int], None]
# Test seam: replaces Jev inventory with a canned report (no browser is opened).
InventorySynchronizer = Callable[[SqliteStore, int, SynchronizationTrigger], SynchronizationReport]
IncidentRecorderFactory = Callable[[], AbstractContextManager[Any]]
AgenticExecutorFactory = Callable[[InMemorySessionLeaseBroker], PriceBrowserExecutor]
AgenticInventoryExecutorFactory = Callable[[InMemorySessionLeaseBroker], InventoryBrowserExecutor]


@dataclass(slots=True)
class AgenticBrowserJobContext:
    """One hard allowance shared by inventory and price inside a coordinator job."""

    local_user_id: int
    job_kind: BrowserJobKind
    job_id: str
    deadline: datetime
    job_limit_micro_usd: int
    total_actions: int = 0
    computer_actions: int = 0
    cost_micro_usd: int = 0
    inventory_allowance: bool = False
    phase_deadline: datetime | None = None

    def start_phase(self, *, now: datetime | None = None, inventory: bool = False) -> None:
        """Freeze one capability's time cap inside the unchanged operation allowance."""
        current = now or datetime.now(UTC)
        cap = MAX_INVENTORY_SECONDS if inventory else MAX_EXECUTOR_SECONDS
        self.phase_deadline = min(self.deadline, current + timedelta(seconds=cap))

    def remaining_limits(
        self, *, now: datetime | None = None, inventory: bool = False,
    ) -> ExecutionLimits | None:
        current = now or datetime.now(UTC)
        if self.phase_deadline is None:
            self.start_phase(now=current)
        assert self.phase_deadline is not None
        deadline = min(self.deadline, self.phase_deadline)
        remaining_seconds = min(
            MAX_INVENTORY_SECONDS if inventory else MAX_EXECUTOR_SECONDS,
            int((deadline - current).total_seconds()),
        )
        self.inventory_allowance |= inventory
        ceiling = MAX_INVENTORY_ACTIONS if self.inventory_allowance else MAX_EXECUTOR_ACTIONS
        remaining_actions = ceiling - self.total_actions
        if not inventory:
            remaining_actions = min(MAX_EXECUTOR_ACTIONS, remaining_actions)
        remaining_cost = self.job_limit_micro_usd - self.cost_micro_usd
        if remaining_seconds < 1 or remaining_actions < 1 or remaining_cost < 1:
            return None
        limits_type = InventoryExecutionLimits if inventory else ExecutionLimits
        return limits_type(
            deadline=deadline,
            max_actions=remaining_actions,
            max_computer_use_actions=min(
                remaining_actions,
                max(0, MAX_COMPUTER_USE_ACTIONS - self.computer_actions),
            ),
            timeout_seconds=remaining_seconds,
            max_job_cost=UsdAmount(remaining_cost),
        )

    def consume(self, usage: ExecutionUsage) -> None:
        self.total_actions += usage.total_actions
        self.computer_actions += usage.computer_use_actions
        self.cost_micro_usd += usage.cost.micro_usd


# A /checknow within this window of a complete inventory sync reuses it.
_INVENTORY_REUSE_SECONDS = 60.0


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
        notifier_builder: NotifierBuilder,
        browser_factory: BrowserFactory | None = None,
        checks_today: DailyCounter | None = None,
        capped_notice_sent_today: DailyCounter | None = None,
        session_repository: UserSessionRepository | None = None,
        auth_required_notifier: AuthRequiredNotifier | None = None,
        inventory_synchronizer: InventorySynchronizer | None = None,
        incident_recorder_factory: IncidentRecorderFactory | None = None,
        execution_gate: threading.Lock | None = None,
        agentic_executor_factory: AgenticExecutorFactory | None = None,
        agentic_inventory_executor_factory: AgenticInventoryExecutorFactory | None = None,
        bookings_inventory_executor_factory: AgenticInventoryExecutorFactory | None = None,
        desktop_trial_executor_factory: AgenticExecutorFactory | None = None,
        session_verifier: Callable[[bytes, datetime], SessionVerificationResult] | None = None,
        session_uncertain_notifier: AuthRequiredNotifier | None = None,
        session_clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = config
        self._db_path = config.data_directory.path / "booksaver.db"
        self._stop_event = stop_event
        self._notifier_builder = notifier_builder
        self._browser_factory = browser_factory or self._default_browser_factory
        self._session_repository = session_repository or EncryptedUserSessionRepository(
            config.data_directory
        )
        self._auth_required_notifier = auth_required_notifier
        self._session_uncertain_notifier = session_uncertain_notifier
        self._session_verifier = session_verifier
        self._session_clock = session_clock or (lambda: datetime.now(UTC))
        self._maintenance_disabled_logged = False
        self._inventory_synchronizer = inventory_synchronizer
        self._incident_recorder_factory = incident_recorder_factory
        self._checks_today = checks_today or DailyCounter()
        self._capped_notice_sent_today = capped_notice_sent_today or DailyCounter()
        self._execution_gate = execution_gate or threading.Lock()
        self._agentic_executor_factory = agentic_executor_factory
        self._agentic_inventory_executor_factory = agentic_inventory_executor_factory
        self._bookings_inventory_executor_factory = bookings_inventory_executor_factory
        self._desktop_trial_executor_factory = desktop_trial_executor_factory
        self._job_local = threading.local()
        # Callers waiting on an in-flight inventory sync, keyed by Telegram user. A
        # /bookings sent while that user's sync (e.g. post-connect) is running joins
        # it instead of being refused as busy.
        self._inventory_lock = threading.Lock()
        self._inventory_waiters: dict[int, list[Callable[[InventoryCompletion], None]]] = {}
        # Last complete inventory sync per internal user id, so a /checknow right
        # after connect or /bookings does not re-sync a list that was just loaded.
        self._recent_inventory: dict[int, tuple[float, SynchronizationReport, bool]] = {}
        self._monotonic: Callable[[], float] = time.monotonic

    @property
    def checks_today(self) -> dict[int, int]:
        return self._checks_today.snapshot()

    def set_auth_required_notifier(self, notifier: AuthRequiredNotifier | None) -> None:
        self._auth_required_notifier = notifier

    def set_session_uncertain_notifier(self, notifier: AuthRequiredNotifier | None) -> None:
        self._session_uncertain_notifier = notifier

    def request_session_maintenance(
        self, user_id: int, now: datetime | None = None,
    ) -> SessionMaintenanceRun:
        """Verify one exact admitted caller without reservation or model work."""
        status = SessionMaintenanceStatus
        if self._stop_event.is_set():
            return SessionMaintenanceRun(status.STOPPING)
        if not self._execution_gate.acquire(blocking=False):
            return SessionMaintenanceRun(status.BUSY)
        try:
            if self._stop_event.is_set():
                return SessionMaintenanceRun(status.STOPPING)
            at = as_utc(now or self._session_clock())
            verifier = self._session_verifier
            if verifier is None:
                from booksaver.infrastructure.browser.session_maintenance import (
                    BrowserSessionMaintenance,
                )
                if not BrowserSessionMaintenance.is_supported():
                    if not self._maintenance_disabled_logged:
                        logger.warning(
                            "Background session maintenance disabled: unsupported platform"
                        )
                        self._maintenance_disabled_logged = True
                    return SessionMaintenanceRun(status.DISABLED)
                verifier = BrowserSessionMaintenance(
                    mobile_settings=self._config.mobile_web_settings,
                ).verify
            with SqliteStore(self._db_path) as store:
                if not self._is_active_user(store, user_id):
                    return SessionMaintenanceRun(status.UNAVAILABLE)
                snapshot = self._session_repository.load_for_maintenance(user_id)
                if snapshot is None:
                    return SessionMaintenanceRun(status.UNAVAILABLE)
                due = snapshot.metadata.maintenance_due_at(at)
                if due > at:
                    return SessionMaintenanceRun(status.NOT_DUE, due)
                claimed = self._session_repository.claim_maintenance(
                    user_id, snapshot.metadata.revision_id, at,
                )
                if claimed is None:
                    return SessionMaintenanceRun(status.STALE)
                deadline = at + MAINTENANCE_TIMEOUT
                if self._stop_event.is_set() or not self._is_active_user(store, user_id):
                    return SessionMaintenanceRun(status.STOPPING)
                try:
                    verification = verifier(claimed.cookies, deadline)
                except SessionMaintenanceCleanupError:
                    # The caller retains the browser gate until admission is stopped. A
                    # lifecycle shutdown is mandatory if owned processes may still exist.
                    self._stop_event.set()
                    logger.error("Session maintenance cleanup unconfirmed; stopping daemon")
                    return SessionMaintenanceRun(status.STOPPING)
                except Exception:
                    # No exception strings: browser failures can contain cookies or URLs.
                    logger.warning("Session maintenance unavailable for user %s", user_id)
                    verification = SessionVerificationResult(SessionVerificationOutcome.RETRY_LATER)
                finished = as_utc(self._session_clock())
                if finished > deadline:
                    verification = SessionVerificationResult(SessionVerificationOutcome.RETRY_LATER)
                if self._stop_event.is_set():
                    return SessionMaintenanceRun(status.STOPPING)
                # Serialize the final access decision against revoke/purge DB transactions.
                # No browser work runs under this short write lock.
                with store.conn:
                    store.conn.execute("BEGIN IMMEDIATE")
                    if not self._is_active_user(store, user_id):
                        return SessionMaintenanceRun(status.UNAVAILABLE)
                    attempt = claimed.metadata.maintenance.attempt_id
                    assert attempt is not None
                    updated = self._session_repository.complete_maintenance(
                        user_id, claimed.metadata.revision_id, attempt, verification, finished,
                    )
                if updated is None:
                    return SessionMaintenanceRun(status.STALE)
                if verification.outcome is SessionVerificationOutcome.AUTHENTICATED:
                    outcome = status.VERIFIED
                elif verification.outcome is SessionVerificationOutcome.RETRY_LATER:
                    outcome = status.RETRY_LATER
                else:
                    outcome = status.REAUTH_REQUIRED
                self._notify_session_issue(user_id, updated.metadata.revision_id, finished)
                return SessionMaintenanceRun(outcome, updated.metadata.maintenance.next_attempt_at)
        finally:
            self._execution_gate.release()

    def run_session_maintenance(self) -> datetime | None:
        """One due admitted user per scheduler tick; never depend on eligible bookings."""
        if self._stop_event.is_set():
            return None
        now = as_utc(self._session_clock())
        due_users: list[tuple[datetime, int]] = []
        with SqliteStore(self._db_path) as store:
            for user in SqliteUserRepository(store).list_active():
                try:
                    snapshot = self._session_repository.load_for_maintenance(user.user_id)
                except Exception:
                    # An unreadable caller cannot starve other admitted users.
                    continue
                if snapshot is not None:
                    due_users.append((snapshot.metadata.maintenance_due_at(now), user.user_id))
        if not due_users:
            return None
        due, user_id = min(due_users)
        if due > now:
            return due
        result = self.request_session_maintenance(user_id, now)
        if result.status in {SessionMaintenanceStatus.BUSY, SessionMaintenanceStatus.STOPPING,
                             SessionMaintenanceStatus.DISABLED}:
            return now + timedelta(seconds=60)
        # Allow other due users at the next ordinary discovery tick, without a catch-up burst.
        return min(result.next_attempt_at or now + timedelta(seconds=60),
                   now + timedelta(seconds=60))

    @contextmanager
    def _job_scope(self, user_id: int, job_kind: BrowserJobKind) -> Iterator[None]:
        """Admit one shared inventory-and-price allowance for this coordinator job."""
        previous = getattr(self._job_local, "agentic", None)
        self._job_local.agentic = AgenticBrowserJobContext(
            local_user_id=user_id,
            job_kind=job_kind,
            job_id=f"agentic-{job_kind.value}-{uuid.uuid4().hex}",
            deadline=datetime.now(UTC) + timedelta(seconds=(
                MAX_INVENTORY_SECONDS + MAX_EXECUTOR_SECONDS
                if job_kind in {BrowserJobKind.CHECK_NOW, BrowserJobKind.SCHEDULED_SLOT}
                else MAX_INVENTORY_SECONDS
            )),
            job_limit_micro_usd=self._config.agent_settings.max_job_cost_micro_usd,
        )
        try:
            yield
        finally:
            self._job_local.agentic = previous

    def _current_agentic_job(self) -> AgenticBrowserJobContext | None:
        current = getattr(self._job_local, "agentic", None)
        return current if isinstance(current, AgenticBrowserJobContext) else None

    @contextmanager
    def _resume_agentic_job(
        self,
        context: AgenticBrowserJobContext | None,
    ) -> Iterator[None]:
        """Restore one previously admitted job so later work sees only its residual limits."""
        previous = getattr(self._job_local, "agentic", None)
        self._job_local.agentic = context
        try:
            yield
        finally:
            self._job_local.agentic = previous

    def _agentic_job(self, user_id: int, job_kind: BrowserJobKind) -> AgenticBrowserJobContext:
        context = self._current_agentic_job()
        if context is None or context.local_user_id != user_id:
            context = AgenticBrowserJobContext(
                local_user_id=user_id,
                job_kind=job_kind,
                job_id=f"agentic-{job_kind.value}-{uuid.uuid4().hex}",
                deadline=datetime.now(UTC) + timedelta(seconds=MAX_INVENTORY_SECONDS),
                job_limit_micro_usd=self._config.agent_settings.max_job_cost_micro_usd,
            )
        return context

    def _record_post_browser_incidents(self, check_result: CheckResult | None) -> None:
        """Resolve open DOM incidents for the steps a successful check just proved."""
        if self._incident_recorder_factory is None:
            return
        try:
            resolved_steps = self._incident_handoffs(check_result=check_result)
            if not resolved_steps:
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
        except Exception:
            # Incident persistence is operationally secondary and must never
            # alter the completed caller result.
            logger.warning("DOM incident post-browser handoff failed")

    @staticmethod
    def _incident_handoffs(
        *,
        check_result: CheckResult | None,
    ) -> tuple[tuple[DomJourney, DomStepId, datetime], ...]:
        """Price steps a successful check proved, minus any that needed assistance."""
        if check_result is None or check_result.failure_reason is not None:
            return ()
        from booksaver.application.browser_resilience import PRICE_SEARCH_DOM_STEPS

        diagnoses: tuple[TerminalBrowserDiagnosis, ...] = (
            *check_result.assisted_diagnoses,
            *((check_result.terminal_diagnosis,) if check_result.terminal_diagnosis else ()),
        )
        assisted_steps = {diagnosis.step_id for diagnosis in diagnoses}
        observed_at = check_result.checked_at.astimezone(UTC)
        return tuple(
            (DOM_STEP_REGISTRY.definition(step_id).journey, step_id, observed_at)
            for step_id in PRICE_SEARCH_DOM_STEPS
            if step_id not in assisted_steps
        )

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
                    with self._job_scope(identity.user_id, BrowserJobKind.SCHEDULED_SLOT):
                        self._run_scheduled_user_locked(store, identity.user_id)
            finally:
                self._report_monitoring_stalls(identity.user_id)
                self._inform_provider_change(identity.user_id)
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
        callback = on_complete or (lambda _completion: None)
        with self._inventory_lock:
            waiters = self._inventory_waiters.get(telegram_user_id)
            if waiters is not None:
                waiters.append(callback)
                return ImmediateAdmission.ACCEPTED
            if not self._execution_gate.acquire(blocking=False):
                return ImmediateAdmission.BUSY
            worker = threading.Thread(
                target=self._run_inventory_worker,
                args=(telegram_user_id, trigger),
                name=f"booksaver-inventory-{telegram_user_id}",
                daemon=True,
            )
            # Start under the lock so nobody can join a run whose worker never starts.
            try:
                worker.start()
            except Exception:
                self._execution_gate.release()
                raise
            self._inventory_waiters[telegram_user_id] = [callback]
        return ImmediateAdmission.ACCEPTED

    def after_inventory_sync(
        self,
        telegram_user_id: int,
        on_settled: Callable[[], None],
    ) -> bool:
        """Run `on_settled` once this caller's in-flight inventory sync finishes.

        Returns False (and never calls `on_settled`) when no sync is running for them.
        """
        with self._inventory_lock:
            waiters = self._inventory_waiters.get(telegram_user_id)
            if waiters is None:
                return False
            waiters.append(lambda _completion: on_settled())
            return True

    def _run_inventory_worker(
        self,
        telegram_user_id: int,
        trigger: SynchronizationTrigger,
    ) -> None:
        completion = InventoryCompletion(None)
        try:
            if self._stop_event.is_set():
                return
            with SqliteStore(self._db_path) as store:
                user = SqliteUserRepository(store).get_by_telegram_id(telegram_user_id)
                if user is None or not user.is_active:
                    return
                with self._job_scope(user.user_id, BrowserJobKind.BOOKINGS_SYNC):
                    report, _used_agentic = self._synchronize_user_job(
                        store,
                        user.user_id,
                        trigger,
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
            # Detach waiters and release the gate atomically so a concurrent request
            # either joins this run or starts a fresh one, never sees a spurious BUSY.
            with self._inventory_lock:
                callbacks = self._inventory_waiters.pop(telegram_user_id, [])
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
            for on_complete in callbacks:
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
                with self._job_scope(user.user_id, BrowserJobKind.CHECK_NOW):
                    report: SynchronizationReport | None = None
                    result: CheckResult | None = None
                    used_agentic_inventory = False
                    try:
                        try:
                            recent = self._recent_complete_inventory(user.user_id)
                            if recent is not None:
                                report, used_agentic_inventory = recent
                            else:
                                report, used_agentic_inventory = self._synchronize_user_job(
                                    store,
                                    user.user_id,
                                    SynchronizationTrigger.CHECK_NOW,
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
                        if used_agentic_inventory:
                            current_run_booking_ids = set(
                                SqliteAccountReservationRepository(
                                    store
                                ).positively_observed_booking_ids_for_run(
                                    user_id=user.user_id,
                                    run_id=report.run_id,
                                )
                            )
                            if booking_id not in current_run_booking_ids:
                                unavailable_detail = (
                                    report.failure_detail
                                    if report.completeness is InventoryCompleteness.FAILED
                                    and report.failure_detail
                                    else (
                                        "The selected reservation was not positively verified "
                                        "in the current Booking.com refresh."
                                    )
                                )
                                completion = ImmediateCompletion(
                                    ImmediateCompletionKind.UNAVAILABLE,
                                    unavailable_detail=unavailable_detail,
                                )
                                return
                        elif report.completeness is not InventoryCompleteness.COMPLETE:
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
                                with self._browser_factory() as browser:
                                    if self._stop_event.is_set():
                                        return
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
                    finally:
                        self._record_post_browser_incidents(result)

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
            agentic_jobs_by_user: dict[int, AgenticBrowserJobContext] = {}
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
                    with self._job_scope(user.user_id, BrowserJobKind.SCHEDULED_SLOT):
                        report, used_agentic_inventory = self._synchronize_user_job(
                            store,
                            user.user_id,
                            SynchronizationTrigger.SCHEDULED,
                        )
                        current_agentic_job = self._current_agentic_job()
                        if current_agentic_job is not None:
                            agentic_jobs_by_user[user.user_id] = current_agentic_job
                except Exception:
                    logger.exception(
                        "Scheduled inventory synchronization failed for user %s",
                        user.user_id,
                    )
                    continue
                if used_agentic_inventory:
                    current_ids = set(
                        SqliteAccountReservationRepository(
                            store
                        ).positively_observed_booking_ids_for_run(
                            user_id=user.user_id,
                            run_id=report.run_id,
                        )
                    )
                    bookings_by_user[user.user_id] = [
                        booking
                        for booking in bookings.list_active_for_user(user.user_id)
                        if booking.booking_id in current_ids
                    ]
                elif report.completeness is InventoryCompleteness.COMPLETE:
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
                with self._resume_agentic_job(agentic_jobs_by_user.get(user_id)):
                    with self._browser_factory() as browser:
                        if self._stop_event.is_set():
                            break
                        result = self._run_booking(store, browser, user_id, booking)
                self._record_post_browser_incidents(result)
                if (
                    self._auth_required_notifier is not None
                    and result.failure_reason is not None
                    and result.failure_reason.code is FailureCode.AUTH_REQUIRED
                ):
                    try:
                        self._notify_auth_required(user_id)
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
            report, used_agentic_inventory = self._synchronize_user_job(
                store,
                user_id,
                SynchronizationTrigger.SCHEDULED,
            )
        except Exception:
            logger.exception(
                "Scheduled inventory synchronization failed for user %s",
                user_id,
            )
            return
        if (
            not used_agentic_inventory
            and report.completeness is not InventoryCompleteness.COMPLETE
        ):
            return

        active_bookings = bookings.list_active_for_user(user_id)
        if used_agentic_inventory:
            current_run_booking_ids = set(
                SqliteAccountReservationRepository(
                    store
                ).positively_observed_booking_ids_for_run(
                    user_id=user_id,
                    run_id=report.run_id,
                )
            )
            active_bookings = [
                booking
                for booking in active_bookings
                if booking.booking_id in current_run_booking_ids
            ]
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

        checked: list[tuple[Booking, CheckResult]] = []
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
                if self._stop_event.is_set():
                    break
                result = self._run_booking(
                    store,
                    browser,
                    planned_user_id,
                    booking,
                )
            checked.append((booking, result))
            self._record_post_browser_incidents(result)
            if (
                self._auth_required_notifier is not None
                and result.failure_reason is not None
                and result.failure_reason.code is FailureCode.AUTH_REQUIRED
            ):
                self._notify_auth_required(planned_user_id)

        # Silent desktop price trial (intent 041): after every normal check of the slot, so a
        # reading cannot use the time allowance those checks share.
        if (
            self._desktop_trial_executor_factory is not None
            and self._config.desktop_trial_settings.active_for(user_id, datetime.now(UTC).date())
        ):
            run_desktop_trial(
                store=store,
                executor_factory=self._desktop_trial_executor_factory,
                sessions=AuthenticatedSessionProvider(users, self._session_repository),
                user_id=user_id,
                checked=checked,
                stop_event=self._stop_event,
            )

    def _synchronize_user_job(
        self,
        store: SqliteStore,
        user_id: int,
        trigger: SynchronizationTrigger,
    ) -> tuple[SynchronizationReport, bool]:
        """Run one inventory sync; the flag is False only for a report no run observed."""
        try:
            report, used_agentic = self._synchronize_user_job_uncached(
                store, user_id, trigger,
            )
        except BaseException:
            with self._inventory_lock:
                self._recent_inventory.pop(user_id, None)
            raise
        with self._inventory_lock:
            if report.succeeded:
                self._recent_inventory[user_id] = (self._monotonic(), report, used_agentic)
            else:
                self._recent_inventory.pop(user_id, None)
        return report, used_agentic

    def _recent_complete_inventory(
        self, user_id: int,
    ) -> tuple[SynchronizationReport, bool] | None:
        """Return a complete sync from the last minute, or None if a fresh one is needed."""
        with self._inventory_lock:
            recent = self._recent_inventory.get(user_id)
        if recent is None or self._monotonic() - recent[0] >= _INVENTORY_REUSE_SECONDS:
            return None
        return recent[1], recent[2]

    def _synchronize_user_job_uncached(
        self,
        store: SqliteStore,
        user_id: int,
        trigger: SynchronizationTrigger,
    ) -> tuple[SynchronizationReport, bool]:
        if self._inventory_synchronizer is not None:
            return self._inventory_synchronizer(store, user_id, trigger), False
        if not self._is_active_user(store, user_id):
            # Every active user is served by the code reader with Jev (ADR-062); a caller
            # revoked before the sync starts gets no browser at all.
            return (
                SynchronizationReport(
                    run_id=str(uuid.uuid4()),
                    completeness=InventoryCompleteness.FAILED,
                    discovered=0,
                    eligible=0,
                    ineligible=0,
                    failure_code=SynchronizationFailureCode.AUTH_REQUIRED,
                    failure_detail="This user is no longer authorized for Booking.com syncs.",
                ),
                False,
            )
        return self._synchronize_agentic_inventory(store, user_id, trigger), True

    def _synchronize_agentic_inventory(
        self,
        store: SqliteStore,
        user_id: int,
        trigger: SynchronizationTrigger,
    ) -> SynchronizationReport:
        users = SqliteUserRepository(store)
        provider = AuthenticatedSessionProvider(users, self._session_repository)
        resolution = provider.resolve(user_id)
        repository = SqliteAccountReservationRepository(store)
        if not resolution.is_ready or resolution.snapshot is None:
            recoverable = (resolution.unavailable_reason is SessionUnavailableReason.EXPIRED
                           and self._session_repository.load_for_maintenance(user_id) is not None)
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
                    SynchronizationFailureCode.VERIFICATION_PENDING
                    if recoverable
                    else SynchronizationFailureCode.AUTH_REQUIRED,
                    "We could not verify your saved Booking.com login yet. "
                    "We will try again automatically."
                    if recoverable
                    else f"Booking.com session is {reason}.",
                ),
                observed_at=datetime.now(UTC),
            )
            self._notify_auth_required(user_id)
            return report

        snapshot = resolution.snapshot
        executor_factory = (
            self._bookings_inventory_executor_factory
            if trigger is SynchronizationTrigger.BOOKINGS
            else self._agentic_inventory_executor_factory
        )
        if executor_factory is None:
            return repository.reconcile(
                user_id=user_id,
                run_id=str(uuid.uuid4()),
                trigger=trigger,
                session_revision=snapshot.metadata.revision_id,
                result=InventoryDiscoveryResult.failed(
                    SynchronizationFailureCode.NAVIGATION_FAILED,
                    "Booking.com syncs are unavailable: the inventory executor is not "
                    "configured.",
                ),
                observed_at=datetime.now(UTC),
            )
        current_agentic_job = self._current_agentic_job()
        context = self._agentic_job(
            user_id,
            current_agentic_job.job_kind
            if current_agentic_job is not None
            else BrowserJobKind.BOOKINGS_SYNC,
        )
        context.start_phase(inventory=True)
        limits = context.remaining_limits(inventory=True)
        if limits is None:
            return repository.reconcile(
                user_id=user_id,
                run_id=str(uuid.uuid4()),
                trigger=trigger,
                session_revision=snapshot.metadata.revision_id,
                result=InventoryDiscoveryResult.failed(
                    SynchronizationFailureCode.NAVIGATION_FAILED,
                    "The shared agentic browser job allowance was exhausted.",
                ),
                observed_at=datetime.now(UTC),
            )

        lease_broker = InMemorySessionLeaseBroker()
        executor = executor_factory(lease_broker)
        saved_reservations = repository.list_for_user(user_id)
        known_reservations = tuple(
            KnownInventoryReservation(
                confirmation_id=reservation.observation.confirmation_id,
                property_name=reservation.observation.property_name,
                check_in=reservation.observation.check_in,
                check_out=reservation.observation.check_out,
            )
            for reservation in saved_reservations
            # A presence-only match cannot fill missing booking facts. Keep incomplete
            # records on the detail-discovery path until they qualify for monitoring.
            if reservation.eligibility.is_eligible
            and reservation.observation.confirmation_id is not None
            and reservation.observation.property_name is not None
            and reservation.observation.check_in is not None
            and reservation.observation.check_out is not None
        )[:25]
        outcome = OwnerBoundAgenticInventoryExecution(
            InventoryExecutionService(executor, lease_broker),
            lease_broker,
        ).execute(
            owner_user_id=user_id,
            session_material=snapshot.cookies,
            limits=limits,
            known_confirmation_ids=tuple(
                dict.fromkeys(
                    reservation.observation.confirmation_id
                    for reservation in saved_reservations
                    if reservation.observation.confirmation_id is not None
                )
            )[:25],
            known_reservations=known_reservations,
        )
        context.consume(outcome.result.usage)
        observed_at = datetime.now(UTC)
        report = repository.reconcile(
            user_id=user_id,
            run_id=str(uuid.uuid4()),
            trigger=trigger,
            session_revision=snapshot.metadata.revision_id,
            result=outcome.discovery_result,
            observed_at=observed_at,
        )
        report = replace(
            report,
            upcoming_empty_observed=(
                outcome.result.status is InventoryExecutionStatus.EMPTY_UPCOMING
                and outcome.validation.failure is None
            ),
        )
        provenance = outcome.result.provenance
        metrics = InventoryExecutionMetrics(
            run_id=report.run_id,
            user_id=user_id,
            source=(
                provenance.source.value if provenance is not None else "agentic_inventory"
            ),
            terminal_status=outcome.result.status.value,
            accepted_count=outcome.validation.accepted_positive_count,
            rejected_count=outcome.validation.rejected_reservation_count,
            scope_count=outcome.validation.scope_count,
            page_count=outcome.validation.page_count,
            detail_count=outcome.validation.detail_count,
            semantic_action_count=(
                outcome.result.usage.total_actions
                - outcome.result.usage.computer_use_actions
            ),
            computer_action_count=outcome.result.usage.computer_use_actions,
            input_tokens=outcome.result.usage.tokens.input_tokens,
            output_tokens=outcome.result.usage.tokens.output_tokens,
            model_cost_micro_usd=outcome.result.usage.cost.micro_usd,
            latency_ms=outcome.result.latency_ms,
            fallback_used=outcome.result.fallback_used,
            safety_codes=tuple(
                sorted(violation.value for violation in outcome.result.safety_violations)
            ),
        )
        try:
            SqliteInventoryExecutionMetricsRepository(store).record(metrics)
        except Exception:
            logger.warning(
                "Could not record redacted agentic inventory metrics run=%s",
                report.run_id,
                exc_info=True,
            )

        if report.failure_code is SynchronizationFailureCode.AUTH_REQUIRED:
            provider.mark_reauth_required(user_id, snapshot.metadata.revision_id)
            self._notify_auth_required(user_id)
        elif outcome.refreshed_session is not None:
            try:
                provider.refresh(
                    user_id,
                    snapshot.metadata.revision_id,
                    outcome.refreshed_session,
                    observed_at,
                )
            except Exception:
                logger.warning(
                    "Could not persist verified agentic inventory session refresh for user %s",
                    user_id,
                    exc_info=True,
                )
        logger.info(
            "Agentic inventory synchronization user=%s trigger=%s run=%s status=%s "
            "accepted=%s rejected=%s actions=%s computer_actions=%s cost_micro_usd=%s "
            "duration_ms=%s fallback=%s",
            user_id,
            trigger.value,
            report.run_id,
            outcome.result.status.value,
            outcome.validation.accepted_positive_count,
            outcome.validation.rejected_reservation_count,
            outcome.result.usage.total_actions,
            outcome.result.usage.computer_use_actions,
            outcome.result.usage.cost.micro_usd,
            outcome.result.latency_ms,
            outcome.result.fallback_used,
        )
        return report

    def _notify_auth_required(self, user_id: int) -> None:
        try:
            status = self._session_repository.status(user_id)
            if status.revision_id is not None:
                self._notify_session_issue(user_id, status.revision_id, self._session_clock())
            elif self._auth_required_notifier is not None:
                # Missing or undecryptable bundles have no revision to claim a
                # once-per-revision notice against; the notifier's own cooldown applies.
                self._auth_required_notifier(user_id)
        except Exception:
            logger.warning("Could not issue Booking.com reconnect notice for user %s", user_id)

    def _notify_session_issue(self, user_id: int, revision: str, now: datetime) -> None:
        if self._auth_required_notifier is None and self._session_uncertain_notifier is None:
            return
        try:
            with SqliteStore(self._db_path) as store:
                with store.conn:
                    store.conn.execute("BEGIN IMMEDIATE")
                    if not self._is_active_user(store, user_id):
                        return
                    reason = self._session_repository.claim_session_notice(user_id, revision, now)
            if reason is None:
                return
            current = self._session_repository.status(user_id)
            if current.revision_id != revision:
                return
            notifier = (self._auth_required_notifier if reason is SessionNotice.SIGNED_OUT
                        else self._session_uncertain_notifier)
            if notifier is not None:
                notifier(user_id)
        except Exception:
            logger.warning("Could not issue Booking.com session notice for user %s", user_id)

    def _run_booking(
        self, store: SqliteStore, browser: Any, user_id: int, booking: Booking
    ) -> CheckResult:
        # shortcut: `browser` (the per-check context callers open) is unused since Jev runs its
        # own browser; drop it and the browser_factory together in a follow-up.
        del browser
        agentic_job = self._current_agentic_job()
        if agentic_job is not None:
            agentic_job.start_phase()
        history = SqliteCheckHistoryRepository(store)
        users = SqliteUserRepository(store)
        provider = AuthenticatedSessionProvider(users, self._session_repository)
        resolution = provider.resolve(user_id)
        if not resolution.is_ready or resolution.snapshot is None:
            reason = resolution.unavailable_reason
            if (reason is SessionUnavailableReason.EXPIRED
                and self._session_repository.load_for_maintenance(user_id) is None):
                reason = SessionUnavailableReason.REAUTH_REQUIRED
            result = self._session_unavailable_result(
                users, user_id, booking, reason
            )
            history.add(result)
            SqliteCheckTraceRepository(store).add(TraceRecorder(booking.booking_id).finish(result))
            return result
        snapshot = resolution.snapshot
        user = users.get_by_id(user_id)
        if user is None or not user.is_active:
            result = CheckResult.failure(
                booking.booking_id,
                datetime.now(UTC),
                FailureReason(
                    FailureCode.CALLER_REVOKED,
                    "The booking owner is no longer authorized for browser execution.",
                ),
            )
            history.add(result)
            return result
        return self._run_booking_price(store, user_id, booking, user, provider, snapshot, history)

    def _run_booking_price(
        self,
        store: SqliteStore,
        user_id: int,
        booking: Booking,
        user: User,
        provider: AuthenticatedSessionProvider,
        snapshot: UserSessionSnapshot,
        history: SqliteCheckHistoryRepository,
    ) -> CheckResult:
        """Run the Jev price method with all of its canonical effects (ADR-056)."""
        agentic_settings = self._config.agentic_browser_settings
        agentic_price_check: OwnerBoundAgenticPriceCheck | None = None
        agentic_limits: ExecutionLimits | None = None
        current_agentic_job = self._current_agentic_job()
        agentic_job = self._agentic_job(
            user_id,
            current_agentic_job.job_kind
            if current_agentic_job is not None
            else BrowserJobKind.CHECK_NOW,
        )
        if self._agentic_executor_factory is not None:
            agentic_limits = agentic_job.remaining_limits()
            if agentic_limits is None:
                result = CheckResult.failure(
                    booking.booking_id,
                    datetime.now(UTC),
                    FailureReason(
                        FailureCode.BUDGET_EXCEEDED,
                        "The shared inventory-and-price browser allowance was exhausted.",
                    ),
                )
                history.add(result)
                SqliteCheckTraceRepository(store).add(
                    TraceRecorder(booking.booking_id).finish(result)
                )
                return result
            lease_broker = InMemorySessionLeaseBroker()
            agentic_price_check = OwnerBoundAgenticPriceCheck(
                AgenticPriceExecutionService(
                    self._agentic_executor_factory(lease_broker), lease_broker,
                ),
                lease_broker,
            )
        monitor = BookingComSearchMonitor(
            check_history=history,
            failure_tracker=FailureTracker(history),
            trace_repo=SqliteCheckTraceRepository(store),
            mobile_profile_id=self._config.mobile_web_settings.profile_id,
            agentic_price_check=agentic_price_check,
            agentic_owner_user_id=user_id,
            agentic_execution_limits=agentic_limits,
        )
        result = monitor.run_authenticated(booking, snapshot)
        agentic_outcome = monitor.last_agentic_outcome
        if agentic_outcome is not None:
            agentic_job.consume(agentic_outcome.result.usage)
        if user.is_owner and agentic_outcome is not None:
            blocked_statuses = {
                PriceExecutionStatus.SESSION_UNAVAILABLE,
                PriceExecutionStatus.SIGNED_OUT,
                PriceExecutionStatus.MFA_REQUIRED,
                PriceExecutionStatus.CAPTCHA,
                PriceExecutionStatus.BOT_WALL,
                PriceExecutionStatus.UNAVAILABLE,
            }
            violations: set[CriticalAgenticViolation] = set()
            if (
                ExecutorSafetyViolation.PROHIBITED_ACTION_EXECUTED
                in agentic_outcome.result.safety_violations
            ):
                violations.add(CriticalAgenticViolation.PROHIBITED_ACTION_EXECUTED)
            if (
                ExecutorSafetyViolation.NON_ALLOWLISTED_DESTINATION
                in agentic_outcome.result.safety_violations
            ):
                violations.add(CriticalAgenticViolation.NON_ALLOWLISTED_DESTINATION)
            if agentic_outcome.result.usage.cost.micro_usd > MAX_JOB_COST_MICRO_USD:
                violations.add(CriticalAgenticViolation.JOB_COST_CAP_BREACH)
            try:
                SqliteAgenticQualificationRepository(store).record_check(
                    AgenticCanaryCheck(
                        check_id=result.check_id,
                        owner_user_id=user_id,
                        observed_at=result.checked_at,
                        eligible_unblocked=(agentic_outcome.result.status not in blocked_statuses),
                        valid_observation=agentic_outcome.validation.accepted,
                        manual_price_correct=None,
                        model_cost=agentic_outcome.result.usage.cost,
                        duration_ms=agentic_outcome.result.latency_ms,
                        fallback_used=agentic_outcome.result.fallback_used,
                        policy_version=(
                            agentic_settings.price_executor.qualification_policy_version
                        ),
                        violations=frozenset(violations),
                    )
                )
            except Exception:
                logger.warning(
                    "Could not record redacted owner canary metrics for check %s",
                    result.check_id,
                    exc_info=True,
                )

        if (
            result.failure_reason is not None
            and result.failure_reason.code is FailureCode.AUTH_REQUIRED
        ):
            provider.mark_reauth_required(user_id, snapshot.metadata.revision_id)
        else:
            try:
                refreshed = (
                    agentic_outcome.refreshed_session if agentic_outcome is not None else None
                )
                if refreshed is not None:
                    provider.refresh(
                        user_id,
                        snapshot.metadata.revision_id,
                        refreshed,
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
        return result

    @staticmethod
    def _session_unavailable_result(
        users: SqliteUserRepository,
        user_id: int,
        booking: Booking,
        reason: SessionUnavailableReason | None,
    ) -> CheckResult:
        if reason is SessionUnavailableReason.EXPIRED:
            return CheckResult.failure(
                booking.booking_id, datetime.now(UTC),
                FailureReason(
                    code=FailureCode.OBSERVATION_UNAVAILABLE,
                    detail="We could not verify your saved Booking.com login yet. "
                           "We will try again automatically.",
                ),
            )
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

    def _inform_provider_change(self, user_id: int) -> None:
        """Tell an invitee once that TypeSafe's Jev now reads page content (ADR-062)."""
        try:
            version = self._config.agentic_browser_settings.disclosure_version
            with SqliteStore(self._db_path) as store:
                user = SqliteUserRepository(store).get_by_id(user_id)
                consents = SqliteAgenticDisclosureConsentRepository(store)
                record = consents.get(user_id)
                if (
                    user is None or user.is_owner or not user.is_active
                    or (record is not None and record.disclosure_version == version)
                    or self._session_repository.status(user_id).health
                    is not UserSessionHealth.READY
                ):
                    return
                chat_id = resolve_telegram_chat_id(user, self._config.telegram_bot_settings)
                token = os.environ.get("BOOKSAVER_TELEGRAM_BOT_TOKEN")
                if chat_id is None or not token:
                    return
                TelegramNotifier(bot_token=token, chat_id=str(chat_id)).send(
                    "BookSaver: a change to how your bookings are read",
                    "BookSaver now uses TypeSafe's Jev, instead of Anthropic's Claude, to read the "
                    "Booking.com pages it checks for you: hotel offers, and the price and "
                    "cancellation lines of your reservations. Your cookies and password stay on "
                    "this server, and BookSaver still never books, pays or cancels anything. No "
                    "action is needed.",
                )
                consents.acknowledge(
                    user_id=user_id, disclosure_version=version, acknowledged_at=datetime.now(UTC),
                )
        except Exception:
            logger.warning("Could not inform user %s of the provider change", user_id,
                           exc_info=True)

    def _report_monitoring_stalls(self, user_id: int) -> None:
        """Tell one user about stalled or recovered reservations; never affects the slot."""
        try:
            if self._session_repository.status(user_id).health is not UserSessionHealth.READY:
                return  # A sign-in or uncertain-session notice covers this user.
            now = datetime.now(UTC)
            with SqliteStore(self._db_path) as store:
                user = SqliteUserRepository(store).get_by_id(user_id)
                chat_id = (
                    resolve_telegram_chat_id(user, self._config.telegram_bot_settings)
                    if user is not None and user.is_active
                    else None
                )
                token = os.environ.get("BOOKSAVER_TELEGRAM_BOT_TOKEN")
                if chat_id is None or not token:
                    return
                notifier = TelegramNotifier(bot_token=token, chat_id=str(chat_id))
                stalls = SqliteMonitoringStallRepository(store)
                notices = stalls.notices(user_id)
                reservations = [
                    r for r in stalls.list_upcoming(user_id, now.date()) if is_monitored(r)
                ]
                for key in notices.keys() - {r.reservation_key for r in reservations}:
                    stalls.delete(user_id, key)
                for reservation in reservations:
                    reason = stall_reason(reservation, now)
                    notified_at = notices.get(reservation.reservation_key)
                    conclusive_at = reservation.last_conclusive_at
                    # A result newer than the notice ended that stall, even if a new one began.
                    if notified_at is not None and (
                        reason is None
                        or (conclusive_at is not None and conclusive_at > notified_at)
                    ):
                        notifier.send(*recovery_message(reservation))
                        stalls.delete(user_id, reservation.reservation_key)
                        notified_at = None
                    # Recorded only after delivery, so a failed send retries on the next run.
                    if reason is not None and notified_at is None:
                        notifier.send(*stall_message(reservation, reason))
                        stalls.record(user_id, reservation.reservation_key, reason, now)
        except Exception:
            logger.warning("Could not report monitoring stalls for user %s", user_id, exc_info=True)

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
