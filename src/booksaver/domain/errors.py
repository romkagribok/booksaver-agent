from __future__ import annotations


class BookSaverError(Exception):
    pass


class ConfigValidationError(BookSaverError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


class BookingRejectedError(BookSaverError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class LocalPathViolation(BookSaverError):
    def __init__(self, path: str, data_dir: str) -> None:
        self.path = path
        self.data_dir = data_dir
        super().__init__(f"Path '{path}' is not under data directory '{data_dir}'")


class UserKeyInvalidError(BookSaverError):
    """Raised by LLMClientFactory when a booking owner's personal Anthropic
    key cannot be resolved (missing/invalid BOOKSAVER_SECRET_KEY, corrupt
    ciphertext). Callers map this to FailureCode.USER_KEY_INVALID (bolt 009,
    US-027) rather than a generic extraction failure."""

    def __init__(self, user_id: int, detail: str = "personal API key is invalid") -> None:
        self.user_id = user_id
        super().__init__(f"user {user_id}: {detail}")


class SecretKeyError(BookSaverError):
    """Raised when BOOKSAVER_SECRET_KEY is missing/invalid at the moment a
    personal-key operation (encrypt/decrypt) is attempted. Owner-billed
    checks never construct a FernetKeyStore call, so this never blocks
    laptop/owner-only deployments (bolt 009, US-027)."""
