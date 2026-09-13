"""D-020 event imagery — ingest-time download to same-origin static paths.

Why at ingest time, not in the browser:
  * The public site is a pure static bundle with strict CSP (no external image hosts).
  * Security policy forbids adding third-party origins or an app-server proxy layer.
So the sandboxed runner downloads candidate images ONCE and serves them from
public/data/media/<sha1-16>.jpg — same-origin, content-hashed, size-capped.

Candidate sources (priority order):
  1. Feed-native: Media RSS / enclosure <image> reference shipped by the feed itself.
     Fresh articles carry this every cycle; it costs nothing but a single download.
  2. og:image / twitter:image on the article page — budgeted passive GET, and only
     for events not already recorded as attempted in the ledger (public/data/media/
     .og-attempts.json). Failed lookups are remembered so dead URLs never burn two
     cycles' worth of timeout headroom; successful ones leave no trace.

Hard rules:
  * HTTPS-only downloads, JPEG/PNG magic bytes required before storing.
  * Per-image size cap (MAX_IMAGE_BYTES) and per-cycle attempt budgets sized to fit
    inside TimeoutStartSec=285 with feed fetches included (~130s worst case):
      og page GETs: <=16 @2s = 32s; image downloads: <=8 @6s = 48s. Media total ~93s.
  * video_url is an external YouTube watch link from yt:videoId — NEVER embedded;
    it must match the schema pattern exactly or it is dropped (local check only).
  * No image found = no `media.image`. The UI must not fabricate one (schema contract).

The ledger lives under public/data/media/ because that directory is inside the
service's ReadWritePaths while WorkingDirectory itself is read-only.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlparse

MEDIA_DIR_NAME = 'media'            # under public/data/ (service ReadWritePaths)
MAX_IMAGE_BYTES = 450_000           # ~450 KB cap per stored image
OG_TIMEOUT_S = 2.0                  # article-page fetch for og:image (head only, 64KB read)
DL_TIMEOUT_S = 6.0                  # image download timeout
MAX_OG_FETCHES_PER_CYCLE = 16       # passive page GETs total this cycle (~32s worst case)
MAX_DOWNLOADS_PER_CYCLE = 8         # image downloads per cycle (feed-native + og, ~48s worst case)
LEDGER_NAME = '.og-attempts.json'   # private ledger inside media/ (dotfile, not served by name pattern)
LEDGER_MAX_ENTRIES = 200

UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) SycamoreIngest/0.3'}

_YT_WATCH_RE = re.compile(r'^https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{6,25}$')
_OG_IMAGE_TAG = '<meta property="og:image" content='


def _http_get(url: str, timeout: float) -> bytes | None:
    """GET a URL; returns body up to cap+1 or None on any failure."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = (resp.headers.get('Content-Type') or '').lower()
            if 'html' in ctype and not url.lower().split('?')[0].endswith(('.jpg', '.jpeg', '.png')):
                return None  # got a page where an image was expected
            data = resp.read(MAX_IMAGE_BYTES + 1)
    except Exception:
        return None
    if len(data) > MAX_IMAGE_BYTES or not data:
        return None
    return data


def _is_image_bytes(data: bytes | None) -> bool:
    """JPEG or PNG magic. Both are stored as .jpg (browsers sniff <img> content); the
    schema pattern only allows jpe?g, so this is a deliberate, documented tradeoff."""
    if not data:
        return False
    return data[:3] == b'\xff\xd8\xff' or data[:4] == b'\x89PNG'


