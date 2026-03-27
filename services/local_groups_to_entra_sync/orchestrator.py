import logging
from dataclasses import dataclass, field

from .app_registration_service import AppRegistrationService
from .entra_group_service import EntraGroupService
from .repositories import GroupRepository, SyncRecordRepository
from .token_provider import TokenProvider

logger = logging.getLogger(__name__)

SYNC_TYPE = "MS Graph"
RESOURCE_SECURITY_GROUP = "security_group"
RESOURCE_APP_REGISTRATION = "app_registration"


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
    ):
        self._token_provider = token_provider
        self._group_repo = group_repo
        self._sync_record_repo = sync_record_repo
        self._entra_group_svc = entra_group_svc
        self._app_reg_svc = app_reg_svc

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

            # Step 3: Sync the security group for this group
            try:
                self._sync_security_group(group.id, group.name, summary)
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
            resolved_client_ids = {c.id for c in clients}
            for mid in client_ids:
                if mid not in resolved_client_ids:
                    logger.warning("Unresolved client_id=%s in group lumen_id=%s", mid, group.id)

            resolved_agent_ids = {a.id for a in agents}
            for mid in agent_ids:
                if mid not in resolved_agent_ids:
                    logger.warning("Unresolved agent_id=%s in group lumen_id=%s", mid, group.id)

            resolved_mcp_ids = {m.id for m in mcp_servers}
            for mid in mcp_server_ids:
                if mid not in resolved_mcp_ids:
                    logger.warning("Unresolved mcp_server_id=%s in group lumen_id=%s", mid, group.id)

            # Step 5: Sync security groups for agents (no App Registration)
            for agent in agents:
                try:
                    self._sync_security_group(agent.id, agent.name, summary)
                except Exception as exc:
                    logger.error(
                        "Failed to sync security group for agent lumen_id=%s name=%s: %s",
                        agent.id, agent.name, exc,
                    )
                    summary.failed += 1
                    summary.failed_entities.append({"lumen_id": agent.id, "reason": str(exc)})

            # Step 6: Sync security groups + App Registrations for clients
            for client in clients:
                try:
                    self._sync_security_group(client.id, client.name, summary)
                except Exception as exc:
                    logger.error(
                        "Failed to sync security group for client lumen_id=%s name=%s: %s",
                        client.id, client.name, exc,
                    )
                    summary.failed += 1
                    summary.failed_entities.append({"lumen_id": client.id, "reason": str(exc)})

                try:
                    self._sync_app_registration(client.id, client.name, summary)
                except Exception as exc:
                    logger.error(
                        "Failed to sync app registration for client lumen_id=%s name=%s: %s",
                        client.id, client.name, exc,
                    )
                    summary.failed += 1
                    summary.failed_entities.append({"lumen_id": client.id, "reason": str(exc)})

            # Step 7: Sync security groups + App Registrations for MCP servers
            for mcp in mcp_servers:
                try:
                    self._sync_security_group(mcp.id, mcp.name, summary)
                except Exception as exc:
                    logger.error(
                        "Failed to sync security group for mcp_server lumen_id=%s name=%s: %s",
                        mcp.id, mcp.name, exc,
                    )
                    summary.failed += 1
                    summary.failed_entities.append({"lumen_id": mcp.id, "reason": str(exc)})

                try:
                    self._sync_app_registration(mcp.id, mcp.name, summary)
                except Exception as exc:
                    logger.error(
                        "Failed to sync app registration for mcp_server lumen_id=%s name=%s: %s",
                        mcp.id, mcp.name, exc,
                    )
                    summary.failed += 1
                    summary.failed_entities.append({"lumen_id": mcp.id, "reason": str(exc)})

        # Step 8: Emit summary
        logger.info(
            "Sync complete: created=%d updated=%d skipped=%d failed=%d",
            summary.created, summary.updated, summary.skipped, summary.failed,
        )
        for entry in summary.skipped_entities:
            logger.warning("Skipped entity: lumen_id=%s reason=%s", entry["lumen_id"], entry["reason"])
        for entry in summary.failed_entities:
            logger.error("Failed entity: lumen_id=%s reason=%s", entry["lumen_id"], entry["reason"])

        return summary

    def _sync_security_group(self, lumen_id: str, name: str, summary: SyncSummary) -> None:
        """Create or update an Entra security group for the given entity."""
        record = self._sync_record_repo.get_sync_record(lumen_id, SYNC_TYPE, RESOURCE_SECURITY_GROUP)

        if record is None:
            ms_object_id = self._entra_group_svc.create_security_group(name, lumen_id)
            self._sync_record_repo.upsert_sync_record(lumen_id, ms_object_id, SYNC_TYPE, RESOURCE_SECURITY_GROUP)
            logger.info("Created security group: lumen_id=%s ms_object_id=%s", lumen_id, ms_object_id)
            summary.created += 1
        else:
            ms_object_id = record.ms_object_id
            existing = self._entra_group_svc.get_security_group(ms_object_id)

            if existing is None:
                # 404 — treat as new
                ms_object_id = self._entra_group_svc.create_security_group(name, lumen_id)
                self._sync_record_repo.upsert_sync_record(lumen_id, ms_object_id, SYNC_TYPE, RESOURCE_SECURITY_GROUP)
                logger.info("Re-created security group (was 404): lumen_id=%s ms_object_id=%s", lumen_id, ms_object_id)
                summary.created += 1
            elif existing.get("displayName") != name:
                old_name = existing.get("displayName")
                self._entra_group_svc.update_security_group(ms_object_id, name)
                logger.info(
                    "Updated security group: lumen_id=%s old_name=%s new_name=%s",
                    lumen_id, old_name, name,
                )
                summary.updated += 1
            else:
                logger.info("Security group up-to-date: lumen_id=%s", lumen_id)

    def _sync_app_registration(self, lumen_id: str, name: str, summary: SyncSummary) -> None:
        """Create or update an Entra App Registration for the given entity."""
        record = self._sync_record_repo.get_sync_record(lumen_id, SYNC_TYPE, RESOURCE_APP_REGISTRATION)

        if record is None:
            ms_object_id = self._app_reg_svc.create_app_registration(name)
            self._sync_record_repo.upsert_sync_record(lumen_id, ms_object_id, SYNC_TYPE, RESOURCE_APP_REGISTRATION)
            logger.info("Created app registration: lumen_id=%s ms_object_id=%s", lumen_id, ms_object_id)
            summary.created += 1
        else:
            ms_object_id = record.ms_object_id
            existing = self._app_reg_svc.get_app_registration(ms_object_id)

            if existing is None:
                # 404 — treat as new
                ms_object_id = self._app_reg_svc.create_app_registration(name)
                self._sync_record_repo.upsert_sync_record(lumen_id, ms_object_id, SYNC_TYPE, RESOURCE_APP_REGISTRATION)
                logger.info("Re-created app registration (was 404): lumen_id=%s ms_object_id=%s", lumen_id, ms_object_id)
                summary.created += 1
            elif existing.get("displayName") != name:
                old_name = existing.get("displayName")
                self._app_reg_svc.update_app_registration(ms_object_id, name)
                logger.info(
                    "Updated app registration: lumen_id=%s old_name=%s new_name=%s",
                    lumen_id, old_name, name,
                )
                summary.updated += 1
            else:
                logger.info("App registration up-to-date: lumen_id=%s", lumen_id)
