# Atmospheric visual polish — October 1, 2026

Local implementation of the approved visual treatment. The current checkout,
rather than the generated concept images, supplied the camera and layout baseline.
Existing working-tree edits were retained. No deployment was performed.

The header stays opaque; reporting and event details use dark transparent glass.
The eye/globe mark replaces the tree without changing the wordmark or its footprint.
Cesium's native atmosphere gains a restrained 12-second breathing cycle. Overview
markers are severity-colored luminous beacons: critical red rings expand/fade
every 1.8 seconds, escalating amber beacons breathe over 3.2 seconds, and lower
severity sage halos use quieter 4.5/5.5-second cycles. Selection strengthens the
same beacon. Camera framing,
star field, imagery, water, night lights, and rendering limits are retained.
There are no CRT filters. Panel fades change opacity without moving content.

Ambient and interaction sound toggles live inside the expanded Layers popover;
both start muted. Sound is synthesized locally after opt-in, suspends offscreen,
and releases resources on destruction. The expanded phone popover retains its
intended 275px width rather than shrinking to the collapsed toolbar's width.

## Verification

- `npm run verify`: formatting, Astro diagnostics (zero errors/warnings/hints),
  production build, and all 40 web tests passed.
- Python ingest: all 121 tests passed during `make verify`.
- Targeted globe regression passed after adding checks for the retained star
  field, static reduced-motion atmosphere/halo, live preference changes, hidden
  phase suspension, selection cleanup, and resource destruction.
- `npm run test:dev`: 35 served JavaScript modules, all three workspaces, and the
  retained 500-event snapshot passed.
- Chromium WebGL browser review at 1440×900 and 390×844: no page errors;
  desktop header, brand footprint, search, heading/filters, toolbar, reporting
  tray, map, and selected detail bounding boxes exactly match the pre-edit baseline.
  The header is solid `rgb(11, 15, 21)` with no backdrop filter. Both transparent
  panels use 81% dark tint; text-token contrast remains at least 4.5:1 even over
  pure white imagery. Audio opt-in/muting/cleanup and reduced motion passed.

Browser review used headless Chromium with software WebGL. It verifies appearance
and interactions, not hardware GPU performance or speaker fidelity. The existing
30fps target and 1.5× resolution cap remain unchanged. Build output retains the
existing Cesium large-chunk advisory; Python 3.14 emits resource warnings in the
unchanged ingest tests. Both verification commands exit successfully.

## Screenshots

- [Severity beacons in the normal overview](screenshots/beacons-desktop.png)
- [A later beacon pulse phase](screenshots/beacons-phase-two.png)
- [Overview](screenshots/overview-desktop.png)
- [Transparent event detail and reporting](screenshots/detail-desktop.png)
- [Optional audio controls](screenshots/sound-controls-desktop.png)
- [Phone audio controls](screenshots/sound-controls-phone.png)

[Browser measurements](browser-results.json) include panel materials, desktop
bounding boxes, expanded phone controls, and the empty page-error list. Camera
navigation when selecting a report is the existing behavior. Snapshot freshness
and reporting content reflect the captured local data.

The beacon revision adds ordinary marker pulses rather than limiting pulsing to
fullscreen/selection. Critical and selected beacons draw after quieter reports
at coincident fixes; the reporting order and every event coordinate remain intact.
The 40-test web verification passed, followed by the globe regression for normal
overview pulsing, severity colors, expanding red rings, and reduced-motion/hidden
phase suspension. Desktop/mobile browser checks produced no errors and unchanged
layout measurements. The later normal-overview capture verifies final stacking.

## Zoom-responsive beacons and Earth rotation

Beacon halos now gain width, brightness and pulse amplitude as the camera moves
closer, reaching a capped peak at the minimum permitted zoom. Pale circle outlines
are removed; small severity-colored cores retain the exact plotted location.
Earth rotation starts enabled and has a toggle under Layers → Appearance.
Normal mode uses the IERS mean Earth rate; Time lapse uses one turn per hour,
with solar time accelerated by the same factor. Rotation preserves camera latitude,
distance and orientation and carries imagery and reports together. It pauses
during navigation, close inspection, selected reports/regions/flights, reduced
motion and hidden/covered views. Navigation resumes after eight seconds idle.

The full 40-test verification passed for this revision. A browser check exposed
that clamping frame time slowed physical rotation under software rendering; the
final correction uses elapsed time with explicit pause resets. The globe regression
then passed with a new slow-frame test, and final Astro diagnostics reported zero
errors, warnings and hints. Desktop/mobile browser checks retain identical site
geometry, readable Appearance buttons, working keyboard close, and no page errors.
The HTTP smoke check passed for 35 modules, three views and 500 events using fresh
connections; the default pooled-connection run disconnected at the Cesium CSS
module. Application source and dev-server configuration were unchanged by that
test workaround.

[Native WebGL measurements](rotation-browser-results.json) record rotation rates
of 0.00007292115 rad/s normally and 0.00174532925 rad/s in Time lapse. The same
critical report has halo widths of 42px at 6,800 km, 54.54px at 10 km and 75.6px at
the nearest zoom, with correspondingly stronger light. Browser instrumentation
exposed runtime objects only in the intercepted test response, not in the site.
The [updated overview](screenshots/rotation-overview.png) retains the original
framing and star field. [Desktop rotation controls](screenshots/rotation-controls.png)
and [phone controls](screenshots/rotation-controls-phone.png) show full Appearance
labels; the phone popover fits within the 390×844 viewport. The final production
build produced 504 pages, and formatting checks passed. Checks use software WebGL
and do not certify GPU frame rate.
