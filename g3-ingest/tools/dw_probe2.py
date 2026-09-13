#!/usr/bin/env python3
"""Dump child element names of one DW RSS 1.0 item (passive)."""
import urllib.request, xml.etree.ElementTree as ET

req = urllib.request.Request(
    "https://rss.dw.com/rdf/rss-en-world",
    headers={"User-Agent": "Sycamore/0.3 (RSS reader; local use)"},
)
body = urllib.request.urlopen(req, timeout=15).read()
root = ET.fromstring(body)
items = root.findall(".//{http://purl.org/rss/1.0/}item")
print("n items:", len(items))
it = items[0]
for c in it:
    t = c.tag
    ns, _, local = (t[1:] if t.startswith("{") else "").partition("}") or ("", "", t)
    text = (c.text or "").strip()[:70].replace("\n", " ")
    print(f"  {ns + ':' if ns else ''}{local} -> {text!r}")
