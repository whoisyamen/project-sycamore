# Horizon / Nocturne / Obsidian implementation

September 29, 2026. Local implementation of the three approved dark UI concepts.
The user requested Horizon for Overview, Nocturne Desk for Threat desk, and a new
third Obsidian Index tab, with one consistent dark palette and polished flow.

## References and result

References: `02-design/ui-concepts/2026-09-29/04-horizon.png`,
`05-nocturne-desk.png`, `06-obsidian-index.png`, and `dark-design-prompts.md`.
The [design system](../02-design/DESIGN_SYSTEM.md) records the accepted direction.
The live site uses real retained reporting, source media, and actual freshness;
the PNGs use illustrative stories. Typography, content length, and responsive
composition therefore adapt to actual content rather than embedding a mockup.

- `/`: panoramic satellite globe, report spotlight, compact globe dock,
  horizontal reporting tray, and preserved full Feed view/source-detail sheet.
- `/intelligence`: editorial lead and secondary reports, reading-lens toolbar,
  satellite context, source health, reading band, and existing section anchors.
- `/reporting`: new third tab, matte cartographic context, shared filters,
  semantic report table, inline source details, Share, and Load more.

The masthead, leaf mark, search, steel-blue accents, graphite controls, focus
styles, and status presentation unify all three. Nocturne retains its serif
hierarchy and copper editorial rule. The index stays sans-serif and structured.

## Source pointers

- Shared layout: `g3-astro/src/layouts/Base.astro`, `components/Header.astro`,
  `components/ReportFilters.astro`, `styles/global.css`, `styles/workspace.css`.
- Horizon: `pages/index.astro`, `components/HorizonFeed.astro`,
  `client/dashboard.ts`, `client/render.ts`.
- Nocturne: `pages/intelligence.astro`, `client/nocturne.ts`, `client/threat.ts`.
- Obsidian: `pages/reporting.astro`, `client/reporting.ts`,
  `client/reporting-render.ts`.
- Reading-page geography: `components/GeographicContext.astro`,
  `client/context-globe.ts`; layout options in `client/globe.ts`.
- Browser URL/filter continuity: `client/site.ts` and existing `client/state.ts`.
- Verification: `tests/workspaces.test.ts`, `tests/artifacts.test.ts`,
  `tests/run.ts`, and `scripts/check-dev.mjs`.

## Preserved behavior and boundaries

Snapshot schemas, validation, IDs, source links, geographic precision,
classification caveats, refresh interval, demo labels, and failure handling stay
on the existing contracts. Filter and selected-report parameters carry across
navigation. Refreshes preserve selected index context and Threat desk lens state.
The index displays 50 matching reports at a time; selected reports outside the
current results stay visible with a note. Keyboard closing restores row focus.

Mini-globes group nearby reporting into representative locations, disclose
approximation, and link back to the full globe. The index preview has source
country boundaries and no animated water/night overlay. Main Horizon defaults to
satellite and a closer, lowered camera; optional aircraft remain in Layers. Globe
imagery detail, 30 fps target, resolution cap, water/night effects, flight routes,
and thinning remain intact. No browser frame-rate improvement is claimed.

This is UI work over the current data. No new ingestion provider, intelligence
pipeline, iteration card, deployed site, or installed service was introduced.
The tree already contained extensive user changes; those were preserved.

## Validation

`make verify` passed: formatting, Astro diagnostics (zero errors/warnings/hints),
production build, all 38 web tests, and all 121 Python ingestion tests.
The build retains the existing Cesium large-chunk warning. Python reports
existing TemporaryDirectory ResourceWarnings without failing tests.

`npm run test:dev` passed against the local server: 34 served JavaScript modules,
all three workspace routes, and the 500-event snapshot.

Evidence logs and browser screenshots are in
[`qa-horizon-nocturne/`](qa-horizon-nocturne/). Browser review is separate from
DOM tests; it checks actual Cesium imagery and responsive layout. Screenshot
reporting content is dated and may differ from the next published snapshot.

Browser review covered 1440×900, 1024×768, 768×1024, and 390×844.
The final tablet index fits topic, report, source, and published columns without
horizontal scrolling; location stays available in expanded source context.
All reviewed pages had no document overflow and no browser JavaScript errors.
Horizon imagery was warmed before the saved final capture; an earlier capture
caught an incomplete material load and was replaced after visual inspection.

A reduced-motion phone session also passed browser interaction checks for layer
expansion, dark/satellite imagery, flight toggling, zoom/reset, Globe/Feed views,
source details, modal state, Escape closing, filtering, and filter-carrying tab
navigation. DOM tests separately cover inline selection, filters, refresh,
sharing, keyboard focus, and loading all 101 records in a pagination fixture.
