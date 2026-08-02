"""Provider rendering and tool mapping for the Anthropic agent brain (offline)."""

from types import SimpleNamespace

import pytest
from anthropic.types import ToolUseBlock

from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    AgentHistoryEvent,
    AgentHistoryOutcome,
    AgentStopReason,
    AgentTurnContext,
    ElementInfo,
    LLMUsage,
    Observation,
)
from booksaver.infrastructure.llm.anthropic_adapter import (
    AGENT_PROMPT_VERSION,
    AnthropicAgentBrain,
    LLMProviderError,
    action_from_tool_call,
    render_agent_turn_context,
)


class TestActionFromToolCall:
    def test_click(self):
        action = action_from_tool_call("click", {"ref": "e7"})
        assert action.type is AgentActionType.CLICK
        assert action.ref == "e7"

    def test_fill(self):
        action = action_from_tool_call("fill", {"ref": "e2", "text": "Hotel Test"})
        assert action.type is AgentActionType.FILL
        assert (action.ref, action.value) == ("e2", "Hotel Test")

    def test_select(self):
        action = action_from_tool_call("select", {"ref": "e3", "value": "2"})
        assert action.type is AgentActionType.SELECT
        assert (action.ref, action.value) == ("e3", "2")

    def test_scroll(self):
        action = action_from_tool_call("scroll", {"direction": "down"})
        assert action.type is AgentActionType.SCROLL
        assert action.value == "down"

    def test_request_screenshot(self):
        action = action_from_tool_call("request_screenshot", {})
        assert action.type is AgentActionType.REQUEST_SCREENSHOT

    def test_give_up_requires_coded_reason_and_explanation(self):
        action = action_from_tool_call(
            "give_up",
            {"reason_code": "captcha", "explanation": "Captcha challenge is visible."},
        )
        assert action.type is AgentActionType.GIVE_UP
        assert action.stop_reason is AgentStopReason.CAPTCHA
        assert action.value == "Captcha challenge is visible."

    def test_malformed_give_up_becomes_provider_error(self):
        action = action_from_tool_call("give_up", {"reason": "captcha"})
        assert action.type is AgentActionType.GIVE_UP
        assert action.stop_reason is AgentStopReason.PROVIDER_ERROR

    def test_model_cannot_claim_controller_owned_provider_error(self):
        action = action_from_tool_call(
            "give_up",
            {
                "reason_code": "provider_error",
                "explanation": "The provider failed.",
            },
        )
        assert action.type is AgentActionType.GIVE_UP
        assert action.stop_reason is AgentStopReason.PROVIDER_ERROR
        assert action.value == "model supplied a controller-owned stop reason"

    def test_missing_action_ref_becomes_provider_error(self):
        action = action_from_tool_call("click", {})
        assert action.type is AgentActionType.GIVE_UP
        assert action.stop_reason is AgentStopReason.PROVIDER_ERROR

    def test_unknown_tool_becomes_give_up(self):
        action = action_from_tool_call("evaluate_js", {"code": "alert(1)"})
        assert action.type is AgentActionType.GIVE_UP
        assert "unknown tool" in action.value
        assert action.stop_reason is AgentStopReason.PROVIDER_ERROR


def _context(*, screenshot_forced: bool = True) -> AgentTurnContext:
    observation = Observation(
        url="https://www.booking.com/mytrips",
        title="My trips",
        text="One upcoming trip",
        elements=(ElementInfo("e9", "link", "Trip details", "/mytrips/1"),),
        screenshot=b"png" if screenshot_forced else None,
        popup_count=1,
        popup_urls=("https://www.booking.com/hotel/example",),
    )
    event = AgentHistoryEvent(
        outcome=AgentHistoryOutcome.EXECUTED,
        detail="Click returned normally but the verifier still failed.",
        action=AgentAction(type=AgentActionType.CLICK, ref="e1"),
        semantic_target="click|link|trip details|/mytrips/1",
        popup_opened=True,
    )
    return AgentTurnContext(
        goal="Open the reservation detail view.",
        verification_condition="A reservation detail heading is visible.",
        observation=observation,
        history=(event,),
        llm_calls_used=2,
        max_llm_calls=4,
        no_progress_count=2,
        screenshot_forced=screenshot_forced,
        seconds_remaining=41.5,
    )


def test_turn_context_renders_structured_progress_and_remaining_policy() -> None:
    rendered = render_agent_turn_context(_context())

    assert "A reservation detail heading is visible." in rendered
    assert "semantic_target=click|link|trip details|/mytrips/1" in rendered
    assert "made_progress=no" in rendered
    assert "popup_opened=yes" in rendered
    assert "popup is unavailable to your actions" in rendered
    assert "provider calls used: 2/4" in rendered
    assert "provider calls remaining after this turn: 1" in rendered
    assert "recovery time remaining: 41.5s" in rendered
    assert "visual reorientation: yes" in rendered


def test_agent_metadata_is_redacted_and_versioned() -> None:
    brain = AnthropicAgentBrain.__new__(AnthropicAgentBrain)
    brain._model = "test-model"  # noqa: SLF001

    assert brain.provider == "anthropic"
    assert brain.role == "navigation_agent"
    assert brain.model == "test-model"
    assert brain.prompt_version == AGENT_PROMPT_VERSION


def test_provider_exception_becomes_coded_provider_error() -> None:
    class _Messages:
        def create(self, **kwargs):
            raise TimeoutError("sensitive provider detail")

    brain = AnthropicAgentBrain.__new__(AnthropicAgentBrain)
    brain._client = SimpleNamespace(messages=_Messages())  # noqa: SLF001
    brain._model = "test-model"  # noqa: SLF001
    brain.last_usage = LLMUsage(99, 99)

    with pytest.raises(LLMProviderError) as raised:
        brain.decide(_context(screenshot_forced=False))

    assert str(raised.value) == "agent provider call failed"
    assert "sensitive provider detail" not in str(raised.value)
    assert brain.last_usage is None


def test_malformed_provider_tool_call_becomes_typed_schema_error() -> None:
    class _Messages:
        def create(self, **kwargs):
            return SimpleNamespace(
                content=[
                    ToolUseBlock(
                        type="tool_use",
                        id="tool-1",
                        name="click",
                        input={},
                    )
                ],
                usage={"input_tokens": 123, "output_tokens": 17},
            )

    brain = AnthropicAgentBrain.__new__(AnthropicAgentBrain)
    brain._client = SimpleNamespace(messages=_Messages())  # noqa: SLF001
    brain._model = "test-model"  # noqa: SLF001

    with pytest.raises(LLMProviderError) as raised:
        brain.decide(_context(screenshot_forced=False))

    assert str(raised.value) == "agent provider schema validation failed"
    assert brain.last_usage == LLMUsage(input_tokens=123, output_tokens=17)


def test_agent_brain_records_usage_for_successful_call() -> None:
    calls = []

    class _Messages:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                content=[
                    ToolUseBlock(
                        type="tool_use",
                        id="tool-1",
                        name="click",
                        input={"ref": "e9"},
                    )
                ],
                usage=SimpleNamespace(input_tokens=400, output_tokens=25),
            )

    brain = AnthropicAgentBrain.__new__(AnthropicAgentBrain)
    brain._client = SimpleNamespace(messages=_Messages())  # noqa: SLF001
    brain._model = "test-model"  # noqa: SLF001

    action = brain.decide(_context(screenshot_forced=False))

    assert action == AgentAction(type=AgentActionType.CLICK, ref="e9")
    assert brain.last_usage == LLMUsage(input_tokens=400, output_tokens=25)
    assert calls[0]["timeout"] == 20.0
