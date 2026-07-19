"""US-023: [telegram_bot] config section parsing and validation."""

import pytest

from booksaver.application.load_config import load_config
from booksaver.domain.errors import ConfigValidationError
from booksaver.domain.value_objects import TelegramBotSettings


class DictSource:
    def __init__(self, data: dict) -> None:
        self._data = data

    def read(self) -> dict:
        return self._data


def _base(telegram_bot: dict | None = None) -> dict:
    data = {
        "schedule": {"check_interval": "6h"},
        "storage": {"data_directory": "~/.booksaver-test"},
    }
    if telegram_bot is not None:
        data["telegram_bot"] = telegram_bot
    return data


class TestTelegramBotConfig:
    def test_defaults_when_section_absent(self):
        cfg = load_config(DictSource(_base()))
        assert cfg.telegram_bot_settings.enabled is False
        assert cfg.telegram_bot_settings.owner_chat_id is None
        assert cfg.telegram_bot_settings.poll_timeout_seconds == 30

    def test_enabled_with_owner_chat_id_parses(self):
        cfg = load_config(
            DictSource(_base({"enabled": True, "owner_chat_id": 123456789}))
        )
        assert cfg.telegram_bot_settings.enabled is True
        assert cfg.telegram_bot_settings.owner_chat_id == 123456789

    def test_enabled_without_owner_chat_id_rejected(self):
        with pytest.raises(ConfigValidationError, match="owner_chat_id"):
            load_config(DictSource(_base({"enabled": True})))

    def test_poll_timeout_below_minimum_is_clamped_up(self):
        cfg = load_config(
            DictSource(_base({"enabled": True, "owner_chat_id": 1, "poll_timeout_seconds": 5}))
        )
        assert cfg.telegram_bot_settings.poll_timeout_seconds == 25

    def test_poll_timeout_above_maximum_is_clamped_down(self):
        cfg = load_config(
            DictSource(_base({"enabled": True, "owner_chat_id": 1, "poll_timeout_seconds": 999}))
        )
        assert cfg.telegram_bot_settings.poll_timeout_seconds == 50

    def test_poll_timeout_within_range_is_kept_as_is(self):
        cfg = load_config(
            DictSource(_base({"enabled": True, "owner_chat_id": 1, "poll_timeout_seconds": 40}))
        )
        assert cfg.telegram_bot_settings.poll_timeout_seconds == 40

    def test_non_numeric_owner_chat_id_rejected(self):
        with pytest.raises(ConfigValidationError, match="telegram_bot"):
            load_config(
                DictSource(_base({"enabled": True, "owner_chat_id": "not-a-number"}))
            )

    def test_disabled_ignores_missing_owner_chat_id(self):
        cfg = load_config(DictSource(_base({"enabled": False})))
        assert cfg.telegram_bot_settings.enabled is False
        assert cfg.telegram_bot_settings.owner_chat_id is None

    def test_access_mode_defaults_to_fixed_invite(self):
        cfg = load_config(DictSource(_base()))
        assert cfg.telegram_bot_settings.access_mode == "invite"

    def test_legacy_owner_access_mode_normalizes_to_invite(self):
        cfg = load_config(
            DictSource(_base({"enabled": True, "owner_chat_id": 1, "access_mode": "owner"}))
        )
        assert cfg.telegram_bot_settings.access_mode == "invite"

    def test_access_mode_invite_accepted(self):
        cfg = load_config(
            DictSource(
                _base({"enabled": True, "owner_chat_id": 1, "access_mode": "invite"})
            )
        )
        assert cfg.telegram_bot_settings.access_mode == "invite"

    def test_access_mode_open_rejected(self):
        with pytest.raises(ConfigValidationError, match="access_mode"):
            load_config(
                DictSource(_base({"enabled": True, "owner_chat_id": 1, "access_mode": "open"}))
            )

    def test_access_mode_unknown_value_rejected(self):
        with pytest.raises(ConfigValidationError, match="no public/open mode"):
            load_config(
                DictSource(
                    _base({"enabled": True, "owner_chat_id": 1, "access_mode": "public"})
                )
            )

    def test_rebook_confirm_timeout_seconds_defaults_to_600(self):
        cfg = load_config(DictSource(_base()))
        assert cfg.telegram_bot_settings.rebook_confirm_timeout_seconds == 600

    def test_rebook_confirm_timeout_seconds_parses_custom_value(self):
        cfg = load_config(
            DictSource(
                _base(
                    {
                        "enabled": True,
                        "owner_chat_id": 1,
                        "rebook_confirm_timeout_seconds": 120,
                    }
                )
            )
        )
        assert cfg.telegram_bot_settings.rebook_confirm_timeout_seconds == 120

    def test_rebook_confirm_timeout_seconds_too_low_rejected(self):
        with pytest.raises(ConfigValidationError, match="rebook_confirm_timeout_seconds"):
            load_config(
                DictSource(
                    _base(
                        {
                            "enabled": True,
                            "owner_chat_id": 1,
                            "rebook_confirm_timeout_seconds": 5,
                        }
                    )
                )
            )


class TestTelegramBotSettingsValueObject:
    def test_enabled_requires_owner_chat_id(self):
        with pytest.raises(ValueError, match="owner_chat_id"):
            TelegramBotSettings(enabled=True, owner_chat_id=None)

    def test_poll_timeout_out_of_range_rejected_by_direct_construction(self):
        with pytest.raises(ValueError, match="poll_timeout_seconds"):
            TelegramBotSettings(poll_timeout_seconds=10)

    def test_rebook_confirm_timeout_seconds_default_is_600(self):
        assert TelegramBotSettings().rebook_confirm_timeout_seconds == 600

    def test_rebook_confirm_timeout_seconds_rejected_below_minimum(self):
        with pytest.raises(ValueError, match="rebook_confirm_timeout_seconds"):
            TelegramBotSettings(rebook_confirm_timeout_seconds=10)

    def test_defaults_are_valid(self):
        settings = TelegramBotSettings()
        assert settings.enabled is False
        assert settings.poll_timeout_seconds == 30
        assert settings.access_mode == "invite"

    def test_legacy_owner_value_normalizes_on_direct_construction(self):
        assert TelegramBotSettings(access_mode="owner").access_mode == "invite"

    def test_open_access_mode_rejected_by_direct_construction(self):
        with pytest.raises(ValueError, match="no public/open mode"):
            TelegramBotSettings(access_mode="open")
