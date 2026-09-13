import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import {
  isRecord,
  isIndex,
  isDetail,
  checkIndex,
  checkDetail,
  MAX_DETAIL_BYTES,
} from '../src/data/intelligence';
import { parseSnapshot } from '../src/data/validate';
import { event, snapshot } from './fixtures';

const ROOT = fileURLToPath(new URL('../../shared/fixtures/intelligence/', import.meta.url));
const load = async (rel: string) => JSON.parse(await readFile(`${ROOT}${rel}`, 'utf8'));

function canonicalHash(value: unknown): string {
  const parts: string[] = [];
  ser(value, parts);
  return createHash('sha256').update(parts.join('')).digest('hex');
}
function serNum(v: number): string {
  if (v === 0) return '0';
  if (Number.isInteger(v)) return Math.abs(v) < 1e21 ? String(v) : v.toString();
  return v.toString();
}
function ser(v: unknown, out: string[]) {
  if (v === null) out.push('null');
  else if (v === true) out.push('true');
  else if (v === false) out.push('false');
  else if (typeof v === 'number') {
    if (!Number.isFinite(v)) throw new Error('non-finite');
    out.push(serNum(v));
  } else if (typeof v === 'string') out.push(JSON.stringify(v));
  else if (Array.isArray(v)) {
    out.push('[');
    v.forEach((x, i) => {
      if (i) out.push(',');
      ser(x, out);
    });
    out.push(']');
  } else if (typeof v === 'object' && v !== null) {
    const keys = Object.keys(v as Record<string, unknown>).sort();
    out.push('{');
    keys.forEach((k, i) => {
      if (i) out.push(',');
      out.push(JSON.stringify(k), ':');
      ser((v as Record<string, unknown>)[k], out);
    });
    out.push('}');
  } else throw new Error('unsupported ' + typeof v);
}

test('intelligence valid fixtures pass both generated validators', async () => {
  assert.ok(isRecord(await load('valid/record.json')));
  assert.ok(isIndex(await load('valid/index.json')));
  assert.ok(isDetail(await load('valid/detail.json')));
});

test('detail with unknown property rejected', async () => {
  assert.equal(isDetail(await load('invalid/detail-unknown-property.json')), false);
  assert.equal(isDetail(await load('invalid/detail-evidence-extra-property.json')), false);
});

test('oversize array rejected', async () => {
  const detail = await load('valid/detail.json');
  detail.evidence = Array.from({ length: 21 }, () => detail.evidence[0]);
  assert.equal(isDetail(detail), false);
});

test('nullable fields accept null and reject wrong primitives', async () => {
  const detail = await load('valid/detail.json');
  detail.evidence[0].publishedAt = null;
  assert.ok(isDetail(detail));
  detail.evidence[0].publishedAt = 'not-a-time';
  assert.equal(isDetail(detail), false);
  detail.evidence[0].publishedAt = true;
  assert.equal(isDetail(detail), false); // interger/boolean distinction preserved
});

test('v1 strictness unchanged: plus-uid rejected, old snapshot valid', async () => {
  const plus = await load('invalid/v1-event-plus-uid.json');
  assert.throws(() => parseSnapshot(snapshot([plus as never])));
  const v1 = await load('valid/v1-event.json');
  assert.equal(parseSnapshot(snapshot([v1 as never])).events[0].id, 17);
});

test('canonical hash vectors match Python', async () => {
  const vectors = await load('canonical-hash-vectors.json');
  for (const vec of vectors.vectors) {
    assert.equal(canonicalHash(vec.value), vec.sha256, `vector ${vec.name} mismatch`);
  }
});

test('canonical hash rejects non-finite numbers', () => {
  assert.throws(() => canonicalHash({ x: NaN }));
  assert.throws(() => canonicalHash({ x: Infinity }));
});

test('checkIndex rejects unsafe or inconsistent artifact paths', async () => {
  checkIndex(await load('valid/index.json'));
  const bad = await load('valid/index.json');
  bad.entries.push({ ...bad.entries[0] });
  assert.throws(() => checkIndex(bad));
  const evil = await load('valid/index.json');
  evil.entries[0].artifactPath = '/data/intelligence/v1/releases/../../etc/passwd';
  assert.throws(() => checkIndex(evil));
});

test('checkDetail enforces referential integrity and reader consistency', async () => {
  checkDetail(await load('valid/detail.json'));
  for (const rel of [
    'invalid/detail-dangling-evidence.json',
    'invalid/detail-dangling-mention.json',
    'invalid/detail-source-text-null-excerpt.json',
    'invalid/detail-metadata-invented-excerpt.json',
    'invalid/detail-removed-with-excerpt.json',
    'invalid/detail-unpaired-offset.json',
    'invalid/detail-invalid-offset.json',
    'invalid/detail-related-self.json',
  ]) {
    const bad = await load(rel);
    assert.throws(() => checkDetail(bad), `expected rejection for ${rel}`);
  }
  const wrongEvent = await load('invalid/detail-wrong-event-uid.json');
  assert.throws(() =>
    checkDetail(wrongEvent, {
      eventUid: 'aaaaaaaa-0000-4000-8000-000000000001',
    }),
  );
  const wrongRelease = await load('invalid/detail-wrong-release-uid.json');
  assert.throws(() =>
    checkDetail(wrongRelease, {
      releaseUid: '99999999-0000-4000-8000-000000000001',
    }),
  );
});

test('complete detail size cap enforced in JS too', async () => {
  const detail = await load('valid/detail.json');
  detail.evidence = Array.from({ length: 20 }, () => ({
    ...detail.evidence[0],
    evidenceUid: crypto.randomUUID(),
    title: 'x'.repeat(500),
    excerpt: 'y'.repeat(600),
    sourceUrl: 'https://alpha.example/very-long-' + 'a'.repeat(1900),
  }));
  assert.throws(() => checkDetail(detail));
  assert.ok(MAX_DETAIL_BYTES === 150 * 1024);
});

test('generated intelligence validator contains no dynamic evaluation', async () => {
  const src = await readFile(
    fileURLToPath(new URL('../src/data/generated-intelligence-validator.js', import.meta.url)),
    'utf8',
  );
  assert.equal(src.includes('eval('), false);
  assert.equal(src.includes('new Function'), false);
});
