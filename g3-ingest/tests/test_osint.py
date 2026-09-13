"""Offline OSINT contract and last-good publication regressions."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sycamore_ingest import flight_client as flights, censys_client as censys, runner


def row(lon=12, lat=48, contact=1000):
    return ['abc123', 'TEST ', 'Germany', contact, contact, lon, lat, 1000, False, 100, 90, 0]


class OsintTests(unittest.TestCase):
    def test_flight_first_fix_survives_and_builds_a_trail(self):
        first = flights.build_envelope({'time': 1000, 'states': [row()]})
        self.assertEqual(first['trails']['abc123'], [[12, 48, 1000000]])
        second = flights.build_envelope({'time': 1030, 'states': [row(13, contact=1030)]}, first)
        self.assertEqual(len(second['trails']['abc123']), 2)
        self.assertEqual(second['aircraft'][0]['cs'], 'TEST')

    def test_invalid_and_stale_fixes_are_dropped(self):
        states = [row(None), row(181), row(contact=900), row(contact=None), row(float('nan'))]
        result = flights.build_envelope({'time': 1000, 'states': states})
        self.assertEqual(result['count'], 0)

    def test_trails_expire_and_remain_bounded(self):
        previous = {'trails': {'abc123': [[1, 2, 0]]}}
        for i in range(20):
            previous = flights.build_envelope({'time': 1000+i, 'states': [row(10+i/10, contact=1000+i)]}, previous)
        self.assertEqual(len(previous['trails']['abc123']), flights.TRAIL_POINTS)
        self.assertGreater(previous['trails']['abc123'][0][2], 0)

    def test_censys_country_and_dateline_query(self):
        self.assertEqual(censys.build_query({'kind': 'country', 'country_code': 'de'})[0], 'host.location.country_code="DE"')
        query, limit = censys.build_query({'kind': 'bbox', 'west': 179, 'east': -179, 'south': -18, 'north': -16})
        self.assertTrue(query.startswith('geo_distance(host.location.coordinates,-17.000,-180.000,'))
        self.assertLess(int(query.rsplit(',', 1)[1].removesuffix('km)')), 200)
        self.assertEqual(limit, 12)
        with self.assertRaises(ValueError):
            censys.build_query({'kind': 'country', 'name': ''})

    def test_censys_platform_search_request_and_response(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({'result': {'hits': [
            {'host_v1': {'resource': {'ip': '192.0.2.1', 'services': [{'port': 443}, {'port': 443}], 'location': {'coordinates': {'latitude': 48, 'longitude': 12}, 'country_code': 'DE'}}}},
            {'host_v1': {'resource': {'ip': '192.0.2.2', 'location': {'coordinates': {'latitude': None}}}}},
        ]}}).encode()
        with patch.dict(censys.os.environ, {'CENSYS_ORGANIZATION_ID': '11111111-2222-3333-4444-555555555555'}), patch.object(censys.urllib.request, 'urlopen', return_value=response) as request:
            hosts = censys.fetch_region('test-key', {'kind': 'country', 'country_code': 'DE'})
        sent = request.call_args.args[0]
        self.assertEqual(sent.get_method(), 'POST')
        self.assertEqual(sent.get_header('Authorization'), 'Bearer test-key')
        self.assertEqual(sent.full_url, censys.API + '?organization_id=11111111-2222-3333-4444-555555555555')
        self.assertNotIn('test-key', sent.full_url)
        self.assertEqual(json.loads(sent.data), {'query': 'host.location.country_code="DE"', 'page_size': 12, 'fields': ['host.ip', 'host.location', 'host.services.port']})
        self.assertEqual(hosts, [{'ip': '192.0.2.1', 'lon': 12, 'lat': 48, 'country_code': 'DE', 'ports': [443]}])

    def test_censys_rejects_bad_responses_but_accepts_empty_search(self):
        for payload in [{}, {'result': {}}, {'result': {'hits': None}}, {'result': {'hits': [{'host': {}}]}}]:
            response = MagicMock()
            response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
            with self.subTest(payload=payload), patch.object(censys.urllib.request, 'urlopen', return_value=response):
                with self.assertRaises(censys.CensysUnavailable):
                    censys.fetch_region('test-key', {'kind': 'country', 'country_code': 'DE'})
        for hits in [[], None]:
            response.__enter__.return_value.read.return_value = json.dumps({'result': {'hits': hits, 'total_hits': 0}}).encode()
            with patch.object(censys.urllib.request, 'urlopen', return_value=response):
                self.assertEqual(censys.fetch_region('test-key', {'kind': 'country', 'country_code': 'DE'}), [])

    def test_censys_drops_invalid_coordinates_and_ips(self):
        for lat, lon, ip in [(None, 12, '192.0.2.1'), (True, 12, '192.0.2.1'), (float('nan'), 12, '192.0.2.1'), (48, 181, '192.0.2.1'), (48, 12, 'invalid'), (48, 12, True)]:
            self.assertIsNone(censys.normalize_host({'ip': ip, 'location': {'coordinates': {'latitude': lat, 'longitude': lon}}}))

    def test_censys_requires_its_own_token(self):
        with patch.dict(censys.os.environ, {'SHODAN_API_KEY': 'old-key'}, clear=True), patch.object(censys.urllib.request, 'urlopen') as request:
            self.assertIsNone(censys._api_key())
            with self.assertRaises(censys.CensysUnavailable):
                censys.fetch_region(None, {'kind': 'country', 'country_code': 'US'})
            request.assert_not_called()

    def test_censys_missing_configuration_is_absent(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(flights, 'fetch_states', return_value={'time':1000, 'states': []}), patch.object(censys, '_api_key', return_value='test-key'), patch.object(censys, 'fetch_region') as fetch:
            self.assertEqual(runner._osint_cycle(Path(folder)), [])
            fetch.assert_not_called()
            self.assertTrue((Path(folder)/'flights.json').exists())

    def test_censys_errors_are_actionable_without_leaking_key(self):
        url = censys.API
        errors = [
            (censys.urllib.error.HTTPError(url, 403, 'secret-key', {}, None), 'API Access role'),
            (censys.urllib.error.URLError('secret-key'), 'URLError'),
        ]
        for error, expected in errors:
            with self.subTest(error=type(error).__name__), patch.object(censys.urllib.request, 'urlopen', side_effect=error):
                with self.assertRaises(censys.CensysUnavailable) as raised:
                    censys.fetch_region('secret-key', {'kind': 'country', 'country_code': 'US'})
                self.assertIn(expected, str(raised.exception))
                self.assertNotIn('secret-key', str(raised.exception))

    def test_censys_invalid_or_empty_regions_preserve_previous(self):
        for regions, expected in [({}, ['Censys hosts']), ([None], ['Censys hosts']), ([], [])]:
            with self.subTest(regions=regions), tempfile.TemporaryDirectory() as folder:
                out = Path(folder)
                (out/'regions.json').write_text(json.dumps(regions))
                (out/'censys.json').write_text('{"previous":true}')
                with patch.object(flights, 'fetch_states', return_value={'time':1000, 'states': []}), patch.object(censys, '_api_key', return_value='test-key'), patch.object(censys, 'fetch_region') as fetch:
                    self.assertEqual(runner._osint_cycle(out), expected)
                    fetch.assert_not_called()
                self.assertEqual((out/'censys.json').read_text(), '{"previous":true}')

    def test_censys_cycle_publishes_with_configured_key_and_regions(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            region = {'kind': 'country', 'country_code': 'US'}
            (out/'regions.json').write_text(json.dumps({'regions': [region]}))
            with patch.object(flights, 'fetch_states', return_value={'time':1000, 'states': []}), patch.dict(censys.os.environ, {'CENSYS_PERSONAL_ACCESS_TOKEN': 'test-key'}), patch.object(censys, 'fetch_region', return_value=[{'ip':'192.0.2.1', 'lat':40, 'lon':-75, 'ports':[443]}]) as fetch:
                self.assertEqual(runner._osint_cycle(out), [])
                fetch.assert_called_once_with('test-key', region)
            self.assertEqual(json.loads((out/'censys.json').read_text())['count'], 1)

    def test_failure_retains_previous_files(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            (out/'flights.json').write_text('{"previous":true}')
            (out/'censys.json').write_text('{"previous":true}')
            (out/'regions.json').write_text('[{"kind":"country","country_code":"DE"}]')
            with patch.object(flights, 'fetch_states', side_effect=OSError()), patch.object(censys, '_api_key', return_value='test-key'), patch.object(censys, 'fetch_region', side_effect=censys.CensysUnavailable('offline')):
                self.assertEqual(runner._osint_cycle(out), ['OpenSky flights', 'Censys hosts'])
            self.assertEqual((out/'flights.json').read_text(), '{"previous":true}')
            self.assertEqual((out/'censys.json').read_text(), '{"previous":true}')
