"""
Normalize a raw GDELT article record into the Sycamore event schema.

GDELT gives us article-level coverage; one article ≠ one event. We:
  1. Bucket into a topic (cyber / geopolitical / maritime / military)
     using a simple keyword gate on the article title.
  2. Drop records that can't be geocoded (GDELT provides lat/lon only when
     it can resolve a place; missing or 0/0 → drop, no guessing).
  3. Drop records that aren't English (GDELT language field).
  4. Map GDELT AvgTone (-100..+100) and an article count proxy to a
     severity tier.

Quality gate: only events with a domain, a real geocode, and ≥1 source URL
make it through. Garbage in, garbage out, so we filter aggressively.
"""
from __future__ import annotations
import re
import hashlib
from datetime import datetime, timezone
from typing import Any

# Topic gates. Order matters: more specific first.
CYBER_TOKENS = re.compile(
    r"\b(cyber|ransomware|phishing|malware|breach|hack(?:er|ing)?|"
    r"vulnerability|cve-\d|ddos|exploit|backdoor|zero-day|"
    r"credentials? (?:leak|stolen)|data (?:leak|exfil)|"
    r"control system|ot security|scada)\b",
    re.IGNORECASE,
)
MARITIME_TOKENS = re.compile(
    r"\b(maritime|naval|piracy|tanker|cargo ship|submarine|cable cut|"
    r"strait of hormuz|baltic sea|south china sea|red sea|shipping lane|"
    r"container ship|bulk carrier|merchant vessel|navy)\b",
    re.IGNORECASE,
)
MILITARY_TOKENS = re.compile(
    r"\b(military|airstrike|drone strike|artillery|missile|troops|"
    r"infantry|tank brigade|battalion|soldier|combat(?: zone)?|"
    r"frontline|front line|offensive|insurgent|militia)\b",
    re.IGNORECASE,
)
GEOPOL_TOKENS = re.compile(
    r"\b(sanction|tariff|diplomat(?:ic)?|embassy|consulate|election|"
    r"treaty|cease-?fire|humanitarian corridor|"
    r"foreign minister|state department|eu commission|nato|un security|"
    r"bilateral|multilateral|referendum|imposes|eu imposes|"
    r"imposes new|wto|world trade|opec|g7|g20)\b",
    re.IGNORECASE,
)

# Tiers (criticality) gate on tone and a couple of intensifiers.
CRITICAL_HINTS = re.compile(
    r"\b(offensive|invasion|massacre|killed|deadly|catastrophic|"
    r"emergency|outage|crippled|million|critical infrastructure|"
    r"state-?adjacent|attributed|zero-day|mass casualty)\b",
    re.IGNORECASE,
)


def classify_topic(title: str) -> str | None:
    """Return topic bucket, or None if the article doesn't match any of our gates."""
    if CYBER_TOKENS.search(title):
        return "cyber"
    if MARITIME_TOKENS.search(title):
        return "maritime"
    if MILITARY_TOKENS.search(title):
        return "military"
    if GEOPOL_TOKENS.search(title):
        return "geopolitical"
    return None


def classify_severity(title: str, tone: float) -> str:
    """Map (title, tone) to a severity tier. Conservative: default to watching."""
    if CRITICAL_HINTS.search(title) or tone <= -10:
        return "critical"
    if tone <= -5:
        return "escalating"
    if tone >= 5:
        return "deesc"
    return "watching"


def is_english(language: str) -> bool:
    """GDELT's language field is a 3-letter code. We only ship English for now."""
    return (language or "").lower().startswith("english") or (language or "").lower() == "en"


def is_geocoded(lat: float | None, lon: float | None) -> bool:
    """Drop 0/0 (the classic null-island artifact) and missing values."""
    if lat is None or lon is None:
        return False
    try:
        if float(lat) == 0.0 and float(lon) == 0.0:
            return False
    except (TypeError, ValueError):
        return False
    return -90 <= float(lat) <= 90 and -180 <= float(lon) <= 180


