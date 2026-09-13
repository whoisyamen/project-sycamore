# Sycamore ingestion

Python 3.10+ on Linux; standard library only. Curated RSS is primary. `--gdelt`
adds optional GDELT coverage without replacing RSS. Existing source definitions
are in `sycamore_ingest/rss_client.py`.

```sh
python3 -m sycamore_ingest.runner
python3 -m sycamore_ingest.runner --gdelt
python3 -m sycamore_ingest.runner --out /tmp/sycamore-data
python3 -m sycamore_ingest.runner --snapshot-only
python3 -m unittest discover -s tests -v
```

`--snapshot-only` migrates existing JSON without fetching or advancing the
successful-sync timestamp. `--first` is retained as a no-op compatibility flag.
The default output remains `../g3-astro/public/data/`.

## Pipeline

1. Fetch each RSS source and record success or failure, including parse failures.
2. Normalize headlines, source summaries, timestamps, topics, severity, and known
   locations. Reject records violating the shared event contract.
3. Deduplicate source URLs and merge matching story keys across outlets, including
   articles arriving in the same cycle. Classification rules are unchanged.
4. Refresh existing sourcing estimates and retain up to 500 recent ingested events.
5. Validate and atomically replace `snapshot.json` containing events and manifest.
6. Write compatibility `events.json` and `manifest.json` mirrors.

A filesystem lock serializes overlapping local cycles. Temporary files use
unique names, flush to disk before rename, and are removed on failure.
Consumers and the next cycle read the snapshot as the canonical committed state.
A corrupt existing snapshot fails closed rather than resetting IDs or data.

`manifest.lastSync` is the last successful source check; `lastAttempt` records
attempts separately. `health.status` is `ok`, `degraded` for partial failures, or
`error` for total failure. A total failure preserves the previous events and
successful timestamp. A successful empty fetch is valid. `nextEventId` persists
the high-water mark across pruning. Old optional event fields remain readable.

## Contracts and tests

`shared/schemas/` is authoritative. `contracts.py` implements the schema keywords
used here without third-party runtime packages and rejects unsupported keywords.
The site compiles the same schemas with Ajv before builds and tests. The Python
suite covers source health, deduplication, ID persistence, schema failures, and
atomic output. The original normalizer script also runs within that suite.

Iteration 1.1.2 added intelligence schemas under `shared/schemas/intelligence/`,
an explicit schema registry (`validate_intelligence`), cross-object checks
(`check_index`/`check_detail`), and stable identity helpers (`identity.py`) with
cross-language canonical-hash parity fixtures.

## Archive shadow mode (iteration 1.2.1)

The JSON pipeline remains the authority. Shadow mode adds a durable SQLite
archive (stdlib `sqlite3`) that observes the SAME fetched batch before
URL-skip/dedupe and before `events[:MAX_EVENTS]` pruning, so history survives
the live projection cap.

```sh
# Development/test only — use a TEMPORARY path outside the repo.
python3 -m sycamore_ingest.runner --out /tmp/sycamore-data --mode shadow \
    --archive /tmp/sycamore-archive.sqlite
```

Rules enforced by `runner.run(mode=...)`:

- `legacy` (default) requires no archive and behaves exactly as before.
- `shadow` requires an explicit `--archive` path that must NOT live under
  `g3-astro/public/` or `g3-astro/dist/`. Invalid configuration is rejected
  before any fetch — no guessed private paths.
- Sources are never fetched twice; the same batch feeds both the projector and
  the archive.
- Archive writes are best-effort: a shadow DB failure records a `shadow_gaps`
  row and the legacy output still publishes unchanged. Shadow gaps are never
  labeled as continuous history.
- Migrations under `sycamore_ingest/migrations/` are applied transactionally
  with SHA-256 checksums; editing an already-applied migration is rejected.

## Archive mode (iteration 1.2.2)

Archive mode switches authority from the JSON files to the durable archive:
`publication_jobs` (migration 002) stores replayable, immutable v1 payloads and
the snapshot files are a forward-only projection of committed payloads. Enabled
for testing/manual runs only — production stays on legacy/shadow until the 1.2.3
cutover.

```sh
# Development/test only — use a TEMPORARY path outside the repo.
python3 -m sycamore_ingest.runner --out /tmp/sycamore-data --mode archive \
    --archive /tmp/sycamore-archive.sqlite
```

