from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from booksaver.domain.user import User, UserAccessState, UserRole

from .access import AccessControl
from .admin_usage import AdminUsageProvider
from .client import TelegramBotClient
from .router import CallbackRouter, CommandRouter, IncomingCallback, IncomingCommand

if TYPE_CHECKING:
    from booksaver.infrastructure.persistence.sqlite_store import SqliteUserRepository

logger = logging.getLogger(__name__)

Reply = Callable[[int, str], None]
Send = Callable[[int, str, dict[str, Any] | None], None]
NotifyAccessLoss = Callable[[int, str], None]
CancelRemoteAuthentication = Callable[[int], bool]
RevokeUserSession = Callable[[int], bool]
PurgeIncidentEvidence = Callable[[int], object]

ACCESS_LOSS_MESSAGE = "You no longer have access to this bot."

USAGE = (
    "Usage:\n"
    "/admin users\n"
    "/admin revoke <user_id>\n"
    "/admin purge <user_id> [confirm]\n"
    "/admin invite"
)


def _resolve_user(users: SqliteUserRepository, token: str) -> User | None:
    """Resolve only the internal BookSaver id shown by owner admin controls."""
    try:
        as_int = int(token)
    except ValueError:
        return None
    return users.get_by_id(as_int)


class _UserLabelFields(Protocol):
    @property
    def user_id(self) -> int: ...

    @property
    def telegram_username(self) -> str | None: ...


def _user_label(user: _UserLabelFields) -> str:
    """Human-safe admin label; Telegram numeric identities are never exposed."""
    username = user.telegram_username
    if username:
        return f"@{username.lstrip('@')}"
    return f"User #{user.user_id} (no @username)"


