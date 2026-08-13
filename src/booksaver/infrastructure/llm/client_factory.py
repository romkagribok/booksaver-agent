from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from booksaver.application.ports import AgentBrain, InventoryInterpreter, LLMExtractor
from booksaver.domain.errors import SecretKeyError, UserKeyInvalidError
from booksaver.domain.model_policy import CallerKeyRef, ModelProfile, ModelRole

if TYPE_CHECKING:
    from booksaver.application.model_policy import BrowserJobCostBudget
    from booksaver.application.ports import RegisteredPageStateResolver, UserRepository
    from booksaver.domain.models import Booking, Config
    from booksaver.domain.user import User
    from booksaver.infrastructure.crypto.fernet_key_store import FernetKeyStore
    from booksaver.infrastructure.llm.adaptive_execution import (
        AdaptiveAnthropicRuntimeFactory,
    )
    from booksaver.infrastructure.llm.page_state_classifier import (
        AnthropicPageStateClassifier,
    )

logger = logging.getLogger(__name__)


class AnthropicLLMClientFactory:
    """LLMClientFactory seam (US-029/US-027): builds extraction/agent LLM
    clients, resolving a per-booking key when the booking's owner has one.

    Hybrid billing (US-027): when `user_repo`/`key_store` are supplied and a
    `booking` is given, the booking's owning user is resolved; if that user
    has `encrypted_key` set, it is decrypted and used for *that user's* LLM
    work instead of the owner's env-var key. Any other booking (or any
    caller that omits `user_repo`/`key_store`, e.g. CLI paths that don't yet
    have a `Booking` in hand) falls back to the single owner env-var key —
    byte-identical to pre-US-027 behavior.

    A user whose personal key cannot be decrypted (missing/invalid
    `BOOKSAVER_SECRET_KEY`, corrupt ciphertext) raises `UserKeyInvalidError`
    rather than silently falling back to the owner key — callers (the check
    job) map this to `FailureCode.USER_KEY_INVALID` so the failure is
    attributed to the right user and they're told to `/setkey` again or
    `/deletekey`. A missing/unset key (no personal key at all) is not an
    error — it degrades to DOM-only/scripted-only mode (ADR-009) exactly as
    before, never raises.
    """

    def __init__(
        self,
        cfg: Config,
        api_key: str | None = None,
        user_repo: UserRepository | None = None,
        key_store: FernetKeyStore | None = None,
    ) -> None:
        self._cfg = cfg
        # Explicit api_key (mainly for tests); default resolves the owner's
        # env var, matching the pre-v7 _make_llm_extractor/_make_agent_brain.
        self._owner_api_key = (
            api_key if api_key is not None else os.environ.get("BOOKSAVER_LLM_API_KEY")
        )
        self._user_repo = user_repo
        self._key_store = key_store

    def _resolve_api_key(self, booking: Booking | None) -> str | None:
        owner = self._resolve_owner(booking)
        return self._resolve_api_key_for_user(owner)

    def _resolve_api_key_for_user(self, owner: User | None) -> str | None:
        if owner is not None and owner.encrypted_key is not None:
            if self._key_store is None:
                raise UserKeyInvalidError(
                    owner.user_id,
                    "personal API key cannot be decrypted because the key store is unavailable",
                )
            try:
                return self._key_store.decrypt(owner.encrypted_key)
            except SecretKeyError as exc:
                raise UserKeyInvalidError(owner.user_id, str(exc)) from exc
        return self._owner_api_key

    def _resolve_active_user(self, user_id: int) -> User | None:
        if self._user_repo is None:
            logger.warning("Cannot resolve user-scoped LLM capability without a user repository")
            return None
        user = self._user_repo.get_by_id(user_id)
        if user is None or not user.is_active:
            logger.warning("User-scoped LLM capability unavailable for inactive or unknown user")
            return None
        return user

    def _resolve_owner(self, booking: Booking | None) -> User | None:
        if booking is None or self._user_repo is None:
            return None
        return self._user_repo.get_owner_of_booking(booking.booking_id)

    def for_booking(self, booking: Booking | None) -> LLMExtractor | None:
        api_key = self._resolve_api_key(booking)
        if not api_key:
            logger.warning(
                "BOOKSAVER_LLM_API_KEY not set — LLM extraction disabled (DOM-only mode)"
            )
            return None
        try:
            from booksaver.infrastructure.llm.anthropic_adapter import AnthropicExtractor

            model = self._cfg.extraction_settings.get(
                "model", self._cfg.agent_settings.primary_model
            )
            return AnthropicExtractor(api_key=api_key, model=model)
        except ImportError:
            logger.warning(
                "anthropic package not installed — LLM extraction disabled (DOM-only mode)"
            )
            return None

    def agent_brain_for_booking(self, booking: Booking | None) -> AgentBrain | None:
        if booking is not None and self._user_repo is not None:
            owner = self._resolve_owner(booking)
            if owner is None:
                logger.warning("Cannot resolve agent brain for an unowned booking")
                return None
            return self.agent_brain_for_user(owner.user_id)
        return self._build_agent_brain(self._resolve_api_key(booking), role="navigation_agent")

    def agent_brain_for_user(
        self, user_id: int, role: str = "navigation_agent"
    ) -> AgentBrain | None:
        """Resolve a navigation brain for one explicit active local user."""
        if role != "navigation_agent":
            raise ValueError(f"Unsupported agent role: {role!r}")
        user = self._resolve_active_user(user_id)
        if user is None:
            return None
        return self._build_agent_brain(self._resolve_api_key_for_user(user), role=role)

    def _build_agent_brain(self, api_key: str | None, *, role: str) -> AgentBrain | None:
        if not api_key:
            logger.warning(
                "BOOKSAVER_LLM_API_KEY not set — agent escalation disabled (scripted-only)"
            )
            return None
        try:
            from booksaver.infrastructure.llm.anthropic_adapter import AnthropicAgentBrain

            model = self._cfg.agent_settings.primary_model
            brain = AnthropicAgentBrain(api_key=api_key, model=model)
            if brain.role != role:
                raise ValueError(f"Agent brain does not implement role {role!r}")
            return brain
        except ImportError:
            logger.warning(
                "anthropic package not installed — agent escalation disabled (scripted-only)"
            )
            return None

    def inventory_interpreter_for_user(
        self, user_id: int, role: str = "inventory_interpreter"
    ) -> InventoryInterpreter | None:
        """Resolve positive-only inventory interpretation for an active user."""
        if role != "inventory_interpreter":
            raise ValueError(f"Unsupported inventory interpreter role: {role!r}")
        user = self._resolve_active_user(user_id)
        if user is None:
            return None
        api_key = self._resolve_api_key_for_user(user)
        if not api_key:
            logger.warning("BOOKSAVER_LLM_API_KEY not set — inventory interpretation disabled")
            return None
        try:
            from booksaver.infrastructure.llm.anthropic_adapter import (
                AnthropicInventoryInterpreter,
            )

            model = self._cfg.extraction_settings.get(
                "model", self._cfg.agent_settings.primary_model
            )
            interpreter = AnthropicInventoryInterpreter(api_key=api_key, model=model)
            if interpreter.role != role:
                raise ValueError(f"Inventory interpreter does not implement role {role!r}")
            return interpreter
        except ImportError:
            logger.warning("anthropic package not installed — inventory interpretation disabled")
            return None

    def caller_key_ref_for_user(self, user_id: int) -> CallerKeyRef | None:
        """Describe one active caller's funding source without decrypting it.

        Coordinator admissions need an immutable caller identity before any
        ambiguous browser work exists.  This method deliberately performs no
        secret-key operation and constructs no provider client.
        """
        user = self._resolve_active_user(user_id)
        if user is None:
            return None
        if user.encrypted_key is not None:
            return CallerKeyRef(
                caller_user_id=user.user_id,
                funding_mode="personal",
                provenance="encrypted_user_key",
            )
        if not self._owner_api_key:
            return None
        return CallerKeyRef(
            caller_user_id=user.user_id,
            funding_mode="shared",
            provenance="owner_env",
        )

    def bind_for_user(
        self,
        user_id: int,
        *,
        expected_key_ref: CallerKeyRef | None = None,
    ) -> CallerBoundAnthropicFactory | None:
        """Resolve one active caller and key once for a Sonnet/Opus episode."""
        user = self._resolve_active_user(user_id)
        if user is None:
            return None
        key_ref = self.caller_key_ref_for_user(user_id)
        if key_ref is None:
            return None
        if expected_key_ref is not None and key_ref != expected_key_ref:
            raise UserKeyInvalidError(
                user_id,
                "caller LLM funding source changed after browser-job admission",
            )
        api_key = self._resolve_api_key_for_user(user)
        if not api_key:
            return None
        return CallerBoundAnthropicFactory(
            api_key=api_key,
            key_ref=key_ref,
        )

    def adaptive_runtime_for_user(
        self,
        user_id: int,
        budget: BrowserJobCostBudget,
    ) -> LazyAdaptiveAnthropicRuntimeFactory | None:
        """Return a role-lazy runtime sharing one admitted browser-job budget."""
        key_ref = self.caller_key_ref_for_user(user_id)
        if key_ref is None:
            return None
        if key_ref != budget.caller_key_ref:
            raise ValueError("adaptive budget does not belong to the requested caller")
        return LazyAdaptiveAnthropicRuntimeFactory(
            factory=self,
            user_id=user_id,
            key_ref=key_ref,
            budget=budget,
        )

    def bind_for_booking(self, booking: Booking) -> CallerBoundAnthropicFactory | None:
        if self._user_repo is None:
            return None
        owner = self._resolve_owner(booking)
        if owner is None or not owner.is_active:
            return None
        return self.bind_for_user(owner.user_id)


