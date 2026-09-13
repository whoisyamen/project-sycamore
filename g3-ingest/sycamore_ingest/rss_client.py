"""
Curated RSS feed client. No rate limits, no API keys, higher signal-to-noise
than GDELT for English-language news. Each feed is independently maintained
and self-describing; we just parse with stdlib XML.

2026-09 expansion (probe-verified): 14 feeds across cyber / geopolitical /
maritime / military desks so the live map has continuous multi-source supply,
not a single-topic wall. RSS 1.0 RDF (DW) is handled via namespace-agnostic
local-name matching; Media RSS <enclosure>/<media:content>/yt:videoId are
extracted for event imagery and video links.

Each fetch has a 15s timeout; failure of one feed doesn't fail the cycle.
"""
from __future__ import annotations
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from typing import Any
from dataclasses import dataclass

USER_AGENT = "Sycamore/0.3 (RSS reader; local use)"

FEEDS: list[dict[str, str]] = [
    # ── Cyber (originals) ────────────────────────────────────────────────
    {"name": "KrebsOnSecurity",     "url": "https://krebsonsecurity.com/feed/",            "topic": "cyber"},
    {"name": "BleepingComputer",    "url": "https://www.bleepingcomputer.com/feed/",      "topic": "cyber"},
    {"name": "The Hacker News",     "url": "https://thehackernews.com/rss.xml",           "topic": "cyber"},
    # CISA advisories carry no incident location and are US-government notices,
    # not events; they would dilute the map. Dropped from event ingestion 2026-09.
    {"name": "SecurityWeek",        "url": "https://www.securityweek.com/feed/",          "topic": "cyber"},
    {"name": "Dark Reading",        "url": "https://www.darkreading.com/rss.xml",         "topic": "cyber"},
    # ── Geopolitical world desks (2026-09 expansion, all probe-verified) ─
    {"name": "BBC World",           "url": "https://feeds.bbci.co.uk/news/world/rss.xml","topic": "geopolitical"},
    {"name": "Al Jazeera English",  "url": "https://www.aljazeera.com/xml/rss/all.xml",   "topic": "geopolitical"},
    {"name": "Guardian World",      "url": "https://www.theguardian.com/world/rss",       "topic": "geopolitical"},
    {"name": "France24 EN",         "url": "https://www.france24.com/en/rss",             "topic": "geopolitical"},
    # RSS 1.0 RDF — items live in the purl.org/rss/1.0 namespace, dates use dc:date.
    {"name": "DW News World",       "url": "https://rss.dw.com/rdf/rss-en-world",         "topic": "geopolitical"},
    {"name": "NPR World",           "url": "https://feeds.npr.org/1004/rss.xml",          "topic": "geopolitical"},
    # ── Maritime / military (2026-09 expansion) ──────────────────────────
    {"name": "gCaptain",            "url": "https://gcaptain.com/feed/",                  "topic": "maritime"},
    {"name": "The War Zone TWZ",    "url": "https://www.twz.com/feed",                    "topic": "military"},
]


# Per-image static-serving budget shared with media_pipeline (thumbnail scoring).
# Conservative — the site has strict CSP and serves from a static edge; very large
# thumbnails hurt page weight more than they help map cards.
MEDIA_MAX_BYTES = 450_000


@dataclass
class FeedItem:
    title:        str
    link:         str
    source:       str   # e.g. "KrebsOnSecurity"
    topic:        str
    published_ms: int | None
    description:  str = ""   # source's own lede; honest, no LLM
    media_image:  str = ""   # feed-supplied image URL (enclosure / Media RSS)
    video_url:    str = ""   # direct watch link when the item is a video piece