Bootstrap rule (fail-closed): the first archive-mode run needs a committed state.
Start it with the current snapshot directory and `--snapshot-only`, which imports
existing events under a stable identity and publishes job #1 without any fetch:

```sh
python3 -m sycamore_ingest.runner --out /path/to/current/snapshot \
    --mode archive --archive /tmp/sycamore-archive.sqlite --snapshot-only
```

The same guardrails as shadow apply (explicit path outside `public/` and `dist/`,
rejected before any fetch). After bootstrap, `nextEventId` is reconciled to the
DB high-water; no allocation below an imported ID.

Recovery entry points (run automatically at the start of every archive-mode cycle,
before any fetch — manual use is for diagnostics):

- `publisher.replay(archive, out_dir)` — publishes pending jobs in strictly
  increasing sequence order: validate payload, atomic-replace `snapshot.json`
  plus mirrors, then acknowledge. Repeating a job is harmless (identical bytes);
  replay never refetches sources.
- `publisher.sync_mirrors(archive, out_dir)` — rewrites on-disk snapshot/mirrors
  from the newest published payload when they are missing or divergent, so a
  crash between file write and ack self-heals without refetching.

```python
from pathlib import Path
from sycamore_ingest import publisher
from sycamore_ingest.archive import Archive

with Archive('/tmp/sycamore-archive.sqlite') as a:
    print(publisher.replay(a, Path('/tmp/sycamore-data')))       # list[int] of sequences (re)written
    print(publisher.sync_mirrors(a, Path('/tmp/sycamore-data'))) # True when files were repaired
```

A total source failure still produces a publication (previous events retained,
`lastSync` preserved, `lastAttempt` advanced, health `error` with `failedSources`)
inside the same transaction as the `ingest_runs` row.

Live vs synthetic data stay distinct. A 90-day archive is a load result, not
proof that 90 days of actual reports were collected.

## Installed service

The repository's `systemd/` files retain their original paths and entrypoint.
This refactor does not install/reload/enable services. Existing timers read the
updated module on their next invocation. Use `journalctl --user -u
sycamore-ingest.service` to inspect attempts. A total source failure exits nonzero
and still publishes an error snapshot with the last valid events.

The service writes local files; it does not expose a network listener or publish
CDN data. No new sources, credentials, or accounts are needed.

## Censys configuration

The optional Censys layer needs `CENSYS_PERSONAL_ACCESS_TOKEN` in `_private/runtime.env`
(file mode 600). The service loads this through `EnvironmentFile`; after changing
an installed unit, run `systemctl --user daemon-reload`. The key stays server-side.
For manual ingestion from `g3-ingest/`, load the trusted local environment first:

```sh
set -a
. ../_private/runtime.env
set +a
python3 -m sycamore_ingest.runner
```

Save exported globe selections as `g3-astro/public/data/regions.json`, or use
an object such as `{"regions":[{"kind":"country","country_code":"US","name":"United States"}]}`
with the countries you intend to sample. Missing keys or missing/empty regions
are logged as skipped. Malformed region files and request failures preserve the
previous sample. Successful cycles log the published sample count.

Set `CENSYS_ORGANIZATION_ID` in the same environment file when using organization
access; otherwise Censys uses the personal wallet where applicable. The token is
a Platform Personal Access Token, not the legacy API ID/secret pair. Existing
Shodan credentials are unused; the runner now publishes `censys.json`.

The client uses `POST https://api.platform.censys.io/v3/global/search/query`,
bearer authorization, and a JSON body containing CenQL `query`, `page_size`, and
`fields`. It reads `result.hits[].host_v1.resource`, taking coordinates from
`location.coordinates` and observed ports from `services[].port`. Country queries
use `host.location.country_code`; boxes become `geo_distance` radius queries,
which can include surrounding areas. Coordinates are provider estimates.

Search requires a Starter, Search, or Core plan with the API Access role. Censys
Free supports known-asset lookups only; switching providers does not make
geographic API search free. HTTP 401/402/403/429 errors are logged without tokens
or raw response bodies. Requests consume credits: at most eight sequential
search pages per ingest cycle, 12 hits per region by default (3–50 configurable,
with at most 30 published per region). No pagination or rescans are requested.
The existing timer cadence still applies, so choose regions with your quota in mind.

References: [API setup and access](https://docs.censys.com/reference/get-started),
[search endpoint](https://docs.censys.com/reference/v3-globaldata-search-query),
[CenQL geography](https://docs.censys.com/docs/censys-query-language#geo_distance-function).
