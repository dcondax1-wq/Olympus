// Architectural scenery: stepped crowns and a civic orbital promenade, never data.
import * as THREE from '../jarvis/three.module.min.js';

export function skylinePorts(towers, extent) {
  const group = new THREE.Group(), selected = towers.map((s, i) => ({ ...s, index: i })).filter((s) => s.seed > 0.94);
  const crowns = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial({ color: '#7696bb', metalness: 0.7, roughness: 0.25, emissive: '#17314f', emissiveIntensity: 0.5 }), selected.length * 3);
  const mat = new THREE.Matrix4(), q = new THREE.Quaternion(), up = new THREE.Vector3(0, 1, 0);
  selected.forEach((s, i) => {
    q.setFromAxisAngle(up, s.yaw);
    for (let tier = 0; tier < 3; tier++) {
      const width = 0.88 - tier * 0.22;
      mat.compose(new THREE.Vector3(s.x, s.h + 1.5 + tier * 3, s.z), q, new THREE.Vector3(s.w * width, 3, s.d * width));
      crowns.setMatrixAt(i * 3 + tier, mat);
      crowns.setColorAt(i * 3 + tier, new THREE.Color(tier === 2 ? '#ffce74' : '#8cabbf'));
    }
  });
  crowns.frustumCulled = false; group.add(crowns);
  const path = [], rad = extent + 36;
  for (let i = 0; i < 160; i++) {
    const a = i / 160 * Math.PI * 2, b = (i + 1) / 160 * Math.PI * 2;
    for (const r of [rad - 1.5, rad + 1.5]) path.push(Math.cos(a) * r, 7, Math.sin(a) * r, Math.cos(b) * r, 7, Math.sin(b) * r);
    if (i % 5 === 0) path.push(Math.cos(a) * rad, 0.1, Math.sin(a) * rad, Math.cos(a) * rad, 7, Math.sin(a) * rad);
  }
  const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.Float32BufferAttribute(path, 3));
  const rail = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: '#304862', transparent: true, opacity: 0.12 })); group.add(rail);
  return { group, setTier(count) { crowns.count = selected.filter((s) => s.index < count).length * 3; rail.visible = count > 250; } };
}
