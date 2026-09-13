# Review of Sol's plan — rationale and evidence

Revision 2, 2026-09-09. Scope: plan, handoffs and current-architecture documentation.
No runtime feature, database, service, account, billing or deployment was changed.
Current-code findings came from direct source inspection; no current test-pass
claim is made by this planning revision.

## Findings addressed

| Finding | Evidence / risk | Revision |
| --- | --- | --- |
| Optional fields called backward compatible | event/snapshot schemas have additionalProperties:false; version fixed at 1 | Preserve strict v1; separate intelligence schemas/index/detail artifacts |
| Stable IDs underspecified | runner numeric allocation + nextEventId; URL set skips existing report; live list capped | Persistent UUID mapping, transactional counter, source identities and revision/observation separation |
| Singular source fields on multi-source events | Existing sources[] merges outlets | Many-to-many event evidence to source revisions |
| Blind dual-write and easy rollback | DB commit and file rename cannot share one transaction | Legacy/shadow/archive authority; ordered replayable publication; explicit post-cutover reconciliation |
| Archive too late in pipeline | _cycle deduplicates and slices events before publication | Observe same source batch before dedup/pruning; preserve changed-source text and history |
| New enrichment delivery missing | Existing client fetches only snapshot.json; no production API | Versioned bounded artifacts, event/projection checks and release-order protocol |
| Related event outside live window | Existing selection expects live numeric ID | Bounded target summary with evidence in Part 1; historic API later |
| Correlation could imply certainty | Country centroids, publisher URLs, source count and tone are weak signals | Qualified entity roles; centroid exclusion; lineage/independence; rank ≠ probability |
| Source correction/deletion conflicts with permanent history | Original plan says append-only forever | Versioned corrections, derived invalidation, payload tombstones and rights policy |
| Early customer focus vague | General intelligence audience, paid validation after broad platform | Defined initial customer/task, early interviews and observed repeated workflow |
| Differentiation delayed | Distinctive features at end of Part 2 | Signal Trail preview in 1.3.3 and first release in 1.4 |
| Semantic work looked mandatory | Old build order put embeddings before later core workflow | Optional evaluated branch; no dependency for saved briefs/paid pilot |
| “Unlimited” alerts and cheap archive assumed | Old monetization plan lacked usage economics | Explicit caps, provider rights and contribution/support ledger |
| Paid features could still ship publicly | Static snapshots/artifacts inherently accessible | Separate serializers and server entitlement/cache/export checks |
| Test gates lacked methodology | Precision targets without sample protocol/abstention/independence | Reviewed/held-out fixtures, per-type metrics, coverage and honest provisional results |
| Gates could force repeated approval pauses | “Stop at gate” read as permission barrier | Verify gate, continue within authorized scope; missing decisions remain explicit |
| Historical architecture contradicted active code | ARCHITECTURE described MapLibre; index imports globe.ts | Corrected current-runtime description and future-plan links |
| Handoff too broad for weaker model | One large roadmap, broad template, few ready tasks | START_HERE prompt, task register, precise specification/wire types, three detailed ordered briefs |

## Source-inspection anchors

- shared/schemas/event.schema.json and snapshot.schema.json.
- g3-ingest/sycamore_ingest/contracts.py: keyword/reference whitelist.
- g3-ingest/sycamore_ingest/runner.py: _cycle, _publish, run, _atomic_write.
- g3-ingest/sycamore_ingest/normalizer.py: normalize, dedupe_key, geolocation and score.
- g3-ingest/tests/test_pipeline.py: replay, health, pruning, atomic writes.
- g3-astro/src/client/{refresh,state,dashboard}.ts: fetching and selected-event state.
- g3-astro/src/data/validate.ts: schema/count/ID validation.
- g3-astro/src/pages/index.astro: createGlobe and controls/detail integration.
- g3-astro/src/client/globe.ts: targetFrameRate = 30.
- g3-astro/tests/run.ts: explicit imported test modules.
- g3-astro/scripts/{generate-validator,performance-report}.mjs.
- 00-admin/DECISIONS.md D-023 and HANDOFF-2026-09-07.md.

## External technical references checked

These support limited infrastructure defaults, not competitor superiority or
customer demand. Recheck current versions before actual provider/library choice.

- SQLite online backup API: use a consistent backup/restore method.
  https://www.sqlite.org/backup.html
- PostgreSQL text search: an integrated initial search option.
  https://www.postgresql.org/docs/current/textsearch.html
- PostgreSQL row-security policies: supplemental isolation with role caveats.
  https://www.postgresql.org/docs/current/ddl-rowsecurity.html

## What remains deliberately unresolved

- Which customer segment actually returns and pays.
- Final subscription prices, monthly spend ceiling and provider selection.
- Commercial use/retention/export permissions for every selected source.
- Current runtime baseline and browser measurements.
- Hosting choice, production database sizing and actual served freshness.
- Independently reviewed relation relevance and extraction corpus.
- Whether semantic discovery improves the product at an acceptable cost.

These are explicit tasks/gates, not silent decisions delegated to the next model.
The revision does not promise success; it reduces ambiguous implementation and
makes failure or missing evidence visible early.

## Planning verification

The revision was checked across 13 documents: all local Markdown links resolve,
code fences are balanced, no conflict markers remain, and the register contains
34 unique iteration IDs covering all 12 epochs. Only 1.1.1 is READY. These checks
passed using a read-only Python document/link/register inspection.

Runtime suites were not rerun for this documentation-only revision. Their current
results belong to the baseline iteration; old session test results are not being
reused as current evidence. External technical sources were checked only for the
specific backup/search/isolation defaults documented above.
