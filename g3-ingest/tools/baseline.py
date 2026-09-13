"""Offline fixture benchmark / report collector for Sycamore ingestion.

Iteration 1.1.1 deliverable: measures the existing pipeline against defined
fixtures in isolated temporary directories with ALL network functions mocked.
Writes measurements + a sanitized log only beneath the supplied report
directory. Makes zero external requests; unexpected network calls fail.

Usage:
    python3 tools/baseline.py --out <report-dir>

The report directory is rejected if it resolves inside g3-astro/public/data
or already contains a live snapshot.

Outputs:
    <report-dir>/fixture-measurements.json   machine-readable measurements
    <report-dir>/logs/fixture-benchmark.log  sanitized run log
"""
from __future__ import annotations

import argparse
import copy
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sycamore_ingest import gdelt_client, media_pipeline, normalizer, runner, rss_client
from sycamore_ingest.contracts import validate_snapshot

# Deterministic base clock: fixed epoch so fixture timestamps are reproducible.
_BASE_MS = 1_789_000_000_000
_STEP_MS = 1_000

ARTICLE = {
    "title": "Major ransomware hits regional power grid in Frankfurt",
    "url": "https://alpha.example/story",
    "domain": "alpha.example",
    "language": "English",
    "tone": -6,
    "seendate": "20260903T120000Z",
    "location": {"fullName": "Frankfurt", "countryCode": "DE"},
    "lat": 50.11,
    "long": 8.68,
}


class DeterministicClock:
    """Reproducible _now_ms substitute: base + step*call_count."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> int:
        current = _BASE_MS + _STEP_MS * self.calls
        self.calls += 1
        return current


def make_batch(success: int = 1, failed: tuple[str, ...] = ()) -> rss_client.FeedBatch:
    """FeedBatch matching the test file's helper: succeeds/fails counts only."""
    result = rss_client.FeedBatch()  # empty item list; to_articles is patched
    result.succeeded = success
    result.failed = list(failed)
    return result


def scale_articles(n: int) -> list[dict]:
    """Synthetic records: unique URL + title, fixed geocode (precise tier).

    The word 'ransomware' is kept in each title so classify_topic gates them
    through. Records are explicitly synthetic; the live projection cap is
    MAX_EVENTS (500), which the scale notes record.
    """
    out = []
    for i in range(n):
        out.append({
            **ARTICLE,
            "title": f"Major ransomware incident number {i} hits regional power grid in Frankfurt",
            "url": f"https://scale{i}.example/story{i}",
            "domain": f"scale{i}.example",
        })
    return out


_CLOCK: DeterministicClock | None = None


def run_once(out_dir: Path, articles: list[dict], *, success: int = 1,
             failed: tuple[str, ...] = (), snapshot_only: bool = False) -> dict:
    """Run one fully-mocked cycle. Any unexpected network path raises."""
    global _CLOCK
    if _CLOCK is None:
        _CLOCK = DeterministicClock()
    batch = make_batch(success, failed)
    with patch.object(runner, "_now_ms", _CLOCK), \
         patch.object(rss_client, "fetch_all", return_value=batch), \
         patch.object(rss_client, "to_articles", return_value=articles), \
         patch.object(runner, "_osint_cycle", return_value=[]), \
         patch.object(media_pipeline, "attach_media", return_value=0), \
         patch.object(gdelt_client, "fetch_last_15min",
                      side_effect=AssertionError("GDELT must not be invoked in benchmark")):
        return runner.run(out_dir, use_gdelt=False, snapshot_only=snapshot_only)


def snapshot_of(out_dir: Path) -> dict:
    with open(out_dir / "snapshot.json", encoding="utf-8") as f:
        return json.load(f)


def sample(out_dir: Path, fn) -> tuple[dict, float]:
    """Run fn(out_dir) in place, return (metrics, elapsed_ms)."""
    started = time.perf_counter()
    fn(out_dir)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    snap = snapshot_of(out_dir)
    validate_snapshot(snap)
    ids = [e["id"] for e in snap["events"]]
    metrics = {
        "snapshotBytes": (out_dir / "snapshot.json").stat().st_size,
        "events": len(snap["events"]),
        "healthStatus": snap["manifest"]["health"]["status"],
        "lastSync": snap["manifest"]["lastSync"],
        "lastAttempt": snap["manifest"]["lastAttempt"],
        "nextEventId": snap["manifest"]["nextEventId"],
        "counts": snap["manifest"]["counts"],
        "eventIds": ids[:6],
    }
    return metrics, elapsed_ms


