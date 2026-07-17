"""
Workflow Runs API — REST endpoints over WorkflowRunService.

Slice 1 of NETRA Phase 5B: exposes the persistence layer for
kio_orchestrate() invocations. Consumers:
  - kyros-agents droid job runner (write side: create/start/append/complete)
  - Archon UI Droid Lanes view (read side: list running)
  - Archon MCP tools (`list_active_droids`, `list_review_tasks`, etc.)
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..config.logfire_config import get_logger
from ..services.agile import WorkflowRunService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/workflow-runs", tags=["workflow-runs"])


# ── Request models ───────────────────────────────────────────────────────

class CreateWorkflowRunRequest(BaseModel):
    workflow_name: str
    project_id: str | None = None
    sprint_id: str | None = None
    task_id: str | None = None
    persona: str | None = None
    invocation_input: dict | None = Field(default_factory=dict)


class AppendOutputsRequest(BaseModel):
    patch: dict


class SetOutcomesRequest(BaseModel):
    outcomes: dict


class FailRequest(BaseModel):
    error: str


# ── Endpoints ────────────────────────────────────────────────────────────

@router.post("")
async def create_workflow_run(request: CreateWorkflowRunRequest):
    """Register a new workflow run (state=pending)."""
    service = WorkflowRunService()
    success, result = service.create_run(
        workflow_name=request.workflow_name,
        project_id=request.project_id,
        sprint_id=request.sprint_id,
        task_id=request.task_id,
        persona=request.persona,
        invocation_input=request.invocation_input,
    )
    if not success:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("")
async def list_workflow_runs(
    project_id: str | None = Query(default=None),
    state: str | None = Query(default=None),
    persona: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
):
    """List workflow runs with optional filters (project, state, persona)."""
    service = WorkflowRunService()
    success, result = service.list_runs(
        project_id=project_id, state=state, persona=persona, limit=limit
    )
    if not success:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/{run_id}")
async def get_workflow_run(run_id: str):
    service = WorkflowRunService()
    success, result = service.get_run(run_id)
    if not success:
        raise HTTPException(status_code=404, detail=result.get("error"))
    return result


@router.post("/{run_id}/start")
async def start_workflow_run(run_id: str):
    """Transition pending → running (droid picked up the work)."""
    service = WorkflowRunService()
    success, result = service.mark_started(run_id)
    if not success:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/{run_id}/append-outputs")
async def append_workflow_outputs(run_id: str, request: AppendOutputsRequest):
    """Stream intermediate outputs (droid runner posts here as it works)."""
    service = WorkflowRunService()
    success, result = service.append_outputs(run_id, request.patch)
    if not success:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/{run_id}/complete")
async def complete_workflow_run(run_id: str, outputs: dict | None = None):
    """Transition to 'completed'. Final outputs snapshot optional."""
    service = WorkflowRunService()
    success, result = service.mark_completed(run_id, outputs)
    if not success:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/{run_id}/fail")
async def fail_workflow_run(run_id: str, request: FailRequest):
    service = WorkflowRunService()
    success, result = service.mark_failed(run_id, request.error)
    if not success:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/{run_id}/cancel")
async def cancel_workflow_run(run_id: str):
    service = WorkflowRunService()
    success, result = service.mark_cancelled(run_id)
    if not success:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/{run_id}/outcomes")
async def set_workflow_outcomes(run_id: str, request: SetOutcomesRequest):
    """Slice 5: post-hoc outcome tracking (PR merged? tests pass?)."""
    service = WorkflowRunService()
    success, result = service.set_outcomes(run_id, request.outcomes)
    if not success:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result
