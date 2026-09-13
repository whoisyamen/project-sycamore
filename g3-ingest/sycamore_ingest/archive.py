"""Durable archive in shadow mode (iteration 1.2.1).

Legacy JSON pipeline remains the authority; this module persists source
observations and event identity/history BEFORE live pruning. Shadow mode is
additive: the runner observes the SAME single fetched batch, and a shadow DB
failure never blocks legacy publication -- it records a gap instead.

INT-001/INT-002 rules implemented here:
- Stable event UID mapping: import_snapshot returns existing mapping on repeat
  import, never new UUIDs; changed titles retain identity.
- Source natural keys: provider UID + provider-native ID, else provider UID +
  canonical source URL (identity.source_key / canonicalize_url).
- Source revisions: UNIQUE(source_uid, content_hash) -- identical re-fetch
  creates an observation, not a duplicate content revision.
- Event revisions: appended only when semantic content hash changes; clock-only
  changes never append a material revision.
- FK enforcement on every connection; migrations are checksummed and applied
  transactionally; editing an applied migration is an error.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import sqlite3
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from . import identity

MIGRATIONS_DIR = Path(__file__).resolve().parent / 'migrations'

# Checked-in provider registry (1.2.1). Extended by migration later archive
# iterations; never an arbitrary display name in the DB.
PROVIDERS: dict[str, dict[str, Any]] = {
    'rss': {'display_name': 'Curated RSS', 'policy_version': 1},
    'gdelt': {'display_name': 'GDELT DOC 2.0', 'policy_version': 1},
}

NORMALIZATION_VERSION = 'rss-v1'


class ArchiveError(RuntimeError):
    """Base for archive failures."""


class MigrationChecksumError(ArchiveError):
    """An already-applied migration's bytes changed."""


class MigrationApplyError(ArchiveError):
    """Migration SQL failed."""


class BootstrapRequired(ArchiveError):
    """Archive-mode state cannot be derived; cutover bootstrap step is missing.

    Raised when a DB holds live-ingest-only history (no committed publication, no
    importable legacy payloads). The operator must run the documented bootstrap:
    `--mode archive --snapshot-only` against the current snapshot directory."""


def _payload_bytes(snapshot: dict) -> bytes:
    """Canonical UTF-8 JSON bytes used for payload_hash (INT-003 §2/§7)."""
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode('utf-8')


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode('utf-8')
    return hashlib.sha256(data).hexdigest()


@dataclasses.dataclass(frozen=True)
class BatchObservation:
    """Outcome of observing one fetched article in shadow mode."""
    url: str
    source_uid: str | None
    source_revision_uid: str | None
    normalization_outcome: str  # accepted | rejected:<reason>
    event: dict | None          # normalized event when accepted, else None


@dataclasses.dataclass(frozen=True)
class BatchResult:
    """Summary of one record_batch call."""
    provider_uid: str
    observations: tuple[BatchObservation, ...]
    accepted: int = 0
    rejected: int = 0

    @property
    def by_url(self) -> dict[str, str | None]:
        """Map article URL -> source revision UID (None when rejected)."""
        return {o.url: o.source_revision_uid for o in self.observations}


def _now_ms() -> int:
    import time
    return int(time.time() * 1000)


def _new_uid() -> str:
    return str(uuid.uuid4())


# Backward-compatible alias for existing call sites in this module.
_uid = _new_uid


def _split_sql(text: str) -> list[str]:
    """Split a migration file into statements, dropping comments and blanks."""
    text = re.sub(r'--[^\n]*', '', text)
    return [s.strip() for s in text.split(';') if s.strip()]


def _checksum_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_ledger(conn: sqlite3.Connection) -> None:
    conn.execute(
        'CREATE TABLE IF NOT EXISTS schema_migrations ('
        ' version INTEGER PRIMARY KEY,'
        ' checksum TEXT NOT NULL,'
        ' applied_at INTEGER NOT NULL)'
    )


