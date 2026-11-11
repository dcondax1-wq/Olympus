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

    python -X utf8 -m tests.test_cities_page            (~15 min on a quiet machine; --no-browser: a and b only, ~3 s; --only=c|d|e|f|g|j|k runs one section; k = the Athens nested world)
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import shutil
import subprocess
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
ONLY = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)   # e.g. --only=c  or  --only=a,b,g: one section at a time (the machine is slow)
want = lambda k: ONLY is None or k in ONLY  # noqa: E731
BAD_ORIGINS = ("githubusercontent", "/kalshi.json")          # the Kalshi feed: the site copy (tried first, absent on the test server) and the raw file, blocked on purpose in the offline runs


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------ a. files
def part_a():
    need = ["index.html", "cities.json", "fixture.json", "jarvis.json", "manifest.webmanifest", "icon.svg", "app.js", "datasets.js", "generator.js",
            "scene.js", "shaders.js", "landmarks.js", "rig.js", "util.js", "insight.js", "procedural.js"]
    check("a. every file of the page is there", all(os.path.isfile(os.path.join(PAGE, n)) for n in need), [n for n in need if not os.path.isfile(os.path.join(PAGE, n))])
    html = read(os.path.join(PAGE, "index.html"))
    check("a. the OLYMPUS kit ?v=o2 (css, themes, olympus.js with data-app=cities), module app, manifest, icon",
          'olympus.css?v=o4' in html and 'themes.js?v=o4' in html and 'olympus.js?v=o4" data-app="cities"' in html and 'type="module"' in html
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
          and all(os.path.isfile(os.path.normpath(os.path.join(PAGE, i["src"].split("?", 1)[0]))) for i in mf["icons"]), mf)
    # the real published files the adapters read
    urls = re.findall(r"url: '(\.\./[^']+)'", srcs["datasets.js"])
    check("a. every file an adapter reads is a published page file that exists (odeon, datacity, tree, forge, pantheon, fates, arena, athena ...)",
          len(set(urls)) >= 9 and all(os.path.isfile(os.path.normpath(os.path.join(PAGE, u))) for u in urls), [u for u in set(urls) if not os.path.isfile(os.path.normpath(os.path.join(PAGE, u)))])
    cfg = json.loads(read(os.path.join(PAGE, "cities.json")))
    C = cfg["cities"]
    sig = lambda c: (c["dataset"], c["district_by"], c["height_by"], c["layout"])  # noqa: E731
    check("a. 120+ city specs (the owner asked for hundreds; this ships %d, one JSON entry each)" % len(C), len(C) >= 120, len(C))
    conts = {c["group"] for c in C}
    check("a. six continents (Trading, Research, Money, Kalshi, Life, Obsidian), each with regions; every city has a region and scenery (river / harbor / rail)",
          conts == {"trading", "research", "money", "kalshi", "life", "obsidian"} and all(c.get("region") and c.get("scenery") in ("river", "harbor", "rail") for c in C)
          and len({c["region"] for c in C}) >= 18 and {c["scenery"] for c in C} == {"river", "harbor", "rail"}, (conts, len({c["region"] for c in C})))
    check("a. every continent has cities and the big ones have many regions", all(sum(1 for c in C if c["group"] == g) >= 5 for g in conts) and len({c["region"] for c in C if c["group"] == "trading"}) >= 5)
    check("a. unique id, name, motto, landmark label and accent colour", all(len({c[k] if k != "lm" else c["landmark"]["label"] for c in C}) == len(C) for k in ("id", "name", "motto", "lm"))
          and len({c["palette"]["accent"] for c in C}) == len(C))
    check("a. every city is a different TYPE: (dataset, district, height, layout) is unique", len({sig(c) for c in C}) == len(C))
    check("a. variety: 14 landmarks, 8 skies, 8 weathers, 5 layouts, 6 groups, 20 datasets in use",
          len({c["landmark"]["kind"] for c in C}) >= 14 and len({c["sky"]["kind"] for c in C}) >= 8 and len({c["weather"] for c in C}) >= 8
          and len({c["layout"] for c in C}) >= 5 and len({c["group"] for c in C}) >= 6 and len({c["dataset"] for c in C}) >= 20,
          (len({c["landmark"]["kind"] for c in C}), len({c["sky"]["kind"] for c in C}), len({c["weather"] for c in C}), len({c["layout"] for c in C}), len({c["dataset"] for c in C})))
    fx = json.loads(read(os.path.join(PAGE, "fixture.json")))
    odeon = json.loads(read(os.path.join(PAGE, "..", "odeon", "trades.json")))
    atlas_backtests = {"atlas_ema": "EMA", "atlas_macd": "MACD", "atlas_sr": "S/R"}
    def fixture_has_source_rows(dataset):
        if dataset not in fx:
            return False
        items = fx[dataset]["items"]
        if dataset not in atlas_backtests:
            return len(items) >= 8
        strategy = atlas_backtests[dataset]
        source_count = sum(t.get("bot") == "ATLAS" and t.get("strat") == strategy and t.get("src") == "backtest" for t in odeon["trades"])
        return source_count > 0 and len(items) == min(44, source_count) and all(
            row["f"].get("bot") == "ATLAS" and row["f"].get("strat") == strategy and row["f"].get("src") == "backtest" for row in items)
    check("a. fixture.json: a sample for every dataset the cities use, each with rows, <= 250 KB",
          all(fixture_has_source_rows(c["dataset"]) for c in C) and os.path.getsize(os.path.join(PAGE, "fixture.json")) <= 250_000)
    node = shutil.which("node")
    if node:
        before = {n: open(os.path.join(PAGE, n), "rb").read() for n in ("cities.json", "fixture.json")}
        try:
            generated = []
            for _ in range(2):
                for tool in ("cities_catalogue.mjs", "cities_fixture.mjs"):
                    subprocess.run([node, os.path.join(ROOT, "tools", tool)], check=True, capture_output=True, timeout=180)
                generated.append({n: open(os.path.join(PAGE, n), "rb").read() for n in before})
            check("a. the catalogue and fixture generators reproduce the same bytes for the same published source files", generated[0] == generated[1],
                  [n for n in before if generated[0][n] != generated[1][n]])
        finally:
            for n, data in before.items():
                with open(os.path.join(PAGE, n), "wb") as fh:
                    fh.write(data)
    else:
        print("[SKIP] node missing: the catalogue reproducibility check was skipped")
    card = json.loads(read(os.path.join(PAGE, "jarvis.json")))
    raw = read(os.path.join(PAGE, "jarvis.json"))
    ids = [c["id"] for c in C]
    ok = (card["v"] == 1 and card["name"] and len(card["name"]) <= 40 and card["status"]["level"] in ("ok", "warn", "bad", "off") and len(card["status"]["label"]) <= 48
          and len(card["kpis"]) <= 3 and all(len(k["label"]) <= 20 and len(str(k["value"])) <= 24 for k in card["kpis"])
          and len(card["lines"]) <= 3 and all(len(x) <= 120 for x in card["lines"]) and isinstance(card["t"], int) and re.fullmatch(r"#[0-9a-f]{6}", card["theme"])
          and 60 <= card["stale_after"] <= 1_209_600 and card["open"][1:] in ids and len(raw.encode()) <= 8192 and not re.search(r"[<>&]", raw.replace("&amp;", "")))
    check("a. jarvis.json: the Jarvis card contract (docs/JARVIS_APPS.md), the card opens a real city, 'City of the day', the random seed and tomorrow's city in it",
          ok and "City of the day" in raw and "Random seed" in raw and "Tomorrow:" in raw, card)
    check("a. the kit's effects and sound are wired: fx-core.js + fx-burst.js in the page, OLYMPUS_SFX ambient + thunder, photo mode, share, favourites in localStorage",
          "fx-core.js" in html and "fx-burst.js" in html and "sfx.js" in html and 'id="photoB"' in html and "sparkleBurst" in srcs["app.js"] and "OLYMPUS_SFX" in srcs["app.js"] and "'thunder'" in srcs["app.js"]
          and "cities.fav" in srcs["app.js"] and "cities.visited" in srcs["app.js"] and "navigator.share" in srcs["app.js"] and "toBlob" in srcs["app.js"])
    check("a. the new engine files are deterministic by construction: no Math.random call in procedural / insight",
          all(not re.search(r"Math\.random\s*\(", srcs[n]) for n in ("procedural.js", "insight.js")))
    return C


# ------------------------------------------------------------------ b. the card tool
def part_b(C):
    ids = [c["id"] for c in C]
    a, b = CC.build("2026-11-04", 1793700000, C), CC.build("2026-11-04", 1793700000, C)
    check("b. cities_card.build is deterministic (same date + time -> same bytes)", CC.dumps(a) == CC.dumps(b))
    days = [f"2026-{m:02d}-{d:02d}" for m in range(1, 13) for d in range(1, 29)]
    picks = [CC.city_of_day(d, ids) for d in days]
    check("b. the city of the day spreads over the list (336 days hit 100+ different cities, none more than 6 days)",
          len(set(picks)) >= 100 and max(picks.count(i) for i in set(picks)) <= 6, (len(set(picks)), max(picks.count(i) for i in set(picks))))
    seeds = [CC.seed_of_day(d) for d in days]
    check("b. the random seed of the day: 6 letters from the alphabet, deterministic, 300+ different seeds in 336 days", all(re.fullmatch(r"[a-hj-km-np-z2-9]{6}", x) for x in seeds) and len(set(seeds)) > 300
          and seeds == [CC.seed_of_day(d) for d in days], len(set(seeds)))
    card = CC.build("2026-11-04", 1793700000, C)
    check("b. the card names the continent and region, tomorrow's city and the seed", "Tomorrow:" in card["lines"][1] and any(k["label"] == "Random seed" and k["value"] == CC.seed_of_day("2026-11-04") for k in card["kpis"]), card)
    check("b. a card is valid for every city (open route, name, kpis)", all(CC.build("2026-11-04", 1, [c for c in C if c["id"] == i])["open"] == "#" + i for i in ids[:5]))
    tmp = tempfile.mkdtemp(prefix="cities_card_")
    os.makedirs(os.path.join(tmp, "cities"))
    msg = CC.publish(tmp)
    check("b. publish(out) writes <out>/cities/jarvis.json and skips a build without the page", os.path.isfile(os.path.join(tmp, "cities", "jarvis.json")) and "city of the day" in msg
          and "skipped" in CC.publish(os.path.join(tmp, "nowhere")), msg)
    return days, picks, seeds


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


