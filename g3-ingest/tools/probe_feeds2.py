#!/usr/bin/env python3
"""Round 2: maritime/military gap + non-XML sniff."""
import time, urllib.request, xml.etree.ElementTree as ET

UA = {"User-Agent": "Sycamore/0.3 (RSS reader; local use)"}

CANDIDATES = [
    ("Naval News",        "https://navynews.co.uk/feed/",                    "maritime"),
    ("USNI News",         "https://usni.org/rss.xml",                        "military"),
    ("The War Zone TWZ",  "https://www.twz.com/feed",                        "military"),
    ("Naval Post",        "http://feeds.feedburner.com/navy.mil/News-Release","maritime"),
    ("Lloyd List Maritime","https://lloydslistupdate-1.rssing.com/channel/48951.xml","maritime"),
]

def probe(name, url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            body = r.read(300_000)
        head = body[:400].decode("utf-8", "replace")
        if not (head.lstrip().startswith("<?xml") or head.lstrip().startswith("<")):
            return f"DROPPED {name}: non-XML ({head[:60]!r})"
        root = ET.fromstring(body)
        n_item = len(root.findall(".//item")) + len(root.findall("{http://www.w3.org/2005/Atom}entry"))
        t = (root.findtext(".//item/title") or "")[:60]
        return f"{name}: items={n_item} sample={t!r}"
    except Exception as e:
        return f"DROPPED {name}: {type(e).__name__}: {str(e)[:80]}"

if __name__ == "__main__":
    for name, url, topic in CANDIDATES:
        print(probe(name, url), flush=True)
        time.sleep(0.4)
