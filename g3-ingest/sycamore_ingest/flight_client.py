"""OpenSky Network air-traffic snapshot (public REST, no key required).

Produces the OSINT flights envelope consumed by the globe's FLIGHTS layer:
  {version, ts, source, count, aircraft[], trails{}}

The public API is CORS-restricted to its own origin, so browser code can never
call it directly — this module (server-side, laptop ingest) owns that fetch.
Trails are merged across cycles from the previous published envelope so the UI
can draw short motion streaks without keeping any state of its own.

Honesty rules: coordinates and telemetry come verbatim from OpenSky; we never
interpolate a position between observations (a trail segment is only ever drawn
between two real fixes). Aircraft with null positions or stale last_contact are
dropped, not guessed at.
"""
from __future__ import annotations

import json
import math
import urllib.request
from datetime import timezone
from typing import Any

API = 'https://opensky-network.org/api/states/all'
UA = {'User-Agent': 'sycamore-ingest/1.0 (OSINT dashboard; contact: local operator)'}
MAX_AGE_S = 60          # drop fixes older than this (OpenSky keeps recent history)
TRAIL_POINTS = 8        # per-aircraft rolling fix count published for the UI
TRAIL_MAX_AGE_MS = 15 * 60_000   # a plane unseen >15 min is no longer tracked
MIN_ALT_M = -20         # keep surface/aircraft alike; OpenSky rarely emits below


def _now_ms() -> int:
    from datetime import datetime

    return int(datetime.now(timezone.utc).timestamp() * 1000)


def fetch_states(timeout_s: float = 30.0) -> dict[str, Any]:
    """GET states/all (whole globe) and validate the envelope shape."""
    with urllib.request.urlopen(urllib.request.Request(API, headers=UA), timeout=timeout_s) as resp:
        payload = json.loads(resp.read().decode('utf-8'))
    if not isinstance(payload.get('states'), list):
        raise ValueError(f'OpenSky response missing states[] (got keys {list(payload)})')
    return payload


def _fix(row: list, now_s: int) -> dict | None:
    """One OpenSky state row -> normalized fix, or None when unusable."""
    if len(row) < 12:
        return None
    (icao24, callsign, origin_country, _tpos, last_contact, lon, lat, baro_alt,
     on_ground, velocity_ms, true_track_deg) = row[:11]
    try:
        lon_f, lat_f = float(lon), float(lat)
        alt_m = float(baro_alt if baro_alt is not None else -90.0)
        vel_ms = float(velocity_ms or 0.0)
        track_deg = float(true_track_deg or 0.0)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (lon_f, lat_f, alt_m, vel_ms, track_deg)):
        return None
    if lon_f == 0 and lat_f == 0:          # OpenSky's "no position" sentinel
        return None
    if not (-180 <= lon_f <= 180 and -90 <= lat_f <= 90) or alt_m < MIN_ALT_M:
        return None
    try:
        last_s = int(last_contact)
    except (TypeError, ValueError, OverflowError):
        return None
    if last_s <= 0:
        return None
    age_ms = (now_s * 1000) - (last_s * 1000 if last_s else _now_ms())
    if not (-5_000 <= age_ms <= MAX_AGE_S * 1000):   # tiny clock skew tolerated both ways
        return None
    ident = str(icao24).strip().lower() or f'anon-{abs(hash((lon_f, lat_f))) % 10**8}'
    return {
        'id': ident[:9],
        'cs': (str(callsign).strip() if callsign else '')[:16] or None,
        'oc': str(origin_country)[:24] if origin_country else None,
        'lon': round(lon_f, 4),
        'lat': round(lat_f, 4),
        'alt_m': int(round(alt_m)),
        'v_ms': round(vel_ms, 1) or None,
        'hdg': round(track_deg % 360, 1) if track_deg else None,
    }


def build_envelope(payload: dict[str, Any], previous: dict | None = None) -> dict:
    """Normalize a states/all payload into the published envelope.

    Pure function of (payload, previous envelope): deterministic merge so tests
    can exercise trail logic without network access."""
    now_s = int(payload.get('time') or _now_ms() / 1000)
    aircraft: dict[str, dict] = {}
    for row in payload['states']:
        fix = _fix(row, now_s)
        if fix is None:
            continue
        existing = aircraft.get(fix['id'])
        if existing is not None and (existing['alt_m'] or 0) >= (fix['alt_m'] or 0):
            continue  # duplicate row for one tail number — keep the higher fix
        aircraft[fix['id']] = fix

    prev_trails: dict[str, list] = {}
    if isinstance(previous, dict):
        raw_trails = previous.get('trails')
        if isinstance(raw_trails, dict):
            prev_trails = {k: v for k, v in raw_trails.items() if isinstance(v, list)}

    trails: dict[str, list] = {}
    cutoff_ms = now_s * 1000 - TRAIL_MAX_AGE_MS
    for ident, fix in aircraft.items():
        hist = [p for p in prev_trails.get(ident, [])
                if isinstance(p, (list, tuple)) and len(p) == 3 and p[2] >= cutoff_ms][-TRAIL_POINTS:]
        last_fix = hist[-1] if hist else None
        moved = last_fix is None or abs(last_fix[0] - fix['lon']) > 4e-5 or abs(last_fix[1] - fix['lat']) > 4e-5
        stale_enough = last_fix is not None and (now_s * 1000) - int(last_fix[2]) >= TRAIL_MAX_AGE_MS // 8
        if moved or stale_enough:
            hist.append([fix['lon'], fix['lat'], now_s * 1000])
        trails[ident] = hist[-TRAIL_POINTS:]

    rows = sorted(aircraft.values(), key=lambda a: (a.get('alt_m') or 0), reverse=True)
    return {
        'version': 1,
        'ts': now_s * 1000,
        'source': {'name': 'OpenSky Network', 'endpoint': API},
        'count': len(rows),
        'aircraft': rows,
        'trails': trails,
    }


def load_previous(path) -> dict | None:
    """Read the last published envelope for trail continuity; tolerate absence."""
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) and 'aircraft' in data else None
    except (OSError, ValueError):
        return None
