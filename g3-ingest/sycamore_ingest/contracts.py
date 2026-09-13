"""Validate the project's shared draft-07 schema subset with no runtime dependencies.

Only the keywords used in shared/schemas are supported. Unknown assertions fail
closed so schema additions cannot silently bypass Python validation.

Iteration 1.1.2 additions:
- type arrays (e.g. ["integer", "null"]) matching one of a finite primitive list,
  preserving integer/boolean distinction and finite-number checks;
- maxItems bound for arrays;
- an explicit intelligence schema registry (INT-001): new record/index/detail
  schemas validate through validate_intelligence(name, value) and resolve only
  approved local schema names from the repository. Old API is preserved.
- cross-object checks (check_index / check_detail) that schema validity alone
  cannot prove: referential integrity, evidence-kind/excerpt pairing,
  related-card support, offset pairing and the 150 KiB detail cap.
"""
from __future__ import annotations
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit

SCHEMAS = Path(__file__).resolve().parents[2] / 'shared' / 'schemas'
ANNOTATIONS = {'$schema', 'title', 'description', 'default', '$id'}
ASSERTIONS = {'$ref', 'type', 'required', 'properties', 'additionalProperties', 'enum', 'const',
              'items', 'minItems', 'maxItems', 'minimum', 'maximum', 'minLength', 'maxLength', 'format', 'pattern'}

# INT-001: explicit registry of approved intelligence schema names. Only these
# names resolve; anything else (filesystem paths, URLs) fails closed.
INTELLIGENCE_SCHEMAS = {
    'record.schema.json': SCHEMAS / 'intelligence' / 'record.schema.json',
    'index.schema.json': SCHEMAS / 'intelligence' / 'index.schema.json',
    'detail.schema.json': SCHEMAS / 'intelligence' / 'detail.schema.json',
}
MAX_DETAIL_BYTES = 150 * 1024

_UID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


def _type_matches(value, kind) -> bool:
    """Match a JSON value against one primitive type name (or a nullable list)."""
    if isinstance(kind, list):
        return any(_type_matches(value, k) for k in kind)
    if kind == 'object':
        return isinstance(value, dict)
    if kind == 'array':
        return isinstance(value, list)
    if kind == 'string':
        return isinstance(value, str)
    if kind == 'integer':
        return type(value) is int
    if kind == 'number':
        return type(value) in (int, float) and math.isfinite(value)
    if kind == 'boolean':
        return type(value) is bool
    if kind == 'null':
        return value is None
    raise ValueError(f'Unsupported schema type: {kind!r}')


def validate(value, schema: dict, location: str = '$') -> None:
    unsupported = set(schema) - ANNOTATIONS - ASSERTIONS
    if unsupported:
        raise ValueError(f'Unsupported schema keywords: {unsupported}')
    if '$ref' in schema:
        ref = schema['$ref']
        if ref not in {'event.schema.json', 'manifest.schema.json'}:
            raise ValueError('Unsupported schema reference')
        validate(value, json.loads((SCHEMAS / ref).read_text()), location)
        return
    kind = schema.get('type')
    if kind and not _type_matches(value, kind):
        raise ValueError(f'{location}: expected {kind if isinstance(kind, list) else kind}')
    if 'const' in schema and (value != schema['const'] or type(value) is not type(schema['const'])):
        raise ValueError(f'{location}: invalid constant')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError(f'{location}: invalid enum')
    if isinstance(value, dict):
        if set(schema.get('required', [])) - set(value):
            raise ValueError(f'{location}: missing required fields')
        props = schema.get('properties', {})
        for key, item in value.items():
            if key in props:
                validate(item, props[key], f'{location}.{key}')
            elif schema.get('additionalProperties') is False:
                raise ValueError(f'{location}: unexpected field {key}')
            elif isinstance(schema.get('additionalProperties'), dict):
                validate(item, schema['additionalProperties'], f'{location}.{key}')
    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0):
            raise ValueError(f'{location}: too few items')
        if len(value) > schema.get('maxItems', float('inf')):
            raise ValueError(f'{location}: too many items')
        for i, item in enumerate(value):
            validate(item, schema.get('items', {}), f'{location}[{i}]')
    if isinstance(value, str):
        if not schema.get('minLength', 0) <= len(value) <= schema.get('maxLength', float('inf')):
            raise ValueError(f'{location}: invalid text length')
        if 'pattern' in schema and not re.search(schema['pattern'], value):
            raise ValueError(f'{location}: invalid text pattern')
        if schema.get('format') == 'uri':
            parsed = urlsplit(value)
            if not parsed.scheme or any(c.isspace() for c in value) or (parsed.scheme in ('http','https') and not parsed.netloc):
                raise ValueError(f'{location}: invalid URI')
    if type(value) in (int, float):
        if not math.isfinite(value) or not schema.get('minimum', -math.inf) <= value <= schema.get('maximum', math.inf):
            raise ValueError(f'{location}: invalid number')


