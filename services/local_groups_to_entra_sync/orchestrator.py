import logging
from dataclasses import dataclass, field

from .agent_identity_service import AgentIdentityService
from .app_registration_service import AppRegistrationService
from .config import (
    RESOURCE_AGENT_IDENTITY,
    RESOURCE_APP_REGISTRATION,
    RESOURCE_SECURITY_GROUP,
    RESOURCE_SERVICE_PRINCIPAL,
    SYNC_TYPE,
)
from .entra_group_service import EntraGroupService
from .repositories import GroupRepository, SyncRecordRepository
from .token_provider import TokenProvider

logger = logging.getLogger(__name__)



@dataclass
class SyncSummary:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    skipped_entities: list[dict] = field(default_factory=list)
    failed_entities: list[dict] = field(default_factory=list)


class SyncOrchestrator:
    def __init__(
        self,
        token_provider: TokenProvider,
        group_repo: GroupRepository,
        sync_record_repo: SyncRecordRepository,
        entra_group_svc: EntraGroupService,
        app_reg_svc: AppRegistrationService,
        agent_identity_svc: AgentIdentityService,
    ):
        self._token_provider = token_provider
        self._group_repo = group_repo
        self._sync_record_repo = sync_record_repo
        self._entra_group_svc = entra_group_svc
        self._app_reg_svc = app_reg_svc
        self._agent_identity_svc = agent_identity_svc

    def run(self) -> SyncSummary:
        summary = SyncSummary()

        # Step 1: Acquire token (raises AuthenticationError on failure — aborts run)
        self._token_provider.get_token()

        # Step 2: Discover all groups
        groups = self._group_repo.get_all_groups()

        for group in groups:
            # Skip groups with null/empty name
            if not group.name:
                logger.warning("Skipping group with null/empty name: lumen_id=%s", group.id)
                summary.skipped += 1
                summary.skipped_entities.append({"lumen_id": group.id, "reason": "null or empty name"})
                continue

            # Step 3: Create/update the Entra security group for this peer group
            try:
                group_ms_id = self._sync_security_group(group.id, group.name, summary)
            except Exception as exc:
                logger.error(
                    "Failed to sync security group for lumen_id=%s name=%s: %s",
                    group.id, group.name, exc,
                )
                summary.failed += 1
                summary.failed_entities.append({"lumen_id": group.id, "reason": str(exc)})
                continue

            # Step 4: Resolve members
            members = group.members or {}
            client_ids = members.get("client_ids") or []
            agent_ids = members.get("agent_ids") or []
            mcp_server_ids = members.get("mcp_server_ids") or []

            clients = self._group_repo.get_clients_by_ids(client_ids)
            agents = self._group_repo.get_agents_by_ids(agent_ids)
            mcp_servers = self._group_repo.get_mcp_servers_by_ids(mcp_server_ids)

            # Warn on unresolved member IDs
            for mid in client_ids:
                if mid not in {c.id for c in clients}:
                    logger.warning("Unresolved client_id=%s in group lumen_id=%s", mid, group.id)
            for mid in agent_ids:
                if mid not in {a.id for a in agents}:
                    logger.warning("Unresolved agent_id=%s in group lumen_id=%s", mid, group.id)
            for mid in mcp_server_ids:
                if mid not in {m.id for m in mcp_servers}:
                    logger.warning("Unresolved mcp_server_id=%s in group lumen_id=%s", mid, group.id)

            # Collect ms_object_ids of all provisioned members to add to the group
            member_ms_ids: list[str] = []

            # Step 5: Agents → Agent Identities (beta/servicePrincipals via blueprint)
            for agent in agents:
                try:
                    ms_id = self._sync_agent_identity(agent.id, agent.name, summary)
                    if ms_id:
                        member_ms_ids.append(ms_id)
                except Exception as exc:
                    logger.error(
                        "Failed to sync agent identity for lumen_id=%s name=%s: %s",
                        agent.id, agent.name, exc,
                    )
                    summary.failed += 1
                    summary.failed_entities.append({"lumen_id": agent.id, "reason": str(exc)})

            # Step 6: Clients → App Registrations
            for client in clients:
                try:
                    ms_id = self._sync_app_registration(client.id, client.name, summary)
                    if ms_id:
                        member_ms_ids.append(ms_id)
                except Exception as exc:
                    logger.error(
                        "Failed to sync app registration for client lumen_id=%s name=%s: %s",
                        client.id, client.name, exc,
                    )
                    summary.failed += 1
                    summary.failed_entities.append({"lumen_id": client.id, "reason": str(exc)})

            # Step 7: MCP Servers → App Registrations
            for mcp in mcp_servers:
                try:
                    ms_id = self._sync_app_registration(mcp.id, mcp.name, summary)
                    if ms_id:
                        member_ms_ids.append(ms_id)
                except Exception as exc:
                    logger.error(
                        "Failed to sync app registration for mcp_server lumen_id=%s name=%s: %s",
                        mcp.id, mcp.name, exc,
                    )
                    summary.failed += 1
                    summary.failed_entities.append({"lumen_id": mcp.id, "reason": str(exc)})

            # Step 8: Add all provisioned members to the security group
            if group_ms_id:
                for member_ms_id in member_ms_ids:
                    try:
                        self._entra_group_svc.add_group_member(group_ms_id, member_ms_id)
                    except Exception as exc:
                        logger.error(
                            "Failed to add member ms_object_id=%s to group ms_object_id=%s: %s",
                            member_ms_id, group_ms_id, exc,
                        )
                        summary.failed += 1
                        summary.failed_entities.append({
                            "lumen_id": group.id,
                            "reason": f"add_member failed for member {member_ms_id}: {exc}",
                        })

        # Step 9: Emit summary
        logger.info(
            "Sync complete: created=%d updated=%d skipped=%d failed=%d",
            summary.created, summary.updated, summary.skipped, summary.failed,
        )
        for entry in summary.skipped_entities:
            logger.warning("Skipped entity: lumen_id=%s reason=%s", entry["lumen_id"], entry["reason"])
        for entry in summary.failed_entities:
            logger.error("Failed entity: lumen_id=%s reason=%s", entry["lumen_id"], entry["reason"])

        return summary

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _sync_security_group(self, lumen_id: str, name: str, summary: SyncSummary) -> str | None:
        """Create or update an Entra security group. Returns the ms_object_id."""
        record = self._sync_record_repo.get_sync_record(lumen_id, SYNC_TYPE, RESOURCE_SECURITY_GROUP)

        if record is None:
            ms_object_id = self._entra_group_svc.create_security_group(name, lumen_id)
            self._sync_record_repo.upsert_sync_record(lumen_id, ms_object_id, SYNC_TYPE, RESOURCE_SECURITY_GROUP)
            logger.info("Created security group: lumen_id=%s ms_object_id=%s", lumen_id, ms_object_id)
            summary.created += 1
            return ms_object_id

        ms_object_id = record.ms_object_id
        existing = self._entra_group_svc.get_security_group(ms_object_id)

        if existing is None:
            ms_object_id = self._entra_group_svc.create_security_group(name, lumen_id)
            self._sync_record_repo.upsert_sync_record(lumen_id, ms_object_id, SYNC_TYPE, RESOURCE_SECURITY_GROUP)
            logger.info("Re-created security group (was 404): lumen_id=%s ms_object_id=%s", lumen_id, ms_object_id)
            summary.created += 1
        elif existing.get("displayName") != name:
            old_name = existing.get("displayName")
            self._entra_group_svc.update_security_group(ms_object_id, name)
            logger.info("Updated security group: lumen_id=%s old_name=%s new_name=%s", lumen_id, old_name, name)
            summary.updated += 1
        else:
            logger.info("Security group up-to-date: lumen_id=%s", lumen_id)

        return ms_object_id

    def _sync_agent_identity(self, lumen_id: str, name: str, summary: SyncSummary) -> str | None:
        """Create or update an Entra Agent Identity for an Agent entity. Returns ms_object_id."""
        record = self._sync_record_repo.get_sync_record(lumen_id, SYNC_TYPE, RESOURCE_AGENT_IDENTITY)

        if record is None:
            ms_object_id = self._agent_identity_svc.create_agent_identity(name)
            self._sync_record_repo.upsert_sync_record(lumen_id, ms_object_id, SYNC_TYPE, RESOURCE_AGENT_IDENTITY)
            logger.info("Created agent identity: lumen_id=%s ms_object_id=%s", lumen_id, ms_object_id)
            summary.created += 1
            return ms_object_id

        ms_object_id = record.ms_object_id
        existing = self._agent_identity_svc.get_agent_identity(ms_object_id)

        if existing is None:
            ms_object_id = self._agent_identity_svc.create_agent_identity(name)
            self._sync_record_repo.upsert_sync_record(lumen_id, ms_object_id, SYNC_TYPE, RESOURCE_AGENT_IDENTITY)
            logger.info("Re-created agent identity (was 404): lumen_id=%s ms_object_id=%s", lumen_id, ms_object_id)
            summary.created += 1
        elif existing.get("displayName") != name:
            old_name = existing.get("displayName")
            self._agent_identity_svc.update_agent_identity(ms_object_id, name)
            logger.info("Updated agent identity: lumen_id=%s old_name=%s new_name=%s", lumen_id, old_name, name)
            summary.updated += 1
        else:
            logger.info("Agent identity up-to-date: lumen_id=%s", lumen_id)

        return ms_object_id

    def _sync_app_registration(self, lumen_id: str, name: str, summary: SyncSummary) -> str | None:
        """Create or update an Entra App Registration and its Service Principal.

        Returns the Service Principal object ID (used for group membership).
        """
        # --- App Registration ---
        app_record = self._sync_record_repo.get_sync_record(lumen_id, SYNC_TYPE, RESOURCE_APP_REGISTRATION)
        app_id: str | None = None  # the appId (client ID), needed to create the SP

        if app_record is None:
            ms_object_id, app_id = self._app_reg_svc.create_app_registration(name)
            self._sync_record_repo.upsert_sync_record(lumen_id, ms_object_id, SYNC_TYPE, RESOURCE_APP_REGISTRATION)
            logger.info("Created app registration: lumen_id=%s ms_object_id=%s app_id=%s", lumen_id, ms_object_id, app_id)
            summary.created += 1
        else:
            ms_object_id = app_record.ms_object_id
            existing = self._app_reg_svc.get_app_registration(ms_object_id)

            if existing is None:
                ms_object_id, app_id = self._app_reg_svc.create_app_registration(name)
                self._sync_record_repo.upsert_sync_record(lumen_id, ms_object_id, SYNC_TYPE, RESOURCE_APP_REGISTRATION)
                logger.info("Re-created app registration (was 404): lumen_id=%s ms_object_id=%s", lumen_id, ms_object_id)
                summary.created += 1
            else:
                app_id = existing.get("appId")
                if existing.get("displayName") != name:
                    old_name = existing.get("displayName")
                    self._app_reg_svc.update_app_registration(ms_object_id, name)
                    logger.info("Updated app registration: lumen_id=%s old_name=%s new_name=%s", lumen_id, old_name, name)
                    summary.updated += 1
                else:
                    logger.info("App registration up-to-date: lumen_id=%s", lumen_id)

        if not app_id:
            logger.error("Could not determine appId for lumen_id=%s — skipping service principal", lumen_id)
            return None

        # --- Service Principal ---
        sp_record = self._sync_record_repo.get_sync_record(lumen_id, SYNC_TYPE, RESOURCE_SERVICE_PRINCIPAL)

        if sp_record is None:
            sp_id = self._app_reg_svc.create_service_principal(app_id)
            self._sync_record_repo.upsert_sync_record(lumen_id, sp_id, SYNC_TYPE, RESOURCE_SERVICE_PRINCIPAL)
            logger.info("Created service principal: lumen_id=%s sp_id=%s", lumen_id, sp_id)
            summary.created += 1
            return sp_id

        sp_id = sp_record.ms_object_id
        existing_sp = self._app_reg_svc.get_service_principal(sp_id)

        if existing_sp is None:
            sp_id = self._app_reg_svc.create_service_principal(app_id)
            self._sync_record_repo.upsert_sync_record(lumen_id, sp_id, SYNC_TYPE, RESOURCE_SERVICE_PRINCIPAL)
            logger.info("Re-created service principal (was 404): lumen_id=%s sp_id=%s", lumen_id, sp_id)
            summary.created += 1
        else:
            logger.info("Service principal up-to-date: lumen_id=%s sp_id=%s", lumen_id, sp_id)

        return sp_id
