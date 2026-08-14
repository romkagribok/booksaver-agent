from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from anthropic.types import TextBlock, ToolUseBlock

from booksaver.application.browser_resilience import (
    DOM_STEP_REGISTRY,
    ModelClassifierCall,
    PageClassificationEvidence,
    PageClassifierProviderFailure,
    VisibleControlEvidence,
)
from booksaver.application.model_policy import AdmittedModelAttempt
from booksaver.application.ports import PageSnapshot
from booksaver.domain.agent import ElementInfo, LLMUsage, Observation
from booksaver.domain.browser_resilience import (
    DomStepId,
    EvidenceCategory,
    FreshPageObservation,
    OperatorAction,
    PageState,
    PageStateSource,
)
from booksaver.domain.model_policy import (
    AdaptiveModelPortfolio,
    CallerKeyRef,
    CostReservation,
    EscalationTrigger,
    ModelAttemptPlan,
    ModelProfile,
    ModelRole,
    ReservationStatus,
    UsdAmount,
)
from booksaver.infrastructure.browser.page_state import (
    classification_inputs_from_observation,
)
from booksaver.infrastructure.llm.anthropic_adapter import LLMFailureKind
from booksaver.infrastructure.llm.page_state_classifier import (
    AnthropicPageStateClassifier,
    CallerBoundPageStateClassifier,
    classification_evidence_from_page,
)


def _profile(*, opus: bool = False) -> ModelProfile:
    portfolio = AdaptiveModelPortfolio()
    factory = portfolio.escalation if opus else portfolio.primary
    return factory(ModelRole.CLASSIFICATION, "booking-page-state-v2")


def _attempt(profile: ModelProfile) -> AdmittedModelAttempt:
    return AdmittedModelAttempt(
        plan=ModelAttemptPlan(
            ordinal=1,
            profile=profile,
            trigger=EscalationTrigger.INITIAL_AMBIGUOUS,
        ),
        reservation=CostReservation(
            reservation_id="classifier-reservation-1",
            job_id="classifier-job-1",
            utc_date=date(2026, 8, 13),
            profile=profile,
            reserved_cost=UsdAmount(25_000),
            status=ReservationStatus.RESERVED,
        ),
        caller_key_ref=CallerKeyRef(1, "personal", "encrypted_user_key"),
    )


def _observation() -> FreshPageObservation:
    return FreshPageObservation(
        observation_id="page-observation-1",
        observed_at=datetime(2026, 8, 13, tzinfo=UTC),
        evidence=frozenset({EvidenceCategory.WEAK_ACCOUNT_CHROME}),
    )


def _evidence() -> PageClassificationEvidence:
    return PageClassificationEvidence(
        observation_id="page-observation-1",
        title="Your Booking account",
        visible_text="Manage your trips or sign in to continue",
        controls=(
            VisibleControlEvidence(reference="e0", role="button", label="Continue"),
            VisibleControlEvidence(
                reference="e1",
                role="link",
                label="Bookings and trips",
            ),
        ),
    )


def _tool_input(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "state": "authentication_required",
        "confidence": 0.97,
        "evidence_categories": ["credential_control"],
        "evidence_references": [{"category": "credential_control", "reference": "e0"}],
        "operator_action": "connect",
    }
    value.update(overrides)
    return value


def _response(tool_input: dict[str, object]):
    return SimpleNamespace(
        content=[
            ToolUseBlock(
                type="tool_use",
                id="tool-classifier-1",
                name="classify_page_state",
                input=tool_input,
            )
        ],
        usage=SimpleNamespace(input_tokens=210, output_tokens=44),
    )


def _classifier(profile: ModelProfile, response_or_exception: object):
    calls: list[dict[str, object]] = []

    class _Messages:
        def create(self, **kwargs):
            calls.append(kwargs)
            if isinstance(response_or_exception, Exception):
                raise response_or_exception
            return response_or_exception

    classifier = AnthropicPageStateClassifier.__new__(AnthropicPageStateClassifier)
    classifier._profile = profile  # noqa: SLF001
    classifier._client = SimpleNamespace(messages=_Messages())  # noqa: SLF001
    return classifier, calls


