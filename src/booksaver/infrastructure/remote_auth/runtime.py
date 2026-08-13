from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from booksaver.application.browser_resilience import DOM_STEP_REGISTRY
from booksaver.application.dom_incident import DomIncidentRecorder, DomIncidentRepository
from booksaver.application.remote_auth import RemoteAuthenticationManager, RemoteBrowserWork
from booksaver.application.user_sessions import UserSessionService
from booksaver.domain.browser_resilience import DomStepId, PageStateResolution
from booksaver.domain.dom_incident import IncidentDraft
from booksaver.domain.model_policy import BrowserJobKind, ModelStopReason
from booksaver.domain.models import Config
from booksaver.infrastructure.persistence.dom_incident import SqliteDomIncidentRepository
from booksaver.infrastructure.persistence.encrypted_diagnostics import (
    EncryptedDiagnosticStore,
)
from booksaver.infrastructure.persistence.encrypted_session_store import (
    EncryptedUserSessionRepository,
)
from booksaver.infrastructure.persistence.sqlite_store import SqliteStore, SqliteUserRepository
from booksaver.infrastructure.telegram.client import TelegramBotClient
from booksaver.infrastructure.telegram.connect_command import ReconnectNotifier

from .browser_runner import RemoteAuthPageStateCapability, SystemRemoteBrowserRunner
from .gateway import RemoteAuthGatewayRunner, RemoteAuthHttpApp
from .telegram_init_data import TelegramInitDataVerifier


class AdaptiveBrowserJobContext(Protocol):
    local_user_id: int
    runtime: Any
    budget: Any


class AdaptiveBrowserJobAdmission(Protocol):
    context: AdaptiveBrowserJobContext | None
    stop_reason: ModelStopReason | None


AdaptiveRuntimeScope = Callable[
    [int, BrowserJobKind], AbstractContextManager[AdaptiveBrowserJobAdmission]
]


@dataclass(frozen=True)
class RemoteAuthRuntime:
    manager: RemoteAuthenticationManager
    reconnect_notifier: ReconnectNotifier
    gateway: RemoteAuthGatewayRunner

    def run(self, stop_event: threading.Event) -> None:
        try:
            self.gateway.run(stop_event)
        finally:
            self.manager.stop_all()


class _StoppedPageStateResolver:
    """Return one exact no-call stop when caller-scoped LLM work is unavailable."""

    def __init__(self, stop_reason: ModelStopReason) -> None:
        self._stop_reason = stop_reason

    def resolve(self, step_id: DomStepId, _observation: Any) -> PageStateResolution:
        definition = DOM_STEP_REGISTRY.definition(step_id)
        return PageStateResolution(
            classification=None,
            terminal_reason=definition.reason_for_model_stop(self._stop_reason),
            model_stop_reason=self._stop_reason,
        )


def build_remote_auth_runtime(
    config: Config,
    db_path: Path,
    stop_event: threading.Event,
    bot_token: str,
    client: TelegramBotClient,
    browser_gate: threading.Lock,
    on_connected: Callable[[int], None] | None = None,
    adaptive_runtime_scope: AdaptiveRuntimeScope | None = None,
) -> RemoteAuthRuntime:
    settings = config.remote_auth_settings
    reconnect = ReconnectNotifier(
        db_path=db_path,
        client=client,
        bot_settings=config.telegram_bot_settings,
    )

    def _capture(telegram_user_id: int, cookies_json: str) -> object:
        with SqliteStore(db_path) as store:
            service = UserSessionService(
                SqliteUserRepository(store),
                EncryptedUserSessionRepository(config.data_directory),
            )
            return service.import_cookies(telegram_user_id, cookies_json)

    def _notify(chat_id: int, message: str) -> None:
        client.send_message(chat_id, message)

    def _connected(telegram_user_id: int) -> None:
        with SqliteStore(db_path) as store:
            user = SqliteUserRepository(store).get_by_telegram_id(telegram_user_id)
        if user is not None:
            reconnect.clear(user.user_id)
            if on_connected is not None:
                on_connected(telegram_user_id)

    def _page_state_capability(
        work: RemoteBrowserWork,
    ) -> AbstractContextManager[RemoteAuthPageStateCapability]:
        from contextlib import contextmanager

        @contextmanager
        def _scope() -> Iterator[RemoteAuthPageStateCapability]:
            if adaptive_runtime_scope is None:
                yield RemoteAuthPageStateCapability()
                return
            with adaptive_runtime_scope(
                work.telegram_user_id,
                BrowserJobKind.REMOTE_AUTH,
            ) as admission:
                if admission.stop_reason is not None:
                    yield RemoteAuthPageStateCapability(
                        resolver=_StoppedPageStateResolver(admission.stop_reason)
                    )
                    return
                adaptive = admission.context
                assert adaptive is not None
                yield RemoteAuthPageStateCapability(
                    resolver=adaptive.runtime.page_state_resolver(),
                    source_user_id=adaptive.local_user_id,
                    budget=adaptive.budget,
                )

        return _scope()

    def _record_incident(draft: IncidentDraft) -> None:
        # The runner invokes this sink only after Playwright/display cleanup.
        with SqliteStore(db_path) as store:
            DomIncidentRecorder(
                incidents=cast(
                    DomIncidentRepository,
                    SqliteDomIncidentRepository(store),
                ),
                diagnostics=EncryptedDiagnosticStore(store),
            ).record_safely(draft)

    manager = RemoteAuthenticationManager(
        settings=settings,
        runner=SystemRemoteBrowserRunner(
            settings,
            config.mobile_web_settings,
            page_state_capability_factory=_page_state_capability,
            incident_sink=_record_incident,
        ),
        daemon_stop_event=stop_event,
        capture_session=_capture,
        notify_user=_notify,
        on_success=_connected,
        browser_gate=browser_gate,
    )
    verifier = TelegramInitDataVerifier(
        bot_token,
        max_age_seconds=settings.telegram_init_max_age_seconds,
    )
    gateway = RemoteAuthGatewayRunner(
        settings,
        RemoteAuthHttpApp(settings, manager, verifier),
    )
    return RemoteAuthRuntime(manager, reconnect, gateway)
