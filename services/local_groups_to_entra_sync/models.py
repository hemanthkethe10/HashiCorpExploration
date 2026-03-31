from sqlalchemy import Boolean, Column, String, DateTime, JSON, BigInteger
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Group(Base):
    """Maps to the afa_peer_groups_registry collection/table."""
    __tablename__ = "afa_peer_groups_registry"

    id            = Column(String, primary_key=True)   # Lumen_ID, pushed to Entra extension
    name          = Column(String, nullable=True)       # Lumen_Name — nullable, groups without name are skipped
    description   = Column(String, nullable=True)
    members       = Column(String, nullable=True)       # JSON-encoded string: {"agent_ids":[], "client_ids":[], "mcp_server_ids":[]}
    policy_ids    = Column(String, nullable=True)       # JSON-encoded string array, stored but not processed
    registered_by = Column(String, nullable=True)
    is_deleted    = Column(Boolean, nullable=True, default=False)
    created_at    = Column(DateTime, nullable=True)
    updated_at    = Column(DateTime, nullable=True)


class Client(Base):
    __tablename__ = "clients"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class Agent(Base):
    """Maps to the afa_agents_registry collection/table."""
    __tablename__ = "afa_agents_registry"

    id                  = Column(String, primary_key=True)   # full agent identifier
    afa_name            = Column(String, nullable=False)      # display name (was `name`)
    afa_description     = Column(String, nullable=True)
    agent_url           = Column(String, nullable=True)
    agent_card          = Column(String, nullable=True)       # raw JSON string
    custom_tags         = Column(String, nullable=True)       # JSON-encoded string array
    search_skills_tags  = Column(String, nullable=True)       # JSON-encoded string array
    registered_by       = Column(String, nullable=True)
    agent_unique_ref    = Column(String, nullable=True)
    timeout_ms          = Column(BigInteger, nullable=True)
    agent_icon          = Column(String, nullable=True)
    eval_score_avg      = Column(String, nullable=True)
    enabled             = Column(Boolean, nullable=True, default=False)
    changes_detected    = Column(Boolean, nullable=True, default=False)
    synced_agent_card   = Column(String, nullable=True)
    is_deleted          = Column(Boolean, nullable=True, default=False)
    created_at          = Column(DateTime, nullable=True)
    updated_at          = Column(DateTime, nullable=True)


class MCP_Server(Base):
    __tablename__ = "mcp_servers"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class SyncRecord(Base):
    __tablename__ = "sync_records"

    id = Column(String, primary_key=True)          # internal UUID
    lumen_id = Column(String, nullable=False)       # references Group/Client/Agent/MCP_Server.id
    ms_object_id = Column(String, nullable=False)
    sync_type = Column(String, nullable=False)      # e.g. "MS Graph"
    resource_type = Column(String, nullable=False)  # "security_group" | "app_registration"
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
