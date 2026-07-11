"""US-029: LLMClientFactory seam — behavior must match pre-v7 owner-key
resolution exactly; the factory just adds the (currently unused) `booking`
parameter so a later slice can resolve per-user keys without a call-site
change.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from booksaver.domain.models import Config
from booksaver.domain.value_objects import CheckInterval, DataDirectory, NotificationSettings
from booksaver.infrastructure.llm.client_factory import AnthropicLLMClientFactory


def _config() -> Config:
    return Config(
        check_interval=CheckInterval(duration=timedelta(hours=6)),
        data_directory=DataDirectory(path=Path("/tmp/booksaver-test")),
        notification_settings=NotificationSettings(),
        loaded_at=datetime.now(UTC),
    )


class TestLLMClientFactory:
    def test_for_booking_returns_none_without_api_key(self):
        factory = AnthropicLLMClientFactory(_config(), api_key=None)
        assert factory.for_booking(None) is None

    def test_agent_brain_for_booking_returns_none_without_api_key(self):
        factory = AnthropicLLMClientFactory(_config(), api_key=None)
        assert factory.agent_brain_for_booking(None) is None

    def test_for_booking_builds_extractor_with_configured_model(self):
        factory = AnthropicLLMClientFactory(_config(), api_key="sk-test-key")
        extractor = factory.for_booking(None)
        assert extractor is not None

    def test_agent_brain_for_booking_builds_brain_with_configured_model(self):
        factory = AnthropicLLMClientFactory(_config(), api_key="sk-test-key")
        brain = factory.agent_brain_for_booking(None)
        assert brain is not None

    def test_booking_argument_does_not_change_resolution_without_user_repo(self):
        """Without a user_repo/key_store (pre-US-027 callers), resolution is
        identical whether a booking is passed or not — the owner key is
        always used.
        """
        from .monitor.fakes import make_booking

        factory = AnthropicLLMClientFactory(_config(), api_key="sk-test-key")
        without_booking = factory.for_booking(None)
        with_booking = factory.for_booking(make_booking())
        assert type(without_booking) is type(with_booking)


class _FakeUserRepo:
    def __init__(self, owner) -> None:
        self._owner = owner

    def get_owner_of_booking(self, booking_id: str):
        return self._owner


class _FakeKeyStore:
    def __init__(self, plaintext: str | None = None, raise_error: bool = False) -> None:
        self._plaintext = plaintext
        self._raise = raise_error

    def decrypt(self, ciphertext: bytes) -> str:
        if self._raise:
            from booksaver.domain.errors import SecretKeyError

            raise SecretKeyError("boom")
        assert self._plaintext is not None
        return self._plaintext


def _user(encrypted_key: bytes | None):
    from booksaver.domain.user import User, UserAccessState, UserRole

    return User(
        user_id=1,
        telegram_user_id=42,
        role=UserRole.USER,
        access_state=UserAccessState.ACTIVE,
        created_at=datetime.now(UTC),
        encrypted_key=encrypted_key,
    )


class TestHybridBilling:
    """US-027: booking -> owning user -> personal key, else owner key."""

    def test_falls_back_to_owner_key_when_user_has_no_personal_key(self):
        from .monitor.fakes import make_booking

        factory = AnthropicLLMClientFactory(
            _config(),
            api_key="sk-owner-key",
            user_repo=_FakeUserRepo(_user(encrypted_key=None)),
            key_store=_FakeKeyStore(),
        )
        assert factory.for_booking(make_booking()) is not None

    def test_uses_personal_key_when_set(self):
        from .monitor.fakes import make_booking

        factory = AnthropicLLMClientFactory(
            _config(),
            api_key=None,  # no owner key at all — only the personal key works
            user_repo=_FakeUserRepo(_user(encrypted_key=b"ciphertext")),
            key_store=_FakeKeyStore(plaintext="sk-personal-key"),
        )
        assert factory.for_booking(make_booking()) is not None

    def test_invalid_personal_key_raises_user_key_invalid_error(self):
        import pytest

        from booksaver.domain.errors import UserKeyInvalidError

        from .monitor.fakes import make_booking

        factory = AnthropicLLMClientFactory(
            _config(),
            api_key="sk-owner-key",
            user_repo=_FakeUserRepo(_user(encrypted_key=b"ciphertext")),
            key_store=_FakeKeyStore(raise_error=True),
        )

        with pytest.raises(UserKeyInvalidError):
            factory.for_booking(make_booking())

    def test_agent_brain_also_uses_personal_key(self):
        from .monitor.fakes import make_booking

        factory = AnthropicLLMClientFactory(
            _config(),
            api_key=None,
            user_repo=_FakeUserRepo(_user(encrypted_key=b"ciphertext")),
            key_store=_FakeKeyStore(plaintext="sk-personal-key"),
        )
        assert factory.agent_brain_for_booking(make_booking()) is not None

    def test_no_user_repo_behaves_like_pre_us027(self):
        from .monitor.fakes import make_booking

        factory = AnthropicLLMClientFactory(_config(), api_key="sk-owner-key")
        assert factory.for_booking(make_booking()) is not None
