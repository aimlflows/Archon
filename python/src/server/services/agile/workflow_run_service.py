"""
Workflow Run Service — persistence for kio_orchestrate() invocations.

Slice 1 of NETRA Phase 5B (2026-07-17): the droid factory needs durable
state for background droid work. Every kio_orchestrate() call by the
kyros-agents droid runner produces one archon_workflow_runs row that
Archon UI's Droid Lanes view surfaces in real time.
"""

from datetime import datetime
from typing import Any

from src.server.utils import get_supabase_client

from ...config.logfire_config import get_logger

logger = get_logger(__name__)


VALID_STATES = ("pending", "running", "completed", "failed", "cancelled")


class WorkflowRunService:
    """CRUD + state transitions for archon_workflow_runs."""

    def __init__(self, supabase_client=None):
        self.supabase_client = supabase_client or get_supabase_client()

    # ────────────────────────────────────────────────────────────
    # CRUD
    # ────────────────────────────────────────────────────────────

    def create_run(
        self,
        workflow_name: str,
        project_id: str | None = None,
        sprint_id: str | None = None,
        task_id: str | None = None,
        persona: str | None = None,
        invocation_input: dict | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """Register a new workflow run (state='pending' unless started immediately)."""
        try:
            if not workflow_name or not workflow_name.strip():
                return False, {"error": "workflow_name is required"}

            row = {
                "workflow_name": workflow_name.strip(),
                "persona": persona,
                "project_id": project_id,
                "sprint_id": sprint_id,
                "task_id": task_id,
                "state": "pending",
                "invocation_input": invocation_input or {},
                "outputs": {},
                "outcomes": {},
            }
            response = self.supabase_client.table("archon_workflow_runs").insert(row).execute()
            if not response.data:
                return False, {"error": "Insert returned no data"}
            run = response.data[0]
            logger.info(f"Workflow run created: {run['id'][:8]} — {workflow_name}")
            return True, {"run": run}
        except Exception as e:
            logger.error(f"create_run failed: {e}")
            return False, {"error": str(e)}

    def get_run(self, run_id: str) -> tuple[bool, dict[str, Any]]:
        try:
            response = (
                self.supabase_client.table("archon_workflow_runs")
                .select("*")
                .eq("id", run_id)
                .execute()
            )
            if not response.data:
                return False, {"error": f"Run '{run_id}' not found"}
            return True, {"run": response.data[0]}
        except Exception as e:
            logger.error(f"get_run failed: {e}")
            return False, {"error": str(e)}

    def list_runs(
        self,
        project_id: str | None = None,
        state: str | None = None,
        persona: str | None = None,
        limit: int = 50,
    ) -> tuple[bool, dict[str, Any]]:
        """List workflow runs with optional filters. Ordered newest first."""
        try:
            query = self.supabase_client.table("archon_workflow_runs").select("*")
            if project_id:
                query = query.eq("project_id", project_id)
            if state:
                if state not in VALID_STATES:
                    return False, {"error": f"invalid state '{state}'"}
                query = query.eq("state", state)
            if persona:
                query = query.eq("persona", persona)
            response = query.order("created_at", desc=True).limit(limit).execute()
            runs = response.data or []
            return True, {"runs": runs, "count": len(runs)}
        except Exception as e:
            logger.error(f"list_runs failed: {e}")
            return False, {"error": str(e)}

    # ────────────────────────────────────────────────────────────
    # State transitions
    # ────────────────────────────────────────────────────────────

    def mark_started(self, run_id: str) -> tuple[bool, dict[str, Any]]:
        return self._update_state(run_id, "running", extra={"started_at": datetime.now().isoformat()})

    def mark_completed(
        self, run_id: str, outputs: dict | None = None
    ) -> tuple[bool, dict[str, Any]]:
        extra: dict[str, Any] = {"completed_at": datetime.now().isoformat()}
        if outputs is not None:
            extra["outputs"] = outputs
        return self._update_state(run_id, "completed", extra=extra)

    def mark_failed(self, run_id: str, error: str) -> tuple[bool, dict[str, Any]]:
        return self._update_state(
            run_id,
            "failed",
            extra={"completed_at": datetime.now().isoformat(), "error": error},
        )

    def mark_cancelled(self, run_id: str) -> tuple[bool, dict[str, Any]]:
        return self._update_state(
            run_id, "cancelled", extra={"completed_at": datetime.now().isoformat()}
        )

    def append_outputs(self, run_id: str, patch: dict) -> tuple[bool, dict[str, Any]]:
        """Merge `patch` into outputs JSONB — used by droid runner to stream
        intermediate results without waiting for completion."""
        try:
            ok, current = self.get_run(run_id)
            if not ok:
                return False, current
            merged = {**(current["run"].get("outputs") or {}), **patch}
            response = (
                self.supabase_client.table("archon_workflow_runs")
                .update({"outputs": merged})
                .eq("id", run_id)
                .execute()
            )
            if not response.data:
                return False, {"error": "Update returned no data"}
            return True, {"run": response.data[0]}
        except Exception as e:
            logger.error(f"append_outputs failed: {e}")
            return False, {"error": str(e)}

    def set_outcomes(self, run_id: str, outcomes: dict) -> tuple[bool, dict[str, Any]]:
        """Slice 5: post-hoc outcome tracking (PR merged? tests pass? value shipped?)."""
        try:
            response = (
                self.supabase_client.table("archon_workflow_runs")
                .update({"outcomes": outcomes})
                .eq("id", run_id)
                .execute()
            )
            if not response.data:
                return False, {"error": "Update returned no data"}
            return True, {"run": response.data[0]}
        except Exception as e:
            logger.error(f"set_outcomes failed: {e}")
            return False, {"error": str(e)}

    def _update_state(
        self,
        run_id: str,
        state: str,
        extra: dict | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        if state not in VALID_STATES:
            return False, {"error": f"invalid state '{state}'"}
        try:
            payload: dict[str, Any] = {"state": state}
            if extra:
                payload.update(extra)
            response = (
                self.supabase_client.table("archon_workflow_runs")
                .update(payload)
                .eq("id", run_id)
                .execute()
            )
            if not response.data:
                return False, {"error": f"Run '{run_id}' not found or update failed"}
            return True, {"run": response.data[0]}
        except Exception as e:
            logger.error(f"_update_state({state}) failed: {e}")
            return False, {"error": str(e)}
