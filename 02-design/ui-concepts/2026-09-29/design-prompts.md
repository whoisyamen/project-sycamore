# Sycamore UI concepts — September 29, 2026

Three visual design proposals generated with the built-in imagegen tool. No website code was written or changed. Reporting, timestamps, imagery, and interface controls in the images are illustrative; these are design mockups, not captures of an implemented site.

Recommended direction: Atlas Workspace for the main globe experience. Daylight Briefing emphasizes reading and scanning. Research Console keeps the reporting list, geographic context, and selected source visible together.

## Images

- [Atlas Workspace](01-atlas-workspace.png)
- [Daylight Briefing](02-daylight-briefing.png)
- [Research Console](03-research-console.png)

## Design research

- [Anthropic frontend-design skill](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md): grounded visual identity, deliberate typography, restrained decoration, and clear action labels. Applied as visual guidance only.
- [IBM Carbon data table guidance](https://carbondesignsystem.com/components/data-table/usage/): ample content width, unified search/filter toolbar, consistent rows, and progressive disclosure.
- [Nielsen Norman Group visual hierarchy](https://www.nngroup.com/articles/visual-hierarchy-ux-definition/): size, contrast, and grouping guide attention.
- Repository context: README.md, iteration register, DESIGN_SYSTEM.md, threat desk redesign plan, GLOBE.md, PERFORMANCE.md, and current QA globe screenshots.

## Final generation prompts

### 01-atlas-workspace

Use case: ui-mockup.
Asset type: high-fidelity desktop website redesign concept for Project Sycamore, a local-first global reporting dashboard covering cyber, geopolitical, maritime, and military reporting.
Create ONE complete polished browser-content screenshot, landscape 16:10, ideally 1920 × 1200. Full-bleed interface, crisp legible text, pixel-perfect product-design quality. No physical device, no perspective, no surrounding presentation board. This is the first of three distinct proposed redesigns: ATLAS WORKSPACE.

Design direction: a sophisticated, spacious dark analyst workspace. Retain Sycamore's character using mineral charcoal #141A17, layered forest-gray #202A24, warm ivory #F2F0E6, muted sage #A7B6A2, restrained amber #E8BB78. Color and hierarchy express function, not decoration. Crisp proportional sans-serif body text, a refined Georgia-like serif only for the page title, sparse tabular numbers. Minimal 10px rounding on actual panels, precise hairline separators. Expensive, quiet, purpose-built, strong alignment. No neon, generic SaaS KPI card row, sci-fi HUD, gratuitous gradients, or excessive all-caps.

Layout: narrow 190px left navigation; generous main workspace to its right. A clean 76px masthead shows the simple branching leaf emblem and exact brand "SYCAMORE"; below it the sidebar has "Overview" selected in amber, "Threat desk", then muted supporting items "Data health" and "About". At the bottom a unobtrusive status reads "Illustrative snapshot". Across the main top: title "Global overview", a wide search field "Search reporting or places", and small right-aligned text "Design concept · illustrative reporting". Under that a slim shared filter strip with "All topics", "All severity", "24 hours", and "Reset". Main content is roughly 65% spacious globe and 35% elegantly structured reporting pane, with no overlays blocking the globe.

Spatial anchor: a very beautiful scientifically plausible Cesium-style Earth as a real spherical globe, Africa and Europe visible, dark blue ocean with delicate natural water highlights, real satellite land detail, restrained atmosphere rim, soft day/night terminator, warm night lights on the dark side, a quiet near-black space backdrop with very sparse small stars. Earth occupies most of the central column. Sparse sage, amber and coral markers with no gratuitous connections or arcs. Preserve rich globe realism. A small discreet bottom globe dock reads "Layers", "Satellite", "−", "+", "Reset view". Beneath the globe, a simple Globe / Feed segmented switch with "Globe" selected. Small lower-left caption "Locations are approximate". A tiny key uses colored circles AND text "Critical", "Escalating", "Watching".

Reporting pane: heading "Reporting", small text "Latest first"; three readable rows with generous vertical rhythm, topic label, short headline, place and source metadata. First selected row has an amber left edge and a subtle tinted background. Exact sample headlines:
"Shipping disruption reported in Red Sea" with "Maritime", "Red Sea · approximate", "Example news desk".
"Vendor publishes security update" with "Cyber", "Global", "Example technology desk".
"New policy proposal under review" with "Geopolitical", "Europe · approximate", "Example policy desk".
Selected-item summary occupies the lower part of the pane with exact title "Report context", short body "A sample report showing how geography, source attribution, and article context stay together.", and well-defined actions "Read source" and "Share". Include a restrained outlined panel at the bottom titled "Data health", body "Last source check: illustrative snapshot". The fictional content is clearly concept data, never label it verified intelligence or live breaking news.

Constraints: all content must look shippable as a desktop web application, not a marketing landing page. Restrained icon system, accessible high text contrast, realistic clickable controls, no placeholder gibberish or excessive tiny text, ample whitespace, faithfully render the important quoted strings. Do not add logotypes of other companies, confidence percentages, invented threat scores, AI chat, subscription upsells, charts with fabricated axes, live counters, or disconnected future capabilities.

### 02-daylight-briefing

Use case: ui-mockup.
Asset type: high-fidelity desktop website redesign concept for Project Sycamore, a source-based reporting workspace for cyber, geopolitical, maritime, and military news.
Create ONE complete polished browser-content screenshot, landscape 16:10, ideally 1920 × 1200. Full-bleed interface, sharp clear typography, no monitor frame, no perspective, no surrounding design board. This is a distinctly different second proposed redesign: DAYLIGHT BRIEFING.

Design direction: a fresh, modern light analyst desk. Porcelain white #F7F9F6 canvas, white working surfaces, dark pine ink #22382E, restrained sage #6D8575, brass #B58B45, soft gray-green borders #DEE5DE. The design is warm and calm but contemporary and data-focused. Compact proportional sans-serif for content, one graceful Georgia-like serif page headline, balanced moderate weights. Generous spacing, well-defined grouping, 14px rounding only on the globe enclosure and the selected context panel, mostly open content rows instead of identical card grids. No terracotta, neon, generic KPI dashboards, newspaper broadsheet columns, huge promotional hero, or decorative gradient washes.

Layout: a full-width top header around 80px tall. A simple stylized branching leaf emblem and exact name "SYCAMORE" at left; nav "Overview" selected with a fine sage underline and "Threat desk"; a wide search box "Search reporting or places" across the center-right. Top-right small text "Design concept · illustrative reporting". Next a generous, carefully aligned workspace title area: headline "The global picture.", a short supporting line "Sourced reporting, with geographic context.", and on the right a visible understated status "Last source check" / "Illustrative snapshot".

The main workspace is a balanced asymmetric two-column composition. Left about 55% width is a clean reporting desk with the heading "Reporting", a quiet toolbar for "All topics", "All severity", "24 hours", and "Latest first". Three broad beautiful report rows, each with a small rounded editorial photograph thumbnail, a short topic label, large readable headline, source and geographic metadata. First row selected with subtle sage tint. Images should be simple generic news imagery, never a real person or company logo: maritime ships, an abstract computing device, an institutional building. Exact row content:
"Maritime" / "Shipping disruption reported in Red Sea" / "Example news desk" / "Red Sea · approximate".
"Cyber" / "Vendor publishes security update" / "Example technology desk" / "Global".
"Geopolitical" / "New policy proposal under review" / "Example policy desk" / "Europe · approximate".
A clean smaller section underneath reads "Explore the Threat desk" with two horizontal useful entries "Vulnerabilities & exploits" / "Text matches in reporting" and "Policy & regulation" / "Mentions in reporting". These are existing reading views of reporting, not verified alerts.

Right about 45% is one striking globe enclosure, dark pine-charcoal inside with subtle near-black space backdrop. A high-detail real spherical Earth, satellite continents, natural blue oceans, delicate sunlit water texture, soft terminator and warm night lights, Europe and Africa in view, restrained atmosphere, scattered colored event dots. The globe is still a core spatial anchor, not a decorative background, around 500px diameter. Its panel header reads "Geographic context"; compact bottom controls "Layers", "Satellite", "−", "+", and tiny caption "Locations are approximate". Below it a rounded ivory-white source context panel titled "Selected report", repeating short headline "Shipping disruption reported in Red Sea", short copy "Open the original reporting for detail and attribution.", and strong pine action "Read source" beside quiet "Share".
A modest bottom strip aligns across the workspace, exact text "Globe" and "Feed" as a segmented view control, plus "Reporting refreshes every 60s while visible". Everything is readable and realistic.

Constraints: this must look like a working research web application redesigned for daylight use. Accurate alignment, obvious navigation and selection, clear contrast, elegant professional hierarchy. Keep all sample data explicitly illustrative. Render important quoted copy correctly. Do not invent confidence scores, real-time verification claims, threat meters, paid features, bots, extra charts, excessive badges, or fake operational telemetry.

### 03-research-console

Use case: ui-mockup.
Asset type: high-fidelity desktop website redesign concept for Project Sycamore, a professional sourced-reporting and geographic analysis workspace.
Create ONE complete desktop web-app browser-content screenshot, landscape 16:10, ideally 1920 × 1200. Full-bleed, perfectly front-on, sharp readable typography, no computer or phone frame, no surrounding artwork. Third distinct proposed redesign: RESEARCH CONSOLE.

Design direction: a compact, carefully organized information-first research console. Slate navy #101820 background, muted blue-gray #1C2A34 working surfaces, warm white #F0F2EC text, sea-glass #9CBEB2 active accent, amber #D8AF72 secondary context, coral reserved for severity dots. This is restrained professional application design with a disciplined 8px spacing rhythm and clear hierarchies. Elegant proportional sans-serif throughout, strong 26px headings, 16px readable report text, sparse tabular timestamps. Four-pixel corner rounding, slim structured separators, no neon cyberpunk, HUD, sci-fi radar, fake network nodes, generic metric-card strip, or glassmorphism.

Layout: a compact 70px full-width masthead with a small branching leaf emblem and exact brand "SYCAMORE", navigation "Overview" selected and "Threat desk". Center has a broad search field "Search reporting or places". Far right an unobtrusive amber outlined label "Illustrative snapshot", with a small second line "Design concept".
Below the header a single functional toolbar with title "Reporting workspace", filters "All topics", "All severity", "24 hours", an unobtrusive "Reset", and a view switch "Workspace" selected / "Feed". The rest of the page is an elegant three-pane research workspace. Left about 40% wide contains a highly readable sortable reporting list; center about 35% contains a large richly detailed interactive globe; right about 25% contains the selected report's source context. Provide generous pane padding and exact aligned top boundaries. No decoration masquerading as data.

Left pane: title "Reporting", small supporting text "Latest first". A compact column-header line "Report" and "Source". Five consistent report rows, each with topic and an actual one- or two-line readable headline, source and approximate geographic metadata. First row selected with a muted sea-glass outline and narrow sea-glass selection edge. Exact first three rows:
"Maritime" / "Shipping disruption reported in Red Sea" / "Example news desk" / "Red Sea · approximate".
"Cyber" / "Vendor publishes security update" / "Example technology desk" / "Global".
"Geopolitical" / "New policy proposal under review" / "Example policy desk" / "Europe · approximate".
Remaining rows use "Military" / "Regional exercise reported" / "Example regional desk" and "Maritime" / "Port operations resume" / "Example shipping desk".
No large thumbnails, let clear text and selection state carry the design. A quiet lower-left area titled "Data health", with body "Last source check: illustrative snapshot" and "Source links remain available".

Center pane: header "Globe" with small "Layers" control. A realistic high-fidelity Cesium-style sphere showing the eastern Mediterranean, northeast Africa, and Arabian Peninsula from orbit, natural dark satellite texture, blue ocean highlights, soft solar terminator, warm night lights, subtle rim and a sparse dark star backdrop. Event dots match the rows with the selected Red Sea dot amber and the rest dimmed. A small direct label near the selected geographic area reads "Red Sea". The globe must remain spherical and plausible, not a flat map. Compact bottom controls "Satellite", "−", "+", "Reset view"; tiny text "Locations are approximate". Small color-and-word legend for "Critical", "Escalating", "Watching".

Right pane: header "Report context" with a small close icon. Topic "Maritime". Large clear headline "Shipping disruption reported in Red Sea". Short body "Illustrative article context. Read the original source for the reported details." Fine divider. Three clearly stacked metadata groups: "Source" / "Example news desk"; "Location" / "Red Sea · approximate"; "Coverage" / "Source-based reporting". A restrained amber primary button "Read source" and secondary outlined "Share". Further down a small disclosure titled "About this view", text "Classification is automated. Geographic locations may be approximate." A bottom text link "Open Threat desk".

Global bottom status bar: "Reporting refreshes every 60s while visible" at left, "Concept data" at right. Make the design feel usable for long reading sessions, with intentional hierarchy, convincing icon sizing, consistent controls and accessible contrast. Do not add unsupported confidence numbers, threat scores, automated verification, entity graphs, AI assistants, trading charts, animated-looking trails, or real news-provider logos. Render all important quoted labels verbatim and keep sample reporting clearly illustrative.

