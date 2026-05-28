"""
Sprint Service Module for KYROS Agile PM

Provides CRUD operations for sprints with velocity tracking.
"""

from datetime import datetime
from typing import Any

from src.server.utils import get_supabase_client
from ...config.logfire_config import get_logger

logger = get_logger(__name__)


class SprintService:
    """Service class for sprint operations"""

    def __init__(self, supabase_client=None):
        """Initialize with optional supabase client"""
        self.supabase_client = supabase_client or get_supabase_client()

    def create_sprint(
        self,
        project_id: str,
        name: str,
        goal: str = "",
        start_date: str | None = None,
        end_date: str | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        Create a new sprint.

        Args:
            project_id: Project UUID
            name: Sprint name (e.g., "Sprint 5")
            goal: Sprint goal/objective
            start_date: Sprint start date (ISO format)
            end_date: Sprint end date (ISO format)

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            if not name or not name.strip():
                return False, {"error": "Sprint name is required"}

            sprint_data = {
                "project_id": project_id,
                "name": name.strip(),
                "goal": goal or "",
                "start_date": start_date,
                "end_date": end_date,
                "state": "future",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            response = self.supabase_client.table("archon_sprints").insert(sprint_data).execute()

            if not response.data:
                return False, {"error": "Failed to create sprint"}

            sprint = response.data[0]
            logger.info(f"Sprint created: {sprint['id'][:8]} - {name}")

            return True, {"sprint": sprint}

        except Exception as e:
            logger.error(f"Error creating sprint: {e}")
            return False, {"error": str(e)}

    def list_sprints(self, project_id: str) -> tuple[bool, dict[str, Any]]:
        """
        List sprints for a project with progress stats.

        Returns sprints ordered: active first, then future, then closed.
        """
        try:
            # Use v_sprint_summary view for progress stats
            response = (
                self.supabase_client.table("v_sprint_summary")
                .select("*")
                .eq("project_id", project_id)
                .execute()
            )

            # Sort: active first, then future, then closed
            sprints = response.data or []
            state_order = {"active": 0, "future": 1, "closed": 2}
            sprints.sort(key=lambda s: (state_order.get(s.get("state", "future"), 1), s.get("start_date") or ""))

            return True, {"sprints": sprints, "count": len(sprints)}

        except Exception as e:
            logger.error(f"Error listing sprints: {e}")
            return False, {"error": str(e)}

    def get_sprint(self, sprint_id: str) -> tuple[bool, dict[str, Any]]:
        """Get a single sprint by ID with progress stats."""
        try:
            response = (
                self.supabase_client.table("v_sprint_summary")
                .select("*")
                .eq("id", sprint_id)
                .execute()
            )

            if not response.data:
                return False, {"error": f"Sprint '{sprint_id}' not found"}

            return True, {"sprint": response.data[0]}

        except Exception as e:
            logger.error(f"Error getting sprint: {e}")
            return False, {"error": str(e)}

    def get_active_sprint(self, project_id: str) -> tuple[bool, dict[str, Any]]:
        """Get the currently active sprint for a project."""
        try:
            response = (
                self.supabase_client.table("v_sprint_summary")
                .select("*")
                .eq("project_id", project_id)
                .eq("state", "active")
                .execute()
            )

            if not response.data:
                return True, {"sprint": None, "message": "No active sprint"}

            return True, {"sprint": response.data[0]}

        except Exception as e:
            logger.error(f"Error getting active sprint: {e}")
            return False, {"error": str(e)}

    def start_sprint(self, sprint_id: str) -> tuple[bool, dict[str, Any]]:
        """
        Activate a sprint.
        - Closes any currently active sprint in the same project
        - Sets start_date if not already set

        Args:
            sprint_id: Sprint UUID

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Get the sprint
            success, result = self.get_sprint(sprint_id)
            if not success:
                return success, result

            sprint = result["sprint"]
            project_id = sprint["project_id"]

            if sprint["state"] == "active":
                return False, {"error": "Sprint is already active"}

            if sprint["state"] == "closed":
                return False, {"error": "Cannot reactivate a closed sprint"}

            # Close any currently active sprint
            self.supabase_client.table("archon_sprints").update({
                "state": "closed",
                "updated_at": datetime.now().isoformat()
            }).eq("project_id", project_id).eq("state", "active").execute()

            # Activate this sprint
            update_data = {
                "state": "active",
                "updated_at": datetime.now().isoformat()
            }

            # Set start_date if not already set
            if not sprint.get("start_date"):
                update_data["start_date"] = datetime.now().date().isoformat()

            response = (
                self.supabase_client.table("archon_sprints")
                .update(update_data)
                .eq("id", sprint_id)
                .execute()
            )

            if not response.data:
                return False, {"error": "Failed to start sprint"}

            logger.info(f"Sprint started: {sprint['name']}")
            return True, {"sprint": response.data[0]}

        except Exception as e:
            logger.error(f"Error starting sprint: {e}")
            return False, {"error": str(e)}

    def close_sprint(self, sprint_id: str) -> tuple[bool, dict[str, Any]]:
        """
        Close a sprint and calculate velocity.

        Velocity = sum of story points for completed tasks.

        Returns summary including incomplete task count.
        """
        try:
            # Get sprint with summary stats
            success, result = self.get_sprint(sprint_id)
            if not success:
                return success, result

            sprint = result["sprint"]

            if sprint["state"] == "closed":
                return False, {"error": "Sprint is already closed"}

            # Velocity = completed points (from view)
            velocity = sprint.get("completed_points") or 0
            total_tasks = sprint.get("total_tasks") or 0
            completed_tasks = sprint.get("completed_tasks") or 0
            incomplete_tasks = total_tasks - completed_tasks

            # Close sprint
            update_data = {
                "state": "closed",
                "velocity": velocity,
                "updated_at": datetime.now().isoformat()
            }

            # Set end_date if not already set
            if not sprint.get("end_date"):
                update_data["end_date"] = datetime.now().date().isoformat()

            response = (
                self.supabase_client.table("archon_sprints")
                .update(update_data)
                .eq("id", sprint_id)
                .execute()
            )

            if not response.data:
                return False, {"error": "Failed to close sprint"}

            logger.info(f"Sprint closed: {sprint['name']} (velocity: {velocity})")

            return True, {
                "sprint": response.data[0],
                "summary": {
                    "velocity": velocity,
                    "total_tasks": total_tasks,
                    "completed_tasks": completed_tasks,
                    "incomplete_tasks": incomplete_tasks
                }
            }

        except Exception as e:
            logger.error(f"Error closing sprint: {e}")
            return False, {"error": str(e)}

    def update_sprint(
        self,
        sprint_id: str,
        name: str | None = None,
        goal: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """Update sprint details."""
        try:
            update_data = {"updated_at": datetime.now().isoformat()}

            if name is not None:
                update_data["name"] = name.strip()
            if goal is not None:
                update_data["goal"] = goal
            if start_date is not None:
                update_data["start_date"] = start_date
            if end_date is not None:
                update_data["end_date"] = end_date

            if len(update_data) == 1:  # Only updated_at
                return False, {"error": "No fields to update"}

            response = (
                self.supabase_client.table("archon_sprints")
                .update(update_data)
                .eq("id", sprint_id)
                .execute()
            )

            if not response.data:
                return False, {"error": f"Sprint '{sprint_id}' not found"}

            logger.info(f"Sprint updated: {sprint_id}")
            return True, {"sprint": response.data[0]}

        except Exception as e:
            logger.error(f"Error updating sprint: {e}")
            return False, {"error": str(e)}

    def assign_task_to_sprint(
        self,
        task_id: str,
        sprint_id: str | None
    ) -> tuple[bool, dict[str, Any]]:
        """
        Assign or unassign a task to a sprint.

        Args:
            task_id: Task UUID
            sprint_id: Sprint UUID or None to unassign

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Verify sprint exists if assigning
            if sprint_id:
                success, result = self.get_sprint(sprint_id)
                if not success:
                    return success, result

            # Update task
            response = (
                self.supabase_client.table("archon_tasks")
                .update({
                    "sprint_id": sprint_id,
                    "updated_at": datetime.now().isoformat()
                })
                .eq("id", task_id)
                .execute()
            )

            if not response.data:
                return False, {"error": f"Task '{task_id}' not found"}

            action = "assigned to sprint" if sprint_id else "unassigned from sprint"
            logger.info(f"Task {task_id[:8]} {action}")

            return True, {"task": response.data[0]}

        except Exception as e:
            logger.error(f"Error assigning task to sprint: {e}")
            return False, {"error": str(e)}

    def get_sprint_tasks(self, sprint_id: str) -> tuple[bool, dict[str, Any]]:
        """Get all tasks assigned to a sprint."""
        try:
            response = (
                self.supabase_client.table("archon_tasks")
                .select("*")
                .eq("sprint_id", sprint_id)
                .order("created_at")
                .execute()
            )

            return True, {
                "sprint_id": sprint_id,
                "tasks": response.data or [],
                "count": len(response.data or [])
            }

        except Exception as e:
            logger.error(f"Error getting sprint tasks: {e}")
            return False, {"error": str(e)}
