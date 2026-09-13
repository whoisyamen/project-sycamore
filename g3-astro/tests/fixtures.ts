import type { Event, Snapshot } from '../src/data/types';
export const now = 1788552000000;
export const event: Event = {
  id: 1,
  t: 'cyber',
  sev: 'watching',
  title: 'Infrastructure security advisory for London',
  src: 'Example News',
  loc: 'London, UK',
  lat: 51.5,
  lon: -0.12,
  ts: now - 3600000,
  sources: ['https://example.com/story'],
  score: { articles: 1, tone: 0 },
};
export function snapshot(events: Event[] = [event], attempt = now): Snapshot {
  const byTopic = { cyber: 0, geopolitical: 0, maritime: 0, military: 0 };
  const bySeverity = { critical: 0, escalating: 0, watching: 0, deesc: 0 };
  for (const e of events) {
    byTopic[e.t]++;
    bySeverity[e.sev]++;
  }
  return {
    version: 1,
    events,
    manifest: {
      version: 1,
      lastSync: attempt,
      lastAttempt: attempt,
      nextEventId: Math.max(0, ...events.map((e) => e.id)) + 1,
      source: { name: 'Example', endpoint: 'https://example.com/feed' },
      counts: { events: events.length, byTopic, bySeverity },
      health: { status: 'ok', durationMs: 1 },
    },
  };
}
