import { test } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { readFile } from 'node:fs/promises';
import { initDashboard } from '../src/client/dashboard';
import type { Event } from '../src/data/types';
import { event, snapshot } from './fixtures';

test('dashboard filters, selects, shares, refreshes and remains usable without WebGL', async () => {
  // Exercise the real generated page and controller; the map adapter is the only stub.
  const html = await readFile(new URL('../dist/index.html', import.meta.url), 'utf8');
  const dom = new JSDOM(html, { url: 'https://site.example/', pretendToBeVisual: true });
  const window = dom.window;
  for (const key of [
    'window',
    'document',
    'location',
    'history',
    'HTMLElement',
    'HTMLAnchorElement',
    'CustomEvent',
  ] as const)
    Object.defineProperty(globalThis, key, {
      value: key === 'window' ? window : window[key],
      configurable: true,
    });
  Object.defineProperty(globalThis, 'navigator', { value: window.navigator, configurable: true });
  Object.defineProperty(window, 'matchMedia', {
    value: () => ({ matches: true, addEventListener() {} }),
  });
  const context = {
    events: [
      event,
      { ...event, id: 2, t: 'maritime' as const, title: 'Shipping disruption near London' },
    ],
    manifest: snapshot().manifest,
    demo: false,
  };
  let shown: Event[] = [];
  const presentationStates: boolean[] = [];
  const suspendedStates: boolean[] = [];
  initDashboard(context, () => ({
    update(events) {
      shown = events;
    },
    focus() {},
    resize() {},
    setPresentationMode(enabled) {
      presentationStates.push(enabled);
    },
    setSuspended(suspended) {
      suspendedStates.push(suspended);
    },
    destroy() {},
  }));
  const document = window.document;
  const click = (selector: string) => (document.querySelector(selector) as HTMLElement).click();
  assert.equal(document.querySelectorAll('#feed-list .event-card').length, 2);
  assert.equal(document.getElementById('main')?.dataset.tab, 'map');
  assert.equal(
    document.querySelector('.view-tabs [data-tab="map"]')?.getAttribute('aria-pressed'),
    'true',
  );
  click('[data-map-fullscreen]');
  assert.equal(document.getElementById('main')?.classList.contains('map-presentation'), true);
  assert.equal(
    document.querySelector('[data-map-fullscreen]')?.getAttribute('aria-pressed'),
    'true',
  );
  assert.equal(presentationStates.at(-1), true);
  click('[data-map-fullscreen]');
  assert.equal(document.getElementById('main')?.classList.contains('map-presentation'), false);
  assert.equal(
    document.querySelector('[data-map-fullscreen]')?.getAttribute('aria-pressed'),
    'false',
  );
  assert.equal(presentationStates.at(-1), false);
  click('.view-tabs [data-tab="feed"]');
  assert.equal(document.getElementById('main')?.dataset.tab, 'feed');
  assert.equal(
    document.querySelector('.view-tabs [data-tab="feed"]')?.getAttribute('aria-pressed'),
    'true',
  );
  assert.equal(new URL(window.location.href).searchParams.get('view'), 'feed');
  assert.equal(suspendedStates.at(-1), true);
  click('[data-topic="cyber"]');
  assert.equal(shown.length, 1);
  assert.equal(new URL(window.location.href).searchParams.get('topic'), 'cyber');
  click('[data-lens="policy"]');
  assert.equal(document.querySelectorAll('#feed-list .event-card').length, 0);
  assert.equal(new URL(window.location.href).searchParams.get('lens'), 'policy');
  click('[data-lens="all"]');
  assert.equal(document.querySelectorAll('#feed-list .event-card').length, 1);
  const first = document.querySelector<HTMLElement>('#feed-list a')!;
  first.focus();
  first.click();
  assert.equal(document.getElementById('detail-panel')?.hidden, false);
  assert.equal(document.getElementById('detail-panel')?.getAttribute('aria-modal'), 'true');
  assert.equal(document.querySelector<HTMLElement>('.feed-panel')!.inert, true);
  assert.equal(new URL(window.location.href).searchParams.get('event'), '1');
  click('#share-event');
  await new Promise((r) => setTimeout(r, 0));
  const fallback = document.querySelector<HTMLInputElement>('.share-fallback')!;
  assert.ok(fallback.value.includes('event=1') && fallback.value.includes('topic=cyber'));
  assert.doesNotMatch(document.getElementById('share-status')!.textContent!, /Link copied/);
  const updated = snapshot([
    { ...event, title: 'Updated infrastructure advisory for London' },
    { ...event, id: 99, src: 'Another Source' },
  ]);
  context.events = updated.events;
  document.dispatchEvent(new window.CustomEvent('sycamore:snapshot', { detail: updated }));
  assert.equal(
    document.querySelector('#detail-title')?.textContent,
    'Updated infrastructure advisory for London',
  );
  assert.equal(new URL(window.location.href).searchParams.get('event'), '1');
  const sourceSelect = document.getElementById('source') as HTMLSelectElement;
  assert.ok([...sourceSelect.options].some((option) => option.value === 'Another Source'));
  sourceSelect.value = 'Another Source';
  sourceSelect.dispatchEvent(new window.Event('change'));
  assert.equal(document.querySelectorAll('#feed-list .event-card').length, 1);
  assert.equal(new URL(window.location.href).searchParams.get('src'), 'Another Source');
  click('#reset-filters');
  assert.equal(document.querySelectorAll('#feed-list .event-card').length, 2);
  const sortSelect = document.getElementById('sort') as HTMLSelectElement;
  sortSelect.value = 'oldest';
  sortSelect.dispatchEvent(new window.Event('change'));
  assert.equal(document.querySelector('#feed-list a')?.getAttribute('data-event'), '1');
  click('#reset-filters');
  click('#close-detail');
  assert.equal(document.getElementById('detail-panel')?.hidden, true);
  assert.equal((document.activeElement as HTMLElement).dataset.event, '1');
  const search = document.getElementById('search') as HTMLInputElement;
  search.value = 'no match';
  search.dispatchEvent(new window.Event('input'));
  assert.equal(document.querySelectorAll('#feed-list .event-card').length, 0);
  click('#reset-filters');
  click('#feed-list [data-event="99"]');
  assert.equal(new URL(window.location.href).searchParams.get('event'), '99');
  document.dispatchEvent(new window.CustomEvent('sycamore:snapshot', { detail: snapshot([]) }));
  assert.equal(document.getElementById('detail-panel')?.hidden, true);
  assert.equal(document.getElementById('selection-notice')?.hidden, false);
  assert.equal(document.activeElement, search);
  dom.window.close();
});

