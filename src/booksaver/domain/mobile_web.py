from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class MobileProfileId(StrEnum):
    """Allowlisted mobile Chromium identities supported by BookSaver."""

    ANDROID_CHROMIUM = "android-chromium"
    ANDROID_CHROMIUM_COMPACT = "android-chromium-compact"


@dataclass(frozen=True)
class MobileWebProfile:
    profile_id: MobileProfileId
    playwright_device_name: str
    browser_engine: str = "chromium"

    def __post_init__(self) -> None:
        if self.browser_engine != "chromium":
            raise ValueError("Mobile web monitoring requires Chromium")
        if not self.playwright_device_name.strip():
            raise ValueError("playwright_device_name must be non-empty")

    def context_options(
        self,
        device_descriptor: dict[str, Any],
        *,
        locale: str,
        timezone_id: str,
    ) -> dict[str, Any]:
        """Validate and specialize Playwright's version-matched device descriptor."""
        options = {
            key: value
            for key, value in device_descriptor.items()
            if key != "default_browser_type"
        }
        user_agent = str(options.get("user_agent", ""))
        viewport = options.get("viewport")
        if (
            "Android" not in user_agent
            or "Mobile" not in user_agent
            or options.get("is_mobile") is not True
            or options.get("has_touch") is not True
            or not isinstance(viewport, dict)
        ):
            raise ValueError("Playwright device descriptor is not Android mobile Chromium")
        options.update(
            screen=dict(viewport),
            locale=locale,
            timezone_id=timezone_id,
        )
        return options

_PROFILES: dict[MobileProfileId, MobileWebProfile] = {
    MobileProfileId.ANDROID_CHROMIUM: MobileWebProfile(
        profile_id=MobileProfileId.ANDROID_CHROMIUM,
        playwright_device_name="Pixel 7",
    ),
    MobileProfileId.ANDROID_CHROMIUM_COMPACT: MobileWebProfile(
        profile_id=MobileProfileId.ANDROID_CHROMIUM_COMPACT,
        playwright_device_name="Pixel 5",
    ),
}

_LOCALE_RE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


@dataclass(frozen=True)
class MobileWebSettings:
    """Non-secret configuration for every monitored Playwright context."""

    profile_id: MobileProfileId = MobileProfileId.ANDROID_CHROMIUM
    locale: str = "en-US"
    timezone_id: str = "UTC"
    profile: MobileWebProfile = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not _LOCALE_RE.fullmatch(self.locale):
            raise ValueError(f"Invalid browser locale: {self.locale!r}")
        try:
            ZoneInfo(self.timezone_id)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Invalid browser timezone: {self.timezone_id!r}") from exc
        object.__setattr__(self, "profile", _PROFILES[self.profile_id])

    @classmethod
    def from_values(
        cls,
        profile_id: str = MobileProfileId.ANDROID_CHROMIUM.value,
        locale: str = "en-US",
        timezone_id: str = "UTC",
    ) -> MobileWebSettings:
        try:
            selected = MobileProfileId(profile_id.strip().lower())
        except ValueError as exc:
            allowed = ", ".join(item.value for item in MobileProfileId)
            raise ValueError(
                f"Unknown mobile device_profile {profile_id!r}; allowed: {allowed}"
            ) from exc
        return cls(profile_id=selected, locale=locale.strip(), timezone_id=timezone_id.strip())

    def context_options(self, device_descriptor: dict[str, Any]) -> dict[str, Any]:
        return self.profile.context_options(
            device_descriptor,
            locale=self.locale,
            timezone_id=self.timezone_id,
        )


class AuthenticationEvidence(StrEnum):
    VALIDATED = "validated"
    SIGNED_OUT = "signed_out"
    INDETERMINATE = "indeterminate"


class GeniusEvidence(StrEnum):
    APPLIED_OR_PRESENT = "applied_or_present"
    NOT_OBSERVED = "not_observed"
    INDETERMINATE = "indeterminate"


class PriceSourceChannel(StrEnum):
    AUTHENTICATED_MOBILE_WEB = "authenticated_mobile_web"


@dataclass(frozen=True)
class PriceSourceProvenance:
    """Non-secret evidence required for an accepted mobile-web price."""

    profile_id: MobileProfileId
    session_revision_id: str
    genius_evidence: GeniusEvidence
    observed_at: datetime
    authentication: AuthenticationEvidence = AuthenticationEvidence.VALIDATED
    channel: PriceSourceChannel = PriceSourceChannel.AUTHENTICATED_MOBILE_WEB

    def __post_init__(self) -> None:
        if self.authentication is not AuthenticationEvidence.VALIDATED:
            raise ValueError("Accepted price provenance requires validated authentication")
        if self.genius_evidence is GeniusEvidence.INDETERMINATE:
            raise ValueError("Accepted price provenance cannot use indeterminate Genius evidence")
        if not self.session_revision_id.strip():
            raise ValueError("session_revision_id must be non-empty")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")

    def as_redacted_dict(self) -> dict[str, str]:
        return {
            "channel": self.channel.value,
            "profile_id": self.profile_id.value,
            "session_revision_id": self.session_revision_id,
            "authentication": self.authentication.value,
            "genius_evidence": self.genius_evidence.value,
            "observed_at": self.observed_at.isoformat(),
        }
