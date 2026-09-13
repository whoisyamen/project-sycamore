# Sycamore Intelligence Baseline — Iteration 1.1.1

Status: COMPLETE (2026-09-10)
Scope: baseline tooling and documentation only. No runtime/schema/service change.

## What was measured

- Source state: 22 scoped files hashed (SHA-256) — see `source-state.json`.
  Git is not available in this tree (not a repo); the hash manifest is the
  source of truth. Rehashed after `g3-ingest/tools/baseline.py` was added.
- Verification suites:
  - Ingest: `python3 -m unittest discover -s tests -v` → **31 tests, OK**, exit 0, ~3.0 s.
  - Web: `npm run verify` → **21/21 pass**, exit 0, 316.6 s wall
    (216.9 s test duration includes full build).
  - Asset report: `npm run perf:report` → exit 0, 0.7 s. 931 files total,
    233,012,016 bytes on disk; **4,281,441 B bundled (1,143,120 B gzip)**.
    The globe chunk dominates (`_astro/globe.*.js`, 4,157,258 B / 1,114,568 B gzip).
- Live snapshot (read-only, local current data, not deployed freshness):
  `g3-astro/public/data/snapshot.json`, 508,961 B, SHA-256
  `ebdc088b391a2c68f7e70c8ec070b5e07b2cc1e3bcae3aa3f54757ccca983cc7`,
  355 events, `nextEventId` 402, lastSync=lastAttempt=1789075438867 ms
  (2026-09-10 21:24 UTC), health **degraded** — failedSources `["OpenSky flights"]`
  (the known live OSINT-layer state; not a regression). Schema-valid via
  `contracts.validate_snapshot`.
