from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse


class RemoteAuthStatus(Enum):
    STARTING = "starting"
    READY = "ready"
    CONNECTED = "connected"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {
            RemoteAuthStatus.SUCCEEDED,
            RemoteAuthStatus.FAILED,
            RemoteAuthStatus.EXPIRED,
            RemoteAuthStatus.CANCELLED,
        }


class RemoteAuthFailure(Enum):
    SETUP_FAILED = "setup_failed"
    BROWSER_FAILED = "browser_failed"
    CAPTURE_REJECTED = "capture_rejected"
    ACCESS_REVOKED = "access_revoked"


@dataclass(frozen=True)
class RemoteAuthSettings:
    enabled: bool = False
    public_url: str | None = None
    listen_host: str = "0.0.0.0"
    listen_port: int = 8080
    websocket_port: int = 6080
    session_timeout_seconds: int = 600
    telegram_init_max_age_seconds: int = 300
    novnc_root: Path = Path("/usr/share/novnc")
    display: str = ":99"

    def __post_init__(self) -> None:
        if self.enabled:
            if self.public_url is None:
                raise ValueError("remote_auth.public_url is required when enabled")
            parsed = urlparse(self.public_url)
            if (
                parsed.scheme != "https"
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "remote_auth.public_url must be an HTTPS origin without credentials, "
                    "query, or fragment"
                )
        if not self.listen_host.strip():
            raise ValueError("remote_auth.listen_host must be non-empty")
        for label, value in (
            ("listen_port", self.listen_port),
            ("websocket_port", self.websocket_port),
        ):
            if not 1 <= value <= 65535:
                raise ValueError(f"remote_auth.{label} must be between 1 and 65535")
        if self.listen_port == self.websocket_port:
            raise ValueError("remote_auth listen and websocket ports must differ")
        if not 120 <= self.session_timeout_seconds <= 1800:
            raise ValueError(
                "remote_auth.session_timeout_seconds must be between 120 and 1800"
            )
        if not 60 <= self.telegram_init_max_age_seconds <= 900:
            raise ValueError(
                "remote_auth.telegram_init_max_age_seconds must be between 60 and 900"
            )
        if not self.display.startswith(":") or not self.display[1:].isdigit():
            raise ValueError("remote_auth.display must look like ':99'")

    @property
    def base_url(self) -> str:
        if self.public_url is None:
            raise RuntimeError("Remote authentication has no public URL")
        return self.public_url.rstrip("/")


@dataclass(frozen=True)
class AttemptLaunch:
    url: str
    expires_at: datetime


@dataclass(frozen=True)
class ViewerGrant:
    session_token: str
    expires_at: datetime


@dataclass(frozen=True)
class ViewerState:
    status: RemoteAuthStatus
    expires_at: datetime
    websocket_path: str | None = None
    websocket_token: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class TelegramMiniAppIdentity:
    telegram_user_id: int
    authenticated_at: datetime
