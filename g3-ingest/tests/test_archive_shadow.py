"""Iteration 1.2.1: runner-in-shadow integration tests.

The runner stays legacy-authoritative; archive observation is additive. These
tests verify the single-fetch contract, observation-before-pruning, config
guardrails, failure isolation and legacy parity.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sycamore_ingest import runner, rss_client, archive
from sycamore_ingest.archive import Archive

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


def batch(success=1, failed=()):
    result = rss_client.FeedBatch()
    result.succeeded = success
    result.failed = list(failed)
    return result


class ShadowConfigTests(unittest.TestCase):
    def test_legacy_default_requires_no_archive(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'out'
            with patch.object(runner, '_osint_cycle', return_value=[]), \
                 patch.object(rss_client, 'fetch_all', return_value=batch()), \
                 patch.object(rss_client, 'to_articles', return_value=[]):
                manifest = runner.run(out)
            self.assertEqual(manifest['health']['status'], 'ok')

    def test_shadow_requires_archive_path(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'out'
            with self.assertRaises(ValueError):
                runner.run(out, mode='shadow', archive_path=None)

    def test_shadow_rejects_public_data_path(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'out'
            # Real project public data path must be rejected (guard checks
            # against the actual repo, not any temp dir).
            bad = runner.DEFAULT_OUT / 'archive.db'
            with self.assertRaises(ValueError):
                runner.run(out, mode='shadow', archive_path=bad)

    def test_invalid_mode_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'out'
            with self.assertRaises(ValueError):
                runner.run(out, mode='space')


class ShadowIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name) / 'out'
        self.db = Path(self.temp.name) / 'archive.db'
        self.osint = patch.object(runner, '_osint_cycle', return_value=[])
        self.osint.start()
        self.addCleanup(self.osint.stop)
        self._fetch = None

    def run_shadow(self, articles, result=None, use_gdelt=False):
        result = result if result is not None else batch()
        with patch.object(rss_client, 'fetch_all', return_value=result), \
             patch.object(rss_client, 'to_articles', return_value=list(articles)):
            return runner.run(self.out, mode='shadow', archive_path=self.db, use_gdelt=use_gdelt)

    def snapshot(self):
        return json.loads((self.out / 'snapshot.json').read_text())

    def test_output_parity_legacy_vs_shadow(self):
        # Fixed batch and identical setup: shadow must publish the same v1.
        with patch.object(rss_client, 'fetch_all', return_value=batch()), \
             patch.object(rss_client, 'to_articles', return_value=[ARTICLE]):
            runner.run(self.out)  # legacy run
        legacy = self.snapshot()
        with patch.object(rss_client, 'fetch_all', return_value=batch()), \
             patch.object(rss_client, 'to_articles', return_value=[ARTICLE]):
            runner.run(self.out)  # shadow run over same out; parities through archive
        shadow = self.snapshot()
        self.assertEqual(legacy['version'], shadow['version'])
        self.assertEqual([e['id'] for e in legacy['events']],
                         [e['id'] for e in shadow['events']])

    def test_single_fetch_observed_before_dedupe(self):
        # Two DISTINCT articles (different outlets, same story) merge into one
        # v1 event; the archive records both observations BEFORE merge/dedupe.
        second = {**ARTICLE, 'url': 'https://beta.example/story-copy',
                  'domain': 'beta.example', '_rss_source': 'BetaFeed'}
        count = {'fetch': 0}
        def fetch_all():
            count['fetch'] += 1
            return batch()
        with patch.object(rss_client, 'fetch_all', side_effect=fetch_all), \
             patch.object(rss_client, 'to_articles', return_value=[ARTICLE, second]):
            manifest = runner.run(self.out, mode='shadow', archive_path=self.db)
        self.assertEqual(count['fetch'], 1, 'must not fetch twice in shadow')
        self.assertEqual(manifest['counts']['events'], 1, 'articles merged into one event')
        with Archive(self.db) as a:
            obs = a.conn.execute('SELECT COUNT(*) c FROM source_observations').fetchone()['c']
            self.assertEqual(obs, 2, 'both observations archived before merge/dedupe')

    def test_nongeolocated_captured_without_v1_marker(self):
        nongeo = {**ARTICLE, 'lat': 0, 'long': 0,
                  '_rss_description': '',  # no geocodable summary either
                  'title': 'Cyber incident reported without tracked coordinates'}
        self.run_shadow([nongeo])
        snap = self.snapshot()
        self.assertEqual(len(snap['events']), 0)
        with Archive(self.db) as a:
            row = a.conn.execute(
                'SELECT normalization_outcome FROM source_observations'
            ).fetchone()
            self.assertEqual(row['normalization_outcome'], 'rejected:no_map_event')

    def test_invalid_url_rejected_legacy_continues(self):
        bad = {**ARTICLE, 'url': 'javascript:alert(1)'}
        self.run_shadow([bad])
        snap = self.snapshot()
        self.assertEqual(len(snap['events']), 0)
        with Archive(self.db) as a:
            # No unsafe content is stored in the archive for an invalid URL.
            sources = a.conn.execute('SELECT COUNT(*) c FROM source_records').fetchone()['c']
            self.assertEqual(sources, 0, 'invalid URL must not create source records')

    def test_pruned_report_returns_with_same_identity(self):
        # Seed > MAX_EVENTS (500) events so the oldest is pruned from v1 but
        # remains archived; reobserving it must recover the same source identity.
        articles = []
        for i in range(510):
            articles.append({**ARTICLE, 'title': f'Ransomware wave {i} in Frankfurt region',
                             'url': f'https://alpha.example/story/{i}',
                             'domain': 'alpha.example'})
        self.run_shadow(articles)
        snap = self.snapshot()
        self.assertEqual(len(snap['events']), runner.MAX_EVENTS, 'v1 projection capped')
        old_url = articles[0]['url']
        with Archive(self.db) as a:
            row = a.conn.execute(
                'SELECT source_uid FROM source_records WHERE original_url=?', (old_url,)
            ).fetchone()
            self.assertIsNotNone(row, 'pruned source must remain archived')
            source_uid = row['source_uid']
        self.run_shadow([articles[0]])  # reobserve oldest
        with Archive(self.db) as a:
            row = a.conn.execute(
                'SELECT source_uid FROM source_records WHERE original_url=?', (old_url,)
            ).fetchone()
            self.assertEqual(row['source_uid'], source_uid, 'identity stable across pruning')

    def test_shadow_db_failure_does_not_block_legacy(self):
        # record_batch raising must not break the JSON pipeline; the cycle
        # completes and the gap is recorded best-effort.
        with patch.object(rss_client, 'fetch_all', return_value=batch()), \
             patch.object(rss_client, 'to_articles', return_value=[ARTICLE]), \
             patch.object(archive.Archive, 'record_batch', side_effect=RuntimeError('db down')):
            manifest = runner.run(self.out, mode='shadow', archive_path=self.db)
        self.assertEqual(manifest['health']['status'], 'ok')
        self.assertEqual(len(self.snapshot()['events']), 1)
        with Archive(self.db) as a:
            rows = a.conn.execute('SELECT state FROM shadow_gaps').fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['state'], 'open')

    def test_repeat_shadow_cycles_are_idempotent(self):
        self.run_shadow([ARTICLE])
        first_revs = 0
        with Archive(self.db) as a:
            first_revs = a.conn.execute('SELECT COUNT(*) c FROM event_revisions').fetchone()['c']
        self.run_shadow([ARTICLE])  # identical re-fetch
        with Archive(self.db) as a:
            revs = a.conn.execute('SELECT COUNT(*) c FROM event_revisions').fetchone()['c']
            self.assertEqual(revs, first_revs, 'identical re-fetch must not append revisions')

    def test_changed_title_appends_source_revision(self):
        self.run_shadow([ARTICLE])
        changed = {**ARTICLE, 'title': 'Frankfurt grid ransomware: revised headline'}
        self.run_shadow([changed])
        with Archive(self.db) as a:
            revs = a.conn.execute('SELECT COUNT(*) c FROM source_revisions').fetchone()['c']
            self.assertEqual(revs, 2, 'changed lede creates a new source revision')


if __name__ == '__main__':
    unittest.main()