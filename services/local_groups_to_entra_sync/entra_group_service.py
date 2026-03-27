import logging
import re
import time

import requests

from .token_provider import TokenProvider

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert a display name to a valid mailNickname (alphanumeric + hyphens, no spaces)."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "group"


def _attach_extension_with_retry(
    url: str, payload: dict, headers: dict, retries: int = 5, backoff: float = 2.0
) -> None:
    """POST to the extensions endpoint, retrying on 404 (group not yet propagated)."""
    for attempt in range(1, retries + 1):
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 404 and attempt < retries:
            wait = backoff * attempt
            logger.warning(
                "Extension endpoint returned 404 (group not yet propagated), "
                "retrying in %.1fs (attempt %d/%d) url=%s",
                wait, attempt, retries, url,
            )
            time.sleep(wait)
            continue
        response.raise_for_status()
        return
    # Final attempt already raised via raise_for_status above


class EntraGroupService:
    def __init__(self, token_provider: TokenProvider):
        self._token_provider = token_provider

    def _auth_headers(self) -> dict:
        token = self._token_provider.get_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def create_security_group(self, display_name: str, lumen_id: str) -> str:
        """Creates a security group, attaches the Lumen_ID extension, returns ms_object_id."""
        headers = self._auth_headers()
        logger.info("Creating security group: display_name=%s lumen_id=%s", display_name, lumen_id)

        payload = {
            "displayName": display_name,
            "mailEnabled": False,
            "mailNickname": _slugify(display_name),
            "securityEnabled": True,
        }
        response = requests.post(f"{GRAPH_BASE_URL}/groups", json=payload, headers=headers)
        logger.debug("POST /groups status=%d", response.status_code)
        response.raise_for_status()

        ms_object_id: str = response.json()["id"]
        logger.info("Security group created: ms_object_id=%s lumen_id=%s", ms_object_id, lumen_id)

        ext_url = f"{GRAPH_BASE_URL}/groups/{ms_object_id}/extensions"
        ext_payload = {"extensionName": "com.lumen.groupSync", "lumenId": lumen_id}
        logger.debug("Attaching Lumen_ID extension: url=%s lumen_id=%s", ext_url, lumen_id)

        _attach_extension_with_retry(ext_url, ext_payload, headers)
        logger.info("Lumen_ID extension attached: ms_object_id=%s lumen_id=%s", ms_object_id, lumen_id)

        return ms_object_id

    def get_security_group(self, ms_object_id: str) -> dict | None:
        """Returns the group dict or None on 404."""
        logger.debug("Fetching security group: ms_object_id=%s", ms_object_id)
        headers = self._auth_headers()
        response = requests.get(
            f"{GRAPH_BASE_URL}/groups/{ms_object_id}",
            params={"$select": "id,displayName"},
            headers=headers,
        )
        if response.status_code == 404:
            logger.warning("Security group not found (404): ms_object_id=%s", ms_object_id)
            return None
        response.raise_for_status()
        data = response.json()
        logger.debug("Fetched security group: ms_object_id=%s displayName=%s", ms_object_id, data.get("displayName"))
        return data

    def update_security_group(self, ms_object_id: str, display_name: str) -> None:
        """Updates the display name of an existing security group."""
        logger.info("Updating security group: ms_object_id=%s new_display_name=%s", ms_object_id, display_name)
        headers = self._auth_headers()
        response = requests.patch(
            f"{GRAPH_BASE_URL}/groups/{ms_object_id}",
            json={"displayName": display_name},
            headers=headers,
        )
        logger.debug("PATCH /groups/%s status=%d", ms_object_id, response.status_code)
        response.raise_for_status()
        logger.info("Security group updated: ms_object_id=%s", ms_object_id)
