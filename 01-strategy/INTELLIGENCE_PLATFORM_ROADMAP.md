# Sycamore Intelligence Platform Roadmap

Revision: 2 — Astra review of Sol's plan, 2026-09-09.
Status: planning complete; implementation gates have not been executed.
Owner: project owner. Implementers: one coordinating model plus scoped contributors.

## Start here

This is the delivery sequence. Read the linked specification for implementation
rules and the active brief for the exact next task.

- [Implementation specification](../03-architecture/INTELLIGENCE_IMPLEMENTATION_SPEC.md):
  identity, evidence, storage, publication, APIs, evaluation and recovery.
- [Iteration register](../03-architecture/iterations/REGISTER.md):
  dependencies, file ownership, outputs, tests and state for every iteration.
- [Handoff protocol](../03-architecture/iterations/README.md):
  how to start, resume, verify and close work.
- [First implementation brief](../03-architecture/iterations/1.1.1-baseline.md):
  inspect and measure the current application safely.
- [Commercial validation](MONETIZATION_PLAN.md):
  customer hypothesis, pilot gates, packaging and economics.
- [Revision rationale](../03-architecture/PLAN_REVIEW.md):
  findings and corrections to the earlier plan.

This revision supersedes Sol's roadmap and handoff instructions. Existing
iteration numbers are retained where possible; REGISTER explains changed scope.
Proposals below are engineering defaults, not claims that features or customer
validation already exist. External deployment, purchases and customer messages
need authorization in the session that performs them.

## Product promise and first customer hypothesis

**Understand what changed, trace the evidence, and explain its relevance.**

The first customer hypothesis is an independent analyst or small security/risk
team preparing recurring cyber and geopolitical briefs. Their task is to move
from scattered reports to a defensible update about a watched organization,
region or infrastructure dependency. This is a hypothesis to test in Part 1;
the general public map remains the discovery surface.

The first distinctive experience is **Signal Trail**: an event's reporting
history, new evidence, corrections, source dependence and related events in one
drawer. An analyst should be able to answer “what is new since I last checked?”
and produce a short cited brief. The defensible advantage would accumulate in
clean historical records, reviewed entity resolution, correction history and
saved analyst workflows. A graph or globe alone does not establish uniqueness.

Do not claim competitor absence, a market moat, revenue or user demand without
current evidence. Earlier OSIRIS comparisons are inspiration, not requirements.

## Current facts and constraints

Verified by source inspection during this revision; tests and runtime measurements
remain tasks for 1.1.1:

- Astro + TypeScript renders a static application; index initializes
  `src/client/globe.ts` and Cesium. Preserve accepted imagery, water/night effects,
  camera behavior, attribution, reduced motion and the 30 fps target.
- Python ingest uses a file lock, validates records, caps the live list at 500,
  then publishes canonical snapshot JSON followed by compatibility mirrors.
- Event IDs are numeric; `nextEventId` persists their high-water mark. Existing
  links, routes and selections depend on them.
- Snapshot version is fixed at 1 and event/snapshot schemas reject unknown fields.
  Adding an optional property to new schemas does NOT make old validators accept it.
- Source URLs already seen in the current snapshot are skipped. Revisions to the
  same article and identity after pruning need deliberate archive behavior.
- Flights and Censys have independent envelopes; telemetry is not automatically
  a news event. Preserve that separation.
- Local file publication does not prove freshness at a deployed CDN.
- The old architecture document's MapLibre description is stale. This roadmap
  and the corrected current architecture document distinguish current from target.
- No usable Git metadata was available in this checkout during review; use a
  source hash manifest when a revision cannot be recorded.

## Delivery rules

Part = major product outcome. Epoch = releasable capability. Iteration = bounded
implementation and review unit, ordinarily one coherent change.

Workflow: inspect → record scope → implement → test failures → measure →
review gate → update handoff. Continue to the next authorized iteration when
the gate passes; a gate is not an automatic permission question.
Never mark “complete” from a plan, a previous model's assertion or tests that
ran against a different source state.

Near-term work has detailed briefs. Later work has scoped cards that must be
expanded using newly observed customer and system evidence before coding.
This avoids pretending today's choices can specify every future service.

Every user-facing iteration includes empty, loading, stale, error, corrected and
restricted states; keyboard/focus and mobile behavior; a feature fallback; and a
bounded measurement of whether the change helps.

## Part 1 — Reliable memory and the first distinctive release

