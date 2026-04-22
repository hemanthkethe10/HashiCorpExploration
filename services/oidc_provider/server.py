"""
OIDC Provider — FastAPI application.

Endpoints required by Azure Workload Identity Federation:

  GET  /.well-known/openid-configuration   Discovery document
  GET  /.well-known/jwks.json              JSON Web Key Set (public keys)
  POST /token                              Issue a signed JWT
  GET  /health                             Liveness probe
"""
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import ISSUER_URL, SIGNING_ALG
from .keys import get_jwks
from .token_service import AZURE_WIF_AUDIENCE, issue_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OIDC Provider", version="1.0.0")


# ---------------------------------------------------------------------------
# Discovery document
# ---------------------------------------------------------------------------

@app.get("/.well-known/openid-configuration", include_in_schema=False)
def openid_configuration() -> JSONResponse:
    """
    RFC 8414 / OpenID Connect Discovery 1.0 metadata document.
    Azure WIF fetches this to locate the JWKS URI.
    """
    doc = {
        "issuer": ISSUER_URL,
        "jwks_uri": f"{ISSUER_URL}/.well-known/jwks.json",
        # Azure WIF only needs the JWKS URI, but a complete discovery doc
        # makes this provider compatible with any OIDC-aware consumer.
        "authorization_endpoint": f"{ISSUER_URL}/authorize",
        "token_endpoint": f"{ISSUER_URL}/token",
        "response_types_supported": ["id_token"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": [SIGNING_ALG],
        "claims_supported": ["sub", "iss", "aud", "iat", "exp", "jti"],
        "scopes_supported": ["openid"],
    }
    return JSONResponse(content=doc)


# ---------------------------------------------------------------------------
# JWKS endpoint
# ---------------------------------------------------------------------------

@app.get("/.well-known/jwks.json", include_in_schema=False)
def jwks() -> JSONResponse:
    """
    JSON Web Key Set — exposes the RSA public key used to verify tokens.
    Azure WIF caches this; restart the provider only after rotating keys
    and updating the federated credential in Entra.
    """
    return JSONResponse(content=get_jwks())


# ---------------------------------------------------------------------------
# Token endpoint
# ---------------------------------------------------------------------------

class TokenRequest(BaseModel):
    subject: str = Field(..., description="The `sub` claim — must match the federated credential subject filter in Azure.")
    audience: str = Field(
        default=AZURE_WIF_AUDIENCE,
        description="The `aud` claim. Defaults to 'api://AzureADTokenExchange' as required by Azure WIF.",
    )
    extra_claims: dict | None = Field(
        default=None,
        description="Optional additional claims to include in the token payload.",
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int


@app.post("/token", response_model=TokenResponse)
def token(req: TokenRequest) -> TokenResponse:
    """
    Issue a signed JWT for Azure Workload Identity Federation.

    The returned token can be exchanged for an Azure AD access token via:
      POST https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token
      grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer
      client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer
      client_assertion=<token>
      client_id=<app_client_id>
      scope=<scope>
    """
    if not req.subject:
        raise HTTPException(status_code=400, detail="subject is required")

    from .config import TOKEN_TTL_SECONDS
    signed = issue_token(subject=req.subject, audience=req.audience, extra_claims=req.extra_claims)
    return TokenResponse(access_token=signed, expires_in=TOKEN_TTL_SECONDS)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "issuer": ISSUER_URL}
