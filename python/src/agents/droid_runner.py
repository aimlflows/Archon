"""
Droid Job Runner — NETRA Phase 5B Slice 1 (2026-07-17).

Background poll loop that turns Archon `archon_tasks` rows into
actual droid work. This is the "24/7 droid execution" side of the
factory: user drags a card to `todo` in Archon UI (or Kio-Orchestrator
creates one via kio_orchestrate), assigns it to a persona like
`kio-dev`, and this runner picks it up.

Lifecycle per task:
    1. Discover: GET /api/tasks?filter_by=status&filter_value=todo
       (client-side filter for assignee LIKE 'kio-%')
    2. Register: POST /api/workflow-runs (state=pending)
    3. Start:    POST /api/workflow-runs/{id}/start (state=running)
                 + PUT  /api/tasks/{tid}  status=doing
    4. Invoke:   HTTP MCP session against bmad-mcp:
                 initialize → notifications/initialized →
                 tools/call kio_invoke_agent(agent_id, task)
    5. Persist:  POST /api/workflow-runs/{id}/complete
                 with {"droid_output": <persona-shaped prompt>, ...}
                 + PUT /api/tasks/{tid} status=review
                   (or `done` if autonomy_level='autonomous')

Configuration is env-driven; sensible in-cluster defaults let the
container "just work" behind the same Service names other kyros-*
pods use.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ─── Config (env-driven; in-cluster defaults) ────────────────────────

ARCHON_API_URL = os.getenv(
    "ARCHON_API_URL",
    # Same-ns Service name; when scaled up the deploy sees kyros-api directly
    "http://kyros-api:8181",
)
BMAD_MCP_URL = os.getenv(
    "BMAD_MCP_URL",
    "http://bmad-mcp.netra-core-uat.svc.cluster.local:8849/mcp",
)
POLL_INTERVAL_SECONDS = int(os.getenv("DROID_RUNNER_POLL_SECONDS", "15"))
DROID_ASSIGNEE_PREFIX = "kio-"
HTTP_TIMEOUT = 60.0

_running_task: asyncio.Task | None = None


# ─── HTTP MCP session against bmad-mcp ───────────────────────────────

async def _bmad_invoke_agent(persona: str, task_prompt: str) -> dict[str, Any]:
    """Run a full MCP session against bmad-mcp: initialize → tools/call
    kio_invoke_agent. Returns {'ok': bool, 'output': str, 'raw': dict}."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        # ─ initialize ─
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "kyros-droid-runner", "version": "1"},
            },
        }
        init_resp = await client.post(
            BMAD_MCP_URL,
            json=init_payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        init_resp.raise_for_status()
        session_id = init_resp.headers.get("mcp-session-id", "")
        if not session_id:
            return {"ok": False, "output": "no session id from bmad-mcp", "raw": {}}

        headers = {
            "mcp-session-id": session_id,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        # ─ initialized notification (required) ─
        await client.post(
            BMAD_MCP_URL,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=headers,
        )
        # ─ tools/call kio_invoke_agent ─
        call_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "kio_invoke_agent",
                "arguments": {"agent_id": persona, "task": task_prompt},
            },
        }
        call_resp = await client.post(BMAD_MCP_URL, json=call_payload, headers=headers)
        call_resp.raise_for_status()
        raw_text = call_resp.text

        # Parse SSE response (bmad-mcp emits "event: message\ndata: {...}")
        output_text = ""
        for line in raw_text.splitlines():
            if line.startswith("data: "):
                try:
                    parsed = json.loads(line[len("data: ") :])
                    content = parsed.get("result", {}).get("content", [])
                    for chunk in content:
                        if chunk.get("type") == "text":
                            output_text += chunk.get("text", "")
                except json.JSONDecodeError:
                    continue
        return {"ok": bool(output_text), "output": output_text, "raw": {"session_id": session_id}}


# ─── Archon REST helpers ─────────────────────────────────────────────

async def _archon_list_todo_tasks(client: httpx.AsyncClient) -> list[dict]:
    r = await client.get(
        f"{ARCHON_API_URL}/api/tasks",
        params={"filter_by": "status", "filter_value": "todo", "per_page": 50},
    )
    r.raise_for_status()
    payload = r.json()
    tasks = payload.get("tasks") if isinstance(payload, dict) else payload
    return tasks or []


async def _archon_update_task(client: httpx.AsyncClient, task_id: str, patch: dict) -> None:
    await client.put(f"{ARCHON_API_URL}/api/tasks/{task_id}", json=patch)