Release outcome: open an event → see its Signal Trail → inspect a useful related
event → verify the original evidence. Achieve this on the static application,
with no production API required.

| Epoch | Iterations and deliverables | Exit gate |
| --- | --- | --- |
| 1.1 Baseline and contracts | 1.1.1 current-system baseline; 1.1.2 identity/evidence schemas and v1 projection; 1.1.3 customer discovery kit and local measurement interface | Existing v1 fixtures remain valid; producers/consumers mapped; evaluation rubric and customer hypothesis recorded |
| 1.2 Durable memory | 1.2.1 SQLite archive in shadow mode; 1.2.2 replayable snapshot publication; 1.2.3 cutover and recovery rehearsal | Capture before pruning; retries don't duplicate records; revisions survive; restore and publication recovery demonstrated |
| 1.3 Evidence and entities | 1.3.1 structured extraction and reviewed corpus; 1.3.2 reversible alias resolution; 1.3.3 Evidence/Entities and Signal Trail preview | Provenance for every displayed assertion; reviewed extraction metrics; no panel collisions |
| 1.4 Related Intelligence v1 | 1.4.1 deterministic ranking; 1.4.2 Related view and complete Signal Trail; 1.4.3 held-out relevance and user-task evaluation | Useful recommendations with honest abstention; old feed-to-source workflow works; first release evidence package |

### Key implementation choices

Preserve the strict public v1 snapshot. Put new identity/evidence/history fields
in internal records and separate versioned intelligence artifacts. Old clients
continue using v1. New clients fetch enrichment only when needed and validate
that it belongs to the selected event revision.

SQLite is the first real archive for the single-writer local pipeline, not a
throwaway fake of PostgreSQL. Do not maintain two production database adapters
without need. Capture source observations before deduplication/pruning; project
only accepted map events to v1. Records without trustworthy location may be
retained privately for analysis, but must not gain fabricated map coordinates.

Start with CVEs, explicitly mentioned domains/IPs/ASNs, and qualified locations.
Do not infer subject infrastructure from the publisher's URL. Do not infer
physical proximity from country centroids. Retain ambiguous entities unresolved.

Make Signal Trail available as soon as revisions exist. Show publication time,
observation time and changes separately. Source-count growth is not necessarily
new independent evidence.

### Part 1 product and commercial gate

Observe the task with a small target-user sample using the protocol in
MONETIZATION_PLAN. Prepare materials locally; record observations only when
actual sessions occur. Technical implementation can continue while recruitment
is pending, but the commercial gate remains “awaiting evidence.”

First-release scope excludes semantic search, a general reconnaissance toolbox,
subscriptions, team workspaces and large source expansion. The release itself
must already demonstrate the intended differentiation.

## Part 2 — Investigation that earns repeat use

Release outcome: find historical evidence, follow a subject through time, save
a local investigation and assemble an editable cited change brief.

| Epoch | Iterations and deliverables | Exit gate |
| --- | --- | --- |
| 2.1 Archive access | 2.1.1 API contracts/service boundary; 2.1.2 production storage decision and staging release; 2.1.3 paginated archive search | Contract/load tests on target database; restore drill; healthy freshness at actual serving boundary |
| 2.2 Investigation | 2.2.1 local saved investigation and breadcrumb state; 2.2.2 one demand-backed passive provider pivot; 2.2.3 cited brief/export | Users complete event → entity → history → brief; export contains correct evidence and timestamps |
| 2.3 Optional semantic discovery | 2.3.1 offline comparison; 2.3.2 bounded hybrid ranking if useful; 2.3.3 index sizing decision only if needed | Held-out improvement without provenance regression; measured cost budget; may be skipped |
| 2.4 Product pilot | 2.4.1 refine Signal Trail/Coverage display; 2.4.2 “what changed” brief workflow; 2.4.3 repeat-use and willingness-to-pay decision | Observed repeat task completion and credible paid-pilot interest |

### Infrastructure transition

Retain Astro/Cesium. Introduce one Python API process reusing the ingestion
domain modules, plus a worker process and one primary database. A same-origin
proxy routes `/api/v1/` to the service; public snapshots remain separately
cacheable. Proposed packaging lives in `g3-api/`; choose and pin the HTTP
framework through an ADR in 2.1.1 after a small contract spike.

Before public multi-user service, prefer managed PostgreSQL if backups,
concurrency and operations justify the cost. SQLite remains viable for the local
single-operator release. PostgreSQL-specific migrations and integration tests
must run on PostgreSQL, not only on SQLite. Retire the old production adapter
after the migration window; keep portable fixtures.

