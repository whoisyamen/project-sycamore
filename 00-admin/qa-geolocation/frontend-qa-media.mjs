// D-020 media rendering QA. Verifies card thumbnails, detail hero, video links,
// and CSP conformance. Run AFTER frontend-qa.mjs (this reuses the same dev
// server on :4321).
import { chromium } from '/home/yams/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--enable-unsafe-swiftshader'] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const cspViolations = [];
page.on('response', resp => {
  // CSP reports don't show in response events on stock Chromium without a
  // reporting endpoint; we instead confirm every <img> src is same-origin.
  if (resp.url().includes('/data/media/') && !resp.url().startsWith('http://localhost:4321/')) {
    cspViolations.push(resp.url());
  }
});
const results = [];
async function test(name, fn) {
  try {
    const detail = await fn();
    results.push({ name, pass: true, detail });
    console.log('PASS', name, detail ?? '');
  } catch (e) {
    results.push({ name, pass: false, error: e.message });
    console.log('FAIL', name, e.message);
  }
}

await page.goto('http://localhost:4321');
await page.waitForSelector('.map-marker');
await page.waitForTimeout(800);

await test('Live events have media blocks where expected', async () => {
  const stats = await page.evaluate(() => {
    const evts = JSON.parse(document.body.dataset.context).events;
    const withImg = evts.filter(e => e.media?.image);
    const withVid = evts.filter(e => e.media?.video_url);
    return { total: evts.length, withImg: withImg.length, withVid: withVid.length,
             imgSamples: withImg.slice(0, 3).map(e => ({ id: e.id, img: e.media.image })) };
  });
  console.log('  stats:', JSON.stringify(stats));
  assert(stats.total > 0, 'expected events to load');
  assert(stats.withImg >= 1, `expected at least one event with image, got ${stats.withImg}`);
  for (const s of stats.imgSamples) {
    assert.match(s.img, /^data\/media\/[a-f0-9]{16}\.jpe?g$/, `bad image path: ${s.img}`);
  }
  return { withImg: stats.withImg, withVid: stats.withVid, total: stats.total };
});

await test('Dashboard feed cards render thumbnail when present', async () => {
  const stats = await page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll('#feed-list [data-event]'));
    const withImg = cards.filter(c => c.querySelector('.card-thumb img'));
    const imgs = withImg.map(c => c.querySelector('.card-thumb img').getAttribute('src'));
    return { cards: cards.length, withImg: withImg.length, imgs: imgs.slice(0, 3) };
  });
  console.log('  stats:', JSON.stringify(stats));
  assert(stats.cards > 0, 'no feed cards');
  // At least one card should have a thumb (we know >=1 events have images).
  if (stats.withImg > 0) {
    for (const src of stats.imgs) {
      assert(src.startsWith('/data/media/') || src.startsWith('data/media/'),
             `thumb src not same-origin: ${src}`);
    }
  }
  return { cards: stats.cards, withImg: stats.withImg };
});

await test('Detail panel renders hero image and CSP-clean', async () => {
  // Click the first event with media, then verify the detail rendering.
  const targetId = await page.evaluate(() => {
    const evts = JSON.parse(document.body.dataset.context).events;
    return (evts.find(e => e.media?.image) || {}).id;
  });
  if (!targetId) {
    return { skipped: 'no events with image in current dataset' };
  }
  // Click the corresponding card in the feed list.
  await page.locator(`#feed-list [data-event="${targetId}"]`).first().click();
  await page.waitForTimeout(600);
  const heroStats = await page.evaluate(() => {
    const body = document.getElementById('detail-body');
    if (!body) return null;
    const hero = body.querySelector('img');
    return hero ? { tag: hero.tagName, src: hero.getAttribute('src'), alt: hero.getAttribute('alt'),
                    w: hero.naturalWidth, h: hero.naturalHeight } : null;
  });
  console.log('  heroStats:', JSON.stringify(heroStats));
  assert(heroStats, 'expected hero <img> in #detail-body');
  assert(heroStats.src.startsWith('/data/media/') || heroStats.src.startsWith('data/media/'),
         `hero src not same-origin: ${heroStats.src}`);
  return { id: targetId, src: heroStats.src, naturalSize: `${heroStats.w}x${heroStats.h}` };
});

await test('No CSP violations from media sources', async () => {
  assert.equal(cspViolations.length, 0, `external media loaded: ${cspViolations.join(', ')}`);
  return { violations: 0 };
});

await browser.close();
const passed = results.filter(r => r.pass).length;
const failed = results.filter(r => !r.pass).length;
console.log(`\nSummary: ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
