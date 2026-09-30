# Sycamore architecture

Current-runtime description, corrected during the 2026-09-09 roadmap review.
The future architecture is proposed in
[the intelligence specification](INTELLIGENCE_IMPLEMENTATION_SPEC.md), with
execution tracked in [the iteration register](iterations/REGISTER.md).
Future capabilities are not implied to be running today.

For the website-only threat desk and its current-data limitations, see the
[redesign plan](THREAT_DESK_REDESIGN_PLAN.md). The numbered iteration register
continues to own future intelligence ingestion and evidence features.

## Runtime boundary

Astro builds static routes. TypeScript enhances filtering, map selection, and
periodic data refresh. Python runs locally under the existing user service and
writes JSON. No public application server, accounts, billing, or new providers
are introduced. Active directory names are retained for service compatibility.

## Website

`src/pages/` composes layouts and components. `src/client/state.ts` owns filter
and URL logic; `dashboard.ts` coordinates controls, selection and focus;
`index.astro` initializes `globe.ts`, the active Cesium adapter. `map.ts` is a
legacy implementation, not the current dashboard renderer. `render.ts`
provides escaped event/card/source rendering shared by server and browser.
`site.ts` owns a single non-overlapping refresh loop and refreshes collections.

`src/data/loader.ts` is build-only filesystem access. Missing or invalid data
renders an unavailable state. Explicit `PUBLIC_DEMO_MODE=true` loads fictional
fixtures and disables polling. There is no implicit sample fallback.

The homepage initializes from server-rendered data stored in an escaped HTML
data attribute. Browser refreshes use `/data/snapshot.json`, validated before
replacing state. Validation is generated ahead of time from shared schemas;
the browser does not compile code dynamically or require `unsafe-eval`.

Astro uses Tailwind through PostCSS. Cesium assets and workers are served locally;
the globe uses Esri dark/satellite imagery and local water/night-effect assets.
`globe-effects.ts` owns those effects; `osint.ts` coordinates additional data
layers. External imagery and layer requests have their own availability and
freshness behavior. System font stacks avoid font-provider dependencies.
Preserve the accepted 30 fps target and imagery/effect quality when adding UI.

## Data contract

`shared/schemas/` defines event, manifest, and snapshot contracts. The snapshot is
`{ version: 1, events, manifest }`. Existing event fields and route IDs remain
compatible. Optional legacy fields remain optional in TypeScript.

The event and snapshot schemas reject extra properties. An optional field added
to a new schema is not automatically compatible with an old compiled validator.
The roadmap therefore keeps the public v1 projection unchanged and introduces
separate, versioned intelligence artifacts for new readers.

Manifest additions: `lastAttempt`, `nextEventId`, and `health.failedSources`.
`lastSync` now explicitly means successful source check, not attempted update.
Both validators also check unique IDs and consistency of event/topic/severity
counts. The Python validator rejects unsupported schema keywords.

The client fetches on load, every 60 seconds while visible, and on returning to
the tab. Requests time out after 15 seconds and never overlap. Older snapshots
are ignored. Fetch/validation failure preserves last good state and exposes
connection status. Source failure status is read from the manifest. Data becomes
delayed after 30 minutes without a successful check.

## Ingestion

RSS responses record source health separately from item count. Optional GDELT
can contribute even when RSS fails. Validated normalized records deduplicate by
URL, then merge by the existing topic/location/day/headline key. Sourcing scores
refresh after merges. The output caps at 500 records while retaining the next
unused ID in the manifest. Classification and geocoding rules are unchanged.

A filesystem lock serializes writers. Canonical snapshot publication uses a
unique temporary file, flush/fsync, and atomic rename; legacy event/manifest
mirrors follow. The next cycle reads canonical data first. Failed ingestion
keeps previous records and reports failure; corrupt stored data is not reset.

## Routes and publishing

Existing `/boards/[id]` static pages remain usable. Dashboard links
`/?event=<id>` support new records before rebuilding detail pages. Legacy
`#event/<id>` and mode filter links remain readable. The retired `/outlooks`
route points users to the Threat desk.

The development server serves current public JSON. Production `dist/` is a
snapshot of build time; freshness on a deployed host requires republishing data
and rebuilding static event pages. No deployment pipeline or installed timer
configuration is changed here. `public/_headers` is a Cloudflare Pages template
that requires verification against actual hosting when deployment is authorized.