- Offline fixture benchmark (`g3-ingest/tools/baseline.py`, network fully mocked):
  10 cases × 5 reps. All passed. See `fixture-measurements.json` and
  `logs/fixture-benchmark.log`. Summary (median duration):

  | Case | median ms | events | health |
  | --- | --- | --- | --- |
  | identical source repeated | 14.7 | 1 | ok |
  | same URL / revised title | 11.1 | 1 | ok |
  | two outlets / same story | 5.7 | 1 | ok |
  | partial provider failure | 10.7 | 1 | degraded |
  | total failure after success | 11.3 | 1 | error |
  | successful empty feed | 5.1 | 0 | ok |
  | pruning / high-water | 22.3 | 2 | ok |
  | snapshot-only migration | 9.6 | 1 | ok |
  | scale 500 synthetic | 657.8 | 500 | ok |
  | scale 5,000 synthetic | 3,544.6 | 500 (cap) | ok |

  Scale notes: 5,000 synthetic records are processed in ~3.5 s median, but the
  snapshot is capped at `MAX_EVENTS=500` (today's projection cap) — synthetic
  records are not claimed archived. `nextEventId` correctly advances past the
  cap (5001) so pruning preserves the high-water mark.

## Producer/consumer map (symbol + file line)

| Boundary | Producer | Consumer | Contract / failure risk |
| --- | --- | --- | --- |
| Numeric ID / nextEventId | runner allocation: `_load_previous` setdefault (`runner.py:75`), `next_id` (`runner.py:215`), `next_id += 1` (`runner.py:245`) | routes/state/selection/validation: `boards/[id].astro:8-10` (params from event.id), `client/state.ts:32-33` (event from URL), `contracts.py:86` (nextEventId check), `data/validate.ts:24-27` (client-side check) | Link break or ID reuse. High-water survives pruning (fixture case 7). |
| Deduplication | `normalizer.dedupe_key` (`normalizer.py:700-712` — topic+coords+day+normalized title SHA-1) and URL set (`runner.py:217-220`) | `runner._cycle` merge (`runner.py:231-244`) | Same report vs event identity. Revised titles ignored; outlets merge (fixture cases 1-3). |
| V1 snapshot | `runner._publish` (`runner.py:121-129`) writes canonical snapshot first | `data/loader.ts:23-32`, `client/refresh.ts:3-13` (fetch+reject older), `client/site.ts:9-10,62-68` (accept + dispatch), `data/validate.ts:5-27` | Strict schema and latest-state selection. Atomic write + failure retention verified (test suite). |
| Compatibility mirrors | `runner._publish` after snapshot (`runner.py:127-129` — events.json, manifest.json) | `data/loader.ts:26-29` (compat read), `contracts.py:61-72` refs | Partial write vs canonical state. Mirrors written only after canonical commit; crash never compromises next cycle. |
| Geolocation | `normalizer.resolve_location` (`normalizer.py:306`), `_resolve_event_geo` (`normalizer.py:340`), `runner._validate_geolocation` (`runner.py:99-118`) | globe marker and detail copy: `client/dashboard.ts` (map layer), `types.ts:37-41` (geo tier/source honesty) | Approximate location presented as exact. Fail-closed on unsafe rows; tier-2 rows re-derived deterministically. |
| Source health | `runner._cycle` batch succeeded/failed (`runner.py:188-193`), `_failure` (`runner.py:132-138`), manifest health (`runner.py:283-286`) | status UI: `client/refresh.ts:11-13` (stale rejection), `client/site.ts:14` `dataStatus`, `types.ts:66` health shape | Attempt mistaken for success. Partial→degraded, total→error, empty→ok distinguishable (fixture cases 4-6). |
| Independent telemetry | `runner._osint_cycle` (`runner.py:141-182`) — flights/censys envelopes | globe/osint client (dashboard/globe layers), `types.ts` envelope shapes | Layer stale state vs event freshness. Failures feed cycle health; benchmark patches `_osint_cycle` to `[]` so runs stay offline. |
| Served data | local `public/data` (`runner.DEFAULT_OUT`, `runner.py:18`) + deploy mechanism | real browser/CDN (deployment header template restricts scripts and data caching — verify check) | Local success is not served freshness. Snapshot labeled local current data; deployed freshness requires a later gate. |

## Benchmark isolation guarantees

- `--out` is required; rejects paths resolving inside `g3-astro/public/data`
  or containing a live snapshot.
- Every cycle runs in a fresh `TemporaryDirectory`; fixtures are independent.
- `rss_client.fetch_all`/`to_articles` patched; `runner._osint_cycle` → `[]`;
  `media_pipeline.attach_media` → 0; GDELT fetch patched to raise if invoked;
  `use_gdelt=False`. Zero external requests (verified by patch side effects).
- Deterministic clock (`_now_ms` = base + step·call) makes timestamps
  reproducible; `perf_counter` measures wall duration.

## Acceptance checklist

- [x] Both existing verification suites completed with recorded exit codes (0/0).
- [x] No unexplained failures: ingest 31/31, web 21/21; live degraded status is
      the known OpenSky state.
- [x] Producer/consumer map includes IDs, strict schemas, timing and serving boundary.
- [x] Benchmark uses temporary outputs and makes zero external requests.
- [x] Baseline JSON contains measured counts/bytes/timing and truthful missing
      metrics (browser: not_measured with reason; scale caps called out).
- [x] Source-state manifest and command logs identify what was actually tested.
- [x] No runtime/schema/service change smuggled in (only `tools/baseline.py` added).
- [x] Next iteration named: **1.1.2-contracts.md**.

## Artifacts

- `source-state.json` — SHA-256 manifest of 22 scoped files
- `baseline.json` — machine-readable measurements
- `fixture-measurements.json` — raw per-rep fixture samples (10 × 5)
- `logs/ingest-tests.log`, `logs/web-verify.log`, `logs/perf-report.log`,
  `logs/fixture-benchmark.log` — command results, sanitized
- `g3-ingest/tools/baseline.py` — reusable offline benchmark/report collector

Next: 1.1.2 contracts. Do not start database implementation within this iteration.