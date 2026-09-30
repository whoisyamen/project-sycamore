import { test } from 'node:test';
import assert from 'node:assert/strict';
import { defaults, filterEvents, readState, stateUrl } from '../src/client/state';
import { dataStatus } from '../src/data/status';
import { event, now, snapshot } from './fixtures';

test('combines query, topic, severity and time filters without mutating input', () => {
  const events = [
    event,
    { ...event, id: 2, t: 'maritime' as const },
    { ...event, id: 3, ts: now - 8 * 86400000 },
  ];
  const state = {
    ...defaults,
    q: 'LONDON',
    topic: 'cyber' as const,
    sev: 'watching' as const,
    range: '24h' as const,
  };
  assert.deepEqual(
    filterEvents(events, state, now).map((e) => e.id),
    [1],
  );
  assert.equal(events.length, 3);
  assert.deepEqual(filterEvents(events, { ...state, q: 'missing' }, now), []);
});
test('time boundaries and future timestamps are handled explicitly', () => {
  assert.equal(
    filterEvents([{ ...event, ts: now - 86400000 }], { ...defaults, range: '24h' }, now).length,
    1,
  );
  assert.equal(
    filterEvents([{ ...event, ts: now + 1 }], { ...defaults, range: '24h' }, now).length,
    0,
  );
});
test('selection and every filter survive URL round-trip including special search characters', () => {
  const state = {
    ...defaults,
    topic: 'cyber' as const,
    sev: 'critical' as const,
    mode: 'pulse' as const,
    range: '7d' as const,
    q: 'A & B / C',
    event: 45,
  };
  const url = stateUrl(state, 'https://site.example/boards/2');
  assert.equal(url.pathname, '/');
  assert.deepEqual(readState(url), state);
});
test('threat lens, source, sort and view filters combine and survive the URL', () => {
  const events = [
    event,
    { ...event, id: 2, sev: 'critical' as const, src: 'Wire Service', ts: now - 7200000 },
    { ...event, id: 3, title: 'New privacy regulation passed' },
  ];
  const state = {
    ...defaults,
    lens: 'policy' as const,
    src: 'Example News',
    sort: 'severity' as const,
    view: 'feed' as const,
  };
  assert.deepEqual(readState(stateUrl(state, 'https://site.example/')), state);
  // Lens and source combine: only the policy item from the selected source remains.
  assert.deepEqual(
    filterEvents(events, state, now).map((e) => e.id),
    [3],
  );
  assert.deepEqual(
    filterEvents(events, { ...state, lens: 'all' }, now).map((e) => e.id),
    [3, 1],
  );
  assert.deepEqual(filterEvents(events, { ...defaults, lens: 'vulnerabilities' }, now), []);
  assert.deepEqual(filterEvents(events, { ...defaults, lens: 'emerging' }, now), []);
  assert.deepEqual(
    filterEvents(events, { ...defaults, src: 'Wire Service' }, now).map((e) => e.id),
    [2],
  );
  assert.deepEqual(
    filterEvents(events, { ...defaults, sort: 'oldest' }, now).map((e) => e.id),
    [2, 1, 3],
  );
});
test('legacy event hashes and mode links restore; invalid input defaults safely', () => {
  assert.equal(readState(new URL('https://site.example/#event/12')).event, 12);
  assert.equal(readState(new URL('https://site.example/?mode=pulse')).mode, 'pulse');
  assert.deepEqual(
    readState(new URL('https://site.example/?topic=no&range=no&event=NaN')),
    defaults,
  );
  assert.equal(readState(new URL('https://site.example/?event=999999999999999999')).event, null);
});
test('freshness separates successful checks, failed attempts, staleness, and demo', () => {
  const mf = snapshot().manifest;
  assert.equal(dataStatus(mf, false, false, now).kind, 'ok');
  assert.equal(dataStatus(mf, false, false, now + 30 * 60000).kind, 'delayed');
  assert.equal(
    dataStatus({ ...mf, lastAttempt: now + 40 * 60000 }, false, false, now + 40 * 60000).kind,
    'delayed',
  );
  assert.equal(
    dataStatus({ ...mf, health: { status: 'degraded' } }, false, false, now).label,
    'Some sources unavailable',
  );
  assert.equal(dataStatus({ ...mf, health: { status: 'error' } }, false, false, now).kind, 'error');
  assert.equal(dataStatus(null).kind, 'error');
  assert.equal(dataStatus(null, true).kind, 'demo');
});
