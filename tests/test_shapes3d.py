"""AGORA 3D shapes (tools/web_public/olympus/shapes3d.js: 41 shapes, bake(), OLYMPUS_SHAPES.mount in shapes-mount.js) and the Agora Gallery app (tools/web_public/gallery/), 2026-11-10.

  a. static: shapes3d.js is pure (three only, no DOM / network / storage), the AGORA look (no neon words), the gallery files and kit lines (agora_kit.static_kit), stage.js / gallery.js split
     (the page never imports three.js, so it is never blank), the fixture mirrors the library, the wiring section exists
  b. node: all 41 shapes build in HD and LITE; baking for the collection (one draw each); triangle and draw-call budgets; LITE is smaller than HD; repeated parts are instanced; stand on y = 0; finite numbers; warm colours only;
     options (pillar values, fit size), dispose, determinism; gallerycore.js maths (shelf, step, fitDistance, modeFor, inertia, glyphs)
  c. one browser smoke (Chromium 390 x 844, 240 s limit): 3D stage starts, shelf of 41 with category chips, next / tile / quality / look-closer, drag turns, the scene builder (pick, Share, #hash restores), the collection (all 41, tap to pick), OLYMPUS_SHAPES.mount demo page + its flat fallback, ?flat=1 fallback
    python -X utf8 -m tests.test_shapes3d            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "gallery", "Agora Gallery"
check = AK.check
LIB = os.path.join(AK.WEB, "olympus", "shapes3d.js")
OLD = ["doric", "ionic", "temple", "lighthouse", "obelisk", "sundial", "hourglass", "owl", "scroll", "amphora", "coinstack", "scales", "pillarbar", "trireme", "laurel", "shield", "helmet", "lyre", "brazier"]
NEW = ["olivetree", "chariot", "cornucopia", "kylix", "redvase", "bust", "anchor", "stele", "tetradrachm", "harp", "caduceus", "pegasus", "sandal", "bow", "swordspear", "trophy", "goldbars", "vaultdoor", "fountain", "stoa", "dolphin", "mosaic"]
IDS = OLD + NEW
CATS = ["Architecture", "Objects", "Beasts", "Money", "Sea"]


def test_static():
    lib = AK.read(LIB)
    code = re.sub(r"//[^\n]*", "", lib)
    check("a. shapes3d.js is pure: three.js is its only import; no document / window / fetch / storage / eval", re.findall(r"^import .* from '([^']+)'", lib, re.M) == ["../jarvis/three.module.min.js"]
          and not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(|\blocalStorage\b|sessionStorage|indexedDB|\beval\s*\(|XMLHttpRequest|WebSocket", code))
    check("a. the AGORA look: no neon / cyber words, no cyan / violet / magenta colours in the library", not AK.BANNED_LOOK.search(lib) and not re.search(r"#(?:0ff|00f|f0f|a855f7|c084fc|7fe9ff)\b|#00ffff|#ff00ff", lib, re.I))
    check("a. the public API: SHAPES, IDS, GROUPS, BUDGET, materials, build, fit, stats, dispose, pedestal, warmLights, bake, bakedShape",
          all(re.search(r"export (?:const|function) " + n + r"\b", lib) for n in ("SHAPES", "IDS", "GROUPS", "BUDGET", "materials", "build", "fit", "stats", "dispose", "pedestal", "warmLights", "bake", "bakedShape")))
    check("a. both builds exist in code: every shape reads `lite` (a LITE variant) and repeated parts use InstancedMesh", "lite" in lib and lib.count("instanced(") >= 30 and "new THREE.InstancedMesh" in lib)
    AK.static_kit(APP, NAME)
    d = os.path.join(AK.WEB, APP)
    html, page, stage, css = (AK.read(os.path.join(d, n)) for n in ("index.html", "gallery.js", "stage.js", "gallery.css"))
    imports = re.findall(r"^import .* from '([^']+)'", page + "\n" + AK.read(os.path.join(d, "gallerycore.js")), re.M)
    check("a. the page (gallery.js + gallerycore.js) imports only gallerycore.js (which imports the pure shapes2d.js drawings), never three.js, so it is never blank; stage.js is a separate module that does, loaded first",
          imports == ["./gallerycore.js", "../olympus/shapes2d.js"] and all(x in stage for x in ("three.module.min.js", "olympus/render.js", "olympus/shapes3d.js")) and html.index('src="stage.js') < html.index('src="gallery.js'), imports)
    check("a. stage.js has no markup from data, no network, no storage, and starts only after a WebGL test", not re.search(r"innerHTML|fetch\(|localStorage|sessionStorage|XMLHttpRequest|\bimport\s*\(", stage) and "webglOK" in stage)
    check("a. the 2D drawing is always in the page: a #flat drawing, the shelf, prev / next, the quality buttons, the look-closer button",
          all(f'id="{i}"' in html for i in ("flat", "flatSvg", "flatRow", "shelf", "prev", "next", "quality", "focusBtn", "stage", "hint", "views", "cats", "buildCard", "picked", "buildShare", "buildClear", "shareUrl", "collCard", "collOpen")) and "touch-action: pan-y" in css)
    fx = json.load(open(os.path.join(d, "fixture.json"), encoding="utf-8"))
    check("a. the fixture lists the 41 shapes with name, meaning and category", sorted(s["id"] for s in fx["shapes"]) == sorted(IDS) and all(s["name"] and len(s["means"]) > 20 and s["group"] in CATS for s in fx["shapes"]), [s["id"] for s in fx["shapes"]])
    s2 = AK.read(os.path.join(AK.WEB, "olympus", "shapes2d.js"))
    mount = AK.read(os.path.join(AK.WEB, "olympus", "shapes-mount.js"))
    demo = AK.read(os.path.join(AK.WEB, "olympus", "shapes-demo.html"))
    check("a. shapes2d.js is pure data (no import, no document / window), one drawing per shape, built with createElementNS only",
          not re.search(r"^import |\bwindow\.|\bfetch\(|innerHTML", re.sub(r"//[^\n]*", "", s2), re.M) and "createElementNS" in s2 and all(re.search(r"^  " + i + r": \[", s2, re.M) for i in IDS))
    check("a. shapes-mount.js: OLYMPUS_SHAPES.mount(canvasOrEl, id, opts) with a flat 2D fallback, render core + kit, no innerHTML / network / storage / dynamic import, warm (not violet) reflections",
          all(x in mount for x in ("window.OLYMPUS_SHAPES", "export function mount", "flatFallback", "createRenderer", "shapes2d.js", "webglOK", "theme: AGORA")) and not re.search(r"innerHTML|fetch\(|localStorage|sessionStorage|XMLHttpRequest|\bimport\s*\(", mount)
          and "#a855f7" not in mount and "#c084fc" not in mount)
    check("a. the demo page olympus/shapes-demo.html mounts three spots with one line each", demo.count("M.mount(") == 3 and "shapes-mount.js" in demo and "__mounts" in demo)
    wiring = AK.read(os.path.join(AK.ROOT, "docs", "NEW_APPS_WIRING.md"))
    check("a. docs/NEW_APPS_WIRING.md has the gallery section with the wiring rows", "gallery" in wiring.lower() and "Agora Gallery" in wiring and "shapes3d.js" in wiring and "OLYMPUS_SHAPES.mount" in wiring and "shapes-mount.js" in wiring and "scene builder" in wiring.lower())


# ------------------------------------------------------------------------------------------------ node
SHAPES_HARNESS = r"""
import * as S from './olympus/shapes3d.js';
const out = { ids: S.IDS, groups: S.GROUPS, budget: S.BUDGET, shapes: {}, errors: [] };
const T = S.THREE;
for (const s of S.SHAPES) {
  const r = { meta: [s.name, s.means, s.group] };
  for (const lite of [true, false]) {
    try {
      const g1 = S.build(s.id, { lite }), g2 = S.build(s.id, { lite });
      const st = S.stats(g1), st2 = S.stats(g2);
      const b = new T.Box3().setFromObject(g1);
      let bad = 0, inst = 0, tex = 0;
      g1.traverse((o) => {
        if (!o.isMesh) return;
        if (o.isInstancedMesh) inst++;
        const p = o.geometry.attributes.position.array; for (let i = 0; i < p.length; i += 7) if (!Number.isFinite(p[i])) bad++;
        const m = o.material; if (m.emissive && m.emissive.r > 0.6) bad++;
      });
      const mats = g1.userData.ownMaterials;
      const cold = [];
      for (const k of Object.keys(mats)) {
        const m = mats[k]; if (!m || !m.color || ['water', 'glass'].includes(k)) continue;
        const c = m.color; if (c.b > c.r * 1.02 && k !== 'ink') cold.push(k + ':' + c.getHexString());
        if (Math.max(c.r, c.g, c.b) > 1.7) cold.push(k + ':bright');
      }
      r[lite ? 'lite' : 'hd'] = { draws: st.draws, tris: st.tris, inst, instances: st.instances, size: st.size, minY: b.min.y, maxY: b.max.y, bad, cold, same: st.tris === st2.tris && JSON.stringify(st.size) === JSON.stringify(st2.size), update: typeof g1.userData.update, id: g1.userData.id };
      if (g1.userData.update) { g1.userData.update(1.3); g1.userData.update(2.6); }
      S.dispose(g1); S.dispose(g2);
    } catch (e) { out.errors.push(s.id + ' ' + lite + ' ' + e.message); }
  }
  out.shapes[s.id] = r;
}
// options
const p3 = S.stats(S.build('pillarbar', { values: [0.2, 0.5, 0.9], lite: true })), p9 = S.stats(S.build('pillarbar', { values: [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], lite: true }));
const pj = S.stats(S.build('pillarbar', { values: ['x', null, 9, -4], lite: true }));
out.pillar = [p3.instances, p9.instances, p3.size[0] < p9.size[0], pj.instances, S.build('pillarbar', { values: [1, 2], tones: ['gain', 'loss'], lite: true }).userData.bars];
const f = S.build('doric', { size: 5 }), fb = new T.Box3().setFromObject(f), fs = fb.getSize(new T.Vector3());
out.fit = [Math.max(fs.x, fs.y, fs.z), fb.min.y, (fb.min.x + fb.max.x) / 2];
let thrown = null; try { S.build('nope'); } catch (e) { thrown = e.name; } out.thrown = thrown;
const M = S.materials({ lite: false }), a = S.build('owl', { materials: M }), b = S.build('amphora', { materials: M });
out.shared = [a.userData.ownMaterials === null, b.userData.ownMaterials === null];
S.dispose(a); out.sharedAlive = typeof M.marble.color.r === 'number';
const sc = new T.Scene(), L = S.warmLights(sc, { lite: true }); out.lights = [sc.children.length, L.key.color.r >= L.key.color.b]; L.remove(); out.lights.push(sc.children.length);
const ped = S.pedestal({ lite: true }); out.ped = [S.stats(ped).draws, S.stats(ped).tris < 600];
// the temple is made of one instanced colonnade; the HD temple has more columns than LITE
const t1 = S.stats(S.build('temple', { lite: true })).instances, t2 = S.stats(S.build('temple', { lite: false })).instances;
out.temple = [t1, t2];
out.baked = {}; let bt = 0;
for (const id of S.IDS) {
  const m = S.bakedShape(id, { size: 2 }), bb = new T.Box3().setFromObject(m), sz = bb.getSize(new T.Vector3());
  let bad = 0; const pa = m.geometry.attributes.position.array, ca = m.geometry.attributes.color.array; for (let i = 0; i < pa.length; i++) if (!Number.isFinite(pa[i])) bad++; for (let i = 0; i < ca.length; i++) if (!(ca[i] >= 0 && ca[i] <= 1)) bad++;
  const tris = m.geometry.index.count / 3; bt += tris;
  out.baked[id] = { tris, max: Math.max(sz.x, sz.y, sz.z), minY: bb.min.y, bad, isMesh: m.isMesh, mats: Array.isArray(m.material) ? m.material.length : 1, id: m.userData.id };
  m.geometry.dispose();
}
out.bakedTotal = bt;
out.groupsOf = Object.fromEntries(S.SHAPES.map((s) => [s.id, s.group]));
console.log(JSON.stringify(out));
"""

CORE_HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {};
  const fx = { shapes: [{ id: 'owl', name: 'Owl', means: 'Wisdom', group: 'Beasts' }, { id: 'owl', name: 'dup' }, { id: 'nope' }, null, { id: 'doric', group: 'zzz' }] };
  const sh = C.shelf(fx);
  o.shelf = [sh.map((s) => s.id), sh[1].group, C.shelf(null).length, C.shelf({ shapes: 'x' }).length, C.shelf({ shapes: [] })[0].id, C.shelf(undefined).every((s) => s.name && s.group)];
  o.grouped = C.grouped(C.shelf(null)).map((g) => [g.name, g.items.length]);
  o.step = [C.step(0, -1, 19), C.step(18, 1, 19), C.step(3, 1, 19), C.step('x', 1, 19), C.step(5, 0, 0), C.step(-1, 0, 19), C.step(2, 40, 19)];
  o.index = [C.indexOf(sh, 'doric'), C.indexOf(sh, 'zzz')];
  o.fmt = [C.fmt(1828), C.fmt(32000), C.fmt('x'), C.fmt(999.6)];
  const d1 = C.fitDistance(34, 1, 1.7, 1.5, false), d2 = C.fitDistance(34, 0.5, 1.7, 1.5, false), d3 = C.fitDistance(34, 1, 1.7, 1.5, true);
  o.fit = [d1 > 4 && d1 < 12, d2 > d1, d3 < d1, C.fitDistance('x', 'y', 1, 1, false) > 0, C.fitDistance(34, 0, 1, 1) > 0];
  o.mode = [C.modeFor('auto', 'low').lite, C.modeFor('auto', 'high').lite, C.modeFor('auto', 'off').lite, C.modeFor('high', 'low').lite, C.modeFor('lite', 'ultra').lite, C.modeFor('zzz', 'high').mode, C.modeFor('high', 'low').level, C.modeFor('lite', 'high').level, C.modeFor('auto', 'high').level];
  o.inertia = [C.inertia(3, 0) === 3, C.inertia(3, 0.2) < 3 && C.inertia(3, 0.2) > 0, C.inertia(3, 2), C.inertia(-3, 0.2) < 0, C.inertia(0.01, 0)];
  o.tap = [C.isTap(2, 120), C.isTap(20, 120), C.isTap(2, 900)];
  o.glyphs = Object.keys(C.GLYPHS).length; o.glyphIds = Object.keys(C.GLYPHS).sort();
  o.glyphOK = Object.values(C.GLYPHS).every((g) => Array.isArray(g) && g.length >= 2 && g.every((e) => ['path', 'rect', 'circle', 'ellipse'].includes(e[0]) && typeof e[1] === 'object'));
  const ids = C.shelf(null).map((s) => s.id);
  o.cat = [C.filter(C.shelf(null), 'Money').length, C.filter(C.shelf(null), 'All').length, C.filter(C.shelf(null), 'zzz').length, C.filter(C.shelf(null), 'Beasts').map((s) => s.id).sort(), C.GROUPS];
  const a1 = C.toggleId([], 'owl', 6), a2 = C.toggleId(a1.ids, 'temple', 6), a3 = C.toggleId(a2.ids, 'owl', 6), full = C.toggleId(['a', 'b', 'c', 'd', 'e', 'f'], 'g', 6);
  o.toggle = [a1.ids, a1.added, a2.ids, a3.ids, a3.added, full.full, full.ids.length, C.toggleId([], 'x', 0).ids, C.MAX_BUILD];
  const hh = C.makeHash(['owl', 'temple', 'lyre']);
  o.hash = [hh, C.parseHash(hh, ids, 6), C.parseHash('#b=owl,nope,lyre', ids, 6), C.parseHash('#b=', ids, 6), C.parseHash('#x=owl', ids, 6), C.parseHash('b=owl', ids, 6), C.parseHash('#b=doric,ionic,temple,owl,lyre,harp,bust,anchor', ids, 6).length, C.parseHash('#b=owl;<script>', ids, 6), C.parseHash(null, ids, 6)];
  const r0 = C.ring(0, 2), r1 = C.ring(1, 2), r4 = C.ring(4, 2);
  o.ring = [r0.length, r1.length, r1[0].x, r4.length, Math.abs(r4[0].z - 2) < 1e-9, Math.abs(r4[1].x - 2) < 1e-9, r4.every((p) => Math.abs(Math.hypot(p.x, p.z) - 2) < 1e-9), C.ringRadius(1), C.ringRadius(6), C.ringRadius(2) >= 1.3];
  const col = C.collection(41, 1.7), pts = col.places;
  let minD = 99; for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) minD = Math.min(minD, Math.hypot(pts[i].x - pts[j].x, pts[i].z - pts[j].z));
  o.coll = [pts.length, pts[0].x, minD > 1.3, col.outer, C.collection(0, 1.7).places.length, C.collection(1, 1.7).places.length, C.collection(7, 1.7).places.length];
  o.words = [C.position(2, 19), C.qualityWords(true).startsWith('Lite'), C.qualityWords(false).startsWith('High'), C.GROUPS.length, C.MODES];
  console.log(JSON.stringify(o));
});
"""


