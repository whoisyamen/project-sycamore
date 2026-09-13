#!/usr/bin/env python3
"""One-shot: add media block + geo.source 'summary' to event.schema.json (order preserved)."""
import json, collections, sys

P = "/home/yams/operations/project-sycamore/shared/schemas/event.schema.json"
s = json.load(open(P), object_pairs_hook=collections.OrderedDict)
props = s["properties"]

assert "media" not in props, "media already present — rerun would double-insert"

# 1) geo.source enum gains 'summary' (locus found in the source's lede text).
src_enum = props["geo"]["properties"]["source"]["enum"]
if "summary" not in src_enum:
    src_enum.append("summary")
props["geo"]["description"] = (
    "D-014/D-020: provenance of the event's lat/lon. tier=precise means a real place was resolved; "
    "tier=approximate means a representative point is shown (geo.scope says whether country, city or region) and the marker is intentionally approximate, not incident-site accurate. Legacy rows pre-D-014 may lack this object; the client treats absence as approximate."
)

# 2) media block: same-origin image path + optional external video watch link.
media = collections.OrderedDict([
    ("type", "object"),
    ("description", (
        "D-020 event imagery, populated at ingest time only when the source feed ships an explicit "
        "image reference (Media RSS / enclosure) or a resolvable og:image on the article page. image is a same-origin path under public/data/media/ downloaded and size-capped by the ingest service; video_url is an external watch link from yt:videoId, never embedded.")),
    ("properties", collections.OrderedDict([
        ("image", collections.OrderedDict([
            ("type", "string"),
            ("pattern", "^data/media/[a-f0-9]{16}\\.jpe?g$"),
            ("description", "Same-origin path, relative to the site root. Absent = no verified image; UI must not fabricate one.",),
        ])),
        ("video_url", collections.OrderedDict([
            ("type", "string"),
            ("format", "uri"),
            ("pattern", "^https://www\\.youtube\\.com/watch\\?v=[A-Za-z0-9_-]{6,25}$"),
            ("description", "External watch link only (yt:videoId from the feed). Never embedded; user leaves the site on click.",),
        ])),
    ])),
])

# Insert before 'geo' to keep a stable visual order.
new_props = collections.OrderedDict()
for k, v in props.items():
    if k == "geo":
        new_props["media"] = media
    new_props[k] = v
if "media" not in new_props:  # pragma: no cover — safety net
    new_props["media"] = media

s["properties"] = new_props
with open(P, "w") as f:
    json.dump(s, f, indent=1)
    f.write("\n")
print("schema updated:", list(props.keys()))
