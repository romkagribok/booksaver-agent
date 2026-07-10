"""Tool-call → AgentAction mapping for the Anthropic agent brain (no network)."""

from booksaver.domain.agent import AgentActionType
from booksaver.infrastructure.llm.anthropic_adapter import action_from_tool_call


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

    def test_give_up_with_reason(self):
        action = action_from_tool_call("give_up", {"reason": "captcha"})
        assert action.type is AgentActionType.GIVE_UP
        assert action.value == "captcha"

    def test_unknown_tool_becomes_give_up(self):
        action = action_from_tool_call("evaluate_js", {"code": "alert(1)"})
        assert action.type is AgentActionType.GIVE_UP
        assert "unknown tool" in action.value
