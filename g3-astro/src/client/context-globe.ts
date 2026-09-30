import type { DataContext, Snapshot } from '../data/types';
import type { Event } from '../data/types';

function previewLocations(events: Event[]) {
  const cells = new Set<string>();
  return [...events]
    .sort((a, b) => b.ts - a.ts)
    .filter((event) => {
      const cell = `${Math.floor(event.lon / 20)}:${Math.floor(event.lat / 20)}`;
      if (cells.has(cell)) return false;
      cells.add(cell);
      return true;
    })
    .slice(0, 14);
}

/** One quiet spatial preview per reading page; no aircraft or ancillary polling. */
export async function initContextGlobe(context: DataContext) {
  const container = document.querySelector<HTMLElement>('[data-context-globe]');
  if (!container) return;
  try {
    const { createGlobe } = await import('./globe');
    const globe = await createGlobe(container, {
      layout: 'context',
      initialImagery: container.dataset.imagery === 'satellite' ? 'satellite' : 'dark',
      onSelectEvent: (id) => {
        location.href = `/?event=${id}`;
      },
    });
    globe.update(previewLocations(context.events), null);
    const visibility = new IntersectionObserver(([entry]) =>
      globe.setSuspended(!entry.isIntersecting),
    );
    visibility.observe(container);
    document.addEventListener('sycamore:snapshot', (event) => {
      globe.update(previewLocations((event as CustomEvent<Snapshot>).detail.events), null);
    });
    window.addEventListener('pagehide', (event) => {
      if (!event.persisted) {
        visibility.disconnect();
        globe.destroy();
      }
    });
  } catch {
    const fallback = container.parentElement?.querySelector<HTMLElement>('.context-globe-fallback');
    if (fallback) fallback.hidden = false;
  }
}
