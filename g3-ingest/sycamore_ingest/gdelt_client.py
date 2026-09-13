"""
GDELT DOC 2.0 client. No API key needed.

Returns a list of raw GDELT event records. Schema is documented at
https://blog.gdeltproject.org/gdelt-2-0-our-global-knowledge-graph/
but the fields we actually use are: GLOBALEVENTID, SQLDATE, EventCode,
Actor1Name, Actor2Name, GoldsteinScale, AvgTone, ActionGeo_FullName,
ActionGeo_CountryCode, ActionGeo_Lat, ActionGeo_Long, SOURCEURL.
"""
from __future__ import annotations
import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Any

# GDELT DOC 2.0 returns up to 250 events per call. We pull the last 15 min
# in article-coverage mode (not event-stream) so we get human-readable URLs
# attached to each record.
GDELT_DOC = "https://api.gdeltproject.org/api/v2/doc/doc"

USER_AGENT = "Sycamore/0.3 (https://github.com/local/sycamore; contact: local)"


def fetch_last_15min(query: str = "*", max_records: int = 250) -> list[dict[str, Any]]:
    """Pull articles from GDELT for the trailing 15 minutes.

    GDELT's `timespan=15min` covers the trailing window from now-15m to now.
    Returns raw GDELT records; normalization happens in normalizer.py.
    """
    return _fetch(query, "15min", max_records)


def fetch_last_24h(query: str = "*", max_records: int = 250) -> list[dict[str, Any]]:
    """Backfill helper used by runner.py to seed the events list on first run."""
    return _fetch(query, "24h", max_records)


def _fetch(query: str, timespan: str, max_records: int, _retries: int = 0) -> list[dict[str, Any]]:
    """Internal: issue one GDELT call with retry on 429."""
    params = urllib.parse.urlencode({
        "query":      query,
        "mode":       "ArtList",
        "maxrecords": str(max_records),
        "format":     "json",
        "timespan":   timespan,
        "sort":       "datedesc",
    })
    url = f"{GDELT_DOC}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429 and _retries < 2:
            wait = 6 * (2 ** _retries)
            sys.stderr.write(f"[gdelt] 429 — sleeping {wait}s then retrying\n")
            time.sleep(wait)
            return _fetch(query, timespan, max_records, _retries=_retries + 1)
        raise
    return payload.get("articles", [])


def sleep_between_calls(seconds: float = 6.0) -> None:
    """Public helper: GDELT asks for ≤1 req per 5s."""
    time.sleep(seconds)


class GDELTError(RuntimeError):
    """Raised when GDELT returns an error envelope or is unreachable."""


def is_healthcheck() -> dict[str, Any]:
    """Cheap probe; if GDELT returns >=1 article we treat it as healthy."""
    try:
        arts = fetch_last_15min(max_records=1)
        return {"ok": True, "sample_count": len(arts)}
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        return {"ok": False, "error": str(e)}
