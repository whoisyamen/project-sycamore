# Globe implementation and verification

The dashboard initializes one Cesium 1.145 globe and returns its `GlobeAdapter`
to `initDashboard`. `Map.astro` supplies markup only. The adapter owns entities,
primitives, subscriptions, polling, resize observation and destruction.

- Import Cesium widget CSS. A `ResizeObserver` and initial animation frame call
  `viewer.resize()`; the dashboard also calls the adapter's real resize method.
- `npm run dev` and `npm run build` copy Assets, Workers and ThirdParty from the
  installed Cesium package. `CESIUM_BASE_URL` points to the same-origin copy.
- Esri Dark Gray retains land, borders and labels; satellite retains ungraded land
  imagery. `globe-effects.ts` adds a Fabric surface material over either provider:
  4K NASA/GEBCO bathymetry, a conservative Natural Earth water mask, two animated
  normal-map scales, Fresnel reflection, sun glint and a soft solar terminator.
  It computes diffuse/alpha explicitly because GlobeFS does not use a material's
  emission or specular fields. World-space mapping avoids Cesium tile seams.
- NASA Black Marble 2016 supplies historical night lights, visible on the night
  side. Current solar time is the default; the optional 600× time lapse is labeled
  and resets to current time when switched off. Water motion pauses independently.
  Reduced-motion users start with water and time animation paused.
- Ground atmosphere and Cesium globe lighting stay off to avoid double shading;
  a low-intensity outer atmosphere adds a restrained edge. Rendering is capped at
  30 fps and 1.5× resolution. Material textures are self-hosted; sources and exact
  processing are in `public/data/globe/effects/SOURCES.md`. No ion token is needed.
- The bundled Cesium skybox is visible behind the globe for a star-field backdrop;
  land/water imagery, lighting, and globe effects retain their previous settings.
- Effects own their controls, frame subscription and GPU textures and release
  them before Viewer destruction. Water motion is decorative, not observed seas.
- Event and Censys entities live in `CustomDataSource` collections. Cities
  and earthquakes use point collections; aircraft use billboards; trails use polyline collections
  with `Material`, not entity `MaterialProperty` objects.
- Country outlines preserve individual antimeridian-split rings. Picking uses
  ellipsoid coordinates and polygon containment. Camera longitude uses a circular
  mean so Fiji does not fly toward Greenwich. City picks carry source coordinates.
- Layer buttons expose pressed state, and zoom/reset controls complement dragging
  and scrolling. Missing article images hide their image wrapper.

## OSINT data

Flights read `public/data/flights.json` from ingest every minute. The first
observation is retained so later cycles can build trails. Each trail fix is
`[longitude, latitude, timestamp_ms]`, not altitude. The aircraft envelope contains
altitude separately. Invalid/stale fixes are rejected; failures keep the last
published file. The globe labels unavailable or stale flight/Censys data.

Seismic data comes from USGS's past-hour feed when enabled. Deployment CSP permits
that origin. Censys reads an ingest-produced sample only; no API key enters the
browser. The ingest client calls `POST https://api.platform.censys.io/v3/global/search/query`
with a bearer token and reads `result.hits[].host_v1.resource`. Coordinates come
from `location.coordinates`, and ports from `services[].port`. See
https://docs.censys.com/reference/v3-globaldata-search-query.

Export a globe selection, review its bounds, and save the downloaded file as
`g3-astro/public/data/regions.json`. Censys ingest requires `CENSYS_PERSONAL_ACCESS_TOKEN` in the
existing ingest environment, plus `CENSYS_ORGANIZATION_ID` for organization access.
Geographic API search requires a search-capable plan; Censys Free only supports
known-asset lookups. The globe reads `public/data/censys.json`. Missing key or regions means absent, not failed.
Boxes become enclosing radius queries, so samples can include surrounding areas.
For hand-authored country queries use `country_code` (two-letter ISO), e.g.
`{"kind":"country","country_code":"DE","name":"Germany"}`.
Network failures preserve last-good samples rather than publishing an empty success.

## Checks

- `npm run check`, `npm run build`, `npm test`
- `npm run test:dev` while the site is running on port 4321
- `cd ../g3-ingest && python -m unittest discover -s tests -v`

The globe regression uses real Cesium collections, providers, materials and
properties with a substitute Viewer shell; it tests state, picking, resize and
cleanup without requiring a GPU. It does not certify canvas appearance or WebGL.
Manual browser verification should cover desktop/mobile layout, globe dragging,
country/city picks, event-to-feed selection, repeated layer/satellite toggles,
and network/console errors. Browser automation in the repair session was blocked
by a missing browser-plugin service module.

## Performance maintenance

See [PERFORMANCE.md](PERFORMANCE.md) for the optimization audit, repeatable build
inventory, profiling limits and recreation skills. Flight trail preparation is
cached per successful poll; coordinate conversion is lazy and reused across
camera tiers and selection. Preserve the cached positions as immutable inputs.
