from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from booksaver.domain.agent import CheckTrace
from booksaver.domain.check_result import CheckResult
from booksaver.domain.models import Booking
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


def make_booking(
    booking_id: str = "b-1",
    ref: str = "https://example.com/hotel",
    occupancy: Occupancy | None = Occupancy(adults=2),
) -> Booking:
    return Booking(
        booking_id=booking_id,
        platform=Platform.BOOKING_COM,
        product_type=ProductType.HOTEL,
        confirmation_id=ConfirmationId(f"CONF-{booking_id}"),
        property=Property(name="Hotel Test", booking_com_ref=ref),
        stay_dates=StayDates(check_in=date(2026, 9, 1), check_out=date(2026, 9, 5)),
        room_type=RoomType(label="Standard Double"),
        baseline_price=Money(amount=Decimal("400.00"), currency="EUR"),
        refundability=RefundabilityPolicy(is_refundable=True, note="Free cancellation"),
        registered_at=datetime.now(UTC),
        occupancy=occupancy,
    )


class FakeBookingRepository:
    def __init__(self, bookings: list[Booking] | None = None) -> None:
        self.bookings = bookings or []
        self.owners: dict[str, int] = {}

    def get_by_id(self, booking_id: str) -> Booking | None:
        return next((b for b in self.bookings if b.booking_id == booking_id), None)

    def get_owner_user_id(self, booking_id: str) -> int | None:
        return self.owners.get(booking_id)


class FakeCheckHistoryRepository:
    def __init__(self) -> None:
        self.results: list[CheckResult] = []

    def add(self, result: CheckResult) -> None:
        self.results.append(result)

    def get_recent(self, booking_id: str, limit: int = 10) -> list[CheckResult]:
        matching = [r for r in self.results if r.booking_id == booking_id]
        return list(reversed(matching))[:limit]

    def count_consecutive_failures(self, booking_id: str) -> int:
        matching = [r for r in self.results if r.booking_id == booking_id]
        count = 0
        for result in reversed(matching):
            if result.outcome.value != "failure":
                break
            count += 1
        return count


class FakeCheckTraceRepository:
    def __init__(self) -> None:
        self.traces: list[CheckTrace] = []

    def add(self, trace: CheckTrace) -> None:
        self.traces.append(trace)

    def get(self, check_id: str) -> CheckTrace | None:
        return next((t for t in self.traces if t.check_id == check_id), None)
