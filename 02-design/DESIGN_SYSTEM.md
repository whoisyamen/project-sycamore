# Sycamore design system

The September 29, 2026 direction implements the approved [Horizon, Nocturne Desk,
and Obsidian Index concepts](ui-concepts/2026-09-29/dark-design-prompts.md).
It supersedes the September 24 olive interface. The three views share one dark
material system while preserving their distinct compositions.

## Shared visual language

Obsidian backgrounds, graphite surfaces, cool silver copy, and steel-blue
interaction accents connect the workspace. Copper is an editorial detail in
Nocturne, with sage reserved for status. Severity colors continue to describe
automated classifications; they do not imply independent verification.

Canonical tokens live in `g3-astro/src/styles/global.css`; view composition lives
in `g3-astro/src/styles/workspace.css`.

| Token | Value | Purpose |
| --- | --- | --- |
| `--bg` | `#0a0d12` | Page canvas |
| `--surface` | `#141a22` | Reading surfaces |
| `--raised` | `#25303a` | Elevated controls |
| `--border` | `#303944` | Dividers and control boundaries |
| `--text` | `#edf0f2` | Primary copy |
| `--muted` | `#a9b3bf` | Secondary copy |
| `--accent` | `#9bbdd5` | Focus, selection, navigation |
| `--warm` | `#d1b293` | Nocturne editorial details |
| `--sage` | `#a6c7b5` | Quiet data status |

Use the system sans stack for interface copy, Horizon, and Obsidian. Georgia
provides the Nocturne editorial hierarchy. No external fonts are required.
The shared masthead includes the branching-leaf mark, three navigation links,
search, and actual snapshot health. Borders are fine, corners restrained, and
keyboard focus visible. Images belong to actual retained reports; missing media
gets a quiet fallback rather than invented imagery. The concept PNGs contain
illustrative content, while the implementation uses actual snapshot content and
its real freshness state.

## Three connected views

- **Overview / Horizon (`/`):** a full-width orbital Earth, open featured-report
  overlay, compact controls, and a horizontal reporting tray. Satellite imagery
  opens by default. Aircraft remain available through Layers. Feed view provides
  a full reporting grid, and selected reports retain the existing source-detail
  panel. Globe effects, imagery detail, 30 fps target, and resolution cap remain
  intact. The horizon camera and quiet space background follow the approved PNG.
- **Threat desk / Nocturne (`/intelligence`):** an asymmetric editorial mosaic
  with a lead report, two secondary stories, source actions, and a subordinate
  satellite globe. Reading lenses and source context remain available through
  the toolbar and lower reading band. Existing topic, briefing, source, and
  paged lens sections keep their anchor links. The mosaic favors reports with
  available source imagery and labels itself as selected reporting; the full
  index remains one link away.
- **Reporting index / Obsidian (`/reporting`):** a spacious heading, matte dark
  cartographic globe, unified filters, and aligned report rows. Source context
  expands inline with Read source, Share, and Close details. Fifty reports load
  initially; Load more exposes the rest. Selected reports remain visible when
  filters or pagination exclude them, with a clear note. No detail sidebar.

Search and topic, severity, time, source, lens, corroboration, sort, and selected
report state use the existing URL contract. Navigation carries these parameters
between the three views. Shared links retain the selected report and filters.
Refreshes use the existing validated snapshot protocol and health semantics.
Mini-globes show representative locations grouped into geographic cells;
they disclose that locations are approximate and link to the full overview.

## Responsive behavior and access

Below 980px the masthead uses two rows; phones use three. Horizon keeps its
panoramic canvas with horizontally scrollable reporting. Its source-detail sheet
traps focus and makes the background inert on smaller screens; Escape and Close
restore focus. Nocturne stacks the mosaic and context sections. Obsidian becomes
a two-column report/source table; expanded details include location and published
time. Reading pages scroll normally, and the index health baseline stays visible.

Honor reduced motion, real touch targets, readable contrast, accessible form
labels, and keyboard shortcuts. Reporting remains readable when WebGL or imagery
fails. Snapshot delays, failures, empty data, and fictional demo data retain their
existing visible labels. Locations are not verified incident coordinates;
source-label counts are not feed-health checks; newly observed means ingestion
here within 48 hours. Dedicated advisory, regulatory, social, and dark-web feeds
remain outside this redesign.

Browser evidence and verification are recorded in the
[implementation handoff](../00-admin/HANDOFF-2026-09-29-HORIZON-NOCTURNE.md).
Automated DOM tests do not certify Cesium appearance or browser frame timing.