def apply_migrations(db_path: Path) -> None:
    """Apply pending migrations transactionally; verify checksums.

    Ledger rows are written by the migration itself; apply_migrations verifies
    the version exists after running and rejects edited applied migrations.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        _write_ledger(conn)
        files = sorted(MIGRATIONS_DIR.glob('*.sql'), key=lambda p: int(p.name.split('_')[0]))
        for path in files:
            version = int(path.name.split('_')[0])
            raw = path.read_bytes()
            checksum = _checksum_bytes(raw)
            row = conn.execute(
                'SELECT checksum FROM schema_migrations WHERE version=?', (version,)
            ).fetchone()
            if row is not None:
                if row['checksum'] != checksum:
                    raise MigrationChecksumError(
                        f'migration {version} checksum changed after apply; refusing drift'
                    )
                continue  # already applied: no-op
            conn.execute('BEGIN')
            try:
                for stmt in _split_sql(raw.decode('utf-8')):
                    if stmt:
                        conn.execute(stmt)
                row = conn.execute(
                    'SELECT checksum FROM schema_migrations WHERE version=?', (version,)
                ).fetchone()
                if row is None:
                    raise MigrationApplyError(
                        f'migration {version} did not register its ledger row'
                    )
                conn.execute(
                    'UPDATE schema_migrations SET checksum=?, applied_at=? WHERE version=?',
                    (checksum, _now_ms(), version),
                )
                conn.execute('COMMIT')
            except Exception:
                conn.execute('ROLLBACK')
                raise
    finally:
        conn.close()


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection with FK enforcement and row access."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA busy_timeout = 5000')
    return conn


class Archive:
    """Repository over the archive SQLite DB. One connection per process.

    All writes go through explicit transactions. FK violations raise
    sqlite3.IntegrityError, which the runner treats as a shadow gap.
    """

    def __init__(self, db_path: Path, *, apply: bool = True):
        self.db_path = Path(db_path)
        if apply:
            apply_migrations(self.db_path)
        self.conn = connect(self.db_path)
        self._ensure_providers()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> 'Archive':
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- providers ---------------------------------------------------------

    def _ensure_providers(self) -> None:
        for uid, info in PROVIDERS.items():
            self.conn.execute(
                'INSERT OR IGNORE INTO providers (provider_uid, display_name, policy_version)'
                ' VALUES (?, ?, ?)',
                (uid, info['display_name'], info['policy_version']),
            )
        self.conn.commit()

    # -- import ------------------------------------------------------------

    def import_snapshot(self, snapshot: dict, import_identity: str) -> dict[int, str]:
        """Import existing v1 snapshot events; return stable numeric-ID->UID map.

        Repeat import with the same identity returns the existing mapping and
        never allocates new UUIDs. Imported event revisions carry an explicit
        missing-history marker (source='legacy_import'); the source-observation
        history before import is unknown.
        """
        mapping: dict[int, str] = {}
        max_id = 0
        with self.conn:
            for event in snapshot['events']:
                legacy_id = int(event['id'])
                max_id = max(max_id, legacy_id)
                row = self.conn.execute(
                    'SELECT event_uid, import_identity FROM events WHERE legacy_id=?',
                    (legacy_id,),
                ).fetchone()
                if row is not None:
                    # Live-ingested events have NULL import_identity and are
                    # compatible with any import stream; a conflicting explicit
                    # identity is an error (two different import batches).
                    if row['import_identity'] is not None and row['import_identity'] != import_identity:
                        raise ArchiveError(
                            f'legacy_id {legacy_id} already imported under a different identity'
                        )
                    mapping[legacy_id] = row['event_uid']
                    continue
                event_uid = _uid()
                self.conn.execute(
                    'INSERT INTO events (event_uid, legacy_id, status, import_identity)'
                    ' VALUES (?, ?, ?, ?)',
                    (event_uid, legacy_id, 'active', import_identity),
                )
                sem = identity.canonical_sha256(
                    {k: event[k] for k in ('id', 't', 'sev', 'title', 'loc', 'lat', 'lon', 'ts', 'sources') if k in event}
                )
                rev = {
                    'revision_uid': _uid(),
                    'event_uid': event_uid,
                    'semantic_hash': sem,
                    'created_at': _now_ms(),
                    'permitted_payload': json.dumps(event, ensure_ascii=False, sort_keys=True),
                    'normalization_version': 'legacy-import',
                    'source': 'legacy_import',
                }
                key = ('revision_uid', 'event_uid', 'semantic_hash', 'created_at',
                       'permitted_payload', 'normalization_version', 'source')
                self.conn.execute(
                    'INSERT INTO event_revisions (' + ','.join(key) + ') VALUES (?,?,?,?,?,?,?)',
                    tuple(rev[k] for k in key),
                )
                self.conn.execute(
                    'UPDATE events SET current_revision_uid=? WHERE event_uid=?',
                    (rev['revision_uid'], event_uid),
                )
                mapping[legacy_id] = event_uid
            # High-water counter: at least max imported ID+1 and manifest value.
            counter = max(max_id + 1, snapshot.get('manifest', {}).get('nextEventId', max_id + 1))
            self._ensure_counter('event_id', max(counter, self._counter('event_id')))
        return mapping

    def _counter(self, name: str) -> int:
        return _counter_tx(self.conn, name)

    def _ensure_counter(self, name: str, value: int) -> None:
        # Join the caller's open transaction when one exists (import_snapshot);
        # otherwise own a small explicit tx. Never nest BEGINs on this connection.
        if self.conn.in_transaction:
            _ensure_counter_tx(self.conn, name, value)
            return
        with self.transaction():
            _ensure_counter_tx(self.conn, name, value)

    def latest_projection(self) -> dict | None:
        """Derive the archive-mode previous state for the next cycle.

        Source of truth, per INT-003 §4 / iteration 1.2.2 bootstrap rule:
          (a) The highest-sequence publication_jobs payload — full v1 snapshot bytes; a PENDING job counts too, so crash recovery never loses committed intent (sync_mirrors/replay forward from it).
          (b) Else, events carrying an import_identity whose CURRENT revision is the FULL legacy-import payload (geo/score/media provenance intact), with a manifest rebuilt per _empty_manifest rules and nextEventId reconciled to max(event IDs)+1 / identity_counters high-water.

        Live-ingest-only revisions are semantic content only (no geo/score) — they can never satisfy rule (b). A DB matching neither raises BootstrapRequired at the runner boundary BEFORE any fetch."""
        row = self.conn.execute(
            "SELECT payload_or_reference FROM publication_jobs"
            ' ORDER BY sequence DESC LIMIT 1').fetchone()
        if row is not None:
            return json.loads(row['payload_or_reference'])

        rows = self.conn.execute("""
            SELECT e.legacy_id, cur.permitted_payload
              FROM events e
             JOIN event_revisions cur ON cur.revision_uid = e.current_revision_uid
             WHERE e.import_identity IS NOT NULL AND e.status='active'""").fetchall()
        if not rows:
            return None
        import copy as _copy
        from .runner import _empty_manifest  # local import avoids a cycle at module load
        events = [json.loads(r['permitted_payload']) for r in rows]
        manifest = _copy.deepcopy(_empty_manifest())
        max_id = max((e['id'] for e in events), default=0) + 1
        counter_row = self.conn.execute(
            "SELECT next_value FROM identity_counters WHERE name='event_id'").fetchone()
        if counter_row is not None:
            manifest['nextEventId'] = max(max_id, int(counter_row['next_value']))
        else:
            manifest['nextEventId'] = max_id
        return {'version': 1, 'events': events, 'manifest': manifest}

    # -- run bookkeeping ---------------------------------------------------

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Explicit BEGIN IMMEDIATE ... COMMIT/ROLLBACK on this Archive's connection.

        Used by publisher.commit_cycle and replay acknowledgement; public methods must
        NOT be called from inside it (they open their own transactions) — use the *_tx
        helpers instead."""
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            yield self.conn
        except Exception:
            self.conn.execute('ROLLBACK')
            raise
        else:
            self.conn.execute('COMMIT')

    def begin_run(self, observed_at: int) -> str:
        """Start a shadow-mode ingest run (own transaction)."""
        with self.transaction() as conn:
            return _begin_run_tx(conn, observed_at)

    def finish_run(self, run_uid: str, outcome: str, counts: dict, last_success: int | None) -> None:
        """Close a shadow-mode ingest run (own transaction)."""
        with self.transaction() as conn:
            _finish_run_tx(conn, run_uid, outcome, counts, last_success)

    def record_batch(self, run_uid: str, provider_uid: str, articles: list[dict],
                     observed_at: int) -> BatchResult:
        """Store source records/revisions/observations for one fetched batch.

        Observations are recorded once per (run, source, revision); replaying the same
        run/batch is a no-op thanks to the PRIMARY KEY. Normalization outcome is computed
        per article: accepted events are returned; rejected articles (invalid URL, no
        geocode, non-English, no topic) are retained as observations with an explicit
        outcome -- never fabricated v1 markers. This public method wraps the same core
        used inside archive-mode commit transactions (_record_batch_tx)."""
        self._ensure_providers()
        with self.transaction() as conn:
            return _record_batch_tx(conn, run_uid, provider_uid, articles, observed_at)

    # -- event revisions ----------------------------------------------------

    def event_uid_for(self, legacy_id: int, import_identity: str | None = None) -> str:
        row = self.conn.execute(
            'SELECT event_uid FROM events WHERE legacy_id=?', (legacy_id,)
        ).fetchone()
        if row is not None:
            return row['event_uid']
        event_uid = _uid()
        with self.conn:
            self.conn.execute(
                'INSERT INTO events (event_uid, legacy_id, status, import_identity)'
                ' VALUES (?,?,?,?)',
                (event_uid, legacy_id, 'active', import_identity),
            )
        return event_uid

    def record_event_revision(self, legacy_id: int, normalized_content: dict,
                              source_revision_uids: list[str],
                              observed_at: int) -> tuple[str, bool]:
        """Append an event revision only if semantic content changed.

        Returns (event_uid, appended). Clock-only changes (ingestedAt, score
        freshness) must be excluded by the caller from normalized_content; the
        semantic hash is computed over exactly what is passed.
        """
        event_uid = self.event_uid_for(legacy_id)
        sem = identity.canonical_sha256(normalized_content)
        with self.conn:
            row = self.conn.execute(
                'SELECT revision_uid FROM event_revisions WHERE event_uid=? AND semantic_hash=?',
                (event_uid, sem),
            ).fetchone()
            if row is not None:
                return event_uid, False
            revision_uid = _uid()
            payload = json.dumps(
                {**normalized_content, 'id': legacy_id}, ensure_ascii=False, sort_keys=True
            )
            self.conn.execute(
                'INSERT INTO event_revisions (revision_uid, event_uid, semantic_hash,'
                ' created_at, permitted_payload, normalization_version, source)'
                ' VALUES (?,?,?,?,?,?,?)',
                (revision_uid, event_uid, sem, observed_at, payload,
                 NORMALIZATION_VERSION, 'ingest'),
            )
            for src in source_revision_uids:
                self.conn.execute(
                    'INSERT OR IGNORE INTO event_evidence (event_revision_uid,'
                    ' source_revision_uid, role) VALUES (?,?,?)',
                    (revision_uid, src, 'evidence'),
                )
            self.conn.execute(
                'UPDATE events SET current_revision_uid=? WHERE event_uid=?',
                (revision_uid, event_uid),
            )
        return event_uid, True

    # -- comparison and gaps ----------------------------------------------

    def compare_projection(self, legacy_snapshot: dict, candidate_snapshot: dict) -> list[str]:
        """Compare two v1 projections with fixed clocks; emit differences.

        Uses stored timestamps only for ordering diagnostics; does not claim
        deployed freshness. Guarantees the shadow path never changes public
        behavior (legacy value wins on any difference).
        """
        diffs: list[str] = []
        if legacy_snapshot.get('version') != candidate_snapshot.get('version'):
            diffs.append('version differs')
        le = legacy_snapshot.get('events', [])
        ce = candidate_snapshot.get('events', [])
        lmap = {e['id']: e for e in le}
        cmap = {e['id']: e for e in ce}
        if set(lmap) != set(cmap):
            diffs.append(f"event id sets differ: only_legacy={sorted(set(lmap)-set(cmap))}, only_candidate={sorted(set(cmap)-set(lmap))}")
        for eid in sorted(set(lmap) & set(cmap)):
            l, c = lmap[eid], cmap[eid]
            for field in ('title', 'loc', 'lat', 'lon', 'sev', 't'):
                if l.get(field) != c.get(field):
                    diffs.append(f'event {eid} {field} differs')
            if l.get('sources') != c.get('sources'):
                diffs.append(f'event {eid} sources differ')
        for key in ('counts', 'health'):
            if legacy_snapshot.get('manifest', {}).get(key) != candidate_snapshot.get('manifest', {}).get(key):
                diffs.append(f'manifest {key} differs')
        return diffs

    def record_shadow_gap(self, run_uid: str, reason: str) -> None:
        """Persist a gap marker so missing coverage stays visible to operators.

        A later successful cycle updates the gap row's state to 'reconciled'
        but never labels the archive as continuous history.
        """
        with self.conn:
            self.conn.execute(
                'INSERT INTO shadow_gaps (run_uid, reason, seen_at, state) VALUES (?,?,?,?)'
                ' ON CONFLICT(run_uid) DO UPDATE SET reason=excluded.reason,'
                ' seen_at=excluded.seen_at, state=excluded.state',
                (run_uid, reason, _now_ms(), 'open'),
            )

    def gap_state(self, run_uid: str) -> str | None:
        row = self.conn.execute(
            'SELECT state FROM shadow_gaps WHERE run_uid=?', (run_uid,)
        ).fetchone()
        return row['state'] if row else None


