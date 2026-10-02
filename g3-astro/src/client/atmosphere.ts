/** Decorative sound and detail transitions. Audio is opt-in and entirely local. */
export function installAtmosphere(controls: HTMLElement) {
  let ambient = false;
  let interactions = false;
  let disposed = false;
  let away = false;
  let audio: AudioContext | null = null;
  let ambientGain: GainNode | null = null;
  const oscillators = new Set<OscillatorNode>();
  const nodes = new Set<AudioNode>();
  const animations = new Set<Animation>();
  const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const section = document.createElement('div');
  section.className = 'globe-control-section sound-controls';
  section.setAttribute('role', 'group');
  section.setAttribute('aria-label', 'Sound');
  const label = document.createElement('span');
  label.className = 'globe-control-label';
  label.textContent = 'Sound';
  const buttons = document.createElement('div');
  buttons.className = 'globe-effects-buttons';
  section.append(label, buttons);
  controls.appendChild(section);

  const makeToggle = (name: string, key: 'ambient' | 'interactions') => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'globe-layer-chip';
    button.dataset.sound = key;
    button.textContent = name;
    button.setAttribute('aria-pressed', 'false');
    button.title = `Enable ${name.toLowerCase()}`;
    button.addEventListener('click', () => {
      if (key === 'ambient') ambient = !ambient;
      else interactions = !interactions;
      refresh();
      void syncAudio();
    });
    buttons.appendChild(button);
    return button;
  };
  const ambientButton = makeToggle('Ambient sound', 'ambient');
  const interactionButton = makeToggle('Interaction sounds', 'interactions');

  function refresh() {
    for (const [button, enabled] of [
      [ambientButton, ambient],
      [interactionButton, interactions],
    ] as const) {
      button.setAttribute('aria-pressed', String(enabled));
      button.classList.toggle('active', enabled);
      button.title = `${enabled ? 'Mute' : 'Enable'} ${button.textContent!.toLowerCase()}`;
    }
  }

  function prepareAudio() {
    if (audio) return audio;
    // Constructed only after a sound toggle, never on page load or a refresh.
    audio = new window.AudioContext();
    ambientGain = audio.createGain();
    ambientGain.gain.value = 0;
    const filter = audio.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = 180;
    ambientGain.connect(filter).connect(audio.destination);
    nodes.add(ambientGain);
    nodes.add(filter);
    for (const [frequency, level] of [
      [55, 0.12],
      [82.5, 0.06],
      [110, 0.025],
    ]) {
      const voice = audio.createOscillator();
      const gain = audio.createGain();
      voice.type = 'sine';
      voice.frequency.value = frequency;
      gain.gain.value = level;
      voice.connect(gain).connect(ambientGain);
      voice.start();
      oscillators.add(voice);
      nodes.add(voice);
      nodes.add(gain);
    }
    return audio;
  }

  async function syncAudio() {
    if (disposed) return;
    const wanted = (ambient || interactions) && !document.hidden && !away;
    if (!wanted) {
      if (audio && audio.state !== 'closed') await audio.suspend().catch(() => {});
      return;
    }
    try {
      const context = prepareAudio();
      await context.resume();
      // Visibility or the toggle may have changed while resume was pending.
      if (disposed || context.state === 'closed') return;
      if (document.hidden || away || !(ambient || interactions)) {
        await context.suspend();
        return;
      }
      ambientGain!.gain.setTargetAtTime(ambient ? 0.045 : 0, context.currentTime, 0.3);
    } catch {
      if (disposed) return;
      ambient = interactions = false;
      refresh();
      for (const button of [ambientButton, interactionButton]) {
        button.disabled = true;
        button.title = 'Sound is unavailable in this browser';
      }
      if (audio && audio.state !== 'closed') void audio.close().catch(() => {});
    }
  }

  function tone(report = false) {
    if (disposed || !interactions || document.hidden || away || audio?.state !== 'running') return;
    const context = audio;
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    const duration = report ? 0.22 : 0.055;
    const start = context.currentTime;
    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(report ? 330 : 620, start);
    oscillator.frequency.exponentialRampToValueAtTime(report ? 440 : 430, start + duration);
    gain.gain.setValueAtTime(0, start);
    gain.gain.linearRampToValueAtTime(report ? 0.025 : 0.018, start + 0.008);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    oscillator.connect(gain).connect(context.destination);
    oscillators.add(oscillator);
    nodes.add(oscillator);
    nodes.add(gain);
    oscillator.onended = () => {
      oscillator.disconnect();
      gain.disconnect();
      oscillators.delete(oscillator);
      nodes.delete(oscillator);
      nodes.delete(gain);
    };
    oscillator.start(start);
    oscillator.stop(start + duration + 0.02);
  }

  const onClick = (event: MouseEvent) => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const target = event.target;
    if (!(target instanceof Element) || target.closest('.sound-controls, [data-event]')) return;
    if (target.closest('button:not(:disabled), a[href]')) tone();
  };
  const onChange = (event: Event) => {
    if (event.target instanceof HTMLSelectElement) tone();
  };
  const onSelection = (event: Event) => {
    if ((event as CustomEvent<number | null>).detail !== null) tone(true);
  };

  const body = document.getElementById('detail-body');
  const panel = document.getElementById('detail-panel');
  const detailObserver = body
    ? new MutationObserver(() => {
        if (disposed || document.hidden || away || panel?.hidden || motionPreference.matches)
          return;
        if (!body.animate) return;
        for (const animation of animations) animation.cancel();
        animations.clear();
        const animation = body.animate([{ opacity: 0.65 }, { opacity: 1 }], {
          duration: 180,
          easing: 'ease-out',
        });
        animations.add(animation);
        animation.onfinish = () => animations.delete(animation);
      })
    : null;
  detailObserver?.observe(body!, { childList: true });

  const onVisibility = () => {
    document.documentElement.dataset.pageHidden = String(document.hidden || away);
    for (const animation of animations) {
      if (document.hidden || away) animation.pause();
      else animation.play();
    }
    void syncAudio();
  };
  const onMotionChange = () => {
    if (!motionPreference.matches) return;
    for (const animation of animations) animation.cancel();
    animations.clear();
  };
  const onPageHide = (event: PageTransitionEvent) => {
    away = true;
    if (event.persisted) onVisibility();
    else destroy();
  };
  const onPageShow = () => {
    away = false;
    onVisibility();
  };

  function destroy() {
    if (disposed) return;
    disposed = true;
    detailObserver?.disconnect();
    document.removeEventListener('click', onClick);
    document.removeEventListener('change', onChange);
    document.removeEventListener('sycamore:selection', onSelection);
    document.removeEventListener('visibilitychange', onVisibility);
    window.removeEventListener('pagehide', onPageHide);
    window.removeEventListener('pageshow', onPageShow);
    motionPreference.removeEventListener?.('change', onMotionChange);
    for (const animation of animations) animation.cancel();
    animations.clear();
    for (const oscillator of oscillators) {
      oscillator.onended = null;
      oscillator.stop();
    }
    for (const node of nodes) node.disconnect();
    oscillators.clear();
    nodes.clear();
    if (audio && audio.state !== 'closed') void audio.close().catch(() => {});
    section.remove();
    delete document.documentElement.dataset.pageHidden;
  }

  document.addEventListener('click', onClick);
  document.addEventListener('change', onChange);
  document.addEventListener('sycamore:selection', onSelection);
  document.addEventListener('visibilitychange', onVisibility);
  window.addEventListener('pagehide', onPageHide);
  window.addEventListener('pageshow', onPageShow);
  motionPreference.addEventListener?.('change', onMotionChange);
  if (!window.AudioContext) {
    for (const button of [ambientButton, interactionButton]) {
      button.disabled = true;
      button.title = 'Sound is unavailable in this browser';
    }
  }
  onVisibility();
  return { destroy };
}
