// HERMES effects: the animated background (a WebGL fragment shader, domain-warped noise in each card's palette, drawn at
// a fraction of the screen's pixels and scaled up: smooth gradients, cheap on an iPhone 13) and a 2D particle layer
// (coins, sparks, embers, confetti). One requestAnimationFrame loop; it stops while the page is hidden.
//   const fx = createFx(bgCanvas, particleCanvas, { still })
//   fx.palette(colors, mode)   cross-fade to a card's 3 colours (#rrggbb) and pattern (0 flow, 1 rays, 2 rings, 3 orbs)
//   fx.burst(kind, n, opts)    'coins' | 'sparks' | 'embers' | 'confetti'
//   fx.onFrame(fn)             fn(t seconds) every frame (the card tilt)
//   fx.colors()                the current palette (for the share image)
// still = prefers-reduced-motion: one frame per palette change, no particles, no loop.

const VERT = 'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
const FRAG = `precision mediump float;
uniform vec2 R;uniform float T,K,MA,MB;uniform vec3 A0,A1,A2,B0,B1,B2;
float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float n(vec2 p){vec2 i=floor(p),f=fract(p);vec2 u=f*f*(3.-2.*f);
 return mix(mix(h(i),h(i+vec2(1,0)),u.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),u.x),u.y);}
float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<4;i++){v+=a*n(p);p=p*2.03+vec2(1.7,9.2);a*=.5;}return v;}
float pat(vec2 uv,float m,float t){
 vec2 q=vec2(fbm(uv*1.6+t*.05),fbm(uv*1.6-t*.04+3.1));
 float flow=fbm(uv*1.3+q*1.8+t*.03);
 float r=length(uv),a=atan(uv.y,uv.x);
 float rays=(.5+.5*sin(a*7.+t*.5+q.x*4.))*smoothstep(1.3,.0,r)*.7+flow*.4;
 float rings=.5+.5*sin(r*14.-t*1.4+q.y*3.);rings=mix(rings,flow,.45);
 float orbs=smoothstep(.75,.0,length(uv-vec2(sin(t*.3),cos(t*.23))*.45))+smoothstep(.65,.0,length(uv+vec2(cos(t*.27),sin(t*.31))*.5))*.8+flow*.3;
 float w0=1.-min(abs(m-0.),1.),w1=1.-min(abs(m-1.),1.),w2=1.-min(abs(m-2.),1.),w3=1.-min(abs(m-3.),1.);
 return pow(clamp(flow*w0+rays*w1+rings*w2+orbs*w3,0.,1.),1.45);}
vec3 pal(float v,vec3 c0,vec3 c1,vec3 c2){return v<.5?mix(c0,c1,v*2.):mix(c1,c2,(v-.5)*2.);}
void main(){vec2 uv=(gl_FragCoord.xy-.5*R)/R.y;
 float vb=pat(uv,MB,T),va=K<.999?pat(uv,MA,T):vb;   // the old pattern only while the fade runs
 vec3 c=mix(pal(va,A0,A1,A2),pal(vb,B0,B1,B2),K);
 c*=1.-.35*length(uv*vec2(.9,.7));
 c+=(h(gl_FragCoord.xy+T)-.5)*.025;
 gl_FragColor=vec4(c,1.);}`;

const hex = (s) => { const m = /^#?([0-9a-f]{6})$/i.exec(String(s || '')); const v = m ? parseInt(m[1], 16) : 0; return [(v >> 16 & 255) / 255, (v >> 8 & 255) / 255, (v & 255) / 255]; };
const ease = (x) => 1 - Math.pow(1 - Math.min(1, Math.max(0, x)), 3);

function shader(canvas) {
  let gl = null;
  try { gl = canvas.getContext('webgl', { antialias: false, depth: false, alpha: false, powerPreference: 'low-power', preserveDrawingBuffer: false }); } catch (_) { gl = null; }
  if (!gl) return null;
  const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null; };
  const vs = sh(gl.VERTEX_SHADER, VERT), fs = sh(gl.FRAGMENT_SHADER, FRAG);
  if (!vs || !fs) return null;
  const pr = gl.createProgram();
  gl.attachShader(pr, vs); gl.attachShader(pr, fs); gl.linkProgram(pr);
  if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) return null;
  gl.useProgram(pr);
  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(pr, 'p');
  gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const U = {};
  for (const k of ['R', 'T', 'K', 'MA', 'MB', 'A0', 'A1', 'A2', 'B0', 'B1', 'B2']) U[k] = gl.getUniformLocation(pr, k);
  return {
    draw(w, h, t, k, A, B, ma, mb) {
      gl.viewport(0, 0, w, h);
      gl.uniform2f(U.R, w, h); gl.uniform1f(U.T, t); gl.uniform1f(U.K, k); gl.uniform1f(U.MA, ma); gl.uniform1f(U.MB, mb);
      for (let i = 0; i < 3; i++) { gl.uniform3fv(U['A' + i], A[i]); gl.uniform3fv(U['B' + i], B[i]); }
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    },
  };
}

