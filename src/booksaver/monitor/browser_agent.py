from __future__ import annotations

import hashlib
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import cast
from urllib.parse import urlsplit

from booksaver.application.ports import AgentBrain, InteractiveBrowser
from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    AgentBudget,
    AgentHistoryEvent,
    AgentHistoryOutcome,
    AgentStopReason,
    AgentTurnContext,
    BudgetExceeded,
    ElementInfo,
    EscalationResult,
    Observation,
    RecoveryPolicy,
    blocked_action_reason,
    blocked_url_reason,
)
from booksaver.domain.check_result import FailureCode
from booksaver.domain.errors import UserKeyInvalidError
from booksaver.domain.journey import JourneyStep

from .trace import TraceRecorder, redact

logger = logging.getLogger(__name__)

_CAPTCHA_PAGE_PATTERN = re.compile(
    r"(are you a human|verify you are human|hcaptcha|px-captcha|unusual traffic)",
    re.IGNORECASE,
)
_AUTH_PAGE_PATTERN = re.compile(
    r"(sign in to manage|log in to your account|enter your password|"
    r"verification code|two-factor authentication|multi-factor authentication)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _TraceStep:
    """Runtime-compatible step label for recovery outside SearchJourney."""

    value: str


class BrowserAgent:
    """Complete one failed Booking.com operation with bounded LLM assistance."""

    def __init__(
        self,
        browser: InteractiveBrowser,
        brain: AgentBrain,
        budget: AgentBudget,
        recorder: TraceRecorder,
        recovery_policy: RecoveryPolicy | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._browser = browser
        self._brain = brain
        self._budget = budget
        self._recorder = recorder
        self._policy = recovery_policy or RecoveryPolicy()
        self._clock = clock
        self.last_screenshot: bytes | None = None

    def complete_step(
        self,
        step: JourneyStep | str,
        goal: str,
        verify: Callable[[], bool],
        trigger: str,
        screenshot_first: bool = False,
        verification_condition: str | None = None,
    ) -> EscalationResult:
        """Recover one operation and return only after authoritative verification.

        ``step`` accepts a stable string so account-inventory operations can use
        the same controller without expanding the search-journey enum.
        """
        trace_step = _trace_step(step)
        step_name = trace_step.value
        safe_trigger = _safe_detail(trigger)
        self._recorder.escalation_started(
            cast("JourneyStep", trace_step), safe_trigger
        )
        history: list[AgentHistoryEvent] = [
            AgentHistoryEvent(
                outcome=AgentHistoryOutcome.SCRIPT_FAILED,
                detail=f"scripted attempt failed: {safe_trigger}",
                error=safe_trigger,
            )
        ]
        self._recorder.agent_outcome(
            cast("JourneyStep", trace_step), history[0]
        )
        no_progress_count = 0
        semantic_executions: dict[str, int] = {}
        step_llm_calls = 0
        tier2_pending = screenshot_first
        forced_reorientation_pending = False
        screenshot_requests = 0
        used_screenshot = False
        started_at = self._clock()

        try:
            preflight = self._browser.observe()
        except Exception as exc:
            return self._stop(
                trace_step,
                f"browser state could not be inspected safely at {step_name}: "
                f"{_safe_error(exc, include_message=False)}",
                FailureCode.AGENT_GAVE_UP,
                used_screenshot,
                AgentStopReason.MISSING_BROWSER_CAPABILITY,
            )
        preflight_problem = _observation_safety_problem(preflight)
        if preflight_problem is not None:
            detail, failure_code, stop_reason = preflight_problem
            return self._stop(
                trace_step, detail, failure_code, used_screenshot, stop_reason
            )

        # A verifier may read browser state, so it is only called after the
        # controllable page and every popup have passed the same destination
        # guards used before provider calls and actions.
        if _safe_verify(verify):
            try:
                verified_state = self._browser.observe()
            except Exception as exc:
                return self._stop(
                    trace_step,
                    f"verified browser state could not be inspected safely at "
                    f"{step_name}: {_safe_error(exc, include_message=False)}",
                    FailureCode.AGENT_GAVE_UP,
                    used_screenshot,
                    AgentStopReason.MISSING_BROWSER_CAPABILITY,
                )
            safety_problem = _observation_safety_problem(verified_state)
            if safety_problem is not None:
                detail, failure_code, stop_reason = safety_problem
                return self._stop(
                    trace_step, detail, failure_code, used_screenshot, stop_reason
                )
            self._recorder.agent_result(
                cast("JourneyStep", trace_step),
                "step already complete after the scripted error",
            )
            return EscalationResult(
                ok=True,
                detail=f"agent found {step_name} already complete",
            )

        try:
            while True:
                self._budget.check_time()
                elapsed = self._clock() - started_at
                if elapsed > self._policy.timeout_seconds:
                    return self._stop(
                        trace_step,
                        f"recovery timeout exceeded at {step_name} "
                        f"({elapsed:.0f}s/{self._policy.timeout_seconds}s)",
                        FailureCode.BUDGET_EXCEEDED,
                        used_screenshot,
                        AgentStopReason.BUDGET_EXHAUSTED,
                    )
                if step_llm_calls >= self._policy.max_llm_calls:
                    return self._stop(
                        trace_step,
                        f"agent made no verified progress at {step_name} within "
                        f"{self._policy.max_llm_calls} LLM calls",
                        FailureCode.AGENT_NO_PROGRESS,
                        used_screenshot,
                        AgentStopReason.NO_PROGRESS,
                    )

                try:
                    observation = self._browser.observe()
                except Exception as exc:
                    return self._stop(
                        trace_step,
                        f"browser state could not be inspected safely at {step_name}: "
                        f"{_safe_error(exc, include_message=False)}",
                        FailureCode.AGENT_GAVE_UP,
                        used_screenshot,
                        AgentStopReason.MISSING_BROWSER_CAPABILITY,
                    )
                safety_problem = _observation_safety_problem(observation)
                if safety_problem is not None:
                    detail, failure_code, stop_reason = safety_problem
                    return self._stop(
                        trace_step, detail, failure_code, used_screenshot, stop_reason
                    )

                forced_screenshot_turn = forced_reorientation_pending
                if tier2_pending:
                    observation = self._with_screenshot(observation)
                    if observation.screenshot is not None:
                        used_screenshot = True
                        reason = (
                            "forced after no progress"
                            if forced_screenshot_turn
                            else "visual step — screenshot on entry"
                            if screenshot_first
                            else "requested by agent"
                        )
                        self._recorder.screenshot_tier(
                            cast("JourneyStep", trace_step), reason
                        )
                    screenshot_first = False
                self._budget.consume_step(tier2=observation.screenshot is not None)
                tier2_pending = False
                forced_reorientation_pending = False

                context = AgentTurnContext(
                    goal=goal,
                    observation=observation,
                    history=tuple(history),
                    llm_calls_used=step_llm_calls,
                    max_llm_calls=self._policy.max_llm_calls,
                    no_progress_count=no_progress_count,
                    screenshot_forced=forced_screenshot_turn,
                    seconds_remaining=max(
                        0.0, self._policy.timeout_seconds - elapsed
                    ),
                    verification_condition=verification_condition,
                )
                # Enforce the shared check budget before inviting a turn, but only
                # consume after the brain admits a real provider attempt. Nested
                # daily gates (inventory) may raise BudgetExceeded without calling
                # the provider; those must not charge step or check budgets.
                self._budget.ensure_llm_call_available()
                try:
                    action = self._brain.decide(context)
                except UserKeyInvalidError:
                    raise
                except BudgetExceeded:
                    raise
                except Exception as exc:
                    self._budget.consume_llm_call()
                    safe_error = _safe_error(exc, include_message=False)
                    logger.warning("Browser-agent provider call failed: %s", safe_error)
                    return self._stop(
                        trace_step,
                        f"browser-agent provider failed at {step_name}: {safe_error}",
                        FailureCode.LLM_ERROR,
                        used_screenshot,
                        AgentStopReason.PROVIDER_ERROR,
                    )
                self._budget.consume_llm_call()
                step_llm_calls += 1
                self._budget.check_time()
                decision_elapsed = self._clock() - started_at
                if decision_elapsed > self._policy.timeout_seconds:
                    return self._stop(
                        trace_step,
                        f"recovery timeout exceeded at {step_name} after provider "
                        f"response ({decision_elapsed:.0f}s/"
                        f"{self._policy.timeout_seconds}s)",
                        FailureCode.BUDGET_EXCEEDED,
                        used_screenshot,
                        AgentStopReason.BUDGET_EXHAUSTED,
                    )

                target = _target_for(action, observation)
                action_for_trace = replace(
                    action,
                    value=(
                        _safe_detail(action.value)
                        if action.value is not None
                        else None
                    ),
                )
                self._recorder.agent_action(
                    cast("JourneyStep", trace_step),
                    action_for_trace,
                    tier2=observation.screenshot is not None,
                    target_label=target.label if target is not None else None,
                )

                if action.type is AgentActionType.GIVE_UP:
                    reason = _safe_detail(action.value or "no reason given")
                    stop_reason = action.stop_reason or _infer_stop_reason(reason)
                    return self._stop(
                        trace_step,
                        f"agent gave up at {step_name}: {reason}",
                        (
                            FailureCode.LLM_ERROR
                            if stop_reason is AgentStopReason.PROVIDER_ERROR
                            else FailureCode.BUDGET_EXCEEDED
                            if stop_reason is AgentStopReason.BUDGET_EXHAUSTED
                            else FailureCode.AGENT_NO_PROGRESS
                            if stop_reason is AgentStopReason.NO_PROGRESS
                            else FailureCode.AGENT_GAVE_UP
                        ),
                        used_screenshot,
                        stop_reason,
                    )

                if action.type is AgentActionType.REQUEST_SCREENSHOT:
                    if observation.screenshot is not None or screenshot_requests >= 1:
                        detail = "screenshot already provided or requested"
                        self._recorder.agent_blocked(
                            cast("JourneyStep", trace_step), detail
                        )
                        history.append(
                            event := AgentHistoryEvent(
                                outcome=AgentHistoryOutcome.REFUSED,
                                detail=detail,
                                action=action,
                            )
                        )
                        self._recorder.agent_outcome(
                            cast("JourneyStep", trace_step), event
                        )
                        continue
                    screenshot_requests += 1
                    tier2_pending = True
                    history.append(
                        event := AgentHistoryEvent(
                            outcome=AgentHistoryOutcome.SCREENSHOT_REQUESTED,
                            detail="screenshot requested; provided next turn",
                            action=action,
                        )
                    )
                    self._recorder.agent_outcome(
                        cast("JourneyStep", trace_step), event
                    )
                    continue

                semantic_target = _semantic_action_key(action, observation)
                executions = semantic_executions.get(semantic_target, 0)
                if executions >= self._policy.max_semantic_executions:
                    detail = (
                        f"repeated semantic action refused: {semantic_target} already "
                        "failed to progress the verified step goal"
                    )
                    self._recorder.agent_blocked(
                        cast("JourneyStep", trace_step), detail
                    )
                    history.append(
                        event := AgentHistoryEvent(
                            outcome=AgentHistoryOutcome.REFUSED,
                            detail=detail,
                            action=action,
                            semantic_target=semantic_target,
                        )
                    )
                    self._recorder.agent_outcome(
                        cast("JourneyStep", trace_step),
                        event,
                        no_progress_count=no_progress_count,
                        semantic_execution_count=executions,
                    )
                    if forced_screenshot_turn:
                        return self._stop(
                            trace_step,
                            f"agent made no progress after screenshot reorientation "
                            f"at {step_name}",
                            FailureCode.AGENT_NO_PROGRESS,
                            used_screenshot,
                            AgentStopReason.NO_PROGRESS,
                        )
                    if no_progress_count >= self._policy.no_progress_before_screenshot:
                        tier2_pending = True
                        forced_reorientation_pending = True
                    continue

                blocked = blocked_action_reason(action, observation)
                if blocked is not None:
                    self._recorder.agent_blocked(
                        cast("JourneyStep", trace_step), blocked
                    )
                    return self._stop(
                        trace_step,
                        f"action refused by guard: {blocked}",
                        FailureCode.BLOCKED_ACTION,
                        used_screenshot,
                        AgentStopReason.UNSAFE_ACTION,
                    )

                semantic_executions[semantic_target] = executions + 1
                execution_error: str | None = None
                try:
                    self._browser.act(action)
                except Exception as exc:
                    execution_error = _safe_error(exc)
                self._budget.check_time()

                try:
                    after = self._browser.observe()
                except Exception as exc:
                    after = observation
                    execution_error = execution_error or _safe_error(exc)
                self._budget.check_time()

                safety_problem = _observation_safety_problem(after)
                if safety_problem is not None:
                    detail, failure_code, stop_reason = safety_problem
                    self._recorder.agent_blocked(
                        cast("JourneyStep", trace_step), detail
                    )
                    return self._stop(
                        trace_step, detail, failure_code, used_screenshot, stop_reason
                    )

                goal_verified = _safe_verify(verify)
                if goal_verified:
                    try:
                        verified_state = self._browser.observe()
                    except Exception as exc:
                        return self._stop(
                            trace_step,
                            f"verified browser state could not be inspected safely at "
                            f"{step_name}: {_safe_error(exc, include_message=False)}",
                            FailureCode.AGENT_GAVE_UP,
                            used_screenshot,
                            AgentStopReason.MISSING_BROWSER_CAPABILITY,
                        )
                    safety_problem = _observation_safety_problem(verified_state)
                    if safety_problem is not None:
                        detail, failure_code, stop_reason = safety_problem
                        return self._stop(
                            trace_step,
                            detail,
                            failure_code,
                            used_screenshot,
                            stop_reason,
                        )
                event = _history_event(
                    action=action,
                    semantic_target=semantic_target,
                    before=observation,
                    after=after,
                    goal_verified=goal_verified,
                    execution_error=execution_error,
                )
                history.append(event)
                next_no_progress = 0 if event.made_progress else no_progress_count + 1
                self._recorder.agent_outcome(
                    cast("JourneyStep", trace_step),
                    event,
                    no_progress_count=next_no_progress,
                    semantic_execution_count=semantic_executions[semantic_target],
                )

                if goal_verified:
                    self._recorder.agent_result(
                        cast("JourneyStep", trace_step), "step completed by agent"
                    )
                    return EscalationResult(
                        ok=True,
                        detail=f"agent completed {step_name}",
                        used_screenshot=used_screenshot,
                    )

                if event.made_progress:
                    no_progress_count = 0
                    semantic_executions.clear()
                    continue

                no_progress_count += 1
                if forced_screenshot_turn and observation.screenshot is not None:
                    return self._stop(
                        trace_step,
                        f"agent made no progress after screenshot reorientation at "
                        f"{step_name}",
                        FailureCode.AGENT_NO_PROGRESS,
                        used_screenshot,
                        AgentStopReason.NO_PROGRESS,
                    )
                if no_progress_count >= self._policy.no_progress_before_screenshot:
                    tier2_pending = True
                    forced_reorientation_pending = True

        except BudgetExceeded as exc:
            return self._stop(
                trace_step,
                str(exc),
                FailureCode.BUDGET_EXCEEDED,
                used_screenshot,
                AgentStopReason.BUDGET_EXHAUSTED,
            )

    def _stop(
        self,
        step: _TraceStep,
        detail: str,
        failure_code: FailureCode,
        used_screenshot: bool,
        stop_reason: AgentStopReason,
    ) -> EscalationResult:
        self._recorder.agent_outcome(
            cast("JourneyStep", step),
            AgentHistoryEvent(
                outcome=AgentHistoryOutcome.STOPPED,
                detail=detail,
            ),
            stop_reason=stop_reason,
        )
        self._recorder.agent_result(cast("JourneyStep", step), detail)
        return EscalationResult(
            ok=False,
            detail=detail,
            failure_code=failure_code,
            used_screenshot=used_screenshot,
            stop_reason=stop_reason,
        )

    def _with_screenshot(self, observation: Observation) -> Observation:
        try:
            self.last_screenshot = self._browser.screenshot()
            return replace(observation, screenshot=self.last_screenshot)
        except Exception as exc:
            logger.warning(
                "Screenshot capture failed, staying on tier 1: %s", _safe_error(exc)
            )
            return observation


def _trace_step(step: JourneyStep | str) -> _TraceStep:
    return _TraceStep(step.value if isinstance(step, JourneyStep) else step)


def _target_for(action: AgentAction, observation: Observation) -> ElementInfo | None:
    return next((el for el in observation.elements if el.ref == action.ref), None)


def _normalise_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _safe_detail(value: str, max_chars: int = 240) -> str:
    redacted = redact(value)
    redacted = re.sub(
        r"https?://[^\s]+",
        lambda match: _url_without_query(match.group(0)),
        redacted,
    )
    return redacted[:max_chars]


def _safe_error(exc: Exception, *, include_message: bool = True) -> str:
    name = type(exc).__name__
    if not include_message or not str(exc):
        return name
    return f"{name}: {_safe_detail(str(exc))}"


def _url_without_query(url: str) -> str:
    parsed = urlsplit(url.rstrip(".,;:)"))
    return f"{parsed.scheme}://{parsed.hostname or ''}{parsed.path}"


def _normalise_href(href: str | None) -> str:
    if not href:
        return ""
    parsed = urlsplit(href)
    return f"{parsed.hostname or ''}{parsed.path}".casefold().rstrip("/")


def _unsafe_popup_reason(urls: tuple[str, ...]) -> str | None:
    for url in urls:
        if url.startswith("unavailable:"):
            return "browser popup metadata could not be inspected safely"
        reason = _unsafe_booking_url_reason(url, surface="popup")
        if reason is not None:
            return reason
    return None


def _observation_safety_problem(
    observation: Observation,
) -> tuple[str, FailureCode, AgentStopReason] | None:
    """Validate every browser destination before trusted code or the model runs."""
    visible_evidence = f"{observation.title}\n{observation.text[:30_000]}"
    if _CAPTCHA_PAGE_PATTERN.search(visible_evidence):
        return (
            "Booking.com presented a bot-verification wall",
            FailureCode.BOT_WALL,
            AgentStopReason.CAPTCHA,
        )
    if _AUTH_PAGE_PATTERN.search(visible_evidence):
        return (
            "Booking.com authentication is required",
            FailureCode.AUTH_REQUIRED,
            AgentStopReason.AUTHENTICATION_REQUIRED,
        )
    if observation.popup_count > len(observation.popup_urls):
        return (
            "browser popup metadata could not be inspected safely",
            FailureCode.AGENT_GAVE_UP,
            AgentStopReason.MISSING_BROWSER_CAPABILITY,
        )
    main_page_problem = _unsafe_booking_url_reason(
        observation.url, surface="controllable page"
    )
    if main_page_problem is not None:
        return (
            main_page_problem,
            FailureCode.BLOCKED_ACTION,
            AgentStopReason.UNSAFE_ACTION,
        )
    popup_problem = _unsafe_popup_reason(observation.popup_urls)
    if popup_problem is not None:
        return (
            popup_problem,
            FailureCode.BLOCKED_ACTION,
            AgentStopReason.UNSAFE_ACTION,
        )
    for candidate_url in (observation.url, *observation.popup_urls):
        blocked = blocked_url_reason(candidate_url)
        if blocked is not None:
            return (
                blocked,
                FailureCode.BLOCKED_ACTION,
                AgentStopReason.UNSAFE_ACTION,
            )
    return None


def _unsafe_booking_url_reason(url: str, *, surface: str) -> str | None:
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").casefold()
    if parsed.scheme == "https" and (
        hostname == "booking.com" or hostname.endswith(".booking.com")
    ):
        return None
    return f"browser opened a non-Booking.com {surface}: {parsed.scheme}://{hostname}"


def _element_signature(element: ElementInfo) -> str:
    return "|".join(
        (
            _normalise_text(element.role),
            _normalise_text(element.label),
            _normalise_href(element.href),
        )
    )


def _semantic_action_key(action: AgentAction, observation: Observation) -> str:
    target = _target_for(action, observation)
    if target is None:
        target_key = action.ref or ""
    else:
        signature = _element_signature(target)
        occurrence = 1
        for element in observation.elements:
            if element.ref == target.ref:
                break
            if _element_signature(element) == signature:
                occurrence += 1
        target_key = f"{signature}|occurrence={occurrence}"
    value = _normalise_text(action.value or "")
    material = f"{action.type.value}:{target_key}:{value}".encode()
    digest = hashlib.sha256(material).hexdigest()[:16]
    return f"{action.type.value}:{digest}"


def _history_event(
    *,
    action: AgentAction,
    semantic_target: str,
    before: Observation,
    after: Observation,
    goal_verified: bool,
    execution_error: str | None,
) -> AgentHistoryEvent:
    target = _target_for(action, before)
    target_signature = _element_signature(target) if target is not None else None
    before_target_count = (
        sum(
            _element_signature(element) == target_signature
            for element in before.elements
        )
        if target_signature is not None
        else 0
    )
    after_target_count = (
        sum(
            _element_signature(element) == target_signature
            for element in after.elements
        )
        if target_signature is not None
        else 0
    )
    popup_opened = after.popup_count > before.popup_count or bool(
        set(after.popup_urls) - set(before.popup_urls)
    )
    return AgentHistoryEvent(
        outcome=(
            AgentHistoryOutcome.FAILED
            if execution_error is not None
            else AgentHistoryOutcome.EXECUTED
        ),
        detail=(
            f"action failed: {execution_error}"
            if execution_error is not None
            else "action executed; authoritative goal verification followed"
        ),
        action=action,
        semantic_target=semantic_target,
        goal_verified=goal_verified,
        url_changed=before.url != after.url,
        content_changed=(
            _normalise_text(before.title) != _normalise_text(after.title)
        ),
        # Dynamic banners, prices, timers, and unrelated controls must not reset
        # semantic repetition. Only a change to the selected target's visible
        # occurrence count is action-correlated element progress.
        elements_changed=before_target_count != after_target_count,
        scroll_changed=before.scroll_y != after.scroll_y,
        popup_opened=popup_opened,
        error=execution_error,
    )


def _safe_verify(verify: Callable[[], bool]) -> bool:
    try:
        return verify()
    except Exception:
        return False


def _infer_stop_reason(reason: str) -> AgentStopReason:
    lowered = reason.casefold()
    if "captcha" in lowered or "bot" in lowered:
        return AgentStopReason.CAPTCHA
    if "login" in lowered or "sign in" in lowered or "authentication" in lowered:
        return AgentStopReason.AUTHENTICATION_REQUIRED
    if "sold out" in lowered or "unavailable" in lowered or "no rooms" in lowered:
        return AgentStopReason.EXPLICIT_UNAVAILABLE
    if "popup" in lowered or "new tab" in lowered or "cannot control" in lowered:
        return AgentStopReason.MISSING_BROWSER_CAPABILITY
    return AgentStopReason.UNKNOWN
