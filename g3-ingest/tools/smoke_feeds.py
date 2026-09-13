#!/usr/bin/env python3
"""Smoke-test full feed fetch after parser rewrite (read-only network probes)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sycamore_ingest import rss_client as rc

b = rc.fetch_all()
print("TOTAL:", len(b), "| ok_feeds:", b.succeeded, "| failed:", b.failed)
by_src: dict[str, list] = {}
for i in b:
    by_src.setdefault(i.source, []).append(i)
n_img = sum(1 for i in b if i.media_image)
n_vid = sum(1 for i in b if i.video_url)
print(f"items_with_feed_image={n_img} items_with_video_link={n_vid}")
for src, items in sorted(by_src.items()):
    sample = items[0]
    print(f"{src:24s} n={len(items):3d}  img_first={'Y' if sample.media_image else 'N'}  "
          f"pub_ms_ok={sample.published_ms is not None}  {sample.title[:58]}")
