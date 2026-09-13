# Intelligence implementation specification

Revision 2. Proposed implementation contract, not implemented functionality.
Read with the [roadmap](../01-strategy/INTELLIGENCE_PLATFORM_ROADMAP.md).
Paths below are relative to project-sycamore. New files are explicitly labeled.

## 1. Mandatory invariants

1. Existing numeric event IDs, query links, legacy hashes and static board routes
   remain resolvable. Never renumber imported events.
2. `/data/snapshot.json` remains strict version 1. No extra event/envelope keys.
3. A successful empty source response, a failed response and an unconfigured
   optional source are distinct states.
4. `lastSync` denotes successful source checking. New observation, publication
   and enrichment clocks must not overwrite its meaning.
5. A report, an incident, an entity mention and a relationship are different
   records. Similar reports do not establish one incident or causation.
6. Every displayed enrichment references stored evidence and its source revision.
7. Missing coordinates remain missing internally. Map placement requires existing
   geolocation policy. An organization headquarters is not an incident location.
8. Existing archive ingestion, enrichment, telemetry and publication failures have
   separate health. None may be reported as a successful fresh update.
9. Private user notes and paid-only data never enter public snapshot/artifact files.
10. Tests operate on fixtures and temporary output, never the installed service's
    live output. A documentation revision is not authorization to deploy.

## 2. File ownership and construction sequence

