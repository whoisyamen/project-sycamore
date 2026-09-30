import type { DataContext, Snapshot } from '../data/types';
import { dataStatus } from '../data/status';
import { fetchSnapshot, acceptSnapshot } from './refresh';
import { eventDetail } from './render';
import { installBoot, markBoot } from './boot';
import { bindDeskPaging } from './desk';
import { threatDesk } from './threat';
installBoot();
export const context: DataContext = JSON.parse(
  document.body.dataset.context ?? '{"events":[],"manifest":null,"demo":false}',
);
const builtIds = new Set(context.events.map((e) => e.id));
let current: Snapshot | null = context.manifest
  ? { version: 1, events: context.events, manifest: context.manifest }
  : null;
let disconnected = false;
function updateStatus() {
  const status = dataStatus(context.manifest, context.demo, disconnected);
  const wrapper = document.querySelector<HTMLElement>('.sync-status');
  if (wrapper) {
    wrapper.dataset.status = status.kind;
    wrapper.title = status.detail;
  }
  const label = document.getElementById('sync-label');
  if (label) label.textContent = status.label;
}
function replaceContent(container: HTMLElement, html: string) {
  if (container.innerHTML === html) return;
  const active = document.activeElement;
  const href =
    active instanceof HTMLAnchorElement && container.contains(active) ? active.href : null;
  container.innerHTML = html;
  if (href) {
    const link = [...container.querySelectorAll<HTMLAnchorElement>('a')].find(
      (a) => a.href === href,
    );
    if (link) link.focus({ preventScroll: true });
    else {
      container.tabIndex = -1;
      container.focus({ preventScroll: true });
    }
  }
}
function updateCollections() {
  const collection = document.querySelector<HTMLElement>('[data-collection="intelligence"]');
  const openSection =
    document.activeElement instanceof HTMLButtonElement
      ? document.activeElement.dataset.section
      : null;
  if (collection && collection.dataset.managed !== 'nocturne') {
    replaceContent(collection, threatDesk(context.events, Date.now(), builtIds));
    bindDeskPaging(collection);
    if (openSection)
      collection
        .querySelector<HTMLButtonElement>(`[data-desk-more][data-section="${openSection}"]`)
        ?.focus({ preventScroll: true });
  }
  const article = document.querySelector<HTMLElement>('[data-event-page]');
  if (article) {
    const event = context.events.find((e) => e.id === Number(article.dataset.eventPage));
    if (event) replaceContent(article, eventDetail(event));
    const note = document.getElementById('event-archive-notice');
    if (note) note.hidden = Boolean(event);
  }
}
let pending = false;
let snapshotSettled = false;
function settleSnapshot(detail?: string) {
  if (snapshotSettled) return;
  snapshotSettled = true;
  markBoot('snapshot', detail);
}
async function refresh() {
  if (context.demo) {
    settleSnapshot('Demo snapshot. Live refresh is off.');
    return;
  }
  if (pending || document.hidden) {
    if (document.hidden) settleSnapshot();
    return;
  }
  pending = true;
  try {
    const next = acceptSnapshot(current, await fetchSnapshot());
    current = next;
    context.events = next.events;
    context.manifest = next.manifest;
    disconnected = false;
    updateCollections();
    document.dispatchEvent(new CustomEvent('sycamore:snapshot', { detail: next }));
    settleSnapshot();
  } catch {
    disconnected = true;
    settleSnapshot('Refresh failed. Showing the last published snapshot.');
  } finally {
    pending = false;
    updateStatus();
  }
}
updateStatus();
// Carry a reading selection and its filters between the three workspaces.
document.querySelectorAll<HTMLAnchorElement>('.site-header nav a').forEach((link) => {
  link.addEventListener('click', () => {
    const current = new URL(location.href);
    const target = new URL(link.getAttribute('href')!, location.href);
    target.search = '';
    for (const key of ['q', 'topic', 'sev', 'range', 'src', 'lens', 'sort', 'mode', 'event']) {
      const value = current.searchParams.get(key);
      if (value) target.searchParams.set(key, value);
    }
    link.href = target.href;
  });
});
bindDeskPaging(document);
void refresh();
const interval = window.setInterval(() => {
  updateStatus();
  void refresh();
}, 60000);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) {
    updateStatus();
    void refresh();
  }
});
window.addEventListener('pagehide', (event) => {
  if (!event.persisted) clearInterval(interval);
});

// Capture handles dynamically rendered feed/detail images as well as initial HTML.
function hideFailedImage(image: HTMLImageElement) {
  const wrapper = image.closest('.card-thumb, .event-hero');
  if (wrapper instanceof HTMLElement) wrapper.hidden = true;
}
document.addEventListener(
  'error',
  (event) => {
    if (event.target instanceof HTMLImageElement) hideFailedImage(event.target);
  },
  true,
);
document.querySelectorAll<HTMLImageElement>('.card-thumb img, .event-hero img').forEach((image) => {
  if (image.complete && image.naturalWidth === 0) hideFailedImage(image);
});
