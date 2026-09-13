# Sycamore

A local-first global reporting dashboard: a map and feed for sourced cyber,
geopolitical, maritime, and military events. The interface uses the Sycamore
name during this local redesign; public branding and deployment remain separate decisions.

## Active projects

- **`g3-astro/`** — Astro static website, TypeScript interactions, Tailwind/PostCSS,
  and a Cesium 3D globe with OSINT layers. This is the only active website.
- **`g3-ingest/`** — Python standard-library RSS ingestion; optional GDELT.
- **`shared/schemas/`** — event, manifest, and atomic snapshot contracts used by both.
- **`00-admin/`, `01-strategy/`, `02-design/`, `03-architecture/`, `04-content/`** —
  decisions, product direction, design, architecture, and editorial policies.
- **`g1-prototype/`, `g2-astro/`** — archived historical prototypes. Retained for
  reference, excluded from active builds and checks.
- **`_private/`** — local sensitive material; never published or committed.

The active directory names are retained because installed ingestion services
reference them. Do not rename them without updating those references.

## Local development

Use Node 22.12+ (Node 24+ on the 24.x line) and Python 3.10+ on Linux.

```sh
cd g3-astro
npm ci
npm run dev
```

Open http://127.0.0.1:4321. Startup fails if that port is already occupied; it does not silently switch ports.
Map tiles require access to Esri; the feed works without the map.

To ingest reporting manually, from `g3-ingest/`:

```sh
python3 -m sycamore_ingest.runner
```

To convert existing event/manifest files to the new snapshot without any network
fetch or fresh-sync claim:

```sh
python3 -m sycamore_ingest.runner --snapshot-only
```

The installed timer is not reconfigured by this refactor. Its existing module
entrypoint and output paths remain compatible; the next run uses the updated code.

After dependency upgrades, stop the existing development server before starting
it again. An old process can serve incompatible Vite files from the new install.
For Astro-managed servers use `npx astro dev stop`, then `npm run dev`.

## Checks

From the project root:

```sh
make verify
```

This runs Astro type checks, a production build, TypeScript/DOM/artifact tests,
and Python ingestion tests. Browser visual review is an additional manual step;
DOM tests do not exercise WebGL or measure layout. `npm audit` in `g3-astro/`
checks the dependency lockfile against current advisories. With the dev server
running, `npm run test:dev` verifies module HTTP responses, MIME types, and Vite
client substitutions for both the map and Boards pages.

## Data behavior

The public client fetches `/data/snapshot.json` on load and every 60 seconds while
visible. Events and health metadata update together; failures keep the last good
data. A 30-minute gap since the last successful source check is labeled delayed.
A valid empty feed is distinct from unavailable data. The feed retains at most
500 events, so briefing counts describe that retained coverage.

`events.json` and `manifest.json` remain compatibility mirrors. New consumers
must use the snapshot. Event IDs have a persisted high-water mark and are not
reused after pruning. Source classifications remain heuristic, not verification.

Explicit demo mode is available with `PUBLIC_DEMO_MODE=true npm run dev` (or build).
It uses clearly labeled fictional events, disables polling, and never silently
replaces missing production data. Restart the dev server when changing modes.

## Product surface

- `/` — map, feed, search, topic/severity/time filters, event details, and sharing.
- `/boards` and `/boards/[id]` — topic groups and existing event permalinks.
- `/briefing` — recent coverage across 24-hour, 7-day, and 30-day windows.
- `/outlooks` — retirement notice linking to Briefing.

Dashboard links (`/?event=123`) work for newly ingested records before a static
rebuild. Shared filters use `topic`, `sev`, `range`, and `q`; legacy `mode` filters
and `#event/123` links remain readable. Watchlists, comparison, sample outlooks,
market panels, and the scrolling ticker have been removed.

## Deployment boundary

Nothing here publishes the site or changes accounts, domains, or installed
services. Static `dist/` includes a point-in-time copy of public data; production
updates require republishing the snapshot and rebuilt event pages. The local dev
server serves current `public/data/` directly. `public/_headers` is a Cloudflare
Pages header template, not evidence of headers on a deployed host.

Existing editorial and security policies remain applicable. No publishing,
provider accounts, domain purchases, or external communication without explicit
authorization. Operation SM remains the related content project.

# project-sycamore
