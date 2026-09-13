# Iteration register — authoritative task state

Revision 2. All implementation is pending. “Ready” means scoped enough to start,
not that its tests have passed. Only 1.1.1 is ready now.
The project root is /home/yams/operations/project-sycamore.

Every row is an implementation card: work, dependencies, files, deliverable and
acceptance. Read the implementation specification sections cited in the row.
If a later card lacks a detailed brief, use the handoff template to expand it
before coding. Unknown customer/provider/budget decisions are written as pending,
never filled with invented approvals.

## Execution order

Part 1: 1.1.1 → 1.1.2 → 1.2.1 → 1.2.2 → 1.2.3 → 1.3.1 →
1.3.2 → 1.3.3 → 1.4.1 → 1.4.2 → 1.4.3.
1.1.3 can run after 1.1.1 alongside technical work with no overlapping edits.
Recruitment delays do not prevent fixture-based technical implementation.

Part 2 core: 2.1.1 → 2.1.2 → 2.1.3 → 2.2.1 → 2.2.2 (conditional) →
2.2.3 → 2.4.1 → 2.4.2 → 2.4.3.
Skip 2.2.2 when external enrichment is not needed for the observed task.
2.3 is an optional branch from reviewed 1.4.3 results and never a core dependency.

Paid pilot: reviewed repeated use and save intent → 3.1 → 3.3.
3.2 is needed only if alerts are part of the paid offer.
3.4 requires real team/API demand, not just technical completion.

## Part 1 cards

| ID / status | Prerequisite | Ordered implementation and owned files | Required evidence / next |
| --- | --- | --- | --- |
| 1.1.1 COMPLETE (2026-09-10) | None | Follow 1.1.1-baseline.md; inspect contracts/runner/client; create baseline tool, reports and hash manifest only | Both suites recorded (ingest 31 OK, web 21/21, exit 0); identity/serving map filed; limitations explicit; artifacts under performance/intelligence-baseline/ → 1.1.2 |
| 1.1.2 COMPLETE (2026-09-10) | Baseline identity map | Follow 1.1.2-contracts.md; new intelligence schemas/fixtures; identity.py; validator registry and generator; v1 unchanged | Cross-language fixture parity (6 hash vectors identical in Py/JS), IDs survive import/replay, old validator reads old projection; ingest 65 OK, web verify 32/32, exit 0 → 1.2.1 |
| 1.1.3 PENDING | Baseline | Prepare discovery script/task worksheet from MONETIZATION_PLAN; new client measurement adapter default no-op; no provider/contact collection | No article/query/indicator contents in payload; no network from default adapter; customer evidence still pending if no sessions |
| 1.2.1 COMPLETE (2026-09-10) | 1.1.2 | Follow 1.2.1-archive-shadow.md; archive.py, migration SQL, runner mode integration; capture before pruning | Repeated source/revision import, gap reporting, FK/replay tests; legacy output still authoritative; ingest 101 OK, web verify 32/32, exit 0 → 1.2.2 |
| 1.2.2 COMPLETE (2026-09-11) | 1.2.1 | publisher.py; publication_jobs; archive-mode projection and ordered replay; spec §5 | Every §5.2 failure-matrix row green; no lost committed events / ID reuse / mirror repair; archive bootstrap guardrail; ingest 121 OK (101+20), web verify 32/32, exit 0 → 1.2.3 |
| 1.2.3 PENDING | 1.2.2 | tools/archive_admin.py and recovery runbook; backup/restore, shadow comparison, cutover configuration | Ten fixture cycles + restore evidence; actual scheduled cycles before live cutover; post-cutover rollback rehearsed → 1.3.1 |
| 1.3.1 PENDING | 1.2.3 technical gate | entities.py, mention migration, fixtures; extract explicit indicators, source offsets and roles; spec §6 | ≥120 reviewed excerpts or provisional pilot label; per-type precision/recall; publisher-host and Unicode tests → 1.3.2 |
| 1.3.2 PENDING | 1.3.1 | alias/assignment migration + operator correction command; preserve superseded assignments | Alias ambiguity stays unresolved; merge/split reversibility; dependent edges invalidated → 1.3.3 |
| 1.3.3 PENDING | 1.3.2 | client/intelligence.ts, DetailPanel, dashboard/index integration, global.css; static artifacts; Evidence/Entities/history preview | Selection race tests, mismatch fallback, evidence resolution, real viewport/focus review → 1.4.1 |
| 1.4.1 PENDING | 1.3.2 | relationships.py; bounded entity candidate index; configurable versioned rule weights | Hand-computed score fixtures, no all-pairs growth, no repeated/syndicated bonus, honest abstention → 1.4.2 |
| 1.4.2 PENDING | 1.3.3 + 1.4.1 | Related cards/Signal Trail, history and back behavior; artifact publisher | Out-of-window target summary works; changed/retracted evidence visible; public limits; layout/focus matrix → 1.4.3 |
| 1.4.3 PENDING | 1.4.2 | Evaluation runner/report and task worksheet; independently reviewed held-out queries | Metrics/sample counts + reasons; task outcomes; release gate PASS/FAIL/awaiting review → 2.1.1 or repair |

