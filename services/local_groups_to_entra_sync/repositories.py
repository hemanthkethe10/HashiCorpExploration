import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from .models import Agent, Client, Group, MCP_Server, SyncRecord

logger = logging.getLogger(__name__)


class GroupRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_all_groups(self) -> list[Group]:
        return self._session.query(Group).all()

    def get_clients_by_ids(self, ids: list[str]) -> list[Client]:
        if not ids:
            return []
        return self._session.query(Client).filter(Client.id.in_(ids)).all()

    def get_agents_by_ids(self, ids: list[str]) -> list[Agent]:
        if not ids:
            return []
        return self._session.query(Agent).filter(Agent.id.in_(ids)).all()

    def get_mcp_servers_by_ids(self, ids: list[str]) -> list[MCP_Server]:
        if not ids:
            return []
        return self._session.query(MCP_Server).filter(MCP_Server.id.in_(ids)).all()


class SyncRecordRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_sync_record(
        self, lumen_id: str, sync_type: str, resource_type: str
    ) -> SyncRecord | None:
        return (
            self._session.query(SyncRecord)
            .filter(
                SyncRecord.lumen_id == lumen_id,
                SyncRecord.sync_type == sync_type,
                SyncRecord.resource_type == resource_type,
            )
            .first()
        )

    def upsert_sync_record(
        self, lumen_id: str, ms_object_id: str, sync_type: str, resource_type: str
    ) -> SyncRecord:
        try:
            record = self.get_sync_record(lumen_id, sync_type, resource_type)
            now = datetime.utcnow()
            if record is None:
                record = SyncRecord(
                    id=str(uuid.uuid4()),
                    lumen_id=lumen_id,
                    ms_object_id=ms_object_id,
                    sync_type=sync_type,
                    resource_type=resource_type,
                    created_at=now,
                    updated_at=now,
                )
                self._session.add(record)
            else:
                record.ms_object_id = ms_object_id
                record.updated_at = now
            self._session.commit()
            return record
        except Exception:
            logger.error(
                "Failed to write SyncRecord for lumen_id=%s ms_object_id=%s",
                lumen_id,
                ms_object_id,
            )
            self._session.rollback()
            return SyncRecord(
                id=str(uuid.uuid4()),
                lumen_id=lumen_id,
                ms_object_id=ms_object_id,
                sync_type=sync_type,
                resource_type=resource_type,
            )
