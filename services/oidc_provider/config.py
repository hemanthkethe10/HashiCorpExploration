"""
Configuration for the OIDC provider.
All values can be overridden via environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# The public base URL of this OIDC provider.
# Azure WIF will fetch <ISSUER_URL>/.well-known/openid-configuration
# so this must be reachable from the internet (or your Azure tenant's network).
ISSUER_URL: str = os.getenv("OIDC_ISSUER_URL", "http://localhost:8080")

# Default token lifetime in seconds (1 hour)
TOKEN_TTL_SECONDS: int = int(os.getenv("OIDC_TOKEN_TTL", "3600"))

# Supported signing algorithm
SIGNING_ALG: str = "RS256"
