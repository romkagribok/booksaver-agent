from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from booksaver.application.remote_auth import RemoteAuthenticationManager
from booksaver.application.user_sessions import UserSessionService
from booksaver.domain.models import Config
from booksaver.infrastructure.persistence.encrypted_session_store import (
    EncryptedUserSessionRepository,
)
from booksaver.infrastructure.persistence.sqlite_store import SqliteStore, SqliteUserRepository
from booksaver.infrastructure.telegram.client import TelegramBotClient
from booksaver.infrastructure.telegram.connect_command import ReconnectNotifier

from .browser_runner import SystemRemoteBrowserRunner
from .gateway import RemoteAuthGatewayRunner, RemoteAuthHttpApp
from .telegram_init_data import TelegramInitDataVerifier


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


def build_remote_auth_runtime(
    config: Config,
    db_path: Path,
    stop_event: threading.Event,
    bot_token: str,
    client: TelegramBotClient,
    browser_gate: threading.Lock,
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

    manager = RemoteAuthenticationManager(
        settings=settings,
        runner=SystemRemoteBrowserRunner(settings, config.mobile_web_settings),
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
