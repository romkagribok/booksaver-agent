"""US-021: [agent] config section parsing and validation."""

import pytest

from booksaver.application.load_config import load_config
from booksaver.domain.errors import ConfigValidationError


class DictSource:
    def __init__(self, data: dict) -> None:
        self._data = data

    def read(self) -> dict:
        return self._data


def _base(agent: dict | None = None) -> dict:
    data = {
        "schedule": {"check_interval": "6h"},
        "storage": {"data_directory": "~/.booksaver-test"},
    }
    if agent is not None:
        data["agent"] = agent
    return data


class TestAgentConfig:
    def test_defaults_when_section_absent(self):
        from booksaver.domain.agent import AgentSettings

        cfg = load_config(DictSource(_base()))
        defaults = AgentSettings()
        assert cfg.agent_settings.max_steps == defaults.max_steps
        assert cfg.agent_settings.max_llm_calls == 20
        assert cfg.agent_settings.check_timeout_seconds == 180
        assert cfg.agent_settings.model == "claude-sonnet-4-6"
        assert cfg.agent_settings.max_recovery_calls_per_step == 4
        assert cfg.agent_settings.recovery_timeout_seconds == 60
        assert cfg.agent_settings.screenshot_after_no_progress == 2
        assert cfg.agent_settings.max_semantic_action_executions == 2

    def test_explicit_values_parsed(self):
        cfg = load_config(
            DictSource(
                _base({
                    "max_steps": 5,
                    "max_llm_calls": 8,
                    "check_timeout_seconds": 90,
                    "model": "claude-haiku-4-5",
                    "max_recovery_calls_per_step": 3,
                    "recovery_timeout_seconds": 45,
                    "screenshot_after_no_progress": 1,
                    "max_semantic_action_executions": 1,
                })
            )
        )
        assert cfg.agent_settings.max_steps == 5
        assert cfg.agent_settings.max_llm_calls == 8
        assert cfg.agent_settings.check_timeout_seconds == 90
        assert cfg.agent_settings.model == "claude-haiku-4-5"
        assert cfg.agent_settings.max_recovery_calls_per_step == 3
        assert cfg.agent_settings.recovery_timeout_seconds == 45
        assert cfg.agent_settings.screenshot_after_no_progress == 1
        assert cfg.agent_settings.max_semantic_action_executions == 1

    def test_partial_section_keeps_other_defaults(self):
        cfg = load_config(DictSource(_base({"max_steps": 30})))
        assert cfg.agent_settings.max_steps == 30
        assert cfg.agent_settings.max_llm_calls == 20

    def test_zero_steps_rejected(self):
        with pytest.raises(ConfigValidationError, match="max_steps"):
            load_config(DictSource(_base({"max_steps": 0})))

    def test_out_of_range_timeout_rejected(self):
        with pytest.raises(ConfigValidationError, match="check_timeout_seconds"):
            load_config(DictSource(_base({"check_timeout_seconds": 5})))

    def test_non_numeric_value_rejected(self):
        with pytest.raises(ConfigValidationError, match="agent"):
            load_config(DictSource(_base({"max_steps": "many"})))

    @pytest.mark.parametrize(
        "field",
        [
            "max_recovery_calls_per_step",
            "recovery_timeout_seconds",
            "screenshot_after_no_progress",
            "max_semantic_action_executions",
        ],
    )
    def test_non_positive_recovery_value_rejected(self, field: str):
        with pytest.raises(ConfigValidationError, match=field):
            load_config(DictSource(_base({field: 0})))
