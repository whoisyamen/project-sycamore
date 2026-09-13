# D-020 / D-021 Live Verification — 2026-09-05

## Scope

Real-time ingestion from many sources, the map covered, and event imagery in
the existing dark/teal style. No deployment or public communication authorized.

## Ingest pipeline

- **13 curated RSS feeds** (D-009 RSS-first): 5 cyber, 6 geopolitical, 2
  maritime/military. 336 articles per cycle (varies; sometimes higher). Sources
  probe-verified live: KrebsOnSecurity, BleepingComputer, The Hacker News,
  SecurityWeek, Dark Reading, BBC World, Al Jazeera English, Guardian World,
  France24 EN, DW News World (RSS 1.0 RDF — handled via namespace-agnostic
  local-name matching), NPR World, gCaptain, The War Zone TWZ.
- **RSS 1.0 RDF** items live in `purl.org/rss/1.0/` namespace and use
  `dc:date` instead of `pubDate`; DW items would be silently dropped before
  this work. Now parsed correctly: 11 items/cycle from DW.
- **Media RSS / enclosure / yt:videoId** extraction in `_item_media()`:
  picks the highest-quality image under 2× the static-serving budget,
  prefers `<media:content>` with size hints, falls back to width-bounded
  thumbnails, then enclosures, then YT watch links.
