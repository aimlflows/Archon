"""
Sprints API endpoints for KYROS Agile PM

Handles sprint management with velocity tracking.
"""

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from ..config.logfire_config import get_logger
from ..services.agile import SprintService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/sprints", tags=["sprints"])


# Request/Response Models
class CreateSprintRequest(BaseModel):
    project_id: str
    name: str
    goal: str | None = ""
    start_date: str | None = None  # ISO date format
    end_date: str | None = None  # ISO date format


class UpdateSprintRequest(BaseModel):
    name: str | None = None
    goal: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class AssignTaskRequest(BaseModel):
    task_id: str
    sprint_id: str | None = None  # None to unassign


# Endpoints
@router.post("")
async def create_sprint(request: CreateSprintRequest, response: Response):
    """Create a new sprint."""
    service = SprintService()
    success, result = service.create_sprint(
        project_id=request.project_id,
        name=request.name,
        goal=request.goal or "",
        start_date=request.start_date,
        end_date=request.end_date
    )

    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to create sprint"))

    response.status_code = 201
    return result


@router.get("")
async def list_sprints(project_id: str):
    """
    List sprints for a project with progress stats.

    Returns sprints ordered: active first, then future, then closed.
    """
    service = SprintService()
    success, result = service.list_sprints(project_id=project_id)

    if not success:
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to list sprints"))

    return result


@router.get("/active")
async def get_active_sprint(project_id: str):
    """Get the currently active sprint for a project."""
    service = SprintService()
    success, result = service.get_active_sprint(project_id=project_id)

    if not success:
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to get active sprint"))

    return result


@router.get("/{sprint_id}")
async def get_sprint(sprint_id: str):
    """Get a single sprint by ID with progress stats."""
    service = SprintService()
    success, result = service.get_sprint(sprint_id)

    if not success:
        raise HTTPException(status_code=404, detail=result.get("error", "Sprint not found"))

    return result


@router.patch("/{sprint_id}")
async def update_sprint(sprint_id: str, request: UpdateSprintRequest):
    """Update sprint details."""
    service = SprintService()
    success, result = service.update_sprint(
        sprint_id=sprint_id,
        name=request.name,
        goal=request.goal,
        start_date=request.start_date,
        end_date=request.end_date
    )

    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to update sprint"))

    return result


@router.post("/{sprint_id}/start")
async def start_sprint(sprint_id: str):
    """
    Activate a sprint.

    - Closes any currently active sprint in the same project
    - Sets start_date if not already set
    """
    service = SprintService()
    success, result = service.start_sprint(sprint_id)

    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to start sprint"))

    return result


@router.post("/{sprint_id}/close")
async def close_sprint(sprint_id: str):
    """
    Close a sprint and calculate velocity.

    Returns summary including:
    - velocity (completed story points)
    - total/completed/incomplete task counts
    """
    service = SprintService()
    success, result = service.close_sprint(sprint_id)

    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to close sprint"))

    return result


@router.get("/{sprint_id}/tasks")
async def get_sprint_tasks(sprint_id: str):
    """Get all tasks assigned to a sprint."""
    service = SprintService()
    success, result = service.get_sprint_tasks(sprint_id)

    if not success:
        raise HTTPException(status_code=404, detail=result.get("error", "Sprint not found"))

    return result


@router.post("/assign-task")
async def assign_task_to_sprint(request: AssignTaskRequest):
    """
    Assign or unassign a task to a sprint.

    Set sprint_id to null to unassign.
    """
    service = SprintService()
    success, result = service.assign_task_to_sprint(
        task_id=request.task_id,
        sprint_id=request.sprint_id
    )

    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to assign task"))

    return result
