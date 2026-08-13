"""Strict loader for synthetic browser-recovery replay fixtures.

Fixtures are data-only state machines. They contain bounded visible observations and
expected semantic decisions, never browser handles, database identifiers, or prompts.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    AgentDiagnosisReason,
    AgentHistoryEvent,
    AgentHistoryOutcome,
    AgentStopReason,
    ElementInfo,
    Observation,
)

_SCHEMA_VERSION = 1
_MAX_FIXTURE_BYTES = 256 * 1024
_MAX_STATES = 20
_MAX_ELEMENTS = 100
_MAX_TEXT_CHARS = 30_000
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{2,79}$")
_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_EMAIL_PATTERN = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_PHONE_PATTERN = re.compile(r"(?<!\w)\+?\d(?:[ ().-]*\d){9,}(?!\w)")
_LONG_NUMBER_PATTERN = re.compile(r"(?<!\d)\d{7,}(?!\d)")
_LONG_TOKEN_PATTERN = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{32,}(?![A-Za-z0-9_-])")
_SECRET_PATTERN = re.compile(
    r"(?:bearer\s+[A-Za-z0-9._~-]+|sk-[A-Za-z0-9_-]+|-----BEGIN [A-Z ]+PRIVATE KEY-----)",
    re.IGNORECASE,
)
_SENSITIVE_WORDING = re.compile(
    r"\b(?:api[ -]?key|authorization|cookie|credit card|card number|confirmation (?:id|number)|"
    r"guest name|localstorage|password|phone number|session (?:id|token))\b",
    re.IGNORECASE,
)


class ReplayFixtureError(ValueError):
    """A replay fixture is unsafe or does not satisfy the curated schema."""


def curated_fixture_directory() -> Path:
    """Return the packaged, privacy-reviewed replay fixture directory."""
    return Path(__file__).with_name("fixture_data")


@dataclass(frozen=True)
class ActionExpectation:
    action_type: AgentActionType
    role: str | None = None
    label: str | None = None
    href: str | None = None
    value: str | None = None
    stop_reason: AgentStopReason | None = None
    diagnosis_reason: AgentDiagnosisReason | None = None

    def matches(self, action: AgentAction, observation: Observation) -> bool:
        if action.type is not self.action_type:
            return False
        if self.stop_reason is not None and action.stop_reason is not self.stop_reason:
            return False
        if (
            self.diagnosis_reason is not None
            and action.diagnosis_reason is not self.diagnosis_reason
        ):
            return False
        if self.value is not None and _normalize(action.value) != _normalize(self.value):
            return False
        if self.role is None and self.label is None and self.href is None:
            return True
        element = next((item for item in observation.elements if item.ref == action.ref), None)
        if element is None:
            return False
        return (
            (self.role is None or _normalize(element.role) == _normalize(self.role))
            and (self.label is None or _normalize(element.label) == _normalize(self.label))
            and (self.href is None or element.href == self.href)
        )


@dataclass(frozen=True)
class ReplayTransition:
    expectation: ActionExpectation
    next_state: str | None = None
    terminal_category: str | None = None


@dataclass(frozen=True)
class ReplayState:
    state_id: str
    observation: Observation
    history: tuple[AgentHistoryEvent, ...]
    no_progress_count: int
    screenshot_forced: bool
    transitions: tuple[ReplayTransition, ...]


@dataclass(frozen=True)
class ReplayFixture:
    fixture_id: str
    journey: str
    step: str
    goal: str
    verification_condition: str
    start_state: str
    max_calls: int
    timeout_seconds: float
    terminal_diagnosis_required: bool
    expected_outcome_categories: frozenset[str]
    states: tuple[ReplayState, ...]

    def state(self, state_id: str) -> ReplayState:
        state = next((item for item in self.states if item.state_id == state_id), None)
        if state is None:
            raise ReplayFixtureError(
                f"fixture {self.fixture_id!r} references unknown state {state_id!r}"
            )
        return state


def load_fixture(path: Path) -> ReplayFixture:
    """Load and validate one sanitized replay fixture from ``path``."""
    try:
        if path.stat().st_size > _MAX_FIXTURE_BYTES:
            raise ReplayFixtureError(f"fixture exceeds {_MAX_FIXTURE_BYTES} bytes")
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReplayFixtureError(f"could not read fixture {path.name!r}: {exc}") from exc
    try:
        raw: object = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ReplayFixtureError(f"invalid JSON in fixture {path.name!r}: {exc.msg}") from exc

    _reject_sensitive_data(raw, "$.")
    root = _mapping(raw, "$")
    _keys(
        root,
        "$",
        required={
            "schema_version",
            "id",
            "journey",
            "step",
            "goal",
            "verification_condition",
            "start_state",
            "max_calls",
            "timeout_seconds",
            "expected_outcome_categories",
            "states",
        },
        optional={"terminal_diagnosis_required"},
    )
    if _integer(root["schema_version"], "$.schema_version") != _SCHEMA_VERSION:
        raise ReplayFixtureError(f"$.schema_version must be {_SCHEMA_VERSION}")

    fixture_id = _identifier(root["id"], "$.id")
    journey = _identifier(root["journey"], "$.journey")
    step = _identifier(root["step"], "$.step")
    goal = _bounded_string(root["goal"], "$.goal", 500)
    verification = _bounded_string(
        root["verification_condition"], "$.verification_condition", 500
    )
    start_state = _identifier(root["start_state"], "$.start_state")
    max_calls = _integer(root["max_calls"], "$.max_calls")
    if not 1 <= max_calls <= 20:
        raise ReplayFixtureError("$.max_calls must be between 1 and 20")
    timeout_seconds = _number(root["timeout_seconds"], "$.timeout_seconds")
    if not 0 < timeout_seconds <= 300:
        raise ReplayFixtureError("$.timeout_seconds must be greater than 0 and at most 300")
    terminal_diagnosis_required = _optional_boolean(
        root.get("terminal_diagnosis_required"),
        "$.terminal_diagnosis_required",
    )

    expected_raw = _sequence(root["expected_outcome_categories"], "$.expected_outcome_categories")
    expected_categories = frozenset(
        _identifier(value, f"$.expected_outcome_categories[{index}]")
        for index, value in enumerate(expected_raw)
    )
    if not expected_categories:
        raise ReplayFixtureError("$.expected_outcome_categories must not be empty")

    states_raw = _sequence(root["states"], "$.states")
    if not 1 <= len(states_raw) <= _MAX_STATES:
        raise ReplayFixtureError(f"$.states must contain between 1 and {_MAX_STATES} states")
    states = tuple(
        _parse_state(value, f"$.states[{index}]") for index, value in enumerate(states_raw)
    )
    state_ids = [state.state_id for state in states]
    if len(state_ids) != len(set(state_ids)):
        raise ReplayFixtureError("$.states contains duplicate state ids")
    if start_state not in state_ids:
        raise ReplayFixtureError("$.start_state does not identify a fixture state")
    for state in states:
        for transition in state.transitions:
            if transition.next_state is not None and transition.next_state not in state_ids:
                raise ReplayFixtureError(
                    f"state {state.state_id!r} transitions to unknown state "
                    f"{transition.next_state!r}"
                )

    return ReplayFixture(
        fixture_id=fixture_id,
        journey=journey,
        step=step,
        goal=goal,
        verification_condition=verification,
        start_state=start_state,
        max_calls=max_calls,
        timeout_seconds=timeout_seconds,
        terminal_diagnosis_required=bool(terminal_diagnosis_required),
        expected_outcome_categories=expected_categories,
        states=states,
    )


def load_fixture_directory(path: Path) -> tuple[ReplayFixture, ...]:
    """Load every curated JSON fixture in deterministic filename order."""
    paths = sorted(path.glob("*.json"))
    if len(paths) > 20:
        raise ReplayFixtureError("fixture directory exceeds the 20-file safety limit")
    fixtures = tuple(load_fixture(item) for item in paths)
    if not fixtures:
        raise ReplayFixtureError(f"no JSON fixtures found in {path}")
    fixture_ids = [fixture.fixture_id for fixture in fixtures]
    if len(fixture_ids) != len(set(fixture_ids)):
        raise ReplayFixtureError("fixture directory contains duplicate fixture ids")
    return fixtures


def _parse_state(value: object, path: str) -> ReplayState:
    raw = _mapping(value, path)
    _keys(
        raw,
        path,
        required={
            "id",
            "observation",
            "history",
            "no_progress_count",
            "screenshot_forced",
            "transitions",
        },
    )
    state_id = _identifier(raw["id"], f"{path}.id")
    no_progress_count = _integer(raw["no_progress_count"], f"{path}.no_progress_count")
    if no_progress_count < 0:
        raise ReplayFixtureError(f"{path}.no_progress_count must be non-negative")
    screenshot_forced = _boolean(raw["screenshot_forced"], f"{path}.screenshot_forced")
    history_raw = _sequence(raw["history"], f"{path}.history")
    transitions_raw = _sequence(raw["transitions"], f"{path}.transitions")
    if not transitions_raw:
        raise ReplayFixtureError(f"{path}.transitions must not be empty")
    return ReplayState(
        state_id=state_id,
        observation=_parse_observation(raw["observation"], f"{path}.observation"),
        history=tuple(
            _parse_history(item, f"{path}.history[{index}]")
            for index, item in enumerate(history_raw)
        ),
        no_progress_count=no_progress_count,
        screenshot_forced=screenshot_forced,
        transitions=tuple(
            _parse_transition(item, f"{path}.transitions[{index}]")
            for index, item in enumerate(transitions_raw)
        ),
    )


def _parse_observation(value: object, path: str) -> Observation:
    raw = _mapping(value, path)
    _keys(
        raw,
        path,
        required={"url", "title", "text", "elements", "popup_count", "popup_urls", "scroll_y"},
    )
    url = _booking_url(raw["url"], f"{path}.url")
    text = _bounded_string(raw["text"], f"{path}.text", _MAX_TEXT_CHARS)
    elements_raw = _sequence(raw["elements"], f"{path}.elements")
    if len(elements_raw) > _MAX_ELEMENTS:
        raise ReplayFixtureError(f"{path}.elements exceeds {_MAX_ELEMENTS} entries")
    elements = tuple(
        _parse_element(item, f"{path}.elements[{index}]")
        for index, item in enumerate(elements_raw)
    )
    refs = [element.ref for element in elements]
    if len(refs) != len(set(refs)):
        raise ReplayFixtureError(f"{path}.elements contains duplicate refs")
    popup_urls_raw = _sequence(raw["popup_urls"], f"{path}.popup_urls")
    popup_urls = tuple(
        _booking_url(item, f"{path}.popup_urls[{index}]")
        for index, item in enumerate(popup_urls_raw)
    )
    popup_count = _integer(raw["popup_count"], f"{path}.popup_count")
    if popup_count < len(popup_urls) or popup_count < 0:
        raise ReplayFixtureError(f"{path}.popup_count must cover every listed popup URL")
    scroll_y = _integer(raw["scroll_y"], f"{path}.scroll_y")
    if scroll_y < 0:
        raise ReplayFixtureError(f"{path}.scroll_y must be non-negative")
    return Observation(
        url=url,
        title=_bounded_string(raw["title"], f"{path}.title", 300),
        text=text,
        elements=elements,
        popup_count=popup_count,
        popup_urls=popup_urls,
        scroll_y=scroll_y,
    )


def _parse_element(value: object, path: str) -> ElementInfo:
    raw = _mapping(value, path)
    _keys(raw, path, required={"ref", "role", "label", "href"})
    href_raw = raw["href"]
    href = None if href_raw is None else _booking_url(href_raw, f"{path}.href")
    return ElementInfo(
        ref=_bounded_string(raw["ref"], f"{path}.ref", 40),
        role=_bounded_string(raw["role"], f"{path}.role", 40),
        label=_bounded_string(raw["label"], f"{path}.label", 300),
        href=href,
    )


def _parse_history(value: object, path: str) -> AgentHistoryEvent:
    raw = _mapping(value, path)
    optional = {
        "goal_verified",
        "url_changed",
        "content_changed",
        "elements_changed",
        "scroll_changed",
        "popup_opened",
        "error",
        "semantic_target",
    }
    _keys(raw, path, required={"outcome", "detail"}, optional=optional)
    try:
        outcome = AgentHistoryOutcome(_bounded_string(raw["outcome"], f"{path}.outcome", 40))
    except ValueError as exc:
        raise ReplayFixtureError(f"{path}.outcome is not a supported history outcome") from exc
    return AgentHistoryEvent(
        outcome=outcome,
        detail=_bounded_string(raw["detail"], f"{path}.detail", 500),
        semantic_target=_optional_string(
            raw.get("semantic_target"), f"{path}.semantic_target", 300
        ),
        goal_verified=_optional_boolean(raw.get("goal_verified"), f"{path}.goal_verified"),
        url_changed=_optional_boolean(raw.get("url_changed"), f"{path}.url_changed"),
        content_changed=_optional_boolean(raw.get("content_changed"), f"{path}.content_changed"),
        elements_changed=_optional_boolean(
            raw.get("elements_changed"), f"{path}.elements_changed"
        ),
        scroll_changed=_optional_boolean(raw.get("scroll_changed"), f"{path}.scroll_changed"),
        popup_opened=_optional_boolean(raw.get("popup_opened"), f"{path}.popup_opened"),
        error=_optional_string(raw.get("error"), f"{path}.error", 300),
    )


def _parse_transition(value: object, path: str) -> ReplayTransition:
    raw = _mapping(value, path)
    _keys(raw, path, required={"action"}, optional={"next_state", "terminal_category"})
    next_state = _optional_identifier(raw.get("next_state"), f"{path}.next_state")
    terminal = _optional_identifier(raw.get("terminal_category"), f"{path}.terminal_category")
    if (next_state is None) == (terminal is None):
        raise ReplayFixtureError(
            f"{path} must contain exactly one of next_state or terminal_category"
        )
    return ReplayTransition(
        expectation=_parse_action_expectation(raw["action"], f"{path}.action"),
        next_state=next_state,
        terminal_category=terminal,
    )


def _parse_action_expectation(value: object, path: str) -> ActionExpectation:
    raw = _mapping(value, path)
    optional = {
        "role",
        "label",
        "href",
        "value",
        "stop_reason",
        "diagnosis_reason",
    }
    _keys(raw, path, required={"type"}, optional=optional)
    try:
        action_type = AgentActionType(_bounded_string(raw["type"], f"{path}.type", 40))
    except ValueError as exc:
        raise ReplayFixtureError(f"{path}.type is not a supported agent action") from exc
    stop_reason_raw = raw.get("stop_reason")
    try:
        stop_reason = (
            None
            if stop_reason_raw is None
            else AgentStopReason(_bounded_string(stop_reason_raw, f"{path}.stop_reason", 40))
        )
    except ValueError as exc:
        raise ReplayFixtureError(f"{path}.stop_reason is not supported") from exc
    diagnosis_reason_raw = raw.get("diagnosis_reason")
    try:
        diagnosis_reason = (
            None
            if diagnosis_reason_raw is None
            else AgentDiagnosisReason(
                _bounded_string(
                    diagnosis_reason_raw,
                    f"{path}.diagnosis_reason",
                    40,
                )
            )
        )
    except ValueError as exc:
        raise ReplayFixtureError(f"{path}.diagnosis_reason is not supported") from exc
    href_raw = raw.get("href")
    href = None if href_raw is None else _booking_url(href_raw, f"{path}.href")
    return ActionExpectation(
        action_type=action_type,
        role=_optional_string(raw.get("role"), f"{path}.role", 40),
        label=_optional_string(raw.get("label"), f"{path}.label", 300),
        href=href,
        value=_optional_string(raw.get("value"), f"{path}.value", 300),
        stop_reason=stop_reason,
        diagnosis_reason=diagnosis_reason,
    )


def _reject_sensitive_data(value: object, path: str) -> None:
    if isinstance(value, str):
        if (
            _EMAIL_PATTERN.search(value)
            or _PHONE_PATTERN.search(value)
            or _LONG_NUMBER_PATTERN.search(value)
            or _LONG_TOKEN_PATTERN.search(value)
            or _SECRET_PATTERN.search(value)
            or _SENSITIVE_WORDING.search(value)
        ):
            raise ReplayFixtureError(f"{path} contains secret or PII-shaped content")
        for match in _URL_PATTERN.findall(value):
            _validate_booking_url(match.rstrip(".,;)"), path)
        return
    if isinstance(value, dict):
        raw = cast(dict[object, object], value)
        for key, item in raw.items():
            _reject_sensitive_data(key, f"{path}<key>")
            _reject_sensitive_data(item, f"{path}{key}.")
        return
    if isinstance(value, list):
        raw_items = cast(list[object], value)
        for index, item in enumerate(raw_items):
            _reject_sensitive_data(item, f"{path}[{index}].")


def _booking_url(value: object, path: str) -> str:
    url = _bounded_string(value, path, 2_000)
    _validate_booking_url(url, path)
    return url


def _validate_booking_url(url: str, path: str) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ReplayFixtureError(f"{path} contains an invalid URL") from exc
    host = (parsed.hostname or "").casefold()
    if (
        parsed.scheme != "https"
        or not (host == "booking.com" or host.endswith(".booking.com"))
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or bool(parsed.query)
        or bool(parsed.fragment)
    ):
        raise ReplayFixtureError(
            f"{path} must be a query-free HTTPS URL on booking.com or a booking.com subdomain"
        )


def _mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ReplayFixtureError(f"{path} must be an object with string keys")
    return cast(dict[str, object], value)


def _sequence(value: object, path: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise ReplayFixtureError(f"{path} must be an array")
    return cast(list[object], value)


def _keys(
    value: Mapping[str, object],
    path: str,
    *,
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    allowed = required | (optional or set())
    missing = required - value.keys()
    unknown = value.keys() - allowed
    if missing:
        raise ReplayFixtureError(f"{path} is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ReplayFixtureError(f"{path} has unknown fields: {', '.join(sorted(unknown))}")


def _bounded_string(value: object, path: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReplayFixtureError(f"{path} must be a non-empty string")
    if len(value) > limit:
        raise ReplayFixtureError(f"{path} exceeds {limit} characters")
    return value


def _optional_string(value: object | None, path: str, limit: int) -> str | None:
    return None if value is None else _bounded_string(value, path, limit)


def _identifier(value: object, path: str) -> str:
    identifier = _bounded_string(value, path, 80)
    if not _ID_PATTERN.fullmatch(identifier):
        raise ReplayFixtureError(f"{path} must be lower-case kebab-case")
    return identifier


def _optional_identifier(value: object | None, path: str) -> str | None:
    return None if value is None else _identifier(value, path)


def _integer(value: object, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ReplayFixtureError(f"{path} must be an integer")
    return value


def _number(value: object, path: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ReplayFixtureError(f"{path} must be a number")
    return float(value)


def _boolean(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        raise ReplayFixtureError(f"{path} must be a boolean")
    return value


def _optional_boolean(value: object | None, path: str) -> bool:
    return False if value is None else _boolean(value, path)


def _normalize(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip().casefold()
