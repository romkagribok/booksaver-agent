from __future__ import annotations

import logging
import os
import re
import threading
import time
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from booksaver.application.account_sync import SynchronizeBookingAccount
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
    AgentStopReason,
    AgentTurnContext,
    BudgetExceeded,
)
from booksaver.domain.check_result import CheckResult, FailureCode, FailureReason
from booksaver.domain.errors import UserKeyInvalidError
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
from booksaver.monitor.trace import SnapshotWriter, TraceRecorder
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
        self.input_tokens += _bounded_usage_count(
            getattr(provider_usage, "input_tokens", 0)
        )
        self.output_tokens += _bounded_usage_count(
            getattr(provider_usage, "output_tokens", 0)
        )

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
            self._usage.record_delegate_call(
                self._delegate, default_role="navigation_agent"
            )


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

    def interpret(
        self, page_text: str, source_url: str
    ) -> tuple[Any, ...]:
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
            self._usage.record_delegate_call(
                self._delegate, default_role="inventory_interpreter"
            )


class _UnavailableLegacySessionRepository:
    """Null object preventing accidental daemon fallback to legacy global cookies."""

    def load(self, _platform: Any) -> None:
        return None

    def save(self, _session: Any) -> None:
        raise RuntimeError("Legacy global session writes are disabled in the daemon")


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
        self._checks_today = checks_today or DailyCounter()
        self._llm_calls_today = llm_calls_today or DailyCounter()
        self._capped_notice_sent_today = capped_notice_sent_today or DailyCounter()
        self._execution_gate = execution_gate or threading.Lock()

    @property
    def checks_today(self) -> dict[int, int]:
        return self._checks_today.snapshot()

    @property
    def llm_calls_today(self) -> dict[int, int]:
        return self._llm_calls_today.snapshot()

    def set_auth_required_notifier(
        self, notifier: AuthRequiredNotifier | None
    ) -> None:
        self._auth_required_notifier = notifier

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
                    self._run_scheduled_user_locked(store, identity.user_id)
            finally:
                # Terminalize through a fresh connection so an unexpected
                # browser/persistence transaction cannot strand this slot in
                # RUNNING until the next process restart.
                with SqliteStore(self._db_path) as store:
                    SqliteScheduledCheckSlotRepository(store).complete(
                        identity, datetime.now(UTC)
                    )
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
                with self._browser_factory() as browser:
                    report = self._synchronize_user(
                        store, browser, user.user_id, trigger
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
                    user = SqliteUserRepository(store).get_by_telegram_id(
                        telegram_user_id
                    )
                    if user is not None and user.is_active:
                        reservations = tuple(
                            SqliteAccountReservationRepository(store).list_for_user(
                                user.user_id
                            )
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
                    current = SqliteUserRepository(store).get_by_telegram_id(
                        telegram_user_id
                    )
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
                with self._browser_factory() as browser:
                    try:
                        report = self._synchronize_user(
                            store,
                            browser,
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

                # A check may take minutes. Re-authorize and re-resolve at
                # completion so revocation/deletion during navigation does
                # not disclose its result through the callback.
                current_user = users.get_by_telegram_id(telegram_user_id)
                current_booking = bookings.get_by_id(booking_id)
                if (
                    current_user is not None
                    and current_user.is_active
                    and current_booking is not None
                    and bookings.get_owner_user_id(booking_id)
                    == current_user.user_id
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
                if (
                    not bookings.list_all_for_user(user.user_id)
                    and not has_account_inventory
                ):
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
                except Exception:
                    logger.exception(
                        "Scheduled inventory synchronization failed for user %s",
                        user.user_id,
                    )
                    continue
                if report.completeness is InventoryCompleteness.COMPLETE:
                    bookings_by_user[user.user_id] = bookings.list_active_for_user(
                        user.user_id
                    )
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
                if (
                    self._session_repository.status(user_id).health
                    is not UserSessionHealth.READY
                ):
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
            max_checks_per_user_per_day=(
                self._config.limits_settings.max_checks_per_user_per_day
            ),
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
            if self._stop_event.is_set() or not self._is_active_user(
                store, planned_user_id
            ):
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
        source: BookingComAccountInventorySource
        if remaining_llm == 0:
            source = BookingComAccountInventorySource(
                check_time=budget.check_time,
                recovery_unavailable_detail=(
                    "Daily LLM allowance is exhausted; the deterministic inventory "
                    "result was preserved."
                )
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
            )
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
            logger.warning(
                "Could not issue Booking.com reconnect notice for user %s", user_id
            )

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
            SqliteCheckTraceRepository(store).add(
                TraceRecorder(booking.booking_id).finish(result)
            )
            return result
        snapshot = resolution.snapshot
        remaining_llm = max(
            0,
            self._config.limits_settings.max_llm_calls_per_user_per_day
            - self._llm_calls_today.count(user_id),
        )
        settings = self._config.agent_settings
        if remaining_llm:
            settings = replace(
                settings, max_llm_calls=min(settings.max_llm_calls, remaining_llm)
            )
        monitor = BookingComSearchMonitor(
            browser=browser,
            # Kept only for the legacy run_all_active API; owner-bound daemon
            # execution below never resolves or falls back to this global state.
            session_manager=SessionManager(
                _UnavailableLegacySessionRepository()
            ),
            check_history=history,
            booking_repo=SqliteBookingRepository(store),
            failure_tracker=FailureTracker(history),
            llm_factory=self._llm_factory_builder(self._config, store),
            agent_settings=settings,
            trace_repo=SqliteCheckTraceRepository(store),
            snapshot_writer=SnapshotWriter(
                self._config.data_directory.path / "snapshots"
            ),
            mobile_profile_id=self._config.mobile_web_settings.profile_id,
        )
        monitor.set_llm_enabled(remaining_llm > 0)
        result = monitor.run_authenticated(booking, snapshot)
        used = min(monitor.last_llm_calls_used, remaining_llm)
        if used:
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
            due = users_needing_capped_notice(
                [user_id], self._capped_notice_sent_today
            )
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