def _parse_seendate_ms(value: Any) -> int | None:
    """Parse GDELT-style seendate to ms; return None when unavailable."""
    if not value:
        return None
    try:
        import datetime as _dt
        from datetime import timezone
        s = str(value).strip()
        if 'T' in s:
            return int(_dt.datetime.strptime(s[:19], '%Y%m%dT%H%M%S')
                       .replace(tzinfo=timezone.utc).timestamp() * 1000)
        return int(_dt.datetime.strptime(s[:8], '%Y%m%d')
                   .replace(tzinfo=timezone.utc).timestamp() * 1000)
    except (ValueError, TypeError):
        return None


def _normalize_probe(article: dict) -> dict | None:
    """Best-effort normalization outcome probe (no side effects, no network)."""
    from . import normalizer
    return normalizer.normalize(article, 0)


# -- transactional cores -------------------------------------------------------
# Shared by the shadow public methods and archive-mode commit transactions. Each
# function operates on a connection that ALREADY has an open explicit transaction;
# it performs no BEGIN/COMMIT of its own (the caller's context manager owns the tx).

def _begin_run_tx(conn: sqlite3.Connection, observed_at: int) -> str:
    run_uid = _new_uid()
    conn.execute(
        'INSERT INTO ingest_runs (run_uid, started_at, outcome, counts)'
        ' VALUES (?, ?, ?, ?)',
        (run_uid, observed_at, 'running', '{}'),
    )
    return run_uid


