// Iteration 1.1.2: intelligence contract types, validators and cross-object checks.
// Mirrors shared/schemas/intelligence/* and INTELLIGENCE_WIRE_SHAPES.md.
// The generated standalone validators live in generated-intelligence-validator.js.
import {
  validateRecord,
  validateIndex,
  validateDetail,
} from './generated-intelligence-validator.js';

export const MAX_DETAIL_BYTES = 150 * 1024;

export type Uid = string;
export type Hash = string; // 64 lowercase hex SHA-256
export type TimeMs = number; // nonnegative integer ms UTC
export type SourceUrl = string; // absolute http(s)

export interface EvidenceRef {
  evidenceUid: Uid;
  sourceUid: Uid;
  sourceRevisionUid: Uid;
  eventRevisionUids: Uid[]; // 1-6
  providerUid: string; // max 80
  sourceUrl: SourceUrl; // max 2048
  title: string; // max 500
  publishedAt: TimeMs | null;
  observedAt: TimeMs;
  excerpt: string | null; // max 600
  evidenceKind: 'source_text' | 'metadata_only';
  reportingOriginUid: Uid | null;
  independence: 'known_primary' | 'known_syndicated' | 'unknown';
  status: 'active' | 'corrected' | 'retracted' | 'removed';
}

export interface MentionRef {
  mentionUid: Uid;
  evidenceUid: Uid;
  role: 'subject' | 'publisher' | 'mentioned' | 'affected' | 'uncertain';
  field: 'title' | 'summary' | 'structured_subject';
  rawText: string; // max 300
  start: number | null;
  end: number | null;
  methodVersion: string; // max 80
}

export interface EntitySummary {
  entityUid: Uid;
  kind: 'country' | 'region' | 'domain' | 'ip' | 'cidr' | 'asn' | 'cve' | 'organization';
  canonicalValue: string; // max 253
  displayName: string; // max 300
  resolution: 'exact' | 'reviewed_alias';
  mentions: MentionRef[]; // max 5
}

export interface TimelineEntry {
  entryUid: Uid;
  kind: 'first_observed' | 'new_source' | 'source_revised' | 'correction' | 'retraction';
  observedAt: TimeMs;
  sourcePublishedAt: TimeMs | null;
  eventRevisionUid: Uid;
  label: string; // max 300
  evidenceUids: Uid[]; // max 5
}

export interface RelatedCard {
  edgeUid: Uid;
  kind: 'shared_evidence';
  target: {
    eventUid: Uid;
    eventRevisionUid: Uid;
    eventId: number | null;
    title: string; // max 500
    publishedAt: TimeMs | null;
    locationLabel: string | null; // max 300
    sourceUrls: SourceUrl[]; // 1-5
  };
  reasons: RelationReason[]; // 1-3
  methodVersion: string; // max 80
}

export interface RelationReason {
  code: 'shared_subject_cve' | 'shared_subject_infrastructure' | 'shared_subject_organization';
  entityUid: Uid; // present in entities[]
  evidenceUids: Uid[]; // 1-4
  label: string; // max 300
}

export interface IntelligenceRecord {
  schemaVersion: 1;
  eventUid: Uid;
  eventRevisionUid: Uid;
  eventId: number;
  projectionHash: Hash;
  generatedAt: TimeMs;
  evidence: EvidenceRef[]; // max 20
  entities: EntitySummary[]; // max 20
  timeline: TimelineEntry[]; // max 20
  related: RelatedCard[]; // max 5
  truncated: { evidence: boolean; entities: boolean; timeline: boolean; related: boolean };
}

export interface IntelligenceIndex {
  schemaVersion: 1;
  releaseUid: Uid;
  generatedAt: TimeMs;
  snapshotHash: Hash;
  entries: {
    eventId: number;
    eventUid: Uid;
    eventRevisionUid: Uid;
    projectionHash: Hash;
    artifactPath: string;
  }[]; // max 500
}

export interface IntelligenceDetail {
  schemaVersion: 1;
  releaseUid: Uid;
  eventUid: Uid;
  eventRevisionUid: Uid;
  projectionHash: Hash;
  generatedAt: TimeMs;
  evidence: EvidenceRef[]; // max 20
  entities: EntitySummary[]; // max 20
  timeline: TimelineEntry[]; // max 20
  related: RelatedCard[]; // max 5
  truncated: { evidence: boolean; entities: boolean; timeline: boolean; related: boolean };
}

export function isRecord(value: unknown): value is IntelligenceRecord {
  return validateRecord(value);
}
export function isIndex(value: unknown): value is IntelligenceIndex {
  return validateIndex(value);
}
export function isDetail(value: unknown): value is IntelligenceDetail {
  return validateDetail(value);
}