def _classify(
    classifier: AnthropicPageStateClassifier,
    profile: ModelProfile,
) -> ModelClassifierCall:
    return classifier.classify(
        step=DOM_STEP_REGISTRY.definition(DomStepId.SESSION_VALIDATION),
        observation=_observation(),
        evidence=_evidence(),
        attempt=_attempt(profile),
    )


def _remote_inventory_evidence() -> PageClassificationEvidence:
    return PageClassificationEvidence(
        observation_id="page-observation-1",
        title="Changed trips page",
        visible_text="Reservation inventory is visible",
        controls=(
            VisibleControlEvidence(
                reference="e0",
                role="heading",
                label="Your stays",
            ),
            VisibleControlEvidence(
                reference="e1",
                role="tab",
                label="Current",
            ),
        ),
    )


def _classify_remote_inventory(
    classifier: AnthropicPageStateClassifier,
    profile: ModelProfile,
    evidence: PageClassificationEvidence | None = None,
) -> ModelClassifierCall:
    return classifier.classify(
        step=DOM_STEP_REGISTRY.definition(DomStepId.REMOTE_AUTH_SESSION_CAPTURE),
        observation=_observation(),
        evidence=evidence or _remote_inventory_evidence(),
        attempt=_attempt(profile),
    )


def test_valid_tool_reply_returns_typed_decision_and_usage() -> None:
    profile = _profile()
    classifier, calls = _classifier(profile, _response(_tool_input()))

    result = _classify(classifier, profile)

    assert result.decision is not None
    assert result.decision.state is PageState.AUTHENTICATION_REQUIRED
    assert result.decision.operator_action is OperatorAction.CONNECT
    assert result.decision.evidence == frozenset({EvidenceCategory.CREDENTIAL_CONTROL})
    assert result.usage == LLMUsage(input_tokens=210, output_tokens=44)
    assert calls[0]["model"] == "claude-sonnet-5"
    assert calls[0]["tool_choice"] == {
        "type": "tool",
        "name": "classify_page_state",
    }


def test_request_contains_only_bounded_text_and_groundable_controls() -> None:
    profile = _profile()
    classifier, calls = _classifier(profile, _response(_tool_input()))

    _classify(classifier, profile)

    request = str(calls[0]["messages"])
    assert "Your Booking account" in request
    assert "Bookings and trips" in request
    assert '"reference":"e0"' in request
    assert '"reference":"e1"' in request
    assert "selector" not in request.casefold()
    assert "screenshot" not in request.casefold()
    assert "https://" not in request
    assert "href" not in request.casefold()
    assert "cookie" not in request.casefold()
    assert "control_value" not in request.casefold()
    assert "sk-ant" not in request


def test_authenticated_model_state_is_candidate_not_verified() -> None:
    profile = _profile()
    classifier, _ = _classifier(
        profile,
        _response(
            _tool_input(
                state="authenticated_candidate",
                evidence_categories=["weak_account_chrome"],
                evidence_references=[],
                operator_action="none",
            )
        ),
    )

    result = _classify(classifier, profile)

    assert result.decision is not None
    classification = result.decision.classification(
        source=PageStateSource.SONNET,
        observation_id="page-observation-1",
    )
    assert classification.state is PageState.AUTHENTICATED_CANDIDATE


def test_remote_inventory_claim_requires_grounded_heading_and_companion_refs() -> None:
    profile = _profile()
    classifier, _ = _classifier(
        profile,
        _response(
            _tool_input(
                state="inventory",
                evidence_categories=["supported_inventory_structure"],
                evidence_references=[
                    {
                        "category": "supported_inventory_structure",
                        "reference": "e0",
                    },
                    {
                        "category": "supported_inventory_structure",
                        "reference": "e1",
                    },
                ],
                operator_action="none",
            )
        ),
    )

    result = _classify_remote_inventory(classifier, profile)

    assert result.schema_valid
    assert result.decision is not None
    assert result.decision.state is PageState.INVENTORY