test('map initialization failure preserves feed interaction and legacy deep links', async () => {
  const html = await readFile(new URL('../dist/index.html', import.meta.url), 'utf8');
  const dom = new JSDOM(html, { url: 'https://site.example/#event/1', pretendToBeVisual: true });
  const window = dom.window;
  for (const key of [
    'window',
    'document',
    'location',
    'history',
    'HTMLElement',
    'HTMLAnchorElement',
    'CustomEvent',
  ] as const)
    Object.defineProperty(globalThis, key, {
      value: key === 'window' ? window : window[key],
      configurable: true,
    });
  Object.defineProperty(globalThis, 'navigator', { value: window.navigator, configurable: true });
  Object.defineProperty(window, 'matchMedia', {
    value: () => ({ matches: true, addEventListener() {} }),
  });
  initDashboard({ events: [event], manifest: snapshot().manifest, demo: false }, () => {
    throw new Error('No WebGL');
  });
  const doc = window.document;
  assert.equal(doc.getElementById('map-error')?.hidden, false);
  assert.equal(doc.getElementById('detail-panel')?.hidden, false);
  const close = doc.getElementById('close-detail')!;
  close.focus();
  close.dispatchEvent(
    new window.KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }),
  );
  assert.equal(doc.activeElement, doc.getElementById('share-event'));
  doc.activeElement!.dispatchEvent(
    new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }),
  );
  assert.equal(doc.getElementById('detail-panel')?.hidden, true);
  (doc.querySelector('#feed-list a') as HTMLElement).click();
  assert.equal(doc.getElementById('detail-panel')?.hidden, false);
  let copied = '';
  Object.defineProperty(window.navigator, 'clipboard', {
    value: {
      async writeText(value: string) {
        copied = value;
      },
    },
  });
  doc.getElementById('share-event')!.click();
  await new Promise((r) => setTimeout(r, 0));
  assert.ok(copied.includes('event=1'));
  assert.equal(doc.getElementById('share-status')!.textContent, 'Link copied');
  dom.window.close();
});
