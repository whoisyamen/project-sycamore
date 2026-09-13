# INT-003 — Archive-mode publication and ordered replay

Status: ACCEPTED (2026-09-10) — iteration 1.2.2.
Scope: `mode="archive"` capability in g3-ingest; DB becomes authoritative for v1
publication through replayable jobs. Live cutover remains explicitly out of scope
(that is 1.2.3 with backup/restore rehearsal and scheduled-cycle evidence).

## Context

INT-002 (iteration 1.2.1) established the durable archive in shadow mode: one
fetched batch observed before dedupe/pruning, stable event UIDs, semantic
revisions, gap ledger — while legacy JSON stayed authoritative. Spec §5 defines a
third mode, `archive`: "DB is authoritative; publisher derives v1 from committed
state." This ADR fixes the design decisions that iteration 1.2.2 implements and
tests with fixtures only.

## Decision

1. **Authority switch by construction, not flag flip.** In archive mode the cycle
   body reuses the exact legacy merge/dedupe/score/prune/media/OSINT ordering —
   same deterministic computation as `runner._cycle` — but two things change:
   (a) previous state is derived from committed DB projection instead of
   snapshot.json, and (b) terminal publication is a single commit transaction +
   ordered replay instead of direct `_publish`. Legacy (`legacy`) and shadow modes
   are byte-identical to 1.2.1 behavior; all pre-existing tests must pass unchanged.

2. **One explicit transaction per cycle.** `publisher.commit_cycle` stores, inside
   ONE BEGIN IMMEDIATE ... COMMIT: the ingest_runs row (outcome ok|degraded|error),
   source_health rows for every provider in this run (ok/empty from batch size,
   failed from the cycle's failed-source list including OSINT envelope failures and
   invalid-record markers), permitted source records/revisions/observations for
   EVERY fetched article (same dedupe semantics as shadow: UNIQUE(source_uid,
   content_hash); observation PK per run), event evidence + material revisions over
   the PRE-prune merged list (clock-only changes never append — same semantic-hash
   rule as 1.2.1), then computes and validates (`validate_snapshot`) the v1
   projection (latest MAX_EVENTS accepted map events, legacy sort order) and inserts
   an immutable publication_jobs row with a monotonic sequence allocated from
   identity_counters('publication_sequence') in-transaction. Any exception rolls
   back everything: no partial rows of any kind — this is spec §5.2's "before DB
   commit" recovery (previous public snapshot stays valid).

3. **Ordered replay, idempotent.** `publisher.replay` publishes pending jobs in
   strictly increasing sequence order under the existing `.ingest.lock`. Per job:
   re-validate payload schema; write snapshot.json via temp file + fsync + atomic
   replace (+ directory sync); repair/replace legacy mirrors events.json and
   manifest.json from the SAME committed bytes; acknowledge (state='published',
   attempts+1) in a separate small transaction only after all three files are on
   disk. Re-running an acknowledged job rewrites identical bytes — harmless, per
   spec §5.2 "after snapshot replace, before acknowledgement". Mirrors can never
   cause the canonical file to regress: replay writes committed payloads forward
   by sequence; `sync_mirrors` (called at archive-mode startup) repairs divergent
   or missing mirrors from the latest published payload_hash without refetching.

4. **Bootstrap guardrail (fail-closed).** An archive-mode cycle may derive previous
   state only from: (a) a committed publication_jobs payload, or (b) events whose
   current revision carries an explicit import_identity (full legacy-import v1
   payloads). A DB with neither — live-ingest-only revisions and no prior
   publication — raises before any fetch. Cutover therefore begins by importing the
   current snapshot into a fresh archive under a stable identity; that procedure is
   documented in README/INT-002 lineage, never invented at runtime. This exists
   because live-ingest event_revisions store semantic content only (no geo/score),
   and projection must always be computed from FULL v1 rows to keep merge semantics
   identical to legacy — reconstruction from semantic-only payloads is prohibited by
   design rather than handled ad hoc.

5. **Media/OSINT boundary.** Media attachment stays inside the cycle, before commit:
   attached media paths are part of the v1 projection payload (legacy parity). The
   spec §5.2 "enrichment fails" row maps to what exists today — OSINT envelopes
   (flights/censys) and attach_media failures remain strictly non-blocking via their
   existing try/except isolation; they degrade health labels, never block the DB
   commit or file publication. Future enrichment (1.4 entities etc.) will run after
   canonical commit in its own retryable job per spec §5.2 — out of scope here.

6. **Total source failure publishes a retained projection.** Mirroring legacy
   `_failure`: previous committed events are re-published with lastSync preserved,
   lastAttempt advanced and health.status='error' + failedSources; the ingest_runs
   row (outcome='error') is stored in the same transaction as that publication job.

7. **Payload retention note.** publication_jobs.payload_or_reference stores inline
   JSON for now. The reference form (payload path outside public/data) is a 1.2.3
   concern tied to source-retention/deletion policy; schema field names follow spec
   §4.2 so the switch does not require another migration of this table's identity.

## Failure matrix mapping (spec §5.2 — implemented and fixture-tested in 1.2.2)

| Spec row | Implementation point |
| --- | --- |
| Before DB commit | Single transaction rollback; zero partial rows; file untouched |
| After DB commit, before file replace | Job stays pending; replay re-publishes without any provider fetch |
| Snapshot replaced, before acknowledgement | Repeat is harmless: identical bytes, hash verified against payload_hash |
| Mirror write fails | Canonical snapshot remains committed; sync_mirrors repairs from committed payload; never restores an older snapshot |
| Multiple pending jobs | Replay in increasing sequence only; final file == highest-sequence payload |
| Total source failure | Retained previous events + lastSync preserved + error health, same tx as run row |
| Enrichment fails | OSINT/media failures non-blocking (existing isolation); publication proceeds |
| Disk full / write error mid-publish | Last-good snapshot byte-identical; job pending and retryable after capacity restored |

Shadow gap rows remain 1.2.3/operational: this iteration's archive mode has no
shadow path to gap — failures are transactional (rollback) or replay-pending, both
observable in the DB itself.

## Rejected alternatives

- Deriving projection from semantic-only event_revisions: rejected — loses geo/score
  provenance and changes merge/validation semantics vs legacy; bootstrap guardrail
  forbids that state instead (§4 above).
- Dual write (DB + direct _publish) in archive mode: rejected by spec §5.2 "do not
  assume two writes to JSON and DB are one transaction"; the publication job is the
  single source of public truth, files are a replayable projection of it.
- Switching production to archive mode now: rejected — cutover requires backup/restore
  rehearsal (1.2.3), ten fixture cycles with fixed clocks including empty/failed/dup/
  revised/pruned inputs (§5.3) and three successful scheduled shadow cycles observed
  in the real service; none of that evidence exists yet.

## Consequences

- g3-ingest gains mode='archive' (default remains legacy); README documents it plus
  bootstrap/replay/mirror-sync entry points for the future runbook.
- Migration 002 adds publication_jobs to every archive DB on next open; shadow-only
  deployments are unaffected in behavior (new table, no new writes).
- 1.2.3 proceeds from this ADR: backup via SQLite online-backup API, restore into a
  fresh directory with integrity/FK/ID/publication-queue verification, cutover config
  and post-cutover rollback rehearsal — none of which is claimed complete here.
