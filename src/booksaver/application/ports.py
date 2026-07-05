from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from booksaver.domain.check_result import CheckResult
from booksaver.domain.models import Booking
from booksaver.domain.rebook import (
    ConfirmationAnswer,
    ConfirmationPrompt,
    RebookEvent,
    RebookSession,
)
from booksaver.domain.savings import SavingsOpportunity
from booksaver.domain.session import SessionState
from booksaver.domain.value_objects import ConfirmationId, Money, Platform


@runtime_checkable
class BookingRepository(Protocol):
    def add(self, booking: Booking) -> None: ...
    def get_by_id(self, booking_id: str) -> Booking | None: ...
    def get_by_confirmation(self, confirmation_id: ConfirmationId) -> Booking | None: ...
    def list_active(self) -> list[Booking]: ...
    def exists(self, confirmation_id: ConfirmationId) -> bool: ...


@runtime_checkable
class CheckHistoryRepository(Protocol):
    def add(self, result: CheckResult) -> None: ...
    def get_recent(self, booking_id: str, limit: int = 10) -> list[CheckResult]: ...
    def count_consecutive_failures(self, booking_id: str) -> int: ...


@runtime_checkable
class SessionRepository(Protocol):
    def load(self, platform: Platform) -> SessionState | None: ...
    def save(self, session: SessionState) -> None: ...


@dataclass(frozen=True)
class PageContent:
    url: str
    html: str
    text: str


@dataclass(frozen=True)
class ExtractionResult:
    price: Money | None
    is_refundable: bool | None
    cancellation_deadline_raw: str | None
    confidence: float  # 0.0 - 1.0; below threshold treated as failed extraction


@runtime_checkable
class BrowserSession(Protocol):
    def open_page(self, url: str) -> PageContent: ...
    def get_cookies(self) -> bytes: ...
    def restore_cookies(self, data: bytes) -> None: ...
    def is_authenticated(self) -> bool: ...


@runtime_checkable
class LLMExtractor(Protocol):
    def extract_price(self, page_text: str, booking: Booking) -> ExtractionResult: ...


@runtime_checkable
class Notifier(Protocol):
    @property
    def channel_name(self) -> str: ...
    def send(self, subject: str, body: str) -> None: ...


@runtime_checkable
class SavingsRepository(Protocol):
    def add(self, opportunity: SavingsOpportunity) -> None: ...
    def get(self, opportunity_id: str) -> SavingsOpportunity | None: ...
    def list_for_booking(self, booking_id: str) -> list[SavingsOpportunity]: ...
    def list_all(self) -> list[SavingsOpportunity]: ...
    def mark_notified(self, opportunity_id: str, at: datetime) -> None: ...


@runtime_checkable
class ConfirmationGate(Protocol):
    def ask(self, prompt: ConfirmationPrompt) -> ConfirmationAnswer: ...


@runtime_checkable
class RebookSessionRepository(Protocol):
    def add(self, session: RebookSession) -> None: ...
    def update(self, session: RebookSession) -> None: ...
    def get(self, session_id: str) -> RebookSession | None: ...


@runtime_checkable
class RebookEventRepository(Protocol):
    def append(self, event: RebookEvent) -> None: ...
    def list_for_session(self, session_id: str) -> list[RebookEvent]: ...


@runtime_checkable
class ConfigSource(Protocol):
    def read(self) -> dict[str, Any]: ...
