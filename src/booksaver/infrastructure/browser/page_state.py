from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from booksaver.application.browser_resilience import (
    DeterministicPageClassifier,
    PageClassificationEvidence,
    VisibleControlEvidence,
)
from booksaver.domain.agent import Observation, blocked_url_reason
from booksaver.domain.browser_resilience import (
    EvidenceCategory,
    FreshPageObservation,
    PageState,
    PageStateClassification,
    PageStateSource,
)

_BOOKING_HOST = "booking.com"
_CAPTCHA_TEXT = re.compile(
    r"(verify you are human|are you a human|hcaptcha|recaptcha|px-captcha)", re.I
)
_BOT_WALL_TEXT = re.compile(
    r"(unusual traffic|automated (?:traffic|requests)|access denied|robot check)",
    re.I,
)
_MFA_TEXT = re.compile(
    r"(verification code|security code|one[- ]time (?:code|password)|"
    r"two[- ]factor|passkey|approve (?:this )?(?:sign[- ]?in|login)|"
    r"check your (?:phone|email))",
    re.I,
)
_CREDENTIAL_TEXT = re.compile(
    r"(sign in to manage|log in to your account|sign in or register|"
    r"enter your password|create an account|continue with email)",
    re.I,
)
_WEAK_ACCOUNT_TEXT = re.compile(
    r"(Genius\s+(?:Level|discount|deal|rate)|Bookings\s*(?:&|and)\s*Trips|"
    r"Manage account|My account)",
    re.I,
)
_URL_OR_QUERY_TEXT = re.compile(
    r"(?:https?://\S+|www\.\S+|(?:^|\s)[?&][A-Za-z0-9_.~-]+=[^\s&]+)", re.I
)
_SECRET_TEXT = re.compile(
    r"(?:(?:cookie|authorization)\s*:\s*\S+|"
    r"bearer\s+[A-Za-z0-9._~-]{8,}|"
    r"(?:password|passwd|secret|api[_ -]?key)\s*[:=]\s*\S+)",
    re.I,
)
_MAX_CLASSIFIER_TEXT = 6_000
_MAX_CLASSIFIER_TITLE = 256
_MAX_CLASSIFIER_CONTROLS = 80

_CAPTCHA_SELECTORS = (
    "iframe[src*='captcha']",
    "[data-testid*='captcha']",
    "[class*='captcha']",
)
_MFA_SELECTORS = (
    "input[autocomplete='one-time-code']",
    "input[name*='otp']",
    "input[name*='verification']",
    "[data-testid*='passkey']",
)
_PASSWORD_SELECTORS = (
    "input[type='password']",
    "input[autocomplete='current-password']",
)
_IDENTITY_SELECTORS = (
    "input[autocomplete='username']",
    "input[type='email']",
)
_WEAK_ACCOUNT_SELECTORS = (
    '[data-testid="header-profile"]',
    '[data-testid="header-profile-menu"]',
    '[data-testid="header-bookings-link"]',
    'a[href*="myreservations"]',
)
_STRONG_INVENTORY_SELECTORS = (
    '[data-testid="bookings-list"]',
    '[data-testid="reservation-list"]',
    '[data-testid="my-bookings-list"]',
    '[data-testid="reservation-card"]',
    '[data-testid="booking-card"]',
    '[data-testid="bookings-empty-state"]',
    '[data-testid="reservation-empty-state"]',
    '[data-inventory-complete="true"]',
    "[data-inventory-scopes]",
)


def assess_page_state(page: Any, text: str | None = None) -> PageStateClassification:
    """Create one bounded, protected-first assessment of the current page.

    Only allowlisted evidence categories cross the infrastructure boundary. Raw
    page text, selectors, URLs, form values, and browser objects do not.
    """

    evidence: set[EvidenceCategory] = set()
    supported_states: set[PageState] = set()
    try:
        raw_url = str(page.url)
        visible_text = text if text is not None else page.locator("body").inner_text()
    except Exception:
        evidence.add(EvidenceCategory.OBSERVATION_UNAVAILABLE)
    else:
        destination_evidence = _destination_evidence(raw_url)
        if destination_evidence is not None:
            evidence.add(destination_evidence)
        if _BOT_WALL_TEXT.search(visible_text):
            evidence.add(EvidenceCategory.BOT_WALL)
        if _CAPTCHA_TEXT.search(visible_text) or _has_visible(
            page, _CAPTCHA_SELECTORS
        ):
            evidence.add(EvidenceCategory.CAPTCHA_CHALLENGE)
        if _MFA_TEXT.search(visible_text) or _has_visible(page, _MFA_SELECTORS):
            evidence.add(EvidenceCategory.MFA_CONTROL)
        credential_text = bool(_CREDENTIAL_TEXT.search(visible_text))
        if (
            credential_text
            or _has_visible(page, _PASSWORD_SELECTORS)
            or (
                (_is_auth_destination(raw_url) or credential_text)
                and _has_visible(page, _IDENTITY_SELECTORS)
            )
        ):
            evidence.add(EvidenceCategory.CREDENTIAL_CONTROL)
        if _WEAK_ACCOUNT_TEXT.search(visible_text) or _has_visible(
            page, _WEAK_ACCOUNT_SELECTORS
        ):
            evidence.add(EvidenceCategory.WEAK_ACCOUNT_CHROME)
        if _is_inventory_destination(raw_url) and _has_visible(
            page, _STRONG_INVENTORY_SELECTORS
        ):
            evidence.add(EvidenceCategory.SUPPORTED_INVENTORY_STRUCTURE)
            supported_states.add(PageState.INVENTORY)

    observation = FreshPageObservation(
        observation_id=uuid4().hex,
        observed_at=datetime.now(UTC),
        evidence=frozenset(evidence),
    )
    return DeterministicPageClassifier().classify(
        observation,
        supported_states=frozenset(supported_states),
    )


