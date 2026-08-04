from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ScheduleExpiration(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["afterDateTime", "afterDuration", "noExpiration"] = "afterDateTime"
    end_date_time: str | None = Field(None, alias="endDateTime")


class ScheduleInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    start_date_time: str | None = Field(None, alias="startDateTime")
    expiration: ScheduleExpiration


class RoleAssignmentRequest(BaseModel):
    """Payload for PIM group assignment schedule requests (assign / update)."""

    model_config = ConfigDict(populate_by_name=True)

    access_id: Literal["member", "owner"] = Field("member", alias="accessId")
    principal_id: str = Field(alias="principalId")
    group_id: str = Field(alias="groupId")
    justification: str = "Lumen Exploration"
    schedule_info: ScheduleInfo = Field(alias="scheduleInfo")
    assignment_id: str | None = Field(None, alias="assignmentId")


class RoleAssignmentRemoveRequest(BaseModel):
    """Payload for removing an existing PIM group assignment."""

    model_config = ConfigDict(populate_by_name=True)

    access_id: Literal["member", "owner"] = Field("member", alias="accessId")
    principal_id: str = Field(alias="principalId")
    group_id: str = Field(alias="groupId")
    justification: str = "Lumen Exploration"
    assignment_id: str | None = Field(None, alias="assignmentId")


class RoleAssignmentResponse(BaseModel):
    action: str
    request: dict
