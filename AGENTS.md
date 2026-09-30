# Repository instructions

Active tree: `g3-astro` (site) and `g3-ingest` (Python ingest). `g1-prototype` and `g2-astro` are archives. Schemas live in `shared/`, not under `g3-astro/`.

Read `README.md`, then `03-architecture/iterations/REGISTER.md`. Iterations 1.1.1 through 1.2.2 are complete. Next card is 1.2.3. Do not treat `START_HERE.md` as a request to redo 1.1.1. Handoffs before 2026-09-11 are historical.

Skills: `skills/sycamore-recreate`, `skills/sycamore-performance`.

Do not recurse `node_modules`, `dist`, `.astro`, or `g3-astro/public/cesium`. Regenerate with `npm ci` and the Makefile. Do not read or copy `_private/`.
