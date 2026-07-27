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
    access_mode: str = "owner",
    limits_settings: LimitsSettings | None = None,
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


def test_runner_publishes_default_and_owner_command_scopes(tmp_path: Path) -> None:
    owner_chat_id = 555
    stop_event = threading.Event()
    published: list[dict] = []

    class _Transport:
        def __call__(self, url: str, data: bytes, timeout: float) -> bytes:
            body = json.loads(data.decode("utf-8"))
            if url.endswith("/setMyCommands"):
                published.append(body)
                return json.dumps({"ok": True, "result": True}).encode("utf-8")
            stop_event.set()
            return json.dumps({"ok": True, "result": []}).encode("utf-8")

    cfg = _config(tmp_path, enabled=True, owner_chat_id=owner_chat_id)
    runner = build_bot_runner(
        cfg,
        tmp_path / "booksaver.db",
        Scheduler(),
        client=TelegramBotClient("fake-token", transport=_Transport()),
    )
    assert runner is not None

    runner(stop_event)

    assert [entry["scope"] for entry in published] == [
        {"type": "default"},
        {"type": "all_private_chats"},
        {"type": "chat", "chat_id": owner_chat_id},
    ]
    default_names = {entry["command"] for entry in published[0]["commands"]}
    private_names = {entry["command"] for entry in published[1]["commands"]}
    owner_names = {entry["command"] for entry in published[2]["commands"]}
    assert "admin" not in default_names
    assert private_names == default_names
    assert owner_names == default_names | {"admin"}
    assert {"register", "editbooking", "deletebooking", "rebook"}.isdisjoint(
        default_names
    )


def test_command_publication_failure_does_not_prevent_bot_loop(tmp_path: Path) -> None:
    stop_event = threading.Event()
    get_updates_calls = 0

    class _Transport:
        def __call__(self, url: str, data: bytes, timeout: float) -> bytes:
            nonlocal get_updates_calls
            if url.endswith("/setMyCommands"):
                return json.dumps({"ok": False, "description": "temporary"}).encode()
            get_updates_calls += 1
            stop_event.set()
            return json.dumps({"ok": True, "result": []}).encode()

    cfg = _config(tmp_path, enabled=True, owner_chat_id=555)
    runner = build_bot_runner(
        cfg,
        tmp_path / "booksaver.db",
        Scheduler(),
        client=TelegramBotClient("fake-token", transport=_Transport()),
    )
    assert runner is not None

    runner(stop_event)

    assert get_updates_calls == 1


def test_unknown_callback_is_acknowledged_as_expired(tmp_path: Path) -> None:
    owner_chat_id = 555
    stop_event = threading.Event()
    batches = [
        {
            "ok": True,
            "result": [
                {
                    "update_id": 1,
                    "callback_query": {
                        "id": "cb-stale",
                        "from": {"id": owner_chat_id},
                        "message": {
                            "chat": {"id": owner_chat_id, "type": "private"},
                            "message_id": 3,
                        },
                        "data": "stale:anything",
                    },
                }
            ],
        },
        {"ok": True, "result": []},
    ]
    answers: list[dict] = []

    class _Transport:
        def __call__(self, url: str, data: bytes, timeout: float) -> bytes:
            body = json.loads(data.decode())
            if url.endswith("/setMyCommands"):
                return json.dumps({"ok": True, "result": True}).encode()
            if url.endswith("/answerCallbackQuery"):
                answers.append(body)
                return json.dumps({"ok": True, "result": True}).encode()
            reply = batches.pop(0)
            if not batches:
                stop_event.set()
            return json.dumps(reply).encode()

    cfg = _config(tmp_path, enabled=True, owner_chat_id=owner_chat_id)
    runner = build_bot_runner(
        cfg,
        tmp_path / "booksaver.db",
        Scheduler(),
        client=TelegramBotClient("fake-token", transport=_Transport()),
    )
    assert runner is not None

    runner(stop_event)

    assert answers == [
        {"callback_query_id": "cb-stale", "text": "This action has expired."}
    ]