def validate_intelligence(name: str, value) -> None:
    """Validate against an approved intelligence schema from the registry (INT-001).

    Only names in INTELLIGENCE_SCHEMAS resolve. Arbitrary $refs are rejected by
    validate() itself; this function never reads a path/URL from the value.
    """
    if name not in INTELLIGENCE_SCHEMAS:
        raise ValueError(f'Unsupported intelligence schema: {name!r}')
    schema = json.loads(INTELLIGENCE_SCHEMAS[name].read_text())
    validate(value, schema)
    # A registry schema must not smuggle unsupported refs or keywords.
    bad = _collect_unsupported(schema)
    if bad:
        raise ValueError(f'Intelligence schema {name} uses unsupported constructs: {bad}')


def _collect_unsupported(schema: dict, seen: set | None = None) -> list[str]:
    """Deep-scan a schema for $refs outside the approved set and unknown keywords.

    Walks actual schema nodes only: `items`, `additionalProperties` and each
    value under `properties`. A property map itself is not a schema node.
    """
    if seen is None:
        seen = set()
    key = id(schema)
    if key in seen or not isinstance(schema, dict):
        return []
    seen.add(key)
    problems: list[str] = []
    unsupported = set(schema) - ANNOTATIONS - ASSERTIONS
    if unsupported:
        problems.append(f'keywords {sorted(unsupported)}')
    if '$ref' in schema and schema['$ref'] not in {'event.schema.json', 'manifest.schema.json'}:
        problems.append(f"$ref {schema['$ref']!r}")
    if isinstance(schema.get('items'), dict):
        problems.extend(_collect_unsupported(schema['items'], seen))
    if isinstance(schema.get('additionalProperties'), dict):
        problems.extend(_collect_unsupported(schema['additionalProperties'], seen))
    for sub in (schema.get('properties') or {}).values():
        problems.extend(_collect_unsupported(sub, seen))
    return problems


# --------------------------------------------------------------------------
# Cross-object checks (INT-001, INTELLIGENCE_WIRE_SHAPES.md "Minimum cross-object validation")
# --------------------------------------------------------------------------

def check_index(index: dict) -> None:
    """Index UID/path structure and numeric-ID uniqueness."""
    validate_intelligence('index.schema.json', index)
    ids = [e['eventId'] for e in index['entries']]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate numeric event IDs in index')
    uids = [e['eventUid'] for e in index['entries']]
    if len(set(uids)) != len(uids):
        raise ValueError('Duplicate event UIDs in index')
    for entry in index['entries']:
        if not entry['artifactPath'].startswith('/data/intelligence/v1/releases/'):
            raise ValueError(f"Artifact path outside allowed structure: {entry['artifactPath']!r}")
        # reject dot segments, query, fragment
        if any(seg in ('..', '.') for seg in entry['artifactPath'].split('/')) or '?' in entry['artifactPath'] or '#' in entry['artifactPath']:
            raise ValueError(f'Unsafe artifact path: {entry["artifactPath"]!r}')
        expected_prefix = f"/data/intelligence/v1/releases/{index['releaseUid']}/events/{entry['eventUid']}.json"
        if entry['artifactPath'] != expected_prefix:
            raise ValueError(f'Artifact path does not match release/event UIDs: {entry["artifactPath"]!r}')


