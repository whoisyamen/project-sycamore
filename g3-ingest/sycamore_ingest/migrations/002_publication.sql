-- Sycamore publication schema — migration 002 (iteration 1.2.2)
-- Adds the replayable publish-intent table from INTELLIGENCE_IMPLEMENTATION_SPEC
-- §4.2 and INT-003: one row per committed cycle, monotonic sequence, immutable
-- payload bytes addressed by sha256 so ordered replay can hash-verify before any
-- file write. The ledger row for version 2 is inserted in the same transaction;
-- apply_migrations fills its checksum from the file bytes (001 pattern).

CREATE TABLE IF NOT EXISTS publication_jobs (
  publication_uid    TEXT PRIMARY KEY,          -- stable intent identity across retries/replays
  sequence           INTEGER UNIQUE NOT NULL,   -- monotonic per INT-003 §2/§3; replay order = this order
  run_uid            TEXT NOT NULL REFERENCES ingest_runs(run_uid),
  payload_hash       TEXT NOT NULL,             -- sha256 of the stored UTF-8 JSON bytes (canonical)
  payload_or_reference TEXT NOT NULL,           -- inline v1 snapshot JSON now; reference form is a documented 1.2.3 retention path
  state              TEXT NOT NULL DEFAULT 'pending',   -- pending|published
  attempts           INTEGER NOT NULL DEFAULT 0,        -- incremented before each file-write attempt (crash-observable)
  created_at         INTEGER NOT NULL,          -- ms UTC, commit time
  published_at       INTEGER                     -- successful delivery boundary; null until acknowledged
);

CREATE INDEX IF NOT EXISTS idx_pub_jobs_state ON publication_jobs(state, sequence);

INSERT INTO schema_migrations (version, checksum, applied_at)
VALUES (2, '', 0);  -- checksum filled in by apply_migrations from the file bytes