def _finish_run_tx(conn: sqlite3.Connection, run_uid: str, outcome: str,
                   counts: dict, last_success: int | None) -> None:
    conn.execute(
        'UPDATE ingest_runs SET finished_at=?, outcome=?, counts=?, last_success=?'
        ' WHERE run_uid=?',
        (_now_ms(), outcome, json.dumps(counts, sort_keys=True), last_success, run_uid),
    )


def _upsert_health(conn, run_uid: str, provider_uid: str, state: str, error_code: str | None,
                   observed_at: int) -> None:
    conn.execute(
        "INSERT INTO source_health (run_uid, provider_uid, state, error_code, observed_at)"
        ' VALUES (?,?,?,?,?)'
        " ON CONFLICT(run_uid, provider_uid) DO UPDATE SET state=excluded.state,"
        ' error_code=excluded.error_code, observed_at=excluded.observed_at',
        (run_uid, provider_uid, state, error_code, observed_at),
    )


def _record_batch_tx(conn: sqlite3.Connection, run_uid: str, provider_uid: str,
                     articles: list[dict], observed_at: int) -> BatchResult:
    """Source records/revisions/observations + this provider's source_health row core.

    Health state here reflects the OBSERVED batch (ok when any article fetched, empty
    otherwise); archive-mode commits may overwrite it afterwards with 'failed' for a
    cycle-level fetch failure on that same connection."""
    observations: list[BatchObservation] = []
    accepted = 0
    rejected = 0
    for article in articles:
        url = (article.get('url') or '').strip()
        try:
            canonical = identity.canonicalize_url(url)
            natural = identity.source_key(provider_uid, source_url=url)
        except ValueError:
            observations.append(BatchObservation(url, None, None,
                                                 'rejected:invalid_url', None))
            rejected += 1
            continue
        row = conn.execute(
            'SELECT source_uid FROM source_records WHERE natural_key=?', (natural,)
        ).fetchone()
        if row is None:
            source_uid = _new_uid()
            conn.execute(
                'INSERT INTO source_records (source_uid, provider_uid, natural_key,'
                ' original_url, canonical_url) VALUES (?,?,?,?,?)',
                (source_uid, provider_uid, natural, url, canonical),
            )
        else:
            source_uid = row['source_uid']

        # Semantic content: title + lede + URL (excluding clocks).
        content = {
            'title': (article.get('title') or '').strip(),
            'summary': (article.get('_rss_description') or article.get('summary') or '').strip()[:600],
            'url': canonical,
        }
        content_hash = identity.canonical_sha256(content)
        rev_row = conn.execute(
            'SELECT revision_uid FROM source_revisions'
            ' WHERE source_uid=? AND content_hash=?',
            (source_uid, content_hash),
        ).fetchone()
        if rev_row is None:
            revision_uid = _new_uid()
            conn.execute(
                'INSERT INTO source_revisions (revision_uid, source_uid, content_hash,'
                ' published_at, observed_at, allowed_payload) VALUES (?,?,?,?,?,?)',
                (revision_uid, source_uid, content_hash,
                 _parse_seendate_ms(article.get('seendate')),
                 observed_at,
                 json.dumps(content, ensure_ascii=False, sort_keys=True)),
            )
        else:
            revision_uid = rev_row['revision_uid']

        outcome = 'accepted'
        event = None
        try:
            event = _normalize_probe(article)
        except (TypeError, ValueError):
            outcome = 'rejected:normalization_error'
        if event is None:
            outcome = 'rejected:no_map_event'

        conn.execute(
            'INSERT OR IGNORE INTO source_observations (run_uid, source_uid,'
            ' revision_uid, normalization_outcome, observed_at) VALUES (?,?,?,?,?)',
            (run_uid, source_uid, revision_uid, outcome, observed_at),
        )
        observations.append(BatchObservation(url, source_uid, revision_uid, outcome, event))
        if event is not None:
            accepted += 1
        else:
            rejected += 1
    state = 'ok' if articles else 'empty'
    _upsert_health(conn, run_uid, provider_uid, state, None, observed_at)
    return BatchResult(provider_uid, tuple(observations), accepted, rejected)


