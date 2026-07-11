from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path

from booksaver.daemon.scheduler import Scheduler
from booksaver.domain.models import Config
from booksaver.domain.value_objects import (
    CheckInterval,
    DataDirectory,
    NotificationSettings,
    TelegramBotSettings,
)
from booksaver.infrastructure.telegram.client import TelegramBotClient
from booksaver.infrastructure.telegram.gateway import build_bot_runner


def _data_dir(tmp_path: Path) -> DataDirectory:
    d = tmp_path / "booksaver"
    d.mkdir()
    return DataDirectory(path=d)


def _config(
    tmp_path: Path,
    enabled: bool,
    owner_chat_id: int | None = 555,
    access_mode: str = "owner",
) -> Config:
    return Config(
        check_interval=CheckInterval.parse("1h"),
        data_directory=_data_dir(tmp_path),
        notification_settings=NotificationSettings(),
        loaded_at=datetime.now(UTC),
        telegram_bot_settings=TelegramBotSettings(
            enabled=enabled,
            owner_chat_id=owner_chat_id if enabled else None,
            access_mode=access_mode,
        ),
    )


def test_returns_none_when_bot_disabled(tmp_path: Path) -> None:
    cfg = _config(tmp_path, enabled=False)
    runner = build_bot_runner(cfg, tmp_path / "booksaver.db", Scheduler())
    assert runner is None


def test_returns_none_when_enabled_but_token_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BOOKSAVER_TELEGRAM_BOT_TOKEN", raising=False)
    cfg = _config(tmp_path, enabled=True)
    runner = build_bot_runner(cfg, tmp_path / "booksaver.db", Scheduler())
    assert runner is None


def test_returns_a_runner_when_enabled_with_injected_client(tmp_path: Path) -> None:
    class _FakeTransport:
        def __call__(self, url: str, data: bytes, timeout: float) -> bytes:
            return json.dumps({"ok": True, "result": []}).encode("utf-8")

    cfg = _config(tmp_path, enabled=True, owner_chat_id=555)
    client = TelegramBotClient("fake-token", transport=_FakeTransport())
    runner = build_bot_runner(cfg, tmp_path / "booksaver.db", Scheduler(), client=client)
    assert runner is not None


def test_end_to_end_owner_status_command_and_stranger_refusal(tmp_path: Path) -> None:
    owner_chat_id = 555
    stranger_chat_id = 777
    responses: list[dict] = [
        {
            "ok": True,
            "result": [
                {
                    "update_id": 1,
                    "message": {
                        "chat": {"id": owner_chat_id},
                        "from": {"id": owner_chat_id},
                        "text": "/status",
                    },
                },
                {
                    "update_id": 2,
                    "message": {
                        "chat": {"id": stranger_chat_id},
                        "from": {"id": stranger_chat_id},
                        "text": "/status",
                    },
                },
            ],
        },
        {"ok": True, "result": []},
    ]
    sent: list[tuple[int, str]] = []
    stop_event = threading.Event()

    class _ScriptedTransport:
        def __init__(self) -> None:
            self._calls = 0

        def __call__(self, url: str, data: bytes, timeout: float) -> bytes:
            body = json.loads(data.decode("utf-8"))
            if url.endswith("/sendMessage"):
                sent.append((body["chat_id"], body["text"]))
                return json.dumps({"ok": True, "result": {}}).encode("utf-8")
            # getUpdates
            reply = responses[min(self._calls, len(responses) - 1)]
            self._calls += 1
            if self._calls >= len(responses):
                stop_event.set()
            return json.dumps(reply).encode("utf-8")

    cfg = _config(tmp_path, enabled=True, owner_chat_id=owner_chat_id)
    client = TelegramBotClient("fake-token", transport=_ScriptedTransport())
    runner = build_bot_runner(cfg, tmp_path / "booksaver.db", Scheduler(), client=client)
    assert runner is not None

    runner(stop_event)

    owner_replies = [text for chat_id, text in sent if chat_id == owner_chat_id]
    stranger_replies = [text for chat_id, text in sent if chat_id == stranger_chat_id]
    assert any("BookSaver status" in t for t in owner_replies)
    assert len(stranger_replies) == 1
    assert "private" in stranger_replies[0]


