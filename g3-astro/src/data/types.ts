// Shared TypeScript types for the Sycamore data layer.
// Mirrors shared/schemas/event.schema.json + manifest.schema.json.

export type Topic = 'cyber' | 'geopolitical' | 'maritime' | 'military';
export type Severity = 'critical' | 'escalating' | 'watching' | 'deesc';

/** D-012: corroboration detail attached to every event's score. */
export interface Corroboration {
  sources: string[]; // all corroborating article URLs (mirrors Event.sources)
  outlets?: string[]; // distinct reporting hostnames, first-seen order
}

/** D-012 feed modes. PULSE = multi-source OR high-confidence single source. */
export type FeedMode = 'all' | 'pulse' | 'news';

export interface Event {
  id: number;
  t: Topic;
  sev: Severity;
  title: string;
  summary?: string; // source's own lede; optional, may be empty
  src: string;
  loc: string;
  lat: number;
  lon: number;
  ts: number; // ms since epoch UTC, source-provided
  ingestedAt?: number; // ms since epoch UTC, when we saw it
  sources: string[];
  score: {
    articles: number;
    tone: number;
    quality?: number; // legacy rows may lack this
    confidence?: number; // D-012 local estimate (our number, not a fact)
    corroboration?: Corroboration; // D-012 source/outlet detail
  };
  /** D-014/D-020: provenance of lat/lon. Optional for legacy rows; treat absence as
   *  approximate (country-centroid) so the UI can default to the honest style. */
  geo?: {
    tier: 'precise' | 'approximate';
    source: 'source' | 'nominatim' | 'title' | 'summary';
  };
  /** D-020 event imagery, populated at ingest only from explicit feed references or a
   *  resolvable og:image. image is same-origin under /data/media/; video_url is an external
   *  watch link (YouTube), never embedded. Absent = no verified media — UI must not invent one. */
  media?: {
    image?: string; // e.g. "data/media/<hash>.jpg" relative to site root, or absolute "/data/..."
    video_url?: string; // https://www.youtube.com/watch?v=... only
  };
}

export interface Manifest {
  version: 1;
  lastAttempt?: number;
  nextEventId?: number;
  lastSync: number; // ms since epoch UTC
  source: { name: string; endpoint: string };
  counts: {
    events: number;
    byTopic: Partial<Record<Topic, number>>;
    bySeverity: Partial<Record<Severity, number>>;
    ingested?: number;
    deduped?: number;
    merged?: number; // D-012 corroboration merges this cycle
    pulse?: number; // D-012 events satisfying the PULSE predicate at write time
  };
  health: {
    status: 'ok' | 'degraded' | 'error';
    lastError?: string;
    durationMs?: number;
    failedSources?: string[];
  };
}

export const TOPIC_LABELS: Record<Topic, string> = {
  cyber: 'CYBER',
  geopolitical: 'GEOPOLITICAL',
  maritime: 'MARITIME',
  military: 'MILITARY',
};

export const SEVERITY_LABELS: Record<Severity, string> = {
  critical: 'CRITICAL',
  escalating: 'ESCALATING',
  watching: 'WATCHING',
  deesc: 'DE-ESCALATING',
};

/** PULSE predicate — must stay in sync with normalizer.pulse() (Python). */
export function isPulse(ev: Event): boolean {
  const s = ev.score || {};
  const nSources = s.corroboration ? s.corroboration.sources.length : (ev.sources?.length ?? 0);
  return nSources >= 2 || (s.confidence ?? 0) >= 85;
}

/** Distinct corroborating source count for badges. */
export function corrobCount(ev: Event): number {
  const s = ev.score || {};
  if (s.corroboration && Array.isArray(s.corroboration.sources))
    return s.corroboration.sources.length;
  return ev.sources?.length ?? 1;
}

export interface Snapshot {
  version: 1;
  events: Event[];
  manifest: Manifest;
}
export interface DataContext {
  events: Event[];
  manifest: Manifest | null;
  demo: boolean;
}