def test_unauthorized_callback_is_acknowledged_without_dispatch(tmp_path: Path) -> None:
    owner_chat_id = 555
    stranger = 777
    stop_event = threading.Event()
    updates_sent = False
    answers: list[dict] = []

    class _Transport:
        def __call__(self, url: str, data: bytes, timeout: float) -> bytes:
            nonlocal updates_sent
            body = json.loads(data.decode())
            if url.endswith("/setMyCommands"):
                return json.dumps({"ok": True, "result": True}).encode()
            if url.endswith("/answerCallbackQuery"):
                answers.append(body)
                return json.dumps({"ok": True, "result": True}).encode()
            if not updates_sent:
                updates_sent = True
                return json.dumps(
                    {
                        "ok": True,
                        "result": [
                            {
                                "update_id": 1,
                                "callback_query": {
                                    "id": "cb-forged",
                                    "from": {"id": stranger},
                                    "message": {
                                        "chat": {"id": stranger, "type": "private"},
                                        "message_id": 2,
                                    },
                                    "data": "admin:users",
                                },
                            }
                        ],
                    }
                ).encode()
            stop_event.set()
            return json.dumps({"ok": True, "result": []}).encode()

    cfg = _config(tmp_path, enabled=True, owner_chat_id=owner_chat_id)
    runner = build_bot_runner(
        cfg,
        tmp_path / "booksaver.db",
        Scheduler(),
        client=TelegramBotClient("fake-token", transport=_Transport()),
    )
    assert runner is not None

    runner(stop_event)

    assert answers == [
        {"callback_query_id": "cb-forged", "text": "This action is not available."}
    ]