## Part 2 cards

| ID / status | Prerequisite | Ordered implementation and owned files | Required evidence / next |
| --- | --- | --- | --- |
| 2.1.1 PENDING | Part 1 technical release | ADR for HTTP framework/process/auth boundary; API schema/OpenAPI fixture; g3-api minimal read adapter to domain modules | Invalid query/cursor/error contracts tested; no browser-side DB access → 2.1.2 |
| 2.1.2 PENDING | 2.1.1 + hosting/cost decision | Staging serving adapter, database migration, target-database tests, backup/probe runbook | Fixed-copy + catch-up + brief write freeze + ID/revision checksum parity + serving probes; rollback window → 2.1.3 |
| 2.1.3 PENDING | 2.1.2 | Search queries/indexes; web archive client; no full archive download | Search fixtures and stable cursor/asOf tests; 100k synthetic records, declared load, p95 and actual coverage dates → 2.2.1 |
| 2.2.1 PENDING | 2.1.3 | Investigation state schema, local persistence adapter, route and breadcrumb | Reload/back/schema migration; local save deletion/export; no claim of cloud sync; private notes absent from URL → 2.2.3 or 2.2.2 |
| 2.2.2 CONDITIONAL | 2.2.1 + demonstrated missing context | One passive provider adapter with rights/cost metadata, timeout/cache/rate-limit handling | Input allowlist, provider errors, stale result labels, SSRF boundary; no active scanning → 2.2.3 |
| 2.2.3 PENDING | 2.2.1 (provider optional) | Select evidence → deterministic editable brief → downloadable permitted export | Every claim/reference resolves; injection escaped; missing evidence stays missing; removal/correction handled → 2.4.1 |
| 2.3.1 OPTIONAL | Reviewed 1.4.3 corpus | Offline embedding experiment; input/model/version manifests, no public inference yet | Compare against deterministic baseline on held-out data; unit cost and leakage check → skip or 2.3.2 |
| 2.3.2 OPTIONAL | 2.3.1 positive result | Feature-flagged hybrid ranking, separate similarity labels, timeout fallback | Improvement and no unsupported attribution; deterministic fallback → 2.3.3 only if scaling requires |
| 2.3.3 OPTIONAL | Measured retrieval limit | ADR comparing existing DB index with dedicated vector service; migrate only if justified | Load/cost/restore evidence; relational store stays authoritative; otherwise close as skipped |
| 2.4.1 PENDING | 2.2.3 | Refine Signal Trail/source independence and coverage labels from observations | User distinguishes repeated article from independent reporting; delayed source from no incident → 2.4.2 |
| 2.4.2 PENDING | 2.4.1 | “Since last brief” baseline selection and change list; no LLM required | Revisions, corrections and removed items diff correctly; chosen asOf preserved → 2.4.3 |
| 2.4.3 PENDING | 2.4.2 | Four-week repeated-task study/pilot review; prepare offer evidence | Actual returning-user numerator/denominator, useful briefs, interest vs paid commitment separated → 3.1/3.3 or revise |