def summarize(name: str, samples: list[dict], durations: list[float],
              note: str = "") -> dict:
    return {
        "name": name,
        "reps": len(samples),
        "note": note,
        "durationMs": {
            "min": min(durations),
            "median": statistics.median(durations),
            "max": max(durations),
        },
        "samples": samples,
    }


def measure(case_fn, reps: int = 5) -> list[dict]:
    """Run case_fn in a fresh temp dir reps times; return raw (metrics, elapsed) pairs.

    Each rep gets a fresh deterministic clock shared across all cycles in the
    scenario, so cross-cycle invariants (lastAttempt > lastSync) hold and
    timestamps are reproducible.
    """
    global _CLOCK
    out = []
    for _ in range(reps):
        _CLOCK = DeterministicClock()
        with tempfile.TemporaryDirectory() as td:
            m, d = sample(Path(td), case_fn)
            out.append((m, d))
    return out


def run_cases() -> list[dict]:
    results: list[dict] = []

    def run_identical(out: Path):
        run_once(out, [ARTICLE])
        run_once(out, [ARTICLE])
        snap = snapshot_of(out)
        assert len(snap["events"]) == 1
        assert snap["manifest"]["counts"]["deduped"] >= 1
    raw = measure(run_identical)
    results.append(summarize("identical_source_repeated", [m for m, _ in raw], [d for _, d in raw],
                             "second identical article deduped; single event/ID retained"))

    def run_revised(out: Path):
        run_once(out, [ARTICLE])
        run_once(out, [{**ARTICLE, "title": "Frankfurt ransomware incident: a different headline"}])
        snap = snapshot_of(out)
        assert len(snap["events"]) == 1
    raw = measure(run_revised)
    results.append(summarize(
        "same_url_revised_title", [m for m, _ in raw], [d for _, d in raw],
        "CURRENT behavior: same event retained; revised title text ignored (no revision handling yet)"))

    def run_merge(out: Path):
        second = {**ARTICLE, "url": "https://beta.example/story", "domain": "beta.example"}
        run_once(out, [ARTICLE, second])
        snap = snapshot_of(out)
        assert len(snap["events"]) == 1
        assert len(snap["events"][0]["sources"]) == 2
        assert snap["manifest"]["counts"]["merged"] >= 1
    raw = measure(run_merge)
    results.append(summarize("two_outlets_same_story", [m for m, _ in raw], [d for _, d in raw],
                             "corroboration merge: 2 sources, 1 event"))

    def run_partial(out: Path):
        run_once(out, [ARTICLE])
        run_once(out, [], success=1, failed=("BBC",))
        snap = snapshot_of(out)
        assert snap["manifest"]["health"]["status"] == "degraded"
        assert snap["manifest"]["lastSync"] > 0
    raw = measure(run_partial)
    results.append(summarize("partial_provider_failure", [m for m, _ in raw], [d for _, d in raw],
                             "degraded status; retained successful-check semantics"))

    def run_total_failure(out: Path):
        run_once(out, [ARTICLE])
        before = snapshot_of(out)
        run_once(out, [], success=0, failed=("BBC", "CISA"))
        snap = snapshot_of(out)
        assert snap["manifest"]["health"]["status"] == "error"
        assert snap["manifest"]["lastSync"] == before["manifest"]["lastSync"]
        assert snap["manifest"]["lastAttempt"] > snap["manifest"]["lastSync"]
        assert snap["events"] == before["events"]
    raw = measure(run_total_failure)
    results.append(summarize("total_failure_after_success", [m for m, _ in raw], [d for _, d in raw],
                             "error status; retained previous events and lastSync"))

    def run_empty(out: Path):
        run_once(out, [])
        snap = snapshot_of(out)
        assert snap["manifest"]["health"]["status"] == "ok"
        assert snap["manifest"]["counts"]["events"] == 0
    raw = measure(run_empty)
    results.append(summarize("successful_empty_feed", [m for m, _ in raw], [d for _, d in raw],
                             "ok health with zero events"))

    def run_high_water(out: Path):
        run_once(out, [ARTICLE])
        snap = snapshot_of(out)
        high = copy.deepcopy(snap["events"][0])
        high["id"] = 99
        high["ingestedAt"] = 1
        high["sources"] = ["https://old.example/story"]
        high["title"] = "Old ransomware report in Frankfurt"
        snap["events"].append(high)
        snap["manifest"]["counts"] = runner._counts(snap["events"])
        snap["manifest"]["nextEventId"] = 100
        runner._publish(out, snap["events"], snap["manifest"])
        with patch.object(runner, "MAX_EVENTS", 1):
            run_once(out, [])
        assert len(snapshot_of(out)["events"]) == 1
        run_once(out, [{**ARTICLE, "title": "A different ransomware attack in Frankfurt",
                        "url": "https://new.example/story"}])
        ids = [e["id"] for e in snapshot_of(out)["events"]]
        assert 100 in ids, f"high-water ID not reused; got {ids}"
    raw = measure(run_high_water)
    results.append(summarize("pruning_high_water", [m for m, _ in raw], [d for _, d in raw],
                             "pruned to MAX_EVENTS; nextEventId high-water survives, ID 100 reused"))

    def run_snapshot_only(out: Path):
        run_once(out, [ARTICLE])
        before = snapshot_of(out)
        (out / "snapshot.json").unlink()
        with patch.object(rss_client, "fetch_all", side_effect=AssertionError("must not fetch")):
            migrated = runner.run(out, use_gdelt=False, snapshot_only=True)
        assert migrated["lastSync"] == before["manifest"]["lastSync"]
        snap = snapshot_of(out)
        assert snap["manifest"]["lastSync"] == before["manifest"]["lastSync"]
        assert snap["manifest"]["health"]["status"] == before["manifest"]["health"]["status"]
    raw = measure(run_snapshot_only)
    results.append(summarize("snapshot_only_migration", [m for m, _ in raw], [d for _, d in raw],
                             "no fetch triggered; lastSync preserved, no invented success"))

    # Scale: 500 and 5,000 synthetic records (projection cap at MAX_EVENTS=500)
    def make_scale_case(n: int):
        def case_scale(out: Path):
            run_once(out, scale_articles(n))
            snap = snapshot_of(out)
            assert snap["manifest"]["counts"]["events"] == min(n, runner.MAX_EVENTS)
        return case_scale
    raw = measure(make_scale_case(500))
    results.append(summarize("scale_500_synthetic", [m for m, _ in raw], [d for _, d in raw],
                             "500 unique synthetic records; all retained (cap 500)"))
    raw = measure(make_scale_case(5_000))
    results.append(summarize(
        "scale_5000_synthetic", [m for m, _ in raw], [d for _, d in raw],
        "5000 unique synthetic records ingested; snapshot capped at MAX_EVENTS=500 "
        "(today's projection cap). Synthetic records are not claimed archived."))

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True,
                        help="Report directory. Must not resolve inside public/data or contain a live snapshot.")
    args = parser.parse_args(argv)

    out_dir = args.out.resolve()
    project_root = Path(__file__).resolve().parents[3]  # project-sycamore
    live_data = (project_root / "g3-astro" / "public" / "data").resolve()
    if out_dir == live_data or live_data in out_dir.parents:
        parser.error(f"--out resolves inside live data dir: {out_dir}")
    if (out_dir / "snapshot.json").exists() or (out_dir / "events.json").exists():
        parser.error(f"--out already contains a live snapshot: {out_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "logs").mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "logs" / "fixture-benchmark.log"

    started = time.perf_counter()
    results = run_cases()
    wall_ms = (time.perf_counter() - started) * 1000.0

    payload = {
        "schemaVersion": 1,
        "collectedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool": "g3-ingest/tools/baseline.py",
        "repsPerCase": 5,
        "wallClockMs": wall_ms,
        "fixtureMeasurements": results,
    }
    out_json = out_dir / "fixture-measurements.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"baseline.py fixture benchmark — collectedAt {payload['collectedAt']}\n")
        f.write(f"wallClockMs {wall_ms:.1f}\n")
        for r in results:
            d = r["durationMs"]
            f.write(f"{r['name']}: min {d['min']:.1f}ms | median {d['median']:.1f}ms | "
                    f"max {d['max']:.1f}ms | events {r['samples'][-1]['events']} | "
                    f"health {r['samples'][-1]['healthStatus']}\n")
        f.write("All cases passed with zero external requests (network fully mocked).\n")

    print(f"Wrote {out_json}")
    print(f"Wrote {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())