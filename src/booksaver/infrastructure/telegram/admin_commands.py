from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from booksaver.domain.user import User, UserAccessState

from .access import AccessControl
from .client import TelegramBotClient
from .router import CallbackRouter, CommandRouter, IncomingCallback, IncomingCommand

if TYPE_CHECKING:
    from booksaver.infrastructure.persistence.sqlite_store import SqliteUserRepository

logger = logging.getLogger(__name__)

Reply = Callable[[int, str], None]
Send = Callable[[int, str, dict[str, Any] | None], None]

USAGE = (
    "Usage:\n"
    "/admin users\n"
    "/admin revoke <user_id|telegram_id>\n"
    "/admin purge <user_id|telegram_id> [confirm]\n"
    "/admin invite\n"
    "/admin mode <owner|invite> [confirm]"
)


def _resolve_user(users: SqliteUserRepository, token: str) -> User | None:
    """Accepts either a BookSaver `user_id` or a Telegram user id and
    resolves whichever one matches — the owner types whatever `/admin users`
    printed, which shows both."""
    try:
        as_int = int(token)
    except ValueError:
        return None
    user = users.get_by_id(as_int)
    if user is not None:
        return user
    return users.get_by_telegram_id(as_int)


def register_admin_commands(
    router: CommandRouter,
    reply: Reply,
    db_path: Path,
    access_control: AccessControl,
    *,
    callback_router: CallbackRouter | None = None,
    client: TelegramBotClient | None = None,
    send: Send | None = None,
) -> None:
    """`/admin ...` (US-028): owner-only. Every branch re-checks
    `access_control.is_owner` (never trusts having reached the handler alone)
    and logs an audit entry — refusals log user id + command only, never
    message bodies, matching US-026.
    """

    def _menu_markup() -> dict[str, Any]:
        return {
            "inline_keyboard": [
                [
                    {"text": "Users", "callback_data": "admin:users"},
                    {"text": "Create invite", "callback_data": "admin:invite"},
                ],
                [
                    {"text": "Revoke user", "callback_data": "admin:revoke"},
                    {"text": "Purge user", "callback_data": "admin:purge"},
                ],
                [{"text": "Access mode", "callback_data": "admin:mode"}],
            ]
        }

    def _admin(cmd: IncomingCommand) -> None:
        if not access_control.is_owner(cmd.chat_id):
            logger.info(
                "Admin command refused: user_id=%s command=/admin (non-owner)", cmd.user_id
            )
            reply(cmd.chat_id, "Admin commands are owner-only.")
            return

        parts = cmd.args.split()
        if not parts:
            if send is not None and callback_router is not None and client is not None:
                send(cmd.chat_id, "Choose an admin action:", _menu_markup())
            else:
                reply(cmd.chat_id, USAGE)
            return

        sub, *rest = parts
        logger.info("Admin command: user_id=%s command=/admin %s", cmd.user_id, sub)

        if sub == "users":
            _handle_users(cmd, reply, db_path)
        elif sub == "revoke":
            _handle_revoke(cmd, reply, db_path, rest)
        elif sub == "purge":
            _handle_purge(cmd, reply, db_path, rest)
        elif sub == "invite":
            _handle_invite(cmd, reply, db_path)
        elif sub == "mode":
            _handle_mode(cmd, reply, access_control, rest)
        else:
            reply(cmd.chat_id, USAGE)

    router.register("/admin", _admin)

    if callback_router is not None and client is not None:

        def _ack(callback: IncomingCallback, text: str | None = None) -> None:
            try:
                client.answer_callback_query(callback.callback_query_id, text=text)
            except Exception:
                logger.warning("Could not answer admin callback %s", callback.callback_query_id)

        def _edit(
            callback: IncomingCallback,
            text: str,
            markup: dict[str, Any] | None = None,
        ) -> None:
            try:
                client.edit_message_text(
                    callback.chat_id, callback.message_id, text, reply_markup=markup
                )
            except Exception:
                logger.warning("Could not edit admin menu message %s", callback.message_id)

        def _reply_via_edit(callback: IncomingCallback) -> Reply:
            return lambda _chat_id, text: _edit(
                callback,
                text,
                {"inline_keyboard": [[{"text": "Back", "callback_data": "admin:menu"}]]},
            )

        def _synthetic(callback: IncomingCallback, args: str) -> IncomingCommand:
            return IncomingCommand(
                user_id=callback.user_id,
                chat_id=callback.chat_id,
                command="/admin",
                args=args,
                raw_text=f"/admin {args}",
                message_id=callback.message_id,
            )

        def _target_keyboard(action: str) -> tuple[str, dict[str, Any]]:
            from booksaver.infrastructure.persistence.sqlite_store import (
                SqliteStore,
                SqliteUserRepository,
            )

            with SqliteStore(db_path) as store:
                users = [
                    user
                    for user in SqliteUserRepository(store).list_all()
                    if not user.is_owner
                ]
            if not users:
                return (
                    "No non-owner users are available.",
                    {
                        "inline_keyboard": [
                            [{"text": "Back", "callback_data": "admin:menu"}]
                        ]
                    },
                )
            rows = [
                [
                    {
                        "text": (
                            f"#{user.user_id} · tg {user.telegram_user_id} · "
                            f"{user.access_state.value}"
                        ),
                        "callback_data": f"admin:{action}:{user.user_id}",
                    }
                ]
                for user in users[:20]
            ]
            rows.append([{"text": "Back", "callback_data": "admin:menu"}])
            return f"Choose a user to {action}:", {"inline_keyboard": rows}

        def _confirmation(
            action: str, value: str, label: str
        ) -> tuple[str, dict[str, Any]]:
            return (
                f"Confirm {label}?",
                {
                    "inline_keyboard": [
                        [
                            {
                                "text": "Confirm",
                                "callback_data": f"admin:{action}:{value}:confirm",
                            },
                            {"text": "Cancel", "callback_data": "admin:menu"},
                        ]
                    ]
                },
            )

        def _admin_callback(callback: IncomingCallback) -> None:
            if not access_control.is_owner(callback.chat_id):
                _ack(callback, "Admin commands are owner-only.")
                return
            _ack(callback)
            parts = callback.data.split(":")
            action = parts[1] if len(parts) > 1 else ""

            if action == "menu":
                _edit(callback, "Choose an admin action:", _menu_markup())
                return
            if action == "users":
                _handle_users(
                    _synthetic(callback, "users"), _reply_via_edit(callback), db_path
                )
                return
            if action == "invite":
                _handle_invite(
                    _synthetic(callback, "invite"), _reply_via_edit(callback), db_path
                )
                return
            if action in ("revoke", "purge"):
                if len(parts) == 2:
                    text, markup = _target_keyboard(action)
                    _edit(callback, text, markup)
                    return
                user_token = parts[2]
                if len(parts) == 3:
                    text, markup = _confirmation(
                        action, user_token, f"{action} user #{user_token}"
                    )
                    _edit(callback, text, markup)
                    return
                if len(parts) == 4 and parts[3] == "confirm":
                    cmd = _synthetic(
                        callback,
                        f"{action} {user_token}"
                        + (" confirm" if action == "purge" else ""),
                    )
                    if action == "revoke":
                        _handle_revoke(cmd, _reply_via_edit(callback), db_path, [user_token])
                    else:
                        _handle_purge(
                            cmd,
                            _reply_via_edit(callback),
                            db_path,
                            [user_token, "confirm"],
                        )
                    return
            if action == "mode":
                if len(parts) == 2:
                    _edit(
                        callback,
                        f"Current access mode: {access_control.mode}. Choose a mode:",
                        {
                            "inline_keyboard": [
                                [
                                    {"text": "Owner only", "callback_data": "admin:mode:owner"},
                                    {"text": "Invite", "callback_data": "admin:mode:invite"},
                                ],
                                [{"text": "Back", "callback_data": "admin:menu"}],
                            ]
                        },
                    )
                    return
                mode = parts[2]
                if mode not in ("owner", "invite"):
                    _edit(callback, "That admin choice has expired.", _menu_markup())
                    return
                if len(parts) == 3:
                    text, markup = _confirmation("mode", mode, f"switch access mode to {mode}")
                    _edit(callback, text, markup)
                    return
                if len(parts) == 4 and parts[3] == "confirm":
                    _handle_mode(
                        _synthetic(callback, f"mode {mode} confirm"),
                        _reply_via_edit(callback),
                        access_control,
                        [mode, "confirm"],
                    )
                    return
            _edit(callback, "That admin choice has expired.", _menu_markup())

        callback_router.register("admin:", _admin_callback)


