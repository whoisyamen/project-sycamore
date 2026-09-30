import type { DataContext, Snapshot } from '../data/types';
import { dataStatus } from '../data/status';
import { readState, stateUrl } from './state';
import { threatDesk } from './threat';
import { bindDeskPaging } from './desk';

export function initNocturne(context: DataContext) {
  const collection = document.querySelector<HTMLElement>('[data-managed="nocturne"]')!;
  const search = document.getElementById('search') as HTMLInputElement;
  const range = document.getElementById('desk-range') as HTMLSelectElement;
  const builtIds = new Set(context.events.map((event) => event.id));
  let state = readState(new URL(location.href));
  function render() {
    const focused = document.activeElement;
    const href =
      focused instanceof HTMLAnchorElement && collection.contains(focused) ? focused.href : null;
    const pagingSection =
      focused instanceof HTMLButtonElement && collection.contains(focused)
        ? focused.dataset.section
        : null;
    collection.innerHTML = threatDesk(context.events, Date.now(), builtIds, state);
    bindDeskPaging(collection);
    // Preserve historical section links and paging without putting every list above the fold.
    const section = location.hash.slice(1);
    collection.querySelectorAll<HTMLElement>(':scope > .desk-section').forEach((element) => {
      element.hidden = element.id !== section;
    });
    search.value = state.q;
    range.value = state.range;
    document.querySelectorAll<HTMLButtonElement>('[data-desk-lens]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.deskLens === state.lens));
    });
    document.getElementById('desk-health-label')!.textContent = dataStatus(
      context.manifest,
      context.demo,
    ).label;
    if (href) {
      const replacement = [...collection.querySelectorAll<HTMLAnchorElement>('a')].find(
        (link) => link.href === href,
      );
      if (replacement) replacement.focus({ preventScroll: true });
      else {
        collection.tabIndex = -1;
        collection.focus({ preventScroll: true });
      }
    }
    if (pagingSection)
      collection
        .querySelector<HTMLButtonElement>(`[data-section="${pagingSection}"]`)
        ?.focus({ preventScroll: true });
  }
  function update(push = false, hash = '') {
    const url = stateUrl(state, location.href);
    url.pathname = '/intelligence';
    url.hash = hash;
    history[push ? 'pushState' : 'replaceState'](null, '', url);
    render();
    document.getElementById('announcement')!.textContent = 'Threat desk view updated';
  }
  search.closest('form')?.addEventListener('submit', (event) => event.preventDefault());
  search.addEventListener('input', () => {
    state.q = search.value;
    update();
  });
  range.addEventListener('change', () => {
    state.range = range.value as typeof state.range;
    update();
  });
  document.querySelectorAll<HTMLButtonElement>('[data-desk-lens]').forEach((button) =>
    button.addEventListener('click', () => {
      state.lens = button.dataset.deskLens as typeof state.lens;
      update(true);
    }),
  );
  document.getElementById('desk-reset')!.addEventListener('click', () => {
    state = readState(new URL('/intelligence', location.href));
    update();
  });
  document.querySelectorAll<HTMLAnchorElement>('a[href^="#"]').forEach((link) => {
    if (!link.closest('.nocturne-page')) return;
    link.addEventListener('click', (event) => {
      event.preventDefault();
      const section = link.hash.slice(1);
      if (['vulnerabilities', 'policy', 'emerging'].includes(section))
        state.lens = section as typeof state.lens;
      update(true, link.hash);
      const destination = collection.querySelector<HTMLElement>(`#${section}`);
      if (destination) {
        destination.tabIndex = -1;
        destination.focus({ preventScroll: true });
        destination.scrollIntoView({ block: 'start' });
      }
    });
  });
  const restore = () => {
    state = readState(new URL(location.href));
    render();
  };
  window.addEventListener('popstate', restore);
  window.addEventListener('hashchange', restore);
  document.addEventListener('sycamore:snapshot', (event) => {
    const snapshot = (event as CustomEvent<Snapshot>).detail;
    context.events = snapshot.events;
    context.manifest = snapshot.manifest;
    render();
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
  });
  render();
}