# Tiny city → (lat, lon, country_code) lookup. Used only as a fallback when the
# source article (typically an RSS feed) doesn't carry coordinates and the title
# or summary mentions a recognizable city. NOT exhaustive; only the cities that
# dominate geopolitics + cyber reporting. If a city isn't here, we drop the
# record rather than guess — bad geocodes are worse than no record.
CITY_GEOCODE: dict[str, tuple[float, float, str]] = {
    # NOTE: "washington" deliberately absent — bare "Washington" is ambiguous
    # (DC vs. state) and policy is to abstain on uncertainty.
    "new york":     (40.7128, -74.0060,  "US"),
    "san francisco":(37.7749, -122.4194, "US"),
    "los angeles":  (34.0522, -118.2437, "US"),
    "seattle":      (47.6062, -122.3321, "US"),
    "boston":       (42.3601, -71.0589,  "US"),
    "chicago":      (41.8781, -87.6298,  "US"),
    "atlanta":      (33.7490, -84.3880,  "US"),
    "london":       (51.5074, -0.1278,   "GB"),
    "brussels":     (50.8503,  4.3517,   "BE"),
    "paris":        (48.8566,  2.3522,   "FR"),
    "berlin":       (52.5200, 13.4050,   "DE"),
    "frankfurt":    (50.1109,  8.6821,   "DE"),
    "munich":       (48.1351, 11.5820,   "DE"),
    "moscow":       (55.7558, 37.6173,   "RU"),
    "kyiv":         (50.4501, 30.5234,   "UA"),
    "kiev":         (50.4501, 30.5234,   "UA"),
    "beijing":      (39.9042, 116.4074,  "CN"),
    "shanghai":     (31.2304, 121.4737,  "CN"),
    "hong kong":    (22.3193, 114.1694,  "HK"),
    "taipei":       (25.0330, 121.5654,  "TW"),
    "tokyo":        (35.6762, 139.6503,  "JP"),
    "seoul":        (37.5665, 126.9780,  "KR"),
    "singapore":    (1.3521,  103.8198,  "SG"),
    "new delhi":    (28.6139, 77.2090,   "IN"),
    "delhi":        (28.6139, 77.2090,   "IN"),
    "mumbai":       (19.0760, 72.8777,   "IN"),
    "dubai":        (25.2048, 55.2708,   "AE"),
    "riyadh":       (24.7136, 46.6753,   "SA"),
    "tel aviv":     (32.0853, 34.7818,   "IL"),
    "jerusalem":    (31.7683, 35.2137,   "IL"),
    "tehran":       (35.6892, 51.3890,   "IR"),
    "baghdad":      (33.3152, 44.3661,   "IQ"),
    "kabul":        (34.5553, 69.2075,   "AF"),
    "islamabad":    (33.6844, 73.0479,   "PK"),
    "lagos":        (6.5244,  3.3792,    "NG"),
    "johannesburg": (-26.2041, 28.0473,  "ZA"),
    "cairo":        (30.0444, 31.2357,   "EG"),
    "nairobi":      (-1.2921, 36.8219,   "KE"),
    "jakarta":      (-6.2088, 106.8456,  "ID"),
    "manila":       (14.5995, 120.9842,  "PH"),
    "sydney":       (-33.8688, 151.2093, "AU"),
    "ottawa":       (45.4215, -75.6972,  "CA"),
    "toronto":      (43.6532, -79.3832,  "CA"),
    "mexico city":  (19.4326, -99.1332,  "MX"),
    "buenos aires": (-34.6037, -58.3816, "AR"),
    "sao paulo":    (-23.5505, -46.6333, "BR"),
    "rio de janeiro":(-22.9068, -43.1729, "BR"),
    "the hague":    (52.0705,  4.3007,   "NL"),
    "amsterdam":    (52.3676,  4.9041,   "NL"),
    "rotterdam":    (51.9244,  4.4777,   "NL"),
    "stockholm":    (59.3293, 18.0686,   "SE"),
    "oslo":         (59.9139, 10.7522,   "NO"),
    "helsinki":     (60.1699, 24.9384,   "FI"),
    "warsaw":       (52.2297, 21.0122,   "PL"),
    "prague":       (50.0755, 14.4378,   "CZ"),
    "vienna":       (48.2082, 16.3738,   "AT"),
    "zurich":       (47.3769,  8.5417,   "CH"),
    "geneva":       (46.2044,  6.1432,   "CH"),
    "rome":         (41.9028, 12.4964,   "IT"),
    "madrid":       (40.4168, -3.7038,   "ES"),
    "lisbon":       (38.7223, -9.1393,   "PT"),
    "athens":       (37.9838, 23.7275,   "GR"),
    "ankara":       (39.9334, 32.8597,   "TR"),
    "istanbul":     (41.0082, 28.9784,   "TR"),
    "kiev":         (50.4501, 30.5234,   "UA"),
    "gaza":         (31.3547, 34.3088,   "PS"),
    "rafah":        (31.2825, 34.2447,   "PS"),
    "khartoum":     (15.5007, 32.5599,   "SD"),
    "addis ababa":  (9.0320,  38.7470,   "ET"),
    "kinshasa":     (-4.4419, 15.2663,   "CD"),
    "cape town":    (-33.9249, 18.4241,  "ZA"),
    "kigali":       (-1.9706, 30.1044,   "RW"),
    "dakar":        (14.7167, -17.4677,  "SN"),
    "accra":        (5.6037,  -0.1870,   "GH"),
    "casablanca":   (33.5731, -7.5898,   "MA"),
    "tunis":        (36.8065, 10.1815,   "TN"),
    "algiers":      (36.7538,  3.0588,   "DZ"),
    "tripoli":      (32.8872, 13.1913,   "LY"),
    "kabul":        (34.5553, 69.2075,   "AF"),
    "caracas":      (10.4806, -66.9036,  "VE"),
    "havana":       (23.1136, -82.3666,  "CU"),
    "sanaa":        (15.3694, 44.1910,   "YE"),
    "damascus":     (33.5138, 36.2765,   "SY"),
    "beirut":       (33.8938, 35.5018,   "LB"),
    "amman":        (31.9454, 35.9284,   "JO"),
    "hebron":       (31.5326, 35.0998,   "PS"),
    "nablus":       (32.2211, 35.2544,   "PS"),
    "jenin":        (32.4573, 35.2287,   "PS"),
    "ramallah":     (31.9038, 35.2034,   "PS"),
    "bethlehem":    (31.7054, 35.2024,   "PS"),
    "jericho":      (31.8667, 35.4500,   "PS"),
    "tulkarm":      (32.3104, 35.0286,   "PS"),
    "qalqilya":     (32.1897, 34.9706,   "PS"),
    "salfit":       (32.0836, 35.1749,   "PS"),
    "tubas":        (32.3211, 35.3697,   "PS"),
    # ── 2026-09 coverage expansion: capitals/majors of frequently-covered regions
    "doha":         (25.2854,  51.5310,  "QA"),
    "muscat":       (23.5880,  58.3829,  "OM"),
    "kuwait city":  (29.3759,  47.9774,  "KW"),
    "phnom penh":   (11.5564, 104.9282,  "KH"),
    "ho chi minh":  (10.8231, 106.6297,  "VN"),
    "vietnam city": (10.8231, 106.6297,  "VN"),   # legacy spelling of Ho Chi Minh City
    "hanoi":        (21.0285, 105.8542,  "VN"),
    "vientiane":    (17.9757, 102.6033,  "LA"),
    "yangon":       (16.7867,  96.1641,  "MM"),
    "kuala lumpur": ( 3.1390, 101.6869,  "MY"),
    "vilnius":      (54.6872,  25.2797,  "LT"),
    "riga":         (56.9496,  24.1052,  "LV"),
    "tallinn":      (59.4370,  24.7536,  "EE"),
    "belgrade":     (44.7866,  20.4489,  "RS"),
    "zagreb":       (45.8150,  15.9819,  "HR"),
    "sofia":        (42.6977,  23.3219,  "BG"),
    "bucharest":    (44.4268,  26.1025,  "RO"),
    "tirana":       (41.3275,  19.8187,  "AL"),
    "podgorica":    (42.4304,  19.2599,  "ME"),
    "skopje":       (41.9979,  21.4286,  "MK"),
    "ljubljana":    (46.0569,  14.5058,  "SI"),
    "bratislava":   (48.1486,  17.1077,  "SK"),
    "luxembourg city":(49.6113, 6.1322, "LU"),
    "dublin":       (53.3498,  -6.2603,  "IE"),
    "reykjavik":    (64.1466, -21.9426,  "IS"),
    "tbilisi":      (41.7151,  44.8271,  "GE"),   # country ambiguity avoided: city entry only; bare country name stays unlisted
    "yerevan":      (40.1792,  44.4993,  "AM"),
    "baku":         (40.4095,  49.8671,  "AZ"),
    "astana":       (51.1604,  71.4752,  "KZ"),
    "almaty":       (43.2220,  76.8512,  "KZ"),
    "dushanbe":     (38.5598,  68.7870,  "TJ"),
    "ashgabat":     (37.9514,  58.3242,  "TM"),
    "minsk":        (53.9006,  27.5590,  "BY"),
}


