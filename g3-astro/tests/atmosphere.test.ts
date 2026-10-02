import { test } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { installAtmosphere } from '../src/client/atmosphere';

test('sound is opt-in, independently muted, suspended offscreen and released on navigation', async () => {
  const dom = new JSDOM(
    '<div id="controls"></div><button id="action">Action</button><aside id="detail-panel"><div id="detail-body"></div></aside>',
    { pretendToBeVisual: true },
  );
  const saved = new Map<string, PropertyDescriptor | undefined>();
  for (const key of ['window', 'document', 'Element', 'HTMLSelectElement', 'MutationObserver']) {
    saved.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
    Object.defineProperty(globalThis, key, {
      value: key === 'window' ? dom.window : (dom.window as any)[key],
      configurable: true,
    });
  }
  dom.window.matchMedia = (() => ({ matches: true })) as any;
  const contexts: MockAudio[] = [];
  class Param {
    value = 0;
    setTargetAtTime(value: number) {
      this.value = value;
    }
    setValueAtTime() {}
    linearRampToValueAtTime() {}
    exponentialRampToValueAtTime() {}
  }
  class Node {
    gain = new Param();
    frequency = new Param();
    type = '';
    onended: (() => void) | null = null;
    stopped = false;
    disconnected = false;
    connect(target: Node) {
      return target;
    }
    disconnect() {
      this.disconnected = true;
    }
    start() {}
    stop() {
      this.stopped = true;
    }
  }
  class MockAudio {
    state = 'suspended';
    currentTime = 1;
    destination = new Node();
    nodes: Node[] = [];
    voices: Node[] = [];
    constructor() {
      contexts.push(this);
    }
    node() {
      const node = new Node();
      this.nodes.push(node);
      return node;
    }
    createGain() {
      return this.node();
    }
    createBiquadFilter() {
      return this.node();
    }
    createOscillator() {
      const node = this.node();
      this.voices.push(node);
      return node;
    }
    async resume() {
      this.state = 'running';
    }
    async suspend() {
      this.state = 'suspended';
    }
    async close() {
      this.state = 'closed';
    }
  }
  Object.defineProperty(dom.window, 'AudioContext', { value: MockAudio, configurable: true });
  const flush = () => new Promise((resolve) => setImmediate(resolve));
  const doc = dom.window.document;
  const controls = doc.getElementById('controls')!;
  let atmosphere: ReturnType<typeof installAtmosphere> | null = null;
  try {
    atmosphere = installAtmosphere(controls);
    const ambient = controls.querySelector<HTMLButtonElement>('[data-sound="ambient"]')!;
    const interactions = controls.querySelector<HTMLButtonElement>('[data-sound="interactions"]')!;
    const select = () =>
      doc.dispatchEvent(new dom.window.CustomEvent('sycamore:selection', { detail: 1 }));
    doc.getElementById('action')!.click();
    select();
    assert.equal(contexts.length, 0, 'loading and selection never enable audio');
    assert.equal(ambient.getAttribute('aria-pressed'), 'false');
    assert.equal(interactions.getAttribute('aria-pressed'), 'false');
    ambient.click();
    await flush();
    const audio = contexts[0];
    assert.equal(audio.state, 'running');
    assert.equal(audio.voices.length, 3);
    assert.ok(audio.nodes[0].gain.value > 0);
    select();
    assert.equal(audio.voices.length, 3, 'ambient does not enable interaction tones');
    interactions.click();
    await flush();
    doc.getElementById('action')!.click();
    select();
    assert.equal(audio.voices.length, 5, 'actions and report selections each have a tone');
    ambient.click();
    await flush();
    assert.equal(audio.nodes[0].gain.value, 0);
    assert.equal(audio.state, 'running', 'interaction sounds remain enabled');
    Object.defineProperty(doc, 'hidden', { value: true, configurable: true });
    doc.dispatchEvent(new dom.window.Event('visibilitychange'));
    await flush();
    assert.equal(audio.state, 'suspended');
    assert.equal(doc.documentElement.dataset.pageHidden, 'true');
    select();
    assert.equal(audio.voices.length, 5, 'hidden pages cannot play sounds');
    Object.defineProperty(doc, 'hidden', { value: false, configurable: true });
    doc.dispatchEvent(new dom.window.Event('visibilitychange'));
    await flush();
    assert.equal(audio.state, 'running');
    interactions.click();
    await flush();
    assert.equal(audio.state, 'suspended', 'both toggles off suspends the audio graph');
    dom.window.dispatchEvent(new dom.window.PageTransitionEvent('pagehide', { persisted: true }));
    assert.equal(audio.state, 'suspended', 'cached navigation suspends rather than destroys');
    dom.window.dispatchEvent(new dom.window.PageTransitionEvent('pageshow', { persisted: true }));
    await flush();
    assert.equal(audio.state, 'suspended', 'restoring a muted page does not unmute it');
    atmosphere.destroy();
    atmosphere.destroy();
    await flush();
    assert.equal(audio.state, 'closed');
    assert.ok(audio.voices.every((voice) => voice.stopped && voice.disconnected));
    assert.ok(audio.nodes.every((node) => node.disconnected));
    assert.equal(controls.querySelector('.sound-controls'), null);
    assert.equal(doc.documentElement.dataset.pageHidden, undefined);
    Object.defineProperty(dom.window, 'AudioContext', { value: undefined, configurable: true });
    atmosphere = installAtmosphere(controls);
    assert.ok(
      [...controls.querySelectorAll<HTMLButtonElement>('button')].every(
        (button) => button.disabled,
      ),
    );
    assert.equal(contexts.length, 1, 'unsupported audio leaves the dashboard usable');
  } finally {
    atmosphere?.destroy();
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else Reflect.deleteProperty(globalThis, key);
    }
    dom.window.close();
  }
});
