from __future__ import annotations

import logging
from collections.abc import Callable

from booksaver.application.ports import AgentBrain, InteractiveBrowser
from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    AgentBudget,
    BudgetExceeded,
    EscalationResult,
    Observation,
    blocked_action_reason,
    blocked_url_reason,
)
from booksaver.domain.check_result import FailureCode
from booksaver.domain.journey import JourneyStep

from .trace import TraceRecorder

logger = logging.getLogger(__name__)

# Two consecutive failed actions auto-escalate the observation to tier 2 (ADR-015).
_FAILURES_BEFORE_SCREENSHOT = 2
# Identical successful-but-unverified actions signal the agent is stuck (e.g. refilling
# an already-correct search box). Nudge early, give up before burning the step budget.
_LOOP_HINT_AFTER = 3
_LOOP_GIVE_UP_AFTER = 5
# Screenshot requests are expensive (2x step cost) and agents can spam them when stuck.
_MAX_SCREENSHOT_REQUESTS = 2


class BrowserAgent:
    """LLM agent that takes over exactly one failed journey step (US-020).

    Loop: observe (tier 1, screenshot on demand) → brain decides one bounded
    action → guard → act → verify. Success returns control to the scripted
    journey; give-up, guard trips, and budget breaches end the check with their
    distinct failure codes.
    """

    def __init__(
        self,
        browser: InteractiveBrowser,
        brain: AgentBrain,
        budget: AgentBudget,
        recorder: TraceRecorder,
    ) -> None:
        self._browser = browser
        self._brain = brain
        self._budget = budget
        self._recorder = recorder
        self.last_screenshot: bytes | None = None  # reused by failure snapshots

    def complete_step(
        self,
        step: JourneyStep,
        goal: str,
        verify: Callable[[], bool],
        trigger: str,
        screenshot_first: bool = False,
    ) -> EscalationResult:
        self._recorder.escalation_started(step, trigger)
        history: list[str] = [f"scripted attempt failed: {trigger}"]
        consecutive_failures = 0
        tier2_pending = screenshot_first
        used_screenshot = False
        recent_action_keys: list[str] = []
        screenshot_requests = 0

        try:
            while True:
                self._budget.check_time()
                observation = self._browser.observe()
                if tier2_pending:
                    observation = self._with_screenshot(observation)
                    used_screenshot = True
                    if screenshot_first:
                        self._recorder.screenshot_tier(step, "visual step — screenshot on entry")
                        screenshot_first = False
                self._budget.consume_step(tier2=tier2_pending)
                tier2 = tier2_pending
                tier2_pending = False

                self._budget.consume_llm_call()
                action = self._brain.decide(goal, observation, history)
                self._recorder.agent_action(step, action, tier2=tier2)

                if action.type is AgentActionType.GIVE_UP:
                    reason = action.value or "no reason given"
                    self._recorder.agent_result(step, f"gave up: {reason}")
                    return EscalationResult(
                        ok=False,
                        detail=f"agent gave up at {step.value}: {reason}",
                        failure_code=FailureCode.AGENT_GAVE_UP,
                        used_screenshot=used_screenshot,
                    )

                if action.type is AgentActionType.REQUEST_SCREENSHOT:
                    recent_action_keys.append(_action_key(action))
                    screenshot_requests += 1
                    if screenshot_requests > _MAX_SCREENSHOT_REQUESTS:
                        streak = _action_streak(recent_action_keys)
                        if streak >= _LOOP_GIVE_UP_AFTER:
                            detail = (
                                f"agent stuck requesting screenshots at {step.value} "
                                f"without acting on the calendar"
                            )
                            self._recorder.agent_result(step, detail)
                            return EscalationResult(
                                ok=False,
                                detail=detail,
                                failure_code=FailureCode.AGENT_GAVE_UP,
                                used_screenshot=used_screenshot,
                            )
                        history.append(
                            "Screenshot already provided — stop requesting. Click the date "
                            "display, previous/next month arrows, or a calendar day cell."
                        )
                        continue
                    self._recorder.screenshot_tier(step, "requested by agent")
                    tier2_pending = True
                    history.append("screenshot requested; provided next turn")
                    continue

                blocked = blocked_action_reason(action, observation)
                if blocked is not None:
                    self._recorder.agent_blocked(step, blocked)
                    history.append(f"action refused by guard: {blocked}")
                    continue  # the agent may pick another action within budget

                try:
                    self._browser.act(action)
                    action_key = _action_key(action)
                    recent_action_keys.append(action_key)
                    history.append(f"did {action.type.value} ref={action.ref}")
                    consecutive_failures = 0
                except Exception as exc:
                    consecutive_failures += 1
                    history.append(f"action failed: {exc}")
                    if consecutive_failures >= _FAILURES_BEFORE_SCREENSHOT:
                        self._recorder.screenshot_tier(
                            step, f"{consecutive_failures} consecutive failed actions"
                        )
                        tier2_pending = True
                        consecutive_failures = 0
                    continue

                landed = blocked_url_reason(self._browser.observe().url)
                if landed is not None:
                    self._recorder.agent_blocked(step, landed)
                    return EscalationResult(
                        ok=False,
                        detail=landed,
                        failure_code=FailureCode.BLOCKED_ACTION,
                        used_screenshot=used_screenshot,
                    )

                if verify():
                    self._recorder.agent_result(step, "step completed by agent")
                    return EscalationResult(
                        ok=True,
                        detail=f"agent completed {step.value}",
                        used_screenshot=used_screenshot,
                    )
                history.append("step goal not yet met after that action")
                streak = _action_streak(recent_action_keys)
                if streak >= _LOOP_GIVE_UP_AFTER:
                    detail = (
                        f"agent stuck in loop at {step.value}: repeated "
                        f"{action_key} {_LOOP_GIVE_UP_AFTER} times without progress"
                    )
                    self._recorder.agent_result(step, detail)
                    return EscalationResult(
                        ok=False,
                        detail=detail,
                        failure_code=FailureCode.AGENT_GAVE_UP,
                        used_screenshot=used_screenshot,
                    )
                if streak >= _LOOP_HINT_AFTER:
                    history.append(_loop_nudge(step, action))
                    tier2_pending = True

        except BudgetExceeded as exc:
            self._recorder.agent_result(step, f"budget exceeded: {exc}")
            return EscalationResult(
                ok=False,
                detail=str(exc),
                failure_code=FailureCode.BUDGET_EXCEEDED,
                used_screenshot=used_screenshot,
            )

    def _with_screenshot(self, observation: Observation) -> Observation:
        from dataclasses import replace

        try:
            self.last_screenshot = self._browser.screenshot()
            return replace(observation, screenshot=self.last_screenshot)
        except Exception as exc:
            logger.warning("Screenshot capture failed, staying on tier 1: %s", exc)
            return observation


def _action_key(action: AgentAction) -> str:
    return f"{action.type.value}:{action.ref or ''}:{action.value or ''}"


def _action_streak(recent_keys: list[str]) -> int:
    if not recent_keys:
        return 0
    last = recent_keys[-1]
    streak = 0
    for key in reversed(recent_keys):
        if key != last:
            break
        streak += 1
    return streak


def _loop_nudge(step: JourneyStep, action: AgentAction) -> str:
    base = (
        "LOOP WARNING: that same action did not progress the goal. "
        "Try a DIFFERENT element — do not repeat it."
    )
    if step is JourneyStep.FILL_SEARCH and action.type is AgentActionType.FILL:
        return (
            f"{base} The destination is likely already set; open the DATE picker "
            "(click the date display or month arrows), select the correct check-in "
            "and check-out days, then close the calendar. Do not refill the search box."
        )
    if step is JourneyStep.FILL_SEARCH and action.type is AgentActionType.CLICK:
        return (
            f"{base} Try a different calendar control — month arrows, a day cell, "
            "or the date display — until check-in and check-out dates match the goal."
        )
    return base
