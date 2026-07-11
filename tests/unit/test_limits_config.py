"""US-031: [limits] config section parsing and validation."""

import pytest

from booksaver.application.load_config import load_config
from booksaver.domain.errors import ConfigValidationError
from booksaver.domain.value_objects import LimitsSettings


class DictSource:
    def __init__(self, data: dict) -> None:
        self._data = data

    def read(self) -> dict:
        return self._data


def _base(limits: dict | None = None) -> dict:
    data = {
        "schedule": {"check_interval": "6h"},
        "storage": {"data_directory": "~/.booksaver-test"},
    }
    if limits is not None:
        data["limits"] = limits
    return data


class TestLimitsConfig:
    def test_defaults_when_section_absent(self):
        cfg = load_config(DictSource(_base()))
        assert cfg.limits_settings.max_bookings_per_user == 3
        assert cfg.limits_settings.max_checks_per_user_per_day == 48
        assert cfg.limits_settings.max_llm_calls_per_user_per_day == 200
        assert cfg.limits_settings.messages_per_minute_per_chat == 20

    def test_overriding_all_fields_parses(self):
        cfg = load_config(
            DictSource(
                _base(
                    {
                        "max_bookings_per_user": 5,
                        "max_checks_per_user_per_day": 100,
                        "max_llm_calls_per_user_per_day": 500,
                        "messages_per_minute_per_chat": 10,
                    }
                )
            )
        )
        assert cfg.limits_settings.max_bookings_per_user == 5
        assert cfg.limits_settings.max_checks_per_user_per_day == 100
        assert cfg.limits_settings.max_llm_calls_per_user_per_day == 500
        assert cfg.limits_settings.messages_per_minute_per_chat == 10

    def test_zero_max_bookings_per_user_rejected(self):
        with pytest.raises(ConfigValidationError, match="limits"):
            load_config(DictSource(_base({"max_bookings_per_user": 0})))

    def test_negative_max_checks_per_user_per_day_rejected(self):
        with pytest.raises(ConfigValidationError, match="limits"):
            load_config(DictSource(_base({"max_checks_per_user_per_day": -1})))

    def test_non_numeric_value_rejected(self):
        with pytest.raises(ConfigValidationError, match="limits"):
            load_config(DictSource(_base({"max_llm_calls_per_user_per_day": "lots"})))


class TestLimitsSettingsValueObject:
    def test_defaults_are_valid(self):
        settings = LimitsSettings()
        assert settings.max_bookings_per_user == 3
        assert settings.max_checks_per_user_per_day == 48
        assert settings.max_llm_calls_per_user_per_day == 200
        assert settings.messages_per_minute_per_chat == 20

    def test_each_field_must_be_at_least_one(self):
        for field_name in (
            "max_bookings_per_user",
            "max_checks_per_user_per_day",
            "max_llm_calls_per_user_per_day",
            "messages_per_minute_per_chat",
        ):
            with pytest.raises(ValueError, match=field_name):
                LimitsSettings(**{field_name: 0})
