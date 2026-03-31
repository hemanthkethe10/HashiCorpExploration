"""FastAPI server exposing the sync orchestrator as an HTTP endpoint.

Run with:
    uvicorn services.local_groups_to_entra_sync.server:app --reload

Required environment variables (loaded from .env via python-dotenv):
    TENANT_ID         - Azure AD tenant ID
    CLIENT_ID         - Service principal client ID
    CLIENT_SECRET     - Service principal client secret
    GRAPH_SCOPE       - Microsoft Graph scope (e.g. https://graph.microsoft.com/.default)
    DATABASE_HOST     - Database host
    DATABASE_PORT     - Database port
    DATABASE_NAME     - Database name
    DATABASE_USER     - Database user
    DATABASE_PASSWORD - Database password
"""

import logging
import os
import uuid
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .agent_identity_service import AgentIdentityService
from .app_registration_service import AppRegistrationService
from .entra_group_service import EntraGroupService
from .exceptions import AuthenticationError
from .models import Agent, Base, Client, Group, MCP_Server
from .orchestrator import SyncOrchestrator, SyncSummary
from .repositories import GroupRepository, SyncRecordRepository
from .token_provider import TokenProvider

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Local Groups to Entra Sync",
    description="Synchronizes local DB peer groups to Microsoft Entra security groups and App Registrations.",
    version="1.0.0",
)


@app.on_event("startup")
def create_sync_records_table() -> None:
    """Create the sync_records table if it doesn't exist on application startup."""
    try:
        engine = _get_engine()
        from .models import SyncRecord
        SyncRecord.__table__.create(bind=engine, checkfirst=True)
        logger.info("sync_records table ready")
    except Exception as exc:
        logger.error("Failed to create sync_records table: %s", exc, exc_info=True)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _build_database_url() -> str:
    host = _require_env("DATABASE_HOST")
    port = _require_env("DATABASE_PORT")
    name = _require_env("DATABASE_NAME")
    user = _require_env("DATABASE_USER")
    password = _require_env("DATABASE_PASSWORD")
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def _get_engine():
    database_url = _build_database_url()
    return create_engine(database_url)


def _get_session() -> Session:
    engine = _get_engine()
    return sessionmaker(bind=engine)()


def _build_orchestrator() -> SyncOrchestrator:
    tenant_id = _require_env("TENANT_ID")
    client_id = _require_env("CLIENT_ID")
    client_secret = _require_env("CLIENT_SECRET")
    graph_scope = _require_env("GRAPH_SCOPE")
    blueprint_principal_id = _require_env("AGENT_BLUEPRINT_PRINCIPAL_ID")

    session = _get_session()
    token_provider = TokenProvider(tenant_id, client_id, client_secret, graph_scope)
    group_repo = GroupRepository(session)
    sync_record_repo = SyncRecordRepository(session)
    entra_group_svc = EntraGroupService(token_provider)
    app_reg_svc = AppRegistrationService(token_provider)
    agent_identity_svc = AgentIdentityService(token_provider, blueprint_principal_id)

    return SyncOrchestrator(
        token_provider,
        group_repo,
        sync_record_repo,
        entra_group_svc,
        app_reg_svc,
        agent_identity_svc,
    )


