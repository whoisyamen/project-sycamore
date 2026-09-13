-- Sycamore archive schema — migration 001 (iteration 1.2.1 shadow mode)
-- Mirrors INTELLIGENCE_IMPLEMENTATION_SPEC §4.2 minimum tables plus the
-- schema_migrations ledger. Applied transactionally by archive.apply_migrations;
-- the ledger row for version 1 is inserted by the same transaction.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version    INTEGER PRIMARY KEY,
  checksum   TEXT NOT NULL,
  applied_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS providers (
  provider_uid   TEXT PRIMARY KEY,
  display_name   TEXT NOT NULL,
  policy_version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS source_records (
  source_uid    TEXT PRIMARY KEY,
  provider_uid  TEXT NOT NULL REFERENCES providers(provider_uid),
  natural_key   TEXT NOT NULL UNIQUE,
  original_url  TEXT NOT NULL,
  canonical_url TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_revisions (
  revision_uid   TEXT PRIMARY KEY,
  source_uid     TEXT NOT NULL REFERENCES source_records(source_uid),
  content_hash   TEXT NOT NULL,
  published_at   INTEGER,             -- nullable; source-stated time, ms UTC
  observed_at    INTEGER NOT NULL,    -- our observation time, ms UTC
  allowed_payload TEXT NOT NULL,      -- JSON; permitted retained text/metadata
  UNIQUE(source_uid, content_hash)
);

CREATE TABLE IF NOT EXISTS ingest_runs (
  run_uid      TEXT PRIMARY KEY,
  started_at   INTEGER NOT NULL,
  finished_at  INTEGER,
  outcome      TEXT NOT NULL DEFAULT 'running',  -- running|ok|degraded|error|gap
  counts       TEXT NOT NULL DEFAULT '{}',       -- JSON diagnostic counts
  last_success INTEGER
);

CREATE TABLE IF NOT EXISTS source_observations (
  run_uid               TEXT NOT NULL REFERENCES ingest_runs(run_uid),
  source_uid            TEXT NOT NULL REFERENCES source_records(source_uid),
  revision_uid          TEXT NOT NULL REFERENCES source_revisions(revision_uid),
  normalization_outcome TEXT NOT NULL,  -- accepted|rejected:<reason>
  observed_at           INTEGER NOT NULL,
  PRIMARY KEY (run_uid, source_uid, revision_uid)
);

CREATE TABLE IF NOT EXISTS events (
  event_uid            TEXT PRIMARY KEY,
  legacy_id            INTEGER UNIQUE,   -- existing numeric v1 event ID; nullable pre-import
  current_revision_uid TEXT REFERENCES event_revisions(revision_uid),
  status               TEXT NOT NULL DEFAULT 'active',
  import_identity      TEXT               -- opaque import batch identity (1.2.1 import_snapshot)
);

CREATE TABLE IF NOT EXISTS event_revisions (
  revision_uid          TEXT PRIMARY KEY,
  event_uid             TEXT NOT NULL REFERENCES events(event_uid),
  semantic_hash         TEXT NOT NULL,
  created_at            INTEGER NOT NULL,
  permitted_payload     TEXT NOT NULL,   -- JSON normalized content
  normalization_version TEXT NOT NULL,
  source                TEXT NOT NULL DEFAULT 'ingest',  -- 'ingest'|'legacy_import'
  UNIQUE(event_uid, semantic_hash)
);

CREATE TABLE IF NOT EXISTS event_evidence (
  event_revision_uid  TEXT NOT NULL REFERENCES event_revisions(revision_uid),
  source_revision_uid TEXT NOT NULL REFERENCES source_revisions(revision_uid),
  role                TEXT NOT NULL DEFAULT 'evidence',
  PRIMARY KEY (event_revision_uid, source_revision_uid)
);

CREATE TABLE IF NOT EXISTS identity_counters (
  name       TEXT PRIMARY KEY,
  next_value INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS source_health (
  run_uid      TEXT NOT NULL REFERENCES ingest_runs(run_uid),
  provider_uid TEXT NOT NULL REFERENCES providers(provider_uid),
  state        TEXT NOT NULL,          -- ok|empty|failed|skipped
  error_code   TEXT,
  observed_at  INTEGER NOT NULL,
  PRIMARY KEY (run_uid, provider_uid)
);

-- Gap ledger: missing archive coverage must stay visible to the operator.
-- A later successful cycle updates state to 'reconciled'; never claims
-- continuous history.
CREATE TABLE IF NOT EXISTS shadow_gaps (
  run_uid  TEXT PRIMARY KEY REFERENCES ingest_runs(run_uid),
  reason   TEXT NOT NULL,
  seen_at  INTEGER NOT NULL,
  state    TEXT NOT NULL DEFAULT 'open'  -- open|reconciled
);

CREATE INDEX IF NOT EXISTS idx_source_obs_run ON source_observations(run_uid);
CREATE INDEX IF NOT EXISTS idx_source_rev_source ON source_revisions(source_uid);
CREATE INDEX IF NOT EXISTS idx_ev_rev_event ON event_revisions(event_uid);
CREATE INDEX IF NOT EXISTS idx_event_evidence_rev ON event_evidence(event_revision_uid);

INSERT INTO schema_migrations (version, checksum, applied_at)
VALUES (1, '', 0);  -- checksum filled in by apply_migrations from the file bytes