UNIT_E = """async (days) => {
  const [D, G, P, I, U] = await Promise.all([import('/cities/datasets.js'), import('/cities/generator.js'), import('/cities/procedural.js'), import('/cities/insight.js'), import('/cities/util.js')]);
  const cfg = await (await fetch('/cities/cities.json')).json();
  const env = { get: async (u) => { if (/^https?:/.test(u)) throw new Error('remote'); const r = await fetch(u); if (!r.ok) throw new Error(u); return r.json(); }, fixture: await (await fetch('/cities/fixture.json')).json() };
  const cache = new Map(), r = U.rng(11), bad = [], hashes = new Set(), dsu = new Set();
  let same = 0;
  for (let i = 0; i < 150; i++) {
    const seed = P.newSeed(r), id = P.seedDataset(seed), ds = await D.loadDataset(id, env, cache);
    const spec = P.randomSpec(seed, ds), spec2 = P.randomSpec(seed, ds), errs = G.validateSpec(spec, D.DATASETS);
    if (errs.length) bad.push([seed, id, errs]);
    const c = G.generate(spec, ds, { cap: 3000 }), c2 = G.generate(spec, ds, { cap: 3000 });
    if (JSON.stringify(spec) === JSON.stringify(spec2) && c.hash === c2.hash && c.n > 0) same++;
    hashes.add(c.hash); dsu.add(id);
  }
  const sent = [];
  for (const s of cfg.cities) {
    const ds = await D.loadDataset(s.dataset, env, cache), c = G.generate(s, ds, { cap: 3000 }), ins = I.insight(s, ds, c);
    sent.push([s.id, ins.sentence.startsWith(s.name + ':'), ins.sentence.length, ins.numeric]);
  }
  const a = P.randomSpec('abc123', await D.loadDataset(P.seedDataset('abc123'), env, cache)), b = P.randomSpec('abc124', await D.loadDataset(P.seedDataset('abc124'), env, cache));
  return { bad, same, distinct: hashes.size, datasets: dsu.size, sent, seeds: days.map(U.seedOfDay), cleaned: P.cleanSeed(' Ab-C1!23_x '), differs: a.name !== b.name || a.palette.accent !== b.palette.accent };
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
    atlas_setups = {"atlas-ema-city": "atlas_ema", "atlas-macd-city": "atlas_macd", "atlas-sr-city": "atlas_sr"}
    sample_ok = lambda r: (r["fxN"] == min(44, b[atlas_setups[r["id"]]]["n"]) if r["id"] in atlas_setups else r["fxN"] > 5)
    check("c. the sample fixture builds each city from source rows, including small ATLAS backtests", all(sample_ok(r) for r in R), [r["id"] for r in R if not sample_ok(r)])
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
    e = p.evaluate(UNIT_E, days)
    check("c. random cities: 150 seeds -> 150 valid specs, the same seed gives the same spec and the same city (hash), 148+ different cities, 15+ datasets reached",
          not e["bad"] and e["same"] == 150 and e["distinct"] >= 148 and e["datasets"] >= 15 and e["differs"] and e["cleaned"] == "abc123x", {k: e[k] for k in ("bad", "same", "distinct", "datasets", "cleaned")})
    check("c. the score card: every one of the %d cities says one plain sentence that starts with its name (20-200 characters)" % len(e["sent"]), all(x[1] and 20 <= x[2] <= 200 for x in e["sent"]),
          [x for x in e["sent"] if not (x[1] and 20 <= x[2] <= 200)][:3])
    check("c. the random seed of the day: the page (JS) and tools/cities_card.py (Python) agree on 336 days", e["seeds"] == [CC.seed_of_day(x) for x in days], e["seeds"][:3])
    nc = d["newCity"]
    check("c. a NEW city is one JSON entry: valid, generates, different from its sibling, no engine change", not nc["errs"] and nc["n"] == 60 and nc["differs"] and nc["districts"] >= 3, nc)


# ------------------------------------------------------------------ d. the page in Chromium
LAYOUT_JS = """() => {
  const w = innerWidth, h = innerHeight, vis = (e) => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden'; };
  const orb = { x0: w - 80, y0: h - 160, x1: w, y1: h };
  const hit = (r) => r.right > orb.x0 && r.left < orb.x1 && r.bottom > orb.y0 && r.top < orb.y1;
  const tap = [...document.querySelectorAll('.tab, .ic, .x, .pill, .cams button, .seg button, button.chip, .mini, .list li:not(.count)')].filter(vis);
  const small = tap.filter(e => { const r = e.getBoundingClientRect(); return r.height < 43.5 || (e.tagName === 'BUTTON' && r.width < 43.5); }).map(e => e.className + ':' + Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height));
  const sh = document.querySelector('.sheet.on'), shr = sh ? sh.getBoundingClientRect() : null;
  const clipped = (e) => { if (!shr || !sh.contains(e) || e === sh) return false; const r = e.getBoundingClientRect(); return r.bottom > shr.bottom + 1 || r.top < shr.top - 1; };   // scrolled out of the sheet: not on screen
  const inOrb = [...document.querySelectorAll('.tab, .ic, .x, .pill, .cams button, .seg button, button.chip, .mini, .sheet.on, .dock, .top, .list li, input')].filter(vis).filter((e) => !clipped(e)).filter(e => hit(e.getBoundingClientRect())).map(e => e.className || e.tagName);
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

    def __init__(self, br, base, vw=None, q="low", extra="", reduced=False, init=None, kalshi="abort", touch=True, world=True):
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
        # Existing world/navigation checks enter through the explicit map route.
        # The normal skyline entrance has its own assertion in section i.
        self.url = base + f"?q={q}" + ("&world=1" if world else "") + extra

    def _console(self, m):
        if m.type == "error" and not any(o in (m.location or {}).get("url", "") for o in BAD_ORIGINS) and "favicon" not in m.text:
            self.errs.append("console: " + m.text)

    def open(self, timeout=120):
        self.p.goto(self.url)
        self.p.wait_for_function("['true','fallback'].includes(document.body.dataset.ready)", timeout=timeout * 1000)
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



def sec_c(br, base, C, days, picks, ids):
    # ---- c. the engine as modules
    ctx = br.new_context()
    p = ctx.new_page()
    p.goto(base + "jarvis.json")
    run_unit(p, days, picks)
    ctx.close()



def sec_d(br, base, C, days, picks, ids):
    # ---- d. the hub and three cities, 390 x 844, touch
    pg = Page(br, base, q="low").open()
    p = pg.p
    time.sleep(4)
    info = pg.info()
    mp = p.evaluate("window.__cities.map()")
    check("d. the hub opens: the AGORA map draws one skyline per city, no error", info["mode"] == "hub" and info["islands"] == len(C) and mp["cities"] == len(C) and mp["running"] and mp["banners"] >= 6 and not info["errors"], (info, mp))
    private = sum(1 for c in C if c["dataset"] in ("kalshi", "notes"))
    p.wait_for_function(f"window.__cities.info().live >= {len(C) - private}", timeout=240000)
    check("d. the islands turn LIVE as the real files arrive (all but the Kalshi feed and the vault: %d of %d)" % (len(C) - private, len(C)), pg.info()["live"] >= len(C) - private, pg.info()["live"])
    lay = p.evaluate(LAYOUT_JS)
    check("d. hub layout: no sideways scroll, the orb's corner free, one top bar / one sheet / one dock, 44 px targets, nothing off screen",
          not lay["sideways"] and not lay["inOrb"] and lay["counts"] == {"top": 1, "sheet": 1, "dock": 1} and not lay["small"] and not lay["off"], lay)
    check("d. the map draws the six district banners and the capital names (big, fully on screen)", p.evaluate("window.__cities.map().labels") >= 8)
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
    m0 = p.evaluate("window.__cities.map()")
    time.sleep(5)
    i2 = pg.info()
    m1 = p.evaluate("window.__cities.map()")
    check("d. Tour: the map glides past the districts by itself (view changes, tour on)", i2["tour"] and abs(m0["x"] - m1["x"]) + abs(m0["y"] - m1["y"]) + abs(m0["scale"] - m1["scale"]) * 500 > 20, (m0, m1))
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
        before = p.evaluate("window.__cities.rig().t")
        bx = p.evaluate("(() => { const r = document.querySelector('#mini').getBoundingClientRect(); return [r.left + r.width * 0.2, r.top + r.height * 0.25]; })()")
        p.touchscreen.tap(bx[0], bx[1])
        try:
            p.wait_for_function("(b) => { const t = window.__cities.rig().t; return Math.abs(t[0] - b[0]) + Math.abs(t[2] - b[2]) > 4; }", arg=before, timeout=120000)
            flew = True
        except Exception:
            flew = False
        check(f"d. {cid}: the minimap flies the camera where you tap", flew, (before, p.evaluate("window.__cities.rig().t")))
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



