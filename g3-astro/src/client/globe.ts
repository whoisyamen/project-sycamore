// D-023 — Interactive OSINT globe (Cesium 1.145, self-hosted build, no ion token).
// A real 3D earth with selectable countries and cities plus layered signals: news
// events, live air traffic (OpenSky via ingest), seismic activity (USGS) and an
// internet-exposure sample (Censys via keyed ingest). Every plotted position is
// source-provided; the globe never interpolates or imputes a location.

import * as Cesium from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';
Cesium.Ion.defaultAccessToken = '';
const BASE = import.meta.env.BASE_URL;
(window as Window & { CESIUM_BASE_URL?: string }).CESIUM_BASE_URL = `${BASE}cesium/`;

import type { Event } from '../data/types';
import { attachGlobeEffects } from './globe-effects';
import { geoTier } from './render';
import type {
  FlightsEnvelope,
  ImageryMode,
  LayerName,
  RegionSelection,
  CensysEnvelope,
} from './osint';

// ---------------------------------------------------------------- palette (midnight atlas: ice, slate and coral)
const INK = Cesium.Color.fromCssColorString('#080f19');
const PLANE = Cesium.Color.fromCssColorString('#a6c6d9');
const ACCENT = Cesium.Color.fromCssColorString('#83c9de');
const CORAL = Cesium.Color.fromCssColorString('#ec8278');
const SLATE = Cesium.Color.fromCssColorString('#9bb3cd');
const ASH = Cesium.Color.fromCssColorString('#728a9a');
// Recolor only the basemap's ocean; retain land, boundaries and zoom-level labels.
const OCEAN = Cesium.Color.fromCssColorString('#0c1e30');
const BASEMAP_OCEAN = Cesium.Color.fromCssColorString('#232227');
const SEVERITY: Record<string, { color: typeof INK; pulse: boolean }> = {
  critical: { color: CORAL, pulse: true },
  escalating: { color: ACCENT, pulse: false },
  watching: { color: SLATE, pulse: false },
  deesc: { color: ASH, pulse: false },
};
// Top-down airliner silhouette (nose up = heading 0); tinted dim gray per billboard.
const PLANE_IMG = `${BASE}data/globe/plane.svg`;

// ---------------------------------------------------------------- baselines (built once per session)
interface CityRow {
  lon: number;
  lat: number;
  name: string;
  iso: string;
  pop: number;
}
let citiesCache: CityRow[] | null = null;
async function loadCities(): Promise<CityRow[]> {
  if (!citiesCache) {
    const rows: [number, number, string, string, number][] = await (
      await fetch(`${BASE}data/globe/cities.json`)
    ).json();
    citiesCache = rows.map(([lon, lat, name, iso, pop]) => ({ lon, lat, name, iso, pop }));
  }
  return citiesCache;
}

interface CountryFeature {
  id: number;
  name: string;
  iso3: string;
  areaKm2: number;
  bbox: [number, number, number, number];
  centroid: [number, number] | null;
  rings: number[][][];
}
let countriesCache: CountryFeature[] | null = null;
async function loadCountries(): Promise<CountryFeature[]> {
  if (!countriesCache) {
    const fc = await (await fetch(`${BASE}data/globe/countries.geojson`)).json();
    let id = -1;
    countriesCache = [];
    for (const f of fc.features ?? []) {
      const rings = f.rings;
      if (!Array.isArray(rings) || rings.length === 0) continue;
      ++id;
      let minLon = Infinity,
        maxLon = -Infinity,
        minLat = Infinity,
        maxLat = -Infinity;
      let sy = 0,
        sinLon = 0,
        cosLon = 0,
        n = 0;
      for (const ring of rings) {
        for (const [lon, lat] of ring) {
          sy += lat;
          const lonRad = Cesium.Math.toRadians(lon);
          sinLon += Math.sin(lonRad);
          cosLon += Math.cos(lonRad);
          ++n;
          if (lon < minLon) minLon = lon;
          if (lon > maxLon) maxLon = lon;
          if (lat < minLat) minLat = lat;
          if (lat > maxLat) maxLat = lat;
        }
      }
      countriesCache.push({
        id,
        name: String(f.properties?.name ?? ''),
        iso3: String(f.properties?.iso ?? '').toUpperCase(),
        areaKm2: 0,
        bbox: [minLon, minLat, maxLon, maxLat],
        centroid: n > 0 ? [Cesium.Math.toDegrees(Math.atan2(sinLon, cosLon)), sy / n] : null,
        rings,
      });
    }
    countriesCache.sort((a, b) => b.areaKm2 - a.areaKm2);
  }
  return countriesCache;
}

function ringContains(ring: number[][], lon: number, lat: number): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0],
      yi = ring[i][1],
      xj = ring[j][0],
      yj = ring[j][1];
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function countryAt(lon: number, lat: number): CountryFeature | null {
  const list = countriesCache ?? [];
  for (const c of list) {
    if (lon < c.bbox[0] || lon > c.bbox[2] || lat < c.bbox[1] || lat > c.bbox[3]) continue;
    for (const ring of c.rings) {
      if (ringContains(ring, lon, lat)) return c;
    }
  }
  return null;
}

function haversineKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  const R = 6371,
    dLat = ((lat2 - lat1) * Math.PI) / 180,
    dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ---------------------------------------------------------------- adapter contract (EventMap-compatible + OSINT extensions)
export interface GlobeAdapter {
  update(events: Event[], active: number | null): void;
  focus(id: number): void;
  resize(): void;
  destroy(): void;
  setLayers(layers: Partial<Record<LayerName, boolean>>): void;
  setImageMode(mode: ImageryMode): void;
  getLayer(name: LayerName): boolean;
  getImageMode(): ImageryMode;
  resetView(): void;
  zoom(direction: number): void;
  setPresentationMode(enabled: boolean): void;
  setSuspended(suspended: boolean): void;
  /** Resolves when current-view imagery is in, or when the wait times out. */
  whenImagerySettled(timeoutMs?: number): Promise<'ready' | 'timeout'>;
}

