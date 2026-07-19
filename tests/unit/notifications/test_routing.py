from __future__ import annotations

from datetime import UTC, datetime

from booksaver.domain.user import User, UserAccessState, UserRole
from booksaver.domain.value_objects import TelegramBotSettings
from booksaver.infrastructure.notifications.routing import OwnerBookingNotifierResolver

from ..monitor.fakes import FakeBookingRepository, make_booking
from ..savings.test_pipeline import FakeNotifier


class FakeUserRepo:
    def __init__(self, users: list[User]) -> None:
        self._users = {u.user_id: u for u in users}

    def get_by_id(self, user_id: int) -> User | None:
        return self._users.get(user_id)


def _owner_user(user_id: int = 1, telegram_user_id: int | None = None) -> User:
    return User(
        user_id=user_id,
        telegram_user_id=telegram_user_id,
        role=UserRole.OWNER,
        access_state=UserAccessState.ACTIVE,
        created_at=datetime.now(UTC),
    )


def _invited_user(
    user_id: int = 2,
    telegram_user_id: int | None = 4242,
    access_state: UserAccessState = UserAccessState.ACTIVE,
) -> User:
    return User(
        user_id=user_id,
        telegram_user_id=telegram_user_id,
        role=UserRole.USER,
        access_state=access_state,
        created_at=datetime.now(UTC),
    )


def test_owner_owned_booking_uses_the_static_owner_notifiers() -> None:
    booking = make_booking("b-owner")
    booking_repo = FakeBookingRepository([booking])
    booking_repo.owners[booking.booking_id] = 1
    owner_notifier = FakeNotifier("email")

    resolver = OwnerBookingNotifierResolver(
        booking_repo=booking_repo,
        user_repo=FakeUserRepo([_owner_user()]),
        owner_notifiers=[owner_notifier],
        telegram_bot_settings=TelegramBotSettings(),
        telegram_bot_token=None,
    )

    notifiers = resolver(booking)
    assert notifiers == [owner_notifier]


def test_revoked_owner_booking_gets_no_notifiers() -> None:
    booking = make_booking("b-revoked-owner")
    booking_repo = FakeBookingRepository([booking])
    booking_repo.owners[booking.booking_id] = 1
    owner = _owner_user()
    owner.access_state = UserAccessState.REVOKED

    resolver = OwnerBookingNotifierResolver(
        booking_repo=booking_repo,
        user_repo=FakeUserRepo([owner]),
        owner_notifiers=[FakeNotifier("email")],
        telegram_bot_settings=TelegramBotSettings(),
        telegram_bot_token=None,
    )

    assert resolver(booking) == []


def test_invited_user_booking_routes_to_their_own_telegram_chat() -> None:
    booking = make_booking("b-invited")
    booking_repo = FakeBookingRepository([booking])
    booking_repo.owners[booking.booking_id] = 2

    resolver = OwnerBookingNotifierResolver(
        booking_repo=booking_repo,
        user_repo=FakeUserRepo([_invited_user(telegram_user_id=4242)]),
        owner_notifiers=[FakeNotifier("email")],
        telegram_bot_settings=TelegramBotSettings(),
        telegram_bot_token="fake-token",
    )

    notifiers = resolver(booking)
    assert len(notifiers) == 1
    assert notifiers[0].channel_name == "telegram"


def test_invited_user_with_no_chat_id_or_token_gets_no_notifiers_not_a_crash() -> None:
    booking = make_booking("b-invited")
    booking_repo = FakeBookingRepository([booking])
    booking_repo.owners[booking.booking_id] = 2

    resolver = OwnerBookingNotifierResolver(
        booking_repo=booking_repo,
        user_repo=FakeUserRepo([_invited_user(telegram_user_id=None)]),
        owner_notifiers=[FakeNotifier("email")],
        telegram_bot_settings=TelegramBotSettings(),
        telegram_bot_token="fake-token",
    )

    assert resolver(booking) == []


def test_revoked_owning_user_gets_no_notifiers() -> None:
    booking = make_booking("b-revoked")
    booking_repo = FakeBookingRepository([booking])
    booking_repo.owners[booking.booking_id] = 2

    resolver = OwnerBookingNotifierResolver(
        booking_repo=booking_repo,
        user_repo=FakeUserRepo([_invited_user(access_state=UserAccessState.REVOKED)]),
        owner_notifiers=[FakeNotifier("email")],
        telegram_bot_settings=TelegramBotSettings(),
        telegram_bot_token="fake-token",
    )

    assert resolver(booking) == []


def test_unresolvable_booking_owner_gets_no_notifiers() -> None:
    booking = make_booking("b-orphan")
    booking_repo = FakeBookingRepository([booking])
    # No owners entry recorded for this booking id.

    resolver = OwnerBookingNotifierResolver(
        booking_repo=booking_repo,
        user_repo=FakeUserRepo([]),
        owner_notifiers=[FakeNotifier("email")],
        telegram_bot_settings=TelegramBotSettings(),
        telegram_bot_token="fake-token",
    )

    assert resolver(booking) == []
