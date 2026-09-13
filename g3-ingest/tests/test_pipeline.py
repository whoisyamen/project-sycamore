"""Offline integration checks. Run: python3 -m unittest discover -s tests."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sycamore_ingest import runner, rss_client
from sycamore_ingest.contracts import validate_snapshot, validate

ARTICLE = {'title':'Major ransomware hits regional power grid in Frankfurt','url':'https://alpha.example/story',
           'domain':'alpha.example','language':'English','tone':-6,'seendate':'20260903T120000Z',
           'location':{'fullName':'Frankfurt','countryCode':'DE'},'lat':50.11,'long':8.68}


def batch(success=1, failed=()):
    result = rss_client.FeedBatch()
    result.succeeded = success
    result.failed = list(failed)
    return result


class PipelineTests(unittest.TestCase):
    def setUp(self):
        osint = patch.object(runner, '_osint_cycle', return_value=[])
        osint.start()
        self.addCleanup(osint.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()
    def run_cycle(self, articles=(), result=None):
        with patch.object(rss_client,'fetch_all',return_value=result if result is not None else batch()), \
             patch.object(rss_client,'to_articles',return_value=list(articles)):
            return runner.run(self.out)
    def snapshot(self):
        return json.loads((self.out/'snapshot.json').read_text())

    def test_existing_normalizer_script(self):
        result = subprocess.run([sys.executable,str(Path(__file__).with_name('test_normalizer.py'))],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_same_cycle_merge_and_repeated_url(self):
        second = {**ARTICLE,'url':'https://beta.example/story','domain':'beta.example'}
        mf = self.run_cycle([ARTICLE,second,ARTICLE])
        self.assertEqual(mf['counts']['events'],1)
        self.assertEqual(mf['counts']['merged'],1)
        self.assertEqual(mf['counts']['deduped'],1)
        ev = self.snapshot()['events'][0]
        self.assertEqual(len(ev['sources']),2)
        self.assertEqual(ev['sources'],ev['score']['corroboration']['sources'])
        mf = self.run_cycle([ARTICLE,second])
        self.assertEqual(mf['counts']['deduped'],2)
        self.assertEqual(self.snapshot()['events'][0]['id'],ev['id'])

    def test_same_url_with_changed_title_does_not_create_new_event(self):
        self.run_cycle([ARTICLE])
        self.run_cycle([{**ARTICLE,'title':'Frankfurt ransomware incident: a different headline'}])
        self.assertEqual(len(self.snapshot()['events']),1)

    def test_all_sources_fail_retains_data_and_last_success(self):
        mf = self.run_cycle([ARTICLE])
        before = self.snapshot()['events']
        with patch.object(runner,'_now_ms',return_value=mf['lastSync']+3600000):
            failure = self.run_cycle(result=batch(0,['BBC','CISA']))
        self.assertEqual(failure['health']['status'],'error')
        self.assertEqual(failure['lastSync'],mf['lastSync'])
        self.assertGreater(failure['lastAttempt'],failure['lastSync'])
        self.assertEqual(self.snapshot()['events'],before)
        validate_snapshot(self.snapshot())

    def test_partial_failure_and_successful_empty_feed_are_distinct(self):
        partial = self.run_cycle(result=batch(1,['BBC']))
        self.assertEqual(partial['health']['status'],'degraded')
        self.assertGreater(partial['lastSync'],0)
        empty = self.run_cycle(result=batch())
        self.assertEqual(empty['health']['status'],'ok')
        self.assertEqual(empty['counts']['events'],0)
        validate_snapshot(self.snapshot())

    def test_never_successful_has_zero_last_sync(self):
        mf = self.run_cycle(result=batch(0,['RSS']))
        self.assertEqual(mf['lastSync'],0)
        self.assertEqual(mf['health']['status'],'error')

    def test_high_water_id_survives_pruning(self):
        self.run_cycle([ARTICLE])
        snap = self.snapshot()
        high = copy.deepcopy(snap['events'][0]); high['id']=99; high['ingestedAt']=1
        high['sources']=['https://old.example/story']; high['title']='Old ransomware report in Frankfurt'
        snap['events'].append(high)
        snap['manifest']['counts'] = runner._counts(snap['events'])
        snap['manifest']['nextEventId']=100
        runner._publish(self.out,snap['events'],snap['manifest'])
        with patch.object(runner,'MAX_EVENTS',1):
            self.run_cycle()
        self.assertEqual(len(self.snapshot()['events']),1)
        self.run_cycle([{**ARTICLE,'title':'A different ransomware attack in Frankfurt','url':'https://new.example/story'}])
        self.assertIn(100,[e['id'] for e in self.snapshot()['events']])

    def test_invalid_input_is_rejected_and_previous_snapshot_is_preserved(self):
        self.run_cycle([ARTICLE])
        before = self.snapshot()['events']
        result = self.run_cycle([{**ARTICLE,'url':'javascript:alert(1)'}])
        self.assertEqual(self.snapshot()['events'][0]['id'],before[0]['id'])
        validate_snapshot(self.snapshot())
        (self.out/'snapshot.json').write_text('{broken')
        with self.assertRaises(json.JSONDecodeError):
            self.run_cycle([ARTICLE])
        self.assertEqual((self.out/'snapshot.json').read_text(),'{broken')

    def test_atomic_replacement_failure_keeps_previous_snapshot(self):
        self.run_cycle([ARTICLE])
        before = (self.out/'snapshot.json').read_bytes()
        with patch.object(runner.os,'replace',side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                runner._atomic_write(self.out/'snapshot.json',{'broken':True})
        self.assertEqual((self.out/'snapshot.json').read_bytes(),before)
        self.assertEqual(list(self.out.glob('.snapshot.json.*')),[])

    def test_snapshot_only_never_fetches_or_claims_new_sync(self):
        mf = self.run_cycle([ARTICLE])
        (self.out/'snapshot.json').unlink()
        with patch.object(rss_client,'fetch_all',side_effect=AssertionError('must not fetch')):
            migrated = runner.run(self.out,snapshot_only=True)
        self.assertEqual(migrated['lastSync'],mf['lastSync'])
        validate_snapshot(self.snapshot())

    def test_rss_health_tracks_parse_errors_and_valid_empty_feeds(self):
        feeds = [{'name':'good','url':'https://good.example/rss','topic':'cyber'}, {'name':'bad','url':'https://bad.example/rss','topic':'cyber'}]
        with patch.object(rss_client,'FEEDS',feeds), patch.object(rss_client.time,'sleep'), \
             patch.object(rss_client,'_fetch_one',side_effect=[b'<rss><channel/></rss>',b'<html>error</html>']):
            result = rss_client.fetch_all()
        self.assertEqual(result.succeeded,1)
        self.assertEqual(result.failed,['bad'])
        self.assertEqual(list(result),[])

    def test_unsupported_schema_assertions_fail_closed(self):
        with self.assertRaises(ValueError):
            validate('hello',{'type':'string','unknownRule':True})


if __name__ == '__main__':
    unittest.main()
