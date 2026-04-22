"""
Issues signed JWTs for Azure Workload Identity Federation.

Azure WIF validates:
  - iss  == the federated credential's issuer
  - sub  == the federated credential's subject
  - aud  == "api://AzureADTokenExchange"  (required by Azure)
  - exp  > now
  - The signature verifies against the JWKS at <issuer>/.well-known/jwks.json
"""
import logging
import time
import uuid

import jwt

from .config import ISSUER_URL, SIGNING_ALG, TOKEN_TTL_SECONDS
from .keys import get_kid, get_private_key

logger = logging.getLogger(__name__)

# Azure WIF requires this exact audience value
AZURE_WIF_AUDIENCE = "api://AzureADTokenExchange"


def issue_token(subject: str, audience: str = AZURE_WIF_AUDIENCE, extra_claims: dict | None = None) -> str:
    """
    Issue a signed JWT suitable for Azure Workload Identity Federation.

    Args:
        subject:      The `sub` claim — must match the federated credential's subject filter.
        audience:     The `aud` claim — defaults to the Azure WIF required value.
        extra_claims: Any additional claims to embed in the token payload.

    Returns:
        A compact serialized JWT string.
    """
    now = int(time.time())
    payload: dict = {
        "iss": ISSUER_URL,
        "sub": subject,
        "aud": audience,
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(
        payload,
        get_private_key(),
        algorithm=SIGNING_ALG,
        headers={"kid": get_kid()},
    )
    logger.info("Issued token for sub=%s aud=%s exp=%s", subject, audience, now + TOKEN_TTL_SECONDS)
    return token
