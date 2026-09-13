import { isPulse, type Event, type FeedMode, type Severity, type Topic } from '../data/types';
export type Range = 'all' | '24h' | '7d' | '30d';
export interface DashboardState {
  topic: Topic | 'all';
  sev: Severity | 'all';
  mode: FeedMode;
  range: Range;
  q: string;
  event: number | null;
}
export const defaults: DashboardState = {
  topic: 'all',
  sev: 'all',
  mode: 'all',
  range: 'all',
  q: '',
  event: null,
};
const valid = {
  topic: ['all', 'cyber', 'geopolitical', 'maritime', 'military'],
  sev: ['all', 'critical', 'escalating', 'watching', 'deesc'],
  mode: ['all', 'pulse', 'news'],
  range: ['all', '24h', '7d', '30d'],
};
export function readState(url: URL): DashboardState {
  const state = { ...defaults };
  for (const key of ['topic', 'sev', 'mode', 'range'] as const) {
    const value = url.searchParams.get(key);
    if (value && valid[key].includes(value)) Object.assign(state, { [key]: value });
  }
  state.q = (url.searchParams.get('q') ?? '').slice(0, 200);
  const id = url.searchParams.get('event') ?? url.hash.match(/^#event\/(\d+)$/)?.[1];
  if (id && /^\d+$/.test(id) && Number.isSafeInteger(+id) && +id > 0) state.event = +id;
  return state;
}
export function stateUrl(state: DashboardState, base: string): URL {
  const url = new URL('/', base);
  for (const key of ['topic', 'sev', 'mode', 'range', 'q'] as const)
    if (state[key] !== defaults[key]) url.searchParams.set(key, state[key]);
  if (state.event !== null) url.searchParams.set('event', String(state.event));
  return url;
}
export function filterEvents(events: Event[], state: DashboardState, now = Date.now()): Event[] {
  const days = { all: Infinity, '24h': 1, '7d': 7, '30d': 30 }[state.range];
  const query = state.q.trim().toLocaleLowerCase();
  return events
    .filter(
      (e) =>
        (state.topic === 'all' || e.t === state.topic) &&
        (state.sev === 'all' || e.sev === state.sev) &&
        (state.mode === 'all' || (state.mode === 'pulse' ? isPulse(e) : !isPulse(e))) &&
        (days === Infinity || (e.ts >= now - days * 86400000 && e.ts <= now)) &&
        `${e.title} ${e.summary ?? ''} ${e.loc} ${e.src}`.toLocaleLowerCase().includes(query),
    )
    .sort((a, b) => b.ts - a.ts || b.id - a.id);
}