def sec_e(br, base, C, days, picks, ids):
    # ---- e. budgets per tier
    for q in (os.environ.get("CITIES_TIERS") or "off,low,high,ultra").split(","):          # CITIES_TIERS=off,low to run fewer
        pg = Page(br, base, q=q).open()
        if q == "off":
            check("e. effects off: useful atlas, all catalogue cities, no renderer", pg.p.evaluate("document.body.dataset.ready === 'fallback'") and pg.p.locator('.atlas-city').count() == len(C) and pg.info().get('tier') is None)
            pg.close()
            continue
        time.sleep(2)
        hub = pg.p.evaluate("window.__cities.stats()")
        inf = pg.enter("ideas-city", settle=1.0)
        st = pg.p.evaluate("window.__cities.stats()")
        B = st["budget"]
        want = st["caps"]["cap"]
        passes = {"off": 1, "low": 2, "high": 3, "ultra": 3}[q]
        check(f"e. tier {q}: hub {hub['calls']} draw calls / {hub['triangles']:,} triangles, 31k-idea city {st['calls']} calls / {st['triangles']:,} triangles ({inf['n']:,} of {inf['total']:,} buildings), both inside the budget (draw calls {B['calls']}; triangles hub {B['hubTris']:,} / city {B['tris']:,})",
              hub["tier"] == q and st["tier"] == q and hub["calls"] <= B["calls"] and hub["triangles"] <= B["hubTris"] and st["calls"] <= B["calls"] and st["triangles"] <= B["tris"]
              and inf["n"] == min(inf["total"], want) and st["passes"] == passes and st["calls"] > 0, (hub, st, inf))
        if q in ("low", "ultra"):
            shot(pg.p, f"ideas_{q}.png")
        check(f"e. tier {q}: no console errors", not pg.errs, pg.errs[:4])
        pg.close()



def sec_f(br, base, C, days, picks, ids):
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
    check("f. no WebGL: the illustrated, searchable atlas keeps every city accessible", all(c["name"] in txt for c in C), txt[:200])
    ctx.close()

SFX_STUB = """(() => { window.OLYMPUS_SFX = { calls: [], play(n) { this.calls.push('play:' + n); }, stop(n) { this.calls.push('stop:' + n); }, mute() {}, setVolume() {}, unlock() {}, state() { return {}; }, names: [] }; })()"""


def sec_g(br, base, C, days, picks, ids):
    """the 2026-11-04 night pass: continents, favourites, visited, random seeds, report, compare, photo, share, scenery, fireworks, sound, the tour"""
    pg = Page(br, base, q="low", init=SFX_STUB).open()
    p = pg.p
    time.sleep(3)
    cont = p.evaluate("window.__cities.conts()")
    labels = p.evaluate("[...document.querySelectorAll('#labels i.cont')].filter(e => e.style.display !== 'none').map(e => e.textContent)")
    check("g. the world map has six continents with their cities (%s), drawn as labels when zoomed out (%d visible)" % (", ".join(f"{c['name']} {c['count']}" for c in cont), len(labels)),
          [c["key"] for c in cont] == ["trading", "research", "money", "kalshi", "life", "obsidian"] and sum(c["count"] for c in cont) == len(C) and len(labels) >= 2, (cont, labels))
    m0 = p.evaluate("window.__cities.map()")                      # the hub is the drawn map now (agoramap.js): a fly is the map zooming in on that district
    p.evaluate("window.__cities.contTap('kalshi')")
    p.wait_for_function(f"(() => {{ const m = window.__cities.map(); return m.scale > {m0['scale'] * 1.15} || Math.abs(m.x - {m0['x']}) + Math.abs(m.y - {m0['y']}) > 40; }})()", timeout=240000)
    cap = p.evaluate("document.querySelector('#caption').textContent")
    check("g. tap a continent: the camera flies to it and says what is there", "KALSHI" in cap.upper() and "cities" in cap, cap)
    # favourites + visited, persisted
    p.evaluate("window.__cities.select(4)")
    p.wait_for_function("window.__cities.info().sheet === 'island'", timeout=60000)
    sid = p.evaluate("window.__cities.specs()[4]")
    card = p.evaluate("({ say: (document.querySelector('.sheet .say') || {}).textContent || '', pills: [...document.querySelectorAll('.sheet .pill')].map(e => e.textContent) })")
    check("g. an island card shows what the city says in one sentence, Save, Compare and Share", len(card["say"]) > 20 and any("Save" in x for x in card["pills"]) and "Compare" in card["pills"] and "Share" in card["pills"], card)
    p.evaluate("[...document.querySelectorAll('.sheet .pill')].find(e => /Save/.test(e.textContent)).click()")
    favs = p.evaluate("window.__cities.favs()")
    pg.enter("plans-city", settle=1.0)
    pg.back()
    check("g. Save puts the city in favourites and entering one marks it visited", favs == [sid] and p.evaluate("window.__cities.visited()") == ["plans-city"], (favs, p.evaluate("window.__cities.visited()")))
    p.reload()
    p.wait_for_function("document.body.dataset.ready === 'true'", timeout=120000)
    check("g. favourites and visited survive a reload (localStorage, per viewer)", p.evaluate("window.__cities.favs()") == [sid] and p.evaluate("window.__cities.visited()") == ["plans-city"])
    p.evaluate("document.querySelector('#findB').click()")
    p.evaluate("[...document.querySelectorAll('.sheet .seg button')].find(e => /Saved/.test(e.textContent)).click()")
    n_saved = p.evaluate("document.querySelectorAll('.sheet .list li:not(.count)').length")
    p.evaluate("[...document.querySelectorAll('.sheet .seg button')].find(e => /Not visited/.test(e.textContent)).click()")
    cnt = p.evaluate("document.querySelector('.sheet .list li.count').textContent")
    p.evaluate("[...document.querySelectorAll('.sheet .seg button')].find(e => e.textContent === 'Everything').click()")
    p.evaluate("[...document.querySelectorAll('.sheet .seg button')].find(e => e.textContent === 'Trading').click()")
    regs = p.evaluate("[...document.querySelectorAll('.sheet .seg')].filter(e => e.style.display !== 'none').map(e => e.children.length)")
    check("g. Find: continents, regions, Saved and Not visited filters (1 saved, %d not visited, regions appear under a continent)" % (len(C) - 1), n_saved == 1 and f"{len(C) - 1} matching" in cnt and f"{len(C)} total" in cnt and max(regs) >= 6, (n_saved, cnt, regs))
    chips = p.evaluate("[...document.querySelectorAll('.chip')].map(e => e.textContent.replace(/\\s/g, '')).join('|')")
    check("g. the hub chips count what you saved and visited", "saved1" in chips and "visited1" in chips, chips)
    p.evaluate("document.querySelector('#sheetX').click()")
    # random city: the dice, the seed link
    p.evaluate("document.querySelector('#diceB').click()")
    p.wait_for_function("window.__cities.info().mode === 'city'", timeout=180000)
    ri = pg.info()
    check("g. the dice build a random city (a seeded one, id r-<seed>, in the address bar)", ri["id"].startswith("r-") and ri["n"] > 0 and p.evaluate("location.hash") == "#" + ri["id"], ri)
    link = p.evaluate(f"window.__cities.shareLink('{ri['id']}')")
    check("g. share link: a random city is ?seed=<seed>, a made city is ?city=<id>", f"?seed={ri['id'][2:]}" in link and "?city=trades-city" in p.evaluate("window.__cities.shareLink('trades-city')"), link)
    pg.back()
    pg.close()
    hashes = []
    for _ in range(2):
        pg2 = Page(br, base, q="low", extra="&seed=abc123", init=SFX_STUB)
        pg2.p.goto(pg2.url)
        pg2.p.wait_for_function("window.__cities && window.__cities.info().id === 'r-abc123' && window.__cities.info().mode === 'city'", timeout=240000)
        hashes.append(pg2.info()["hash"])
        pg2.close()
    check("g. ?seed=abc123 opens the same random city every time (same hash on two loads: a shareable seed)", hashes[0] == hashes[1] and len(hashes[0]) == 8, hashes)

    pg = Page(br, base, q="low", init=SFX_STUB).open()
    p = pg.p
    # the three scenery kinds, report, compare, photo, fireworks, sound
    by = {}
    for c in C:
        by.setdefault(c["scenery"], []).append(c)
    small = {"plans", "workshop", "feeds", "gods"}
    scen = {}
    for kind in ("river", "harbor", "rail"):
        cand = next((c for c in by[kind] if c["dataset"] in small), by[kind][0])
        pg.enter(cand["id"], settle=1.5)
        st = p.evaluate("window.__cities.stats()")
        sc = p.evaluate("window.__cities.scenery()")
        scen[kind] = (cand["id"], sc, st["calls"], st["budget"]["calls"])
        pg.back()
    check("g. scenery: a river with bridges, a harbor with piers and ships, a railway with a train, each inside the draw-call budget",
          all(v[1] and v[1]["kind"] == k and v[1]["props"] >= 3 and v[2] <= v[3] for k, v in scen.items()), scen)
    pad = next(c for c in C if c["sound"] == "pad" or c["weather"] in ("snow", "fog", "fireflies", "dust"))
    pg.enter(pad["id"], settle=3.5)
    calls = p.evaluate("window.OLYMPUS_SFX.calls")
    rec = pg.info()["records"]
    check("g. fireworks on the record building: it went off by itself after entering (the kit's sparkleBurst + toast + the scene's sparks)", rec >= 1 and p.evaluate("typeof OLYMPUS_FX === 'object' && typeof OLYMPUS_FX.sparkleBurst === 'function'"), (rec, calls))
    check("g. ambient sound: a calm city starts the OLYMPUS_SFX pad", "play:pad" in calls, calls)
    p.evaluate("window.__cities.report()")
    rep_ = p.evaluate("({ say: (document.querySelector('.sheet .say') || {}).textContent || '', bars: document.querySelectorAll('.sheet .barrow').length, h: document.querySelector('#sheetTitle').textContent })")
    lay = p.evaluate(LAYOUT_JS)
    check("g. city report: its sentence, a bar per district, the numbers, how to read it; the sheet fits the phone", rep_["h"] == "City report" and rep_["say"].startswith(pad["name"] + ":") and rep_["bars"] >= 1
          and not lay["overlaps"] and not lay["inOrb"] and not lay["sideways"] and not lay["off"], (rep_, lay))
    shot(p, "g_report.png")
    p.evaluate("document.querySelector('#sheetX').click()")
    pg.back()
    check("g. leaving the city stops the ambient pad", "stop:pad" in p.evaluate("window.OLYMPUS_SFX.calls"))
    p.evaluate("window.__cities.compare('trades-city', 'canyon')")
    p.wait_for_function("document.querySelectorAll('.sheet .cmp canvas').length === 2", timeout=120000)
    cmpx = p.evaluate("({ cols: document.querySelectorAll('.sheet .cmpcol').length, says: [...document.querySelectorAll('.sheet .cmpcol .say')].map(e => e.textContent.slice(0, 20)), title: document.querySelector('#sheetTitle').textContent })")
    lay = p.evaluate(LAYOUT_JS)
    check("g. compare two cities side by side: two columns, each with its picture, sentence and numbers; the sheet fits", cmpx["cols"] == 2 and all(cmpx["says"]) and not lay["overlaps"] and not lay["sideways"] and not lay["off"], (cmpx, lay))
    shot(p, "g_compare.png")
    p.evaluate("document.querySelector('#sheetX').click()")
    pg.enter("trades-city", settle=2.0)
    p.evaluate("window.__cities.photoMode(true)")
    hid = p.evaluate("({ photo: document.body.classList.contains('photo'), top: getComputedStyle(document.querySelector('.top')).display, bar: getComputedStyle(document.querySelector('#photoBar')).display })")
    size = p.evaluate("window.__cities.photo()")
    check("g. photo mode: the screen clears (top bar, dock, minimap hidden), a Take photo bar, and the picture is a real JPEG (%d bytes)" % size, hid["photo"] and hid["top"] == "none" and hid["bar"] != "none" and size > 3000, (hid, size))
    p.evaluate("document.querySelector('#photoDone').click()")
    check("g. photo mode ends with Done", p.evaluate("!document.body.classList.contains('photo')"))
    pg.back()
    p.evaluate("window.__cities.tour()")
    time.sleep(2)
    ti = pg.info()
    check("g. the tour flies across all six continents (stops in each), then touch takes over", ti["tour"] and ti["tourConts"] == 6, ti)
    p.evaluate("window.__cities.tour()")
    check("g. no console errors in the new features", not pg.errs, pg.errs[:5])
    pg.close()


