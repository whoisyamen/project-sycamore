import { test } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { threatView } from '../src/data/threat';
import { threatDesk } from '../src/client/threat';
import { applyDeskPage } from '../src/client/desk';
import { event, now } from './fixtures';

test('threat desk distinguishes text matches, ingest time, and represented sources', () => {
  const events = [
    {
      ...event,
      id: 2,
      title: 'CVE-2026-12345 exploited in the wild',
      src: '<unsafe outlet>',
      ts: now - 10 * 86400000,
      ingestedAt: now - 3600000,
    },
    { ...event, id: 3, title: 'New privacy law passed', ingestedAt: now - 3 * 86400000 },
    { ...event, id: 4, title: 'Another report', ingestedAt: now + 3600000 },
  ];
  const view = threatView(events, now);
  assert.deepEqual(
    view.vulnerabilities.map((e) => e.id),
    [2],
  );
  assert.deepEqual(
    view.policy.map((e) => e.id),
    [3],
  );
  assert.deepEqual(
    view.emerging.map((e) => e.id),
    [2],
  );
  assert.deepEqual(view.sources, [
    ['Example News', 2],
    ['<unsafe outlet>', 1],
  ]);
  const html = threatDesk(events, now);
  assert.match(html, /\/?event=2/);
  assert.match(html, /&lt;unsafe outlet&gt;/);
  assert.doesNotMatch(html, /<unsafe outlet>/);
});

test('threat desk is the single reading surface for boards and briefings', () => {
  const html = threatDesk([event], now);
  const doc = new JSDOM(html).window.document;
  assert.ok(doc.querySelector('section#vulnerabilities'));
  assert.ok(doc.querySelector('section#policy'));
  assert.ok(doc.querySelector('section#emerging'));
  assert.ok(doc.querySelector('section#boards'));
  assert.ok(doc.querySelector('section#briefing'));
  assert.ok(doc.querySelector('section#sources'));
  // Topic groups and time windows from the retired pages now render here.
  assert.equal(doc.querySelectorAll('.board-group').length, 4);
  assert.equal(doc.querySelectorAll('.briefing-window').length, 3);
});

test('threat desk monitor tiles page so topic boards stay within reach', () => {
  const events = Array.from({ length: 5 }, (_, index) => ({
    ...event,
    id: index + 1,
    title: `CVE-2026-1000${index} exploited`,
    ts: now - index * 1000,
  }));
  const doc = new JSDOM(threatDesk(events, now)).window.document;
  const section = doc.querySelector<HTMLElement>('#vulnerabilities');
  assert.ok(section);
  assert.equal(section.querySelectorAll('.event-card:not([hidden])').length, 3);
  assert.equal(section.querySelectorAll('.event-card[hidden]').length, 2);
  assert.equal(section.querySelector('[data-desk-more]')?.textContent, 'Load 2 more');
  assert.equal(doc.querySelectorAll('#board-cyber .event-card[hidden]').length, 2);
  assert.equal(doc.querySelector('#briefing [hidden]'), null);
  assert.equal(doc.querySelector('#sources [hidden]'), null);
  applyDeskPage(section, 6);
  assert.equal(section.querySelectorAll('.event-card[hidden]').length, 0);
  assert.equal((section.querySelector('[data-desk-more]') as HTMLElement).hidden, true);
});
