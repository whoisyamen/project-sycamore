# Commercial validation and monetization

Revision 2. All customers, prices and conversion targets below are hypotheses.
No interviews, sales, billing integration or revenue are claimed.
Delivery sequence: [roadmap](INTELLIGENCE_PLATFORM_ROADMAP.md).
This replaces earlier assumptions about unlimited alerts and automatic archive value.

## 1. First customer and job

Working hypothesis: independent analysts and small security/risk teams producing
recurring cyber/geopolitical updates. A concrete job:
“Tell me what changed around a watched subject, let me verify it, and help me
deliver a short defensible brief.”

The public map attracts readers; the paid workflow saves repeated analyst effort.
Customer validation must begin in Part 1. Do not wait for a year of infrastructure
work, a giant graph or 90 days of historical storage to find out whether anyone
needs the workflow.

Alternative segments to test only if the first hypothesis fails: journalists
tracking a developing story, or small organizations monitoring regional exposure.
Do not design all three workflows simultaneously.

## 2. Discovery kit — build in 1.1.3

Prepare locally:
- interview script;
- five-event demo containing a revision, a duplicate/syndicated report, an
  uncertain entity and a meaningful related event;
- task worksheet and timing rubric;
- observation sheet with anonymous participant code;
- separate evidence ledger for interview, usage and payment evidence.

Target 8–12 relevant conversations initially; this is a small directional sample,
not market validation. Actual outreach/contact collection requires authorization.
Pending recruitment is recorded as pending, not “no demand.”

Script:
1. What report or decision did you prepare most recently?
2. Walk through the sources and tools you used, and the time each step took.
3. Where did conflicting reports or repeated stories cause extra work?
4. What did you save, share or have to reconstruct later?
5. Who benefits, who uses the tool, and who can approve paying for it?
6. Ask the participant to complete the same brief task with their current method
   and with Sycamore. Alternate order across participants when practical.
7. What essential evidence is missing? What would make them distrust the result?
8. Ask for a concrete next action: return for another task, bring a sample workflow,
   introduce the buyer, or discuss a paid pilot. Praise is not purchase intent.

Do not lead with the feature list or ask only “would you pay for this?”

## 3. Product success and failure gates

Proposed gates; freeze them before examining results and report raw counts.

| Checkpoint | Evidence sought | Proceed / revise |
| --- | --- | --- |
| Part 1 problem fit | At least five relevant participants, three describing the same recurring pain; actual workflow examples | Narrow task and revise scope if pain is inconsistent |
| Part 1 usability | Four of five can identify a material change and verify its source without assistance; no mistaken certainty from UI | Fix information hierarchy and evidence wording before more sources |
| Part 2 utility | Median task time improves by ≥25% on comparable tasks without lower evidence accuracy; report sample/time distribution | Improve workflow twice before broadening customer scope |
| Part 2 recurrence | At least three of five pilot users return for the task in three of four weeks | Missing repeat use triggers task/offer review |
| Paid pilot readiness | Two qualified buyers agree to a bounded offer and price conversation; distinguish verbal interest, signed pilot and payment | Build only capabilities necessary for this paid workflow |
| Paid expansion | Actual renewals, contribution margin, support load and acquisition evidence | Do not scale solely on page views or trial signups |

Small samples inform decisions; they do not prove a stable conversion rate.
Retain explanations of failures and reasons people decline. No model may fabricate
observations or replace user review with simulated personas.

## 4. Minimum paid offer and feature boundaries

Initial offer hypothesis: searchable permitted history, saved investigations,
“since last brief” change summaries and cited exports. Alerts are optional if
buyers value them; semantic discovery and team/API work are not prerequisites.

| Capability | Public | Paid individual pilot | Team, conditional |
| --- | --- | --- | --- |
| Live map/feed and original sources | Useful, included | Included | Included |
| Signal Trail | Current bounded context | Deeper permitted history | Shared workflow |
| Search | Current public window | Permitted archive | Larger bounded queries |
| Saved work | Local device saves | Private cross-device saves | Organization ownership |
| Brief/export | Share selected public context | Cited editable briefs | Shared briefs/controlled exports |
| Alerts | Preview if available | Measured cap | Measured shared cap |
| API | None initially | None initially | Scoped/metered when demanded |

Do not promise “full archive” before coverage and source rights support it.
Show earliest observation date, coverage gaps and unavailable source payloads.
Do not claim an archive is uniquely valuable just because it is large.

Source access, caching, storage, commercial display, derived summaries,
redistribution and bulk export are different permissions. Create a source-policy
registry before storing/serving new data. Record terms URL, review date,
attribution, retention, transformations allowed, public/paid/export allowance and
quota. Unknown commercial permission excludes the source from the paid/export
projection pending verification. This is an operational gate, not a legal opinion.
For licensing decisions, verify current authoritative terms and obtain qualified
review where necessary.

## 5. Pricing and unit economics

Do not invent a final price or claim a merchant-of-record provider is selected.
Historical D-007 proposes that route; actual providers, supported business/location,
fees, tax coverage and suitability must be checked at selection time.

Before paid pilot, record:
- owner-approved monthly spending ceiling;
- actual provider/storage/compute/bandwidth prices and observation date;
- expected ingest volume, retained bytes/event, expensive queries and exports;
- low/base/high usage assumptions;
- package price hypotheses tied to observed saved effort;
- caps that prevent a single account exhausting provider quota.

Useful ledger formulas:
- monthly variable service cost = provider calls + compute + storage + egress
  + messaging + payment fees;
- contribution = net collected subscription revenue minus refunds and variable
  service cost;
- contribution per active account = contribution / paying active accounts;
- break-even accounts = fixed monthly operating cost / positive contribution
  per account (rough estimate; no result when contribution ≤0).

Track founder/support time separately so “cheap to serve” does not conceal
manual work. Report estimates vs invoices explicitly. Quotas and fair-use limits
replace “unlimited” until usage and margins support a different offer.

Keep the free experience useful. Do not backfill demand by withdrawing essential
source context; sell persistent work and depth demonstrated to be valuable.

## 6. Measurement contract

Part 1 default: local/no-op adapter with no external analytics requests.
Event names:
event_open, source_open, intelligence_open, related_open, timeline_open,
local_save, brief_export, archive_search, upgrade_view.

Payload allowlist: event name, UI feature version, coarse view category,
success/error code and elapsed-time bucket. No article text, raw query, private
indicator, notes, full URL or secret. Retention cohorts require an explicit
privacy/measurement design later; a no-op adapter cannot produce retention data.

Use observed task sessions until privacy-appropriate usage measurement exists.
Event counts are diagnostics; the core success unit is a completed, source-verified
brief and repeated use of that workflow.

## 7. Pilot and release workflow

1. Complete technical gates and prepare a local demo.
2. Conduct authorized user sessions; revise the task and information hierarchy.
3. Prepare a bounded offer, rights inventory, costs and service expectations.
4. Implement only needed auth/saves/entitlements in sandbox/staging.
5. Verify server enforcement, private caches, cancellation/refund/grace/replay
   behavior and recovery before accepting live payments.
6. Run a small authorized paid pilot; review usage, support and renewals.
7. Add team/API or expensive enrichment only with evidence of demand.

No new external messages, accounts, purchases, subscriptions or production
launches occur merely because this planning document exists.