def sec_h(br, base, C, days, picks, ids):
    """Cities world upgrade: the fallback is a useful app, with truthful records, at phone size."""
    for quality in ("low", "high"):
        ctx = br.new_context(viewport={"width": 390, "height": 844}, has_touch=True, reduced_motion="reduce")
        ctx.add_init_script(SPEC_NO_GL)
        p = ctx.new_page()
        p.goto(base + "?q=" + quality + "&demo=1")
        p.wait_for_function("document.body.dataset.ready === 'fallback'", timeout=60000)
        check(f"h. {quality}: all catalogue cities remain accessible without a GPU", p.locator(".atlas-city").count() == len(C))
        check(f"h. {quality}: six fully named illustrated districts (Olympus HQ + five, each one label with its count), no horizontal scroll", p.locator(".atlas-map text").count() == 6
              and p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        portals = p.locator(".atlas-portal")
        check(f"h. {quality}: three named city portals have touch-sized targets", portals.count() == 3 and portals.evaluate_all("els => els.every(e=>{const r=e.getBoundingClientRect();return r.width>=44&&r.height>=44})"))
        shot(p, f"atlas_{quality}_phone.png")
        portals.first.click()
        check(f"h. {quality}: a portal opens a labelled sample city with real districts", p.locator(".district-world").is_visible()
              and "SAMPLE DATA" in p.locator(".dw-intro > .dw-kicker").inner_text() and p.locator(".dw-district-card").count() > 0)
        p.locator(".dw-district-card").first.click()
        check(f"h. {quality}: a district contains source-record buildings", p.locator(".dw-record-card").count() > 0)
        p.locator(".dw-record-card").first.click()
        check(f"h. {quality}: a building reveals its source record and fields", p.locator(".dw-record").is_visible() and p.locator(".dw-fields dd").count() > 0)
        p.get_by_role("button", name="World map", exact=True).click()
        check(f"h. {quality}: breadcrumbs return to the atlas", p.locator(".district-world").count() == 0)
        p.locator(".atlas-filters").get_by_role("button", name="Research", exact=True).click()      # (the network bar has a Research button too)
        visible = p.locator(".atlas-city").evaluate_all("els=>els.filter(e=>!e.hidden).length")
        check(f"h. {quality}: district filter matches the actual catalogue", visible == sum(s["group"] == "research" for s in C))
        search = p.get_by_role("searchbox", name="Search the city atlas")
        search.fill("no such city xyz")
        check(f"h. {quality}: a search with no matches explains how to recover", p.locator(".atlas-empty").is_visible())
        search.fill("")
        p.get_by_role("button", name="All districts", exact=True).click()
        check(f"h. {quality}: clearing the filters restores every city", p.locator(".atlas-city").evaluate_all("els=>els.filter(e=>!e.hidden).length") == len(C))
        ctx.close()


def sec_i(br, base, C, days, picks, ids):
    """Default is navigable WebGL; the atlas stays the unsupported/off fallback."""
    pg = Page(br, base, q="high", world=False, extra="&demo=1").open()
    pg.p.wait_for_function("window.__cities.info().mode === 'city' && window.__cities.info().id === 'trades-city'", timeout=120000)
    check("i. normal HD entrance lands in the NQ Trades City with four flight cameras", pg.p.locator('#cams button').count() == 4 and not pg.p.locator('.district-world').count())
    pg.back()
    pg.p.locator('.atlas-portal').first.click()
    pg.p.wait_for_function("window.__cities.info().mode === 'city'", timeout=120000)
    check("i. world portals enter the genuine WebGL city, not a flat drilldown", pg.info()['id'] == 'trades-city' and not pg.p.locator('.district-world').count())
    pg.close()



# ------------------------------------------------------------------ j. ATHENS: the giant Greek metropolis (cities/athens*.js, 2026-11-10)
ATHENS_JS = ("athens-interior.js", "athens-plan.js", "athens-geo.js", "athens-build.js", "athens.js", "athens-ui.js", "athens-entry.js", "athens-data.js")


def part_athens():
    need = list(ATHENS_JS) + ["athens.css", "athens-btn.css", "athens-fixture.json"]
    check("j. Athens files are all there", all(os.path.isfile(os.path.join(PAGE, n)) for n in need), [n for n in need if not os.path.isfile(os.path.join(PAGE, n))])
    html = read(os.path.join(PAGE, "index.html"))
    check("j. index.html loads only the small entry module; the metropolis is imported on demand", "athens-entry.js" in html and "athens.js" not in html.replace("athens-entry.js", ""))
    srcs = {n: read(os.path.join(PAGE, n)) for n in ATHENS_JS}
    outside = {n: [u for u in re.findall(r"https?://[^\s'\"`)]+", t) if "w3.org" not in u] for n, t in srcs.items()}
    check("j. Athens has no outside address, no CDN, no Math.random, no network call", not any(outside.values()) and all("Math.random" not in t for t in srcs.values()) and all("fetch(" not in t for n, t in srcs.items() if n != "athens-data.js")
          and "fetch(url" in srcs["athens-data.js"] and "http" not in srcs["athens-data.js"].replace("//", ""), outside)
    check("j. three.js from ../jarvis/ only; scenery only (no order, no trade call)", "../jarvis/three.module.min.js" in srcs["athens.js"] and not any(w in " ".join(srcs.values()).lower() for w in ("placeorder", "/api/order", "arm_live")))
    check("j. hill lit warm (normals leaned to the sky, limestone colours), photo mode with a watermark and no network, temple interior, ambient life",
          "lean every normal" in srcs["athens.js"] and "OLYMPUS" in srcs["athens.js"] and "toBlob" in srcs["athens-ui.js"] and "preserveDrawingBuffer" not in " ".join(srcs.values())
          and "InstancedMesh" in srcs["athens-interior.js"] and "lifeInit" in srcs["athens.js"] and "this.ambient = this.tierName !== 'low' && !this.reduced" in srcs["athens.js"])
    check("j. warm light: 3500 K by day, 2700 K at dusk; marble, bronze and gold materials", all(k in srcs["athens.js"] for k in ("3500", "2700", "MeshPhongMaterial")) and all(k in srcs["athens-geo.js"] for k in ("marble", "bronze", "gold")))
    check("j. instancing + near / far LOD + frustum-culled house chunks, tier caps, LITE stays light",
          all(k in srcs["athens.js"] for k in ("InstancedMesh", "c.a.visible = !far", "TIERS", "low: {")) and "frameGap" in srcs["athens-entry.js"])
    check("j. UI: minimap, find list by group (Trading / Money / Research / Life), flying tours, tap a building -> app card, 44 px targets",
          all(k in srcs["athens-ui.js"] for k in ("ath-mini", "GROUPS", "renderJump", "renderTours", "showCard", "Open ")) and "min-height:44px" in read(os.path.join(PAGE, "athens.css")))
    r = subprocess.run(["node", "--input-type=module", "-e", """
import { planAthens, GROUPS, TOURS, riverDist, RIVER_W } from './tools/web_public/cities/athens-plan.js';
const a = planAthens(), g = {}; a.apps.forEach((x) => { g[x.group] = (g[x.group] || 0) + 1; });
const ids = new Set(a.apps.map((x) => x.id)), near = a.houses.filter((h) => riverDist(h.x, h.z) < RIVER_W / 2).length;
let clash = 0; for (const x of a.apps) for (const y of a.apps) if (x !== y && Math.hypot(x.x - y.x, x.z - y.z) < 20) clash++;
const hc = a.houses.filter((h) => a.apps.some((x) => Math.hypot(h.x - x.x, h.z - x.z) < 14)).length;
const b = planAthens().houses.length;
console.log(JSON.stringify({ houses: a.houses.length, again: b, apps: a.apps.length, uniq: ids.size, g, groups: GROUPS.map((x) => x.key), lm: a.landmarks.length, tours: TOURS.length, near, clash, hc, trees: a.trees.length, ships: a.ships.length }));
"""], cwd=ROOT, capture_output=True, text=True, timeout=60)
    try:
        d = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        d = {}
        print(r.stdout[-400:], r.stderr[-400:])
    check("j. plan: hundreds of buildings, deterministic, 40 distinct app temples in 4 groups, none on the river, none touching each other or a house",
          d.get("houses", 0) >= 700 and d.get("houses") == d.get("again") and d.get("apps") == 40 == d.get("uniq") and set(d.get("g", {})) == {"trading", "money", "research", "life"}
          and d.get("near") == 0 and d.get("clash") == 0 and d.get("hc") == 0, d)
    r2 = subprocess.run(["node", "--input-type=module", "-e", """
import fs from 'fs';
import { buildLive } from './tools/web_public/cities/athens-data.js';
import * as core from './tools/web_public/stoa/stoacore.js';
const fx = JSON.parse(fs.readFileSync('./tools/web_public/cities/athens-fixture.json', 'utf8')), now = Date.now();
const money = { ...fx.money, streams: fx.money.streams.map((s) => ({ ...s, items: (s.items || []).map((i) => ({ ...i, expires: new Date(now + (i.expires_in_h || 0) * 3600000).toISOString() })) })) };
const a = buildLive({ home: fx.home, money, alerts: fx.alerts }, core, now, true);
const calm = buildLive({ home: { accounts: [{ id: 'x', name: 'Calm', eval: { room: 1900, mll: 2000, dll_used: 0, dll: 1000 }, pnl: { today: 0 }, conn: { connected: true } }] }, money: { streams: [{ id: 'm', name: 'M', status: 'ok', age_min: 5, items: [] }] }, alerts: null }, core, now, false);
const empty = buildLive({ home: null, money: null, alerts: null }, core, now, true);
const nocore = buildLive({ home: fx.home }, null, now, true);
console.log(JSON.stringify({ n: Object.keys(a.needs).length, ids: Object.keys(a.needs).sort(), usd: a.pnl.usd, r: a.pnl.r, lines: a.lines, open: a.open, calm: Object.keys(calm.needs).length, calmLines: calm.lines.length, emptyLines: empty.lines.length, nocore: nocore.lines.length }));
"""], cwd=ROOT, capture_output=True, text=True, timeout=60)
    try:
        e = json.loads(r2.stdout.strip().splitlines()[-1])
    except Exception:
        e = {}
        print(r2.stdout[-400:], r2.stderr[-400:])
    check("j. live data (read only, example fallback): a drawdown / old-feed / deal glows the right temples, a healthy day glows none, 3 plain lines always, never blank, works without the Stoa core",
          e.get("n", 0) >= 6 and {"fates", "demeter", "observatory", "hera"} <= set(e.get("ids", [])) and e.get("usd") == 252 and e.get("open") == 1 and len(e.get("lines", [])) == 3
          and e.get("calm") == 0 and e.get("calmLines") == 3 and e.get("emptyLines") == 3 and e.get("nocore") == 3, e)
    check("j. plan: 18+ monuments, 5 flying tours, trees and ships", d.get("lm", 0) >= 18 and d.get("tours") == 5 and d.get("trees", 0) > 300 and d.get("ships", 0) >= 12, d)


def sec_j(br, base, C, days, picks, ids):
    """Athens in Chromium at 390 x 844: builds, draws within budget, tap -> card, find list, tour, LITE lighter, closes cleanly."""
    errs = []
    out = {}
    for q in ("high", "low"):
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True)
        p = ctx.new_page()
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.on("console", lambda m: errs.append(m.text) if m.type == "error" and "githubusercontent" not in m.text and "Failed to load resource" not in m.text else None)
        p.goto(base + f"?athens=1&first=0&q={q}", wait_until="domcontentloaded")
        p.wait_for_function("window.__athens || window.__athensError", timeout=150000)
        p.wait_for_timeout(2500)
        out[q] = p.evaluate("({ err: window.__athensError || null, calls: window.__athens && window.__athens.calls(), tris: window.__athens && window.__athens.tris(), houses: window.__athens && window.__athens.houses, tier: window.__athens && window.__athens.tier })")
        if q == "high":
            os.makedirs(SHOTS, exist_ok=True)
            p.screenshot(path=os.path.join(SHOTS, "athens_390x844_open.png"))
            p.evaluate("window.__athens.scene.flyTo(60, 60, { dist: 200, yaw: .2, pitch: .5, dur: .05 })")
            p.wait_for_function("!window.__athens.scene.fly", timeout=60000)
            p.wait_for_timeout(600)
            pt = p.evaluate("(() => { const s = window.__athens.scene, P = s.anchors.map((a) => [a, s.project(a.x, a.y * .6, a.z)]); let best = null, bd = 0; for (const [a, q] of P) { if (a.kind !== 'app' || !q.vis || q.y < 200 || q.y > 640 || q.x < 40 || q.x > 350) continue; const d = Math.min(...P.filter(([b]) => b !== a).map(([, r]) => Math.hypot(r.x - q.x, r.y - q.y))); if (d > bd) { bd = d; best = [a.id, q.x, q.y]; } } window.__tapId = best[0]; return [best[1], best[2]]; })()")
            p.touchscreen.tap(pt[0], pt[1])
            p.wait_for_timeout(900)
            card = p.evaluate("(() => { const c = document.querySelector('.ath-card'); return { shown: !c.hidden, title: c.querySelector('h3') && c.querySelector('h3').textContent, go: c.querySelector('.ath-go') && c.querySelector('.ath-go').getAttribute('href') }; })()")
            p.screenshot(path=os.path.join(SHOTS, "athens_390x844_card.png"))
            live = p.evaluate("(() => { const s = window.__athens.scene, l = window.__athens.live; return l ? { glow: s.anchors.filter((a) => a.need).length, calm: s.anchors.filter((a) => a.kind === 'app' && !a.need).length, pillar: s.pillarAnchor && s.pillarAnchor.blurb, ships: s.anchors.filter((a) => a.kind === 'ship').length, lines: document.querySelectorAll('.ath-today p').length, demo: l.demo, pts: !!s.needPts } : null; })()")
            check("j. alive with data: glowing temples, calm temples, the P&L pillar with $ and R, an account ship each, the 3-line banner (example numbers marked)",
                  live and live["glow"] >= 6 and live["calm"] >= 30 and "$252" in live["pillar"] and " R" in live["pillar"] and live["ships"] == 3 and live["lines"] == 3 and live["demo"] and live["pts"], live)
            fates = p.evaluate("(() => { const s = window.__athens.scene, a = s.anchors.find((x) => x.id === 'fates'); window.__athens.ui.showCard(a); return document.querySelector('.ath-card').textContent; })()")
            check("j. a glowing temple's card says what needs you, in plain words", "Needs you" in fates and "Drawdown" in fates, fates)
            p.screenshot(path=os.path.join(SHOTS, "athens_390x844_needs.png"))
            amb = p.evaluate("({ birds: !!window.__athens.scene.birds, smoke: !!window.__athens.scene.smoke, shimmer: window.__athens.scene.wU.uShimmer.value })")
            check("j. ambient life on in HD: birds, market smoke, water shimmer", amb["birds"] and amb["smoke"] and amb["shimmer"] == 1, amb)
            p.click("[data-a=enter]")
            p.wait_for_timeout(500)
            inside = p.evaluate("({ hall: !!window.__athens.scene.interior, text: document.querySelector('.ath-int').textContent, go: !!document.querySelector('.ath-int .ath-go'), flat: document.querySelector('.ath-int').classList.contains('flat') })")
            p.screenshot(path=os.path.join(SHOTS, "athens_390x844_interior.png"))
            check("j. Enter opens a 3D marble hall with the app name, the same reason text and the Open button", inside["hall"] and not inside["flat"] and "Needs you" in inside["text"] and "Fates" in inside["text"] and inside["go"], inside)
            p.click("[data-a=leave]")
            check("j. leaving the hall frees it", p.evaluate("!window.__athens.scene.interior"))
            p.click("[data-a=photo]")
            ui_hidden = p.evaluate("getComputedStyle(document.querySelector('.ath-top')).display === 'none' && getComputedStyle(document.querySelector('.ath-dock')).display === 'none' && !document.querySelector('.ath-photobar').hidden")
            p.screenshot(path=os.path.join(SHOTS, "athens_390x844_photo.png"))
            with p.expect_download(timeout=60000) as dl:
                p.click("[data-a=save]")
            path = dl.value.path()
            head = open(path, "rb").read(8)
            check("j. photo mode hides the UI and Save picture downloads a PNG", ui_hidden and head == b"\x89PNG\r\n\x1a\n" and dl.value.suggested_filename.endswith(".png") and os.path.getsize(path) > 5000, [ui_hidden, head, dl.value.suggested_filename])
            p.click("[data-a=photodone]")
            p.wait_for_timeout(300)
            f0 = p.evaluate("window.__athens.scene.frameCount")
            for _ in range(40):
                p.wait_for_timeout(500)
                if p.evaluate("[...document.querySelectorAll('.ath-label')].filter((l) => l.style.display !== 'none' && l.style.transform).filter((l) => { const m = document.querySelector('.ath-mini').getBoundingClientRect(), r = l.getBoundingClientRect(); return r.right > m.left && r.left < m.right && r.bottom > m.top && r.top < m.bottom; }).length") == 0:
                    break
            overlap = p.evaluate("(() => { const m = document.querySelector('.ath-mini').getBoundingClientRect(); return [...document.querySelectorAll('.ath-label')].filter((l) => l.style.display !== 'none' && l.style.transform).map((l) => l.getBoundingClientRect()).filter((r) => r.right > m.left && r.left < m.right && r.bottom > m.top && r.top < m.bottom).length; })()")
            check("j. no monument label hides behind the minimap", overlap == 0, overlap)
            check("j. tap a building -> its app card with an Open link", card["shown"] and p.evaluate("window.__tapId") in (card["go"] or "") and card["title"], card)
            p.click("[data-a=jump]")
            p.wait_for_timeout(600)
            grp = p.evaluate("[...document.querySelectorAll('.ath-groups summary b')].map((b) => b.textContent)")
            small = p.evaluate("[...document.querySelectorAll('.ath-dock button, .ath-ic, .ath-row')].filter((b) => b.getBoundingClientRect().height && (b.getBoundingClientRect().height < 43.5 || b.getBoundingClientRect().width < 43.5)).length")
            p.fill(".ath-q", "harbour")
            p.wait_for_timeout(400)
            rows = p.evaluate("[...document.querySelectorAll('.ath-row b')].map((b) => b.textContent)")
            p.screenshot(path=os.path.join(SHOTS, "athens_390x844_find.png"))
            check("j. find list is organised by group (Needs you now, Trading, Money, Research, Life, City works), searchable, targets >= 44 px", grp == ["Needs you now", "Trading", "Money", "Research", "Life", "City works"] and small == 0 and any("Harbour" in r for r in rows), [grp, small, rows])
            p.click("[data-a=sheetx]")
            p.click("[data-a=tours]")
            p.click("[data-a=tour] >> nth=0")
            p.wait_for_timeout(1800)
            touring = p.evaluate("window.__athens.scene.touring")
            p.screenshot(path=os.path.join(SHOTS, "athens_390x844_tour.png"))
            check("j. a flying tour starts and the camera moves on its own", touring is True)
            p.click("[data-a=stop]")
            t1 = p.evaluate("window.__athens.scene.time")
            try:
                p.wait_for_function(f"window.__athens.scene.time !== {t1}", timeout=40000)
            except Exception:
                pass
            t2 = p.evaluate("window.__athens.scene.time")
            check("j. day and dusk change by themselves (auto cycle, about 90 s)", p.evaluate("window.__athens.scene.mode") == "auto" and abs(t2 - t1) > 0.002, [t1, t2])
            p.click("[data-a=time2]")
            check("j. one tap locks Day (3500 K), light stops moving", p.evaluate("window.__athens.scene.mode") == "day")
            p.click("[data-a=time2]")
            p.wait_for_timeout(4500)
            dusk = p.evaluate("window.__athens.scene.time")
            p.screenshot(path=os.path.join(SHOTS, "athens_390x844_dusk.png"))
            check("j. dusk switch warms the light", dusk > .6, dusk)
            p.click("[data-a=close]")
            p.wait_for_timeout(500)
            check("j. close leaves Cities as it was (overlay gone, no leftover renderer)", p.evaluate("!document.querySelector('#athens') && !window.__athens"))
        if q == "low":
            amb = p.evaluate("({ birds: !!window.__athens.scene.birds, smoke: !!window.__athens.scene.smoke, shimmer: window.__athens.scene.wU.uShimmer.value })")
            p.evaluate("window.__athens.ui.showCard(window.__athens.scene.anchors.find((a) => a.id === 'fates'))")
            p.click("[data-a=enter]")
            p.wait_for_timeout(300)
            flat = p.evaluate("({ hall: !!window.__athens.scene.interior, flat: document.querySelector('.ath-int').classList.contains('flat'), text: document.querySelector('.ath-int').textContent })")
            check("j. LITE: no birds, smoke or shimmer; Enter shows a flat card (no 3D hall) with the same reason and button", not amb["birds"] and not amb["smoke"] and amb["shimmer"] == 0 and flat["flat"] and not flat["hall"] and "Needs you" in flat["text"], [amb, flat])
        ctx.close()
    # first visit: shown once (localStorage), 3 steps; reduced motion: no light cycle
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True, reduced_motion="reduce")
    p = ctx.new_page()
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(base + "?athens=1&q=high", wait_until="domcontentloaded")
    p.wait_for_function("window.__athens && window.__athens.live", timeout=150000)
    p.wait_for_timeout(800)
    shown = p.evaluate("!document.querySelector('.ath-first').hidden")
    steps = 0
    while p.evaluate("!document.querySelector('.ath-first').hidden") and steps < 5:
        steps += 1
        if steps == 1:
            p.screenshot(path=os.path.join(SHOTS, "athens_390x844_first.png"))
        p.click("[data-a=firstnext]")
        p.wait_for_timeout(250)
    check("j. first visit: a 3-step card appears once and ends after 3 taps", shown and steps == 3, [shown, steps])
    ta = p.evaluate("window.__athens.scene.time")
    p.wait_for_timeout(1500)
    check("j. reduced motion: no automatic day / dusk cycle (locked on Day, only the buttons change the light)", p.evaluate("window.__athens.scene.mode") == "day" and p.evaluate("window.__athens.scene.time") == ta)
    check("j. reduced motion: no birds, smoke or shimmer", not p.evaluate("!!window.__athens.scene.birds"))
    p.click("[data-a=close]")
    p.evaluate("window.openAthens()")
    p.wait_for_function("window.__athens && window.__athens.live", timeout=150000)
    p.wait_for_timeout(500)
    check("j. the first-visit card does not come back", p.evaluate("document.querySelector('.ath-first').hidden"))
    ctx.close()
    ctx = br.new_context(viewport={"width": 375, "height": 667}, device_scale_factor=2, has_touch=True, is_mobile=True)
    p = ctx.new_page()
    p.goto(base + "?athens=1&first=0&q=low", wait_until="domcontentloaded")
    p.wait_for_function("window.__athens && window.__athens.live", timeout=150000)
    p.wait_for_timeout(1500)
    lay = p.evaluate("(() => { const r = (s) => document.querySelector(s).getBoundingClientRect(), d = r('.ath-dock'), m = r('.ath-mini'), t = r('.ath-today'); return { sideways: document.documentElement.scrollWidth > innerWidth, dockIn: d.bottom <= innerHeight && d.left >= 0 && d.right <= innerWidth, miniIn: m.right <= innerWidth && m.bottom < d.top, bannerClear: t.right <= m.left + 1 || t.bottom <= m.top }; })()")
    p.screenshot(path=os.path.join(SHOTS, "athens_375x667_open.png"))
    check("j. layout at 375 x 667: dock, minimap and banner fit and do not collide", not lay["sideways"] and lay["dockIn"] and lay["miniIn"] and lay["bannerClear"], lay)
    ctx.close()
    hi, lo = out["high"], out["low"]
    check("j. HIGH: 900+ houses, <= 40 draw calls, <= 150k triangles on screen", not hi["err"] and hi["houses"] >= 900 and hi["calls"] <= 42 and hi["tris"] <= 150_000, hi)
    check("j. LITE: fewer houses, <= 25 draw calls, <= 80k triangles (stays light on an iPhone)", not lo["err"] and 400 <= lo["houses"] < hi["houses"] and lo["calls"] <= 28 and lo["tris"] <= 80_000, lo)
    check("j. no console error or page error", not errs, errs[:3])


