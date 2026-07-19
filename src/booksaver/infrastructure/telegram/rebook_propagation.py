from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from booksaver.application.post_rebook import (
    activate_replacement,
    archive_cancelled_source,
    canonicalize_booking_property_ref,
    replacement_facts,
)
from booksaver.domain.post_rebook import (
    HandoffOutcome,
    PostRebookContext,
    PostRebookRejected,
    PostRebookRejection,
)
from booksaver.domain.value_objects import ConfirmationId, Money
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteBookingRepository,
    SqliteStore,
    SqliteUserRepository,
)

from .client import TelegramBotClient
from .dialogs import DialogAborted, DialogDefinition, DialogManager, DialogStep

ActiveUserPredicate = Callable[[], bool]


def _safe_disposition(context: PostRebookContext) -> str:
    if context.cancellation_outcome is HandoffOutcome.COMPLETED:
        return (
            "The old reservation remains archived, so BookSaver is not monitoring a "
            "reservation for this stay. Use /register if you need to add it manually."
        )
    return "The original reservation remains monitored with its existing baseline."


def _rejection_message(error: PostRebookRejected, context: PostRebookContext) -> str:
    if error.reason is PostRebookRejection.ACCESS_LOST:
        return "You no longer have access to this bot. No monitoring change was made."
    if error.reason is PostRebookRejection.CONFLICT:
        return (
            "I couldn't safely update monitoring with those details. Check the confirmation "
            "and try again; no replacement data was saved. "
            + _safe_disposition(context)
        )
    return (
        "The monitored booking changed while this rebook was in progress, so I did not apply "
        "the replacement details. Review /bookings before trying again."
    )


def archive_reported_cancellation(db_path: Path, context: PostRebookContext) -> bool:
    """Persist the cancellation fail-safe. False means access disappeared."""
    try:
        with SqliteStore(db_path) as store:
            archive_cancelled_source(SqliteBookingRepository(store), context)
    except PostRebookRejected as error:
        if error.reason is PostRebookRejection.ACCESS_LOST:
            return False
        raise
    return True