# Named regions and waterways with a single representative point. Used only
# for explicit headline loci ("in the West Bank", "Via Hormuz"); the marker
# is a regional approximation, never incident coordinates.
REGION_GEOCODE: dict[str, tuple[float, float, str]] = {
    "west bank":    (31.9466, 35.3027,   "PS"),  # covers the Palestinian-governed
                                                  # areas of the Jordan Valley, Hebron hills, Nablus,
                                                  # Jenin, etc. Better than letting an online geocoder
                                                  # resolve the ambiguous name to a US suburb.
    "hormuz":       (26.5667, 56.2528,   "INT"),  # Strait of Hormuz waterway.
    "panama canal": (9.08,   -79.68,     "PA"),
    # Waterways/sea regions that dominate Houthi-era shipping news; INT = open sea.
    "red sea":      (19.5000, 38.7000,   "INT"),
    "gulf of aden": (12.6667, 48.6667,   "INT"),
}
REGION_LABEL = {
    "west bank":    "West Bank, Palestine",
    "hormuz":       "Strait of Hormuz, INT",
    "panama canal": "Panama Canal, PA",
    "red sea":      "Red Sea, open water (INT)",
    "gulf of aden": "Gulf of Aden, open water (INT)",
}


# Only dictionary names in explicit locative phrases qualify. Actor countries,
# arbitrary proper nouns and old marker labels are never location evidence.
GEO_POLICY = "explicit-locus-v1"          # tier 1 only: headline locative locus (legacy)
GEO_POLICY_V2 = "tiered-locus-v2"         # + tier 2: source-lede single mention, same guards
_LOCATIVE = re.compile(r"\b(?:in|at|near|off|across|inside|outside|within|via)\s+(?:the\s+)?$", re.I)
_ADDRESS_SUFFIX = re.compile(r"^\s+(?:road|street|avenue|drive|lane|boulevard|way|rd|st|ave)\b", re.I)
# A capitalized word after a place name usually continues a proper noun
# ("Paris Hilton") — unless a second capitalized word follows ("Hormuz Keeps
# Below"), which marks a title-case headline verb, not a name.


