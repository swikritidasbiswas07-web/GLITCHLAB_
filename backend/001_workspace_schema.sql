-- GLITCHLAB_ Build 05D: PostgreSQL schema for existing auth + isolated workspaces.
-- Additive only. Does NOT migrate data or change FastAPI connection settings.
-- Preserves TEXT timestamps and INTEGER flags for fidelity with SQLite records.
-- Run on a dedicated, empty GLITCHLAB_ database/schema only.
CREATE TABLE IF NOT EXISTS auth_users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES auth_users(id),
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gl_workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_by TEXT NOT NULL REFERENCES auth_users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gl_memberships (
    workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('admin','editor','reviewer','creator')),
    joined_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, user_id)
);

CREATE TABLE IF NOT EXISTS gl_content_drafts (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
    author_id TEXT NOT NULL REFERENCES auth_users(id),
    title TEXT NOT NULL,
    channel TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gl_content_versions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
    draft_id TEXT NOT NULL REFERENCES gl_content_drafts(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT,
    UNIQUE (draft_id, number)
);

CREATE TABLE IF NOT EXISTS gl_reference_sources (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    uploaded_by TEXT NOT NULL REFERENCES auth_users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gl_policy_rules (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    pattern TEXT NOT NULL,
    replacement TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE (workspace_id, code)
);

CREATE TABLE IF NOT EXISTS gl_guideline_cases (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
    rule_id TEXT NOT NULL REFERENCES gl_policy_rules(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    sample TEXT NOT NULL,
    expected_match INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gl_evaluation_runs (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
    draft_id TEXT NOT NULL REFERENCES gl_content_drafts(id) ON DELETE CASCADE,
    version_id TEXT NOT NULL REFERENCES gl_content_versions(id) ON DELETE CASCADE,
    tested_by TEXT NOT NULL REFERENCES auth_users(id),
    checked_rules INTEGER NOT NULL,
    rule_snapshot TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gl_evaluation_findings (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
    run_id TEXT NOT NULL REFERENCES gl_evaluation_runs(id) ON DELETE CASCADE,
    rule_code TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    matched_text TEXT NOT NULL,
    start INTEGER NOT NULL,
    "end" INTEGER NOT NULL,
    suggestion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gl_review_decisions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
    draft_id TEXT NOT NULL REFERENCES gl_content_drafts(id) ON DELETE CASCADE,
    version_id TEXT NOT NULL REFERENCES gl_content_versions(id) ON DELETE CASCADE,
    actor_id TEXT NOT NULL REFERENCES auth_users(id),
    decision TEXT NOT NULL,
    comment TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS gl_memberships_user_idx ON gl_memberships(user_id);
CREATE INDEX IF NOT EXISTS gl_content_drafts_workspace_idx ON gl_content_drafts(workspace_id);
CREATE INDEX IF NOT EXISTS gl_content_versions_lookup_idx ON gl_content_versions(workspace_id,draft_id,number);
CREATE INDEX IF NOT EXISTS gl_sources_workspace_idx ON gl_reference_sources(workspace_id);
CREATE INDEX IF NOT EXISTS gl_rules_workspace_idx ON gl_policy_rules(workspace_id);
CREATE INDEX IF NOT EXISTS gl_cases_workspace_idx ON gl_guideline_cases(workspace_id);
CREATE INDEX IF NOT EXISTS gl_runs_scope_idx ON gl_evaluation_runs(workspace_id,draft_id,created_at);
CREATE INDEX IF NOT EXISTS gl_findings_scope_idx ON gl_evaluation_findings(workspace_id,run_id);
CREATE INDEX IF NOT EXISTS gl_reviews_scope_idx ON gl_review_decisions(workspace_id,draft_id,created_at);