| Boundary | Existing entry points to inspect | Proposed files to create when iteration authorizes |
| --- | --- | --- |
| Contracts | shared/schemas/{event,manifest,snapshot}.schema.json; g3-ingest/sycamore_ingest/contracts.py | shared/schemas/intelligence/*.schema.json; shared/fixtures/intelligence/ |
| Web validation | g3-astro/scripts/generate-validator.mjs; src/data/validate.ts | src/data/intelligence.ts; generated-intelligence-validator.js and declaration |
| Identity | runner.py _cycle; normalizer.py normalize/dedupe_key | sycamore_ingest/identity.py |
| Archive | runner.py _load_previous/_publish/run | sycamore_ingest/archive.py; migrations/001_archive.sql |
| Publication | runner.py _atomic_write/_publish | sycamore_ingest/publisher.py |
| Extraction | normalizer.py; contracts.py | sycamore_ingest/entities.py; tests/test_entities.py |
| Correlation | new domain module | sycamore_ingest/relationships.py; tests/test_relationships.py |
| Drawer | src/client/dashboard.ts; render.ts; components/DetailPanel.astro; pages/index.astro | src/client/intelligence.ts; tests/intelligence.test.ts |
| API, later | domain modules above | g3-api/ after 2.1.1 ADR; no API in Part 1 |
| Operational tools | tests/test_pipeline.py; scripts/performance-report.mjs | g3-ingest/tools/baseline.py; tools/archive_admin.py when authorized |

Do not move the working ingestion package or rename the active g3 directories.
Do not edit generated validators manually. New web test modules must be imported
from tests/run.ts; a new file alone is not automatically executed by that runner.

## 3. Public compatibility and artifact protocol

### 3.1 Preserve the old boundary

Freeze representative old snapshots AND their validator behavior in fixtures.
Internal enrichment records use their own schema namespace. Do not widen the
v1 schema as a shortcut. A future v2 snapshot requires a different endpoint and
a separate reader migration.

The Python validator currently only resolves event.schema.json and
manifest.schema.json references and supports a limited keyword set. New
intelligence validation must use an explicit registry of trusted local schemas;
never resolve arbitrary file paths or URLs from $ref. Keep unknown assertions
failing closed. Add parity fixtures before adding a keyword or reference.

Define each intelligence schema with bounded strings/arrays and
additionalProperties:false. Foreign keys and cross-record consistency checks
are application invariants, not assumed JSON-schema behavior.

### 3.2 Part 1 static enrichment delivery

Exact nested fields, bounds, null semantics and reference checks are in
[Part 1 wire shapes](INTELLIGENCE_WIRE_SHAPES.md). Implement these as schemas in
1.1.2; do not invent different nested payloads from the abbreviated lists below.

New endpoint shapes (proposed; absent endpoints mean feature unavailable):

- /data/intelligence/v1/index.json
- /data/intelligence/v1/releases/<releaseUid>/events/<eventUid>.json

Index fields:
`schemaVersion:1, releaseUid, generatedAt, snapshotHash, entries[]`.

Each entry:
`eventId, eventUid, eventRevisionUid, projectionHash, artifactPath`.

Detail fields:
`schemaVersion:1, releaseUid, eventUid, eventRevisionUid, projectionHash,
generatedAt, evidence[], entities[], timeline[], related[], truncated`.

Relation cards carry a bounded target summary, target UID and source links so a
related target outside the 500-event live window is not a dead link. In Part 1,
render that bounded summary inside the drawer; do not call the legacy selection
handler with a missing numeric ID. Full historic navigation arrives with the API.

Hash definition: SHA-256 over canonical JSON (UTF-8, object keys sorted recursively,
no whitespace, original array order, reject non-finite numbers). Supply cross-language
fixtures including accented text and fractional coordinates. The v1 projection
hash includes the whole selected v1 event; the source-content hash below has a
different purpose. If parity is hard, fix the algorithm/fixtures; do not disable
the comparison.

Reader algorithm:

1. Render the ordinary event immediately.
2. On an intelligence-view request, fetch and validate the small index.
3. Find the selected numeric ID and compare its projectionHash with the current
   v1 event. A missing/mismatched entry means “intelligence updating.”
4. Fetch only the same-origin allowlisted artifactPath.
5. Validate schema, release UID, event/revision IDs and projection hash.
6. Recheck selection/request token before rendering. Ignore a late response for
   another event. Cancel requests on selection change/page teardown.
7. On failure, keep Overview usable; offer one manual retry. No retry loop.
8. Mark empty results distinctly from failed/unavailable/stale results.

The snapshotHash is diagnostic for release consistency; do not hide all unchanged
events merely because a health-only snapshot update changes the full hash.

Bound initial history to 20 timeline entries, 20 entities, 20 evidence references
and five related cards; show truncation explicitly. Never silently imply a full
history. Every reference displayed must resolve within the artifact or to an
approved source URL. Public artifacts only include fields allowed for public
redistribution.

### 3.3 Publishing order and CDN behavior

Build a release in a non-public staging directory. Validate the complete
reference graph and payload limits. Publish immutable detail artifacts first,
then atomically replace v1 snapshot, then replace intelligence index. Finally
repair compatibility mirrors. A crash between these steps produces missing or
mismatched enrichment; the reader algorithm handles it without mixing evidence.

Local rename is not CDN publication. In the serving adapter: upload/verify immutable
artifacts, update mutable snapshot/index, and probe the served hashes and cache
headers. Record publishedAt separately from ingest completion. Keep previous
releases through the declared cache/rollback window; initial target seven days
with usage monitoring. Revocations/takedowns override ordinary cache retention.

Mutable snapshot/index revalidate; immutable artifacts may be cached only as
permitted by source policy. Deleting local files does not purge CDN copies.
Record a serving-level removal/purge procedure before public distribution.

## 4. Identity, time and database model

### 4.1 Identity rules

Use assigned UUIDs for eventUid and immutable revision IDs. Their persistence,
not a hash of a mutable title/location, makes identity stable.

Import each existing numeric ID once into a unique mapping to eventUid. Record
the import manifest/checksum so reruns reuse the same mapping. Allocate new
numeric IDs from a transactional counter initialized to at least both the
maximum imported ID + 1 and the existing manifest.nextEventId. Never recycle
IDs, including after deletions or restoring an older backup; reconcile the
counter with the latest surviving published/import manifest before resuming.

ProviderUid comes from a checked-in provider registry, not an arbitrary display
name. Source record natural key = provider UID + provider-native record ID when
available, otherwise provider UID + canonical source URL. Store a unique
constraint for this key. Store original URL separately. Normalize only scheme/
host case, default ports and fragments initially; preserve path/query semantics.
Any tracking-parameter rules require provider-specific fixtures.

One source record can have multiple immutable revisions; one event can cite many
source records. Therefore sourceRecordUid and providerUid are not single fields
on a canonical event. Two providers syndicating one article remain two observations
but may belong to one reporting-origin group.

Identical content seen again updates observation history/lastSeen, not the
semantic event revision. A changed headline/summary becomes a source revision.
Do not create a new event just because the title changed at the same URL.
Event merge/split corrections are explicit operations with lineage and aliases;
relationships never silently merge events.

### 4.2 Minimum tables (logical schema; implement SQL in 1.2.1)

All times are UTC milliseconds to match current data. FKs are enforced. Use
explicit transactions. Only create tables needed by the active iteration.

| Table | Key fields and constraints | Purpose |
| --- | --- | --- |
| providers | provider_uid PK, display_name, policy_version | Stable source registry |
| source_records | source_uid PK, provider_uid FK, natural_key UNIQUE, original_url, canonical_url | Identity across fetches |
| source_revisions | revision_uid PK, source_uid FK, content_hash, published_at nullable, observed_at, allowed_payload, UNIQUE(source_uid,content_hash) | Immutable changed source text/metadata |
| source_observations | run_uid + source_uid + revision_uid UNIQUE, observed_at | Repeated observations without duplicate revisions |
| events | event_uid PK, legacy_id UNIQUE nullable, current_revision_uid, status | Canonical event identity |
| event_revisions | revision_uid PK, event_uid FK, semantic_hash, created_at, permitted_payload, normalization_version | Material changes, including corrections |
| event_evidence | event_revision_uid + source_revision_uid UNIQUE, role | Many-to-many provenance |
| identity_counters | name PK, next_value | Transactional legacy ID allocation |
| ingest_runs | run_uid PK, started_at, finished_at, outcome, counts, last_success | Source-check history |
| source_health | run_uid + provider_uid UNIQUE, state, error_code, observed_at | Per-provider success/empty/failure/skipped |
| publication_jobs | publication_uid PK, sequence UNIQUE, run_uid FK, payload_hash, payload_or_reference, state, attempts | Replayable publish intent |
| entities | entity_uid PK, kind, canonical_value, UNIQUE(kind,canonical_value) | Qualified entities |
| mentions | mention_uid PK, source_revision_uid FK, field, start, end, raw_text, normalized_value, role, method_version, resolution_state | Evidence-backed extraction |
| entity_assignments | assignment_uid PK, mention_uid FK, entity_uid FK, supersedes_uid nullable, reviewed_at | Reversible resolutions |
| relationships | edge_uid PK, left_revision_uid, right_revision_uid, kind, method_version, rank_score, reasons, computed_at, status | Versioned derived results |
| corrections | correction_uid PK, target_uid, action, reason, supersedes_uid, created_at | Merge/split/retraction/tombstone audit |

Tables involving entities and relationships are added in 1.3/1.4 migrations.
Append-only history is subject to source retention and deletion policy: use a
tombstone and permitted minimal audit record when payload removal is required;
do not promise permanent storage of every payload.

Time meanings:
- publishedAt: source-stated time; unknown stays null.
- firstSeen/lastSeen: observation timestamps, not backdated to article publication.
- updatedAt: material normalized content change.
- enrichmentComputedAt: derived result generation.
- publishedAt on a release: successful delivery boundary.
- source/source-revision timestamps never imply incident occurrence time.

Semantic hash excludes lastSeen and continuously recalculated freshness/confidence
so every polling cycle does not manufacture a “new development.”

## 5. Archive migration and crash recovery

### 5.1 Modes

`legacy`: current pipeline publishes v1; no DB authority.
`shadow`: current pipeline publishes v1; archive observes the SAME fetched batch
before source dedup/pruning. A shadow failure is reported but does not stop legacy
publication. It creates a coverage gap that must be reconciled before cutover.
`archive`: DB is authoritative; publisher derives v1 from committed state.

Do not fetch external sources twice for shadow comparison. Do not install/change
the actual timer while developing these modes.

### 5.2 Archive-mode transaction/publisher

Pseudocode describes required ordering, not code to paste untested:

    acquire existing writer lock
    fetch providers outside DB transaction, with bounded timeouts
    begin transaction
      store run/source health and permitted source observations
      resolve source identities and new source revisions
      update event evidence/revisions; preserve numeric IDs
      compute current v1 projection (latest 500 accepted map events)
      validate projection; retain all archived source/event history
      insert immutable publication payload + monotonic sequence
    commit transaction
    publish pending sequences in order (single publisher)
      validate payload again
      write + fsync temp file; atomic replace; sync directory as appropriate
      replace/repair legacy mirrors
      acknowledge completed publication in a DB transaction
    release lock

Enrichment runs after canonical commit in its own retryable job. It cannot delay
source persistence or block Overview.

Failure cases and expected behavior:

| Failure | Expected recovery |
| --- | --- |
| Before DB commit | Roll back; previous public snapshot stays valid; attempt failure visible operationally |
| After DB commit, before file replace | Pending publication survives; replay without fetching sources |
| After snapshot replace, before acknowledgement | Repeating the same job is harmless; verify payload/hash and repair mirrors |
| Mirror write fails | Canonical snapshot remains committed; repair mirrors; never restore an older snapshot |
| Multiple pending jobs | Publish in increasing sequence; never regress to an older payload |
| Total source failure | Keep previous events/lastSync; record attempt and error health |
| Enrichment fails | Archive and v1 continue; derived view says unavailable/stale |
| Disk full | Do not overwrite last-good snapshot; emit actionable error; retry after capacity restored |
| Shadow archive gap | Reconcile retained observations or disclose unrecoverable gap; no “continuous archive” claim |

Do not assume two writes to JSON and DB are one transaction.

### 5.3 Cutover and rollback

Before cutover: snapshot backup + DB consistent backup + media/reference inventory;
stable-ID mapping report; compare fixed-clock projections for at least ten
fixture cycles including empty, failed, duplicate, revised and pruned inputs.
During compatibility comparison, use a versioned legacy projection policy that
preserves the existing selected headline/summary, sort order and count semantics.
The archive may record a changed source revision even when the legacy reader
would have skipped that URL; this alone must not change the comparison projection.
Capture those source changes in history. Updating the public selected headline
or severity is a separate reviewed projection-policy change with an explicit
expected-differences fixture; never normalize unexplained differences away.
For real serving release, also observe three successful scheduled shadow cycles
and record source-coverage gaps. A fixture run does not substitute for these.

Rollback before cutover: disable shadow mode, preserve DB for diagnosis.
Rollback after cutover: stop the writer/publisher; keep last valid served
projection and DB; repair/replay forward where possible. Do not simply resume
the old JSON writer and let two authorities diverge.

Emergency legacy operation, if necessary: export a validated latest v1 plus
high-water ID from DB, freeze/archive the DB at a recorded sequence, run one
legacy writer, then import its intervening records/ID allocation as a documented
reconciliation before restoring archive authority.

Use a consistent SQLite backup API rather than copying only the live database
file. Restore into a fresh directory; verify integrity/FKs, IDs, event count,
latest revision, publication queue and regenerated v1 payload.
[SQLite online backup documentation](https://www.sqlite.org/backup.html).

## 6. Extraction and correlation rules

### 6.1 Evidence roles

Extraction input: licensed source title/lede/structured subject fields.
The article's host is a publisher entity, not incident infrastructure. Distinguish
`subject`, `publisher`, `mentioned`, `affected` and `uncertain` roles.

Retain a valid private/reserved IP mentioned in evidence with its address-scope
label; do not present it as a globally routable asset or perform public lookups.
Do not silently erase source evidence because an indicator is not queryable.

Source offsets use Unicode code-point indices, start inclusive/end exclusive,
over stored source-revision text before normalization. Supply accented/non-BMP
fixtures and a JS code-point-to-string-offset helper if highlighting uses offsets.
If the text is unavailable, label metadata-only provenance; never invent a quote.

Organization aliases must be reviewed mappings, not fuzzy auto-merges. Similar
names create unresolved candidates. A correction invalidates/recomputes derived
edges and related summaries; existing saved briefs show that cited evidence changed.

### 6.2 Deterministic ranking v1

Candidate generation uses inverted entity indexes, not all-pairs event comparison.
Take at most 200 eligible candidates per selected event. Default same-entity
window 30 days; CVE history up to 365 days. Show these limits in evaluation.

Initial rule configuration, versioned and evaluated before release:

- exact CVE in subject evidence: 60 points;
- exact subject domain/IP/ASN: 50;
- explicitly resolved subject organization: 35;
- same incident category: +10;
- source publication within 7 days: +10;
- same qualified region: +5.

Take the strongest exact-entity base rather than summing repeated mentions.
Return only edges with a qualifying subject-entity base and score ≥45. Top five,
ties broken by source time then stable ID. Generic entities shared by >20% of
the evaluated corpus cannot be the sole base. Missing evidence means abstain.
Weights/thresholds are hypotheses; record changes in the evaluation artifact.

Country centroid distance cannot strengthen a factual link. Geography/time-only
results may later appear in a separate “nearby reporting” section; not as an
evidence-backed relationship. Unknown source independence provides no
corroboration bonus. Syndicated copies remain one known reporting-origin group.

Store reasons such as `shared_subject_cve`, entity UID, source-revision IDs and
method version. Score means ranking, not probability or truth. Public copy:
“Both reports mention CVE-…”, not “same attacker” or “80% confirmed.”
Do not rank on negative tone as evidence of incident severity.

### 6.3 Evaluation, not self-certification

Create at least 120 reviewed source excerpts covering all four topics and
structured indicator positives/negatives, publisher-host traps, homonyms,
private IPs, missing locations, syndicated stories and corrections.
Track fixture permission/provenance. Synthetic adversarial cases supplement
real reviewed cases; report their scores separately.

Use at least 40 query events for relation evaluation, including 10 where no useful
related event exists. Group near-duplicates and revisions before a 60/20/20
train/development/held-out split to avoid leakage. Freeze held-out IDs/checksums.
If data is too small, mark results provisional and use a pilot, not a broad claim.

An independent reviewer or domain-informed owner reviews ground truth. The
implementation model may propose labels but cannot claim independent review
of its own labels. Report disagreements and adjudication.

Metrics:
- mention precision = correct accepted mentions / all accepted mentions;
- recall = correct accepted / all labeled eligible mentions;
- P@3-returned = relevant returned cards / returned cards, capped at 3/query;
- coverage = queries with ≥1 returned card / all queries;
- eligible coverage = queries with a labeled useful target and ≥1 relevant return
  / queries with a labeled useful target;
- slot precision = relevant returned / (3 × query count), diagnostic, no padding;
- reason correctness and unsupported-attribution count, plus per-topic breakdown.

Initial release gate: precision ≥95%, P@3-returned ≥80%, eligible coverage ≥50%,
zero unsupported attribution claims, and 100% resolvable evidence references.
Report sample counts and uncertainty; targets do not imply statistical assurance.
If insufficient reviewed data exists, ship only an explicitly limited pilot.

## 7. UI state and accessibility contract

Use one reducer for drawer mode:
`closed | controls | event(overview/evidence/entities/related/timeline) | region`.
Feed/map mobile state remains separate. Opening another drawer mode replaces the
active surface; back navigation restores the previous event context. On desktop
the feed may coexist in its own reserved column. Avoid more fixed offsets.

Reuse existing close/selection/fullscreen handlers in dashboard.ts. Integrate
the dynamically constructed map controls in index.astro rather than creating a
second conflicting controller. No direct DOM hidden toggles outside the adapter
that dispatches/reflects state after migration.

Test at 1440×900, 1024×768, 980×720, 979×720, 390×844 and 844×390, plus 200% zoom.
Check controls open → event open → related pivot → back → close; region selection;
feed/map changes; native/presentation fullscreen; long headlines; empty and
unavailable enrichment; browser Back; no WebGL and refresh during selection.

A real rendered browser check must verify no unintended rectangle overlap or
clipped controls, tab order, escape/close, focus return, readable scroll areas and
bottom safe-area space. Desktop nonmodal panes must not trap focus; mobile modal
detail must. Screenshots alone do not test focus; DOM tests alone do not test layout.
If browser unavailable, mark visual gate blocked and keep feature unapproved for
release; continue independent work.

## 8. API, private data and later operations

Proposed endpoint contract:
- GET /api/v1/events?cursor=&limit=20&q=&topic=&from=&to=
- GET /api/v1/events/<uid>
- GET /api/v1/events/<uid>/intelligence
- GET /api/v1/entities/<uid>
- GET /api/v1/entities/<uid>/timeline?cursor=
- saved investigations, alerts and exports added only with authenticated ownership.

List envelope: `schemaVersion, items, nextCursor, asOf`.
Error envelope: `error:{code,message,requestId}`; no raw provider error bodies.
Limits: max 100 records/page, q ≤200 characters, bounded date interval, request
timeout, prepared SQL and per-principal quotas. Cursor binds query filters and
stable (time,UID) ordering to asOf; reject altered/incompatible cursors.

Private responses use no shared cache and server ownership/entitlement checks.
Public metadata and member-only payloads have separate serializers. Downloads
and exports repeat entitlement checks, not just the visible page. Scope signed
share links to explicitly chosen content, expiry and revocation; never put
private query text/notes into ordinary URLs.

Managed auth/billing providers and prices remain decisions in Part 3. No custom
password storage. Provider webhooks must verify authenticity, deduplicate event
IDs, handle out-of-order state by reconciliation, and invalidate relevant caches.
A replay must not extend a subscription or deliver an alert twice.

Durable jobs: queued → leased → succeeded, or retry_wait/dead.
Store attempts, nextAttemptAt, leaseExpiresAt and idempotency key. Retry transient
failures with bounded backoff/jitter; do not retry invalid input indefinitely.
Delivery may be at-least-once: deduplicate user-visible effects.

PostgreSQL row security may support tenant isolation but is not a substitute for
API authorization; table owners and privileged roles need careful treatment.
Test with the real application role.
[PostgreSQL row-security documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).

Before hosted cutover, produce a runbook for deploy, backup/restore, stale sources,
stuck jobs, exhausted quotas, bad releases, compromised keys and user-data export/
deletion. Run one restore rehearsal; report source-observed-to-served lag.
Revalidate provider/library documentation and costs when selecting dependencies.
