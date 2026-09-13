"""RSS-first ingestion with validated, atomic snapshots and stable event IDs."""
from __future__ import annotations
import argparse
import copy
import fcntl
import json
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from . import gdelt_client, rss_client, normalizer, media_pipeline, flight_client, censys_client
from .contracts import validate_event, validate_snapshot
from .publisher import commit_cycle as _commit_cycle  # archive mode (1.2.2)

MAX_EVENTS = 500
MAX_ARTICLES = 250
DEFAULT_OUT = Path(__file__).resolve().parents[2] / 'g3-astro' / 'public' / 'data'
# Stable label for repeated legacy-snapshot imports into the archive. The
# import stream is idempotent: same legacy IDs map to the same UIDs forever.
_LEGACY_IMPORT_IDENTITY = 'legacy-snapshot:v1'


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _atomic_write(path: Path, payload: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, prefix=f'.{path.name}.', delete=False) as f:
            name = f.name
            json.dump(payload, f, ensure_ascii=False,
                      indent=None if compact else 2,
                      separators=(',', ':') if compact else None,
                      allow_nan=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, 0o644)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def _counts(events: list[dict], **extra) -> dict:
    topic = dict.fromkeys(('cyber','geopolitical','maritime','military'), 0)
    severity = dict.fromkeys(('critical','escalating','watching','deesc'), 0)
    for event in events:
        topic[event['t']] += 1
        severity[event['sev']] += 1
    return {'events': len(events), 'byTopic': topic, 'bySeverity': severity,
            'pulse': sum(normalizer.pulse(e) for e in events), **extra}


def _empty_manifest() -> dict:
    return {'version': 1, 'lastSync': 0, 'lastAttempt': 0, 'nextEventId': 1,
            'source': {'name': 'Curated RSS', 'endpoint': rss_client.FEEDS[0]['url']},
            'counts': _counts([]), 'health': {'status': 'error', 'durationMs': 0}}


def _load_previous(out: Path) -> dict:
    snapshot_path = out / 'snapshot.json'
    if snapshot_path.exists():
        snapshot = json.loads(snapshot_path.read_text())
    elif (out / 'events.json').exists():
        events = json.loads((out / 'events.json').read_text())
        manifest = json.loads((out / 'manifest.json').read_text()) if (out / 'manifest.json').exists() else _empty_manifest()
        # Migration never treats an old failed attempt as a successful sync.
        if manifest['health']['status'] != 'ok':
            manifest['lastSync'] = 0
        manifest['counts'] = _counts(events)
        snapshot = {'version': 1, 'events': events, 'manifest': manifest}
    else:
        snapshot = {'version': 1, 'events': [], 'manifest': _empty_manifest()}
    snapshot['manifest'].setdefault('nextEventId', max((e['id'] for e in snapshot['events']), default=0) + 1)
    snapshot['manifest'].setdefault('lastAttempt', snapshot['manifest']['lastSync'])
    validate_snapshot(snapshot)
    return snapshot


def _expected_geo(event: dict) -> tuple[float, float] | None:
    """Re-derive coordinates for an event's title+summary under current policy.

    Tier 1 (headline locative locus) first; tier 2 only if the stored record was
    itself summary-sourced — a stale v1 row never silently upgrades to new coords.
    Returns None when the text no longer resolves anywhere (unsafe state)."""
    title = event.get('title') or ''
    summary = event.get('summary') or ''
    expected = normalizer.resolve_location(title)
    if expected is not None:
        return expected['lat'], expected['lon']
    if event.get('geo', {}).get('source') == 'summary':
        tier2 = normalizer._resolve_event_geo(title, summary)
        if tier2 is not None and tier2['geo']['source'] == 'summary':
            return tier2['lat'], tier2['lon']
    return None