export interface GlobeOptions {
  onSelectEvent?: (id: number) => void; // marker picked → dashboard selects it in feed/panel
  onRegionSelected?: (r: RegionSelection | null) => void; // country/city picked or cleared
  layout?: 'horizon' | 'context';
  initialImagery?: ImageryMode;
  creditContainer?: HTMLElement;
}

const SEISMIC_URL = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson';
const POLL_MS = 60_000;

// Flight history is useful only while it still reads as motion. Wider views get
// fewer, shorter, fainter tails; zooming in progressively reveals more history.
// This keeps the global view legible without making the layer feel static.
const FLIGHT_TRAIL_TIERS = [
  {
    maxHeight: 2_500_000,
    maxTrails: 140,
    maxFixes: 14,
    alpha: 0.28,
    width: 1.35,
    maxAircraft: 1_400,
    gridDeg: 1.5,
    aircraftAlpha: 0.68,
  },
  {
    maxHeight: 8_000_000,
    maxTrails: 72,
    maxFixes: 8,
    alpha: 0.2,
    width: 1.08,
    maxAircraft: 700,
    gridDeg: 3.5,
    aircraftAlpha: 0.56,
  },
  {
    maxHeight: Infinity,
    maxTrails: 28,
    maxFixes: 4,
    alpha: 0.12,
    width: 0.85,
    maxAircraft: 320,
    gridDeg: 7.5,
    aircraftAlpha: 0.46,
  },
] as const;

function flightTrailTier(height: number): number {
  return FLIGHT_TRAIL_TIERS.findIndex((tier) => height <= tier.maxHeight);
}

function incidentCallout(event: Event): string {
  const raw = (event.summary || event.title).replace(/\s+/g, ' ').trim();
  const clipped = raw.length > 104 ? `${raw.slice(0, 101).trimEnd()}…` : raw;
  const words = clipped.split(' ');
  const lines: string[] = [];
  let line = '';
  for (const word of words) {
    const next = line ? `${line} ${word}` : word;
    if (next.length > 42 && line) {
      lines.push(line);
      line = word;
      if (lines.length === 2) break;
    } else line = next;
  }
  if (lines.length < 2 && line) lines.push(line);
  return `CRITICAL · ${event.loc}\n${lines.join('\n')}`;
}

