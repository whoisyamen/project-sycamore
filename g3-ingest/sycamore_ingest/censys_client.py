"""Censys Platform v3 geographic host samples for the globe.

Uses a server-side Personal Access Token and optional organization ID. Requires
search access; the Free tier only supports known-asset lookups. API reference:
https://docs.censys.com/reference/v3-globaldata-search-query
"""
from __future__ import annotations

import json
import math
import os
import urllib.parse
import urllib.error
import urllib.request
from ipaddress import ip_address

API = 'https://api.platform.censys.io/v3/global/search/query'
UA = {'User-Agent': 'sycamore-ingest/1.0 (OSINT dashboard; contact: local operator)'}


class CensysUnavailable(RuntimeError):
    """Raised when credentials, access, transport, or response validation fail."""


def _api_key() -> str | None:
    return os.environ.get('CENSYS_PERSONAL_ACCESS_TOKEN', '').strip() or None


def build_query(region: dict) -> tuple[str, int]:
    """Build a country-code or geographic-radius search; bound the returned sample.

    Bboxes are represented by their enclosing circle, so results are a sample of
    the surrounding area, not a precise political-boundary measurement.
    """
    q: list[str] = []
    if region.get('kind') == 'country':
        code = str(region.get('country_code', '')).upper()
        if len(code) != 2 or not (code.isascii() and code.isalpha()):
            raise ValueError('Country queries require a two-letter country_code')
        q.append(f'host.location.country_code="{code}"')
    elif region.get('kind') == 'bbox':
        west, east = float(region['west']), float(region['east'])
        south, north = float(region['south']), float(region['north'])
        if not all(math.isfinite(v) for v in (west, east, south, north)) or not (-180 <= west <= 180 and -180 <= east <= 180 and -90 <= south <= north <= 90):
            raise ValueError('Invalid geographic bounds')
        lat_c = (south + north) / 2.0
        span = (east - west) % 360 if west > east else east - west
        lon_c = ((west + span / 2 + 180) % 360) - 180

        dlat_km = abs(north - south) * 111.0
        dlon_km = span * 111.0 * math.cos(math.radians(lat_c))
        radius_km = max(50, int((math.hypot(dlat_km, dlon_km) / 2)))
        q.append(f'geo_distance(host.location.coordinates,{lat_c:.3f},{lon_c:.3f},{radius_km}km)')
    else:
        raise ValueError(f'Unsupported region kind: {region.get("kind")!r}')
    page_size = int(region.get('limit', 12)) or 12
    return ' '.join(q), min(max(page_size, 3), 50)


def fetch_region(key: str | None, region: dict, timeout_s: float = 25.0) -> list[dict]:
    """One Platform v3 search page; never follows pagination or performs scans."""
    if not key:
        raise CensysUnavailable('CENSYS_PERSONAL_ACCESS_TOKEN not configured')
    query, page_size = build_query(region)
    url = API
    organization = os.environ.get('CENSYS_ORGANIZATION_ID', '').strip()
    if organization:
        url += '?' + urllib.parse.urlencode({'organization_id': organization})
    body = json.dumps({
        'query': query,
        'page_size': page_size,
        'fields': ['host.ip', 'host.location', 'host.services.port'],
    }).encode('utf-8')
    request = urllib.request.Request(url, data=body, method='POST', headers={
        **UA, 'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json', 'Accept': 'application/json',
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        error.close()
        reasons = {
            401: 'Censys rejected the Personal Access Token (HTTP 401)',
            402: 'Censys credits exhausted; check account credits (HTTP 402)',
            403: 'Censys denied search; check plan, API Access role, organization ID and credits (HTTP 403)',
            429: 'Censys rate limit reached (HTTP 429)',
        }
        raise CensysUnavailable(reasons.get(error.code, f'Censys HTTP error {error.code}')) from None
    except Exception as error:
        # Never log request headers, raw response bodies, or exception messages.
        raise CensysUnavailable(f'Censys request failed ({type(error).__name__})') from None
    result = payload.get('result') if isinstance(payload, dict) else None
    if not isinstance(result, dict) or 'hits' not in result:
        raise CensysUnavailable('Censys response missing result.hits[]')
    hits = result['hits']
    if hits is None and result.get('total_hits') == 0:
        hits = []  # The API schema permits null hits on an empty result.
    if not isinstance(hits, list):
        raise CensysUnavailable('Censys response has invalid result.hits')
    out: list[dict] = []
    for hit in hits[:page_size]:
        asset = hit.get('host_v1') if isinstance(hit, dict) else None
        if not isinstance(asset, dict) or not isinstance(asset.get('resource'), dict):
            raise CensysUnavailable('Censys search returned an unexpected host schema')
        host = normalize_host(asset['resource'])
        if host is not None:
            out.append(host)
    return out


def normalize_host(resource: dict) -> dict | None:
    """Keep only provider coordinates and observed ports; never invent a position."""
    location = resource.get('location')
    if not isinstance(location, dict):
        return None
    coordinates = location.get('coordinates')
    if not isinstance(coordinates, dict):
        return None
    lat, lon = coordinates.get('latitude'), coordinates.get('longitude')
    if not all(type(v) in (int, float) and math.isfinite(v) for v in (lat, lon)):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    raw_ip = resource.get('ip')
    if not isinstance(raw_ip, str):
        return None
    try:
        ip = str(ip_address(raw_ip))
    except ValueError:
        return None
    services = resource.get('services') or []
    if not isinstance(services, list):
        raise CensysUnavailable('Censys response has invalid host services')
    ports = sorted({service['port'] for service in services
                    if isinstance(service, dict) and type(service.get('port')) is int
                    and 0 <= service['port'] <= 65535})
    code = location.get('country_code') or ''
    return {'ip': ip, 'lon': lon, 'lat': lat,
            'country_code': code[:2].upper() if isinstance(code, str) else '',
            'ports': ports}


def _region_label(region: dict) -> str | None:
    """Short human label so the UI can attribute a host to its queried region."""
    kind = region.get('kind')
    if kind == 'country':
        return (str(region.get('name', '')).strip()[:40] or None)
    if kind == 'bbox':
        try:
            return f'box {float(region["south"]):.2f}/{float(region["west"]):.2f}'
        except (KeyError, TypeError, ValueError):
            return 'region'
    return str(kind)[:16] or None


def build_envelope(regions: list[dict], fetch_fn) -> dict:
    """Pure envelope builder; fetch_fn(region)->list[host] so tests can inject fixtures.

    A source failure propagates so the runner preserves the previous envelope.
    Publishing a partial or empty success would hide an outage."""
    from datetime import datetime, timezone

    hosts: list[dict] = []
    for region in regions[:8]:  # hard cap on sequential search pages per cycle
        found = fetch_fn(region) or []
        label = _region_label(region)
        for host in found[:30]:  # defensive per-region cap even if a fixture overflows
            tagged = dict(host)
            tagged['label'] = label
            hosts.append(tagged)
    return {
        'version': 1,
        'ts': int(datetime.now(timezone.utc).timestamp() * 1000),
        'source': {'name': 'Censys Platform / host search', 'endpoint': API},
        'count': len(hosts),
        'hosts': hosts[:300],
    }
