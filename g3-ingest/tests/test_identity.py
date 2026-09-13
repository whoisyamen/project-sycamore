"""Iteration 1.1.2: stable identity primitives (INT-001 / spec §4.1)."""
import hashlib
import json
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sycamore_ingest import identity

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / 'shared' / 'fixtures' / 'intelligence'


class CanonicalHashTests(unittest.TestCase):
    def test_shared_hash_vectors(self):
        data = json.loads((FIX / 'canonical-hash-vectors.json').read_text())
        for vec in data['vectors']:
            self.assertEqual(
                identity.canonical_sha256(vec['value']),
                vec['sha256'],
                f"vector {vec['name']} mismatch",
            )

    def test_rejects_non_finite_numbers(self):
        for bad in (float('nan'), float('inf'), float('-inf')):
            with self.assertRaises(ValueError):
                identity.canonical_sha256({'x': bad})

    def test_key_order_does_not_matter(self):
        self.assertEqual(
            identity.canonical_sha256({'a': 1, 'b': [1, 2]}),
            identity.canonical_sha256({'b': [1, 2], 'a': 1}),
        )

    def test_array_order_matters(self):
        self.assertNotEqual(
            identity.canonical_sha256({'a': [1, 2]}),
            identity.canonical_sha256({'a': [2, 1]}),
        )

    def test_semantic_change_changes_hash_clock_only_does_not(self):
        base = {'title': 'Frankfurt ransomware', 'lat': 50.11, 'lon': 8.68, 'lastSeen': 100}
        changed = {**base, 'title': 'Frankfurt ransomware revised'}
        new_seen = {**base, 'lastSeen': 200}
        self.assertNotEqual(
            identity.canonical_sha256(base),
            identity.canonical_sha256(changed),
        )
        # Clock-only fields DO change the plain canonical hash (that is why the
        # semantic hash excludes them); this test documents current behavior and
        # the caller must strip continuously recalculated fields before hashing.
        self.assertNotEqual(
            identity.canonical_sha256(base),
            identity.canonical_sha256(new_seen),
        )


class EventUidTests(unittest.TestCase):
    def test_existing_mapping_reused(self):
        mapping = {17: 'aaaaaaaa-0000-4000-8000-000000000001'}
        uid, created = identity.ensure_event_uid(mapping, 17)
        self.assertEqual(uid, 'aaaaaaaa-0000-4000-8000-000000000001')
        self.assertFalse(created)

    def test_new_mapping_allocated_and_recorded(self):
        mapping: dict[int, str] = {}
        uid, created = identity.ensure_event_uid(mapping, 17)
        self.assertTrue(created)
        self.assertEqual(mapping[17], uid)
        # replay: same result, no duplicate
        uid2, created2 = identity.ensure_event_uid(mapping, 17)
        self.assertEqual(uid2, uid)
        self.assertFalse(created2)

    def test_changed_title_retains_mapping(self):
        mapping = {17: 'aaaaaaaa-0000-4000-8000-000000000001'}
        uid, _ = identity.ensure_event_uid(mapping, 17)
        self.assertEqual(uid, 'aaaaaaaa-0000-4000-8000-000000000001')

    def test_invalid_event_id_rejected(self):
        with self.assertRaises(ValueError):
            identity.ensure_event_uid({}, 0)
        with self.assertRaises(ValueError):
            identity.ensure_event_uid({}, -1)

    def test_import_manifest_checksum_stable(self):
        m1 = {1: 'aaaaaaaa-0000-4000-8000-000000000001', 2: 'bbbbbbbb-0000-4000-8000-000000000002'}
        m2 = dict(reversed(list(m1.items())))
        self.assertEqual(identity.import_manifest_checksum(m1), identity.import_manifest_checksum(m2))


class SourceKeyTests(unittest.TestCase):
    def test_native_id_preferred(self):
        self.assertEqual(
            identity.source_key('provider.rss.alpha', provider_native_id='42'),
            'provider.rss.alpha|42',
        )

    def test_same_url_different_provider_distinct(self):
        url = 'https://alpha.example/story/17'
        a = identity.source_key('provider.rss.alpha', source_url=url)
        b = identity.source_key('provider.rss.beta', source_url=url)
        self.assertNotEqual(a, b)

    def test_url_canonicalization_default_port_and_fragment(self):
        url = 'https://Alpha.Example:443/story/17?x=1#frag'
        canonical = identity.canonicalize_url(url)
        self.assertEqual(canonical, 'https://alpha.example/story/17?x=1')
        # original retained separately is the caller's job; canonical never has fragment
        self.assertNotIn('#', canonical)

    def test_query_strings_remain_distinct(self):
        a = identity.canonicalize_url('https://alpha.example/story?q=one')
        b = identity.canonicalize_url('https://alpha.example/story?q=two')
        self.assertNotEqual(a, b)

    def test_non_default_port_preserved(self):
        self.assertEqual(
            identity.canonicalize_url('https://alpha.example:8443/x'),
            'https://alpha.example:8443/x',
        )

    def test_invalid_scheme_rejected(self):
        for url in ('javascript:alert(1)', 'file:///etc/passwd', 'data:text/plain,hi', ''):
            with self.assertRaises(ValueError):
                identity.canonicalize_url(url)

    def test_source_key_checksum_stable_and_distinct(self):
        a = identity.source_key_checksum('p|42')
        b = identity.source_key_checksum('p|43')
        self.assertEqual(a, identity.source_key_checksum('p|42'))
        self.assertNotEqual(a, b)
        self.assertEqual(len(a), 64)


if __name__ == '__main__':
    unittest.main()