"""
Epic Service Module for KYROS Agile PM

Provides CRUD operations for epics with progress tracking and UAT sign-off workflow.
"""

from datetime import datetime
from typing import Any

from src.server.utils import get_supabase_client
from ...config.logfire_config import get_logger

logger = get_logger(__name__)


class EpicService:
    """Service class for epic operations"""

    def __init__(self, supabase_client=None):
        """Initialize with optional supabase client"""
        self.supabase_client = supabase_client or get_supabase_client()

    def create_epic(
        self,
        project_id: str,
        title: str,
        description: str = "",
        acceptance_criteria: str | None = None,
        target_date: str | None = None,
        priority: str = "medium"
    ) -> tuple[bool, dict[str, Any]]:
        """
        Create a new epic.

        Args:
            project_id: Project UUID
            title: Epic title
            description: Epic description
            acceptance_criteria: Definition of done (Gherkin format)
            target_date: Target completion date (ISO format)
            priority: Priority level (highest, high, medium, low, lowest)

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            if not title or not title.strip():
                return False, {"error": "Title is required"}

            valid_priorities = ["highest", "high", "medium", "low", "lowest"]
            if priority not in valid_priorities:
                return False, {"error": f"Invalid priority. Must be one of: {valid_priorities}"}

            epic_data = {
                "project_id": project_id,
                "title": title.strip(),
                "description": description or "",
                "acceptance_criteria": acceptance_criteria,
                "target_date": target_date,
                "priority": priority,
                "status": "open",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            response = self.supabase_client.table("archon_epics").insert(epic_data).execute()

            if not response.data:
                return False, {"error": "Failed to create epic"}

            epic = response.data[0]
            logger.info(f"Epic created: {epic.get('key') or epic['id'][:8]}")

            return True, {"epic": epic}

        except Exception as e:
            logger.error(f"Error creating epic: {e}")
            return False, {"error": str(e)}

    def list_epics(
        self,
        project_id: str,
        status: str | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        List epics for a project with progress stats.

        Args:
            project_id: Project UUID
            status: Optional filter (open, in_progress, testing, done, cancelled)

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Use v_epic_summary view for progress stats
            query = self.supabase_client.table("v_epic_summary").select("*").eq("project_id", project_id)

            if status:
                query = query.eq("status", status)

            response = query.order("created_at", desc=True).execute()

            return True, {"epics": response.data or [], "count": len(response.data or [])}

        except Exception as e:
            logger.error(f"Error listing epics: {e}")
            return False, {"error": str(e)}

    def get_epic(self, epic_id: str) -> tuple[bool, dict[str, Any]]:
        """Get a single epic by ID or key with progress stats."""
        try:
            # Try to get from summary view first (has progress stats)
            response = (
                self.supabase_client.table("v_epic_summary")
                .select("*")
                .or_(f"id.eq.{epic_id},key.eq.{epic_id}")
                .execute()
            )

            if not response.data:
                return False, {"error": f"Epic '{epic_id}' not found"}

            return True, {"epic": response.data[0]}

        except Exception as e:
            logger.error(f"Error getting epic: {e}")
            return False, {"error": str(e)}

    def update_epic(
        self,
        epic_id: str,
        title: str | None = None,
        description: str | None = None,
        acceptance_criteria: str | None = None,
        target_date: str | None = None,
        priority: str | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """Update epic details (not status - use update_status for that)."""
        try:
            update_data = {"updated_at": datetime.now().isoformat()}

            if title is not None:
                update_data["title"] = title.strip()
            if description is not None:
                update_data["description"] = description
            if acceptance_criteria is not None:
                update_data["acceptance_criteria"] = acceptance_criteria
            if target_date is not None:
                update_data["target_date"] = target_date
            if priority is not None:
                valid_priorities = ["highest", "high", "medium", "low", "lowest"]
                if priority not in valid_priorities:
                    return False, {"error": f"Invalid priority. Must be one of: {valid_priorities}"}
                update_data["priority"] = priority

            if len(update_data) == 1:  # Only updated_at
                return False, {"error": "No fields to update"}

            # Support both UUID and key
            response = (
                self.supabase_client.table("archon_epics")
                .update(update_data)
                .or_(f"id.eq.{epic_id},key.eq.{epic_id}")
                .execute()
            )

            if not response.data:
                return False, {"error": f"Epic '{epic_id}' not found"}

            logger.info(f"Epic updated: {epic_id}")
            return True, {"epic": response.data[0]}

        except Exception as e:
            logger.error(f"Error updating epic: {e}")
            return False, {"error": str(e)}

    def update_status(
        self,
        epic_id: str,
        new_status: str,
        uat_approved: bool = False
    ) -> tuple[bool, dict[str, Any]]:
        """
        Update epic status with validation rules.

        - Moving to 'done' requires uat_approved=True (GK sign-off)
        - Moving to 'done' requires epic to be in 'testing' status

        Args:
            epic_id: Epic UUID or key
            new_status: New status (open, in_progress, testing, done, cancelled)
            uat_approved: Required True for done status

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            valid_statuses = ["open", "in_progress", "testing", "done", "cancelled"]
            if new_status not in valid_statuses:
                return False, {"error": f"Invalid status. Must be one of: {valid_statuses}"}

            # Get current epic
            success, result = self.get_epic(epic_id)
            if not success:
                return success, result

            epic = result["epic"]
            old_status = epic["status"]

            # Validation: done requires UAT sign-off
            if new_status == "done" and not uat_approved:
                return False, {"error": "Cannot move to 'done' without UAT sign-off. Set uat_approved=True"}

            # Validation: done requires testing status
            if new_status == "done" and old_status != "testing":
                return False, {"error": f"Epic must be in 'testing' status before marking as done. Current: {old_status}"}

            # Update status
            update_data = {
                "status": new_status,
                "updated_at": datetime.now().isoformat()
            }

            response = (
                self.supabase_client.table("archon_epics")
                .update(update_data)
                .eq("id", epic["id"])
                .execute()
            )

            if not response.data:
                return False, {"error": "Failed to update epic status"}

            # Log to changelog
            try:
                self.supabase_client.table("archon_changelog").insert({
                    "entity_type": "epic",
                    "entity_id": epic["id"],
                    "entity_key": epic.get("key"),
                    "field_changed": "status",
                    "old_value": old_status,
                    "new_value": new_status,
                    "change_type": "status_change",
                    "changed_by": "gk",
                    "created_at": datetime.now().isoformat()
                }).execute()
            except Exception as log_err:
                logger.warning(f"Failed to log changelog: {log_err}")

            logger.info(f"Epic status updated: {epic_id} {old_status} -> {new_status}")
            return True, {
                "epic": response.data[0],
                "old_status": old_status,
                "new_status": new_status
            }

        except Exception as e:
            logger.error(f"Error updating epic status: {e}")
            return False, {"error": str(e)}

    def get_tasks(self, epic_id: str) -> tuple[bool, dict[str, Any]]:
        """Get all tasks for an epic."""
        try:
            # Get epic first to get the actual UUID
            success, result = self.get_epic(epic_id)
            if not success:
                return success, result

            epic = result["epic"]

            response = (
                self.supabase_client.table("archon_tasks")
                .select("*")
                .eq("epic_id", epic["id"])
                .order("created_at")
                .execute()
            )

            return True, {
                "epic_id": epic["id"],
                "epic_key": epic.get("key"),
                "tasks": response.data or [],
                "count": len(response.data or [])
            }

        except Exception as e:
            logger.error(f"Error getting epic tasks: {e}")
            return False, {"error": str(e)}

    def get_execution_order(
        self,
        epic_id: str | None = None,
        project_id: str | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        Get recommended task execution order based on dependencies.
        Uses the get_execution_order() database function.

        Args:
            epic_id: Optional epic filter
            project_id: Optional project filter

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Call the database function
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

    def cancel_epic(self, epic_id: str, reason: str = "") -> tuple[bool, dict[str, Any]]:
        """Cancel an epic with optional reason."""
        try:
            success, result = self.update_status(epic_id, "cancelled")
            if not success:
                return success, result

            # Log cancellation reason if provided
            if reason:
                try:
                    self.supabase_client.table("archon_changelog").insert({
                        "entity_type": "epic",
                        "entity_id": result["epic"]["id"],
                        "entity_key": result["epic"].get("key"),
                        "field_changed": "status",
                        "old_value": result["old_status"],
                        "new_value": "cancelled",
                        "change_type": "cancellation",
                        "changed_by": "gk",
                        "reason": reason,
                        "created_at": datetime.now().isoformat()
                    }).execute()
                except Exception as log_err:
                    logger.warning(f"Failed to log cancellation reason: {log_err}")

            return True, result

        except Exception as e:
            logger.error(f"Error cancelling epic: {e}")
            return False, {"error": str(e)}
