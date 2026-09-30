import type { Event } from '../data/types';
import { threatView } from '../data/threat';
import { DESK_PAGE } from './desk';
import {
  boards,
  briefing,
  escape,
  eventCard,
  cardThumbnail,
  primarySource,
  timestamp,
} from './render';
import { TOPIC_LABELS } from '../data/types';
import { defaults, filterEvents, type DashboardState } from './state';

function editorialCard(event: Event, lead = false): string {
  const image = cardThumbnail(event);
  const source = primarySource(event);
  return `<article class="editorial-card${lead ? ' editorial-lead' : ''}">
    <a class="editorial-image${image ? '' : ' no-editorial-image'}" href="/?event=${event.id}" aria-label="Open geographic context for ${escape(event.title)}">${image || '<span class="media-unavailable">Source-based reporting</span>'}</a>
    <div class="editorial-copy"><p class="editorial-topic"><span class="severity-dot ${event.sev}"></span>${escape(TOPIC_LABELS[event.t].toLowerCase())}</p>
    <h2><a href="/?event=${event.id}">${escape(event.title)}</a></h2>
    <p class="editorial-source">${escape(event.src)} <span aria-hidden="true">·</span> <time datetime="${new Date(event.ts).toISOString()}">${escape(timestamp(event.ts))}</time></p>
    ${event.summary ? `<p class="editorial-summary">${escape(event.summary)}</p>` : ''}
    ${source ? `<a class="editorial-source-link" href="${escape(source)}" target="_blank" rel="noopener noreferrer">Read source <span aria-hidden="true">↗</span></a>` : ''}</div>
    </article>`;
}

function monitorCard(event: Event, deferred: boolean): string {
  const html = eventCard(event, false, false, true);
  return deferred ? html.replace('<a class="event-card', '<a hidden class="event-card') : html;
}

export function threatDesk(
  events: Event[],
  now = Date.now(),
  builtIds = new Set(events.map((event) => event.id)),
  state: DashboardState = { ...defaults },
): string {
  const view = threatView(events, now);
  let eligible = filterEvents(events, state, now);
  if (state.lens === 'emerging') eligible.sort((a, b) => (b.ingestedAt ?? 0) - (a.ingestedAt ?? 0));
  const illustrated = eligible.filter((event) => Boolean(cardThumbnail(event)));
  const featured = illustrated.length >= 3 ? illustrated : eligible;
  const hero = `<div class="editorial-hero">${
    eligible.length
      ? editorialCard(featured[0], true) +
        '<div class="secondary-stories">' +
        featured
          .slice(1, 3)
          .map((event) => editorialCard(event))
          .join('') +
        '</div>'
      : '<div class="editorial-empty"><h2>No reporting in this view.</h2><p>Try a different reading lens or coverage window. Reset the filters to read all retained reporting.</p></div>'
  }</div>
    <p class="desk-view-caption">${eligible.length} matching reports · Selected reporting shown here. <a href="/reporting">Read the full index ↗</a></p>`;
  const section = (
    id: string,
    index: string,
    title: string,
    description: string,
    items: Event[],
  ) => {
    const cards =
      items.map((event, itemIndex) => monitorCard(event, itemIndex >= DESK_PAGE)).join('') ||
      '<p class="empty-state">No matching reporting in the retained snapshot.</p>';
    const remaining = Math.max(0, items.length - DESK_PAGE);
    const more = remaining
      ? `<div class="desk-more-row"><button type="button" class="button desk-more" data-desk-more data-section="${id}" aria-controls="${id}-grid" aria-expanded="false">Load <span data-desk-step>${Math.min(DESK_PAGE, remaining)}</span> more</button></div>`
      : '';
    return `<section class="desk-section" id="${id}" data-desk-page="${DESK_PAGE}"><div class="desk-section-heading"><div><p class="eyebrow">${index} / MONITOR</p><h2>${title}</h2><p>${description}</p></div><span class="desk-total">${items.length} ${items.length === 1 ? 'match' : 'matches'}</span></div><div class="card-grid" id="${id}-grid">${cards}</div>${more}</section>`;
  };
  const groups = (id: string, index: string, title: string, description: string, html: string) =>
    `<section class="desk-section desk-groups" id="${id}"><div class="desk-section-heading"><div><p class="eyebrow">${index} / ${title.toUpperCase()}</p><h2>${title}</h2><p>${description}</p></div><span class="desk-total">${events.length} events</span></div>${html}</section>`;
  return (
    hero +
    section(
      'vulnerabilities',
      '01',
      'Vulnerabilities & exploits',
      'Text matches for CVEs, zero-days, exploits, and vulnerabilities in the current reporting feed. Not a complete CVE inventory.',
      view.vulnerabilities,
    ) +
    section(
      'policy',
      '02',
      'Policy & regulation',
      'Reporting that mentions laws, regulation, sanctions, or compliance. Check the original source for jurisdiction and effective dates.',
      view.policy,
    ) +
    section(
      'emerging',
      '03',
      'Newly observed',
      'Items first ingested here in the last 48 hours, newest first. Ingestion time is not the time an event began or proof of an early warning.',
      view.emerging,
    ) +
    groups(
      'boards',
      '04',
      'Reporting by topic',
      'Every retained item grouped by coverage board — cyber, geopolitics, maritime, and military. The same reporting the map plots, organized for a closer read.',
      boards(events, builtIds, DESK_PAGE),
    ) +
    groups(
      'briefing',
      '05',
      'Briefing windows',
      'The same reporting stepped back through 24-hour, 7-day, and 30-day windows with a per-topic breakdown.',
      briefing(events, now, builtIds),
    ) +
    `<section class="desk-section" id="sources"><div class="desk-section-heading"><div><p class="eyebrow">06 / COVERAGE</p><h2>Source footprint</h2><p>Source labels represented in the retained reporting snapshot. Counts are events, not feed-health checks.</p></div><span class="desk-total">${view.sources.length} source labels</span></div><div class="source-grid">${
      view.sources
        .slice(0, 16)
        .map(
          ([name, count]) =>
            `<div class="source-row"><span>${escape(name)}</span><strong>${count}</strong></div>`,
        )
        .join('') || '<p class="empty-state">No sources represented yet.</p>'
    }</div></section>`
  );
}
