from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path


class Platform(Enum):
    BOOKING_COM = "booking_com"


class ProductType(Enum):
    HOTEL = "hotel"


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError(f"Money amount must be non-negative, got {self.amount}")
        if not re.match(r"^[A-Z]{3}$", self.currency):
            raise ValueError(f"Invalid ISO-4217 currency code: '{self.currency}'")

    @classmethod
    def of(cls, amount: str | Decimal, currency: str) -> Money:
        try:
            decimal_amount = Decimal(str(amount))
        except InvalidOperation:
            raise ValueError(f"Invalid monetary amount: '{amount}'")
        return cls(amount=decimal_amount, currency=currency.upper().strip())


@dataclass(frozen=True)
class StayDates:
    check_in: date
    check_out: date

    def __post_init__(self) -> None:
        if self.check_out <= self.check_in:
            raise ValueError(
                f"check_out ({self.check_out}) must be after check_in ({self.check_in})"
            )


@dataclass(frozen=True)
class ConfirmationId:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("ConfirmationId must be non-empty")

    @classmethod
    def of(cls, value: str) -> ConfirmationId:
        stripped = value.strip()
        if not stripped:
            raise ValueError("ConfirmationId must be non-empty")
        return cls(value=stripped)


@dataclass(frozen=True)
class Property:
    name: str
    booking_com_ref: str

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Property name must be non-empty")
        if not self.booking_com_ref or not self.booking_com_ref.strip():
            raise ValueError("Property booking_com_ref must be non-empty")


@dataclass(frozen=True)
class RoomType:
    label: str

    def __post_init__(self) -> None:
        if not self.label or not self.label.strip():
            raise ValueError("RoomType label must be non-empty")


@dataclass(frozen=True)
class RefundabilityPolicy:
    is_refundable: bool
    note: str
    deadline: date | None = None


_DURATION_RE = re.compile(r"^(\d+)(m|h|d)$")
_MIN_INTERVAL = timedelta(minutes=15)


def _parse_duration(s: str) -> timedelta:
    m = _DURATION_RE.match(s.strip())
    if not m:
        raise ValueError(f"Invalid interval format '{s}'. Use e.g. '6h', '30m', '1d'")
    n, unit = int(m.group(1)), m.group(2)
    if unit == "m":
        return timedelta(minutes=n)
    elif unit == "h":
        return timedelta(hours=n)
    else:
        return timedelta(days=n)


@dataclass(frozen=True)
class CheckInterval:
    duration: timedelta

    def __post_init__(self) -> None:
        if self.duration <= timedelta(0):
            raise ValueError("CheckInterval must be positive")
        if self.duration < _MIN_INTERVAL:
            raise ValueError(
                f"CheckInterval must be at least 15m to avoid abusive polling (got {self})"
            )

    @classmethod
    def parse(cls, s: str) -> CheckInterval:
        return cls(duration=_parse_duration(s))

    def __str__(self) -> str:
        total_seconds = int(self.duration.total_seconds())
        if total_seconds % 86400 == 0:
            return f"{total_seconds // 86400}d"
        elif total_seconds % 3600 == 0:
            return f"{total_seconds // 3600}h"
        else:
            return f"{total_seconds // 60}m"


@dataclass(frozen=True)
class DataDirectory:
    path: Path

    def __post_init__(self) -> None:
        if "://" in str(self.path):
            raise ValueError(f"DataDirectory must be a local path, not a URL: {self.path}")

    @classmethod
    def of(cls, path_str: str) -> DataDirectory:
        if "://" in path_str:
            raise ValueError(f"DataDirectory must be a local path, not a URL: {path_str}")
        resolved = Path(path_str).expanduser().resolve()
        return cls(path=resolved)


@dataclass(frozen=True)
class NotificationSettings:
    email: str | None = None
    telegram_chat_id: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