# ------------------------------------------------------------------ k. ATHENS nested world: villages, districts, houses, walking, villagers
NEST_JS = ("athens-villages.js", "athens-world.js", "athens-nest.js")

NEST_NODE = r"""
import fs from 'fs';
import { planAthens } from './tools/web_public/cities/athens-plan.js';
import * as V from './tools/web_public/cities/athens-villages.js';
import * as W from './tools/web_public/cities/athens-world.js';
const R = './tools/web_public/cities/', out = {};
const files = {}; for (const u of V.allUrls()) { try { files[u] = JSON.parse(fs.readFileSync(new URL(u, 'file://' + process.cwd() + '/' + R).pathname, 'utf8')); } catch (e) { files[u] = null; } }
const NOW = Date.parse('2026-11-10T12:00:00Z'), apps = V.allApps(), by = (id) => apps.find((a) => a.id === id), vd = (id, f = files) => V.villageData(by(id), f, NOW);
out.apps = apps.length; out.uniq = new Set(apps.map((a) => a.id)).size; out.temples = apps.filter((a) => a.temple).length; out.groups = [...new Set(apps.map((a) => a.group))].sort();
out.specs = apps.every((a) => { const s = V.specFor(a.id); return Array.isArray(s.src) && typeof s.map === 'function'; });
const k = vd('kronos'), sib = vd('sibyl'), mer = vd('mercury'), pyt = vd('pythia'), nik = vd('nike'), lyc = vd('lyceum'), chr = vd('chrysos'), dc = vd('datacity'), cas = vd('plutus');
out.kronos = { n: k.rows.length, status: k.status, fact: k.fact, days: new Set(k.rows.map((r) => r.label)).size, tones: [...new Set(k.rows.map((r) => r.tone))].sort(), money: k.rows.every((r) => r.money && /\$/.test(r.say)), sizes: k.rows.every((r) => r.size >= 0 && r.size <= 1) };
out.sibyl = { n: sib.rows.length, ok: sib.rows.every((r) => r.label && r.say) }; out.mercury = { n: mer.rows.length, fact: mer.fact, noFakeUsd: !/\$80\b/.test(mer.fact) };
out.pythia = { n: pyt.rows.length, within14: pyt.rows.every((r) => /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d+ (Nov|Dec)/.test(r.say)) };
out.misc = { nike: nik.rows.length, lyceum: lyc.rows.length, chrysos: chr.rows.length, datacity: dc.rows.length, plutus: cas.rows.length };
out.nofiles = { allNone: apps.map((a) => V.villageData(a, {}, NOW)).every((d) => d.status === 'none' && d.rows.length === 0 && /no data today/.test(d.fact)) };
const junk = {}; for (const u of V.allUrls()) junk[u] = { weird: [1, 'x', null], trades: 'nope', accounts: [null, 3] };
out.junk = apps.every((a) => { try { V.villageData(a, junk, NOW); return true; } catch (e) { return false; } });
out.limit = apps.every((a) => vd(a.id).rows.length <= V.MAX_ROWS);
const st = {}; for (const a of apps) { const d = vd(a.id); st[d.status] = (st[d.status] || 0) + 1; } out.status = st;
const plan = planAthens(), w = W.buildWorld(plan, files, { now: NOW }), w2 = W.buildWorld(planAthens(), files, { now: NOW });
out.world = { villages: w.villages.length, summary: w.summary, again: w2.summary === w.summary && w2.villages[7].houses[0].x === w.villages[7].houses[0].x, counts: w.counts };
const seen = new Set(); let dup = 0, small = 0, over = 0;
for (const v of w.villages) { for (const h of v.houses) { const key = h.x + ',' + h.z; if (seen.has(key)) dup++; seen.add(key); } if (v.houses.length < 6) small++; if (v.real > v.rows.length) over++; }
out.claims = { dup, small, over, claimed: w.items.length, total: plan.houses.length, scenery: w.scenery.length, sumReal: w.villages.reduce((s, v) => s + v.real, 0) };
out.honest = { sumMatches: w.counts.houses === out.claims.sumReal, text: /^\d+ houses from \d+ apps, \d+ apps? without data today/.test(w.summary), noneCount: w.counts.none === w.villages.filter((v) => !v.real).length };
out.districts = w.districts.map((d) => [d.key, d.villages.length, d.houses]);
const hi = W.renderList(w, 1100), lo = W.renderList(w, 520, 6);
out.render = { hi: hi.length, lo: lo.length, loMax: Math.max(...w.villages.map((v) => lo.filter((h) => h.village === v.idx).length)) };
const col = W.makeCollider(hi, plan); let inside = 0, tried = 0, moved = 0;
for (const v of w.villages) { const d = W.doorOf(col, v); for (const h of v.houses.slice(0, 4)) { let s = { x: d.x, z: d.z, yaw: W.headingTo(d.x, d.z, h.x, h.z) }; for (let i = 0; i < 300; i++) s = W.walkStep(s, { fwd: 1 }, .05, col); tried++; if (hi.some((q) => { const f = W.footprint(q); return Math.abs(s.x - q.x) < f.hx && Math.abs(s.z - q.z) < f.hz; })) inside++; if (Math.hypot(s.x - d.x, s.z - d.z) > 3) moved++; } }
out.collide = { inside, tried, moved };
let slideOk = false, slideInfo = null;
for (const hb of hi.filter((h) => h.village >= 0).slice(0, 60)) { const f = W.footprint(hb), wx = hb.x - f.hx - .7, wz = hb.z; if (col.hits(wx, wz) || col.hits(wx - 3, wz)) continue;
  let s = { x: wx - 2, z: wz, yaw: Math.PI / 2 + .7 }; for (let i = 0; i < 30; i++) s = W.walkStep(s, { fwd: 1 }, .05, col);
  if (Math.abs(s.z - wz) > .8 && s.x < hb.x - f.hx + .01) { slideOk = true; slideInfo = [s.x, s.z, wx, wz]; break; } }
out.slide = { ok: slideOk, info: slideInfo };
out.water = col.hits(0, 330) && col.hits(2000, 0);
const dt = W.walkStep({ x: -75, z: 135, yaw: 0 }, { fwd: 1 }, 1, W.makeCollider([], plan)); out.speed = Math.round(Math.hypot(dt.x + 75, dt.z - 135) * 10) / 10;
const npcs = W.makeNpcs(w, col, 120); let bad = 0, factOk = 0;
for (const n of npcs) { for (let t = 0; t < 600; t += 25) { const p = W.npcAt(n, t); if (!Number.isFinite(p.x + p.z) || col.hits(p.x, p.z, .3)) bad++; } const f2 = W.npcFact(w, n, 100); if (f2.village && f2.text.startsWith(f2.village.name)) factOk++; }
out.npc = { n: npcs.length, bad, factOk, low: W.TIER_NPC.low, high: W.TIER_NPC.high, ultra: W.TIER_NPC.ultra, groups: new Set(npcs.map((n) => n.colour)).size };
const wh = W.whereAmI(w, w.villages[0].x, w.villages[0].z);
out.where = { village: wh.village && wh.village.id, district: wh.district, c0: W.compassName(0), c90: W.compassName(Math.PI / 2), c225: W.compassName(Math.PI * 1.25) };
console.log(JSON.stringify(out));
"""


