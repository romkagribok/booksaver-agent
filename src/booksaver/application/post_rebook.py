from __future__ import annotations

from dataclasses import replace
from urllib.parse import unquote, urlsplit, urlunsplit

from booksaver.domain.models import Booking, BookingStatus
from booksaver.domain.post_rebook import (
    PostRebookContext,
    PostRebookResult,
    ReplacementFacts,
)
from booksaver.domain.value_objects import ConfirmationId, Money, Property

from .ports import PostRebookRepository


def _property_path(value: str) -> str | None:
    parsed = urlsplit(value.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    path = parsed.path.rstrip("/")
    if parsed.scheme.lower() != "https":
        return None
    if host != "booking.com" and not host.endswith(".booking.com"):
        return None
    if not unquote(path).lower().startswith("/hotel/"):
        return None
    return path


def canonicalize_booking_property_ref(value: str, source_ref: str) -> str:
    """Validate a Booking.com property URL and remove tracking/session data."""
    path = _property_path(value)
    if path is None:
        raise ValueError("Enter an HTTPS Booking.com property URL containing /hotel/.")

    source_path = _property_path(source_ref)
    if source_path is not None and unquote(source_path).casefold() != unquote(path).casefold():
        raise ValueError("That URL is for a different Booking.com property.")

    return urlunsplit(("https", "www.booking.com", path, "", ""))


def replacement_facts(
    confirmation: str,
    property_ref: str,
    actual_total: str,
    source_booking: Booking,
) -> ReplacementFacts:
    parts = actual_total.strip().split()
    if len(parts) != 2:
        raise ValueError('Enter the actual all-in total as "amount CURRENCY", e.g. "315.42 USD".')
    amount, currency = parts
    return ReplacementFacts(
        confirmation_id=ConfirmationId.of(confirmation),
        property_ref=canonicalize_booking_property_ref(
            property_ref, source_booking.property.booking_com_ref
        ),
        actual_total=Money.of(amount, currency),
    )


def replacement_booking(source: Booking, facts: ReplacementFacts) -> Booking:
    return replace(
        source,
        confirmation_id=facts.confirmation_id,
        property=Property(
            name=source.property.name,
            booking_com_ref=facts.property_ref,
        ),
        baseline_price=facts.actual_total,
        status=BookingStatus.ACTIVE,
    )


def archive_cancelled_source(
    repo: PostRebookRepository, context: PostRebookContext
) -> PostRebookResult:
    return repo.archive_cancelled_source(context)


def activate_replacement(
    repo: PostRebookRepository,
    context: PostRebookContext,
    facts: ReplacementFacts,
) -> PostRebookResult:
    return repo.activate_replacement(context, facts)