class CallerBoundAnthropicFactory:
    """Build both approved tiers from one immutable caller key resolution."""

    def __init__(self, *, api_key: str, key_ref: CallerKeyRef) -> None:
        self._api_key = api_key
        self.key_ref = key_ref

    def agent_brain(self, profile: ModelProfile) -> AgentBrain:
        if profile.role not in {
            ModelRole.RECOVERY,
            ModelRole.CLASSIFICATION,
            ModelRole.DIAGNOSTIC,
        }:
            raise ValueError(f"Profile role {profile.role.value!r} is not an agent role")
        from booksaver.infrastructure.llm.anthropic_adapter import AnthropicAgentBrain

        return AnthropicAgentBrain(api_key=self._api_key, model=profile.model_id)

    def inventory_interpreter(self, profile: ModelProfile) -> InventoryInterpreter:
        if profile.role is not ModelRole.INTERPRETATION:
            raise ValueError("Inventory interpreter requires an interpretation profile")
        from booksaver.infrastructure.llm.anthropic_adapter import (
            AnthropicInventoryInterpreter,
        )

        return AnthropicInventoryInterpreter(api_key=self._api_key, model=profile.model_id)

    def extractor(self, profile: ModelProfile) -> LLMExtractor:
        if profile.role is not ModelRole.EXTRACTION:
            raise ValueError("Extractor requires an extraction profile")
        from booksaver.infrastructure.llm.anthropic_adapter import AnthropicExtractor

        return AnthropicExtractor(api_key=self._api_key, model=profile.model_id)

    def page_classifier(self, profile: ModelProfile) -> AnthropicPageStateClassifier:
        if profile.role is not ModelRole.CLASSIFICATION:
            raise ValueError("Page classifier requires a classification profile")
        from booksaver.infrastructure.llm.page_state_classifier import (
            AnthropicPageStateClassifier,
        )

        return AnthropicPageStateClassifier(api_key=self._api_key, profile=profile)

    def adaptive_runtime(self, budget: BrowserJobCostBudget) -> AdaptiveAnthropicRuntimeFactory:
        """Bind approved role adapters to one caller-scoped browser-job budget."""
        from booksaver.infrastructure.llm.adaptive_execution import (
            AdaptiveAnthropicRuntimeFactory,
        )

        return AdaptiveAnthropicRuntimeFactory(delegates=self, budget=budget)