def _geocode_table() -> dict[str, tuple[float, float, str]]:
    return {**COUNTRY_GEOCODE, **CITY_GEOCODE, **REGION_GEOCODE}


def _scan_text(text: str) -> list[tuple[int, int, str, tuple[float, float, str]]]:
    """Find dictionary place mentions in `text` with false-match guards.

    Returns (start, end, name, coords). Same rules for titles and summaries —
    the coverage difference between tiers is only WHICH text we scan.
    """
    table = _geocode_table()
    mentions: list[tuple[int, int, str, tuple[float, float, str]]] = []
    occupied: list[tuple[int, int]] = []
    for name in sorted(table, key=len, reverse=True):
        flags = 0 if name in {"US", "U.S.", "U.S", "UK", "U.K."} else re.I
        for match in re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, flags):
            start, end = match.span()
            if any(start < b and end > a for a, b in occupied):
                continue
            occupied.append((start, end))
            if not match.group()[0].isupper():
                continue
            suffix = text[end:]
            cont = re.match(r"\s+[A-Z][a-z]+", suffix)
            if _ADDRESS_SUFFIX.search(suffix) or (cont and not re.match(
                    r"\s+[A-Z][a-z]+", suffix[cont.end():])):
                continue
            mentions.append((start, end, name, table[name]))
    return mentions


def resolve_location(title: str) -> dict | None:
    """One explicit locus in the headline; uncertainty means abstain.

    No network or summary fallback — this is tier 1 of _resolve_event_geo().
    Dictionary names embedded in longer proper nouns, street addresses, and
    coordinated/multiple loci are not resolved.
    """
    mentions = _scan_text(title)
    loci = [m for m in mentions if _LOCATIVE.search(title[:m[0]])]
    if len({m[3] for m in loci}) != 1:
        return None
    chosen = loci[0]
    for other in mentions:
        if other[0] > chosen[1] and other[3] != chosen[3]:
            if re.search(r"\b(?:and|or)\b|/|&", title[chosen[1]:other[0]], re.I):
                return None
    start, end, name, (lat, lon, country) = chosen
    return _build_location(title, start, end, name, lat, lon, country, source="title")


