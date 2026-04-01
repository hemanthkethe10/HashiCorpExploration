"""Centralised configuration constants for the local-groups-to-entra-sync service."""

import os
from enum import Enum

# Microsoft Graph API base URLs
GRAPH_V1_URL = "https://graph.microsoft.com/v1.0"
GRAPH_BETA_URL = "https://graph.microsoft.com/beta"

# Entra group extension name used to store the Lumen_ID on security groups
GROUP_EXTENSION_NAME = "com.lumen.groupSync"

# Sync type label written to SyncRecord rows
SYNC_TYPE = "MS Graph"

# SyncRecord resource_type values
RESOURCE_SECURITY_GROUP = "security_group"
RESOURCE_APP_REGISTRATION = "app_registration"
RESOURCE_SERVICE_PRINCIPAL = "service_principal"
RESOURCE_AGENT_IDENTITY = "agent_identity"
RESOURCE_AGENT_INSTANCE = "agent_instance"

# Retry / backoff defaults for Graph API calls that need propagation time
RETRY_COUNT = 5
RETRY_BACKOFF_SECONDS = 3.0

def get_sponsor_user_id() -> str:
    val = os.environ.get("AGENT_SPONSOR_USER_ID")
    if not val:
        raise ValueError("AGENT_SPONSOR_USER_ID env var is required")
    return val


def get_agent_blueprint_id() -> str | None:
    return os.environ.get("AGENT_BLUEPRINT_PRINCIPAL_ID")


class LumenResourceType(str, Enum):
    """Lumen entity types stored as the resourceType tag on Entra App Registrations."""
    CLIENT = "Client"
    MCP_SERVER = "MCP Server"
    AGENT = "AGENT"
