"""
Droid factory MCP tools — NETRA Phase 5B Slice 1.

Exposes 4 tools that make the NETRA droid factory operable from any
MCP client (Claude Code / Antigravity / Cursor / …):

  list_active_droids(project_id=None)     → active workflow_runs
  list_review_tasks(project_id=None)      → tasks awaiting HITL approval
  approve_task(task_id, decision, notes)  → close the HITL gate
  assign_droid(task_id, persona)          → route a task to a droid

Follows the existing HTTP-based module pattern (features/tasks/task_tools.py).
"""

import json
import logging

import httpx
from mcp.server.fastmcp import Context, FastMCP

from src.mcp_server.utils.error_handling import MCPErrorFormatter
from src.mcp_server.utils.timeout_config import get_default_timeout
from src.server.config.service_discovery import get_api_url

logger = logging.getLogger(__name__)

VALID_DECISIONS = ("approve", "reject", "redirect")


def register_droid_tools(mcp: FastMCP) -> None:
    """Register the 4 droid-factory MCP tools with the server."""

    @mcp.tool()
    async def list_active_droids(
        ctx: Context,
        project_id: str | None = None,
        persona: str | None = None,
        limit: int = 25,
    ) -> str:
        """
        List droids currently running (workflow_runs.state='running').

        Args:
            project_id: Filter to a single project (optional).
            persona:    Filter by persona (e.g. "kio-dev", "kio-qa"). Optional.
            limit:      Max rows (default 25).

        Returns:
            JSON: {"runs":[...], "count": N}
        """
        try:
            api = get_api_url()
            params: dict = {"state": "running", "limit": limit}
            if project_id:
                params["project_id"] = project_id
            if persona:
                params["persona"] = persona
            async with httpx.AsyncClient(timeout=get_default_timeout()) as client:
                r = await client.get(f"{api}/api/workflow-runs", params=params)
                r.raise_for_status()
                return json.dumps(r.json())
        except httpx.HTTPStatusError as e:
            return MCPErrorFormatter.from_http_error("list_active_droids", e)
        except Exception as e:
            logger.exception("list_active_droids failed")
            return MCPErrorFormatter.format_error("list_active_droids", str(e))

    @mcp.tool()
    async def list_review_tasks(
        ctx: Context,
        project_id: str | None = None,
        limit: int = 25,
    ) -> str:
        """
        List tasks awaiting HITL review (tasks with status='review').

        Args:
            project_id: Filter to a single project (optional).
            limit:      Max rows.

        Returns:
            JSON: {"tasks":[...], "count": N}
        """
        try:
            api = get_api_url()
            params: dict = {"filter_by": "status", "filter_value": "review", "per_page": limit}
            if project_id:
                params["project_id"] = project_id
            async with httpx.AsyncClient(timeout=get_default_timeout()) as client:
                r = await client.get(f"{api}/api/tasks", params=params)
                r.raise_for_status()
                return json.dumps(r.json())
        except httpx.HTTPStatusError as e:
            return MCPErrorFormatter.from_http_error("list_review_tasks", e)
        except Exception as e:
            logger.exception("list_review_tasks failed")
            return MCPErrorFormatter.format_error("list_review_tasks", str(e))

    @mcp.tool()
    async def approve_task(
        ctx: Context,
        task_id: str,
        decision: str,
        notes: str | None = None,
    ) -> str:
        """
        HITL gate action on a task in the 'review' column.

        Args:
            task_id:  UUID of the task.
            decision: "approve" (→ status=done) | "reject" (→ status=todo)
                       | "redirect" (→ status=doing so the droid picks up
                       clarified requirements).
            notes:    Optional human comment appended to task description.

        Returns:
            JSON of the updated task.
        """
        try:
            if decision not in VALID_DECISIONS:
                return MCPErrorFormatter.format_error(
                    "approve_task",
                    f"decision must be one of {VALID_DECISIONS}",
                )

            status_by_decision = {"approve": "done", "reject": "todo", "redirect": "doing"}
            patch: dict = {"status": status_by_decision[decision]}
            if notes:
                patch["review_notes"] = notes  # UI + backend can surface this

            api = get_api_url()
            async with httpx.AsyncClient(timeout=get_default_timeout()) as client:
                r = await client.put(f"{api}/api/tasks/{task_id}", json=patch)
                r.raise_for_status()
                return json.dumps(r.json())
        except httpx.HTTPStatusError as e:
            return MCPErrorFormatter.from_http_error("approve_task", e)
        except Exception as e:
            logger.exception("approve_task failed")
            return MCPErrorFormatter.format_error("approve_task", str(e))

    @mcp.tool()
    async def assign_droid(
        ctx: Context,
        task_id: str,
        persona: str,
    ) -> str:
        """
        Route a task to a droid by setting its assignee field.

        Args:
            task_id: UUID of the task.
            persona: droid identity — e.g. "kio-dev", "kio-qa", "kio-analyst".
                     The kyros-agents droid runner polls tasks WHERE assignee
                     LIKE 'kio-%' AND status='todo' and invokes the matching
                     persona via bmad-mcp.

        Returns:
            JSON of the updated task.
        """
        try:
            if not persona or not persona.strip():
                return MCPErrorFormatter.format_error(
                    "assign_droid", "persona is required"
                )
            api = get_api_url()
            patch = {"assignee": persona.strip()}
            async with httpx.AsyncClient(timeout=get_default_timeout()) as client:
                r = await client.put(f"{api}/api/tasks/{task_id}", json=patch)
                r.raise_for_status()
                return json.dumps(r.json())
        except httpx.HTTPStatusError as e:
            return MCPErrorFormatter.from_http_error("assign_droid", e)
        except Exception as e:
            logger.exception("assign_droid failed")
            return MCPErrorFormatter.format_error("assign_droid", str(e))

    logger.info("✓ Droid factory tools registered (4 tools)")
