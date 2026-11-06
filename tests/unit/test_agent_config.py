"""[agent] config parsing, and retired Claude/routing keys that are ignored (FR-14)."""

import warnings
from pathlib import Path

import pytest

from booksaver.application.load_config import load_config
from booksaver.domain.browser_executor import PriceExecutorKind
from booksaver.domain.errors import ConfigValidationError

RETIRED_WARNING = "Ignoring config keys that no longer have any effect"


class DictSource:
    def __init__(self, data: dict) -> None:
        self._data = data

    def read(self) -> dict:
        return self._data


def _base(agent: dict | None = None) -> dict:
    data: dict = {"storage": {"data_directory": "~/.booksaver-test"}}
    if agent is not None:
        data["agent"] = agent
    return data


def _load_recording(data: dict):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cfg = load_config(DictSource(data))
    return cfg, [str(w.message) for w in caught if RETIRED_WARNING in str(w.message)]


class TestAgentConfig:
    def test_defaults_when_section_absent(self):
        cfg, retired = _load_recording(_base())
        assert cfg.agent_settings.max_job_cost_micro_usd == 1_000_000
        assert retired == []

    def test_explicit_job_cost_is_exact(self):
        cfg = load_config(DictSource(_base({"max_job_cost_usd": "0.75"})))
        assert cfg.agent_settings.max_job_cost_micro_usd == 750_000

    @pytest.mark.parametrize("value", ["0", "1.01", "many"])
    def test_out_of_range_job_cost_rejected(self, value: str):
        with pytest.raises(ConfigValidationError, match="max_job_cost_usd"):
            load_config(DictSource(_base({"max_job_cost_usd": value})))


def test_production_config_loads_and_warns_once_naming_the_ignored_keys(
    tmp_path: Path,
) -> None:
    production = {
        "storage": {"data_directory": str(tmp_path)},
        "agent": {"max_steps": 25, "max_llm_calls": 20, "check_timeout_seconds": 360},
        "agentic_browser": {
            "price_executor": "jev",
            "routing": "consented_users",
            "disclosure_version": "typesafe-visible-booking-page-v1",
        },
        "limits": {
            "max_bookings_per_user": 5,
            "max_checks_per_user_per_day": 12,
            "max_llm_calls_per_user_per_day": 100,
            "messages_per_minute_per_chat": 15,
        },
        "jev_comparison": {
            "enabled": False,
            "participants": "all",
            "max_daily_cost_usd": "0.25",
        },
    }

    cfg, retired = _load_recording(production)

    assert len(retired) == 1
    for key in (
        "agent.check_timeout_seconds",
        "agent.max_llm_calls",
        "agent.max_steps",
        "agentic_browser.routing",
        "limits.max_llm_calls_per_user_per_day",
    ):
        assert key in retired[0]
    assert cfg.agentic_browser_settings.price_executor is PriceExecutorKind.JEV
    assert cfg.agentic_browser_settings.disclosure_version == "typesafe-visible-booking-page-v1"
    limits = cfg.limits_settings
    assert (
        limits.max_bookings_per_user,
        limits.max_checks_per_user_per_day,
        limits.messages_per_minute_per_chat,
    ) == (5, 12, 15)
    assert cfg.agent_settings.max_job_cost_micro_usd == 1_000_000
    assert cfg.jev_comparison_settings.enabled is False
    assert cfg.jev_comparison_settings.max_daily_cost_nano_usd == 250_000_000


def test_retired_model_and_inventory_routing_values_are_ignored_not_rejected() -> None:
    data = _base({"primary_model": "claude-fable-5", "max_steps": 0})
    data["extraction"] = {"model": "claude-sonnet-4-6"}
    data["agentic_browser"] = {"inventory_routing": "legacy", "routing": "maybe"}

    cfg, retired = _load_recording(data)

    assert len(retired) == 1
    for key in (
        "agent.primary_model",
        "agent.max_steps",
        "extraction.model",
        "agentic_browser.inventory_routing",
        "agentic_browser.routing",
    ):
        assert key in retired[0]
    assert cfg.agentic_browser_settings.price_executor is PriceExecutorKind.JEV