def _ensure_counter_tx(conn: sqlite3.Connection, name: str, value: int) -> None:
    conn.execute(
        'INSERT INTO identity_counters (name, next_value) VALUES (?, ?)'
        ' ON CONFLICT(name) DO UPDATE SET next_value=MAX(next_value, excluded.next_value)',
        (name, value),
    )


def _counter_tx(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute(
        'SELECT next_value FROM identity_counters WHERE name=?', (name,)
    ).fetchone()
    return row['next_value'] if row else 1


def _link_event_revision_tx(conn: sqlite3.Connection, run_uid: str, legacy_id: int,
                            semantic_content: dict, by_url: dict[str, str | None]) -> tuple[str, bool]:
    """Append an event revision (if the semantic hash changed) and link evidence to
    this run's observed source revisions for each of its URLs.

    Returns (event_uid, appended). Evidence links only cover sources observed in THIS
    batch — pre-existing legacy rows cite earlier history already stored at import /
    previous-commit time; a URL never seen by the archive gets no fabricated link."""
    event_row = conn.execute(
        'SELECT event_uid FROM events WHERE legacy_id=?', (legacy_id,)
    ).fetchone()
    if event_row is None:
        event_uid = _new_uid()
        conn.execute(
            'INSERT INTO events (event_uid, legacy_id, status) VALUES (?, ?, ?)',
            (event_uid, legacy_id, 'active'),
        )
    else:
        event_uid = event_row['event_uid']
    sem = identity.canonical_sha256(semantic_content)
    row = conn.execute(
        'SELECT revision_uid FROM event_revisions WHERE event_uid=? AND semantic_hash=?',
        (event_uid, sem),
    ).fetchone()
    if row is not None:
        return event_uid, False
    revision_uid = _new_uid()
    payload = json.dumps({**semantic_content, 'id': legacy_id}, ensure_ascii=False, sort_keys=True)
    conn.execute(
        'INSERT INTO event_revisions (revision_uid, event_uid, semantic_hash,'
        ' created_at, permitted_payload, normalization_version, source)'
        " VALUES (?,?,?,?,?,?,?)",
        (revision_uid, event_uid, sem, _now_ms(), payload, NORMALIZATION_VERSION, 'ingest'),
    )
    for url in semantic_content.get('sources', []):  # type: ignore[union-attr]
        src = by_url.get(url)
        if src is None:
            continue
        conn.execute(
            'INSERT OR IGNORE INTO event_evidence (event_revision_uid,'
            ' source_revision_uid, role) VALUES (?,?,?)',
            (revision_uid, src, 'evidence'),
        )
    conn.execute(
        'UPDATE events SET current_revision_uid=? WHERE event_uid=?',
        (revision_uid, event_uid),
    )
    return event_uid, True


def archive_available(db_path: Path) -> bool:
    """Cheap availability probe used before any fetch in shadow mode."""
    try:
        with connect(db_path) as conn:
            conn.execute('SELECT 1').fetchone()
        return True
    except Exception:
        return False


if __name__ == '__main__':
    print('archive.py requires explicit db path; use tools/archive_admin.py (1.2.3).', file=sys.stderr)