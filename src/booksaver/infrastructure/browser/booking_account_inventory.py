from __future__ import annotations

import html
import json
import re
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from booksaver.application.ports import InventoryInterpreter, PageContent
from booksaver.domain.account_sync import (
    InventoryCompleteness,
    InventoryDiscoveryResult,
    InventoryRecoveryOutcome,
    ReservationLifecycle,
    ReservationObservation,
    SynchronizationFailureCode,
)
from booksaver.domain.agent import (
    AgentAction,
    AgentActionType,
    AgentStopReason,
    BudgetExceeded,
    Observation,
)
from booksaver.domain.errors import UserKeyInvalidError
from booksaver.domain.value_objects import Money, Occupancy

_INVENTORY_URL = "https://secure.booking.com/myreservations.html"
_MAX_PAGES = 20
_MAX_RESERVATIONS = 500
_REQUIRED_SCOPES = frozenset({"upcoming", "past", "cancelled"})
_CAPTCHA_MARKERS = re.compile(
    r"(are you a human|verify you are human|hcaptcha|px-captcha|unusual traffic)",
    re.I,
)
_AUTH_MARKERS = re.compile(
    r"(sign in to manage|log in to your account|sign in or register|"
    r"enter your password|verification code)",
    re.I,
)
_READ_ONLY_SCOPE_LABEL = re.compile(
    r"(?:active|upcoming|past|previous|completed|cancelled|canceled)"
    r"(?: bookings| trips| reservations| stays)?"
    r"(?:\s*\(\d+\)|\s+\d+)?",
    re.I,
)
_READ_ONLY_PAGINATION_LABEL = re.compile(
    r"(?:next|previous)(?: page)?|page\s+\d+|"
    r"(?:show|load) more (?:bookings|reservations|trips|stays)",
    re.I,
)
_READ_ONLY_BUTTON_PAGINATION_LABEL = re.compile(
    r"(?:show|load) more (?:bookings|reservations|trips|stays)",
    re.I,
)
_READ_ONLY_DETAIL_LABEL = re.compile(
    r"(?:view )?(?:booking|reservation|trip)(?: details?)?|details?|confirmed",
    re.I,
)


RecoveryFactory = Callable[[Any], Any | None]