export function createFx(bg, layer, { still = false } = {}) {
  const S = { from: [[0, 0, 0], [0, 0, 0], [0, 0, 0]], to: [[0, 0, 0], [0, 0, 0], [0, 0, 0]], hexes: ['#12081f', '#3b1a6b', '#f2c14e'],
    ma: 0, mb: 0, k0: 0, parts: [], frames: [], raf: 0, t0: performance.now(), lastW: 0, lastH: 0 };
  const gl = shader(bg);
  const ctx = layer.getContext('2d');
  const BG_SCALE = 0.42;                                     // shader pixels per CSS pixel: soft gradients, ~1/20 of the work

  function size() {
    const w = Math.max(1, innerWidth), h = Math.max(1, innerHeight);
    if (w === S.lastW && h === S.lastH) return;
    S.lastW = w; S.lastH = h;
    bg.width = Math.round(w * BG_SCALE); bg.height = Math.round(h * BG_SCALE);
    const d = window.OLYMPUS ? window.OLYMPUS.dpr() : Math.min(2, devicePixelRatio || 1);   // <= 2, <= 1.5 on LITE
    layer.width = Math.round(w * d); layer.height = Math.round(h * d);
    ctx.setTransform(d, 0, 0, d, 0, 0);
  }

  function cssFallback(k) {                                 // no WebGL: the same palette as a CSS gradient
    const c = S.hexes;
    bg.style.background = `radial-gradient(120% 80% at 20% 15%, ${c[1]} 0%, transparent 60%), radial-gradient(90% 70% at 85% 80%, ${c[2]}55 0%, transparent 65%), ${c[0]}`;
    bg.style.opacity = String(0.85 + 0.15 * k);
  }

  function particles(dt) {
    const w = S.lastW, h = S.lastH;
    ctx.clearRect(0, 0, w, h);
    const P = S.parts;
    for (let i = P.length - 1; i >= 0; i--) {
      const p = P[i];
      p.life += dt;
      if (p.life > p.max) { P.splice(i, 1); continue; }
      p.vy += p.g * dt; p.vx *= 0.995; p.x += p.vx * dt; p.y += p.vy * dt; p.rot += p.vr * dt;
      const a = Math.min(1, (p.max - p.life) / 0.6) * Math.min(1, p.life / 0.12);
      ctx.globalAlpha = a;
      if (p.kind === 'coins') {
        const sx = Math.abs(Math.cos(p.rot)) * p.s;
        ctx.fillStyle = '#f7c948'; ctx.beginPath(); ctx.ellipse(p.x, p.y, Math.max(0.6, sx), p.s, 0, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#fff3c4'; ctx.beginPath(); ctx.ellipse(p.x - sx * 0.3, p.y - p.s * 0.3, Math.max(0.3, sx * 0.35), p.s * 0.35, 0, 0, Math.PI * 2); ctx.fill();
      } else if (p.kind === 'confetti') {
        ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot); ctx.fillStyle = p.c; ctx.fillRect(-p.s, -p.s * 0.4, p.s * 2, p.s * 0.8); ctx.restore();
      } else {
        ctx.fillStyle = p.c; ctx.beginPath(); ctx.arc(p.x, p.y, p.s * (p.kind === 'embers' ? 1 - p.life / p.max * 0.6 : 1), 0, Math.PI * 2); ctx.fill();
      }
    }
    ctx.globalAlpha = 1;
  }

  let last = performance.now();
  function frame(now) {
    S.raf = 0;
    if (window.OLYMPUS ? window.OLYMPUS.hidden() : document.hidden) return;   // hidden tab: no frame (the battery)
    const dt = Math.min(0.05, (now - last) / 1000), t = (now - S.t0) / 1000;
    last = now;
    size();
    const k = ease((now - S.k0) / 900);
    if (gl) gl.draw(bg.width, bg.height, t, k, S.from, S.to, S.ma, S.mb);
    else cssFallback(k);
    if (!still) {
      particles(dt);
      for (const f of S.frames) f(t);
      S.raf = requestAnimationFrame(frame);
    }
  }
  const kick = () => { if (!S.raf) S.raf = requestAnimationFrame(frame); };
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { last = performance.now(); kick(); } });
  addEventListener('resize', () => { S.lastW = 0; kick(); });

  return {
    gl: !!gl,
    palette(colors, mode = 0) {
      const now = performance.now(), k = ease((now - S.k0) / 900);
      // start the fade from where the last one is now
      S.from = S.from.map((c, i) => c.map((v, j) => v + (S.to[i][j] - v) * k));
      S.ma = k > 0.5 ? S.mb : S.ma;
      S.to = colors.map(hex); S.mb = mode; S.k0 = still ? now - 1e4 : now; S.hexes = colors.slice();
      kick();
    },
    burst(kind, n = 60, { x = 0.5, y = 0.45, colors = ['#f7c948', '#ffffff', '#7af0c4'] } = {}) {
      if (still) return;
      const w = S.lastW || innerWidth, h = S.lastH || innerHeight, cap = 160 - S.parts.length;
      for (let i = 0; i < Math.min(n, cap); i++) {
        const a = Math.random() * Math.PI * 2, sp = kind === 'embers' ? 20 + Math.random() * 40 : 140 + Math.random() * 360;
        S.parts.push({ kind, x: x * w + (kind === 'embers' ? (Math.random() - 0.5) * w : 0), y: kind === 'embers' ? -10 - Math.random() * h * 0.3 : y * h,
          vx: Math.cos(a) * sp * (kind === 'embers' ? 0.3 : 1), vy: kind === 'embers' ? 30 + Math.random() * 50 : Math.sin(a) * sp - 180,
          g: kind === 'embers' ? 8 : kind === 'sparks' ? 120 : 420, rot: Math.random() * 6, vr: (Math.random() - 0.5) * 12,
          s: kind === 'coins' ? 5 + Math.random() * 5 : kind === 'confetti' ? 3 + Math.random() * 4 : 1.2 + Math.random() * 2.2,
          c: colors[i % colors.length], life: 0, max: kind === 'embers' ? 4 + Math.random() * 3 : 1.6 + Math.random() * 1.4 });
      }
      kick();
    },
    onFrame(fn) { S.frames.push(fn); kick(); },
    colors: () => S.hexes.slice(),
    count: () => S.parts.length,
  };
}