def build_replacement_dialog(
    db_path: Path,
    context: PostRebookContext,
    expected_telegram_user_id: int,
) -> DialogDefinition:
    source = context.source_booking

    def validate_confirmation(text: str, _answers: dict[str, str]) -> str | None:
        try:
            ConfirmationId.of(text)
        except ValueError as error:
            return str(error)
        return None

    def validate_ref(text: str, _answers: dict[str, str]) -> str | None:
        try:
            canonicalize_booking_property_ref(text, source.property.booking_com_ref)
        except ValueError as error:
            return str(error)
        return None

    def validate_total(text: str, _answers: dict[str, str]) -> str | None:
        parts = text.strip().split()
        if len(parts) != 2:
            return 'Enter the actual all-in total as "amount CURRENCY", e.g. "315.42 USD".'
        try:
            Money.of(parts[0], parts[1])
        except ValueError as error:
            return str(error)
        return None

    def ref_prompt(answers: dict[str, str]) -> str:
        return (
            f"Saved confirmation: {answers['confirmation_id'].strip()}\n\n"
            "Paste the Booking.com property URL for the replacement. It must be the same "
            "property; tracking and session parameters will be removed."
        )

    def total_prompt(answers: dict[str, str]) -> str:
        canonical = canonicalize_booking_property_ref(
            answers["property_ref"], source.property.booking_com_ref
        )
        return (
            f"Saved Booking.com property: {canonical}\n\n"
            "What was the ACTUAL final all-in total at checkout? Reply as amount CURRENCY, "
            'for example "315.42 USD". I will not use the earlier detected offer price.'
        )

    def summary_prompt(answers: dict[str, str]) -> str:
        facts = replacement_facts(
            answers["confirmation_id"],
            answers["property_ref"],
            answers["actual_total"],
            source,
        )
        return (
            f"Saved actual total: {facts.actual_total.amount} {facts.actual_total.currency}\n\n"
            "Confirm the new monitored reservation:\n"
            f"Property: {source.property.name}\n"
            f"Stay: {source.stay_dates.check_in} -> {source.stay_dates.check_out}\n"
            f"Room: {source.room_type.label}\n"
            f"Confirmation: {facts.confirmation_id.value}\n"
            f"Booking.com URL: {facts.property_ref}\n"
            f"Actual all-in baseline: {facts.actual_total.amount} {facts.actual_total.currency}\n\n"
            "Reply yes to replace the monitored baseline, or no to leave the current safe state."
        )

    def validate_final(text: str, _answers: dict[str, str]) -> str | None:
        normalized = text.strip().lower()
        if normalized in {"no", "n"}:
            raise DialogAborted(
                "Replacement details cancelled. No replacement was activated. "
                + _safe_disposition(context)
            )
        if normalized not in {"yes", "y"}:
            return "Reply yes to update monitoring, or no to cancel these replacement details."
        return None

    def on_complete(telegram_user_id: int, _chat_id: int, answers: dict[str, str]) -> str:
        if telegram_user_id != expected_telegram_user_id:
            return "I couldn't safely update monitoring. No replacement data was saved."
        facts = replacement_facts(
            answers["confirmation_id"],
            answers["property_ref"],
            answers["actual_total"],
            source,
        )
        try:
            with SqliteStore(db_path) as store:
                user = SqliteUserRepository(store).get_by_telegram_id(telegram_user_id)
                if user is None or user.user_id != context.user_id or not user.is_active:
                    raise PostRebookRejected(PostRebookRejection.ACCESS_LOST)
                result = activate_replacement(
                    SqliteBookingRepository(store), context, facts
                )
        except PostRebookRejected as error:
            return _rejection_message(error, context)

        warning = ""
        if context.cancellation_outcome is HandoffOutcome.ABANDONED:
            warning = (
                "\n\nImportant: you reported that the old reservation was not cancelled. "
                "BookSaver now monitors the replacement, but you may still hold both bookings."
            )
        elif context.cancellation_outcome is HandoffOutcome.UNREPORTED:
            warning = (
                "\n\nImportant: the old cancellation was not confirmed. BookSaver now monitors "
                "the replacement; verify whether the old reservation still needs cancellation."
            )
        return (
            "Replacement monitoring updated.\n"
            f"Property: {result.booking.property.name}\n"
            f"Confirmation: {result.booking.confirmation_id.value}\n"
            f"New baseline: {result.booking.baseline_price.amount} "
            f"{result.booking.baseline_price.currency}\n"
            "Future scheduled checks and /checknow will use these actual replacement details."
            + warning
        )

    archived = context.cancellation_outcome is HandoffOutcome.COMPLETED
    return DialogDefinition(
        name=f"post-rebook:{'archived' if archived else 'original-active'}",
        steps=(
            DialogStep(
                key="confirmation_id",
                prompt=(
                    "You reported the replacement booking completed. Enter the NEW Booking.com "
                    "confirmation ID. The detected offer price will not be used as your baseline."
                ),
                validate=validate_confirmation,
            ),
            DialogStep(key="property_ref", prompt=ref_prompt, validate=validate_ref),
            DialogStep(key="actual_total", prompt=total_prompt, validate=validate_total),
            DialogStep(key="final_confirm", prompt=summary_prompt, validate=validate_final),
        ),
        on_complete=on_complete,
    )


def reconcile_reported_outcomes(
    *,
    client: TelegramBotClient,
    dialog_manager: DialogManager,
    db_path: Path,
    chat_id: int,
    telegram_user_id: int,
    context: PostRebookContext,
    replacement_outcome: HandoffOutcome,
    is_active: ActiveUserPredicate,
) -> None:
    if not is_active():
        return

    if context.cancellation_outcome is HandoffOutcome.COMPLETED:
        try:
            if not archive_reported_cancellation(db_path, context):
                return
        except PostRebookRejected:
            if is_active():
                client.send_message(
                    chat_id,
                    "I couldn't safely reconcile the reported cancellation because the "
                    "monitored booking changed. Review /bookings before continuing.",
                )
            return

    if not is_active():
        return

    if replacement_outcome is HandoffOutcome.COMPLETED:
        prompt = dialog_manager.start(
            chat_id,
            build_replacement_dialog(db_path, context, telegram_user_id),
        )
        client.send_message(chat_id, prompt)
        return

    if context.cancellation_outcome is HandoffOutcome.COMPLETED:
        client.send_message(
            chat_id,
            f"Recorded: old reservation cancelled; replacement {replacement_outcome.value}. "
            "BookSaver is not monitoring a reservation for this stay. Use /register if you "
            "completed a replacement later.",
        )
        return

    client.send_message(
        chat_id,
        f"Recorded: old cancellation {context.cancellation_outcome.value}; replacement "
        f"{replacement_outcome.value}. The original reservation remains monitored with its "
        "existing baseline.",
    )
