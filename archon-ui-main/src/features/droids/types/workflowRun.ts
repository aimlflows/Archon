/**
 * Droid factory workflow run types — mirrors the Python
 * WorkflowRunService schema (see archon_workflow_runs migration 012).
 */

export type WorkflowRunState =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface WorkflowRun {
  id: string;
  workflow_name: string;
  persona: string | null;
  project_id: string | null;
  sprint_id: string | null;
  task_id: string | null;
  state: WorkflowRunState;
  invocation_input: Record<string, unknown>;
  outputs: Record<string, unknown>;
  outcomes: Record<string, unknown>;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ListWorkflowRunsResponse {
  runs: WorkflowRun[];
  count: number;
}

export interface CreateWorkflowRunRequest {
  workflow_name: string;
  project_id?: string;
  sprint_id?: string;
  task_id?: string;
  persona?: string;
  invocation_input?: Record<string, unknown>;
}

export interface WorkflowRunFilters {
  project_id?: string;
  state?: WorkflowRunState;
  persona?: string;
  limit?: number;
}