@app.post("/sync", response_model=SyncSummary, summary="Trigger a full synchronization run")
def trigger_sync() -> SyncSummary:
    """Start a synchronization run.

    Reads all local groups from the database and mirrors them as Entra
    security groups and App Registrations. Returns a summary of the run.
    """
    try:
        orchestrator = _build_orchestrator()
    except RuntimeError as exc:
        logger.error("Configuration error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    try:
        summary = orchestrator.run()
    except AuthenticationError as exc:
        logger.error("Authentication failed: %s", exc)
        raise HTTPException(status_code=401, detail=f"Authentication failed: {exc}")
    except Exception as exc:
        logger.error("Unexpected error during sync: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sync failed: {exc}")

    return summary


@app.post("/seed", summary="Seed the database with test data")
def seed_database() -> dict:
    """Create tables and insert sample Groups, Clients, Agents, and MCP Servers.

    Safe to call multiple times — existing rows are skipped via merge.
    """
    try:
        engine = _get_engine()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    try:
        now = datetime.utcnow()

        agent_id = f"poet.dev-lumen.xeninc.us-a2a-test-{uuid.uuid4().hex[:8]}"
        client_id = f"client.{uuid.uuid4().hex[:8]}.example.com"
        mcp_id = f"mcp_{uuid.uuid4().hex[:16]}"

        agents = [
            Agent(
                id=agent_id,
                afa_name="Test Agent",
                afa_description="Seeded test agent",
                agent_url=f"https://example.com/a2a/{agent_id}/",
                agent_card=None,
                registered_by="seed-endpoint",
                agent_unique_ref=f"agent-{uuid.uuid4().hex[:12]}",
                timeout_ms=600000,
                enabled=False,
                changes_detected=False,
                is_deleted=False,
                created_at=now,
                updated_at=now,
            ),
        ]
        clients = [
            Client(
                id=client_id,
                name="Test Client",
                client_url=f"https://{client_id}/",
                description="Seeded test client",
                registered_by="seed-endpoint",
                enabled=False,
                is_deleted=False,
                created_at=now,
                updated_at=now,
            ),
        ]
        mcp_servers = [
            MCP_Server(
                id=mcp_id,
                name="Test MCP Server",
                description="Seeded test MCP server",
                mcp_url="https://example.com/api/mcp",
                registered_by="seed-endpoint",
                mcp_unique_ref=f"mcp-{uuid.uuid4().hex[:12]}",
                enabled=False,
                changes_detected=False,
                is_deleted=False,
                created_at=now,
                updated_at=now,
            ),
        ]

        for obj in agents + clients + mcp_servers:
            session.merge(obj)

        group = Group(
            id=f"peer_group_{uuid.uuid4().hex[:16]}",
            name="Test Peer Group",
            description="Seeded test group",
            members=f'{{"agent_ids": ["{agent_id}"], "client_ids": ["{client_id}"], "mcp_server_ids": ["{mcp_id}"]}}',
            policy_ids="[]",
            registered_by="seed-endpoint",
            is_deleted=False,
            created_at=now,
            updated_at=now,
        )
        session.merge(group)
        session.commit()

        logger.info("Database seeded successfully")
        return {
            "status": "seeded",
            "groups": 1,
            "agents": len(agents),
            "clients": len(clients),
            "mcp_servers": len(mcp_servers),
        }
    except Exception as exc:
        session.rollback()
        logger.error("Seed failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Seed failed: {exc}")
    finally:
        session.close()


class AddMemberRequest(BaseModel):
    group_id: str
    member_id: str


@app.post("/test/agent-identity", summary="[TEST] Create a single agent identity")
def test_create_agent_identity(display_name: str) -> dict:
    """Create one agent identity and return its ms_object_id.

    Useful for validating the blueprint principal config and payload
    before running a full sync.

    Query param:
        display_name: the displayName for the new agent identity
    """
    try:
        token_provider = TokenProvider(
            _require_env("TENANT_ID"),
            _require_env("CLIENT_ID"),
            _require_env("CLIENT_SECRET"),
            _require_env("GRAPH_SCOPE"),
        )
        blueprint_principal_id = _require_env("AGENT_BLUEPRINT_PRINCIPAL_ID")
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    svc = AgentIdentityService(token_provider, blueprint_principal_id)
    try:
        ms_object_id = svc.create_agent_identity(display_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"ms_object_id": ms_object_id, "display_name": display_name}


@app.post("/test/add-member", summary="[TEST] Add a member to a security group")
def test_add_member(body: AddMemberRequest) -> dict:
    """Add an existing directory object (agent identity, app registration, etc.)
    to a security group by providing both object IDs directly.

    Body:
        group_id:  ms_object_id of the target security group
        member_id: ms_object_id of the directory object to add
    """
    try:
        token_provider = TokenProvider(
            _require_env("TENANT_ID"),
            _require_env("CLIENT_ID"),
            _require_env("CLIENT_SECRET"),
            _require_env("GRAPH_SCOPE"),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    svc = EntraGroupService(token_provider)
    try:
        svc.add_group_member(body.group_id, body.member_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"status": "added", "group_id": body.group_id, "member_id": body.member_id}


@app.delete("/cleanup", summary="Delete all synced Entra resources and clear SyncRecords")
def cleanup() -> dict:
    """Delete every Entra resource that was created by a previous sync run.

    For each SyncRecord in the local DB:
    - security_group    → DELETE /v1.0/groups/{id}
    - app_registration  → DELETE /v1.0/applications/{id}
    - agent_identity    → DELETE /beta/servicePrincipals/{id}

    The SyncRecord row is removed from the DB after a successful (or 404) deletion,
    so the next call to /sync will treat all entities as new.

    Individual failures are collected and reported; they do not abort the cleanup.
    """
    try:
        token_provider = TokenProvider(
            _require_env("TENANT_ID"),
            _require_env("CLIENT_ID"),
            _require_env("CLIENT_SECRET"),
            _require_env("GRAPH_SCOPE"),
        )
        blueprint_principal_id = _require_env("AGENT_BLUEPRINT_PRINCIPAL_ID")
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    entra_group_svc = EntraGroupService(token_provider)
    app_reg_svc = AppRegistrationService(token_provider)
    agent_identity_svc = AgentIdentityService(token_provider, blueprint_principal_id)

    try:
        session = _get_session()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    sync_record_repo = SyncRecordRepository(session)
    records = sync_record_repo.get_all_sync_records()

    deleted, failed, errors = 0, 0, []

    for record in records:
        ms_id = record.ms_object_id
        rtype = record.resource_type
        try:
            if rtype == "security_group":
                entra_group_svc.delete_security_group(ms_id)
            elif rtype == "app_registration":
                app_reg_svc.delete_app_registration(ms_id)
            elif rtype == "agent_identity":
                agent_identity_svc.delete_agent_identity(ms_id)
            elif rtype == "service_principal":
                app_reg_svc.delete_service_principal(ms_id)
            elif rtype == "agent_instance":
                agent_identity_svc.delete_agent_instance(ms_id)
            else:
                logger.warning("Unknown resource_type=%s for SyncRecord id=%s — skipping", rtype, record.id)
                continue

            sync_record_repo.delete_sync_record(record)
            deleted += 1
            logger.info("Cleaned up %s ms_object_id=%s lumen_id=%s", rtype, ms_id, record.lumen_id)

        except Exception as exc:
            failed += 1
            msg = f"{rtype} ms_object_id={ms_id} lumen_id={record.lumen_id}: {exc}"
            errors.append(msg)
            logger.error("Cleanup failed for %s", msg)

    session.close()
    return {"deleted": deleted, "failed": failed, "errors": errors}


class CreateAgentRegistryRequest(BaseModel):
    display_name: str
    agent_url: str
    agent_card: dict
    owner_ids: list[str] = []


@app.post("/test/agent-registry", summary="[TEST] Create a single agent instance in the Entra Agent Registry")
def test_create_agent_registry(body: CreateAgentRegistryRequest) -> dict:
    """Create one agent identity + agent instance and return their IDs.

    Useful for validating the agentCardManifest mapping and agent registry
    creation flow without running a full sync.

    Body:
        display_name: display name for the agent identity and instance
        agent_url:    the A2A endpoint URL for the agent
        agent_card:   the raw local agent card dict (will be mapped to agentCardManifest)
        owner_ids:    optional list of owner object IDs
    """
    try:
        token_provider = TokenProvider(
            _require_env("TENANT_ID"),
            _require_env("CLIENT_ID"),
            _require_env("CLIENT_SECRET"),
            _require_env("GRAPH_SCOPE"),
        )
        blueprint_principal_id = _require_env("AGENT_BLUEPRINT_PRINCIPAL_ID")
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    svc = AgentIdentityService(token_provider, blueprint_principal_id)

    try:
        agent_identity_id = svc.create_agent_identity(body.display_name, resource_id=uuid.uuid4().hex)
    except Exception as exc:
        logger.error("Failed to create agent identity: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent identity creation failed: {exc}")

    try:
        instance_id = svc.create_agent_instance(
            display_name=body.display_name,
            agent_url=body.agent_url,
            agent_card=body.agent_card,
            agent_identity_id=agent_identity_id,
            owner_ids=body.owner_ids,
            blueprint_id=blueprint_principal_id,
        )
    except Exception as exc:
        logger.error("Failed to create agent instance: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent instance creation failed: {exc}")

    return {
        "agent_identity_id": agent_identity_id,
        "agent_instance_id": instance_id,
        "display_name": body.display_name,
    }


@app.get("/health", summary="Health check")
def health() -> dict:
    """Returns 200 OK when the server is running."""
    return {"status": "ok"}
