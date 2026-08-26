from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from booksaver.domain.account_sync import ReservationObservation
from booksaver.domain.agent import AgentAction, AgentTurnContext, CheckTrace, Observation
from booksaver.domain.browser_executor import (
    PriceExecutionRequest,
    PriceExecutionResult,
    SessionLeaseReference,
)
from booksaver.domain.browser_resilience import (
    DomStepId,
    PageStateResolution,
    PopupAdoptionResult,
)
from booksaver.domain.check_result import CheckResult
from booksaver.domain.inventory_executor import (
    InventoryExecutionRequest,
    InventoryExecutionResult,
)
from booksaver.domain.model_policy import EscalationTrigger
from booksaver.domain.models import Booking
from booksaver.domain.offer import OfferCandidate
from booksaver.domain.post_rebook import PostRebookContext, PostRebookResult, ReplacementFacts
from booksaver.domain.rebook import (
    ConfirmationAnswer,
    ConfirmationPrompt,
    RebookEvent,
    RebookSession,
)
from booksaver.domain.savings import SavingsOpportunity
from booksaver.domain.session import SessionState
from booksaver.domain.user import InviteCode, User, UserAccessState, UserRole
from booksaver.domain.value_objects import ConfirmationId, Money, Occupancy, Platform


@runtime_checkable
class BookingRepository(Protocol):
    def add(self, booking: Booking, user_id: int | None = None) -> None: ...
    def get_by_id(self, booking_id: str) -> Booking | None: ...
    def get_by_confirmation(self, confirmation_id: ConfirmationId) -> Booking | None: ...
    def list_active(self) -> list[Booking]: ...
    def list_active_for_user(self, user_id: int) -> list[Booking]: ...
    def list_all_for_user(self, user_id: int) -> list[Booking]: ...
    def get_owner_user_id(self, booking_id: str) -> int | None: ...
    def exists(self, confirmation_id: ConfirmationId) -> bool: ...
    def set_occupancy(self, booking_id: str, occupancy: Occupancy) -> None: ...
    def update(self, booking: Booking) -> None: ...
    def delete(self, booking_id: str) -> bool: ...


@runtime_checkable
class PostRebookRepository(Protocol):
    def archive_cancelled_source(self, context: PostRebookContext) -> PostRebookResult: ...
    def activate_replacement(
        self, context: PostRebookContext, facts: ReplacementFacts
    ) -> PostRebookResult: ...


@runtime_checkable
class UserRepository(Protocol):
    """Schema v7 (US-029). Exactly one OWNER row exists at all times."""

    def get_owner(self) -> User: ...
    def get_by_id(self, user_id: int) -> User | None: ...
    def get_by_telegram_id(self, telegram_user_id: int) -> User | None: ...
    def get_or_create_by_telegram_id(
        self, telegram_user_id: int, role: UserRole = UserRole.USER
    ) -> User: ...
    def list_all(self) -> list[User]: ...
    def list_active(self) -> list[User]: ...
    def set_access_state(self, user_id: int, access_state: UserAccessState) -> None: ...
    def link_telegram_id(self, user_id: int, telegram_user_id: int) -> None: ...
    def get_owner_of_booking(self, booking_id: str) -> User | None: ...
    def set_encrypted_key(self, user_id: int, encrypted_key: bytes | None) -> None: ...
    def purge(self, user_id: int) -> None: ...


@runtime_checkable
class InviteCodeRepository(Protocol):
    """Schema v8 (US-026). Single-use, owner-issued admission codes."""

    def issue(
        self, issued_by: int, expires_at: datetime | None = None
    ) -> InviteCode: ...
    def redeem(self, code: str, used_by: int, now: datetime) -> InviteCode | None: ...
    def get(self, code: str) -> InviteCode | None: ...


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


@dataclass(frozen=True)
class PageSnapshot:
    """What the journey (and, in bolt 007, the agent) sees of the current page."""

    url: str
    title: str
    text: str


@runtime_checkable
class InteractiveBrowser(Protocol):
    """Interactive superset of BrowserSession for the search journey (ADR-013).

    Scripted steps drive it with CSS selectors; bolt 007's agent drives the same
    port. All actions raise on failure (missing selector, timeout) — the journey
    turns exceptions into StepOutcome failures.
    """

    def goto(self, url: str) -> None: ...
    def click(self, selector: str) -> None: ...
    def click_first_visible(self, selector: str) -> None: ...
    def fill(self, selector: str, text: str) -> None: ...
    def press(self, selector: str, key: str) -> None: ...
    def wait_for(self, selector: str, timeout_ms: int | None = None) -> None: ...
    def exists(self, selector: str) -> bool: ...
    def query_text(self, selector: str) -> list[str]: ...
    def query_attr(self, selector: str, attr: str) -> list[str]: ...
    def snapshot(self) -> PageSnapshot: ...
    # Agent surface (bolt 007): enumerated-element observation + guarded actions
    def observe(self) -> Observation: ...
    def act(self, action: AgentAction) -> None: ...
    def screenshot(self) -> bytes: ...
    def get_cookies(self) -> bytes: ...
    def restore_cookies(self, data: bytes) -> None: ...
    def verify_authenticated_account(self) -> bool: ...
    def is_authenticated(self) -> bool: ...


@runtime_checkable
class SessionRestoreTarget(Protocol):
    """Code-owned local browser bootstrap that can receive opaque session bytes."""

    def restore_session(self, data: bytes) -> None: ...


