"""Archive-mode publication and ordered replay (iteration 1.2.2, spec §5.2).

Authority model per INT-003: in archive mode the SQLite DB is authoritative for
the v1 projection. One explicit transaction stores run/source health/observations/
revisions AND an immutable publication payload with a monotonic sequence; files on
disk are a replayable forward-only projection of committed payloads, never a second
authority. JSON and DB writes are explicitly NOT one transaction — the pending-job
queue plus hash-verified replay is what makes crashes recoverable without refetching
sources or regressing public content.

Failure matrix coverage (spec §5.2) lives in tests/test_publication.py; each row of
the spec table maps to an injected-failure fixture there.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from .archive import (Archive, _begin_run_tx, _ensure_counter_tx,
                      _finish_run_tx, _link_event_revision_tx, _new_uid,
                      _now_ms, _record_batch_tx, sha256_hex)


class PublicationError(RuntimeError):
    """Base for publication/replay failures."""


class PayloadHashMismatch(PublicationError):
    """Stored payload bytes no longer match the recorded hash (corruption)."""


def _payload_bytes(snapshot: dict) -> bytes:
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode('utf-8')


# Display labels used by the runner's failed-source list -> provider UIDs. Cycle-level
# failure names that are not providers ('Invalid source records', OSINT layer names)
# never become health rows; they live in manifest.health and run outcome only.
_PROVIDER_LABELS = {'RSS': 'rss', 'GDELT': 'gdelt'}


def _provider_uids(failed_sources: Iterable[str]) -> set[str]:
    return {_PROVIDER_LABELS[s.upper()] for s in failed_sources if s.upper() in _PROVIDER_LABELS}


# -- commit ------------------------------------------------------------------

def commit_cycle(archive: Archive, *, started_ms: int, provider_articles: list[tuple[str, list[dict]]],
                 failed_sources: Iterable[str] | None = None,
                 revision_items: list[tuple[int, dict]] | None = None,
                 snapshot_payload: dict) -> dict:
    """Store one cycle's committed state + publication intent in ONE transaction.

    provider_articles: [(provider_uid, fetched articles)] — every article observed this
        run (accepted or rejected by normalization), the same single-fetch batch the
        legacy/shadow paths use; an empty list records nothing for that provider and a
        failed provider still gets its 'failed' health row from `failed_sources`.
    revision_items: [(legacy_id, semantic_content)] for every PRE-prune merged event —
        material revisions are appended only when the semantic hash changes (clock-only
        cycles append nothing), with evidence links to this run's source observations.
    snapshot_payload: full v1 {'version','events'(<=MAX_EVENTS),'manifest'}; validated
        here, inside the transaction, before any publication row is written.

    Returns {'publication_uid': str, 'sequence': int}. Any exception rolls back ALL of
    it — no partial rows (spec §5.2 "before DB commit").
    """
    from .contracts import validate_snapshot  # local: keep module import light/cycle-free
    failed_labels = list(failed_sources or ())
    failed_uids = _provider_uids(failed_labels)
    with archive.transaction() as conn:
        run_uid = _begin_run_tx(conn, started_ms)
        by_url: dict[str, str | None] = {}
        accepted_total = rejected_total = 0
        observed_providers: set[str] = set()
        for provider_uid, articles in provider_articles:
            result = _record_batch_tx(conn, run_uid, provider_uid, list(articles), started_ms)
            by_url.update(result.by_url)
            accepted_total += result.accepted
            rejected_total += result.rejected
            observed_providers.add(provider_uid)

        # One source_health row per provider in this run: failed (cycle-level fetch
        # failure for that provider, possibly with zero articles), ok, or empty.
        health_states = {p: ('failed' if p in failed_uids else ('ok' if a else 'empty'))
                         for p, a in provider_articles} | dict.fromkeys(failed_uids - observed_providers, 'failed')
        for uid in sorted(health_states):
            st = health_states[uid]
            conn.execute(
                "INSERT INTO source_health (run_uid, provider_uid, state, error_code, observed_at)"
                ' VALUES (?,?,?,?,?)'
                " ON CONFLICT(run_uid, provider_uid) DO UPDATE SET state=excluded.state,"
                ' error_code=excluded.error_code, observed_at=excluded.observed_at',
                (run_uid, uid, st, None if st != 'failed' else 'source_failure', started_ms))

        for event_id, semantic in revision_items or ():
            _link_event_revision_tx(conn, run_uid, int(event_id), semantic, by_url)

        payload_bytes = _payload_bytes(snapshot_payload)
        validate_snapshot(json.loads(payload_bytes.decode('utf-8')))
        sequence_row = conn.execute(
            'SELECT next_value FROM identity_counters WHERE name=?', ('publication_sequence',)).fetchone()
        seq = 1 if sequence_row is None else int(sequence_row['next_value'])
        _ensure_counter_tx(conn, 'publication_sequence', seq + 1)
        # Reconcile the legacy event-ID high-water with what this projection carries.
        next_event_id = snapshot_payload.get('manifest', {}).get(
            'nextEventId', max((e['id'] for e in snapshot_payload.get('events', [])), default=0) + 1)
        _ensure_counter_tx(conn, 'event_id', int(next_event_id))

        publication_uid = _new_uid()
        conn.execute(
            'INSERT INTO publication_jobs (publication_uid, sequence, run_uid, payload_hash,'
            " payload_or_reference, state, attempts, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (publication_uid, seq, run_uid, sha256_hex(payload_bytes),
             json.dumps(snapshot_payload, ensure_ascii=False, sort_keys=True), 'pending', 0, _now_ms()))

        manifest = snapshot_payload['manifest']
        outcome = {'ok': 'ok', 'degraded': 'degraded'}.get(manifest.get('health', {}).get('status'), 'error')
        last_success = manifest.get('lastSync') if outcome in ('ok', 'degraded') else None
        _finish_run_tx(conn, run_uid, outcome,
                       {'accepted': accepted_total, 'rejected': rejected_total, **manifest.get('counts', {})},
                       last_success)
    return {'publication_uid': publication_uid, 'sequence': seq}


# -- replay ------------------------------------------------------------------

def pending_jobs(archive: Archive) -> list[dict]:
    rows = archive.conn.execute(
        "SELECT * FROM publication_jobs WHERE state='pending' ORDER BY sequence ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def _acknowledge(conn, publication_uid: str) -> None:
    conn.execute(
        'UPDATE publication_jobs SET state=\'published\', attempts=attempts+1,'
        " published_at=? WHERE publication_uid=?", (_now_ms(), publication_uid))


def replay(archive: Archive, out_dir: Path) -> list[int]:
    """Publish pending jobs in strictly increasing sequence order.

    Per job: hash-verify the stored payload against its recorded sha256 (a mismatch is
    corruption — operator-visible error, never silently repaired), record an attempt
    BEFORE writing so a crashed write stays observable on retry, then write snapshot.json
    and repair/replace legacy mirrors events.json + manifest.json from the SAME committed
    bytes (temp file + fsync + atomic replace + directory sync). Acknowledge in a small
    separate transaction only after all three files are on disk. A repeated job rewrites
    identical bytes — harmless per spec §5.2. Returns sequences written this call, ascending.

    Never fetches sources and never writes out-of-order: the single writer holds
    .ingest.lock (runner) and jobs replay in committed sequence order."""
    out_dir = Path(out_dir)
    published: list[int] = []
    from .contracts import validate_snapshot  # local: keep module import light/cycle-free
    for job in pending_jobs(archive):
        raw = json.loads(job['payload_or_reference'])
        actual = sha256_hex(_payload_bytes(raw))
        if actual != job['payload_hash']:
            raise PayloadHashMismatch(
                f"publication sequence {job['sequence']}: stored payload hash mismatch; "
                'restore from backup or reconcile via archive admin (1.2.3)')
        validate_snapshot(raw)  # spec §5.2: re-validate the committed schema before any file write
        with archive.conn:  # attempt recorded before the write boundary (spec §5.2 row 2/8)
            archive.conn.execute(
                'UPDATE publication_jobs SET attempts=attempts+1 WHERE publication_uid=?',
                (job['publication_uid'],))
        _write_snapshot_files(out_dir, raw)
        with archive.transaction() as conn:
            _acknowledge(conn, job['publication_uid'])
        published.append(int(job['sequence']))
    return published


def sync_mirrors(archive: Archive, out_dir: Path) -> bool:
    """Repair on-disk snapshot/mirrors from the latest PUBLISHED payload.

    Called at archive-mode startup (and by future admin tooling): if any of the three
    files is missing or diverges in content hash from the newest published job's stored
    bytes, rewrite all three from that committed payload — a crash between file write and
    acknowledgement self-heals without refetching sources. Never restores an older
    snapshot; only forward writes from committed state. Returns True when anything was
    rewritten."""
    out_dir = Path(out_dir)
    row = archive.conn.execute(
        'SELECT * FROM publication_jobs WHERE state=\'published\''
        ' ORDER BY sequence DESC LIMIT 1').fetchone()
    if row is None:
        return False  # nothing committed yet; the first cycle's replay writes the files
    raw = json.loads(row['payload_or_reference'])
    stored_hash = sha256_hex(_payload_bytes(raw))
    needs_rewrite = True
    snap_path = out_dir / 'snapshot.json'
    if snap_path.exists() and (out_dir / 'events.json').exists() and (out_dir / 'manifest.json').exists():
        try:
            on_disk = json.loads(snap_path.read_text(encoding='utf-8'))
            events_on_disk = json.loads((out_dir / 'events.json').read_text(encoding='utf-8'))
            manifest_on_disk = json.loads((out_dir / 'manifest.json').read_text(encoding='utf-8'))
            needs_rewrite = (sha256_hex(_payload_bytes(on_disk)) != stored_hash
                              or events_on_disk != raw['events']
                              or manifest_on_disk != raw['manifest'])
        except (ValueError, OSError):
            needs_rewrite = True  # unparseable/missing mirrors must be repaired from the DB
    if not needs_rewrite:
        return False
    _write_snapshot_files(out_dir, raw)
    return True


def _dir_sync(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_json_atomic(path: Path, payload: Any) -> None:
    """Same atomicity contract as runner._atomic_write (temp+fsync+replace+dir sync)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=f'.{path.name}.', delete=False) as f:
            name = f.name
            json.dump(payload, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, 0o644)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
    _dir_sync(path.parent)


def _write_snapshot_files(out_dir: Path, payload: dict) -> None:
    """Write canonical snapshot.json + legacy mirrors from one committed payload.

    Canonical file first; mirrors are compatibility projections of the SAME bytes'
    content — a crash mid-mirror never compromises the next cycle (mirrors re-derive)."""
    _write_json_atomic(out_dir / 'snapshot.json', payload)
    _write_json_atomic(out_dir / 'events.json', payload['events'])
    _write_json_atomic(out_dir / 'manifest.json', payload['manifest'])
