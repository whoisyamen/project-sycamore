import type { DataContext, Snapshot } from '../data/types';
import { dataStatus } from '../data/status';
import { fetchSnapshot, acceptSnapshot } from './refresh';
import { boards, briefing, eventDetail } from './render';
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
  const collection = document.querySelector<HTMLElement>('[data-collection]');
  if (collection) {
    const html =
      collection.dataset.collection === 'boards'
        ? boards(context.events, builtIds)
        : briefing(context.events, Date.now(), builtIds);
    replaceContent(collection, html);
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
async function refresh() {
  if (pending || context.demo || document.hidden) return;
  pending = true;
  try {
    const next = acceptSnapshot(current, await fetchSnapshot());
    current = next;
    context.events = next.events;
    context.manifest = next.manifest;
    disconnected = false;
    updateCollections();
    document.dispatchEvent(new CustomEvent('sycamore:snapshot', { detail: next }));
  } catch {
    disconnected = true;
  } finally {
    pending = false;
    updateStatus();
  }
}
updateStatus();
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
