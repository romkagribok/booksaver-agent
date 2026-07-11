"""US-027 / ADR-019: Fernet-encrypted personal Anthropic keys at rest."""

import pytest
from cryptography.fernet import Fernet

from booksaver.domain.errors import SecretKeyError
from booksaver.infrastructure.crypto.fernet_key_store import FernetKeyStore


def _valid_secret() -> str:
    return Fernet.generate_key().decode("utf-8")


class TestFernetKeyStore:
    def test_encrypt_then_decrypt_round_trips(self):
        store = FernetKeyStore(secret_key=_valid_secret())
        ciphertext = store.encrypt("sk-ant-super-secret")
        assert store.decrypt(ciphertext) == "sk-ant-super-secret"

    def test_ciphertext_does_not_contain_plaintext(self):
        store = FernetKeyStore(secret_key=_valid_secret())
        ciphertext = store.encrypt("sk-ant-super-secret")
        assert b"sk-ant-super-secret" not in ciphertext

    def test_missing_secret_key_raises_clear_error(self, monkeypatch):
        monkeypatch.delenv("BOOKSAVER_SECRET_KEY", raising=False)
        store = FernetKeyStore()
        with pytest.raises(SecretKeyError, match="BOOKSAVER_SECRET_KEY"):
            store.encrypt("sk-ant-x")

    def test_invalid_secret_key_raises_clear_error(self, monkeypatch):
        monkeypatch.setenv("BOOKSAVER_SECRET_KEY", "not-a-valid-fernet-key")
        store = FernetKeyStore()
        with pytest.raises(SecretKeyError, match="valid Fernet key"):
            store.encrypt("sk-ant-x")

    def test_decrypting_with_a_different_secret_key_raises(self):
        store_a = FernetKeyStore(secret_key=_valid_secret())
        store_b = FernetKeyStore(secret_key=_valid_secret())
        ciphertext = store_a.encrypt("sk-ant-x")
        with pytest.raises(SecretKeyError, match="could not be decrypted"):
            store_b.decrypt(ciphertext)

    def test_reads_secret_from_env_var_when_not_explicit(self, monkeypatch):
        monkeypatch.setenv("BOOKSAVER_SECRET_KEY", _valid_secret())
        store = FernetKeyStore()
        ciphertext = store.encrypt("sk-ant-env")
        assert store.decrypt(ciphertext) == "sk-ant-env"