def check_detail(detail: dict, *, expected: dict | None = None) -> None:
    """Detail cross-object checks.

    expected may carry releaseUid/eventUid/eventRevisionUid/projectionHash to
    verify the artifact matches the request and index (reader consistency).
    """
    validate_intelligence('detail.schema.json', detail)
    if expected:
        for field in ('releaseUid', 'eventUid', 'eventRevisionUid', 'projectionHash'):
            if expected.get(field) is not None and detail[field] != expected[field]:
                raise ValueError(f'Detail {field} mismatch: {detail[field]!r} != {expected[field]!r}')

    evidence_uids = {e['evidenceUid'] for e in detail['evidence']}
    entity_uids = {e['entityUid'] for e in detail['entities']}
    timeline_uids = {t['entryUid'] for t in detail['timeline']}
    if len(evidence_uids) != len(detail['evidence']):
        raise ValueError('Duplicate evidence UIDs')
    if len(entity_uids) != len(detail['entities']):
        raise ValueError('Duplicate entity UIDs')
    if len(timeline_uids) != len(detail['timeline']):
        raise ValueError('Duplicate timeline entry UIDs')

    # All references point to included objects with unique UIDs.
    for ev in detail['evidence']:
        if ev['reportingOriginUid'] is not None and ev['reportingOriginUid'] not in evidence_uids:
            raise ValueError(f"Evidence {ev['evidenceUid']} references missing origin UID")
    for entity in detail['entities']:
        for mention in entity['mentions']:
            if mention['evidenceUid'] not in evidence_uids:
                raise ValueError(f"Mention {mention['mentionUid']} references missing evidence {mention['evidenceUid']}")
            start, end = mention['start'], mention['end']
            if (start is None) != (end is None):
                raise ValueError(f'Mention {mention["mentionUid"]} has unpaired offsets')
            if start is not None and not (0 <= start < end):
                raise ValueError(f'Mention {mention["mentionUid"]} has invalid offsets')
    for entry in detail['timeline']:
        for uid in entry['evidenceUids']:
            if uid not in evidence_uids:
                raise ValueError(f"Timeline {entry['entryUid']} references missing evidence {uid}")
    for card in detail['related']:
        for reason in card['reasons']:
            if reason['entityUid'] not in entity_uids:
                raise ValueError(f"Reason references missing entity {reason['entityUid']}")
            for uid in reason['evidenceUids']:
                if uid not in evidence_uids:
                    raise ValueError(f"Reason references missing evidence {uid}")
        if card['target']['eventUid'] == detail['eventUid']:
            raise ValueError('Related card targets the selected event itself')

    # No source_text with null excerpt; no metadata_only with invented excerpt.
    for ev in detail['evidence']:
        if ev['evidenceKind'] == 'source_text' and not ev.get('excerpt'):
            raise ValueError(f"Evidence {ev['evidenceUid']} is source_text with empty excerpt")
        if ev['evidenceKind'] == 'metadata_only' and ev.get('excerpt') is not None:
            raise ValueError(f"Evidence {ev['evidenceUid']} is metadata_only with invented excerpt")

    # Removed payloads must not remain in the excerpt.
    for ev in detail['evidence']:
        if ev['status'] == 'removed' and ev.get('excerpt'):
            raise ValueError(f"Removed evidence {ev['evidenceUid']} still carries an excerpt")

    # Complete detail <= 150 KiB uncompressed.
    size = len(json.dumps(detail, ensure_ascii=False, separators=(',', ':')))
    if size > MAX_DETAIL_BYTES:
        raise ValueError(f'Detail exceeds {MAX_DETAIL_BYTES} bytes: {size}')


def validate_event(event: dict) -> None:
    validate(event, json.loads((SCHEMAS / 'event.schema.json').read_text()))


def validate_snapshot(snapshot: dict) -> None:
    validate(snapshot, json.loads((SCHEMAS / 'snapshot.schema.json').read_text()))
    events, manifest = snapshot['events'], snapshot['manifest']
    if len({e['id'] for e in events}) != len(events) or manifest['counts']['events'] != len(events):
        raise ValueError('Inconsistent event IDs/counts')
    for group, field in [('byTopic', 't'), ('bySeverity', 'sev')]:
        actual: dict[str, int] = {}
        for event in events:
            actual[event[field]] = actual.get(event[field], 0) + 1
        counts = manifest['counts'][group]
        if any(counts.get(k, 0) != actual.get(k, 0) for k in set(counts) | set(actual)):
            raise ValueError('Inconsistent topic/severity counts')
    if manifest.get('nextEventId', max((e['id'] for e in events), default=0) + 1) <= max((e['id'] for e in events), default=0):
        raise ValueError('Invalid next event ID')