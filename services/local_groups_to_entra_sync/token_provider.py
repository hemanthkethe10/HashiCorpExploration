from datetime import datetime, timedelta

import requests

from .exceptions import AuthenticationError


class TokenProvider:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, scope: str):
        self._token_url = (
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        )
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._access_token: str | None = None
        self._expires_at: datetime | None = None

    def get_token(self) -> str:
        """Returns a valid access token, refreshing if within 60s of expiry."""
        if (
            self._access_token is None
            or self._expires_at is None
            or datetime.utcnow() >= self._expires_at - timedelta(seconds=60)
        ):
            self._refresh_token()
        return self._access_token  # type: ignore[return-value]

    def _refresh_token(self) -> None:
        response = requests.post(
            self._token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": self._scope,
            },
        )

        if not response.ok:
            body = response.json() if response.content else {}
            error_description = body.get("error_description") or body.get("error", "unknown error")
            raise AuthenticationError(
                f"Token request failed with status {response.status_code}: {error_description}"
            )

        data = response.json()
        self._access_token = data["access_token"]
        expires_in = int(data.get("expires_in", 3600))
        self._expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
