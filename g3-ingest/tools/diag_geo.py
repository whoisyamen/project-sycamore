#!/usr/bin/env python3
"""Diagnose: of all fetched RSS items, how many pass topic/geo gates and why do they drop?"""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sycamore_ingest import rss_client, normalizer

batch = list(rss_client.fetch_all())
print("items:", len(batch))
reasons = collections.Counter()
topic_hits = 0
geo_title = geo_summary = 0
samples_by_reason: dict[str, list] = {}

for item in batch:
    art = rss_client.to_articles([item])[0] if hasattr(rss_client, 'to_articles') else None
    title = (art.get('title') or '').strip()
    summary = (art.get('_rss_description') or '').strip()[:600]
    tpc = normalizer.classify_topic(title)
    if tpc is None:
        reasons['topic'] += 1
        samples_by_reason.setdefault('topic', [])
        if len(samples_by_reason['topic']) < 3:
            samples_by_reason['topic'].append(f"{item.source}: {title[:90]}")
        continue
    topic_hits += 1
    hit = normalizer.resolve_location(title)
    if hit is not None:
        geo_title += 1
        reasons['pass-title'] += 1
        continue
    h2 = normalizer._resolve_event_geo(title, summary)
    if h2 is not None and (h2.get('geo') or {}).get('source') == 'summary':
        geo_summary += 1
        reasons['pass-summary'] += 1
        samples_by_reason.setdefault('pass-summary', [])
        if len(samples_by_reason['pass-summary']) < 6:
            samples_by_reason['pass-summary'].append(f"{item.source}: {title[:70]} -> {h2.get('loc')}")
        continue
    reasons[f'drop-geo (summary_len={len(summary)})'] += 1

print("topic pass:", topic_hits)
print("tier1 title loci:", geo_title, "| tier2 summary loci:", geo_summary)
for r in sorted(reasons):
    print(f"  {r}: {reasons[r]}")
for k in ('pass-summary', 'topic'):
    if samples_by_reason.get(k):
        print(f"\n-- sample: {k}")
        for s in samples_by_reason[k]:
            print("   ", s)
