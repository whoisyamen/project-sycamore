---
name: sycamore-performance
description: Audit and optimize Sycamore runtime and build performance while preserving its accepted Cesium globe quality, interactions, and source-data behavior.
---

Locate the Sycamore checkout and read g3-astro/PERFORMANCE.md and GLOBE.md. Work on g3-astro, not the archived prototypes. Record npm run build followed by npm run perf:report before changing code. Keep comparisons on the same data snapshot and dependency lockfile; report bytes separately from browser frame timings.

Inspect globe.ts rebuildFlights, prepareTrails, camera tier checks, polling and destruction before optimizing. Route histories are filtered/sorted per successful poll; Cartesian coordinates are prepared lazily and reused until the next snapshot. Do not redo history work per frame or mutate shared cached positions. Steady camera frames must not rebuild primitives. Preserve selected full history, ambient fading and all source fixes; timestamps are not altitude. Material.ColorType is the registered color material.

Keep image resolution, globe screen-space error, 30 fps target, controls, and data freshness semantics intact. Reducing these is a quality tradeoff requiring discussion, not a silent performance win. Water/time animation requires ongoing rendering; do not enable requestRenderMode without explicit invalidation for animation, camera movement, data, textures and controls.

Inspect callers before removing code or packages. The old MapLibre implementation has been removed; map.ts retains only the dashboard adapter contract. Do not delete ingestion generators, source assets, archives, or Cesium workers because they are absent from the main JS bundle. Cache only content-hashed _astro assets indefinitely; live /data snapshots remain no-store.

Run npm run verify after changes and npm run perf:report for the resulting production build. Use npm run test:dev against a running local server. For browser measurement, use a production preview and fixed viewport, device scale, camera locations and snapshot: warm imagery, record frame times while orbiting and zooming, then select flights, toggle layers, revisit tabs and check memory over repeated cycles. Check both imagery modes and reduced motion. Report unavailable browser measurements explicitly; DOM tests and gzip sizes do not establish FPS improvements.
