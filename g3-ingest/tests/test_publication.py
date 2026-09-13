"""Iteration 1.2.2: archive-mode publication (publisher) + ordered replay tests.

Covers every spec §5.2 failure-matrix row with injected-failure fixtures plus the
register-card acceptance items (no lost committed events, no ID reuse, mirror repair),
archive config guardrails and migration replay/checksum behavior. All fixtures use temp
dirs only; rss_client/gdelt/media/osint are mocked — zero external requests by construction.

Authority model under test (INT-003): the SQLite DB is authoritative for v1 in archive
mode via replayable publication_jobs; files on disk are a forward-only, hash-verified
projection of committed payloads.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sycamore_ingest import runner, rss_client, archive, publisher
from sycamore_ingest.archive import Archive, MigrationChecksumError
from sycamore_ingest.normalizer import normalize

ARTICLE = {
    'title': 'Major ransomware hits regional power grid in Frankfurt',
    'url': 'https://alpha.example/story',
    'domain': 'alpha.example',
    'language': 'English',
    'tone': -6,
    'seendate': '20260903T120000Z',
    'location': {'fullName': 'Frankfurt', 'countryCode': 'DE'},
    'lat': 50.11,
    'long': 8.68,
    '_rss_topic': 'cyber',
    '_rss_source': 'AlphaFeed',
    '_rss_description': 'Regional power grid in Frankfurt disrupted.',
}


def make_article(n: int) -> dict:
    return {**ARTICLE,
            'title': f'Ransomware wave number {n} disrupts Frankfurt region',
            'url': f'https://alpha.example/story-{n}',
            '_rss_description': f'Outage variant {n}.', }


def batch(success=1, failed=()):
    result = rss_client.FeedBatch()
    result.succeeded = success
    result.failed = list(failed)
    return result


class PublicationTestCase(unittest.TestCase):
    """Shared scaffolding: temp out dir + archive db; osint layers mocked off."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        add_cleanup_dir = getattr(self, 'addCleanup', None)  # unittest >=3.8 always has it
        if add_cleanup_dir is not None:
            self.addCleanup(shutil.rmtree, self.temp.name, ignore_errors=True)
        else:
            self.addTearDown(lambda: shutil.rmtree(self.temp.name, ignore_errors=True))
        root = Path(self.temp.name)
        self.out = root / 'out'
        self.db = root / 'archive.db'
        m = patch.object(runner, '_osint_cycle', return_value=[])
        m.start()
        if add_cleanup_dir is not None:
            self.addCleanup(m.stop)

    def legacy_out(self, articles):
        """Produce a real legacy out dir (snapshot.json + mirrors) for bootstrap sources."""
        with patch.object(rss_client, 'fetch_all', return_value=batch()), \
             patch.object(rss_client, 'to_articles', return_value=list(articles)):
            runner.run(self.out)  # default mode='legacy'

    def archive_cycle(self, articles, result=None):
        """One live archive-mode cycle (commit + replay inside run)."""
        with patch.object(rss_client, 'fetch_all', side_effect=result if isinstance(result, Exception) else None,
                          return_value=batch()) if not isinstance(result, Exception) \
                else patch.object(rss_client, 'fetch_all', side_effect=lambda: (_ for _ in ()).throw(result)), \
             patch.object(rss_client, 'to_articles', return_value=list(articles)):
            return runner.run(self.out, mode='archive', archive_path=self.db)

    def snapshot_bytes(self):
        p = self.out / 'snapshot.json'
        return None if not p.exists() else p.read_bytes()

    def jobs(self):
        with Archive(self.db) as a:
            rows = a.conn.execute(
                "SELECT publication_uid, sequence, state, attempts FROM publication_jobs"
                ' ORDER BY sequence ASC').fetchall()
        return [dict(r) for r in rows]


