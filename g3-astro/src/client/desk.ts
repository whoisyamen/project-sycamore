/** One row on the desktop threat-desk grid. Further matches stay one click away. */
export const DESK_PAGE = 3;

const shownBySection = new Map<string, number>();

export function applyDeskPage(section: HTMLElement, shown: number) {
  const cards = [...section.querySelectorAll<HTMLElement>('.card-grid > .event-card')];
  cards.forEach((card, index) => {
    card.hidden = index >= shown;
  });
  const remaining = cards.filter((card) => card.hidden).length;
  const button = section.querySelector<HTMLButtonElement>('[data-desk-more]');
  const step = section.querySelector('[data-desk-step]');
  if (step) step.textContent = String(Math.min(DESK_PAGE, remaining));
  if (button) {
    button.hidden = remaining === 0;
    button.setAttribute('aria-expanded', String(remaining === 0));
  }
}

/** Re-apply any opened pages after a snapshot refresh replaces the desk HTML. */
export function bindDeskPaging(root: ParentNode) {
  root.querySelectorAll<HTMLElement>('[data-desk-page]').forEach((section) => {
    const id = section.id;
    const stored = shownBySection.get(id);
    if (stored != null) applyDeskPage(section, stored);
    const button = section.querySelector<HTMLButtonElement>('[data-desk-more]');
    if (!button || button.dataset.bound === 'true') return;
    button.dataset.bound = 'true';
    button.addEventListener('click', () => {
      const cards = [...section.querySelectorAll<HTMLElement>('.card-grid > .event-card')];
      const visible = cards.filter((card) => !card.hidden).length;
      const next = visible + DESK_PAGE;
      shownBySection.set(id, next);
      applyDeskPage(section, next);
      if (button.hidden) cards[visible]?.focus();
      else button.focus();
    });
  });
}
