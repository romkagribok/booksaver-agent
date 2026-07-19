"""US-028: owner-only /admin commands."""

from datetime import UTC, date, datetime

from booksaver.domain.models import Booking, BookingStatus
from booksaver.domain.value_objects import (
    ConfirmationId,
    Money,
    Occupancy,
    Platform,
    ProductType,
    Property,
    RefundabilityPolicy,
    RoomType,
    StayDates,
)
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteBookingRepository,
    SqliteStore,
    SqliteUserRepository,
)
from booksaver.infrastructure.telegram.access import AccessControl
from booksaver.infrastructure.telegram.admin_commands import register_admin_commands
from booksaver.infrastructure.telegram.admin_usage import AdminUsageSnapshot
from booksaver.infrastructure.telegram.router import (
    CallbackRouter,
    CommandRouter,
    IncomingCallback,
    IncomingCommand,
)

OWNER_CHAT_ID = 555


def _cmd(chat_id: int, args: str, user_id: int | None = None) -> IncomingCommand:
    return IncomingCommand(
        user_id=user_id if user_id is not None else chat_id,
        chat_id=chat_id,
        command="/admin",
        args=args,
        raw_text=f"/admin {args}".strip(),
    )


def _wire(tmp_path, notify_access_loss=None, *, send=None, usage_provider=None):
    db_path = tmp_path / "t.db"
    with SqliteStore(db_path):
        pass
    router = CommandRouter()
    sent: list[tuple[int, str]] = []
    access_control = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path)
    register_admin_commands(
        router=router, reply=lambda c, t: sent.append((c, t)), db_path=db_path,
        access_control=access_control,
        send=send,
        notify_access_loss=notify_access_loss,
        usage_provider=usage_provider,
    )
    return router, sent, db_path, access_control


class _InteractiveClient:
    def __init__(self) -> None:
        self.answered: list[tuple[str, str | None]] = []
        self.edits: list[dict] = []

    def answer_callback_query(self, callback_query_id: str, text: str | None = None):
        self.answered.append((callback_query_id, text))
        return {}

    def edit_message_text(self, chat_id, message_id, text, reply_markup=None):
        self.edits.append(
            {"chat_id": chat_id, "message_id": message_id, "text": text, "markup": reply_markup}
        )
        return {}


def _interactive_wire(tmp_path, notify_access_loss=None, *, usage_provider=None):
    db_path = tmp_path / "interactive.db"
    with SqliteStore(db_path):
        pass
    router = CommandRouter()
    callbacks = CallbackRouter()
    client = _InteractiveClient()
    sent: list[dict] = []
    access_control = AccessControl(owner_chat_id=OWNER_CHAT_ID, db_path=db_path)
    register_admin_commands(
        router=router,
        reply=lambda chat_id, text: sent.append({"chat_id": chat_id, "text": text}),
        db_path=db_path,
        access_control=access_control,
        callback_router=callbacks,
        client=client,  # type: ignore[arg-type]
        send=lambda chat_id, text, markup: sent.append(
            {"chat_id": chat_id, "text": text, "markup": markup}
        ),
        notify_access_loss=notify_access_loss,
        usage_provider=usage_provider,
    )
    return router, callbacks, client, sent, db_path, access_control


def _callback(data: str, chat_id: int = OWNER_CHAT_ID) -> IncomingCallback:
    return IncomingCallback(
        user_id=chat_id,
        chat_id=chat_id,
        callback_query_id=f"cb-{len(data)}",
        message_id=10,
        data=data,
    )


def _booking(
    booking_id: str,
    confirmation: str,
    property_name: str,
    *,
    status: BookingStatus = BookingStatus.ACTIVE,
) -> Booking:
    return Booking(
        booking_id=booking_id,
        platform=Platform.BOOKING_COM,
        product_type=ProductType.HOTEL,
        confirmation_id=ConfirmationId.of(confirmation),
        property=Property(
            name=property_name,
            booking_com_ref="https://booking.com/hotel/private-sentinel",
        ),
        stay_dates=StayDates(date(2026, 10, 1), date(2026, 10, 5)),
        room_type=RoomType("PRIVATE ROOM SENTINEL"),
        baseline_price=Money.of("987654.32", "ZZZ"),
        refundability=RefundabilityPolicy(True, "PRIVATE REFUND SENTINEL"),
        occupancy=Occupancy(2),
        registered_at=datetime.now(UTC),
        status=status,
    )