def _build_location(text: str, start: int, end: int, name: str,
                    lat: float, lon: float, country: str, source: str) -> dict:
    """Assemble the location record for a chosen dictionary mention."""
    if name in REGION_GEOCODE:
        label = f"{REGION_LABEL[name]} (regional approximation)"
        scope = "region"
    else:
        label = f"{text[start:end]}, {country} (approximate)"
        scope = "city" if name in CITY_GEOCODE else "country"
    return {"lat": lat, "lon": lon, "loc": label[:80],
            "geo": {"tier": "approximate", "source": source, "policy": GEO_POLICY_V2,
                    "scope": scope, "evidence": text[start:end]}}


def _resolve_event_geo(title: str, summary: str) -> dict | None:
    """Tiered location resolution; uncertainty means abstain (never guess).

    Tier 1 — explicit locative locus in the headline (source="title"): strictest.
    Tier 2 — single locative dictionary mention in the source's own lede text
             (summary, source="summary"). Prose summaries carry far more location
             signal than headlines; the same false-match guards apply, plus a
             minimum length so boilerplate stubs can't produce hits.
    Multiple distinct places anywhere → abstain. No network geocoding at any tier.
    """
    hit = resolve_location(title)
    if hit is not None:
        return hit
    summary = (summary or "").strip()
    if len(summary) < 40:
        return None
    mentions = _scan_text(summary)
    loci = [m for m in mentions if _LOCATIVE.search(summary[:m[0]])]
    if not loci or len({m[3][2] for m in loci}) != 1:
        # Distinct country codes, not raw coords — a city and its capital region
        # can share coordinates without being the "same place" claim we need.
        return None
    start, end, name, (lat, lon, cc) = loci[0]
    return _build_location(summary, start, end, name, lat, lon, cc, source="summary")


def _geocode_from_title(title: str) -> tuple[float, float, str] | None:
    hit = resolve_location(title)
    if hit is None:
        return None
    name = hit["geo"]["evidence"]
    key = name.lower()
    return CITY_GEOCODE.get(key) or REGION_GEOCODE.get(key) or COUNTRY_GEOCODE.get(key) or COUNTRY_GEOCODE.get(name)


