"""Independent local data acceptance probe. Run after the geolocation migration."""
import json
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'g3-ingest'))
from sycamore_ingest.contracts import validate_snapshot


def get(name):
    with urlopen('http://localhost:4321/data/' + name, timeout=10) as response:
        assert response.status == 200
        return json.load(response)

snapshot = get('snapshot.json')
validate_snapshot(snapshot)
assert snapshot['events'] == get('events.json'), 'HTTP event mirror differs from canonical snapshot'
assert snapshot['manifest'] == get('manifest.json'), 'HTTP manifest mirror differs from canonical snapshot'
assert snapshot == json.loads((ROOT / 'g3-astro/public/data/snapshot.json').read_text()), 'HTTP and source snapshot disagree'
west_bank = [e for e in snapshot['events'] if e['id'] == 36]
assert len(west_bank) == 1, 'Original West Bank event ID 36 missing or duplicated'
e = west_bank[0]
assert 31 < e['lat'] < 33 and 34 < e['lon'] < 36, 'West Bank marker is outside its region'
assert e.get('geo', {}).get('tier') == 'approximate', 'West Bank incident site is not precisely verified'
unsafe = [e['id'] for e in snapshot['events'] if e.get('geo', {}).get('source') == 'nominatim']
assert not unsafe, f'Unchecked historical Nominatim markers remain: {unsafe}'
print(json.dumps({'status': 'passed', 'events': len(snapshot['events']), 'westBank': {k: e[k] for k in ('id', 'lat', 'lon', 'loc', 'geo')}, 'health': snapshot['manifest']['health'], 'checks': ['schema/counts/IDs', 'HTTP mirrors', 'HTTP vs source', 'West Bank regional location', 'no historical Nominatim pins']}, indent=2))
