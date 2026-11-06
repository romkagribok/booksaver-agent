from __future__ import annotations


class BookSaverError(Exception):
    pass


class ConfigValidationError(BookSaverError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


class SecretKeyError(BookSaverError):
    """Raised when BOOKSAVER_SECRET_KEY is missing/invalid at the moment an
    encrypt/decrypt operation (sessions, diagnostics) is attempted."""


class SessionRevokedError(BookSaverError):
    """Raised when authentication state is written for a permanently purged user."""
