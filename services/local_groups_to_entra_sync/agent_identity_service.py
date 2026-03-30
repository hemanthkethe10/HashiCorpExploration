"""AgentIdentityService — provisions Entra Agent Identities via the Graph API."""

import logging

import requests

from .config import GRAPH_BETA_URL, GRAPH_V1_URL, SPONSOR_USER_ID,LumenResourceType
from .token_provider import TokenProvider

logger = logging.getLogger(__name__)


class AgentIdentityService:
    def __init__(self, token_provider: TokenProvider, blueprint_principal_id: str):
        """
        Args:
            token_provider:          Provides a valid Bearer token for Graph API calls.
            blueprint_principal_id:  Object ID of the agentIdentityBlueprintPrincipal
                                     service principal (AGENT_BLUEPRINT_PRINCIPAL_ID env var).
        """
        self._token_provider = token_provider
        self._blueprint_principal_id = blueprint_principal_id

    def _auth_headers(self) -> dict:
        token = self._token_provider.get_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def create_agent_identity(self, display_name: str, resource_id: str) -> str:
        """Create a new agent identity service principal.

        Returns:
            The ms_object_id of the newly created service principal.
        """
        headers = self._auth_headers()
        logger.info(
            "Creating agent identity: display_name=%s blueprint_principal_id=%s resource_id=%s",
            display_name, self._blueprint_principal_id, resource_id,
        )
        response = requests.post(
            f"{GRAPH_BETA_URL}/servicePrincipals/microsoft.graph.agentIdentity",
            json={
                "displayName": display_name,
                "agentIdentityBlueprintId": self._blueprint_principal_id,
                "sponsors@odata.bind": [f"{GRAPH_V1_URL}/users/{SPONSOR_USER_ID}"],
                "tags": [f"resourceType:{LumenResourceType.AGENT.value}", f"resourceId:{resource_id}"],
            },
            headers=headers,
        )
        logger.debug(
            "POST /beta/servicePrincipals/microsoft.graph.agentIdentity status=%d body=%s",
            response.status_code, response.text[:500],
        )
        response.raise_for_status()

        ms_object_id: str = response.json()["id"]
        logger.info("Agent identity created: ms_object_id=%s display_name=%s", ms_object_id, display_name)
        return ms_object_id

    def get_agent_identity(self, ms_object_id: str) -> dict | None:
        """Returns the service principal dict or None on 404."""
        logger.debug("Fetching agent identity: ms_object_id=%s", ms_object_id)
        headers = self._auth_headers()
        response = requests.get(
            f"{GRAPH_BETA_URL}/servicePrincipals/{ms_object_id}",
            params={"$select": "id,displayName"},
            headers=headers,
        )
        if response.status_code == 404:
            logger.warning("Agent identity not found (404): ms_object_id=%s", ms_object_id)
            return None
        response.raise_for_status()
        data = response.json()
        logger.debug("Fetched agent identity: ms_object_id=%s displayName=%s", ms_object_id, data.get("displayName"))
        return data

    def update_agent_identity(self, ms_object_id: str, display_name: str, resource_id: str) -> None:
        """Update the display name and resource tags of an existing agent identity."""
        logger.info("Updating agent identity: ms_object_id=%s new_display_name=%s", ms_object_id, display_name)
        headers = self._auth_headers()
        response = requests.patch(
            f"{GRAPH_BETA_URL}/servicePrincipals/{ms_object_id}",
            json={
                "displayName": display_name,
                "tags": [F"resourceType:{LumenResourceType.AGENT.value}", f"resourceId:{resource_id}"],
            },
            headers=headers,
        )
        logger.debug("PATCH /beta/servicePrincipals/%s status=%d", ms_object_id, response.status_code)
        response.raise_for_status()
        logger.info("Agent identity updated: ms_object_id=%s", ms_object_id)

    def delete_agent_identity(self, ms_object_id: str) -> None:
        """Delete an agent identity. Silently ignores 404 (already gone)."""
        logger.info("Deleting agent identity: ms_object_id=%s", ms_object_id)
        headers = self._auth_headers()
        response = requests.delete(
            f"{GRAPH_BETA_URL}/servicePrincipals/{ms_object_id}",
            headers=headers,
        )
        if response.status_code == 404:
            logger.warning("Agent identity already gone (404): ms_object_id=%s", ms_object_id)
            return
        response.raise_for_status()
        logger.info("Agent identity deleted: ms_object_id=%s", ms_object_id)
