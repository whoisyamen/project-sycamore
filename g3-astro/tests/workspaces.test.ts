import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { JSDOM } from 'jsdom';
import { initReporting } from '../src/client/reporting';
import { initNocturne } from '../src/client/nocturne';
import { event, snapshot } from './fixtures';

async function page(route: string) {
  const html = await readFile(new URL(`../dist/${route}/index.html`, import.meta.url), 'utf8');
  const dom = new JSDOM(html, { url: `https://site.example/${route}`, pretendToBeVisual: true });
  const win = dom.window;
  for (const key of [
    'window',
    'document',
    'location',
    'history',
    'HTMLElement',
    'HTMLAnchorElement',
    'HTMLButtonElement',
    'HTMLInputElement',
    'CustomEvent',
  ] as const) {
    Object.defineProperty(globalThis, key, {
      value: key === 'window' ? win : win[key],
      configurable: true,
    });
  }
  Object.defineProperty(globalThis, 'navigator', { value: win.navigator, configurable: true });
  win.HTMLElement.prototype.scrollIntoView = () => {};
  return dom;
}

test('reporting index preserves source context across filters, refresh, sharing and keyboard close', async () => {
  const dom = await page('reporting');
  const doc = dom.window.document;
  const context = {
    events: [
      event,
      { ...event, id: 2, t: 'maritime' as const, title: 'Shipping report', src: '<unsafe outlet>' },
    ],
    manifest: snapshot().manifest,
    demo: false,
  };
  initReporting(context);
  const click = (selector: string) => doc.querySelector<HTMLElement>(selector)!.click();
  assert.equal(doc.querySelectorAll('.report-row').length, 2);
  assert.equal(doc.querySelector('unsafe'), null);
  click('[data-select-event="1"]');
  assert.equal(doc.querySelector('[data-select-event="1"]')?.getAttribute('aria-expanded'), 'true');
  assert.equal((doc.getElementById('report-context-1') as HTMLElement).hidden, false);
  assert.equal(new URL(dom.window.location.href).pathname, '/reporting');
  const source = doc.getElementById('source') as HTMLSelectElement;
  source.value = '<unsafe outlet>';
  source.dispatchEvent(new dom.window.Event('change'));
  assert.equal((doc.getElementById('index-selection-note') as HTMLElement).hidden, false);
  assert.ok(doc.querySelector('.expanded [data-select-event="1"]'));
  click('[data-share-report="1"]');
  await new Promise((resolve) => setTimeout(resolve, 0));
  const shared = new URL(doc.querySelector<HTMLInputElement>('.share-fallback')!.value);
  assert.equal(shared.pathname, '/reporting');
  assert.equal(shared.searchParams.get('event'), '1');
  assert.equal(shared.searchParams.get('src'), '<unsafe outlet>');
  const update = snapshot([
    { ...event, title: 'Updated source report' },
    { ...event, id: 3, src: 'New Source' },
  ]);
  doc.dispatchEvent(new dom.window.CustomEvent('sycamore:snapshot', { detail: update }));
  assert.match(doc.querySelector('[data-select-event="1"]')!.textContent!, /Updated source report/);
  assert.ok([...source.options].some((option) => option.value === 'New Source'));
  assert.equal(source.value, '<unsafe outlet>');
  doc.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  assert.equal(new URL(dom.window.location.href).searchParams.has('event'), false);
  click('#reset-filters');
  const row = doc.querySelector<HTMLElement>('[data-select-event="1"]')!;
  row.focus();
  row.click();
  doc.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  assert.equal(doc.activeElement?.getAttribute('data-select-event'), '1');
  doc.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: '/', bubbles: true }));
  assert.equal(doc.activeElement?.id, 'search');
  assert.ok(doc.querySelector('#report-context-1 a[rel="noopener noreferrer"]'));
  const retained = Array.from({ length: 101 }, (_, index) => ({
    ...event,
    id: index + 1,
    ts: event.ts - index,
  }));
  doc.dispatchEvent(
    new dom.window.CustomEvent('sycamore:snapshot', { detail: snapshot(retained) }),
  );
  assert.equal(doc.querySelectorAll('.report-row').length, 50);
  click('#reporting-more');
  assert.equal(doc.querySelectorAll('.report-row').length, 100);
  click('#reporting-more');
  assert.equal(doc.querySelectorAll('.report-row').length, 101);
  assert.equal((doc.getElementById('reporting-more') as HTMLElement).hidden, true);
  assert.equal(doc.activeElement?.getAttribute('data-select-event'), '101');
  dom.window.close();
});

test('Nocturne lenses, search and old section links survive refreshed reporting', async () => {
  const dom = await page('intelligence');
  const doc = dom.window.document;
  const current = Date.now();
  const events = [
    {
      ...event,
      title: 'CVE-2026-12345 vulnerability report',
      ts: current - 1000,
      ingestedAt: current - 2000,
    },
    {
      ...event,
      id: 2,
      title: 'Policy regulation report',
      ts: current - 2000,
      ingestedAt: current - 3 * 86400000,
    },
  ];
  const context = { events, manifest: snapshot(events).manifest, demo: false };
  initNocturne(context);
  const click = (selector: string) => doc.querySelector<HTMLElement>(selector)!.click();
  click('[data-desk-lens="emerging"]');
  assert.equal(doc.querySelectorAll('.editorial-card').length, 1);
  assert.match(doc.querySelector('.editorial-lead h2')!.textContent!, /CVE/);
  const search = doc.getElementById('search') as HTMLInputElement;
  search.value = 'missing';
  search.dispatchEvent(new dom.window.Event('input'));
  assert.ok(doc.querySelector('.editorial-empty'));
  click('#desk-reset');
  click('.reading-lenses a[href="#policy"]');
  assert.equal((doc.getElementById('policy') as HTMLElement).hidden, false);
  assert.equal((doc.getElementById('vulnerabilities') as HTMLElement).hidden, true);
  assert.equal(new URL(dom.window.location.href).searchParams.get('lens'), 'policy');
  const link = doc.querySelector<HTMLAnchorElement>('#policy .event-card')!;
  link.focus();
  const updated = snapshot(events.map((event) => ({ ...event, title: event.title + ' updated' })));
  doc.dispatchEvent(new dom.window.CustomEvent('sycamore:snapshot', { detail: updated }));
  assert.equal((doc.getElementById('policy') as HTMLElement).hidden, false);
  assert.equal((doc.activeElement as HTMLAnchorElement).href, link.href);
  assert.match(doc.querySelector('.editorial-lead h2')!.textContent!, /updated/);
  assert.ok(doc.querySelector('.editorial-source-link[rel="noopener noreferrer"]'));
  dom.window.close();
});