class _InventoryParser(HTMLParser):
    def __init__(self, source_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source_url = source_url
        self.cards: list[dict[str, str]] = []
        self.next_url: str | None = None
        self.scope_urls: dict[str, str] = {}
        self.scope_controls: set[str] = set()
        self.button_pagination = False
        self.detail_urls: set[str] = set()
        self.recognized_inventory = False
        self.recognized_empty = False
        self.explicit_complete = False
        self._json_depth = 0
        self._json_chunks: list[str] = []
        self.json_documents: list[Any] = []
        self._control_depth = 0
        self._control_attrs: dict[str, str] = {}
        self._control_text: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = {key: value or "" for key, value in attrs}
        testid = values.get("data-testid", "")
        declared_scopes = {
            scope.strip().lower()
            for scope in values.get("data-inventory-scopes", "").split(",")
            if scope.strip()
        }
        if (
            values.get("data-inventory-complete", "").lower() == "true"
            or _REQUIRED_SCOPES.issubset(declared_scopes)
        ):
            self.explicit_complete = True
        if testid in {"bookings-list", "reservation-list", "my-bookings-list"}:
            self.recognized_inventory = True
        if testid in {"bookings-empty-state", "reservation-empty-state"}:
            self.recognized_inventory = True
            self.recognized_empty = True
        if testid in {"reservation-card", "booking-card"}:
            self.recognized_inventory = True
            self.cards.append(values)
        if tag == "a" and (
            values.get("rel") == "next"
            or testid in {"pagination-next", "bookings-pagination-next"}
        ):
            href = values.get("href")
            if href:
                self.next_url = urljoin(self.source_url, href)
        if self._control_depth:
            self._control_depth += 1
        elif tag in {"a", "button"} or values.get("role") == "tab":
            self._control_depth = 1
            self._control_attrs = values
            self._control_text = []
        if tag == "a":
            target = (
                values.get("href")
                or values.get("data-href")
                or values.get("data-url")
            )
            if target:
                candidate = urljoin(self.source_url, target)
                lowered = candidate.lower()
                source_path = urlparse(self.source_url).path.lower()
                if (
                    not source_path.startswith("/confirmation")
                    and ("trip_id=" in lowered or "/confirmation" in lowered)
                ):
                    self.detail_urls.add(candidate)
                    self.recognized_inventory = True
        if tag == "script" and values.get("type", "").lower() in {
            "application/ld+json",
            "application/json",
        }:
            self._json_depth = 1
            self._json_chunks = []
        elif self._json_depth:
            self._json_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._control_depth:
            self._control_depth -= 1
            if self._control_depth == 0:
                self._register_scope_control()
        if self._json_depth:
            self._json_depth -= 1
            if tag == "script" and self._json_depth == 0:
                try:
                    self.json_documents.append(json.loads("".join(self._json_chunks)))
                except (TypeError, ValueError):
                    pass

    def handle_data(self, data: str) -> None:
        if self._control_depth:
            self._control_text.append(data)
        if self._json_depth:
            self._json_chunks.append(data)

    def _register_scope_control(self) -> None:
        target = (
            self._control_attrs.get("href")
            or self._control_attrs.get("data-href")
            or self._control_attrs.get("data-url")
        )
        testid = self._control_attrs.get("data-testid", "").lower()
        target_path = urlparse(urljoin(self.source_url, target)).path.lower() if target else ""
        is_scope_control = (
            self._control_attrs.get("role", "").lower() == "tab"
            or "tab" in testid
            or "myreservations" in target_path
            or "mytrips" in target_path
        )
        evidence = " ".join(
            [
                *self._control_attrs.values(),
                " ".join(self._control_text),
            ]
        ).lower()
        normalized_label = " ".join(evidence.split())
        if not is_scope_control:
            if (
                not target
                and _READ_ONLY_BUTTON_PAGINATION_LABEL.search(normalized_label)
            ):
                self.button_pagination = True
                self.recognized_inventory = True
            return
        for scope in _REQUIRED_SCOPES:
            aliases = {scope}
            if scope == "upcoming":
                aliases.add("active")
            if scope == "past":
                aliases.update({"completed", "previous"})
            if scope == "cancelled":
                aliases.add("canceled")
            if any(alias in evidence for alias in aliases):
                self.scope_controls.add(scope)
                self.recognized_inventory = True
                if target:
                    self.scope_urls[scope] = urljoin(self.source_url, target)


class BookingComAccountInventorySource:
    """Scripted, read-only account inventory adapter (ADRs 027-028).

    The DOM-card attributes are a narrow adapter contract covered by fixtures.
    JSON-LD ``LodgingReservation`` is accepted as an additional structured
    source. Unknown layouts are incomplete rather than guessed.
    """

    def __init__(
        self,
        *,
        recovery_factory: RecoveryFactory | None = None,
        interpreter: InventoryInterpreter | None = None,
        consume_interpreter_call: Callable[[], None] | None = None,
        check_time: Callable[[], None] | None = None,
        llm_calls_used: Callable[[], int] | None = None,
        recovery_unavailable_detail: str | None = None,
        action_observer: Callable[[AgentAction], None] | None = None,
    ) -> None:
        self._recovery_factory = recovery_factory
        self._interpreter = interpreter
        self._consume_interpreter_call = consume_interpreter_call
        self._check_time = check_time or (lambda: None)
        self._llm_calls_used = llm_calls_used or (lambda: 0)
        self._recovery_unavailable_detail = recovery_unavailable_detail
        self._action_observer = action_observer
        self._recovery_outcome = InventoryRecoveryOutcome.NOT_NEEDED
        self._recovery_step: str | None = None
        self._recovery_detail: str | None = None
        self._recovery_failure_code: SynchronizationFailureCode | None = None

    def discover(self, browser: Any) -> InventoryDiscoveryResult:
        self._recovery_outcome = InventoryRecoveryOutcome.NOT_NEEDED
        self._recovery_step = None
        self._recovery_detail = None
        self._recovery_failure_code = None
        result = self._discover(browser)
        outcome = self._recovery_outcome
        if (
            outcome is InventoryRecoveryOutcome.RECOVERED
            and result.completeness is not InventoryCompleteness.COMPLETE
        ):
            outcome = InventoryRecoveryOutcome.PARTIAL
        return replace(
            result,
            recovery_outcome=outcome,
            recovery_step=self._recovery_step,
            recovery_detail=self._recovery_detail,
            llm_calls_used=self._llm_calls_used(),
        )

    def _discover(self, browser: Any) -> InventoryDiscoveryResult:
        pending: list[tuple[str, str, str]] = [
            ("url", _INVENTORY_URL, "upcoming")
        ]
        visited: set[tuple[str, str, str]] = set()
        visited_scopes: set[str] = set()
        observations: dict[str, ReservationObservation] = {}
        explicit_complete = False
        unidentified_inventory_seen = False

        try:
            self._check_time()
            while pending and len(visited) < _MAX_PAGES:
                self._check_time()
                work_kind, target, scope = pending.pop(0)
                work_key = (work_kind, target, scope)
                if work_key in visited:
                    continue
                if work_kind == "url" and not _allowlisted(target):
                    return InventoryDiscoveryResult(
                        tuple(observations.values()),
                        InventoryCompleteness.INCOMPLETE,
                        SynchronizationFailureCode.PAGINATION_INCOMPLETE,
                        "Booking.com reservation pagination did not complete.",
                    )
                visited.add(work_key)
                before_navigation = _safe_observe(browser)
                try:
                    if work_kind in {"recover_scope", "recover_pagination"}:
                        page = self._recover_navigation(
                            browser,
                            work_kind=(
                                "scope"
                                if work_kind == "recover_scope"
                                else "pagination"
                            ),
                            target=target,
                            scope=scope,
                            trigger=RuntimeError(
                                "Booking.com inventory scope controls changed"
                            ),
                            before=before_navigation,
                        )
                        if page is None:
                            if self._recovery_failure_code is not None:
                                return InventoryDiscoveryResult.failed(
                                    self._recovery_failure_code,
                                    self._recovery_detail
                                    or "Booking.com inventory recovery was blocked.",
                                )
                            return InventoryDiscoveryResult(
                                tuple(observations.values()),
                                InventoryCompleteness.INCOMPLETE,
                                SynchronizationFailureCode.PAGINATION_INCOMPLETE,
                                self._recovery_detail
                                or "Booking.com inventory scope traversal was incomplete.",
                            )
                    elif work_kind == "scope":
                        page = browser.open_inventory_scope(scope)
                    else:
                        page = browser.open_page(target)
                    self._check_time()
                except UserKeyInvalidError:
                    raise
                except BudgetExceeded:
                    raise
                except Exception as exc:
                    page = self._recover_navigation(
                        browser,
                        work_kind=work_kind,
                        target=target,
                        scope=scope,
                        trigger=exc,
                        before=before_navigation,
                    )
                    if page is None:
                        return InventoryDiscoveryResult.failed(
                            self._recovery_failure_code
                            or SynchronizationFailureCode.NAVIGATION_FAILED,
                            self._recovery_detail
                            or "Booking.com reservation inventory could not be read.",
                        )
                if not browser.is_authenticated():
                    return InventoryDiscoveryResult.failed(
                        SynchronizationFailureCode.AUTH_REQUIRED,
                        "Booking.com account authentication is required.",
                    )
                parser = _InventoryParser(page.url)
                parser.feed(page.html)
                if _CAPTCHA_MARKERS.search(page.text):
                    return InventoryDiscoveryResult.failed(
                        SynchronizationFailureCode.BOT_WALL,
                        "Booking.com presented a bot-verification wall; retry later.",
                    )
                if _looks_like_empty_scope(page.text, scope):
                    parser.recognized_inventory = True
                    parser.recognized_empty = True
                page_observations = _parse_page(parser, page.url, page.text)
                deterministic_page_observations = tuple(page_observations)
                navigation_kind = _navigation_kind(work_kind, target)
                explicit_complete = explicit_complete or parser.explicit_complete
                unidentified_cards = [
                    card
                    for card in parser.cards
                    if not (
                        card.get("data-reservation-id")
                        or card.get("data-booking-id")
                        or card.get("data-confirmation-id")
                    )
                ]
                if unidentified_cards and len(page_observations) < len(parser.cards):
                    unidentified_inventory_seen = True
                    interpreted = self._interpret_page(page)
                    if interpreted is None:
                        return InventoryDiscoveryResult.failed(
                            SynchronizationFailureCode.EXTRACTION_AMBIGUOUS,
                            self._recovery_detail
                            or "Booking.com reservations were visible but could not be identified.",
                        )
                    if interpreted is not None:
                        page_observations.extend(interpreted)
                for observation in page_observations:
                    existing = observations.get(observation.remote_id)
                    if observation.extraction_method == "llm_inventory":
                        observations[observation.remote_id] = (
                            observation
                            if existing is None
                            else _merge_positive_interpretation(existing, observation)
                        )
                        continue
                    if (
                        existing is not None
                        and existing.lifecycle is not ReservationLifecycle.UNKNOWN
                        and observation.lifecycle is not ReservationLifecycle.UNKNOWN
                        and existing.lifecycle is not observation.lifecycle
                    ):
                        return InventoryDiscoveryResult.failed(
                            SynchronizationFailureCode.IDENTITY_AMBIGUOUS,
                            "Booking.com returned conflicting reservation identities.",
                        )
                    if (
                        existing is None
                        or _fact_count(observation) > _fact_count(existing)
                    ):
                        observations[observation.remote_id] = observation
                if len(observations) > _MAX_RESERVATIONS:
                    return InventoryDiscoveryResult(
                        tuple(list(observations.values())[:_MAX_RESERVATIONS]),
                        InventoryCompleteness.INCOMPLETE,
                        SynchronizationFailureCode.PAGINATION_INCOMPLETE,
                        "Booking.com returned more reservations than the safe limit.",
                    )
                visible_unknown_scopes = set()
                if self._recovery_factory is not None and not explicit_complete:
                    visible_unknown_scopes = _visible_scope_controls(browser) - (
                        parser.scope_controls | visited_scopes
                    )
                is_navigation_container = bool(
                    parser.scope_controls
                    or parser.detail_urls
                    or visible_unknown_scopes
                )
                if (
                    not page_observations
                    and not parser.recognized_empty
                ):
                    code = (
                        SynchronizationFailureCode.EXTRACTION_AMBIGUOUS
                        if parser.recognized_inventory
                        else SynchronizationFailureCode.UNSUPPORTED_LAYOUT
                    )
                    interpreted = self._interpret_page(page)
                    if interpreted is None:
                        if (
                            not is_navigation_container
                            and self._recovery_factory is None
                        ):
                            return InventoryDiscoveryResult.failed(
                                code,
                                self._recovery_detail
                                or "Booking.com reservation inventory layout was not recognized.",
                            )
                    else:
                        page_observations.extend(interpreted)
                        for observation in interpreted:
                            existing = observations.get(observation.remote_id)
                            observations[observation.remote_id] = (
                                observation
                                if existing is None
                                else _merge_positive_interpretation(existing, observation)
                            )
                navigation_verified = _navigation_page_verified(
                    navigation_kind,
                    target,
                    scope,
                    page,
                    parser,
                    deterministic_page_observations,
                )
                if (
                    not navigation_verified
                    and self._recovery_factory is not None
                    and work_kind != "recover_scope"
                ):
                    recovery_before = _safe_observe(browser)
                    recovered = self._recover_navigation(
                        browser,
                        work_kind=navigation_kind,
                        target=target,
                        scope=scope,
                        trigger=RuntimeError(
                            f"Booking.com inventory {navigation_kind} evidence changed"
                        ),
                        before=recovery_before,
                    )
                    if recovered is None:
                        if self._recovery_failure_code is not None:
                            return InventoryDiscoveryResult.failed(
                                self._recovery_failure_code,
                                self._recovery_detail
                                or "Booking.com inventory recovery was blocked.",
                            )
                        return InventoryDiscoveryResult(
                            tuple(observations.values()),
                            InventoryCompleteness.INCOMPLETE,
                            SynchronizationFailureCode.PAGINATION_INCOMPLETE,
                            self._recovery_detail
                            or (
                                "Booking.com inventory navigation changed and could not "
                                "be verified."
                            ),
                        )
                    recovered_parser = _InventoryParser(recovered.url)
                    recovered_parser.feed(recovered.html)
                    recovered_observations = _parse_page(
                        recovered_parser, recovered.url, recovered.text
                    )
                    navigation_verified = _navigation_page_verified(
                        navigation_kind,
                        target,
                        scope,
                        recovered,
                        recovered_parser,
                        tuple(recovered_observations),
                    )
                    if not navigation_verified:
                        return InventoryDiscoveryResult(
                            tuple(observations.values()),
                            InventoryCompleteness.INCOMPLETE,
                            SynchronizationFailureCode.PAGINATION_INCOMPLETE,
                            "Booking.com inventory recovery did not prove the requested view.",
                        )
                    page = recovered
                    parser = recovered_parser
                    page_observations = recovered_observations
                    for observation in recovered_observations:
                        existing = observations.get(observation.remote_id)
                        if existing is None or _fact_count(observation) > _fact_count(existing):
                            observations[observation.remote_id] = observation
                if navigation_kind == "scope" and navigation_verified:
                    visited_scopes.add(scope)
                if parser.next_url is not None:
                    pending.append(("url", parser.next_url, scope))
                if parser.button_pagination:
                    pending.append(
                        ("recover_pagination", f"button-{len(visited)}", scope)
                    )
                for candidate_scope, candidate_url in sorted(
                    parser.scope_urls.items()
                ):
                    pending.append(("url", candidate_url, candidate_scope))
                interactive_scopes = sorted(
                    parser.scope_controls - parser.scope_urls.keys() - visited_scopes
                )
                if interactive_scopes and not hasattr(browser, "open_inventory_scope"):
                    continue
                for candidate_scope in interactive_scopes:
                    pending.append(("scope", candidate_scope, candidate_scope))
                if self._recovery_factory is not None and not explicit_complete:
                    recovery_scopes = (
                        visible_unknown_scopes
                        | (
                            _REQUIRED_SCOPES
                            - visited_scopes
                            - parser.scope_controls
                            - parser.scope_urls.keys()
                        )
                    )
                    for candidate_scope in sorted(recovery_scopes):
                        pending.append(
                            ("recover_scope", candidate_scope, candidate_scope)
                        )
                for detail_url in sorted(parser.detail_urls):
                    pending.append(("url", detail_url, scope))
        except UserKeyInvalidError:
            raise
        except BudgetExceeded:
            self._set_recovery_failure(
                InventoryRecoveryOutcome.BUDGET_EXHAUSTED,
                "inventory_discovery",
                "Booking.com inventory discovery exceeded its time budget; the last "
                "safe inventory was preserved.",
            )
            return InventoryDiscoveryResult.failed(
                SynchronizationFailureCode.NAVIGATION_FAILED,
                self._recovery_detail
                or "Booking.com inventory discovery exceeded its time budget.",
            )
        except Exception:
            return InventoryDiscoveryResult.failed(
                SynchronizationFailureCode.NAVIGATION_FAILED,
                "Booking.com reservation inventory could not be read.",
            )

        if pending:
            return InventoryDiscoveryResult(
                tuple(observations.values()),
                InventoryCompleteness.INCOMPLETE,
                SynchronizationFailureCode.PAGINATION_INCOMPLETE,
                "Booking.com reservation pagination did not reach a terminal page.",
            )
        missing_scopes = _REQUIRED_SCOPES - visited_scopes
        if not explicit_complete and missing_scopes:
            return InventoryDiscoveryResult(
                tuple(observations.values()),
                InventoryCompleteness.INCOMPLETE,
                SynchronizationFailureCode.PAGINATION_INCOMPLETE,
                "Booking.com did not prove complete upcoming, past, and cancelled inventory.",
            )
        if unidentified_inventory_seen:
            return InventoryDiscoveryResult(
                tuple(observations.values()),
                InventoryCompleteness.INCOMPLETE,
                SynchronizationFailureCode.EXTRACTION_AMBIGUOUS,
                "Booking.com exposed reservation cards whose identities were not "
                "deterministically complete; no absence conclusion was made.",
            )
        return InventoryDiscoveryResult(
            tuple(observations.values()), InventoryCompleteness.COMPLETE
        )

    def _recover_navigation(
        self,
        browser: Any,
        *,
        work_kind: str,
        target: str,
        scope: str,
        trigger: Exception,
        before: Observation | None,
    ) -> PageContent | None:
        observation = before or _safe_observe(browser)
        if observation is None:
            self._set_recovery_failure(
                InventoryRecoveryOutcome.UNAVAILABLE,
                f"inventory_{scope}_{work_kind}",
                "Booking.com inventory recovery had no safe page evidence.",
            )
            return None
        if _CAPTCHA_MARKERS.search(observation.text):
            self._set_recovery_failure(
                InventoryRecoveryOutcome.BLOCKED,
                f"inventory_{scope}_{work_kind}",
                "Booking.com presented a bot-verification wall; retry later.",
                failure_code=SynchronizationFailureCode.BOT_WALL,
            )
            return None
        if _AUTH_MARKERS.search(observation.text) or not browser.is_authenticated():
            self._set_recovery_failure(
                InventoryRecoveryOutcome.BLOCKED,
                f"inventory_{scope}_{work_kind}",
                "Booking.com authentication is required; send /connect and retry.",
                failure_code=SynchronizationFailureCode.AUTH_REQUIRED,
            )
            return None
        if not _allowlisted(observation.url):
            self._set_recovery_failure(
                InventoryRecoveryOutcome.BLOCKED,
                f"inventory_{scope}_{work_kind}",
                "Booking.com inventory recovery left the approved reservation pages.",
            )
            return None
        if self._recovery_factory is None:
            self._set_recovery_failure(
                InventoryRecoveryOutcome.UNAVAILABLE,
                f"inventory_{scope}_{work_kind}",
                self._recovery_unavailable_detail
                or (
                    "LLM inventory recovery is unavailable; retry after restoring "
                    "allowance or configuration."
                ),
            )
            return None

        recovery_kind = _navigation_kind(work_kind, target)
        step = f"inventory_{scope}_{recovery_kind}"
        try:
            self._check_time()
            agent = self._recovery_factory(
                _InventoryGuardedBrowser(
                    browser,
                    action_observer=self._action_observer,
                )
            )
            if agent is None:
                raise RuntimeError("navigation agent is unavailable")
            result = agent.complete_step(
                step,
                goal=(
                    f"Open the read-only {scope} Booking.com reservation inventory and expose "
                    "its reservation list, explicit empty state, or reservation-detail links."
                ),
                verify=lambda: _inventory_recovery_verified(
                    browser, target, scope, recovery_kind, observation
                ),
                trigger=type(trigger).__name__,
                screenshot_first=True,
                verification_condition=(
                    "The controllable page remains an authenticated allowlisted Booking.com "
                    f"reservation page with stable visible {scope} inventory evidence."
                ),
            )
            self._check_time()
        except UserKeyInvalidError:
            raise
        except BudgetExceeded:
            raise
        except Exception as exc:
            self._set_recovery_failure(
                InventoryRecoveryOutcome.PROVIDER_ERROR,
                step,
                f"Booking.com inventory recovery was unavailable ({type(exc).__name__}).",
            )
            return None
        if not result.ok:
            outcome = _outcome_from_escalation(result)
            self._set_recovery_failure(
                outcome,
                step,
                _redacted_recovery_failure(outcome),
            )
            return None
        recovered = _safe_observe(browser)
        if recovered is None or not _allowlisted(recovered.url):
            self._set_recovery_failure(
                InventoryRecoveryOutcome.BLOCKED,
                step,
                "Booking.com inventory recovery did not end on an approved reservation page.",
            )
            return None
        self._recovery_outcome = InventoryRecoveryOutcome.RECOVERED
        self._recovery_step = step
        self._recovery_failure_code = None
        self._recovery_detail = (
            "Booking.com inventory navigation was recovered with guarded assistance."
        )
        return _page_from_observation(recovered)

    def _interpret_page(
        self, page: PageContent
    ) -> list[ReservationObservation] | None:
        step = "inventory_interpretation"
        if _CAPTCHA_MARKERS.search(page.text) or _AUTH_MARKERS.search(page.text):
            self._set_recovery_failure(
                InventoryRecoveryOutcome.BLOCKED,
                step,
                "Booking.com inventory interpretation was blocked by authentication "
                "or verification.",
            )
            return None
        if not _allowlisted(page.url):
            self._set_recovery_failure(
                InventoryRecoveryOutcome.BLOCKED,
                step,
                "Booking.com inventory interpretation refused an unapproved page.",
            )
            return None
        if self._interpreter is None or self._consume_interpreter_call is None:
            self._set_recovery_failure(
                InventoryRecoveryOutcome.UNAVAILABLE,
                step,
                self._recovery_unavailable_detail
                or (
                    "LLM inventory interpretation is unavailable; the last safe "
                    "inventory was preserved."
                ),
            )
            return None
        try:
            self._check_time()
            self._consume_interpreter_call()
            candidates = self._interpreter.interpret(page.text, page.url)
            self._check_time()
        except BudgetExceeded:
            self._set_recovery_failure(
                InventoryRecoveryOutcome.BUDGET_EXHAUSTED,
                step,
                "Inventory recovery budget is exhausted; the last safe inventory was preserved.",
            )
            return None
        except UserKeyInvalidError:
            raise
        except Exception as exc:
            self._set_recovery_failure(
                InventoryRecoveryOutcome.PROVIDER_ERROR,
                step,
                f"Booking.com inventory interpretation was unavailable ({type(exc).__name__}).",
            )
            return None
        valid: list[ReservationObservation] = []
        seen: dict[str, ReservationObservation] = {}
        for candidate in candidates:
            validated = _validated_interpreted_observation(
                candidate, page.url, page.text
            )
            if validated is None:
                continue
            candidate = validated
            existing = seen.get(candidate.remote_id)
            if (
                existing is not None
                and existing.lifecycle is not ReservationLifecycle.UNKNOWN
                and candidate.lifecycle is not ReservationLifecycle.UNKNOWN
                and existing.lifecycle is not candidate.lifecycle
            ):
                self._set_recovery_failure(
                    InventoryRecoveryOutcome.BLOCKED,
                    step,
                    "Booking.com inventory interpretation returned conflicting identities.",
                )
                return None
            if existing is None or _fact_count(candidate) > _fact_count(existing):
                seen[candidate.remote_id] = candidate
        valid.extend(seen.values())
        if not valid:
            self._set_recovery_failure(
                InventoryRecoveryOutcome.GAVE_UP,
                step,
                "Booking.com inventory interpretation produced no validated reservation evidence.",
            )
            return None
        self._recovery_outcome = InventoryRecoveryOutcome.RECOVERED
        self._recovery_step = step
        self._recovery_failure_code = None
        self._recovery_detail = (
            "Booking.com reservation details were recovered with guarded assistance."
        )
        return valid

    def _set_recovery_failure(
        self,
        outcome: InventoryRecoveryOutcome,
        step: str,
        detail: str,
        *,
        failure_code: SynchronizationFailureCode | None = None,
    ) -> None:
        self._recovery_outcome = outcome
        self._recovery_step = step
        self._recovery_detail = detail[:500]
        self._recovery_failure_code = failure_code


class _InventoryGuardedBrowser:
    """Inventory-specific read-only allowlist over the shared action guard."""

    def __init__(
        self,
        browser: Any,
        *,
        action_observer: Callable[[AgentAction], None] | None = None,
    ) -> None:
        self._browser = browser
        self._observation: Observation | None = None
        self._action_observer = action_observer

    def __getattr__(self, name: str) -> Any:
        return getattr(self._browser, name)

    def observe(self) -> Observation:
        observation = self._browser.observe()
        if not isinstance(observation, Observation):
            raise TypeError("Inventory browser returned an invalid observation")
        destinations = (observation.url, *observation.popup_urls)
        if any(not _allowlisted(url) for url in destinations):
            observation = replace(
                observation,
                popup_count=max(
                    observation.popup_count,
                    len(observation.popup_urls) + 1,
                ),
            )
        self._observation = observation
        return observation

    def act(self, action: AgentAction) -> None:
        observation = self._observation or self.observe()
        target = next(
            (item for item in observation.elements if item.ref == action.ref),
            None,
        )
        if action.type in {AgentActionType.FILL, AgentActionType.SELECT}:
            raise RuntimeError("inventory recovery refused an input action")
        if action.type is AgentActionType.CLICK:
            if target is None or not _is_read_only_inventory_control(
                target.role,
                target.label,
                target.href,
                observation.url,
            ):
                raise RuntimeError("inventory recovery refused a non-read-only control")
        self._browser.act(action)
        if self._action_observer is not None:
            try:
                self._action_observer(action)
            except Exception:
                # Telemetry must never turn an already-executed read-only action
                # into an apparent failure that the agent could retry.
                pass


def _is_read_only_inventory_control(
    role: str,
    label: str,
    href: str | None,
    source_url: str,
) -> bool:
    normalized_role = role.casefold()
    normalized_label = " ".join(label.casefold().split())
    if normalized_role not in {"button", "link", "tab"}:
        return False
    if _READ_ONLY_SCOPE_LABEL.fullmatch(normalized_label):
        return href is None or _allowlisted(urljoin(source_url, href))
    if _READ_ONLY_PAGINATION_LABEL.fullmatch(normalized_label):
        if href is None:
            return bool(
                _READ_ONLY_BUTTON_PAGINATION_LABEL.fullmatch(normalized_label)
            )
        destination = urlparse(urljoin(source_url, href))
        return _allowlisted(destination.geturl()) and any(
            name in parse_qs(destination.query)
            for name in ("page", "cursor", "offset")
        )
    if href is None or not _allowlisted(urljoin(source_url, href)):
        return False
    destination = urlparse(urljoin(source_url, href))
    is_detail_destination = (
        destination.path.casefold().startswith("/confirmation")
        or "trip_id" in parse_qs(destination.query)
    )
    return is_detail_destination and bool(
        _READ_ONLY_DETAIL_LABEL.fullmatch(normalized_label)
    )


def _safe_observe(browser: Any) -> Observation | None:
    try:
        observation = browser.observe()
        return observation if isinstance(observation, Observation) else None
    except Exception:
        return None


def _observation_changed(before: Observation, after: Observation) -> bool:
    return any(
        (
            before.url != after.url,
            before.title != after.title,
            " ".join(before.text.split()) != " ".join(after.text.split()),
            before.scroll_y != after.scroll_y,
            tuple((item.role, item.label, item.href) for item in before.elements)
            != tuple((item.role, item.label, item.href) for item in after.elements),
        )
    )


def _navigation_kind(work_kind: str, target: str) -> str:
    if work_kind in {"scope", "recover_scope"}:
        return "scope"
    if work_kind in {"pagination", "recover_pagination"}:
        return "pagination"
    parsed = urlparse(target)
    query = parse_qs(parsed.query)
    if parsed.path.casefold().startswith("/confirmation") or "trip_id" in query:
        return "detail"
    if any(name in query for name in ("page", "cursor", "offset")):
        return "pagination"
    return "scope"


def _scope_aliases(scope: str) -> tuple[str, ...]:
    return {
        "upcoming": ("upcoming", "active", "confirmed"),
        "past": ("past", "previous", "completed"),
        "cancelled": ("cancelled", "canceled"),
    }[scope]


def _url_explicitly_selects_scope(url: str, scope: str) -> bool:
    query = parse_qs(urlparse(url).query)
    selected = {
        value.casefold()
        for key in ("scope", "status", "tab", "filter")
        for value in query.get(key, ())
    }
    return bool(selected.intersection(_scope_aliases(scope)))


def _scope_text_evidence(text: str, scope: str) -> bool:
    normalized = " ".join(text.casefold().split())
    if _looks_like_empty_scope(normalized, scope):
        return True
    # A status word next to a generic nav label is not enough. Positive text
    # evidence must expose a reservation-specific fact in the same visible
    # content segment, not somewhere near a persistent tab label.
    segments = re.split(r"(?:\r?\n|[|·]|(?<=[.!?])\s+)", text.casefold())
    return any(
        any(re.search(rf"\b{re.escape(alias)}\b", segment) for alias in _scope_aliases(scope))
        and re.search(
            r"\b(?:confirmation|check-in|check in|hotel|property)\b",
            segment,
        )
        is not None
        for segment in segments
    )


def _scope_observation_changed(before: Observation, after: Observation) -> bool:
    return any(
        (
            before.url != after.url,
            before.title != after.title,
            " ".join(before.text.split()) != " ".join(after.text.split()),
        )
    )


def _lifecycle_matches_scope(
    observation: ReservationObservation,
    scope: str,
) -> bool:
    return {
        "upcoming": observation.lifecycle is ReservationLifecycle.UPCOMING,
        "past": observation.lifecycle is ReservationLifecycle.COMPLETED,
        "cancelled": observation.lifecycle is ReservationLifecycle.CANCELLED,
    }[scope]


def _navigation_page_verified(
    kind: str,
    target: str,
    scope: str,
    page: PageContent,
    parser: _InventoryParser,
    observations: tuple[ReservationObservation, ...],
) -> bool:
    if not _allowlisted(page.url):
        return False
    if _CAPTCHA_MARKERS.search(page.text) or _AUTH_MARKERS.search(page.text):
        return False
    if kind == "detail":
        requested = urlparse(target)
        actual = urlparse(page.url)
        same_detail_family = (
            requested.path.casefold().startswith("/confirmation")
            and actual.path.casefold().startswith("/confirmation")
        ) or (
            "trip_id" in parse_qs(requested.query)
            and "trip_id" in parse_qs(actual.query)
        )
        return same_detail_family and bool(observations)
    if kind == "pagination":
        if target.startswith("button-"):
            return True
        requested_query = parse_qs(urlparse(target).query)
        actual_query = parse_qs(urlparse(page.url).query)
        cursor_matches = any(
            requested_query.get(name) == actual_query.get(name)
            for name in ("page", "cursor", "offset")
            if name in requested_query
        )
        return cursor_matches and bool(
            observations or parser.recognized_empty or parser.next_url
        )
    if any(_lifecycle_matches_scope(item, scope) for item in observations):
        return True
    visible_text = _visible_page_text(page)
    if _looks_like_empty_scope(visible_text, scope) or _scope_text_evidence(
        visible_text, scope
    ):
        return True
    # The default inventory entry represents upcoming only when it exposes
    # actual reservation/detail content, never from a persistent nav alias.
    return scope == "upcoming" and bool(parser.detail_urls)


def _visible_page_text(page: PageContent) -> str:
    html_text = html.unescape(re.sub(r"<[^>]+>", " ", page.html))
    return " ".join((page.text, html_text))


def _inventory_recovery_verified(
    browser: Any,
    target: str,
    scope: str,
    kind: str,
    before: Observation,
) -> bool:
    observation = _safe_observe(browser)
    if observation is None or not _allowlisted(observation.url):
        return False
    if _CAPTCHA_MARKERS.search(observation.text) or _AUTH_MARKERS.search(observation.text):
        return False
    try:
        if not browser.is_authenticated():
            return False
    except Exception:
        return False
    changed = _observation_changed(before, observation)
    if kind == "scope":
        # Interactive controls are intentionally excluded: persistent tab labels
        # cannot prove which scope's content is currently rendered.
        matches = _scope_text_evidence(
            " ".join((observation.title, observation.text)), scope
        )
        return matches and (
            _scope_observation_changed(before, observation)
            or _url_explicitly_selects_scope(before.url, scope)
        )
    if kind == "pagination":
        requested_query = parse_qs(urlparse(target).query)
        actual_query = parse_qs(urlparse(observation.url).query)
        if not any(name in requested_query for name in ("page", "cursor", "offset")):
            return changed
        return changed and any(
            requested_query.get(name) == actual_query.get(name)
            for name in ("page", "cursor", "offset")
            if name in requested_query
        )
    requested_url = urlparse(target)
    actual_url = urlparse(observation.url)
    return changed and (
        (
            requested_url.path.casefold().startswith("/confirmation")
            and actual_url.path.casefold().startswith("/confirmation")
        )
        or (
            "trip_id" in parse_qs(requested_url.query)
            and "trip_id" in parse_qs(actual_url.query)
        )
    )


def _visible_scope_controls(browser: Any) -> set[str]:
    observation = _safe_observe(browser)
    if observation is None:
        return set()
    found: set[str] = set()
    for item in observation.elements:
        label = " ".join(item.label.casefold().split())
        if label in {"active", "upcoming"}:
            found.add("upcoming")
        elif label in {"past", "previous", "completed"}:
            found.add("past")
        elif label in {"cancelled", "canceled"}:
            found.add("cancelled")
    return found


def _page_from_observation(observation: Observation) -> PageContent:
    fragments: list[str] = []
    for item in observation.elements:
        label = html.escape(item.label)
        role = html.escape(item.role)
        if item.href:
            fragments.append(
                f'<a role="{role}" href="{html.escape(item.href, quote=True)}">{label}</a>'
            )
        else:
            fragments.append(f'<button role="{role}">{label}</button>')
    return PageContent(
        url=observation.url,
        html="<main>" + "".join(fragments) + "</main>",
        text=observation.text,
    )


def _validated_interpreted_observation(
    candidate: ReservationObservation,
    source_url: str,
    page_text: str,
) -> ReservationObservation | None:
    if candidate.lifecycle is not ReservationLifecycle.UPCOMING:
        return None
    if candidate.refundable is False:
        return None
    if not candidate.remote_id.strip():
        return None
    if len(candidate.remote_id.strip()) < 4 or not _literal_visible(
        candidate.remote_id, page_text
    ):
        return None
    if candidate.source_url and not _allowlisted(candidate.source_url):
        return None
    if not _allowlisted(source_url):
        return None
    # Interpretation can identify visible, positive evidence, but it cannot be
    # the authority for monitoring eligibility. Keep the standalone observation
    # deliberately non-eligible and retain only non-actionable facts that are
    # independently present verbatim in the deterministic page text.
    return replace(
        candidate,
        lifecycle=ReservationLifecycle.UNKNOWN,
        confirmation_id=(
            candidate.confirmation_id
            if candidate.confirmation_id
            and _literal_visible(candidate.confirmation_id, page_text)
            else None
        ),
        property_name=(
            candidate.property_name
            if candidate.property_name
            and _literal_visible(candidate.property_name, page_text)
            else None
        ),
        property_ref=(
            candidate.property_ref
            if candidate.property_ref
            and _literal_visible(candidate.property_ref, page_text)
            else None
        ),
        check_in=None,
        check_out=None,
        room_type=None,
        booked_total=None,
        refundable=None,
        refund_note="",
        refund_deadline=None,
        occupancy=None,
        source_url=source_url,
        extraction_method="llm_inventory",
    )


def _literal_visible(value: str, page_text: str) -> bool:
    normalized_value = " ".join(value.casefold().split())
    normalized_text = " ".join(page_text.casefold().split())
    if not normalized_value:
        return False
    return re.search(
        rf"(?<![a-z0-9]){re.escape(normalized_value)}(?![a-z0-9])",
        normalized_text,
    ) is not None


def _merge_positive_interpretation(
    existing: ReservationObservation,
    candidate: ReservationObservation,
) -> ReservationObservation:
    """Merge only grounded, non-eligibility metadata into scripted evidence."""
    return replace(
        existing,
        confirmation_id=existing.confirmation_id or candidate.confirmation_id,
        property_name=existing.property_name or candidate.property_name,
        property_ref=existing.property_ref or candidate.property_ref,
        source_url=existing.source_url or candidate.source_url,
        extraction_method=existing.extraction_method,
    )


def _outcome_from_escalation(result: Any) -> InventoryRecoveryOutcome:
    if result.stop_reason is AgentStopReason.UNSAFE_ACTION:
        return InventoryRecoveryOutcome.BLOCKED
    if result.stop_reason is AgentStopReason.BUDGET_EXHAUSTED:
        return InventoryRecoveryOutcome.BUDGET_EXHAUSTED
    if result.stop_reason is AgentStopReason.PROVIDER_ERROR:
        return InventoryRecoveryOutcome.PROVIDER_ERROR
    return InventoryRecoveryOutcome.GAVE_UP


def _redacted_recovery_failure(outcome: InventoryRecoveryOutcome) -> str:
    messages = {
        InventoryRecoveryOutcome.BLOCKED: (
            "Booking.com inventory recovery stopped at the read-only safety boundary."
        ),
        InventoryRecoveryOutcome.BUDGET_EXHAUSTED: (
            "Booking.com inventory recovery exhausted its bounded LLM allowance."
        ),
        InventoryRecoveryOutcome.PROVIDER_ERROR: (
            "Booking.com inventory recovery was unavailable from the configured LLM provider."
        ),
    }
    return messages.get(
        outcome,
        "Booking.com inventory recovery could not verify progress; the last safe "
        "inventory was preserved.",
    )


def _allowlisted(url: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "https"
        and (hostname == "booking.com" or hostname.endswith(".booking.com"))
        and (
            "myreservations" in parsed.path.lower()
            or "mytrips" in parsed.path.lower()
            or parsed.path.lower().startswith("/confirmation")
        )
    )


def _parse_page(
    parser: _InventoryParser, source_url: str, page_text: str = ""
) -> list[ReservationObservation]:
    observations: dict[str, ReservationObservation] = {}
    for card in parser.cards:
        observation = _observation_from_mapping(card, source_url)
        if observation is not None:
            observations[observation.remote_id] = observation
    for document in parser.json_documents:
        for observation in _observations_from_apollo_cache(document, source_url):
            observations[observation.remote_id] = observation
            parser.recognized_inventory = True
        for item in _walk_json(document):
            observation = (
                _observation_from_json_ld(item, source_url)
                if item.get("@type") in {"LodgingReservation", "Reservation"}
                else _observation_from_generic_json(item, source_url)
            )
            if observation is not None and (
                item.get("@type") in {"LodgingReservation", "Reservation"}
                or _fact_count(observation) >= 2
            ):
                existing = observations.get(observation.remote_id)
                if existing is None or _fact_count(observation) > _fact_count(existing):
                    observations[observation.remote_id] = observation
                parser.recognized_inventory = True
    page_observations = list(observations.values())
    if len(page_observations) == 1 and page_observations[0].occupancy is None:
        occupancy = _occupancy_from_text(page_text)
        if occupancy is not None:
            page_observations[0] = replace(
                page_observations[0], occupancy=occupancy
            )
    return page_observations


def _observations_from_apollo_cache(
    document: Any, source_url: str
) -> list[ReservationObservation]:
    if not isinstance(document, dict):
        return []
    entities = [
        value
        for value in document.values()
        if isinstance(value, dict)
        and value.get("__typename") == "PostBookingReservation"
    ]
    observations: list[ReservationObservation] = []
    for entity in entities:
        identity = _resolve_cache_value(document, entity.get("identity"))
        property_data = _resolve_cache_value(document, entity.get("property"))
        price = _resolve_cache_value(document, entity.get("price"))
        check_in = _resolve_cache_value(
            document, entity.get("reservationCheckinDate")
        )
        check_out = _resolve_cache_value(
            document, entity.get("reservationCheckoutDate")
        )
        remote_id = _first_string(identity, "reservationId", "reservationNumber")
        if remote_id is None:
            continue
        property_name = _apollo_property_name(property_data)
        property_ref = _first_string(
            property_data, "url", "hotelId", "propertyId"
        )
        room_type = _apollo_room_type(document, entity)
        currency = (
            _first_string(price, "currency", "currencyCode")
            or _first_string(property_data, "currencyCode")
            or _deep_first_string(
                _resolve_cache_value(document, entity), "selectedCurrency"
            )
        )
        total_text = _first_string(
            price,
            "userTotal",
            "total",
            "userTotalPretty",
            "totalPretty",
        )
        non_refundable = _first_bool(entity, "hasNonRefundableRoom")
        refundable = None if non_refundable is None else not non_refundable
        resolved = _resolve_cache_value(document, entity)
        observations.append(
            ReservationObservation(
                remote_id=remote_id,
                confirmation_id=remote_id,
                lifecycle=_lifecycle(
                    _first_string(
                        entity,
                        "reservationStatus",
                        "confirmedStatus",
                        "status",
                    )
                ),
                property_name=property_name,
                property_ref=property_ref,
                check_in=_apollo_date(check_in),
                check_out=_apollo_date(check_out),
                room_type=room_type,
                booked_total=_money(_amount_text(total_text), currency),
                refundable=refundable,
                refund_note=_first_string(
                    entity, "cancellationType", "cancellationPolicy"
                )
                or "",
                occupancy=_occupancy_from_apollo(resolved),
                observed_at=datetime.now(UTC),
                source_url=source_url,
                extraction_method="apollo_cache",
            )
        )
    return observations


def _resolve_cache_value(
    cache: dict[str, Any],
    value: Any,
    *,
    visited: frozenset[str] = frozenset(),
    depth: int = 0,
) -> Any:
    if depth > 12:
        return {}
    if isinstance(value, dict):
        reference = value.get("__ref")
        if isinstance(reference, str):
            if reference in visited:
                return {}
            return _resolve_cache_value(
                cache,
                cache.get(reference, {}),
                visited=visited | {reference},
                depth=depth + 1,
            )
        return {
            key: _resolve_cache_value(
                cache, nested, visited=visited, depth=depth + 1
            )
            for key, nested in value.items()
        }
    if isinstance(value, list):
        return [
            _resolve_cache_value(cache, item, visited=visited, depth=depth + 1)
            for item in value
        ]
    return value


def _apollo_room_type(cache: dict[str, Any], entity: dict[str, Any]) -> str | None:
    room_reservations = entity.get("roomReservations")
    if isinstance(room_reservations, list):
        for raw_reservation in room_reservations:
            reservation = _resolve_cache_value(cache, raw_reservation)
            room = _resolve_cache_value(cache, reservation.get("room"))
            name = _first_string(room, "roomName", "name")
            if name:
                return name
    room_types = _resolve_cache_value(cache, entity.get("roomTypes"))
    if isinstance(room_types, list):
        for room_type in room_types:
            if isinstance(room_type, str) and room_type.strip():
                return room_type
            if isinstance(room_type, dict):
                name = _first_string(room_type, "roomName", "name")
                if name:
                    return name
    return None


def _apollo_property_name(property_data: dict[str, Any]) -> str | None:
    name = property_data.get("hotelName") or property_data.get("name")
    if isinstance(name, dict):
        return _first_string(name, "translation", "rawValue", "value")
    return _string(name)


def _apollo_date(value: Any) -> date | None:
    if not isinstance(value, dict):
        return None
    raw = value.get("rawDate") or value.get("date")
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(raw, UTC).date()
        except (OverflowError, OSError, ValueError):
            return None
    return _date(_string(raw))


def _deep_first_string(value: Any, *keys: str) -> str | None:
    if isinstance(value, dict):
        direct = _first_string(value, *keys)
        if direct:
            return direct
        for nested in value.values():
            found = _deep_first_string(nested, *keys)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _deep_first_string(nested, *keys)
            if found:
                return found
    return None


def _deep_first_int(value: Any, *keys: str) -> int | None:
    if isinstance(value, dict):
        direct = _first_int(value, *keys)
        if direct is not None:
            return direct
        for nested in value.values():
            found = _deep_first_int(nested, *keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _deep_first_int(nested, *keys)
            if found is not None:
                return found
    return None


def _occupancy_from_apollo(value: Any) -> Occupancy | None:
    adults = _deep_first_int(
        value, "adults", "adultCount", "numberOfAdults", "numberOfAdultGuests"
    )
    if adults is None:
        return None
    try:
        return Occupancy(
            adults,
            _deep_first_int(
                value,
                "children",
                "childCount",
                "numberOfChildren",
                "numberOfChildGuests",
            )
            or 0,
            _deep_first_int(value, "rooms", "roomCount", "numberOfRooms") or 1,
        )
    except ValueError:
        return None


def _occupancy_from_text(text: str) -> Occupancy | None:
    adults_match = re.search(r"\b(\d+)\s+adults?\b", text, re.I)
    if adults_match is None:
        return None
    children_match = re.search(r"\b(\d+)\s+(?:children|child)\b", text, re.I)
    rooms_match = re.search(r"\b(\d+)\s+rooms?\b", text, re.I)
    try:
        return Occupancy(
            int(adults_match.group(1)),
            int(children_match.group(1)) if children_match else 0,
            int(rooms_match.group(1)) if rooms_match else 1,
        )
    except ValueError:
        return None


def _amount_text(raw: str | None) -> str | None:
    if not raw:
        return None
    value = re.sub(r"[^\d,.\-]", "", raw)
    if "," in value and "." in value:
        if value.rfind(".") > value.rfind(","):
            value = value.replace(",", "")
        else:
            value = value.replace(".", "").replace(",", ".")
    elif "," in value:
        pieces = value.split(",")
        value = "".join(pieces) if len(pieces[-1]) == 3 else ".".join(pieces)
    return value or None


def _looks_like_empty_scope(text: str, scope: str) -> bool:
    normalized = " ".join(text.lower().split())
    aliases = {
        "upcoming": ("active", "upcoming"),
        "past": ("past", "previous"),
        "cancelled": ("canceled", "cancelled"),
    }[scope]
    return any(
        phrase in normalized
        for alias in aliases
        for phrase in (
            f"no {alias} bookings",
            f"no {alias} trips",
            f"no {alias} reservations",
            f"no {alias} stays",
        )
    )


def _observation_from_mapping(
    values: dict[str, str], source_url: str
) -> ReservationObservation | None:
    remote_id = (
        values.get("data-reservation-id")
        or values.get("data-booking-id")
        or values.get("data-confirmation-id")
    )
    if not remote_id:
        return None
    total = _money(
        values.get("data-total-amount"), values.get("data-currency")
    )
    return ReservationObservation(
        remote_id=remote_id,
        confirmation_id=values.get("data-confirmation-id") or None,
        lifecycle=_lifecycle(values.get("data-status")),
        property_name=values.get("data-property-name") or None,
        property_ref=values.get("data-property-url") or None,
        check_in=_date(values.get("data-checkin")),
        check_out=_date(values.get("data-checkout")),
        room_type=values.get("data-room-type") or None,
        booked_total=total,
        refundable=_bool(values.get("data-refundable")),
        refund_note=values.get("data-refund-note", ""),
        refund_deadline=_date(values.get("data-refund-deadline")),
        occupancy=_occupancy(values),
        observed_at=datetime.now(UTC),
        source_url=source_url,
    )


def _observation_from_json_ld(
    item: dict[str, Any], source_url: str
) -> ReservationObservation | None:
    remote_id = item.get("reservationId") or item.get("reservationNumber")
    if not isinstance(remote_id, str) or not remote_id.strip():
        return None
    reserved = item.get("reservationFor")
    reserved = reserved if isinstance(reserved, dict) else {}
    price = item.get("totalPrice") or item.get("price")
    currency = item.get("priceCurrency")
    return ReservationObservation(
        remote_id=remote_id,
        confirmation_id=_string(item.get("reservationNumber")),
        lifecycle=_lifecycle(_string(item.get("reservationStatus"))),
        property_name=_string(reserved.get("name")),
        property_ref=_string(reserved.get("url")),
        check_in=_date(_string(item.get("checkinTime") or item.get("checkInTime"))),
        check_out=_date(_string(item.get("checkoutTime") or item.get("checkOutTime"))),
        room_type=_string(item.get("reservationForName") or item.get("roomType")),
        booked_total=_money(_string(price), _string(currency)),
        refundable=_bool(_string(item.get("refundable"))),
        refund_note=_string(item.get("cancellationPolicy")) or "",
        occupancy=None,
        observed_at=datetime.now(UTC),
        source_url=source_url,
    )


def _observation_from_generic_json(
    item: dict[str, Any], source_url: str
) -> ReservationObservation | None:
    remote_id = _first_string(
        item,
        "reservationId",
        "reservation_id",
        "bookingId",
        "booking_id",
        "reservationNumber",
        "confirmationNumber",
        "confirmationId",
    )
    if remote_id is None:
        return None
    property_data = _first_mapping(
        item, "property", "hotel", "accommodation", "reservationFor"
    )
    total_data = _first_mapping(item, "totalPrice", "bookedTotal", "price")
    total_amount = _first_string(
        item, "totalAmount", "amount", "bookedAmount", "totalPrice"
    )
    currency = _first_string(item, "currency", "priceCurrency", "currencyCode")
    if total_data is not None:
        total_amount = total_amount or _first_string(
            total_data, "amount", "value", "total"
        )
        currency = currency or _first_string(
            total_data, "currency", "currencyCode", "code"
        )
    property_name = _first_string(item, "propertyName", "hotelName")
    property_ref = _first_string(item, "propertyUrl", "hotelUrl")
    if property_data is not None:
        property_name = property_name or _first_string(property_data, "name", "title")
        property_ref = property_ref or _first_string(
            property_data, "url", "id", "propertyId"
        )
    occupancy_data = _first_mapping(item, "occupancy", "guests", "guestCounts")
    return ReservationObservation(
        remote_id=remote_id,
        confirmation_id=_first_string(
            item, "confirmationId", "confirmationNumber", "reservationNumber"
        ),
        lifecycle=_lifecycle(
            _first_string(item, "status", "reservationStatus", "bookingStatus")
        ),
        property_name=property_name,
        property_ref=property_ref,
        check_in=_date(
            _first_string(item, "checkIn", "checkin", "check_in", "checkinTime")
        ),
        check_out=_date(
            _first_string(item, "checkOut", "checkout", "check_out", "checkoutTime")
        ),
        room_type=_first_string(
            item, "roomType", "roomName", "accommodationUnitName"
        ),
        booked_total=_money(total_amount, currency),
        refundable=_first_bool(item, "refundable", "isRefundable"),
        refund_note=_first_string(
            item, "cancellationPolicy", "refundNote", "cancellationText"
        )
        or "",
        refund_deadline=_date(
            _first_string(item, "refundDeadline", "freeCancellationUntil")
        ),
        occupancy=_occupancy_from_json(occupancy_data or item),
        observed_at=datetime.now(UTC),
        source_url=source_url,
        extraction_method="embedded_json",
    )


def _fact_count(observation: ReservationObservation) -> int:
    return sum(
        value is not None and value != ""
        for value in (
            observation.confirmation_id,
            observation.property_name,
            observation.property_ref,
            observation.check_in,
            observation.check_out,
            observation.room_type,
            observation.booked_total,
            observation.refundable,
            observation.occupancy,
        )
    )


def _walk_json(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for nested in value.values():
            if isinstance(nested, (dict, list)):
                found.extend(_walk_json(nested))
    elif isinstance(value, list):
        for item in value:
            found.extend(_walk_json(item))
    return found


def _lifecycle(raw: str | None) -> ReservationLifecycle:
    value = (raw or "").lower()
    if "cancel" in value:
        return ReservationLifecycle.CANCELLED
    if any(token in value for token in ("complete", "past", "checkout")):
        return ReservationLifecycle.COMPLETED
    if "current" in value or "checked_in" in value:
        return ReservationLifecycle.CURRENT
    if any(
        token in value
        for token in ("upcoming", "active", "confirmed", "reservationconfirmed")
    ):
        return ReservationLifecycle.UPCOMING
    return ReservationLifecycle.UNKNOWN


def _date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _money(amount: str | None, currency: str | None) -> Money | None:
    if not amount or not currency:
        return None
    try:
        return Money.of(amount, currency)
    except ValueError:
        return None


def _bool(raw: str | None) -> bool | None:
    if raw is None or raw == "":
        return None
    value = raw.lower()
    if value in {"1", "true", "yes", "refundable"}:
        return True
    if value in {"0", "false", "no", "non_refundable", "non-refundable"}:
        return False
    return None


def _occupancy(values: dict[str, str]) -> Occupancy | None:
    try:
        adults = int(values["data-adults"])
        children = int(values.get("data-children", "0"))
        rooms = int(values.get("data-rooms", "1"))
        return Occupancy(adults, children, rooms)
    except (KeyError, ValueError):
        return None


def _occupancy_from_json(item: dict[str, Any]) -> Occupancy | None:
    adults = _first_int(item, "adults", "adultCount", "numberOfAdults")
    if adults is None:
        return None
    try:
        return Occupancy(
            adults,
            _first_int(item, "children", "childCount", "numberOfChildren") or 0,
            _first_int(item, "rooms", "roomCount", "numberOfRooms") or 1,
        )
    except ValueError:
        return None


def _first_string(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value)
    return None


def _first_mapping(item: dict[str, Any], *keys: str) -> dict[str, Any] | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, dict):
            return value
    return None


def _first_int(item: dict[str, Any], *keys: str) -> int | None:
    raw = _first_string(item, *keys)
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


def _first_bool(item: dict[str, Any], *keys: str) -> bool | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, bool):
            return value
        parsed = _bool(_string(value))
        if parsed is not None:
            return parsed
    return None


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
