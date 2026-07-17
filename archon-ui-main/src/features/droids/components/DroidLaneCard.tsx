/**
 * One card representing an active workflow run inside a persona lane.
 * Shows what the droid is working on RIGHT NOW.
 */

import type { WorkflowRun } from "../types/workflowRun";

interface DroidLaneCardProps {
  run: WorkflowRun;
}

function fmtElapsed(startedAt: string | null): string {
  if (!startedAt) return "";
  const start = new Date(startedAt).getTime();
  const now = Date.now();
  const sec = Math.max(0, Math.floor((now - start) / 1000));
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ${sec % 60}s`;
  const hr = Math.floor(min / 60);
  return `${hr}h ${min % 60}m`;
}

export function DroidLaneCard({ run }: DroidLaneCardProps) {
  const input = run.invocation_input as Record<string, unknown>;
  const taskTitle =
    (input?.task_title as string) || (input?.title as string) || run.workflow_name;
  const taskDesc = (input?.task_description as string) || "";
  const output = run.outputs?.droid_output as string | undefined;

  return (
    <div className="rounded-md border border-white/10 bg-white/5 p-3 backdrop-blur-sm">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-blue-300">
          {run.workflow_name}
        </span>
        <span className="text-xs text-white/60">{fmtElapsed(run.started_at)}</span>
      </div>
      <div className="mb-2 text-sm font-medium text-white/90 line-clamp-2">
        {taskTitle}
      </div>
      {taskDesc && (
        <div className="mb-2 text-xs text-white/60 line-clamp-2">{taskDesc}</div>
      )}
      {output && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-white/50 hover:text-white/80">
            live output ({output.length} chars)
          </summary>
          <pre className="mt-1 max-h-32 overflow-y-auto text-xs text-white/70 whitespace-pre-wrap">
            {output.slice(0, 500)}
            {output.length > 500 ? "…" : ""}
          </pre>
        </details>
      )}
      <div className="mt-2 flex items-center justify-between">
        <span className="text-xs text-white/40 font-mono">{run.id.slice(0, 8)}</span>
        {run.task_id && (
          <span className="text-xs text-white/40 font-mono">
            → {run.task_id.slice(0, 8)}
          </span>
        )}
      </div>
    </div>
  );
}