def _validate_geolocation(events: list[dict]) -> None:
    """Fail closed on legacy/unsafe state, including failure and mirror paths.

    An operator runs the private offline audit migration; the sandboxed timer
    neither writes private evidence under public/ nor silently discards history.
    Tier-2 (summary-lede) rows are re-derived from stored title+summary text —
    deterministic, no network — so a summary-sourced row survives only while its
    own source lede still resolves to the same place."""
    for event in events:
        if event.get('geo', {}).get('source') == 'source':
            continue  # article-supplied coordinates keep their provenance
        expected = _expected_geo(event)
        stored_lat, stored_lon = event.get('lat'), event.get('lon')
        try:
            ok = (expected is not None and abs(float(stored_lat) - expected[0]) < 1e-6
                  and abs(float(stored_lon) - expected[1]) < 1e-6)
        except (TypeError, ValueError):
            ok = False
        if not ok:
            raise ValueError(f"Unsafe geolocation for event {event['id']}; run fix_bad_geocodes offline migration")


def _publish(out: Path, events: list[dict], manifest: dict) -> None:
    _validate_geolocation(events)
    snapshot = {'version': 1, 'events': events, 'manifest': manifest}
    validate_snapshot(snapshot)
    # Commit the canonical file first. Legacy outputs are compatibility mirrors;
    # a crash while writing either mirror never compromises the next cycle.
    _atomic_write(out / 'snapshot.json', snapshot)
    _atomic_write(out / 'events.json', events)
    _atomic_write(out / 'manifest.json', manifest)


def _failure(out: Path, previous: dict, started: int, failed: list[str]) -> dict:
    manifest = copy.deepcopy(previous['manifest'])
    manifest.update(lastAttempt=_now_ms(), counts=_counts(previous['events'], ingested=0, deduped=0, merged=0))
    manifest['health'] = {'status': 'error', 'durationMs': _now_ms() - started,
                          'failedSources': failed, 'lastError': 'Source update failed; retained last valid events.'}
    _publish(out, previous['events'], manifest)
    return manifest


def _osint_cycle(out: Path) -> list[str]:
    """Publish independent OSINT envelopes alongside events (D-023).

    Each source is strictly additive and never blocks event publication: a failed
    fetch leaves the previous envelope in place, so the globe degrades to stale-but-labeled
    data instead of disappearing. Returns the names of sources that failed this cycle."""
    failed: list[str] = []
    # FLIGHTS — OpenSky states/all (public, no key). Trails merge from last published file.
    try:
        payload = flight_client.fetch_states()
        envelope = flight_client.build_envelope(payload, flight_client.load_previous(out / 'flights.json'))
        _atomic_write(out / 'flights.json', envelope, compact=True)
    except Exception as error:  # noqa: BLE001 — source failures are per-source, not fatal
        sys.stderr.write(f'[ingest] flights failed (kept previous): {type(error).__name__}\n')
        failed.append('OpenSky flights')
    # CENSYS — host search for operator-selected regions; skipped entirely without a key.
    try:
        key = censys_client._api_key()  # noqa: SLF001 — same package, intentional reuse
        if not key:
            sys.stderr.write('[ingest] censys skipped: CENSYS_PERSONAL_ACCESS_TOKEN not configured\n')
            return failed
        if not (out / 'regions.json').exists():
            sys.stderr.write('[ingest] censys skipped: regions.json not configured\n')
            return failed
        with open(out / 'regions.json', encoding='utf-8') as f:
            regions = json.load(f)
        if isinstance(regions, dict):
            regions = regions.get('regions')
        if not isinstance(regions, list) or any(not isinstance(r, dict) for r in regions):
            raise ValueError('regions.json must contain a regions array of objects')
        if not regions:
            sys.stderr.write('[ingest] censys skipped: no sampling regions selected\n')
            return failed
        fetch_fn = lambda region: censys_client.fetch_region(key, region)  # noqa: E731 — closure over key
        envelope = censys_client.build_envelope(regions, fetch_fn)
        _atomic_write(out / 'censys.json', envelope)
        sys.stderr.write(f'[ingest] censys published: {envelope["count"]} host samples\n')
    except Exception as error:  # noqa: BLE001
        reason = str(error) if isinstance(error, censys_client.CensysUnavailable) else type(error).__name__
        sys.stderr.write(f'[ingest] censys failed (kept previous): {reason}\n')
        failed.append('Censys hosts')
    return failed


