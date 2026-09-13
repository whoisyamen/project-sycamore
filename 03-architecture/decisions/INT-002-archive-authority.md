# INT-002 — Archive authority and shadow mode

Status: ACCEPTED (2026-09-10) — iteration 1.2.1.
Scope: durable archive in shadow mode. Legacy JSON pipeline stays authoritative.

## Context

Iterations 1.1.1/1.1.2 established the v1 projection boundary, canonical hashing,
stable event UID mapping and explicit intelligence contracts. Before live
pruning (MAX_EVENTS=500) discards history, source observations and event
identity must be persisted without changing what the public JSON publishes.
The spec (§5.1) defines three modes: legacy, shadow, archive. This iteration
implements only legacy (default) and shadow.

## Decision

1. **Legacy stays authoritative.** `runner.run()` defaults to `mode="legacy"`
   and publishes exactly as before. Shadow mode is additive: a single fetched
   batch is observed BEFORE URL-skip dedupe and before `events[:MAX_EVENTS]`.
   Sources are never fetched twice. Shadow DB failure never blocks or alters
   legacy publication; it records a gap instead.
2. **Archive path is explicit and guarded.** `mode="shadow"` requires an
   `archive_path` outside `public/data` and `dist`. Configuration is rejected
   before any fetch. No private DB is written under public assets.
3. **SQLite via stdlib `sqlite3`**, FK enforcement enabled on every connection
   (`PRAGMA foreign_keys=ON`). Tables created from spec §4 minimal set plus a
   migration ledger:
   - `schema_migrations(version, checksum, applied_at)` — each migration is
     applied in a transaction; `version` is a monotonically increasing integer.
     Migration text is SHA-256 hashed at apply time. Re-applying an existing
     version is a no-op. Editing an already-applied migration's bytes changes
     its checksum and is rejected as an error (prevents silent drift).
   - `providers`, `source_records`, `source_revisions`, `source_observations`,
     `events`, `event_revisions`, `event_evidence`, `identity_counters`,
     `ingest_runs`, `source_health` per INTELLIGENCE_IMPLEMENTATION_SPEC §4.2.
4. **Repository functions** with typed returns (see archive.py docstrings):
   - `import_snapshot(snapshot, import_identity)` — stable numeric-ID→UID map;
     repeat import returns the existing mapping, never new UUIDs. Records an
     explicit missing-history marker (`source: "legacy_import"`) on imported
     event revisions; the source-observation history before import is unknown.
   - `record_batch(run_uid, articles, observed_at)` — stores source records,
     revisions, observations and per-article normalization outcome
     (accepted/rejected + reason). Retrying the same run/batch is idempotent.
     `UNIQUE(run_uid, source_uid, revision_uid)` prevents duplicate rows.
   - `record_event_revision(event_uid, evidence_refs, normalized_content)` —
     appends a new event revision only when the semantic content hash changes;
     clock-only changes do not append a material revision. Event↔evidence links
     are stored with FK enforcement.
   - `compare_projection(legacy_snapshot, candidate_snapshot)` — fixed-clock
     comparison of events, ID map, sources, counts and health; emits a list of
     differences. Runner uses a fixed clock in shadow integration so only real
     content differences appear.
   - `record_shadow_gap(run_uid, reason)` — persistent, visible gap marker.
5. **Failed shadow cycle ≠ new coverage.** If archive writing fails, the legacy
   path completes normally and the gap is recorded (`record_shadow_gap`).
   A later successful cycle updates the gap state but never labels the archive
   as continuous history.

## Failure behavior (spec §5.2 matrix, shadow subset)

| Failure | Expected behavior in this iteration |
| --- | --- |
| Invalid shadow config (missing/unsafe path) | Rejected before any fetch |
| DB transaction error before commit | Rollback; no partial rows; legacy path continues |
| After DB commit, legacy publish fails | Archive rows exist but no public change; next run reconciles; gap recorded |
| Archive unavailable mid-run | Legacy completes; `record_shadow_gap` writes (best-effort) |
| FK constraint violation | Transaction fails closed; no orphan rows |

Rollback: default remains legacy; disable shadow and retain the test DB for
diagnosis. No archive-mode authority switch exists yet. Post-cutover rollback is
implemented/rehearsed in 1.2.2/1.2.3.

## Rejected alternatives

- Archive as authority now: rejected — cutover requires ten fixture cycles,
  backup/recovery rehearsal and three real scheduled shadow cycles (spec §5.3).
- Two writes in one transaction: rejected — JSON and DB are separate; shadow
  observes, it does not publish.
- Guessing a private archive path: rejected — configuration is explicit.
- Extending v1 schema to carry archive state: rejected (1.1.2 INT-001).

## Consequences

- g3-ingest/README.md documents modes and temporary-path instructions.
- 1.2.2 publication brief will expand the failure matrix before coding.
- The migration ledger and test DBs live under temporary paths in tests; the
  default production pipeline is never invoked merely for benchmark data.