---
name: sycamore-recreate
description: Recreate or restore the Sycamore Astro/Cesium dashboard from its source checkout, preserving its accepted globe design, data contracts, and local runtime.
---

Locate the Sycamore checkout (current location: /home/yams/operations/project-sycamore). Read README.md, g3-astro/GLOBE.md, and g3-astro/PERFORMANCE.md. The active website is g3-astro; g1-prototype and g2-astro are archives, not dependencies.

For a clean recreation, retain g3-astro source, package-lock.json, public data/images/effects, g3-ingest, shared schemas, and these skills. Generated node_modules, .astro, dist, logs and public/cesium are unnecessary: npm ci and prebuild regenerate dependencies and Cesium assets. Do not copy _private, credentials, or machine services. Snapshot data is dated coverage, not a claim of current freshness.

Use the Node version supported by the checked-in engines and README, then run npm ci in g3-astro. Run npm run verify and the Python ingestion tests from the root Makefile. Start npm run dev on 127.0.0.1:4321; inspect the process already using that port before starting another. Restore source-provided public data rather than fabricating missing reporting. Ingestion can be run separately as documented in g3-ingest/README.md.

Preserve the accepted appearance: dark/satellite globe, solar shading with night composite faded at close zoom, animated water with reduced-motion controls, compact control dock, spatial aircraft thinning, three-part fading tails, selected full recorded route and dimmed unrelated traffic. Keep 30 fps target, current resolution cap, and imagery detail unless the user requests a design change. Cesium routes require Material.ColorType, not the string 'Cesium.Color'.

Check desktop and mobile feed/map tabs, event filters and links, imagery/layer toggles, flight pin/unpin and zoom tiers. Automated globe tests substitute a Viewer shell and do not certify WebGL. Recreating locally does not authorize deployment or installed-service changes.
