# Refactor validation — September 4, 2026

## Delivered

Calm map-first Sycamore dashboard, responsive feed/details, refreshed Boards and
Briefing, preserved event links, explicit demo mode, retired sample features,
modular TypeScript, locally bundled map assets, updated dependencies, and
standard-library Python ingestion with atomic snapshots and stable IDs.

Earlier prototypes are marked archived in place. Active directories and installed
service configuration remain unchanged. The existing timer has produced a valid
snapshot with the new fields; the local HTTP check observed 24 events and healthy
source status. No public deployment was performed.

## Checks passed

- `make verify`: formatting, Astro type checks (zero errors/warnings/hints),
  static build (28 pages at verification time), 18 website tests, and 12 Python
  ingestion checks including the original normalizer regression script.
- Website tests: combined filtering, time boundaries, URL round trips and legacy
  links, freshness states, invalid snapshots, source-text escaping, new-record
  links, selection and refresh, mobile modal focus, clipboard success/fallback,
  map-initialization failure, generated routes/scripts, header template, and
  AA text-token contrast on primary surfaces.
- Ingestion checks: same-cycle merges, repeat URLs, partial/total failures,
  valid empty feeds, retained successful timestamps, high-water IDs after
  pruning, invalid input, atomic-write failure, migration, and RSS parse health.
- Final `npm audit --audit-level=low`: zero vulnerabilities in the active website.
- Local HTTP: redesigned homepage and `/data/snapshot.json` both respond at
  **http://127.0.0.1:4321**. This is a development preview, not public hosting.

## Remaining review boundaries

No browser is connected to this session. Real desktop/mobile rendering, WebGL,
map tile recovery, visual comparison with current Conflictly, and 200% zoom have
not been visually verified. DOM tests do not substitute for these checks. The
existing Conflictly study guided the design. Suggested viewport checks are in
`02-design/DESIGN_SYSTEM.md`.

The build reports its standard >500 kB chunk notice for MapLibre (about 772 KiB
minified before compression). It is lazy-loaded only on the map page; the feed
controls initialize independently. Secondary pages do not load the map library.

The `_headers` file is a Cloudflare Pages template. Actual deployment headers,
edge configuration, and publication of future data snapshots remain unverified
and outside this local implementation. Existing prototype dependencies were
left archived and were not included in the active audit.

## Review commands

From `g3-astro/`, `npm run dev` starts the local preview; Astro prints its port.
`astro dev status`, `astro dev logs`, and `astro dev stop` are available through
`npx astro dev status` / `npx astro dev logs` / `npx astro dev stop` for that
project's development server. From the project root, use `make verify` to repeat
the automated checks.

## Development-server repair

The pre-upgrade Astro process was still serving port 4321 after dependencies
changed on disk. Confirmed symptoms: an unsubstituted
`__SERVER_FORWARD_CONSOLE__` in `/@vite/client` and HTTP 504 responses without
JavaScript MIME types for the optimized validator dependencies.

Stopped both old and temporary Sycamore servers, removed the stale Vite optimizer
cache, and started one current server on 4321. Enabled Vite `strictPort` to prevent
silent port changes. Added `npm run test:dev` to verify the served JavaScript
module graph, including lazy map imports, alongside the existing build tests.
