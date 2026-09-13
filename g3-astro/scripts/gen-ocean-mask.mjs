// Natural Earth 1:50m admin polygons (GeoJSON with original geometry, including Antarctica).
// node scripts/gen-ocean-mask.mjs input.geojson /tmp/ocean-mask.svg
// Rasterize at 4096 x 2048; R = water, G = blurred water (visual coastal falloff).
import { readFileSync, writeFileSync } from 'node:fs';
const [input, output] = process.argv.slice(2);
if (!input || !output) throw new Error('usage: gen-ocean-mask.mjs input.geojson output.svg');
const { features } = JSON.parse(readFileSync(input, 'utf8'));
const paths = features.flatMap(({ geometry }) => {
  const polygons = geometry.type === 'MultiPolygon' ? geometry.coordinates : [geometry.coordinates];
  return polygons.map(
    (rings) =>
      `<path d="${rings.map((ring) => ring.map(([lon, lat], i) => `${i ? 'L' : 'M'}${(((lon + 180) / 360) * 4096).toFixed(2)},${(((90 - lat) / 180) * 2048).toFixed(2)}`).join(' ') + 'Z').join(' ')}"/>`,
  );
});
writeFileSync(
  output,
  `<svg xmlns="http://www.w3.org/2000/svg" width="4096" height="2048" viewBox="0 0 4096 2048"><rect width="4096" height="2048" fill="white"/><g fill="black" fill-rule="evenodd" stroke="black" stroke-width="1">${paths.join('')}</g></svg>`,
);
