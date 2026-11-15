-- Build 05J: immutable workspace policy snapshot ledger (additive)
CREATE TABLE IF NOT EXISTS gl_policy_releases (
 id TEXT PRIMARY KEY,
 workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
 number INTEGER NOT NULL CHECK(number>=1),
 snapshot_hash TEXT NOT NULL,
 snapshot TEXT NOT NULL,
 note TEXT NOT NULL,
 published_by TEXT NOT NULL REFERENCES auth_users(id),
 published_at TEXT NOT NULL,
 UNIQUE(workspace_id,number)
);
CREATE INDEX IF NOT EXISTS gl_policy_releases_workspace_idx ON gl_policy_releases(workspace_id,number DESC);
