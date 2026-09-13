"""Smoke test for the normalizer. Run with: python3 tests/test_normalizer.py"""
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sycamore_ingest import normalizer


def assert_eq(name, got, want):
    ok = got == want
    mark = "OK " if ok else "FAIL"
    print(f"  {mark} {name}: got={got!r} want={want!r}")
    if not ok:
        raise SystemExit(1)


def test_classify_topic():
    print("classify_topic")
    assert_eq("cyber",        normalizer.classify_topic("Major ransomware attack on hospital"),  "cyber")
    assert_eq("maritime",     normalizer.classify_topic("Tanker reports piracy in Gulf of Aden"),  "maritime")
    assert_eq("military",     normalizer.classify_topic("Airstrike targets frontline positions"),   "military")
    assert_eq("geopolitical", normalizer.classify_topic("EU imposes new sanctions package"),       "geopolitical")
    assert_eq("drop",         normalizer.classify_topic("Local sports match ends 2-1"),            None)


def test_classify_severity():
    print("classify_severity")
    assert_eq("critical",   normalizer.classify_severity("Massive invasion reported", -3),  "critical")
    assert_eq("escalating", normalizer.classify_severity("Border tensions rise",        -6),  "escalating")
    assert_eq("watching",   normalizer.classify_severity("Diplomat visits capital",     0),   "watching")
    assert_eq("deesc",      normalizer.classify_severity("Ceasefire holds",             6),   "deesc")


def test_is_geocoded():
    print("is_geocoded")
    assert_eq("null island", normalizer.is_geocoded(0, 0),     False)
    assert_eq("missing",     normalizer.is_geocoded(None, 5),  False)
    assert_eq("valid",       normalizer.is_geocoded(50.1, 8.7), True)
    assert_eq("oob lat",     normalizer.is_geocoded(91, 0),     False)
    assert_eq("oob lon",     normalizer.is_geocoded(0, 181),    False)


def test_normalize_drop_paths():
    print("normalize (drops)")
    assert_eq("no title",     normalizer.normalize({"title": ""}, 1),                                          None)
    assert_eq("no geo",       normalizer.normalize({"title": "Ransomware hits hospital", "lat": 0, "long": 0, "language": "English", "url": "https://x", "domain": "x.com"}, 1), None)
    assert_eq("non-english",  normalizer.normalize({"title": "Ransomware hits hospital", "lat": 50, "long": 8, "language": "Russian", "url": "https://x", "domain": "x.com"}, 1), None)
    assert_eq("no url",       normalizer.normalize({"title": "Ransomware hits hospital", "lat": 50, "long": 8, "language": "English", "url": "", "domain": "x.com"}, 1), None)
    assert_eq("no topic",     normalizer.normalize({"title": "Local sports match ends 2-1", "lat": 50, "long": 8, "language": "English", "url": "https://x", "domain": "x.com"}, 1), None)


def test_normalize_happy_path():
    print("normalize (happy)")
    art = {
        "title":     "Critical infrastructure ransomware attack on regional power grid",
        "lat":       50.11,
        "long":      8.68,
        "language":  "English",
        "url":       "https://example.com/article",
        "domain":    "example.com",
        "seendate":  "20260903T120000Z",
        "tone":      -8.5,
        "location":  {"fullName": "Frankfurt", "countryCode": "DE"},
    }
    ev = normalizer.normalize(art, 42)
    assert ev is not None
    assert_eq("id",      ev["id"],      42)
    assert_eq("topic",   ev["t"],       "cyber")
    assert_eq("sev",     ev["sev"],     "critical")
    assert_eq("src",     ev["src"],     "example.com")
    assert_eq("loc",     ev["loc"],     "Frankfurt, DE")
    assert_eq("sources", ev["sources"], ["https://example.com/article"])
    assert_eq("tone",    ev["score"]["tone"], -8.5)


def test_geocode_no_false_positive():
    print("geocode (no false positive)")
    # 'rome' must NOT match inside 'chrome'; 'istanbul' inside the sentence
    # should match; 'Germany' should fall through to country centroid.
    assert_eq("rome in chrome -> None", normalizer._geocode_from_title("19 Chrome and Edge Extensions Found With Bad Code"),
              None)
    # city match
    istanbul = normalizer._geocode_from_title("Turkish Rescue Teams Search For 10 Missing After Cargo Ship Sinks Off Istanbul")
    assert istanbul is not None and istanbul[2] == "TR", f"istanbul geo: {istanbul}"
    # country fallback
    de = normalizer._geocode_from_title("Major outage reported across Germany")
    assert de is not None and de[2] == "DE", f"germany geo: {de}"


def test_dedupe_key_stable():
    print("dedupe_key")
    a = {"t": "cyber", "lat": 50.11, "lon": 8.68, "ts": 1700000000000, "title": "Foo Bar"}
    b = {"t": "cyber", "lat": 50.13, "lon": 8.71, "ts": 1700000000000, "title": "Foo bar"}  # small coord delta, lowercase
    assert_eq("same key", normalizer.dedupe_key(a), normalizer.dedupe_key(b))


# ── D-012: corroboration + confidence ───────────────────────────────────────

