// "LE 3D": extruded, beveled chrome letters with black-glass faces and magenta neon tube edges.
// The L sits lower than the E: its foot dips through a cyan liquidity level, which slices the
// chrome with a glowing contour and flares where it breaks through.
import { FontLoader } from 'three/addons/loaders/FontLoader.js';
import { TextGeometry } from 'three/addons/geometries/TextGeometry.js';
import { Reflector } from 'three/addons/objects/Reflector.js';
import { C, col, makeEnv, backdrop, flare, glowSprite, present } from './_common.js';

export default async ({ THREE, renderer, size }) => {
  const font = await new FontLoader().loadAsync('/node_modules/three/examples/fonts/helvetiker_bold.typeface.json');
  const scene = new THREE.Scene();
  scene.environment = makeEnv(THREE, renderer, {
    top: 0x0c0418, horizon: 0x0a0314, bottom: 0x010003,
    panels: [
      { c: 0xf4ecff, i: 1.6, w: 8, h: 1.6, pos: [0, 7, 1] },
      { c: 0xffffff, i: 2.6, w: 6, h: 0.2, pos: [0, 6.5, 3] },
      { c: C.magenta, i: 2.2, w: 1.4, h: 9, pos: [-7, 1, 1.5] },
      { c: C.violet, i: 2.4, w: 3, h: 9, pos: [7, 0.5, -1.5] },
      { c: C.cyan, i: 1.0, w: 7, h: 0.5, pos: [0, -6, 2.5] },
      { c: 0xffffff, i: 2.2, w: 0.16, h: 7, pos: [-3, 0.5, 7], rz: 0.65 },
      { c: C.hotpink, i: 1.8, w: 0.22, h: 7, pos: [3.5, -1, 7], rz: -0.5 },
      { c: C.purple, i: 0.9, w: 12, h: 3, pos: [0, 1, -8] },
    ],
    // 80s-chrome horizon wall behind the camera: violet sky, hot horizon line, magenta ground
    extra: (s) => {
      const dome = new THREE.Mesh(new THREE.SphereGeometry(40, 64, 32), new THREE.ShaderMaterial({ side: THREE.BackSide,
        uniforms: { hy: { value: -0.075 } },
        vertexShader: 'varying vec3 vD; void main(){ vD = normalize(position); gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }',
        fragmentShader: `uniform float hy; varying vec3 vD;
          void main(){ float y = vD.y - hy; float front = smoothstep(-0.6, 0.4, vD.z);
            vec3 sky = mix(vec3(0.42,0.12,0.95)*0.45, vec3(0.004,0.0,0.014), smoothstep(0., 0.12, y));
            vec3 gnd = mix(vec3(1.0,0.14,0.78)*0.6, vec3(0.03,0.0,0.05), smoothstep(0., 0.16, -y));
            vec3 c = (y > 0. ? sky : gnd)*mix(0.35, 1., front); c += vec3(1.,0.85,1.)*exp(-pow(y/0.007,2.))*1.35*front;
            gl_FragColor = vec4(c, 1.); }` }));
      s.add(dome);
    },
    res: 512,
  });
  scene.add(backdrop(THREE, { inner: 0x4a1080, outer: 0x010004, center: [0.5, 0.5], radius: 0.72, k: 0.24, glow: { c: 0x7c3aed, i: 0.1, pos: [0.5, 0.5], size: [0.35, 0.2] } }));

  const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 100);
  camera.position.set(-0.5, -0.35, 6.6); camera.lookAt(0, -0.05, 0);

  // ---------- letters ----------
  const depth = 0.5, bt = 0.06, bs = 0.045;
  const mkGeo = (ch) => { const g = new TextGeometry(ch, { font, size: 1, height: depth, curveSegments: 6, bevelEnabled: true, bevelThickness: bt, bevelSize: bs, bevelSegments: 6 }); g.computeBoundingBox(); return g; };
  const gL = mkGeo('L'), gE = mkGeo('E');
  const wL = gL.boundingBox.max.x - gL.boundingBox.min.x, wE = gE.boundingBox.max.x - gE.boundingBox.min.x, gap = 0.1;
  const total = wL + gap + wE;
  const levelY = 0.0;            // world y of the liquidity level (in letter space, before group transform)
  const dip = 0.17;              // how far the L's foot sweeps below the level

  const yLine = { value: 0 }, toLetter = { value: new THREE.Matrix4() };
  const sliceMat = (faceOrSide) => {
    const m = faceOrSide === 'face'
      ? new THREE.MeshPhysicalMaterial({ color: 0xf2eefa, metalness: 1, roughness: 0.03, envMapIntensity: 1.0 })
      : new THREE.MeshPhysicalMaterial({ color: 0xb8a6e8, metalness: 1, roughness: 0.12, envMapIntensity: 1.2, clearcoat: 0.4, clearcoatRoughness: 0.05 });
    m.onBeforeCompile = (sh) => {
      sh.uniforms.yLine = yLine; sh.uniforms.toLetter = toLetter; sh.uniforms.cyan = { value: col(THREE, C.cyan, 1) };
      sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vWp;').replace('#include <worldpos_vertex>', '#include <worldpos_vertex>\nvWp = (modelMatrix*vec4(transformed,1.)).xyz;');
      sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vWp; uniform float yLine; uniform vec3 cyan; uniform mat4 toLetter;')
        .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
          { float dy = (toLetter*vec4(vWp,1.)).y - yLine; totalEmissiveRadiance += cyan*(exp(-pow(dy/0.014, 2.))*3.0 + exp(-pow(dy/0.07, 2.))*0.5 + (dy < 0. ? 0.9*exp(dy/0.12) : 0.)); }`);
    };
    return m;
  };
  const mats = [sliceMat('face'), sliceMat('side')];
  const letters = new THREE.Group(); scene.add(letters);
  const L = new THREE.Mesh(gL, mats), E = new THREE.Mesh(gE, mats);
  L.position.set(-total / 2 - gL.boundingBox.min.x, levelY - dip - gL.boundingBox.min.y + bs * 0, -depth / 2);
  E.position.set(-total / 2 + wL + gap - gE.boundingBox.min.x, levelY + 0.03 - gE.boundingBox.min.y, -depth / 2);
  letters.add(L, E);

  // neon tubes tracing the front-face outline of each glyph (capsule chains: crisp corners)
  // neon tube: magenta above the level, cyan where the L has swept below it, white-hot at the crossing
  const neonMat = new THREE.ShaderMaterial({
    uniforms: { toLetter, yLine, mag: { value: col(THREE, C.magenta, 2.3) }, cy: { value: col(THREE, C.cyan, 2.4) } },
    vertexShader: 'varying vec3 vWp; void main(){ vWp = (modelMatrix*vec4(position,1.)).xyz; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }',
    fragmentShader: `uniform mat4 toLetter; uniform float yLine; uniform vec3 mag, cy; varying vec3 vWp;
      void main(){ float dy = (toLetter*vec4(vWp,1.)).y - yLine; vec3 c = mix(cy, mag, smoothstep(-0.015, 0.015, dy));
        c += vec3(1.)*exp(-pow(dy/0.02, 2.))*1.2; gl_FragColor = vec4(c, 1.); }`,
  });
  const tubeR = 0.014;
  const outline = (ch, mesh) => {
    for (const sh of font.generateShapes(ch, 1)) {
      const pts = sh.getPoints(); if (pts.length && pts[0].equals(pts[pts.length - 1])) pts.pop();
      for (let i = 0; i < pts.length; i++) {
        const a = pts[i], b = pts[(i + 1) % pts.length];
        const A = new THREE.Vector3(a.x, a.y, depth + bt), B = new THREE.Vector3(b.x, b.y, depth + bt);
        const len = A.distanceTo(B); if (len < 1e-4) continue;
        const cyl = new THREE.Mesh(new THREE.CylinderGeometry(tubeR, tubeR, len, 10, 1, true), neonMat);
        cyl.position.copy(A).add(B).multiplyScalar(0.5); cyl.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), B.clone().sub(A).normalize());
        mesh.add(cyl);
        const j = new THREE.Mesh(new THREE.SphereGeometry(tubeR, 10, 8), neonMat); j.position.copy(A); mesh.add(j);
      }
    }
  };
  outline('L', L); outline('E', E);

  // tilt the whole word into perspective
  letters.rotation.set(0.12, 0.42, 0.0);
  const scale = 2.02 / total; letters.scale.setScalar(scale);
  letters.position.set(0.03, -0.43 * scale, 0);
  letters.updateMatrixWorld(true);
  toLetter.value.copy(letters.matrixWorld).invert(); yLine.value = levelY;

  // ---------- the cyan liquidity level ----------
  // a solid laser bar near the break, dashed toward the edges, all lying in the tilted letter plane
  const lvlGroup = new THREE.Group(); letters.add(lvlGroup);
  const barMat = new THREE.MeshBasicMaterial({ color: col(THREE, C.cyan, 2.2) });
  const bar = (x0, x1, r) => { const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, x1 - x0, 12), barMat); m.rotation.z = Math.PI / 2; m.position.set((x0 + x1) / 2, levelY, 0.0); lvlGroup.add(m); };
  const xL0 = -total / 2, xL1 = -total / 2 + wL;
  bar(xL0 - 0.35, xL1 + gap + wE + 0.35, 0.015);
  for (let x = xL1 + gap + wE + 0.45; x < 2.3; x += 0.16) bar(x, x + 0.08, 0.01);
  for (let x = xL0 - 0.45; x > -2.3; x -= 0.16) bar(x - 0.08, x, 0.01);
  // flare where the level breaks through the L (inner corner of the foot) and a softer one at the stem
  const fl = flare(THREE, { tint: C.cyan, core: 0xffffff, k: 1.45, scale: 0.75, streak: 2.6 });
  const pf = new THREE.Vector3(xL1 + 0.02, levelY, depth / 2 + 0.02).applyMatrix4(letters.matrixWorld); fl.position.copy(pf); scene.add(fl);
  const g2 = glowSprite(THREE, C.cyan, 0.9, 0.5); g2.position.copy(new THREE.Vector3(xL0 - 0.03, levelY, depth / 2).applyMatrix4(letters.matrixWorld)); scene.add(g2);

  // underglow: soft magenta pool beneath the word
  

  // sparks thrown off where the level breaks through the L
  let seed = 3; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < 16; i++) {
    const a = -0.4 + rnd() * 2.2, d = 0.08 + rnd() * 0.35, sp = glowSprite(THREE, i % 4 ? C.cyan : 0xffffff, 1.6, 0.025 + rnd() * 0.03);
    sp.position.copy(new THREE.Vector3(xL1 + 0.02 + Math.cos(a) * d, levelY + Math.sin(a) * d * 0.6, depth / 2 + 0.05 + rnd() * 0.1).applyMatrix4(letters.matrixWorld)); scene.add(sp);
  }

  // glossy black floor beneath: blurred reflection that fades into the dark
  const box = new THREE.Box3().setFromObject(L); const floorY = box.min.y - 0.05;
  const floor = new Reflector(new THREE.PlaneGeometry(60, 60), { textureWidth: size, textureHeight: size, multisample: 4, shader: {
    uniforms: { color: { value: null }, tDiffuse: { value: null }, textureMatrix: { value: null }, px: { value: 1 / size } },
    vertexShader: 'uniform mat4 textureMatrix; varying vec4 vUv; varying vec3 vW; void main(){ vUv = textureMatrix*vec4(position,1.); vW = (modelMatrix*vec4(position,1.)).xyz; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }',
    fragmentShader: `uniform sampler2D tDiffuse; uniform float px; varying vec4 vUv; varying vec3 vW;
      void main(){ vec2 uv = vUv.xy/vUv.w; vec3 r = vec3(0.);
        for (int i = 0; i < 16; i++) { float a = float(i)*2.39996; float rr = sqrt(float(i)+.5)/4.; r += texture2D(tDiffuse, uv + vec2(cos(a), sin(a))*rr*px*10.).rgb; }
        r /= 16.; float d = length(vW.xz - vec2(0., 0.)); float fade = exp(-d*d*0.035);
        float near = smoothstep(3.2, 0.2, vW.z);
        vec2 g = abs(fract(vW.xz*2.2 + .5) - .5)/fwidth(vW.xz*2.2); float ln = 1. - min(min(g.x, g.y), 1.);
        vec3 grid = vec3(0.55,0.24,1.0)*ln*0.5*exp(-d*d*0.09);
        gl_FragColor = vec4(r*0.55*near + grid + vec3(0.004,0.001,0.009), fade); }`,
  } });
  floor.material.transparent = true; floor.material.depthWrite = false; floor.rotation.x = -Math.PI / 2; floor.position.y = floorY; scene.add(floor);

  const out = present(THREE, renderer, scene, camera, size, { scale: 2, samples: 4, frames: 1, vignette: 0.5, ca: 0.3 });
  return { ...out, bloom: { strength: 0.6, radius: 0.4, threshold: 0.9 } };
};
