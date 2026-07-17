/**
 * Review Gate panel — HITL modal shown on tasks in the `review` column
 * (NETRA Phase 5B Slice 2.1b).
 *
 * Shows the droid's output attached to the workflow_run and gives Kris
 * three actions:
 *   Approve   → PUT /api/tasks/{id}  status=done       (ships)
 *   Reject    → PUT /api/tasks/{id}  status=todo       (retry)
 *   Redirect  → PUT /api/tasks/{id}  status=doing      (droid continues
 *                                                       with clarified
 *                                                       requirements)
 *
 * Also: reassign persona dropdown (HITL override — Kris's Slice 2 addition).
 * The reassignment writes assignee back, which the runner picks up on the
 * next poll if status returns to `todo`.
 */

import { useState } from "react";
import {
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  TextArea,
} from "../../ui/primitives";
import type { Task } from "../../projects/tasks/types";
import { callAPIWithETag } from "../../shared/api/apiClient";
import { useTaskWorkflowRun } from "../hooks/useTaskWorkflowRun";

interface ReviewGatePanelProps {
  isOpen: boolean;
  onClose: () => void;
  task: Task;
  projectId: string;
  onActioned?: () => void; // parent refetches list on approve/reject/redirect
}

const KIO_PERSONAS = [
  "kio-analyst",
  "kio-architect",
  "kio-dev",
  "kio-qa",
  "kio-pm",
  "kio-sm",
  "kio-orchestrator",
  "kio-researcher",
] as const;

export function ReviewGatePanel({
  isOpen,
  onClose,
  task,
  projectId,
  onActioned,
}: ReviewGatePanelProps) {
  const { run, isLoading } = useTaskWorkflowRun(task.id, projectId);
  const [notes, setNotes] = useState("");
  const [reassignPersona, setReassignPersona] = useState<string>(
    task.assignee || "kio-dev",
  );
  const [submitting, setSubmitting] = useState<"" | "approve" | "reject" | "redirect">(
    "",
  );
  const [error, setError] = useState<string | null>(null);

  const output = (run?.outputs?.droid_output as string) || "";
  const outputOK = (run?.outputs?.ok as boolean) ?? false;

  async function transition(
    action: "approve" | "reject" | "redirect",
    nextStatus: "done" | "todo" | "doing",
  ) {
    setSubmitting(action);
    setError(null);
    try {
      const patch: Record<string, unknown> = { status: nextStatus };
      if (reassignPersona && reassignPersona !== task.assignee) {
        patch.assignee = reassignPersona;
      }
      if (notes) patch.review_notes = notes;

      await callAPIWithETag(`/api/tasks/${task.id}`, {
        method: "PUT",
        body: JSON.stringify(patch),
      });
      onActioned?.();
      onClose();
      setNotes("");
    } catch (e) {
      setError((e as Error)?.message || "Unknown error");
    } finally {
      setSubmitting("");
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Review · {task.title}</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          {task.description && (
            <div>
              <Label className="text-xs uppercase text-white/60">Task description</Label>
              <div className="mt-1 rounded-md border border-white/10 bg-black/20 p-3 text-sm text-white/80 whitespace-pre-wrap">
                {task.description}
              </div>
            </div>
          )}

          <div>
            <Label className="text-xs uppercase text-white/60 flex items-center justify-between">
              <span>
                Droid output
                {run && (
                  <span className="ml-2 font-mono text-white/40">
                    run={run.id.slice(0, 8)} · persona={run.persona} · state={run.state}
                  </span>
                )}
              </span>
              {run && (
                <span
                  className={
                    outputOK
                      ? "rounded-full bg-emerald-500/20 px-2 py-0.5 text-emerald-200"
                      : "rounded-full bg-amber-500/20 px-2 py-0.5 text-amber-200"
                  }
                >
                  {outputOK ? "ok" : "empty/failed"}
                </span>
              )}
            </Label>
            <div className="mt-1 max-h-72 overflow-y-auto rounded-md border border-white/10 bg-black/40 p-3 font-mono text-xs text-white/80 whitespace-pre-wrap">
              {isLoading && "loading…"}
              {!isLoading && !run && "No workflow run found for this task."}
              {!isLoading && run && !output && "(no droid output captured)"}
              {output}
            </div>
          </div>

          <div>
            <Label htmlFor="review-notes" className="text-xs uppercase text-white/60">
              Notes to droid (optional — attached on Redirect/Reject)
            </Label>
            <TextArea
              id="review-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="What should the droid do differently on the next iteration?"
              rows={3}
              className="mt-1"
            />
          </div>

          <div>
            <Label className="text-xs uppercase text-white/60">
              Assignee (HITL override — reassign to a different droid)
            </Label>
            <Select value={reassignPersona} onValueChange={setReassignPersona}>
              <SelectTrigger className="mt-1">
                <SelectValue placeholder="Pick a persona" />
              </SelectTrigger>
              <SelectContent>
                {KIO_PERSONAS.map((p) => (
                  <SelectItem key={p} value={p}>
                    {p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {error && (
            <div className="rounded border border-red-500/40 bg-red-500/10 p-2 text-sm text-red-200">
              {error}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => transition("reject", "todo")}
            disabled={submitting !== ""}
          >
            {submitting === "reject" ? "…" : "Reject → todo"}
          </Button>
          <Button
            variant="outline"
            onClick={() => transition("redirect", "doing")}
            disabled={submitting !== ""}
          >
            {submitting === "redirect" ? "…" : "Redirect → doing"}
          </Button>
          <Button
            onClick={() => transition("approve", "done")}
            disabled={submitting !== ""}
          >
            {submitting === "approve" ? "…" : "Approve → done"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
