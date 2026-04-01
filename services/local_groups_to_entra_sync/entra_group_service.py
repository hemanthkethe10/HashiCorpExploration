import logging
import re

import requests

from .base_service import GraphService
from .config import GRAPH_V1_URL, GROUP_EXTENSION_NAME, RETRY_BACKOFF_SECONDS, RETRY_COUNT
from .http_utils import post_with_retry
from .token_provider import TokenProvider

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert a display name to a valid mailNickname (alphanumeric + hyphens)."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-") or "group"


class EntraGroupService(GraphService):
    def __init__(self, token_provider: TokenProvider):
        super().__init__(token_provider)

    def create_security_group(self, display_name: str, description: str, lumen_id: str) -> str:
        """Creates a security group, attaches the Lumen_ID extension, returns ms_object_id."""
        headers = self._auth_headers()
        logger.info("Creating security group: display_name=%s lumen_id=%s", display_name, lumen_id)

        response = requests.post(
            f"{GRAPH_V1_URL}/groups",
            json={
                "displayName": display_name,
                "mailEnabled": False,
                "mailNickname": _slugify(display_name),
                "securityEnabled": True,
                "description":description
            },
            headers=headers,
        )
        logger.debug("POST /groups status=%d", response.status_code)
        response.raise_for_status()

        ms_object_id: str = response.json()["id"]
        logger.info("Security group created: ms_object_id=%s lumen_id=%s", ms_object_id, lumen_id)

        # Attach Lumen_ID extension — retries on 404 (group not yet propagated)
        ext_url = f"{GRAPH_V1_URL}/groups/{ms_object_id}/extensions"
        post_with_retry(
            url=ext_url,
            payload={"extensionName": GROUP_EXTENSION_NAME, "lumenId": lumen_id},
            headers=headers,
            retry_on_status={404},
            context=f"attach-extension group={ms_object_id}",
        )
        logger.info("Lumen_ID extension attached: ms_object_id=%s lumen_id=%s", ms_object_id, lumen_id)

        return ms_object_id

    def get_security_group(self, ms_object_id: str) -> dict | None:
        """Returns the group dict or None on 404."""
        logger.debug("Fetching security group: ms_object_id=%s", ms_object_id)
        headers = self._auth_headers()
        response = requests.get(
            f"{GRAPH_V1_URL}/groups/{ms_object_id}",
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
            f"{GRAPH_V1_URL}/groups/{ms_object_id}",
            json={"displayName": display_name},
            headers=headers,
        )
        logger.debug("PATCH /groups/%s status=%d", ms_object_id, response.status_code)
        response.raise_for_status()
        logger.info("Security group updated: ms_object_id=%s", ms_object_id)

    def add_group_member(self, group_ms_object_id: str, member_ms_object_id: str) -> None:
        """Add a directory object as a member of a security group.

        Retries on 404 (resource not yet propagated).
        Treats 400 "already exists" as an idempotent no-op.
        """
        logger.info("Adding member to group: group_id=%s member_id=%s", group_ms_object_id, member_ms_object_id)
        headers = self._auth_headers()

        def _is_success(r: requests.Response) -> bool:
            if r.status_code == 204:
                logger.info("Member added to group: group_id=%s member_id=%s", group_ms_object_id, member_ms_object_id)
                return True
            return False

        def _is_noop(r: requests.Response) -> bool:
            if r.status_code == 400:
                body = r.json() if r.content else {}
                if "already exist" in body.get("error", {}).get("message", "").lower():
                    logger.info(
                        "Member already in group (skipping): group_id=%s member_id=%s",
                        group_ms_object_id, member_ms_object_id,
                    )
                    return True
            return False

        post_with_retry(
            url=f"{GRAPH_V1_URL}/groups/{group_ms_object_id}/members/$ref",
            payload={"@odata.id": f"{GRAPH_V1_URL}/directoryObjects/{member_ms_object_id}"},
            headers=headers,
            retry_on_status={404},
            context=f"add-member group={group_ms_object_id} member={member_ms_object_id}",
            backoff=RETRY_BACKOFF_SECONDS,
            retries=RETRY_COUNT,
            success_check=_is_success,
            noop_check=_is_noop,
        )

    def delete_security_group(self, ms_object_id: str) -> None:
        """Delete a security group. Silently ignores 404 (already gone)."""
        logger.info("Deleting security group: ms_object_id=%s", ms_object_id)
        headers = self._auth_headers()
        response = requests.delete(f"{GRAPH_V1_URL}/groups/{ms_object_id}", headers=headers)
        if response.status_code == 404:
            logger.warning("Security group already gone (404): ms_object_id=%s", ms_object_id)
            return
        response.raise_for_status()
        logger.info("Security group deleted: ms_object_id=%s", ms_object_id)
