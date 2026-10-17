// Liquidity Engine app icon, concept "Ribbon" (reversal ribbon). One thick glossy neon tube traces the trade: it dives, pierces the cyan liquidity line
// (the sweep), and rockets back up to the target. Magenta -> violet -> cyan along its length.
import { backdrop, glowSprite, present, col, flare } from './_common.js';
export default async ({ THREE, renderer, size, q }) => {
  const P = (k, d) => +(q.get(k) ?? d);
  const scene = new THREE.Scene();
  scene.add(backdrop(THREE, { inner: 0x2a0a58, outer: 0x040109, center: [0.5, 0.5], radius: 0.8, k: 0.9 }));
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -10, 10); camera.position.z = 5;
  const ly = P('ly', -0.3);
  const pts = [[-0.74, 0.66, -0.1], [-0.5, 0.22, 0], [-0.3, -0.26, 0.05], [-0.2, -0.52, 0.08], [-0.1, -0.3, 0.06], [0.14, 0.06, 0.03], [0.42, 0.38, 0], [0.7, 0.68, -0.08]]
    .map(p => new THREE.Vector3(...p));
  const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal');
  const R = P('r', 0.075), seg = 400;
  const geo = new THREE.TubeGeometry(curve, seg, R, 48, false);
  // per-vertex colour + taper along u (tube vertices are laid out ring by ring)
  const n = geo.attributes.position.count, rings = seg + 1, per = n / rings;
  const cA = new THREE.Color(0xff2bd6), cB = new THREE.Color(0x8b5cf6), cC = new THREE.Color(0x22d3ee);
  const colors = new Float32Array(n * 3), us = new Float32Array(n);
  for (let i = 0; i < n; i++) { const u = Math.floor(i / per) / seg; us[i] = u;
    const c = u < 0.5 ? cA.clone().lerp(cB, u / 0.5) : cB.clone().lerp(cC, (u - 0.5) / 0.5); colors.set([c.r, c.g, c.b], i * 3); }
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3)); geo.setAttribute('u', new THREE.BufferAttribute(us, 1));
  const mat = new THREE.ShaderMaterial({ vertexColors: true, transparent: true,
    uniforms: { L: { value: new THREE.Vector3(-0.5, 0.7, 0.6).normalize() } },
    vertexShader: `attribute float u; varying float vU; varying vec3 vC; varying vec3 vN; varying vec3 vV;
      void main(){ vU = u; vC = color; vec4 w = modelViewMatrix*vec4(position,1.); vN = normalize(normalMatrix*normal); vV = normalize(-w.xyz); gl_Position = projectionMatrix*w; }`,
    fragmentShader: `uniform vec3 L; varying float vU; varying vec3 vC; varying vec3 vN; varying vec3 vV;
      void main(){ vec3 n = normalize(vN), v = vec3(0.,0.,1.); float nv = max(dot(n,v),0.);
        vec3 c = vC*(0.42+0.5*nv);                       // saturated body, brighter where it faces us
        c += mix(vC, vec3(1.), 0.3)*pow(nv, 16.)*0.45;    // hot core line
        float s = pow(max(dot(reflect(-L,n), v),0.), 48.); c += vec3(1.)*s*1.1;   // glossy highlight
        c += vC*pow(1.-nv, 3.)*0.35;                      // rim
        float a = smoothstep(0.0, 0.16, vU);              // tail fades in
        gl_FragColor = vec4(c*a, a); }` });
  const tube = new THREE.Mesh(geo, mat); scene.add(tube);
  // halo sleeve
  const halo = new THREE.Mesh(new THREE.TubeGeometry(curve, seg, R * 2.4, 16, false), new THREE.ShaderMaterial({ vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: 'attribute float u; varying float vU; varying vec3 vC; varying vec3 vN; void main(){ vU=u; vC=color; vN=normalize(normalMatrix*normal); gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }',
    fragmentShader: 'varying float vU; varying vec3 vC; varying vec3 vN; void main(){ float nv = max(dot(normalize(vN), vec3(0.,0.,1.)),0.); gl_FragColor = vec4(vC*pow(nv,2.)*0.2*smoothstep(0.,0.2,vU)*(1.-smoothstep(0.9,1.,vU)), 1.); }' }));
  // per-vertex colours for the halo sleeve (its own vertex layout)
  { const g2 = halo.geometry, n2 = g2.attributes.position.count, per2 = n2 / rings, c2 = new Float32Array(n2 * 3), u2 = new Float32Array(n2);
    for (let i = 0; i < n2; i++) { const u = Math.floor(i / per2) / seg; u2[i] = u; const c = u < 0.5 ? cA.clone().lerp(cB, u / 0.5) : cB.clone().lerp(cC, (u - 0.5) / 0.5); c2.set([c.r, c.g, c.b], i * 3); }
    g2.setAttribute('color', new THREE.BufferAttribute(c2, 3)); g2.setAttribute('u', new THREE.BufferAttribute(u2, 1)); }
  halo.position.z = -0.3; scene.add(halo);
  // end cap glow (target)
  const end = curve.getPoint(1); const f2 = flare(THREE, { tint: 0x22d3ee, k: 0.6, scale: 0.36, streak: 0 }); f2.position.set(end.x, end.y, 1); scene.add(f2);
  // liquidity line + pierce flare
  const line = (w, k, hex) => { const m = new THREE.Mesh(new THREE.PlaneGeometry(2.2, w), new THREE.MeshBasicMaterial({ color: col(THREE, hex, k), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })); m.position.set(0, ly, -0.5); scene.add(m); };
  line(0.014, 1.5, 0xd9fbff); line(0.04, 0.45, 0x22d3ee); line(0.12, 0.1, 0x22d3ee);
  const f = flare(THREE, { tint: 0x22d3ee, k: 0.5, scale: 0.42, streak: 0.6 }); f.position.set(-0.27, ly, 1); scene.add(f);
  const out = present(THREE, renderer, scene, camera, size, { scale: 2, samples: 4, vignette: 0.35, grain: 0.006, ca: 0.1 });
  return { ...out, bloom: { strength: 0.55, radius: 0.4, threshold: 0.85 } };
};
