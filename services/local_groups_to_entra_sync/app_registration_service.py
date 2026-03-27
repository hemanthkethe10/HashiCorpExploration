import requests

from .token_provider import TokenProvider

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


class AppRegistrationService:
    def __init__(self, token_provider: TokenProvider):
        self._token_provider = token_provider

    def _auth_headers(self) -> dict:
        token = self._token_provider.get_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def create_app_registration(self, display_name: str) -> str:
        """Creates an app registration, returns ms_object_id."""
        headers = self._auth_headers()
        response = requests.post(
            f"{GRAPH_BASE_URL}/applications",
            json={"displayName": display_name},
            headers=headers,
        )
        response.raise_for_status()
        ms_object_id: str = response.json()["id"]
        return ms_object_id

    def get_app_registration(self, ms_object_id: str) -> dict | None:
        """Returns the app registration dict or None on 404."""
        headers = self._auth_headers()
        response = requests.get(
            f"{GRAPH_BASE_URL}/applications/{ms_object_id}",
            headers=headers,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def update_app_registration(self, ms_object_id: str, display_name: str) -> None:
        """Updates the display name of an existing app registration."""
        headers = self._auth_headers()
        response = requests.patch(
            f"{GRAPH_BASE_URL}/applications/{ms_object_id}",
            json={"displayName": display_name},
            headers=headers,
        )
        response.raise_for_status()
