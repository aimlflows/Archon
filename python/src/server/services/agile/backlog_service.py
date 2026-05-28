"""
Backlog Service Module for KYROS Agile PM

Provides CRUD operations for backlog items with WSJF scoring and MoSCoW prioritization.
"""

from datetime import datetime
from typing import Any

from src.server.utils import get_supabase_client
from ...config.logfire_config import get_logger

logger = get_logger(__name__)


class BacklogService:
    """Service class for backlog item operations"""

    def __init__(self, supabase_client=None):
        """Initialize with optional supabase client"""
        self.supabase_client = supabase_client or get_supabase_client()

    def add_item(
        self,
        project_id: str,
        title: str,
        description: str = "",
        item_type: str = "idea"
    ) -> tuple[bool, dict[str, Any]]:
        """
        Add a new backlog item.

        Args:
            project_id: Project UUID
            title: Item title
            description: Item description
            item_type: Type (idea, feature, bug, tech_debt, spike, improvement)

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            if not title or not title.strip():
                return False, {"error": "Title is required"}

            valid_types = ["idea", "feature", "bug", "tech_debt", "spike", "improvement"]
            if item_type not in valid_types:
                return False, {"error": f"Invalid item_type. Must be one of: {valid_types}"}

            item_data = {
                "project_id": project_id,
                "title": title.strip(),
                "description": description or "",
                "item_type": item_type,
                "status": "new",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            response = self.supabase_client.table("archon_backlog_items").insert(item_data).execute()

            if not response.data:
                return False, {"error": "Failed to create backlog item"}

            item = response.data[0]
            logger.info(f"Backlog item created: {item['id'][:8]}")

            return True, {"backlog_item": item}

        except Exception as e:
            logger.error(f"Error creating backlog item: {e}")
            return False, {"error": str(e)}

    def list_items(
        self,
        project_id: str,
        status: str | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        List backlog items for a project, sorted by MoSCoW then WSJF.

        Args:
            project_id: Project UUID
            status: Optional filter (new, refined, ready, promoted, rejected)

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Use the v_backlog_prioritized view for sorted results
            query = self.supabase_client.table("v_backlog_prioritized").select("*").eq("project_id", project_id)

            if status:
                query = query.eq("status", status)

            response = query.execute()

            return True, {"items": response.data or [], "count": len(response.data or [])}

        except Exception as e:
            logger.error(f"Error listing backlog items: {e}")
            return False, {"error": str(e)}

    def get_item(self, item_id: str) -> tuple[bool, dict[str, Any]]:
        """Get a single backlog item by ID."""
        try:
            response = (
                self.supabase_client.table("archon_backlog_items")
                .select("*")
                .eq("id", item_id)
                .single()
                .execute()
            )

            if not response.data:
                return False, {"error": f"Backlog item '{item_id}' not found"}

            return True, {"backlog_item": response.data}

        except Exception as e:
            logger.error(f"Error getting backlog item: {e}")
            return False, {"error": str(e)}

    def refine_item(
        self,
        item_id: str,
        business_value: int | None = None,
        time_criticality: int | None = None,
        risk_reduction: int | None = None,
        effort_estimate: int | None = None,
        moscow: str | None = None,
        acceptance_criteria: str | None = None,
        status: str | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        Refine a backlog item with WSJF scores and MoSCoW priority.

        Args:
            item_id: Backlog item UUID
            business_value: WSJF score 0-10
            time_criticality: WSJF score 0-10
            risk_reduction: WSJF score 0-10
            effort_estimate: WSJF score 0-10 (higher = more effort)
            moscow: Priority (must, should, could, wont)
            acceptance_criteria: Definition of done
            status: New status (new, refined, ready)

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            update_data = {"updated_at": datetime.now().isoformat()}

            # WSJF scores (validate 0-10 range)
            if business_value is not None:
                if not 0 <= business_value <= 10:
                    return False, {"error": "business_value must be 0-10"}
                update_data["business_value"] = business_value

            if time_criticality is not None:
                if not 0 <= time_criticality <= 10:
                    return False, {"error": "time_criticality must be 0-10"}
                update_data["time_criticality"] = time_criticality

            if risk_reduction is not None:
                if not 0 <= risk_reduction <= 10:
                    return False, {"error": "risk_reduction must be 0-10"}
                update_data["risk_reduction"] = risk_reduction

            if effort_estimate is not None:
                if not 0 <= effort_estimate <= 10:
                    return False, {"error": "effort_estimate must be 0-10"}
                update_data["effort_estimate"] = effort_estimate

            # MoSCoW
            if moscow is not None:
                valid_moscow = ["must", "should", "could", "wont"]
                if moscow not in valid_moscow:
                    return False, {"error": f"moscow must be one of: {valid_moscow}"}
                update_data["moscow"] = moscow

            # Other fields
            if acceptance_criteria is not None:
                update_data["acceptance_criteria"] = acceptance_criteria

            if status is not None:
                valid_statuses = ["new", "refined", "ready", "promoted", "rejected"]
                if status not in valid_statuses:
                    return False, {"error": f"status must be one of: {valid_statuses}"}
                update_data["status"] = status

            if len(update_data) == 1:  # Only updated_at
                return False, {"error": "No fields to update"}

            response = (
                self.supabase_client.table("archon_backlog_items")
                .update(update_data)
                .eq("id", item_id)
                .execute()
            )

            if not response.data:
                return False, {"error": f"Backlog item '{item_id}' not found"}

            item = response.data[0]
            logger.info(f"Backlog item refined: {item_id[:8]}")

            return True, {"backlog_item": item}

        except Exception as e:
            logger.error(f"Error refining backlog item: {e}")
            return False, {"error": str(e)}

    def promote_item(
        self,
        item_id: str,
        target_type: str,
        epic_id: str | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        Promote a backlog item to an Epic or Task.
        Requires item to be in 'ready' status.

        Args:
            item_id: Backlog item UUID
            target_type: 'epic' or 'task'
            epic_id: Parent epic ID if promoting to task

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Get the backlog item
            success, result = self.get_item(item_id)
            if not success:
                return success, result

            item = result["backlog_item"]

            if item["status"] != "ready":
                return False, {"error": f"Item must be in 'ready' status to promote. Current: {item['status']}"}

            project_id = item["project_id"]

            if target_type.lower() == "epic":
                # Create epic
                epic_data = {
                    "project_id": project_id,
                    "title": item["title"],
                    "description": item.get("description", ""),
                    "acceptance_criteria": item.get("acceptance_criteria"),
                    "status": "open",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                }

                epic_response = self.supabase_client.table("archon_epics").insert(epic_data).execute()

                if not epic_response.data:
                    return False, {"error": "Failed to create epic"}

                new_epic = epic_response.data[0]

                # Update backlog item
                self.supabase_client.table("archon_backlog_items").update({
                    "status": "promoted",
                    "promoted_to_epic_id": new_epic["id"],
                    "updated_at": datetime.now().isoformat()
                }).eq("id", item_id).execute()

                logger.info(f"Backlog item promoted to epic: {new_epic['id'][:8]}")
                return True, {"epic": new_epic, "promoted_from": item_id}

            elif target_type.lower() == "task":
                # Determine issue_type based on backlog item_type
                issue_type_map = {
                    "idea": "story",
                    "feature": "story",
                    "bug": "bug",
                    "tech_debt": "task",
                    "spike": "task",
                    "improvement": "task"
                }
                issue_type = issue_type_map.get(item.get("item_type", "idea"), "task")

                # Create task
                task_data = {
                    "project_id": project_id,
                    "epic_id": epic_id,
                    "title": item["title"],
                    "description": item.get("description", ""),
                    "acceptance_criteria": item.get("acceptance_criteria"),
                    "status": "backlog",
                    "issue_type": issue_type,
                    "story_points": item.get("effort_estimate"),
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                }

                task_response = self.supabase_client.table("archon_tasks").insert(task_data).execute()

                if not task_response.data:
                    return False, {"error": "Failed to create task"}

                new_task = task_response.data[0]

                # Update backlog item
                self.supabase_client.table("archon_backlog_items").update({
                    "status": "promoted",
                    "promoted_to_task_id": new_task["id"],
                    "updated_at": datetime.now().isoformat()
                }).eq("id", item_id).execute()

                logger.info(f"Backlog item promoted to task: {new_task['id'][:8]}")
                return True, {"task": new_task, "promoted_from": item_id}

            else:
                return False, {"error": f"Invalid target_type: {target_type}. Use 'epic' or 'task'"}

        except Exception as e:
            logger.error(f"Error promoting backlog item: {e}")
            return False, {"error": str(e)}

    def reject_item(self, item_id: str, reason: str = "") -> tuple[bool, dict[str, Any]]:
        """Reject a backlog item with optional reason."""
        try:
            update_data = {
                "status": "rejected",
                "updated_at": datetime.now().isoformat()
            }

            # Store rejection reason in story_format JSON field
            if reason:
                update_data["story_format"] = {"rejection_reason": reason}

            response = (
                self.supabase_client.table("archon_backlog_items")
                .update(update_data)
                .eq("id", item_id)
                .execute()
            )

            if not response.data:
                return False, {"error": f"Backlog item '{item_id}' not found"}

            logger.info(f"Backlog item rejected: {item_id[:8]}")
            return True, {"backlog_item": response.data[0]}

        except Exception as e:
            logger.error(f"Error rejecting backlog item: {e}")
            return False, {"error": str(e)}
