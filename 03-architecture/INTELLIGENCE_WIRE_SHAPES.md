# Part 1 wire shapes — implementation contract

These are exact proposed shapes for 1.1.2 to turn into JSON Schema and TypeScript.
They are not existing runtime types. Follow the hash, identity, size and publication
rules in [the specification](INTELLIGENCE_IMPLEMENTATION_SPEC.md).
If baseline inspection requires a change, record it in INT-001 before coding.

## Scalar rules

- UID: canonical lowercase UUID string, assigned once and persisted.
- Hash: 64 lowercase hexadecimal SHA-256 characters.
- TimeMs: nonnegative integer UTC milliseconds. Unknown times use null only where
  the type explicitly permits it.
- Text: plain text, never trusted HTML; escape when rendering.
- SourceUrl: absolute http(s) URL; never javascript/data/file schemes.
- ArtifactPath: same-origin path matching the release/event structure below;
  validate parsed path and reject dot segments, query strings and fragments.
- Arrays contain no duplicate UID references unless a field explicitly represents
  repeated observations. All objects reject undeclared fields.

Type declarations below are documentation. Names in declarations are not extra
JSON fields. Nullable must be supported and parity-tested in the validator
implementation. For nullable fields, use JSON Schema type arrays such as
\`"type": ["integer", "null"]\`. Extend the Python validator to accept a value
matching one of a finite list of supported primitive types, preserving its
integer/boolean distinction and finite-number check. Add parity fixtures for
null, the correct primitive and every wrong primitive. Do not implement arbitrary
schema unions or skip validation because the existing subset lacks this feature.

## Index

    interface IntelligenceIndexV1 {
      schemaVersion: 1;
      releaseUid: UID;
      generatedAt: TimeMs;
      snapshotHash: Hash;
      entries: IntelligenceIndexEntry[]; // max 500
    }
    interface IntelligenceIndexEntry {
      eventId: number; // existing positive integer
      eventUid: UID;
      eventRevisionUid: UID;
      projectionHash: Hash;
      artifactPath: string;
    }

Entry IDs and UIDs are unique. Artifact path:
"/data/intelligence/v1/releases/" + releaseUid + "/events/" + eventUid + ".json".
Do not put paid-only historic entries in the public index.

## Selected-event detail

    interface IntelligenceDetailV1 {
      schemaVersion: 1;
      releaseUid: UID;
      eventUid: UID;
      eventRevisionUid: UID;
      projectionHash: Hash;
      generatedAt: TimeMs;
      evidence: EvidenceRef[];       // max 20
      entities: EntitySummary[];     // max 20
      timeline: TimelineEntry[];     // max 20
      related: RelatedCard[];        // max 5
      truncated: {
        evidence: boolean;
        entities: boolean;
        timeline: boolean;
        related: boolean;
      };
    }

All keys are required, including empty arrays and truncation flags.
A schema-valid empty result means no eligible material; a failed fetch is not an
empty result. Do not publish empty arrays merely to conceal enrichment failure.
The reader has a separate unavailable/error state.

## Evidence reference

    interface EvidenceRef {
      evidenceUid: UID;
      sourceUid: UID;
      sourceRevisionUid: UID;
      eventRevisionUids: UID[];        // 1–6 supported selected/target revisions
      providerUid: string;            // max 80; checked registry key
      sourceUrl: SourceUrl;           // max 2048
      title: string;                  // max 500
      publishedAt: TimeMs | null;
      observedAt: TimeMs;
      excerpt: string | null;         // max 600, only permitted retained text
      evidenceKind: "source_text" | "metadata_only";
      reportingOriginUid: UID | null;
      independence: "known_primary" | "known_syndicated" | "unknown";
      status: "active" | "corrected" | "retracted" | "removed";
    }

source_text requires a nonempty permitted excerpt; metadata_only requires null.
A removed source payload must not remain in the excerpt. Retain only the metadata
permitted by policy; if that cannot support a reference, omit the dependent card
and expose a correction/removal entry. Different hostnames alone do not establish
independence.

## Entity summary and mention

    interface EntitySummary {
      entityUid: UID;
      kind: "country" | "region" | "domain" | "ip" | "cidr" | "asn" | "cve" | "organization";
      canonicalValue: string;          // max 253
      displayName: string;             // max 300
      resolution: "exact" | "reviewed_alias";
      mentions: MentionRef[];          // max 5 per entity
    }
    interface MentionRef {
      mentionUid: UID;
      evidenceUid: UID;
      role: "subject" | "publisher" | "mentioned" | "affected" | "uncertain";
      field: "title" | "summary" | "structured_subject";
      rawText: string;                 // max 300, rights permitting
      start: number | null;            // code points; inclusive
      end: number | null;              // code points; exclusive
      methodVersion: string;           // max 80
    }

Both offsets null or both integers with 0 ≤ start < end. Offsets reference the
stored source-revision field, not the shortened public excerpt. Do not highlight
against the excerpt with those offsets. The reader can show rawText safely as a
label; a full-source highlighter must use the original qualified field.

Unresolved organization candidates remain internal and do not become resolved
entity links. A timeline can describe unresolved evidence without inventing a UID.

## Timeline

    interface TimelineEntry {
      entryUid: UID;
      kind: "first_observed" | "new_source" | "source_revised" | "correction" | "retraction";
      observedAt: TimeMs;
      sourcePublishedAt: TimeMs | null;
      eventRevisionUid: UID;
      label: string;                   // max 300, deterministic factual wording
      evidenceUids: UID[];             // max 5, all present in evidence[]
    }

Order by observedAt ascending then entryUid; pagination/truncation must say which
window is displayed. Do not reinterpret observedAt as incident occurrence.
A correction may have zero surviving evidence references if the payload was
removed; label the limitation instead of inventing a citation.

## Related card

    interface RelatedCard {
      edgeUid: UID;
      kind: "shared_evidence";
      target: {
        eventUid: UID;
        eventRevisionUid: UID;
        eventId: number | null;        // live selection only if present in current v1
        title: string;                 // max 500
        publishedAt: TimeMs | null;
        locationLabel: string | null;  // max 300, optional geography
        sourceUrls: SourceUrl[];       // 1–5 permitted links
      };
      reasons: RelationReason[];       // 1–3
      methodVersion: string;            // max 80
    }
    interface RelationReason {
      code: "shared_subject_cve" | "shared_subject_infrastructure" | "shared_subject_organization";
      entityUid: UID;                  // present in entities[]
      evidenceUids: UID[];             // 1–4 source refs present in evidence[]
      label: string;                   // max 300, generated from verified fields
    }

Evidence refs must include support from both selected and target event revisions,
using their eventRevisionUids assignments.
Store event-to-source assignments in the archive and validate that both sides are
represented before publication. A shared entity label alone is insufficient.
Rank scores stay internal in Part 1; a UI percentage would suggest false certainty.

If five cards need more evidence than the payload limit permits, return fewer
complete cards and set truncated.related=true. Never drop their support to fit.
If a target is absent from the live snapshot, eventId is null even if it has a
historic numeric ID; the reader displays the included summary/evidence. The
archive API later uses target.eventUid for full navigation.

## Minimum cross-object validation

1. Index UID/path structure and numeric-ID uniqueness.
2. Selected event/release/revision/hash match the request and index.
3. All references point to included objects with unique UIDs.
4. Every factual relation has support from both source sides.
5. No active card depends solely on removed/retracted evidence.
6. No source_text with null excerpt or metadata_only with invented excerpt.
7. Bounds, timestamp/null and offset rules.
8. Complete detail ≤150 KiB uncompressed; trim whole dependent groups, never
   produce dangling references.
9. Public source policy permits every payload field and link.
10. Rendering escapes all labels, titles, rawText and excerpts.

These checks supplement schema validation. Implement them as explicit tested
functions; do not assume schema validity proves semantic consistency.