class ConfigGuardrailTests(unittest.TestCase):
    def test_archive_requires_explicit_path(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'out'
            with self.assertRaises(ValueError):
                runner.run(out, mode='archive', archive_path=None)

    def test_archive_rejects_public_data_path(self):
        # The guard checks against the actual repo layout (g3-astro/public and dist).
        bad = runner.DEFAULT_OUT / 'archive.db'
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'out'
            with self.assertRaises(ValueError):
                runner.run(out, mode='archive', archive_path=bad)

    def test_invalid_mode_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'out'
            with self.assertRaises(ValueError):
                runner.run(out, mode='archiv')


class MigrationReplayTests(unittest.TestCase):
    """002 applies once; second apply is a no-op; mutated applied bytes are rejected."""

    def test_apply_twice_noop_and_checksum_drift_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / 'm.db'
            # Apply against the REAL migrations dir first (001 + 002).
            archive.apply_migrations(db)
            tables_before = self._tables(db)
            ledger_before = self._ledger(db)
            # Second apply: no-op.
            archive.apply_migrations(db)
            self.assertEqual(self._tables(db), tables_before)
            self.assertEqual(self._ledger(db), ledger_before)

            # Now replay with a COPIED migrations dir so the repo files are never touched.
            mig = root / 'migs'
            shutil.copytree(archive.MIGRATIONS_DIR, mig)
            db2 = root / 'drift.db'
            with patch.object(archive, 'MIGRATIONS_DIR', mig):
                archive.apply_migrations(db2)
                self.assertEqual(self._ledger(db2), ledger_before)  # identical checksums
                (mig / '002_publication.sql').write_text((mig / '002_publication.sql').read_text() + '\n-- drift\n')
                with self.assertRaises(MigrationChecksumError):
                    archive.apply_migrations(db2)

    @staticmethod
    def _tables(db_path: Path):
        conn = sqlite3.connect(str(db_path))  # noqa — test-only read probe
        try:
            return {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            conn.close()

    @staticmethod
    def _ledger(db_path: Path):
        conn = sqlite3.connect(str(db_path))  # noqa — test-only read probe
        try:
            return {r[0]: r[1] for r in conn.execute(
                'SELECT version, checksum FROM schema_migrations ORDER BY version')}
        finally:
            conn.close()


import sqlite3  # used by MigrationReplayTests probes (kept at bottom to match import style above)


class CommitAtomicityTests(PublicationTestCase):
    """Spec §5.2 row 1 — before DB commit: full rollback, previous snapshot byte-identical."""

    def test_mid_transaction_failure_rolls_back_everything(self):
        self.legacy_out([make_article(1)])
        runner.run(self.out, mode='archive', archive_path=self.db, snapshot_only=True)  # bootstrap job #1
        before = self.snapshot_bytes()
        with Archive(self.db) as a:
            rows_before = {t: a.conn.execute(f'SELECT COUNT(*) c FROM {t}').fetchone()['c'] for t in (
                'source_records', 'source_observations', 'event_revisions', 'ingest_runs')}

        # Inject failure INSIDE the commit transaction after some writes happened
        # (observations recorded, then event-revision linking raises).
        def boom(conn, run_uid, legacy_id, semantic_content, by_url):
            raise RuntimeError('injected mid-transaction')

        with patch.object(publisher, '_link_event_revision_tx', side_effect=boom), \
             self.assertRaises(RuntimeError) as ctx:
            self.archive_cycle([make_article(2)])
        self.assertIn('injected mid-transaction', str(ctx.exception))

        # Full rollback: zero new rows of any kind; snapshot bytes untouched.
        with Archive(self.db) as a:
            rows_after = {t: a.conn.execute(f'SELECT COUNT(*) c FROM {t}').fetchone()['c'] for t in (
                'source_records', 'source_observations', 'event_revisions', 'ingest_runs')}
        self.assertEqual(rows_before, rows_after)
        jobs = self.jobs()
        self.assertEqual(len(jobs), 1, 'no publication row may survive a rolled-back commit')
        self.assertEqual(before, self.snapshot_bytes(), 'last-good snapshot untouched by the rollback')


class CrashBoundaryTests(PublicationTestCase):
    """Spec §5.2 rows 2/3/8 — failures between DB commit and acknowledgement."""

    def test_commit_then_file_write_failure_stays_pending_and_replays_without_fetch(self):
        # Row 2: after DB commit, before file replace.
        self.legacy_out([make_article(1)])
        runner.run(self.out, mode='archive', archive_path=self.db, snapshot_only=True)
        first = self.snapshot_bytes()

        def fail_write(out_dir, payload):
            raise OSError('injected: write failure after commit')

        with patch.object(publisher, '_write_snapshot_files', side_effect=fail_write), \
             self.assertRaises(OSError):
            self.archive_cycle([make_article(2)])  # commits job #2; replay crashes on the file boundary

        jobs = self.jobs()
        self.assertEqual(jobs[1]['state'], 'pending')
        self.assertEqual(jobs[1]['attempts'], 1, 'attempt recorded before the write (crash-observable)')
        self.assertEqual(first, self.snapshot_bytes(), 'last-good snapshot untouched by the failed replay')

        # Re-running replay publishes WITHOUT any provider fetch.
        with Archive(self.db) as a:
            published = publisher.replay(a, self.out)
        self.assertEqual(published, [2])
        jobs = self.jobs()
        self.assertEqual(jobs[1]['state'], 'published')
        snap = json.loads((self.out / 'snapshot.json').read_text())
        urls = {u for e in snap['events'] for u in e['sources']}
        self.assertIn('https://alpha.example/story-2', urls)

    def test_file_written_before_ack_failure_is_harmless_on_repeat(self):
        # Row 3: snapshot replaced, before acknowledgement — repeating the job is harmless.
        self.legacy_out([make_article(1)])
        runner.run(self.out, mode='archive', archive_path=self.db, snapshot_only=True)

        def fail_ack(conn, publication_uid):
            raise OSError('injected: ack failure after file writes')

        with patch.object(publisher, '_acknowledge', side_effect=fail_ack), \
             self.assertRaises(OSError):
            self.archive_cycle([make_article(2)])  # job #2 committed; files written; ack crashed

        on_disk_after_crash = (self.out / 'snapshot.json').read_bytes()
        jobs = self.jobs()
        self.assertEqual(jobs[1]['state'], 'pending')
        stored_hash = None
        with Archive(self.db) as a:
            row = a.conn.execute(
                "SELECT payload_or_reference, payload_hash FROM publication_jobs WHERE sequence=2").fetchone()
            import hashlib
            raw = json.loads(row['payload_or_reference'])
            self.assertEqual(hashlib.sha256(publisher._payload_bytes(raw)).hexdigest(), row['payload_hash'],
                             'on-disk file must hash-verify against the stored payload_hash')

        with Archive(self.db) as a:  # repeat the same job — harmless, identical bytes
            published = publisher.replay(a, self.out)
        self.assertEqual(published, [2])
        self.assertGreaterEqual(jobs and len(self.jobs()), 2)
        self.assertEqual((self.out / 'snapshot.json').read_bytes(), on_disk_after_crash,
                          'repeating the job rewrites identical bytes')
        final = self.jobs()
        self.assertEqual(final[1]['state'], 'published')

    def test_disk_full_mid_publish_keeps_last_good_and_is_retryable(self):
        # Row 8: _write_json_atomic raises OSError on first attempt only.
        self.legacy_out([make_article(1)])
        runner.run(self.out, mode='archive', archive_path=self.db, snapshot_only=True)
        last_good = (self.out / 'snapshot.json').read_bytes()

        real_write_json = publisher._write_json_atomic
        state = {'failed': False}

        def flaky(path, payload):
            if not state['failed']:
                state['failed'] = True
                raise OSError('injected: ENOSPC')
            return real_write_json(path, payload)

        with patch.object(publisher, '_write_json_atomic', side_effect=flaky), \
             self.assertRaises(OSError):
            self.archive_cycle([make_article(2)])  # job #2 committed; first file write fails atomically

        self.assertEqual((self.out / 'snapshot.json').read_bytes(), last_good,
                          'atomic replace: last-good snapshot byte-for-byte untouched')
        jobs = self.jobs()
        self.assertEqual(jobs[1]['state'], 'pending')
        with Archive(self.db) as a:  # retry after unpatching (disk space restored)
            published = publisher.replay(a, self.out)
        self.assertEqual(published, [2])
        snap = json.loads((self.out / 'snapshot.json').read_text())
        urls = {u for e in snap['events'] for u in e['sources']}
        self.assertIn('https://alpha.example/story-2', urls)


class MirrorRepairTests(PublicationTestCase):
    """Spec §5.2 row 4 — mirrors diverge/missing: rewritten from committed payload, never regressed."""

    def test_deleted_mirrors_repaired_from_committed_payload(self):
        self.legacy_out([make_article(1)])
        runner.run(self.out, mode='archive', archive_path=self.db, snapshot_only=True)
        self.archive_cycle([make_article(2), make_article(3)])
        snap = json.loads((self.out / 'snapshot.json').read_text())

        (self.out / 'events.json').unlink()
        (self.out / 'manifest.json').unlink()
        with Archive(self.db) as a:
            rewritten = publisher.sync_mirrors(a, self.out)
        self.assertTrue(rewritten)
        events_on_disk = json.loads((self.out / 'events.json').read_text())
        manifest_on_disk = json.loads((self.out / 'manifest.json').read_text())
        self.assertEqual(events_on_disk, snap['events'])
        self.assertEqual(manifest_on_disk, snap['manifest'])

    def test_stale_published_payload_on_disk_healed_forward_never_regressed(self):
        # Row-4 variant: corruption/crash leaves an OLDER published payload on disk while the DB holds a newer
        # PUBLISHED job; sync_mirrors must heal forward from the newest committed state — never rewrite older bytes.
        self.legacy_out([make_article(1)])
        runner.run(self.out, mode='archive', archive_path=self.db, snapshot_only=True)  # job #1 published (bootstrap)
        self.archive_cycle([make_article(2), make_article(3)])                          # job #2 published

        with Archive(self.db) as a:
            payloads = {r['sequence']: json.loads(r['payload_or_reference']) for r in a.conn.execute(
                'SELECT sequence, payload_or_reference FROM publication_jobs'
                " WHERE state='published'")}
        self.assertEqual(set(payloads), {1, 2})

        # Simulate the corrupted/older on-disk state: rewrite all three files from job #1's committed bytes.
        stale = payloads[1]
        for name, part in (('snapshot.json', None), ('events.json', 'events'), ('manifest.json', 'manifest')):
            data = stale if part is None else stale[part]
            with open(self.out / name, 'w', encoding='utf-8') as f:  # noqa: SIM115 — explicit close for the fixture
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write('\n')
        self.assertNotIn('https://alpha.example/story-3', (self.out / 'events.json').read_text(),
                         'precondition: on-disk state is stale relative to job #2')

        with Archive(self.db) as a:
            rewritten = publisher.sync_mirrors(a, self.out)
        self.assertTrue(rewritten)
        healed_snap = json.loads((self.out / 'snapshot.json').read_text())
        events_on_disk = json.loads((self.out / 'events.json').read_text())
        manifest_on_disk = json.loads((self.out / 'manifest.json').read_text())
        newest = payloads[2]  # highest-sequence PUBLISHED payload — the only legal repair source here
        self.assertEqual(healed_snap, newest, 'canonical snapshot healed to the NEWEST published payload')
        self.assertEqual(events_on_disk, newest['events'])
        self.assertEqual(manifest_on_disk, newest['manifest'])
        urls = {u for e in events_on_disk for u in e.get('sources', [])}
        self.assertIn('https://alpha.example/story-3', urls)

    def test_divergent_mirror_content_repaired(self):
        self.legacy_out([make_article(1)])
        runner.run(self.out, mode='archive', archive_path=self.db, snapshot_only=True)
        self.archive_cycle([make_article(2)])
        # Tamper with the mirror only (content diverges from committed payload).
        tampered = json.loads((self.out / 'events.json').read_text()) + [{'id': 999}]
        (self.out / 'events.json').write_text(json.dumps(tampered))
        with Archive(self.db) as a:
            rewritten = publisher.sync_mirrors(a, self.out)
        self.assertTrue(rewritten)
        snap = json.loads((self.out / 'snapshot.json').read_text())
        events_on_disk = json.loads((self.out / 'events.json').read_text())
        self.assertEqual(events_on_disk, snap['events'], 'mirror restored from committed payload')


class OrderedReplayTests(PublicationTestCase):
    """Spec §5.2 row 5 — multiple pending jobs replay in strictly increasing sequence order."""

    def test_two_suppressed_commits_replay_in_committed_order(self):
        # Row 5: two cycles commit while file publication is suppressed (crash-equivalent), leaving pending jobs;
        # one subsequent replay must write them in committed order and the final file equals the highest payload.
        self.legacy_out([make_article(1)])
        runner.run(self.out, mode='archive', archive_path=self.db, snapshot_only=True)  # job #1 published (bootstrap)

        with patch.object(publisher, 'replay', side_effect=lambda *a, **k: []):
            self.archive_cycle([make_article(2)])   # commits job #2; file publication suppressed
            self.archive_cycle([make_article(3)])   # previous state came from the committed DB projection (job #2), not disk

        with Archive(self.db) as a:
            seqs = [r['sequence'] for r in a.conn.execute(
                "SELECT sequence FROM publication_jobs ORDER BY sequence")]
            pending_states = {r['sequence']: r['state'] for r in a.conn.execute(
                'SELECT sequence, state FROM publication_jobs')}
        self.assertEqual(seqs, [1, 2, 3], 'two suppressed cycles committed while replay was off')
        self.assertEqual(pending_states[2], 'pending', 'suppressed job stays pending and retryable')

        # Disk is still the bootstrap bytes — nothing may have been published out of order.
        with Archive(self.db) as a:
            boot_payload = json.loads(a.conn.execute(
                "SELECT payload_or_reference FROM publication_jobs WHERE sequence=1").fetchone()['payload_or_reference'])
        self.assertEqual(json.loads((self.out / 'snapshot.json').read_text()), boot_payload,
                         'no file write may happen while replay is suppressed')

        written: list[dict] = []
        real_write_files = publisher._write_snapshot_files

        def spy(out_dir, payload):
            written.append(payload)
            return real_write_files(out_dir, payload)

        with patch.object(publisher, '_write_snapshot_files', side_effect=spy), \
             Archive(self.db) as a:
            published = publisher.replay(a, self.out)
        self.assertEqual(published, [2, 3], 'replay walks pending jobs in strictly increasing sequence order')
        self.assertEqual(len(written), 2, 'writer saw exactly the two committed payloads, in order')

        urls_0 = {u for e in written[0]['events'] for u in e.get('sources', [])}
        urls_1 = {u for e in written[1]['events'] for u in e.get('sources', [])}
        self.assertIn('https://alpha.example/story-2', urls_0)
        self.assertNotIn('https://alpha.example/story-3', urls_0, 'lower-sequence job must not carry later content')
        self.assertEqual(urls_1 - urls_0, {'https://alpha.example/story-3'}, 'content only grows forward')
        # Wall-clock lastSync is monotonic non-decreasing across the ordered writes (the strictly-increasing
        # ordering case with deterministic clocks is covered by test_replay_writes_in_strictly_increasing_sequence_order).
        self.assertGreaterEqual(written[1]['manifest']['lastSync'], written[0]['manifest']['lastSync'])

        final_snap = json.loads((self.out / 'snapshot.json').read_text())
        with Archive(self.db) as a:
            top = a.conn.execute(
                "SELECT payload_or_reference FROM publication_jobs ORDER BY sequence DESC LIMIT 1").fetchone()
        self.assertEqual(final_snap, json.loads(top['payload_or_reference']),
                         'final file equals the highest-sequence committed payload exactly')

    def test_replay_writes_in_strictly_increasing_sequence_order(self):
        # Build two pending jobs with distinguishable payloads via direct commit_cycle calls
        # (replay deliberately NOT invoked between them — the "suppressed" fixture).
        self.legacy_out([make_article(1)])
        runner.run(self.out, mode='archive', archive_path=self.db, snapshot_only=True)

        def payload_for(article_no: int):
            ev = normalize(make_article(article_no), 2 + article_no)
            manifest = {'version': 1, 'lastSync': 5_000_000 * (article_no + 1), 'lastAttempt': 5_000_000 * (article_no + 1),
                        'nextEventId': ev['id'] + 1, 'source': {'name': 'Curated RSS', 'endpoint': rss_client.FEEDS[0]['url']},
                        'counts': runner._counts([ev]), 'health': {'status': 'ok', 'durationMs': 1, 'failedSources': []}}
            return {'version': 1, 'events': [ev], 'manifest': manifest}

        with Archive(self.db) as a:
            publisher.commit_cycle(a, started_ms=runner._now_ms(), provider_articles=[('rss', [])],
                                   failed_sources=[], revision_items=None, snapshot_payload=payload_for(2))
            publisher.commit_cycle(a, started_ms=runner._now_ms() + 10**6, provider_articles=[('rss', [])],
                                   failed_sources=[], revision_items=None, snapshot_payload=payload_for(3))

        written: list[dict] = []
        real_write_files = publisher._write_snapshot_files

        def spy(out_dir, payload):
            written.append(payload)
            return real_write_files(out_dir, payload)

        with patch.object(publisher, '_write_snapshot_files', side_effect=spy), \
             Archive(self.db) as a:
            published = publisher.replay(a, self.out)
        # Bootstrap committed job #1 (published at run time); these two direct commits are sequences 2 and 3.
        self.assertEqual(published, [2, 3], 'pending jobs replay in committed sequence order')
        syncs = [p['manifest']['lastSync'] for p in written]
        self.assertGreater(syncs[-1], syncs[0], 'writer saw strictly increasing lastSync (committed order)')
        final_snap = json.loads((self.out / 'snapshot.json').read_text())
        with Archive(self.db) as a:
            top = a.conn.execute(
                "SELECT payload_or_reference FROM publication_jobs ORDER BY sequence DESC LIMIT 1").fetchone()
        self.assertEqual(final_snap, json.loads(top['payload_or_reference']),
                         'final file equals the highest-sequence committed payload exactly')


class TotalFailureTests(PublicationTestCase):
    """Spec §5.2 rows 6/7 — total source failure and enrichment (media) failure."""

    def test_total_source_failure_retains_previous_state_in_one_transaction(self):
        # Row 6: fetch_all raises in archive mode. Previous committed events retained; lastSync unchanged,
        # lastAttempt advanced, health error + failedSources recorded; ingest_runs outcome=error in the SAME tx.
        self.legacy_out([make_article(1)])
        runner.run(self.out, mode='archive', archive_path=self.db, snapshot_only=True)  # job #1: bootstrap state

        with Archive(self.db) as a:
            boot = json.loads(a.conn.execute(
                "SELECT payload_or_reference FROM publication_jobs WHERE sequence=1").fetchone()['payload_or_reference'])
        prev_events = boot['events']
        prev_last_sync = boot['manifest']['lastSync']

        fetch_calls = {'n': 0}
        def failing_fetch():
            fetch_calls['n'] += 1
            raise RuntimeError('injected: all feeds down')

        with patch.object(rss_client, 'fetch_all', side_effect=failing_fetch):
            result = runner.run(self.out, mode='archive', archive_path=self.db)
        self.assertEqual(fetch_calls['n'], 1, 'exactly one fetch attempt in the failed cycle')
        jobs = self.jobs()
        self.assertEqual(len(jobs), 2, 'total failure still produces a committed publication (row 6)')

        with Archive(self.db) as a:
            row = a.conn.execute(
                "SELECT payload_or_reference FROM publication_jobs WHERE sequence=2").fetchone()
            run_row = a.conn.execute('SELECT outcome FROM ingest_runs ORDER BY started_at DESC LIMIT 1').fetchone()
            health_rows = a.conn.execute(
                'SELECT provider_uid, state, error_code FROM source_health'
                " WHERE run_uid=(SELECT run_uid FROM publication_jobs WHERE sequence=2)").fetchall()

        payload = json.loads(row['payload_or_reference'])
        self.assertEqual(payload['events'], prev_events, 'previous committed events retained')
        self.assertEqual(payload['manifest']['lastSync'], prev_last_sync, 'lastSync preserved on total failure')
        self.assertGreaterEqual(payload['manifest']['lastAttempt'], prev_last_sync)
        self.assertEqual(payload['manifest']['health']['status'], 'error')
        self.assertIn('RSS', payload['manifest']['health']['failedSources'])
        self.assertEqual(run_row['outcome'], 'error', 'run row outcome=error inside the same transaction')
        states = {r['provider_uid']: (r['state'], r['error_code']) for r in health_rows}
        self.assertEqual(states.get('rss'), ('failed', 'source_failure'))

    def test_media_enrichment_failure_does_not_block_publication(self):
        # Row 7: attach_media patched to raise — cycle still publishes; failure non-fatal.
        import sycamore_ingest.media_pipeline as media_pipeline
        self.legacy_out([make_article(1)])
        runner.run(self.out, mode='archive', archive_path=self.db, snapshot_only=True)

        def fail_attach(pairs, out):
            raise RuntimeError('injected: media pipeline down')

        with patch.object(media_pipeline, 'attach_media', side_effect=fail_attach), \
             patch.object(rss_client, 'fetch_all', return_value=batch()), \
             patch.object(rss_client, 'to_articles', return_value=[make_article(2)]):
            result = runner.run(self.out, mode='archive', archive_path=self.db)

        self.assertEqual(result['kind'], 'archive')
        snap = json.loads((self.out / 'snapshot.json').read_text())
        urls = {u for e in snap['events'] for u in e['sources']}
        self.assertIn('https://alpha.example/story-2', urls, 'new event published despite media failure')
        jobs = self.jobs()
        self.assertEqual(jobs[-1]['state'], 'published')


class NoLossAndIdentityTests(PublicationTestCase):
    """Register-card acceptance: no lost committed events, stable IDs across crash/replay sequences."""

    def test_no_lost_events_and_stable_ids_across_crash_boundaries(self):
        # Three fixture cycles adding distinct articles + one title-revision cycle with crashes at each boundary.
        self.legacy_out([make_article(1)])  # file state: event id 1 (story-1)

        def fail_write_once(out_dir, payload):
            raise OSError('injected: crash between commit and replace')

        # Cycle A: article 2; CRASH after DB commit before file write.
        runner.run(self.out, mode='archive', archive_path=self.db, snapshot_only=True)  # bootstrap job #1
        with patch.object(publisher, '_write_snapshot_files', side_effect=fail_write_once), \
             self.assertRaises(OSError):
            self.archive_cycle([make_article(2)])          # commits job #2; files not written

        # Recovery run (fetch returns article 3 this time — cycle B) replays the pending job FIRST, no refetch of it.
        with patch.object(rss_client, 'fetch_all', return_value=batch()), \
             patch.object(rss_client, 'to_articles', return_value=[make_article(3)]):
            runner.run(self.out, mode='archive', archive_path=self.db)  # replays job #2 + commits/publishes job #3

        # Cycle C: title revision of article 2 (same URL); CRASH before acknowledgement.
        def fail_ack(conn, publication_uid):
            raise OSError('injected: crash after file write, before ack')

        revised = make_article(2)
        revised['title'] = 'Ransomware wave number 2 disrupts Frankfurt region — update'
        with patch.object(publisher, '_acknowledge', side_effect=fail_ack), \
             self.assertRaises(OSError):
            self.archive_cycle([revised])                  # commits job #4; files written; ack crashed

        # Final recovery run: replay heals the unacked job (identical bytes) and publishes.
        with patch.object(rss_client, 'fetch_all', return_value=batch()), \
             patch.object(rss_client, 'to_articles', return_value=[make_article(2)]):
            runner.run(self.out, mode='archive', archive_path=self.db)  # replays job #4 + commits/publishes

        jobs = self.jobs()
        for j in jobs:
            self.assertEqual(j['state'], 'published', f"job {j['sequence']} must end published")
        self.assertEqual([j['sequence'] for j in jobs], [1, 2, 3, 4, 5])

        # Live archive cycles create source_records for URLs they OBSERVE (stories 2 and 3); story-1 exists only as an
        # import identity — its full payload persists in the imported revision, never re-fabricated from observation.
        with Archive(self.db) as a:
            rows = {r['original_url'] for r in a.conn.execute(
                "SELECT original_url FROM source_records WHERE provider_uid='rss'")}
        self.assertEqual(rows, {'https://alpha.example/story-2', 'https://alpha.example/story-3'},
                         'source identity recorded exactly once per observed URL')

        # Imported identity intact: story-1 carries the bootstrap import marker, and a FULL legacy-import revision
        # (geo/score provenance) persists in its history — live cycles may advance the CURRENT pointer to semantic-only
        # revisions, but they never destroy imported full payloads (INT-003 rule-b semantics).
        with Archive(self.db) as a:
            ev = a.conn.execute(
                "SELECT import_identity FROM events WHERE legacy_id=1").fetchone()
        self.assertEqual(ev['import_identity'], runner._LEGACY_IMPORT_IDENTITY)
        with Archive(self.db) as a:
            full_rows = [json.loads(r[0]) for r in a.conn.execute(
                """SELECT er.permitted_payload FROM event_revisions er
                    JOIN events e ON e.event_uid=er.event_uid
                   WHERE e.legacy_id=1 AND er.source='legacy_import'""")]
        self.assertEqual(len(full_rows), 1, 'exactly one full legacy-import revision survives')
        stored = full_rows[0]
        self.assertIn('lat', stored, 'full v1 row: geo provenance retained in history')
        self.assertIn('score', stored, 'full v1 row: score provenance retained in history')

        # Latest file reflects all non-pruned commits; IDs stable and unique.
        snap = json.loads((self.out / 'snapshot.json').read_text())
        by_url = {}
        for e in snap['events']:
            for u in e['sources']:
                by_url[u] = e['id']
        self.assertEqual(len({e['id'] for e in snap['events']}), len(snap['events']), 'unique event IDs')
        self.assertIn('https://alpha.example/story-1', by_url)
        self.assertIn('https://alpha.example/story-3', by_url)

    def test_reobserving_old_urls_allocates_no_new_ids(self):
        self.legacy_out([make_article(1)])
        runner.run(self.out, mode='archive', archive_path=self.db, snapshot_only=True)
        self.archive_cycle([make_article(2), make_article(3)])
        with Archive(self.db) as a:
            ids_before = [e['id'] for e in json.loads(a.conn.execute(
                "SELECT payload_or_reference FROM publication_jobs ORDER BY sequence DESC LIMIT 1"
            ).fetchone()['payload_or_reference'])['events']]

        # Re-observe the SAME article (same URL): dedupe must skip it; no new ID, stable source uid.
        with Archive(self.db) as a:
            before_uid = a.conn.execute(
                "SELECT source_uid FROM source_records WHERE original_url=?", ('https://alpha.example/story-2',)).fetchone()['source_uid']
        self.archive_cycle([make_article(2)])  # identical re-fetch of story-2 only

        with Archive(self.db) as a:
            after_payload = json.loads(a.conn.execute(
                "SELECT payload_or_reference FROM publication_jobs ORDER BY sequence DESC LIMIT 1"
            ).fetchone()['payload_or_reference'])['events']
            after_uid = a.conn.execute(
                "SELECT source_uid FROM source_records WHERE original_url=?", ('https://alpha.example/story-2',)).fetchone()['source_uid']
        self.assertEqual(after_uid, before_uid, 'reobservation keeps the same source identity')
        ids_after = [e['id'] for e in after_payload]
        prev_ids = set(ids_before)
        ids_after_set = set(ids_after)
        # No event that already existed got a different ID: previous IDs are all still present.
        self.assertTrue(prev_ids <= ids_after_set, 'previous IDs all still present (no identity drift)')
        # A pure re-observation of known URLs allocates no new ID at all.
        self.assertLessEqual(max(ids_after_set), max(prev_ids), 'pure re-observation allocates no new ID')

    def test_bootstrap_high_water_honored_and_counter_monotonic(self):
        # Import 50 events under a stable identity, then live archive cycles must allocate only above the high-water:
        # no allocation below nextEventId, and the event_id counter stays monotonic across commit/crash/replay.
        imported = [normalize(make_article(i + 1), i + 1) for i in range(50)]
        manifest = runner._empty_manifest()
        now_ms = runner._now_ms()
        manifest.update(lastSync=now_ms, lastAttempt=now_ms, nextEventId=51, counts=runner._counts(imported))
        manifest['health'] = {'status': 'ok', 'durationMs': 0}
        self.out.mkdir(parents=True, exist_ok=True)
        runner._publish(self.out, imported, manifest)

        # Bootstrap: import into the archive under a stable identity + commit job #1 (no fetch).
        result = runner.run(self.out, mode='archive', archive_path=self.db, snapshot_only=True)
        self.assertEqual(result['kind'], 'bootstrap')

        def counter_event_id():
            with Archive(self.db) as a:
                row = a.conn.execute(
                    "SELECT next_value FROM identity_counters WHERE name='event_id'").fetchone()
            return int(row['next_value']) if row else None

        self.assertGreaterEqual(counter_event_id(), 51, 'imported high-water honored at bootstrap')

        # Live cycle A: one new article must get ID exactly the imported high-water (51), not below it.
        with patch.object(rss_client, 'fetch_all', return_value=batch()), \
             patch.object(rss_client, 'to_articles', return_value=[make_article(90)]):
            runner.run(self.out, mode='archive', archive_path=self.db)
        with Archive(self.db) as a:
            payload_a = json.loads(a.conn.execute(
                "SELECT payload_or_reference FROM publication_jobs ORDER BY sequence DESC LIMIT 1"
            ).fetchone()['payload_or_reference'])
        new_ids_a = [e['id'] for e in payload_a['events']]
        self.assertEqual(len(new_ids_a), 51, 'imported events retained + one new event')
        by_url_a = {u: e['id'] for e in payload_a['events'] for u in e.get('sources', [])}
        self.assertEqual(by_url_a.get('https://alpha.example/story-90'), 51,
                         'new allocation starts exactly at the imported high-water')
        self.assertGreaterEqual(counter_event_id(), 52)

        # Crash between commit and file write on cycle B; recovery run replays it. IDs must stay monotonic —
        # a replayed/committed job can never re-allocate an ID below what was already committed.
        def fail_write_once(out_dir, payload):
            raise OSError('injected: crash between commit and replace')

        with patch.object(publisher, '_write_snapshot_files', side_effect=fail_write_once), \
             self.assertRaises(OSError):
            with patch.object(rss_client, 'fetch_all', return_value=batch()), \
                 patch.object(rss_client, 'to_articles', return_value=[make_article(91)]):
                runner.run(self.out, mode='archive', archive_path=self.db)  # job committed; files not written

        counter_after_commit = counter_event_id()
        self.assertGreaterEqual(counter_after_commit, 53)

        with patch.object(rss_client, 'fetch_all', return_value=batch()), \
             patch.object(rss_client, 'to_articles', return_value=[make_article(92)]):
            runner.run(self.out, mode='archive', archive_path=self.db)  # replays pending job + commits next

        with Archive(self.db) as a:
            payload_c = json.loads(a.conn.execute(
                "SELECT payload_or_reference FROM publication_jobs ORDER BY sequence DESC LIMIT 1"
            ).fetchone()['payload_or_reference'])
        by_url_c = {u: e['id'] for e in payload_c['events'] for u in e.get('sources', [])}
        self.assertEqual(by_url_c.get('https://alpha.example/story-90'), 51, 'committed ID stable across crash/replay')
        self.assertGreaterEqual(counter_event_id(), counter_after_commit, 'counter monotonic through replay')

    def test_bootstrap_guardrail_rejects_non_bootstrappable_db_before_fetch(self):
        # Spec row: fresh DB with only live-ingest revisions, no publication payload and no imported identity must
        # raise BEFORE any fetch — the error names the required bootstrap step. No network by construction: we
        # assert on the exception and that fetch_all was never called at all.
        root = Path(tempfile.mkdtemp())
        try:
            db_path = root / 'live-only.db'
            with Archive(db_path) as a:  # migrations applied; seed ONE live-ingest observation (semantic content only)
                run_uid = a.begin_run(runner._now_ms())
                batch_result = a.record_batch(run_uid, 'rss', [make_article(7)], runner._now_ms())
                a.finish_run(run_uid, 'ok', {'accepted': len(batch_result.observations)}, None)

            def counting_fetch():
                self.fail('guardrail must fire before any source fetch')  # noqa: PT015 — zero-fetch is the contract
                return batch()

            out_dir = root / 'out'
            with patch.object(rss_client, 'fetch_all', side_effect=counting_fetch):
                with self.assertRaises(archive.BootstrapRequired) as ctx:
                    runner.run(out_dir, mode='archive', archive_path=db_path)
            msg = str(ctx.exception)
            self.assertIn('snapshot-only', msg, 'error must name the required bootstrap step')
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_imported_only_db_projects_without_publication(self):
        # Bootstrap rule (b): a DB holding only import_identity events (no publication_jobs row yet) projects its
        # full legacy-import payloads — reconstruction from semantic-only revisions stays impossible by design.
        root = Path(tempfile.mkdtemp())
        try:
            db_path = root / 'imported.db'
            imported_events = [normalize(make_article(i + 1), i + 1) for i in range(5)]
            manifest = runner._empty_manifest()
            now_ms = runner._now_ms()
            snapshot = {'version': 1, 'events': list(imported_events),
                        'manifest': {**manifest, 'lastSync': now_ms, 'lastAttempt': now_ms,
                                     'nextEventId': 6, 'counts': runner._counts(list(imported_events)),
                                     'health': {'status': 'ok', 'durationMs': 0}}}
            with Archive(db_path) as a:
                mapping = a.import_snapshot(snapshot, 'fixture-import')
                projection = a.latest_projection()

            self.assertEqual(len(mapping), 5, 'import identity maps every legacy ID stably')
            self.assertIsNotNone(projection, 'rule (b): imported state is bootstrappable without any publication job')
            projected_ids = sorted(e['id'] for e in projection['events'])
            self.assertEqual(projected_ids, [1, 2, 3, 4, 5])
            # Full v1 rows survive reconstruction — geo/score provenance intact (semantic-only rule excluded).
            first = next(e for e in projection['events'] if e['id'] == 1)
            self.assertEqual(first['lat'], imported_events[0]['lat'])
            self.assertIn('score', first)
            # High-water honored: manifest.nextEventId at least max ID+1.
            self.assertGreaterEqual(projection['manifest']['nextEventId'], 6)

            # Repeat import under the SAME identity is idempotent (stable UIDs, no new rows).
            with Archive(db_path) as a2:
                mapping2 = a2.import_snapshot(snapshot, 'fixture-import')
            self.assertEqual(mapping2, mapping)
        finally:
            shutil.rmtree(root, ignore_errors=True)
