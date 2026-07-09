from __future__ import annotations

import logging
from collections.abc import Callable

from booksaver.application.ports import AgentBrain, InteractiveBrowser
from booksaver.domain.agent import (
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
