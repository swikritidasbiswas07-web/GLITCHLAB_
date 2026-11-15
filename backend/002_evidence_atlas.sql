-- Build 05I: additive PostgreSQL-only migration. Apply once using apply_evidence_schema.py.
CREATE TABLE IF NOT EXISTS gl_evidence_items (
 id TEXT PRIMARY KEY,
 workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
 source_id TEXT NOT NULL REFERENCES gl_reference_sources(id) ON DELETE CASCADE,
 quote TEXT NOT NULL CHECK (length(quote) BETWEEN 1 AND 4000),
 source_locator TEXT NOT NULL DEFAULT '',
 source_sha256 TEXT NOT NULL,
 recorded_by TEXT NOT NULL REFERENCES auth_users(id),
 created_at TEXT NOT NULL,
 UNIQUE (id, workspace_id)
);
CREATE INDEX IF NOT EXISTS gl_evidence_source_idx ON gl_evidence_items(workspace_id,source_id);
CREATE TABLE IF NOT EXISTS gl_claims (
 id TEXT PRIMARY KEY,
 workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
 draft_id TEXT NOT NULL REFERENCES gl_content_drafts(id) ON DELETE CASCADE,
 version_id TEXT NOT NULL REFERENCES gl_content_versions(id) ON DELETE CASCADE,
 claim_text TEXT NOT NULL CHECK (length(claim_text) BETWEEN 1 AND 1200),
 recorded_by TEXT NOT NULL REFERENCES auth_users(id),
 created_at TEXT NOT NULL,
 UNIQUE (id, workspace_id)
);
CREATE INDEX IF NOT EXISTS gl_claim_version_idx ON gl_claims(workspace_id,draft_id,version_id);
CREATE TABLE IF NOT EXISTS gl_claim_evidence (
 id TEXT PRIMARY KEY,
 workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
 claim_id TEXT NOT NULL,
 evidence_id TEXT NOT NULL,
 stance TEXT NOT NULL CHECK (stance IN ('supports','contradicts','context')),
 rationale TEXT NOT NULL,
 added_by TEXT NOT NULL REFERENCES auth_users(id),
 attested_by TEXT REFERENCES auth_users(id),
 attested_at TEXT,
 created_at TEXT NOT NULL,
 FOREIGN KEY (claim_id,workspace_id) REFERENCES gl_claims(id,workspace_id) ON DELETE CASCADE,
 FOREIGN KEY (evidence_id,workspace_id) REFERENCES gl_evidence_items(id,workspace_id) ON DELETE CASCADE,
 UNIQUE (claim_id,evidence_id)
);
CREATE INDEX IF NOT EXISTS gl_claim_evidence_lookup_idx ON gl_claim_evidence(workspace_id,claim_id);
