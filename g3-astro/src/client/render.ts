import { SEVERITY_LABELS, TOPIC_LABELS, type Event } from '../data/types';
export function escape(value: unknown): string {
  return String(value ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!,
  );
}
export const timestamp = (ms: number) =>
  new Intl.DateTimeFormat('en', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
    hour12: false,
  }).format(ms) + ' UTC';
export function sourceList(event: Event): string {
  return `<ul class="sources">${[...new Set(event.sources)]
    .filter((u) => /^https?:\/\//i.test(u))
    .map((url, i) => {
      let host: string;
      try {
        host = new URL(url).hostname.replace(/^www\./, '');
      } catch {
        return '';
      }
      return `<li><a href="${escape(url)}" target="_blank" rel="noopener noreferrer"><span class="source-number">${String(i + 1).padStart(2, '0')}</span><span>${escape(host)}<small>Read original reporting</small></span><span aria-hidden="true">↗</span></a></li>`;
    })
    .join('')}</ul>`;
}
/** D-020: media paths are ingest-controlled (schema pattern ^data/media/<hash>.jpg) but we still escape — the contract is defense in depth. */
export function cardThumbnail(event: Event): string {
  const image = event.media?.image ?? '';
  if (!/^\/?data\/media\/[a-f0-9]{16}\.(jpe?g)$/i.test(image)) return '';
  const src = image.startsWith('/') ? image : `/${image}`;
  return `<div class="card-thumb"><img src="${escape(src)}" alt="" loading="lazy" decoding="async"></div>`;
}
export function eventCard(
  event: Event,
  dashboard = false,
  active = false,
  liveLink = false,
  withMedia = false,
): string {
  const thumb = withMedia ? cardThumbnail(event) : '';
  return `<a class="event-card${active ? ' selected' : ''}${thumb ? ' has-thumb' : ''}" href="${dashboard || liveLink ? '/?event=' : '/boards/'}${event.id}" ${dashboard ? `data-event="${event.id}" aria-current="${active ? 'true' : 'false'}"` : ''}>
    <div class="event-kicker"><span class="topic">${TOPIC_LABELS[event.t]}</span><span class="severity-dot ${event.sev}" aria-label="${SEVERITY_LABELS[event.sev]}"></span></div>
    ${thumb}
    <h3>${escape(event.title)}</h3><p class="event-location">${escape(event.loc)}</p>
    <div class="event-meta"><span>${escape(event.src)}</span><time datetime="${new Date(event.ts).toISOString()}">${escape(timestamp(event.ts))}</time></div>
  </a>`;
}
/** D-014: missing geo block (legacy rows) is treated as approximate so the UI
 *  defaults to the honest style instead of trusting an unverified location. */
export function geoTier(ev: Event): 'precise' | 'approximate' {
  return ev.geo?.tier ?? 'approximate';
}

export function primarySource(event: Event): string | null {
  return (
    event.sources.find((url) => {
      try {
        return ['http:', 'https:'].includes(new URL(url).protocol);
      } catch {
        return false;
      }
    }) ?? null
  );
}

export function overviewSpotlight(event: Event): string {
  const source = primarySource(event);
  return `<p class="spotlight-topic"><span class="severity-dot ${event.sev}"></span>${escape(TOPIC_LABELS[event.t].toLowerCase())}</p>
    <h2>${escape(event.title)}</h2><p class="spotlight-source">${escape(event.src)}</p>
    <div class="spotlight-actions">${source ? `<a class="button primary-button" href="${escape(source)}" target="_blank" rel="noopener noreferrer">Read source <span aria-hidden="true">↗</span></a>` : ''}
    <button class="button quiet-button" data-preview-event="${event.id}">Report context</button>
    <button class="spotlight-share text-button" data-spotlight-share="${event.id}" aria-label="Share this report">Share</button></div><p id="spotlight-share-status" role="status"></p>`;
}