class TestNonOwnerRefusal:
    def test_non_owner_is_refused(self, tmp_path):
        router, sent, _db, _ac = _wire(tmp_path)
        router.dispatch(_cmd(chat_id=999, args="users"))
        assert sent == [(999, "Admin commands are owner-only.")]


class TestUsersListing:
    def test_lists_users_by_username_without_telegram_ids(self, tmp_path):
        usage_by_user: dict[int, AdminUsageSnapshot] = {}
        router, sent, db_path, _ac = _wire(
            tmp_path, usage_provider=lambda user_id: usage_by_user[user_id]
        )
        with SqliteStore(db_path) as store:
            user = SqliteUserRepository(store).get_or_create_by_telegram_id(42)
            store.conn.execute(
                "UPDATE users SET telegram_username = ? WHERE user_id = ?",
                ("alice", user.user_id),
            )
            store.conn.commit()
            owner = SqliteUserRepository(store).get_owner()
        usage_by_user[owner.user_id] = AdminUsageSnapshot(0, 0)
        usage_by_user[user.user_id] = AdminUsageSnapshot(3, 7)

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="users"))

        assert len(sent) == 1
        assert "Users:" in sent[0][1]
        assert "@alice · role=user · access=active · active bookings=0" in sent[0][1]
        assert "checks=3, LLM calls=7" in sent[0][1]
        assert "42" not in sent[0][1]
        assert "tg=" not in sent[0][1]

    def test_lists_missing_username_as_internal_user_number(self, tmp_path):
        router, sent, db_path, _ac = _wire(tmp_path)
        with SqliteStore(db_path) as store:
            user = SqliteUserRepository(store).get_or_create_by_telegram_id(99112233)

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="users"))

        assert f"User #{user.user_id} (no @username)" in sent[0][1]
        assert "99112233" not in sent[0][1]
        assert "Usage today (resets at UTC midnight and daemon restart): unavailable" in sent[0][1]
        assert "checks=0" not in sent[0][1]

    def test_allowlisted_aggregate_uses_sql_counts_and_hides_exact_data(
        self, tmp_path, monkeypatch
    ):
        usage_by_user: dict[int, AdminUsageSnapshot] = {}
        router, sent, db_path, _ac = _wire(
            tmp_path, usage_provider=lambda user_id: usage_by_user[user_id]
        )
        with SqliteStore(db_path) as store:
            users = SqliteUserRepository(store)
            user = users.get_or_create_by_telegram_id(8675309)
            users.set_telegram_username(user.user_id, "alice")
            users.set_encrypted_key(user.user_id, b"PRIVATE KEY SENTINEL")
            owner = users.get_owner()
            bookings = SqliteBookingRepository(store)
            bookings.add(
                _booking(
                    "private-booking-id-sentinel",
                    "PRIVATE-CONFIRMATION-SENTINEL",
                    "PRIVATE PROPERTY SENTINEL",
                ),
                user_id=user.user_id,
            )
            bookings.add(
                _booking(
                    "archived-booking-id-sentinel",
                    "ARCHIVED-CONFIRMATION-SENTINEL",
                    "ARCHIVED PROPERTY SENTINEL",
                    status=BookingStatus.ARCHIVED,
                ),
                user_id=user.user_id,
            )
            store.conn.execute(
                """
                INSERT INTO check_history (
                    check_id, booking_id, checked_at, outcome, extraction_method,
                    failure_code, failure_detail
                ) VALUES (?, ?, ?, 'failure', 'none', 'navigation_failed', ?)
                """,
                (
                    "PRIVATE-CHECK-ID-SENTINEL",
                    "private-booking-id-sentinel",
                    datetime.now(UTC).isoformat(),
                    "PRIVATE FAILURE SENTINEL",
                ),
            )
            store.conn.commit()

        usage_by_user[owner.user_id] = AdminUsageSnapshot(0, 0)
        usage_by_user[user.user_id] = AdminUsageSnapshot(12, 34)

        def materialization_forbidden(*_args, **_kwargs):
            raise AssertionError("Admin aggregates must not materialize Booking records")

        monkeypatch.setattr(
            SqliteBookingRepository, "list_all_for_user", materialization_forbidden
        )
        monkeypatch.setattr(
            SqliteBookingRepository, "list_active_for_user", materialization_forbidden
        )
        monkeypatch.setattr(SqliteBookingRepository, "list_all", materialization_forbidden)

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="users"))

        output = sent[0][1]
        assert "@alice · role=user · access=active · active bookings=1" in output
        assert "checks=12, LLM calls=34" in output
        for sentinel in (
            "8675309",
            "PRIVATE KEY SENTINEL",
            "private-booking-id-sentinel",
            "PRIVATE-CONFIRMATION-SENTINEL",
            "PRIVATE PROPERTY SENTINEL",
            "PRIVATE ROOM SENTINEL",
            "987654.32",
            "ZZZ",
            "PRIVATE REFUND SENTINEL",
            "PRIVATE-CHECK-ID-SENTINEL",
            "PRIVATE FAILURE SENTINEL",
            "navigation_failed",
        ):
            assert sentinel not in output

    def test_usage_provider_failure_reports_unavailable(self, tmp_path):
        def fail(_user_id: int) -> AdminUsageSnapshot:
            raise RuntimeError("counter unavailable")

        router, sent, _db_path, _ac = _wire(tmp_path, usage_provider=fail)

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="users"))

        assert "Usage today (resets at UTC midnight and daemon restart): unavailable" in sent[0][1]


