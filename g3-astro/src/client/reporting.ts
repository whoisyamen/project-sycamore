import type { DataContext, Snapshot } from '../data/types';
import { dataStatus } from '../data/status';
import { filterEvents, readState, defaults, type DashboardState } from './state';
import { reportingRows, reportingUrl } from './reporting-render';

export function initReporting(context: DataContext) {
  const get = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
  const rows = get('reporting-rows');
  const search = get<HTMLInputElement>('search');
  let state = { ...readState(new URL(location.href)), view: 'feed' as const };
  let shown = 50;
  const selects = {
    'topic-filter': 'topic',
    severity: 'sev',
    range: 'range',
    source: 'src',
    mode: 'mode',
    sort: 'sort',
    'lens-filter': 'lens',
  } as const;
  function sync() {
    search.value = state.q;
    const source = get<HTMLSelectElement>('source');
    const labels = [...new Set(context.events.map((event) => event.src))].sort();
    if (state.src !== 'all' && !labels.includes(state.src)) labels.push(state.src);
    source.replaceChildren(
      ...['all', ...labels].map((label) => {
        const option = document.createElement('option');
        option.value = label;
        option.textContent = label === 'all' ? 'All sources' : label;
        return option;
      }),
    );
    for (const [id, key] of Object.entries(selects)) get<HTMLSelectElement>(id).value = state[key];
    document.querySelectorAll<HTMLButtonElement>('[data-topic], [data-lens]').forEach((button) => {
      button.setAttribute(
        'aria-pressed',
        String(
          button.dataset.topic
            ? button.dataset.topic === state.topic
            : button.dataset.lens === state.lens,
        ),
      );
    });
    get('legacy-mode').hidden = state.mode === 'all';
    get('legacy-mode').textContent =
      state.mode === 'pulse'
        ? 'Corroborated reporting filter is active.'
        : 'Single-source reporting filter is active.';
  }
  function render() {
    const active = document.activeElement as HTMLElement | null;
    const key = rows.contains(active) ? active?.dataset.focusKey : null;
    const visible = filterEvents(context.events, state);
    const displayed = visible.slice(0, shown);
    const selected = context.events.find((event) => event.id === state.event);
    const outside = selected && !displayed.some((event) => event.id === selected.id);
    rows.innerHTML = reportingRows(outside ? [selected, ...displayed] : displayed, state.event);
    get('index-count').textContent = String(visible.length);
    const more = get('reporting-more');
    if (more) more.hidden = shown >= visible.length;
    const caption = get('index-page-caption');
    if (caption)
      caption.textContent = `Showing ${Math.min(shown, visible.length)} of ${visible.length} matching reports`;
    const note = get('index-selection-note');
    note.hidden = state.event === null || Boolean(selected && !outside);
    note.textContent = selected
      ? 'The selected report is shown above the current filter results.'
      : 'The selected report is outside the retained snapshot. Other reporting remains available.';
    get('index-health').textContent = dataStatus(context.manifest, context.demo).label;
    if (key)
      [...rows.querySelectorAll<HTMLElement>('[data-focus-key]')]
        .find((el) => el.dataset.focusKey === key)
        ?.focus({ preventScroll: true });
  }
  function update(push = false) {
    history[push ? 'pushState' : 'replaceState'](null, '', reportingUrl(state, location.href));
    sync();
    render();
    get('announcement').textContent =
      `${filterEvents(context.events, state).length} matching reports`;
  }
  search.closest('form')?.addEventListener('submit', (event) => event.preventDefault());
  search.addEventListener('input', () => {
    state.q = search.value;
    update();
  });
  for (const [id, key] of Object.entries(selects))
    get<HTMLSelectElement>(id).addEventListener('change', (event) => {
      Object.assign(state, { [key]: (event.target as HTMLSelectElement).value });
      update();
    });
  document.querySelectorAll<HTMLButtonElement>('[data-topic], [data-lens]').forEach((button) =>
    button.addEventListener('click', () => {
      if (button.dataset.topic) state.topic = button.dataset.topic as DashboardState['topic'];
      else state.lens = button.dataset.lens as DashboardState['lens'];
      update();
    }),
  );
  get('reset-filters').addEventListener('click', () => {
    state = { ...defaults, view: 'feed' };
    shown = 50;
    update();
  });
  get('reporting-more')?.addEventListener('click', () => {
    const firstNew = filterEvents(context.events, state)[shown];
    shown += 50;
    render();
    if (get('reporting-more').hidden && firstNew)
      rows.querySelector<HTMLElement>(`[data-focus-key="report-${firstNew.id}"]`)?.focus();
  });
  document.querySelector('[data-report-sort]')?.addEventListener('click', () => {
    state.sort = state.sort === 'newest' ? 'oldest' : 'newest';
    update();
  });
  rows.addEventListener('click', async (event) => {
    const button = (event.target as HTMLElement).closest<HTMLElement>(
      '[data-select-event], [data-share-report]',
    );
    if (!button) return;
    if (button.dataset.selectEvent) {
      const id = Number(button.dataset.selectEvent);
      const closing = state.event === id;
      state.event = closing ? null : id;
      update(true);
      if (closing)
        rows
          .querySelector<HTMLElement>(`[data-focus-key="report-${id}"]`)
          ?.focus({ preventScroll: true });
    } else {
      const id = Number(button.dataset.shareReport);
      const url = reportingUrl({ ...state, event: id }, location.href).href;
      const status = rows.querySelector<HTMLElement>(`[data-share-status="${id}"]`)!;
      try {
        await navigator.clipboard.writeText(url);
        status.textContent = 'Link copied';
      } catch {
        const input = document.createElement('input');
        input.value = url;
        input.readOnly = true;
        input.className = 'share-fallback';
        input.setAttribute('aria-label', 'Copy this report link');
        status.replaceChildren(input);
        input.focus();
        input.select();
      }
    }
  });
  document.addEventListener('keydown', (event) => {
    const editing =
      event.target instanceof HTMLElement
        ? event.target.closest('input,textarea,select,[contenteditable="true"]')
        : null;
    if (event.key === '/' && !editing && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault();
      search.focus();
    }
    if (event.key === 'Escape' && state.event !== null) {
      const id = state.event;
      state.event = null;
      update(true);
      rows
        .querySelector<HTMLElement>(`[data-focus-key="report-${id}"]`)
        ?.focus({ preventScroll: true });
    }
  });
  window.addEventListener('popstate', () => {
    state = { ...readState(new URL(location.href)), view: 'feed' };
    sync();
    render();
  });
  document.addEventListener('sycamore:snapshot', (event) => {
    const snapshot = (event as CustomEvent<Snapshot>).detail;
    context.events = snapshot.events;
    context.manifest = snapshot.manifest;
    sync();
    render();
  });
  sync();
  render();
}
