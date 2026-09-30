export type BootStep = 'snapshot' | 'globe' | 'feed';

const STEPS: BootStep[] = ['snapshot', 'globe', 'feed'];
const READY_LABEL: Record<BootStep, string> = {
  snapshot: 'Published reporting loaded',
  globe: 'Globe ready',
  feed: 'Signal feed rendered',
};

type StepState = { done: boolean; detail?: string };
type BootQueue = Record<BootStep, StepState>;

function queue(): BootQueue {
  const host = window as Window & { __sycamoreBoot?: BootQueue };
  host.__sycamoreBoot ??= {
    snapshot: { done: false },
    globe: { done: false },
    feed: { done: false },
  };
  return host.__sycamoreBoot;
}

/** Record one overview startup step. Safe to call before the screen is installed. */
export function markBoot(step: BootStep, detail?: string) {
  queue()[step] = { done: true, detail };
  document.dispatchEvent(new CustomEvent('sycamore:boot', { detail: step }));
}

export function installBoot() {
  const screen = document.getElementById('boot-screen');
  if (!screen || screen.dataset.installed === 'true') return;
  screen.dataset.installed = 'true';
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const started = performance.now();
  const blocked = ['.skip-link', '.site-header', '#main']
    .map((selector) => document.querySelector<HTMLElement>(selector))
    .filter((el): el is HTMLElement => Boolean(el));
  for (const el of blocked) el.inert = true;

  let closed = false;
  let safety = 0;
  const release = () => {
    if (closed) return;
    closed = true;
    window.clearTimeout(safety);
    for (const el of blocked) el.inert = false;
    const finish = () => {
      screen.hidden = true;
      screen.setAttribute('aria-busy', 'false');
      if (!screen.contains(document.activeElement)) return;
      const panel = document.getElementById('detail-panel');
      const target =
        panel && !panel.hidden
          ? document.getElementById('close-detail')
          : document.getElementById('main');
      target?.focus();
    };
    if (reduced) finish();
    else {
      screen.classList.add('is-leaving');
      window.setTimeout(finish, 280);
    }
  };
  const dismiss = (immediate = false) => {
    if (immediate || reduced) release();
    else window.setTimeout(release, Math.max(0, 500 - (performance.now() - started)));
  };
  const paint = () => {
    const state = queue();
    let done = 0;
    for (const step of STEPS) {
      const item = screen.querySelector<HTMLElement>(`[data-boot-step="${step}"]`);
      if (!item) continue;
      const ready = state[step].done;
      item.dataset.state = ready ? 'done' : 'wait';
      const detail = item.querySelector('.boot-step-detail');
      if (detail && ready) detail.textContent = state[step].detail || READY_LABEL[step];
      if (ready) done += 1;
    }
    const bar = screen.querySelector<HTMLElement>('.boot-progress > span');
    if (bar) bar.style.width = `${(done / STEPS.length) * 100}%`;
    const progress = screen.querySelector<HTMLElement>('[role="progressbar"]');
    progress?.setAttribute('aria-valuenow', String(done));
    if (done === STEPS.length) dismiss(false);
  };

  screen.querySelector('[data-boot-skip]')?.addEventListener('click', () => dismiss(true));
  document.addEventListener('sycamore:boot', paint);
  safety = window.setTimeout(() => dismiss(true), 20000);
  paint();
  screen.querySelector<HTMLElement>('[data-boot-skip]')?.focus();
}
