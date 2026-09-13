#!/usr/bin/env python3
"""Probe candidate RSS/Atom feeds; print VERIFIED/DROPPED with reason."""
import sys, time, urllib.request, xml.etree.ElementTree as ET

CANDIDATES = [
    # (name, url, topic)
    ("SecurityWeek", "https://www.securityweek.com/feed/", "cyber"),
    ("Dark Reading", "https://www.darkreading.com/rss.xml", "cyber"),
    ("SC Magazine",  "https://www.scmagazine.com/rss.aspx", "cyber"),
    ("ESET Blog",   "https://blog.eset.net/feed/", "cyber"),
    ("Sophos News", "https://news.sophos.com/en-us/feed/", "cyber"),
    ("Recorded Future Newsroom", "https://www.recordedfuture.com/blog/rss.xml", "cyber"),
    ("Mandiant Blog","https://cloud.google.com/mandiant/threat-intelligence-blog/rss?hl=en", "cyber"),
    ("Trend Micro Vulnerability Lab","https://www.trendmicro.com/en_us/research/feed/vulnerabilities.html?type=rss", "cyber"),
    # geopolitical world desks
    ("Al Jazeera English", "https://www.aljazeera.com/xml/rss/all.xml", "geopolitical"),
    ("Guardian World",     "https://www.theguardian.com/world/rss", "geopolitical"),
    ("France24 EN",        "https://www.france24.com/en/rss", "geopolitical"),
    ("DW News World",      "https://rss.dw.com/rdf/rss-en-world", "geopolitical"),
    ("NPR World",          "https://feeds.npr.org/1004/rss.xml", "geopolitical"),
    ("ABC International",  "http://abcnews.go.com/International/headlines/dayfeed", "geopolitical"),
    ("Middle East Eye",     "https://www.middleeasteye.net/rss", "geopolitical"),
    ("Euronews EN",         "https://feeds.euronews.com/feeds/en-full.xml", "geopolitical"),
    # maritime / naval
    ("Naval News",          "https://navynews.co.uk/feed/", "maritime"),
    ("Marine Insight",      "https://www.marinelink.com/rss/newsfeed.rss?category=0", "maritime"),
    ("The Maritime Executive","https://www.maritimetraffic.com/?feed=rss2", "maritime"),
]

UA = {"User-Agent": "Sycamore/0.3 (RSS reader; local use)"}

def probe(name, url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            body = r.read(400_000)
        root = ET.fromstring(body)
        n_item = len(root.findall(".//item")) + len(root.findall("{http://www.w3.org/2005/Atom}entry"))
        if n_item == 0:
            return f"DROPPED {name}: parses but 0 items (root={root.tag})"
        # peek first title for sanity
        t = root.findtext(".//item/title") or ""
        ok_title = len(t) > 5 and not re_lower_has_html_tags(t, body[:200])
        return f"VERIFIED {name}: {n_item} items | sample: {(t or '')[:60]!r}"
    except Exception as e:
        return f"DROPPED {name}: {type(e).__name__}: {str(e)[:80]}"

def re_lower_has_html_tags(t, head):
    import re
    if "<" in t and ">" in t:
        # title with HTML is fine; only flag if the *head* looks like an error page
        pass
    return False

if __name__ == "__main__":
    for name, url, topic in CANDIDATES:
        print(probe(name, url), flush=True)
        time.sleep(0.4)
