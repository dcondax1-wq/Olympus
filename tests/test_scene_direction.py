"""SCENE DIRECTION (2026-11-11): how it FEELS to be in the 3D worlds on an iPhone. Cameras, controls, the HUD and what the characters say.
Shared: tools/web_public/olympus/camera-rig.js (third person follow, conversation two-shot -> close-up, establishing shot, tour; sphere-cast collision) and
olympus/controls.js (tap-to-walk A* on a grid, gestures, the HUD: hints that fade, name plates for the near people only, the context ring). Scenes:
ergasterion/direct.js (+ floor.js drive hooks), symposium/direct.js (+ hall.js hooks), cities/walk-direct.js (Hellas walking). Dialogue: olympus/people-talk.js opener.

  a. node: the rig and the controls (colliders, sphere cast, damping, A*, the walker, ring and plate layout)
  b. node: the camera is NEVER inside a collider across scripted walks (Ergasterion: every hall, the doors, the camp; Symposium: every seat in close-up; a Hellas polis)
  c. node: tap-to-walk reaches its targets (random taps on the Ergasterion floor; a person: you end up in front of them)
  d. node: dialogue: every person's opener is whole sentences with their real name and role, one fact from their data, an invitation; every number grounded
  e. static: the hooks and the wiring (floor.js / hall.js / hellas.js drive hooks, joystick only as an option, names from the roster in Ergasterion)
    python -X utf8 -m tests.test_scene_direction
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

check = AK.check
WEB = AK.WEB
NODE = r"""
import * as R from './olympus/camera-rig.js';
import * as K from './olympus/controls.js';
import * as E from './ergasterion/direct.js';
import * as EC from './ergasterion/ergasterioncore.js';
import * as SD from './symposium/direct.js';
import * as SC from './symposium/symposiumcore.js';
import * as WD from './cities/walk-direct.js';
import * as C from './olympus/people-core.js';
import * as T from './olympus/people-talk.js';
import fs from 'node:fs';
import path from 'node:path';
const o = {};
const cam = () => ({ position: { x: 0, y: 0, z: 0, set(x, y, z) { this.x = x; this.y = y; this.z = z; } }, lookAt() {} });
// ---- a. the parts
{
  const W = R.makeWorld({ boxes: [{ x0: 0, x1: 1, z0: 0, z1: 1, y0: 0, y1: 1, tag: 'crate' }], circles: [{ x: 5, z: 0, r: 1, y1: 2 }], walls: [{ ax: -5, az: 3, bx: 5, bz: 3, t: 0.2, y1: 3 }] });
  o.hits = [R.hitTag(W, { x: 0.5, y: 0.5, z: 0.5 }, 0.1), R.hitTag(W, { x: 0.5, y: 1.5, z: 0.5 }, 0.1), R.hitTag(W, { x: 5, y: 1, z: 0 }, 0.1), R.hitTag(W, { x: 0, y: 1, z: 3.25 }, 0.1), R.hitTag(W, { x: 0, y: -0.2, z: -3 }, 0.1), R.hitTag(W, { x: -3, y: 1, z: -3 }, 0.1)];
  const f = R.castSphere(W, { x: -2, y: 1, z: -2 }, { x: -2, y: 1, z: 6 }, 0.2);
  o.cast = [+f.toFixed(3), R.castSphere(W, { x: -3, y: 1, z: -2 }, { x: -3, y: 1, z: 1 }, 0.2)];
  const v = { v: 0 }; let x = 0; const xs = []; for (let i = 0; i < 120; i++) { x = R.damp(x, 10, v, 0.3, 1 / 60); xs.push(x); }
  o.damp = { end: +x.toFixed(3), over: xs.some((q) => q > 10.0001), mono: xs.every((q, i) => i === 0 || q >= xs[i - 1]) };
  const g = K.createGrid({ x0: -10, x1: 10, z0: -10, z1: 10, cell: 0.5 }, (px, pz) => R.hits(R.makeWorld({ walls: [{ ax: 0, az: -10, bx: 0, bz: -1.2, t: 0.2 }, { ax: 0, az: 1.2, bx: 0, bz: 10, t: 0.2 }] }), { x: px, y: 0.5, z: pz }, 0.01));
  const p = K.findPath(g, { x: -6, z: 5 }, { x: 6, z: 5 });
  o.astar = { n: p ? p.length : 0, door: !!(p && p.some((q) => Math.abs(q.z) < 1.3 && Math.abs(q.x) < 1.5)), free: !!(p && p.every((q, i) => i === 0 || K.lineFree(g, p[i - 1], q))), none: K.findPath(K.createGrid({ x0: 0, x1: 4, z0: 0, z1: 4, cell: 0.5 }, (px) => px > 1.6 && px < 2.4, { pad: 0 }), { x: 0.5, z: 2 }, { x: 3.5, z: 2 }),
    closest: (K.findPath(K.createGrid({ x0: 0, x1: 4, z0: 0, z1: 4, cell: 0.5 }, (px) => px > 1.6 && px < 2.4, { pad: 0 }), { x: 0.5, z: 2 }, { x: 3.5, z: 2 }, { closest: true }) || []).slice(-1)[0] || null };
  const L = K.ringLayout(380, 30, 4, { w: 390, h: 844 }), B = K.ringLayout(195, 300, 4, { w: 390, h: 844 });
  o.ring = { inside: L.items.every((q) => q.x >= 36 && q.x <= 354 && q.y >= 36 && q.y <= 808), under: B.items.every((q) => q.y >= 300), n: L.items.length, apart: B.items.every((q, i) => i === 0 || Math.hypot(q.x - B.items[i - 1].x, q.y - B.items[i - 1].y) >= 56) };
  const plates = K.declutter([{ id: 'a', name: 'Kalamos', x: 100, y: 300, dist: 2 }, { id: 'b', name: 'Pyrrhos', x: 104, y: 302, dist: 3 }, { id: 'c', name: 'Metis', x: 300, y: 300, dist: 20 }, { id: 'd', name: 'Telamon', x: 250, y: 200, dist: 4 }, { id: 'e', name: 'Far but asked', x: 200, y: 600, dist: 30, important: true }, { id: 'f', name: 'Behind', x: 200, y: 600, dist: 1, front: false }], { max: 3 });
  o.plates = plates.map((q) => q.id);
}
// ---- b. never inside: Ergasterion
{
  const W = E.worldOf(), G = E.navOf(W), rig = R.createRig(cam(), { world: W, dist: 3.5, pitch: 0.36 }), wk = K.createWalker({ speed: 2.7 });
  const stops = [[6.5, 6.4], [6.5, -6], [-6, -6], [-6, 6], [6.5, 6.4], [6.5, 12.5], [0.5, 13.0], [12.5, 18.2], [-1.5, 22.0], [6.5, 6.4], [-11.5, 8.5], [11.8, -8.8]];
  let frames = 0, inside = 0, worst = '', reached = 0, legs = 0, pulled = 0; wk.place(6.5, 6.4, Math.PI); rig.follow({ x: 6.5, z: 6.4, yaw: Math.PI, h: 1.35 }).setAz(Math.PI).snap();
  for (let k = 1; k < stops.length; k++) {
    const pth = K.findPath(G, wk.pos, { x: stops[k][0], z: stops[k][1] }, { reach: 5, closest: true }); legs++; if (!pth) continue; let done = false; wk.go(pth, () => { done = true; });
    for (let i = 0; i < 1800 && !done; i++) { const s = wk.tick(1 / 30); rig.follow({ x: s.x, z: s.z, yaw: s.yaw, h: 1.35, moving: s.moving }); if (i % 40 === 0) rig.orbit(0.7, (i % 80 ? 0.2 : -0.25)); if (i % 90 === 0) rig.zoom(i % 180 ? 0.6 : 1.7); const st = rig.update(1 / 30); frames++; if (st.pulled > 0) pulled++; const t = rig.inside(0.1); if (t) { inside++; worst = t + ' at ' + JSON.stringify(st.pos); } }
    if (done) reached++;
  }
  // talk shots with every station worker and every tent, from both sides
  let talks = 0;
  for (const s of EC.STATIONS.concat(EC.CAMP_SPOTS.map((c) => ({ x: c.x, z: c.z - 1.9, id: 'tent' })))) for (const side of [1, -1]) {
    const a = K.approach({ x: s.x, z: s.z + 4 }, { x: s.x, z: s.z }, 1.7); rig.shot('talk', { a: { x: a.x, y: 0, z: a.z, h: 1.3 }, b: { x: s.x, y: 0.24, z: s.z, h: 1.4 }, side, two: 1, lookDown: 0.3 }, { cut: true });
    for (let i = 0; i < 150; i++) { const st = rig.update(1 / 30); frames++; talks++; const t = rig.inside(0.1); if (t) { inside++; worst = 'talk ' + s.id + ' ' + t + ' at ' + JSON.stringify(st.pos); } }
  }
  // the establishing shot of the page, and the tour
  rig.shot('follow'); rig.follow({ x: 6.5, z: 6.4, yaw: Math.PI, h: 1.35 }).setAz(Math.PI);
  rig.shot('establish', { from: { x: 11.1, y: 7.2, z: 9.4 }, look: { x: 5.3, y: 0.6, z: 1.9 }, pivot: { x: 9.9, y: 6.4, z: 8.6 }, dur: 3.4 });
  for (let i = 0; i < 150; i++) { rig.update(1 / 30); frames++; const t = rig.inside(0.1); if (t) { inside++; worst = 'establish ' + t; } }
  o.erg = { frames, inside, worst, reached, legs, pulled, talks, landed: rig.state().mode };
  // tap-to-walk: random taps on free floor reach their target; a tap on a person ends in front of them
  let ok = 0, n = 0, maxErr = 0, seed = 7; const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  wk.place(6.5, 6.4, 0);
  for (let k = 0; k < 40; k++) {
    const tx = -13 + rnd() * 29, tz = -10 + rnd() * 33; if (!G.freeAt(tx, tz)) continue; n++;
    const pth = K.findPath(G, wk.pos, { x: tx, z: tz }); if (!pth) continue; let done = false; wk.go(pth, () => { done = true; });
    for (let i = 0; i < 3000 && !done; i++) wk.tick(1 / 30);
    const e = Math.hypot(wk.pos.x - tx, wk.pos.z - tz); maxErr = Math.max(maxErr, e); if (done && e < 0.1) ok++;
  }
  const q = EC.STATIONS.find((s) => s.id === 'queue'), sp = K.approach({ x: 6.5, z: 6.4 }, { x: q.x, z: q.z }, 1.6), pth = K.findPath(G, { x: 6.5, z: 6.4 }, sp, { reach: 5 });
  let done = false; wk.place(6.5, 6.4, 0); wk.go(pth, () => { done = true; }); for (let i = 0; i < 2000 && !done; i++) wk.tick(1 / 30);
  o.taps = { n, ok, maxErr: +maxErr.toFixed(3), person: { done, d: +Math.hypot(wk.pos.x - q.x, wk.pos.z - q.z).toFixed(2), front: wk.pos.z > q.z } };
}
// ---- b. never inside: Symposium (every seat, a close-up from your place), and a Hellas polis
{
  let inside = 0, frames = 0, worst = '';
  for (const N of [8, 24, 38]) {
    const L = SC.seats(N), r = L.r, tr = Math.max(0.9, r * 0.32), W = SD.worldOf(r, tr), rig = R.createRig(cam(), { world: W, radius: 0.18 });
    for (let i = 0; i < N; i++) {
      const s = L.seats[i], yaw = Math.atan2(s.x, s.z) + Math.PI, off = r * 0.3, a = { x: Math.sin(yaw) * off, y: 0.2, z: Math.cos(yaw) * off, h: 1.35 }, b = { x: s.x * 0.97, y: 0.9, z: s.z * 0.97, h: 0.12 };
      rig.shot('talk', { a, b, side: i % 2 ? 1 : -1, two: 1.6, lookDown: 0.32, back: 1.45 }, { cut: true });
      for (let k = 0; k < 120; k++) { const st = rig.update(1 / 30); frames++; const t = rig.inside(0.08); if (t) { inside++; worst = N + ':' + i + ' ' + t + ' ' + JSON.stringify(st.pos); } }
    }
  }
  o.sym = { inside, frames, worst };
  const plan = { R: 60, hillR: 10, houses: [] };
  for (let i = 0; i < 60; i++) { const a = i * 0.7, d = 16 + (i % 9) * 4.5; plan.houses.push({ x: Math.sin(a) * d, z: Math.cos(a) * d, hx: 2.2, hz: 1.8, h: 4 + (i % 4) }); }
  const col = { hits: (x, z, r = 0.45) => { const d = Math.hypot(x, z); if (d > plan.R - 2.5 || d < plan.hillR + r) return true; return plan.houses.some((h) => { const px = Math.max(h.x - h.hx, Math.min(x, h.x + h.hx)), pz = Math.max(h.z - h.hz, Math.min(z, h.z + h.hz)); return (x - px) ** 2 + (z - pz) ** 2 < r * r; }); } };
  const W = WD.worldOf(plan), G = WD.navOf(plan, col), rig = R.createRig(cam(), { world: W, radius: 0.3, dist: 4.8, pitch: 0.34 }), wk = K.createWalker({ speed: 3 });
  let hin = 0, hf = 0, reached = 0, tries = 0; wk.place(0, 13, 0); rig.follow({ x: 0, z: 13, yaw: 0, h: 1.15 }).snap();
  for (let k = 0; k < 14; k++) { const a = k * 1.9, d = 14 + (k % 5) * 8, t = { x: Math.sin(a) * d, z: Math.cos(a) * d }; if (!G.freeAt(t.x, t.z)) continue; tries++; const pth = K.findPath(G, wk.pos, t); if (!pth) continue; let done = false; wk.go(pth, () => { done = true; });
    for (let i = 0; i < 3000 && !done; i++) { const s = wk.tick(1 / 30); rig.follow({ x: s.x, z: s.z, yaw: s.yaw, h: 1.15, moving: s.moving }); if (i % 50 === 0) rig.orbit(1.1, 0); rig.update(1 / 30); hf++; if (rig.inside(0.12)) hin++; } if (done) reached++; }
  o.hellas = { inside: hin, frames: hf, reached, tries };
}
// ---- d. dialogue
{
  const now = Date.parse('2026-11-11T15:00:00Z'), WEBD = process.cwd(), roster = C.normRoster(JSON.parse(fs.readFileSync('olympus/people.json', 'utf8')));
  const readIn = (p) => { const I = {}; for (const src of (p.sources || []).concat(['../ergasterion/queue.json', '../ergasterion/builders.json', '../archive/index.json', '../home.json', '../money/index.json'])) { try { I[src] = JSON.parse(fs.readFileSync(path.resolve(WEBD, 'olympus', src), 'utf8')); } catch (_) { /* not published here */ } } return I; };
  const all = roster.people.concat(roster.villagers.slice(0, 12)), bad = [], ung = [], sentencesBad = [], seen = [];
  const SENT = /^["(A-Z0-9+$-]/;
  for (const p of all) for (const I of [readIn(p), C.sampleInputs(now)]) {
    const f = C.buildFacts(p, I, now), op = T.opener(p, f, { hour: 15 }), g = T.greeting(p, f, null, { hour: 15, ownerName: 'Alex' });
    if (!op.intro.includes(p.name) || /Lives in |the the |: [a-z]+:|undefined|null|NaN/.test(op.text) || !op.invite || !/[?.]$/.test(op.invite)) bad.push(p.id + ' | ' + op.text);
    const S = op.text.split(/(?<=[.!?])\s+(?=["(A-Z0-9+$-])/);
    for (const s of S) { const words = s.replace(/[()".]/g, ' ').trim().split(/\s+/).filter(Boolean); if (words.length < 2 || !/[.!?)"]$/.test(s) || !SENT.test(s)) sentencesBad.push(p.id + ' | ' + s); }
    const u = T.ungrounded(g, T.corpus(p, f, ['Alex'])); if (u.length) ung.push(p.id + ' | ' + u.join(','));
    seen.push(op);
  }
  const lit = C.resolve(roster, 'bot:lit'), fl = C.buildFacts(lit, C.sampleInputs(now), now), opl = T.opener(lit, fl, { hour: 9 });
  const moods = ['calm', 'blunt', 'curious', 'wry'].map((t) => ['proud', 'busy', 'worried', 'sheepish'].map((m) => T.opener({ ...lit, temperament: t }, { ...fl, mood: m }, { hour: 9 }).mood)).flat();
  o.talk = { n: seen.length, bad: bad.slice(0, 6), sentencesBad: sentencesBad.slice(0, 6), ung: ung.slice(0, 6), lit: opl.text, moodsWhole: moods.every((m) => /^[A-Z].{8,}[.!?]$/.test(m) && m.split(' ').length >= 3), moods: moods.slice(0, 4),
    roles: ['job:queue', 'job:dev', 'mind', 'villager:zenith', 'builder:a1d36b03'].map((id) => { const p = C.resolve(roster, id); return p ? T.roleShort(p) : null; }),
    who: EC.STATIONS.map((s) => { const p = C.resolve(roster, EC.personId(s.id)); return [s.who, p ? p.name : null]; }) };
}
console.log(JSON.stringify(o));
"""


def test_node():
    r = subprocess.run(["node", "--input-type=module", "-e", NODE], cwd=WEB, capture_output=True, text=True, timeout=300)
    check("node harness runs", r.returncode == 0 and r.stdout.strip().startswith("{"), (r.stderr or r.stdout)[-1500:])
    if r.returncode != 0:
        return
    o = json.loads(r.stdout.strip().splitlines()[-1])
    check("a. colliders: a sphere touches a box / misses above it / hits an upright circle / a wall segment / the ground; free air is free",
          o["hits"][0] == "crate" and o["hits"][1] == "" and o["hits"][2] == "circle" and o["hits"][3] == "wall" and o["hits"][4] == "ground" and o["hits"][5] == "", o["hits"])
    check("a. the sphere cast stops before the wall (about 0.6 of the way, never past it) and runs free where nothing is", 0.55 < o["cast"][0] < 0.65 and o["cast"][1] == 1, o["cast"])
    check("a. damping is critically damped: reaches the target, never overshoots, never goes back", abs(o["damp"]["end"] - 10) < 0.05 and not o["damp"]["over"] and o["damp"]["mono"], o["damp"])
    check("a. A* goes through the door of a wall, every leg of the path is free; a closed wall gives no path, or (closest) the nearest reachable spot on your side", o["astar"]["door"] and o["astar"]["free"] and o["astar"]["n"] >= 2 and o["astar"]["none"] is None and o["astar"]["closest"] and 1.2 <= o["astar"]["closest"]["x"] <= 1.6, o["astar"])
    check("a. the context ring: 4 buttons inside the screen even at a corner, in an arc under the person, 56 px apart", o["ring"]["inside"] and o["ring"]["under"] and o["ring"]["n"] == 4 and o["ring"]["apart"], o["ring"])
    check("a. name plates: only near people (an important one even when far), at most 3, overlapping ones dropped, nobody behind the camera", o["plates"] == ["e", "a", "d"], o["plates"])
    e = o["erg"]
    check(f"b. ERGASTERION: the follow camera is NEVER inside a wall, column, station, crate, tent, table or the cart: {e['frames']} frames of a scripted walk through every hall, the doors and the camp (swiping and pinching), "
          f"30 talk shots and the establishing shot; it was pulled in front of something in {e['pulled']} frames",
          e["inside"] == 0 and e["frames"] > 3000 and e["reached"] == e["legs"] and e["talks"] == 150 * 50 and e["landed"] == "follow" and e["pulled"] > 0, e)
    t = o["taps"]
    check(f"c. TAP-TO-WALK: {t['ok']} of {t['n']} random taps on the floor reached (within 10 cm); a tap on Kalamos ends in front of him (talking distance)",
          t["n"] >= 15 and t["ok"] == t["n"] and t["person"]["done"] and 1.0 < t["person"]["d"] < 2.6 and t["person"]["front"], t)
    s = o["sym"]
    check(f"b. SYMPOSIUM: the conversation camera (two-shot, then the close-up with its dolly) is never inside the table, a couch or a column: every seat of halls of 8, 24 and 38 ({s['frames']} frames)", s["inside"] == 0 and s["frames"] > 8000, s)
    h = o["hellas"]
    check(f"b. HELLAS walking: across {h['frames']} frames of tap-to-walk in a polis (orbiting the camera) the camera is never inside a house, the hill or the wall; {h['reached']} of {h['tries']} walks arrived",
          h["inside"] == 0 and h["frames"] > 500 and h["reached"] == h["tries"] and h["tries"] >= 5, h)
    k = o["talk"]
    check(f"d. DIALOGUE: {k['n']} openers (every person and 12 villagers, real files and sample data): hello, 'I am <real name>, <a real role>', one fact, an invitation; no 'Lives in', no raw titles",
          k["n"] >= 90 and not k["bad"], k["bad"])
    check("d. every sentence a speech bubble can show is a WHOLE sentence (no fragments like 'Quietly'), and every mood line too", not k["sentencesBad"] and k["moodsWhole"], (k["sentencesBad"], k["moods"]))
    check("d. honesty: every number in every greeting is in that person's own facts (the grounding check)", not k["ung"], k["ung"])
    check("d. the LIT bot opens with its last paper trade in $ AND R and an invitation", re.search(r"I am Phoibos, the LIT bot.*My last paper trade made [+-]\$[\d,]+ \([+-][\d.]+R\)", k["lit"]) and k["lit"].endswith("?"), k["lit"])
    check("d. roles in plain words (name plates): the queue's scribe, the coding agents' foreman, the Mind, an app's voice, a builder", k["roles"][0] == "Scribe of the task queue" and k["roles"][1] == "Foreman of the coding agents" and k["roles"][2].startswith("Mind") and k["roles"][3] == "Voice of the Zenith app" and k["roles"][4] == "One of the builders", k["roles"])
    check("d. ERGASTERION names: every station worker is shown with the roster's own Greek name (no 'The', no 'Dev')", all(a == b and a for a, b in k["who"]) and len(k["who"]) == 15, k["who"])


def test_static():
    rd = lambda p: AK.read(os.path.join(WEB, p))  # noqa: E731
    fl, hall, hel, hui, erg, sym = rd("ergasterion/floor.js"), rd("symposium/hall.js"), rd("cities/hellas.js"), rd("cities/hellas-ui.js"), rd("ergasterion/ergasterion.js"), rd("symposium/symposium.js")
    check("e. hooks: floor.js drive / refs / setPlayer, hall.js drive / refs / front, hellas.js walkDirector (each in a marked SCENE DIRECTION section)",
          all(x in fl for x in ("drive(fn, opt)", "refs()", "setPlayer(x, z, yaw)", "SCENE DIRECTION HOOK")) and all(x in hall for x in ("drive(fn)", "refs()", "front:")) and "this.walkDirector && this.walkDirector.tick(dt)" in hel)
    check("e. the pages load the directors on demand (?direct=0 keeps the old controls) and the joystick is only an option (?joy=1)",
          "import('./direct.js?v=d2')" in rd("ergasterion/floorload.js") and "import('./direct.js?v=d2')" in rd("symposium/hallload.js") and "__ergDirect" in erg and "__symDirect" in sym and "import('./walk-direct.js?v=d2')" in hui and "get('direct') === '0'" in erg and "joyOn()" in erg and "joyOn()" in hui and ".hel.walking.nojoy .hel-stickzone{display:none}" in rd("cities/hellas.css"))
    rig, ctl = rd("olympus/camera-rig.js"), rd("olympus/controls.js")
    check("e. the shared kit: no network, no random, no orders; text only through textContent", not re.search(r"fetch\(|XMLHttpRequest|Math\.random|innerHTML|placeorder", rig + ctl, re.I))
    css = rd("olympus/people.css")
    check("e. the speech bubble always shows the whole sentence (the words not yet spoken are dimmed, never invisible)", ".pp-sayoff { color: rgba(" in css and "color: transparent" not in css.split(".pp-sayoff")[1][:40])


WAIT = "(f, ms) => new Promise((ok) => { const t0 = Date.now(), i = setInterval(() => { let v = null; try { v = f(); } catch (e) { v = null; } if (v || Date.now() - t0 > ms) { clearInterval(i); ok(v || null); } }, 150); })"


def until(p, expr, ms=20000):
    return p.evaluate(f"(() => ({WAIT})(() => {expr}, {ms}))()")


def test_browser():
    """f. Chromium 390 x 844 (one browser on the machine: flock -w 2400 /tmp/olympus_browser.lock): the directed scenes, live"""
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("f. browser part skipped: no Playwright", True)
        return
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            # ---- ERGASTERION
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, "ergasterion", "?demo=1&q=high&clock=quiet", hook="ERGASTERION")
            d0 = until(p, "window.ERG_DIRECTOR && window.ERG_DIRECTOR.state()", 30000)
            ui = p.evaluate("() => ({ joy: document.querySelector('#joy').hidden, hint: document.querySelector('#hint').hidden, ocHint: !!document.querySelector('.oc-hint'), talkBtn: document.querySelector('#talkBtn').hidden })")
            check("f. ERGASTERION opens directed: your own character on the floor, the old joystick and hint hidden, one quiet hint line, the establishing shot",
                  bool(d0) and d0["avatar"] in (True, False) and ui["joy"] and ui["hint"] and ui["ocHint"] and d0["cam"]["mode"] in ("establish", "follow"), (d0 and d0["cam"]["mode"], ui))
            hello = until(p, "window.ERG_DIRECTOR.state().hello", 40000)
            cta = until(p, "document.querySelector('.oc-cta') && document.querySelector('.oc-cta').textContent", 10000)
            st = p.evaluate("window.ERG_DIRECTOR.state()")
            name = (cta or "").replace("Talk to ", "")
            check("f. the first seconds: the nearest worker greets you by their real name and job with one fact and an invitation, and ONE button says what to do ('Talk to <name>')",
                  bool(hello) and bool(name) and f"I am {name}, " in hello and hello.rstrip().endswith(("?", ".")) and st["greeter"].startswith("w:") and st["avatar"], (hello, cta, st["greeter"]))
            box = p.evaluate("() => { const r = document.querySelector('#floor3d').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
            w0 = p.evaluate("window.ERG_DIRECTOR.state()")
            p.touchscreen.tap(box[0] + box[2] * 0.5, box[1] + box[3] * 0.82)
            p.wait_for_timeout(1800)
            w1 = p.evaluate("window.ERG_DIRECTOR.state()")
            check("f. TAP-TO-WALK (a real touch on the floor): a path is planned and your character walks along it",
                  w1["walks"] > w0["walks"] and (w1["path"] or abs(w1["me"]["x"] - w0["me"]["x"]) + abs(w1["me"]["z"] - w0["me"]["z"]) > 0.2), (w0["me"], w1["me"], w1["walks"]))
            p.evaluate("(() => { const d = window.ERG_DIRECTOR; d.goTo(d.state().greeter); })()")
            until(p, "document.querySelectorAll('.oc-ring button').length === 4", 30000)
            p.wait_for_timeout(600)      # the buttons pop in (scale .6 -> 1 in 0.22 s)
            ring = p.evaluate("[...document.querySelectorAll('.oc-ring button')].map((b) => { const r = b.getBoundingClientRect(); return [b.textContent, Math.round(r.width), Math.round(r.height)]; })")
            check("f. tap a person: you walk up to them and a ring offers Talk / Show work / Follow / Wave (each at least 44 px)",
                  bool(ring) and [r[0] for r in ring] == ["Talk", "Show work", "Follow", "Wave"] and all(r[1] >= 44 and r[2] >= 44 for r in ring), ring)
            p.evaluate("document.querySelector('.oc-ring button[data-act=talk]').click()")
            p.wait_for_timeout(600)
            t1 = p.evaluate("({ st: window.ERG_DIRECTOR.state(), open: !!(window.OLYMPUS_PEOPLE && window.OLYMPUS_PEOPLE.isOpen && window.OLYMPUS_PEOPLE.isOpen()) })")
            ph = until(p, "window.ERG_DIRECTOR.state().cam.phase === 'close-up' && 'close-up'", 30000)
            p.evaluate("window.OLYMPUS_PEOPLE && window.OLYMPUS_PEOPLE.close()")
            back = until(p, "window.ERG_DIRECTOR.state().mode === 'walk' && window.ERG_DIRECTOR.state().cam.mode", 8000)
            check("f. Talk: the chat opens and the camera cuts to the conversation (two-shot, then the close-up); closing the chat returns to following you",
                  t1["st"]["mode"] == "talk" and t1["open"] and t1["st"]["cam"]["phase"] in ("two-shot", "close-up") and ph == "close-up" and back == "follow", (t1["st"]["cam"]["phase"], t1["open"], ph, back))
            fin = p.evaluate("window.ERG_DIRECTOR.state()")
            plates = p.evaluate("[...document.querySelectorAll('.oc-plate b')].map((b) => b.textContent)")
            check(f"f. the camera was inside a collider in 0 of {fin['frames']} live frames; the name plates show at most 3 real names (never 'The' or 'Dev')",
                  fin["insideN"] == 0 and fin["frames"] > 30 and len(plates) <= 3 and not any(n in ("The", "Dev") for n in plates), (fin["insideN"], fin["frames"], plates))
            check("f. ERGASTERION directed: no page error", not errs, errs[:4])
            AK.shot(p, "direction-ergasterion")
            ctx.close()
            # ---- SYMPOSIUM
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, "symposium", "?q=high", hook="SYMPOSIUM")
            s0 = until(p, "window.SYM_DIRECTOR && window.SYM_DIRECTOR.state()", 30000)
            sh = until(p, "window.SYM_DIRECTOR.state().hello", 40000)
            cta = until(p, "document.querySelector('.oc-cta') && document.querySelector('.oc-cta').textContent", 10000)
            check("f. SYMPOSIUM: an establishing shot over the colonnade lands at your place; the person across the table (real news first) greets you by name; one button 'Talk to <name>'",
                  bool(s0) and bool(sh) and bool(cta) and ("I am " + cta.replace("Talk to ", "") + ",") in sh, (sh, cta))
            p.evaluate("document.querySelector('.oc-cta').click()")
            ph = until(p, "window.SYM_DIRECTOR.state().cam.phase === 'close-up' && window.SYM_DIRECTOR.state()", 30000)
            p.evaluate("window.OLYMPUS_PEOPLE && window.OLYMPUS_PEOPLE.close()")
            back = until(p, "window.SYM_DIRECTOR.state().mode === 'stand' && 'stand'", 8000)
            fin = p.evaluate("window.SYM_DIRECTOR.state()")
            check(f"f. SYMPOSIUM talk: the chat opens on the greeter, the camera goes to the close-up and back to your place; inside a collider in 0 of {fin['frames']} frames",
                  bool(ph) and ph["mode"] == "talk" and back == "stand" and fin["insideN"] == 0 and fin["frames"] > 30 and not errs, (bool(ph), back, fin["insideN"], errs[:3]))
            AK.shot(p, "direction-symposium")
            ctx.close()
            # ---- HELLAS walking
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.goto(f"{origin}/cities/?hellas=1&q=high&demo=1", wait_until="domcontentloaded")
            p.wait_for_function("window.__hellas && window.__hellas.ready", timeout=170000)
            p.evaluate("(() => { const u = window.__hellas.ui; u.enter(window.__hellas.world.poleis[0]); })()")
            p.wait_for_timeout(4000)
            p.evaluate("window.__hellas.ui.startWalk()")
            h0 = until(p, "window.__hellasDirector && window.__hellasDirector.state()", 30000)
            stick = p.evaluate("getComputedStyle(document.querySelector('.hel-stickzone')).display")
            cta = until(p, "document.querySelector('.oc-cta') && document.querySelector('.oc-cta').textContent", 30000)
            check("f. HELLAS walking is third person (your character), the thumb joystick is gone unless asked for, and the nearest townsperson is one tap away ('Talk to <name>')",
                  bool(h0) and stick == "none" and bool(cta) and cta.startswith("Talk to "), (bool(h0), stick, cta))
            p.evaluate("document.querySelector('.oc-cta').click()")
            ht = until(p, "window.__hellasDirector.state().mode === 'talk' && window.__hellasDirector.state()", 40000)
            card = p.evaluate("(() => { const c = document.querySelector('.hel-card'); return c && !c.hidden ? c.innerText : ''; })()")
            check("f. HELLAS talk: you walk up, the talk card opens and the conversation camera frames them; the hello names them and gives the last result of their street",
                  bool(ht) and ("Hello! I am " in card or "Welcome! I am " in card) and ("The last result here" in card or "quiet here" in card), card[:300])
            p.evaluate("window.__hellas.ui.hideCard()")
            hw = p.evaluate("window.__hellasDirector.state()")
            p.touchscreen.tap(195, 560)
            p.wait_for_timeout(1500)
            hw2 = p.evaluate("window.__hellasDirector.state()")
            check(f"f. HELLAS tap the street: you walk there; the camera was inside a house / the hill / the wall in 0 of {hw2['frames']} frames",
                  hw2["walks"] > hw["walks"] and hw2["insideN"] == 0 and hw2["frames"] > 30 and not errs, (hw["walks"], hw2["walks"], hw2["insideN"], errs[:3]))
            AK.shot(p, "direction-hellas")
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_node()
    test_static()
    if "--static" not in sys.argv:
        test_browser()
    AK.finish()
