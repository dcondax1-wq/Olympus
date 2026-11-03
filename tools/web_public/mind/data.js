// OLYMPUS Mind: the data adapter. The only door to the vault is Jarvis's own module, ../jarvis/obsidian.js:
//   graphSnapshot() -> null (not connected) | {v: 1, t, notes: [{id, title, path, tags, links, mtime, words, kind, snippet?,
//                                                                  preview? (optional, newer Jarvis: the note's first lines)}],
//                                             learned: [{t, text, note}]}
//   onIndexChange(cb) -> unsubscribe
// This page never reads a token, never fetches and never sends anything: it only calls those two functions.
//   openFeed(onUpdate, {demo})                            onUpdate({mode: 'live'|'demo'|'offline', snap}) now and on every change
// Every snapshot goes through normalize(): each field checked, times in ms (seconds accepted), text capped, junk dropped.
// 'demo' = the module is missing, failed or says "not connected" (a built-in fake brain from demo.js); 'offline' = it was
// connected this session and now answers null (the last real brain stays on screen).
import { createDemo } from './demo.js';

const KINDS = new Set(['note', 'daily', 'memory', 'inbox', 'me']);
const MAX_NOTES = 5000;
const POLL_MS = 60000;                              // a fresh snapshot every minute, besides onIndexChange
const text = (v, max = 300) => (typeof v === 'string' ? v.replace(/\s+/g, ' ').trim().slice(0, max) : '');
/** Note text for the card's markdown preview: line breaks kept (at most one blank line in a row), spaces tidied, capped. */
const lines = (v, max) => (typeof v === 'string' ? v.replace(/\r\n?/g, '\n').replace(/[ \t]+/g, ' ').replace(/ *\n */g, '\n').replace(/\n{3,}/g, '\n\n').trim().slice(0, max) : '');
const ms = (v) => { const x = Number(v); return Number.isFinite(x) && x > 0 ? (x < 1e11 ? x * 1000 : x) : 0; };   // seconds or ms
const strings = (v, max) => (Array.isArray(v) ? v.filter((x) => typeof x === 'string' || typeof x === 'number').map(String).slice(0, max) : []);
const baseName = (p) => p.split('/').pop().replace(/\.md$/i, '');

function normalize(raw) {
  if (!raw || typeof raw !== 'object' || !Array.isArray(raw.notes)) return null;
  const seen = new Set(), notes = [];
  for (const n of raw.notes) {
    if (!n || typeof n !== 'object' || n.id == null) continue;
    const id = String(n.id);
    if (seen.has(id)) continue;
    seen.add(id);
    const path = text(n.path, 400);
    notes.push({
      id, path,
      title: text(n.title, 160) || baseName(path) || id,
      tags: strings(n.tags, 24).map((t) => t.replace(/^#/, '').trim().toLowerCase()).filter(Boolean),
      links: strings(n.links, 400),
      mtime: ms(n.mtime),
      words: Math.max(0, Math.floor(Number(n.words) || 0)),
      kind: KINDS.has(n.kind) ? n.kind : 'note',
      snippet: lines(n.preview, 1500) || lines(n.snippet, 600),
    });
    if (notes.length >= MAX_NOTES) break;
  }
  const learned = (Array.isArray(raw.learned) ? raw.learned : [])
    .filter((l) => l && text(l.text))
    .map((l) => ({ t: ms(l.t), text: text(l.text, 280), note: l.note == null ? null : String(l.note) }))
    .sort((a, b) => a.t - b.t)
    .slice(-500);
  return { t: ms(raw.t) || Date.now(), notes, learned };
}

async function loadJarvis() {
  try {
    const mod = await import('../jarvis/obsidian.js');
    return mod && typeof mod.graphSnapshot === 'function' ? mod : null;
  } catch (_) {
    return null;                                    // not deployed yet, or it failed to load: the demo brain
  }
}

export async function openFeed(onUpdate, { demo = createDemo() } = {}) {
  const real = await loadJarvis();
  let mode = null, last = null, busy = false, again = false, demoOff = null;

  const watch = (src) => {
    try {
      const u = typeof src.onIndexChange === 'function' ? src.onIndexChange(() => pull()) : null;
      return typeof u === 'function' ? u : () => {};
    } catch (_) {
      return () => {};                              // a broken subscription still leaves the 60 s refresh
    }
  };

  async function pull() {
    if (busy) { again = true; return; }
    busy = true;
    try {
      do {
        again = false;
        let snap = null;
        if (real) { try { snap = normalize(await real.graphSnapshot()); } catch (_) { snap = null; } }
        if (snap) { mode = 'live'; last = snap; }
        else if (mode === 'live' || mode === 'offline') mode = 'offline';
        else { mode = 'demo'; last = normalize(await demo.graphSnapshot()); }
        if (mode === 'demo' && !demoOff) demoOff = watch(demo);              // the demo only "learns" while it is shown
        if (mode !== 'demo' && demoOff) { demoOff(); demoOff = null; }
        onUpdate({ mode, snap: last });
      } while (again);
    } finally {
      busy = false;
    }
  }

  if (real) watch(real);
  setInterval(pull, POLL_MS);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') pull(); });
  await pull();
}
