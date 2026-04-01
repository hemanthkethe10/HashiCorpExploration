"""Pydantic response models for the sync service API."""

from pydantic import BaseModel, Field


class EntityFailure(BaseModel):
    lumen_id: str
    reason: str


class SyncSummaryResponse(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    skipped_entities: list[EntityFailure] = Field(default_factory=list)
    failed_entities: list[EntityFailure] = Field(default_factory=list)
