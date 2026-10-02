import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';
import * as Cesium from '@cesium/engine';
import { event } from './fixtures';

test('globe runtime: markers, picks, persistent cities, imagery toggles, resize and cleanup', async () => {
  // Substitute only the GPU/widget shell; collections, providers, materials,
  // entities and properties use the installed Cesium runtime.
  const dom = new JSDOM('<div id="map"></div>', { pretendToBeVisual: true });
  const saved = new Map<string, PropertyDescriptor | undefined>();
  const install = (key: string, value: unknown) => {
    saved.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
    Object.defineProperty(globalThis, key, { value, configurable: true, writable: true });
  };
  for (const key of [
    'window',
    'document',
    'HTMLCanvasElement',
    'HTMLImageElement',
    'HTMLVideoElement',
    'Image',
  ] as const)
    install(key, key === 'window' ? dom.window : dom.window[key]);
  let prefersReducedMotion = true;
  Object.defineProperty(dom.window, 'matchMedia', {
    value: () => ({
      get matches() {
        return prefersReducedMotion;
      },
    }),
  });
  let resized = () => {};
  let disconnected = false;
  install(
    'ResizeObserver',
    class {
      constructor(callback: () => void) {
        resized = callback;
      }
      observe() {}
      disconnect() {
        disconnected = true;
      }
    },
  );
  install('ImageBitmap', class {});
  install('OffscreenCanvas', class {});
  install('requestAnimationFrame', () => 1);
  install('cancelAnimationFrame', () => {});
  let selected: any;
  let clicked: number | undefined;
  let picked: unknown;
  let pickPosition = Cesium.Cartesian3.fromDegrees(10, 51);
  let viewer: any;
  class CesiumWidget {
    clock = new Cesium.Clock();
    creditDisplay = { addStaticCredit() {}, removeStaticCredit() {} };
    entities = new Cesium.EntityCollection();
    dataSources = new Cesium.DataSourceCollection();
    scene: any;
    camera: any;
    resizeCount = 0;
    rotations: { axis: Cesium.Cartesian3; angle: number }[] = [];
    destroyed = false;
    get canvas() {
      return this.scene.canvas;
    }
    constructor(container: HTMLElement, options: any) {
      viewer = this;
      const canvas = dom.window.document.createElement('canvas');
      container.appendChild(canvas);
      this.camera = {
        position: Cesium.Cartesian3.fromDegrees(20, 25, 19e6),
        direction: new Cesium.Cartesian3(),
        up: Cesium.Cartesian3.clone(Cesium.Cartesian3.UNIT_Z),
        right: new Cesium.Cartesian3(),
        positionCartographic: Cesium.Cartographic.fromDegrees(20, 25, 19e6),
        setView: ({ destination }: any) => {
          this.camera.position = Cesium.Cartesian3.clone(destination);
          Cesium.Cartesian3.normalize(
            Cesium.Cartesian3.negate(destination, this.camera.direction),
            this.camera.direction,
          );
          this.camera.positionCartographic = Cesium.Cartographic.fromCartesian(destination);
        },
        _adjustOrthographicFrustum() {},
        rotate: (axis: Cesium.Cartesian3, angle: number) => {
          this.rotations.push({ axis, angle });
          Cesium.Camera.prototype.rotate.call(this.camera, axis, angle);
          this.camera.positionCartographic = Cesium.Cartographic.fromCartesian(
            this.camera.position,
          );
        },
        flyTo: (options: any) => this.camera.setView(options),
        flyHome() {},
        zoomIn() {},
        pickEllipsoid: () => pickPosition,
      };
      this.scene = {
        canvas,
        imageryLayers: new Cesium.ImageryLayerCollection(),
        primitives: new Cesium.PrimitiveCollection(),
        globe: { ellipsoid: Cesium.Ellipsoid.WGS84 },
        skyAtmosphere: { show: true },
        skyBox: { show: false },
        preUpdate: new Cesium.Event(),
        screenSpaceCameraController: { minimumZoomDistance: 1 },
        pick: () => picked,
      };
      this.scene.imageryLayers.add(options.baseLayer);
    }
    resize() {
      this.resizeCount++;
    }
    destroy() {
      this.destroyed = true;
      this.scene.primitives.destroy();
      this.dataSources.destroy();
      this.scene.imageryLayers.destroy();
    }
  }
  install('__testCesium', { ...Cesium, CesiumWidget });
  const root = new URL('../', import.meta.url);
  const countries = JSON.parse(
    await readFile(new URL('public/data/globe/countries.geojson', root), 'utf8'),
  );
  install('fetch', async (url: string) => {
    const data = url.includes('countries.geojson')
      ? countries
      : url.includes('cities.json')
        ? [[10, 51, 'Test city', 'DE', 1000000]]
        : url.includes('flights.json')
          ? {
              version: 1,
              ts: Date.now(),
              count: 1,
              aircraft: [{ id: 'abc123', lon: 10, lat: 51, alt_m: 1000 }],
              trails: {
                abc123: [
                  [10, 51, 1],
                  [11, 51, 2],
                  [12, 51.5, 3],
                  [13, 52, 4],
                ],
              },
            }
          : url.includes('censys.json')
            ? { ts: Date.now(), count: 1, hosts: [{ ip: '192.0.2.1', lon: 10, lat: 51 }] }
            : {
                features: [
                  {
                    geometry: { coordinates: [10, 51] },
                    properties: { mag: 5, place: 'Test earthquake' },
                  },
                ],
              };
    return { ok: true, json: async () => data };
  });
  const directory = await mkdtemp(join(tmpdir(), 'sycamore-globe-test-'));
  let adapter: any;
  try {
    const source = (await readFile(new URL('src/client/globe.ts', root), 'utf8'))
      .replace(
        "import * as Cesium from '@cesium/engine';",
        'const Cesium = globalThis.__testCesium;',
      )
      .replace("import '@cesium/engine/Source/Widget/CesiumWidget.css';", '');
    const outfile = join(directory, 'globe.mjs');
    await build({
      stdin: { contents: source, loader: 'ts', resolveDir: new URL('src/client/', root).pathname },
      outfile,
      bundle: true,
      platform: 'node',
      format: 'esm',
      define: { 'import.meta.env.BASE_URL': '"/"' },
    });
    const { createGlobe } = await import(pathToFileURL(outfile).href);
    const container = dom.window.document.getElementById('map')!;
    adapter = await createGlobe(container, {
      onSelectEvent: (id: number) => {
        clicked = id;
      },
      onRegionSelected: (r: unknown) => {
        selected = r;
      },
    });
    const flush = () => new Promise((resolve) => setImmediate(resolve));
    await flush();
    const surface = viewer.scene.globe.material;
    const effectButtons = [
      ...container.querySelectorAll<HTMLButtonElement>('.globe-effects button'),
    ];
    const [waterMotion, nightLights, timeLapse] = effectButtons;
    assert.equal(surface.uniforms.nightDetail, 1);
    viewer.camera.positionCartographic.height = 1_000_000;
    viewer.scene.preUpdate.raiseEvent();
    assert.equal(surface.uniforms.nightDetail, 0, 'close zoom suppresses low-res night texture');
    viewer.camera.positionCartographic.height = 19_000_000;
    viewer.scene.preUpdate.raiseEvent();
    assert.equal(surface.uniforms.nightDetail, 1, 'global view retains full night composite');
    assert.equal(viewer.scene.skyBox.show, true, 'the star-field background stays visible');
    assert.equal(
      viewer.scene.skyAtmosphere.atmosphereLightIntensity,
      9,
      'reduced motion keeps the atmosphere steady',
    );
    prefersReducedMotion = false;
    viewer.scene.preUpdate.raiseEvent();
    const glow = viewer.scene.skyAtmosphere.atmosphereLightIntensity;
    assert.ok(glow > 9 && glow <= 10.2, 'normal motion advances a restrained atmosphere pulse');
    Object.defineProperty(dom.window.document, 'hidden', { value: true, configurable: true });
    viewer.scene.preUpdate.raiseEvent();
    assert.equal(
      viewer.scene.skyAtmosphere.atmosphereLightIntensity,
      glow,
      'hidden pages hold the decorative phase',
    );
    Object.defineProperty(dom.window.document, 'hidden', { value: false, configurable: true });
    prefersReducedMotion = true;
    viewer.scene.preUpdate.raiseEvent();
    assert.equal(
      viewer.scene.skyAtmosphere.atmosphereLightIntensity,
      9,
      'changing the motion preference restores a steady glow',
    );
    assert.equal(
      waterMotion.getAttribute('aria-pressed'),
      'false',
      'reduced motion starts with water paused',
    );
    viewer.scene.preUpdate.raiseEvent();
    assert.equal(surface.uniforms.elapsed, 0);
    waterMotion.click();
    viewer.scene.preUpdate.raiseEvent();
    assert.ok(surface.uniforms.elapsed > 0, 'explicitly enabled water advances');
    waterMotion.click();
    const pausedAt = surface.uniforms.elapsed;
    viewer.scene.preUpdate.raiseEvent();
    assert.equal(surface.uniforms.elapsed, pausedAt, 'pausing holds the water phase');
    nightLights.click();
    assert.equal(surface.uniforms.nightEnabled, 0);
    timeLapse.click();
    assert.ok(Math.abs(viewer.clock.multiplier - 23.9344697) < 0.00001);
    assert.equal(viewer.clock.shouldAnimate, true);
    assert.equal(surface.uniforms.nightEnabled, 1, 'time lapse enables day/night');
    timeLapse.click();
    assert.equal(viewer.clock.multiplier, 1);
    assert.equal(
      viewer.clock.shouldAnimate,
      false,
      'returning to current time respects reduced motion',
    );
    adapter.update([{ ...event, lat: 51, lon: 10 }], event.id);
    assert.equal(viewer.dataSources.get(0).entities.values.length, 1);
    const selectedMarker = viewer.dataSources.get(0).entities.values[0];
    assert.ok(selectedMarker.billboard, 'selected report gains a halo on its original entity');
    assert.equal(
      selectedMarker.billboard.scale.getValue(),
      1,
      'reduced motion keeps the halo still',
    );
    adapter.update([{ ...event, lat: 51, lon: 10 }], null);
    assert.ok(
      viewer.dataSources.get(0).entities.values[0].billboard.width.getValue() <
        selectedMarker.billboard.width.getValue(),
      'clearing selection returns the beacon to its smaller resting halo',
    );
    adapter.update([{ ...event, lat: 51, lon: 10 }], event.id);
    picked = { id: viewer.dataSources.get(0).entities.values[0] };
    viewer.scene.canvas.click();
    assert.equal(clicked, event.id);
    adapter.update(
      [
        {
          ...event,
          sev: 'critical',
          lat: 51,
          lon: 10,
          summary: 'Critical infrastructure disruption with active incident response underway.',
        },
      ],
      event.id,
    );
    adapter.setPresentationMode(true);
    const presentationMarker = viewer.dataSources.get(0).entities.values[0];
    assert.ok(presentationMarker.label, 'critical incidents gain floating presentation labels');
    assert.match(
      presentationMarker.label.text.getValue(),
      /CRITICAL · London, UK/,
      'critical callout is anchored to the incident marker',
    );
    assert.equal(
      presentationMarker.point.pixelSize.getValue(),
      3.9,
      'reduced-motion presentation retains a small colored core',
    );
    adapter.setPresentationMode(false);
    assert.equal(
      viewer.dataSources.get(0).entities.values[0].label,
      undefined,
      'presentation callouts are removed when fullscreen presentation ends',
    );
    for (const [lon, lat, name] of [
      [10, 51, 'Germany'],
      [100, 60, 'Russia'],
      [-179.95, -16.82, 'Fiji'],
    ] as const) {
      picked = undefined;
      pickPosition = Cesium.Cartesian3.fromDegrees(lon, lat);
      viewer.scene.canvas.click();
      assert.equal(selected?.name, name);
      assert.ok(viewer.entities.values.length > 0);
    }
    adapter.setLayers({ events: false });
    assert.equal(adapter.getLayer('events'), false);
    assert.equal(viewer.dataSources.get(0).entities.values.length, 0);
    adapter.setLayers({ events: true, cities: true, seismic: true, censys: true });
    await flush();
    assert.equal(viewer.dataSources.get(0).entities.values.length, 1);
    assert.equal(viewer.dataSources.get(1).entities.values.length, 1);
    assert.equal(viewer.dataSources.get(1).name, 'censys');
    picked = { id: viewer.dataSources.get(1).entities.values[0] };
    viewer.scene.canvas.click();
    assert.equal(selected?.name, '192.0.2.1 · ports ?');
    assert.equal(selected?.kind, 'city');
    const cities = viewer.scene.primitives.get(0);
    viewer.camera.positionCartographic.height = 1000000;
    viewer.scene.preUpdate.raiseEvent();
    assert.equal(cities.length, 1);
    viewer.scene.preUpdate.raiseEvent();
    assert.equal(cities.length, 1, 'cities survive consecutive frames');
    picked = { id: cities.get(0).id };
    viewer.scene.canvas.click();
    assert.equal(selected?.kind, 'city');
    assert.equal(selected?.lon, 10);
    assert.equal(
      viewer.scene.primitives.get(1).length,
      3,
      'ambient route is split into a fading tail',
    );
    assert.equal(
      viewer.scene.primitives.get(1).get(0).material.type,
      Cesium.Material.ColorType,
      'flight trail uses Cesium registered color material type',
    );
    assert.ok(
      viewer.scene.primitives.get(1).get(0).material.uniforms.color.alpha <
        viewer.scene.primitives.get(1).get(2).material.uniforms.color.alpha,
      'older route history is quieter than the newest motion tail',
    );
    assert.equal(viewer.scene.primitives.get(2).length, 1, 'aircraft');
    picked = { id: viewer.scene.primitives.get(2).get(0).id };
    viewer.scene.canvas.click();
    assert.equal(viewer.scene.primitives.get(1).length, 1, 'selected flight uses one full route');
    assert.equal(
      viewer.scene.primitives.get(1).get(0).width,
      2.55,
      'clicking an aircraft pins and emphasizes its route',
    );
    const selectedPositions = viewer.scene.primitives.get(1).get(0).positions;
    assert.equal(selectedPositions.length, 4, 'selection retains all recorded fixes');
    viewer.camera.positionCartographic.height = 19_000_000;
    viewer.scene.preUpdate.raiseEvent();
    assert.strictEqual(
      viewer.scene.primitives.get(1).get(0).positions[0],
      selectedPositions[0],
      'zoom rebuild reuses prepared route coordinates',
    );
    const stableTrail = viewer.scene.primitives.get(1).get(0);
    viewer.scene.preUpdate.raiseEvent();
    assert.strictEqual(
      viewer.scene.primitives.get(1).get(0),
      stableTrail,
      'steady camera frames do not rebuild flight primitives',
    );
    assert.equal(viewer.scene.primitives.get(3).length, 1, 'seismic');
    for (let i = 0; i < 3; i++) {
      adapter.setImageMode('satellite');
      assert.equal(adapter.getImageMode(), 'satellite');
      assert.equal(surface.uniforms.satellite, 1);
      assert.equal(viewer.scene.imageryLayers.get(1).show, true);
      adapter.setImageMode('dark');
      assert.equal(viewer.scene.imageryLayers.get(0).isDestroyed(), false);
      assert.equal(viewer.scene.imageryLayers.get(0).show, true);
      assert.equal(surface.uniforms.satellite, 0);
    }
    const before = viewer.resizeCount;
    resized();
    adapter.resize();
    assert.equal(viewer.resizeCount, before + 2);
    adapter.destroy();
    adapter.destroy();
    assert.equal(disconnected, true);
    assert.equal(viewer.destroyed, true);
    assert.equal(container.querySelector('.globe-region-panel'), null);
    assert.equal(container.querySelector('.globe-effects'), null);
    assert.equal(surface.isDestroyed(), true);
    assert.equal(viewer.scene.preUpdate.numberOfListeners, 0);
    const overview = await createGlobe(container, { layout: 'horizon' });
    try {
      assert.equal(overview.getRotation(), true, 'overview rotation is enabled by default');
      overview.update([{ ...event, lat: 51, lon: 10 }], null);
      const marker = viewer.dataSources.get(0).entities.values[0];
      const steadySize = marker.point.pixelSize.getValue();
      prefersReducedMotion = false;
      viewer.scene.preUpdate.raiseEvent();
      const firstSize = marker.point.pixelSize.getValue();
      assert.ok(
        firstSize > steadySize,
        'normal overview markers pulse without fullscreen or selection',
      );
      const firstAlpha = marker.point.color.getValue().alpha;
      await new Promise((resolve) => setTimeout(resolve, 25));
      viewer.scene.preUpdate.raiseEvent();
      assert.notEqual(
        marker.point.pixelSize.getValue(),
        firstSize,
        'marker size advances with the decorative phase',
      );
      assert.notEqual(
        marker.point.color.getValue().alpha,
        firstAlpha,
        'marker light changes with the pulse',
      );
      const pausedSize = marker.point.pixelSize.getValue();
      Object.defineProperty(dom.window.document, 'hidden', { value: true, configurable: true });
      viewer.scene.preUpdate.raiseEvent();
      assert.equal(
        marker.point.pixelSize.getValue(),
        pausedSize,
        'offscreen marker pulses hold their phase',
      );
      Object.defineProperty(dom.window.document, 'hidden', { value: false, configurable: true });
      prefersReducedMotion = true;
      assert.equal(
        marker.point.pixelSize.getValue(),
        steadySize,
        'live reduced-motion preference restores steady markers',
      );
      assert.equal(viewer.scene.skyBox.show, true);
      assert.ok(marker.billboard, 'ordinary reports have luminous beacons before selection');
      assert.equal(marker.billboard.scale.getValue(), 1, 'reduced motion keeps the beacon steady');
      overview.update(
        [
          { ...event, id: 1, sev: 'critical', lat: 51, lon: 10 },
          { ...event, id: 2, sev: 'escalating', lat: 51, lon: 10 },
        ],
        null,
      );
      const [escalatingBeacon, criticalBeacon] = viewer.dataSources.get(0).entities.values;
      const red = criticalBeacon.billboard.color.getValue();
      const amber = escalatingBeacon.billboard.color.getValue();
      assert.ok(red.red > 0.9 && red.green < 0.4 && red.blue < 0.5, 'critical beacons stay red');
      assert.ok(
        amber.red > amber.green && amber.green > amber.blue,
        'escalating beacons stay amber',
      );
      assert.ok(
        criticalBeacon.billboard.width.getValue() > escalatingBeacon.billboard.width.getValue(),
        'critical events have a stronger visible aura',
      );
      prefersReducedMotion = false;
      const firstScale = criticalBeacon.billboard.scale.getValue();
      await new Promise((resolve) => setTimeout(resolve, 25));
      viewer.scene.preUpdate.raiseEvent();
      assert.ok(
        criticalBeacon.billboard.scale.getValue() > firstScale,
        'critical red rings expand as their cycle advances',
      );
      prefersReducedMotion = true;
      viewer.camera.positionCartographic.height = 6_800_000;
      viewer.scene.preUpdate.raiseEvent();
      const farWidth = criticalBeacon.billboard.width.getValue();
      const farAlpha = criticalBeacon.billboard.color.getValue().alpha;
      viewer.camera.positionCartographic.height = 10_000;
      viewer.scene.preUpdate.raiseEvent();
      const closeWidth = criticalBeacon.billboard.width.getValue();
      const closeAlpha = criticalBeacon.billboard.color.getValue().alpha;
      viewer.camera.positionCartographic.height = 1;
      viewer.scene.preUpdate.raiseEvent();
      const peakWidth = criticalBeacon.billboard.width.getValue();
      assert.ok(
        farWidth < closeWidth && closeWidth < peakWidth,
        'zoom progressively broadens beacons',
      );
      assert.equal(peakWidth, 42 * 1.8, 'nearest allowed zoom reaches peak aura size');
      assert.ok(
        farAlpha < closeAlpha && closeAlpha < criticalBeacon.billboard.color.getValue().alpha,
        'zoom progressively strengthens light',
      );
      viewer.camera.positionCartographic.height = 0;
      viewer.scene.preUpdate.raiseEvent();
      assert.equal(criticalBeacon.billboard.width.getValue(), peakWidth, 'zoom strength is capped');
      assert.equal(
        criticalBeacon.point.outlineWidth.getValue(),
        0,
        'beacons have no pale circle outlines',
      );
      assert.ok(
        criticalBeacon.point.pixelSize.getValue() < 5,
        'colored centers stay small at peak zoom',
      );
      assert.ok(
        criticalBeacon.point.color
          .getValue()
          .withAlpha(1)
          .equals(Cesium.Color.fromCssColorString('#ff596b')),
        'critical core is red rather than white',
      );

      // Deterministic wall time, with Cesium's real rotation implementation.
      let now = performance.now();
      install('performance', { now: () => now });
      const tick = (milliseconds = 33) => {
        now += milliseconds;
        viewer.scene.preUpdate.raiseEvent();
      };
      viewer.camera.setView({ destination: Cesium.Cartesian3.fromDegrees(20, -5, 6_800_000) });
      prefersReducedMotion = false;
      tick();
      const startPosition = Cesium.Cartographic.clone(viewer.camera.positionCartographic);
      tick();
      const lastRotation = viewer.rotations.at(-1);
      assert.deepEqual(lastRotation.axis, Cesium.Cartesian3.UNIT_Z, 'rotation uses the polar axis');
      assert.ok(
        Math.abs(lastRotation.angle - 7.292115e-5 * 0.033) < 1e-10,
        'normal mode uses Earth’s real angular speed',
      );
      const position = viewer.camera.positionCartographic;
      assert.ok(
        position.longitude < startPosition.longitude,
        'westward viewpoint shows eastward Earth rotation',
      );
      assert.ok(
        Math.abs(position.latitude - startPosition.latitude) < 1e-10,
        'rotation retains latitude',
      );
      assert.ok(
        Math.abs(position.height - startPosition.height) < 0.00001,
        'rotation retains camera distance',
      );
      tick(2000);
      assert.ok(
        Math.abs(viewer.rotations.at(-1).angle - 7.292115e-5 * 2) < 1e-10,
        'slow rendering does not slow Earth’s real rotation rate',
      );
      const lapse = container.querySelectorAll<HTMLButtonElement>('.globe-effects button')[2];
      lapse.click();
      tick();
      assert.ok(
        Math.abs(viewer.rotations.at(-1).angle - ((Math.PI * 2) / 3600) * 0.033) < 1e-10,
        'time lapse turns once per hour',
      );
      lapse.click();
      tick();
      assert.ok(
        Math.abs(viewer.rotations.at(-1).angle - 7.292115e-5 * 0.033) < 1e-10,
        'leaving time lapse restores real speed',
      );
      const assertPaused = (reason: string) => {
        const count = viewer.rotations.length;
        tick();
        assert.equal(viewer.rotations.length, count, reason);
      };
      overview.setRotation(false);
      assert.equal(overview.getRotation(), false);
      assertPaused('rotation toggle stops motion');
      overview.setRotation(true);
      prefersReducedMotion = true;
      assertPaused('reduced motion pauses rotation');
      prefersReducedMotion = false;
      overview.setSuspended(true);
      assertPaused('covered globe does not rotate');
      overview.setSuspended(false);
      Object.defineProperty(dom.window.document, 'hidden', { value: true, configurable: true });
      assertPaused('hidden page does not rotate');
      tick(86_400_000);
      Object.defineProperty(dom.window.document, 'hidden', { value: false, configurable: true });
      dom.window.document.dispatchEvent(new dom.window.Event('visibilitychange'));
      tick();
      assert.ok(
        viewer.rotations.at(-1).angle <= 7.292115e-5 * 0.1,
        'resume never catches up with a large jump',
      );
      overview.update([{ ...event, lat: 51, lon: 10 }], event.id);
      assertPaused('inspecting a selected event holds its view');
      overview.update([{ ...event, lat: 51, lon: 10 }], null);
      viewer.camera.positionCartographic.height = 1_000_000;
      assertPaused('close inspection holds its view');
      viewer.camera.positionCartographic.height = 6_800_000;
      container.dispatchEvent(new dom.window.Event('pointerdown'));
      tick(9000);
      assertPaused('dragging holds rotation even after a long gesture');
      dom.window.dispatchEvent(new dom.window.Event('pointerup'));
      const afterGesture = viewer.rotations.length;
      tick(7999);
      assert.equal(viewer.rotations.length, afterGesture, 'rotation waits after navigation');
      tick(2);
      assert.equal(viewer.rotations.length, afterGesture + 1, 'idle overview resumes rotation');
    } finally {
      overview.destroy();
    }
  } finally {
    adapter?.destroy();
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else Reflect.deleteProperty(globalThis, key);
    }
    dom.window.close();
    await rm(directory, { recursive: true, force: true });
  }
});
