import check from './generated-validator.js';
import type { Snapshot } from './types';

export function parseSnapshot(value: unknown): Snapshot {
  if (!check(value)) throw new Error('Invalid event snapshot');
  const snapshot = value as Snapshot;
  const ids = new Set(snapshot.events.map((e) => e.id));
  if (
    ids.size !== snapshot.events.length ||
    snapshot.manifest.counts.events !== snapshot.events.length
  )
    throw new Error('Inconsistent event snapshot');
  for (const [key, field] of [
    ['byTopic', 't'],
    ['bySeverity', 'sev'],
  ] as const) {
    const counts = snapshot.manifest.counts[key] as Record<string, number>;
    const actual: Record<string, number> = {};
    for (const e of snapshot.events) actual[e[field]] = (actual[e[field]] ?? 0) + 1;
    for (const k of new Set([...Object.keys(counts), ...Object.keys(actual)]))
      if ((counts[k] ?? 0) !== (actual[k] ?? 0)) throw new Error('Inconsistent snapshot counts');
  }
  if (
    snapshot.manifest.nextEventId !== undefined &&
    snapshot.manifest.nextEventId <= Math.max(0, ...ids)
  )
    throw new Error('Invalid next event ID');
  return snapshot;
}
