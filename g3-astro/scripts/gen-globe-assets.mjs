// One-time generator for globe baselines (Natural Earth 50m + worldcities).
// Run: node scripts/gen-globe-assets.mjs <countries.geojson> <cities.json>
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';

const [countryPath, cityPath] = process.argv.slice(2);
if (!countryPath || !cityPath) {
  console.error('usage: node scripts/gen-globe-assets.mjs countries.geojson cities.json');
  process.exit(1);
}
mkdirSync(new URL('../public/data/globe/', import.meta.url), { recursive: true });

const r4 = (n) => Math.round(n * 1e4) / 1e4;

// --- Countries -----------------------------------------------------------
// Output shape per feature (ring-normalized, antimeridian-split):
//   properties: { name, iso }
//   rings: [ [[lon,lat]...], ... ]     outer rings only — holes are irrelevant at 50m and halve the walk
//   bbox: [minLon,minLat,maxLon,maxLat] aggregated across sub-rings (Russia spans ±180 by design)
//   centroid: [lon,lat]                point-average of all ring points — fly-to target, never a guessed boundary
// Rings crossing the antimeridian are split into two closed sub-rings at ±180 so client-side
// picking and highlight polylines can treat every ring as lon-monotone (no globe-crossing segments).

function crossesAM(ring) {
  let min = Infinity,
    max = -Infinity;
  for (const [lon] of ring) {
    if (lon < min) min = lon;
    if (lon > max) max = lon;
  }
  return max - min > 180; // a simple closed ring only spans that far when it crosses ±180
}

function splitRing(ringIn) {
  const ring = ringIn.slice();
  if (!crossesAM(ring)) return [ring];
  const out = [];
  let cur = [ring[0]];
  for (let i = 1; i <= ring.length - 1; ++i) {
    // segment i-1 -> i, all edges of the closed ring exactly once
    const a = ring[i - 1],
      b = ring[i];
    if (Math.abs(b[0] - a[0]) > 180) {
      // Adjacent vertices on opposite sides of ±180: this segment crosses the seam.
      // Close 'cur' at the boundary point ON A'S SIDE, start the new ring from B's side — same physical meridian.
      const deltaWrapped = ((b[0] - a[0] + 540) % 360) - 180; // true short-path signed movement (±<180)
      const seamOnASide = Math.sign(a[0]) > 0 ? 180 : -180; // where the path leaves a's side, in unwrapped coords from a
      const f = (seamOnASide - a[0]) / deltaWrapped; // fraction along segment at the crossing (<few degrees wide → linear lat is fine)
      const seamLat = r4(a[1] + f * (b[1] - a[1]));
      cur.push([r4(seamOnASide), seamLat]);
      out.push(cur);
      cur = [[-seamOnASide, seamLat], b]; // new ring opens on the opposite side of the seam
    } else {
      cur.push(b);
    }
  }
  out.push(cur);
  // Drop sub-rings that still span ≥~358° (e.g. Antarctica's outline, which touches ±180 at a vertex and wraps the pole): such rings are unrenderable as polylines on an ellipsoid globe and useless for point-in-polygon tests — dropping them is honest because no event-worthy location sits under the polar cap ring anyway.
  return out
    .filter((r) => r.length >= 3)
    .map((r) =>
      r[0][1] === r[r.length - 1][1] && r[0][0] === r[r.length - 1][0]
        ? r
        : [...r, [r4(r[0][0]), r4(r[0][1])]],
    );
}

function ringSpanDeg(pts) {
  let minLon = Infinity,
    maxLon = -Infinity;
  for (const [lon] of pts) {
    if (lon < minLon) minLon = lon;
    if (lon > maxLon) maxLon = lon;
  }
  return maxLon - minLon;
}

function ringBBox(pts) {
  let minLon = Infinity,
    maxLon = -Infinity,
    minLat = Infinity,
    maxLat = -Infinity;
  for (const [lon, lat] of pts) {
    if (lon < minLon) minLon = lon;
    if (lon > maxLon) maxLon = lon;
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
  }
  return [r4(minLon), r4(minLat), r4(maxLon), r4(maxLat)];
}

const raw = JSON.parse(readFileSync(countryPath, 'utf8'));
const features = [];
for (const f of raw.features ?? []) {
  const p = f.properties;
  if (!p || typeof p.NAME !== 'string' || !f.geometry?.coordinates) continue;
  // Polygon -> [poly]; MultiPolygon -> polys. Each poly: [outerRing, ...holes] — outer only (see header).
  const polys =
    f.geometry.type === 'MultiPolygon' ? f.geometry.coordinates : [f.geometry.coordinates];
  let rings = [];
  for (const poly of polys) {
    if (!Array.isArray(poly?.[0])) continue;
    const ring = poly[0].map(([lon, lat]) => [r4(lon), r4(lat)]);
    // Sub-rings that still span ≥358° after splitting (Antarctica's pole-wrapping outline) are unrenderable as polylines on an ellipsoid and useless for point-in-polygon tests — dropped rather than drawn across the whole globe.
    if (ringSpanDeg(ring) >= 358) continue;
    rings.push(...splitRing(ring).filter((sub) => ringSpanDeg(sub) < 179)); // post-split pieces must be lon-monotone-safe too
  }
  let minLon = Infinity,
    maxLon = -Infinity,
    minLat = Infinity,
    maxLat = -Infinity,
    sx = 0,
    sy = 0,
    n = 0;
  for (const ring of rings) {
    const [a, b, c, d] = ringBBox(ring);
    if (a < minLon) minLon = a;
    if (c > maxLon) maxLon = c;
    if (b < minLat) minLat = b;
    if (d > maxLat) maxLat = d;
    for (const [lon, lat] of ring) {
      sx += lon;
      sy += lat;
      ++n;
    }
  }
  features.push({
    type: 'Feature',
    properties: { name: p.NAME, iso: String(p.ADM0_A3 ?? '').toUpperCase() },
    rings,
    bbox: [r4(minLon), r4(minLat), r4(maxLon), r4(maxLat)],
    centroid: n ? [r4(sx / n), r4(sy / n)] : null, // point-average — honest fly-to target for multi-archipelago states (Russia/Fiji/NZ)
  });
}
const countries = JSON.stringify({ type: 'FeatureCollection', features });

// --- Cities --------------------------------------------------------------
// worldcities rows [lat, lon, name, ISO2, pop] -> public format [lon, lat, name, iso, pop], keep >= MIN_POP.
const citiesRaw = JSON.parse(readFileSync(cityPath, 'utf8'));
const MIN_POP = Number(process.env.MIN_POP || 30000);
const seen = new Set();
const cities = [];
for (const row of citiesRaw) {
  const [lat, lon, name, iso, pop] = row;
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
  if ((pop ?? 0) < MIN_POP) continue;
  const key = `${iso}:${name.toLowerCase()}`;
  if (seen.has(key)) continue; // worldcities has dupes with slightly different coords
  seen.add(key);
  cities.push([r4(lon), r4(lat), name, iso, Number(pop)]);
}

const outDir = new URL('../public/data/globe/', import.meta.url).pathname;
writeFileSync(`${outDir}countries.geojson`, countries);
writeFileSync(`${outDir}cities.json`, JSON.stringify(cities));
console.log(
  `globe assets: ${features.length} countries (${Buffer.byteLength(countries)} B), ${cities.length} cities (pop>=${MIN_POP})`,
);