@runtime_checkable
class VerifiedSessionRefreshSource(Protocol):
    """Local browser capability used only after code-owned authentication verification."""

    def verify_authenticated_account(self) -> bool: ...
    def capture_session(self) -> bytes: ...


@runtime_checkable
class SessionLeaseBroker(Protocol):
    """Keeps session material outside executor requests and provider-facing objects."""

    def restore_into(
        self, reference: SessionLeaseReference, target: SessionRestoreTarget
    ) -> None: ...
    def capture_verified_refresh(
        self,
        reference: SessionLeaseReference,
        source: VerifiedSessionRefreshSource,
    ) -> bool: ...
    def take_verified_refresh(self, reference: SessionLeaseReference) -> bytes | None: ...
    def close(self, reference: SessionLeaseReference) -> None: ...


@runtime_checkable
class PriceBrowserExecutor(Protocol):
    """Replaceable, untrusted perception/navigation executor (ADR-036)."""

    def execute(self, request: PriceExecutionRequest) -> PriceExecutionResult: ...


@runtime_checkable
class InventoryBrowserExecutor(Protocol):
    """Replaceable, untrusted positive-only account perception executor (ADR-039)."""

    def execute(self, request: InventoryExecutionRequest) -> InventoryExecutionResult: ...


@runtime_checkable
class PopupAdoptingBrowser(Protocol):
    """Optional guarded capability for adopting a popup opened by the last action.

    The caller supplies only the registered DOM step.  The adapter owns page
    identity, destination inspection, and control transfer; a model can never
    select a page or URL.
    """

    def adopt_read_only_popup(self, step_id: DomStepId) -> PopupAdoptionResult: ...


@runtime_checkable
class AgentBrain(Protocol):
    """One LLM decision per agent turn (ADR-016)."""

    def decide(self, context: AgentTurnContext) -> AgentAction: ...


@runtime_checkable
class EscalatingAgentBrain(Protocol):
    """Optional single-turn Opus capability after code-measured quality failure."""

    def decide_with_escalation(
        self, context: AgentTurnContext, trigger: EscalationTrigger
    ) -> AgentAction: ...


@runtime_checkable
class RegisteredPageStateResolver(Protocol):
    """Resolve one registered current-page state without browser authority."""

    def resolve(
        self, step_id: DomStepId, observation: Observation
    ) -> PageStateResolution: ...


@runtime_checkable
class CheckTraceRepository(Protocol):
    def add(self, trace: CheckTrace) -> None: ...
    def get(self, check_id: str) -> CheckTrace | None: ...


@runtime_checkable
class LLMExtractor(Protocol):
    def extract_price(self, page_text: str, booking: Booking) -> ExtractionResult: ...
    def extract_offers(self, page_text: str, booking: Booking) -> list[OfferCandidate]: ...


@runtime_checkable
class InventoryInterpreter(Protocol):
    """Positive-only reservation interpretation; never conveys completeness."""

    def interpret(
        self, page_text: str, source_url: str
    ) -> tuple[ReservationObservation, ...]: ...


@runtime_checkable
class Notifier(Protocol):
    @property
    def channel_name(self) -> str: ...
    def send(self, subject: str, body: str) -> None: ...


@runtime_checkable
class SavingsRepository(Protocol):
    def add(self, opportunity: SavingsOpportunity) -> None: ...
    def get(self, opportunity_id: str) -> SavingsOpportunity | None: ...
    def get_current_for_booking(self, booking_id: str) -> SavingsOpportunity | None: ...
    def list_for_booking(self, booking_id: str) -> list[SavingsOpportunity]: ...
    def list_all(self) -> list[SavingsOpportunity]: ...
    def list_all_for_user(self, user_id: int) -> list[SavingsOpportunity]: ...
    def list_current_for_user(self, user_id: int) -> list[SavingsOpportunity]: ...
    def mark_notified(self, opportunity_id: str, at: datetime) -> None: ...


@runtime_checkable
class ConfirmationGate(Protocol):
    def ask(self, prompt: ConfirmationPrompt) -> ConfirmationAnswer: ...


@runtime_checkable
class RebookSessionRepository(Protocol):
    def add(self, session: RebookSession) -> None: ...
    def add_if_opportunity_current(self, session: RebookSession) -> bool: ...
    def update(self, session: RebookSession) -> None: ...
    def get(self, session_id: str) -> RebookSession | None: ...


@runtime_checkable
class RebookEventRepository(Protocol):
    def append(self, event: RebookEvent) -> None: ...
    def list_for_session(self, session_id: str) -> list[RebookEvent]: ...


@runtime_checkable
class ConfigSource(Protocol):
    def read(self) -> dict[str, Any]: ...


@runtime_checkable
class LLMClientFactory(Protocol):
    """Per-user LLM client resolution seam (US-029).

    Today every implementation resolves the single owner env-var key for
    every booking, matching pre-multi-user behavior exactly. The seam exists
    so a later slice (US-027, `/setkey`) can resolve booking -> owning user
    -> decrypted personal key (falling back to the owner key under per-user
    caps) without changing any call site.
    """

    def for_booking(self, booking: Booking | None) -> LLMExtractor | None: ...
    def agent_brain_for_booking(self, booking: Booking | None) -> AgentBrain | None: ...
    def agent_brain_for_user(
        self, user_id: int, role: str = "navigation_agent"
    ) -> AgentBrain | None: ...
    def inventory_interpreter_for_user(
        self, user_id: int, role: str = "inventory_interpreter"
    ) -> InventoryInterpreter | None: ...
