"""Iteration 1.2.1: archive repository unit tests (migrations, import, batch,
event revisions, comparison, gaps). Every test uses a temporary DB path."""
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sycamore_ingest import archive, identity
from sycamore_ingest.archive import Archive, MigrationChecksumError, MigrationApplyError

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

SNAPSHOT = {
    'version': 1,
    'events': [
        {'id': 1, 't': 'cyber', 'sev': 'critical', 'title': 'Frankfurt grid ransomware',
         'src': 'AlphaFeed', 'loc': 'Frankfurt, DE', 'lat': 50.11, 'lon': 8.68,
         'ts': 1789034400000, 'sources': ['https://alpha.example/story'],
         'score': {'articles': 1, 'tone': -6.0}},
        {'id': 99, 't': 'geopolitical', 'sev': 'watching', 'title': 'Regional summit talks advance',
         'src': 'BetaFeed', 'loc': 'Berlin, DE', 'lat': 52.52, 'lon': 13.40,
         'ts': 1789035000000, 'sources': ['https://beta.example/report'],
         'score': {'articles': 1, 'tone': 2.0}},
    ],
    'manifest': {'version': 1, 'lastSync': 1789075438867, 'nextEventId': 100,
                 'source': {'name': 'Curated RSS', 'endpoint': 'https://rss.example/feed'},
                 'counts': {'events': 2},
                 'health': {'status': 'ok'}},
}


def snapshot_with_events(events, next_event_id=3):
    return {'version': 1, 'events': events,
            'manifest': {'version': 1, 'lastSync': 1000, 'nextEventId': next_event_id,
                         'source': {'name': 'Curated RSS', 'endpoint': 'https://rss.example/feed'},
                         'counts': {'events': len(events)},
                         'health': {'status': 'ok'}}}