Use database text search first. PostgreSQL supports integrated text search;
a separate search cluster is a later measured decision.
[PostgreSQL text-search documentation](https://www.postgresql.org/docs/current/textsearch.html).

Scheduled enrichment initially uses a durable jobs table with leases, bounded
retries and idempotency keys. Queues, graph databases, microservices, Kubernetes
and dedicated vector services are not prerequisites for this plan.

Semantic work is optional and never blocks saved investigations, briefs,
customer pilots or monetization. Rule-based change briefs can launch first.

## Part 3 — Paid reliability and professional workflows

Release outcome: a small paid product with enforceable access, useful saved work,
reliable alerts and observable costs.

| Epoch | Iterations and deliverables | Exit gate |
| --- | --- | --- |
| 3.1 Accounts and saved work | 3.1.1 identity/ownership boundary; 3.1.2 migrate local saves to private server saves | Cross-user isolation; deletion/export; anonymous dashboard survives auth failure |
| 3.2 Alerts | 3.2.1 rules and leased jobs; 3.2.2 in-app inbox, then authorized delivery channels | No duplicate effects on retry; corrections propagate; stale feeds cannot trigger false “all clear” |
| 3.3 Paid pilot | 3.3.1 plan caps and price experiment; 3.3.2 billing lifecycle; 3.3.3 server enforcement and pilot review | Signed/replayed/out-of-order billing events handled; cache isolation; measured retention and costs |
| 3.4 Conditional team/API expansion | 3.4.1 ownership/roles/audit; 3.4.2 scoped API/metering; 3.4.3 service readiness | Demand from actual design partners; tenant isolation; cost and support capacity |

Paid pilot need not wait for all alerts or all Part 2 features. Once historical
evidence, saved briefs and repeat use create paid value, 3.1 and 3.3 may proceed.
Team/API work is explicitly conditional.

Public static artifacts must contain only the public entitlement tier.
Hiding a paid history panel while shipping its data in a public JSON file is
not access control. Protected responses and exports require server checks,
private cache rules and bounded query/export jobs.

The free live feed remains useful with source links and essential context.
Charge for demonstrated archive depth, saved workflows, controlled alerts and
exports, with provider costs and support effort measured.

## Release budgets and stop/continue decisions

These are proposed initial engineering targets, not measured performance or
market facts. Record hardware, fixture size, sample counts and uncertainty.
Freeze targets before evaluating results; change them through a documented
decision, never to conceal a miss.

- Part 1: no unplanned v1 payload growth; intelligence detail target ≤150 KiB
  uncompressed per selected event, at most five initial related cards.
- UI: retain the accepted 30 fps target under comparable globe workload; investigate
  >10% degradation in baseline frame time or interaction latency. Real browser
  evidence is required for layout gates; a build is not screenshot verification.
- Extraction: ≥95% precision on eligible structured mentions, with recall and
  unresolved rates reported per type.
- Related recommendations: ≥0.80 precision among returned top-three cards on
  independently reviewed held-out queries; report coverage and missing slots
  separately so abstaining on every event cannot pass.
- API staging: target p95 ≤500 ms for bounded warm reads and ≤1 s for archive
  search under a declared load (start at 10 concurrent readers, 100k fixture events).
  Measure cold performance separately; public promises follow real evidence.
- Recovery: initial staging targets RPO ≤24 h and RTO ≤4 h; tighten before offering
  service commitments. Crash replay must lose no committed DB transaction.
- Costs: measure bytes retained per record, provider usage per ingest/user task,
  worker runtime, export size and monthly spend projection. Commercial ceilings
  are set with the owner before provisioning or paid pilot.
- Never present a synthetic 90-day load fixture as 90 days of collected history.

If technical quality fails, keep the feature off and fix the failing slice.
If user value fails after two documented workflow revisions, reconsider the
customer/task before expanding infrastructure. If semantic work fails evaluation,
skip it. If paid conversion fails, revise offer and customer hypothesis using
recorded reasons; adding more map layers is not the default response.

## Continuity and authority

The register is the single task-state index. Each active brief records exact
files, commands, source hash/commit, last successful step and next action.
Roadmap gates are outcomes; historical architecture notes are evidence, not
permission barriers to user-authorized development.

Implementation starts at 1.1.1. This revision does not claim that the baseline,
archive or any customer gate has already passed.
