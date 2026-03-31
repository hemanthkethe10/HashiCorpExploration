import logging

import requests

from .config import GRAPH_V1_URL, RETRY_BACKOFF_SECONDS, RETRY_COUNT
from .http_utils import post_with_retry
from .token_provider import TokenProvider

logger = logging.getLogger(__name__)


class AppRegistrationService:
    def __init__(self, token_provider: TokenProvider):
        self._token_provider = token_provider

    def _auth_headers(self) -> dict:
        token = self._token_provider.get_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


    def create_app_registration(self, display_name: str, resource_type: str, resource_id: str, extra_tags: dict | None = None) -> tuple[str, str]:
        """Create an app registration with Lumen resource tags.

        Returns:
            (ms_object_id, app_id) — the application object ID and the appId (client ID).
        """
        logger.info("Creating app registration: display_name=%s resource_type=%s resource_id=%s",
                    display_name, resource_type, resource_id)
        headers = self._auth_headers()
        tags = [f"resourceType:{resource_type}", f"resourceId:{resource_id}"]
        for k, v in (extra_tags or {}).items():
            tags.append(f"{k}:{v}")
        response = requests.post(
            f"{GRAPH_V1_URL}/applications",
            json={"displayName": display_name, "tags": tags},
            headers=headers,
        )
        logger.debug("POST /applications status=%d", response.status_code)
        response.raise_for_status()
        data = response.json()
        ms_object_id: str = data["id"]
        app_id: str = data["appId"]
        logger.info("App registration created: ms_object_id=%s app_id=%s", ms_object_id, app_id)
        return ms_object_id, app_id

    def get_app_registration(self, ms_object_id: str) -> dict | None:
        """Returns the app registration dict (includes appId) or None on 404."""
        logger.debug("Fetching app registration: ms_object_id=%s", ms_object_id)
        headers = self._auth_headers()
        response = requests.get(
            f"{GRAPH_V1_URL}/applications/{ms_object_id}",
            params={"$select": "id,appId,displayName"},
            headers=headers,
        )
        if response.status_code == 404:
            logger.warning("App registration not found (404): ms_object_id=%s", ms_object_id)
            return None
        response.raise_for_status()
        return response.json()

    def update_app_registration(self, ms_object_id: str, display_name: str, resource_type: str, resource_id: str, extra_tags: dict | None = None) -> None:
        """Updates the display name and Lumen resource tags of an existing app registration."""
        logger.info("Updating app registration: ms_object_id=%s new_display_name=%s", ms_object_id, display_name)
        headers = self._auth_headers()
        tags = [f"resourceType:{resource_type}", f"resourceId:{resource_id}"]
        for k, v in (extra_tags or {}).items():
            tags.append(f"{k}:{v}")
        response = requests.patch(
            f"{GRAPH_V1_URL}/applications/{ms_object_id}",
            json={"displayName": display_name, "tags": tags},
            headers=headers,
        )
        logger.debug("PATCH /applications/%s status=%d", ms_object_id, response.status_code)
        response.raise_for_status()

    def delete_app_registration(self, ms_object_id: str) -> None:
        """Deletes an app registration. Silently ignores 404 (already gone)."""
        logger.info("Deleting app registration: ms_object_id=%s", ms_object_id)
        headers = self._auth_headers()
        response = requests.delete(f"{GRAPH_V1_URL}/applications/{ms_object_id}", headers=headers)
        if response.status_code == 404:
            logger.warning("App registration already gone (404): ms_object_id=%s", ms_object_id)
            return
        response.raise_for_status()

    def create_service_principal(self, app_id: str) -> str:
        """Create a service principal for an existing app registration.

        Retries on 400 — Graph returns 400 when the app registration hasn't
        fully propagated yet. Backoff: 3s, 6s, 9s, 12s.

        Returns:
            The service principal object ID (used for group membership).
        """
        logger.info("Creating service principal for app_id=%s", app_id)
        headers = self._auth_headers()

        response = post_with_retry(
            url=f"{GRAPH_V1_URL}/servicePrincipals",
            payload={"appId": app_id},
            headers=headers,
            retry_on_status={400},
            context=f"create-service-principal app_id={app_id}",
            retries=RETRY_COUNT,
            backoff=RETRY_BACKOFF_SECONDS,
        )
        sp_id: str = response.json()["id"]
        logger.info("Service principal created: sp_id=%s app_id=%s", sp_id, app_id)
        return sp_id

    def get_service_principal(self, sp_id: str) -> dict | None:
        """Returns the service principal dict or None on 404."""
        logger.debug("Fetching service principal: sp_id=%s", sp_id)
        headers = self._auth_headers()
        response = requests.get(
            f"{GRAPH_V1_URL}/servicePrincipals/{sp_id}",
            params={"$select": "id,appId,displayName"},
            headers=headers,
        )
        if response.status_code == 404:
            logger.warning("Service principal not found (404): sp_id=%s", sp_id)
            return None
        response.raise_for_status()
        return response.json()

    def delete_service_principal(self, sp_id: str) -> None:
        """Deletes a service principal. Silently ignores 404 (already gone)."""
        logger.info("Deleting service principal: sp_id=%s", sp_id)
        headers = self._auth_headers()
        response = requests.delete(f"{GRAPH_V1_URL}/servicePrincipals/{sp_id}", headers=headers)
        if response.status_code == 404:
            logger.warning("Service principal already gone (404): sp_id=%s", sp_id)
            return
        response.raise_for_status()