class LazyAdaptiveAnthropicRuntimeFactory:
    """Resolve the caller secret only when an ambiguous role is invoked.

    Search and inventory construct role adapters before their deterministic
    checks finish.  These proxies keep that construction side-effect free:
    decrypting a personal key and creating Anthropic clients happens on the
    first actual ``decide``/``interpret``/``extract`` call.
    """

    def __init__(
        self,
        *,
        factory: AnthropicLLMClientFactory,
        user_id: int,
        key_ref: CallerKeyRef,
        budget: BrowserJobCostBudget,
    ) -> None:
        self._factory = factory
        self._user_id = user_id
        self._key_ref = key_ref
        self._budget = budget
        self._lock = threading.Lock()
        self._bound: CallerBoundAnthropicFactory | None = None
        self._runtime: AdaptiveAnthropicRuntimeFactory | None = None

    @property
    def budget(self) -> BrowserJobCostBudget:
        return self._budget

    def _resolved_runtime(self) -> AdaptiveAnthropicRuntimeFactory:
        with self._lock:
            if self._runtime is None:
                self._runtime = self._resolved_delegates_locked().adaptive_runtime(self._budget)
            return self._runtime

    def _resolved_delegates(self) -> CallerBoundAnthropicFactory:
        with self._lock:
            return self._resolved_delegates_locked()

    def _resolved_delegates_locked(self) -> CallerBoundAnthropicFactory:
        if self._bound is None:
            bound = self._factory.bind_for_user(
                self._user_id,
                expected_key_ref=self._key_ref,
            )
            if bound is None:
                raise RuntimeError("caller-scoped adaptive model runtime is unavailable")
            self._bound = bound
        return self._bound

    def agent_brain(self, **kwargs: Any) -> Any:
        return _LazyRoleProxy(
            lambda: self._resolved_runtime().agent_brain(**kwargs),
            provider="anthropic",
            role="navigation_agent",
            prompt_version=kwargs.get("prompt_version", "booking-browser-recovery-v5"),
        )

    def inventory_interpreter(self, **kwargs: Any) -> Any:
        return _LazyRoleProxy(
            lambda: self._resolved_runtime().inventory_interpreter(**kwargs),
            provider="anthropic",
            role="inventory_interpreter",
            prompt_version=kwargs.get("prompt_version", "booking-inventory-interpretation-v1"),
        )

    def extractor(self, **kwargs: Any) -> Any:
        return _LazyRoleProxy(
            lambda: self._resolved_runtime().extractor(**kwargs),
            provider="anthropic",
            role="offer_extractor",
            prompt_version=kwargs.get("prompt_version", "booking-offer-extraction-v1"),
        )

    def page_state_resolver(self) -> RegisteredPageStateResolver:
        """Return protected-first classification using this job's one budget."""
        from booksaver.application.browser_resilience import PageStateResolver

        return _RegisteredPageStateResolverAdapter(
            resolver=PageStateResolver(_LazyPageStateClassifier(self)),
            budget=self._budget,
        )


