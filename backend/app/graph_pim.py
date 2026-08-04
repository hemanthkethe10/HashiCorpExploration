import logging
from typing import Any, Literal

import httpx
from azure.identity import DefaultAzureCredential

from app.config import Settings
from app.pim_schemas import RoleAssignmentRemoveRequest, RoleAssignmentRequest

logger = logging.getLogger(__name__)

GRAPH_SCOPE = "https://graph.microsoft.com/.default"
ASSIGNMENT_SCHEDULE_REQUESTS_URL = (
    "https://graph.microsoft.com/v1.0/identityGovernance/"
    "privilegedAccess/group/assignmentScheduleRequests"
)

PimAction = Literal["adminAssign", "adminUpdate", "adminRemove"]


class GraphApiError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Microsoft Graph error {status_code}: {detail}")


class GraphPimClient:
    def __init__(self, settings: Settings, credential: DefaultAzureCredential | None = None) -> None:
        self._settings = settings
        self._credential = credential or DefaultAzureCredential(
            exclude_interactive_browser_credential=True
        )

    def _get_access_token(self) -> str:
        logger.info("Requesting Microsoft Graph token (scope=%s)", GRAPH_SCOPE)
        return self._credential.get_token(GRAPH_SCOPE).token

    def _build_payload(
        self,
        body: RoleAssignmentRequest | RoleAssignmentRemoveRequest,
        action: PimAction,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "accessId": body.access_id,
            "principalId": body.principal_id,
            "groupId": body.group_id,
            "action": action,
            "justification": body.justification,
        }
        if body.assignment_id:
            payload["assignmentId"] = body.assignment_id
        if action != "adminRemove" and isinstance(body, RoleAssignmentRequest):
            payload["scheduleInfo"] = body.schedule_info.model_dump(by_alias=True, exclude_none=True)
        return payload

    async def create_assignment(self, body: RoleAssignmentRequest) -> dict[str, Any]:
        return await self._submit_request(body, "adminAssign")

    async def update_assignment(self, body: RoleAssignmentRequest) -> dict[str, Any]:
        return await self._submit_request(body, "adminUpdate")

    async def remove_assignment(self, body: RoleAssignmentRemoveRequest) -> dict[str, Any]:
        return await self._submit_request(body, "adminRemove")

    async def _submit_request(
        self,
        body: RoleAssignmentRequest | RoleAssignmentRemoveRequest,
        action: PimAction,
    ) -> dict[str, Any]:
        payload = self._build_payload(body, action)
        token = self._get_access_token()

        logger.info(
            "Submitting PIM assignmentScheduleRequest (action=%s, groupId=%s, principalId=%s)",
            action,
            body.group_id,
            body.principal_id,
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                ASSIGNMENT_SCHEDULE_REQUESTS_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if response.is_error:
            logger.warning("Graph API request failed: %s", response.text)
            raise GraphApiError(response.status_code, response.text)

        return response.json()
