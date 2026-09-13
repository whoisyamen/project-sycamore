import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseSnapshot } from '../src/data/validate';
import { acceptSnapshot, fetchSnapshot } from '../src/client/refresh';
import { event, snapshot, now } from './fixtures';
import { eventCard, eventDetail, briefing } from '../src/client/render';
import { JSDOM } from 'jsdom';

test('accepts shared optional fields and valid empty snapshots', () => {
  assert.equal(parseSnapshot(snapshot()).events[0].ingestedAt, undefined);
  assert.equal(parseSnapshot(snapshot([])).events.length, 0);
});
test('rejects invalid coordinates, scripts as source URLs, duplicates, and inconsistent counts', () => {
  assert.throws(() => parseSnapshot(snapshot([{ ...event, lat: 91 }])));
  assert.throws(() => parseSnapshot(snapshot([{ ...event, sources: ['javascript:alert(1)'] }])));
  assert.throws(() => parseSnapshot(snapshot([event, event])));
  const bad = snapshot();
  bad.manifest.counts.byTopic.cyber = 3;
  assert.throws(() => parseSnapshot(bad));
  assert.throws(() => parseSnapshot({ events: [] }));
});
test('failed and malformed fetches cannot replace last good data; older snapshots are ignored', async () => {
  const current = snapshot();
  const fetcher = async () =>
    new Response(JSON.stringify(snapshot([{ ...event, id: 2 }], now + 1000)));
  assert.equal((await fetchSnapshot(fetcher as typeof fetch)).events[0].id, 2);
  await assert.rejects(
    fetchSnapshot((async () => new Response('no', { status: 503 })) as typeof fetch),
  );
  await assert.rejects(fetchSnapshot((async () => new Response('{broken')) as typeof fetch));
  await assert.rejects(
    fetchSnapshot((async () => {
      throw new Error('offline');
    }) as typeof fetch),
  );
  assert.equal(acceptSnapshot(current, snapshot([], now - 1)), current);
  assert.equal(acceptSnapshot(current, snapshot([], now + 1)).events.length, 0);
});
test('event rendering escapes untrusted source text and emits real source links', () => {
  const hostile = {
    ...event,
    title: '<img src=x onerror=alert(1)>',
    summary: '</script><script>alert(1)</script>',
    src: '" onclick="bad',
  };
  const dom = new JSDOM(eventCard(hostile) + eventDetail(hostile));
  assert.equal(dom.window.document.querySelectorAll('script,img,[onclick]').length, 0);
  assert.equal(dom.window.document.querySelector('.summary')?.textContent, hostile.summary);
  assert.equal(
    dom.window.document.querySelector('.sources a')?.getAttribute('rel'),
    'noopener noreferrer',
  );
});
test('approximate location disclosure does not promise country or incident-site accuracy', () => {
  for (const loc of ['West Bank', 'Strait of Hormuz']) {
    const doc = new JSDOM(eventDetail({ ...event, loc })).window.document;
    assert.equal(
      doc.querySelector('.precision-note')?.textContent,
      'Approximate location — marker represents the named place or region, not a verified incident site. See original reporting for details.',
    );
  }
});

test('briefing uses event counts and reporting rather than invented narrative', () => {
  const dom = new JSDOM(briefing([event], now));
  assert.equal(dom.window.document.querySelectorAll('.briefing-window').length, 3);
  assert.equal(dom.window.document.querySelectorAll('.event-card').length, 3);
});

test('new board and briefing records link to the dashboard before static pages exist', async () => {
  const { boards } = await import('../src/client/render');
  const next = { ...event, id: 99 };
  for (const html of [
    boards([event, next], new Set([1])),
    briefing([event, next], now, new Set([1])),
  ]) {
    const doc = new JSDOM(html).window.document;
    assert.ok(doc.querySelector('a[href="/boards/1"]'));
    assert.ok(doc.querySelector('a[href="/?event=99"]'));
    assert.equal(doc.querySelector('a[href="/boards/99"]'), null);
  }
});
