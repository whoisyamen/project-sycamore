import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { parseSnapshot } from './validate';
import type { DataContext, Snapshot } from './types';

let buildContext: Promise<DataContext> | null = null;
/** One coherent dataset per static build; development reads each current snapshot. */
export function loadData(): Promise<DataContext> {
  if (!import.meta.env.PROD) return readData();
  return (buildContext ??= readData());
}

/** Build-only filesystem loader. Browser updates use the atomic snapshot. */
async function readData(): Promise<DataContext> {
  if (import.meta.env.PUBLIC_DEMO_MODE === 'true') {
    const { demoEvents } = await import('./demo');
    return { events: demoEvents, manifest: null, demo: true };
  }
  const dir = resolve('public/data');
  try {
    let raw: unknown;
    try {
      raw = JSON.parse(await readFile(resolve(dir, 'snapshot.json'), 'utf8'));
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
      // One-time compatibility with the installed pre-snapshot ingest service.
      const events = JSON.parse(await readFile(resolve(dir, 'events.json'), 'utf8'));
      const manifest = JSON.parse(await readFile(resolve(dir, 'manifest.json'), 'utf8'));
      raw = { version: 1, events, manifest };
    }
    const snapshot: Snapshot = parseSnapshot(raw);
    return { events: snapshot.events, manifest: snapshot.manifest, demo: false };
  } catch {
    console.warn('[data] No valid snapshot. Rendering the unavailable state.');
    return { events: [], manifest: null, demo: false };
  }
}
