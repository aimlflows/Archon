"""
Task Dependencies API endpoints for KYROS Agile PM

Handles task dependencies, blocking/unblocking, and workflow queries.
"""

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from ..config.logfire_config import get_logger
from ..services.agile import DependencyService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/dependencies", tags=["dependencies"])


# Request/Response Models
class AddDependencyRequest(BaseModel):
    task_id: str
    blocked_by_task_id: str
    dependency_type: str = "blocks"  # blocks, relates_to, duplicates


class RemoveDependencyRequest(BaseModel):
    task_id: str
    blocked_by_task_id: str


class BlockTaskRequest(BaseModel):
    reason: str


class UnblockTaskRequest(BaseModel):
    resolution: str = ""


# Dependency Management Endpoints
@router.post("")
async def add_dependency(request: AddDependencyRequest, response: Response):
    """
    Add a dependency between two tasks.

    Validates for circular dependencies when type is 'blocks'.
    """
    service = DependencyService()
    success, result = service.add_dependency(
        task_id=request.task_id,
        blocked_by_task_id=request.blocked_by_task_id,
        dependency_type=request.dependency_type
    )

    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to add dependency"))

    response.status_code = 201
    return result


@router.delete("")
async def remove_dependency(request: RemoveDependencyRequest):
    """Remove a dependency between two tasks."""
    service = DependencyService()
    success, result = service.remove_dependency(
        task_id=request.task_id,
        blocked_by_task_id=request.blocked_by_task_id
    )

    if not success:
        raise HTTPException(status_code=404, detail=result.get("error", "Dependency not found"))

    return result


@router.get("/blockers/{task_id}")
async def get_task_blockers(task_id: str):
    """Get all tasks that block the given task."""
    service = DependencyService()
    success, result = service.get_task_blockers(task_id)

    if not success:
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to get blockers"))

    return result


@router.get("/dependents/{task_id}")
async def get_task_dependents(task_id: str):
    """Get all tasks that are blocked by the given task."""
    service = DependencyService()
    success, result = service.get_task_dependents(task_id)

    if not success:
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to get dependents"))

    return result


# Workflow Query Endpoints
@router.get("/unblocked")
async def get_unblocked_tasks(project_id: str, epic_id: str | None = None):
    """
    Get tasks that have no unresolved blocking dependencies.

    These are tasks ready to be worked on.
    """
    service = DependencyService()
    success, result = service.get_unblocked_tasks(project_id, epic_id)

    if not success:
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to get unblocked tasks"))

    return result


@router.get("/execution-order")
async def get_execution_order(project_id: str | None = None, epic_id: str | None = None):
    """
    Get tasks in dependency-aware execution order (topological sort).

    Returns tasks ordered by depth (0 = no dependencies first).
    """
    service = DependencyService()
    success, result = service.get_execution_order(project_id, epic_id)

    if not success:
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to get execution order"))

    return result


# Task Blocking Endpoints
@router.post("/tasks/{task_id}/block")
async def block_task(task_id: str, request: BlockTaskRequest):
    """
    Block a task with a reason.

    Blocked tasks are flagged for attention and may trigger kio-consultant.
    """
    service = DependencyService()
    success, result = service.block_task(task_id, request.reason)

    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to block task"))

    return result


@router.post("/tasks/{task_id}/unblock")
async def unblock_task(task_id: str, request: UnblockTaskRequest):
    """
    Unblock a task, returning it to todo status.

    Optionally include resolution notes.
    """
    service = DependencyService()
    success, result = service.unblock_task(task_id, request.resolution)

    if not success:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to unblock task"))

    return result


# Risk & Audit Endpoints
@router.get("/at-risk")
async def get_tasks_at_risk(project_id: str):
    """
    Get tasks at risk of auto-blocking based on inactivity threshold.

    Tasks with >75% of threshold elapsed are returned.
    """
    service = DependencyService()
    success, result = service.get_tasks_at_risk(project_id)

    if not success:
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to get tasks at risk"))

    return result


@router.get("/changelog/{entity_id}")
async def get_changelog(entity_id: str, entity_type: str = "task", limit: int = 20):
    """
    Get changelog/audit trail for an entity.

    Tracks status changes, blocks/unblocks, and other modifications.
    """
    service = DependencyService()
    success, result = service.get_changelog(entity_id, entity_type, limit)

    if not success:
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to get changelog"))

    return result
