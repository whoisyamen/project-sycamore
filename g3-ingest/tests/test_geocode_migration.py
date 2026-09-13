"""Migration uses actual temporary snapshots; no source fetching."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sycamore_ingest import normalizer, runner, fix_bad_geocodes
from sycamore_ingest.contracts import validate_snapshot


def event(id, title, provenance='nominatim'):
    return {'id':id,'title':title,'t':'geopolitical','sev':'watching','src':'BBC',
            'lat':40.0,'lon':-100.0,'loc':'bogus old location','ts':10,'ingestedAt':20,
            'sources':[f'https://example.com/{id}'],'score':{'articles':1,'tone':0},
            'geo':{'source':provenance,'tier':'precise'}}


class MigrationTests(unittest.TestCase):
    def test_audit_all_preserve_source_quarantine_and_idempotent_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'public'/'data'; out.mkdir(parents=True)
            archive = Path(tmp)/'private-audit'
            events = [event(36,'Teen shot dead in West Bank'),
                      event(80,'Rockwell Automation OTTO Fleet Manager'),
                      event(90,'Ransomware targets unknown institution','source'),
                      event(91,'Attacks reported in Moscow and Kyiv')]
            legacy = event(92,'Troops arrive in Plymouth'); legacy.pop('geo'); events.append(legacy)
            manifest = runner._empty_manifest(); manifest.update(nextEventId=100,counts=runner._counts(events))
            original = {'version':1,'events':events,'manifest':manifest}
            runner._atomic_write(out/'snapshot.json',original)
            before = (out/'snapshot.json').read_bytes()
            self.assertTrue(hasattr(fix_bad_geocodes,'migrate'), 'locked migration API missing')
            with patch('urllib.request.urlopen',side_effect=AssertionError('offline only')):
                report = fix_bad_geocodes.migrate(out, archive)
            self.assertEqual(report['counts'],{'audited':5,'preservedSource':1,'updated':1,'unchanged':0,'quarantined':3,'published':2})
            snap = json.loads((out/'snapshot.json').read_text()); validate_snapshot(snap)
            self.assertEqual([e['id'] for e in snap['events']],[36,90])
            self.assertEqual(snap['events'][1],events[2])
            self.assertEqual(snap['events'][0]['geo']['scope'],'region')
            self.assertEqual(snap['manifest']['nextEventId'],100)
            for key in ['ts','ingestedAt','sources','score']:
                self.assertEqual(snap['events'][0][key],events[0][key])
            self.assertEqual((Path(report['archive'])/'snapshot.json').read_bytes(),before)
            audit = json.loads((Path(report['archive'])/'audit.json').read_text())
            self.assertEqual(len(audit['records']),5)
            self.assertEqual(len(json.loads((Path(report['archive'])/'quarantine.json').read_text())),3)
            self.assertEqual(json.loads((out/'events.json').read_text()),snap['events'])
            self.assertEqual(json.loads((out/'manifest.json').read_text()),snap['manifest'])
            once = (out/'snapshot.json').read_bytes()
            again = fix_bad_geocodes.migrate(out,archive)
            self.assertEqual(again['counts']['updated'],0)
            self.assertEqual(again['counts']['quarantined'],0)
            self.assertEqual((out/'snapshot.json').read_bytes(),once)

    def test_runner_refuses_unsafe_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            events=[event(1,'Rockwell Automation OTTO Fleet Manager')]
            manifest=runner._empty_manifest(); manifest.update(nextEventId=2,counts=runner._counts(events))
            with self.assertRaisesRegex(ValueError,'geolocation'):
                runner._publish(Path(tmp),events,manifest)
            self.assertFalse((Path(tmp)/'snapshot.json').exists())


if __name__ == '__main__': unittest.main()
