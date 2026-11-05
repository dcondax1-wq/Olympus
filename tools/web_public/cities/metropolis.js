// Civic scenery surrounds the measured city. These towers and roads are scenery,
// never additional trades, data rows or financial results. Three batched draws.
import * as THREE from '../jarvis/three.module.min.js';
import { hash32, rng, rgb } from './util.js';

export const METROPOLIS_CAPS = { ultra: 1800, high: 1200, low: 200, off: 0 };

export function metropolisPlan(city, spec, cap = METROPOLIS_CAPS.ultra) {
  const random = rng(hash32('civic:' + spec.id)), b = city.bounds, r = Math.max(40, b.r), out = [];
  // Fill unused blocks near the measured centre first. A spatial index keeps
  // the decorative low rises clear of every data tower, even in a 40k-row city.
  const cell = Math.max(6.5, city.pitch * .68), bucketSize = Math.max(18, cell * 3);
  const buckets = new Map(), key = (ix, iz) => `${ix}:${iz}`;
  for (let k = 0; k < city.n; k++) {
    const ix = Math.floor(city.x[k] / bucketSize), iz = Math.floor(city.z[k] / bucketSize), id = key(ix, iz);
    if (!buckets.has(id)) buckets.set(id, []);
    buckets.get(id).push(k);
  }
  const clear = (x, z, w, d) => {
    const ix = Math.floor(x / bucketSize), iz = Math.floor(z / bucketSize);
    for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) {
      for (const k of buckets.get(key(ix + dx, iz + dz)) || []) {
        if (Math.abs(x - city.x[k]) < (w + city.w[k]) / 2 + 1.5 &&
            Math.abs(z - city.z[k]) < (d + city.d[k]) / 2 + 1.5) return false;
      }
    }
    return true;
  };
  const pad = city.pitch * 3 + 30;
  const sceneryBlocked = (x, z) => (spec.scenery === 'river' && x > b.maxx + pad - 8) ||
    (spec.scenery === 'harbor' && z < b.minz - pad + 12) ||
    (spec.scenery === 'rail' && Math.abs(z - (b.minz - pad - 12)) < 12);
  const infillTarget = Math.round(cap * .55);
  const addBlock = (ix, iz) => {
    if (out.length >= infillTarget) return;
    const x = (ix + (random() - .5) * .16) * cell, z = (iz + (random() - .5) * .16) * cell;
    if (x < b.minx - 9 * cell || x > b.maxx + 9 * cell || z < b.minz - 9 * cell || z > b.maxz + 9 * cell || sceneryBlocked(x, z)) return;
    const w = cell * (.34 + random() * .15), d = cell * (.34 + random() * .15);
    if (!clear(x, z, w, d)) return;
    out.push({ x, z, w, d, h: 3 + random() * 7 + (random() > .94 ? 5 : 0), seed: random(), infill: true });
  };
  const maxRing = Math.ceil((Math.max(Math.abs(b.minx),Math.abs(b.maxx),Math.abs(b.minz),Math.abs(b.maxz)) + 9 * cell) / cell);
  for (let ring = 0; ring <= maxRing && out.length < infillTarget; ring++) {
    if (!ring) { addBlock(0, 0); continue; }
    for (let i = -ring; i <= ring; i++) { addBlock(i, -ring); addBlock(i, ring); }
    for (let i = -ring + 1; i < ring; i++) { addBlock(-ring, i); addBlock(ring, i); }
  }
  for (let i = 0; out.length < cap && i < cap * 3; i++) {
    const a = i * 2.399963 + random() * .12, distance = r * (1.12 + random() * .64) + 40;
    const x = Math.cos(a) * distance, z = Math.sin(a) * distance;
    if (x > b.minx - 18 && x < b.maxx + 18 && z > b.minz - 18 && z < b.maxz + 18) continue;
    if (sceneryBlocked(x, z)) continue;
    const crown = Math.pow(Math.max(0, Math.cos(a * 5 + .7)), 8), h = 10 + random() * 28 + crown * (30 + city.maxH * .55);
    out.push({ x, z, w: 3 + random() * 4, d: 3 + random() * 4, h, seed: random() });
  }
  return out;
}