def run_lib_harness():
    exe = shutil.which("node")
    if not exe:
        return None
    tmp = tempfile.mkdtemp(prefix="ag-shapes-")
    try:
        os.makedirs(os.path.join(tmp, "olympus"))
        os.makedirs(os.path.join(tmp, "jarvis"))
        shutil.copy(LIB, os.path.join(tmp, "olympus", "shapes3d.js"))
        shutil.copy(os.path.join(AK.WEB, "jarvis", "three.module.min.js"), os.path.join(tmp, "jarvis", "three.module.min.js"))
        with open(os.path.join(tmp, "package.json"), "w") as fh:
            fh.write('{"type":"module"}')
        with open(os.path.join(tmp, "run.mjs"), "w") as fh:
            fh.write(SHAPES_HARNESS)
        r = subprocess.run([exe, os.path.join(tmp, "run.mjs")], capture_output=True, text=True, timeout=120)
        if r.returncode:
            print(r.stderr[-1500:])
            return {"_error": r.stderr[-600:]}
        return json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_core_harness():
    exe = shutil.which("node")
    tmp = tempfile.mkdtemp(prefix="ag-gcore-")
    try:
        os.makedirs(os.path.join(tmp, "gallery"))
        os.makedirs(os.path.join(tmp, "olympus"))
        shutil.copy(os.path.join(AK.WEB, APP, "gallerycore.js"), os.path.join(tmp, "gallery", "gallerycore.js"))
        shutil.copy(os.path.join(AK.WEB, "olympus", "shapes2d.js"), os.path.join(tmp, "olympus", "shapes2d.js"))
        with open(os.path.join(tmp, "package.json"), "w") as fh:
            fh.write('{"type":"module"}')
        with open(os.path.join(tmp, "harness.cjs"), "w") as fh:
            fh.write(CORE_HARNESS)
        r = subprocess.run([exe, os.path.join(tmp, "harness.cjs"), os.path.join(tmp, "gallery", "gallerycore.js")], capture_output=True, text=True, timeout=120)
        if r.returncode:
            print(r.stderr[-1500:])
            return {"_error": r.stderr[-600:]}
        return json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_node():
    if not shutil.which("node"):
        check("b. node tests skipped: no node", True)
        return
    o = run_lib_harness()
    check("b. the library loads in node and builds every shape without an error", o and "_error" not in o and not o["errors"], o and (o.get("_error") or o.get("errors")))
    if not o or "_error" in o:
        return
    sh = o["shapes"]
    check("b. 41 shapes (the first 19 plus 22 new) in five categories, each with a name and a plain meaning", sorted(o["ids"]) == sorted(IDS) and len(IDS) == 41 and o["groups"] == CATS and all(v["meta"][0] and len(v["meta"][1]) > 30 and v["meta"][2] in o["groups"] for v in sh.values()), o["ids"])
    cnt = {c: sum(1 for v in sh.values() if v["meta"][2] == c) for c in CATS}
    check("b. every category has at least 3 shapes (Architecture, Objects, Beasts, Money, Sea)", all(n >= 3 for n in cnt.values()), cnt)
    lt, hb = o["budget"]["lite"], o["budget"]["hd"]
    over = [f"{k} lite {v['lite']['tris']}/{v['lite']['draws']}" for k, v in sh.items() if v["lite"]["tris"] > lt["tris"] or v["lite"]["draws"] > lt["draws"]] + [f"{k} hd {v['hd']['tris']}/{v['hd']['draws']}" for k, v in sh.items() if v["hd"]["tris"] > hb["tris"] or v["hd"]["draws"] > hb["draws"]]
    check(f"b. PERF budgets: LITE <= {lt['tris']} triangles and {lt['draws']} draw calls, HD <= {hb['tris']} and {hb['draws']}, for all 41", not over, over)
    bigger = [k for k, v in sh.items() if not v["lite"]["tris"] < v["hd"]["tris"]]
    check("b. every LITE variant is smaller than its HD build (fewer triangles)", not bigger, bigger)
    low = [k for k, v in sh.items() if v["lite"]["tris"] > v["hd"]["tris"] * 0.8 and v["hd"]["tris"] > 800]
    check("b. LITE is a real low-poly cut (at most 80% of HD) wherever HD is over 800 triangles", not low, low)
    tot_l, tot_h = sum(v["lite"]["tris"] for v in sh.values()), sum(v["hd"]["tris"] for v in sh.values())
    check("b. the whole shelf: LITE total is under a third of HD total and the HD total is under 150,000 triangles", tot_l * 3 < tot_h and tot_h < 150000, (tot_l, tot_h))
    check("b. repeated parts are instanced: temple columns, laurel leaves, coins, oars, strings, pillar bars, flame marks (>= 30 shapes use InstancedMesh in HD)", sum(1 for v in sh.values() if v["hd"]["inst"] > 0) >= 30
          and all(sh[k]["hd"]["inst"] > 0 for k in ("temple", "laurel", "coinstack", "trireme", "lyre", "pillarbar", "obelisk", "caduceus", "goldbars", "mosaic", "olivetree", "stoa", "fountain", "pegasus")), [k for k, v in sh.items() if not v["hd"]["inst"]])
    check("b. the temple has a bigger colonnade in HD than in LITE", o["temple"][1] > o["temple"][0] > 0, o["temple"])
    size = [k for k, v in sh.items() for m in ("lite", "hd") if not (0.8 <= max(v[m]["size"]) <= 4.0 and v[m]["size"][1] >= 0.4)]
    check("b. every shape is between 0.8 and 4 units, at least 0.4 tall (a sane native size)", not size, size)
    ground = [k for k, v in sh.items() for m in ("lite", "hd") if not -0.15 <= v[m]["minY"] <= 0.15]
    check("b. every shape stands on y = 0 (the lowest point within 0.15)", not ground, ground)
    bad = [k for k, v in sh.items() for m in ("lite", "hd") if v[m]["bad"]]
    check("b. every vertex is a finite number and nothing glows (no emissive above 0.6)", not bad, bad)
    cold = {k: v[m]["cold"] for k, v in sh.items() for m in ("lite", "hd") if v[m]["cold"]}
    check("b. warm colours only: every material is warmer than blue (water and glass aside), nothing brighter than 1.7", not cold, cold)
    same = [k for k, v in sh.items() for m in ("lite", "hd") if not v[m]["same"]]
    check("b. deterministic: building a shape twice gives the same triangles and size", not same, same)
    check("b. gentle motion hooks (update(t)) on the torch, scales, ship, lighthouse and the spinning coin only", sorted(k for k, v in sh.items() if v["hd"]["update"] == "function") == ["brazier", "lighthouse", "scales", "tetradrachm", "trireme"], [k for k, v in sh.items() if v["hd"]["update"] == "function"])
    check("b. pillarbar: bars follow the values (3 vs 9), junk values are clamped (4 bars), more bars are wider, tones accepted", o["pillar"][0] == 3 * 3 and o["pillar"][1] == 9 * 3 and o["pillar"][2] and o["pillar"][3] == 4 * 3 and o["pillar"][4] == 2, o["pillar"])
    check("b. size option fits the longest side (5), stands on y = 0, centred; an unknown id throws a RangeError", abs(o["fit"][0] - 5) < 1e-6 and abs(o["fit"][1]) < 1e-6 and abs(o["fit"][2]) < 1e-6 and o["thrown"] == "RangeError", (o["fit"], o["thrown"]))
    check("b. a shared material set survives disposing one shape; the pedestal and the warm lights work", o["shared"] == [True, True] and o["sharedAlive"] and o["lights"] == [3, True, 0] and o["ped"][0] == 2 and o["ped"][1], (o["shared"], o["lights"], o["ped"]))
    ow, ly = sh["owl"]["hd"]["size"], sh["lyre"]["hd"]["size"]
    check("b. the redone owl and lyre read as themselves: the owl is a tall pear (taller than 2.2, under 1.4 wide, 14+ parts), the lyre is a tall U (about 2 high, narrower than 1.5)",
          ow[1] >= 2.2 and ow[0] <= 1.4 and ow[0] / ow[1] < 0.6 and ly[1] >= 1.9 and ly[0] <= 1.5 and ly[0] / ly[1] < 0.75 and sh["owl"]["lite"]["draws"] >= 14, (ow, ly))
    bk = o["baked"]
    badk = [k for k, v in bk.items() if not (v["isMesh"] and v["mats"] == 1 and v["id"] == k and v["bad"] == 0 and 0 < v["tris"] <= sh[k]["lite"]["tris"] and 0.9 <= v["max"] <= 2.001 and -0.05 <= v["minY"] <= 0.15)]
    check("b. bake: every shape becomes ONE mesh (one draw call) with vertex colours, finite, fitted into the size asked (at most 2, at least 0.9), standing on y = 0, never more triangles than its LITE build", len(bk) == 41 and not badk, badk)
    check("b. the collection budget: all 41 baked LITE shapes are under 40,000 triangles in 41 draw calls (+ the floor)", o["bakedTotal"] < 40000, o["bakedTotal"])
    core = run_core_harness()
    check("b. gallerycore.js runs in node", core and "_error" not in core, core)
    if not core or "_error" in core:
        return
    check("b. the shelf: duplicates, unknown ids and junk dropped, a wrong group becomes the first; the built-in list when the fixture is junk (never blank)",
          core["shelf"][0] == ["owl", "doric"] and core["shelf"][1] == "Architecture" and core["shelf"][2] == 41 and core["shelf"][3] == 41 and core["shelf"][4] == "doric" and core["shelf"][5], core["shelf"])
    check("b. grouped(): five categories, in order, 41 shapes in all (and the built-in list is grouped like the library)", [g[0] for g in core["grouped"]] == o["groups"] and sum(g[1] for g in core["grouped"]) == 41
          and {g[0]: g[1] for g in core["grouped"]} == cnt, (core["grouped"], cnt))
    check("b. category chips: filter() by Money / Beasts / All / junk", core["cat"][0] == cnt["Money"] and core["cat"][1] == 41 and core["cat"][2] == 41 and core["cat"][3] == ["dolphin", "owl", "pegasus"] and core["cat"][4] == CATS, core["cat"])
    check("b. scene builder: toggle adds and removes, stops at 6 with a 'full' flag, a junk max is 1; the #hash is made and read back (known shapes only, 6 at most, junk and script text refused)",
          core["toggle"] == [["owl"], True, ["owl", "temple"], ["temple"], False, True, 6, ["x"], 6] and core["hash"][0] == "#b=owl,temple,lyre" and core["hash"][1] == ["owl", "temple", "lyre"] and core["hash"][2] == ["owl", "lyre"]
          and core["hash"][3] == [] and core["hash"][4] is None and core["hash"][5] == ["owl"] and core["hash"][6] == 6 and core["hash"][7] is None and core["hash"][8] is None, core["toggle"] + core["hash"])
    check("b. the ring layout (shapes face outward on a circle) and the collection layout (41 places in rings, none closer than 1.3 apart, first in the middle)",
          core["ring"][:4] == [0, 1, 0, 4] and all(core["ring"][4:7]) and core["ring"][7] == 0 and core["ring"][8] >= 2.2 and core["ring"][9] and core["coll"][0] == 41 and core["coll"][1] == 0 and core["coll"][2] and core["coll"][3] > 5 and core["coll"][4:] == [0, 1, 7], (core["ring"], core["coll"]))
    check("b. step() wraps both ways and survives junk; indexOf falls back to 0", core["step"] == [18, 0, 4, 1, 0, 18, 4] and core["index"] == [1, 0], (core["step"], core["index"]))
    check("b. numbers in thousands; the camera distance grows for a narrow stage and shrinks when focused, junk safe", core["fmt"] == ["1,828", "32,000", "0", "1,000"] and all(core["fit"]), (core["fmt"], core["fit"]))
    check("b. quality: auto follows the core's level, High and Lite force it, junk is auto", core["mode"] == [True, False, True, False, True, "auto", "high", "low", None], core["mode"])
    check("b. drag inertia fades and stops; a tap is short and still", core["inertia"][0] and core["inertia"][1] and core["inertia"][2] == 0 and core["inertia"][3] and core["inertia"][4] == 0 and core["tap"] == [True, False, False], (core["inertia"], core["tap"]))
    check("b. 41 drawings (one per shape, all four primitives, valid), plain words", core["glyphs"] == 41 and core["glyphIds"] == sorted(IDS) and core["glyphOK"] and core["words"][0] == "Shape 3 of 19" and core["words"][1] and core["words"][2] and core["words"][3] == 5 and core["words"][4] == ["auto", "high", "lite"], core["words"])
    gl = set(json.load(open(os.path.join(AK.WEB, APP, "fixture.json"), encoding="utf-8")) and [s["id"] for s in json.load(open(os.path.join(AK.WEB, APP, "fixture.json"), encoding="utf-8"))["shapes"]])
    lib_names = {k: v["meta"] for k, v in sh.items()}
    fx = {s["id"]: [s["name"], s["means"], s["group"]] for s in json.load(open(os.path.join(AK.WEB, APP, "fixture.json"), encoding="utf-8"))["shapes"]}
    check("b. fixture.json equals the library's names, meanings and groups for all 41 (regenerate it when a shape changes)", gl == set(IDS) and fx == lib_names, [k for k in lib_names if fx.get(k) != lib_names[k]])


