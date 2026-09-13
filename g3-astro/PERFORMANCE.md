# Performance and recreation record

Audit: 2026-09-07. The accepted visual iteration is preserved: Cesium resolution,
30 fps target, imagery detail, effects, camera tiers and selection styling are unchanged.

## Implemented

- Removed the uncalled MapLibre renderer, its CSS and dependency (37 packages
  removed; MapLibre itself occupied approximately 41 MB installed). `map.ts`
  retains the adapter interface consumed by the dashboard. MapLibre was already
  excluded from production bundles, so this is dependency/maintenance savings,
  not a 41 MB browser download improvement.
- Flight histories are filtered and sorted once per successful data poll.
  Cartesian positions are lazily cached per history and reused on zoom and
  selection; unseen histories allocate no Cartesian arrays. The next successful
  snapshot replaces the cache. Rendering still uses exact recorded fixes.
- Removed obsolete DOM marker CSS. Article images decode asynchronously.
- Added immutable caching for content-hashed `/_astro/*` in the existing hosting
  header template. `/data/*` stays no-store. This template requires a host that
  supports `_headers`; it does not change local Astro dev response headers.
- Added `npm run perf:report` to inventory production bytes and gzip estimates
  without adding a runtime dependency.

## Evidence and limitations

The initial existing dist artifact contained 4,270,975 bundled JS/CSS bytes
(1,140,589 gzip). The new build contains 4,272,555 bytes (1,141,021 gzip).
These are total bundles, not initial-page transfer. Initial dist was inherited
from the prior iteration; data and generated artifacts can change. This is not
an isolated bundle benchmark and no download reduction is claimed.
Cesium remains the dominant chunk (approximately 4.16 MB / 1.11 MB gzip), loaded
only by the dashboard. Its build size warning remains visible. Splitting it into
arbitrary chunks would not remove the work needed to display the globe.

Reports are in `../performance/before-assets.json` and `after-assets.json`.
For future controlled comparisons, build both versions against the same public
snapshot and lockfile. Run `npm run build` then `npm run perf:report` on each.

The globe regression checks real Cesium materials/collections with a substituted
Viewer, including reuse of route coordinates across zoom and no primitive
rebuild during steady camera frames. It does not measure GPU frame time.
No browser was connected for this audit, so FPS, GPU memory, image quality and
mobile layout need a browser pass. Do not interpret the automated checks as
visual verification or a measured smoothness improvement.

## Repeating the checks

From g3-astro: `npm run verify` (format, diagnostics, production build and tests),
then `npm run perf:report`. With localhost running, use `npm run test:dev`.
From g3-ingest: `python3 -m unittest discover -s tests -v`.

For profiling, use a production preview, fixed viewport/device scale, the same
snapshot and warmed imagery. Record frame-time distributions during orbiting,
zooming across tiers, selecting/unselecting flights and layer toggles. Check
both imagery modes, mobile tabs, reduced motion and repeated navigation for
retained resources. Keep image quality fixed. Continuous water/time animation
needs continuous rendering; request-render mode is not a drop-in optimization.

## Recreating the accepted site

The portable skill sources are `../skills/sycamore-recreate/SKILL.md` and
`../skills/sycamore-performance/SKILL.md`. Keep these with the checkout.
Restore source, lockfile, public assets/data, shared schemas and ingestion code;
run `npm ci` and `npm run verify` in g3-astro. `npm run dev` serves port 4321.
Generated Cesium files are copied from the installed package during prebuild and
predev. Retain original effect assets and their SOURCES.md provenance; do not
replace them with lower-resolution substitutes. Never include private credentials
in a recreation archive. See the root README for data freshness and demo mode.

Audit validation: full npm verify passed (21 tests; Astro diagnostics clean),
31 Python ingestion tests passed, and both skills passed quick_validate.py.
The dev HTTP smoke check passed for 21 JavaScript modules, dashboard and Boards.
Earlier attempts encountered closed sockets during development dependency reloads;
the final traced retry passed without changing application behavior.