def _url_is_https(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme == 'https' and bool(parsed.netloc)
    except Exception:
        return False


def extract_og_image(page_url: str, timeout_s: float = OG_TIMEOUT_S) -> tuple[str | None, bool]:
    """Passive GET of the article page head.

    Returns (image_url_or_None, fetch_failed). `fetch_failed` distinguishes a real
    network/parse failure (record in ledger — do not retry next cycle) from "page
    fetched but no og:image" (also recorded; same treatment: one attempt per event)."""
    try:
        req = urllib.request.Request(page_url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            head = resp.read(64_000).decode('utf-8', errors='ignore')
    except Exception:
        return None, True
    m = re.search(_OG_IMAGE_TAG + r'["\']([^"\']+)', head) or \
        re.search(r'<meta name="twitter:image" content=["\']([^"\']+)', head)
    if not m:
        return None, False  # page reachable but carries no og:image
    url = m.group(1).strip()
    if url.startswith('//'):
        url = 'https:' + url
    elif not url.lower().startswith(('http://', 'https://')):
        try:
            url = urljoin(page_url, url)
        except Exception:
            return None, False
    return (url or None), False


def _load_ledger(media_dir: Path) -> dict[str, str]:
    path = media_dir / LEDGER_NAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        # JSON keys are strings; keep them as such — attach_media compares on str(id).
        return {str(k): v for k, v in data.items() if isinstance(v, str)}
    except Exception:
        return {}


def _save_ledger(media_dir: Path, ledger: dict[str, str]) -> None:
    try:
        media_dir.mkdir(parents=True, exist_ok=True)
        items = list(ledger.items())[-LEDGER_MAX_ENTRIES:]  # drop oldest beyond cap
        payload = {str(k): v for k, v in items}
        fd, tmp = tempfile.mkstemp(dir=media_dir, prefix='.' + LEDGER_NAME)
        try:
            with open(fd, 'w', encoding='utf-8') as f:
                json.dump(payload, f)
            Path(tmp).replace(media_dir / LEDGER_NAME)
        finally:
            if Path(tmp).exists():
                Path(tmp).unlink()
    except Exception:
        pass  # ledger is an optimization; never fail the cycle over it


def _store(media_root: Path, data: bytes) -> str | None:
    """Write image atomically under media/<hash>.jpg; returns site-relative path."""
    digest = hashlib.sha1(data).hexdigest()[:16]
    dest_dir = media_root / MEDIA_DIR_NAME
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        name = f'{digest}.jpg'
        if (dest_dir / name).exists():
            return f'data/{MEDIA_DIR_NAME}/{name}'  # already stored; reuse hash path
        fd, tmp = tempfile.mkstemp(dir=dest_dir, prefix=f'.{name}.')
        try:
            with open(fd, 'wb') as f:
                f.write(data)
            Path(tmp).replace(dest_dir / name)
        finally:
            if Path(tmp).exists():
                Path(tmp).unlink()
    except Exception:
        return None
    return f'data/{MEDIA_DIR_NAME}/{name}'


def attach_media(pairs: list[tuple[dict, dict]], media_root: Path) -> int:
    """Attach `media` blocks to (event, hint) pairs that lack one. Returns count of newly attached.

    - Only touches events WITHOUT an existing image; video_url is only set when the
      event has none yet — a fresh article merged into a legacy row never clobbers
      imagery provenance recorded in earlier cycles.
    - Feed-native candidates always get a download attempt while budget remains; they
      come from the current cycle's fetch and are worth exactly one try per article.
    - og:image attempts consult/write the ledger so each event is looked up at most
      once, ever (one passive GET). Failed lookups never burn two cycles' headroom.
    Budgets sized for a 285s service cap: feeds worst ~130s + media worst
    (16 og @2s = 32s; 8 downloads @6s = 48s ≈ 93s) leaves margin inside the unit."""
    attached = 0
    og_left, dl_left = MAX_OG_FETCHES_PER_CYCLE, MAX_DOWNLOADS_PER_CYCLE
    ledger_dir = media_root / MEDIA_DIR_NAME
    ledger: dict[str, str] = _load_ledger(ledger_dir)

    for event, hint in pairs:
        eid = event['id']
        before = dict(event.get('media') or {})
        vurl = (hint.get('video_url') or '').strip() if isinstance(hint, dict) else ''

        # Video link is free to attach whenever the feed supplied a valid one.
        if _YT_WATCH_RE.match(vurl):
            event.setdefault('media', {}).setdefault('video_url', vurl)

        # Image: never overwrite an existing provenance path.
        image_url = ''
        has_image = bool((event.get('media') or {}).get('image'))
        native_hint = (hint.get('image') or '').strip() if isinstance(hint, dict) else ''
        if not has_image and dl_left > 0:
            if _url_is_https(native_hint):
                image_url = native_hint
            elif og_left > 0 and str(eid) not in ledger:
                page = event['sources'][0] if event.get('sources') else ''
                if re.match(r'^https?://', page):
                    found, fetch_failed = extract_og_image(page)
                    og_left -= 1
                    # Record the attempt either way; one lookup per event.
                    ledger[str(eid)] = 'ok' if (found and _url_is_https(found)) else 'failed'
                    image_url = found or ''

        if image_url and dl_left > 0:
            data = _http_get(image_url, DL_TIMEOUT_S)
            dl_left -= 1
            if _is_image_bytes(data):
                rel = _store(media_root, data)
                if rel:
                    event.setdefault('media', {})['image'] = rel

        after = dict(event.get('media') or {})
        if set(after) - set(before) or any(after[k] != before.get(k) for k in before):
            attached += 1

    _save_ledger(ledger_dir, ledger)
    return attached
