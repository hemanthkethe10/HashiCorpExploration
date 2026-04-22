"""
RSA key pair management for the OIDC provider.

Generates a 2048-bit RSA key on first run and persists it to disk so the
JWKS endpoint stays stable across restarts (Azure WIF caches the JWKS).
"""
import base64
import json
import logging
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

_KEY_DIR = Path(os.getenv("OIDC_KEY_DIR", ".oidc_keys"))
_PRIVATE_KEY_PATH = _KEY_DIR / "private.pem"
_KID = "oidc-provider-key-1"
# Set OIDC_KEY_PASSPHRASE in .env if your private key is passphrase-protected
_PASSPHRASE: bytes | None = os.getenv("OIDC_KEY_PASSPHRASE", "").encode() or None


def _load_or_generate() -> rsa.RSAPrivateKey:
    _KEY_DIR.mkdir(parents=True, exist_ok=True)
    if _PRIVATE_KEY_PATH.exists():
        logger.info("Loading existing RSA private key from %s", _PRIVATE_KEY_PATH)
        pem = _PRIVATE_KEY_PATH.read_bytes()
        return serialization.load_pem_private_key(pem, password=_PASSPHRASE, backend=default_backend())

    logger.info("Generating new RSA-2048 key pair, saving to %s", _PRIVATE_KEY_PATH)
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    _PRIVATE_KEY_PATH.write_bytes(pem)
    _PRIVATE_KEY_PATH.chmod(0o600)
    return private_key


def _b64url_uint(n: int) -> str:
    """Encode an integer as base64url (no padding) for JWKS."""
    length = (n.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(n.to_bytes(length, "big")).rstrip(b"=").decode()


# Module-level singleton — loaded once at import time
private_key: rsa.RSAPrivateKey = _load_or_generate()


def get_jwks() -> dict:
    """Return the JSON Web Key Set containing the public key."""
    pub = private_key.public_key().public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": _KID,
                "n": _b64url_uint(pub.n),
                "e": _b64url_uint(pub.e),
            }
        ]
    }


def get_kid() -> str:
    return _KID


def get_private_key() -> rsa.RSAPrivateKey:
    return private_key
