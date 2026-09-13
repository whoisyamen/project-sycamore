#!/usr/bin/env python3
"""Inspect DW RSS 1.0 RDF item structure (read-only, passive)."""
import urllib.request, xml.etree.ElementTree as ET

req = urllib.request.Request(
    "https://rss.dw.com/rdf/rss-en-world",
    headers={"User-Agent": "Sycamore/0.3 (RSS reader; local use)"},
)
body = urllib.request.urlopen(req, timeout=15).read()
print("bytes:", len(body))
root = ET.fromstring(body)

for tag in ("item", "{http://purl.org/rss/1.0/}item"):
    items = root.findall(f".//{tag}")
    print(tag, "->", len(items))
if not any(root.findall(f".//{t}") for t in ("item",)):
    # dump top-level children of channel to see item element naming
    ch = root.find(".//channel")
    if ch is not None:
        tags = [ET.QName(c).localname + (f" ns={ET.QName(c).namespace}" if c.tag.startswith("{") else "") for c in list(ch)[:12]]
        print("channel children:", tags)
