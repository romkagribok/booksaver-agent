from __future__ import annotations

import logging

from booksaver.application.ports import BookingRepository, Notifier, UserRepository
from booksaver.domain.models import Booking
from booksaver.domain.user import User
from booksaver.domain.value_objects import TelegramBotSettings

from .telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


def resolve_telegram_chat_id(user: User, telegram_bot_settings: TelegramBotSettings) -> int | None:
    """A user's private Telegram chat id, if reachable.

    A user admitted through the bot (owner or invited) has `telegram_user_id`
    set — a Telegram private chat id equals the user's own Telegram id. The
    laptop-mode owner has no Telegram identity at all (`telegram_user_id` is
    `None`); if that same owner also runs the bot on a VPS, `[telegram_bot]
    .owner_chat_id` is the only place their chat id is configured, so it's the
    fallback for owner rows specifically. Any other user with no linked
    Telegram id has no reachable chat.
    """
    if user.telegram_user_id is not None:
        return user.telegram_user_id
    if user.is_owner and telegram_bot_settings.owner_chat_id is not None:
        return telegram_bot_settings.owner_chat_id
    return None


class OwnerBookingNotifierResolver:
    """Routes a savings alert to the booking's owning user (US-030), for use
    as `NotificationDispatcher(resolver=...)`.

    - Owner-owned bookings keep today's behavior unchanged: the statically
      configured channels (owner email via SMTP, plus the single
      `notifications.telegram_chat_id` if set).
    - Bookings owned by another (bot-registered) user route to a fresh
      `TelegramNotifier` addressed to that user's own chat — they don't get
      email, since only the owner's SMTP settings exist.
    - If the owning user can't be resolved, is revoked, has no reachable
      chat, or the bot token isn't configured, this returns `[]` and logs a
      warning — the pipeline (`NotificationDispatcher.dispatch`) already
      treats an empty notifier list as "nothing to send", so a booking with
      an unreachable owner never crashes the whole tick.
    """

    def __init__(
        self,
        booking_repo: BookingRepository,
        user_repo: UserRepository,
        owner_notifiers: list[Notifier],
        telegram_bot_settings: TelegramBotSettings,
        telegram_bot_token: str | None,
    ) -> None:
        self._bookings = booking_repo
        self._users = user_repo
        self._owner_notifiers = owner_notifiers
        self._telegram_bot_settings = telegram_bot_settings
        self._telegram_bot_token = telegram_bot_token

    def __call__(self, booking: Booking) -> list[Notifier]:
        owner_user_id = self._bookings.get_owner_user_id(booking.booking_id)
        if owner_user_id is None:
            logger.warning(
                "Booking %s has no resolvable owning user; alert dropped", booking.booking_id
            )
            return []

        user = self._users.get_by_id(owner_user_id)
        if user is None:
            logger.warning(
                "Booking %s owner user %s no longer exists; alert dropped",
                booking.booking_id,
                owner_user_id,
            )
            return []

        if user.is_owner:
            return self._owner_notifiers

        if not user.is_active:
            logger.warning(
                "Booking %s owner user %s is revoked; alert dropped",
                booking.booking_id,
                user.user_id,
            )
            return []

        chat_id = resolve_telegram_chat_id(user, self._telegram_bot_settings)
        if chat_id is None:
            logger.warning(
                "Booking %s owner user %s has no reachable Telegram chat; alert dropped",
                booking.booking_id,
                user.user_id,
            )
            return []

        if not self._telegram_bot_token:
            logger.warning(
                "Booking %s owner user %s needs a routed Telegram alert but "
                "BOOKSAVER_TELEGRAM_BOT_TOKEN is not set; alert dropped",
                booking.booking_id,
                user.user_id,
            )
            return []

        return [TelegramNotifier(bot_token=self._telegram_bot_token, chat_id=str(chat_id))]
