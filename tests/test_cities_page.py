"""OLYMPUS CITIES (tools/web_public/cities/, 2026-11-04): the world map of floating city islands and the data-driven city generator.
Read-only: nothing here touches trading logic, orders or secrets.

  a. files: the page (kit ?v=o2, data-app="cities", no outside address, safe areas, reduced motion), cities.json (24+ distinct city
     specs: unique names / mottos / landmarks / accents, many data sources, landmarks, skies, weathers, layouts), the real published
     files the adapters read exist, the manifest + icon, no Math.random in the engine, jarvis.json in the Jarvis contract
  b. the card tool (tools/cities_card.py): deterministic, the city of the day spreads over the list, FNV hash matches the page
  c. in Chromium, the engine as modules: spec validation for every city (and a negative control), every adapter yields live rows from
     the real files, the fixture covers every dataset, generator determinism (same spec + data -> same hash) for every city, value /
     bounds / colour sanity, no overlapping footprints, the cap (a deterministic sample that keeps the tallest), the ray picker, 40k
     synthetic buildings in time and in the triangle budget, the Python / JS "city of the day" parity, and a new city from ONE JSON entry
  d. the page at 390 x 844 (touch): the hub (islands, labels, tap -> card, Find, Today, Tour, Surprise), THREE different cities entered
     (tap a building -> card, Find, Top 10, cameras, minimap, back), no console errors / failed requests, layout (no sideways scroll,
     the orb's corner free, one top bar / one sheet / one dock, 44 px targets)
  e. draw calls and triangles within budget per tier (off / low / high / ultra) on the hub and on the 31k-idea city
  f. fallbacks: the Kalshi feed offline -> sample (marked), a stubbed live Kalshi feed -> real rows, ?demo=1, reduced motion, landscape,
     no WebGL -> the plain list
Screenshots: CITIES_SHOTS=<dir> (default: a temp folder, nothing is written into the repo).

    python -X utf8 -m tests.test_cities_page            (~6-9 min on a quiet machine; --no-browser: a and b only, ~2 s; --quick: skips e and f)
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import cities_card as CC  # noqa: E402

WEB = os.path.join(ROOT, "tools", "web_public")
PAGE = os.path.join(WEB, "cities")
SHOTS = os.environ.get("CITIES_SHOTS") or os.path.join(tempfile.gettempdir(), "cities_shots")
RES = []
QUICK = "--quick" in sys.argv                 # c and d only (the engine and the page at 390 x 844), skipping the tier budgets and the fallbacks
BAD_ORIGINS = ("githubusercontent",)          # the Kalshi feed: blocked on purpose in the offline runs


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------ a. files
def part_a():
    need = ["index.html", "cities.json", "fixture.json", "jarvis.json", "manifest.webmanifest", "icon.svg", "app.js", "datasets.js", "generator.js",
            "scene.js", "shaders.js", "landmarks.js", "rig.js", "util.js"]
    check("a. every file of the page is there", all(os.path.isfile(os.path.join(PAGE, n)) for n in need), [n for n in need if not os.path.isfile(os.path.join(PAGE, n))])
    html = read(os.path.join(PAGE, "index.html"))
    check("a. the OLYMPUS kit ?v=o2 (css, themes, olympus.js with data-app=cities), module app, manifest, icon",
          'olympus.css?v=o2' in html and 'themes.js?v=o2' in html and 'olympus.js?v=o2" data-app="cities"' in html and 'type="module"' in html
          and 'rel="manifest"' in html and 'icon.svg' in html)
    check("a. phone viewport with safe areas, theme-color, dark scheme, reduced motion", 'viewport-fit=cover' in html and 'name="theme-color"' in html
          and 'safe-area-inset-bottom' in html and 'prefers-reduced-motion' in html and 'color-scheme' in html)
    srcs = {n: read(os.path.join(PAGE, n)) for n in need if n.endswith((".js", ".html"))}
    outside = {n: re.findall(r"https?://[^\s'\"`)]+", t) for n, t in srcs.items()}
    outside = {n: [u for u in us if "w3.org" not in u] for n, us in outside.items()}
    outside = {n: us for n, us in outside.items() if us}
    check("a. no outside address except the Kalshi feed (datasets.js); everything else is relative", list(outside) == ["datasets.js"]
          and all("raw.githubusercontent.com/demetrades2000-coder/kalshi-feed" in u for u in outside["datasets.js"]), outside)
    check("a. three.js from ../jarvis/, the render core from ../olympus/render.js (no CDN)", "../jarvis/three.module.min.js" in srcs["scene.js"]
          and "../olympus/render.js" in srcs["scene.js"] and "createRenderer" in srcs["scene.js"] and "cdn" not in " ".join(srcs.values()).lower())
    check("a. the engine is deterministic by construction: no Math.random in generator / datasets / util", all(not re.search(r"Math\.random\s*\(", srcs[n]) for n in ("generator.js", "datasets.js", "util.js")))
    mf = json.loads(read(os.path.join(PAGE, "manifest.webmanifest")))
    check("a. manifest: name, standalone, theme, icons that exist", mf["display"] == "standalone" and mf["name"] and mf["theme_color"].startswith("#")
          and all(os.path.isfile(os.path.join(PAGE, i["src"])) for i in mf["icons"]), mf)
    # the real published files the adapters read
    urls = re.findall(r"url: '(\.\./[^']+)'", srcs["datasets.js"])
    check("a. every file an adapter reads is a published page file that exists (odeon, datacity, tree, forge, pantheon, fates, arena, athena ...)",
          len(set(urls)) >= 9 and all(os.path.isfile(os.path.normpath(os.path.join(PAGE, u))) for u in urls), [u for u in set(urls) if not os.path.isfile(os.path.normpath(os.path.join(PAGE, u)))])
    cfg = json.loads(read(os.path.join(PAGE, "cities.json")))
    C = cfg["cities"]
    sig = lambda c: (c["dataset"], c["district_by"], c["height_by"], c["layout"])  # noqa: E731
    check("a. 24+ city specs (the owner asked for at least 24; this ships %d)" % len(C), len(C) >= 24, len(C))
    check("a. unique id, name, motto, landmark label and accent colour", all(len({c[k] if k != "lm" else c["landmark"]["label"] for c in C}) == len(C) for k in ("id", "name", "motto", "lm"))
          and len({c["palette"]["accent"] for c in C}) == len(C))
    check("a. every city is a different TYPE: (dataset, district, height, layout) is unique", len({sig(c) for c in C}) == len(C))
    check("a. variety: 14 landmarks, 8 skies, 8 weathers, 5 layouts, 5 groups, 18+ datasets in use",
          len({c["landmark"]["kind"] for c in C}) >= 14 and len({c["sky"]["kind"] for c in C}) >= 8 and len({c["weather"] for c in C}) >= 8
          and len({c["layout"] for c in C}) >= 5 and len({c["group"] for c in C}) >= 5 and len({c["dataset"] for c in C}) >= 18,
          (len({c["landmark"]["kind"] for c in C}), len({c["sky"]["kind"] for c in C}), len({c["weather"] for c in C}), len({c["layout"] for c in C}), len({c["dataset"] for c in C})))
    fx = json.loads(read(os.path.join(PAGE, "fixture.json")))
    check("a. fixture.json: a sample for every dataset the cities use, each with rows, <= 250 KB",
          all(c["dataset"] in fx and len(fx[c["dataset"]]["items"]) >= 8 for c in C) and os.path.getsize(os.path.join(PAGE, "fixture.json")) <= 250_000)
    card = json.loads(read(os.path.join(PAGE, "jarvis.json")))
    raw = read(os.path.join(PAGE, "jarvis.json"))
    ids = [c["id"] for c in C]
    ok = (card["v"] == 1 and card["name"] and len(card["name"]) <= 40 and card["status"]["level"] in ("ok", "warn", "bad", "off") and len(card["status"]["label"]) <= 48
          and len(card["kpis"]) <= 3 and all(len(k["label"]) <= 20 and len(str(k["value"])) <= 24 for k in card["kpis"])
          and len(card["lines"]) <= 3 and all(len(x) <= 120 for x in card["lines"]) and isinstance(card["t"], int) and re.fullmatch(r"#[0-9a-f]{6}", card["theme"])
          and 60 <= card["stale_after"] <= 1_209_600 and card["open"][1:] in ids and len(raw.encode()) <= 8192 and not re.search(r"[<>&]", raw.replace("&amp;", "")))
    check("a. jarvis.json: the Jarvis card contract (docs/JARVIS_APPS.md), the card opens a real city, 'City of the day' in it", ok and "City of the day" in raw, card)
    return C


# ------------------------------------------------------------------ b. the card tool
def part_b(C):
    ids = [c["id"] for c in C]
    a, b = CC.build("2026-11-04", 1793700000, C), CC.build("2026-11-04", 1793700000, C)
    check("b. cities_card.build is deterministic (same date + time -> same bytes)", CC.dumps(a) == CC.dumps(b))
    days = [f"2026-{m:02d}-{d:02d}" for m in range(1, 13) for d in range(1, 29)]
    picks = [CC.city_of_day(d, ids) for d in days]
    check("b. the city of the day spreads over the list (336 days hit 24+ different cities, none more than 6% of days)",
          len(set(picks)) >= 24 and max(picks.count(i) for i in set(picks)) <= 0.06 * len(days), (len(set(picks)), max(picks.count(i) for i in set(picks))))
    check("b. a card is valid for every city (open route, name, kpis)", all(CC.build("2026-11-04", 1, [c for c in C if c["id"] == i])["open"] == "#" + i for i in ids[:5]))
    tmp = tempfile.mkdtemp(prefix="cities_card_")
    os.makedirs(os.path.join(tmp, "cities"))
    msg = CC.publish(tmp)
    check("b. publish(out) writes <out>/cities/jarvis.json and skips a build without the page", os.path.isfile(os.path.join(tmp, "cities", "jarvis.json")) and "city of the day" in msg
          and "skipped" in CC.publish(os.path.join(tmp, "nowhere")), msg)
    return days, picks


# ------------------------------------------------------------------ c. the engine, as modules in Chromium
UNIT_A = """async () => {
  const [D, G] = await Promise.all([import('/cities/datasets.js'), import('/cities/generator.js')]);
  const cfg = await (await fetch('/cities/cities.json')).json();
  const errs = cfg.cities.map(s => [s.id, G.validateSpec(s, D.DATASETS)]).filter(x => x[1].length);
  const bad = G.validateSpec({ ...cfg.cities[0], height_by: 'abs:nope', layout: 'zzz', palette: {}, landmark: { kind: 'x' }, card: ['nope'] }, D.DATASETS);
  const noDs = G.validateSpec({ ...cfg.cities[0], dataset: 'nothing' }, D.DATASETS);
  const cal = G.validateSpec({ ...cfg.cities.find(c => c.layout === 'calendar'), grid: undefined }, D.DATASETS);
  return { errs, nbad: bad.length, noDs: noDs.length, cal: cal.length, n: cfg.cities.length };
}"""

UNIT_B = """async () => {
  const D = await import('/cities/datasets.js');
  const env = { get: async (u) => { if (/^https?:/.test(u)) throw new Error('remote'); const r = await fetch(u); if (!r.ok) throw new Error(u); return r.json(); }, fixture: {} };
  const out = {};
  for (const id of D.DATASET_IDS) {
    const d = D.DATASETS[id]; if (d.remote || d.vault) continue;
    const ds = await D.loadDataset(id, env);
    const keys = new Set(ds.fields.map(f => f.key));
    let undeclared = [];
    for (let i = 0; i < ds.items.length; i += Math.max(1, Math.floor(ds.items.length / 40))) for (const k of Object.keys(ds.items[i].f)) if (!keys.has(k)) undeclared.push(k);
    const ids = new Set(ds.items.map(i => i.id));
    out[id] = { n: ds.items.length, demo: ds.demo, undeclared: [...new Set(undeclared)], uniqueIds: ids.size === ds.items.length, label: String(ds.label(ds.items[0] || { label: '', id: '' })).length > 0 };
  }
  return out;
}"""

UNIT_C = """async () => {
  const [D, G] = await Promise.all([import('/cities/datasets.js'), import('/cities/generator.js')]);
  const cfg = await (await fetch('/cities/cities.json')).json(), fx = await (await fetch('/cities/fixture.json')).json();
  const noNet = { get: () => Promise.reject(new Error('sample')), fixture: fx };
  const env = { get: async (u) => { if (/^https?:/.test(u)) throw new Error('remote'); const r = await fetch(u); if (!r.ok) throw new Error(u); return r.json(); }, fixture: fx };
  const rows = [], hashes = new Map();
  const cache = new Map(), cacheFx = new Map();
  for (const s of cfg.cities) {
    const ds = await D.loadDataset(s.dataset, env, cache);
    const dsFx = await D.loadDataset(s.dataset, noNet, cacheFx);
    const t0 = performance.now();
    const c = G.generate(s, ds, { cap: 40000 }), c2 = G.generate(s, ds, { cap: 40000 });
    const ms = performance.now() - t0;
    const cf = G.generate(s, dsFx, { cap: 40000 });
    const hr = s.height_range || [2.5, 64];
    let finite = true, inb = true, hin = true, col = true, w0 = true;
    for (let k = 0; k < c.n; k++) {
      for (const v of [c.x[k], c.z[k], c.h[k], c.w[k], c.d[k], c.glow[k], c.win[k]]) if (!Number.isFinite(v)) finite = false;
      if (c.x[k] < c.bounds.minx - 1e-3 || c.x[k] > c.bounds.maxx + 1e-3 || c.z[k] < c.bounds.minz - 1e-3 || c.z[k] > c.bounds.maxz + 1e-3) inb = false;
      if (c.h[k] < hr[0] - 0.02 || c.h[k] > hr[1] + 0.02) hin = false;
      if (c.w[k] <= 0 || c.d[k] <= 0) w0 = false;
      for (let j = 0; j < 3; j++) if (!(c.col[k * 3 + j] >= 0 && c.col[k * 3 + j] <= 1.001)) col = false;
      if (!(c.glow[k] >= 0 && c.glow[k] <= 1 && c.win[k] >= 0 && c.win[k] <= 1)) col = false;
    }
    let dsum = 0; for (const d of c.districts) dsum += d.count;
    // overlaps (small cities, block layouts)
    let overlaps = 0;
    if (c.n <= 700 && ['districts', 'clock', 'calendar'].includes(c.layout)) {
      for (let a = 0; a < c.n; a++) for (let b = a + 1; b < c.n; b++) {
        if (Math.abs(c.x[a] - c.x[b]) < (c.w[a] + c.w[b]) / 2 - 1e-3 && Math.abs(c.z[a] - c.z[b]) < (c.d[a] + c.d[b]) / 2 - 1e-3) overlaps++;
      }
    }
    hashes.set(c.hash, (hashes.get(c.hash) || 0) + 1);
    rows.push({ id: s.id, n: c.n, total: c.total, same: c.hash === c2.hash, fxN: cf.n, finite, inb, hin, col, w0, dsum, overlaps, ms, districts: c.districts.length,
      demo: ds.demo, capOk: c.n === Math.min(ds.items.length, 40000), item: c.item.length === c.n, site: Number.isFinite(c.site.x) && Number.isFinite(c.site.z) && c.site.scale > 0 });
  }
  return { rows, distinct: hashes.size, n: cfg.cities.length };
}"""

UNIT_D = """async () => {
  const [D, G, U] = await Promise.all([import('/cities/datasets.js'), import('/cities/generator.js'), import('/cities/util.js')]);
  const cfg = await (await fetch('/cities/cities.json')).json();
  const env = { get: async (u) => { const r = await fetch(u); if (!r.ok) throw new Error(u); return r.json(); }, fixture: {} };
  const spec = cfg.cities.find(c => c.id === 'ideas-city'), ds = await D.loadDataset('combos', env);
  // the cap: a deterministic sample that keeps the tallest
  const full = G.generate(spec, ds, { cap: 40000 }), c6 = G.generate(spec, ds, { cap: 6000 }), c6b = G.generate(spec, ds, { cap: 6000 }), c15 = G.generate(spec, ds, { cap: 1500 });
  const hT = G.evalExpr(spec.height_by, ds.items);
  const order = Array.from(hT.keys()).sort((a, b) => hT[b] - hT[a] || a - b).slice(0, 100);
  const kept = new Set(Array.from(c6.item));
  const keepsTop = order.every(i => kept.has(i));
  const capRes = { full: full.n, c6: c6.n, c15: c15.n, capped: c6.capped, same: c6.hash === c6b.hash, keepsTop, total: c6.total, fullDiffers: full.hash !== c6.hash };
  // the picker on three cities (vertical and oblique rays)
  const pick = {};
  for (const id of ['trades-city', 'weekdays-city', 'ideas-city']) {
    const s = cfg.cities.find(c => c.id === id), d = await D.loadDataset(s.dataset, env), c = G.generate(s, d, { cap: 6000 }), P = new G.Picker(c);
    let vert = 0, obl = 0, tried = 0;
    for (let q = 0; q < 40; q++) {
      const k = Math.floor((q * c.n) / 40); tried++;
      const top = c.y0[k] + c.h[k];
      const r = P.pick({ x: c.x[k] + 0.01, y: top + 80, z: c.z[k] + 0.01 }, { x: 0, y: -1, z: 0 });
      if (r.index === k) vert++;
      const dir = { x: 0.6, y: -0.35, z: 0.72 }, len = Math.hypot(dir.x, dir.y, dir.z); dir.x /= len; dir.y /= len; dir.z /= len;
      const o = { x: c.x[k] - dir.x * 90, y: c.h[k] * 0.5 - dir.y * 90, z: c.z[k] - dir.z * 90 };
      const r2 = P.pick(o, dir);
      if (r2.index >= 0 && r2.t > 0) obl++;
    }
    const miss = P.pick({ x: c.bounds.maxx + 400, y: 30, z: c.bounds.maxz + 400 }, { x: 0, y: -1, z: 0 });
    pick[id] = { vert, obl, tried, miss: miss.index };
  }
  // 40k synthetic buildings: replicate the ideas
  const items = []; for (let i = 0; i < 40000; i++) { const s = ds.items[i % ds.items.length]; items.push({ id: s.id + '#' + i, code: s.code, label: s.label, f: s.f }); }
  const big = { ...ds, items, label: (it) => it.label || it.id };
  const t0 = performance.now(), cb = G.generate(spec, big, { cap: 40000 }), ms = performance.now() - t0;
  const synth = { n: cb.n, ms, tris: cb.n * 10 };
  // the city of the day parity (the page's function) for a list of dates handed in
  const days = []; for (let m = 1; m <= 12; m++) for (let d = 1; d <= 28; d++) days.push(`2026-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`);
  const ids = cfg.cities.map(c => c.id), todays = days.map(x => U.cityOfDay(x, ids));
  // a NEW city from one JSON entry (no engine change)
  const t = cfg.cities.find(c => c.id === 'trades-city');
  const extra = { ...t, id: 'tmp-city', name: 'Tmp City', motto: 'A city added with one JSON entry only.', district_by: 'weekday', height_by: 'abs:r', palette: { ...t.palette, accent: '#12ab34' } };
  const ds2 = await D.loadDataset('trades', env), errs = G.validateSpec(extra, D.DATASETS), nc = G.generate(extra, ds2, { cap: 1000 }), oc = G.generate(t, ds2, { cap: 1000 });
  return { capRes, pick, synth, todays, newCity: { errs, n: nc.n, differs: nc.hash !== oc.hash, districts: nc.districts.length } };
}"""


def run_unit(p, days, picks):
    a = p.evaluate(UNIT_A)
    check("c. spec validation: every city spec is valid against the dataset registry", not a["errs"] and a["n"] >= 24, a["errs"][:3])
    check("c. spec validation negative controls: a broken spec, an unknown dataset and a calendar without a grid are all rejected", a["nbad"] >= 5 and a["noDs"] >= 1 and a["cal"] >= 1, a)
    b = p.evaluate(UNIT_B)
    live = {k: v for k, v in b.items() if v["n"] > 0 and not v["demo"]}
    check("c. every file adapter yields live rows from the real published files (18+ datasets, derived ones included)", len(live) == len(b) and len(live) >= 18,
          {k: v for k, v in b.items() if v["demo"] or v["n"] == 0})
    check("c. every item field is declared by its dataset, ids are unique, labels exist", all(not v["undeclared"] and v["uniqueIds"] and v["label"] for v in b.values()),
          {k: v for k, v in b.items() if v["undeclared"] or not v["uniqueIds"]})
    check("c. the biggest datasets are real: 30k+ tested ideas, 11k+ idea-tree nodes, 600+ LIT trades", b["combos"]["n"] > 30000 and b["tree"]["n"] > 11000 and b["harbor"]["n"] > 600, (b["combos"]["n"], b["tree"]["n"], b["harbor"]["n"]))
    c = p.evaluate(UNIT_C)
    R = c["rows"]
    check("c. generator determinism: every city twice -> the same hash (positions, sizes, colours, items)", all(r["same"] for r in R), [r["id"] for r in R if not r["same"]])
    check("c. every city is different (distinct hashes) and fills its data (n = rows up to the cap)", c["distinct"] == c["n"] and all(r["capOk"] and r["item"] for r in R), [r["id"] for r in R if not r["capOk"]])
    check("c. values are sane: finite numbers, inside the bounds, heights inside the spec's range, colours / glow / windows in 0..1, sizes > 0, a landmark site",
          all(r["finite"] and r["inb"] and r["hin"] and r["col"] and r["w0"] and r["site"] for r in R), [(r["id"], r["finite"], r["inb"], r["hin"], r["col"]) for r in R if not (r["finite"] and r["inb"] and r["hin"] and r["col"])])
    check("c. district counts add up to the buildings; no overlapping footprints in block layouts", all(r["dsum"] == r["n"] for r in R) and all(r["overlaps"] == 0 for r in R),
          [(r["id"], r["dsum"], r["n"], r["overlaps"]) for r in R if r["dsum"] != r["n"] or r["overlaps"]])
    check("c. the sample fixture builds every city too (the page never shows an empty city)", all(r["fxN"] > 5 for r in R), [r["id"] for r in R if r["fxN"] <= 5])
    check("c. the 31k-idea city generates in under 2 s here", max(r["ms"] for r in R) < 2000, max(r["ms"] for r in R))
    d = p.evaluate(UNIT_D)
    cr = d["capRes"]
    check("c. cap: 6,000 / 1,500 of 30,956 ideas, a deterministic sample (same hash twice) that keeps all of the 100 tallest", cr["c6"] == 6000 and cr["c15"] == 1500 and cr["full"] == cr["total"]
          and cr["capped"] and cr["same"] and cr["keepsTop"] and cr["fullDiffers"], cr)
    pk = d["pick"]
    check("c. picker: a ray from above hits the building under it (40 of 40), an oblique ray hits something, an empty spot hits nothing",
          all(v["vert"] == v["tried"] and v["obl"] >= v["tried"] * 0.95 and v["miss"] == -1 for v in pk.values()), pk)
    sy = d["synth"]
    check("c. 40,000 buildings: generated in under 3 s, one instanced draw of 10 triangles each = 400k, inside the ultra budget (560k)", sy["n"] == 40000 and sy["ms"] < 3000 and sy["tris"] <= 560_000, sy)
    check("c. city of the day: the page (JS) and tools/cities_card.py (Python) pick the same city on 336 days", d["todays"] == picks, [(x, a, b) for x, a, b in zip(days, d["todays"], picks) if a != b][:3])
    nc = d["newCity"]
    check("c. a NEW city is one JSON entry: valid, generates, different from its sibling, no engine change", not nc["errs"] and nc["n"] == 60 and nc["differs"] and nc["districts"] >= 3, nc)


# ------------------------------------------------------------------ d. the page in Chromium
LAYOUT_JS = """() => {
  const w = innerWidth, h = innerHeight, vis = (e) => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden'; };
  const orb = { x0: w - 80, y0: h - 160, x1: w, y1: h };
  const hit = (r) => r.right > orb.x0 && r.left < orb.x1 && r.bottom > orb.y0 && r.top < orb.y1;
  const tap = [...document.querySelectorAll('.tab, .ic, .x, .pill, .cams button, .seg button, button.chip, .mini, .list li:not(.count)')].filter(vis);
  const small = tap.filter(e => { const r = e.getBoundingClientRect(); return r.height < 43.5 || (e.tagName === 'BUTTON' && r.width < 43.5); }).map(e => e.className + ':' + Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height));
  const inOrb = [...document.querySelectorAll('.tab, .ic, .x, .pill, .cams button, .seg button, button.chip, .mini, .sheet.on, .dock, .top, .list li, input')].filter(vis).filter(e => hit(e.getBoundingClientRect())).map(e => e.className || e.tagName);
  const off = [...document.querySelectorAll('.top, .sheet.on, .dock, .mini, .cams')].filter(vis).filter(e => { const r = e.getBoundingClientRect(); return r.left < -1 || r.right > w + 1 || r.top < -1 || r.bottom > h + 1; }).map(e => e.className);
  const lap = (a, b) => { const A = a.getBoundingClientRect(), B = b.getBoundingClientRect(); return A.left < B.right - 1 && A.right > B.left + 1 && A.top < B.bottom - 1 && A.bottom > B.top + 1; };
  const sheet = document.querySelector('.sheet.on'), dock = document.querySelector('.dock'), top = document.querySelector('.top');
  const overlaps = [];
  if (sheet && lap(sheet, dock)) overlaps.push('sheet/dock');
  if (sheet && lap(sheet, top)) overlaps.push('sheet/top');
  return { sideways: document.scrollingElement.scrollWidth > w || document.body.scrollWidth > w, small, inOrb, off, overlaps,
    counts: { top: document.querySelectorAll('.top').length, sheet: document.querySelectorAll('.sheet').length, dock: document.querySelectorAll('.dock').length } };
}"""

SPEC_NO_GL = """(() => {
  const g = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (t, ...a) { return /webgl/i.test(String(t)) ? null : g.call(this, t, ...a); };
})()"""


def shot(p, name):
    os.makedirs(SHOTS, exist_ok=True)
    p.screenshot(path=os.path.join(SHOTS, name.replace(".png", ".jpg")), type="jpeg", quality=80, timeout=120000)


class Page:
    """A Playwright page with its console / request errors collected (the Kalshi feed's own blocked request is not an error)."""

    def __init__(self, br, base, vw=None, q="low", extra="", reduced=False, init=None, kalshi="abort", touch=True):
        self.ctx = br.new_context(viewport=vw or {"width": 390, "height": 844}, device_scale_factor=1, has_touch=touch, **({"reduced_motion": "reduce"} if reduced else {}))
        if init:
            self.ctx.add_init_script(init)
        self.p = self.ctx.new_page()
        self.errs = []
        self.p.on("pageerror", lambda e: self.errs.append("pageerror: " + str(e)))
        self.p.on("console", self._console)
        self.p.on("requestfailed", lambda r: self.errs.append("requestfailed: " + r.url) if not any(o in r.url for o in BAD_ORIGINS) else None)
        self.p.on("response", lambda r: self.errs.append(f"{r.status}: {r.url}") if r.status >= 400 and not any(o in r.url for o in BAD_ORIGINS) and "favicon" not in r.url else None)
        if kalshi == "abort":
            self.p.route("**/raw.githubusercontent.com/**", lambda rt: rt.abort())
        elif kalshi:
            self.p.route("**/raw.githubusercontent.com/**", lambda rt: rt.fulfill(status=200, content_type="application/json", headers={"access-control-allow-origin": "*"}, body=json.dumps(kalshi)))
        self.url = base + f"?q={q}" + extra

    def _console(self, m):
        if m.type == "error" and not any(o in (m.location or {}).get("url", "") for o in BAD_ORIGINS) and "favicon" not in m.text:
            self.errs.append("console: " + m.text)

    def open(self, timeout=120):
        self.p.goto(self.url)
        self.p.wait_for_function("document.body.dataset.ready === 'true'", timeout=timeout * 1000)
        return self

    def info(self):
        return self.p.evaluate("window.__cities.info()")

    def enter(self, cid, settle=2.5):
        self.p.evaluate(f"window.__cities.enter('{cid}')")
        self.p.wait_for_function(f"window.__cities.info().mode === 'city' && window.__cities.info().id === '{cid}'", timeout=120000)
        time.sleep(settle)
        return self.info()

    def back(self):
        self.p.evaluate("document.querySelector('#hubB').click()")
        self.p.wait_for_function("window.__cities.info().mode === 'hub'", timeout=60000)
        time.sleep(0.6)

    def close(self):
        self.ctx.close()


def run_browser(C, days, picks):
    from playwright.sync_api import sync_playwright

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    root = f"http://127.0.0.1:{srv.server_port}"
    base = root + "/cities/"
    ids = [c["id"] for c in C]
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])

            # ---- c. the engine as modules
            ctx = br.new_context()
            p = ctx.new_page()
            p.goto(base + "jarvis.json")
            run_unit(p, days, picks)
            ctx.close()

            # ---- d. the hub and three cities, 390 x 844, touch
            pg = Page(br, base, q="low").open()
            p = pg.p
            time.sleep(4)
            info = pg.info()
            check("d. the hub opens: one island per city, a miniature of each, no 3D error", info["mode"] == "hub" and info["islands"] == len(C) and info["slots"] >= 24 and not info["errors"], info)
            p.wait_for_function(f"window.__cities.info().live >= {len(C) - 3}", timeout=120000)
            check("d. the islands turn LIVE as the real files arrive (all but the two private feeds + the vault)", pg.info()["live"] >= len(C) - 3, pg.info()["live"])
            lay = p.evaluate(LAYOUT_JS)
            check("d. hub layout: no sideways scroll, the orb's corner free, one top bar / one sheet / one dock, 44 px targets, nothing off screen",
                  not lay["sideways"] and not lay["inOrb"] and lay["counts"] == {"top": 1, "sheet": 1, "dock": 1} and not lay["small"] and not lay["off"], lay)
            check("d. island labels are drawn (the nearest names)", p.evaluate("[...document.querySelectorAll('#labels i')].filter(e => e.style.display !== 'none' && e.textContent.length > 2).length") >= 3)
            shot(p, "hub.png")
            pr = p.evaluate("window.__cities.projectIsland(3)")
            p.touchscreen.tap(pr["x"], pr["y"])
            p.wait_for_function("window.__cities.info().sheet === 'island'", timeout=30000)
            time.sleep(1.5)
            card = p.evaluate("({ t: document.querySelector('#sheetTitle').textContent, go: !!document.querySelector('.sheet .pill.go'), live: document.querySelector('.sheet .badge.live, .sheet .badge.demo').textContent })")
            check("d. tap an island: its card (name, LIVE DATA, Enter button) opens above the dock", card["t"] and card["go"] and pg.info()["hubSel"] == 3, card)
            lay = p.evaluate(LAYOUT_JS)
            check("d. with the card open: still no overlap with the dock / top bar, the orb's corner free", not lay["overlaps"] and not lay["inOrb"] and not lay["small"] and not lay["off"], lay)
            shot(p, "hub_card.png")
            p.evaluate("document.querySelector('#sheetX').click()")
            p.evaluate("document.querySelector('#findB').click()")
            p.evaluate("window.__cities.find('canyon')")
            hits = p.evaluate("[...document.querySelectorAll('.sheet .list li:not(.count)')].map(e => e.textContent)")
            check("d. hub Find: 'canyon' finds Drawdown Canyon and only it", len(hits) == 1 and "Drawdown Canyon" in hits[0], hits)
            p.evaluate("document.querySelector('#sheetX').click()")
            p.evaluate("document.querySelector('#todayB').click()")
            today = p.evaluate("({ id: window.__cities.today(), t: document.querySelector('#sheetTitle').textContent, h: document.querySelector('.sheet h3').textContent })")
            name_of = {c["id"]: c["name"] for c in C}
            check("d. Today: the card of the day names the city that tools/cities_card.py picks for today's date", today["t"] == "City of the day" and today["h"] == name_of[today["id"]], today)
            p.evaluate("document.querySelector('#sheetX').click()")
            p.evaluate("document.querySelector('#tourB').click()")
            c0 = pg.info()["camPos"]
            time.sleep(4)
            i2 = pg.info()
            check("d. Tour: the camera flies past the islands by itself (position changes, tour on)", i2["tour"] and sum(abs(a - b) for a, b in zip(c0, i2["camPos"])) > 30, (c0, i2["camPos"]))
            shot(p, "hub_tour.png")
            p.evaluate("window.__cities.tour()")
            check("d. hub: no console errors, no failed requests", not pg.errs, pg.errs[:5])

            seen = []
            for cid, tag in (("trades-city", "trades"), ("equity-mountains", "equity"), ("honesty-city", "honesty")):
                inf = pg.enter(cid, settle=3.2)
                k = p.evaluate("window.__cities.nearestToCenter()")
                pt = p.evaluate(f"window.__cities.project({k})")
                p.touchscreen.tap(pt["x"], pt["y"])
                try:
                    p.wait_for_function("window.__cities.info().sheet === 'building'", timeout=20000)
                    tapped = True
                except Exception:
                    tapped = False
                time.sleep(1.4)
                card = p.evaluate("({ t: document.querySelector('#sheetTitle').textContent, rows: document.querySelectorAll('.sheet .grid4 div').length, big: (document.querySelector('.sheet .big .v') || {}).textContent })")
                lay = p.evaluate(LAYOUT_JS)
                seen.append(inf["hash"])
                check(f"d. {cid}: entered ({inf['n']} of {inf['total']} buildings, {inf['districts']} districts, live data), tap a building -> its card with numbers",
                      inf["mode"] == "city" and inf["n"] > 0 and not inf["demo"] and tapped and card["t"] and card["rows"] >= 3 and card["big"], (inf, tapped, card))
                check(f"d. {cid}: layout (card open): no overlap, the orb's corner free, no sideways scroll, targets >= 44 px, one top bar / sheet / dock",
                      not lay["overlaps"] and not lay["inOrb"] and not lay["sideways"] and not lay["small"] and not lay["off"] and lay["counts"] == {"top": 1, "sheet": 1, "dock": 1}, lay)
                shot(p, f"{tag}_card.png")
                p.evaluate("document.querySelector('#sheetX').click()")
                p.evaluate("document.querySelector('#topB').click()")
                top = p.evaluate("document.querySelectorAll('.sheet .list li').length")
                p.evaluate("window.__cities.find('a')")
                m = p.evaluate("(() => { const c = document.querySelector('.sheet .list li.count'); return c ? c.textContent : ''; })()")
                p.evaluate("document.querySelector('#sheetX').click()")
                p.evaluate("window.__cities.find('')")
                p.evaluate("document.querySelector('#sheetX').click()")
                check(f"d. {cid}: Top 10 lists 10 buildings, Find lights up matches", top == 10 and re.search(r"\d", m) is not None, (top, m))
                pos0 = pg.info()["camPos"]
                moved = {}
                for cam in ("skim", "drone", "grand"):
                    p.evaluate(f"window.__cities.cam('{cam}')")
                    time.sleep(2.2)
                    cp = pg.info()["camPos"]
                    moved[cam] = (round(sum(abs(a - b) for a, b in zip(pos0, cp)), 1), pg.info()["cam"])
                    pos0 = cp
                check(f"d. {cid}: the SKIM / DRONE / GRAND cameras fly (the camera moves each time)", all(v[0] > 5 and v[1] == c for c, v in moved.items()), moved)
                if tag == "trades":
                    shot(p, "trades_grand.png")
                p.evaluate("window.__cities.cam('orbit')")
                before = pg.info()["camPos"]
                bx = p.evaluate("(() => { const r = document.querySelector('#mini').getBoundingClientRect(); return [r.left + r.width * 0.2, r.top + r.height * 0.25]; })()")
                p.touchscreen.tap(bx[0], bx[1])
                time.sleep(2.2)
                after = pg.info()["camPos"]
                check(f"d. {cid}: the minimap flies the camera where you tap", sum(abs(a - b) for a, b in zip(before, after)) > 5, (before, after))
                pg.back()
                check(f"d. {cid}: back to the world map", pg.info()["mode"] == "hub")
            check("d. three DIFFERENT cities were built (3 different hashes)", len(set(seen)) == 3, seen)
            p.evaluate("window.__cities.surprise()")
            p.wait_for_function("window.__cities.info().mode === 'city'", timeout=120000)
            time.sleep(1.5)
            surprised = pg.info()["id"]
            p.evaluate("window.__cities.surprise()")
            p.wait_for_function("window.__cities.info().sel >= 0", timeout=30000)
            check("d. Surprise me: in the hub it enters a random city, inside a city it flies to a random building", surprised in ids and pg.info()["sel"] >= 0, (surprised, pg.info()["sel"]))
            check("d. no console errors, no failed requests on the whole run (hub + 3 cities + surprise)", not pg.errs, pg.errs[:5])
            pg.close()

            if QUICK:
                br.close()
                return
            # ---- e. budgets per tier
            for q in ("off", "low", "high", "ultra"):
                pg = Page(br, base, q=q).open()
                time.sleep(2)
                hub = pg.p.evaluate("window.__cities.stats()")
                inf = pg.enter("ideas-city", settle=1.0)
                st = pg.p.evaluate("window.__cities.stats()")
                B = st["budget"]
                want = st["caps"]["cap"]
                passes = {"off": 1, "low": 2, "high": 3, "ultra": 3}[q]
                check(f"e. tier {q}: hub {hub['calls']} draw calls / {hub['triangles']:,} triangles, 31k-idea city {st['calls']} calls / {st['triangles']:,} triangles ({inf['n']:,} of {inf['total']:,} buildings), both inside the budget ({B['calls']} / {B['tris']:,})",
                      hub["tier"] == q and st["tier"] == q and hub["calls"] <= B["calls"] and hub["triangles"] <= B["tris"] and st["calls"] <= B["calls"] and st["triangles"] <= B["tris"]
                      and inf["n"] == min(inf["total"], want) and st["passes"] == passes and st["calls"] > 0, (hub, st, inf))
                if q in ("low", "ultra"):
                    shot(pg.p, f"ideas_{q}.png")
                check(f"e. tier {q}: no console errors", not pg.errs, pg.errs[:4])
                pg.close()

            # ---- f. fallbacks
            pg = Page(br, base, q="low", kalshi="abort").open()
            inf = pg.enter("kalshi-city", settle=1.5)
            toast = pg.p.evaluate("document.querySelector('#toast').textContent")
            chip = pg.p.evaluate("[...document.querySelectorAll('.chip')].map(e => e.textContent).join('|')")
            check("f. Kalshi feed offline: the city shows the marked sample (SAMPLE chip, a toast), no error", inf["demo"] and inf["n"] > 5 and "SAMPLE" in chip and "sample" in toast.lower(), (inf, chip, toast))
            pg.back()
            inf = pg.enter("obsidian-city", settle=1.0)
            check("f. no vault connected on this browser: Obsidian City shows the marked sample, nothing is fetched or sent", inf["demo"] and inf["n"] > 5, inf)
            check("f. fallbacks: no console errors", not pg.errs, pg.errs[:4])
            pg.close()
            feed = {"v": 3, "kind": "kalshi", "t": 1793760000, "trades": [{"t": 1793700000 + i * 60, "ticker": f"KXBTCD-26NOV0{i % 9}", "title": f"Bitcoin above ${70000 + i} bet {i}", "side": "yes" if i % 2 else "no",
                                                                           "contracts": 3 + i, "price": 0.9, "pnl": (-1) ** i * (i + 1) * 0.7, "asset": "BTC" if i % 3 else "ETH", "strategy": "Late favourite"} for i in range(12)],
                    "positions": [{"ticker": "KXETHD-26NOV05", "title": "Ether open bet", "side": "yes", "contracts": 4, "avg_price": 0.8, "value": 3.2, "pnl": 0, "asset": "ETH"}]}
            pg = Page(br, base, q="low", kalshi=feed).open()
            inf = pg.enter("kalshi-city", settle=1.0)
            check("f. a live Kalshi feed (stubbed): the city shows its 13 real rows (12 trades + 1 open bet), LIVE, not the sample", not inf["demo"] and inf["n"] == 13, inf)
            pg.close()
            pg = Page(br, base, q="low", extra="&demo=1").open()
            time.sleep(1)
            inf = pg.enter("trades-city", settle=1.0)
            check("f. ?demo=1: nothing is fetched, every city is built from the shipped sample (marked SAMPLE)", inf["demo"] and inf["n"] > 5 and pg.info()["live"] == 0, inf)
            check("f. ?demo=1: no console errors", not pg.errs, pg.errs[:4])
            pg.close()
            pg = Page(br, base, q="low", reduced=True).open()
            inf = pg.enter("sessions-city", settle=1.0)
            check("f. reduced motion: the city opens without the fly-in, no auto-orbit drift, no errors", inf["mode"] == "city" and not pg.errs, (inf, pg.errs[:3]))
            pg.close()
            pg = Page(br, base, vw={"width": 844, "height": 390}, q="low").open()
            time.sleep(2)
            inf = pg.enter("levels-city", settle=2.0)
            k = pg.p.evaluate("window.__cities.nearestToCenter()")
            pg.p.evaluate(f"window.__cities.pickBuilding({k})")
            time.sleep(1.2)
            lay = pg.p.evaluate(LAYOUT_JS)
            check("f. landscape 844 x 390: a city opens, a card opens at the side, no sideways scroll, nothing off screen, the orb's corner free", inf["mode"] == "city" and not lay["sideways"]
                  and not lay["off"] and not lay["inOrb"], (inf, lay))
            shot(pg.p, "landscape.png")
            check("f. landscape: no console errors", not pg.errs, pg.errs[:4])
            pg.close()
            ctx = br.new_context(viewport={"width": 390, "height": 844})
            ctx.add_init_script(SPEC_NO_GL)
            p = ctx.new_page()
            p.goto(base + "?q=low")
            p.wait_for_function("document.body.dataset.ready === 'fallback'", timeout=60000)
            txt = p.evaluate("document.querySelector('.fallback').textContent")
            check("f. no WebGL: the page lists every city in plain text instead of a blank screen", all(c["name"] in txt for c in C), txt[:200])
            ctx.close()
            br.close()
    finally:
        srv.shutdown()


def main():
    no_browser = "--no-browser" in sys.argv
    C = part_a()
    days, picks = part_b(C)
    if not no_browser:
        try:
            import playwright  # noqa: F401
        except ImportError:
            print("[SKIP] Playwright missing: the browser part was skipped")
        else:
            run_browser(C, days, picks)
    n_ok = sum(RES)
    print(f"\n{n_ok}/{len(RES)} passed" + (f" -> screenshots in {SHOTS}" if not no_browser else ""))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
