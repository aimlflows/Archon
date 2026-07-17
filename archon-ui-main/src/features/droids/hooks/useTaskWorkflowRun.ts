/**
 * Hook: find the latest workflow_run for a given task_id.
 * MVP: fetches recent runs and filters client-side (backend doesn't
 * expose a task_id filter yet; add later if the poll cost matters).
 */

import { useMemo } from "react";
import { useWorkflowRuns } from "./useWorkflowRuns";
import type { WorkflowRun } from "../types/workflowRun";

export function useTaskWorkflowRun(taskId: string | null | undefined, projectId?: string) {
  const query = useWorkflowRuns({ project_id: projectId, limit: 200 });
  const run = useMemo<WorkflowRun | null>(() => {
    if (!taskId || !query.data?.runs) return null;
    const matches = query.data.runs
      .filter((r) => r.task_id === taskId)
      .sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      );
    return matches[0] ?? null;
  }, [taskId, query.data?.runs]);

  return { ...query, run };
}
