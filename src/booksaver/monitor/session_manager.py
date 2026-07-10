from __future__ import annotations

import logging
from datetime import UTC, datetime

from booksaver.application.ports import SessionRepository
from booksaver.domain.session import SessionState, SessionStatus
from booksaver.domain.value_objects import Platform

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self, repo: SessionRepository, platform: Platform = Platform.BOOKING_COM) -> None:
        self._repo = repo
        self._platform = platform

    def ensure_active(self) -> SessionState | None:
        """Return the active session, or None if the user must re-authenticate."""
        session = self._repo.load(self._platform)
        if session is None:
            logger.warning(
                "No %s session found. Run 'booksaver auth' to log in.", self._platform.value
            )
            return None

        if session.status is SessionStatus.REQUIRES_REAUTH:
            logger.warning(
                "%s session requires re-authentication. Run 'booksaver auth'.",
                self._platform.value,
            )
            return None

        if session.is_expired(datetime.now(UTC)):
            expired = session.with_status(SessionStatus.EXPIRED)
            self._repo.save(expired)
            logger.warning(
                "%s session expired. Run 'booksaver auth' to log in again.",
                self._platform.value,
            )
            return None

        return session

    def mark_reauth_required(self, session: SessionState) -> None:
        self._repo.save(session.with_status(SessionStatus.REQUIRES_REAUTH))
        logger.warning(
            "%s session marked as requiring re-authentication. Run 'booksaver auth'.",
            self._platform.value,
        )

    def save_refreshed(self, session: SessionState, cookies: bytes) -> None:
        self._repo.save(session.with_cookies(cookies))
