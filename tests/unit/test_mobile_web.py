from datetime import UTC, datetime

import pytest

from booksaver.domain.mobile_web import (
    AuthenticationEvidence,
    GeniusEvidence,
    MobileProfileId,
    MobileWebSettings,
    PriceSourceProvenance,
)

PIXEL_7 = {
    "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 7) Chrome/149 Mobile Safari/537.36",
    "viewport": {"width": 412, "height": 839},
    "device_scale_factor": 2.625,
    "is_mobile": True,
    "has_touch": True,
    "default_browser_type": "chromium",
}

PIXEL_5 = {
    **PIXEL_7,
    "viewport": {"width": 393, "height": 727},
}


def test_default_profile_is_android_like_chromium() -> None:
    settings = MobileWebSettings()
    options = settings.context_options(PIXEL_7)

    assert settings.profile_id is MobileProfileId.ANDROID_CHROMIUM
    assert settings.profile.browser_engine == "chromium"
    assert settings.profile.playwright_device_name == "Pixel 7"
    assert options["is_mobile"] is True
    assert options["has_touch"] is True
    assert "Android" in options["user_agent"]
    assert "Mobile" in options["user_agent"]
    assert options["viewport"] == {"width": 412, "height": 839}
    assert "default_browser_type" not in options


def test_allowlisted_compact_profile_and_locale_are_configurable() -> None:
    settings = MobileWebSettings.from_values(
        "android-chromium-compact", "de-DE", "Europe/Berlin"
    )
    options = settings.context_options(PIXEL_5)

    assert settings.profile_id is MobileProfileId.ANDROID_CHROMIUM_COMPACT
    assert settings.profile.playwright_device_name == "Pixel 5"
    assert options["viewport"] == {"width": 393, "height": 727}
    assert options["locale"] == "de-DE"
    assert options["timezone_id"] == "Europe/Berlin"


@pytest.mark.parametrize("profile", ["desktop", "Pixel 7", "iphone", ""])
def test_nonallowlisted_profile_is_rejected(profile: str) -> None:
    with pytest.raises(ValueError, match="Unknown mobile device_profile"):
        MobileWebSettings.from_values(profile)


def test_invalid_locale_and_timezone_are_rejected() -> None:
    with pytest.raises(ValueError, match="locale"):
        MobileWebSettings.from_values(locale="not a locale")
    with pytest.raises(ValueError, match="timezone"):
        MobileWebSettings.from_values(timezone_id="Mars/Olympus")


@pytest.mark.parametrize(
    "genius",
    [GeniusEvidence.APPLIED_OR_PRESENT, GeniusEvidence.NOT_OBSERVED],
)
def test_authenticated_price_provenance_accepts_valid_genius_states(
    genius: GeniusEvidence,
) -> None:
    provenance = PriceSourceProvenance(
        profile_id=MobileProfileId.ANDROID_CHROMIUM,
        session_revision_id="revision-7",
        genius_evidence=genius,
        observed_at=datetime.now(UTC),
    )

    redacted = provenance.as_redacted_dict()
    assert redacted["channel"] == "authenticated_mobile_web"
    assert redacted["authentication"] == "validated"
    assert redacted["genius_evidence"] == genius.value
    assert "cookie" not in " ".join(redacted).lower()


def test_price_provenance_fails_closed_for_ambiguous_context() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValueError, match="validated authentication"):
        PriceSourceProvenance(
            profile_id=MobileProfileId.ANDROID_CHROMIUM,
            session_revision_id="revision-7",
            authentication=AuthenticationEvidence.INDETERMINATE,
            genius_evidence=GeniusEvidence.NOT_OBSERVED,
            observed_at=now,
        )
    with pytest.raises(ValueError, match="indeterminate Genius"):
        PriceSourceProvenance(
            profile_id=MobileProfileId.ANDROID_CHROMIUM,
            session_revision_id="revision-7",
            genius_evidence=GeniusEvidence.INDETERMINATE,
            observed_at=now,
        )


def test_price_provenance_requires_nonsecret_revision_and_aware_time() -> None:
    with pytest.raises(ValueError, match="revision"):
        PriceSourceProvenance(
            profile_id=MobileProfileId.ANDROID_CHROMIUM,
            session_revision_id=" ",
            genius_evidence=GeniusEvidence.NOT_OBSERVED,
            observed_at=datetime.now(UTC),
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        PriceSourceProvenance(
            profile_id=MobileProfileId.ANDROID_CHROMIUM,
            session_revision_id="revision-7",
            genius_evidence=GeniusEvidence.NOT_OBSERVED,
            observed_at=datetime.now(),
        )