def _clean_html(s: str) -> str:
    """Strip HTML tags and decode common entities. RSS descriptions are HTML."""
    import re
    import html as _html
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", s, flags=re.S | re.I)
    s = re.sub(r"</?(p|br|div|li|tr|h\d|ul|ol|table)[^>]*>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:1000]  # hard cap; the panel truncates anyway


def _parse_pub_ms(date_str: str | None) -> int | None:
    """Best-effort RSS date parser. RFC 822 most common; ISO-8601 fallback."""
    if not date_str:
        return None
    from email.utils import parsedate_to_datetime
    from datetime import datetime, timezone
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except (TypeError, ValueError):
        pass
    try:
        dt = datetime.fromisoformat(date_str.strip().replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except (TypeError, ValueError):
        return None


def _localname(tag: str) -> str:
    """Strip an XML namespace from a tag name."""
    if isinstance(tag, str):
        return tag.rsplit("}", 1)[-1]
    return ""


def _find_local(elem, *names):
    """Find first child whose local (namespace-agnostic) name matches.

    RSS feeds are inconsistent about namespaces; matching on the local name
    handles plain <title> and namespaced variants in one pass.
    """
    for c in elem:
        if _localname(c.tag) in names:
            return c
    return None


def _text_of(elem, *names):
    el = _find_local(elem, *names)
    if el is not None and (el.text or "").strip():
        return (el.text or "").strip()
    return ""


# Per-image static-serving budget shared with media_pipeline (thumbnail scoring).


def _item_media(it) -> tuple[str, str, str]:
    """Extract (image_url, video_url) from RSS 2 / Media RSS / yt:videoId."""
    enc_url = ""
    for c in it:
        if _localname(c.tag) == "enclosure":
            url = (c.get("url") or "").strip()
            typ = (c.get("type") or "").lower()
            # Only take image enclosures; skip audio/video/audio-only pieces.
            if url and ("image" in typ):
                enc_url = url

    media_image = ""
    best_score = -1
    for c in it.iter():
        ln = _localname(c.tag)
        if ln not in ("content", "thumbnail"):
            continue
        # Media RSS <media:content> / <media:thumbnail>, possibly with size hints.
        mtype = (c.get("type") or "").lower()
        url = (c.get("url") or c.text or "").strip()
        if not url:
            continue
        # media:content must be an image; a bare <thumbnail> may omit type.
        if ln == "content" and "image" not in mtype:
            continue
        try:
            width = int(c.get("width") or 0)
        except ValueError:
            width = 0
        score = -1
        size_attr = c.get("size")
        if size_attr:
            # Prefer images under the static-serving budget; smaller wins.
            try:
                cand_size = int(size_attr)
                if cand_size <= MEDIA_MAX_BYTES * 2:
                    score = MEDIA_MAX_BYTES * 4 - cand_size
            except ValueError:
                pass
        elif width and 300 <= width <= 1600:
            score = width
        if ln == "thumbnail" and score < 0:
            # Thumbnails are a weaker signal than full content entries.
            score = min(width, 800) - 200 if width else 50
        if score > best_score:
            best_score, media_image = score, url

    yt_id = ""
    for c in it.iter():
        if _localname(c.tag) == "videoId" and not yt_id:
            yt_id = (c.text or "").strip()

    video_url = f"https://www.youtube.com/watch?v={yt_id}" if yt_id else ""
    return media_image, enc_url, video_url


def _parse_feed(feed: dict[str, str], body: bytes) -> list[FeedItem]:
    """Tolerant RSS 2 / Atom / RDF parser. Returns whatever items we can extract.

    Rejects non-feed XML (HTML pages, empty bodies) by raising ET.ParseError so
    fetch_all records it as a failed source and the cycle continues cleanly.
    """
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        raise
    if not list(root):
        # No children at all — empty channel/feed is a real-but-empty result,
        # but an entirely empty document is the caller's way of saying "this
        # isn't a feed". Raise so fetch_all marks the source as failed.
        raise ET.ParseError("empty document")

    # Locate item elements across the three common formats (RSS 2, Atom, RDF).
    candidates = [c for c in root.iter() if _localname(c.tag) == "item"]
    items_elm: list[Any] = candidates or [c for c in root.iter() if _localname(c.tag) == "entry"]

    # If we found no items AND the document's root local name isn't a known feed
    # shape (rss / RDF / feed), the body is probably HTML or another non-feed
    # payload. Raise so fetch_all records this source as failed (succeeded=0,
    # failed=[name]) rather than silently dropping it into the cycle.
    if not items_elm and _localname(root.tag) not in ("rss", "RDF", "feed"):
        raise ET.ParseError(f"not a feed (root={_localname(root.tag)!r})")

    out: list[FeedItem] = []
    for it in items_elm:
        title = _text_of(it, "title") or "(untitled)"

        # RSS 2 / RDF: <link> with text. Atom: <link href="..."/> (canonical first).
        link = ""
        for c in it:
            if _localname(c.tag) == "link":
                t = (c.text or "").strip()
                if t:
                    link = t
                    break
                href = (c.get("href") or "").strip()
                rel = c.get("rel", "")
                if href and not rel:  # Atom canonical entry
                    link = href
        if not link:
            continue  # no resolvable article URL — skip, don't guess

        pub_raw = _text_of(it, "pubDate", "date", "updated", "published")

        desc_elm = None
        for c in it:
            if _localname(c.tag) in ("description", "summary"):
                desc_elm = c
                break
        description = ""
        if desc_elm is not None and (desc_elm.text or "").strip():
            raw_type = (desc_elm.get("type") or "").lower()
            text_src = "".join(desc_elm.itertext())
            try:
                import base64 as _b64
                if "base64" in raw_type and "<" not in text_src[:200]:
                    text_src = _b64.b64decode(text_src).decode("utf-8", errors="replace")
            except Exception:
                pass
            description = _clean_html(text_src)

        media_image, enc_url, video_url = _item_media(it)

        out.append(FeedItem(
            title=title, link=link, source=feed["name"], topic=feed.get("topic", ""),
            published_ms=_parse_pub_ms(pub_raw), description=description,
            media_image=(media_image or enc_url), video_url=video_url,
        ))

    return out


def _fetch_one(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        # Read at most 2 MB; feeds are small and this bounds a hostile/huge feed.
        return resp.read(2 * 1024 * 1024)


class FeedBatch(list[FeedItem]):
    """List-compatible result carrying per-source health, including empty feeds."""
    def __init__(self):
        super().__init__()
        self.succeeded = 0
        self.failed: list[str] = []

    @property
    def feed_names(self) -> dict[str, str]:
        return {f["name"]: f.get("topic", "") for f in FEEDS}


def fetch_all() -> FeedBatch:
    """Fetch configured feeds and report partial/total failures explicitly."""
    out = FeedBatch()
    for feed in FEEDS:
        try:
            body = _fetch_one(feed["url"])
            items = _parse_feed(feed, body)
            out.extend(items)
            out.succeeded += 1
            sys.stderr.write(f"[rss] {feed['name']}: {len(items)} items\n")
        except (urllib.error.URLError, ET.ParseError, TimeoutError, ValueError, OSError) as e:
            out.failed.append(feed["name"])
            sys.stderr.write(f"[rss] {feed['name']} FAILED: {e}\n")
        # Be polite: 500ms between feeds
        time.sleep(0.5)
    return out


def to_articles(items: list[FeedItem]) -> list[dict[str, Any]]:
    """Convert feed items to the loose article shape the normalizer expects."""
    from urllib.parse import urlparse
    out: list[dict[str, Any]] = []
    for it in items:
        try:
            domain = urlparse(it.link).netloc.replace("www.", "")
        except Exception:
            domain = it.source
        out.append({
            "title":    it.title,
            "url":      it.link,
            "domain":   domain,
            "language": "English",
            "tone":     0.0,           # unknown without LLM
            "seendate": _ms_to_gdelt_date(it.published_ms) if it.published_ms else "",
            "location": {"fullName": "", "countryCode": ""},  # RSS rarely has geo
            "lat":      0,
            "long":     0,
            "_rss_topic": it.topic,    # private; read by normalizer
            "_rss_source": it.source,
            "_rss_description": it.description,  # private; the source's lede
            "_media_image": it.media_image,      # private; media pipeline
            "_video_url":   it.video_url,        # private; media pipeline
        })
    return out


def _ms_to_gdelt_date(ms: int) -> str:
    """Format ms since epoch as GDELT-style YYYYMMDDTHHMMSSZ."""
    from datetime import datetime, timezone
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%SZ")