def register_admin_commands(
    router: CommandRouter,
    reply: Reply,
    db_path: Path,
    access_control: AccessControl,
    *,
    callback_router: CallbackRouter | None = None,
    client: TelegramBotClient | None = None,
    send: Send | None = None,
    notify_access_loss: NotifyAccessLoss | None = None,
    usage_provider: AdminUsageProvider | None = None,
    cancel_remote_authentication: CancelRemoteAuthentication,
    revoke_user_session: RevokeUserSession,
    purge_incident_evidence: PurgeIncidentEvidence | None = None,
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
            _handle_users(cmd, reply, db_path, usage_provider=usage_provider)
        elif sub == "revoke":
            _handle_revoke(
                cmd,
                reply,
                db_path,
                rest,
                notify_access_loss=notify_access_loss,
            )
        elif sub == "purge":
            _handle_purge(
                cmd,
                reply,
                db_path,
                rest,
                cancel_remote_authentication=cancel_remote_authentication,
                revoke_user_session=revoke_user_session,
                purge_incident_evidence=purge_incident_evidence,
            )
        elif sub == "invite":
            _handle_invite(cmd, reply, db_path, send=send)
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
                    for user in SqliteUserRepository(store).list_admin_aggregates()
                    if user.role is not UserRole.OWNER
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
                            f"{_user_label(user)} · {user.access_state.value}"
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
                    _synthetic(callback, "users"),
                    _reply_via_edit(callback),
                    db_path,
                    usage_provider=usage_provider,
                )
                return
            if action == "invite":
                _handle_invite(
                    _synthetic(callback, "invite"),
                    _reply_via_edit(callback),
                    db_path,
                    send=send,
                )
                return
            if action in ("revoke", "purge"):
                if len(parts) == 2:
                    text, markup = _target_keyboard(action)
                    _edit(callback, text, markup)
                    return
                user_token = parts[2]
                if len(parts) == 3:
                    from booksaver.infrastructure.persistence.sqlite_store import (
                        SqliteStore,
                        SqliteUserRepository,
                    )

                    try:
                        selected_id = int(user_token)
                    except ValueError:
                        _edit(callback, "That admin choice has expired.", _menu_markup())
                        return
                    with SqliteStore(db_path) as store:
                        selected = SqliteUserRepository(store).get_by_id(selected_id)
                    selected_label = (
                        _user_label(selected) if selected is not None else "selected user"
                    )
                    text, markup = _confirmation(
                        action, user_token, f"{action} {selected_label}"
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
                        _handle_revoke(
                            cmd,
                            _reply_via_edit(callback),
                            db_path,
                            [user_token],
                            notify_access_loss=notify_access_loss,
                        )
                    else:
                        _handle_purge(
                            cmd,
                            _reply_via_edit(callback),
                            db_path,
                            [user_token, "confirm"],
                            cancel_remote_authentication=cancel_remote_authentication,
                            revoke_user_session=revoke_user_session,
                            purge_incident_evidence=purge_incident_evidence,
                        )
                    return
            _edit(callback, "That admin choice has expired.", _menu_markup())

        callback_router.register("admin:", _admin_callback)


def _handle_users(
    cmd: IncomingCommand,
    reply: Reply,
    db_path: Path,
    *,
    usage_provider: AdminUsageProvider | None = None,
) -> None:
    from booksaver.infrastructure.persistence.sqlite_store import (
        SqliteStore,
        SqliteUserRepository,
    )

    with SqliteStore(db_path) as store:
        users = SqliteUserRepository(store).list_admin_aggregates()

    lines = ["Users:"]
    for user in users:
        lines.append(
            f"{_user_label(user)} · role={user.role.value} · "
            f"access={user.access_state.value} · "
            f"active bookings={user.active_booking_count}"
        )
        usage = None
        if usage_provider is not None:
            try:
                usage = usage_provider(user.user_id)
            except Exception:
                logger.warning("Could not read runtime usage for BookSaver user #%s", user.user_id)
        usage_label = "Usage today (resets at UTC midnight and daemon restart)"
        if usage is None:
            lines.append(f"  {usage_label}: unavailable")
        else:
            lines.append(
                f"  {usage_label}: checks={usage.checks_today}, "
                f"LLM calls={usage.llm_calls_today}"
            )
    reply(cmd.chat_id, "\n".join(lines))


def _handle_revoke(
    cmd: IncomingCommand,
    reply: Reply,
    db_path: Path,
    rest: list[str],
    *,
    notify_access_loss: NotifyAccessLoss | None = None,
) -> None:
    if not rest:
        reply(cmd.chat_id, "Usage: /admin revoke <user_id>")
        return
    from booksaver.infrastructure.persistence.sqlite_store import (
        SqliteStore,
        SqliteUserRepository,
    )

    with SqliteStore(db_path) as store:
        users = SqliteUserRepository(store)
        user = _resolve_user(users, rest[0])
        if user is None:
            reply(cmd.chat_id, "No matching user.")
            return
        if user.is_owner:
            reply(cmd.chat_id, "The owner cannot be revoked.")
            return
        users.set_access_state(user.user_id, UserAccessState.REVOKED)
    delivery = "unavailable"
    if notify_access_loss is not None and user.telegram_user_id is not None:
        try:
            notify_access_loss(user.telegram_user_id, ACCESS_LOSS_MESSAGE)
            delivery = "delivered"
        except Exception:
            delivery = "failed"
            logger.warning("Could not deliver a revoked-user access-loss notice")
    reply(
        cmd.chat_id,
        f"{_user_label(user)} revoked. Their checks stop; data retained. "
        f"Access-loss notice {delivery}.",
    )


def _handle_purge(
    cmd: IncomingCommand,
    reply: Reply,
    db_path: Path,
    rest: list[str],
    *,
    cancel_remote_authentication: CancelRemoteAuthentication,
    revoke_user_session: RevokeUserSession,
    purge_incident_evidence: PurgeIncidentEvidence | None,
) -> None:
    if not rest:
        reply(cmd.chat_id, "Usage: /admin purge <user_id> [confirm]")
        return
    from booksaver.infrastructure.persistence.sqlite_store import (
        SqliteStore,
        SqliteUserRepository,
    )

    with SqliteStore(db_path) as store:
        users = SqliteUserRepository(store)
        user = _resolve_user(users, rest[0])
        if user is None:
            reply(cmd.chat_id, "No matching user.")
            return
        if user.is_owner:
            reply(cmd.chat_id, "The owner cannot be purged.")
            return
        if len(rest) < 2 or rest[1] != "confirm":
            reply(
                cmd.chat_id,
                f"This permanently deletes {_user_label(user)}, their encrypted "
                f"Booking.com session, and all bookings/checks/savings. Resend as "
                f"'/admin purge {user.user_id} confirm' to proceed.",
            )
            return
        if user.telegram_user_id is not None:
            cancel_remote_authentication(user.telegram_user_id)
        try:
            revoke_user_session(user.user_id)
        except OSError:
            logger.warning(
                "Could not remove encrypted session while purging BookSaver user #%s",
                user.user_id,
            )
            reply(
                cmd.chat_id,
                f"Could not purge {_user_label(user)} because their encrypted "
                "Booking.com session could not be removed. No database data was "
                "deleted; try again.",
            )
            return
        try:
            if purge_incident_evidence is not None:
                purge_incident_evidence(user.user_id)
        except Exception:
            logger.warning(
                "Could not remove encrypted DOM diagnostics while purging "
                "BookSaver user #%s",
                user.user_id,
            )
            reply(
                cmd.chat_id,
                f"Could not purge {_user_label(user)} because encrypted diagnostic "
                "cleanup did not finish. Their database data was retained; try again.",
            )
            return
        try:
            users.purge(user.user_id)
        except sqlite3.Error:
            logger.warning(
                "Database cleanup did not complete after revoking BookSaver user #%s",
                user.user_id,
            )
            reply(
                cmd.chat_id,
                f"Authentication for {_user_label(user)} was revoked, but database "
                "cleanup did not finish. Retry the same confirmed purge; do not "
                "re-admit the user until it succeeds.",
            )
            return
    reply(cmd.chat_id, f"{_user_label(user)} and all their data were purged.")


def _handle_invite(
    cmd: IncomingCommand,
    reply: Reply,
    db_path: Path,
    *,
    send: Send | None = None,
) -> None:
    from booksaver.infrastructure.persistence.sqlite_store import (
        SqliteInviteCodeRepository,
        SqliteStore,
        SqliteUserRepository,
    )

    with SqliteStore(db_path) as store:
        owner = SqliteUserRepository(store).get_owner()
        invite = SqliteInviteCodeRepository(store).issue(issued_by=owner.user_id)
    reply(cmd.chat_id, "Invite created. Forward the next message to the person you are inviting.")
    command = f"/start {invite.code}"
    if send is None:
        reply(cmd.chat_id, command)
        return
    try:
        send(cmd.chat_id, command, None)
    except Exception:
        # The invite is already committed. Do not issue another code implicitly,
        # and never put the secret code in logs.
        logger.warning("Could not send the newly-created invite command")
