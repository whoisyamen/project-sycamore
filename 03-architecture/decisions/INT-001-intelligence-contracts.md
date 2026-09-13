# INT-001 — Separate intelligence contracts and stable identity

Status: ACCEPTED (2026-09-10) — iteration 1.1.2.
Scope: schema/contract layer only. No database, no frontend UI, no live data rewrites.

## Context

The v1 projection (`/data/snapshot.json`) is strict and frozen. Future
intelligence records (evidence, entities, mentions, timeline, related cards)
need explicit shapes, bounded sizes and stable identity WITHOUT widening v1 or
recalculating event UIDs from mutable fields. Baseline 1.1.1 confirmed: the
Python validator supports a limited keyword subset, resolves only
event/manifest refs, and the client validator is Ajv-generated standalone code
(no runtime eval). Identity today is a numeric event ID allocated by
`runner._cycle`; there is no UID layer, no source-key normalization, and no
canonical hashing.

## Decision

1. Create three JSON Schemas under `shared/schemas/intelligence/`:
   - `record.schema.json` — INTERNAL storage shape for one event's intelligence
     record (event revision + source records with full internal fields).
   - `index.schema.json` — PUBLIC index shape (per INTELLIGENCE_WIRE_SHAPES.md).
   - `detail.schema.json` — PUBLIC selected-event detail shape (per wire
     shapes, including evidence refs, entities, mentions, timeline, related,
     truncation flags).
2. All three schemas are fully inline (no `$ref` between files) so both the
   Python subset validator and the Ajv/standalone generator validate identical
   shapes. Nested interfaces from the wire shapes become inline properties.
3. Bound every array and string per the wire shapes (evidence ≤20, entities
   ≤20, timeline ≤20, related ≤5, mentions ≤5/entity, reasons 1–3, etc.) using
   `maxItems`/`maxLength`/`minItems` so oversize payloads fail schema, not just
   application checks.
4. Nullable fields use JSON Schema type arrays `["integer","null"]` /
   `["string","null"]`. Python validator is extended to accept a value matching
   one of a finite type list, preserving integer/boolean distinction and
   finite-number checks. No `anyOf`/`if`-`then`/`$defs` are introduced.
5. Identity rules (spec §4.1):
   - Event UIDs are assigned UUIDv4 once and persisted; **never** recalculated
     from title/location. `identity.ensure_event_uid(mapping, legacy_id)`
     reuses an existing mapping entry; new IDs are allocated and recorded.
     A mapping checksum (`identity.import_manifest_checksum`) lets reruns reuse
     the same mapping; identity imports are idempotent.
   - Source record natural key = `providerUid + provider-native record id`
     when available, else `providerUid + canonical source URL`.
   - URL canonicalization normalizes ONLY scheme/host case, default ports and
     fragments; path/query are preserved, so distinct query strings stay
     distinct. The original URL is retained separately.
   - Canonical hash = SHA-256 over UTF-8 canonical JSON: object keys sorted
     recursively, no whitespace, original array order, non-finite numbers
     rejected. Implemented identically in Python and TS.

## Selected bounds (documented, not invented)

- UID: canonical lowercase UUIDv4 string `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`
- Hash: `^[0-9a-f]{64}$`
- TimeMs: integer 0..8640000000000000 (matches v1 `ts` bound); unknown → null
  where the type permits.
- SourceUrl: `format: uri` + `pattern: ^https?://` + maxLength 2048.
- ArtifactPath: anchored
  `^/data/intelligence/v1/releases/<releaseUid>/events/<eventUid>\.json$`
  (also enforced by application check rejecting dot segments/query/fragment).
- Size: complete detail ≤150 KiB uncompressed (application check; serialized
  length is the bound, not raw JSON bytes of nested-only fields).
- Excerpt ≤600 chars; omitted/removed payload → null excerpt, never invented.

## Cross-object invariants (application layer, both languages)

Schema validity does NOT prove: referential integrity (all UIDs resolve within
the artifact), release/event/revision/hash consistency with the request,
evidence-kind/excerpt pairing, related-card support from both sides, no
active-card dependence on removed evidence, offset pairing, and the 150 KiB
size cap. These are implemented as explicit tested functions
(`check_index`, `check_detail` in Python; `checkIndex`, `checkDetail` in TS)
per INTELLIGENCE_WIRE_SHAPES.md "Minimum cross-object validation".

## Unresolved / deferred (recorded, not silently solved)

- Provider registry: `providerUid` strings are validated for format/length
  only; the checked-in provider registry table arrives with the archive (1.2.1).
- Tracking-parameter normalization is NOT applied; provider-specific rules are
  deferred with fixtures.
- Independence is stored as a declared enum; hostname-only inference is not
  implemented (spec: different hostnames do not establish independence).
- Persistence of UID mappings, import manifests and archive tables is 1.2.1;
  this iteration's identity helpers accept a mapping in memory for tests.

## Rejected alternatives

- Widening v1: rejected (breaks frozen reader contract; spec §3.1).
- Arbitrary `$ref`/URL resolution in Python: rejected; registry resolves only
  approved local schema names, everything else fails closed.
- Dynamic browser eval for validation: rejected; Ajv standalone code is
  precompiled at build time (existing pattern preserved).
- Deriving eventUid by hashing title+location: rejected (spec §4.1 — identity
  must be assigned and persisted, not derived from mutable content).

## Consequences

- Public v1 readers are untouched; new validators can be removed without
  affecting v1.
- Writers (archive/publisher) consume these schemas in 1.2.1+; nothing in this
  iteration writes public data.
- Fixture parity tests in Python (g3-ingest) and TS (g3-astro) share the same
  files under `shared/fixtures/intelligence/`.