def _semantic_event(event: dict) -> dict:
    """Stable content identity for an event (INT-001/INT-002).

    Excludes continuously recalculated clocks/freshness (ingestedAt, score)
    so polling cycles do not manufacture a 'new development'. Clock-only
    changes never append a material revision.
    """
    return {k: event[k] for k in (
        'id', 't', 'sev', 'title', 'summary', 'src', 'loc', 'lat', 'lon', 'ts', 'sources',
    ) if k in event}


def _shadow_observe(archive, run_uid: str | None, observed_at: int, articles: list[dict],
                    provider: str = 'rss', deduped_ids: set[int] | None = None):
    """Best-effort shadow observation wrapper. Never raises."""
    if archive is None:
        return None
    try:
        result = archive.record_batch(run_uid, provider, articles, observed_at)
        return result
    except Exception as error:  # noqa: BLE001 — shadow failure must not block legacy
        try:
            archive.record_shadow_gap(run_uid, f'record_batch: {type(error).__name__}: {error}')
        except Exception:  # noqa: BLE001
            pass
        return None


def _shadow_record_events(archive, run_uid: str | None, observed_at: int, events: list[dict],
                          by_url: dict[str, str | None]):
    """Record event revisions before pruning. Never raises."""
    if archive is None:
        return
    try:
        for event in events:
            src_revs = [u for u in (by_url.get(s) for s in event.get('sources', [])) if u]
            archive.record_event_revision(event['id'], _semantic_event(event), src_revs, observed_at)
    except Exception as error:  # noqa: BLE001
        try:
            archive.record_shadow_gap(run_uid, f'record_event_revision: {type(error).__name__}: {error}')
        except Exception:  # noqa: BLE001
            pass


def _source_manifest_entry(use_gdelt: bool) -> dict:
    return {'name': 'Curated RSS + GDELT' if use_gdelt else 'Curated RSS',
            'endpoint': rss_client.FEEDS[0]['url']}


def _provider_batches(articles: list[dict], use_gdelt: bool) -> list[tuple[str, list[dict]]]:
    """Split one fetched batch per provider — the SAME partition shadow observation uses.

    RSS articles carry a private '_rss_source' marker; GDELT articles do not (the
    normalizer falls back to domain/'GDELT'). When no article is marked at all the whole
    batch belongs to rss, matching 1.2.1's observed rule exactly."""
    marked = [a for a in articles if a.get('_rss_source')]
    unmarked = [a for a in articles if not a.get('_rss_source')]
    batches: list[tuple[str, list[dict]]] = [('rss', marked or articles)]
    if use_gdelt and unmarked:
        batches.append(('gdelt', unmarked))
    return batches


