# Three-view UI browser review

September 29, 2026. Headless Chromium against the running local Astro server.
Real retained reporting and source media; screenshots are dated snapshot captures.

| View | Viewport | Screenshot |
| --- | --- | --- |
| Horizon | 1440×900 | [Desktop](screenshots/horizon-desktop.png) |
| Horizon | 1024×768 | [Tablet](screenshots/horizon-tablet.png) |
| Horizon | 390×844 | [Phone](screenshots/horizon-phone.png) |
| Nocturne | 1440×900 | [Desktop](screenshots/nocturne-desktop.png) |
| Nocturne | 390×844 | [Phone](screenshots/nocturne-phone.png) |
| Obsidian with source context expanded | 1440×900 | [Desktop](screenshots/index-desktop.png) |
| Obsidian | 768×1024 | [Tablet](screenshots/index-tablet.png) |
| Obsidian | 390×844 | [Phone](screenshots/index-phone.png) |

All reviewed views had no document overflow and no browser JavaScript errors.
Actual Cesium imagery was visually reviewed; this is not an FPS benchmark.
The index's tablet columns fit the viewport, with location available in details.

Browser interaction checks passed in a reduced-motion phone environment:
Layers expansion, dark/satellite switching, quiet initial flight state, flight
toggling, zoom/reset, Globe/Feed switching, report details, mobile modal state,
Escape closing, topic filtering, and navigation carrying the active filter.

[Full verification log](verify.log): formatting, Astro diagnostics, production
build, 38 web tests, and 121 ingestion tests.
[Served HTTP check](dev-http.log): 34 modules and all three workspace routes.

[Implementation handoff](../HANDOFF-2026-09-29-HORIZON-NOCTURNE.md).
