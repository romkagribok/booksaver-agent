"""Intent 026: [jev_comparison] parsing, defaults, and daemon activation."""

from __future__ import annotations

from typing import Any

import pytest

from booksaver.application.load_config import load_config
from booksaver.cli.commands import _make_jev_executor_factory
from booksaver.domain.errors import ConfigValidationError
from booksaver.domain.price_comparison import ComparisonParticipants


class DictSource:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def read(self) -> dict[str, Any]:
        return self._data


def _load(section: dict[str, Any] | None = None) -> Any:
    data: dict[str, Any] = {"storage": {"data_directory": "~/.booksaver-test"}}
    if section is not None:
        data["jev_comparison"] = section
    return load_config(DictSource(data))


def test_paired_mode_is_disabled_by_default() -> None:
    settings = _load().jev_comparison_settings
    assert not settings.enabled
    assert settings.participants is ComparisonParticipants.OWNER
    assert settings.max_daily_cost_nano_usd == 250_000_000


def test_explicit_activation_parses_caps() -> None:
    settings = _load(
        {
            "enabled": True,
            "participants": "all",
            "max_daily_cost_usd": "0.10",
            "max_calls_per_arm": 60,
            "arm_timeout_seconds": 120,
        }
    ).jev_comparison_settings
    assert settings.enabled and settings.admits(is_owner=False)
    assert settings.max_daily_cost_nano_usd == 100_000_000
    assert (settings.max_calls_per_arm, settings.arm_timeout_seconds) == (60, 120)


@pytest.mark.parametrize(
    "section",
    [
        {"model": "jev-latest"},
        {"enabled": "yes"},
        {"participants": "everyone"},
        {"max_daily_cost_usd": "5.00"},
        {"max_calls_per_arm": 500},
        {"arm_timeout_seconds": 600},
    ],
)
def test_invalid_settings_fail_closed(section: dict[str, Any]) -> None:
    with pytest.raises(ConfigValidationError, match="jev_comparison"):
        _load(section)


def test_daemon_enables_jev_only_with_config_and_its_own_secret(monkeypatch: Any) -> None:
    enabled = _load({"enabled": True})
    monkeypatch.delenv("BOOKSAVER_TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("BOOKSAVER_LLM_API_KEY", "anthropic-key-is-not-reused")
    assert _make_jev_executor_factory(enabled) is None
    monkeypatch.setenv("BOOKSAVER_TYPESAFE_API_KEY", "typesafe-key")
    assert _make_jev_executor_factory(_load()) is None
    assert callable(_make_jev_executor_factory(enabled))
