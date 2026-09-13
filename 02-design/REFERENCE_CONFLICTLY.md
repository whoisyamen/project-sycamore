# Reference study — conflictly.app (captured 2026-09-03)

Lord Yams's stated inspiration for the dashboard feel: "the World's Conflict Radar" — real-time OSINT/conflict signals on a live map. Structure captured from its DOM; used to refine our layout, not copied wholesale (we stay nonpartisan/defensive per editorial policy and avoid their community-voting mechanics pre-G4).

## Their layout (desktop)

- **Full-bleed dark world map as the page background** — one canvas covering the entire viewport.
- Fixed top bar: brand · aggregate counters ("19 ACTIVE / 54 TENSIONS") · live counter · nav tabs (LIVE VIEW, PREDICTIONS, SCENARIOS) · SUBSCRIBE / SIGN IN buttons.
- **Left floating panel (~380px)**: "INTEL FEED" with timestamp chip + filter chips (ALL FEED / PULSE ONLY / NEWS ONLY / HIGH / MEDIUM / ESCALATION / DE-ESCALATION / TOP VOTED), then a scrollable stack of event cards — headline, severity badge, one-line summary.
- **Right floating panel (~320px)**: predictions/scenarios with community vote counts; below it a "MARKETS" strip tracking defense stocks (tickers + % change).
- Panels are semi-transparent black with backdrop blur over the map; everything else is markers on the canvas.

## What we adopt

1. **Full-bleed map as background, panels floating above** — replaces our earlier 58/42 split proposal. Stronger "wall" aesthetic and matches design system better (map IS the page).
2. Header aggregate counters + live status chip ("EVENTS 24H: n", last-updated time) — visible freshness is a core product feature for us too.
3. Filter chips on the feed, including an **escalation / de-escalation** classification axis per event (data-driven from our classifier).
4. A small **"MARKETS" signal strip** as one of the miscellaneous sections: defense/energy stock moves tied to tracked events — cheap public data, high "intelligence wall" flavor. Sample/static at launch; live feed later if volume warrants.

## What we deliberately do NOT copy (pre-G4)

- Community predictions/voting and sign-in — requires accounts + moderation surface; deferred past G4 per D-004. Instead: **read-only model-generated scenario outlooks** with confidence bars, no interaction needed (added to vision doc as a launch-scope candidate).
- Their partisan-leaning OSINT framing tone — our editorial policy keeps attribution uncertainty explicit and nonpartisan.

## Implications for G1 prototype

Prototype must demo the full-bleed map + floating panels pattern with real interactivity: marker click ↔ feed card sync, filter chips updating both layers, mobile Map/Feed tab fallback per design system. Built as a single static HTML file (MapLibre GL from CDN) so it runs locally without tooling — G2 will fold the same components into the Astro codebase.
