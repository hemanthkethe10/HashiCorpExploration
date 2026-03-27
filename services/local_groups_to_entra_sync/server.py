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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

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

    session = _get_session()
    token_provider = TokenProvider(tenant_id, client_id, client_secret, graph_scope)
    group_repo = GroupRepository(session)
    sync_record_repo = SyncRecordRepository(session)
    entra_group_svc = EntraGroupService(token_provider)
    app_reg_svc = AppRegistrationService(token_provider)

    return SyncOrchestrator(
        token_provider,
        group_repo,
        sync_record_repo,
        entra_group_svc,
        app_reg_svc,
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

        agents = [
            Agent(id=f"agent_{uuid.uuid4().hex[:8]}", name="Agent Alpha"),
            Agent(id=f"agent_{uuid.uuid4().hex[:8]}", name="Agent Beta"),
        ]
        clients = [
            Client(id=f"client_{uuid.uuid4().hex[:8]}", name="Client Gamma"),
            Client(id=f"client_{uuid.uuid4().hex[:8]}", name="Client Delta"),
        ]
        mcp_servers = [
            MCP_Server(id=f"mcp_{uuid.uuid4().hex[:8]}", name="MCP Server Epsilon"),
        ]

        for obj in agents + clients + mcp_servers:
            session.merge(obj)

        group = Group(
            id=f"peer_group_{uuid.uuid4().hex[:16]}",
            name="Test Peer Group",
            description="Seeded test group",
            members={
                "agent_ids": [a.id for a in agents],
                "client_ids": [c.id for c in clients],
                "mcp_server_ids": [m.id for m in mcp_servers],
            },
            policy_ids=[],
            registered_by="seed-endpoint",
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


@app.get("/health", summary="Health check")
def health() -> dict:
    """Returns 200 OK when the server is running."""
    return {"status": "ok"}
