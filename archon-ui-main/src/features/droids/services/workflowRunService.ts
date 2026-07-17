/**
 * Workflow run service — thin HTTP client over /api/workflow-runs.
 * Follows the existing task service pattern (callAPIWithETag → unwrap).
 */

import { callAPIWithETag } from "../../shared/api/apiClient";
import type {
  CreateWorkflowRunRequest,
  ListWorkflowRunsResponse,
  WorkflowRun,
  WorkflowRunFilters,
} from "../types/workflowRun";

const BASE = "/api/workflow-runs";

function qs(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") search.append(k, String(v));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

export const workflowRunService = {
  async list(filters: WorkflowRunFilters = {}): Promise<ListWorkflowRunsResponse> {
    return callAPIWithETag(`${BASE}${qs(filters)}`);
  },

  async get(id: string): Promise<{ run: WorkflowRun }> {
    return callAPIWithETag(`${BASE}/${id}`);
  },

  async create(payload: CreateWorkflowRunRequest): Promise<{ run: WorkflowRun }> {
    return callAPIWithETag(BASE, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async start(id: string): Promise<{ run: WorkflowRun }> {
    return callAPIWithETag(`${BASE}/${id}/start`, { method: "POST" });
  },

  async complete(id: string, outputs?: Record<string, unknown>): Promise<{ run: WorkflowRun }> {
    return callAPIWithETag(`${BASE}/${id}/complete`, {
      method: "POST",
      body: outputs ? JSON.stringify(outputs) : undefined,
    });
  },

  async fail(id: string, error: string): Promise<{ run: WorkflowRun }> {
    return callAPIWithETag(`${BASE}/${id}/fail`, {
      method: "POST",
      body: JSON.stringify({ error }),
    });
  },

  async cancel(id: string): Promise<{ run: WorkflowRun }> {
    return callAPIWithETag(`${BASE}/${id}/cancel`, { method: "POST" });
  },
};
