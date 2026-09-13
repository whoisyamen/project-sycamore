"""Iteration 1.1.2: intelligence contract validation and cross-object checks.

Runs against shared fixtures in shared/fixtures/intelligence/.
"""
import copy
import json
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sycamore_ingest.contracts import (
    validate_intelligence, check_index, check_detail,
    validate_event, validate_snapshot, INTELLIGENCE_SCHEMAS,
)

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / 'shared' / 'fixtures' / 'intelligence'


def load(rel: str):
    return json.loads((FIX / rel).read_text())


class IntelligenceContractTests(unittest.TestCase):
    def test_v1_event_accepted_by_old_validator(self):
        validate_event(load('valid/v1-event.json'))

    def test_v1_snapshot_accepted_by_old_validator(self):
        validate_snapshot(load('valid/v1-snapshot.json'))

    def test_v1_plus_eventuid_rejected(self):
        # Proves why enrichment is separate: v1 must stay strict.
        with self.assertRaises(ValueError):
            validate_event(load('invalid/v1-event-plus-uid.json'))

    def test_valid_intelligence_records_accepted(self):
        validate_intelligence('record.schema.json', load('valid/record.json'))
        validate_intelligence('index.schema.json', load('valid/index.json'))
        validate_intelligence('detail.schema.json', load('valid/detail.json'))

    def test_unknown_detail_property_rejected(self):
        with self.assertRaises(ValueError):
            validate_intelligence('detail.schema.json', load('invalid/detail-unknown-property.json'))

    def test_nested_extra_property_rejected(self):
        with self.assertRaises(ValueError):
            validate_intelligence('detail.schema.json', load('invalid/detail-evidence-extra-property.json'))

    def test_oversize_array_rejected(self):
        detail = load('valid/detail.json')
        detail['evidence'] = [detail['evidence'][0] for _ in range(21)]
        with self.assertRaises(ValueError):
            validate_intelligence('detail.schema.json', detail)

    def test_nullable_fields_accept_nulls_and_reject_wrong_type(self):
        detail = load('valid/detail.json')
        detail['evidence'][0]['publishedAt'] = None
        validate_intelligence('detail.schema.json', detail)
        bad = copy.deepcopy(detail)
        bad['evidence'][0]['publishedAt'] = 'not-a-time'
        with self.assertRaises(ValueError):
            validate_intelligence('detail.schema.json', bad)
        # integer/boolean distinction preserved: true is not an integer
        bad2 = copy.deepcopy(detail)
        bad2['evidence'][0]['publishedAt'] = True
        with self.assertRaises(ValueError):
            validate_intelligence('detail.schema.json', bad2)

    def test_unknown_schema_name_fails_closed(self):
        with self.assertRaises(ValueError):
            validate_intelligence('../../etc/passwd', {})
        with self.assertRaises(ValueError):
            validate_intelligence('https://evil.example/x.schema.json', {})

    def test_registry_has_no_arbitrary_refs(self):
        # Every registry schema must be fully inline with no unsupported $refs.
        import re
        for name, path in INTELLIGENCE_SCHEMAS.items():
            text = path.read_text()
            self.assertNotIn('"$ref"', text.replace('"$schema"', ''), f'{name} uses $ref')

    def test_cross_object_dangling_references_rejected(self):
        for name in ('detail-dangling-evidence', 'detail-dangling-mention'):
            with self.assertRaises(ValueError, msg=name):
                check_detail(load(f'invalid/{name}.json'))

    def test_cross_object_reader_consistency_rejected(self):
        detail = load('invalid/detail-wrong-event-uid.json')
        with self.assertRaises(ValueError):
            check_detail(detail, expected={'eventUid': 'aaaaaaaa-0000-4000-8000-000000000001'})
        release = load('invalid/detail-wrong-release-uid.json')
        with self.assertRaises(ValueError):
            check_detail(release, expected={'releaseUid': '99999999-0000-4000-8000-000000000001'})

    def test_cross_object_source_text_and_removed_rules(self):
        with self.assertRaises(ValueError):
            check_detail(load('invalid/detail-source-text-null-excerpt.json'))
        with self.assertRaises(ValueError):
            check_detail(load('invalid/detail-metadata-invented-excerpt.json'))
        with self.assertRaises(ValueError):
            check_detail(load('invalid/detail-removed-with-excerpt.json'))

    def test_cross_object_offset_rules(self):
        with self.assertRaises(ValueError):
            check_detail(load('invalid/detail-unpaired-offset.json'))
        with self.assertRaises(ValueError):
            check_detail(load('invalid/detail-invalid-offset.json'))

    def test_cross_object_related_self_rejected(self):
        with self.assertRaises(ValueError):
            check_detail(load('invalid/detail-related-self.json'))

    def test_index_path_rules(self):
        index = load('valid/index.json')
        check_index(index)
        bad = copy.deepcopy(index)
        bad['entries'][0]['eventId'] = 17  # duplicate (only one entry, so add another)
        bad['entries'].append(copy.deepcopy(bad['entries'][0]))
        with self.assertRaises(ValueError):
            check_index(bad)
        evil = copy.deepcopy(index)
        evil['entries'][0]['artifactPath'] = '/data/intelligence/v1/releases/../../etc/passwd'
        with self.assertRaises(ValueError):
            check_index(evil)

    def test_complete_detail_size_cap(self):
        detail = load('valid/detail.json')
        detail['evidence'] = [detail['evidence'][0] for _ in range(20)]
        detail['entities'] = [detail['entities'][0] for _ in range(20)]
        detail['timeline'] = [detail['timeline'][0] for _ in range(20)]
        for e in detail['evidence']:
            e['title'] = 'x' * 500
            e['excerpt'] = 'y' * 600
            e['sourceUrl'] = 'https://alpha.example/very-long-' + 'a' * 1900
        with self.assertRaises(ValueError):
            check_detail(detail)


if __name__ == '__main__':
    unittest.main()