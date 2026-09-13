import type { Event } from './types';
const now = Date.now();
export const demoEvents: Event[] = [
  {
    id: 1,
    t: 'cyber',
    sev: 'watching',
    title: 'Demo: infrastructure security advisory published',
    loc: 'London, UK',
    lat: 51.5,
    lon: -0.12,
  },
  {
    id: 2,
    t: 'maritime',
    sev: 'escalating',
    title: 'Demo: shipping disruption reported near a major trade route',
    loc: 'Red Sea',
    lat: 18,
    lon: 40,
  },
  {
    id: 3,
    t: 'geopolitical',
    sev: 'deesc',
    title: 'Demo: diplomatic talks resume in Geneva',
    loc: 'Geneva, CH',
    lat: 46.2,
    lon: 6.14,
  },
].map((e, i) => ({
  ...e,
  t: e.t as Event['t'],
  sev: e.sev as Event['sev'],
  src: 'Illustrative data',
  ts: now - i * 3600000,
  sources: ['https://example.com/'],
  score: { articles: 1, tone: 0 },
  summary: 'This is a fictional demonstration event. It is not live reporting.',
}));
