# Decisions log — Project Sycamore

Status values: `approved` (Lord Yams confirmed) · `proposed` (Herman's recommendation, pending review). Date format YYYY-MM-DD.

| ID | Decision | Status | Notes |
|----|----------|--------|-------|
| D-001 | Public brand for the site is TBD: extend **SOC Signal** vs new Sycamore-branded identity; domain candidates held in `_private/` | proposed — needs input | Codename stays internal either way. Blocks G1 copy work, not architecture. |
| D-002 | Static-first edge deployment (Cloudflare Pages) + local ingest service on this always-on laptop as the only dynamic component | proposed | Minimal attack surface; near-zero cost at launch; clean path to subscription later without rearchitecture. |
| D-003 | Primary data source: **GDELT** (free, no API key — global geotagged events + article coverage); curated RSS from named outlets as secondary quality layer | proposed | Exact refresh cadence validated during G2 integration testing before we promise "real-time" in copy. |
| D-004 | No user accounts and zero PII collection until the subscription phase (G4) | proposed | Retention pre-G4 comes from content freshness + visible live status, not lock-in features. Shrinks attack surface to near nothing at launch. |
| D-005 | Map stack: **MapLibre GL JS** with dark basemap; G1 prototype validated **Esri World Dark Gray raster tiles** (no API key, no watermark) — CARTO rejected at prototyping because its free tier now requires an API key and watermarks the map without one | approved 2026-09-03 | Open-source renderer avoids per-seat costs while we're small. Tile license/volume limits re-checked before G4 launch traffic. |
| D-006 | Frontend: **Astro + Tailwind CSS with React islands** (map/filter/feed state is client-side interactive — a web-app *feel*); still deployed as an edge-hosted bundle, no public app server; data freshness via 15–30 min polling of JSON manifests | approved 2026-09-03 | Confirmed by Lord Yams. Note: user referenced "Java web" alongside Astro — interpreted as confirming the JS-based Astro stack (Astro is JavaScript, not Java); if a JVM backend was intended it only affects the G2 ingest runtime choice. |
| D-007 | Billing at G4 via merchant of record (Lemon Squeezy or Paddle) rather than raw Stripe integration | proposed | Shifts tax/compliance surface off a solo operator; re-evaluate if volume justifies direct Stripe. |
| D-008 | ~~Remotion as cinematic asset layer~~ — **withdrawn** per Lord Yams direction 2026-09-03: Remotion is out of scope for the site; all in-page motion handled by CSS / Framer Motion per design system rules. Related ARCHITECTURE.md section removed same day | withdrawn | Site and video keep a shared visual language via palette/motion tokens only, not a shared render pipeline. |
| D-014 | Subscription-first monetization — **parked** 2026-09-11 per Lord Yams: user prefers a recurring-subscription-centric offer (poss. single flat paid tier, paywall = history/Signal Trail/saves/briefs/export, pilot earlier than current Part 3 staging). No plan or pricing changes made. Revisit after the site itself is working/released; do not treat parked as approved. | proposed — parked, no action | Held in mind only; MONETIZATION_PLAN.md and roadmap unchanged. |

## Open questions for Lord Yams (G0 exit blockers)

1. **D-001**: Is the public site an extension of SOC Signal, or does it get its own name? Any domain candidates in mind?

---

## G1.5 — Astro prototype status (2026-09-03)

Built a real Astro + Tailwind project at `g2-astro/` to replace the single-file G1 prototype.

- `npm install astro @astrojs/tailwind tailwindcss` succeeded (346 packages).
- `npx astro build` produces `dist/index.html` + 1 JS bundle (~7.6 kB raw, ~3.65 kB gzipped) — D-002 static-output requirement verified.
- Dev server runs at http://127.0.0.1:4321/ via `npm run dev` (still active in this session).
- Source tree: `src/{layouts,components,data,styles}/` — single page composed of 6 Astro components (Base, Header, Map, Feed, Outlooks, Ticker).
- Design tokens in `tailwind.config.mjs` map directly to DESIGN_SYSTEM.md (ink scale, cyan alive, risk palette).

### What changed vs G1

- **Real component split** — 6 single-responsibility `.astro` files instead of one 19 KB blob. Ready for a designer to iterate on one piece without breaking others.
- **Topic rebalance** — sample data is 8 cyber / 5 geopolitical / 3 maritime / 1 military (was military-heavy). Headline counts now show CRITICAL 3, ESCALATING 5 (driven by the rebalanced data, not the old hand-tuned 2/7).
- **Honesty discipline** — fake "last sync 18:12 ET" replaced with persistent **SAMPLE DATA — NOT LIVE** amber chip in the header. Disclosure copy ("Not a news organization — do not rely on this for safety-critical decisions") moved into the right panel as a labeled "About" block.
- **A11y & keyboard nav** — focus-visible rings, tab order through feed chips → listbox → markers (arrow keys cycle markers, Enter selects), `/` focuses chip row, `Esc` clears selection. `role="listbox"`/`role="option"`/`aria-selected` on feed cards.
- **Deep-linking** — every event has `#event/N` URL. Loading `http://127.0.0.1:4321/#event/14` auto-selects and flies the map. `history.replaceState` keeps the URL in sync as you click around.
- **Reduced-motion** — `prefers-reduced-motion: reduce` kills the cyan pulse on the FEED chip and the marquee scroll. WCAG respected.
- **Keyboard-accessible topic filters** — chips are real `<button>`s, not divs; clicking CYBER/MARITIME/etc. hides both feed cards and map markers in lockstep (3 of 17 visible after MARITIME filter, verified via DOM probe).

### Bug found and fixed during verification

Right panel initially overlapped the bottom ticker because panel content (~625 px) was taller than available viewport space above the ticker (~520 px). Vision loop caught the symptom but the real cause was content density, not z-index. Fixed by:
1. Compressing Scenario Outlooks (one row per outlook instead of three lines each).
2. Tightening Market Signal row spacing.
3. Shortening the About block from a full paragraph to a single line.
4. Bumping the panel's top offset from `top-20` (80 px) to `top-14` (56 px) to ride just under the header.
Final DOM geometry: right panel ends at y=526, ticker starts at y=537, 11 px clearance.

### Deferred to G2

- Real GDELT/RSS ingest — G1.5 still uses static sample data in `src/data/events.js`.
- Cloudflare Pages deployment wiring (build config, headers, WAF rules).
- D-001 brand + domain choice still open.
- Caching / ISR / 15-min JSON manifest pattern.
- Boards / Briefing / Outlooks+ pages (only Live View exists; nav links go to `#`).

### Open polish notes (not blockers)

Vision flagged 6 minor polish items: header chip wrap risk at narrow widths, MILITARY chip orphaning on a 4+1 wrap, scenario outlooks lacking severity color, etc. Captured in vision transcript for next iteration. None block the G1.5 → G2 transition.

---

## G3 — Multi-page Astro + real data path (2026-09-03)

### What landed

- **Real Astro project** at `g3-astro/`: 4 pages (`/`, `/boards`, `/boards/[id]`, `/briefing`, `/outlooks`) + 11 pre-rendered board pages for the 11 current events. `npm run build` produces 15 static HTML pages totaling **316 KB on disk** (32 KB JS+CSS).
- **Python ingest service** at `g3-ingest/` with three modules:
  - `gdelt_client.py` — DOC 2.0 client with 429 backoff (rate-limited at runtime, switched to RSS as primary)
  - `rss_client.py` — 7 curated feeds (Krebs, BleepingComputer, The Hacker News, CISA, Reuters World, AP Top News, gCaptain); no rate limit
  - `normalizer.py` — keyword topic gate, word-boundary city/country geocoder (~80 cities, ~50 countries), dedupe hash on (topic, rounded coords, day, lowercased title prefix)
  - `runner.py` — orchestrator with atomic file writes, fail-safe manifest on fetch error, 500-event LRU cap
- **21 normalizer tests** in `tests/test_normalizer.py` (all passing) covering topic classification, severity, geocoding (including the `rome` vs `chrome` false positive), dedupe stability.
- **Shared JSON schemas** at `shared/schemas/{event,manifest}.schema.json` — single source of truth between Python ingest and TypeScript site.
- **systemd timer** installed at `~/.config/systemd/user/sycamore-ingest.{service,timer}` — runs as `User=yams` (no root), `ProtectSystem=strict`, every 15 min, jittered. Verified end-to-end: 5.1s cycle, 117 articles fetched, 11 events stored, manifest written atomically. `journalctl --user -u sycamore-ingest.service` for logs.

### D-009 — RSS-first ingest (new)

- **Primary signal:** curated RSS from named outlets. Higher quality than GDELT DOC 2.0, no rate limits, English-only by construction, source attribution is automatic.
- **Optional secondary:** GDELT DOC 2.0 via `--gdelt` flag for breadth, but the free DOC endpoint throttles aggressively (429 after 1-2 calls within minutes), so it's not on by default.
- **Geocoding strategy:** word-boundary match against ~80 cities + ~50 country names. Drops records that mention neither a known city nor country. **No LLM geocoding, no fabrication** — a record with no resolvable location is dropped, not guessed.
- **Status:** approved 2026-09-03. Confirmed by Lord Yams direction.

### D-010 — Real-time manifest polling (new)

- Static site reads `public/data/manifest.json` at build time to render the "SYNCED Nm AGO" header chip and the Ingest Health block.
- Client polls `/data/manifest.json` every 60s and updates the chip + ingest panel without a full page reload. No LLM, no service worker; just `fetch + setInterval`.
- **Status:** approved 2026-09-03. Implemented as a default behavior; can be disabled by removing the `setInterval` call in `index.astro`.

### D-011 — Public surface stays static (reaffirmation)

Even with G3's real data path, the public attack surface is still the same: CDN serves the static build, Python ingest runs only on this laptop. The `manifest.json` polling is a GET on a static file, not an API call. No change to the G2 security posture.

### What changed vs G1.5

- 1 file → 16 source files; 1 page → 15 pages
- Sample data → real RSS data with manifest-driven "last sync" UI
- `EVENTS` constant → `loader.ts` that reads filesystem (build) or fetches (browser), falls back to sample if no live data
- Single-page IA → 4-page IA with a real boards index, per-event deep-dive pages, briefing window breakdowns, and a standalone outlooks page
- No filters → search + topic chips + time range chips (24h/7d/30d/ALL) with combined filter logic
- No watch/share → per-event watch toggle (localStorage) + clipboard deep-link share + comparison drawer (up to 4 pinned events)
- No keyboard nav → Tab through feed, arrow keys cycle markers, Enter selects, `/` focuses search, `c` toggles compare, `Esc` clears

### What's still deferred to G4

- Cloudflare Pages deployment wiring (build config, headers, WAF rules, custom domain)
- D-001 brand + domain choice
- Subscription auth + billing (D-007, MoR via Lemon Squeezy or Paddle)
- Dedupe loosening (currently very tight; some "new" events are misclassified as dupes of same-day same-coord articles)
- More RSS sources (State Department, UK NCSC, ENISA, Mandiant, etc. — easy to add, gated on quality)
- LLM-based topic/severity classification (explicitly NOT adding in G3; quality gate stays keyword-based to keep the runner stdlib-only)

---

## D-013 — September 2026 whole-project refactor

User approved an inspired redesign using Conflictly's map-first composition,
a calm analyst visual style, the core map/feed/boards/briefing experience, and
whole-project cleanup. Keep **Sycamore** in this local interface during redesign;
this supersedes the earlier internal-name restriction for local development.
Public brand/domain decisions remain separate.

Retain Astro, Tailwind, MapLibre, Python, and active directory paths. Retire
sample outlooks/markets, watch and comparison controls, and scrolling ticker.
Keep source links, shareable selections, filtering, and existing event routes.
Archive older prototypes in place. No deployment or installed-service changes.

Replace timestamp-only polling with validated atomic snapshots. Track successful
checks and attempts separately, persist the next event ID, and keep last good
records on source failures. Schema validators run on both producer and consumer;
browser validation is precompiled. Existing event/manifest files remain mirrors.

Astro dependencies were upgraded during implementation to remove audit findings;
Tailwind 3 now integrates through PostCSS. Browser visual QA remains a separate
verification step when a browser connection is available. The existing
Conflictly reference study is the design source used for this implementation.

- **D-020 (2026-09-05)**: Event imagery is ingest-controlled, same-origin,
  and budgeted. Feeds (RSS 2 / Media RSS / Atom / RDF) carry Media RSS
  `<media:content>` / `<media:thumbnail>` / `<enclosure>` / yt:videoId; the
  ingest runner downloads verified JPEG/PNG bytes (≤450 KB each) to
  `public/data/media/<sha1-16>.jpg` during the cycle and never references the
  original third-party host in the published JSON or in the browser. The
  pattern in `event.schema.json` is `^data/media/<sha1-16>\.jpe?g$`; any
  `media.image` not matching the pattern is dropped by `cardThumbnail()` and
  `eventDetail()` (defense in depth: ingest is the gate, render is the
  backstop). Per-cycle budgets (16 og-page GETs @2s, 8 image downloads @6s)
  fit inside TimeoutStartSec=240 alongside the ~30s feed fetches. The
  runner fails closed on a `media_pipeline` exception: media is strictly
  additive and never blocks publication. og:image lookups are recorded in
  `public/data/media/.og-attempts.json` so each event is fetched at most
  once even after a 404.

- **D-021 (2026-09-05)**: Map cadence is real-time. The systemd timer runs
  every 5 min (was 15 min) and the service unit's `TimeoutStartSec` is
  raised from 120 → 240s to leave headroom for slow feed days and the
  media fallback. The dashboard already polls `manifest.json` every 60s, so
  the timer is the source of freshness. Observed cycle time ~10–11s for
  336 articles across 13 feeds, plus 7–14 images attached. No
  accounts, no PII, no public app server; static edge still serves the
  bundle.

- **D-023 (2026-09-06)**: Replace the dashboard's flat map with a Cesium 1.145
  globe. Ship Cesium assets/workers locally, disable ion, and use Esri Dark
  Gray with oceans recolored navy, retaining land detail and labels, plus optional
  Esri satellite imagery with attribution. One dashboard-owned
  adapter handles event selection, country/city picking, layer state, resize and
  teardown. Country outlines retain separate antimeridian-split rings.
  OSINT layers are additive: OpenSky snapshots/trails and key-gated Censys samples
  are published by ingest; USGS past-hour earthquakes are fetched on demand.
  No positions are fabricated. Missing configuration is absent; source failures
  retain last-good envelopes, with freshness visible in the UI. Selection export
  downloads a region specification for operator-managed ingest, never a browser
  write to the data pipeline. See `g3-astro/GLOBE.md` for contracts and checks.
