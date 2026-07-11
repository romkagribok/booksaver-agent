from __future__ import annotations

import threading
from pathlib import Path

from booksaver.domain.value_objects import DataDirectory
from booksaver.infrastructure.telegram.bot_loop import BotLoop
from booksaver.infrastructure.telegram.client import TelegramApiError
from booksaver.infrastructure.telegram.offset_store import TelegramOffsetStore
from booksaver.infrastructure.telegram.router import CommandRouter, IncomingCommand


def _message_update(update_id: int, chat_id: int, user_id: int, text: str) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "chat": {"id": chat_id},
            "from": {"id": user_id},
            "text": text,
        },
    }


class FakeClient:
    """Stands in for TelegramBotClient: no network, deterministic batches.

    Stops the loop's stop_event once the scripted batches are exhausted so tests
    don't need real threading to terminate `BotLoop.run`.
    """

    def __init__(self, batches: list[list[dict]], stop_event: threading.Event) -> None:
        self._batches = list(batches)
        self._stop_event = stop_event
        self.get_updates_calls: list[int | None] = []
        self.sent: list[tuple[int, str]] = []
        self.raise_once: Exception | None = None

    def get_updates(self, offset: int | None, timeout: int) -> list[dict]:
        self.get_updates_calls.append(offset)
        if self.raise_once is not None:
            exc, self.raise_once = self.raise_once, None
            # Also stop the loop so the post-exception retry wait resolves instantly
            # instead of sleeping out the real _RETRY_WAIT_SECONDS in the test.
            self._stop_event.set()
            raise exc
        if self._batches:
            return self._batches.pop(0)
        self._stop_event.set()
        return []

    def send_message(self, chat_id: int, text: str) -> dict:
        self.sent.append((chat_id, text))
        return {}


def _data_dir(tmp_path: Path) -> DataDirectory:
    d = tmp_path / "booksaver"
    d.mkdir()
    return DataDirectory(path=d)


def _make_loop(
    client: FakeClient,
    tmp_path: Path,
    access_guard=lambda chat_id: True,
    dialog_handler=None,
) -> tuple[BotLoop, CommandRouter, list[int]]:
    router = CommandRouter()
    refused: list[int] = []
    offset_store = TelegramOffsetStore(_data_dir(tmp_path))
    loop = BotLoop(
        client=client,  # type: ignore[arg-type]
        router=router,
        offset_store=offset_store,
        poll_timeout_seconds=30,
        access_guard=access_guard,
        on_refused=refused.append,
        dialog_handler=dialog_handler,
    )
    return loop, router, refused


def test_dispatches_known_command_to_registered_handler(tmp_path: Path) -> None:
    stop_event = threading.Event()
    client = FakeClient([[_message_update(1, chat_id=10, user_id=10, text="/status")]], stop_event)
    loop, router, _ = _make_loop(client, tmp_path)
    seen: list[IncomingCommand] = []
    router.register("/status", seen.append)

    loop.run(stop_event)

    assert len(seen) == 1
    assert seen[0].command == "/status"
    assert seen[0].chat_id == 10


def test_unknown_command_gets_a_polite_reply(tmp_path: Path) -> None:
    stop_event = threading.Event()
    client = FakeClient([[_message_update(1, chat_id=10, user_id=10, text="/nope")]], stop_event)
    loop, _router, _ = _make_loop(client, tmp_path)

    loop.run(stop_event)

    assert client.sent == [(10, "Unknown command: /nope. Send /help for the list.")]


def test_non_owner_chat_is_refused_and_router_not_invoked(tmp_path: Path) -> None:
    stop_event = threading.Event()
    update = _message_update(1, chat_id=999, user_id=999, text="/status")
    client = FakeClient([[update]], stop_event)
    loop, router, refused = _make_loop(
        client, tmp_path, access_guard=lambda chat_id: chat_id == 10
    )
    seen: list[IncomingCommand] = []
    router.register("/status", seen.append)

    loop.run(stop_event)

    assert seen == []
    assert refused == [999]


def test_offset_advances_past_last_processed_update_and_persists(tmp_path: Path) -> None:
    stop_event = threading.Event()
    client = FakeClient(
        [[_message_update(5, chat_id=10, user_id=10, text="/help"),
          _message_update(6, chat_id=10, user_id=10, text="/help")]],
        stop_event,
    )
    offset_store = TelegramOffsetStore(_data_dir(tmp_path))
    router = CommandRouter()
    router.register("/help", lambda cmd: None)
    loop = BotLoop(
        client=client,  # type: ignore[arg-type]
        router=router,
        offset_store=offset_store,
        poll_timeout_seconds=30,
        access_guard=lambda chat_id: True,
        on_refused=lambda chat_id: None,
    )

    loop.run(stop_event)

    assert offset_store.load() == 7  # last update_id (6) + 1


def test_restart_resumes_from_persisted_offset(tmp_path: Path) -> None:
    data_dir = _data_dir(tmp_path)
    TelegramOffsetStore(data_dir).save(100)

    stop_event = threading.Event()
    client = FakeClient([], stop_event)
    router = CommandRouter()
    loop = BotLoop(
        client=client,  # type: ignore[arg-type]
        router=router,
        offset_store=TelegramOffsetStore(data_dir),
        poll_timeout_seconds=30,
        access_guard=lambda chat_id: True,
        on_refused=lambda chat_id: None,
    )

    loop.run(stop_event)

    assert client.get_updates_calls[0] == 100


def test_dialog_handler_consumes_non_command_text(tmp_path: Path) -> None:
    stop_event = threading.Event()
    client = FakeClient([[_message_update(1, chat_id=10, user_id=10, text="Alice")]], stop_event)
    captured: list[IncomingCommand] = []

    def _dialog_handler(cmd: IncomingCommand) -> bool:
        captured.append(cmd)
        return True

    loop, _router, _ = _make_loop(client, tmp_path, dialog_handler=_dialog_handler)

    loop.run(stop_event)

    assert len(captured) == 1
    assert captured[0].raw_text == "Alice"
    assert client.sent == []  # dialog handler owns the reply, bot_loop sends nothing extra


def test_get_updates_api_error_does_not_crash_loop(tmp_path: Path) -> None:
    stop_event = threading.Event()
    client = FakeClient([], stop_event)
    client.raise_once = TelegramApiError("boom")
    loop, _router, _ = _make_loop(client, tmp_path)

    # First call raises (retries with a short wait), second call exhausts batches and stops.
    loop.run(stop_event)

    assert len(client.get_updates_calls) >= 1


def test_handler_exception_does_not_crash_loop(tmp_path: Path) -> None:
    stop_event = threading.Event()
    client = FakeClient(
        [[_message_update(1, chat_id=10, user_id=10, text="/boom"),
          _message_update(2, chat_id=10, user_id=10, text="/help")]],
        stop_event,
    )
    loop, router, _ = _make_loop(client, tmp_path)
    seen: list[str] = []
    router.register("/boom", lambda cmd: (_ for _ in ()).throw(RuntimeError("bad handler")))
    router.register("/help", lambda cmd: seen.append("help"))

    loop.run(stop_event)  # must not raise

    assert seen == ["help"]
