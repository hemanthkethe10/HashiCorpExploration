from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Group(Base):
    __tablename__ = "groups"

    id = Column(String, primary_key=True)   # Lumen_ID
    name = Column(String, nullable=False)    # Lumen_Name
    description = Column(String, nullable=True)
    members = Column(JSON)                   # {agent_ids: [], client_ids: [], mcp_server_ids: []}
    policy_ids = Column(JSON)                # stored, not processed
    registered_by = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class Client(Base):
    __tablename__ = "clients"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)


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
