"""
Epics API endpoints for KYROS Agile PM

Handles epic management with progress tracking and UAT sign-off workflow.
"""

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from ..config.logfire_config import get_logger
from ..services.agile import EpicService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/epics", tags=["epics"])


# Request/Response Models
class CreateEpicRequest(BaseModel):
    project_id: str
    title: str
    description: str | None = ""
    acceptance_criteria: str | None = None
    target_date: str | None = None  # ISO date format
    priority: str | None = "medium"  # highest, high, medium, low, lowest


class UpdateEpicRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    acceptance_criteria: str | None = None
    target_date: str | None = None
    priority: str | None = None


class UpdateEpicStatusRequest(BaseModel):
    status: str  # open, in_progress, testing, done, cancelled
    uat_approved: bool | None = False  # Required True for done status


class CancelEpicRequest(BaseModel):
    reason: str | None = ""


# Endpoints
@router.post("")
async def create_epic(request: CreateEpicRequest, response: Response):
    """Create a new epic."""
    service = EpicService()
    success, result = service.create_epic(
        project_id=request.project_id,
        title=request.title,
        description=request.description or "",
        acceptance_criteria=request.acceptance_criteria,
        target_date=request.target_date,
        priority=request.priority or "medium"
    )

    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to create epic"))

    response.status_code = 201
    return result


@router.get("")
async def list_epics(project_id: str, status: str | None = None):
    """
    List epics for a project with progress stats.

    Query params:
    - project_id: Required project UUID
    - status: Optional filter (open, in_progress, testing, done, cancelled)
    """
    service = EpicService()
    success, result = service.list_epics(project_id=project_id, status=status)

    if not success:
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to list epics"))

    return result


@router.get("/{epic_id}")
async def get_epic(epic_id: str):
    """Get a single epic by ID or key with progress stats."""
    service = EpicService()
    success, result = service.get_epic(epic_id)

    if not success:
        raise HTTPException(status_code=404, detail=result.get("error", "Epic not found"))

    return result


@router.patch("/{epic_id}")
async def update_epic(epic_id: str, request: UpdateEpicRequest):
    """Update epic details (not status - use PATCH /{epic_id}/status for that)."""
    service = EpicService()
    success, result = service.update_epic(
        epic_id=epic_id,
        title=request.title,
        description=request.description,
        acceptance_criteria=request.acceptance_criteria,
        target_date=request.target_date,
        priority=request.priority
    )

    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to update epic"))

    return result


@router.patch("/{epic_id}/status")
async def update_epic_status(epic_id: str, request: UpdateEpicStatusRequest):
    """
    Update epic status.

    Rules:
    - Moving to 'done' requires uat_approved=True (GK sign-off)
    - Moving to 'done' requires epic to be in 'testing' status first
    """
    service = EpicService()
    success, result = service.update_status(
        epic_id=epic_id,
        new_status=request.status,
        uat_approved=request.uat_approved or False
    )

    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to update epic status"))

    return result


@router.post("/{epic_id}/cancel")
async def cancel_epic(epic_id: str, request: CancelEpicRequest):
    """Cancel an epic with optional reason."""
    service = EpicService()
    success, result = service.cancel_epic(epic_id=epic_id, reason=request.reason or "")

    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to cancel epic"))

    return result


@router.get("/{epic_id}/tasks")
async def get_epic_tasks(epic_id: str):
    """Get all tasks for an epic."""
    service = EpicService()
    success, result = service.get_tasks(epic_id)

    if not success:
        raise HTTPException(status_code=404, detail=result.get("error", "Epic not found"))

    return result


@router.get("/{epic_id}/execution-order")
async def get_execution_order(epic_id: str):
    """
    Get recommended task execution order for an epic based on dependencies.

    Uses topological sort to order tasks by their dependency graph.
    """
    service = EpicService()
    success, result = service.get_execution_order(epic_id=epic_id)

    if not success:
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to get execution order"))

    return result