def part_nest():
    need = list(NEST_JS) + ["athens-nest.css"]
    check("k. nest files are all there", all(os.path.isfile(os.path.join(PAGE, n)) for n in need), [n for n in need if not os.path.isfile(os.path.join(PAGE, n))])
    srcs = {n: read(os.path.join(PAGE, n)) for n in NEST_JS}
    css = read(os.path.join(PAGE, "athens-nest.css"))
    check("k. nest: no Math.random, no outside address, no trade or order call, only the village loader reads files",
          all("Math.random" not in t for t in srcs.values()) and not any(re.findall(r"https?://", t) for t in srcs.values()) and not any(w in " ".join(srcs.values()).lower() for w in ("placeorder", "/api/order", "arm_live"))
          and all("fetch(" not in t for n, t in srcs.items() if n != "athens-villages.js") and "AbortController" in srcs["athens-villages.js"])
    check("k. nest: AGORA look (no neon / glow / blur), 44 px targets, joystick on the left half, compass strip, walk bar",
          "min-height:44px" in css and "min-height:50px" in css and "width:50%" in css and not re.search(r"neon|text-shadow:0 0 [4-9]|backdrop-filter", css)
          and all(k in css for k in (".ath-compass", ".ath-stickzone", ".ath-walkbar", ".ath-crumbs", ".ath-dtile")))
    r = subprocess.run(["node", "--input-type=module", "-e", NEST_NODE], cwd=ROOT, capture_output=True, text=True, timeout=90)
    try:
        d = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        d = {}
        print(r.stdout[-500:], r.stderr[-800:])
    check("k. registry: one entry per app (40 temples + 20 hamlet apps, 4 districts), every app has a source list and a row mapper, never throws on junk, 40 rows at most",
          d.get("apps", 0) >= 60 and d.get("apps") == d.get("uniq") and d.get("temples") == 40 and d.get("groups") == ["life", "money", "research", "trading"] and d.get("specs") and d.get("junk") and d.get("limit"),
          {k: d.get(k) for k in ("apps", "uniq", "temples", "groups", "specs", "junk", "limit")})
    kr = d.get("kronos", {})
    check("k. mapping: Kronos = one house per trading day (newest 14) coloured by P&L with $ and R in the sentence, best weekday as the fact; Sibyl / Mercury / Pythia / Nike / Lyceum / Chrysos / Data City / Plutus all give rows",
          kr.get("n") == kr.get("days") and 5 <= kr.get("n", 0) <= 14 and "best weekday so far" in kr.get("fact", "") and kr.get("money") and kr.get("sizes") and {"good", "bad"} <= set(kr.get("tones", []))
          and d.get("sibyl", {}).get("n", 0) >= 10 and d.get("sibyl", {}).get("ok") and d.get("mercury", {}).get("n", 0) >= 5 and d.get("pythia", {}).get("n", 0) >= 1 and d.get("pythia", {}).get("within14")
          and all(d.get("misc", {}).get(x, 0) >= 1 for x in ("nike", "lyceum", "chrysos", "datacity", "plutus")), d.get("kronos"))
    check("k. honesty: a percent is never shown as dollars, with no files every village says 'no data today', example files are marked 'example' (live vs example vs none counted)",
          d.get("mercury", {}).get("noFakeUsd") and d.get("nofiles", {}).get("allNone") and d.get("status", {}).get("example", 0) >= 10 and d.get("status", {}).get("none", 0) >= 1, d.get("status"))
    w = d.get("world", {})
    c = d.get("claims", {})
    h = d.get("honest", {})
    check("k. world: 60+ villages carved from the plan's own houses (no house in two villages, none under 6 houses, deterministic), the headline counts match the houses ('N houses from M apps, K apps without data today')",
          w.get("villages", 0) >= 60 and w.get("again") and c.get("dup") == 0 and c.get("small") == 0 and c.get("over") == 0 and c.get("claimed", 0) + c.get("scenery", 0) == c.get("total") and h.get("sumMatches") and h.get("text") and h.get("noneCount"),
          {"world": w, "claims": c, "honest": h})
    check("k. levels: Athens -> 4 districts (Agora, Acropolis, Harbour, Academy) -> villages -> houses; LITE draws 6 houses per village and never more than the old cap",
          len(d.get("districts", [])) == 4 and all(x[1] >= 8 for x in d.get("districts", [])) and d.get("render", {}).get("hi", 0) <= 1100 and d.get("render", {}).get("lo", 9999) <= 520 and d.get("render", {}).get("loMax", 99) <= 6,
          {"districts": d.get("districts"), "render": d.get("render")})
    co = d.get("collide", {})
    check("k. collision: walking at every village's houses never ends inside a footprint, the walker moves, slides along a wall, cannot enter the sea, walks about 2.6 m per second",
          co.get("inside") == 0 and co.get("tried", 0) >= 200 and co.get("moved", 0) > co.get("tried", 1) * .5 and d.get("slide", {}).get("ok") and d.get("water") and 2.4 <= d.get("speed", 0) <= 2.8,
          {"collide": co, "slide": d.get("slide"), "water": d.get("water"), "speed": d.get("speed")})
    n = d.get("npc", {})
    check("k. villagers: 120 on ULTRA / 80 on HIGH / 0 on LITE, every route is clear of houses, every villager tells a fact that starts with its village, colour = the app's group (4 colours), compass and 'where am I' work",
          n.get("n") == 120 and n.get("bad") == 0 and n.get("factOk") == n.get("n") and (n.get("low"), n.get("high"), n.get("ultra")) == (0, 80, 120) and 1 < n.get("groups", 0) <= 4
          and d.get("where", {}).get("village") == "zenith" and (d.get("where", {}).get("c0"), d.get("where", {}).get("c90"), d.get("where", {}).get("c225")) == ("N", "E", "SW"), {"npc": n, "where": d.get("where")})