export function buildMetropolis(city, spec, box, material, tier = 'high', still = false) {
  const cap = METROPOLIS_CAPS[tier] ?? METROPOLIS_CAPS.high, group = new THREE.Group(); group.name = 'Decorative civic skyline';
  if (!cap) { material.dispose(); return { group, count: 0, calls: 0, triangles: 0, update() {}, dispose() {} }; }
  // Generate one canonical order. Changing tier only takes a shorter prefix.
  const plan = metropolisPlan(city, spec), rows = plan.slice(0, cap), n = rows.length;
  const geometry = new THREE.InstancedBufferGeometry(); geometry.index = box.index;
  geometry.setAttribute('position', box.getAttribute('position')); geometry.setAttribute('normal', box.getAttribute('normal')); geometry.instanceCount = n;
  const ps = new Float32Array(n * 4), hy = new Float32Array(n * 4), color = new Float32Array(n * 3), seed = new Float32Array(n);
  const accent = rgb(spec.palette.accent), amber = rgb('#f89938');
  rows.forEach((b, i) => { ps.set([b.x, b.z, b.w, b.d], i * 4);
    hy.set([b.h, 0, b.infill ? .2 : .12, b.infill ? .76 : .38], i * 4);
    color.set((b.infill ? amber : accent).map((c,j) => c * .82 + (b.infill ? accent[j] : .14) * .18), i * 3); seed[i] = b.seed; });
  const attribute = (name, a, size) => geometry.setAttribute(name, new THREE.InstancedBufferAttribute(a, size));
  attribute('aPosSize', ps, 4); attribute('aHY', hy, 4); attribute('aColor', color, 3); attribute('aSeed', seed, 1);
  attribute('aState', new Float32Array(n * 2), 2); attribute('aBob', new Float32Array(n), 1);
  const towers = new THREE.Mesh(geometry, material); towers.frustumCulled = false; group.add(towers);
  const positions = [], radius = Math.max(50, city.bounds.r), y = .22;
  // Luminous avenues stay beneath the measured buildings; they encode no values.
  const step = Math.max(16, city.pitch * 3), extent = Math.min(radius * 1.25, step * 24);
  for (let p = -extent; p <= extent; p += step) {
    positions.push(-extent, y, p, extent, y, p, p, y, -extent, p, y, extent);
  }
  const roadsGeometry = new THREE.BufferGeometry(); roadsGeometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  const roadsMaterial = new THREE.LineBasicMaterial({ color: spec.palette.accent, transparent: true, opacity: .24, depthWrite: false });
  group.add(new THREE.LineSegments(roadsGeometry, roadsMaterial));
  const flights = !still && ['high', 'ultra'].includes(tier), flightCount = flights ? (tier === 'ultra' ? 96 : 64) : 0;
  const flightGeometry = new THREE.BufferGeometry(), orbit = new Float32Array(flightCount * 4), phase = new Float32Array(flightCount * 3);
  for (let i = 0; i < flightCount; i++) {
    if (i % 3 === 0) orbit.set([radius * (1.15 + i % 4 * .12), i * 2.399963, (i % 2 ? 1 : -1) * (.018 + i % 5 * .003), Math.max(35, city.maxH * .9) + i % 3 * 13], i * 4);
    else orbit.set([extent, Math.round((i % 9 - 4) * Math.min(extent / 5, step) / step) * step, (i % 2 ? 1 : -1) * (12 + i % 5 * 3), i % 2 ? -1 : -2], i * 4);
    phase[i * 3] = i * 37.7;
  }
  flightGeometry.setAttribute('position', new THREE.Float32BufferAttribute(phase, 3));
  flightGeometry.setAttribute('aOrbit', new THREE.Float32BufferAttribute(orbit, 4));
  const clock = { value: 0 }, flightMaterial = new THREE.ShaderMaterial({
    uniforms: { uTime: clock }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: `attribute vec4 aOrbit; uniform float uTime; varying float vRoad; void main(){float a=aOrbit.y+uTime*aOrbit.z;vRoad=step(aOrbit.w,0.);vec3 p=vec3(cos(a)*aOrbit.x,aOrbit.w+sin(a*3.)*3.,sin(a)*aOrbit.x);if(vRoad>.5){float travel=mod(uTime*aOrbit.z+position.x,aOrbit.x*2.)-aOrbit.x;p=aOrbit.w<-1.5?vec3(travel,.7,aOrbit.y):vec3(aOrbit.y,.7,travel);}vec4 mv=modelViewMatrix*vec4(p,1.);gl_Position=projectionMatrix*mv;gl_PointSize=clamp(950./max(1.,-mv.z),2.,5.);}`,
    fragmentShader: `varying float vRoad; void main(){float d=length(gl_PointCoord-.5);gl_FragColor=vec4(mix(vec3(.68,.89,1.),vec3(1.,.78,.4),vRoad),(1.-smoothstep(.1,.5,d))*.85);}`,
  });
  const aircraft = new THREE.Points(flightGeometry, flightMaterial); aircraft.visible = flights; aircraft.frustumCulled = false; group.add(aircraft);
  return { group, count: n, calls: flights ? 3 : 2, triangles: n * (box.index.count / 3),
    update(t) { if (flights) clock.value = t; },
    dispose() { for (const resource of [geometry, material, roadsGeometry, roadsMaterial, flightGeometry, flightMaterial]) resource.dispose(); },
  };
}