def _handle_users(cmd: IncomingCommand, reply: Reply, db_path: Path) -> None:
    from booksaver.infrastructure.persistence.sqlite_store import (
        SqliteBookingRepository,
        SqliteStore,
        SqliteUserRepository,
    )

    with SqliteStore(db_path) as store:
        users = SqliteUserRepository(store).list_all()
        bookings = SqliteBookingRepository(store)
        lines = ["Users:"]
        for user in users:
            count = len(bookings.list_all_for_user(user.user_id))
            lines.append(
                f"#{user.user_id} tg={user.telegram_user_id} {user.role.value} "
                f"{user.access_state.value} key={'yes' if user.encrypted_key else 'no'} "
                f"bookings={count}"
            )
    reply(cmd.chat_id, "\n".join(lines))


def _handle_revoke(cmd: IncomingCommand, reply: Reply, db_path: Path, rest: list[str]) -> None:
    if not rest:
        reply(cmd.chat_id, "Usage: /admin revoke <user_id|telegram_id>")
        return
    from booksaver.infrastructure.persistence.sqlite_store import (
        SqliteStore,
        SqliteUserRepository,
    )

    with SqliteStore(db_path) as store:
        users = SqliteUserRepository(store)
        user = _resolve_user(users, rest[0])
        if user is None:
            reply(cmd.chat_id, f"No user matching '{rest[0]}'.")
            return
        if user.is_owner:
            reply(cmd.chat_id, "The owner cannot be revoked.")
            return
        users.set_access_state(user.user_id, UserAccessState.REVOKED)
    reply(cmd.chat_id, f"User #{user.user_id} revoked. Their checks stop; data retained.")


