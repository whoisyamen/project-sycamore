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
  Object.defineProperty(dom.window, 'matchMedia', { value: () => ({ matches: true }) });
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
    destroyed = false;
    constructor(container: HTMLElement, options: any) {
      viewer = this;
      const canvas = dom.window.document.createElement('canvas');
      container.appendChild(canvas);
      this.camera = {
        positionCartographic: Cesium.Cartographic.fromDegrees(20, 25, 19e6),
        setView: ({ destination }: any) => {
          this.camera.positionCartographic = Cesium.Cartographic.fromCartesian(destination);
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
        preUpdate: new Cesium.Event(),
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
    assert.equal(viewer.clock.multiplier, 600);
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
      10.5,
      'reduced-motion presentation mode statically emphasizes markers',
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