export function eventDetail(event: Event): string {
  const approximate = geoTier(event) === 'approximate';
  const precisionNote = approximate
    ? `<p class="fine-print precision-note">Approximate location — marker represents the named place or region, not a verified incident site. See original reporting for details.</p>`
    : '';
  // D-020 hero media: only ingest-controlled same-origin paths + strict YouTube watch links render.
  const image = event.media?.image ?? '';
  let hero = '';
  if (/^\/?data\/media\/[a-f0-9]{16}\.(jpe?g)$/i.test(image)) {
    const src = image.startsWith('/') ? image : `/${image}`;
    hero += `<figure class="event-hero"><img src="${escape(src)}" alt="" decoding="async"><figcaption>Image via ${escape(event.src)} — see original reporting for the full picture.</figcaption></figure>`;
  }
  let videoNote = '';
  const vid = event.media?.video_url ?? '';
  if (/^https:\/\/www\.youtube\.com\/watch\?v=[A-Za-z0-9_-]{6,25}$/.test(vid)) {
    videoNote = `<p class="fine-print media-video"><a href="${escape(vid)}" target="_blank" rel="noopener noreferrer">Video coverage available on YouTube ↗</a></p>`;
  }
  return `<div class="detail-kicker"><span class="eyebrow">${TOPIC_LABELS[event.t]}</span><span class="severity ${event.sev}">${SEVERITY_LABELS[event.sev]}</span></div>
    <h1 id="detail-title">${escape(event.title)}</h1>
    <p class="detail-location">${escape(event.loc)} <span>·</span> ${escape(timestamp(event.ts))}</p>
    ${hero}${videoNote}
    ${event.summary ? `<section class="detail-section"><h2>From the source</h2><p class="summary">${escape(event.summary)}</p></section>` : ''}
    <section class="detail-section"><h2>Original reporting <span class="muted">/ ${new Set(event.sources).size}</span></h2>${sourceList(event)}<p class="fine-print">Source links provide context. Multiple articles may draw on the same reporting.</p></section>
    ${precisionNote}
    <p class="fine-print classification-note">Topic and severity are automated classifications, not independent verification.</p>`;
}
export function boards(
  events: Event[],
  builtIds = new Set(events.map((e) => e.id)),
  page = 0,
): string {
  return (Object.entries(TOPIC_LABELS) as [Event['t'], string][])
    .map(([topic, label]) => {
      const items = events.filter((e) => e.t === topic).sort((a, b) => b.ts - a.ts);
      const cards =
        items
          .map((e, index) => {
            const html = eventCard(e, false, false, !builtIds.has(e.id), true);
            return page && index >= page
              ? html.replace('<a class="event-card', '<a hidden class="event-card')
              : html;
          })
          .join('') || '<p class="empty-state">No events in this topic yet.</p>';
      const remaining = page ? Math.max(0, items.length - page) : 0;
      const more = remaining
        ? `<div class="desk-more-row"><button type="button" class="button desk-more" data-desk-more data-section="board-${topic}" aria-controls="board-${topic}-grid" aria-expanded="false">Load <span data-desk-step>${Math.min(page, remaining)}</span> more</button></div>`
        : '';
      const paging = page ? ` id="board-${topic}" data-desk-page="${page}"` : '';
      const gridId = page ? ` id="board-${topic}-grid"` : '';
      return `<section class="board-group"${paging}><div class="section-heading"><h2>${label}</h2><span>${items.length} events</span></div><div class="card-grid"${gridId}>${cards}</div>${more}</section>`;
    })
    .join('');
}
export function briefing(
  events: Event[],
  now = Date.now(),
  builtIds = new Set(events.map((e) => e.id)),
): string {
  return (
    [
      ['24h', 1],
      ['7d', 7],
      ['30d', 30],
    ] as const
  )
    .map(([label, days]) => {
      const items = events
        .filter((e) => e.ts >= now - days * 86400000 && e.ts <= now)
        .sort((a, b) => b.ts - a.ts);
      return `<section class="briefing-window"><div class="section-heading"><h2>Last ${label}</h2><span>${items.length} events</span></div>
      <div class="briefing-grid"><div class="breakdown">${Object.entries(TOPIC_LABELS)
        .map(
          ([t, name]) =>
            `<div><span>${name}</span><strong>${items.filter((e) => e.t === t).length}</strong></div>`,
        )
        .join(
          '',
        )}<p class="fine-print">Counts reflect the retained feed, which holds up to 500 events.</p></div>
      <div class="briefing-stories">${
        items
          .slice(0, 5)
          .map((e) => eventCard(e, false, false, !builtIds.has(e.id), true))
          .join('') || '<p class="empty-state">No reporting in this time window.</p>'
      }</div></div></section>`;
    })
    .join('');
}