export function createGlobe(
  container: HTMLElement,
  opts: GlobeOptions = {},
): Promise<GlobeAdapter> {
  return (async () => {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let destroyed = false;
    const cartographic = opts.layout === 'context' && opts.initialImagery !== 'satellite';

    // ---------------------------------------------------------- baselines before first paint matters for picking/labels
    await loadCountries().catch(() => undefined);

    // ---------------------------------------------------------- viewer & scene chrome (keyless Esri basemap)
    const darkLayer = new Cesium.ImageryLayer(
      new Cesium.UrlTemplateImageryProvider({
        url: 'https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
        tilingScheme: new Cesium.WebMercatorTilingScheme(),
        maximumLevel: 16,
        credit: 'Basemap © Esri, HERE, Garmin',
      }),
      {
        colorToAlpha: BASEMAP_OCEAN,
        colorToAlphaThreshold: cartographic ? 0 : 0.025,
        alpha: cartographic ? 1 : 0.78,
      },
    );
    const satLayer = new Cesium.ImageryLayer(
      new Cesium.UrlTemplateImageryProvider({
        url: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        tilingScheme: new Cesium.WebMercatorTilingScheme(),
        maximumLevel: 19,
        credit: 'Imagery © Esri, Maxar, Earthstar Geographics',
      }),
    );
    const viewer = new Cesium.Viewer(container, {
      baseLayer: darkLayer,
      animation: false,
      timeline: false,
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      navigationHelpButton: false,
      sceneModePicker: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
      shouldAnimate: false,
      creditContainer: opts.creditContainer,
    });
    const scene = viewer.scene;
    scene.imageryLayers.add(satLayer);
    satLayer.show = opts.initialImagery === 'satellite';
    darkLayer.show = !satLayer.show;
    const resizeObserver = new ResizeObserver(() => {
      if (!destroyed) viewer.resize();
    });
    resizeObserver.observe(container);
    const resizeFrame = requestAnimationFrame(() => {
      if (!destroyed) viewer.resize();
    });

    scene.globe.baseColor = cartographic ? Cesium.Color.fromCssColorString('#1b242c') : OCEAN;
    scene.globe.showGroundAtmosphere = false; // preserve the dark palette instead of washing it in daylight
    scene.globe.enableLighting = false; // ungraded satellite imagery stays legible across the globe
    scene.globe.dynamicAtmosphereLighting = false;
    scene.globe.maximumScreenSpaceError = 1; // one LOD deeper than default: sharper imagery at global view, ~4x tiles
    scene.backgroundColor = opts.layout
      ? Cesium.Color.fromCssColorString(opts.layout === 'context' ? '#0a0d12' : '#080c12')
      : INK;
    // Cesium's bundled star field sits behind the existing globe/atmosphere.
    if (scene.skyBox) scene.skyBox.show = !opts.layout;
    if (scene.sun) scene.sun.show = false;
    if (scene.moon) scene.moon.show = false;
    if (scene.skyAtmosphere) {
      scene.skyAtmosphere.show = !cartographic;
      scene.skyAtmosphere.atmosphereLightIntensity = 6;
      scene.skyAtmosphere.brightnessShift = -0.2;
    }

    const effects = cartographic
      ? { setSatellite: (_enabled: boolean) => {}, destroy: () => {} }
      : attachGlobeEffects(viewer, container, BASE, reducedMotion);
    viewer.targetFrameRate = 30;
    viewer.resolutionScale = Math.min(window.devicePixelRatio || 1, 1.5);

    const camera = viewer.camera;
    const homeHeight = opts.layout === 'horizon' ? 6.8e6 : opts.layout === 'context' ? 8e6 : 1.9e7;
    const homeLatitude = opts.layout === 'horizon' ? -5 : 25;
    camera.setView({ destination: Cesium.Cartesian3.fromDegrees(20, homeLatitude, homeHeight) });
    if (opts.initialImagery === 'satellite') effects.setSatellite(true);

    // ---------------------------------------------------------- layer registries
    const eventSource = new Cesium.CustomDataSource('events');
    await viewer.dataSources.add(eventSource);
    const eventEntities = eventSource.entities;
    const cityPoints = new Cesium.PointPrimitiveCollection(); // primitives, not entities — 13k cities must stay one draw call class
    scene.primitives.add(cityPoints);
    const censysSource = new Cesium.CustomDataSource('censys');
    await viewer.dataSources.add(censysSource);
    const censysEntities = censysSource.entities;
    const trailPrims = new Cesium.PolylineCollection(); // at most three fading chunks per ambient trail — collection keeps rebuilds one-shot
    scene.primitives.add(trailPrims);
    const aircraftPoints = new Cesium.BillboardCollection(); // heading-oriented plane icons (one draw-call class)
    scene.primitives.add(aircraftPoints);
    const seismicPoints = new Cesium.PointPrimitiveCollection();
    scene.primitives.add(seismicPoints);
    let highlights: Cesium.Entity[] = [];

    // ---------------------------------------------------------- state
    let visibleEvents: Event[] = [];
    let activeEventId: number | null = null;
    let presentationMode = false;
    let imageryMode: ImageryMode = opts.initialImagery ?? 'dark';
    let flightsEnv: FlightsEnvelope | null = null;
    let selectedFlightId: string | null = null;
    let lastFlightTrailTier = -1;
    let seismicData: any = null;
    let censysEnv: CensysEnvelope | null = null;
    const layersOn: Record<LayerName, boolean> = {
      events: true,
      cities: false,
      flights: !opts.layout,
      seismic: false,
      censys: false,
    };

    // ---------------------------------------------------------- DOM overlays (region panel + hover chip) — live inside #map so layout CSS owns them
    const overlay = document.createElement('div');
    overlay.className = 'globe-region-panel';
    overlay.hidden = true;
    overlay.innerHTML = `<button class="region-close" type="button" aria-label="Close region details">×</button>
      <p class="eyebrow region-kind">REGION</p><h2 class="region-name"></h2>
      <dl class="region-stats"></dl>
      <div class="region-actions"><button class="text-button region-export" type="button">Export selection for ingest ↓</button></div>`;
    container.appendChild(overlay);
    const hoverChip = document.createElement('div');
    hoverChip.className = 'globe-hover';
    hoverChip.hidden = true;
    container.appendChild(hoverChip);

    const status = document.createElement('p');
    status.className = 'globe-data-status';
    status.setAttribute('role', 'status');
    container.appendChild(status);
    function refreshStatus() {
      const describe = (label: string, env: { ts: number; count: number } | null) =>
        env
          ? `${label}: ${env.count} · ${new Date(env.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}${Date.now() - env.ts > 300000 ? ' (stale)' : ''}`
          : `${label}: unavailable`;
      status.textContent = [
        layersOn.flights ? describe('Flights', flightsEnv) : '',
        layersOn.seismic
          ? seismicData
            ? `Seismic: ${seismicPoints.length} · USGS, past hour`
            : 'Seismic: unavailable'
          : '',
        layersOn.censys
          ? censysEnv
            ? describe('Censys sample', censysEnv)
            : 'Censys: configure key and regions in ingest'
          : '',
      ]
        .filter(Boolean)
        .join(' / ');
      if (selectedRegion) selectRegion(selectedRegion, false);
    }

    // ---------------------------------------------------------- layer builders (idempotent — full rebuilds are cheap at these counts)
    function rebuildEvents() {
      eventEntities.removeAll();
      if (!layersOn.events || !visibleEvents.length) return;
      for (const e of visibleEvents) {
        const base = SEVERITY[e.sev] ?? SEVERITY.watching;
        const approx = geoTier(e) === 'approximate'; // D-014: dimmer — less certain than precise fixes
        const baseColor = base.color;
        const restingAlpha = approx ? 0.45 : 1;
        const restingSize =
          opts.layout === 'context' ? 4 : activeEventId === e.id ? 9 : approx ? 6.5 : 8;
        const markerColor = presentationMode
          ? reducedMotion
            ? baseColor.withAlpha(1)
            : new Cesium.CallbackProperty(() => {
                const phase = Date.now() / 430 + (e.id % 11) * 0.73;
                const wave = (Math.sin(phase) + 1) / 2;
                const floor = approx ? 0.26 : 0.38;
                return baseColor.withAlpha(floor + (1 - floor) * wave, new Cesium.Color());
              }, false)
          : baseColor.withAlpha(restingAlpha);
        const markerSize =
          presentationMode && !reducedMotion
            ? new Cesium.CallbackProperty(() => {
                const phase = Date.now() / 430 + (e.id % 11) * 0.73;
                return restingSize + 1.2 + ((Math.sin(phase) + 1) / 2) * 2.2;
              }, false)
            : restingSize + (presentationMode ? 1.5 : 0);
        const outlineCol =
          activeEventId === e.id || approx
            ? baseColor
                .brighten(0.25, new Cesium.Color())
                .withAlpha(activeEventId === e.id ? 1 : 0.7)
            : undefined;
        eventEntities.add(
          new Cesium.Entity({
            position: Cesium.Cartesian3.fromDegrees(e.lon, e.lat),
            point: {
              pixelSize: markerSize,
              color: markerColor,
              outlineColor: outlineCol,
              outlineWidth:
                opts.layout === 'context' ? 0.6 : activeEventId === e.id ? 1.6 : approx ? 1.3 : 0,
              disableDepthTestDistance: presentationMode ? Number.POSITIVE_INFINITY : 0,
            },
            label:
              presentationMode && e.sev === 'critical'
                ? {
                    text: incidentCallout(e),
                    font: '500 11px ui-monospace, monospace',
                    fillColor: Cesium.Color.fromCssColorString('#e4edf5'),
                    outlineColor: INK.withAlpha(0.96),
                    outlineWidth: 2,
                    style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                    showBackground: true,
                    backgroundColor: INK.withAlpha(0.88),
                    backgroundPadding: new Cesium.Cartesian2(8, 6),
                    pixelOffset: new Cesium.Cartesian2(0, -17),
                    horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
                    verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                    disableDepthTestDistance: Number.POSITIVE_INFINITY,
                    scaleByDistance: new Cesium.NearFarScalar(1.2e6, 1, 2.2e7, 0.78),
                  }
                : undefined,
            properties: new Cesium.PropertyBag({
              kind: 'event',
              idRef: String(e.id),
              name: e.title,
            }),
          }),
        );
      }
    }

    let lastCityTier = -1;
    function rebuildCities() {
      if (!layersOn.cities || !citiesCache) {
        if (cityPoints.length) cityPoints.removeAll();
        lastCityTier = -1;
        return;
      }
      const height = camera.positionCartographic?.height ?? 0;
      const nextTier = height > 1.7e7 ? -2 : height < 3e6 ? 0 : height < 9e6 ? 1 : 2;
      if (nextTier === lastCityTier) return; // far: hide (density > value); mid: metros only; near: full detail
      let tier: number, rows: CityRow[];
      if (height > 1.7e7) {
        cityPoints.removeAll();
        lastCityTier = -2;
        return;
      } else if (height < 3e6) {
        tier = 0;
        rows = citiesCache;
      } // streets-level — every retained city
      else if (height < 9e6) {
        tier = 1;
        rows = citiesCache.filter((c) => c.pop >= 250_000);
      } // metros only at mid altitude
      else {
        tier = 2;
        rows = citiesCache
          .filter((c, i) => c.pop >= 750_000 || (i % 4 === 0 && c.pop >= 120_000))
          .slice(0, 600);
      } // far: top metros + deterministic sample
      if (tier === lastCityTier) return; // don't churn primitives while the camera drifts inside a band
      lastCityTier = tier;
      cityPoints.removeAll();
      for (const c of rows.slice(0, 12_000)) {
        cityPoints.add({
          position: Cesium.Cartesian3.fromDegrees(c.lon, c.lat),
          pixelSize: tier === 0 ? 4 : 5,
          color: ASH.withAlpha(0.8),
          id: { kind: 'city', name: `${c.name} (${c.iso})`, lon: c.lon, lat: c.lat },
        });
      }
    }

    // Prepare source history once per successful poll, never during zoom/picking.
    function prepareTrails(env: FlightsEnvelope) {
      return Object.entries(env.trails ?? [])
        .map(([id, pts]) => {
          const fixes = pts.filter((p) => Number.isFinite(p[0]) && Number.isFinite(p[1]));
          if (fixes.length < 2) return null;
          const newest = fixes.reduce(
            (latest, p) => Math.max(latest, Number.isFinite(p[2]) ? p[2] : 0),
            0,
          );
          const first = fixes[0];
          const last = fixes[fixes.length - 1];
          let positions: Cesium.Cartesian3[] | undefined;
          return {
            id,
            fixes,
            get positions() {
              return (positions ??= fixes.map((p) => Cesium.Cartesian3.fromDegrees(p[0], p[1])));
            },
            newest,
            movementKm: haversineKm(first[0], first[1], last[0], last[1]),
          };
        })
        .filter((candidate): candidate is NonNullable<typeof candidate> => candidate !== null)
        .sort((a, b) => b.newest - a.newest || b.movementKm - a.movementKm);
    }
    let preparedTrails: ReturnType<typeof prepareTrails> = [];

    function rebuildFlights() {
      trailPrims.removeAll();
      aircraftPoints.removeAll();
      if (!layersOn.flights || !flightsEnv) return;
      const height = camera.positionCartographic?.height ?? 19_000_000;
      const tierIndex = flightTrailTier(height);
      const trailStyle = FLIGHT_TRAIL_TIERS[tierIndex];
      lastFlightTrailTier = tierIndex;

      // Wide views do not need every transponder on screen at once. Keep one
      // representative aircraft per geographic cell, then reveal denser traffic
      // as the camera comes closer. A pinned aircraft is always retained.
      const aircraftCandidates = (flightsEnv.aircraft ?? []).filter(
        (aircraft) => Number.isFinite(aircraft.lon) && Number.isFinite(aircraft.lat),
      );
      const visibleAircraft: typeof aircraftCandidates = [];
      const occupiedCells = new Set<string>();
      const pinnedAircraft = selectedFlightId
        ? aircraftCandidates.find((aircraft) => aircraft.id === selectedFlightId)
        : undefined;
      if (pinnedAircraft) visibleAircraft.push(pinnedAircraft);
      for (const aircraft of aircraftCandidates) {
        if (aircraft.id === selectedFlightId) continue;
        const key = `${Math.floor((aircraft.lon + 180) / trailStyle.gridDeg)}:${Math.floor(
          (aircraft.lat + 90) / trailStyle.gridDeg,
        )}`;
        if (occupiedCells.has(key)) continue;
        occupiedCells.add(key);
        visibleAircraft.push(aircraft);
        if (visibleAircraft.length >= trailStyle.maxAircraft) break;
      }

      for (const aircraft of visibleAircraft) {
        const hdg = Number.isFinite(aircraft.hdg)
          ? (((aircraft.hdg as number) % 360) + 360) % 360
          : 0;
        const selected = aircraft.id === selectedFlightId;
        const focused = selectedFlightId !== null;
        aircraftPoints.add({
          position: Cesium.Cartesian3.fromDegrees(
            aircraft.lon,
            aircraft.lat,
            Math.max(0, aircraft.alt_m || 0),
          ),
          image: PLANE_IMG,
          rotation: Cesium.Math.toRadians(hdg),
          color: PLANE.withAlpha(selected ? 0.96 : focused ? 0.15 : trailStyle.aircraftAlpha),
          translucencyByDistance: new Cesium.NearFarScalar(5e5, 1, 1.9e7, 0.72),
          width: 12,
          height: 12,
          scaleByDistance: new Cesium.NearFarScalar(5e5, selected ? 2.45 : 2.05, 1.9e7, 0.48),
          id: {
            kind: 'flight',
            name: aircraft.cs || aircraft.id,
            flightId: aircraft.id,
          },
        });
      }

      const candidates = preparedTrails;

      const visible = candidates.slice(0, trailStyle.maxTrails);
      const pinned = selectedFlightId
        ? candidates.find((candidate) => candidate.id === selectedFlightId)
        : undefined;
      if (pinned && !visible.some((candidate) => candidate.id === pinned.id)) {
        if (visible.length >= trailStyle.maxTrails) visible[visible.length - 1] = pinned;
        else visible.push(pinned);
      }

      const ordered = selectedFlightId
        ? [
            ...visible.filter((trail) => trail.id !== selectedFlightId),
            ...visible.filter((trail) => trail.id === selectedFlightId),
          ]
        : visible;
      for (const trail of ordered) {
        const selected = trail.id === selectedFlightId;
        const fixes = selected ? trail.fixes : trail.fixes.slice(-trailStyle.maxFixes);
        if (selected) {
          // Selection is the one place where full source-provided history is
          // useful. Draw it last so it reads clearly above ambient traffic.
          trailPrims.add({
            positions: trail.positions,
            width: 2.55,
            material: Cesium.Material.fromType(Cesium.Material.ColorType, {
              color: ACCENT.withAlpha(0.9),
            }),
          });
          continue;
        }

        // A fading motion tail communicates direction without turning every
        // aircraft history into a persistent line across the map.
        const focusFade = selectedFlightId ? 0.24 : 1;
        const segmentCount = fixes.length - 1;
        const chunkCount = Math.min(3, segmentCount);
        for (let chunk = 0; chunk < chunkCount; chunk++) {
          const startSegment = Math.floor((chunk * segmentCount) / chunkCount);
          const endSegment = Math.floor(((chunk + 1) * segmentCount) / chunkCount);
          const offset = trail.positions.length - fixes.length;
          const positions = trail.positions.slice(offset + startSegment, offset + endSegment + 1);
          const recency = (chunk + 1) / chunkCount;
          const ageFade = 0.18 + 0.82 * recency * recency;
          trailPrims.add({
            positions,
            width: trailStyle.width * (0.82 + recency * 0.18),
            material: Cesium.Material.fromType(Cesium.Material.ColorType, {
              color: PLANE.withAlpha(trailStyle.alpha * ageFade * focusFade),
            }),
          });
        }
      }
    }

    function rebuildSeismic() {
      seismicPoints.removeAll();
      if (!layersOn.seismic || !seismicData?.features) return;
      for (const f of seismicData.features.slice(0, 260)) {
        // last hour, all magnitudes — USGS order is newest-first
        const [lon, lat] = f.geometry.coordinates as number[];
        const mag = Number(f.properties.mag ?? 0);
        if (!Number.isFinite(lon + lat) || !(mag > 1.5)) continue; // unlocated or micro events: dropped, not guessed
        seismicPoints.add({
          position: Cesium.Cartesian3.fromDegrees(lon, lat),
          pixelSize: Math.min(9, 2.4 + mag * 0.85),
          color: (mag >= 5 ? CORAL : ACCENT).withAlpha(0.85),
          id: { kind: 'seismic', name: `M${mag} · ${f.properties.place || 'Earthquake'}` },
        });
      }
    }

    function rebuildCensys() {
      censysEntities.removeAll();
      if (!layersOn.censys || !censysEnv?.hosts?.length) return; // file absent until first keyed ingest — layer stays empty, never fakes data
      for (const h of censysEnv.hosts.slice(0, 300)) {
        const ports = (h.ports ?? []).slice(0, 6).join(', ');
        censysEntities.add(
          new Cesium.Entity({
            position: Cesium.Cartesian3.fromDegrees(h.lon, h.lat),
            point: { pixelSize: 4.2, color: CORAL.withAlpha(0.9) },
            properties: new Cesium.PropertyBag({
              kind: 'censys',
              name: `${h.ip} · ports ${ports || '?'}`,
              iso: h.country_code ?? '',
            }),
          }),
        );
      }
    }

    // ---------------------------------------------------------- region selection + highlight geometry from cached baselines
    let selectedRegion: RegionSelection | null = null;
    function setHighlight(r: RegionSelection | null) {
      highlights.forEach((entity) => viewer.entities.remove(entity));
      highlights = [];
      if (!r) return;
      const c = countriesCache?.find((x) => x.name === r.name);
      if (c && r.kind === 'country') {
        for (const ring of c.rings) {
          highlights.push(
            viewer.entities.add({
              polyline: {
                positions: ring.map(([lon, lat]) => Cesium.Cartesian3.fromDegrees(lon, lat)),
                width: 2,
                material: ACCENT,
              },
            }),
          );
        }
      } else if (r.kind === 'city') {
        highlights.push(
          viewer.entities.add({
            position: Cesium.Cartesian3.fromDegrees(r.lon, r.lat),
            ellipse: {
              semiMajorAxis: 14000,
              semiMinorAxis: 14000,
              material: ACCENT.withAlpha(0.12),
              outline: true,
              outlineColor: ACCENT,
            },
          }),
        );
      }
    }

    function selectRegion(r: RegionSelection | null, fly = true) {
      selectedRegion = r;
      opts.onRegionSelected?.(r);
      setHighlight(r);
      if (!r || !countriesCache) {
        overlay.hidden = true;
        return;
      }
      const c = countriesCache.find((x) => x.name.toLowerCase() === r.name!.toLowerCase());
      let inEvents = 0;
      const nearAircraft: number | null = layersOn.flights
        ? (flightsEnv?.aircraft.length ?? 0)
        : null; // aircraft count is a region metric only when the layer has data — never invented
      for (const e of visibleEvents) {
        if (r.kind === 'country' && c) inEvents += pointInCountry(c, e) ? 1 : 0;
        else if (r.kind === 'city' && haversineKm(e.lon, e.lat, r.lon, r.lat) < 14) inEvents++; // city: proximity ring — the honest metric for a metro selection
      }
      const exposure =
        layersOn.censys && censysEnv ? `${censysEnv.count} hosts sampled` : 'key ingest to sample';
      (overlay.querySelector('.region-kind') as HTMLElement).textContent =
        r.kind === 'country' ? `COUNTRY${r.iso3 ? ` · ${r.iso3}` : ''}` : 'CITY REGION';
      (overlay.querySelector('.region-name') as HTMLElement).textContent = r.name;
      const stats: [string, string][] = [
        [r.kind === 'city' ? 'events within 14 km' : 'events in country', String(inEvents)],
        ['aircraft tracked', nearAircraft === null || !flightsEnv ? '—' : `${nearAircraft} global`],
        ['exposure sample', exposure],
      ];
      (overlay.querySelector('.region-stats') as HTMLElement).innerHTML = stats
        .map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`)
        .join('');
      const exportBtn = overlay.querySelector<HTMLButtonElement>('.region-export')!;
      exportBtn.onclick = () => {
        // static surface stays read-only (D-011): the operator applies this spec on the laptop, not via a browser write.
        const countryRow =
          r.kind === 'country'
            ? countriesCache?.find((x) => x.name.toLowerCase() === r.name.toLowerCase())
            : undefined;
        const centerLon = countryRow?.centroid?.[0] ?? r.lon;
        const points = countryRow?.rings.flat() ?? [
          [r.lon - 0.15, Math.max(-90, r.lat - 0.15)],
          [r.lon + 0.15, Math.min(90, r.lat + 0.15)],
        ];
        const lons = points.map(([lon]) => centerLon + ((lon - centerLon + 540) % 360) - 180);
        const wrap = (lon: number) => ((lon + 540) % 360) - 180;
        const spec = [
          {
            kind: 'bbox',
            name: r.name,
            west: wrap(Math.min(...lons)),
            east: wrap(Math.max(...lons)),
            south: Math.min(...points.map((p) => p[1])),
            north: Math.max(...points.map((p) => p[1])),
          },
        ];
        const blob = new Blob(
          [JSON.stringify({ version: 1, ts: Date.now(), regions: spec }, null, 2)],
          { type: 'application/json' },
        );
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `sycamore-regions-${Date.now()}.json`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      };
      overlay.hidden = false;
      if (fly) flyToRegion(r);
    }

    function pointInCountry(c: CountryFeature, e: Event): boolean {
      for (const ring of c.rings) {
        if (ringContains(ring, e.lon, e.lat)) return true;
      }
      return false;
    }

    function flyToRegion(r: RegionSelection | null, eventId?: number) {
      const ev = visibleEvents.find((x) => x.id === eventId);
      if (ev) {
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(
            ev.lon,
            Math.max(-72, Math.min(76, ev.lat + 0.5)),
            Math.min(camera.positionCartographic?.height ?? 9e6, 1.4e6),
          ),
          duration: reducedMotion ? 0 : 1.2,
        });
      } else if (r) {
        // For countries, use the cached centroid from the matched feature (not r.lon/r.lat which are 0/0)
        let flyLon = r.lon,
          flyLat = r.lat;
        if (r.kind === 'country' && countriesCache) {
          const c = countriesCache.find((x) => x.name.toLowerCase() === r.name!.toLowerCase());
          if (c?.centroid) {
            flyLon = c.centroid[0];
            flyLat = c.centroid[1];
          }
        }
        const country = countriesCache?.find((c) => c.name === r.name);
        const h =
          r.kind === 'city'
            ? 3.2e5
            : country
              ? Math.max(
                  8.5e5,
                  Cesium.BoundingSphere.fromPoints(
                    country.rings.flatMap((ring) =>
                      ring.map(([lon, lat]) => Cesium.Cartesian3.fromDegrees(lon, lat)),
                    ),
                  ).radius * 3,
                )
              : 4e6;
        const latAdj = r.kind === 'country' ? 0.4 : 0;
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(
            flyLon,
            Math.max(-72, Math.min(76, flyLat + latAdj)),
            h,
          ),
          duration: reducedMotion ? 0 : 1.2,
        });
      } else {
        viewer.camera.flyHome(reducedMotion ? 0 : 1.5);
      }
    }

    // ---------------------------------------------------------- picking & hover (entity picks for markers; ellipsoid pick + point-in-polygon for regions)
    const canvas = scene.canvas as HTMLCanvasElement;
    function entityProps(id: any): any {
      return id?.properties?.getValue(Cesium.JulianDate.now()) ?? (id?.kind ? id : null);
    }
    function pickAt(x: number, y: number): void {
      // click → select event / city region / country region; water & empty land clear the selection
      const picked = scene.pick(new Cesium.Cartesian2(x, y));
      if (picked?.id) {
        const props = entityProps(picked.id);
        if (props?.kind === 'city') {
          selectRegion({ kind: 'city', name: props.name, lon: props.lon, lat: props.lat });
          return;
        }
        if (!props) return;
        if (props.kind === 'event') {
          opts.onSelectEvent?.(Number(props.idRef));
          return;
        } // marker selects into the feed/panel — no region change
        if (props.kind === 'flight') {
          const flightId = String(props.flightId ?? '');
          if (flightId) {
            selectedFlightId = selectedFlightId === flightId ? null : flightId;
            rebuildFlights();
          }
          return;
        }
        if (props.kind === 'censys') {
          // Extract coordinates from the entity's position
          const pos = picked.id.position?.getValue?.(Cesium.JulianDate.now());
          if (pos) {
            const cart = Cesium.Cartographic.fromCartesian(pos);
            const lon = Cesium.Math.toDegrees(cart.longitude);
            const lat = Cesium.Math.toDegrees(cart.latitude);
            selectRegion({ kind: 'city', name: props.name, lon, lat }, true);
          } else {
            selectRegion({ kind: 'city', name: props.name, lon: 0, lat: 0 }, true);
          }
          return;
        }
      } else {
        const cartesian = camera.pickEllipsoid(new Cesium.Cartesian2(x, y), scene.globe.ellipsoid); // terrain-height pick (ellipsoid here) → real lon/lat under the cursor
        if (destroyed) return;
        if (!cartesian) {
          selectRegion(null, false);
          return;
        }
        const carto = Cesium.Cartographic.fromCartesian(cartesian);
        const lon = Cesium.Math.toDegrees(carto.longitude),
          lat = Cesium.Math.toDegrees(carto.latitude);
        const cities = layersOn.cities ? (citiesCache ?? []) : []; // city selection only offered while the layer is on — no phantom picks over invisible data
        let nearest: { c: CityRow; d: number } | null = null;
        for (const c of cities)
          if (
            (c.lon - lon) ** 2 + (c.lat - lat) ** 2 <= 0.35 * 0.35 &&
            haversineKm(lon, lat, c.lon, c.lat) < 45
          ) {
            const d = haversineKm(lon, lat, c.lon, c.lat);
            if (!nearest || d < nearest.d) nearest = { c, d };
          }
        if (nearest)
          return (
            selectRegion(
              {
                kind: 'city',
                name: `${nearest.c.name} (${nearest.c.iso})`,
                lon: nearest.c.lon,
                lat: nearest.c.lat,
              },
              true,
            ),
            void 0
          );
        const country = countryAt(lon, lat); // water clicks fall through to null — nothing selected over ocean (honest)
        if (country) {
          const c = country;
          const flyLon = c?.centroid?.[0] ?? 0,
            flyLat = c?.centroid?.[1] ?? 0;
          return (
            selectRegion(
              {
                kind: 'country',
                name: country.name,
                iso3: country.iso3 || undefined,
                lon: flyLon,
                lat: flyLat,
              },
              true,
            ),
            void 0
          );
        }
        selectRegion(null); // empty space over land with no match / water → clear selection
      }
    }

    let press: { x: number; y: number } | null = null;
    const downHandler = (ev: PointerEvent) => {
      press = { x: ev.clientX, y: ev.clientY };
    };
    canvas.addEventListener('pointerdown', downHandler);
    const clickHandler = (ev: MouseEvent) => {
      if (
        !canvas.contains(ev.target as Node) ||
        (press && Math.hypot(ev.clientX - press.x, ev.clientY - press.y) > 5)
      )
        return;
      pickAt(ev.offsetX, ev.offsetY);
    };
    canvas.addEventListener('click', clickHandler);
    let hoverTimer: ReturnType<typeof setTimeout> | null = null;
    const moveHandler = (ev: MouseEvent) => {
      // throttled — picking is the expensive part of this whole page
      if (!canvas.contains(ev.target as Node)) return;
      if (hoverTimer) clearTimeout(hoverTimer);
      hoverTimer = setTimeout(() => {
        const picked = scene.pick(new Cesium.Cartesian2(ev.offsetX, ev.offsetY));
        const props = entityProps(picked?.id ?? null);
        if (!props || !picked?.id) {
          hoverChip.hidden = true;
          canvas.style.cursor = '';
          return;
        }
        canvas.style.cursor = 'pointer';
        let text: string | undefined;
        if (props.kind === 'event')
          text = props.name; // title — the feed owns detail, chip only orients
        else if (props.kind === 'city') text = `${props.name} · city`;
        else if (props.kind === 'flight')
          text = `${props.name}${selectedFlightId === String(props.flightId ?? '') ? ' · route pinned' : ' · click to pin route'}`;
        else if (props.kind === 'seismic') text = props.name;
        else if (props.kind === 'censys') text = `exposed host ${props.name}`;
        if (!text) {
          hoverChip.hidden = true;
          return;
        }
        hoverChip.textContent = text.length > 72 ? text.slice(0, 69) + '…' : text; // bounded chip width keeps the globe uncluttered
        const rect = canvas.getBoundingClientRect();
        hoverChip.style.left = `${Math.min(ev.offsetX + 14, Math.max(rect.width - 300, 8))}px`;
        hoverChip.style.top = `${ev.offsetY + 16}px`;
        hoverChip.hidden = false;
      }, 70);
    };
    canvas.addEventListener('mousemove', moveHandler);
    const leaveHandler = () => {
      if (hoverTimer) clearTimeout(hoverTimer);
      hoverChip.hidden = true;
    };
    canvas.addEventListener('mouseleave', leaveHandler);

    overlay.querySelector('.region-close')!.addEventListener('click', () => selectRegion(null));

    // ---------------------------------------------------------- polling (static-host friendly: cache-busted GETs, last-good retention)

    let flightsPending = false;
    let seismicPending = false;
    let censysPending = false;

    async function pollFlights() {
      if (destroyed || document.hidden || !layersOn.flights || flightsPending) return;
      flightsPending = true;
      try {
        const r = await fetch(`${BASE}data/flights.json?t=${Date.now()}`);
        if (!r.ok || destroyed) return;
        const data = await r.json();
        if (destroyed || !Array.isArray(data.aircraft) || !Number.isFinite(data.ts)) return;
        const nextTrails = prepareTrails(data);
        flightsEnv = data;
        preparedTrails = nextTrails;
        rebuildFlights();
        refreshStatus();
      } catch {
        /* keep last good envelope — stale-but-labeled, never blank */
      } finally {
        flightsPending = false;
      }
    }
    async function pollSeismic() {
      if (destroyed || document.hidden || !layersOn.seismic || seismicPending) return;
      seismicPending = true;
      try {
        const r = await fetch(`${SEISMIC_URL}?t=${Date.now()}`);
        if (!r.ok || destroyed) return;
        const data = await r.json();
        if (destroyed || !Array.isArray(data.features)) return;
        seismicData = data;
        rebuildSeismic();
        refreshStatus();
      } catch {
        /* offline → layer empty until next success */
      } finally {
        seismicPending = false;
      }
    }
    async function pollCensys() {
      if (destroyed || document.hidden || !layersOn.censys || censysPending) return;
      censysPending = true;
      try {
        const r = await fetch(`${BASE}data/censys.json?t=${Date.now()}`);
        if (!r.ok || destroyed) return;
        const data = await r.json();
        if (destroyed || !Array.isArray(data.hosts) || !Number.isFinite(data.ts)) return;
        censysEnv = data;
        rebuildCensys();
        refreshStatus();
      } catch {
        /* file absent until first keyed ingest */
      } finally {
        censysPending = false;
      }
    }
    let pollTimer: ReturnType<typeof setInterval> | null = null;

    // ---------------------------------------------------------- camera tiering for city detail + destroy bookkeeping
    const preUpdateListener = () => {
      if (destroyed) return;
      if (layersOn.cities && citiesCache) rebuildCities();
      if (layersOn.flights && flightsEnv) {
        const tier = flightTrailTier(camera.positionCartographic?.height ?? 19_000_000);
        if (tier !== lastFlightTrailTier) rebuildFlights();
      }
    };
    scene.preUpdate.addEventListener(preUpdateListener);

    const visibilityHandler = () => {
      if (destroyed || document.hidden) return;
      refreshStatus();
      if (layersOn.flights) void pollFlights();
      if (layersOn.seismic) void pollSeismic();
      if (layersOn.censys) void pollCensys();
    };
    document.addEventListener('visibilitychange', visibilityHandler);

    // Layout may settle after async initialization.
    if (!destroyed) viewer.resize();

    const adapter: GlobeAdapter = {
      update(events, active) {
        visibleEvents = events;
        activeEventId = active;
        rebuildEvents();
        if (selectedRegion) selectRegion(selectedRegion, false);
      },
      focus(id) {
        flyToRegion(null, id);
      },
      resize() {
        if (!destroyed) viewer.resize();
      },
      getLayer(name) {
        return layersOn[name];
      },
      getImageMode() {
        return imageryMode;
      },
      resetView() {
        selectRegion(null, false);
        camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(20, homeLatitude, homeHeight),
          duration: reducedMotion ? 0 : 1,
        });
      },
      zoom(direction) {
        camera.zoomIn(direction * camera.positionCartographic.height * 0.4);
      },
      setPresentationMode(enabled) {
        if (presentationMode === enabled) return;
        presentationMode = enabled;
        hoverChip.hidden = true;
        rebuildEvents();
        if (!destroyed) viewer.resize();
      },
      setSuspended(suspended) {
        if (destroyed) return;
        // The globe is covered while the tiles-only feed is showing: stop paying
        // for frames nobody can see, and resume on the switch back.
        viewer.useDefaultRenderLoop = !suspended;
      },
      whenImagerySettled(timeoutMs = 4500) {
        return new Promise((resolve) => {
          if (destroyed) {
            resolve('timeout');
            return;
          }
          let settled = false;
          let timer = 0;
          let poll = 0;
          const finish = (status: 'ready' | 'timeout') => {
            if (settled) return;
            settled = true;
            window.clearTimeout(timer);
            window.clearInterval(poll);
            scene.globe.tileLoadProgressEvent.removeEventListener(onProgress);
            resolve(status);
          };
          const onProgress = (remaining: number) => {
            if (remaining === 0 && scene.globe.tilesLoaded) finish('ready');
          };
          timer = window.setTimeout(() => finish('timeout'), timeoutMs);
          poll = window.setInterval(() => {
            if (!destroyed && scene.globe.tilesLoaded) finish('ready');
          }, 200);
          scene.globe.tileLoadProgressEvent.addEventListener(onProgress);
          if (scene.globe.tilesLoaded) finish('ready');
        });
      },
      destroy() {
        if (destroyed) return;
        destroyed = true;
        resizeObserver.disconnect();
        cancelAnimationFrame(resizeFrame);
        if (hoverTimer) clearTimeout(hoverTimer);
        if (pollTimer) clearInterval(pollTimer);
        document.removeEventListener('visibilitychange', visibilityHandler);
        scene.preUpdate.removeEventListener(preUpdateListener);
        canvas.removeEventListener('pointerdown', downHandler);
        canvas.removeEventListener('mouseleave', leaveHandler);
        status.remove();
        overlay.remove();
        hoverChip.remove();
        try {
          canvas.removeEventListener('click', clickHandler);
        } catch {
          /* */
        }
        try {
          canvas.removeEventListener('mousemove', moveHandler);
        } catch {
          /* */
        }
        effects.destroy();
        viewer.destroy();
      },
      setLayers(next: Partial<Record<LayerName, boolean>>) {
        Object.assign(layersOn, next);
        lastCityTier = -1;
        if ('flights' in next) lastFlightTrailTier = -1;
        rebuildCities();
        if (next.flights) void pollFlights();
        if (next.seismic) void pollSeismic();
        if (next.censys) void pollCensys();
        if (next.cities)
          void loadCities()
            .then(() => {
              if (!destroyed) rebuildCities();
            })
            .catch(() => undefined);
        rebuildEvents();
        rebuildFlights();
        rebuildSeismic();
        rebuildCensys();
        lastCityTier = -1;
        refreshStatus();
      },
      setImageMode(mode: ImageryMode) {
        imageryMode = mode;
        darkLayer.show = mode === 'dark';
        satLayer.show = mode === 'satellite';
        effects.setSatellite(mode === 'satellite');
        // The surface material owns night shading; never apply it twice.
        scene.globe.showGroundAtmosphere = false;
        scene.globe.enableLighting = false;
        scene.globe.dynamicAtmosphereLighting = false;
      },
    };

    // initial layer state + first polls (flights default on — trails are the signature look)
    refreshStatus();
    if (layersOn.flights) void pollFlights();

    // Start the poll timer
    pollTimer = setInterval(() => {
      if (document.hidden) return;
      refreshStatus();
      if (layersOn.flights) void pollFlights();
      if (layersOn.seismic) void pollSeismic();
      if (layersOn.censys) void pollCensys();
    }, POLL_MS);

    return adapter;
  })();
}
