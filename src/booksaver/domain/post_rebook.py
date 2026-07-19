from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import BookSaverError
from .models import Booking
from .value_objects import ConfirmationId, Money


class HandoffOutcome(Enum):
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    UNREPORTED = "unreported"


class MonitoringDisposition(Enum):
    SOURCE_ARCHIVED = "source_archived"
    SOURCE_ALREADY_ARCHIVED = "source_already_archived"
    REPLACEMENT_ACTIVE = "replacement_active"
    REPLACEMENT_ALREADY_ACTIVE = "replacement_already_active"


class PostRebookRejection(Enum):
    ACCESS_LOST = "access_lost"
    STALE = "stale"
    CONFLICT = "conflict"


class PostRebookRejected(BookSaverError):
    def __init__(self, reason: PostRebookRejection) -> None:
        self.reason = reason
        super().__init__(f"Post-rebook monitoring reconciliation rejected: {reason.value}")


@dataclass(frozen=True)
class ReplacementFacts:
    confirmation_id: ConfirmationId
    property_ref: str
    actual_total: Money


@dataclass(frozen=True)
class PostRebookContext:
    user_id: int
    session_id: str
    opportunity_id: str
    source_booking: Booking
    cancellation_outcome: HandoffOutcome


@dataclass(frozen=True)
class PostRebookResult:
    disposition: MonitoringDisposition
    booking: Booking
