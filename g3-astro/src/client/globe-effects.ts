import * as Cesium from 'cesium';

// Globe materials blend diffuse + alpha over imagery; emission/specular fields
// are ignored by GlobeFS. Compute the water lighting here, in world coordinates.
// Do not use tile-local materialInput.st: waves/masks must cross tile seams.
export const oceanShader = `
uniform sampler2D oceanMask;
uniform sampler2D nightMap;
uniform sampler2D oceanDepth;
uniform sampler2D waveNormals;
uniform float elapsed;
uniform float nightEnabled;
uniform float nightDetail;
uniform float satellite;

czm_material czm_getMaterial(czm_materialInput inputData) {
    czm_material result = czm_getDefaultMaterial(inputData);
    vec3 positionWC = (czm_inverseView * vec4(-inputData.positionToEyeEC, 1.0)).xyz;
    vec3 up = normalize(positionWC / vec3(40680631590769.0, 40680631590769.0, 40408299984661.0));
    vec2 uv = vec2(atan(up.y, up.x) / czm_twoPi + 0.5, asin(up.z) / czm_pi + 0.5);
    vec2 mask = texture(oceanMask, uv).rg;
    // Conservative land edge; retain provider coast detail when zoomed in.
    float water = smoothstep(0.92, 1.0, mask.r);
    float coast = pow(clamp(1.0 - mask.g, 0.0, 1.0), 0.65);
    float polar = 1.0 - smoothstep(1.22, 1.48, abs(asin(up.z)));
    water *= polar;
    vec3 sun = normalize(czm_sunDirectionWC);
    float sunHeight = dot(up, sun);
    float daylight = smoothstep(-0.16, 0.24, sunHeight);
    float night = (1.0 - smoothstep(-0.22, 0.08, sunHeight)) * nightEnabled;
    vec3 view = normalize(czm_inverseViewRotation * inputData.positionToEyeEC);
    vec3 east = normalize(vec3(-up.y, up.x, 0.00001));
    vec3 north = normalize(cross(up, east));
    // Two periodic wave scales meet at the antimeridian. Two texture reads keep
    // the effect affordable on integrated GPUs; no multi-octave noise loop.
    vec2 waveUV = vec2(uv.x * 2.0, uv.y);
    vec3 swell = texture(waveNormals, fract(waveUV * 4.0 + vec2(elapsed * 0.012, elapsed * 0.004))).xyz * 2.0 - 1.0;
    vec3 ripples = texture(waveNormals, fract(waveUV * 16.0 + vec2(-elapsed * 0.018, elapsed * 0.009))).xyz * 2.0 - 1.0;
    vec2 perturbation = swell.xy * 0.16 + ripples.xy * 0.045;
    vec3 waveNormal = normalize(up + east * perturbation.x + north * perturbation.y);
    float facing = max(dot(up, view), 0.0);
    float fresnel = 0.025 + 0.4 * pow(1.0 - facing, 4.0);
    vec3 halfVector = normalize(sun + view);
    float glint = pow(max(dot(waveNormal, halfVector), 0.0), 150.0);
    float broadGlint = pow(max(dot(up, halfVector), 0.0), 14.0);
    float depthTone = texture(oceanDepth, uv).r;
    float shelf = pow(depthTone, 1.7);
    vec3 deep = mix(vec3(0.016, 0.075, 0.14), vec3(0.02, 0.12, 0.20), satellite);
    vec3 waterColor = mix(deep, vec3(0.05, 0.29, 0.36), clamp(shelf * 0.8 + coast * 0.25, 0.0, 1.0));
    waterColor *= 0.72 + 0.28 * max(sunHeight, 0.0);
    waterColor += vec3(0.055, 0.14, 0.20) * fresnel;
    waterColor += vec3(0.13, 0.23, 0.29) * broadGlint * daylight * (0.65 + swell.x * 0.3);
    waterColor += vec3(0.72, 0.82, 0.83) * glint * daylight * 0.38;
    waterColor += vec3(0.018, 0.045, 0.06) * (swell.x + ripples.y) * daylight;
    waterColor *= mix(1.0, 0.48, night);
    // NASA's color composite contains blue land/ocean. Isolate warm light energy.
    vec3 observed = texture(nightMap, uv).rgb;
    float lights = max(observed.r - observed.b * 0.85 - 0.055, 0.0);
    // The global Black Marble image is intentionally faded as the camera gets
    // close. At street/regional scales a neutral tint preserves sharp provider
    // labels and coast detail instead of magnifying the low-resolution composite.
    lights = pow(lights, 0.8) * 2.2 * nightDetail;
    vec3 nightColor = vec3(0.012, 0.023, 0.044) + vec3(1.0, 0.68, 0.30) * lights;
    float landAlpha = night * mix(0.34, 0.84, nightDetail);
    float oceanAlpha = water * mix(0.94, 0.82, satellite);
    result.alpha = oceanAlpha + landAlpha * (1.0 - oceanAlpha);
    result.diffuse = (waterColor * oceanAlpha + nightColor * landAlpha * (1.0 - oceanAlpha)) / max(result.alpha, 0.0001);
    return result;
}`;