def _mk_ev(id=99, n_sources=1, hours_old_h=None):
    """Build a minimal event dict with `n_sources` distinct-host URLs."""
    now = int(__import__("time").time() * 1000)
    ingestedAt = now - (hours_old_h or 1.0) * 3600e3
    urls = [f"https://outlet{i}.com/story" for i in range(n_sources)]
    return {
        "id": id, "t": "cyber", "sev": "watching", "title": f"Test event number {id} for confidence math only",
        "src": urls[0].split("/")[2] if n_sources else "", "loc": "X", "lat": 1.0, "lon": 2.0,
        "ts": int(ingestedAt), "ingestedAt": int(ingestedAt), "sources": urls,
        "score": {"articles": max(n_sources, 1), "tone": 0.0, "quality": 80},
    }


def test_confidence_math():
    print("confidence (D-012)")
    now = int(__import__("time").time() * 1000)

    single_fresh = _mk_ev(90, n_sources=1, hours_old_h=1.0)
    normalizer.refresh_score(single_fresh, now)
    c_single = single_fresh["score"]["confidence"]

    multi_fresh = _mk_ev(91, n_sources=3, hours_old_h=1.0)
    normalizer.refresh_score(multi_fresh, now)
    c_multi = multi_fresh["score"]["confidence"]

    # Corroboration must raise confidence; freshness must not sink it below the single-source baseline by much.
    assert_eq("multi > single", c_multi > c_single, True)
    assert 1 <= c_single <= 97 and 1 <= c_multi <= 97

    # Recency decay: same corroboration, day-old vs fresh → lower confidence.
    multi_old = _mk_ev(92, n_sources=3, hours_old_h=40)
    normalizer.refresh_score(multi_old, now)
    assert_eq("older < fresher", multi_old["score"]["confidence"] < c_multi, True)

    # Corroboration dict must list distinct outlets.
    corr = multi_fresh["score"]["corroboration"]
    assert_eq("outlets count", len(corr["outlets"]), 3)
    assert_eq("sources mirrored", corr["sources"], multi_fresh["sources"])


def test_pulse_predicate():
    print("pulse (D-012)")
    now = int(__import__("time").time() * 1000)

    e_single_lowconf = _mk_ev(93, n_sources=1, hours_old_h=48.0)   # old + single → low conf
    normalizer.refresh_score(e_single_lowconf, now)
    assert_eq("old single not pulse", normalizer.pulse(e_single_lowconf), False)

    e_multi = _mk_ev(94, n_sources=2, hours_old_h=1.0)             # 2 sources → always pulse
    normalizer.refresh_score(e_multi, now)
    assert_eq("multi-source is pulse", normalizer.pulse(e_multi), True)


def test_backfill_idempotent():
    print("backfill (D-012)")
    ev = _mk_ev(95, n_sources=1, hours_old_h=2.0)
    changed_first  = normalizer.backfill_event(ev)
    snap = json.dumps({"c": ev["score"]["confidence"], "o": len(ev["sources"])})
    changed_second = normalizer.backfill_event(ev)
    assert_eq("first call modifies",  changed_first, True)
    assert_eq("second call no-op",   changed_second, False)
    snap2 = json.dumps({"c": ev["score"]["confidence"], "o": len(ev["sources"])})
    assert_eq("unchanged on re-run", snap == snap2, True)


def test_normalize_emits_confidence():
    print("normalize (D-012 fields)")
    art = {
        "title":     "Critical infrastructure ransomware attack on regional power grid",
        "lat": 50.11, "long": 8.68, "language": "English",
        "url": "https://example.com/article", "domain": "example.com",
        "seendate": "20260903T120000Z", "tone": -8.5,
        "location": {"fullName": "Frankfurt", "countryCode": "DE"},
    }
    ev = normalizer.normalize(art, 42)
    assert ev is not None and "confidence" in ev["score"], "normalize must emit confidence"
    corr = ev["score"]["corroboration"]
    assert_eq("single source", len(corr["sources"]), 1)


# ── D-014: geo precision tier + Nominatim path ──────────────────────────────


def test_normalize_tags_geo_precise_when_source_provided():
    print("normalize (geo precise from source)")
    art = {
        "title": "Ransomware hits Frankfurt hospital",
        "lat": 50.11, "long": 8.68, "language": "English",
        "url": "https://x.example/a", "domain": "x.example",
        "seendate": "20260903T120000Z", "tone": -3.0,
        "location": {"fullName": "Frankfurt", "countryCode": "DE"},
    }
    ev = normalizer.normalize(art, 100)
    assert ev is not None
    assert_eq("geo tier", ev["geo"]["tier"], "precise")
    assert_eq("geo source", ev["geo"]["source"], "source")


def test_normalize_tags_geo_approximate_when_falls_back_to_title():
    print("normalize (geo approximate from title geocoder)")
    # No source coords → title geocoder matches "Istanbul" → approximate
    art = {
        "title": "Cargo ship sinks off Istanbul",
        "language": "English",
        "url": "https://x.example/a", "domain": "x.example",
        "seendate": "20260903T120000Z", "tone": -2.0,
        "location": {"fullName": "", "countryCode": ""},
    }
    ev = normalizer.normalize(art, 101)
    assert ev is not None
    assert_eq("geo tier", ev["geo"]["tier"], "approximate")
    assert_eq("geo source", ev["geo"]["source"], "title")





