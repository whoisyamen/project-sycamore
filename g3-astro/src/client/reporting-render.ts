import { TOPIC_LABELS, SEVERITY_LABELS, type Event } from '../data/types';
import { escape, timestamp, primarySource, geoTier, sourceList } from './render';
import { stateUrl, type DashboardState } from './state';

export function reportingUrl(state: DashboardState, base: string): URL {
  const url = stateUrl({ ...state, view: 'feed' }, base);
  url.pathname = '/reporting';
  url.searchParams.delete('view');
  return url;
}

export function reportingRows(events: Event[], selected: number | null): string {
  return (
    events
      .map((event) => {
        const active = event.id === selected;
        const source = primarySource(event);
        const location =
          geoTier(event) === 'approximate' && !/approximat/i.test(event.loc)
            ? `${event.loc} · approximate`
            : event.loc;
        return `<tr class="report-row${active ? ' expanded' : ''}" data-report-id="${event.id}">
      <td><span class="table-topic"><i class="severity-dot ${event.sev}" aria-label="${SEVERITY_LABELS[event.sev]}"></i>${escape(TOPIC_LABELS[event.t].toLowerCase())}</span></td>
      <td><button type="button" class="report-title" data-select-event="${event.id}" data-focus-key="report-${event.id}" aria-expanded="${active}" aria-controls="report-context-${event.id}">${escape(event.title)}<span aria-hidden="true">${active ? '−' : '+'}</span></button></td>
      <td class="table-source">${escape(event.src)}</td><td class="table-location">${escape(location)}</td>
      <td class="table-published"><time datetime="${new Date(event.ts).toISOString()}">${escape(timestamp(event.ts))}</time></td></tr>
      <tr id="report-context-${event.id}" class="report-context-row" ${active ? '' : 'hidden'}><td colspan="5">
        <div class="inline-context"><div><h2>Report context</h2><p class="inline-summary">${escape(event.summary || 'Read the original source for the reported details and context.')}</p>
        <p class="inline-attribution">Source: ${escape(event.src)} <span aria-hidden="true">·</span> ${escape(location)} <span aria-hidden="true">·</span> <time datetime="${new Date(event.ts).toISOString()}">${escape(timestamp(event.ts))}</time></p>
        <p class="fine-print">Topic and severity are automated classifications, not independent verification.</p>
        <details class="inline-sources"><summary>All source links (${event.sources.length})</summary>${sourceList(event)}</details></div>
        <div class="inline-actions">${source ? `<a class="button primary-button" href="${escape(source)}" target="_blank" rel="noopener noreferrer">Read source ↗</a>` : '<p class="fine-print">No source link available.</p>'}
        <button type="button" class="button quiet-button" data-share-report="${event.id}" data-focus-key="share-${event.id}">Share</button>
        <button type="button" class="text-button" data-select-event="${event.id}" data-focus-key="close-${event.id}">Close details</button><div data-share-status="${event.id}" role="status"></div></div>
        </div></td></tr>`;
      })
      .join('') ||
    '<tr><td colspan="5"><p class="empty-state">No reports match this view. Try another filter or reset the filters.</p></td></tr>'
  );
}
