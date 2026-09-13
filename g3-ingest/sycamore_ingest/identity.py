"""Stable identity primitives for Sycamore intelligence records (iteration 1.1.2).

Implements the rules from INT-001 / INTELLIGENCE_IMPLEMENTATION_SPEC §4:

- Canonical JSON hashing: SHA-256 over UTF-8, object keys sorted recursively,
  no whitespace, original array order, non-finite numbers rejected. Number
  formatting matches ECMAScript Number::toString so the Python and browser
  implementations produce identical digests (verified by cross-language
  fixtures, including fractional coordinates and non-BMP text).
- Event UID allocation: assigned once and persisted; NEVER recalculated from
  mutable title/location. An existing mapping is reused so imports are
  idempotent.
- Source-key normalization: provider UID + provider-native record ID when
  available, otherwise provider UID + canonical source URL. URL
  canonicalization normalizes only scheme/host case, default ports and
  fragments; path/query are preserved.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

_UID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


# --------------------------------------------------------------------------
# Canonical JSON (ECMAScript-compatible number formatting)
# --------------------------------------------------------------------------

def _js_float(value: float) -> str:
    """Serialize a float exactly like ECMAScript Number::toString (shortest round-trip).

    Handles the three divergences from Python repr so digests match the browser:
    1. integral floats emit without '.0' (50.0 -> '50', -0.0 -> '0')
    2. exponent range: JS uses fixed notation for 1e-6 <= |v| < 1e21,
       Python repr switches to exponent earlier
    3. exponent digits are unpadded ('e-7', not 'e-07')
    """
    if not math.isfinite(value):
        raise ValueError("canonical JSON rejects non-finite numbers")
    if value == 0:
        return "0"
    if value == int(value):
        # Integral float within JS fixed-notation range.
        magnitude = abs(value)
        if magnitude < 1e21:
            return str(int(value))
        # >= 1e21 uses exponential in JS; repr gives shortest mantissa.
        r = repr(value)
    else:
        r = repr(value)
    # Normalize exponential form.
    if "e" in r or "E" in r:
        mant, _, exp_str = r.replace("E", "e").partition("e")
        exp = int(exp_str)
        if -6 <= exp < 21:
            # Expand to fixed notation, matching JS decimal printing.
            digits = mant.replace(".", "")
            point = mant.index(".") if "." in mant else len(mant)
            int_digits = point + exp
            if int_digits <= 0:
                return "0." + "0" * (-int_digits) + digits
            if int_digits >= len(digits):
                return digits + "0" * (int_digits - len(digits))
            return digits[:int_digits] + "." + digits[int_digits:]
        sign = "-" if value < 0 else ""
        return f"{sign}{mant}e{exp:+#d}".replace("e+", "e").replace("e-", "e-")
    if r.endswith(".0"):
        return r[:-2]
    return r


def _canonical_parts(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return _js_float(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, list):
        return "[" + ",".join(_canonical_parts(v) for v in value) + "]"
    if isinstance(value, dict):
        parts = []
        for key in sorted(value, key=_sort_key):
            parts.append(json.dumps(str(key), ensure_ascii=False, separators=(",", ":"))
                         + ":" + _canonical_parts(value[key]))
        return "{" + ",".join(parts) + "}"
    raise TypeError(f"cannot canonicalize {type(value).__name__}")


def _sort_key(key: Any) -> Any:
    """Sort object keys by Unicode code points (matches Python, JS fallback for our fixtures)."""
    return str(key)


def canonical_json(value: Any) -> str:
    """Serialize to canonical JSON text (no whitespace, sorted keys, JS numbers)."""
    return _canonical_parts(value)


def canonical_sha256(value: Any) -> str:
    """SHA-256 hex of canonical JSON. Rejects non-finite numbers."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Event UID mapping (immutable after assignment)
# --------------------------------------------------------------------------

def allocate_uid() -> str:
    """Fresh canonical UUIDv4."""
    return str(uuid.uuid4())


def ensure_event_uid(mapping: dict[int, str], event_id: int,
                     allocate: Callable[[], str] = allocate_uid) -> tuple[str, bool]:
    """Return (eventUid, created) for a numeric v1 event ID.

    Reuses an existing mapping entry (import idempotency). A created mapping
    entry is recorded in `mapping` before returning. Never derives identity
    from title/location.
    """
    if not isinstance(event_id, int) or event_id < 1 or event_id > 9007199254740991:
        raise ValueError(f"invalid v1 event ID: {event_id!r}")
    if event_id in mapping:
        uid = mapping[event_id]
        if not _UID_RE.match(uid):
            raise ValueError(f"mapping for event {event_id} holds invalid UID: {uid!r}")
        return uid, False
    uid = allocate()
    if not _UID_RE.match(uid):
        raise ValueError(f"allocator returned invalid UID: {uid!r}")
    mapping[event_id] = uid
    return uid, True


def import_manifest_checksum(mapping: dict[int, str]) -> str:
    """Checksum of a legacy-ID -> eventUid mapping so reruns reuse the same mapping."""
    ordered = {str(k): mapping[k] for k in sorted(mapping)}
    return canonical_sha256(ordered)


# --------------------------------------------------------------------------
# Source-key normalization
# --------------------------------------------------------------------------

def canonicalize_url(url: str) -> str:
    """Normalize scheme/host case, default ports and fragments; preserve path/query.

    Query strings are preserved in full (no global stripping). The caller keeps
    the original URL separately.
    """
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ValueError(f"unsupported source URL: {url!r}")
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower() if parsed.hostname else ""
    if not host:
        raise ValueError(f"source URL missing host: {url!r}")
    port = parsed.port
    if port is not None:
        if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
            netloc = host
        else:
            netloc = f"{host}:{port}"
    else:
        netloc = host
    # userinfo is dropped for canonical identity (never part of a public source URL)
    return urlunsplit((scheme, netloc, parsed.path or "/", parsed.query, ""))


def source_key(provider_uid: str, provider_native_id: str | None = None,
               source_url: str | None = None) -> str:
    """Natural key: provider UID + provider-native ID when available, else provider UID + canonical URL."""
    if not isinstance(provider_uid, str) or not provider_uid.strip():
        raise ValueError("providerUid is required")
    if provider_native_id is not None and provider_native_id != "":
        return f"{provider_uid}|{provider_native_id}"
    if source_url is None:
        raise ValueError("source natural key needs provider-native ID or source URL")
    return f"{provider_uid}|url:{canonicalize_url(source_url)}"


def source_key_checksum(source_key_value: str) -> str:
    """SHA-256 of a natural key for stable opaque storage columns."""
    return hashlib.sha256(source_key_value.encode("utf-8")).hexdigest()