class MigrationTests(unittest.TestCase):
    def test_apply_and_replay_is_noop(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'archive.db'
            archive.apply_migrations(db)
            conn1 = archive.connect(db)
            tables1 = {r['name'] for r in conn1.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            conn1.close()
            archive.apply_migrations(db)  # second apply must be a no-op
            conn2 = archive.connect(db)
            tables2 = {r['name'] for r in conn2.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            conn2.close()
            self.assertEqual(tables1, tables2)
            self.assertIn('shadow_gaps', tables1)
            self.assertIn('schema_migrations', tables1)

    def test_edited_applied_migration_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'archive.db'
            archive.apply_migrations(db)
            # Simulate drift: overwrite the ledger checksum.
            conn = archive.connect(db)
            conn.execute("UPDATE schema_migrations SET checksum='deadbeef' WHERE version=1")
            conn.commit()
            conn.close()
            with self.assertRaises(MigrationChecksumError):
                archive.apply_migrations(db)

    def test_missing_ledger_row_allows_safe_reapply(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'archive.db'
            archive.apply_migrations(db)
            conn = archive.connect(db)
            conn.execute('DELETE FROM schema_migrations WHERE version=1')
            conn.commit()
            conn.close()
            # Re-application after the ledger row is missing performs no
            # duplicate mutation (all DDL is IF NOT EXISTS) and re-registers
            # the row with the file's own checksum.
            archive.apply_migrations(db)
            conn = archive.connect(db)
            row = conn.execute(
                'SELECT checksum FROM schema_migrations WHERE version=1'
            ).fetchone()
            conn.close()
            self.assertIsNotNone(row)
            self.assertEqual(len(row['checksum']), 64)

    def test_fk_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'archive.db'
            a = Archive(db)
            with self.assertRaises(sqlite3.IntegrityError):
                with a.conn:
                    a.conn.execute(
                        "INSERT INTO source_records (source_uid, provider_uid, natural_key,"
                        " original_url, canonical_url) VALUES ('x','missing-provider','k','u','c')"
                    )
            a.close()


class ImportSnapshotTests(unittest.TestCase):
    def test_initial_import_stores_mapping_and_counter(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            mapping = a.import_snapshot(SNAPSHOT, 'import:test')
            self.assertEqual(set(mapping), {1, 99})
            self.assertEqual(a._counter('event_id'), 100)
            row = a.conn.execute(
                'SELECT source FROM event_revisions WHERE event_uid=?',
                (mapping[1],),
            ).fetchone()
            self.assertEqual(row['source'], 'legacy_import')
            a.close()

    def test_repeat_import_same_identity_returns_same_mapping(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            m1 = a.import_snapshot(SNAPSHOT, 'import:test')
            m2 = a.import_snapshot(SNAPSHOT, 'import:test')
            self.assertEqual(m1, m2)
            self.assertEqual(len(m2), 2)
            a.close()

    def test_conflicting_import_identity_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            a.import_snapshot(SNAPSHOT, 'import:first')
            with self.assertRaises(archive.ArchiveError):
                a.import_snapshot(SNAPSHOT, 'import:second')
            a.close()

    def test_changed_title_retains_uid(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            m1 = a.import_snapshot(SNAPSHOT, 'import:test')
            changed = copy.deepcopy(SNAPSHOT)
            changed['events'][0]['title'] = 'Frankfurt grid ransomware: revised headline'
            m2 = a.import_snapshot(changed, 'import:test')
            self.assertEqual(m1[1], m2[1])  # ID 1 keeps its UID


class RecordBatchTests(unittest.TestCase):
    def test_batch_records_sources_and_health(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            run_uid = a.begin_run(1000)
            result = a.record_batch(run_uid, 'rss', [ARTICLE], 1000)
            self.assertEqual(result.accepted, 1)
            self.assertEqual(result.rejected, 0)
            obs = a.conn.execute(
                'SELECT normalization_outcome FROM source_observations'
            ).fetchone()
            self.assertEqual(obs['normalization_outcome'], 'accepted')
            health = a.conn.execute(
                'SELECT state FROM source_health WHERE run_uid=?', (run_uid,)
            ).fetchone()
            self.assertEqual(health['state'], 'ok')
            a.close()

    def test_replay_same_run_no_duplicate_rows(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            run_uid = a.begin_run(1000)
            a.record_batch(run_uid, 'rss', [ARTICLE], 1000)
            a.record_batch(run_uid, 'rss', [ARTICLE], 1000)
            n = a.conn.execute('SELECT COUNT(*) c FROM source_observations').fetchone()['c']
            self.assertEqual(n, 1)
            revs = a.conn.execute('SELECT COUNT(*) c FROM source_revisions').fetchone()['c']
            self.assertEqual(revs, 1)
            a.close()

    def test_identical_refetch_new_observation_no_new_revision(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            r1 = a.begin_run(1000)
            a.record_batch(r1, 'rss', [ARTICLE], 1000)
            r2 = a.begin_run(2000)
            res2 = a.record_batch(r2, 'rss', [ARTICLE], 2000)
            self.assertEqual(res2.accepted, 1)
            revs = a.conn.execute('SELECT COUNT(*) c FROM source_revisions').fetchone()['c']
            self.assertEqual(revs, 1)
            obs = a.conn.execute('SELECT COUNT(*) c FROM source_observations').fetchone()['c']
            self.assertEqual(obs, 2)  # one per run
            a.close()

    def test_changed_title_creates_new_revision(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            r1 = a.begin_run(1000)
            a.record_batch(r1, 'rss', [ARTICLE], 1000)
            r2 = a.begin_run(2000)
            changed = {**ARTICLE, 'title': 'Frankfurt grid ransomware: revised headline'}
            a.record_batch(r2, 'rss', [changed], 2000)
            revs = a.conn.execute('SELECT COUNT(*) c FROM source_revisions').fetchone()['c']
            self.assertEqual(revs, 2)
            a.close()

    def test_two_providers_same_url_distinct_sources(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            run_uid = a.begin_run(1000)
            a.record_batch(run_uid, 'rss', [ARTICLE], 1000)
            other = {**ARTICLE, '_rss_source': 'OtherFeed'}
            a.record_batch(run_uid, 'gdelt', [other], 1000)
            sources = a.conn.execute('SELECT COUNT(*) c FROM source_records').fetchone()['c']
            self.assertEqual(sources, 2)  # distinct natural keys (different providers)
            a.close()

    def test_missing_geolocation_retained_internally(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            run_uid = a.begin_run(1000)
            nongeo = {**ARTICLE, 'lat': 0, 'long': 0,
                      '_rss_description': '',  # no geocodable summary either
                      'title': 'Cyber incident reported without tracked coordinates'}
            result = a.record_batch(run_uid, 'rss', [nongeo], 1000)
            self.assertEqual(result.accepted, 0)
            self.assertEqual(result.rejected, 1)
            obs = a.conn.execute(
                'SELECT normalization_outcome FROM source_observations'
            ).fetchone()
            self.assertEqual(obs['normalization_outcome'], 'rejected:no_map_event')
            # It is still a source observation (history), just not on the v1 map.
            self.assertEqual(a.conn.execute('SELECT COUNT(*) c FROM source_records').fetchone()['c'], 1)
            a.close()

    def test_invalid_url_rejected_no_unsafe_content(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            run_uid = a.begin_run(1000)
            bad = {**ARTICLE, 'url': 'javascript:alert(1)'}
            result = a.record_batch(run_uid, 'rss', [bad], 1000)
            self.assertEqual(result.rejected, 1)
            self.assertIsNone(result.observations[0].source_uid)
            self.assertEqual(a.conn.execute('SELECT COUNT(*) c FROM source_records').fetchone()['c'], 0)
            a.close()

    def test_finish_run_records_outcome(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            run_uid = a.begin_run(1000)
            a.finish_run(run_uid, 'ok', {'events': 1}, last_success=2000)
            row = a.conn.execute(
                'SELECT outcome, last_success FROM ingest_runs WHERE run_uid=?', (run_uid,)
            ).fetchone()
            self.assertEqual(row['outcome'], 'ok')
            self.assertEqual(row['last_success'], 2000)
            a.close()


class EventRevisionTests(unittest.TestCase):
    def test_first_revision_appended(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            src = identity.source_key('rss', source_url='https://alpha.example/story')
            a.conn.execute(
                f"INSERT INTO source_records (source_uid, provider_uid, natural_key,"
                f" original_url, canonical_url) VALUES ('s1','rss',?,?,'https://alpha.example/story')",
                (src, 'https://alpha.example/story'),
            )
            a.conn.execute(
                "INSERT INTO source_revisions (revision_uid, source_uid, content_hash,"
                " published_at, observed_at, allowed_payload) VALUES"
                " ('r1','s1','h1',NULL,1000,'{}')"
            )
            a.conn.commit()
            event_uid, appended = a.record_event_revision(
                1, {'title': 'Frankfurt grid ransomware', 'lat': 50.11},
                ['r1'], 1000,
            )
            self.assertTrue(appended)
            revs = a.conn.execute('SELECT COUNT(*) c FROM event_revisions').fetchone()['c']
            self.assertEqual(revs, 1)
            evidence = a.conn.execute('SELECT COUNT(*) c FROM event_evidence').fetchone()['c']
            self.assertEqual(evidence, 1)
            a.close()

    def test_clock_only_change_no_new_revision(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            a.conn.execute(
                "INSERT INTO source_records (source_uid, provider_uid, natural_key,"
                " original_url, canonical_url) VALUES ('s1','rss','k','u','c')")
            a.conn.execute(
                "INSERT INTO source_revisions (revision_uid, source_uid, content_hash,"
                " published_at, observed_at, allowed_payload) VALUES ('r1','s1','h1',NULL,1000,'{}')")
            a.conn.commit()
            # Semantic content (clock fields already stripped by the caller).
            content = {'title': 'Frankfurt grid ransomware', 'lat': 50.11}
            a.record_event_revision(1, content, ['r1'], 1000)
            _, appended = a.record_event_revision(1, content, ['r1'], 2000)
            self.assertFalse(appended)
            revs = a.conn.execute('SELECT COUNT(*) c FROM event_revisions').fetchone()['c']
            self.assertEqual(revs, 1)
            a.close()

    def test_clock_only_change_does_not_append_material_revision(self):
        # A changed observedAt/ingestedAt clock alone must leave the semantic
        # hash unchanged (spec §4: 'clocks alone do not append a material
        # revision'). The runner strips clocks via _semantic_event.
        from sycamore_ingest import runner as runner_mod
        event = {'id': 1, 't': 'cyber', 'sev': 'critical',
                 'title': 'Frankfurt grid ransomware', 'summary': 's',
                 'src': 'a', 'loc': 'Frankfurt, DE', 'lat': 50.11, 'lon': 8.68,
                 'ts': 1000, 'ingestedAt': 1000, 'sources': ['https://a.example/1'],
                 'score': {'articles': 1}}
        later = {**event, 'ingestedAt': 999_999}
        self.assertEqual(runner_mod._semantic_event(event),
                         runner_mod._semantic_event(later))

    def test_semantic_change_creates_new_revision(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            a.conn.execute(
                "INSERT INTO source_records (source_uid, provider_uid, natural_key,"
                " original_url, canonical_url) VALUES ('s1','rss','k','u','c')")
            a.conn.execute(
                "INSERT INTO source_revisions (revision_uid, source_uid, content_hash,"
                " published_at, observed_at, allowed_payload) VALUES ('r1','s1','h1',NULL,1000,'{}')")
            a.conn.commit()
            a.record_event_revision(1, {'title': 'Frankfurt grid ransomware'}, ['r1'], 1000)
            _, appended = a.record_event_revision(1, {'title': 'Frankfurt grid ransomware revised'}, ['r1'], 2000)
            self.assertTrue(appended)
            revs = a.conn.execute('SELECT COUNT(*) c FROM event_revisions').fetchone()['c']
            self.assertEqual(revs, 2)
            a.close()

    def test_fk_dangling_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            with self.assertRaises(sqlite3.IntegrityError):
                a.record_event_revision(1, {'title': 'x' * 20}, ['missing-revision'], 1000)
            a.close()


class CompareAndGapTests(unittest.TestCase):
    def test_compare_identical_projection(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            e1 = {'id': 1, 'title': 'T', 'loc': 'L', 'sources': ['https://x.example/1']}
            snap = snapshot_with_events([e1])
            self.assertEqual(a.compare_projection(snap, snap), [])
            a.close()

    def test_compare_detects_differences(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            e1 = {'id': 1, 'title': 'T', 'loc': 'L', 'sources': ['https://x.example/1']}
            e2 = {'id': 2, 'title': 'T2', 'loc': 'L2', 'sources': ['https://x.example/2']}
            diffs = a.compare_projection(snapshot_with_events([e1]), snapshot_with_events([e2]))
            self.assertTrue(any('event id sets differ' in d for d in diffs))
            a.close()

    def test_gap_lifecycle(self):
        with tempfile.TemporaryDirectory() as td:
            a = Archive(Path(td) / 'archive.db')
            run_uid = a.begin_run(1000)
            self.assertIsNone(a.gap_state(run_uid))
            a.record_shadow_gap(run_uid, 'record_batch: boom')
            self.assertEqual(a.gap_state(run_uid), 'open')
            # A later successful cycle records its own run; the gap row persists.
            run2 = a.begin_run(2000)
            a.record_batch(run2, 'rss', [ARTICLE], 2000)
            a.finish_run(run2, 'ok', {'events': 1}, 2000)
            self.assertEqual(a.gap_state(run_uid), 'open')  # not labeled continuous
            a.close()


if __name__ == '__main__':
    unittest.main()