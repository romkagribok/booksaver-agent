from datetime import timedelta
from pathlib import Path

import pytest

from booksaver.application.load_config import load_config
from booksaver.domain.errors import ConfigValidationError
from booksaver.infrastructure.config.toml_env_source import TomlEnvConfigSource


def _write_config(path: Path, content: str) -> TomlEnvConfigSource:
    path.write_text(content)
    return TomlEnvConfigSource(path)


class TestLoadConfig:
    def test_valid_randomized_schedule_config_loads(self, tmp_path):
        source = _write_config(
            tmp_path / "config.toml",
            f'''[schedule]
checks_per_booking_per_day = 3
minimum_spacing = "2h"
missed_run_grace = "1h"

[storage]
data_directory = "{tmp_path}"
''',
        )
        cfg = load_config(source)
        assert cfg.check_interval is None
        assert cfg.schedule_settings.checks_per_booking_per_day == 3
        assert cfg.schedule_settings.minimum_spacing == timedelta(hours=2)
        assert cfg.schedule_settings.missed_run_grace == timedelta(hours=1)
        assert cfg.data_directory.path == tmp_path.resolve()
        assert cfg.mobile_web_settings.profile_id.value == "android-chromium"
        assert cfg.mobile_web_settings.profile.playwright_device_name == "Pixel 7"

    def test_browser_mobile_profile_is_configurable(self, tmp_path):
        source = _write_config(
            tmp_path / "config.toml",
            f'''[schedule]
check_interval = "6h"

[storage]
data_directory = "{tmp_path}"

[browser]
device_profile = "android-chromium-compact"
locale = "fr-FR"
timezone_id = "Europe/Paris"
''',
        )

        cfg = load_config(source)

        assert cfg.mobile_web_settings.profile_id.value == "android-chromium-compact"
        assert cfg.mobile_web_settings.locale == "fr-FR"
        assert cfg.mobile_web_settings.timezone_id == "Europe/Paris"

    def test_browser_desktop_or_unknown_profile_is_rejected(self, tmp_path):
        source = _write_config(
            tmp_path / "config.toml",
            f'''[schedule]
check_interval = "6h"

[storage]
data_directory = "{tmp_path}"

[browser]
device_profile = "desktop-chromium"
''',
        )

        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(source)

        assert any("device_profile" in error for error in exc_info.value.errors)

    def test_remote_auth_loads_only_with_https_and_enabled_telegram(self, tmp_path):
        source = _write_config(
            tmp_path / "config.toml",
            f'''[schedule]
check_interval = "6h"

[storage]
data_directory = "{tmp_path}"

[telegram_bot]
enabled = true
owner_chat_id = 123

[remote_auth]
enabled = true
public_url = "https://connect.example.test"
session_timeout_seconds = 900
''',
        )

        cfg = load_config(source)

        assert cfg.remote_auth_settings.enabled is True
        assert cfg.remote_auth_settings.base_url == "https://connect.example.test"
        assert cfg.remote_auth_settings.session_timeout_seconds == 900

    @pytest.mark.parametrize(
        "telegram,public_url",
        [
            ("", "https://connect.example.test"),
            ("[telegram_bot]\nenabled = true\nowner_chat_id = 123", "http://unsafe.test"),
            (
                "[telegram_bot]\nenabled = true\nowner_chat_id = 123",
                "https://connect.example.test/path",
            ),
        ],
    )
    def test_remote_auth_rejects_unsafe_or_unbound_configuration(
        self,
        tmp_path,
        telegram,
        public_url,
    ):
        source = _write_config(
            tmp_path / "config.toml",
            f'''[schedule]
check_interval = "6h"

[storage]
data_directory = "{tmp_path}"

{telegram}

[remote_auth]
enabled = true
public_url = "{public_url}"
''',
        )

        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(source)

        assert any("remote_auth" in error for error in exc_info.value.errors)

    def test_missing_schedule_section_uses_randomized_defaults(self, tmp_path):
        source = _write_config(
            tmp_path / "config.toml",
            f'[storage]\ndata_directory = "{tmp_path}"\n',
        )
        cfg = load_config(source)
        assert cfg.schedule_settings.checks_per_booking_per_day == 3
        assert cfg.schedule_settings.minimum_spacing == timedelta(hours=2)
        assert cfg.schedule_settings.missed_run_grace == timedelta(hours=1)

    def test_missing_data_directory_fails(self, tmp_path):
        source = _write_config(
            tmp_path / "config.toml",
            '[schedule]\ncheck_interval = "6h"\n',
        )
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(source)
        assert any("data_directory" in e for e in exc_info.value.errors)

    def test_all_errors_collected_not_fail_fast(self, tmp_path):
        source = _write_config(tmp_path / "config.toml", "# empty config\n")
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(source)
        errors = exc_info.value.errors
        assert len(errors) == 1, f"expected 1 error, got: {errors}"
        joined = " ".join(errors)
        assert "data_directory" in joined

    def test_invalid_interval_format_fails(self, tmp_path):
        source = _write_config(
            tmp_path / "config.toml",
            f'[schedule]\ncheck_interval = "2hours"\n\n[storage]\ndata_directory = "{tmp_path}"\n',
        )
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(source)
        assert any("check_interval" in e for e in exc_info.value.errors)

    def test_interval_below_minimum_fails(self, tmp_path):
        source = _write_config(
            tmp_path / "config.toml",
            f'[schedule]\ncheck_interval = "5m"\n\n[storage]\ndata_directory = "{tmp_path}"\n',
        )
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(source)
        assert any("check_interval" in e for e in exc_info.value.errors)

    def test_legacy_interval_loads_defaults_and_warns_once(self, tmp_path):
        source = _write_config(
            tmp_path / "config.toml",
            f'[schedule]\ncheck_interval = "6h"\n\n[storage]\ndata_directory = "{tmp_path}"\n',
        )
        with pytest.warns(UserWarning, match="deprecated and ignored") as recorded:
            cfg = load_config(source)
        assert len(recorded) == 1
        assert cfg.check_interval is not None
        assert str(cfg.check_interval) == "6h"
        assert cfg.schedule_settings.checks_per_booking_per_day == 3

    def test_new_schedule_keys_win_when_legacy_interval_is_present(self, tmp_path):
        source = _write_config(
            tmp_path / "config.toml",
            f'''[schedule]
check_interval = "12h"
checks_per_booking_per_day = 4
minimum_spacing = "1h"
missed_run_grace = "30m"

[storage]
data_directory = "{tmp_path}"
''',
        )
        with pytest.warns(UserWarning, match="deprecated and ignored"):
            cfg = load_config(source)
        assert cfg.schedule_settings.checks_per_booking_per_day == 4
        assert cfg.schedule_settings.minimum_spacing == timedelta(hours=1)
        assert cfg.schedule_settings.missed_run_grace == timedelta(minutes=30)

    @pytest.mark.parametrize(
        "schedule_line",
        [
            "checks_per_booking_per_day = 0",
            'minimum_spacing = "0m"',
            'missed_run_grace = "0m"',
            'checks_per_booking_per_day = 3\nminimum_spacing = "8h"',
        ],
    )
    def test_invalid_randomized_schedule_is_rejected(self, tmp_path, schedule_line):
        source = _write_config(
            tmp_path / "config.toml",
            f'[schedule]\n{schedule_line}\n\n[storage]\ndata_directory = "{tmp_path}"\n',
        )
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(source)
        assert any("schedule" in error for error in exc_info.value.errors)

    def test_missing_config_file_raises(self, tmp_path):
        source = TomlEnvConfigSource(tmp_path / "nonexistent.toml")
        with pytest.raises(FileNotFoundError):
            load_config(source)

    def test_notification_settings_optional(self, tmp_path):
        source = _write_config(
            tmp_path / "config.toml",
            f'[schedule]\ncheck_interval = "1h"\n\n[storage]\ndata_directory = "{tmp_path}"\n',
        )
        cfg = load_config(source)
        assert cfg.notification_settings.email is None
        assert cfg.notification_settings.telegram_chat_id is None
