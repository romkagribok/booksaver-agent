from __future__ import annotations

import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from booksaver.domain.agent import AgentSettings
from booksaver.domain.errors import ConfigValidationError
from booksaver.domain.mobile_web import MobileWebSettings
from booksaver.domain.models import Config
from booksaver.domain.remote_auth import RemoteAuthSettings
from booksaver.domain.schedule import ScheduleSettings
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

    schedule_raw = raw.get("schedule", {})
    check_interval: CheckInterval | None = None
    interval_str: str | None = schedule_raw.get("check_interval")
    if interval_str is not None:
        try:
            check_interval = CheckInterval.parse(interval_str)
        except ValueError as e:
            errors.append(f"schedule.check_interval: {e}")
        else:
            warnings.warn(
                "schedule.check_interval is deprecated and ignored; use "
                "checks_per_booking_per_day, minimum_spacing, and missed_run_grace",
                UserWarning,
                stacklevel=2,
            )

    schedule_settings: ScheduleSettings | None = None
    schedule_defaults = ScheduleSettings()
    try:
        schedule_settings = ScheduleSettings(
            checks_per_booking_per_day=int(
                schedule_raw.get(
                    "checks_per_booking_per_day",
                    schedule_defaults.checks_per_booking_per_day,
                )
            ),
            minimum_spacing=CheckInterval.parse(
                str(schedule_raw.get("minimum_spacing", "2h"))
            ).duration,
            missed_run_grace=CheckInterval.parse(
                str(schedule_raw.get("missed_run_grace", "1h"))
            ).duration,
            retention_days=schedule_defaults.retention_days,
        )
    except (ValueError, TypeError) as e:
        errors.append(f"schedule: {e}")

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

    mobile_web_settings: MobileWebSettings | None = None
    browser_raw = raw.get("browser", {})
    try:
        browser_defaults = MobileWebSettings()
        mobile_web_settings = MobileWebSettings.from_values(
            profile_id=str(
                browser_raw.get("device_profile", browser_defaults.profile_id.value)
            ),
            locale=str(browser_raw.get("locale", browser_defaults.locale)),
            timezone_id=str(
                browser_raw.get("timezone_id", browser_defaults.timezone_id)
            ),
        )
    except (ValueError, TypeError) as e:
        errors.append(f"browser: {e}")

    remote_auth_settings: RemoteAuthSettings | None = None
    remote_auth_raw = raw.get("remote_auth", {})
    try:
        remote_auth_defaults = RemoteAuthSettings()
        remote_auth_settings = RemoteAuthSettings(
            enabled=bool(remote_auth_raw.get("enabled", False)),
            public_url=(
                str(remote_auth_raw["public_url"])
                if remote_auth_raw.get("public_url") is not None
                else None
            ),
            listen_host=str(
                remote_auth_raw.get("listen_host", remote_auth_defaults.listen_host)
            ),
            listen_port=int(
                remote_auth_raw.get("listen_port", remote_auth_defaults.listen_port)
            ),
            websocket_port=int(
                remote_auth_raw.get(
                    "websocket_port", remote_auth_defaults.websocket_port
                )
            ),
            session_timeout_seconds=int(
                remote_auth_raw.get(
                    "session_timeout_seconds",
                    remote_auth_defaults.session_timeout_seconds,
                )
            ),
            telegram_init_max_age_seconds=int(
                remote_auth_raw.get(
                    "telegram_init_max_age_seconds",
                    remote_auth_defaults.telegram_init_max_age_seconds,
                )
            ),
            novnc_root=Path(
                str(remote_auth_raw.get("novnc_root", remote_auth_defaults.novnc_root))
            ),
            display=str(remote_auth_raw.get("display", remote_auth_defaults.display)),
        )
        if remote_auth_settings.enabled and (
            telegram_bot_settings is None or not telegram_bot_settings.enabled
        ):
            raise ValueError("remote authentication requires telegram_bot.enabled=true")
    except (ValueError, TypeError) as e:
        errors.append(f"remote_auth: {e}")

    if errors:
        raise ConfigValidationError(errors)

    assert schedule_settings is not None
    assert data_directory is not None
    assert agent_settings is not None
    assert telegram_bot_settings is not None
    assert limits_settings is not None
    assert mobile_web_settings is not None
    assert remote_auth_settings is not None

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
        mobile_web_settings=mobile_web_settings,
        remote_auth_settings=remote_auth_settings,
        schedule_settings=schedule_settings,
    )