def assessment_proves_authenticated(
    assessment: PageStateClassification,
) -> bool:
    """Return true only for fresh, code-owned supported-page proof.

    In particular, a model's ``AUTHENTICATED_CANDIDATE`` classification can
    never authorize cookie capture or refresh.
    """

    return assessment.source is PageStateSource.DETERMINISTIC and assessment.state in {
        PageState.VERIFIED_AUTHENTICATED,
        PageState.INVENTORY,
    }


def assessment_is_protected(assessment: PageStateClassification) -> bool:
    return assessment.state in {
        PageState.OBSERVATION_UNAVAILABLE,
        PageState.AUTHENTICATION_REQUIRED,
        PageState.MFA_REQUIRED,
        PageState.CAPTCHA,
        PageState.BOT_WALL,
        PageState.EXTERNAL,
        PageState.PROHIBITED,
    }


def classification_inputs_from_observation(
    observation: Observation,
) -> tuple[FreshPageObservation, PageClassificationEvidence]:
    """Build safe protected-state and ephemeral model inputs from one observation."""

    observation_id = uuid4().hex
    evidence: set[EvidenceCategory] = set()
    destination_evidence = _destination_evidence(observation.url)
    if destination_evidence is not None:
        evidence.add(destination_evidence)
    visible_text = f"{observation.title}\n{observation.text}"
    if _BOT_WALL_TEXT.search(visible_text):
        evidence.add(EvidenceCategory.BOT_WALL)
    if _CAPTCHA_TEXT.search(visible_text):
        evidence.add(EvidenceCategory.CAPTCHA_CHALLENGE)
    if _MFA_TEXT.search(visible_text):
        evidence.add(EvidenceCategory.MFA_CONTROL)
    if _CREDENTIAL_TEXT.search(visible_text):
        evidence.add(EvidenceCategory.CREDENTIAL_CONTROL)
    if _WEAK_ACCOUNT_TEXT.search(visible_text):
        evidence.add(EvidenceCategory.WEAK_ACCOUNT_CHROME)
    if not evidence:
        evidence.add(EvidenceCategory.UNSUPPORTED_PAGE_STRUCTURE)

    fresh = FreshPageObservation(
        observation_id=observation_id,
        observed_at=datetime.now(UTC),
        evidence=frozenset(evidence),
    )
    if evidence.intersection(
        {
            EvidenceCategory.OBSERVATION_UNAVAILABLE,
            EvidenceCategory.CREDENTIAL_CONTROL,
            EvidenceCategory.MFA_CONTROL,
            EvidenceCategory.CAPTCHA_CHALLENGE,
            EvidenceCategory.BOT_WALL,
        }
    ):
        return fresh, PageClassificationEvidence(
            observation_id=observation_id,
            title="",
            visible_text="",
        )
    controls: list[VisibleControlEvidence] = []
    for element in observation.elements[:_MAX_CLASSIFIER_CONTROLS]:
        role = re.sub(r"[^a-z0-9_]", "_", element.role.casefold())[:64]
        label = _safe_classifier_text(element.label, 256)
        if role and label:
            controls.append(VisibleControlEvidence(role=role, label=label))
    ephemeral = PageClassificationEvidence(
        observation_id=observation_id,
        title=_safe_classifier_text(observation.title, _MAX_CLASSIFIER_TITLE),
        visible_text=_safe_classifier_text(
            observation.text, _MAX_CLASSIFIER_TEXT
        ),
        controls=tuple(controls),
    )
    return fresh, ephemeral


def _safe_classifier_text(value: str, limit: int) -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    normalized = _URL_OR_QUERY_TEXT.sub("[link]", normalized)
    normalized = _SECRET_TEXT.sub("[redacted]", normalized)
    return normalized[:limit]


def _destination_evidence(raw_url: str) -> EvidenceCategory | None:
    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        return EvidenceCategory.EXTERNAL_DESTINATION
    hostname = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme.casefold() != "https" or not (
        hostname == _BOOKING_HOST or hostname.endswith(f".{_BOOKING_HOST}")
    ):
        return EvidenceCategory.EXTERNAL_DESTINATION
    if blocked_url_reason(raw_url) is not None:
        return EvidenceCategory.PROHIBITED_OR_MUTATING_DESTINATION
    return None


def _is_inventory_destination(raw_url: str) -> bool:
    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        return False
    path = parsed.path.casefold()
    return any(
        marker in path for marker in ("myreservations", "mytrips", "/confirmation")
    )


def _is_auth_destination(raw_url: str) -> bool:
    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        return False
    hostname = (parsed.hostname or "").casefold().rstrip(".")
    path = parsed.path.casefold()
    return hostname == "account.booking.com" or any(
        marker in path for marker in ("/sign-in", "/signin", "/login")
    )


def _has_visible(page: Any, selectors: tuple[str, ...]) -> bool:
    for selector in selectors:
        try:
            locator = page.locator(selector)
            for index in range(locator.count()):
                if locator.nth(index).is_visible():
                    return True
        except Exception:
            continue
    return False
