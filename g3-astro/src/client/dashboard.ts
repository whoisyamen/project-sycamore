import { markBoot } from './boot';
import { filterEvents, readState, stateUrl, defaults, type DashboardState } from './state';
import { eventCard, eventDetail } from './render';
import type { EventMap } from './map';
import type { Snapshot, DataContext } from '../data/types';

export function initDashboard(
  context: DataContext,
  createMap: (select: (id: number) => void) => EventMap | Promise<EventMap>,
) {
  const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
  const dashboard = $('main');
  const feed = $('feed-list');
  const panel = $('detail-panel');
  const search = $<HTMLInputElement>('search');
  const severity = $<HTMLSelectElement>('severity');
  const range = $<HTMLSelectElement>('range');
  const source = $<HTMLSelectElement>('source');
  const mode = $<HTMLSelectElement>('mode');
  const sort = $<HTMLSelectElement>('sort');
  let state: DashboardState = readState(new URL(location.href));
  let map: EventMap | null = null;
  let originFocus: HTMLElement | null = null;
  let sharing = false;
  const smallScreen = window.matchMedia('(max-width: 979px)');
  const fullscreenButton = document.querySelector<HTMLButtonElement>('[data-map-fullscreen]');
  let fallbackFullscreen = false;
  function announce(message: string) {
    $('announcement').textContent = message;
  }
  function presentationActive() {
    return document.fullscreenElement === dashboard || fallbackFullscreen;
  }
  function syncPresentation(enabled = presentationActive()) {
    dashboard.classList.toggle('map-presentation', enabled);
    fullscreenButton?.setAttribute('aria-pressed', String(enabled));
    if (fullscreenButton) {
      const label = enabled ? 'Exit fullscreen map' : 'Enter fullscreen map';
      fullscreenButton.setAttribute('aria-label', label);
      fullscreenButton.title = label;
      fullscreenButton.textContent = enabled ? '×' : '⛶';
    }
    map?.setPresentationMode?.(enabled);
    window.requestAnimationFrame(() => map?.resize());
  }
  async function toggleFullscreen() {
    if (presentationActive()) {
      if (document.fullscreenElement === dashboard && document.exitFullscreen) {
        await document.exitFullscreen();
        syncPresentation(false);
      } else {
        fallbackFullscreen = false;
        syncPresentation(false);
      }
      return;
    }
    if (dashboard.requestFullscreen) {
      try {
        await dashboard.requestFullscreen();
        syncPresentation(true);
        return;
      } catch {
        // Browser fullscreen can be unavailable in embedded/local contexts.
      }
    }
    fallbackFullscreen = true;
    syncPresentation(true);
  }
  fullscreenButton?.addEventListener('click', () => void toggleFullscreen());
  document.addEventListener('fullscreenchange', () => {
    fallbackFullscreen = false;
    syncPresentation(document.fullscreenElement === dashboard);
  });
  function updateUrl(push = false) {
    history[push ? 'pushState' : 'replaceState'](null, '', stateUrl(state, location.href));
  }
  function syncView() {
    dashboard.dataset.tab = state.view;
    document
      .querySelectorAll<HTMLButtonElement>('.view-tabs [data-tab]')
      .forEach((tab) => tab.setAttribute('aria-pressed', String(tab.dataset.tab === state.view)));
    map?.setSuspended?.(state.view !== 'map');
    map?.resize();
  }
  function syncSourceOptions() {
    const sources = [...new Set(context.events.map((event) => event.src))].sort((a, b) =>
      a.localeCompare(b),
    );
    if (state.src !== 'all' && !sources.includes(state.src)) sources.push(state.src);
    const wanted = ['all', ...sources];
    const current = [...source.options].map((option) => option.value);
    if (current.length === wanted.length && current.every((value, i) => value === wanted[i]))
      return;
    source.replaceChildren();
    for (const value of wanted) {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = value === 'all' ? 'All sources' : value;
      source.append(option);
    }
  }
  function syncControls() {
    syncSourceOptions();
    search.value = state.q;
    severity.value = state.sev;
    range.value = state.range;
    source.value = state.src;
    mode.value = state.mode;
    sort.value = state.sort;
    const topic = $<HTMLSelectElement>('topic-filter');
    const lens = $<HTMLSelectElement>('lens-filter');
    if (topic) topic.value = state.topic;
    if (lens) lens.value = state.lens;
    document
      .querySelectorAll<HTMLButtonElement>('[data-topic]')
      .forEach((button) =>
        button.setAttribute('aria-pressed', String(button.dataset.topic === state.topic)),
      );
    document
      .querySelectorAll<HTMLButtonElement>('[data-lens]')
      .forEach((button) =>
        button.setAttribute('aria-pressed', String(button.dataset.lens === state.lens)),
      );
    $('legacy-mode').hidden = state.mode === 'all';
    $('legacy-mode').textContent =
      state.mode === 'pulse'
        ? 'Shared filter: corroborated reporting. Reset to show all.'
        : 'Shared filter: single-source reporting. Reset to show all.';
    syncView();
  }
  function syncModal() {
    const modal = smallScreen.matches && !panel.hidden;
    if (modal) panel.setAttribute('aria-modal', 'true');
    else panel.removeAttribute('aria-modal');
    for (const selector of [
      '.site-header',
      '.feed-panel',
      '.view-tabs',
      '.world-map',
      '.horizon-heading',
      '.map-view-toolbar',
    ]) {
      const el = document.querySelector<HTMLElement>(selector);
      if (el) el.inert = modal;
    }
  }
  function fallbackFocus(): HTMLElement {
    return smallScreen.matches && dashboard.dataset.tab === 'map'
      ? document.querySelector<HTMLElement>('.view-tabs [data-tab="map"]')!
      : search;
  }
  function render(preserveFeedFocus = true) {
    const focusedId =
      preserveFeedFocus && feed.contains(document.activeElement)
        ? (document.activeElement as HTMLElement).dataset.event
        : null;
    const scroll = feed.scrollTop;
    const visible = filterEvents(context.events, state);
    const displayed =
      dashboard.classList.contains('horizon-dashboard') && state.view === 'map'
        ? visible.slice(0, 12)
        : visible;
    feed.innerHTML =
      displayed
        .map((e) => eventCard(e, true, e.id === state.event, false, state.view === 'feed'))
        .join('') ||
      '<p class="empty-state">No events match this view. Try another topic or reset the filters.</p>';
    feed.scrollTop = scroll;
    if (focusedId)
      feed
        .querySelector<HTMLElement>(`[data-event="${focusedId}"]`)
        ?.focus({ preventScroll: true });
    $('feed-count').textContent = String(visible.length);
    $('map-event-count').textContent = String(visible.length);
    const selected = context.events.find((e) => e.id === state.event);
    const hadFocus = panel.contains(document.activeElement);
    if (selected) {
      const html = eventDetail(selected);
      if ($('detail-body').innerHTML !== html) {
        const active = document.activeElement;
        const href =
          active instanceof HTMLAnchorElement && panel.contains(active) ? active.href : null;
        $('detail-body').innerHTML = html;
        if (href)
          [...panel.querySelectorAll<HTMLAnchorElement>('a')].find((a) => a.href === href)?.focus();
      }
      panel.hidden = false;
    } else {
      panel.hidden = true;
    }
    const notice = $('selection-notice');
    notice.hidden = state.event === null || Boolean(selected);
    notice.textContent =
      'This event is outside the current feed. Try another signal or reset the filters.';
    // Keep a deep-linked selection on the map even if it is outside the active filter.
    map?.update(
      selected && !visible.some((e) => e.id === selected.id) ? [...visible, selected] : visible,
      state.event,
    );
    syncModal();
    if (hadFocus && panel.hidden) fallbackFocus().focus();
  }
  function select(id: number | null, push = true) {
    if (id !== null)
      originFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    state.event = id;
    $('share-status').textContent = '';
    updateUrl(push);
    render();
    if (id !== null) {
      if (state.view === 'map') map?.focus(id);
      $('close-detail').focus();
    } else {
      const oldId = originFocus?.dataset.event;
      const replacement = oldId ? feed.querySelector<HTMLElement>(`[data-event="${oldId}"]`) : null;
      const target = replacement ?? (originFocus?.isConnected ? originFocus : fallbackFocus());
      target.focus({ preventScroll: true });
    }
  }
  function changeFilters() {
    // Preserve the selected event: filter edits must never erase a shared selection.
    syncControls();
    updateUrl();
    render();
    announce(`${filterEvents(context.events, state).length} matching events`);
  }
  feed.addEventListener('click', (e) => {
    const link = (e.target as HTMLElement).closest<HTMLAnchorElement>('[data-event]');
    if (!link || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    select(Number(link.dataset.event));
  });
  feed.addEventListener('keydown', (e) => {
    if (!['ArrowDown', 'ArrowUp'].includes(e.key)) return;
    const links = [...feed.querySelectorAll<HTMLAnchorElement>('[data-event]')];
    const index = links.indexOf(document.activeElement as HTMLAnchorElement);
    if (index < 0 || !links.length) return;
    e.preventDefault();
    links[(index + (e.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length]?.focus();
  });
  const feedPanel = document.querySelector<HTMLElement>('.horizon-reporting');
  const feedCollapse = document.querySelector<HTMLButtonElement>('[data-feed-collapse]');
  function setFeedCollapsed(collapsed: boolean) {
    if (!feedPanel || !feedCollapse) return;
    feedPanel.dataset.collapsed = String(collapsed);
    feedCollapse.setAttribute('aria-expanded', String(!collapsed));
    const label = collapsed ? 'Expand reporting tray' : 'Collapse reporting tray';
    feedCollapse.setAttribute('aria-label', label);
    feedCollapse.title = label;
    // The tray is a globe inset, so its height changes the stage the camera frames.
    window.requestAnimationFrame(() => map?.reframe?.());
  }
  feedCollapse?.addEventListener('click', () =>
    setFeedCollapsed(feedPanel?.dataset.collapsed !== 'true'),
  );
  $<HTMLSelectElement>('topic-filter')?.addEventListener('change', (e) => {
    state.topic = (e.target as HTMLSelectElement).value as DashboardState['topic'];
    changeFilters();
  });
  $<HTMLSelectElement>('lens-filter')?.addEventListener('change', (e) => {
    state.lens = (e.target as HTMLSelectElement).value as DashboardState['lens'];
    changeFilters();
  });
  search.closest('form')?.addEventListener('submit', (e) => e.preventDefault());
  document.querySelectorAll<HTMLButtonElement>('[data-topic]').forEach((button) =>
    button.addEventListener('click', () => {
      state.topic = button.dataset.topic as DashboardState['topic'];
      changeFilters();
    }),
  );
  document.querySelectorAll<HTMLButtonElement>('[data-lens]').forEach((button) =>
    button.addEventListener('click', () => {
      state.lens = button.dataset.lens as DashboardState['lens'];
      changeFilters();
    }),
  );
  search.addEventListener('input', () => {
    state.q = search.value;
    changeFilters();
  });
  severity.addEventListener('change', () => {
    state.sev = severity.value as DashboardState['sev'];
    changeFilters();
  });
  range.addEventListener('change', () => {
    state.range = range.value as DashboardState['range'];
    changeFilters();
  });
  source.addEventListener('change', () => {
    state.src = source.value || 'all';
    changeFilters();
  });
  mode.addEventListener('change', () => {
    state.mode = mode.value as DashboardState['mode'];
    changeFilters();
  });
  sort.addEventListener('change', () => {
    state.sort = sort.value as DashboardState['sort'];
    changeFilters();
  });
  $('reset-filters').addEventListener('click', () => {
    const view = state.view;
    state = { ...defaults, view };
    changeFilters();
  });
  $('close-detail').addEventListener('click', () => select(null));
  function setView(view: DashboardState['view'], push = true) {
    if (state.view === view) {
      syncView();
      return;
    }
    state.view = view;
    syncView();
    updateUrl(push);
    if (view === 'map' && state.event !== null) map?.focus(state.event);
    announce(view === 'map' ? 'Globe view' : 'Feed view');
  }
  document
    .querySelectorAll<HTMLButtonElement>('.view-tabs [data-tab]')
    .forEach((button) =>
      button.addEventListener('click', () => setView(button.dataset.tab as DashboardState['view'])),
    );
  window.addEventListener('popstate', () => {
    state = readState(new URL(location.href));
    syncControls();
    render();
    if (state.event) {
      if (state.view === 'map') map?.focus(state.event);
      if (!panel.hidden) $('close-detail').focus();
    }
  });
  window.addEventListener('hashchange', () => {
    state = readState(new URL(location.href));
    syncControls();
    render();
    if (state.event) {
      if (state.view === 'map') map?.focus(state.event);
      if (!panel.hidden) $('close-detail').focus();
    }
  });
  smallScreen.addEventListener('change', () => {
    syncModal();
    map?.resize();
  });
  document.addEventListener('keydown', (e) => {
    const editing =
      e.target instanceof HTMLElement
        ? e.target.closest('input,textarea,select,[contenteditable="true"]')
        : null;
    if (e.key === 'Escape' && fallbackFullscreen) {
      e.preventDefault();
      fallbackFullscreen = false;
      syncPresentation(false);
      return;
    }
    if (e.key === 'Escape' && document.fullscreenElement === dashboard) return;
    if (e.key === 'Escape' && !panel.hidden) {
      e.preventDefault();
      select(null);
    }
    if (e.key === '/' && !editing && !e.ctrlKey && !e.metaKey && !e.altKey && panel.hidden) {
      e.preventDefault();
      setView('feed');
      search.focus();
    }
    if (e.key === 'Tab' && !panel.hidden && smallScreen.matches) {
      const controls = [
        ...panel.querySelectorAll<HTMLElement>(
          'a[href],button:not([disabled]),input,select,textarea,[tabindex="0"]',
        ),
      ];
      const first = controls[0],
        last = controls.at(-1);
      if (e.shiftKey && (document.activeElement === first || document.activeElement === panel)) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    }
  });
  $('share-event').addEventListener('click', async () => {
    if (!state.event || sharing) return;
    const url = stateUrl(state, location.href).href;
    sharing = true;
    try {
      await navigator.clipboard.writeText(url);
      $('share-status').textContent = 'Link copied';
    } catch {
      const label = document.createElement('label');
      label.textContent = 'Copy this link:';
      const input = document.createElement('input');
      input.readOnly = true;
      input.value = url;
      input.className = 'share-fallback';
      label.append(input);
      $('share-status').replaceChildren(label);
      input.focus();
      input.select();
    } finally {
      sharing = false;
    }
  });
  document.addEventListener('sycamore:snapshot', (e) => {
    const snapshot = (e as CustomEvent<Snapshot>).detail;
    context.events = snapshot.events;
    context.manifest = snapshot.manifest;
    syncSourceOptions();
    render();
  });
  syncControls();
  function attachMap(instance: EventMap) {
    map = instance;
    map.setPresentationMode?.(presentationActive());
    syncView();
    render();
    if (state.event && state.view === 'map') map.focus(state.event);
    const imagery = document.getElementById('map')?.dataset.imagery;
    markBoot(
      'globe',
      imagery === 'timeout' ? 'Globe is up. Map imagery is still loading.' : undefined,
    );
  }
  try {
    const result = createMap((id) => select(id));
    if (result instanceof Promise)
      void result.then(attachMap).catch(() => {
        $('map-error').hidden = false;
        markBoot('globe', 'Map unavailable. The feed still works.');
      });
    else attachMap(result);
  } catch {
    $('map-error').hidden = false;
    markBoot('globe', 'Map unavailable. The feed still works.');
  }
  render(false);
  markBoot('feed');
  if (state.event) {
    if (!panel.hidden) $('close-detail').focus();
  }
  window.addEventListener('pagehide', (e) => {
    if (!e.persisted) map?.destroy();
  });
}