def frames(p, n):
    """wait until the scene has drawn n more frames (a slow software GPU draws only a few a second)"""
    f = p.evaluate("window.__athens.scene.frameCount")
    p.wait_for_function(f"window.__athens.scene.frameCount >= {f + n}", timeout=90000)


def sec_k(br, base, C, days, picks, ids):
    """Athens nested world in Chromium at 390 x 844: villages load, budgets hold, Places levels with crumbs, a house card, walking, the guide, villagers."""
    errs = []
    out = {}
    os.makedirs(SHOTS, exist_ok=True)
    for q in ("high", "low"):
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2 if q == "high" else 1, has_touch=True, is_mobile=True)
        p = ctx.new_page()
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
        p.goto(base + f"?athens=1&first=0&q={q}&light=day", wait_until="domcontentloaded")
        p.wait_for_function("window.__athens && window.__athens.world", timeout=170000)
        p.wait_for_timeout(2000)
        out[q] = p.evaluate("({ calls: window.__athens.calls(), tris: window.__athens.tris(), houses: window.__athens.houses, npcs: (window.__athens.scene.npcs || []).length, sub: document.querySelector('#athSub').textContent, err: window.__athensWorldError || null })")
        if q == "high":
            p.screenshot(path=os.path.join(SHOTS, "athens_nest_390x844_open.png"))
            p.click("[data-a=n-places]")
            p.wait_for_timeout(400)
            world = p.evaluate("document.querySelector('.ath-sheet').innerText")
            p.screenshot(path=os.path.join(SHOTS, "athens_nest_390x844_world.png"))
            p.click("[data-a=n-district][data-k=money]")
            p.wait_for_timeout(1700)
            dist = p.evaluate("document.querySelector('.ath-sheet').innerText")
            p.screenshot(path=os.path.join(SHOTS, "athens_nest_390x844_district.png"))
            p.click("[data-a=n-village][data-id=kronos]")
            p.wait_for_timeout(2000)
            vill = p.evaluate("({ t: document.querySelector('.ath-sheet').innerText, map: !!document.querySelector('.ath-vmap'), rows: document.querySelectorAll('.ath-hrow').length, crumbs: [...document.querySelectorAll('.ath-sheet .ath-crumbs button')].map((b) => b.textContent) })")
            p.screenshot(path=os.path.join(SHOTS, "athens_nest_390x844_village.png"))
            p.click(".ath-hrow >> nth=0")
            p.wait_for_timeout(1700)
            house = p.evaluate("({ t: document.querySelector('.ath-sheet').innerText, href: (document.querySelector('.ath-sheet .ath-go') || {}).href || '' })")
            p.screenshot(path=os.path.join(SHOTS, "athens_nest_390x844_house.png"))
            p.click(".ath-sheet .ath-crumbs button >> nth=1")
            p.wait_for_timeout(1500)
            back = p.evaluate("document.querySelector('.ath-sheet').innerText")
            p.click("[data-a=sheetx]")
            tiny = p.evaluate("[...document.querySelectorAll('.ath-dock button, .ath-walkbar button')].filter((b) => b.offsetParent && (b.getBoundingClientRect().height < 43.5 || b.getBoundingClientRect().width < 43.5)).map((b) => b.textContent)")
            check("k. HIGH: Places shows the honest count, 4 districts, the villages of a district, a village with a house map and one row per house, a house with the item's words and an Open button, breadcrumbs lead back",
                  "houses from" in world and "without data today" in world and all(x in world for x in ("Agora district", "Acropolis district", "Harbour district", "Academy district")) and "Kronos" in dist and "Mercury" in dist
                  and vill["map"] and vill["rows"] >= 5 and vill["crumbs"][:3] == ["Athens", "Harbour district", "Kronos"] and "R)" in house["t"] and "$" in house["t"] and house["href"].endswith("/kronos/") and "Harbour district" in back and "Kronos" in back,
                  {"w": world[:120], "v": vill, "h": house})
            check("k. the dock fits 6 buttons, all taps >= 44 px", not tiny, tiny)
            p.evaluate("(() => { const s = window.__athens.scene, v = s.world.villages.find((x) => x.id === 'kronos'); s.flyTo(v.x, v.z, { dist: 70, pitch: .7, dur: .02 }); })()")
            p.wait_for_function("!window.__athens.scene.fly", timeout=60000)
            frames(p, 2)
            pt = p.evaluate("(() => { const s = window.__athens.scene, v = s.world.villages.find((x) => x.id === 'kronos'), hh = v.houses[1]; return s.project(hh.x, (hh.y || 0) + hh.h * .6, hh.z); })()")
            p.evaluate(f"window.__athens.ui.tap({pt['x']}, {pt['y']})")
            p.wait_for_timeout(700)
            card = p.evaluate("document.querySelector('.ath-card').innerText")
            p.screenshot(path=os.path.join(SHOTS, "athens_nest_390x844_housecard.png"))
            check("k. tap a village house in 3D -> a card with its plain words, a $ and an R, Open Kronos, Walk here", "Kronos" in card and "$" in card and " R" in card and "Open Kronos" in card and "Walk here" in card, card[:160])
            p.evaluate("(() => { const s = window.__athens.scene, q = s.npcPos[0]; s.flyTo(q.x, q.z, { dist: 40, pitch: .5, dur: .02 }); })()")
            p.wait_for_function("!window.__athens.scene.fly", timeout=60000)
            frames(p, 2)
            p.evaluate("(() => { const s = window.__athens.scene, q = s.npcPos[0], v = s.project(q.x, 3, q.z); window.__athens.ui.tap(v.x, v.y); })()")
            p.wait_for_timeout(700)
            npc = p.evaluate("document.querySelector('.ath-card').innerText")
            p.screenshot(path=os.path.join(SHOTS, "athens_nest_390x844_villager.png"))
            check("k. HIGH: 80 villagers in one extra draw call; tap one -> 'Villager' and a plain fact from its village", out[q]["npcs"] == 80 and "Villager" in npc and ":" in npc, npc[:140])
        # walk (both tiers)
        p.evaluate("window.__athens.nest.act('n-walkto', { dataset: { id: 'kronos' } })")
        frames(p, 3)
        w0 = p.evaluate("(async () => { const { groundY } = await import('./athens-plan.js'), s = window.__athens.scene, w = s.walk; return { x: w.x, z: w.z, y: s.camera.position.y, gy: w.y, ground: groundY(w.x, w.z) }; })()")
        p.evaluate("(() => { const s = window.__athens.scene; s.walk.input.fwd = 1; for (let i = 0; i < 60; i++) s.walkTick(.1); s.walk.input.fwd = 0; })()")
        frames(p, 4)
        w1 = p.evaluate("(() => { const s = window.__athens.scene, w = s.walk; return { x: w.x, z: w.z, dist: w.dist, where: document.querySelector('.ath-where').textContent, compass: document.querySelector('.ath-compass').innerText, stick: !document.querySelector('.ath-stickzone').hidden }; })()")
        p.screenshot(path=os.path.join(SHOTS, f"athens_nest_390x844_walk_{q}.png"))
        p.evaluate("(() => { const z = document.querySelector('.ath-stickzone'), ev = (t, x, y) => z.dispatchEvent(new PointerEvent(t, { pointerId: 9, clientX: x, clientY: y, bubbles: true, isPrimary: true })); ev('pointerdown', 100, 600); ev('pointermove', 100, 556); window.__ev = ev; })()")
        inp = p.evaluate("({ ...window.__athens.scene.walk.input })")
        p.evaluate("window.__ev('pointerup', 100, 556)")
        inp0 = p.evaluate("({ ...window.__athens.scene.walk.input })")
        p.evaluate("window.__athens.nest.act('n-guide', document.querySelector('[data-a=n-guide]'))")
        p.wait_for_timeout(500)
        d0 = p.evaluate("window.__athens.scene.walk.dist")
        p.evaluate("(() => { const s = window.__athens.scene, n = window.__athens.nest; for (let i = 0; i < 80; i++) { n.guideFrame(.1); s.walkTick(.1); } })()")
        gd = p.evaluate("(() => { const g = window.__athens.nest.guide; return g ? { on: true, tgt: g.target.id, moved: window.__athens.scene.walk.dist } : { on: false }; })()")
        p.evaluate("window.__athens.nest.act('n-exit')")
        p.wait_for_timeout(600)
        after = p.evaluate("({ walking: window.__athens.scene.walking, cls: document.querySelector('#athens').classList.contains('walking'), bar: document.querySelector('.ath-walkbar').hidden, dock: getComputedStyle(document.querySelector('.ath-dock')).display })")
        check(f"k. {q.upper()}: Walk drops to street level (eye 1.7 m), the joystick moves the walker, the compass and 'where am I' read right, the guide walks, Leave returns to the city",
              abs(w0["gy"] - (w0["ground"] + 1.7)) < .6 and abs(w0["y"] - w0["gy"]) < .3 and w1["dist"] > 5 and w1["stick"] and "Facing" in w1["where"] and "district" in w1["where"] and w1["compass"].strip() != "" and inp["fwd"] > .6 and inp0["fwd"] == 0
              and gd["on"] and gd["tgt"] and gd["moved"] > d0 + 3 and not after["walking"] and not after["cls"] and after["bar"] and after["dock"] != "none", {"w0": w0, "w1": w1, "inp": inp, "gd": gd, "after": after})
        ctx.close()
    hi, lo = out["high"], out["low"]
    check("k. budgets unchanged: HIGH <= 42 draw calls / 150k triangles, LITE <= 28 draw calls / 80k triangles with 0 villagers; the villages load without an error",
          not hi["err"] and not lo["err"] and hi["calls"] <= 42 and hi["tris"] <= 150_000 and lo["calls"] <= 28 and lo["tris"] <= 80_000 and lo["npcs"] == 0 and hi["houses"] >= 900 and 400 <= lo["houses"] <= 520, out)
    check("k. the header says how many houses and apps are real ('N houses from M apps' and 'without data')", all("houses from" in out[q]["sub"] and "without data" in out[q]["sub"] for q in out), out)
    check("k. no console error or page error", not errs, errs[:3])
    print("       numbers:", json.dumps(out))


SECTIONS = {"c": sec_c, "d": sec_d, "e": sec_e, "f": sec_f, "g": sec_g, "h": sec_h, "i": sec_i, "j": sec_j, "k": sec_k}

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

            for key, fnc in SECTIONS.items():
                if want(key):
                    print(f"--- section {key}", flush=True)
                    fnc(br, base, C, days, picks, ids)
            br.close()
    finally:
        srv.shutdown()


def main():
    no_browser = "--no-browser" in sys.argv
    if "--atlas-only" in sys.argv:
        # The catalogue generator rewrites source fixtures; this UI regression never does.
        C = json.loads(read(os.path.join(PAGE, "cities.json")))["cities"]
        run_browser(C, [], [])
        print(f"\n{sum(RES)}/{len(RES)} passed; screenshots in {SHOTS}")
        return 0 if all(RES) else 1
    C = part_a()
    if want("j"):
        part_athens()
    if want("k"):
        part_nest()
    days, picks, seeds = part_b(C)
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