class TestRevoke:
    def test_typed_target_accepts_internal_id_not_telegram_id(self, tmp_path):
        router, sent, db_path, _ac = _wire(tmp_path)
        with SqliteStore(db_path) as store:
            target = SqliteUserRepository(store).get_or_create_by_telegram_id(42424242)

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="revoke 42424242"))

        assert sent[-1][1] == "No matching user."
        with SqliteStore(db_path) as store:
            current = SqliteUserRepository(store).get_by_id(target.user_id)
        assert current is not None and current.is_active

    def test_revokes_then_delivers_exact_access_loss_message(self, tmp_path):
        delivered: list[tuple[int, str]] = []
        db_path_holder = []

        def notify(chat_id: int, text: str) -> None:
            with SqliteStore(db_path_holder[0]) as store:
                target = SqliteUserRepository(store).get_by_telegram_id(chat_id)
            assert target is not None
            assert target.access_state.value == "revoked"
            delivered.append((chat_id, text))

        router, sent, db_path, _ac = _wire(tmp_path, notify_access_loss=notify)
        db_path_holder.append(db_path)
        with SqliteStore(db_path) as store:
            target = SqliteUserRepository(store).get_or_create_by_telegram_id(42)

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args=f"revoke {target.user_id}"))

        assert delivered == [(42, "You no longer have access to this bot.")]
        assert "notice delivered" in sent[-1][1]
        with SqliteStore(db_path) as store:
            reloaded = SqliteUserRepository(store).get_by_telegram_id(42)
        assert reloaded is not None
        assert reloaded.access_state.value == "revoked"

    def test_notification_failure_keeps_revocation_and_reports_failure(self, tmp_path):
        def fail(_chat_id: int, _text: str) -> None:
            raise RuntimeError("Telegram unavailable")

        router, sent, db_path, _ac = _wire(tmp_path, notify_access_loss=fail)
        with SqliteStore(db_path) as store:
            target = SqliteUserRepository(store).get_or_create_by_telegram_id(42)

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args=f"revoke {target.user_id}"))

        with SqliteStore(db_path) as store:
            reloaded = SqliteUserRepository(store).get_by_id(target.user_id)
        assert reloaded is not None and not reloaded.is_active
        assert "notice failed" in sent[-1][1]

    def test_missing_notifier_reports_unavailable(self, tmp_path):
        router, sent, db_path, _ac = _wire(tmp_path)
        with SqliteStore(db_path) as store:
            target = SqliteUserRepository(store).get_or_create_by_telegram_id(42)

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args=f"revoke {target.user_id}"))

        assert "notice unavailable" in sent[-1][1]

    def test_owner_cannot_be_revoked(self, tmp_path):
        router, sent, db_path, _ac = _wire(tmp_path)
        with SqliteStore(db_path) as store:
            owner = SqliteUserRepository(store).get_owner()

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args=f"revoke {owner.user_id}"))

        assert "cannot be revoked" in sent[-1][1]


