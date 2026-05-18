from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.graph_pim import GraphApiError, GraphPimClient
from app.pim_schemas import (
    RoleAssignmentRemoveRequest,
    RoleAssignmentRequest,
    RoleAssignmentResponse,
)

router = APIRouter(prefix="/api/pim", tags=["pim"])


def get_graph_pim_client(request: Request) -> GraphPimClient:
    client = getattr(request.app.state, "graph_pim_client", None)
    if client is None:
        raise HTTPException(status_code=503, detail="Graph PIM client is not initialized.")
    return client


@router.post("/role-assignments", response_model=RoleAssignmentResponse)
async def create_role_assignment(
    body: RoleAssignmentRequest,
    client: Annotated[GraphPimClient, Depends(get_graph_pim_client)],
) -> RoleAssignmentResponse:
    """Create a PIM group assignment (Graph action: adminAssign)."""
    try:
        result = await client.create_assignment(body)
    except GraphApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return RoleAssignmentResponse(action="adminAssign", request=result)


@router.patch("/role-assignments", response_model=RoleAssignmentResponse)
async def update_role_assignment(
    body: RoleAssignmentRequest,
    client: Annotated[GraphPimClient, Depends(get_graph_pim_client)],
) -> RoleAssignmentResponse:
    """Update a PIM group assignment (Graph action: adminUpdate)."""
    try:
        result = await client.update_assignment(body)
    except GraphApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return RoleAssignmentResponse(action="adminUpdate", request=result)


@router.delete("/role-assignments", response_model=RoleAssignmentResponse)
async def delete_role_assignment(
    body: RoleAssignmentRemoveRequest,
    client: Annotated[GraphPimClient, Depends(get_graph_pim_client)],
) -> RoleAssignmentResponse:
    """Remove a PIM group assignment (Graph action: adminRemove)."""
    try:
        result = await client.remove_assignment(body)
    except GraphApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return RoleAssignmentResponse(action="adminRemove", request=result)
