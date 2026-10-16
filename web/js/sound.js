import { api } from './util.js';
import { A } from './skins.js';

// distinct synthesized chimes per event (Web Audio: no sound files)
const PATTERNS = {
  sweep: [[1200, 0.07]],
  signal: [[880, 0.1], [1320, 0.14]],
  entry: [[660, 0.09], [990, 0.09], [1320, 0.16]],
  exit: [[990, 0.1], [660, 0.18]],
  guard: [[440, 0.16], [330, 0.24]],
  test: [[740, 0.1], [988, 0.1], [1480, 0.2]],
};
let ctx = null;

export function chime(kind, force = false) {
  if (!A.sound && !force) return;
  try {
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
    let t = ctx.currentTime + 0.01;
    for (const [f, d] of PATTERNS[kind] || PATTERNS.signal) {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.type = kind === 'guard' ? 'triangle' : 'sine';
      o.frequency.value = f;
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.22, t + 0.012);
      g.gain.exponentialRampToValueAtTime(0.0001, t + d);
      o.connect(g).connect(ctx.destination);
      o.start(t); o.stop(t + d + 0.02);
      t += d * 0.85;
    }
  } catch (e) { /* audio not available */ }
}

// watch the live bot's log and chime on new events
let seen = null;
export function startSoundWatch() {
  setInterval(async () => {
    if (!A.sound) return;
    let s;
    try { s = await api('/api/live/state'); } catch (e) { return; }
    const log = s.log || [];
    const keys = log.map(l => `${l.t}|${l.text}`);
    if (seen === null) { seen = new Set(keys); return; }
    for (const l of log.slice().reverse()) {
      const k = `${l.t}|${l.text}`;
      if (seen.has(k)) continue;
      seen.add(k);
      if (PATTERNS[l.type]) chime(l.type);
      else if (l.type === 'news') chime('guard');
    }
  }, 8000);
}