def test_west_bank_title_resolves_to_palestine():
    print("normalize (West Bank title → Palestine centroid)")
    art = {
        "title":     "'We expect our sons to be killed,' father of teen shot dead in West Bank tells BBC",
        "language": "English",
        "url": "https://x.example/a", "domain": "x.example",
        "seendate": "20260903T120000Z", "tone": 0.0,
        "location": {"fullName": "", "countryCode": ""},
        "_rss_topic":      "geopolitical",
        "_rss_source":     "BBC World",
        "_rss_description": "",
    }
    ev = normalizer.normalize(art, 105)
    assert ev is not None, "West Bank must resolve to Palestine via local CITY_GEOCODE"
    assert_eq("geo source (local title match)", ev["geo"]["source"], "title")
    assert abs(ev["lat"] - 31.95) < 0.05, f"expected ~31.95N, got {ev['lat']}"
    assert abs(ev["lon"] - 35.30) < 0.05, f"expected ~35.30E, got {ev['lon']}"


def test_runner_merge_cycle():
    """End-to-end: two outlets covering the same story merge into one event; a re-fetch is dup."""
    import tempfile, shutil
    from sycamore_ingest import runner

    class FakeFeedItem:
        def __init__(self, title, link): self.title, self.link = title, link

    base_title = "Major ransomware hits regional power grid in Frankfurt"
    # Cycle 1 articles (outlet A + B cover the same story; C is unrelated).
    cycle1_urls = [f"https://a.example/{i}" for i in range(2)]   # same-host pair → still one outlet? no: two DIFFERENT hosts
    items_a = FakeFeedItem(base_title, "https://alpha.example/story-1")
    items_b = FakeFeedItem(base_title + ".", "https://beta.example/story-2")

    tmpdir = Path(tempfile.mkdtemp(prefix="syc-test-"))
    try:
        # ── cycle 1: outlet A only → one new event, single-source
        runner.rss_client.fetch_all   = lambda: [items_a]                      # type: ignore[method-assign]
        runner.rss_client.to_articles = lambda items: [{                       # type: ignore[method-assign]
            "title": it.title, "url": it.link, "domain": it.link.split("/")[2],
            "language": "English", "tone": -6.0, "seendate": "",
            "location": {"fullName": "", "countryCode": ""}, "lat": 50.11, "long": 8.68,
            "_rss_topic": "cyber", "_rss_source": it.link.split("/")[2], "_rss_description": "",
        } for it in items]
        m1 = runner.run(out_dir=tmpdir)
        evs1 = json.loads((tmpdir / "events.json").read_text())
        assert_eq("c1 events", len(evs1), 1)
        assert_eq("c1 merged", m1["counts"]["merged"], 0)

        # ── cycle 2: outlet B covers same story → merge, not a new event; A's re-fetch is dup
        items_b = FakeFeedItem(base_title + ".", "https://beta.example/story-2")
        runner.rss_client.fetch_all   = lambda: [items_a, items_b]             # type: ignore[method-assign]
        m2 = runner.run(out_dir=tmpdir)
        evs2 = json.loads((tmpdir / "events.json").read_text())
        assert_eq("c2 events still 1", len(evs2), 1)
        assert_eq("c2 merged=1 (B is new, A re-fetch counts as dup)", m2["counts"]["merged"], 1)
        ev = evs2[0]
        hosts = {u.split("/")[2].replace("www.", "") for u in ev["sources"]}
        assert_eq("two distinct outlets", len(hosts), 2)
        corr = ev["score"]["corroboration"]
        assert_eq("corr sources=2", len(corr["sources"]), 2)
        assert_eq("pulse true after merge", normalizer.pulse(ev), True)

        # ── cycle 3: same two articles again → both plain dups, no growth
        m3 = runner.run(out_dir=tmpdir)
        evs3 = json.loads((tmpdir / "events.json").read_text())
        assert_eq("c3 events still 1", len(evs3), 1)
        assert_eq("c3 merged=0",       m3["counts"]["merged"], 0)
        assert_eq("c3 deduped=2",      m3["counts"]["deduped"], 2)

        # ── manifest carries pulse count
        mf = json.loads((tmpdir / "manifest.json").read_text())
        assert isinstance(mf["counts"].get("pulse"), int), "manifest must carry counts.pulse"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    test_classify_topic()
    test_classify_severity()
    test_is_geocoded()
    test_normalize_drop_paths()
    test_normalize_happy_path()
    test_dedupe_key_stable()
    test_confidence_math()
    test_pulse_predicate()
    test_backfill_idempotent()
    test_normalize_emits_confidence()
    test_normalize_tags_geo_precise_when_source_provided()
    test_normalize_tags_geo_approximate_when_falls_back_to_title()
    test_west_bank_title_resolves_to_palestine()
    test_runner_merge_cycle()
    print("ALL PASSED")
