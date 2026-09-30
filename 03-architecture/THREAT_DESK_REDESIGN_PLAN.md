# Threat desk redesign — website delivery plan

Status: UI implemented and locally reviewed, 2026-09-24; revised 2026-09-25 when
the watch rail was removed, boards and briefing were folded into `/intelligence`,
and the dashboard gained a Globe/Feed tab switch over a tiles-only feed. Where
this plan still says "watch rail", read the Threat desk sections instead. This
plan records the requested direction; implementation started before the request
for a written plan arrived. It is a
website initiative alongside, not a replacement for, the numbered intelligence
iterations in [REGISTER.md](iterations/REGISTER.md).

## Goal and boundaries

Turn Sycamore into a more legible threat-intelligence workspace without replacing
the Cesium globe, existing ingestion service, static publishing, data contracts, or
event IDs. Remove the blue-on-blue interface, make the globe feel like an object in
space, and offer an analyst-oriented way into vulnerabilities, policy, early
observations, and source coverage. Keep the feed, boards, briefing, map layers,
selection, URLs, freshness indicators, and mobile interactions intact.

Today the site has a 60-second **browser** snapshot poll over the latest published
JSON; that is not a continuously streamed feed. Ingestion currently uses news RSS
and optionally GDELT. No dedicated NVD/CISA CVE stream, legislative tracker,
X/Twitter feed, or dark-web connector is established by this UI work. Do not label
news keyword matches as verified zero-days, new laws, or pre-mainstream detections.

## Delivery sequence

1. **Document direction.** Record palette, layout, language, and verification
   requirements in [DESIGN_SYSTEM.md](../02-design/DESIGN_SYSTEM.md). Preserve the
   project architecture and register as the source of truth for ingest work.
2. **Re-skin the site.** Update tokens, header/nav, cards, controls, responsive
   layout, and detail surfaces in `g3-astro/src/styles/global.css` and components.
   Let Cesium's existing skybox render stars behind the globe. Leave imagery,
   lighting, picking, layers, camera behavior, and water/night effects alone.
3. **Introduce a threat desk.** Add `/intelligence` and a dashboard watch rail.
   Derive views only from validated v1 snapshot events; text matching is labeled
   as such. "Newly observed" uses `ingestedAt`, not publication time or an
   assertion of novelty. Source footprint counts source labels in the retained 500-event
   snapshot; it does not claim source uptime. Reuse the existing refresh event.
4. **Verify.** Run the web formatter/check/build/tests and inspect the diff. Review
   globe, layout, focus, map failure, browser errors, mobile breakpoints, and
   reduced motion in a browser when available. Record any unverified visuals in
   the handoff rather than implying a WebGL test proves appearance.

## Acceptance

- Desktop makes the globe central and navigable, with a usable feed and a concise
  watch rail; smaller screens keep feed/map tabs and a full-height detail sheet.
- Site-wide surfaces use neutral charcoal/olive, warm ivory, amber, and restrained
  sage/coral semantic accents. Globe style and map overlays remain familiar.
- `/intelligence` sections link back to existing event selections, update on the
  normal snapshot refresh, and show informative empty states.
- Every time/coverage claim has its actual meaning: last successful source check,
  ingest-first-seen time, text match, or represented source-label count.
- Existing event/filter/share links, page routes, data health, and event detail
  provenance continue to work. No ingestion, schema, or deployment change.

## Next data-source decisions (separate future work)

| Desired signal | Required future work | UI truth until then |
| --- | --- | --- |
| CVEs and active exploitation | Evaluate official advisory sources (NVD/CISA KEV/vendor bulletins), advisory identifiers, revisions, severity provenance, refresh/health, and release contract | Existing news text matches only |
| Regulation and law | Choose jurisdictions and primary registries, capture passage vs effective dates and links to primary text, handle amendments | News mentions, not a legal change log |
| X/social and dark web | Choose authorized/licensed sources and scoped collection, record first-observed vs published timestamps, independent corroboration, retention and takedown rules | No such sources connected |
| Earlier-than-mainstream detection | Establish baseline/source timestamps, comparison cohorts, precision reviews, and evidence trails before claiming lead time | "Newly observed here" only |

Future ingest changes need their own scoped cards and schema decisions under the
existing [intelligence specification](INTELLIGENCE_IMPLEMENTATION_SPEC.md). The
planned Evidence/Entities/Signal Trail features in iteration 1.3.3 are separate
from this UI-only reading list.
