# Globe effects textures

- `night-lights-2016.jpg`: NASA Earth Observatory, Black Marble 2016 color composite,
  resampled from 13500 × 6750 to 4096 × 2048, JPEG quality 90.
  Source: https://assets.science.nasa.gov/content/dam/science/esd/eo/images/imagerecords/144000/144898/BlackMarble_2016_3km.jpg
  Description: https://science.nasa.gov/earth/earth-observatory/earth-at-night/maps/
  Historical composite, not live lights, power availability, or current activity.
- `bathymetry.jpg`: NASA Earth Observatory / Jesse Allen, GEBCO ocean bathymetry
  from the British Oceanographic Data Centre, resampled from 5400 × 2700 to 4096 × 2048.
  Source: https://assets.science.nasa.gov/content/dam/science/esd/eo/images/bmng/bathymetry/gebco_08_rev_bath_5400x2700.jpg
  Description: https://science.nasa.gov/earth/earth-observatory/blue-marble-next-generation/topography-bathymetry-maps/
  Depth image drives the ocean palette; this is illustrative shading, not a nautical chart.
- `ocean-mask.png`: Natural Earth 1:50m admin-0 country polygons, public domain.
  Source: https://www.naturalearthdata.com/downloads/50m-cultural-vectors/50m-admin-0-countries/
  Rasterized including polygon holes and Antarctica at 4096 × 2048.
  Red/blue = water mask; green = water mask blurred by 10 pixels.
  Coast coloring is an artistic transition, not measured bathymetry.
- Wave normals: Cesium's bundled `Assets/Textures/waterNormals.jpg`, covered by
  the Cesium distribution's accompanying licenses. No new external runtime host.

Rebuild the mask with `scripts/gen-ocean-mask.mjs input.geojson /tmp/ocean-mask.svg`,
then ImageMagick:

```sh
magick -background white /tmp/ocean-mask.svg -alpha off /tmp/ocean-water.png
magick /tmp/ocean-water.png -blur 0x10 /tmp/ocean-coast.png
magick /tmp/ocean-water.png /tmp/ocean-coast.png /tmp/ocean-water.png -combine public/data/globe/effects/ocean-mask.png
```

Water animation is decorative, not a wave-height or ocean-current observation.
