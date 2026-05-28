"""
Task Dependency Service Module for KYROS Agile PM

Provides operations for task dependencies, blocking/unblocking, and workflow queries.
"""

from datetime import datetime
from typing import Any

from src.server.utils import get_supabase_client
from ...config.logfire_config import get_logger

logger = get_logger(__name__)


class DependencyService:
    """Service class for task dependency operations"""

    def __init__(self, supabase_client=None):
        """Initialize with optional supabase client"""
        self.supabase_client = supabase_client or get_supabase_client()

    def add_dependency(
        self,
        task_id: str,
        blocked_by_task_id: str,
        dependency_type: str = "blocks"
    ) -> tuple[bool, dict[str, Any]]:
        """
        Add a dependency between two tasks.

        Args:
            task_id: The task that will be blocked
            blocked_by_task_id: The task that blocks it
            dependency_type: Type (blocks, relates_to, duplicates)

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            if task_id == blocked_by_task_id:
                return False, {"error": "A task cannot depend on itself"}

            valid_types = ["blocks", "relates_to", "duplicates"]
            if dependency_type not in valid_types:
                return False, {"error": f"Invalid dependency_type. Must be one of: {valid_types}"}

            # Check for circular dependency
            if dependency_type == "blocks":
                is_circular, cycle_path = self._check_circular_dependency(task_id, blocked_by_task_id)
                if is_circular:
                    return False, {
                        "error": f"Circular dependency detected: {' -> '.join(cycle_path)}"
                    }

            # Check if dependency already exists
            existing = (
                self.supabase_client.table("archon_task_dependencies")
                .select("id")
                .eq("task_id", task_id)
                .eq("blocked_by_task_id", blocked_by_task_id)
                .execute()
            )

            if existing.data:
                return False, {"error": "Dependency already exists"}

            # Create dependency
            dep_data = {
                "task_id": task_id,
                "blocked_by_task_id": blocked_by_task_id,
                "dependency_type": dependency_type,
                "created_at": datetime.now().isoformat()
            }

            response = self.supabase_client.table("archon_task_dependencies").insert(dep_data).execute()

            if not response.data:
                return False, {"error": "Failed to create dependency"}

            logger.info(f"Dependency created: {task_id[:8]} blocked by {blocked_by_task_id[:8]}")
            return True, {"dependency": response.data[0]}

        except Exception as e:
            logger.error(f"Error creating dependency: {e}")
            return False, {"error": str(e)}

    def _check_circular_dependency(
        self,
        task_id: str,
        blocked_by_task_id: str
    ) -> tuple[bool, list[str]]:
        """Check if adding this dependency would create a cycle."""
        try:
            # Get task titles for readable error message
            task_response = self.supabase_client.table("archon_tasks").select("id, title").in_("id", [task_id, blocked_by_task_id]).execute()
            task_titles = {t["id"]: t["title"] for t in task_response.data or []}

            # DFS to check for cycle
            visited = set()
            path = [task_titles.get(task_id, task_id[:8])]

            def has_path_to(current_id: str, target_id: str) -> bool:
                if current_id == target_id:
                    return True
                if current_id in visited:
                    return False
                visited.add(current_id)

                deps = (
                    self.supabase_client.table("archon_task_dependencies")
                    .select("blocked_by_task_id")
                    .eq("task_id", current_id)
                    .eq("dependency_type", "blocks")
                    .execute()
                )

                for dep in deps.data or []:
                    blocker_id = dep["blocked_by_task_id"]
                    blocker_title = task_titles.get(blocker_id, blocker_id[:8])
                    path.append(blocker_title)
                    if has_path_to(blocker_id, target_id):
                        return True
                    path.pop()

                return False

            # Check if blocked_by_task_id can reach task_id (would create cycle)
            if has_path_to(blocked_by_task_id, task_id):
                path.insert(0, task_titles.get(blocked_by_task_id, blocked_by_task_id[:8]))
                return True, path

            return False, []

        except Exception as e:
            logger.warning(f"Error checking circular dependency: {e}")
            return False, []

    def remove_dependency(self, task_id: str, blocked_by_task_id: str) -> tuple[bool, dict[str, Any]]:
        """Remove a dependency between two tasks."""
        try:
            response = (
                self.supabase_client.table("archon_task_dependencies")
                .delete()
                .eq("task_id", task_id)
                .eq("blocked_by_task_id", blocked_by_task_id)
                .execute()
            )

            if not response.data:
                return False, {"error": "Dependency not found"}

            logger.info(f"Dependency removed: {task_id[:8]} no longer blocked by {blocked_by_task_id[:8]}")
            return True, {"removed": True}

        except Exception as e:
            logger.error(f"Error removing dependency: {e}")
            return False, {"error": str(e)}

    def get_task_blockers(self, task_id: str) -> tuple[bool, dict[str, Any]]:
        """Get all tasks that block the given task."""
        try:
            response = (
                self.supabase_client.table("archon_task_dependencies")
                .select("*, blocker:blocked_by_task_id(id, title, status, key)")
                .eq("task_id", task_id)
                .eq("dependency_type", "blocks")
                .execute()
            )

            blockers = []
            for dep in response.data or []:
                blocker = dep.get("blocker", {})
                if blocker:
                    blockers.append({
                        "id": blocker.get("id"),
                        "title": blocker.get("title"),
                        "status": blocker.get("status"),
                        "key": blocker.get("key"),
                        "is_done": blocker.get("status") == "done"
                    })

            return True, {
                "task_id": task_id,
                "blockers": blockers,
                "count": len(blockers),
                "all_resolved": all(b["is_done"] for b in blockers) if blockers else True
            }

        except Exception as e:
            logger.error(f"Error getting task blockers: {e}")
            return False, {"error": str(e)}

    def get_task_dependents(self, task_id: str) -> tuple[bool, dict[str, Any]]:
        """Get all tasks that are blocked by the given task."""
        try:
            response = (
                self.supabase_client.table("archon_task_dependencies")
                .select("*, dependent:task_id(id, title, status, key)")
                .eq("blocked_by_task_id", task_id)
                .eq("dependency_type", "blocks")
                .execute()
            )

            dependents = []
            for dep in response.data or []:
                dependent = dep.get("dependent", {})
                if dependent:
                    dependents.append({
                        "id": dependent.get("id"),
                        "title": dependent.get("title"),
                        "status": dependent.get("status"),
                        "key": dependent.get("key")
                    })

            return True, {
                "task_id": task_id,
                "dependents": dependents,
                "count": len(dependents)
            }

        except Exception as e:
            logger.error(f"Error getting task dependents: {e}")
            return False, {"error": str(e)}

    def get_unblocked_tasks(
        self,
        project_id: str,
        epic_id: str | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """Get tasks that have no unresolved blocking dependencies."""
        try:
            # Use the v_unblocked_tasks view
            query = (
                self.supabase_client.table("v_unblocked_tasks")
                .select("*")
                .eq("project_id", project_id)
            )

            if epic_id:
                query = query.eq("epic_id", epic_id)

            response = query.execute()

            return True, {
                "tasks": response.data or [],
                "count": len(response.data or [])
            }

        except Exception as e:
            logger.error(f"Error getting unblocked tasks: {e}")
            return False, {"error": str(e)}

    def get_execution_order(
        self,
        project_id: str | None = None,
        epic_id: str | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """Get tasks in dependency-aware execution order."""
        try:
            response = self.supabase_client.rpc(
                "get_execution_order",
                {"p_epic_id": epic_id, "p_project_id": project_id}
            ).execute()

            return True, {
                "execution_order": response.data or [],
                "count": len(response.data or [])
            }

        except Exception as e:
            logger.error(f"Error getting execution order: {e}")
            return False, {"error": str(e)}

    def block_task(
        self,
        task_id: str,
        reason: str
    ) -> tuple[bool, dict[str, Any]]:
        """Block a task with a reason."""
        try:
            response = (
                self.supabase_client.table("archon_tasks")
                .update({
                    "status": "blocked",
                    "block_reason": reason,
                    "blocked_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                })
                .eq("id", task_id)
                .execute()
            )

            if not response.data:
                return False, {"error": f"Task '{task_id}' not found"}

            task = response.data[0]

            # Log to changelog
            try:
                self.supabase_client.table("archon_changelog").insert({
                    "entity_type": "task",
                    "entity_id": task_id,
                    "entity_key": task.get("key"),
                    "field_changed": "status",
                    "old_value": task.get("status"),
                    "new_value": "blocked",
                    "change_type": "blocked",
                    "changed_by": "system",
                    "reason": reason,
                    "created_at": datetime.now().isoformat()
                }).execute()
            except Exception as log_err:
                logger.warning(f"Failed to log changelog: {log_err}")

            logger.info(f"Task blocked: {task_id[:8]} - {reason}")
            return True, {"task": task}

        except Exception as e:
            logger.error(f"Error blocking task: {e}")
            return False, {"error": str(e)}

    def unblock_task(
        self,
        task_id: str,
        resolution: str = ""
    ) -> tuple[bool, dict[str, Any]]:
        """Unblock a task, returning it to its previous status or todo."""
        try:
            # Get current task to check status
            current = (
                self.supabase_client.table("archon_tasks")
                .select("*")
                .eq("id", task_id)
                .execute()
            )

            if not current.data:
                return False, {"error": f"Task '{task_id}' not found"}

            task = current.data[0]
            if task["status"] != "blocked":
                return False, {"error": f"Task is not blocked. Current status: {task['status']}"}

            # Determine new status (default to todo)
            new_status = "todo"

            response = (
                self.supabase_client.table("archon_tasks")
                .update({
                    "status": new_status,
                    "block_reason": None,
                    "blocked_at": None,
                    "updated_at": datetime.now().isoformat()
                })
                .eq("id", task_id)
                .execute()
            )

            if not response.data:
                return False, {"error": "Failed to unblock task"}

            updated_task = response.data[0]

            # Log to changelog
            try:
                self.supabase_client.table("archon_changelog").insert({
                    "entity_type": "task",
                    "entity_id": task_id,
                    "entity_key": task.get("key"),
                    "field_changed": "status",
                    "old_value": "blocked",
                    "new_value": new_status,
                    "change_type": "unblocked",
                    "changed_by": "system",
                    "reason": resolution,
                    "created_at": datetime.now().isoformat()
                }).execute()
            except Exception as log_err:
                logger.warning(f"Failed to log changelog: {log_err}")

            logger.info(f"Task unblocked: {task_id[:8]} -> {new_status}")
            return True, {"task": updated_task, "resolution": resolution}

        except Exception as e:
            logger.error(f"Error unblocking task: {e}")
            return False, {"error": str(e)}

    def get_tasks_at_risk(self, project_id: str) -> tuple[bool, dict[str, Any]]:
        """Get tasks at risk of auto-blocking based on inactivity threshold."""
        try:
            # Use the v_tasks_at_risk view
            response = (
                self.supabase_client.table("v_tasks_at_risk")
                .select("*")
                .eq("project_id", project_id)
                .execute()
            )

            return True, {
                "tasks": response.data or [],
                "count": len(response.data or [])
            }

        except Exception as e:
            logger.error(f"Error getting tasks at risk: {e}")
            return False, {"error": str(e)}

    def get_changelog(
        self,
        entity_id: str,
        entity_type: str = "task",
        limit: int = 20
    ) -> tuple[bool, dict[str, Any]]:
        """Get changelog/audit trail for an entity."""
        try:
            response = (
                self.supabase_client.table("archon_changelog")
                .select("*")
                .eq("entity_id", entity_id)
                .eq("entity_type", entity_type)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            return True, {
                "entity_id": entity_id,
                "entity_type": entity_type,
                "changelog": response.data or [],
                "count": len(response.data or [])
            }

        except Exception as e:
            logger.error(f"Error getting changelog: {e}")
            return False, {"error": str(e)}
