"""
Configuration for Vault OIDC integration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Vault OIDC configuration
VAULT_ADDR = os.getenv("VAULT_ADDR")
VAULT_NAMESPACE = os.getenv("VAULT_NAMESPACE")
PROVIDER_NAME = os.getenv("PROVIDER_NAME", "default")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# Vault token creation configuration
VAULT_ROOT_TOKEN = os.getenv("VAULT_ROOT_TOKEN")
VAULT_TOKEN_POLICIES = os.getenv("VAULT_TOKEN_POLICIES", "boundary-controller").split(",")
VAULT_TOKEN_PERIOD = os.getenv("VAULT_TOKEN_PERIOD", "24h")

# Boundary configuration
BOUNDARY_ADDR = os.getenv("BOUNDARY_ADDR")
BOUNDARY_TOKEN = os.getenv("BOUNDARY_TOKEN")

# Authorization middleware configuration
VAULT_AUTH_PATH = os.getenv("VAULT_AUTH_PATH")
EXCLUDED_PATHS = ["/health", "/auth/login", "/auth/callback", "/docs", "/openapi.json"]

# In-memory storage for tokens
token_storage = {
    "access_token": None,
    "id_token": None,
    "refresh_token": None,
    "token_type": None,
    "expires_in": None,
    "stored_at": None,
    "userinfo": None
}
