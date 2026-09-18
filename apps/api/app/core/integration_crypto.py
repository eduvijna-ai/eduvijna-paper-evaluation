"""Fernet encryption and hashing helpers for B19 integration secrets."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings, get_settings


def _derive_fernet_key(seed: str) -> bytes:
    digest = hashlib.sha256(f"b19-integration-fernet:{seed}".encode()).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache
def _fernet_for_key_material(key_material: str) -> Fernet:
    # Accept either a raw Fernet key or derive from AUTH_TOKEN_SECRET for local/test.
    try:
        return Fernet(key_material.encode("utf-8"))
    except (ValueError, TypeError):
        return Fernet(_derive_fernet_key(key_material))


def get_fernet(settings: Settings | None = None) -> Fernet:
    cfg = settings or get_settings()
    if cfg.integration_secret_encryption_key:
        return _fernet_for_key_material(cfg.integration_secret_encryption_key)
    if cfg.environment.lower() in {"local", "test"} and cfg.auth_token_secret:
        return Fernet(_derive_fernet_key(cfg.auth_token_secret))
    raise RuntimeError(
        "INTEGRATION_SECRET_ENCRYPTION_KEY is required outside local/test"
    )


def encrypt_secret(plaintext: str, settings: Settings | None = None) -> str:
    token = get_fernet(settings).encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(ciphertext: str, settings: Settings | None = None) -> str:
    try:
        return get_fernet(settings).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt integration secret") from exc


def generate_integration_secret(*, nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_integration_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def verify_integration_secret(secret: str, encoded_hash: str) -> bool:
    digest = hash_integration_secret(secret)
    return hmac.compare_digest(digest, encoded_hash)


def hash_opaque_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