@pytest.mark.parametrize(
    ("references", "controls"),
    [
        (
            [
                {"category": "supported_inventory_structure", "reference": "invented"},
                {"category": "supported_inventory_structure", "reference": "e1"},
            ],
            _remote_inventory_evidence().controls,
        ),
        (
            [
                {"category": "supported_inventory_structure", "reference": "e0"},
                {"category": "supported_inventory_structure", "reference": "e1"},
            ],
            (
                VisibleControlEvidence(reference="e0", role="button", label="Accept"),
                VisibleControlEvidence(reference="e1", role="link", label="Account"),
            ),
        ),
    ],
)
def test_remote_inventory_claim_rejects_invented_or_insufficient_structure(
    references: list[dict[str, str]],
    controls: tuple[VisibleControlEvidence, ...],
) -> None:
    profile = _profile()
    classifier, _ = _classifier(
        profile,
        _response(
            _tool_input(
                state="inventory",
                evidence_categories=["supported_inventory_structure"],
                evidence_references=references,
                operator_action="none",
            )
        ),
    )
    evidence = PageClassificationEvidence(
        observation_id="page-observation-1",
        title="Changed trips page",
        visible_text="Reservation inventory is visible",
        controls=controls,
    )

    result = _classify_remote_inventory(classifier, profile, evidence)

    assert not result.schema_valid
    assert result.decision is None


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(content=[], usage=None),
        SimpleNamespace(
            content=[TextBlock(type="text", text="authentication_required")],
            usage=None,
        ),
        _response(_tool_input(extra="unexpected")),
        _response(_tool_input(confidence=True)),
        _response(_tool_input(state="verified_authenticated")),
        _response(_tool_input(operator_action="none")),
        _response(
            _tool_input(
                evidence_categories=[],
                evidence_references=[{"category": "credential_control", "reference": "e0"}],
            )
        ),
    ],
)
def test_malformed_or_untrusted_tool_reply_is_typed_invalid_schema(response) -> None:
    profile = _profile()
    classifier, _ = _classifier(profile, response)

    result = _classify(classifier, profile)

    assert not result.schema_valid
    assert result.decision is None
    assert result.provider_failure is None


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (LLMFailureKind.AUTHENTICATION, PageClassifierProviderFailure.AUTHENTICATION),
        (LLMFailureKind.RATE_LIMIT, PageClassifierProviderFailure.RATE_LIMIT),
        (LLMFailureKind.UNAVAILABLE, PageClassifierProviderFailure.UNAVAILABLE),
        (LLMFailureKind.TRANSPORT, PageClassifierProviderFailure.TRANSPORT),
    ],
)
def test_provider_failures_remain_typed_without_provider_detail(
    monkeypatch,
    kind: LLMFailureKind,
    expected: PageClassifierProviderFailure,
) -> None:
    import booksaver.infrastructure.llm.page_state_classifier as module

    monkeypatch.setattr(module, "_provider_failure_kind", lambda exc: kind)
    profile = _profile()
    classifier, _ = _classifier(profile, RuntimeError("sensitive sk-ant detail"))

    result = _classify(classifier, profile)

    assert result.provider_failure is expected
    assert result.decision is None
    assert "sensitive" not in repr(result)


def test_transport_failure_is_detected_from_timeout_without_message_matching() -> None:
    profile = _profile()
    classifier, _ = _classifier(profile, TimeoutError("private transport detail"))

    result = _classify(classifier, profile)

    assert result.provider_failure is PageClassifierProviderFailure.TRANSPORT


def test_classifier_refuses_unadmitted_or_wrong_role_profiles() -> None:
    profile = _profile()
    classifier, calls = _classifier(profile, _response(_tool_input()))

    with pytest.raises(ValueError, match="admitted profile"):
        classifier.classify(
            step=DOM_STEP_REGISTRY.definition(DomStepId.SESSION_VALIDATION),
            observation=_observation(),
            evidence=_evidence(),
            attempt=_attempt(_profile(opus=True)),
        )
    assert not calls

    recovery_profile = AdaptiveModelPortfolio().primary(
        ModelRole.RECOVERY,
        "booking-page-state-v2",
    )
    with pytest.raises(ValueError, match="classification profile"):
        AnthropicPageStateClassifier(api_key="sk-test", profile=recovery_profile)


