#!/usr/bin/env python3
"""True drop-reason census via real normalize() (feed topic hint + tiered geo)."""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sycamore_ingest import rss_client, normalizer

batch = list(rss_client.fetch_all())
print("items:", len(batch))
reasons = collections.Counter()
samples: dict[str, list] = {}

def sample(bucket, text):
    samples.setdefault(bucket, [])
    if len(samples[bucket]) < 4:
        samples[bucket].append(text)

for item in batch:
    arts = rss_client.to_articles([item])
    art = arts[0]
    title = (art.get('title') or '').strip()
    summary = (art.get('_rss_description') or '').strip()[:600]
    if len(title) < 10:
        reasons['short-title'] += 1; sample('short-title', f"{item.source}: {title[:80]}"); continue
    topic = art.get('_rss_topic') or normalizer.classify_topic(title)
    if topic is None:
        reasons['topic(feed-hint+classify)'] += 1; sample('topic', f"{item.source}: {title[:80]}"); continue
    try:
        lat = float(art.get("lat") or 0); lon = float(art.get("long") or 0)
    except (TypeError, ValueError):
        lat = lon = 0.0
    if normalizer.is_geocoded(lat, lon):
        reasons['source-geo'] += 1; continue
    hit_t = normalizer.resolve_location(title)
    if hit_t is not None:
        reasons['PASS tier1-title'] += 1; sample('tier1', f"{item.source}: {title[:80]} -> {hit_t.get('loc')}"); continue
    h2 = normalizer._resolve_event_geo(title, summary)
    if h2 is not None and (h2.get('geo') or {}).get('source') == 'summary':
        reasons['PASS tier2-summary'] += 1; sample('tier2', f"{item.source}: {title[:80]} -> {h2.get('loc')}"); continue
    # why no locative?
    mentions = normalizer._scan_text(title) + []
    smentions = normalizer._scan_text(summary) if summary else []
    t_loci = [m for m in _mentions := normalizer._scan_text(title) if normalizer._LOCATIVE.search(title[:m[0]])]
    s_mentions2 = normalizer._scan_text(summary) if len(summary) >= 40 else []
    s_loci = [m for m in s_mentions2 if normalizer._LOCATIVE.search(summary[:m[0]])]
    detail = f"tMentions={len(mentions)} tLoci={len(t_loci)} sMentions={len(s_mentions2)} sLoci={len(s_loci)} summLen={len(summary)}"
    reasons['drop-geo'] += 1
    sample('dropped', f"{item.source}: {title[:70]} | {detail}")

print("\n".join(f"  {r:34s} {c}" for r, c in sorted(reasons.items())))
for k in ('tier1', 'tier2', 'topic', 'dropped'):
    if samples.get(k):
        print(f"\n-- sample: {k}")
        for s in samples[k]:
            print("   ", s)
