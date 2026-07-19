from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from booksaver.domain.agent import AgentSettings
from booksaver.domain.errors import ConfigValidationError
from booksaver.domain.models import Config
from booksaver.domain.value_objects import (
    CheckInterval,
    DataDirectory,
    LimitsSettings,
    NotificationSettings,
    TelegramBotSettings,
)

from .ports import ConfigSource


def load_config(source: ConfigSource) -> Config:
    raw: dict[str, Any] = source.read()
    errors: list[str] = []

    check_interval: CheckInterval | None = None
    interval_str: str | None = raw.get("schedule", {}).get("check_interval")
    if not interval_str:
        errors.append("schedule.check_interval is required")
    else:
        try:
            check_interval = CheckInterval.parse(interval_str)
        except ValueError as e:
            errors.append(f"schedule.check_interval: {e}")

    data_directory: DataDirectory | None = None
    data_dir_str: str | None = raw.get("storage", {}).get("data_directory")
    if not data_dir_str:
        errors.append("storage.data_directory is required")
    else:
        try:
            data_directory = DataDirectory.of(data_dir_str)
        except ValueError as e:
            errors.append(f"storage.data_directory: {e}")

    agent_settings: AgentSettings | None = None
    agent_raw = raw.get("agent", {})
    try:
        defaults = AgentSettings()
        agent_settings = AgentSettings(
            max_steps=int(agent_raw.get("max_steps", defaults.max_steps)),
            max_llm_calls=int(agent_raw.get("max_llm_calls", defaults.max_llm_calls)),
            check_timeout_seconds=int(
                agent_raw.get("check_timeout_seconds", defaults.check_timeout_seconds)
            ),
            model=str(agent_raw.get("model", defaults.model)),
        )
    except (ValueError, TypeError) as e:
        errors.append(f"agent: {e}")

    telegram_bot_settings: TelegramBotSettings | None = None
    telegram_raw = raw.get("telegram_bot", {})
    try:
        tg_enabled = bool(telegram_raw.get("enabled", False))
        owner_chat_id_raw = telegram_raw.get("owner_chat_id")
        owner_chat_id = int(owner_chat_id_raw) if owner_chat_id_raw is not None else None
        poll_timeout_raw = int(telegram_raw.get("poll_timeout_seconds", 30))
        poll_timeout_seconds = min(max(poll_timeout_raw, 25), 50)  # clamp per US-023
        # `owner` is accepted only so existing VPS config files keep starting;
        # TelegramBotSettings normalizes it to the fixed invite-only posture.
        access_mode = str(telegram_raw.get("access_mode", "invite"))
        rebook_timeout_defaults = TelegramBotSettings()
        rebook_confirm_timeout_seconds = int(
            telegram_raw.get(
                "rebook_confirm_timeout_seconds",
                rebook_timeout_defaults.rebook_confirm_timeout_seconds,
            )
        )
        if tg_enabled and owner_chat_id is None:
            raise ValueError("owner_chat_id is required when telegram_bot.enabled is true")
        telegram_bot_settings = TelegramBotSettings(
            enabled=tg_enabled,
            owner_chat_id=owner_chat_id,
            poll_timeout_seconds=poll_timeout_seconds,
            access_mode=access_mode,
            rebook_confirm_timeout_seconds=rebook_confirm_timeout_seconds,
        )
    except (ValueError, TypeError) as e:
        errors.append(f"telegram_bot: {e}")

    # ── [limits] (US-031, bolt 010) — additive section, new-worker-owned ──────
    limits_settings: LimitsSettings | None = None
    limits_raw = raw.get("limits", {})
    try:
        limits_defaults = LimitsSettings()
        limits_settings = LimitsSettings(
            max_bookings_per_user=int(
                limits_raw.get("max_bookings_per_user", limits_defaults.max_bookings_per_user)
            ),
            max_checks_per_user_per_day=int(
                limits_raw.get(
                    "max_checks_per_user_per_day", limits_defaults.max_checks_per_user_per_day
                )
            ),
            max_llm_calls_per_user_per_day=int(
                limits_raw.get(
                    "max_llm_calls_per_user_per_day",
                    limits_defaults.max_llm_calls_per_user_per_day,
                )
            ),
            messages_per_minute_per_chat=int(
                limits_raw.get(
                    "messages_per_minute_per_chat", limits_defaults.messages_per_minute_per_chat
                )
            ),
        )
    except (ValueError, TypeError) as e:
        errors.append(f"limits: {e}")
    # ── end [limits] ────────────────────────────────────────────────────────

    if errors:
        raise ConfigValidationError(errors)

    assert check_interval is not None
    assert data_directory is not None
    assert agent_settings is not None
    assert telegram_bot_settings is not None
    assert limits_settings is not None

    notifications_raw = raw.get("notifications", {})
    notification_settings = NotificationSettings(
        email=notifications_raw.get("email"),
        telegram_chat_id=(
            str(notifications_raw["telegram_chat_id"])
            if notifications_raw.get("telegram_chat_id") is not None
            else None
        ),
        smtp_host=notifications_raw.get("smtp_host"),
        smtp_port=int(notifications_raw.get("smtp_port", 587)),
        smtp_username=notifications_raw.get("smtp_username"),
    )

    extraction_settings = {
        str(k): str(v) for k, v in raw.get("extraction", {}).items() if v is not None
    }

    return Config(
        check_interval=check_interval,
        data_directory=data_directory,
        notification_settings=notification_settings,
        loaded_at=datetime.now(UTC),
        extraction_settings=extraction_settings,
        agent_settings=agent_settings,
        telegram_bot_settings=telegram_bot_settings,
        limits_settings=limits_settings,
    )
