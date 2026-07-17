/**
 * Droid Lanes view — one lane per active persona.
 *
 * NETRA Phase 5B Slice 2.1: at-a-glance visibility into what the
 * kyros-agents droid runner is doing 24/7 in the background.
 * Polls /api/workflow-runs?state=running every 5s.
 */

import { useMemo, useState } from "react";
import { useActiveDroids } from "../hooks/useWorkflowRuns";
import { DroidLaneCard } from "../components/DroidLaneCard";
import type { WorkflowRun } from "../types/workflowRun";

function groupByPersona(runs: WorkflowRun[]): Record<string, WorkflowRun[]> {
  const groups: Record<string, WorkflowRun[]> = {};
  for (const r of runs) {
    const key = r.persona || "unassigned";
    (groups[key] ||= []).push(r);
  }
  return groups;
}

export function DroidLanesView() {
  const [projectFilter, setProjectFilter] = useState<string>("");
  const { data, isLoading, isError, error } = useActiveDroids(
    projectFilter || undefined,
  );

  const lanes = useMemo(() => groupByPersona(data?.runs || []), [data?.runs]);
  const personas = Object.keys(lanes).sort();

  return (
    <div className="flex h-full flex-col gap-4 p-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Droid Lanes</h1>
          <p className="text-sm text-white/60">
            Live view of what each kio-* droid is running right now.
            Poll interval 5s.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={projectFilter}
            onChange={(e) => setProjectFilter(e.target.value)}
            placeholder="Filter by project id (optional)"
            className="rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white placeholder-white/40 backdrop-blur-sm"
          />
          <span className="rounded-full bg-blue-500/20 px-3 py-1 text-xs font-semibold text-blue-200">
            {data?.count ?? 0} running
          </span>
        </div>
      </header>

      {isLoading && (
        <div className="text-sm text-white/60">Loading droid activity…</div>
      )}
      {isError && (
        <div className="rounded border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
          Failed to load droid runs: {(error as Error)?.message || "unknown"}
        </div>
      )}

      {!isLoading && !isError && personas.length === 0 && (
        <div className="mx-auto mt-16 max-w-md rounded-lg border border-white/10 bg-white/5 p-8 text-center">
          <div className="mb-2 text-4xl">🛌</div>
          <div className="mb-1 text-lg font-semibold text-white">
            No droids running
          </div>
          <div className="text-sm text-white/60">
            Assign a task to a kio-* persona in the todo column and the
            kyros-agents runner will pick it up within 15s.
          </div>
        </div>
      )}

      {personas.length > 0 && (
        <div className="flex flex-1 gap-4 overflow-x-auto">
          {personas.map((persona) => (
            <section
              key={persona}
              className="flex min-w-[280px] flex-1 flex-col gap-2 rounded-lg border border-white/10 bg-black/20 p-3"
            >
              <div className="flex items-center justify-between border-b border-white/10 pb-2">
                <span className="font-semibold text-white">{persona}</span>
                <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-white/70">
                  {lanes[persona].length}
                </span>
              </div>
              <div className="flex flex-col gap-2">
                {lanes[persona].map((run) => (
                  <DroidLaneCard key={run.id} run={run} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
