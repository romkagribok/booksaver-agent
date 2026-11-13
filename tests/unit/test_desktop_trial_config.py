"""Intent 041: the desktop trial profile, its settings, and [desktop_trial] parsing."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from booksaver.application.load_config import load_config
from booksaver.domain.errors import ConfigValidationError
from booksaver.domain.mobile_web import DesktopTrialSettings, MobileProfileId, MobileWebSettings
from tests.unit.test_mobile_web import PIXEL_7

DESKTOP_CHROME = {
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "viewport": {"width": 1280, "height": 720},
    "device_scale_factor": 1,
    "is_mobile": False,
    "has_touch": False,
    "default_browser_type": "chromium",
}


class DictSource:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def read(self) -> dict[str, Any]:
        return self._data


def _load(**sections: dict[str, Any]) -> Any:
    return load_config(DictSource({"storage": {"data_directory": "~/.booksaver-test"}, **sections}))


def test_desktop_trial_profile_builds_non_mobile_context_options() -> None:
    settings = MobileWebSettings(profile_id=MobileProfileId.DESKTOP_CHROMIUM_TRIAL)
    options = settings.context_options(DESKTOP_CHROME)
    assert settings.profile.playwright_device_name == "Desktop Chrome"
    assert options["is_mobile"] is False and options["has_touch"] is False
    assert options["screen"] == {"width": 1280, "height": 720}
    assert "default_browser_type" not in options


def test_each_profile_rejects_the_other_kind_of_descriptor() -> None:
    with pytest.raises(ValueError, match="not desktop Chromium"):
        MobileWebSettings(profile_id=MobileProfileId.DESKTOP_CHROMIUM_TRIAL).context_options(
            PIXEL_7
        )
    with pytest.raises(ValueError, match="not Android mobile Chromium"):
        MobileWebSettings().context_options(DESKTOP_CHROME)


def test_config_cannot_select_the_desktop_trial_profile() -> None:
    with pytest.raises(ValueError, match="allowed: android-chromium, android-chromium-compact$"):
        MobileWebSettings.from_values("desktop-chromium-trial")
    with pytest.raises(ConfigValidationError, match="Unknown mobile device_profile"):
        _load(browser={"device_profile": "desktop-chromium-trial"})


def test_trial_is_off_by_default_and_parses_users_with_an_end_date() -> None:
    assert _load().desktop_trial_settings == DesktopTrialSettings()
    settings = _load(
        desktop_trial={"user_ids": [4], "ends_on": date(2026, 11, 20)}
    ).desktop_trial_settings
    assert settings.active_for(4, date(2026, 11, 19))
    assert not settings.active_for(4, date(2026, 11, 20))  # the end date itself is excluded
    assert not settings.active_for(1, date(2026, 11, 19))
    assert _load(
        desktop_trial={"user_ids": [4], "ends_on": "2026-11-20"}
    ).desktop_trial_settings == settings


@pytest.mark.parametrize(
    "section",
    [{"user_ids": [4]}, {"user_ids": "4", "ends_on": "2026-11-20"}, {"user_ids": [True]},
     {"user_ids": [4], "ends_on": "next week"}],
)
def test_invalid_trial_config_is_rejected(section: dict[str, Any]) -> None:
    with pytest.raises(ConfigValidationError, match="desktop_trial"):
        _load(desktop_trial=section)