def test_cancelflow_reports_no_active_dialog(tmp_path: Path) -> None:
    owner_chat_id = 555
    stop_event = threading.Event()
    sent: list[tuple[int, str]] = []
    calls = {"n": 0}

    class _Transport:
        def __call__(self, url: str, data: bytes, timeout: float) -> bytes:
            body = json.loads(data.decode("utf-8"))
            if url.endswith("/sendMessage"):
                sent.append((body["chat_id"], body["text"]))
                return json.dumps({"ok": True, "result": {}}).encode("utf-8")
            if calls["n"] == 0:
                calls["n"] += 1
                return json.dumps(
                    {
                        "ok": True,
                        "result": [
                            {
                                "update_id": 1,
                                "message": {
                                    "chat": {"id": owner_chat_id},
                                    "from": {"id": owner_chat_id},
                                    "text": "/cancelflow",
                                },
                            }
                        ],
                    }
                ).encode("utf-8")
            stop_event.set()
            return json.dumps({"ok": True, "result": []}).encode("utf-8")

    cfg = _config(tmp_path, enabled=True, owner_chat_id=owner_chat_id)
    client = TelegramBotClient("fake-token", transport=_Transport())
    runner = build_bot_runner(cfg, tmp_path / "booksaver.db", Scheduler(), client=client)
    assert runner is not None

    runner(stop_event)

    assert sent == [(owner_chat_id, "No active dialog to cancel.")]


def _run_single_message(
    tmp_path: Path, cfg: Config, chat_id: int, user_id: int, text: str
) -> list[tuple[int, str]]:
    """Wires build_bot_runner with a scripted transport that delivers one
    message then stops the loop, returning every sendMessage call."""
    stop_event = threading.Event()
    sent: list[tuple[int, str]] = []
    calls = {"n": 0}

    class _Transport:
        def __call__(self, url: str, data: bytes, timeout: float) -> bytes:
            body = json.loads(data.decode("utf-8"))
            if url.endswith("/sendMessage"):
                sent.append((body["chat_id"], body["text"]))
                return json.dumps({"ok": True, "result": {}}).encode("utf-8")
            if url.endswith("/deleteMessage"):
                return json.dumps({"ok": True, "result": {}}).encode("utf-8")
            if calls["n"] == 0:
                calls["n"] += 1
                return json.dumps(
                    {
                        "ok": True,
                        "result": [
                            {
                                "update_id": 1,
                                "message": {
                                    "chat": {"id": chat_id},
                                    "from": {"id": user_id},
                                    "text": text,
                                    "message_id": 99,
                                },
                            }
                        ],
                    }
                ).encode("utf-8")
            stop_event.set()
            return json.dumps({"ok": True, "result": []}).encode("utf-8")

    client = TelegramBotClient("fake-token", transport=_Transport())
    runner = build_bot_runner(cfg, tmp_path / "booksaver.db", Scheduler(), client=client)
    assert runner is not None
    runner(stop_event)
    return sent


def test_admin_users_command_works_for_owner(tmp_path: Path) -> None:
    owner_chat_id = 555
    cfg = _config(tmp_path, enabled=True, owner_chat_id=owner_chat_id)
    sent = _run_single_message(
        tmp_path, cfg, chat_id=owner_chat_id, user_id=owner_chat_id, text="/admin users"
    )
    assert any("Users:" in text for _cid, text in sent)


def test_admin_command_refused_for_non_owner(tmp_path: Path) -> None:
    owner_chat_id = 555
    stranger_chat_id = 777
    cfg = _config(tmp_path, enabled=True, owner_chat_id=owner_chat_id)
    sent = _run_single_message(
        tmp_path, cfg, chat_id=stranger_chat_id, user_id=stranger_chat_id, text="/admin users"
    )
    # Refused at the access-control layer (owner mode) before /admin's own
    # owner check even runs — same private-bot refusal as any other command.
    assert len(sent) == 1
    assert "private" in sent[0][1]


def test_invite_mode_admits_a_stranger_with_a_valid_code(tmp_path: Path) -> None:
    from booksaver.infrastructure.persistence.sqlite_store import (
        SqliteInviteCodeRepository,
        SqliteStore,
        SqliteUserRepository,
    )

    owner_chat_id = 555
    stranger_chat_id = 888
    db_path = tmp_path / "booksaver.db"
    with SqliteStore(db_path) as store:
        owner = SqliteUserRepository(store).get_owner()
        invite = SqliteInviteCodeRepository(store).issue(issued_by=owner.user_id)

    cfg = _config(tmp_path, enabled=True, owner_chat_id=owner_chat_id, access_mode="invite")
    sent = _run_single_message(
        tmp_path,
        cfg,
        chat_id=stranger_chat_id,
        user_id=stranger_chat_id,
        text=f"/start {invite.code}",
    )

    assert any("Welcome to BookSaver" in text for _cid, text in sent)
    with SqliteStore(db_path) as store:
        admitted = SqliteUserRepository(store).get_by_telegram_id(stranger_chat_id)
    assert admitted is not None
    assert admitted.access_state.value == "active"
