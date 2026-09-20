"""Local Browser Use OSS executor for guarded Booking.com price perception.

Browser Use is an untrusted navigation/perception harness.  BookSaver restores the owner-bound
session, constructs the trusted search URL, guards every physical action, meters provider use, and
maps typed submissions into the existing provider-neutral price contract.  Validation,
equivalence, savings decisions, persistence, and notifications remain outside this adapter.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, get_args
from urllib.parse import urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from booksaver.application.async_runner import AsyncLoopRunner
from booksaver.application.browser_executor import ExecutionMeter, InMemorySessionLeaseBroker
from booksaver.application.model_policy import BrowserJobCostBudget
from booksaver.application.ports import SessionRestoreTarget
from booksaver.domain.browser_executor import (
    EvidenceCompleteness,
    ExecutorSafetyViolation,
    ObservationSource,
    PriceExecutionRequest,
    PriceExecutionResult,
    PriceExecutionStatus,
    RedactedProvenance,
)
from booksaver.domain.mobile_web import MobileWebSettings
from booksaver.domain.model_policy import ModelStopReason
from booksaver.infrastructure.browser.agentic_executor import (
    TypedObservation,
    _map_extracted_observation,
    _trusted_input_values,
    build_trusted_search_url,
)
from booksaver.infrastructure.browser.browser_use_normalization import (
    normalize_provider_scalar,
    provider_tri_state,
)
from booksaver.infrastructure.browser.browser_use_runtime import (
    ALLOWED_DOMAINS,
    STOCK_ACTIONS,
    UNSAFE_LABEL_TERMS,
    BrowserUseActionGuard,
    BrowserUseCostStop,
    BrowserUseRuntimeFailure,
    BrowserUseSessionHost,
    BrowserUseSessionStatus,
    GuardedClick,
    GuardedKey,
    GuardedScroll,
    GuardedVisualClick,
    GuardedWait,
    agent_history_diagnostic,
    browser_use_screenshot_available,
    budgeted_model_type,
    continued_action_result,
    coordinate_chain_click_decision,
    coordinate_hit_test_chain,
    node_chain_click_decision,
    remember_visible_semantic_state,
    same_tab_click_destination,
    viewport_coordinates,
)

logger = logging.getLogger(__name__)

_PROMPT_VERSION = "browser-use-price-v1"
_EXPECTED_ACTIONS = frozenset(
    {
        "guarded_click",
        "guarded_visual_click",
        "guarded_scroll",
        "guarded_key",
        "guarded_type",
        "guarded_wait",
        "guarded_back",
        "submit_price_observation",
        "done",
    }
)
_SENSITIVE_INPUT_TERMS = re.compile(
    r"(?:^|[^a-z0-9])(?:user(?:name)?|e-?mail|phone|pass(?:word)?|login|signin|sign-in|"
    r"auth|otp|mfa|captcha|security|card|cvv|payment)(?:[^a-z0-9]|$)",
    re.IGNORECASE,
)


class BrowserUsePriceQuerySubmission(BaseModel):
    """Visible query facts only; authentication and current URL remain code-owned."""

    model_config = ConfigDict(extra="forbid")
    property_name: str
    check_in: str
    check_out: str
    adults: str
    children: str
    rooms: str
    currency: str
    genius: Literal["true", "false", "unknown"]
    completeness: Literal["complete", "incomplete", "conflicting"]

    @field_validator(
        "property_name",
        "check_in",
        "check_out",
        "adults",
        "children",
        "rooms",
        "currency",
        "genius",
        "completeness",
        mode="before",
    )
    @classmethod
    def normalize_provider_scalar(cls, value: object) -> object:
        return normalize_provider_scalar(value)


class BrowserUsePriceOfferSubmission(BaseModel):
    """One visibly supported offer; BookSaver validates every evidence field later."""

    model_config = ConfigDict(extra="forbid")
    room_label: str
    total: str
    currency: str
    all_in: Literal["explicit", "unknown", "conflicting"]
    refundability: Literal[
        "explicit_refundable",
        "explicit_nonrefundable",
        "unknown",
        "conflicting",
    ]
    refundability_text: str
    completeness: Literal["complete", "incomplete", "conflicting"]

    @field_validator(
        "room_label",
        "total",
        "currency",
        "all_in",
        "refundability",
        "refundability_text",
        "completeness",
        mode="before",
    )
    @classmethod
    def normalize_provider_scalar(cls, value: object) -> object:
        return normalize_provider_scalar(value)


class BrowserUsePriceObservationSubmission(BrowserUsePriceQuerySubmission):
    """One complete query plus all visibly supported offers in a single terminal action."""

    offers: list[BrowserUsePriceOfferSubmission] = Field(min_length=1, max_length=100)


PriceTerminalStatus = Literal[
    "no_valid_observation", "session_unavailable", "signed_out", "mfa_required",
    "captcha", "bot_wall", "unavailable", "unsafe_action", "provider_failure",
    "budget_exhausted", "timeout",
]
_TERMINAL_STATUS_CHOICES = ", ".join(get_args(PriceTerminalStatus))


class BrowserUsePriceTerminalSubmission(BaseModel):
    """Exact forced-final contract for Browser Use 0.11.13."""

    model_config = ConfigDict(extra="forbid")
    success: bool
    status: PriceTerminalStatus


class GuardedTrustedType(BaseModel):
    """One indexed input plus an exact code-owned request value."""

    model_config = ConfigDict(extra="forbid")
    index: int = Field(ge=1, le=100_000)
    value: str = Field(min_length=1, max_length=500)


@dataclass(slots=True)
class _PriceEpisodeState:
    query: BrowserUsePriceQuerySubmission | None = None
    property_reference: str | None = None
    offers: list[BrowserUsePriceOfferSubmission] = field(default_factory=list)
    observation: TypedObservation | None = None
    terminal: PriceExecutionStatus | None = None
    safety_violations: set[ExecutorSafetyViolation] = field(default_factory=set)
    refreshed_session: bytes | None = field(default=None, repr=False)
    visible_dom_snapshots: list[str] = field(default_factory=list, repr=False)


@dataclass(frozen=True, slots=True)
class BrowserUsePriceRuntimeResult:
    status: PriceExecutionStatus
    observation: TypedObservation | None = None
    refreshed_session: bytes | None = field(default=None, repr=False)
    safety_violations: frozenset[ExecutorSafetyViolation] = frozenset()


class BrowserUsePriceRuntimePort(SessionRestoreTarget, Protocol):
    async def execute(
        self,
        request: PriceExecutionRequest,
        *,
        api_key: str,
        budget: BrowserJobCostBudget,
        meter: ExecutionMeter,
    ) -> BrowserUsePriceRuntimeResult: ...

    async def close(self) -> None: ...


def _terminal_status(raw: object) -> PriceExecutionStatus:
    try:
        status = PriceExecutionStatus(str(raw).strip().casefold())
    except ValueError as exc:
        raise ValueError("unsupported Browser Use price terminal") from exc
    if status is PriceExecutionStatus.OBSERVED:
        raise ValueError("terminal status cannot claim an observation")
    return status


def _tri_state(raw: object) -> bool | None:
    return provider_tri_state(raw)


def _trusted_input_node_allowed(
    guard: BrowserUseActionGuard,
    *,
    node: object,
    current_url: str,
    active_target_id: str | None,
) -> bool:
    """Guard an indexed text field without depending on Booking.com selectors."""

    if not guard.observable_url(current_url):
        return False
    if getattr(node, "target_id", active_target_id) != active_target_id:
        return False
    if getattr(node, "is_visible", True) is not True:
        return False
    node_name = str(getattr(node, "node_name", "")).strip().casefold()
    if node_name not in {"input", "textarea"}:
        return False
    attributes = getattr(node, "attributes", {}) or {}
    if not isinstance(attributes, Mapping) or len(attributes) > 50:
        return False
    normalized: dict[str, str] = {}
    for key, value in attributes.items():
        normalized_key = str(key).casefold()
        normalized_value = str(value)
        if len(normalized_key) > 100 or len(normalized_value) > 1_000:
            return False
        normalized[normalized_key] = normalized_value
    input_type = normalized.get("type", "text").casefold()
    if input_type not in {"text", "search", "date", "number"}:
        return False
    if any(
        key.startswith("on")
        or key in {"download", "formaction", "contenteditable"}
        for key in normalized
    ):
        return False
    label = " ".join(
        (
            str(getattr(node, "get_meaningful_text_for_llm", lambda: "")()),
            normalized.get("aria-label", ""),
            normalized.get("placeholder", ""),
            normalized.get("name", ""),
            normalized.get("id", ""),
            normalized.get("autocomplete", ""),
        )
    )[:4_000]
    return (
        UNSAFE_LABEL_TERMS.search(label) is None
        and _SENSITIVE_INPUT_TERMS.search(label) is None
    )


def _observation_from_state(state: _PriceEpisodeState) -> TypedObservation:
    if state.query is None or state.property_reference is None or not state.offers:
        raise ValueError("price observation is incomplete")
    query = state.query
    parsed_reference = urlsplit(state.property_reference)
    canonical_reference = (
        f"{parsed_reference.scheme}://{parsed_reference.netloc}{parsed_reference.path}"
    )
    return _map_extracted_observation(
        {
            "property_name": query.property_name,
            "property_reference": canonical_reference,
            "check_in": query.check_in,
            "check_out": query.check_out,
            "adults": query.adults,
            "children": query.children,
            "rooms": query.rooms,
            "currency": query.currency,
            # Authentication was independently proved before Browser Use saw the price page.
            "authenticated": True,
            "genius": _tri_state(query.genius),
            "completeness": query.completeness,
            "offers": [offer.model_dump() for offer in state.offers],
        }
    )


def _typed_observation_error_code(exc: ValueError) -> str:
    """Map content-bearing validation errors to fixed, privacy-safe diagnostics."""

    cause = exc.__cause__
    message = str(cause).casefold() if cause is not None else ""
    if "property_reference" in message:
        return "property_reference"
    if "property_name" in message:
        return "property_name"
    if "isoformat" in message or "check_out" in message:
        return "stay_dates"
    if "occupancy" in message or "invalid literal for int" in message:
        return "occupancy"
    if "currency" in message:
        return "currency"
    if "allinevidence" in message:
        return "all_in"
    if "refundabilityevidence" in message:
        return "refundability"
    if "evidencecompleteness" in message:
        return "completeness"
    if "monetary amount" in message or "offer total" in message:
        return "total"
    if "room_label" in message:
        return "room_label"
    if "refundability_text" in message:
        return "refundability_text"
    return "unknown"


def _price_agent_task(request: PriceExecutionRequest) -> str:
    query = request.query
    return (
        "Read the currently open Booking.com results for exactly this trusted query: "
        f"property={query.property_name!r}; check-in={query.stay_dates.check_in.isoformat()}; "
        f"check-out={query.stay_dates.check_out.isoformat()}; adults={query.occupancy.adults}; "
        f"children={query.occupancy.children}; rooms={query.occupancy.rooms}; "
        f"currency={query.currency}. This is read-only. Never sign in, type credentials, solve "
        "MFA or captcha, reserve, book, pay, cancel, modify, upload, download, or leave "
        "Booking.com. Inspect the intended property and its current bookable room/rate table. "
        "The top-level completeness describes ONLY the visible query: property, stay dates, "
        "adults, children, rooms, and currency. Set it to complete only when those query facts "
        "are explicit. Genius may be unknown. Each offer has its own independent completeness, "
        "all_in, and refundability. Call submit_price_observation with the complete query "
        "and visible room/rate offers "
        "even when some offers are incomplete, unknown, or nonrefundable; these do not make "
        "the query incomplete. Use the all-in total for the whole stay when explicit; otherwise "
        "retain the displayed whole-stay total and mark all_in=unknown. Write total as a plain "
        "decimal with no currency symbol or thousands separator. Do not fabricate missing totals. "
        "Mark all_in=explicit only when the displayed total explicitly includes taxes and fees. "
        "Mark refundability=explicit_refundable only when visible text explicitly says the rate "
        "is refundable/free-cancellation and copy that text. When no cancellation text is visible, "
        "use refundability=unknown and refundability_text=unknown. Never infer missing facts. The "
        "observation submission completes the job; use done(success=false, status=<reason>) only "
        "when the query facts or usable visible offer values cannot be obtained. "
        "Allowed status values: "
        f"{_TERMINAL_STATUS_CHOICES}. Use no_valid_observation for missing or ambiguous "
        "query evidence. Never change a completeness value just to pass validation. "
        "BookSaver filters each offer and decides equivalence."
    )


def _price_entry_url(request: PriceExecutionRequest) -> tuple[str, str]:
    """Prefer a trusted canonical property page; retain name-only search compatibility."""

    parsed = urlsplit(request.query.property_reference.strip())
    if parsed.scheme.casefold() == "https" and parsed.hostname:
        params = {
            "checkin": request.query.stay_dates.check_in.isoformat(),
            "checkout": request.query.stay_dates.check_out.isoformat(),
            "group_adults": str(request.query.occupancy.adults),
            "group_children": str(request.query.occupancy.children),
            "no_rooms": str(request.query.occupancy.rooms),
            "selected_currency": request.query.currency,
        }
        candidate = urlunsplit(
            (
                "https",
                parsed.netloc,
                parsed.path,
                urlencode(params),
                "",
            )
        )
        if BrowserUseActionGuard.observable_url(candidate):
            return candidate, "property"
    return build_trusted_search_url(request), "search"


class LocalBrowserUsePriceRuntime:
    """Hardened Browser Use classic-agent episode for one exact price query."""

    def __init__(
        self,
        mobile_settings: MobileWebSettings | None = None,
        *,
        guard: BrowserUseActionGuard | None = None,
    ) -> None:
        self._guard = guard or BrowserUseActionGuard()
        self._host = BrowserUseSessionHost(mobile_settings)
        self._price_state = _PriceEpisodeState()

    @property
    def failure_stage(self) -> str:
        return self._host.failure_stage

    def restore_session(self, data: bytes) -> None:
        self._host.restore_session(data)

    async def execute(
        self,
        request: PriceExecutionRequest,
        *,
        api_key: str,
        budget: BrowserJobCostBudget,
        meter: ExecutionMeter,
    ) -> BrowserUsePriceRuntimeResult:
        hosted = await self._host.start()
        session = hosted.browser
        viewport = hosted.viewport
        file_system_dir = hosted.file_system_dir
        try:
            from browser_use import ActionResult, Agent, ChatAnthropic, Tools
            from browser_use.browser.events import (
                ClickCoordinateEvent,
                ClickElementEvent,
                GoBackEvent,
                ScrollEvent,
                SendKeysEvent,
                TypeTextEvent,
                WaitEvent,
            )
        except ImportError as exc:
            raise RuntimeError("Browser Use 0.11.13 runtime is not installed") from exc

        self._host.failure_stage = "authentication_probe"
        authentication_terminal = await self._host.verify_authentication(request, session)
        if authentication_terminal is not None:
            return BrowserUsePriceRuntimeResult(
                PriceExecutionStatus.TIMEOUT
                if authentication_terminal is BrowserUseSessionStatus.TIMEOUT
                else PriceExecutionStatus.SIGNED_OUT
                if authentication_terminal is BrowserUseSessionStatus.SIGNED_OUT
                else PriceExecutionStatus.PROVIDER_FAILURE
            )
        self._price_state.refreshed_session = self._host.verified_mobile_session

        self._host.failure_stage = "price_navigation"
        meter.record_action()
        entry_destination, entry_kind = _price_entry_url(request)
        await session.navigate_to(entry_destination, new_tab=False)
        await asyncio.sleep(0.5)
        entry_url = await session.get_current_page_url()
        entry_rejection = self._guard.observable_url_rejection_reason(entry_url)
        target_count = len(session.get_page_targets())
        if entry_rejection is not None or target_count != 1:
            logger.warning(
                "Browser Use price entry rejected execution_id=%s reason=%s target_count=%s",
                request.execution_id,
                entry_rejection or "target_count",
                target_count,
            )
            return self._unsafe_result(non_allowlisted=True)

        semantic_ready = False
        for attempt in range(30):
            semantic_ready = await remember_visible_semantic_state(
                session,
                self._price_state.visible_dom_snapshots,
                log_failure=attempt == 0,
            )
            if semantic_ready:
                break
            await asyncio.sleep(0.5)
        screenshot_ready = await browser_use_screenshot_available(session)
        logger.info(
            "Browser Use price model-view preflight execution_id=%s semantic_ready=%s "
            "screenshot_ready=%s entry_kind=%s blocked_requests=%s blocked_hosts=%s",
            request.execution_id,
            semantic_ready,
            screenshot_ready,
            entry_kind,
            self._host.blocked_network_requests,
            ",".join(sorted(self._host.blocked_network_hosts)) or "none",
        )
        if not semantic_ready and not screenshot_ready:
            return BrowserUsePriceRuntimeResult(PriceExecutionStatus.PROVIDER_FAILURE)

        tools: Any = Tools(
            exclude_actions=list(STOCK_ACTIONS), display_files_in_done_text=False
        )
        tools.registry.registry.actions.clear()

        async def stop_unsafe(*, non_allowlisted: bool = False) -> Any:
            self._price_state.terminal = PriceExecutionStatus.UNSAFE_ACTION
            self._price_state.safety_violations.add(
                ExecutorSafetyViolation.NON_ALLOWLISTED_DESTINATION
                if non_allowlisted
                else ExecutorSafetyViolation.PROHIBITED_ACTION_EXECUTED
            )
            return ActionResult(
                is_done=True,
                success=False,
                error="BookSaver rejected an unsafe read-only action",
            )

        async def action_invariant(browser_session: Any, *, phase: str) -> bool:
            reason: str | None = None
            if self._host.dialog_rejected:
                reason = "dialog_rejected"
            elif len(browser_session.get_page_targets()) != 1:
                reason = "target_count"
            elif not self._guard.observable_url(
                await browser_session.get_current_page_url()
            ):
                reason = "destination"
            if reason is not None:
                logger.warning(
                    "Browser Use price action invariant rejected execution_id=%s phase=%s "
                    "reason=%s",
                    request.execution_id,
                    phase,
                    reason,
                )
                return False
            return True

        async def before_action(browser_session: Any) -> bool:
            allowed = await action_invariant(browser_session, phase="before")
            if allowed:
                await remember_visible_semantic_state(
                    browser_session,
                    self._price_state.visible_dom_snapshots,
                )
            return allowed

        async def after_action(browser_session: Any) -> bool:
            return await action_invariant(browser_session, phase="after")

        @tools.action(  # type: ignore[untyped-decorator]
            "Click one visible read-only Booking.com price or property element after safety "
            "checks.",
            param_model=GuardedClick,
            allowed_domains=ALLOWED_DOMAINS,
            terminates_sequence=True,
        )
        async def guarded_click(  # type: ignore[no-untyped-def]
            params: GuardedClick, browser_session
        ) -> Any:
            if not await before_action(browser_session):
                return await stop_unsafe(non_allowlisted=True)
            node = await browser_session.get_element_by_index(params.index)
            if node is None:
                return ActionResult(error="Element is no longer available")
            try:
                meter.record_action()
            except RuntimeError:
                self._price_state.terminal = PriceExecutionStatus.BUDGET_EXHAUSTED
                return ActionResult(is_done=True, success=False, error="Action limit reached")
            current_url = await browser_session.get_current_page_url()
            decision = node_chain_click_decision(
                self._guard,
                current_url=current_url,
                node=node,
                active_target_id=browser_session.agent_focus_target_id,
            )
            if not decision.allowed:
                logger.warning(
                    "Browser Use price click rejected execution_id=%s reason=%s depth=%s",
                    request.execution_id,
                    decision.reason,
                    decision.depth,
                )
                return continued_action_result(
                    ActionResult,
                    "BookSaver rejected this control before execution; choose a visible "
                    "read-only property, room, rate, or disclosure control",
                )
            same_tab_destination = same_tab_click_destination(
                self._guard,
                node=node,
                current_url=current_url,
            )
            if same_tab_destination is not None:
                await browser_session.navigate_to(same_tab_destination, new_tab=False)
            else:
                event = browser_session.event_bus.dispatch(ClickElementEvent(node=node))
                await event
                await event.event_result(raise_if_any=True, raise_if_none=False)
            if not await after_action(browser_session):
                return await stop_unsafe(non_allowlisted=True)
            return ActionResult(extracted_content="Guarded read-only click completed")

        @tools.action(  # type: ignore[untyped-decorator]
            "Click one visible read-only Booking.com price control by screenshot coordinates.",
            param_model=GuardedVisualClick,
            allowed_domains=ALLOWED_DOMAINS,
            terminates_sequence=True,
        )
        async def guarded_visual_click(  # type: ignore[no-untyped-def]
            params: GuardedVisualClick, browser_session
        ) -> Any:
            if not await before_action(browser_session):
                return await stop_unsafe(non_allowlisted=True)
            try:
                meter.record_action(computer_use=True)
            except RuntimeError:
                self._price_state.terminal = PriceExecutionStatus.BUDGET_EXHAUSTED
                return ActionResult(is_done=True, success=False, error="Action limit reached")
            coordinate_x, coordinate_y = viewport_coordinates(
                browser_session,
                coordinate_x=params.coordinate_x,
                coordinate_y=params.coordinate_y,
            )
            if not (
                0 <= coordinate_x < int(viewport["width"])
                and 0 <= coordinate_y < int(viewport["height"])
            ):
                return continued_action_result(
                    ActionResult,
                    "BookSaver rejected coordinates outside the visible screenshot viewport",
                )
            current_url = await browser_session.get_current_page_url()
            chain = await coordinate_hit_test_chain(
                browser_session,
                coordinate_x=coordinate_x,
                coordinate_y=coordinate_y,
            )
            decision = coordinate_chain_click_decision(
                self._guard,
                chain=chain,
                current_url=current_url,
            )
            if not decision.allowed:
                logger.warning(
                    "Browser Use price visual click rejected execution_id=%s reason=%s depth=%s",
                    request.execution_id,
                    decision.reason,
                    decision.depth,
                )
                return continued_action_result(
                    ActionResult,
                    "BookSaver rejected this screenshot point before execution; choose the center "
                    "of a visible read-only property, room, rate, or disclosure control",
                )
            event = browser_session.event_bus.dispatch(
                ClickCoordinateEvent(
                    coordinate_x=coordinate_x,
                    coordinate_y=coordinate_y,
                    force=False,
                )
            )
            await event
            await event.event_result(raise_if_any=True, raise_if_none=False)
            if not await after_action(browser_session):
                return await stop_unsafe(non_allowlisted=True)
            return ActionResult(extracted_content="Guarded visual click completed")

        @tools.action(  # type: ignore[untyped-decorator]
            "Scroll one viewport up or down on the current Booking.com price page.",
            param_model=GuardedScroll,
            allowed_domains=ALLOWED_DOMAINS,
        )
        async def guarded_scroll(  # type: ignore[no-untyped-def]
            params: GuardedScroll, browser_session
        ) -> Any:
            if not await before_action(browser_session):
                return await stop_unsafe(non_allowlisted=True)
            try:
                meter.record_action()
            except RuntimeError:
                self._price_state.terminal = PriceExecutionStatus.BUDGET_EXHAUSTED
                return ActionResult(is_done=True, success=False, error="Action limit reached")
            event = browser_session.event_bus.dispatch(
                ScrollEvent(direction=params.direction, amount=int(viewport["height"]))
            )
            await event
            await event.event_result(raise_if_any=True, raise_if_none=False)
            if not await after_action(browser_session):
                return await stop_unsafe(non_allowlisted=True)
            return ActionResult(extracted_content="Guarded scroll completed")

        @tools.action(  # type: ignore[untyped-decorator]
            "Press one BookSaver-approved navigation key.",
            param_model=GuardedKey,
            allowed_domains=ALLOWED_DOMAINS,
        )
        async def guarded_key(  # type: ignore[no-untyped-def]
            params: GuardedKey, browser_session
        ) -> Any:
            if not await before_action(browser_session):
                return await stop_unsafe(non_allowlisted=True)
            try:
                meter.record_action()
            except RuntimeError:
                self._price_state.terminal = PriceExecutionStatus.BUDGET_EXHAUSTED
                return ActionResult(is_done=True, success=False, error="Action limit reached")
            event = browser_session.event_bus.dispatch(SendKeysEvent(keys=params.key))
            await event
            await event.event_result(raise_if_any=True, raise_if_none=False)
            if not await after_action(browser_session):
                return await stop_unsafe(non_allowlisted=True)
            return ActionResult(extracted_content="Guarded key completed")

        @tools.action(  # type: ignore[untyped-decorator]
            "Replace one visible Booking.com search field with an exact trusted query value.",
            param_model=GuardedTrustedType,
            allowed_domains=ALLOWED_DOMAINS,
            terminates_sequence=True,
        )
        async def guarded_type(  # type: ignore[no-untyped-def]
            params: GuardedTrustedType, browser_session
        ) -> Any:
            if not await before_action(browser_session):
                return await stop_unsafe(non_allowlisted=True)
            if params.value not in _trusted_input_values(request):
                return await stop_unsafe()
            node = await browser_session.get_element_by_index(params.index)
            if node is None:
                return ActionResult(error="Element is no longer available")
            current_url = await browser_session.get_current_page_url()
            if not _trusted_input_node_allowed(
                self._guard,
                node=node,
                current_url=current_url,
                active_target_id=browser_session.agent_focus_target_id,
            ):
                return await stop_unsafe()
            try:
                meter.record_action()
            except RuntimeError:
                self._price_state.terminal = PriceExecutionStatus.BUDGET_EXHAUSTED
                return ActionResult(is_done=True, success=False, error="Action limit reached")
            event = browser_session.event_bus.dispatch(
                TypeTextEvent(
                    node=node,
                    text=params.value,
                    clear=True,
                    is_sensitive=False,
                )
            )
            await event
            await event.event_result(raise_if_any=True, raise_if_none=False)
            if not await after_action(browser_session):
                return await stop_unsafe(non_allowlisted=True)
            return ActionResult(extracted_content="Guarded trusted value entered")

        @tools.action(  # type: ignore[untyped-decorator]
            "Wait briefly for the current Booking.com price page without navigating.",
            param_model=GuardedWait,
            allowed_domains=ALLOWED_DOMAINS,
        )
        async def guarded_wait(  # type: ignore[no-untyped-def]
            params: GuardedWait, browser_session
        ) -> Any:
            if not await before_action(browser_session):
                return await stop_unsafe(non_allowlisted=True)
            try:
                meter.record_action()
            except RuntimeError:
                self._price_state.terminal = PriceExecutionStatus.BUDGET_EXHAUSTED
                return ActionResult(is_done=True, success=False, error="Action limit reached")
            event = browser_session.event_bus.dispatch(
                WaitEvent(seconds=params.milliseconds / 1_000, max_seconds=2.0)
            )
            await event
            await event.event_result(raise_if_any=True, raise_if_none=False)
            if not await after_action(browser_session):
                return await stop_unsafe(non_allowlisted=True)
            return ActionResult(extracted_content="Guarded wait completed")

        @tools.action(  # type: ignore[untyped-decorator]
            "Return once to the previous Booking.com page after read-only inspection.",
            allowed_domains=ALLOWED_DOMAINS,
            terminates_sequence=True,
        )
        async def guarded_back(browser_session) -> Any:  # type: ignore[no-untyped-def]
            if not await before_action(browser_session):
                return await stop_unsafe(non_allowlisted=True)
            try:
                meter.record_action()
            except RuntimeError:
                self._price_state.terminal = PriceExecutionStatus.BUDGET_EXHAUSTED
                return ActionResult(is_done=True, success=False, error="Action limit reached")
            event = browser_session.event_bus.dispatch(GoBackEvent())
            await event
            await event.event_result(raise_if_any=True, raise_if_none=False)
            if not await after_action(browser_session):
                return await stop_unsafe(non_allowlisted=True)
            return ActionResult(extracted_content="Guarded browser history return completed")

        @tools.action(  # type: ignore[untyped-decorator]
            "Submit a complete visible query with visible room/rate offers. Query completeness "
            "covers property, dates, occupancy, and currency only; each offer's completeness, "
            "all_in, and refundability are independent and may be unknown or incomplete.",
            param_model=BrowserUsePriceObservationSubmission,
            allowed_domains=ALLOWED_DOMAINS,
            terminates_sequence=True,
        )
        async def submit_price_observation(  # type: ignore[no-untyped-def]
            params: BrowserUsePriceObservationSubmission, browser_session
        ) -> Any:
            if not await before_action(browser_session):
                return await stop_unsafe(non_allowlisted=True)
            if params.completeness != EvidenceCompleteness.COMPLETE.value:
                return continued_action_result(
                    ActionResult,
                    "Top-level completeness covers only the visible property, stay dates, "
                    "adults, children, rooms, and currency. Offer completeness, all_in, and "
                    "refundability are independent; incomplete or nonrefundable offers do not "
                    "make the query incomplete. Inspect any missing or conflicting query facts "
                    "before submitting again. If they remain unclear, use "
                    "done(success=false, status=no_valid_observation). Do not resubmit unchanged "
                    "evidence or mark missing query facts complete.",
                )
            current_url = await browser_session.get_current_page_url()
            candidate = _PriceEpisodeState(
                query=BrowserUsePriceQuerySubmission.model_validate(
                    params.model_dump(exclude={"offers"})
                ),
                property_reference=current_url,
                offers=list(params.offers),
            )
            try:
                observation = _observation_from_state(candidate)
            except (TypeError, ValueError) as exc:
                logger.warning(
                    "Browser Use typed price observation rejected execution_id=%s reason=%s",
                    request.execution_id,
                    _typed_observation_error_code(exc)
                    if isinstance(exc, ValueError)
                    else "type",
                )
                return continued_action_result(
                    ActionResult,
                    "Typed evidence was invalid; re-inspect and submit exact visible values",
                )
            self._price_state.query = candidate.query
            self._price_state.property_reference = candidate.property_reference
            self._price_state.offers = candidate.offers
            self._price_state.observation = observation
            return ActionResult(
                is_done=True,
                success=True,
                extracted_content="Typed price evidence submitted",
            )

        @tools.action(  # type: ignore[untyped-decorator]
            "Finish without an observation using one status: " + _TERMINAL_STATUS_CHOICES
            + ". Use no_valid_observation for missing or ambiguous evidence.",
            param_model=BrowserUsePriceTerminalSubmission,
            terminates_sequence=True,
        )
        async def done(  # type: ignore[no-untyped-def]
            params: BrowserUsePriceTerminalSubmission, browser_session
        ) -> Any:
            if not await before_action(browser_session):
                return await stop_unsafe(non_allowlisted=True)
            if params.success:
                return continued_action_result(
                    ActionResult,
                    "Use submit_price_observation for success; done is only for closed failure",
                )
            try:
                self._price_state.terminal = _terminal_status(params.status)
            except ValueError:
                return continued_action_result(
                    ActionResult,
                    "Choose one status: " + _TERMINAL_STATUS_CHOICES
                    + ". Use no_valid_observation for missing or ambiguous evidence.",
                )
            return ActionResult(
                is_done=True,
                success=False,
                extracted_content="Typed terminal submitted",
            )

        model_cls = budgeted_model_type(ChatAnthropic, _PROMPT_VERSION)
        model = model_cls(api_key=api_key, budget=budget, meter=meter)

        agent_run_id = f"booksaver-price-{uuid.uuid4().hex}"
        agent = self._host.create_agent(
            Agent,
            task=_price_agent_task(request),
            task_id=agent_run_id,
            llm=model,
            browser_session=session,
            tools=tools,
            viewport=viewport,
            file_system_dir=file_system_dir,
            deadline=request.limits.deadline,
            # Initial authentication retained the exact verified mobile snapshot. Repeating
            # the probe after submission would spend the shared deadline unnecessarily.
            register_done_callback=None,
        )
        actions = frozenset(tools.registry.registry.actions)
        if actions != _EXPECTED_ACTIONS:
            raise RuntimeError("Browser Use price action registry differs from the allowlist")

        self._host.failure_stage = "agent_execution"
        remaining_steps = max(1, request.limits.max_actions - meter.snapshot().total_actions)
        history = None
        run_outcome = "error"
        run_started = time.monotonic()
        try:
            history = await agent.run(max_steps=remaining_steps)
            run_outcome = "returned"
        except asyncio.CancelledError:
            run_outcome = "cancelled"
            raise
        except BrowserUseCostStop:
            run_outcome = "cost_stop"
        finally:
            if self._price_state.observation is None or run_outcome != "returned":
                # agent.run keeps partial history even when the outer deadline cancels it.
                # Inspect only bounded categories; never emit model, page, or error text.
                try:
                    diagnostic = agent_history_diagnostic(
                        history if history is not None else getattr(agent, "history", None),
                        _EXPECTED_ACTIONS,
                    )
                    steps, diagnostic_actions, errors = (
                        diagnostic.steps, diagnostic.actions, diagnostic.errors,
                    )
                except Exception:
                    steps, diagnostic_actions, errors = 0, (), ("diagnostic_unavailable",)
                usage = meter.snapshot()
                logger.warning(
                    "Browser Use price agent summary execution_id=%s outcome=%s elapsed_ms=%s "
                    "steps=%s actions=%s errors=%s model_calls=%s total_actions=%s "
                    "query_submitted=%s offers_submitted=%s observation_submitted=%s",
                    request.execution_id,
                    run_outcome,
                    max(0, round((time.monotonic() - run_started) * 1_000)),
                    steps,
                    diagnostic_actions,
                    errors,
                    usage.model_calls,
                    usage.total_actions,
                    self._price_state.query is not None,
                    len(self._price_state.offers),
                    self._price_state.observation is not None,
                )
            del history

        if self._host.dialog_rejected:
            return self._unsafe_result()
        if self._price_state.terminal is not None:
            return BrowserUsePriceRuntimeResult(
                self._price_state.terminal,
                safety_violations=frozenset(self._price_state.safety_violations),
            )
        if self._price_state.observation is None:
            stop = getattr(model, "_booksaver_stop", None)
            status = (
                PriceExecutionStatus.BUDGET_EXHAUSTED
                if stop
                in {
                    ModelStopReason.JOB_COST_LIMIT,
                    ModelStopReason.DAILY_COST_LIMIT,
                    ModelStopReason.COST_ACCOUNTING_ERROR,
                }
                else PriceExecutionStatus.PROVIDER_FAILURE
            )
            return BrowserUsePriceRuntimeResult(status)
        return BrowserUsePriceRuntimeResult(
            PriceExecutionStatus.OBSERVED,
            observation=self._price_state.observation,
            refreshed_session=self._price_state.refreshed_session,
        )

    def _unsafe_result(self, *, non_allowlisted: bool = False) -> BrowserUsePriceRuntimeResult:
        return BrowserUsePriceRuntimeResult(
            PriceExecutionStatus.UNSAFE_ACTION,
            safety_violations=frozenset(
                {
                    ExecutorSafetyViolation.NON_ALLOWLISTED_DESTINATION
                    if non_allowlisted
                    else ExecutorSafetyViolation.PROHIBITED_ACTION_EXECUTED
                }
            ),
        )

    async def close(self) -> None:
        await self._host.close()


class BrowserUsePriceBrowserExecutor:
    """Synchronous provider-neutral price port over one Browser Use episode."""

    def __init__(
        self,
        *,
        api_key: str,
        lease_broker: InMemorySessionLeaseBroker,
        budget: BrowserJobCostBudget,
        runner: AsyncLoopRunner,
        runtime_factory: Callable[[], BrowserUsePriceRuntimePort] = LocalBrowserUsePriceRuntime,
    ) -> None:
        if not api_key.strip():
            raise ValueError("BOOKSAVER_LLM_API_KEY is required for Browser Use price execution")
        self._api_key = api_key
        self._leases = lease_broker
        self._budget = budget
        self._runner = runner
        self._runtime_factory = runtime_factory

    def execute(self, request: PriceExecutionRequest) -> PriceExecutionResult:
        remaining = (request.limits.deadline - datetime.now(UTC)).total_seconds()
        timeout = max(0.001, min(float(request.limits.timeout_seconds), remaining))
        started = time.monotonic()
        meter = ExecutionMeter(request.limits)
        try:
            return self._runner.run(self._execute(request, started, meter), timeout=timeout)
        except TimeoutError:
            return self._terminal(PriceExecutionStatus.TIMEOUT, meter, started)
        except RuntimeError as exc:
            status = (
                PriceExecutionStatus.BUDGET_EXHAUSTED
                if "limit exhausted" in str(exc)
                else PriceExecutionStatus.PROVIDER_FAILURE
            )
            logger.warning(
                "Browser Use price failed execution_id=%s failure_stage=%s failure_type=%s",
                request.execution_id,
                getattr(exc, "stage", "executor"),
                getattr(exc, "cause_type", type(exc).__name__),
            )
            return self._terminal(status, meter, started)
        except Exception as exc:
            logger.warning(
                "Browser Use price failed execution_id=%s failure_stage=%s failure_type=%s",
                request.execution_id,
                getattr(exc, "stage", "executor"),
                getattr(exc, "cause_type", type(exc).__name__),
            )
            return self._terminal(PriceExecutionStatus.PROVIDER_FAILURE, meter, started)

    async def _execute(
        self,
        request: PriceExecutionRequest,
        started: float,
        meter: ExecutionMeter,
    ) -> PriceExecutionResult:
        runtime = self._runtime_factory()
        try:
            self._leases.restore_into(request.session_lease, runtime)
            try:
                result = await runtime.execute(
                    request,
                    api_key=self._api_key,
                    budget=self._budget,
                    meter=meter,
                )
            except Exception as exc:
                raise BrowserUseRuntimeFailure(
                    stage=str(getattr(runtime, "failure_stage", "runtime_execute")),
                    cause_type=type(exc).__name__,
                ) from None
            if result.status is not PriceExecutionStatus.OBSERVED:
                return self._terminal(
                    result.status,
                    meter,
                    started,
                    safety_violations=result.safety_violations,
                )
            if result.observation is None:
                return self._terminal(
                    PriceExecutionStatus.NO_VALID_OBSERVATION,
                    meter,
                    started,
                )
            if result.refreshed_session is not None:
                self._leases.store_verified_refresh(
                    request.session_lease,
                    result.refreshed_session,
                )
            usage = meter.snapshot()
            return PriceExecutionResult(
                PriceExecutionStatus.OBSERVED,
                query_facts=result.observation.facts,
                offers=result.observation.offers,
                provenance=RedactedProvenance(
                    source=ObservationSource.BROWSER_USE_PRICE_SUBMISSION,
                    action_count=usage.total_actions,
                    evidence_item_count=result.observation.evidence_item_count,
                ),
                refreshed_session_eligible=result.refreshed_session is not None,
                usage=usage,
                latency_ms=max(0, round((time.monotonic() - started) * 1_000)),
                fallback_used=False,
            )
        finally:
            await runtime.close()

    @staticmethod
    def _terminal(
        status: PriceExecutionStatus,
        meter: ExecutionMeter,
        started: float,
        *,
        safety_violations: frozenset[ExecutorSafetyViolation] = frozenset(),
    ) -> PriceExecutionResult:
        return PriceExecutionResult(
            status,
            usage=meter.snapshot(),
            latency_ms=max(0, round((time.monotonic() - started) * 1_000)),
            fallback_used=False,
            safety_violations=safety_violations,
        )


class LocalBrowserUsePriceExecutor:
    """One-shot price executor that owns and closes its async runner."""

    def __init__(
        self,
        *,
        api_key: str,
        lease_broker: InMemorySessionLeaseBroker,
        budget: BrowserJobCostBudget,
        mobile_settings: MobileWebSettings | None = None,
    ) -> None:
        self._api_key = api_key
        self._leases = lease_broker
        self._budget = budget
        self._mobile_settings = mobile_settings or MobileWebSettings()

    def execute(self, request: PriceExecutionRequest) -> PriceExecutionResult:
        with AsyncLoopRunner() as runner:
            return BrowserUsePriceBrowserExecutor(
                api_key=self._api_key,
                lease_broker=self._leases,
                budget=self._budget,
                runner=runner,
                runtime_factory=lambda: LocalBrowserUsePriceRuntime(self._mobile_settings),
            ).execute(request)
