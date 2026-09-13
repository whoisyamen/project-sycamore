# Sycamore design system

Approved direction for the September 2026 local redesign: calm analyst, inspired
by Conflictly's map-first composition. Sycamore remains the local display name.

## Visual language

The map provides geographic context; readable headlines lead the interface.
Use near-black blue-gray surfaces, restrained cyan accents, hairline borders,
and generous separation between controls and reporting. Avoid ornamental live
counters, blinking severity, and persistent secondary information panels.

Canonical CSS tokens are in `g3-astro/src/styles/global.css`:

| Token | Value | Purpose |
| --- | --- | --- |
| `--bg` | `#0c1218` | Page and header |
| `--surface` | `#111a22` | Feed, details, cards |
| `--raised` | `#19242d` | Hover and selection surfaces |
| `--border` | `#2a3742` | Dividers |
| `--text` | `#e6edf0` | Headlines and body |
| `--muted` | `#9aaab6` | Secondary text |
| `--accent` | `#7ad5ce` | Active controls and highlights |

Use the system sans stack for content and system monospace for small section
labels and metadata. No external font fetches. Desktop feed headlines are 14px;
mobile headlines are 15px. Main body text remains comfortably readable.
Severity colors are restrained labels for the existing automated classifications;
they must not imply independent confirmation. No confidence percentage badges.

## Layout and interaction

Desktop (980px+): compact header, full-viewport map, left feed, right details only
when selected. Feed and detail panels scroll internally. Map controls remain
reachable. Remove the right sample outlook/markets panel and scrolling ticker.

Below 980px: compact two-row header, Map/Feed tabs, and full-height detail sheet.
The sheet traps focus and makes the background inert. Escape/close restores
focus. Feed remains usable when WebGL or tiles fail. Secondary pages use normal
document scrolling and collapse cards into one column below 600px.

Topic chips, severity/time selects, and search update the same state for map and
feed. Selected events survive filtering and data refresh while still present in
the current snapshot. Shared URLs restore every active filter and event.

Honor reduced motion for both CSS transitions and map camera movement. Keyboard
focus must remain visible. Never equate the animation of a UI element with data
freshness; use successful source timestamps and explicit outage states.

## Review checklist

Check 1440×900, 1024×768, 768×1024, and 390×844, plus 200% zoom and reduced
motion. Verify no overlap, reachable controls, no horizontal page overflow,
readable feed typography, source links, focus restoration, and map failure.
Browser visual review remains required; DOM tests are not layout verification.