def test_caller_bound_wrapper_builds_only_the_admitted_fixed_profile() -> None:
    built: list[ModelProfile] = []
    calls: list[ModelProfile] = []

    class _Delegate:
        def __init__(self, profile: ModelProfile) -> None:
            self.profile = profile

        def classify(self, *, step, observation, evidence, attempt):
            calls.append(attempt.plan.profile)
            assert attempt.plan.profile == self.profile
            return ModelClassifierCall(provider_failure=PageClassifierProviderFailure.RATE_LIMIT)

    class _Factory:
        def page_classifier(self, profile: ModelProfile):
            built.append(profile)
            return _Delegate(profile)

    classifier = CallerBoundPageStateClassifier(_Factory())
    step = DOM_STEP_REGISTRY.definition(DomStepId.SESSION_VALIDATION)
    sonnet = _profile()
    opus = _profile(opus=True)

    for profile in (sonnet, sonnet, opus):
        classifier.classify(
            step=step,
            observation=_observation(),
            evidence=_evidence(),
            attempt=_attempt(profile),
        )

    assert built == [sonnet, opus]
    assert calls == [sonnet, sonnet, opus]


def test_agent_observation_conversion_drops_browser_authority_and_sensitive_fragments() -> None:
    page = Observation(
        url="https://secure.booking.com/mytrips?token=private",
        title="Trips https://private.example/path",
        text=(
            "Unknown changed layout ?token=secret cookie: session-secret [data-testid='private']"
        ),
        elements=(
            ElementInfo(
                ref="e7",
                role="link",
                label="Trips https://private.example/path",
                href="https://secure.booking.com/mytrips?token=private",
            ),
            ElementInfo(
                ref="e8",
                role="button",
                label="Continue",
                href=None,
            ),
        ),
        screenshot=b"private-pixels",
        popup_urls=("https://private.example/popup",),
    )

    evidence = classification_evidence_from_page(page, _observation())

    rendered = repr(evidence)
    assert "https://" not in rendered
    assert "session-secret" not in rendered
    assert "data-testid" not in rendered
    assert "token=secret" not in rendered
    assert "reference='e7'" in rendered
    assert "reference='e8'" in rendered
    assert "private-pixels" not in rendered
    assert "popup" not in rendered
    assert evidence.controls[-1] == VisibleControlEvidence(
        reference="e8",
        role="button",
        label="Continue",
    )


@pytest.mark.parametrize(
    "protected",
    [
        EvidenceCategory.CREDENTIAL_CONTROL,
        EvidenceCategory.MFA_CONTROL,
        EvidenceCategory.CAPTCHA_CHALLENGE,
        EvidenceCategory.BOT_WALL,
    ],
)
def test_possible_protected_page_conversion_suppresses_text_and_controls(
    protected: EvidenceCategory,
) -> None:
    observation = FreshPageObservation(
        observation_id="protected-observation-1",
        observed_at=datetime(2026, 8, 13, tzinfo=UTC),
        evidence=frozenset({protected}),
    )
    page = PageSnapshot(
        url="https://secure.booking.com/login?token=private",
        title="Private account",
        text="person@example.com secret typed value",
    )

    evidence = classification_evidence_from_page(page, observation)

    assert evidence.title == ""
    assert evidence.visible_text == ""
    assert evidence.controls == ()
    assert not evidence.screenshot_allowed


def test_runtime_observation_converter_suppresses_possible_login_content() -> None:
    observation = Observation(
        url="https://account.booking.com/sign-in?token=private",
        title="Sign in for person@example.com",
        text="Enter your password secret typed value",
        elements=(
            ElementInfo(
                ref="e1",
                role="input",
                label="person@example.com",
            ),
        ),
        screenshot=b"private-pixels",
    )

    fresh, evidence = classification_inputs_from_observation(observation)

    assert EvidenceCategory.CREDENTIAL_CONTROL in fresh.evidence
    assert evidence.title == ""
    assert evidence.visible_text == ""
    assert evidence.controls == ()
    assert not evidence.screenshot_allowed
