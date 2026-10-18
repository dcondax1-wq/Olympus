// "Chrome Monolith": a glossy black-glass candlestick monolith on a mirror neon grid,
// a striped synthwave sun behind, its lower wick piercing the floor (the liquidity level)
// with a cyan light splash.
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { Reflector } from 'three/addons/objects/Reflector.js';
import { C, col, makeEnv, flare, glowSprite, present } from './_common.js';

export default async ({ THREE, renderer, size }) => {
  const scene = new THREE.Scene();
  const horizonC = new THREE.Color(0x2a0848).multiplyScalar(0.55);
  scene.fog = new THREE.FogExp2(horizonC, 0.035);
  scene.environment = makeEnv(THREE, renderer, {
    top: 0x06020c, horizon: 0x1a0630, bottom: 0x010002,
    panels: [
      { c: 0xff4fd8, i: 1.8, w: 10, h: 4, pos: [0, 1.5, -9] },        // sun glow behind
      { c: C.violet, i: 1.6, w: 16, h: 0.6, pos: [0, 0.2, -9] },      // horizon line
      { c: C.magenta, i: 2.2, w: 0.6, h: 8, pos: [-7, 2, -3] },       // left-back rim
      { c: C.violet, i: 2.0, w: 0.6, h: 8, pos: [7, 2, -3] },         // right-back rim
      { c: 0xffffff, i: 1.6, w: 0.12, h: 7, pos: [-2.5, 2, 7], rz: 0.5 }, // glossy streak on front faces
      { c: C.hotpink, i: 1.0, w: 0.2, h: 6, pos: [3, 1, 7], rz: -0.35 },
      { c: 0xe9d5ff, i: 0.8, w: 6, h: 1.5, pos: [0, 8, 0] },
    ],
  });

  const camera = new THREE.PerspectiveCamera(38, 1, 0.05, 400);
  camera.position.set(0, 0.7, 7.5); camera.lookAt(0, 1.6, 0);

  // ---------- sky dome ----------
  const sky = new THREE.Mesh(new THREE.SphereGeometry(300, 48, 24), new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: { hz: { value: horizonC }, hot: { value: col(THREE, 0x8b2fd6, 0.5) }, top: { value: col(THREE, 0x030008, 1) } },
    vertexShader: 'varying vec3 vD; void main(){ vD = normalize(position); gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }',
    fragmentShader: `uniform vec3 hz, hot, top; varying vec3 vD;
      float h(vec3 p){ return fract(sin(dot(p, vec3(12.9898,78.233,37.719)))*43758.5453); }
      void main(){ float y = max(vD.y, 0.); vec3 c = mix(hz, top, smoothstep(0., 0.38, y));
        c += hot*exp(-y*y*900.)*exp(-vD.x*vD.x*3.);
        vec3 q = floor(vD*420.); float st = step(0.9965, h(q))*smoothstep(0.05, 0.3, y)*0.35;
        gl_FragColor = vec4(c + st*vec3(0.8,0.7,1.), 1.); }`,
  }));
  scene.add(sky);

  // ---------- synthwave sun ----------
  const sunR = 15.5;
  const sun = new THREE.Mesh(new THREE.PlaneGeometry(sunR * 2, sunR * 2), new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, fog: false,
    uniforms: { top: { value: col(THREE, 0xff6fdc, 1.25) }, mid: { value: col(THREE, 0xff2bc8, 1.2) }, bot: { value: col(THREE, 0x7c2fe0, 1.05) } },
    vertexShader: 'varying vec2 vP; void main(){ vP = position.xy/' + sunR.toFixed(1) + '; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }',
    fragmentShader: `uniform vec3 top, mid, bot; varying vec2 vP;
      void main(){ float r = length(vP); float y = vP.y;
        vec3 c = y > -0.1 ? mix(mid, top, smoothstep(-0.1, 0.95, y)) : mix(bot, mid, smoothstep(-0.55, -0.1, y));
        float edge = 1. - smoothstep(1. - fwidth(r)*1.5, 1., r);
        float band = 0.;
        if (y < 0.05) { float t = (0.05 - y); float per = 0.11; float ph = fract(t/per); float gap = 0.1 + t*0.75;
          float aa = fwidth(t/per)*1.2; band = smoothstep(1.-gap-aa, 1.-gap+aa, ph); }
        float a = edge*(1.-band);
        gl_FragColor = vec4(c*a, a); }`,
  }));
  sun.position.set(0, 9.6, -60); scene.add(sun);
  const sunHalo = glowSprite(THREE, 0xc026d3, 0.35, sunR * 3.4, sunR * 2.6); sunHalo.position.set(0, 8.8, -61); sunHalo.material.fog = false; scene.add(sunHalo);

  // ---------- mirror grid floor (Reflector with custom shader) ----------
  const floorShader = {
    name: 'NeonGridFloor',
    uniforms: { color: { value: null }, tDiffuse: { value: null }, textureMatrix: { value: null },
      grid: { value: col(THREE, C.magenta, 1.4) }, grid2: { value: col(THREE, C.violet, 1.15) }, fogC: { value: horizonC }, lvl: { value: col(THREE, C.cyan, 1) }, px: { value: 1 / size } },
    vertexShader: `uniform mat4 textureMatrix; varying vec4 vUv; varying vec3 vW;
      void main(){ vUv = textureMatrix*vec4(position,1.); vW = (modelMatrix*vec4(position,1.)).xyz; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
    fragmentShader: `uniform vec3 color, grid, grid2, fogC, lvl; uniform sampler2D tDiffuse; uniform float px; varying vec4 vUv; varying vec3 vW;
      float gl(float x, float w){ float aa = fwidth(x)*1.2; float lw = max(w, aa); float d = abs(fract(x+.5)-.5); return (1.-smoothstep(lw-aa, lw+aa, d))*(w/lw); }
      void main(){
        vec2 uv = vUv.xy/vUv.w; vec3 refl = vec3(0.);
        for (int i = 0; i < 12; i++) { float a = float(i)*2.39996; float rr = sqrt(float(i)+.5)/3.5; refl += texture2D(tDiffuse, uv + vec2(cos(a), sin(a))*rr*px*7.).rgb; }
        refl /= 12.;
        float dist = length(vW - cameraPosition);
        float g = max(gl(vW.x*0.9, 0.022), gl(vW.z*0.9 + 0.5, 0.022));
        vec3 V = normalize(cameraPosition - vW); float fr = 0.12 + 0.88*pow(1. - V.y, 4.);
        vec3 c = vec3(0.004, 0.0015, 0.008) + refl*0.42*fr*color;
        c += mix(grid, grid2, smoothstep(5., 30., dist))*g;
        // the liquidity level: cyan laser line through the pierce point
        float lz = abs(vW.z); c += lvl*(exp(-pow(lz/0.022, 2.))*2.6 + exp(-pow(lz/0.18, 2.))*0.25)*exp(-abs(vW.x)*0.05);
        // splash ripples around the pierce point
        float r = length(vW.xz);
        c += lvl*(exp(-pow((r-0.42)/0.03, 2.))*1.3 + exp(-pow((r-0.8)/0.04, 2.))*0.6 + exp(-pow((r-1.3)/0.06, 2.))*0.25 + exp(-r*r*6.)*1.2);
        float f = 1. - exp(-dist*0.035);
        c = mix(c, fogC, clamp(f, 0., 1.));
        gl_FragColor = vec4(c, 1.); }`,
  };
  const floor = new Reflector(new THREE.PlaneGeometry(240, 240), { shader: floorShader, color: 0xffffff, textureWidth: size, textureHeight: size, multisample: 4 });
  floor.material.uniforms.grid.value = floorShader.uniforms.grid.value;
  floor.material.uniforms.grid2.value = floorShader.uniforms.grid2.value;
  floor.material.uniforms.fogC.value = horizonC;
  floor.material.uniforms.lvl.value = floorShader.uniforms.lvl.value;
  floor.material.uniforms.px.value = 1 / size;
  floor.material.extensions = { derivatives: true };
  floor.rotation.x = -Math.PI / 2; floor.position.z = -100; scene.add(floor);

  // ---------- the monolith candlestick ----------
  const m = new THREE.Group(); m.rotation.y = 0.55; scene.add(m);
  const glassBlack = new THREE.MeshPhysicalMaterial({ color: 0x0b0714, metalness: 0.15, roughness: 0.05, clearcoat: 1, clearcoatRoughness: 0.02, envMapIntensity: 1.6, ior: 1.6, specularIntensity: 1 });
  const chrome = new THREE.MeshPhysicalMaterial({ color: 0xeeeaf8, metalness: 1, roughness: 0.1, envMapIntensity: 1.3 });
  const neon = (hex, k) => new THREE.MeshBasicMaterial({ color: col(THREE, hex, k), fog: false });
  const bY0 = 0.62, bY1 = 2.86, bw = 0.7, bh = bY1 - bY0, bc = (bY0 + bY1) / 2;
  const body = new THREE.Mesh(new RoundedBoxGeometry(bw, bh, bw, 5, 0.05), glassBlack); body.position.y = bc; m.add(body);
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
    const e = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.011, bh - 0.06, 8), neon(sx > 0 && sz < 0 ? C.violet : C.magenta, 2.2));
    e.position.set(sx * (bw / 2 - 0.006), bc, sz * (bw / 2 - 0.006)); m.add(e);
  }
  for (const s of [-1, 1]) {
    const cap = new THREE.Mesh(new RoundedBoxGeometry(bw + 0.06, 0.07, bw + 0.06, 3, 0.025), chrome);
    cap.position.y = s > 0 ? bY1 + 0.035 : bY0 - 0.035; m.add(cap);
  }
  const wick = (y0, y1, r, mat) => { const w = new THREE.Mesh(new THREE.CylinderGeometry(r, r, Math.abs(y1 - y0), 32), mat); w.position.y = (y0 + y1) / 2; m.add(w); return w; };
  wick(bY1 + 0.07, bY1 + 0.62, 0.07, chrome);
  const tip = new THREE.Mesh(new THREE.SphereGeometry(0.07, 24, 16), chrome); tip.position.y = bY1 + 0.62; m.add(tip);
  wick(0.3, bY0 - 0.07, 0.07, chrome);
  wick(-0.2, 0.3, 0.05, neon(C.cyan, 2.4));   // the hot sweep wick dipping through the level

  // ---------- splash at the pierce point ----------
  const fl = flare(THREE, { tint: C.cyan, core: 0xffffff, k: 1.1, scale: 0.9, streak: 1.6, spikes: false });
  fl.position.set(0, 0.03, 0); fl.traverse(o => { if (o.material) o.material.fog = false; }); scene.add(fl);
  let seed = 5; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < 30; i++) { // crown of light droplets flung outward
    const a = i / 30 * Math.PI * 2 + rnd() * 0.15, len = 0.07 + rnd() * 0.12, rr = 0.2 + rnd() * 0.06, h = 0.03 + rnd() * 0.1;
    const d = new THREE.Mesh(new THREE.CylinderGeometry(0.004, 0.011, len, 6), neon(i % 6 === 0 ? 0xffffff : C.cyan, 2.2));
    d.position.set(Math.cos(a) * rr, h + len * 0.4, Math.sin(a) * rr);
    d.lookAt(Math.cos(a) * 5, h + 4, Math.sin(a) * 5); d.rotateX(Math.PI / 2); scene.add(d);
  }
  for (let i = 0; i < 18; i++) {
    const a = rnd() * Math.PI * 2, rr = 0.25 + rnd() * 0.5, s = glowSprite(THREE, C.cyan, 1.5, 0.035 + rnd() * 0.04);
    s.material.fog = false; s.position.set(Math.cos(a) * rr, 0.12 + rnd() * 0.3 * (1 - rr), Math.sin(a) * rr); scene.add(s);
  }
  const wave = new THREE.Mesh(new THREE.TorusGeometry(0.2, 0.012, 8, 96), neon(C.cyan, 2.2)); wave.rotation.x = Math.PI / 2; wave.position.y = 0.012; scene.add(wave);
  const wave2 = new THREE.Mesh(new THREE.TorusGeometry(0.5, 0.008, 8, 128), neon(C.cyan, 1.6)); wave2.rotation.x = Math.PI / 2; wave2.position.y = 0.008; scene.add(wave2);
  // the liquidity level: a raised cyan laser bar across the floor
  const lvl = new THREE.Mesh(new THREE.BoxGeometry(80, 0.014, 0.03), new THREE.MeshBasicMaterial({ color: col(THREE, C.cyan, 2.2), fog: true }));
  lvl.position.y = 0.007; scene.add(lvl);
  // low-poly mountain ridges on the horizon, dark with glowing ridge lines
  const ridge = (side, z, hScale, seedR, hex) => {
    let sd = seedR; const r = () => (sd = (sd * 16807) % 2147483647) / 2147483647;
    const pts = []; const n = 16, x0 = side * 5, x1 = side * 60;
    for (let i = 0; i <= n; i++) { const t = i / n; const x = x0 + (x1 - x0) * t; const env = Math.sin(Math.min(1, t * 1.6) * Math.PI * 0.5) * (1 - t * 0.35); pts.push(new THREE.Vector2(x, (0.4 + r() * 0.9) * env * hScale)); }
    const shape = new THREE.Shape(); shape.moveTo(x0, -0.5); for (const p of pts) shape.lineTo(p.x, p.y); shape.lineTo(x1, -0.5); shape.lineTo(x0, -0.5);
    const mtn = new THREE.Mesh(new THREE.ShapeGeometry(shape), new THREE.MeshBasicMaterial({ color: 0x07020d, side: THREE.DoubleSide, fog: false }));
    mtn.position.z = z; scene.add(mtn);
    const line = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts.map(p => new THREE.Vector3(p.x, p.y, z + 0.05)), false, 'catmullrom', 0), 120, 0.07, 6, false), new THREE.MeshBasicMaterial({ color: col(THREE, hex, 1.5), fog: false }));
    scene.add(line);
  };
  ridge(-1, -48, 5.5, 3, C.violet); ridge(1, -48, 4.8, 9, C.violet);

  // real reflections for the black glass: capture the neon world into a cube map
  const cubeRT = new THREE.WebGLCubeRenderTarget(256, { type: THREE.HalfFloatType });
  const cubeCam = new THREE.CubeCamera(0.05, 400, cubeRT); cubeCam.position.set(0, 1.75, 0); scene.add(cubeCam);
  m.visible = false; cubeCam.update(renderer, scene); m.visible = true;
  glassBlack.envMap = cubeRT.texture; glassBlack.envMapIntensity = 0.8;

  const out = present(THREE, renderer, scene, camera, size, { scale: 2, samples: 4, frames: 1, vignette: 0.45, ca: 0.2 });
  return { ...out, bloom: { strength: 0.75, radius: 0.45, threshold: 0.9 } };
};
