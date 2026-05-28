"""
Backlog API endpoints for KYROS Agile PM

Handles backlog item management with WSJF scoring and MoSCoW prioritization.
"""

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from ..config.logfire_config import get_logger
from ..services.agile import BacklogService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/backlog", tags=["backlog"])


# Request/Response Models
class AddBacklogItemRequest(BaseModel):
    project_id: str
    title: str
    description: str | None = ""
    item_type: str | None = "idea"  # idea, feature, bug, tech_debt, spike, improvement


class RefineBacklogItemRequest(BaseModel):
    business_value: int | None = Field(None, ge=0, le=10)
    time_criticality: int | None = Field(None, ge=0, le=10)
    risk_reduction: int | None = Field(None, ge=0, le=10)
    effort_estimate: int | None = Field(None, ge=0, le=10)
    moscow: str | None = None  # must, should, could, wont
    acceptance_criteria: str | None = None
    status: str | None = None  # new, refined, ready


class PromoteBacklogItemRequest(BaseModel):
    target_type: str  # epic or task
    epic_id: str | None = None  # Parent epic if promoting to task


class RejectBacklogItemRequest(BaseModel):
    reason: str | None = ""


# Endpoints
@router.post("")
async def add_backlog_item(request: AddBacklogItemRequest, response: Response):
    """
    Add a new item to the project backlog.

    After creation, kio-pm auto-triggers for WSJF scoring (when using MCP).
    """
    service = BacklogService()
    success, result = service.add_item(
        project_id=request.project_id,
        title=request.title,
        description=request.description or "",
        item_type=request.item_type or "idea"
    )

    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to add backlog item"))

    response.status_code = 201
    return result


@router.get("")
async def list_backlog_items(project_id: str, status: str | None = None):
    """
    List backlog items for a project, sorted by MoSCoW then WSJF.

    Query params:
    - project_id: Required project UUID
    - status: Optional filter (new, refined, ready, promoted, rejected)
    """
    service = BacklogService()
    success, result = service.list_items(project_id=project_id, status=status)

    if not success:
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to list backlog items"))

    return result


@router.get("/{item_id}")
async def get_backlog_item(item_id: str):
    """Get a single backlog item by ID."""
    service = BacklogService()
    success, result = service.get_item(item_id)

    if not success:
        raise HTTPException(status_code=404, detail=result.get("error", "Backlog item not found"))

    return result


@router.patch("/{item_id}/refine")
async def refine_backlog_item(item_id: str, request: RefineBacklogItemRequest):
    """
    Refine a backlog item with WSJF scores, MoSCoW priority, and acceptance criteria.

    WSJF Score = (business_value + time_criticality + risk_reduction) / effort_estimate
    """
    service = BacklogService()
    success, result = service.refine_item(
        item_id=item_id,
        business_value=request.business_value,
        time_criticality=request.time_criticality,
        risk_reduction=request.risk_reduction,
        effort_estimate=request.effort_estimate,
        moscow=request.moscow,
        acceptance_criteria=request.acceptance_criteria,
        status=request.status
    )

    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to refine backlog item"))

    return result


@router.post("/{item_id}/promote")
async def promote_backlog_item(item_id: str, request: PromoteBacklogItemRequest, response: Response):
    """
    Promote a backlog item to an Epic or Task.

    Requires item to be in 'ready' status (GK approved).
    """
    service = BacklogService()
    success, result = service.promote_item(
        item_id=item_id,
        target_type=request.target_type,
        epic_id=request.epic_id
    )

    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to promote backlog item"))

    response.status_code = 201
    return result


@router.post("/{item_id}/reject")
async def reject_backlog_item(item_id: str, request: RejectBacklogItemRequest):
    """Reject a backlog item with optional reason."""
    service = BacklogService()
    success, result = service.reject_item(item_id=item_id, reason=request.reason or "")

    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to reject backlog item"))

    return result
