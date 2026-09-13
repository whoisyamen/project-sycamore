"""Offline geolocation audit/migration, serialized with the ingest runner.

Run from g3-ingest: python3 -m sycamore_ingest.fix_bad_geocodes
Backups and row-level quarantine evidence are private and must not be web-served.
"""
from __future__ import annotations
import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
from . import normalizer, runner
from .contracts import validate_snapshot

DEFAULT_ARCHIVE = Path(__file__).resolve().parents[1] / 'audits' / 'geolocation'


def _regeocode_event(event: dict) -> dict | None:
    return normalizer.resolve_location(event.get('title', ''))


def migrate(out: Path = runner.DEFAULT_OUT, archive_root: Path = DEFAULT_ARCHIVE) -> dict:
    out, archive_root = Path(out).resolve(), Path(archive_root).resolve()
    # Refuse even sibling directories under the web root (public/audit etc.).
    public_root = next((p for p in (out, *out.parents) if p.name == 'public'), out)
    if archive_root == public_root or public_root in archive_root.parents:
        raise ValueError('Audit archive must be outside public data/web root')
    out.mkdir(parents=True, exist_ok=True)
    with (out / '.ingest.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = runner._load_previous(out)
        # Deterministic content-addressed archive; reruns cannot overwrite evidence.
        serialized = json.dumps(previous, sort_keys=True, ensure_ascii=False).encode()
        digest = hashlib.sha256(serialized).hexdigest()
        archive = archive_root / digest
        archive.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(archive_root, 0o700)
        os.chmod(archive, 0o700)
        for filename in ('snapshot.json', 'events.json', 'manifest.json'):
            source = out / filename
            backup = archive / filename
            if source.exists() and not backup.exists():
                with backup.open('xb') as dest:
                    dest.write(source.read_bytes()); dest.flush(); os.fsync(dest.fileno())
                os.chmod(backup, 0o600)
        counts = dict(audited=len(previous['events']), preservedSource=0, updated=0,
                      unchanged=0, quarantined=0, published=0)
        records, events, quarantined = [], [], []
        for original in previous['events']:
            event = copy.deepcopy(original)
            if event.get('geo', {}).get('source') == 'source':
                action, reason = 'preservedSource', 'Explicit source coordinate provenance; preserved verbatim'
                events.append(event)
            else:
                hit = _regeocode_event(event)
                if hit is None:
                    action, reason = 'quarantined', 'No unique explicit headline locus under current policy; old coordinates are untrusted'
                    quarantined.append(original)
                else:
                    event.update(hit)
                    action = 'unchanged' if event == original else 'updated'
                    reason = 'Offline explicit headline locus; representative point, not incident coordinates'
                    events.append(event)
            counts[action] += 1
            record = {'id':original['id'], 'action':action, 'reason':reason, 'before':original,
                      'after':event if action != 'quarantined' else None}
            if original['id'] == 36 and 'West Bank' in original['title']:
                record['supportingSource'] = 'https://www.bbc.co.uk/news/videos/cn8evz26eyqo'
                record['sourceContext'] = 'BBC identifies al-Mughayyir, south of Nablus, occupied West Bank. Only a regional approximation is used.'
            records.append(record)
        counts['published'] = len(events)
        manifest = copy.deepcopy(previous['manifest'])
        if counts['updated'] or counts['quarantined']:
            manifest['counts'] = runner._counts(events)
        # Preserve ID high water and source-fetch timestamps; this is not a fetch.
        result = {'version':1, 'events':events, 'manifest':manifest}
        validate_snapshot(result)
        report = {'policy':normalizer.GEO_POLICY, 'inputSha256':digest, 'archive':str(archive),
                  'counts':counts, 'records':records}
        runner._atomic_write(archive / 'audit.json', report)
        runner._atomic_write(archive / 'quarantine.json', quarantined)
        # Evidence must be durable before canonical publication; runner validates
        # and commits canonical + both compatibility mirrors under the same lock.
        runner._publish(out, events, manifest)
        actual = json.loads((out / 'snapshot.json').read_text())
        validate_snapshot(actual)
        if actual != result or json.loads((out/'events.json').read_text()) != events or json.loads((out/'manifest.json').read_text()) != manifest:
            raise RuntimeError('Migration publication verification failed')
        return {k:v for k,v in report.items() if k != 'records'}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=runner.DEFAULT_OUT)
    parser.add_argument('--archive', type=Path, default=DEFAULT_ARCHIVE)
    args = parser.parse_args(argv)
    print(json.dumps(migrate(args.out, args.archive), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