class TestPurge:
    def test_purge_requires_explicit_confirmation(self, tmp_path):
        router, sent, db_path, _ac = _wire(tmp_path)
        with SqliteStore(db_path) as store:
            target = SqliteUserRepository(store).get_or_create_by_telegram_id(42)

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args=f"purge {target.user_id}"))

        assert "confirm" in sent[-1][1]
        with SqliteStore(db_path) as store:
            still_there = SqliteUserRepository(store).get_by_telegram_id(42)
        assert still_there is not None

    def test_purge_with_confirm_deletes_the_user(self, tmp_path):
        router, sent, db_path, _ac = _wire(tmp_path)
        with SqliteStore(db_path) as store:
            target = SqliteUserRepository(store).get_or_create_by_telegram_id(42)

        router.dispatch(
            _cmd(chat_id=OWNER_CHAT_ID, args=f"purge {target.user_id} confirm")
        )

        assert "purged" in sent[-1][1]
        with SqliteStore(db_path) as store:
            gone = SqliteUserRepository(store).get_by_telegram_id(42)
        assert gone is None


class TestInvite:
    def test_fallback_replies_with_guidance_then_exact_redeemable_command(self, tmp_path):
        router, sent, db_path, _ac = _wire(tmp_path)

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="invite"))

        assert len(sent) == 2
        assert "/start" not in sent[0][1]
        assert sent[1][1].startswith("/start ")
        code = sent[1][1].removeprefix("/start ")

        from booksaver.infrastructure.persistence.sqlite_store import SqliteInviteCodeRepository

        with SqliteStore(db_path) as store:
            invite = SqliteInviteCodeRepository(store).get(code)
        assert invite is not None
        assert not invite.is_used

    def test_send_failure_does_not_log_code_or_issue_another(self, tmp_path, caplog):
        def fail_send(_chat_id, _text, _markup):
            raise RuntimeError("Telegram unavailable")

        router, sent, db_path, _ac = _wire(tmp_path, send=fail_send)

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="invite"))

        assert len(sent) == 1
        with SqliteStore(db_path) as store:
            rows = store.conn.execute("SELECT code FROM invite_codes").fetchall()
        assert len(rows) == 1
        assert rows[0][0] not in caplog.text
        assert "Could not send the newly-created invite command" in caplog.text


class TestUsageFallback:
    def test_no_subcommand_shows_usage(self, tmp_path):
        router, sent, _db, _ac = _wire(tmp_path)
        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args=""))
        assert "Usage" in sent[-1][1]

    def test_unknown_subcommand_shows_usage(self, tmp_path):
        router, sent, _db, _ac = _wire(tmp_path)
        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="frobnicate"))
        assert "Usage" in sent[-1][1]

    def test_access_mode_command_is_not_available(self, tmp_path):
        router, sent, _db, _ac = _wire(tmp_path)

        router.dispatch(_cmd(chat_id=OWNER_CHAT_ID, args="mode owner confirm"))

        assert "Usage" in sent[-1][1]
        assert "/admin mode" not in sent[-1][1]
        assert "telegram_id" not in sent[-1][1]