def _cycle(out: Path, previous: dict, use_gdelt: bool, *, archive=None,
           run_uid: str | None = None, commit_fn=None) -> dict:
    """Run one ingestion cycle.

    Returns a manifest for legacy/shadow modes; in archive mode (commit_fn set) returns
    {'kind': 'archive', **publication info} after the single commit — file publication
    happens only via publisher.replay afterwards."""
    started = _now_ms()
    failed: list[str] = []
    articles: list[dict] = []
    succeeded_rss = 0
    gdelt_succeeded = False
    media_hints_by_url: dict[str, dict] = {}  # article URL -> feed-native image/video hints
    try:
        batch = rss_client.fetch_all()
        succeeded_rss = getattr(batch, 'succeeded', 1)  # list-compatible test/legacy callers
        failed.extend(getattr(batch, 'failed', []))
        articles.extend(rss_client.to_articles(list(batch)))
        for item in list(batch):  # same order as to_articles output — index-aligned hints
            hint_image = (item.media_image or '').strip()
            hint_video = (item.video_url or '').strip()
            if hint_image or hint_video:
                media_hints_by_url[item.link] = {'image': hint_image, 'video_url': hint_video}
    except Exception as error:
        sys.stderr.write(f'[ingest] RSS failed: {type(error).__name__}\n')
        failed.append('RSS')
    if use_gdelt:
        try:
            articles.extend(gdelt_client.fetch_last_15min(max_records=MAX_ARTICLES))
            gdelt_succeeded = True
        except Exception as error:  # noqa: BLE001 — per-source failure, cycle continues
            sys.stderr.write(f'[ingest] GDELT failed: {type(error).__name__}\n')
            failed.append('GDELT')

    # Total source failure: NO fetch of any enabled provider succeeded (1.2.1 rule).
    total_failure = not succeeded_rss and (not use_gdelt or not gdelt_succeeded)
    if total_failure:
        # Legacy/shadow: retained snapshot via _failure. Archive: the retention itself is a
        # committed publication — same transactional path, so run/health history and
        # replayability are identical to successful cycles (spec §5.2 row 6).
        if archive is not None:  # shadow: observe whatever partial batch exists too
            for provider_uid, arts in _provider_batches(articles, use_gdelt):
                _shadow_observe(archive, run_uid, started, arts, provider=provider_uid)
        if commit_fn is not None:
            manifest = copy.deepcopy(previous['manifest'])
            manifest.update(lastAttempt=_now_ms(), lastSync=previous['manifest'].get('lastSync', 0),
                            counts=_counts(previous['events'], ingested=0, deduped=0, merged=0))
            manifest['health'] = {'status': 'error', 'durationMs': _now_ms() - started,
                                  'failedSources': failed}
            info = commit_fn(provider_articles=[(p, []) for p in ('rss',) + (('gdelt',) if use_gdelt else ())],
                             failed_sources=list(failed), revision_items=None, started_ms=started,
                             snapshot_payload={'version': 1, 'events': copy.deepcopy(previous['events']),
                                               'manifest': manifest})
            return {'kind': 'archive', **info, 'health': copy.deepcopy(manifest['health'])}
        return _failure(out, previous, started, failed)

    # Shadow observation: record the SAME fetched batch before URL-skip/dedupe. RSS and
    # GDELT articles are recorded under their own providers (1.2.1 rule). Archive mode
    # does NOT double-observe here — commit_fn records inside its one transaction.
    observed_by_url: dict[str, str | None] = {}
    batches = _provider_batches(articles, use_gdelt) if archive is not None else []
    for provider_uid, arts in batches:
        obs = _shadow_observe(archive, run_uid, started, arts, provider=provider_uid)
        if obs is not None:
            observed_by_url.update(obs.by_url)

    events = copy.deepcopy(previous['events'])
    next_id = max(previous['manifest'].get('nextEventId', 1), max((e['id'] for e in events), default=0) + 1)
    by_key: dict[str, dict] = {}
    known_urls: set[str] = set()
    for event in events:
        by_key.setdefault(normalizer.dedupe_key(event), event)
        known_urls.update(event['sources'])
    deduped = merged = rejected = 0
    for article in articles:
        event = normalizer.normalize(article, next_id)
        if event is None:
            continue
        try:
            validate_event(event)
        except ValueError:
            rejected += 1
            continue
        url = event['sources'][0]
        if url in known_urls:
            deduped += 1
            continue
        key = normalizer.dedupe_key(event)
        known_urls.add(url)
        if key in by_key:
            target = by_key[key]
            target['sources'] = list(dict.fromkeys([*target['sources'], url]))
            target['score']['articles'] = len(target['sources'])
            merged += 1
        else:
            by_key[key] = event
            events.append(event)
            next_id += 1
    now = _now_ms()
    for event in events:
        normalizer.refresh_score(event, now)
    events.sort(key=lambda e: (e.get('ingestedAt', e['ts']), e['id']), reverse=True)
    pre_prune_events = list(events)  # captured BEFORE pruning so history survives the cap
    _shadow_record_events(archive, run_uid, now, pre_prune_events, observed_by_url)
    events = events[:MAX_EVENTS]

    # D-020 imagery: attach feed-native / og:image media to rows that lack it.
    # Hints are merged across every source URL of an event (corroborated articles).
    if media_hints_by_url:
        pairs = []
        for ev in events:
            hint: dict[str, str] = {}
            for u in ev.get('sources', []):
                h = media_hints_by_url.get(u)
                if not h:
                    continue
                if h.get('image') and 'image' not in hint:
                    hint['image'] = h['image']
                if h.get('video_url') and 'video_url' not in hint:
                    hint['video_url'] = h['video_url']
            pairs.append((ev, hint))
        try:
            attached = media_pipeline.attach_media(pairs, out)
            if attached:
                sys.stderr.write(f'[ingest] Attached imagery to {attached} events.\n')
        except Exception as error:
            # Media is strictly additive; a failure must never block publication.
            sys.stderr.write(f'[ingest] media attach failed (non-fatal): {type(error).__name__}\n')

    if rejected:
        sys.stderr.write(f'[ingest] Rejected {rejected} records that violate the event schema.\n')
        failed.append('Invalid source records')
    # D-023 OSINT envelopes (flights/censys) are independent layers; their failures feed
    # into cycle health so a stale layer is never presented as fresh.
    for name in _osint_cycle(out):
        if name not in failed:
            failed.append(name)
    manifest = {'version': 1, 'lastSync': now, 'lastAttempt': now, 'nextEventId': next_id,
                'source': _source_manifest_entry(use_gdelt),
                'counts': _counts(events, ingested=len(articles), deduped=deduped, merged=merged),
                'health': {'status': 'degraded' if failed else 'ok', 'durationMs': now - started, 'failedSources': failed}}

    if commit_fn is not None:
        # Archive mode (INT-003 §2): ONE transaction stores run + health + source
        # observations/revisions for the SAME single fetched batch and an immutable
        # publication payload; files are written only by ordered replay afterwards.
        revision_items = [(e['id'], _semantic_event(e)) for e in pre_prune_events]
        info = commit_fn(provider_articles=_provider_batches(articles, use_gdelt), failed_sources=list(failed),
                         revision_items=revision_items, started_ms=started,
                         snapshot_payload={'version': 1, 'events': copy.deepcopy(events),
                                           'manifest': manifest})
        return {'kind': 'archive', **info, 'health': copy.deepcopy(manifest['health'])}

    _publish(out, events, manifest)
    return manifest