async def _archon_workflow_run_create(
    client: httpx.AsyncClient, task: dict, persona: str
) -> str | None:
    body = {
        "workflow_name": "droid-invoke",
        "persona": persona,
        "project_id": task.get("project_id"),
        "task_id": task.get("id"),
        "invocation_input": {
            "task_id": task.get("id"),
            "task_title": task.get("title"),
            "task_description": task.get("description"),
            "persona": persona,
            "runner_started_at": datetime.now().isoformat(),
        },
    }
    r = await client.post(f"{ARCHON_API_URL}/api/workflow-runs", json=body)
    if r.status_code >= 400:
        logger.warning(f"workflow_run create failed: {r.status_code} {r.text[:200]}")
        return None
    return (r.json() or {}).get("run", {}).get("id")


async def _archon_workflow_run_start(client: httpx.AsyncClient, run_id: str) -> None:
    await client.post(f"{ARCHON_API_URL}/api/workflow-runs/{run_id}/start")


async def _archon_workflow_run_complete(
    client: httpx.AsyncClient, run_id: str, outputs: dict
) -> None:
    await client.post(
        f"{ARCHON_API_URL}/api/workflow-runs/{run_id}/complete", json=outputs
    )


async def _archon_workflow_run_fail(client: httpx.AsyncClient, run_id: str, error: str) -> None:
    await client.post(
        f"{ARCHON_API_URL}/api/workflow-runs/{run_id}/fail", json={"error": error}
    )


# ─── Core lifecycle per task ─────────────────────────────────────────

async def _process_task(client: httpx.AsyncClient, task: dict) -> None:
    task_id = task.get("id")
    persona = (task.get("assignee") or "").strip()
    autonomy = (task.get("autonomy_level") or "hitl_review_required").strip()
    prompt = task.get("description") or task.get("title") or ""

    if not task_id or not persona.startswith(DROID_ASSIGNEE_PREFIX):
        return

    logger.info(f"▸ Picking up task {task_id[:8]} → persona={persona}")

    # 1. Register + start workflow run
    run_id = await _archon_workflow_run_create(client, task, persona)
    if not run_id:
        logger.error(f"Could not register workflow_run for task {task_id[:8]}")
        return
    await _archon_workflow_run_start(client, run_id)

    # 2. Transition task to doing
    await _archon_update_task(client, task_id, {"status": "doing"})

    # 3. Invoke bmad-mcp for the droid's prompt/artifact
    try:
        result = await _bmad_invoke_agent(persona, prompt)
    except Exception as e:
        logger.exception(f"bmad-mcp invocation failed for {task_id[:8]}")
        await _archon_workflow_run_fail(client, run_id, str(e))
        # Bounce task back to todo so it can be retried / reassigned
        await _archon_update_task(client, task_id, {"status": "todo"})
        return

    # 4. Persist outputs + complete the run
    await _archon_workflow_run_complete(
        client,
        run_id,
        {
            "outputs": {
                "droid_output": result.get("output", ""),
                "ok": result.get("ok", False),
                "produced_at": datetime.now().isoformat(),
            }
        },
    )

    # 5. Transition task to review (blocking HITL) or done (autonomous)
    next_status = "done" if autonomy == "autonomous" else "review"
    await _archon_update_task(client, task_id, {"status": next_status})

    logger.info(f"✓ Task {task_id[:8]} → {next_status} (workflow_run={run_id[:8]})")


# ─── Poll loop ───────────────────────────────────────────────────────

async def _tick() -> None:
    """One pass through the todo queue."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        try:
            tasks = await _archon_list_todo_tasks(client)
        except Exception as e:
            logger.warning(f"list_todo_tasks failed: {e}")
            return

        droid_tasks = [
            t for t in tasks
            if (t.get("assignee") or "").startswith(DROID_ASSIGNEE_PREFIX)
        ]
        if not droid_tasks:
            return

        logger.info(f"tick: {len(droid_tasks)} droid-assigned todo task(s)")
        for t in droid_tasks:
            try:
                await _process_task(client, t)
            except Exception as e:
                logger.exception(f"processing failed for {t.get('id','?')[:8]}: {e}")


async def _run_forever() -> None:
    logger.info(f"Droid runner starting — poll every {POLL_INTERVAL_SECONDS}s")
    logger.info(f"  Archon API: {ARCHON_API_URL}")
    logger.info(f"  bmad-mcp:   {BMAD_MCP_URL}")
    while True:
        await _tick()
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def start_background_runner() -> None:
    """Kick off the poll loop as a background task. Called from server lifespan."""
    global _running_task
    if _running_task and not _running_task.done():
        return
    loop = asyncio.get_event_loop()
    _running_task = loop.create_task(_run_forever())
    logger.info("Droid runner background task launched")


def stop_background_runner() -> None:
    global _running_task
    if _running_task and not _running_task.done():
        _running_task.cancel()
        _running_task = None


async def trigger_tick_once() -> None:
    """Manual/test trigger — one poll pass, no loop."""
    await _tick()
