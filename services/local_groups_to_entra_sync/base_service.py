"""Base class for Graph API service classes."""

from .token_provider import TokenProvider


class GraphService:
    """Provides shared auth header construction for all Graph API services."""

    def __init__(self, token_provider: TokenProvider):
        self._token_provider = token_provider

    def _auth_headers(self) -> dict:
        token = self._token_provider.get_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
