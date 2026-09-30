# Threat desk website redesign — handoff — 2026-09-24

Status: local website implementation and headless browser review verified. No ingest/service/deployment cutover.
This is an independent UI change, not completion of any numbered intelligence
iteration. The existing register still points to 1.2.3 for the next backend card.

## Start here

1. Read [the redesign plan](../03-architecture/THREAT_DESK_REDESIGN_PLAN.md) for
   scope, acceptance criteria, and future source decisions.
2. Read [the design system](../02-design/DESIGN_SYSTEM.md) for palette, layout,
   copy rules, and viewport review list.
3. Use `g3-astro/src/pages/index.astro`, `src/pages/intelligence.astro`,
   `src/data/threat.ts`, and `src/client/threat.ts` for the live UI. The desk is
   a reading view over v1 `/data/snapshot.json`; `site.ts` retains the existing
   60-second refresh loop. `globe.ts` only turns on Cesium's bundled skybox.
4. For actual new ingestion or verified evidence, follow
   [the intelligence specification](../03-architecture/INTELLIGENCE_IMPLEMENTATION_SPEC.md)
   and [iteration register](../03-architecture/iterations/REGISTER.md).

## Delivered

- Neutral olive/charcoal interface, warm amber interaction color, serif headings,
  restyled navigation, reporting feed, map controls, cards, and responsive panels.
- Star field via Cesium's existing bundled skybox. No new remote artwork or globe
  behavior changes beyond showing that backdrop.
- Dashboard watch rail and `/intelligence` sections for vulnerability/exploit
  text matches, policy text matches, first-ingested-here reporting (48h), and
  source labels represented in the retained snapshot. Lists link to original
  event selection; counts respond to snapshot refresh. Empty data stays empty.
- Plan/design/architecture/README/globe-documentation pointers and regression
  coverage for classification, ingest-time boundaries, escaping, and rail refresh.

## Verified locally

- `cd g3-astro && npm run verify`: format, Astro diagnostics (0 issues), static
  build (including `/intelligence`), and 33/33 web tests passed.
- `git diff --check`: passed.
- A follow-up headless Chromium WebGL pass waited for imagery and confirmed the
  existing globe rendered over the star field at 1440×900 and 390×844. All six
  bundled skybox faces and Esri basemap tiles returned 200. The first quick
  screenshot was premature; the globe appeared after its tiles loaded (~25–30s
  on the headless software renderer). Desktop detail and mobile map/detail were
  exercised; the dashboard also loaded at 1024×768 and 768×1024 with no
  horizontal overflow or panel collision. `/intelligence` was inspected at
  390×844. A 720px CSS viewport exercised the narrower layout analogous to
  zoom; a reduced-motion emulation matched the media query; simulated WebGL
  failure showed the map-unavailable message while leaving the feed usable.
- That pass exposed a real overlap between Cesium attribution and the mobile
  Feed/Map switcher, plus a crowded desktop map summary. The CSS now moves
  attribution above the switcher on the Map tab, hides the credits while the
  mobile Feed tab covers the map, and lifts the desktop summary. Final screenshots show
  the legend, summary, credits, and tabs in separate lanes. Cesium sets its
  credit offset inline, so the targeted mobile override requires `!important`.
- A follow-up physical-GPU pass ran on 2026-09-24 with Chromium 152 headless
  using ANGLE over the Intel HD Graphics 630 (`--use-gl=angle --use-angle=gl-egl`;
  renderer string `ANGLE (Intel, Mesa Intel(R) HD Graphics 630 (KBL GT2),
  OpenGL ES 3.2)` — hardware, not SwiftShader). All eleven viewport cases
  (1440×900 desktop/detail, 1024×768, 768×1024, 390×844 feed/map/detail,
  `/intelligence`, 720×900, 720×450 for true 200% zoom of 1440×900, and
  reduced-motion) showed zero JS exceptions, zero failed requests, all skybox
  faces and Esri tiles at 200, no horizontal overflow, and reduced-motion
  emulation active. Screenshots confirm separate lanes for legend, summary,
  credits, and tabs; credits hidden on the mobile Feed tab; and the 200% zoom
  layout fitting without collisions. Evidence is archived under
  [`qa-globe-visual/`](qa-globe-visual/) (per-case JSONL metrics in
  `gpu-pass.jsonl` plus the eleven screenshots in `screenshots/`). This closes
  the headless software-WebGL caveat above; a signed-in interactive human pass
  is still the final publication gate.
- Existing unrelated working-tree changes in admin/iteration documents, ingest
  tools, and generated public data were present beforehand; leave them alone.

## Next actions

- The physical-GPU browser pass is done (evidence above). Remaining before
  publishing: a signed-in human interaction pass and deployment smoke test.
- Decide official advisory and legislative sources, jurisdictions, social/dark-web
  access, evidence provenance, refresh expectations, and evaluation criteria
  before offering those as live intelligence feeds. See the plan's source table.
