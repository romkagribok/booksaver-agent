from __future__ import annotations

import os
from typing import TYPE_CHECKING

from booksaver.domain.errors import SecretKeyError

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

_SECRET_ENV_VAR = "BOOKSAVER_SECRET_KEY"


class FernetKeyStore:
    """Encrypts/decrypts personal Anthropic API keys at rest (ADR-019, US-027).

    The encryption key comes only from the ``BOOKSAVER_SECRET_KEY`` env var
    (ADR-002 — secrets never in config/git). It is read lazily, on first use,
    not at construction — so building this object is always safe (e.g. as a
    default dependency wired at daemon startup); only an actual encrypt/
    decrypt call on a real personal-key operation can raise, and only then.
    This means an owner-only/laptop deployment that never sets
    ``BOOKSAVER_SECRET_KEY`` and never receives a `/setkey` still runs fine.
    """

    def __init__(
        self,
        secret_key: str | None = None,
        *,
        purpose: str = "personal API key",
    ) -> None:
        self._explicit_secret_key = secret_key
        self._purpose = purpose

    def _fernet(self) -> Fernet:
        from cryptography.fernet import Fernet

        secret = self._explicit_secret_key or os.environ.get(_SECRET_ENV_VAR)
        if not secret:
            raise SecretKeyError(
                f"{_SECRET_ENV_VAR} is not set — cannot encrypt/decrypt {self._purpose}. "
                "Generate one with `python -c \"from cryptography.fernet "
                "import Fernet; print(Fernet.generate_key().decode())\"` and set it "
                "as an env var on the VPS before using /setkey."
            )
        try:
            return Fernet(secret.encode("utf-8") if isinstance(secret, str) else secret)
        except (ValueError, TypeError) as exc:
            raise SecretKeyError(
                f"{_SECRET_ENV_VAR} is not a valid Fernet key (must be 32 url-safe "
                "base64-encoded bytes)."
            ) from exc

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet().encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> str:
        from cryptography.fernet import InvalidToken

        try:
            return self._fernet().decrypt(ciphertext).decode("utf-8")
        except InvalidToken as exc:
            raise SecretKeyError(
                f"Stored {self._purpose} could not be decrypted — "
                "BOOKSAVER_SECRET_KEY may have "
                "changed since it was encrypted, or the ciphertext is corrupt."
            ) from exc