def _validate_archive_path(archive_path: Path | None, mode: str) -> Path:
    """Shadow/archive guardrail (identical contract): explicit path outside public/dist."""
    archive_path = Path(archive_path).resolve()
    project_root = Path(__file__).resolve().parents[2]
    forbidden_parents = (project_root / 'g3-astro' / 'public', project_root / 'g3-astro' / 'dist')
    if any(str(archive_path).startswith(str(p)) for p in forbidden_parents):
        raise ValueError(f'{mode} mode: archive_path must be outside public/data and dist: {archive_path}')
    try:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        probe = archive_path.with_name(archive_path.name + '.probe')
        probe.touch()
        probe.unlink()
    except OSError as error:
        raise ValueError(f'{mode} mode: archive_path not writable: {archive_path}: {error}') from error
    return archive_path


def run(out_dir: Path = DEFAULT_OUT, *, first_run: bool = False, use_gdelt: bool = False,
        snapshot_only: bool = False, mode: str = 'legacy', archive_path: Path | None = None) -> dict:
    """Serialize cycles. --first remains a compatible, harmless legacy option.

    mode: 'legacy' (default), 'shadow', or 'archive'. Shadow and archive modes both
    require an explicit archive path outside public/data and dist, validated before any
    fetch; in shadow the legacy JSON stays authoritative while the DB observes additively,
    in archive the committed publication jobs are authoritative for v1 output. Legacy
    behaviour is never altered by either."""
    if mode not in ('legacy', 'shadow', 'archive'):
        raise ValueError(f"Invalid mode: {mode!r}; expected 'legacy', 'shadow' or 'archive'")

    from . import archive as archive_mod
    publisher_replay = None
    publisher_sync = None
    if mode in ('shadow', 'archive') and archive_path is not None:
        # Local aliases keep the legacy path free of any publication dependency at runtime.
        from .publisher import replay, sync_mirrors  # noqa: F401 - bound below for these modes only
        publisher_replay = replay
        publisher_sync = sync_mirrors
    if mode in ('shadow', 'archive'):
        if archive_path is None:
            raise ValueError(f'{mode} mode requires an explicit archive_path outside public/data and dist')
        archive_path = _validate_archive_path(archive_path, mode)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / '.ingest.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous_file_state = _load_previous(out_dir)  # corrupt existing state must never be overwritten

        archive = None
        run_uid = None
        try:
            if mode != 'archive':
                # Fail-closed geolocation audit on the file state (1.2.1 contract for legacy/shadow).
                _validate_geolocation(previous_file_state['events'])

            previous = previous_file_state  # authoritative "previous" state for this cycle's merge
            commit_fn = None
            if mode in ('shadow', 'archive'):
                assert publisher_replay is not None and publisher_sync is not None  # bound above for these modes
                archive = archive_mod.Archive(archive_path)

            if snapshot_only:
                # Cutover/bootstrap step (INT-003 §4): import the current file state under a stable identity; in
                # archive mode also retain it as publication job #1 when none exists yet — idempotent on repeat.
                # No source fetch happens on this path.
                if mode == 'legacy':
                    _publish(out_dir, previous_file_state['events'], previous_file_state['manifest'])
                    return previous_file_state['manifest']
                assert archive is not None  # validated above for shadow/archive modes
                archive.import_snapshot(previous_file_state, _LEGACY_IMPORT_IDENTITY)
                if mode == 'shadow':
                    # 1.2.1 contract: import idempotent; legacy JSON stays authoritative.
                    _publish(out_dir, previous['events'], previous['manifest'])
                    return previous['manifest']
                row = archive.conn.execute('SELECT 1 FROM publication_jobs LIMIT 1').fetchone()
                if row is not None:
                    # Already bootstrapped (or further along): self-heal mirrors from committed state.
                    rewritten = publisher_sync(archive, out_dir)
                    return {'kind': 'bootstrap', 'status': 'repaired' if rewritten else 'already-bootstrapped'}
                now_ms = _now_ms()
                boot_events = previous['events']
                # Same fail-closed audit the legacy --snapshot-only path applies (1.2.x contract): unsafe or
                # stale geolocation in file state is an operator-migration condition, never silently committed.
                _validate_geolocation(boot_events)
                boot_manifest = copy.deepcopy(previous['manifest'])
                # Bootstrap is a migration step, not an ingestion cycle: record it as a clean ok state so the
                # run history never carries the empty-state 'error' health of _empty_manifest (1.2.x contract).
                boot_manifest.update(lastAttempt=now_ms, lastSync=boot_manifest.get('lastSync', 0),
                                     counts=_counts(boot_events, ingested=0, deduped=0, merged=0))
                boot_manifest['health'] = {'status': 'ok', 'durationMs': 0, 'failedSources': []}
                info = _commit_cycle(archive, started_ms=now_ms, provider_articles=[], failed_sources=[],
                                     revision_items=None,
                                     snapshot_payload={'version': 1, 'events': copy.deepcopy(boot_events),
                                                       'manifest': boot_manifest})
                published_seqs = publisher_replay(archive, out_dir)
                return {'kind': 'bootstrap', **info, 'replayedSequences': published_seqs,
                        'health': dict(boot_manifest.get('health') or {'status': 'ok', 'durationMs': 0,
                                                                      'failedSources': []})}

            if mode == 'shadow' and archive is not None:
                # 1.2.1 shadow contract unchanged: idempotent import + run row before fetch; the legacy JSON
                # stays authoritative throughout this branch (files publish via _cycle as usual).
                previous = copy.deepcopy(previous_file_state)
                archive.import_snapshot(previous, _LEGACY_IMPORT_IDENTITY)
                run_uid = archive.begin_run(_now_ms())
            elif mode == 'archive' and archive is not None:
                # Archive authority (INT-003): crash recovery FIRST — any pending job replays in committed order,
                # rewriting exactly the bytes a crashed write left behind (spec §5.2 rows 4/8); only when nothing
                # was pending do mirrors self-heal from the newest published payload. Then the committed DB
                # projection becomes previous state — never file-derived in this mode; its events get the same
                # fail-closed geolocation audit as any published row would.
                if not publisher_replay(archive, out_dir):
                    publisher_sync(archive, out_dir)
                db_state = archive.latest_projection()
                if db_state is None:
                    raise archive_mod.BootstrapRequired(
                        f'{archive_path} holds no bootstrappable state (no published job and no imported '
                        "snapshot); run --mode archive --snapshot-only against the current snapshot directory first.")
                previous = copy.deepcopy(db_state)
                _validate_geolocation(previous['events'])

            if mode == 'archive' and archive is not None:
                def commit_fn(*, provider_articles: list[tuple[str, list[dict]]], failed_sources: list[str] | None = None,
                              revision_items: list[tuple[int, dict]] | None = None, snapshot_payload: dict,
                              started_ms: int) -> dict:
                    # One transaction per cycle (publisher.commit_cycle): run + health + observations/revisions for the
                    # SAME fetched batch + immutable publication payload. File writes happen only in publisher_replay —
                    # never inside this closure.
                    return _commit_cycle(archive, started_ms=started_ms, provider_articles=list(provider_articles),
                                         failed_sources=list(failed_sources or ()), revision_items=revision_items,
                                         snapshot_payload=snapshot_payload)

            if mode == 'shadow' and archive is not None:
                manifest = _cycle(out_dir, previous, use_gdelt, archive=archive, run_uid=run_uid, commit_fn=None)
                try:
                    counts = dict(manifest.get('counts', {}))
                    archive.finish_run(run_uid, manifest['health']['status'], counts, manifest.get('lastSync'))
                except Exception as error:  # noqa: BLE001 — shadow failure must not block legacy publication
                    try:
                        archive.record_shadow_gap(run_uid, f'finish_run: {type(error).__name__}: {error}')
                    except Exception:  # noqa: BLE001
                        pass
                return manifest

            if mode == 'archive':
                info = _cycle(out_dir, previous, use_gdelt, archive=None, run_uid=None, commit_fn=commit_fn)
                published_seqs = publisher_replay(archive, out_dir)  # ordered, hash-verified replay (spec §5.2)
                return {'kind': 'archive', **info, 'replayedSequences': published_seqs}

            # Legacy mode — untouched behaviour end to end.
            return _cycle(out_dir, previous_file_state, use_gdelt)

        except Exception:
            if archive is not None and run_uid is not None:
                try:
                    archive.record_shadow_gap(run_uid, 'cycle raised; legacy continues')
                except Exception:  # noqa: BLE001
                    pass
            if mode != 'archive':
                # If publication already committed a newer snapshot, retain that state (legacy/shadow only — in
                # archive mode an uncommitted cycle leaves mirrors untouched by design).
                try:
                    committed = _load_previous(out_dir)
                    _failure(out_dir, committed, _now_ms(), ['Ingestion processing'])
                except Exception:  # noqa: BLE001 — failure-of-failure must not mask the original error
                    pass
            raise
        finally:
            if archive is not None:
                archive.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Sycamore v1 ingestion (RSS primary; GDELT opt-in).')
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--gdelt', action='store_true')
    parser.add_argument('--first', action='store_true', help='Legacy compatibility option; RSS remains primary')
    parser.add_argument('--snapshot-only', action='store_true', help='Migrate existing JSON to a snapshot without fetching sources')
    parser.add_argument('--mode', choices=('legacy', 'shadow', 'archive'), default='legacy',
                        help="legacy (default), shadow, or archive; shadow/archive require --archive")
    parser.add_argument('--archive', type=Path, default=None,
                        help='SQLite archive path for shadow/archive modes; must be outside public/data and dist')
    args = parser.parse_args(argv)
    try:
        manifest = run(args.out, first_run=args.first, use_gdelt=args.gdelt,
                       snapshot_only=args.snapshot_only, mode=args.mode,
                       archive_path=args.archive)
    except Exception as error:
        print(f'Ingest failed: {type(error).__name__}: {error}', file=sys.stderr)
        return 1
    status = (manifest.get('health') or {}).get('status', 'ok') if isinstance(manifest, dict) else 'ok'
    print(json.dumps(manifest, indent=2))
    return 1 if status == 'error' else 0


if __name__ == '__main__':
    sys.exit(main())