# Country-name fallback. Used when a city isn't in our table but the article
# clearly names a country. Coordinates are country centroids — coarse but
# good enough for a heatmap dot.
COUNTRY_GEOCODE: dict[str, tuple[float, float, str]] = {
    "united states":  (39.8283,  -98.5795,  "US"),
    "US":            (39.8283, -98.5795, "US"),
    "U.S.":          (39.8283, -98.5795, "US"),
    "U.S":           (39.8283, -98.5795, "US"),
    "united kingdom": (55.3781,   -3.4360,  "GB"),
    "britain":        (55.3781,   -3.4360,  "GB"),
    "russia":         (61.5240,  105.3188,  "RU"),
    "ukraine":        (48.3794,   31.1656,  "UA"),
    "china":          (35.8617,  104.1954,  "CN"),
    "japan":          (36.2048,  138.2529,  "JP"),
    "south korea":    (35.9078,  127.7669,  "KR"),
    "north korea":    (40.3399,  127.5101,  "KP"),
    "taiwan":         (23.6978,  120.9605,  "TW"),
    "iran":           (32.4279,   53.6880,  "IR"),
    "iraq":           (33.2232,   43.6793,  "IQ"),
    "israel":         (31.0461,   34.8516,  "IL"),
    "palestine":      (31.9522,   35.2332,  "PS"),
    "syria":          (34.8021,   38.9968,  "SY"),
    "lebanon":        (33.8547,   35.8623,  "LB"),
    "yemen":          (15.5527,   48.5164,  "YE"),
    "saudi arabia":   (23.8859,   45.0792,  "SA"),
    "türkiye":        (38.9637,   35.2433,  "TR"),
    "egypt":          (26.8206,   30.8025,  "EG"),
    "sudan":          (12.8628,   30.2176,  "SD"),
    "ethiopia":       (9.1450,    40.4897,  "ET"),
    "kenya":          (-0.0236,   37.9062,  "KE"),
    "nigeria":        (9.0820,     8.6753,  "NG"),
    "south africa":   (-30.5595,  22.9375,  "ZA"),
    "indonesia":      (-0.7893,  113.9213,  "ID"),
    "philippines":    (12.8797,  121.7740,  "PH"),
    "australia":      (-25.2744, 133.7751,  "AU"),
    "canada":         (56.1304, -106.3468,  "CA"),
    "mexico":         (23.6345, -102.5528,  "MX"),
    "brazil":         (-14.2350, -51.9253,  "BR"),
    "argentina":      (-38.4161, -63.6167,  "AR"),
    "colombia":       (4.5709,   -74.2973,  "CO"),
    "venezuela":      (6.4238,   -66.5897,  "VE"),
    "germany":        (51.1657,   10.4515,  "DE"),
    "france":         (46.2276,    2.2137,  "FR"),
    "spain":          (40.4637,   -3.7492,  "ES"),
    "italy":          (41.8719,   12.5674,  "IT"),
    "netherlands":    (52.1326,    5.2913,  "NL"),
    "belgium":        (50.5039,    4.4699,  "BE"),
    "switzerland":    (46.8182,    8.2275,  "CH"),
    "austria":        (47.5162,   14.5501,  "AT"),
    "poland":         (51.9194,   19.1451,  "PL"),
    "sweden":         (60.1282,   18.6435,  "SE"),
    "norway":         (60.4720,    8.4689,  "NO"),
    "finland":        (61.9241,   25.7482,  "FI"),
    "denmark":        (56.2639,    9.5018,  "DK"),
    "greece":         (39.0742,   21.8243,  "GR"),
    "portugal":       (39.3999,   -8.2245,  "PT"),
    "romania":        (45.9432,   24.9668,  "RO"),
    "hungary":        (47.1625,   19.5033,  "HU"),
    "afghanistan":    (33.9391,   67.7100,  "AF"),
    "pakistan":       (30.3753,   69.3451,  "PK"),
    "india":          (20.5937,   78.9629,  "IN"),
    "bangladesh":     (23.6850,  90.3563,  "BD"),
    "thailand":       (13.7563,  100.5018,  "TH"),
    # ── 2026-09 coverage expansion: high-frequency world-news countries whose
    # absence was dropping real events from the map. Representative points only;
    # tier stays approximate and the UI says so. Deliberately ABSENT (ambiguity):
    # "georgia" (US state), "congo"/"dr congo" (two states), bare "turkey" kept
    # but see note below, "sri lanka"/"cote d'ivoire" spelling variance.
    "vietnam":        (16.5000, 107.8000,  "VN"),
    "myanmar":        (21.9000,  95.9643,  "MM"),
    "burma":          (21.9000,  95.9643,  "MM"),   # alternate name for Myanmar
    "malaysia":       ( 4.2100, 101.9758,  "MY"),
    "cambodia":       (12.5700, 104.9900,  "KH"),
    "laos":           (19.2500, 102.4700,  "LA"),
    "bahrain":        (26.0700,  50.5500,  "BH"),
    "qatar":          (25.3500,  51.1832,  "QA"),
    "oman":           (21.4700,  55.9800,  "OM"),
    "kuwait":         (29.3100,  47.4807,  "KW"),
    "jordan":         (30.5900,  36.2400,  "JO"),   # was missing despite Amman city entry
    "belarus":        (53.7100,  27.9300,  "BY"),
    "czechia":        (49.8200,  15.4699,  "CZ"),
    "libya":          (26.3400,  17.2300,  "LY"),
    "morocco":        (31.7900,  -7.0900,  "MA"),
    "algeria":        (28.0400,   1.6600,  "DZ"),
    "tunisia":        (33.8800,   9.5000,  "TN"),
    "mali":           (17.5700,  -3.9900,  "ML"),
    "chad":           (15.4500,  18.7300,  "TD"),
    "angola":         (-11.2000,  17.8700, "AO"),
    "peru":           (-9.1900, -75.0200,  "PE"),
    "ecuador":        ( -1.8300, -78.1800, "EC"),
    # Bare "turkey" is a food false-positive risk; the locative-prefix rule and
    # initial-capital check make it safe in practice ("in Turkey," but not
    # lowercase prose), so include with care — evidence pass will confirm drops.
    "turkey":         (38.9637,  35.2433,  "TR"),   # plain-spelling alias of türkiye
}


