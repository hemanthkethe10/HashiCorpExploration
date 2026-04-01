"""Pydantic request models for the sync service API."""

from pydantic import BaseModel


class AddMemberRequest(BaseModel):
    group_id: str
    member_id: str


class CreateAgentRegistryRequest(BaseModel):
    display_name: str
    agent_url: str
