import type { Event } from './types';

// These are text-based reading lists over the existing reporting snapshot, not
// dedicated advisory feeds or an assertion that an exploit is confirmed.
const vulnerabilityTerms =
  /\bCVE-\d{4}-\d{4,}\b|\bzero[ -]day\b|\bexploits?\b|\bexploited\b|\bvulnerabilit(?:y|ies)\b|\bsecurity flaw\b/i;
const policyTerms =
  /\bregulat(?:ion|ions|ory)\b|\blegislat(?:ion|ive)\b|\bcybersecurity law\b|\bprivacy law\b|\bdata protection act\b|\bsanctions?\b|\bcompliance\b/i;
const EMERGING_WINDOW_MS = 48 * 60 * 60 * 1000;

/** Threat-desk lens shared by the desk page and the dashboard feed filters. */
export type Lens = 'all' | 'vulnerabilities' | 'policy' | 'emerging';

export const LENS_LABELS: Record<Lens, string> = {
  all: 'All reporting',
  vulnerabilities: 'Vulnerabilities & exploits',
  policy: 'Policy & regulation',
  emerging: 'Newly observed',
};

const text = (event: Event) => `${event.title} ${event.summary ?? ''}`;

export function matchesLens(event: Event, lens: Lens, now = Date.now()): boolean {
  switch (lens) {
    case 'vulnerabilities':
      return vulnerabilityTerms.test(text(event));
    case 'policy':
      return policyTerms.test(text(event));
    case 'emerging':
      return Boolean(
        event.ingestedAt && event.ingestedAt <= now && event.ingestedAt >= now - EMERGING_WINDOW_MS,
      );
    default:
      return true;
  }
}

export function threatView(events: Event[], now = Date.now()) {
  const recent = [...events]
    .filter((event) => event.ts <= now)
    .sort((a, b) => b.ts - a.ts || b.id - a.id);
  const sources = new Map<string, number>();
  for (const event of events) sources.set(event.src, (sources.get(event.src) ?? 0) + 1);
  const byLens = (lens: Exclude<Lens, 'all'>) =>
    recent
      .filter((event) => matchesLens(event, lens, now))
      .sort((a, b) => b.ts - a.ts || b.id - a.id);
  return {
    vulnerabilities: byLens('vulnerabilities'),
    policy: byLens('policy'),
    emerging: recent
      .filter((event) => matchesLens(event, 'emerging', now))
      .sort((a, b) => (b.ingestedAt ?? 0) - (a.ingestedAt ?? 0) || b.id - a.id),
    sources: [...sources].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])),
  };
}
