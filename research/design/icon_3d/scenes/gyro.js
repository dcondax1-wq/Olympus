// "Gyro Reactor": chrome gimbal washers with inlaid neon arcs around a chrome-caged
// energy-cell candlestick whose lower wick pierces a holographic cyan liquidity disc.
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { C, col, makeEnv, backdrop, flare, glowSprite, present } from './_common.js';

export default async ({ THREE, renderer, size }) => {
  const scene = new THREE.Scene();
  scene.environment = makeEnv(THREE, renderer, {
    top: 0x0e0520, horizon: 0x0a0316, bottom: 0x010003,
    panels: [
      { c: 0xf4ecff, i: 1.6, w: 8, h: 2.2, pos: [0, 7, 1] },          // big soft top box
      { c: 0xffffff, i: 3.0, w: 6, h: 0.25, pos: [0, 6.5, 3] },       // hot top strip (glints)
      { c: C.magenta, i: 1.7, w: 1.6, h: 9, pos: [-7, 1, 1.5] },      // left magenta box
      { c: 0xffffff, i: 1.6, w: 0.4, h: 6, pos: [-4.5, 4, 4.5], rz: 0.7 },  // white key strip top-left
      { c: C.violet, i: 2.0, w: 1.6, h: 9, pos: [7, 0.5, 0.5] },      // right violet box
      { c: C.cyan, i: 1.2, w: 7, h: 0.6, pos: [0, -6, 2.5] },         // cyan kicker from below
      { c: 0xffe6fb, i: 1.4, w: 3.5, h: 0.5, pos: [2.5, 2.5, 7] },    // front catch light
      { c: C.purple, i: 0.9, w: 12, h: 3, pos: [0, 1, -8] },          // back wash
      { c: 0xf2dcff, i: 0.9, w: 4, h: 1.2, pos: [0, 6, -4] },         // overhead-back box: lights top faces
      { c: 0xffffff, i: 2.4, w: 0.18, h: 6, pos: [-3, 0.5, 7], rz: 0.6 },   // diagonal streaks behind camera
      { c: C.hotpink, i: 2.0, w: 0.25, h: 6, pos: [3.5, -1, 7], rz: -0.5 },
      { c: C.violet, i: 1.6, w: 0.5, h: 7, pos: [0.5, 0, 8], rz: 0.15 },
    ],
  });
  scene.add(backdrop(THREE, { inner: 0x4a1080, outer: 0x010004, center: [0.5, 0.52], radius: 0.7, k: 0.22, glow: { c: 0x7c3aed, i: 0.12, pos: [0.5, 0.56], size: [0.16, 0.26] } }));

  const camera = new THREE.PerspectiveCamera(25, 1, 0.1, 100);
  camera.position.set(0, 2.3, 9.7); camera.lookAt(0.03, 0.12, 0);

  const chrome = new THREE.MeshPhysicalMaterial({ color: 0xeeeaf8, metalness: 1, roughness: 0.1, envMapIntensity: 1.35, clearcoat: 0.5, clearcoatRoughness: 0.04 });
  const satin = new THREE.MeshPhysicalMaterial({ color: 0xb8b0d0, metalness: 1, roughness: 0.28, envMapIntensity: 1.0 });
  const neon = (hex, k) => new THREE.MeshBasicMaterial({ color: col(THREE, hex, k), toneMapped: false, side: THREE.DoubleSide });

  // ---------- candlestick: chrome cage around a magenta energy core ----------
  const candle = new THREE.Group(); candle.rotation.y = 0.62; candle.scale.setScalar(1.18); candle.position.y = 0.05; scene.add(candle);
  const bodyY = 0.27, bodyH = 1.12, bw = 0.42;
  const core = new THREE.Mesh(new RoundedBoxGeometry(bw * 0.6, bodyH - 0.1, bw * 0.6, 4, 0.05), new THREE.ShaderMaterial({
    uniforms: { a: { value: col(THREE, C.magenta, 2.0) }, b: { value: col(THREE, 0xff86ea, 2.4) }, d: { value: col(THREE, 0xe01cc0, 1.5) } },
    vertexShader: 'varying vec3 vP; varying vec3 vN; varying vec3 vV; void main(){ vP = position; vN = normalize(normalMatrix*normal); vec4 mv = modelViewMatrix*vec4(position,1.); vV = normalize(-mv.xyz); gl_Position = projectionMatrix*mv; }',
    fragmentShader: `uniform vec3 a, b, d; varying vec3 vP; varying vec3 vN; varying vec3 vV;
      void main(){ float f = 1.-abs(dot(vN, vV));
        float bands = 1.;
        float ring = exp(-pow((fract(vP.y*2.6+.3)-.5)/0.03, 2.)); bands += ring*0.5;
        float vg = 0.7 + 0.45*smoothstep(-0.5, 0.5, vP.y);
        vec3 c = mix(d, a, smoothstep(0.0, 0.7, f)); c = mix(c, b, smoothstep(0.7, 1., f));
        float hw = 0.126, inner = 0.7 + 0.55*pow(1.-clamp(min(abs(vP.x), abs(vP.z))/hw, 0., 1.), 1.4);
        gl_FragColor = vec4(c*bands*vg*inner, 1.); }`,
  }));
  core.position.y = bodyY; candle.add(core);
  const shell = new THREE.Mesh(new RoundedBoxGeometry(bw, bodyH, bw, 5, 0.075), new THREE.MeshPhysicalMaterial({
    color: 0xffffff, metalness: 0, roughness: 0.06, transmission: 1, thickness: 0.6, ior: 1.5,
    attenuationColor: new THREE.Color(0xff9cf0), attenuationDistance: 0.8, envMapIntensity: 1.4, clearcoat: 1, clearcoatRoughness: 0.03,
  }));
  shell.position.y = bodyY; candle.add(shell);
  const halo = glowSprite(THREE, C.magenta, 0.45, 2.2, 2.6); halo.position.set(0, bodyY, -0.5); candle.add(halo);
  for (const s of [-1, 1]) {
    const cap = new THREE.Mesh(new RoundedBoxGeometry(bw + 0.07, 0.09, bw + 0.07, 4, 0.04), chrome);
    cap.position.y = bodyY + s * (bodyH / 2 + 0.04); candle.add(cap);
    const collar = new THREE.Mesh(new THREE.CylinderGeometry(0.085, 0.11, 0.07, 32), satin);
    collar.position.y = bodyY + s * (bodyH / 2 + 0.12); candle.add(collar);
    const band = new THREE.Mesh(new THREE.TorusGeometry(0.1, 0.01, 8, 40), neon(C.hotpink, 2.0));
    band.rotation.x = Math.PI / 2; band.position.y = bodyY + s * (bodyH / 2 + 0.12); candle.add(band);
  }
  const topY = bodyY + bodyH / 2 + 0.15, botY = bodyY - bodyH / 2 - 0.15;
  const wick = (y0, y1, r, m = chrome) => { const w = new THREE.Mesh(new THREE.CylinderGeometry(r, r, Math.abs(y1 - y0), 32), m); w.position.y = (y0 + y1) / 2; candle.add(w); return w; };
  wick(topY, topY + 0.3, 0.052);
  const tipTop = new THREE.Mesh(new THREE.SphereGeometry(0.05, 24, 16), chrome); tipTop.position.y = topY + 0.3; candle.add(tipTop);
  const discY = -0.86, lowY = -1.24;
  wick(botY, discY, 0.052);
  wick(discY, lowY, 0.036, neon(C.cyan, 2.2));            // below the pool the wick runs hot: the sweep
  const tipLow = new THREE.Mesh(new THREE.SphereGeometry(0.038, 24, 16), neon(C.ice, 2.0)); tipLow.position.y = lowY; candle.add(tipLow);
  const coreLight = new THREE.PointLight(C.magenta, 2, 5, 2); coreLight.position.set(0, bodyY, -0.6); // scene.add(coreLight);

  // ---------- liquidity disc ----------
  const disc = new THREE.Mesh(new THREE.CircleGeometry(1, 128), new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    uniforms: { c: { value: col(THREE, C.cyan, 1) } },
    vertexShader: 'varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }',
    fragmentShader: `uniform vec3 c; varying vec2 vP;
      float ln(float d, float w){ float fw = fwidth(d)*1.2; return 1.-smoothstep(w, w+fw, abs(d)); }
      void main(){ float r = length(vP), a = atan(vP.y, vP.x);
        float rings = ln((fract(r*10.+.5)-.5)/10., 0.002)*0.45;
        float spokes = ln((fract(a/6.2831*48.+.5)-.5)*6.2831/48.*r, 0.0015)*0.22*smoothstep(0.2,0.5,r);
        float dash = step(0.5, fract(a/6.2831*72.))*exp(-pow((r-0.9)/0.008, 2.))*1.2;
        float rim = exp(-pow((r-0.985)/0.01, 2.))*2.4;
        float shock = exp(-pow((r-0.16)/0.015,2.))*1.6 + exp(-pow((r-0.3)/0.025,2.))*0.8 + exp(-pow((r-0.5)/0.04,2.))*0.35;
        float fill = 0.06 + 0.2*smoothstep(0.5, 1., r);
        float v = (rings + spokes + dash + rim + shock + fill)*smoothstep(1.01, 0.995, r);
        gl_FragColor = vec4(c*v, 1.); }`,
  }));
  const discW = candle.position.y + discY * candle.scale.y; disc.rotation.x = -Math.PI / 2; disc.position.y = discW; disc.scale.setScalar(1.22); scene.add(disc);
  const pierce = flare(THREE, { tint: C.cyan, core: 0xffffff, k: 1.3, scale: 0.8, streak: 1.9 });
  pierce.position.set(0, discW, 0.05); scene.add(pierce);
  const cyanLight = new THREE.PointLight(C.cyan, 4, 4, 2); cyanLight.position.set(0, discY + 0.1, 0.4); // scene.add(cyanLight);

  // ---------- gimbal: beveled chrome washers with inlaid neon arcs ----------
  const gimbal = new THREE.Group(); gimbal.position.y = 0.12; scene.add(gimbal);
  const washer = (R, w, rot, arcs, ticks = 0) => {
    const g = new THREE.Group(); g.rotation.set(...rot, 'YXZ'); gimbal.add(g);
    const bs = w * 0.36, ws = w - 2 * bs;
    const sh = new THREE.Shape(); sh.absarc(0, 0, R + ws / 2, 0, Math.PI * 2, false);
    const hole = new THREE.Path(); hole.absarc(0, 0, R - ws / 2, 0, Math.PI * 2, true); sh.holes.push(hole);
    const depth = 0.012, bev = w * 0.24;
    const geo = new THREE.ExtrudeGeometry(sh, { depth, bevelEnabled: true, bevelThickness: bev, bevelSize: bs, bevelSegments: 7, curveSegments: 160 });
    geo.translate(0, 0, -depth / 2);
    g.add(new THREE.Mesh(geo, chrome));
    const zf = depth / 2 + bev + 0.002;
    for (const [a0, len, hex, k] of arcs) for (const z of [zf, -zf]) {
      // comet arc: dim tail -> hot white-tinted head, reads as spin
      const m = new THREE.Mesh(new THREE.RingGeometry(R - w * 0.1, R + w * 0.1, Math.max(24, Math.round(len * 60)), 1, a0, len), new THREE.ShaderMaterial({
        side: THREE.DoubleSide, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
        uniforms: { c: { value: col(THREE, hex, k) }, a0: { value: a0 }, len: { value: len }, R: { value: R }, hw: { value: w * 0.1 } },
        vertexShader: 'varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }',
        fragmentShader: `uniform vec3 c; uniform float a0, len, R, hw; varying vec2 vP;
          void main(){ float a = atan(vP.y, vP.x); float t = mod(a - a0 + 12.566, 6.2831)/len; t = clamp(t, 0., 1.);
            float across = 1. - pow(abs(length(vP) - R)/hw, 2.);
            float head = smoothstep(1., 0.95, t); float v = (0.06 + 0.94*pow(t, 2.2))*head*clamp(across*1.4, 0., 1.);
            vec3 col = c*v*1.15 + vec3(1.)*pow(t, 18.)*head*1.6*clamp(across, 0., 1.);
            gl_FragColor = vec4(col, 1.); }`,
      }));
      m.position.z = z; g.add(m);
    }
    if (ticks) {
      const im = new THREE.InstancedMesh(new THREE.PlaneGeometry(0.009, w * 0.3), neon(C.violet, 1.0), ticks), o = new THREE.Object3D();
      for (let i = 0; i < ticks; i++) { const a = i / ticks * Math.PI * 2, rr = R + w * 0.72; o.position.set(Math.cos(a) * rr, Math.sin(a) * rr, 0); o.rotation.set(0, 0, a - Math.PI / 2); o.updateMatrix(); im.setMatrixAt(i, o.matrix); }
      g.add(im);
    }
    for (const s of [-1, 1]) { // pivot bearings
      const k = new THREE.Mesh(new THREE.CylinderGeometry(w * 0.32, w * 0.32, depth + 0.12, 32), satin);
      k.position.set(s * R, 0, 0); k.rotation.x = Math.PI / 2; g.add(k);
      const d = new THREE.Mesh(new THREE.CircleGeometry(w * 0.14, 24), neon(C.hotpink, 1.8)); d.position.set(s * R, 0, depth / 2 + 0.065); g.add(d);
    }
    return g;
  };
  // two meridian washers (never cross the candle) + one tilted equator that dips under the body
  washer(1.46, 0.2, [0.1, 0.72, 0.08], [[0.25, 1.9, C.magenta, 1.9], [3.3, 1.9, C.magenta, 1.9], [5.55, 0.22, C.cyan, 1.6]], 120);
  washer(1.27, 0.165, [-0.12, -0.78, -0.06], [[0.6, 1.7, C.violet, 2.3], [3.6, 1.9, C.violet, 2.3]]);
  washer(1.07, 0.14, [-(Math.PI / 2 - 0.42), 0.0, 0.18], [[0.4, 2.0, C.hotpink, 1.9], [3.7, 1.9, C.hotpink, 1.9]]);

  const out = present(THREE, renderer, scene, camera, size, { scale: 2, samples: 4, frames: 2, vignette: 0.5, ca: 0.5 });
  return { ...out, bloom: { strength: 0.75, radius: 0.42, threshold: 0.88 } };
};