const UID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export function checkIndex(index: IntelligenceIndex): void {
  if (!isIndex(index)) throw new Error('Invalid intelligence index');
  const ids = index.entries.map((e) => e.eventId);
  const uids = index.entries.map((e) => e.eventUid);
  if (new Set(ids).size !== ids.length) throw new Error('Duplicate numeric event IDs in index');
  if (new Set(uids).size !== uids.length) throw new Error('Duplicate event UIDs in index');
  for (const entry of index.entries) {
    if (!entry.artifactPath.startsWith('/data/intelligence/v1/releases/')) {
      throw new Error(`Artifact path outside allowed structure: ${entry.artifactPath}`);
    }
    const parts = entry.artifactPath.split('/');
    if (
      parts.includes('..') ||
      parts.includes('.') ||
      entry.artifactPath.includes('?') ||
      entry.artifactPath.includes('#')
    ) {
      throw new Error(`Unsafe artifact path: ${entry.artifactPath}`);
    }
    const expected = `/data/intelligence/v1/releases/${index.releaseUid}/events/${entry.eventUid}.json`;
    if (entry.artifactPath !== expected) {
      throw new Error(`Artifact path does not match release/event UIDs: ${entry.artifactPath}`);
    }
  }
}

export function checkDetail(
  detail: IntelligenceDetail,
  expected?: Partial<IntelligenceDetail>,
): void {
  if (!isDetail(detail)) throw new Error('Invalid intelligence detail');
  if (expected) {
    for (const field of ['releaseUid', 'eventUid', 'eventRevisionUid', 'projectionHash'] as const) {
      if (expected[field] !== undefined && detail[field] !== expected[field]) {
        throw new Error(`Detail ${field} mismatch: ${detail[field]} != ${expected[field]}`);
      }
    }
  }
  const evidenceUids = new Set(detail.evidence.map((e) => e.evidenceUid));
  const entityUids = new Set(detail.entities.map((e) => e.entityUid));
  if (evidenceUids.size !== detail.evidence.length) throw new Error('Duplicate evidence UIDs');
  if (entityUids.size !== detail.entities.length) throw new Error('Duplicate entity UIDs');
  if (new Set(detail.timeline.map((t) => t.entryUid)).size !== detail.timeline.length) {
    throw new Error('Duplicate timeline entry UIDs');
  }
  for (const ev of detail.evidence) {
    if (ev.reportingOriginUid !== null && !evidenceUids.has(ev.reportingOriginUid)) {
      throw new Error(`Evidence ${ev.evidenceUid} references missing origin UID`);
    }
  }
  for (const entity of detail.entities) {
    for (const mention of entity.mentions) {
      if (!evidenceUids.has(mention.evidenceUid)) {
        throw new Error(
          `Mention ${mention.mentionUid} references missing evidence ${mention.evidenceUid}`,
        );
      }
      if ((mention.start === null) !== (mention.end === null)) {
        throw new Error(`Mention ${mention.mentionUid} has unpaired offsets`);
      }
      if (
        mention.start !== null &&
        mention.end !== null &&
        !(mention.start >= 0 && mention.start < mention.end)
      ) {
        throw new Error(`Mention ${mention.mentionUid} has invalid offsets`);
      }
    }
  }
  for (const entry of detail.timeline) {
    for (const uid of entry.evidenceUids) {
      if (!evidenceUids.has(uid))
        throw new Error(`Timeline ${entry.entryUid} references missing evidence ${uid}`);
    }
  }
  for (const card of detail.related) {
    for (const reason of card.reasons) {
      if (!entityUids.has(reason.entityUid))
        throw new Error(`Reason references missing entity ${reason.entityUid}`);
      for (const uid of reason.evidenceUids) {
        if (!evidenceUids.has(uid)) throw new Error(`Reason references missing evidence ${uid}`);
      }
    }
    if (card.target.eventUid === detail.eventUid)
      throw new Error('Related card targets the selected event itself');
  }
  for (const ev of detail.evidence) {
    if (ev.evidenceKind === 'source_text' && !ev.excerpt) {
      throw new Error(`Evidence ${ev.evidenceUid} is source_text with empty excerpt`);
    }
    if (ev.evidenceKind === 'metadata_only' && ev.excerpt !== null) {
      throw new Error(`Evidence ${ev.evidenceUid} is metadata_only with invented excerpt`);
    }
    if (ev.status === 'removed' && ev.excerpt) {
      throw new Error(`Removed evidence ${ev.evidenceUid} still carries an excerpt`);
    }
  }
  const size = new TextEncoder().encode(JSON.stringify(detail)).byteLength;
  if (size > MAX_DETAIL_BYTES) throw new Error(`Detail exceeds ${MAX_DETAIL_BYTES} bytes: ${size}`);
}

export { UID_RE };
