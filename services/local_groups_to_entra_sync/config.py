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

# TODO: Move SPONSOR_USER_ID to an environment variable (AGENT_SPONSOR_USER_ID)
#       so it can be configured per deployment without a code change.
SPONSOR_USER_ID = "47fc13ad-809c-41bb-9768-8d21f92e9dfd"

AGENT_INSTANCE_OWNER_IDS: list[str] = [SPONSOR_USER_ID]

# Agent Identity Blueprint ID used when creating agentInstances
AGENT_BLUEPRINT_ID: str = os.environ.get("AGENT_BLUEPRINT_PRINCIPAL_ID")


class LumenResourceType(str, Enum):
    """Lumen entity types stored as the resourceType tag on Entra App Registrations."""
    CLIENT = "Client"
    MCP_SERVER = "MCP Server"
    AGENT = "AGENT"
