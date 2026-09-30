import { isPulse, type Event, type FeedMode, type Severity, type Topic } from '../data/types';
import { matchesLens, type Lens } from '../data/threat';
export type Range = 'all' | '24h' | '7d' | '30d';
export type View = 'map' | 'feed';
export type Sort = 'newest' | 'oldest' | 'severity';
export interface DashboardState {
  topic: Topic | 'all';
  sev: Severity | 'all';
  mode: FeedMode;
  range: Range;
  /** Exact source label, or 'all'. */
  src: string;
  /** Threat-desk lens over the same reporting: vulnerabilities / policy / newly observed. */
  lens: Lens;
  sort: Sort;
  /** Main-page surface: the globe or the tiles-only feed. */
  view: View;
  q: string;
  event: number | null;
}
export const defaults: DashboardState = {
  topic: 'all',
  sev: 'all',
  mode: 'all',
  range: 'all',
  src: 'all',
  lens: 'all',
  sort: 'newest',
  view: 'map',
  q: '',
  event: null,
};
const valid = {
  topic: ['all', 'cyber', 'geopolitical', 'maritime', 'military'],
  sev: ['all', 'critical', 'escalating', 'watching', 'deesc'],
  mode: ['all', 'pulse', 'news'],
  range: ['all', '24h', '7d', '30d'],
  lens: ['all', 'vulnerabilities', 'policy', 'emerging'],
  sort: ['newest', 'oldest', 'severity'],
  view: ['map', 'feed'],
};
export function readState(url: URL): DashboardState {
  const state = { ...defaults };
  for (const key of ['topic', 'sev', 'mode', 'range', 'lens', 'sort', 'view'] as const) {
    const value = url.searchParams.get(key);
    if (value && valid[key].includes(value)) Object.assign(state, { [key]: value });
  }
  const source = (url.searchParams.get('src') ?? '').trim().slice(0, 80);
  state.src = source && source !== 'all' ? source : 'all';
  state.q = (url.searchParams.get('q') ?? '').slice(0, 200);
  const id = url.searchParams.get('event') ?? url.hash.match(/^#event\/(\d+)$/)?.[1];
  if (id && /^\d+$/.test(id) && Number.isSafeInteger(+id) && +id > 0) state.event = +id;
  return state;
}
export function stateUrl(state: DashboardState, base: string): URL {
  const url = new URL('/', base);
  for (const key of ['topic', 'sev', 'mode', 'range', 'lens', 'sort', 'view', 'src', 'q'] as const)
    if (state[key] !== defaults[key]) url.searchParams.set(key, state[key]);
  if (state.event !== null) url.searchParams.set('event', String(state.event));
  return url;
}
const SEVERITY_RANK: Record<Severity, number> = {
  critical: 0,
  escalating: 1,
  watching: 2,
  deesc: 3,
};
const comparators: Record<Sort, (a: Event, b: Event) => number> = {
  newest: (a, b) => b.ts - a.ts || b.id - a.id,
  oldest: (a, b) => a.ts - b.ts || a.id - b.id,
  severity: (a, b) => SEVERITY_RANK[a.sev] - SEVERITY_RANK[b.sev] || b.ts - a.ts || b.id - a.id,
};
export function filterEvents(events: Event[], state: DashboardState, now = Date.now()): Event[] {
  const days = { all: Infinity, '24h': 1, '7d': 7, '30d': 30 }[state.range];
  const query = state.q.trim().toLocaleLowerCase();
  return events
    .filter(
      (e) =>
        (state.topic === 'all' || e.t === state.topic) &&
        (state.sev === 'all' || e.sev === state.sev) &&
        (state.mode === 'all' || (state.mode === 'pulse' ? isPulse(e) : !isPulse(e))) &&
        (state.src === 'all' || e.src === state.src) &&
        matchesLens(e, state.lens, now) &&
        (days === Infinity || (e.ts >= now - days * 86400000 && e.ts <= now)) &&
        `${e.title} ${e.summary ?? ''} ${e.loc} ${e.src}`.toLocaleLowerCase().includes(query),
    )
    .sort(comparators[state.sort]);
}