## Part 3 cards

| ID / status | Prerequisite | Ordered implementation and owned files | Required evidence / next |
| --- | --- | --- | --- |
| 3.1.1 PENDING | Repeat use/save demand + identity ADR | Managed auth adapter; ownership model; private serializers/cache policy; server auth middleware | Cross-user access, expired session, unauthenticated fallback, account deletion/export → 3.1.2 |
| 3.1.2 PENDING | 3.1.1 | Private saved investigations and explicit local-save import | Import idempotency/conflicts; server validation; evidence revision pins + update notices → paid pilot and/or 3.2 |
| 3.2.1 CONDITIONAL | 3.1.2 + alert demand | Rules schema, durable job leases, change evaluator, unique effects key | Crash after send/before ACK, expiry/retry, correction/retraction and source-outage fixtures → 3.2.2 |
| 3.2.2 CONDITIONAL | 3.2.1 | In-app inbox/digest; authorized channel adapter with consent/disable controls | Duplicate/mute/false-positive rates; replays don't resend; actual channel testing authorized |
| 3.3.1 PENDING | Value/pilot evidence + 3.1 | Freeze limited plan features/quotas/price hypothesis; cost ledger and upgrade events | Owner budget and offer documented; no “unlimited” costs; dry-run plan tests → 3.3.2 |
| 3.3.2 PENDING | 3.3.1 + billing provider decision | Billing adapter in sandbox, webhook inbox/reconciliation, entitlement state machine | Authenticity, replay, out-of-order, refund/cancel/grace/provider-down tests; live billing separate release action → 3.3.3 |
| 3.3.3 PENDING | 3.3.2 | Server-enforced quotas on reads/jobs/exports; cache partition; pilot dashboard | Public-data audit, downgrade behavior, daily reconciliation; actual paid cohort retention and contribution → iterate or 3.4 |
| 3.4.1 CONDITIONAL | Team design partners | Organization ownership, invitations, roles, notes, audit | Cross-tenant/role matrix; revocation and member removal; private/public export tests → 3.4.2 if demanded |
| 3.4.2 CONDITIONAL | Scoped API demand | Scoped keys, hash-at-rest, revocation, per-key quota, docs and metering | Replay/abuse limits, key rotation, permission scope, no source-rights bypass → 3.4.3 |
| 3.4.3 CONDITIONAL | Paying professional use | Load targets, restore/incident drill, support ownership and capacity | Stated service commitments supported by measurements; margins include support; no untested SLA |

## Changed scope from Sol's numbering

- 1.1.2 now creates separate intelligence contracts; it does not add fields to v1.
- 1.1.3 includes customer discovery immediately.
- 1.2 uses explicit authority modes and replayable publication, not blind dual write.
- 1.3.3 begins Signal Trail early.
- 2.2.1 permits local saved work before hosted accounts.
- 2.3 is optional; 2.4 and paid pilots never depend on semantic machinery.
- 2.4 and 3.4 now have individually numbered execution cards.
- 3.3 may follow a small validated paid workflow; it need not wait for every alert
  feature or the full future product.

## State updates

Only the active implementation brief contains detailed live execution notes.
After its gate is evaluated, update that row's status here:
READY → ACTIVE → VALIDATING → COMPLETE, or BLOCKED/FAILED.
Conditional work may become SKIPPED with a written reason; skipped means not
built and never satisfies a dependency that actually requires its output.

Release state is separate: local verified / staging verified / pilot / production.
Do not turn COMPLETE into “deployed” without served evidence.