def _handle_purge(cmd: IncomingCommand, reply: Reply, db_path: Path, rest: list[str]) -> None:
    if not rest:
        reply(cmd.chat_id, "Usage: /admin purge <user_id|telegram_id> [confirm]")
        return
    from booksaver.infrastructure.persistence.sqlite_store import (
        SqliteStore,
        SqliteUserRepository,
    )

    with SqliteStore(db_path) as store:
        users = SqliteUserRepository(store)
        user = _resolve_user(users, rest[0])
        if user is None:
            reply(cmd.chat_id, f"No user matching '{rest[0]}'.")
            return
        if user.is_owner:
            reply(cmd.chat_id, "The owner cannot be purged.")
            return
        if len(rest) < 2 or rest[1] != "confirm":
            reply(
                cmd.chat_id,
                f"This permanently deletes user #{user.user_id} and all their "
                f"bookings/checks/savings. Resend as "
                f"'/admin purge {rest[0]} confirm' to proceed.",
            )
            return
        users.purge(user.user_id)
    reply(cmd.chat_id, f"User #{user.user_id} and all their data were purged.")


def _handle_invite(cmd: IncomingCommand, reply: Reply, db_path: Path) -> None:
    from booksaver.infrastructure.persistence.sqlite_store import (
        SqliteInviteCodeRepository,
        SqliteStore,
        SqliteUserRepository,
    )

    with SqliteStore(db_path) as store:
        owner = SqliteUserRepository(store).get_owner()
        invite = SqliteInviteCodeRepository(store).issue(issued_by=owner.user_id)
    reply(
        cmd.chat_id,
        f"Invite code: {invite.code}\nHave them send: /start {invite.code}",
    )


def _handle_mode(
    cmd: IncomingCommand, reply: Reply, access_control: AccessControl, rest: list[str]
) -> None:
    if not rest or rest[0] not in ("owner", "invite"):
        reply(cmd.chat_id, "Usage: /admin mode <owner|invite> [confirm]")
        return
    new_mode = rest[0]
    if len(rest) < 2 or rest[1] != "confirm":
        reply(
            cmd.chat_id,
            f"This switches access mode to '{new_mode}' for this running daemon "
            f"(reverts to config on restart). Resend as '/admin mode {new_mode} "
            "confirm' to proceed.",
        )
        return
    access_control.set_mode(new_mode)
    reply(cmd.chat_id, f"Access mode switched to '{new_mode}'.")
