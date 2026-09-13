#!/usr/bin/env python3
"""Probe verified feeds for media affordances: <enclosure>, Media RSS, yt:videoId."""
import sys, time, urllib.request, xml.etree.ElementTree as ET
sys.path.insert(0, '.')

UA = {"User-Agent": "Sycamore/0.3 (RSS reader; local use)"}
NS_M = "{http://search.yahoo.com/mrss/}"
NS_YT = "{http://www.youtube.com/xml/schemas/2015/}videoId"

FEED_URLS = [
    ("KrebsOnSecurity", "https://krebsonsecurity.com/feed/", 6),
    ("BleepingComputer", "https://www.bleepingcomputer.com/feed/", 6),
    ("The Hacker News", "https://thehackernews.com/rss.xml", 6),
    ("CISA Alerts", "https://www.cisa.gov/cybersecurity-advisories/all.xml", 4),
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", 8),
    ("gCaptain", "https://gcaptain.com/feed/", 6),
    ("SecurityWeek", "https://www.securityweek.com/feed/", 5),
    ("Dark Reading", "https://www.darkreading.com/rss.xml", 5),
    ("Al Jazeera English", "https://www.aljazeera.com/xml/rss/all.xml", 8),
    ("Guardian World", "https://www.theguardian.com/world/rss", 6),
    ("France24 EN", "https://www.france24.com/en/rss", 5),
    ("NPR World", "https://feeds.npr.org/1004/rss.xml", 5),
    ("Middle East Eye", "https://www.middleeasteye.net/rss", 5),
]

def probe(name, url, n):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            body = r.read(600_000)
        root = ET.fromstring(body)
        items = root.findall(".//item") or root.findall("{http://www.w3.org/2005/Atom}entry")
        enc = medc = yt = 0
        sample_enc, sample_med, sample_yt = "", "", ""
        for it in items[:n]:
            e = it.find("enclosure")
            if e is not None:
                enc += 1
                if not sample_enc and len(items) > 2:
                    sample_enc = f"url={(e.attrib.get('url') or '')[:70]} type={e.attrib.get('type')} len={e.attrib.get('length')}"
            m = it.find(f"{NS_M}content")
            if m is None:
                m = it.find("media:content")
            if m is not None:
                medc += 1
                if not sample_med and len(items) > 2:
                    urls = [u.attrib.get('url', '')[:60] for u in m.findall(f"{NS_M}thumbnail")] or [m.attrib.get('url','')[:60]]
                    sample_med = f"content={m.attrib.get('url','')[:50]} thumbs={urls}"
            y = it.find(NS_YT)
            if y is None:
                y = it.find("yt:videoId")
            if y is not None and (y.text or "").strip():
                yt += 1
                sample_yt = (y.text or "")[:20]
        print(f"{name}: items~{len(items)} enclosure={enc} mediaContent={medc} ytVideoId={yt}")
        if sample_enc:   print("   enc:", sample_enc)
        if sample_med:   print("   med:", sample_med)
        if sample_yt:    print("   yt :", sample_yt)
    except Exception as e:
        print(f"{name}: FAIL {type(e).__name__} {str(e)[:60]}")

if __name__ == "__main__":
    for name, url, n in FEED_URLS:
        probe(name, url, n)
        time.sleep(0.3)
