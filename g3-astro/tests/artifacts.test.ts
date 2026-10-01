import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { JSDOM } from 'jsdom';
import { parseSnapshot } from '../src/data/validate';
const root = new URL('../dist/', import.meta.url);

test('built routes have valid local scripts, accessible landmarks and no retired controls', async () => {
  for (const path of [
    'index.html',
    'intelligence/index.html',
    'reporting/index.html',
    'outlooks/index.html',
  ]) {
    const html = await readFile(new URL(path, root), 'utf8');
    const doc = new JSDOM(html).window.document;
    assert.ok(doc.querySelector('main#main'));
    assert.ok(doc.querySelector('nav[aria-label]'));
    assert.ok(doc.querySelector('meta[name="viewport"]'));
    for (const script of doc.querySelectorAll('script')) {
      assert.equal(script.textContent?.trim(), '');
      assert.ok(script.getAttribute('src')?.startsWith('/_astro/'));
      await readFile(new URL(script.getAttribute('src')!.slice(1), root));
    }
    assert.equal(doc.querySelectorAll('[onclick],#compare-drawer,#watch-toggle').length, 0);
    assert.equal(doc.querySelectorAll('a[href="/outlooks"]').length, 0);
  }
  // Boards and Briefing were folded into the threat desk; only per-event pages remain.
  await assert.rejects(readFile(new URL('briefing/index.html', root)));
  await assert.rejects(readFile(new URL('boards/index.html', root)));
});
test('snapshot validates; generated event pages preserve existing links', async () => {
  const data = parseSnapshot(
    JSON.parse(await readFile(new URL('data/snapshot.json', root), 'utf8')),
  );
  for (const event of data.events) {
    const doc = new JSDOM(await readFile(new URL(`boards/${event.id}/index.html`, root), 'utf8'))
      .window.document;
    assert.equal(doc.querySelector('article h1')?.textContent, event.title);
    assert.ok(doc.querySelector(`a[href="/?event=${event.id}"]`));
  }
});
test('reading workspaces have geographic context; runtime validation needs no dynamic code generation', async () => {
  const dir = new URL('_astro/', root);
  const files = await readdir(dir);
  const js = await Promise.all(
    files.filter((f) => f.endsWith('.js')).map((f) => readFile(new URL(f, dir), 'utf8')),
  );
  const validator = await readFile(
    new URL('../src/data/generated-validator.js', import.meta.url),
    'utf8',
  );
  assert.doesNotMatch(validator, /new Function\(/);
  // A static build must not pull in Viewer's Knockout bootstrap: it evaluates
  // "this" during module import, before our map failure handler can attach.
  for (const code of js) {
    assert.doesNotMatch(code, /\(0,\s*eval\)\s*\(/);
    assert.doesNotMatch(code, /ko\.applyBindings/);
  }
  assert.ok(js.some((code) => code.includes('CesiumWidget') || code.includes('cesium-viewer')));
  const home = new JSDOM(await readFile(new URL('index.html', root), 'utf8')).window.document;
  const desk = new JSDOM(await readFile(new URL('intelligence/index.html', root), 'utf8')).window
    .document;
  const index = new JSDOM(await readFile(new URL('reporting/index.html', root), 'utf8')).window
    .document;
  assert.ok(home.querySelector('#map'));
  assert.ok(desk.querySelector('[data-context-globe]'));
  assert.ok(index.querySelector('[data-context-globe]'));
  for (const doc of [home, desk, index]) {
    assert.equal(doc.querySelectorAll('.site-header nav a').length, 3);
    assert.equal(doc.querySelectorAll('#search').length, 1);
    assert.equal(doc.querySelectorAll('.site-header nav a[aria-current="page"]').length, 1);
  }
});
test('deployment header template restricts scripts and prevents caching data snapshots', async () => {
  const headers = await readFile(new URL('_headers', root), 'utf8');
  assert.match(headers, /script-src 'self' 'wasm-unsafe-eval';/);
  assert.doesNotMatch(headers, /'unsafe-eval'/);
  assert.match(headers, /\/data\/\*[\s\S]*Cache-Control: no-store/);
});

test('text tokens meet AA contrast on primary surfaces', async () => {
  const css = await readFile(new URL('../src/styles/global.css', import.meta.url), 'utf8');
  const color = (name: string) => css.match(new RegExp(`--${name}:\\s*(#[a-fA-F0-9]{6})`))![1];
  const luminance = (hex: string) => {
    const rgb = [1, 3, 5]
      .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
    return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
  };
  for (const text of ['text', 'muted', 'accent'])
    for (const bg of ['bg', 'surface', 'raised']) {
      const ratio = (luminance(color(text)) + 0.05) / (luminance(color(bg)) + 0.05);
      assert.ok(ratio >= 4.5, `${text} on ${bg}: ${ratio}`);
    }
});

test('globe assets and article images are shipped with the static build', async () => {
  for (const path of [
    'cesium/Assets/Textures/SkyBox/tycho2t3_80_px.jpg',
    'cesium/Assets/approximateTerrainHeights.json',
    'data/globe/countries.geojson',
    'data/globe/cities.json',
    'data/globe/effects/ocean-mask.png',
    'data/globe/effects/bathymetry.jpg',
    'data/globe/effects/night-lights-2016.jpg',
    'cesium/Assets/Textures/waterNormals.jpg',
  ]) {
    assert.ok((await readFile(new URL(path, root))).length > 0, path);
  }
  assert.ok((await readdir(new URL('cesium/Workers/', root))).length > 0);
  assert.ok((await readdir(new URL('cesium/ThirdParty/', root))).length > 0);
  const snapshot = parseSnapshot(
    JSON.parse(await readFile(new URL('data/snapshot.json', root), 'utf8')),
  );
  for (const event of snapshot.events) {
    if (event.media?.image)
      assert.ok((await readFile(new URL(event.media.image.replace(/^\//, ''), root))).length > 0);
  }
});
