from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path

from booksaver.domain.session import SessionState, SessionStatus
from booksaver.domain.value_objects import DataDirectory, Platform


def _session_path(data_dir: DataDirectory, platform: Platform) -> Path:
    return data_dir.path / f"session_{platform.value}.json"


class LocalSessionRepository:
    """Persists SessionState as a JSON file in the data directory (ADR-010)."""

    def __init__(self, data_dir: DataDirectory) -> None:
        self._data_dir = data_dir

    def load(self, platform: Platform) -> SessionState | None:
        path = _session_path(self._data_dir, platform)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text())
            return SessionState(
                session_id=raw["session_id"],
                platform=Platform(raw["platform"]),
                cookies=base64.b64decode(raw["cookies_b64"]),
                authenticated_at=datetime.fromisoformat(raw["authenticated_at"]),
                expires_at=(
                    datetime.fromisoformat(raw["expires_at"]) if raw.get("expires_at") else None
                ),
                status=SessionStatus(raw["status"]),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            # Corrupt session file — treat as no session; user re-authenticates
            return None

    def save(self, session: SessionState) -> None:
        path = _session_path(self._data_dir, session.platform)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = {
            "session_id": session.session_id,
            "platform": session.platform.value,
            "cookies_b64": base64.b64encode(session.cookies).decode("ascii"),
            "authenticated_at": session.authenticated_at.isoformat(),
            "expires_at": session.expires_at.isoformat() if session.expires_at else None,
            "status": session.status.value,
        }
        path.write_text(json.dumps(payload, indent=2))
        path.chmod(0o600)
