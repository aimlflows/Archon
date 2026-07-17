/**
 * TanStack Query hook for polling workflow_runs.
 * Refetches every 5s so the Droid Lanes view feels live.
 */

import { useQuery } from "@tanstack/react-query";
import { workflowRunService } from "../services/workflowRunService";
import type { WorkflowRunFilters } from "../types/workflowRun";

export function useWorkflowRuns(filters: WorkflowRunFilters = {}) {
  return useQuery({
    queryKey: ["workflow-runs", filters],
    queryFn: () => workflowRunService.list(filters),
    refetchInterval: 5000, // live-ish view
    staleTime: 1000,
  });
}

export function useActiveDroids(projectId?: string) {
  return useWorkflowRuns({
    state: "running",
    project_id: projectId,
    limit: 100,
  });
}

export function useRecentRuns(projectId?: string) {
  return useWorkflowRuns({
    project_id: projectId,
    limit: 25,
  });
}
