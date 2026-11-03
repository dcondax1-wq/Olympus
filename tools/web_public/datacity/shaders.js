// GLSL of the Data City (three.js ShaderMaterial: three adds the attribute / uniform preamble and maps gl_FragColor).
//   BUILD_*   every building in one InstancedMesh: procedural lit windows (aData.y = share lit), roof glow, a pulse for
//             rising ones (aData.z), dimming for search (aData.w), fog; uMirror = 1 draws the wet-street reflection
//   GLOW_*    additive point sprites (bloom-like) on gold / green roofs, monuments, strategy towers and beacons
//   FLOW_*    trades flowing along the streets (each point moves along its segment in the vertex shader)
//   GROUND_*  the see-through ground with its grid and the plaza glow;  SKY_*  the day / night dome;  TOWER_*  LIT's tower
export const BUILD_VS = `
attribute vec3 aColor; attribute vec4 aData; attribute float aSeed;
uniform float uMirror;
varying vec3 vColor; varying vec4 vData; varying vec3 vLocal; varying vec3 vN; varying float vFD; varying float vWy; varying float vSeed;
void main(){
  vColor=aColor; vData=aData; vLocal=position; vSeed=aSeed;
  vec4 wp = modelMatrix * instanceMatrix * vec4(position,1.0);
  if(uMirror>0.5) wp.y = -wp.y;
  vWy = wp.y;
  vN = normalize(mat3(modelMatrix*instanceMatrix)*normal);
  vec4 mv = viewMatrix*wp; vFD = -mv.z; gl_Position = projectionMatrix*mv;
}`;
export const BUILD_FS = `
uniform float uTime; uniform vec3 uFog; uniform float uFogD; uniform float uMirror; uniform float uDay;
varying vec3 vColor; varying vec4 vData; varying vec3 vLocal; varying vec3 vN; varying float vFD; varying float vWy; varying float vSeed;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)) + vSeed*17.0)*43758.5453); }
void main(){
  vec3 n = abs(vN);
  float side = 1.0 - step(0.5, n.y);
  vec2 uv = n.x > 0.5 ? vec2(vLocal.z, vLocal.y) : vec2(vLocal.x, vLocal.y);
  vec2 g = vec2((uv.x + 0.5) * 3.0, uv.y * vData.x * 1.7);
  vec2 cell = floor(g); vec2 f = fract(g);
  float win = step(0.22,f.x)*step(f.x,0.78)*step(0.28,f.y)*step(f.y,0.72);
  float lit = step(hash(cell + n.xz*3.1), vData.y);
  float diff = 0.30 + 0.55*max(dot(normalize(vN), normalize(vec3(0.45,0.8,0.25))), 0.0);
  vec3 body = mix(vColor*0.16, vColor*0.55, uDay) * diff;
  vec3 warm = mix(vec3(1.0,0.86,0.58), vColor, 0.35);
  vec3 col = body + side*win*lit*warm*mix(1.25, 0.35, uDay);
  col += vColor * (1.0 - side) * 0.55;                                   // glowing roof
  col += vColor * smoothstep(0.93, 1.0, vLocal.y) * side * 0.9;          // roof edge
  col += vColor * vData.z * (0.5 + 0.5*sin(uTime*3.2 + vSeed*6.0)) * 0.45;
  col *= mix(1.0, 0.13, vData.w);
  float fog = 1.0 - exp(-uFogD*uFogD*vFD*vFD);
  col = mix(col, uFog, fog);
  float a = 1.0;
  if(uMirror>0.5) a = 0.26 * (1.0 - smoothstep(0.0, 7.0, -vWy)) * (1.0 - fog);
  gl_FragColor = vec4(col, a);
}`;
export const GLOW_VS = `
attribute vec3 aColor; attribute float aSize; attribute float aPulse; attribute float aSeed;
uniform float uTime; uniform float uPR;
varying vec3 vColor; varying float vA;
void main(){
  vColor = aColor;
  float p = aPulse > 0.5 ? 0.55 + 0.45*sin(uTime*3.2 + aSeed*6.0) : 1.0;
  vA = p;
  vec4 mv = modelViewMatrix * vec4(position,1.0);
  gl_PointSize = aSize * p * uPR * (300.0 / max(1.0, -mv.z));
  gl_Position = projectionMatrix * mv;
}`;
export const GLOW_FS = `
uniform float uDay; varying vec3 vColor; varying float vA;
void main(){
  vec2 d = gl_PointCoord - 0.5; float r = length(d);
  float a = exp(-r*r*14.0) + 0.35*exp(-r*r*60.0);
  gl_FragColor = vec4(vColor * a * vA * mix(1.0, 0.45, uDay), 1.0);
}`;
export const FLOW_VS = `
attribute vec4 aSeg; attribute vec3 aColor; attribute vec2 aMove;
uniform float uTime; uniform float uPR;
varying vec3 vColor;
void main(){
  vColor = aColor;
  float t = fract(uTime * aMove.x + aMove.y);
  vec3 p = vec3(mix(aSeg.x, aSeg.z, t), 0.22, mix(aSeg.y, aSeg.w, t));
  vec4 mv = modelViewMatrix * vec4(p,1.0);
  gl_PointSize = 3.2 * uPR * (60.0 / max(1.0, -mv.z));
  gl_Position = projectionMatrix * mv;
}`;
export const FLOW_FS = `
varying vec3 vColor; uniform float uDay;
void main(){ vec2 d = gl_PointCoord-0.5; float a = exp(-dot(d,d)*18.0); gl_FragColor = vec4(vColor*a*mix(1.0,0.5,uDay),1.0); }`;
export const GROUND_VS = `varying vec3 vW; varying float vFD;
void main(){ vec4 wp = modelMatrix*vec4(position,1.0); vW = wp.xyz; vec4 mv = viewMatrix*wp; vFD = -mv.z; gl_Position = projectionMatrix*mv; }`;
export const GROUND_FS = `
uniform vec3 uFog; uniform float uFogD; uniform float uDay; uniform float uTime;
varying vec3 vW; varying float vFD;
void main(){
  vec2 p = vW.xz / 2.5;
  vec2 g = abs(fract(p - 0.5) - 0.5) / fwidth(p);
  float line = 1.0 - min(min(g.x, g.y), 1.0);
  vec3 base = mix(vec3(0.012,0.016,0.04), vec3(0.42,0.47,0.55), uDay);
  vec3 col = base + line * mix(vec3(0.03,0.12,0.24), vec3(0.08,0.1,0.13), uDay) * 0.6;
  float r = length(vW.xz);
  col += mix(vec3(0.0,0.45,0.75), vec3(0.15,0.2,0.25), uDay) * 0.32 * exp(-r*0.055);
  col += vec3(0.0,0.5,0.8) * 0.18 * smoothstep(0.6, 0.0, abs(r - 15.0)) * (0.6 + 0.4*sin(uTime*1.5));
  float fog = 1.0 - exp(-uFogD*uFogD*vFD*vFD);
  gl_FragColor = vec4(mix(col, uFog, fog), 0.80);
}`;
export const SKY_VS = `varying vec3 vP; void main(){ vP = position; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }`;
export const SKY_FS = `
uniform float uDay; varying vec3 vP;
void main(){
  float h = normalize(vP).y;
  vec3 nTop = vec3(0.005,0.008,0.03), nHor = vec3(0.06,0.05,0.16), nGlow = vec3(0.35,0.12,0.45);
  vec3 dTop = vec3(0.22,0.45,0.85), dHor = vec3(0.72,0.84,0.96), dGlow = vec3(1.0,0.85,0.7);
  vec3 top = mix(nTop, dTop, uDay), hor = mix(nHor, dHor, uDay), glow = mix(nGlow, dGlow, uDay);
  vec3 c = mix(hor, top, smoothstep(0.0, 0.55, h));
  c += glow * 0.35 * exp(-abs(h)*9.0);
  gl_FragColor = vec4(c, 1.0);
}`;
export const TOWER_FS = `
uniform float uTime; uniform float uDay; varying vec3 vL;
void main(){
  float band = smoothstep(0.92, 1.0, fract(vL.y*0.55 - uTime*0.35));
  float rib = smoothstep(0.85, 1.0, abs(sin(atan(vL.z, vL.x)*4.0)));
  vec3 c = vec3(0.02,0.07,0.12) + vec3(0.25,0.85,1.0)*(band*0.9 + rib*0.35) + vec3(0.25,0.85,1.0)*0.12;
  c = mix(c, c*0.6 + vec3(0.1,0.2,0.3), uDay);
  gl_FragColor = vec4(c, 1.0);
}`;
export const TOWER_VS = `varying vec3 vL; void main(){ vL = position; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }`;