- **Coverage geocoding v2**: tier-1 (headline locative locus) unchanged
  (D-014 fail-closed). Tier-2 (single locative dictionary mention in the
  source's own lede) added; same false-match guards as tier-1, plus a
  minimum summary length to prevent boilerplate stubs from hitting. 38
  new cities + 12 new regions added to the offline table. From
  `tools/diag_geo2.py`: 73 articles pass the topic gate; 5 resolve via
  tier-2 summary where the headline alone would have abstained.
  Example: "Iran war live: IRGC claims new attacks on US warships" →
  US, US (approximate), because the lede names "US warships" with a
  locative.

## Media pipeline (D-020)

- **Ingest-time download**, never at render time. Why: strict CSP, no
  external image hosts, no app-server proxy layer allowed.
- **Pipeline** (`g3-ingest/sycamore_ingest/media_pipeline.py`):
  1. Feed-native candidate (Media RSS / enclosure) → first attempt while
     budget remains. This is free per cycle; it came from the same fetch.
  2. og:image / twitter:image on the article page → passive 2s GET, only
     for events not in the `.og-attempts.json` ledger. Failed lookups
     recorded so a 404 never burns two cycles' headroom.
  3. Both paths funnel through `_http_get()` which enforces
     HTTPS-only, JPEG/PNG magic bytes, ≤450 KB. Bytes are content-hashed
     (sha1[:16]) and stored as `data/media/<hash>.jpg`. Identical bytes
     dedupe automatically (existing-hash check before write).
- **Same-origin contract**: `event.schema.json` pattern
  `^data/media/[a-f0-9]{16}\.jpe?g$`; render layers (`cardThumbnail()`,
  `eventDetail()`) re-validate against the pattern before any `<img>`
  tag is emitted. Defense in depth: ingest is the gate, render is the
  backstop, schema is the contract.
- **Budgets per cycle** (sized for TimeoutStartSec=240 with feed fetches):
  16 og-page GETs @2s = 32s, 8 image downloads @6s = 48s. Worst-case
  media total ≈ 93s, observed actual: 7–14 images attached per cycle.
- **Failure mode**: `attach_media()` exceptions are caught at the
  runner boundary; media is strictly additive and never blocks
  publication of the JSON.

## Cadence (D-021)

- **Timer**: every 5 min (was 15 min). 1 min after boot, 1 min jitter.
- **Service unit**: `TimeoutStartSec=240` (was 120s). Sized for
  worst-case feed concurrency + media fallback.
- **Client side**: dashboard already polls `manifest.json` every 60s;
  the timer is the source of freshness, the poll is the delivery.

## Frontend visuals

- **Card thumbnail** (`.event-card.has-thumb > .card-thumb > img`):
  140px tall, full card width, `object-fit: cover`, dark base
  (`#0a141a`) and `--border` outline so unloaded thumbs match the
  panel chrome. Only `.has-thumb` cards reserve the extra height;
  non-imaged events keep the previous density.
- **Detail hero** (`.event-hero` with `<figcaption>`): bounded at
  360px max-height, full width, figcaption in the small-caps monospace
  style already used on the site ("Image via SRC — see original
  reporting for the full picture."). Plain reading for the user; no
  fabricated provenance.
- **Video link row** (`.video-link-row`): external YouTube watch link
  with the same monospace accent style. Never embedded; user leaves
  the site on click. Currently no event in the dataset has a yt:videoId
  (TWZ items don't ship one; we'd need to surface video more in
  future feeds), but the render path is wired and tested.
- **Match to existing style**: all three additions use the same
  `--border` / `--accent` / `--muted` tokens and the same dark
  base color. No new design language; the additions feel native.

## Verification — all green

| Test                                      | Result        | Time    |
|-------------------------------------------|---------------|---------|
| Ingest unit tests (Python)                | 18 / 18 pass  | 0.27 s  |
| Frontend unit tests (npm verify)          | 19 / 19 pass  | 2.7 s   |
| Playwright E2E (existing, all surfaces)   | 28 / 28 pass  | ~60 s   |
| Playwright D-020 media QA                 | 4 / 4 pass    | ~20 s   |
| Live ingest cycle                         | status ok     | 10–11 s |
| Live media samples                        | 14/14 valid JPEG, ≤450 KB, same-origin | <1 s |
| Timer health                              | active, 5 min | —       |

Playwright D-020 media QA breakdown (file:
`00-admin/qa-geolocation/frontend-qa-media.mjs`):
- Live events have media blocks where expected: 14 of 54 events have
  `media.image`, all matching `^data/media/[a-f0-9]{16}\.jpe?g$`.
- Dashboard feed cards render thumbnail when present: 14 cards
  actually render `<img>` with a `/data/media/...` src. Without the
  fix, this was 0.
- Detail panel renders hero image and CSP-clean: clicking a card
  populates `#detail-body`; the first `<img>` is the hero at
  1400×788 real pixels, `/data/media/...` src.
- No CSP violations from media sources: 0 external image hosts hit;
  every media request stayed on `localhost:4321`.

## Files changed in this iteration

- `g3-ingest/sycamore_ingest/rss_client.py` — feeds list, RSS 1.0
  RDF parser, Media RSS / enclosure / yt:videoId extraction,
  namespace-agnostic local-name matching, non-feed-body guard
  (raises `ET.ParseError` so the cycle marks bad sources as failed
  rather than silently dropping them).
- `g3-ingest/sycamore_ingest/media_pipeline.py` (new) — same-origin
  image download, og:image fallback, `.og-attempts.json` ledger.
- `g3-ingest/sycamore_ingest/runner.py` — wired `attach_media()`
  into the cycle, built per-URL hints, fail-soft on media errors.
- `g3-ingest/sycamore_ingest/normalizer.py` — tier-2 summary locus,
  table expansion, `_validate_geolocation` updated to re-derive
  summary-tier rows from stored text.
- `shared/schemas/event.schema.json` — `media` block (D-020),
  `geo.source` enum extended to include `summary`.
- `g3-astro/src/data/types.ts` — `Event.media` block.
- `g3-astro/src/client/render.ts` — `cardThumbnail()`,
  `eventCard(..., withMedia)`, hero `<figure>` in `eventDetail()`,
  video link row.
- `g3-astro/src/client/dashboard.ts` — passes `withMedia=true` when
  rendering feed cards.
- `g3-astro/src/styles/global.css` — `.card-thumb`, `.event-hero`,
  `.video-link-row` styles, all in the existing palette.
- `00-admin/qa-geolocation/frontend-qa-media.mjs` (new) — D-020
  browser checks.
- `~/.config/systemd/user/sycamore-ingest.{service,timer}` —
  TimeoutStartSec 120→240, cadence 15 min→5 min.
- `00-admin/DECISIONS.md` — D-020, D-021 entries.

## Known gaps / follow-up

- **No video items yet in the dataset.** TWZ and BBC ship some YouTube
  embeds but no `yt:videoId` in their RSS. The schema and render path
  are wired; the data simply isn't there. If a future feed is added
  that ships video (e.g. a specific YouTube channel feed), it'll
  surface immediately.
- **og:image fallback rarely fires.** Most of the 14 images in this
  cycle came from feed-native Media RSS. og:image is the safety net
  for feeds that ship a description and a hero image but no
  `<enclosure>`. The ledger is empty for now.
- **City / region coverage still gated by the offline dictionary.**
  Tier-2 adds ~5 resolved events per cycle vs tier-1 alone, but it's
  still conservative (one locative mention in the lede, must be a
  known place, no actor-target conflation). Unknown stays unknown.
  This is by design — the wrong-pin failure mode from Phase 1 is the
  riskiest regression we can introduce, and we'd rather have honest
  absence than a wrong marker.
- **No blog / no social posting pipeline.** This iteration is
  pipeline-and-display only. The user-facing static site is the
  surface.
