from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from booksaver.domain.errors import ConfigValidationError
from booksaver.domain.models import Config
from booksaver.domain.value_objects import CheckInterval, DataDirectory, NotificationSettings

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

    if errors:
        raise ConfigValidationError(errors)

    assert check_interval is not None
    assert data_directory is not None

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
    )