export function attachGlobeEffects(
  viewer: Cesium.Viewer,
  container: HTMLElement,
  base: string,
  reducedMotion: boolean,
) {
  const material = new Cesium.Material({
    fabric: {
      type: 'SycamoreOceanNight',
      uniforms: {
        oceanMask: `${base}data/globe/effects/ocean-mask.png`,
        nightMap: `${base}data/globe/effects/night-lights-2016.jpg`,
        oceanDepth: `${base}data/globe/effects/bathymetry.jpg`,
        waveNormals: `${base}cesium/Assets/Textures/waterNormals.jpg`,
        elapsed: 0,
        nightEnabled: 1,
        nightDetail: 1,
        satellite: 0,
      },
      source: oceanShader,
    },
  });
  viewer.scene.globe.material = material;
  let motion = !reducedMotion;
  let night = true;
  let lapse = false;
  let seconds = 0;
  let previous = performance.now();
  viewer.clock.shouldAnimate = !reducedMotion;
  viewer.clock.multiplier = 1;

  const controls = document.createElement('div');
  controls.className = 'globe-effects';
  controls.setAttribute('role', 'group');
  controls.setAttribute('aria-label', 'Globe appearance');
  const buttons = document.createElement('div');
  buttons.className = 'globe-effects-buttons';
  const caption = document.createElement('p');
  caption.className = 'globe-effects-caption';
  const button = (label: string, title: string, action: () => void) => {
    const element = document.createElement('button');
    element.type = 'button';
    element.className = 'globe-layer-chip';
    element.textContent = label;
    element.title = title;
    element.onclick = action;
    buttons.appendChild(element);
    return element;
  };
  const waterButton = button('Water motion', 'Animate the ocean surface', () => {
    motion = !motion;
    refresh();
  });
  const nightButton = button(
    'Night lights',
    'Show the solar night side with NASA’s 2016 light composite',
    () => {
      night = !night;
      material.uniforms.nightEnabled = Number(night);
      refresh();
    },
  );
  const lapseButton = button(
    'Time lapse',
    'Preview the day/night cycle at ten simulated minutes per second',
    () => {
      lapse = !lapse;
      if (lapse) {
        night = true;
        material.uniforms.nightEnabled = 1;
      }
      viewer.clock.currentTime = Cesium.JulianDate.now();
      viewer.clock.multiplier = lapse ? 600 : 1;
      viewer.clock.shouldAnimate = lapse || !reducedMotion;
      refresh();
    },
  );
  function refresh() {
    for (const [element, active] of [
      [waterButton, motion],
      [nightButton, night],
      [lapseButton, lapse],
    ] as const) {
      element.setAttribute('aria-pressed', String(active));
      element.classList.toggle('active', active);
    }
    caption.textContent = `${lapse ? 'Sun · time lapse 600×' : 'Sun · current time'}${night ? ' / Night imagery · NASA 2016' : ''}`;
  }
  refresh();
  controls.append(buttons, caption);
  container.appendChild(controls);
  const credit = new Cesium.Credit(
    'Ocean relief: NASA / GEBCO · Night lights: NASA Black Marble 2016',
    true,
  );
  viewer.creditDisplay.addStaticCredit(credit);
  const removeUpdate = viewer.scene.preUpdate.addEventListener(() => {
    const now = performance.now();
    // Use elapsed wall time, not frame count; do not jump after a suspended tab.
    if (motion && !document.hidden) seconds += Math.min((now - previous) / 1000, 0.1);
    previous = now;
    material.uniforms.elapsed = seconds;
    const height = viewer.camera.positionCartographic?.height ?? 19_000_000;
    const detail = Cesium.Math.clamp((height - 2_000_000) / 7_000_000, 0, 1);
    // Smooth the handoff so wheel zooming never produces a visible brightness step.
    material.uniforms.nightDetail = detail * detail * (3 - 2 * detail);
  });
  return {
    setSatellite(enabled: boolean) {
      material.uniforms.satellite = Number(enabled);
    },
    destroy() {
      removeUpdate();
      controls.remove();
      viewer.creditDisplay.removeStaticCredit(credit);
      viewer.scene.globe.material = undefined;
      material.destroy();
    },
  };
}
