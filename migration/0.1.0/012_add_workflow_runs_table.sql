-- =====================================================
-- Migration 012: Add archon_workflow_runs table
-- =====================================================
-- Purpose: Persist kio_orchestrate() invocations so droids running
--          24/7 in the background have durable state.
-- Consumer: Kyros-agents droid job runner + Archon UI Droid Lanes.
-- Slice 1 of NETRA Phase 5B unified droid factory UI plan (2026-07-17).
-- =====================================================

CREATE TABLE IF NOT EXISTS archon_workflow_runs (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- What was invoked
    workflow_name    TEXT        NOT NULL,      -- e.g., "sprint-planning", "create-story", "dev-story"
    persona          TEXT,                       -- e.g., "kio-analyst", "kio-dev", "kio-orchestrator"

    -- Where it applies
    project_id       UUID        REFERENCES archon_projects(id) ON DELETE CASCADE,
    sprint_id        UUID,                       -- optional (soft ref — Sprint table may live in different schema)
    task_id          UUID        REFERENCES archon_tasks(id)    ON DELETE SET NULL,

    -- Execution state
    state            TEXT        NOT NULL DEFAULT 'pending'
                                 CHECK (state IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    invocation_input JSONB       NOT NULL DEFAULT '{}'::jsonb,   -- raw kio_orchestrate() args
    outputs          JSONB       NOT NULL DEFAULT '{}'::jsonb,   -- workflow outputs (diffs, notes, artifacts)
    outcomes         JSONB       NOT NULL DEFAULT '{}'::jsonb,   -- Slice 5: post-hoc outcome tracking (PR merged? tests pass?)
    error            TEXT,                                        -- populated on failure

    -- Timestamps
    started_at       TIMESTAMPTZ,
    completed_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes: droid Lanes queries these hot paths
CREATE INDEX IF NOT EXISTS idx_workflow_runs_state           ON archon_workflow_runs(state);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_project         ON archon_workflow_runs(project_id, state);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_task            ON archon_workflow_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_persona_running ON archon_workflow_runs(persona) WHERE state = 'running';

-- Auto-update updated_at on row changes (matches existing archon convention).
CREATE OR REPLACE FUNCTION archon_workflow_runs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_workflow_runs_updated_at ON archon_workflow_runs;
CREATE TRIGGER trg_workflow_runs_updated_at
    BEFORE UPDATE ON archon_workflow_runs
    FOR EACH ROW
    EXECUTE FUNCTION archon_workflow_runs_updated_at();

-- Extend archon_tasks with autonomy_level so the droid runner knows whether to
-- pause at 'review' (HITL required) or auto-transition to 'done' (autonomous).
-- Nullable → treat as 'hitl_review_required' (safe default).
ALTER TABLE archon_tasks
    ADD COLUMN IF NOT EXISTS autonomy_level TEXT
        CHECK (autonomy_level IN ('hitl_review_required', 'hitl_review_optional', 'autonomous'));

COMMENT ON TABLE archon_workflow_runs IS
    'Persists kio_orchestrate() invocations for the NETRA droid factory. '
    'Consumed by kyros-agents droid runner + Archon UI Droid Lanes view.';
COMMENT ON COLUMN archon_tasks.autonomy_level IS
    'How the droid job runner should handle the review→done transition. '
    'NULL / hitl_review_required = block on human approval; hitl_review_optional = '
    'auto-transition after N minutes unless human intervenes; autonomous = ship immediately.';
