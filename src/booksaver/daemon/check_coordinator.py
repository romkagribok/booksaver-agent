from __future__ import annotations

import logging
import os
import threading
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from booksaver.application.account_sync import SynchronizeBookingAccount
from booksaver.application.savings_pipeline import NotificationDispatcher, SavingsPipeline
from booksaver.application.user_sessions import (
    AuthenticatedSessionProvider,
    UserSessionRepository,
)
from booksaver.domain.account_sync import (
    AccountReservation,
    InventoryCompleteness,
    InventoryDiscoveryResult,
    SynchronizationFailureCode,
    SynchronizationReport,
    SynchronizationTrigger,
)
from booksaver.domain.check_result import CheckResult, FailureCode, FailureReason
from booksaver.domain.models import Booking, Config
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
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteAccountReservationRepository,
    SqliteBookingRepository,
    SqliteCheckHistoryRepository,
    SqliteCheckTraceRepository,
    SqliteSavingsRepository,
    SqliteStore,
    SqliteUserRepository,
)
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
        """Run one fair scheduled batch, or skip when another check owns the browser."""
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
        report = SynchronizeBookingAccount(
            BookingComAccountInventorySource(), repository
        ).execute(
            browser=browser,
            user_id=user_id,
            trigger=trigger,
            session_revision=snapshot.metadata.revision_id,
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