class TestInteractiveAdmin:
    def test_no_args_offers_complete_admin_action_menu(self, tmp_path):
        router, _callbacks, _client, sent, _db, _access = _interactive_wire(tmp_path)

        router.dispatch(_cmd(OWNER_CHAT_ID, ""))

        buttons = [
            button["callback_data"]
            for row in sent[0]["markup"]["inline_keyboard"]
            for button in row
        ]
        assert buttons == [
            "admin:users",
            "admin:invite",
            "admin:revoke",
            "admin:purge",
        ]

    def test_invite_callback_edits_guidance_and_sends_exact_command(self, tmp_path):
        _router, callbacks, client, sent, db_path, _access = _interactive_wire(tmp_path)

        callbacks.dispatch(_callback("admin:invite"))

        assert "/start" not in client.edits[-1]["text"]
        assert len(sent) == 1
        assert sent[0]["text"].startswith("/start ")
        code = sent[0]["text"].removeprefix("/start ")
        with SqliteStore(db_path) as store:
            rows = store.conn.execute("SELECT code FROM invite_codes").fetchall()
        assert [row[0] for row in rows] == [code]

    def test_users_callback_uses_runtime_aggregate_provider(self, tmp_path):
        _router, callbacks, client, _sent, _db, _access = _interactive_wire(
            tmp_path,
            usage_provider=lambda _user_id: AdminUsageSnapshot(
                checks_today=4, llm_calls_today=9
            ),
        )

        callbacks.dispatch(_callback("admin:users"))

        assert "checks=4, LLM calls=9" in client.edits[-1]["text"]
        assert "key=" not in client.edits[-1]["text"]

    def test_revoke_picker_excludes_owner_and_requires_confirmation(self, tmp_path):
        _router, callbacks, client, _sent, db_path, _access = _interactive_wire(tmp_path)
        with SqliteStore(db_path) as store:
            target = SqliteUserRepository(store).get_or_create_by_telegram_id(42)

        callbacks.dispatch(_callback("admin:revoke"))
        target_buttons = client.edits[-1]["markup"]["inline_keyboard"]
        callback_data = target_buttons[0][0]["callback_data"]
        assert callback_data == f"admin:revoke:{target.user_id}"

        callbacks.dispatch(_callback(callback_data))
        with SqliteStore(db_path) as store:
            assert SqliteUserRepository(store).get_by_id(target.user_id).is_active
        confirm = client.edits[-1]["markup"]["inline_keyboard"][0][0]["callback_data"]
        assert confirm.endswith(":confirm")

        callbacks.dispatch(_callback(confirm))
        with SqliteStore(db_path) as store:
            assert not SqliteUserRepository(store).get_by_id(target.user_id).is_active

    def test_purge_picker_cancels_without_mutation_and_confirms_cascade(self, tmp_path):
        _router, callbacks, client, _sent, db_path, _access = _interactive_wire(tmp_path)
        with SqliteStore(db_path) as store:
            target = SqliteUserRepository(store).get_or_create_by_telegram_id(42)

        callbacks.dispatch(_callback(f"admin:purge:{target.user_id}"))
        cancel = client.edits[-1]["markup"]["inline_keyboard"][0][1]["callback_data"]
        callbacks.dispatch(_callback(cancel))
        with SqliteStore(db_path) as store:
            assert SqliteUserRepository(store).get_by_id(target.user_id) is not None

        callbacks.dispatch(_callback(f"admin:purge:{target.user_id}:confirm"))
        with SqliteStore(db_path) as store:
            assert SqliteUserRepository(store).get_by_id(target.user_id) is None

    def test_revoke_picker_uses_username_not_telegram_id(self, tmp_path):
        _router, callbacks, client, _sent, db_path, _access = _interactive_wire(tmp_path)
        with SqliteStore(db_path) as store:
            target = SqliteUserRepository(store).get_or_create_by_telegram_id(99112233)
            store.conn.execute(
                "UPDATE users SET telegram_username = ? WHERE user_id = ?",
                ("alice", target.user_id),
            )
            store.conn.commit()

        callbacks.dispatch(_callback("admin:revoke"))

        button_text = client.edits[-1]["markup"]["inline_keyboard"][0][0]["text"]
        assert button_text == "@alice · active"
        assert "99112233" not in button_text

    def test_stale_or_forged_user_callback_expires_safely(self, tmp_path):
        _router, callbacks, client, _sent, _db, _access = _interactive_wire(tmp_path)

        callbacks.dispatch(_callback("admin:revoke:not-a-user"))

        assert client.edits[-1]["text"] == "That admin choice has expired."

    def test_revoke_callback_delivers_access_loss_message(self, tmp_path):
        delivered: list[tuple[int, str]] = []
        _router, callbacks, _client, _sent, db_path, _access = _interactive_wire(
            tmp_path, notify_access_loss=lambda chat_id, text: delivered.append((chat_id, text))
        )
        with SqliteStore(db_path) as store:
            target = SqliteUserRepository(store).get_or_create_by_telegram_id(42)

        callbacks.dispatch(_callback(f"admin:revoke:{target.user_id}:confirm"))

        assert delivered == [(42, "You no longer have access to this bot.")]

    def test_non_owner_callback_is_acknowledged_without_disclosure(self, tmp_path):
        _router, callbacks, client, _sent, _db, _access = _interactive_wire(tmp_path)

        callbacks.dispatch(_callback("admin:users", chat_id=999))

        assert client.edits == []
        assert client.answered[-1][1] == "Admin commands are owner-only."