class _LazyRoleProxy:
    """Small protocol-preserving proxy for one adaptive role adapter."""

    def __init__(
        self,
        resolver: Callable[[], Any],
        *,
        provider: str,
        role: str,
        prompt_version: str,
    ) -> None:
        self._resolver = resolver
        self._lock = threading.Lock()
        self._delegate = None
        self.provider = provider
        self.role = role
        self.prompt_version = prompt_version

    def _resolve(self) -> Any:
        with self._lock:
            if self._delegate is None:
                self._delegate = self._resolver()
            return self._delegate

    @property
    def model(self) -> str:
        if self._delegate is None:
            return "claude-sonnet-5"
        return self._delegate.model

    @property
    def last_usage(self) -> Any:
        if self._delegate is None:
            return None
        return self._delegate.last_usage

    @property
    def last_profile(self) -> Any:
        if self._delegate is None:
            return None
        return getattr(self._delegate, "last_profile", None)

    def decide(self, context: Any) -> Any:
        return self._resolve().decide(context)

    def decide_with_escalation(self, context: Any, trigger: Any) -> Any:
        return self._resolve().decide_with_escalation(context, trigger)

    def interpret(self, page_text: str, source_url: str) -> Any:
        return self._resolve().interpret(page_text, source_url)

    def interpret_with_escalation(
        self,
        page_text: str,
        source_url: str,
        trigger: Any,
    ) -> Any:
        return self._resolve().interpret_with_escalation(page_text, source_url, trigger)

    def extract_price(self, page_text: str, booking: Any) -> Any:
        return self._resolve().extract_price(page_text, booking)

    def extract_offers(self, page_text: str, booking: Any) -> Any:
        return self._resolve().extract_offers(page_text, booking)

    def extract_offers_with_escalation(
        self,
        page_text: str,
        booking: Any,
        trigger: Any,
    ) -> Any:
        return self._resolve().extract_offers_with_escalation(
            page_text,
            booking,
            trigger,
        )


class _LazyPageStateClassifier:
    """Delay caller-key resolution until deterministic classification is ambiguous."""

    def __init__(self, runtime: LazyAdaptiveAnthropicRuntimeFactory) -> None:
        self._runtime = runtime
        self._lock = threading.Lock()
        self._delegate: Any = None

    def classify(self, **kwargs: Any) -> Any:
        with self._lock:
            if self._delegate is None:
                from booksaver.infrastructure.llm.page_state_classifier import (
                    CallerBoundPageStateClassifier,
                )

                bound = self._runtime._resolved_delegates()
                self._delegate = CallerBoundPageStateClassifier(bound)
        return self._delegate.classify(**kwargs)


class _RegisteredPageStateResolverAdapter:
    """Translate agent observations into the shared protected-first resolver."""

    def __init__(self, *, resolver: Any, budget: BrowserJobCostBudget) -> None:
        self._resolver = resolver
        self._budget = budget

    def resolve(self, step_id: Any, observation: Any) -> Any:
        from booksaver.infrastructure.browser.page_state import (
            classification_inputs_from_observation,
        )

        fresh, evidence = classification_inputs_from_observation(observation)
        return self._resolver.resolve(
            step_id=step_id,
            observation=fresh,
            classification_evidence=evidence,
            budget_factory=lambda: self._budget,
        )