def _gdelt_date_to_ms(date_str: str) -> int:
    """GDELT dates are YYYYMMDDTHHMMSSZ; convert to ms since epoch UTC."""
    try:
        dt = datetime.strptime(date_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        return int(datetime.now(timezone.utc).timestamp() * 1000)


def _country_to_label(country_code: str) -> str:
    """GDELT gives us 2- or 3-letter codes. We surface the code, not a full name,
    because we don't have an authoritative name table in this service."""
    return (country_code or "").upper().strip() or "??"


def _quality_score(article: dict[str, Any], tone: float) -> int:
    """0-100 quality score. Title length and tone extremity raise it slightly."""
    s = 40
    title = article.get("title", "") or ""
    if 30 <= len(title) <= 180:
        s += 20
    if article.get("domain"):
        s += 20
    if abs(tone) >= 3:
        s += 10
    if article.get("socialimage"):
        s += 10
    return min(s, 100)


# ── Corroboration & confidence (D-012) ───────────────────────────────────────
# Confidence is a deterministic local estimate of how well-corroborated an event
# is. It uses ONLY fields we already hold: source quality tier, number of
# independent reporting outlets, and recency. No LLM, no network at read time.
# The UI must present it as "confidence" (our estimate), never as a fact about
# the underlying incident — same honesty discipline as the SAMPLE DATA chip.

SOURCE_TIERS: dict[str, int] = {
    # Tier 3: official / primary sources
    "cisa alerts":       3,
    "us-cert":           3,
    # Tier 2: named editorial outlets with a track record on their beat
    "krebsonsecurity":   2,
    "bleepingcomputer":  2,
    "the hacker news":   2,
    "reuters world":     2,
    "ap top news":       2,
    "gcaptain":          1,
}


def source_tier(source_name: str) -> int:
    """Quality tier for a known feed name. Unknown domains get 0 (neutral)."""
    return SOURCE_TIERS.get((source_name or "").lower(), 0)


def _host_of(url: str) -> str:
    try:
        from urllib.parse import urlparse
        h = urlparse(url).netloc.replace("www.", "")
        if "." in h and h.split(".")[-1] not in ("com", "org", "gov", "edu", "uk"):
            # keep 2-level hosts (krebsonsecurity.com) but don't mangle odd ones
            pass
        return h or url
    except Exception:
        return url


def _confidence(quality: int, outlets: list[str], hours_old: float) -> int:
    """0-100. Base 35 + quality*0.2 (max ~7) + outlet diversity (min 40) - recency decay."""
    s = 35 + round(quality * 0.2)
    # Each independent outlet beyond the first adds confidence, capped at +40.
    extra = max(0, len(set(outlets)) - 1)
    s += min(extra * 18, 40)
    # Recency decay: full credit <6h old, down to ~-25 by day-old and floored there.
    if hours_old > 6:
        age_h = max(0.0, hours_old - 6)
        s -= int(min(age_h * (25 / 48), 25))
    return max(1, min(s, 97))


def _corroboration(ev: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Derive (source_urls, unique_outlet_hosts) from an event's source URLs."""
    urls = [u for u in ev.get("sources", []) if isinstance(u, str) and u.startswith(("http://", "https://"))]
    hosts: list[str] = []
    seen: set[str] = set()
    for u in urls:
        h = _host_of(u).lower()
        if h not in seen:
            seen.add(h)
            hosts.append(h)
    return urls, hosts


def _score_fields(ev: dict[str, Any], now_ms: int | None = None) -> tuple[dict, int]:
    """Compute (corroboration_dict, confidence_int) from an event's current state."""
    now = int((now_ms or datetime.now(timezone.utc).timestamp() * 1000))
    urls, hosts = _corroboration(ev)
    quality = int(((ev.get("score") or {}).get("quality")) or 40)
    hours_old = max(0.0, (now - ev.get("ingestedAt", now)) / 3_600_000)
    # Diversity is measured by distinct reporting hosts — that's what "corroborated"
    # means here. Single-source rows yield exactly one host → no diversity bonus.
    outlets = hosts or ([ev["src"]] if ev.get("src") else ["unknown"])
    conf = _confidence(quality, outlets, hours_old)
    return {"sources": urls, "outlets": hosts}, conf


def refresh_score(ev: dict[str, Any], now_ms: int | None = None) -> None:
    """Recompute score.corroboration + score.confidence in place. Unconditional.

    The runner calls this on EVERY event each cycle so confidence always reflects
    current corroboration AND current age (it decays). Cheap local math, no I/O.
    Single-source rows stay single-outlet here; the diversity bonus only accrues
    when merge cycles accumulate real multi-source corroboration.
    """
    corr, conf = _score_fields(ev, now_ms)
    score = ev.setdefault("score", {})
    score["corroboration"] = corr
    score["confidence"] = conf


def backfill_event(ev: dict[str, Any], now_ms: int | None = None) -> bool:
    """Guarded one-shot migration for legacy events missing the new fields.

    Idempotent: an event that already has both corroboration + confidence is left
    untouched (the runner's per-cycle refresh_score keeps those fresh instead).
    Returns True if the event was modified.
    """
    score = ev.setdefault("score", {})
    if isinstance(score.get("corroboration"), dict) and "confidence" in score:
        return False
    corr, conf = _score_fields(ev, now_ms)
    score["corroboration"] = corr
    score["confidence"] = conf
    return True


def pulse(ev: dict[str, Any]) -> bool:
    """PULSE predicate (D-012): corroborated by 2+ sources OR high single-source confidence."""
    score = ev.get("score", {}) or {}
    corr = score.get("corroboration") or {}
    n_sources = len(corr.get("sources") or []) if isinstance(corr, dict) else len(ev.get("sources") or [])
    conf = int(score.get("confidence") or 0)
    return n_sources >= 2 or conf >= 85


def normalize(article: dict[str, Any], next_id: int) -> dict[str, Any] | None:
    """Convert one GDELT or RSS record into a Sycamore event. Returns None to drop."""
    title = (article.get("title") or "").strip()
    if len(title) < 10:
        return None

    if not is_english(article.get("language", "")):
        return None

    # Topic: prefer the RSS-feed hint if present, else run the keyword gate.
    topic = article.get("_rss_topic") or classify_topic(title)
    if topic is None:
        return None

    # Source coordinates retain their provenance; headline/summary fallback is offline.
    try:
        lat = float(article.get("lat") or 0)
        lon = float(article.get("long") or 0)
    except (TypeError, ValueError):
        lat, lon = 0, 0
    # Source's own lede (RSS description). Optional — many feeds don't ship one.
    summary = (article.get("_rss_description") or "").strip()[:600]

    title_location = None
    if not is_geocoded(lat, lon):
        title_location = _resolve_event_geo(title, summary)
        if title_location is None:
            return None
        lat, lon = title_location["lat"], title_location["lon"]
        country = ""
        geo_source, geo_tier = "title", "approximate"
    else:
        country = _country_to_label((article.get("location") or {}).get("countryCode", ""))
        geo_source, geo_tier = "source", "precise"

    try:
        tone = float(article.get("tone") or 0)
    except (TypeError, ValueError):
        tone = 0.0

    loc_full = (article.get("location") or {}).get("fullName") or "Unknown"
    loc = title_location["loc"] if title_location else (f"{loc_full}, {country}" if loc_full != "Unknown" else country)

    src = (article.get("_rss_source") or article.get("domain") or "GDELT").strip()
    url = (article.get("url") or "").strip()
    if not url:
        return None

    quality = _quality_score(article, tone)
    ev = {
        "id":         next_id,
        "t":          topic,
        "sev":        classify_severity(title, tone),
        "title":      title[:200],
        "summary":    summary,                 # may be empty
        "src":        src,
        "loc":        loc[:80],
        "lat":        lat,
        "lon":        lon,
        "ts":         _gdelt_date_to_ms(article.get("seendate", "")) or int(datetime.now(timezone.utc).timestamp() * 1000),
        "ingestedAt": int(datetime.now(timezone.utc).timestamp() * 1000),
        "sources":    [url],
        "score": {
            "articles": 1,
            "tone":     round(tone, 1),
            "quality":  quality,
        },
        "geo": {
            "tier":    geo_tier,
            "source":  geo_source,
        },
    }
    if title_location:
        ev["geo"] = title_location["geo"]
    # New events start single-source; backfill_event computes corroboration +
    # confidence from the same fields so new and legacy rows share one code path.
    if not ev["src"]:
        ev["src"] = _host_of(url) or "GDELT"
    backfill_event(ev, now_ms=ev["ingestedAt"])
    return ev


def dedupe_key(ev: dict[str, Any]) -> str:
    """Stable hash for dedupe. Title + rounded coords + day bucket."""
    day = ev["ts"] // (1000 * 60 * 60 * 24)
    # Round coords to ~10km so a single event reported from nearby towns
    # doesn't dedupe to two records.
    bucket_lat = round(ev["lat"], 1)
    bucket_lon = round(ev["lon"], 1)
    # D-012: strip punctuation before truncating, because outlets rephrase the
    # same headline with different trailing marks ("X hits Y" vs "X Hits Y!").
    # Without this, corroboration merges would almost never fire on real feeds.
    norm_title = re.sub(r"[^a-z0-9 ]", "", (ev.get("title") or "").lower())[:60]
    raw = f"{ev['t']}|{bucket_lat}|{bucket_lon}|{day}|{norm_title}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
