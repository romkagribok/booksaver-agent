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

    def test_booking_argument_does_not_change_resolution_this_slice(self):
        """US-029 seam: `booking` is accepted but unused today — resolution
        is identical whether a booking is passed or not. A later slice
        changes this without touching call sites.
        """
        from .monitor.fakes import make_booking

        factory = AnthropicLLMClientFactory(_config(), api_key="sk-test-key")
        without_booking = factory.for_booking(None)
        with_booking = factory.for_booking(make_booking())
        assert type(without_booking) is type(with_booking)
