"""Invalid personal-key notices respect current user access state."""

from datetime import UTC, datetime
from typing import Any

from booksaver.cli.commands import _notify_invalid_user_keys
from booksaver.domain.check_result import CheckResult, FailureCode, FailureReason
from booksaver.domain.user import User, UserAccessState, UserRole


class _UserRepo:
    def __init__(self, user: User) -> None:
        self.user = user

    def get_owner_of_booking(self, booking_id: str) -> User:
        return self.user


def _invalid_result() -> CheckResult:
    return CheckResult.failure(
        "booking-1",
        datetime.now(UTC),
        FailureReason(FailureCode.USER_KEY_INVALID, "invalid key"),
    )


def test_invalid_key_notice_is_suppressed_after_revocation(
    monkeypatch: Any,
) -> None:
    user = User(
        user_id=2,
        telegram_user_id=222,
        role=UserRole.USER,
        access_state=UserAccessState.REVOKED,
        created_at=datetime.now(UTC),
    )
    sends: list[tuple[int, str]] = []

    class FakeClient:
        def __init__(self, bot_token: str) -> None:
            pass

        def send_message(self, chat_id: int, text: str) -> None:
            sends.append((chat_id, text))

    monkeypatch.setenv("BOOKSAVER_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(
        "booksaver.infrastructure.telegram.client.TelegramBotClient", FakeClient
    )

    _notify_invalid_user_keys(_UserRepo(user), [_invalid_result()])

    assert sends == []