# ------------------------------------------------------------------------------------------------ browser
def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    dog = threading.Timer(240, lambda: (print("[FAIL] c. the browser smoke ran over its 240 s limit", flush=True), os._exit(1)))
    dog.daemon = True
    dog.start()
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low")
            d = p.evaluate("""() => { const g = window.GALLERY3D; return ({ ok: !!(g && g.ok), info: g && g.ok ? g.info() : (g && g.reason), tiles: document.querySelectorAll('#shelf .shape').length, heads: [...document.querySelectorAll('#shelf h3')].map((h) => h.textContent),
              name: document.querySelector('#shapeName').textContent, means: document.querySelector('#shapeMeans').textContent, pos: document.querySelector('#shapePos').textContent, pressed: document.querySelectorAll('#shelf .shape[aria-pressed=true]').length,
              modes: [...document.querySelectorAll('#quality button')].map((b) => b.textContent), font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor,
              tris: document.querySelector('#tTris').textContent, hint: document.querySelector('#hint').textContent, sample: !document.querySelector('#sample').hidden }); }""")
            check("c. the 3D stage starts on the kit's render core (LITE, 2 passes), the shelf has 41 shapes in 5 categories, the first one is on the pedestal with its meaning", d["ok"] and d["info"]["lite"] and d["info"]["id"] == "doric" and d["info"]["passes"] == 2
                  and d["tiles"] == 41 and len(d["heads"]) == 5 and d["name"] == "Doric column" and "Strength" in d["means"] and d["pos"] == "Shape 1 of 41" and d["pressed"] == 1 and d["modes"] == ["Auto", "High", "Lite"] and not d["sample"], d)
            check("c. AGORA look: serif title, warm dark body; triangle count shown (LITE doric 128)", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)" and d["tris"] == "128", d)
            p.wait_for_function("document.querySelector('#stageBox').classList.contains('live')", timeout=90000)
            frames0 = p.evaluate("window.GALLERY3D.info().frames")
            p.wait_for_timeout(2500)
            fr = p.evaluate("window.GALLERY3D.info().frames")
            check("c. the stage draws frames (the 2D drawing fades away once 3D is live)", fr > frames0 >= 1, (frames0, fr))
            AK.shot(p, "gallery-doric")
            p.locator("#next").click()
            p.wait_for_timeout(300)
            n = p.evaluate("() => [document.querySelector('#shapeName').textContent, window.GALLERY3D.info().id, document.querySelector('#shapePos').textContent, document.querySelector('#status').textContent]")
            check("c. the next button shows the Ionic column (name, meaning spoken in the status line)", n[0] == "Ionic column" and n[1] == "ionic" and n[2] == "Shape 2 of 41" and "Learning" in n[3], n)
            p.locator("#prev").click()
            p.locator("#prev").click()
            p.wait_for_timeout(300)
            check("c. previous wraps around to the last shape (the lighthouse)", p.evaluate("document.querySelector('#shapeName').textContent") == "Lighthouse of Pharos", p.evaluate("document.querySelector('#shapeName').textContent"))
            p.locator("#shelf .shape[data-id=owl]").click()
            p.wait_for_timeout(500)
            o = p.evaluate("() => [document.querySelector('#shapeName').textContent, window.GALLERY3D.info().id, window.GALLERY3D.info().focus, document.querySelector('#focusBtn').getAttribute('aria-pressed'), document.querySelector('#shelf .shape[aria-pressed=true]').dataset.id]")
            check("c. tap a shelf tile: the owl is on the pedestal and in focus (camera in), the tile is marked", o == ["Athena's owl", "owl", True, "true", "owl"], o)
            AK.shot(p, "gallery-owl")
            a0 = p.evaluate("window.GALLERY3D.info().yaw")
            box = p.locator("#stage").bounding_box()
            p.mouse.move(box["x"] + 80, box["y"] + box["height"] / 2)
            p.mouse.down()
            p.mouse.move(box["x"] + 200, box["y"] + box["height"] / 2, steps=6)
            p.mouse.up()
            p.wait_for_timeout(200)
            a1 = p.evaluate("window.GALLERY3D.info()")
            check("c. dragging across the stage turns the pedestal (yaw moved), and a drag is not a tap (focus unchanged)", abs(a1["yaw"] - a0) > 0.5 and a1["focus"] is True, (a0, a1["yaw"], a1["focus"]))
            p.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            p.wait_for_timeout(200)
            check("c. a tap on the stage steps back out of the close-up (focus off, button text back)", p.evaluate("() => [window.GALLERY3D.info().focus, document.querySelector('#focusBtn').textContent]") == [False, "Look closer"])
            p.locator("#focusBtn").click()
            p.wait_for_timeout(150)
            check("c. the Look closer button toggles the focus again", p.evaluate("window.GALLERY3D.info().focus") is True)
            p.locator("#quality [data-mode=high]").click()
            p.wait_for_timeout(600)
            q = p.evaluate("() => [window.GALLERY3D.info().lite, window.GALLERY3D.info().mode, window.GALLERY3D.info().level, document.querySelector('#quality [aria-pressed=true]').textContent, document.querySelector('#tTris').textContent]")
            check("c. quality High: the HD build (no longer lite), the render core on the high tier, the owl's HD triangle count shown", q[0] is False and q[1] == "high" and q[2] == "high" and q[3] == "High" and q[4] != "-" and int(q[4].replace(",", "")) > 1000, q)
            p.locator("#quality [data-mode=lite]").click()
            p.wait_for_timeout(600)
            q = p.evaluate("() => [window.GALLERY3D.info().lite, window.GALLERY3D.info().level, document.querySelector('#quality [aria-pressed=true]').textContent, document.querySelector('#lite').hidden, document.querySelector('#qualityNote').textContent]")
            check("c. quality Lite: the low-poly build, the render core on the low tier, the LITE tag shows, plain words under the buttons", q[0] is True and q[1] == "low" and q[2] == "Lite" and q[3] is False and "Lite" in q[4], q)
            p.locator("#focusBtn").click()
            ids = p.evaluate("() => window.GALLERY.S.items.map((s) => s.id)")
            for i in range(len(ids)):
                p.evaluate("(i) => window.GALLERY.select(i, false)", i)
                p.wait_for_timeout(60)
            last = p.evaluate("() => [window.GALLERY3D.info().id, window.GALLERY3D.info().last.tris, window.GALLERY3D.info().last.draws]")
            check("c. all 41 shapes put on the pedestal in LITE one after another with no error (last: the lighthouse, within the LITE budget)", last[0] == "lighthouse" and last[1] <= 2400 and last[2] <= 26 and not errs, (last, errs[:3]))
            # ---- category chips
            p.locator("#cats [data-cat=Money]").click()
            p.wait_for_timeout(150)
            ch = p.evaluate("() => [[...document.querySelectorAll('#shelf section')].filter((s) => !s.hidden).map((s) => s.querySelector('h3').textContent), document.querySelectorAll('#cats button').length, document.querySelector('#cats [aria-pressed=true]').dataset.cat, window.GALLERY3D.info().id]")
            p.locator("#next").click()
            p.wait_for_timeout(150)
            nx = p.evaluate("() => window.GALLERY3D.info().id")
            p.locator("#cats [data-cat=All]").click()
            p.wait_for_timeout(100)
            check("c. category chips: Money shows only the Money shelf (6 chips: All + 5), the pedestal jumps to its first shape, next stays inside the category, All brings the 5 sections back",
                  ch == [["Money"], 6, "Money", "coinstack"] and nx == "scales" and p.evaluate("() => [...document.querySelectorAll('#shelf section')].filter((s) => !s.hidden).length") == 5, (ch, nx))
            # ---- scene builder
            p.evaluate("Object.defineProperty(navigator, 'clipboard', { value: { writeText: (t) => { window.__copied = t; return Promise.resolve(); } }, configurable: true })")
            p.locator("#views [data-view=build]").click()
            for sid in ("owl", "temple", "lyre"):
                p.locator(f"#shelf .shape[data-id={sid}]").click()
            p.wait_for_timeout(400)
            b = p.evaluate("""() => ({ view: window.GALLERY3D.info().view, ids: window.GALLERY3D.info().build.ids, draws: window.GALLERY3D.info().build.draws, tris: window.GALLERY3D.info().build.tris, chips: document.querySelectorAll('#picked button').length,
              count: document.querySelector('#buildCount').textContent, card: !document.querySelector('#buildCard').hidden, info: document.querySelector('#infoCard').hidden, pressed: document.querySelector('#views [aria-pressed=true]').dataset.view, marked: document.querySelectorAll('#shelf .shape[data-picked="1"]').length })""")
            check("c. scene builder: Build tab on, tap the owl, the temple and the lyre -> three shapes on the ring (LITE: under 3 x 26 + pedestal draw calls), three chips, '3 of 6', the shelf marks them, the shape card is out of the way",
                  b["view"] == "build" and b["ids"] == ["owl", "temple", "lyre"] and 0 < b["draws"] <= 3 * 26 + 3 and b["tris"] > 500 and b["chips"] == 3 and "3 of 6" in b["count"] and b["card"] and b["info"] and b["pressed"] == "build" and b["marked"] == 3, b)
            p.locator("#buildShare").click()
            p.wait_for_timeout(300)
            sh = p.evaluate("() => ({ copied: window.__copied, box: document.querySelector('#shareUrl').value, shown: !document.querySelector('#shareUrl').hidden, hash: location.hash, origin: location.origin, note: document.querySelector('#buildNote').textContent })")
            check("c. Share copies the full link ending in #b=owl,temple,lyre, shows it in a box too, and the address bar carries the same #hash", sh["copied"] == sh["origin"] + "/gallery/?demo=1&q=low#b=owl,temple,lyre" and sh["box"] == sh["copied"] and sh["shown"] and sh["hash"] == "#b=owl,temple,lyre" and "copied" in sh["note"].lower(), sh)
            for sid in ("doric", "ionic", "harp", "bust"):
                p.locator(f"#shelf .shape[data-id={sid}]").click()
            full = p.evaluate("() => [window.GALLERY3D.info().build.ids.length, document.querySelector('#status').textContent]")
            p.locator("#picked button").first.click()
            one = p.evaluate("() => [window.GALLERY3D.info().build.ids, location.hash]")
            p.locator("#buildClear").click()
            p.wait_for_timeout(150)
            clr = p.evaluate("() => [window.GALLERY3D.info().build.ids.length, document.querySelector('#buildShare').disabled, document.querySelector('#picked').children.length]")
            check("c. a 7th shape is refused with plain words (the limit is 6), tapping a chip takes one out and updates the link, Clear empties the scene and disables Share",
                  full[0] == 6 and "most a scene holds" in full[1] and one[0] == ["temple", "lyre", "doric", "ionic", "harp"] and one[1] == "#b=temple,lyre,doric,ionic,harp" and clr == [0, True, 0], (full, one, clr))
            # ---- the collection
            p.locator("#views [data-view=collection]").click()
            p.wait_for_function("window.GALLERY3D.info().collection", timeout=60000)
            p.wait_for_timeout(500)
            co = p.evaluate("() => ({ c: window.GALLERY3D.info().collection, text: document.querySelector('#collCount').textContent, card: !document.querySelector('#collCard').hidden, hash: location.hash, name: document.querySelector('#collName').textContent, open: document.querySelector('#collOpen').disabled })")
            check("c. collection: all 41 shapes in one scene, each baked into one draw call (<= 42 draw calls, < 40,000 triangles), the words say so, nothing picked yet, no #hash",
                  co["c"]["count"] == 41 and co["c"]["draws"] <= 42 and co["c"]["tris"] < 40000 and "41 shapes" in co["text"] and co["card"] and co["hash"] == "" and co["name"] == "Tap a shape." and co["open"], co)
            pos = p.evaluate("window.GALLERY3D.projectCollection('owl')")
            p.mouse.click(pos["x"], pos["y"])
            p.wait_for_timeout(250)
            pk = p.evaluate("() => ({ pick: window.GALLERY.S.pick, name: document.querySelector('#collName').textContent, means: document.querySelector('#collMeans').textContent.length, open: document.querySelector('#collOpen').disabled })")
            check("c. tap a shape in the collection: it is named with what it stands for, and 'Show on the pedestal' opens", bool(pk["pick"]) and pk["name"].endswith(".") and pk["means"] > 20 and not pk["open"], pk)
            p.locator("#collOpen").click()
            p.wait_for_timeout(400)
            op = p.evaluate("() => [window.GALLERY3D.info().view, window.GALLERY3D.info().id, window.GALLERY.S.items[window.GALLERY.S.i].id, document.querySelector('#views [aria-pressed=true]').dataset.view]")
            check("c. 'Show on the pedestal' goes back to the Shelf view with that shape in focus", op[0] == "shelf" and op[1] == op[2] == pk["pick"] and op[3] == "shelf", (op, pk["pick"]))
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (tabs, chips, arrows, quality buttons, tiles, Share, Clear)", not t, t[:6])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            # ---- a shared link restores the scene
            ctx, p, errs, seen, off = AK.page(br, origin, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low#b=owl,temple,lyre,nope")
            hr = p.evaluate("() => [window.GALLERY.S.view, window.GALLERY3D.info().view, window.GALLERY3D.info().build.ids, document.querySelector('#views [aria-pressed=true]').dataset.view, document.querySelectorAll('#picked button').length, location.hash]")
            check("c. opening a shared #b=owl,temple,lyre,nope link restores the scene (the unknown shape is dropped): Build tab, three shapes, three chips", hr == ["build", "build", ["owl", "temple", "lyre"], "build", 3, "#b=owl,temple,lyre"], hr)
            check("c. the restored page has no console error and reads only its own files", not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            # ---- OLYMPUS_SHAPES.mount: the one-liner and its flat fallback
            ctx, p, errs, seen, off = AK.page(br, origin, lite=True)
            p.goto(f"{origin}/olympus/shapes-demo.html?q=low")
            p.wait_for_function("window.__done === true", timeout=90000)
            p.wait_for_timeout(2500)
            m = p.evaluate("() => ({ mounts: window.__mounts.map((x) => [x.ok, x.id, x.flat]), canvases: [...document.querySelectorAll('.spot')].map((e) => e.querySelectorAll('canvas').length), h: [...document.querySelectorAll('.spot canvas')].map((c) => c.clientHeight), api: Object.keys(window.OLYMPUS_SHAPES).sort(), n: window.OLYMPUS_SHAPES.ids.length })")
            check("c. OLYMPUS_SHAPES.mount: three one-line mounts on the demo page (owl, pillar chart with values, amphora) all run in 3D, one canvas each, filling their 220 px spots; the API lists 41 shapes",
                  m["mounts"] == [[True, "owl", False], [True, "pillarbar", False], [True, "amphora", False]] and m["canvases"] == [1, 1, 1] and all(x >= 200 for x in m["h"]) and m["n"] == 41 and {"mount", "ids", "shapes", "build", "bake", "bakedShape", "materials"} <= set(m["api"]), m)
            try:
                import io
                from PIL import Image
                im = Image.open(io.BytesIO(p.locator("#s1").screenshot())).convert("RGB").resize((60, 60))
                colours = len(im.getcolors(maxcolors=100000) or [])
                check("c. the mounted owl actually draws something (the spot is not a flat colour)", colours > 25, colours)
            except ImportError:
                check("c. pixel check skipped: no PIL", True)
            p.evaluate("window.__mounts[0].set('lyre'); window.__mounts[2].stop()")
            p.wait_for_timeout(300)
            m2 = p.evaluate("() => [window.__mounts[0].id, document.querySelectorAll('#s3 canvas').length, document.querySelectorAll('#s1 canvas').length]")
            check("c. mount().set('lyre') swaps the shape and stop() frees the canvas; no console error; nothing off the origin", m2 == ["lyre", 0, 1] and not errs and not off, (m2, errs[:3], off[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, lite=True)
            p.goto(f"{origin}/olympus/shapes-demo.html?flat=1")
            p.wait_for_function("window.__done === true", timeout=60000)
            fl = p.evaluate("() => ({ mounts: window.__mounts.map((x) => [x.ok, x.flat]), canvases: document.querySelectorAll('canvas').length, svgs: [...document.querySelectorAll('.spot svg')].map((s) => [s.getAttribute('role'), s.getAttribute('aria-label').length > 30, s.children.length >= 3]) })")
            check("c. mount() with no WebGL (?flat=1): every spot gets the shape's 2D drawing with an accessible name, no canvas, no error - never blank",
                  fl["mounts"] == [[False, True]] * 3 and fl["canvases"] == 0 and fl["svgs"] == [["img", True, True]] * 3 and not errs, fl)
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&flat=1&shape=lyre")
            f = p.evaluate("""() => ({ ok: !!(window.GALLERY3D && window.GALLERY3D.ok), reason: window.GALLERY3D && window.GALLERY3D.reason, name: document.querySelector('#shapeName').textContent, svg: document.querySelector('#flatSvg').children.length,
              flatOn: getComputedStyle(document.querySelector('#flat')).opacity, tiles: document.querySelectorAll('#shelf .shape').length, hint: document.querySelector('#hint').textContent, note: document.querySelector('#qualityNote').textContent, tris: document.querySelector('#tTris').textContent })""")
            check("c. 2D fallback (?flat=1, 375 x 667, reduced motion): 3D is off, yet the Lyre is named with its drawing, 41 tiles, a plain explanation - never blank", not f["ok"] and f["reason"] == "flat" and f["name"] == "Lyre of Apollo" and f["svg"] >= 4 and f["flatOn"] == "1" and f["tiles"] == 41
                  and "drawing" in f["hint"] and "could not start 3D" in f["note"] and f["tris"] == "-", f)
            p.locator("#next").click()
            p.locator("#shelf .shape[data-id=temple]").click()
            f2 = p.evaluate("() => [document.querySelector('#shapeName').textContent, document.querySelector('#flatSvg').children.length, document.querySelector('#focusBtn').getAttribute('aria-pressed')]")
            check("c. in the fallback the shelf, arrows and Look closer still work (a tile tap picks the Temple, shows its drawing and focuses)", f2[0] == "Temple" and f2[1] >= 4 and f2[2] == "true", f2)
            check("c. fallback: no sideways scroll, taps >= 44 px, no console error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        dog.cancel()
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_node()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
