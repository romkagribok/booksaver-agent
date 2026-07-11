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
    LimitsSettings,
    NotificationSettings,
    TelegramBotSettings,
)
from booksaver.infrastructure.persistence.sqlite_store import SqliteStore, SqliteUserRepository
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
    limits_settings: LimitsSettings | None = None,
) -> Config:
    return Config(
        check_interval=CheckInterval.parse("1h"),
        data_directory=_data_dir(tmp_path),
        notification_settings=NotificationSettings(),
        loaded_at=datetime.now(UTC),
        telegram_bot_settings=TelegramBotSettings(
            enabled=enabled, owner_chat_id=owner_chat_id if enabled else None
        ),
        limits_settings=limits_settings or LimitsSettings(),
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


def _scripted_conversation_transport(
    chat_id: int, texts: list[str], sent: list[tuple[int, str]], stop_event: threading.Event
):
    """Replays `texts` one message per getUpdates poll, then an empty batch
    that sets `stop_event`."""

    class _Transport:
        def __init__(self) -> None:
            self._sent_count = 0

        def __call__(self, url: str, data: bytes, timeout: float) -> bytes:
            body = json.loads(data.decode("utf-8"))
            if url.endswith("/sendMessage"):
                sent.append((body["chat_id"], body["text"]))
                return json.dumps({"ok": True, "result": {}}).encode("utf-8")
            if self._sent_count < len(texts):
                text = texts[self._sent_count]
                self._sent_count += 1
                return json.dumps(
                    {
                        "ok": True,
                        "result": [
                            {
                                "update_id": self._sent_count,
                                "message": {
                                    "chat": {"id": chat_id},
                                    "from": {"id": chat_id},
                                    "text": text,
                                },
                            }
                        ],
                    }
                ).encode("utf-8")
            stop_event.set()
            return json.dumps({"ok": True, "result": []}).encode("utf-8")

    return _Transport()


def test_register_dialog_end_to_end_through_the_bot_loop(tmp_path: Path) -> None:
    owner_chat_id = 555
    db_path = tmp_path / "booksaver.db"
    cfg = _config(tmp_path, enabled=True, owner_chat_id=owner_chat_id)
    # Link the chat to a local user the way bolt 009's admission will.
    with SqliteStore(db_path) as store:
        SqliteUserRepository(store).get_or_create_by_telegram_id(owner_chat_id)

    stop_event = threading.Event()
    sent: list[tuple[int, str]] = []
    texts = [
        "/register",
        "Ibis Berlin Mitte",
        "-",
        "2026-09-01",
        "2026-09-05",
        "Standard Double",
        "250.00 EUR",
        "yes",
        "-",
        "-",
        "2",
        "-",
        "-",
        "CONF123",
        "yes",
    ]
    client = TelegramBotClient(
        "fake-token",
        transport=_scripted_conversation_transport(owner_chat_id, texts, sent, stop_event),
    )
    runner = build_bot_runner(cfg, db_path, Scheduler(), client=client)
    assert runner is not None

    runner(stop_event)

    assert any("Registered:" in text for _chat_id, text in sent)
    assert any("Please confirm this booking" in text for _chat_id, text in sent)


def test_cancelflow_aborts_a_register_dialog_mid_flow(tmp_path: Path) -> None:
    owner_chat_id = 555
    db_path = tmp_path / "booksaver.db"
    cfg = _config(tmp_path, enabled=True, owner_chat_id=owner_chat_id)
    with SqliteStore(db_path) as store:
        SqliteUserRepository(store).get_or_create_by_telegram_id(owner_chat_id)

    stop_event = threading.Event()
    sent: list[tuple[int, str]] = []
    texts = ["/register", "Ibis Berlin Mitte", "/cancelflow"]
    client = TelegramBotClient(
        "fake-token",
        transport=_scripted_conversation_transport(owner_chat_id, texts, sent, stop_event),
    )
    runner = build_bot_runner(cfg, db_path, Scheduler(), client=client)
    assert runner is not None

    runner(stop_event)

    assert sent[-1] == (owner_chat_id, "Cancelled the current dialog.")


def test_message_rate_limit_drops_excess_replies_within_the_window(tmp_path: Path) -> None:
    owner_chat_id = 555
    cfg = _config(
        tmp_path,
        enabled=True,
        owner_chat_id=owner_chat_id,
        limits_settings=LimitsSettings(messages_per_minute_per_chat=1),
    )
    stop_event = threading.Event()
    sent: list[tuple[int, str]] = []
    texts = ["/status", "/status"]
    client = TelegramBotClient(
        "fake-token",
        transport=_scripted_conversation_transport(owner_chat_id, texts, sent, stop_event),
    )
    runner = build_bot_runner(cfg, tmp_path / "booksaver.db", Scheduler(), client=client)
    assert runner is not None

    runner(stop_event)

    assert len(sent) == 1  # the second /status reply was dropped, not queued