def test_group_callback_is_generically_acknowledged_before_mutation(tmp_path: Path) -> None:
    from booksaver.infrastructure.persistence.sqlite_store import SqliteBookingRepository
    from tests.unit.monitor.fakes import make_booking

    owner_chat_id = 555
    telegram_user_id = 777
    booking_id = "group-private-boundary"
    db_path = tmp_path / "booksaver.db"
    with SqliteStore(db_path) as store:
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(telegram_user_id)
        SqliteBookingRepository(store).add(make_booking(booking_id), user_id=user.user_id)

    stop_event = threading.Event()
    updates_sent = False
    answers: list[dict] = []
    edits: list[dict] = []

    class _Transport:
        def __call__(self, url: str, data: bytes, timeout: float) -> bytes:
            nonlocal updates_sent
            body = json.loads(data.decode())
            if url.endswith("/setMyCommands"):
                return json.dumps({"ok": True, "result": True}).encode()
            if url.endswith("/answerCallbackQuery"):
                answers.append(body)
                return json.dumps({"ok": True, "result": True}).encode()
            if url.endswith("/editMessageText"):
                edits.append(body)
                return json.dumps({"ok": True, "result": True}).encode()
            if not updates_sent:
                updates_sent = True
                return json.dumps(
                    {
                        "ok": True,
                        "result": [
                            {
                                "update_id": 1,
                                "callback_query": {
                                    "id": "cb-group-delete",
                                    "from": {"id": telegram_user_id},
                                    "message": {
                                        "chat": {"id": -100, "type": "supergroup"},
                                        "message_id": 2,
                                    },
                                    "data": f"bdel:{booking_id}:confirm",
                                },
                            }
                        ],
                    }
                ).encode()
            stop_event.set()
            return json.dumps({"ok": True, "result": []}).encode()

    cfg = _config(tmp_path, enabled=True, owner_chat_id=owner_chat_id)
    runner = build_bot_runner(
        cfg,
        db_path,
        Scheduler(),
        client=TelegramBotClient("fake-token", transport=_Transport()),
    )
    assert runner is not None

    runner(stop_event)

    assert answers == [
        {
            "callback_query_id": "cb-group-delete",
            "text": "Open a private chat with BookSaver to use this action.",
        }
    ]
    assert edits == []
    with SqliteStore(db_path) as store:
        assert SqliteBookingRepository(store).get_by_id(booking_id) is not None


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
                        "chat": {"id": owner_chat_id, "type": "private"},
                        "from": {"id": owner_chat_id},
                        "text": "/status",
                    },
                },
                {
                    "update_id": 2,
                    "message": {
                        "chat": {"id": stranger_chat_id, "type": "private"},
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
            if url.endswith("/setMyCommands"):
                return json.dumps({"ok": True, "result": True}).encode("utf-8")
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
            if url.endswith("/setMyCommands"):
                return json.dumps({"ok": True, "result": True}).encode("utf-8")
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
                                    "chat": {"id": owner_chat_id, "type": "private"},
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
    tmp_path: Path,
    cfg: Config,
    chat_id: int,
    user_id: int,
    text: str,
    *,
    chat_type: str = "private",
    username: str | None = None,
    remote_auth_manager=None,
) -> list[tuple[int, str]]:
    """Wires build_bot_runner with a scripted transport that delivers one
    message then stops the loop, returning every sendMessage call."""
    stop_event = threading.Event()
    sent: list[tuple[int, str]] = []
    calls = {"n": 0}

    class _Transport:
        def __call__(self, url: str, data: bytes, timeout: float) -> bytes:
            body = json.loads(data.decode("utf-8"))
            if url.endswith("/setMyCommands"):
                return json.dumps({"ok": True, "result": True}).encode("utf-8")
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
                                    "chat": {"id": chat_id, "type": chat_type},
                                    "from": {
                                        "id": user_id,
                                        **({"username": username} if username else {}),
                                    },
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
    runner = build_bot_runner(
        cfg,
        tmp_path / "booksaver.db",
        Scheduler(),
        client=client,
        remote_auth_manager=remote_auth_manager,
    )
    assert runner is not None
    runner(stop_event)
    return sent


def test_group_invite_is_rejected_before_redemption(tmp_path: Path) -> None:
    from booksaver.infrastructure.persistence.sqlite_store import (
        SqliteInviteCodeRepository,
    )

    db_path = tmp_path / "booksaver.db"
    with SqliteStore(db_path) as store:
        owner = SqliteUserRepository(store).get_owner()
        invite = SqliteInviteCodeRepository(store).issue(issued_by=owner.user_id)

    cfg = _config(tmp_path, enabled=True, owner_chat_id=555)
    sent = _run_single_message(
        tmp_path,
        cfg,
        chat_id=-100,
        user_id=888,
        text=f"/start {invite.code}",
        chat_type="group",
        username="GroupUser",
    )

    assert sent == [(-100, "BookSaver only works in a private chat with the bot.")]
    with SqliteStore(db_path) as store:
        assert SqliteUserRepository(store).get_by_telegram_id(888) is None
        stored_invite = SqliteInviteCodeRepository(store).get(invite.code)
        assert stored_invite is not None
        assert stored_invite.is_used is False


def test_group_command_does_not_refresh_active_users_identity_or_start_flow(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "booksaver.db"
    with SqliteStore(db_path) as store:
        users = SqliteUserRepository(store)
        user = users.get_or_create_by_telegram_id(888)
        users.set_telegram_username(user.user_id, "Before")

    cfg = _config(tmp_path, enabled=True, owner_chat_id=555)
    sent = _run_single_message(
        tmp_path,
        cfg,
        chat_id=-100,
        user_id=888,
        text="/register",
        chat_type="supergroup",
        username="After",
    )

    assert sent == [(-100, "BookSaver only works in a private chat with the bot.")]
    with SqliteStore(db_path) as store:
        unchanged = SqliteUserRepository(store).get_by_telegram_id(888)
        assert unchanged is not None
        assert unchanged.telegram_username == "Before"


def test_admin_users_command_works_for_owner(tmp_path: Path) -> None:
    owner_chat_id = 555
    cfg = _config(tmp_path, enabled=True, owner_chat_id=owner_chat_id)
    sent = _run_single_message(
        tmp_path, cfg, chat_id=owner_chat_id, user_id=owner_chat_id, text="/admin users"
    )
    assert any("Users:" in text for _cid, text in sent)


def test_admin_purge_wiring_cancels_remote_auth_and_deletes_session(
    tmp_path: Path,
) -> None:
    owner_chat_id = 555
    target_telegram_user_id = 777
    db_path = tmp_path / "booksaver.db"
    cfg = _config(tmp_path, enabled=True, owner_chat_id=owner_chat_id)
    with SqliteStore(db_path) as store:
        target = SqliteUserRepository(store).get_or_create_by_telegram_id(
            target_telegram_user_id
        )
    session_directory = cfg.data_directory.path / "booking_sessions"
    session_directory.mkdir()
    session_path = (
        session_directory / f"user-{target.user_id}-booking-com.session"
    )
    session_path.write_text("encrypted-session-sentinel")

    class _RemoteAuthManager:
        def __init__(self) -> None:
            self.cancelled: list[int] = []

        def cancel_for_telegram_user(self, telegram_user_id: int) -> bool:
            self.cancelled.append(telegram_user_id)
            return True

    manager = _RemoteAuthManager()
    sent = _run_single_message(
        tmp_path,
        cfg,
        chat_id=owner_chat_id,
        user_id=owner_chat_id,
        text=f"/admin purge {target.user_id} confirm",
        remote_auth_manager=manager,
    )

    assert manager.cancelled == [target_telegram_user_id]
    assert not session_path.exists()
    assert (
        session_directory / f"user-{target.user_id}-booking-com.revoked"
    ).exists()
    with SqliteStore(db_path) as store:
        assert SqliteUserRepository(store).get_by_id(target.user_id) is None
    assert any("all their data were purged" in text for _chat_id, text in sent)


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
            if url.endswith("/setMyCommands"):
                return json.dumps({"ok": True, "result": True}).encode("utf-8")
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
                                    "chat": {"id": chat_id, "type": "private"},
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


def test_retired_register_command_is_unknown_immediately(tmp_path: Path) -> None:
    owner_chat_id = 555
    db_path = tmp_path / "booksaver.db"
    cfg = _config(tmp_path, enabled=True, owner_chat_id=owner_chat_id)
    # Link the chat to a local user the way bolt 009's admission will.
    with SqliteStore(db_path) as store:
        SqliteUserRepository(store).get_or_create_by_telegram_id(owner_chat_id)

    stop_event = threading.Event()
    sent: list[tuple[int, str]] = []
    texts = ["/register"]
    client = TelegramBotClient(
        "fake-token",
        transport=_scripted_conversation_transport(owner_chat_id, texts, sent, stop_event),
    )
    runner = build_bot_runner(cfg, db_path, Scheduler(), client=client)
    assert runner is not None

    runner(stop_event)

    assert sent == [
        (owner_chat_id, "Unknown command: /register. Send /help for the list.")
    ]


def test_cancelflow_has_no_booking_dialog_semantics(tmp_path: Path) -> None:
    owner_chat_id = 555
    db_path = tmp_path / "booksaver.db"
    cfg = _config(tmp_path, enabled=True, owner_chat_id=owner_chat_id)
    with SqliteStore(db_path) as store:
        SqliteUserRepository(store).get_or_create_by_telegram_id(owner_chat_id)

    stop_event = threading.Event()
    sent: list[tuple[int, str]] = []
    texts = ["/cancelflow"]
    client = TelegramBotClient(
        "fake-token",
        transport=_scripted_conversation_transport(owner_chat_id, texts, sent, stop_event),
    )
    runner = build_bot_runner(cfg, db_path, Scheduler(), client=client)
    assert runner is not None

    runner(stop_event)

    assert sent[-1] == (owner_chat_id, "No active dialog to cancel.")


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
