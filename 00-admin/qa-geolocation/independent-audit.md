# Independent geolocation audit — complete

Scope: repair wrong geographic markers and verify existing local website before next iteration. No deployment or public communication authorized.

## Evidence

- Original complaint confirmed: id 36 (West Bank) was pinned at Minneapolis (44.97,-93.25); Clancy items at Helena MT (46.46,-111.98); Thailand headline at Santa Fe NM ("Lincoln Avenue"); Hormuz headlines at Montreal/Lincolnshire streets; "October Draft" at Stuarts Draft VA. All from unchecked online-geocoder hits.
- BBC source verified: https://www.bbc.co.uk/news/videos/cn8evz26eyqo identifies al-Mughayyir, south of Nablus, occupied West Bank. Regional approximation only.

## Fix (offline explicit-locus policy `explicit-locus-v1`)

- `g3-ingest/sycamore_ingest/normalizer.py`: `resolve_location()` resolves ONE headline locus from curated dicts (country/city/region) with locative prepositions (in/at/near/off/across/inside/outside/within/via). Actors, products, streets, person names, multi-loci abstain. `REGION_GEOCODE` covers West Bank, Strait of Hormuz (INT), Panama Canal. No network geocoding anywhere — `nominatim_client.py` deleted, zero references remain.
- Migration `fix_bad_geocodes.py`: lock-serialized, content-addressed private archive (`g3-ingest/audits/geolocation/<sha256>/` with snapshot/events/manifest backups, audit.json row records, quarantine.json), source-provenance rows preserved, canonical+mirrors published via runner with read-back verification.
- Final migration: audited 57, published 11, quarantined 46. Rescued vs first pass: Thailand id44, Hormuz id41.
- Tests: 18/18 ingest (`test_geolocation_safety` covers persons/products/streets/actors/pronoun-us/ambiguity/`to`-exclusion/migration), 19/19 frontend `npm run verify`, 28/28 Playwright `frontend-qa.mjs` on live 11-event data, `verify-live-data.py` probe green.
- Removed event pages return clean 404; no dead internal links (artifacts test).

## Known limitations (honest, by design)

- No incident-site precision anywhere: every marker is a representative point; UI copy says so.
- Headlines without an explicit locus are dropped from the wall (46/57 this cycle), including attacker-framed items (Russia/China as locus) and `to`-destination items ("risk to Hormuz shipping", "Ship to Hormuz").
- Bare "Washington"/"Plymouth"/"Korea" abstain as ambiguous; "Falkland Islands" lacks a `for`-locative; Arctic has no sane centroid.
- Next scheduled ingest re-validates and quarantines under the same policy; it cannot restore bad pins (no geocoder code remains).
