"""PROMETHEUS (tools/prometheus/, tools/web_public/prometheus/, 2026-11-03): the strategy-evolution forge.

  a. the GA is deterministic with a seed (same seed = the same history creature for creature; another seed differs), on a
     synthetic fitness and on the real H1 fitness
  b. the bounds: every creature of a long high-mutation run is on the knob grid; the knobs exist in live_model_lit.json and
     the live genome reads them; genome -> params never edits the model; live_model*.json unchanged by the whole test
  c. the fitness uses only 2026 H1: every session handed to engine/lit.py run_x, every trade, every eval unit and every eval
     session index is in 2026-01-01 .. 2026-06-30 (live and random genomes); live reproduces run lit_live's H1 and scores 1.0
  d. the outputs: forge.json schema and size (<= 1 MB), jarvis.json contract (docs/JARVIS_APPS.md), forge_results.json, the
     runlib runs prometheus_s*
  e. the page in Playwright Chromium at 390 x 844: no page / console errors, the generation slider, a tap on a flame opens its
     card (diff vs live, H1 / H2 / 2021-25), the live flame, the verdict panel, the demo fixture (no forge.json), reduced
     motion, no sideways scroll, the bottom-right 80 x 160 px free; screenshots in research/handoff/2026-11-03-day/research_apps/
     prometheus/ (PROMETHEUS_SHOTS=<dir> elsewhere)
  f. the day-sprint upgrade (2026-11-03): every flame in one draw call (the noise fire shader, <= 20 calls a frame), the
     verdict banner ("LIVE LIT STILL BEST" with the numbers), the lineage graph (every creature, the champion's ancestry, a
     tap on a dot opens its card), the Hall of Champions (live first, the fittest distinct genomes, a tap opens the card),
     one bottom sheet clear of the orb, applyTheme(tokens)

    python -X utf8 -m tests.test_prometheus            (parts a-e; e needs Playwright's Chromium)
    python -X utf8 -m tests.test_prometheus fast       (a, b, d: no backtest, no browser)
"""
from __future__ import annotations

import functools
import glob
import hashlib
import http.server
import json
import os
import random
import re
import shutil
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.prometheus import ga as GA  # noqa: E402
from tools.prometheus import genome as G  # noqa: E402

PAGE = os.path.join(ROOT, "tools", "web_public", "prometheus")
SHOTS = os.environ.get("PROMETHEUS_SHOTS") or os.path.join(ROOT, "research", "handoff", "2026-11-03-day", "research_apps", "prometheus")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def model_hashes():
    return {p: hashlib.sha256(open(p, "rb").read()).hexdigest() for p in sorted(glob.glob(os.path.join(ROOT, "live_model*.json")))}


def synth(g):
    """A cheap deterministic fitness with a known optimum (for GA tests)."""
    target = [k.n // 3 for k in G.KNOBS]
    f = -sum((a - b) ** 2 / k.n for a, b, k in zip(g, target, G.KNOBS))
    return round(f, 6), {"pm": f}


def fingerprint(hist):
    return [(c.id, c.gen, c.genome, c.parents, c.mutated, c.origin, c.fit) for gen in hist for c in gen]


# ------------------------------------------------------------------------------------------------ a. determinism
def part_a(real=True):
    sizes = [k.n for k in G.KNOBS]
    base = G.live_genome()
    cfg = GA.GAConfig(pop=16, gens=8, seed=3)
    h1, h2 = GA.evolve(synth, sizes, base, cfg), GA.evolve(synth, sizes, base, cfg)
    check("a. same seed, same history (synthetic fitness: ids, genomes, parents, mutations, fitness)", fingerprint(h1) == fingerprint(h2))
    h3 = GA.evolve(synth, sizes, base, GA.GAConfig(pop=16, gens=8, seed=4))
    check("a. another seed, another history", fingerprint(h1) != fingerprint(h3))
    check("a. generation 0 starts from the live genome (creature #0)", any(c.id == 0 and c.origin == "live" and c.genome == base for c in h1[0]))
    best = [gen[0].fit for gen in h1]
    check("a. elitism: the best fitness never falls from one generation to the next", all(b >= a for a, b in zip(best, best[1:])), best)
    ch = GA.champion(h1)
    line, anc = GA.lineage(h1, ch.id)
    by = {c.id: c for c in GA.all_creatures(h1)}
    check("a. the champion's lineage runs back to generation 0 through real parents",
          line[0] == ch.id and by[line[-1]].gen == 0 and all(line[i + 1] in by[line[i]].parents for i in range(len(line) - 1)), line)
    hof = GA.hall_of_fame(h1, 5)
    check("a. the hall of fame holds distinct genomes, fittest first", len({c.genome for c in hof}) == len(hof)
          and all(a.fit >= b.fit for a, b in zip(hof, hof[1:])))
    if real:
        from tools.prometheus import fitness as FT
        f1, f2 = FT.Fitness(persist=False), FT.Fitness(persist=False)
        c = GA.GAConfig(pop=6, gens=2, n_spark=2, seed=9)
        r1, r2 = GA.evolve(f1, sizes, base, c), GA.evolve(f2, sizes, base, c)
        check("a. same seed, same history on the real H1 fitness (two fresh caches)", fingerprint(r1) == fingerprint(r2))


# ------------------------------------------------------------------------------------------------ b. bounds
def part_b():
    sizes = [k.n for k in G.KNOBS]
    m = G.load_model()
    check("b. 6-10 knobs, each read from live_model_lit.json", 6 <= len(G.KNOBS) <= 10 and all(G._get(m, k.path) is not None for k in G.KNOBS))
    lv = G.live_values(m)
    check("b. the live genome decodes to the live values", G.values(G.live_genome()) == lv, (G.values(G.live_genome()), lv))
    hist = GA.evolve(synth, sizes, G.live_genome(), GA.GAConfig(pop=24, gens=30, pm=0.9, seed=1))
    allc = GA.all_creatures(hist)
    check(f"b. all {len(allc)} creatures of a 30-generation, 90%-mutation run are inside the bounds",
          all(G.in_bounds(c.genome) for c in allc))
    vals = [G.values(c.genome) for c in allc]
    check("b. every decoded value is within its knob's lo..hi", all(k.lo - 1e-9 <= v[k.key] <= k.hi + 1e-9 for v in vals for k in G.KNOBS))
    rng = random.Random(5)
    junk = [tuple(rng.randint(-50, 80) for _ in G.KNOBS) for _ in range(200)]
    check("b. clamp() puts any index vector back on the grid", all(G.in_bounds(G.clamp(g)) for g in junk))
    check("b. sane bounds: entries end before the 15:55 flat, bank above the 1.5R minimum, room share <= 1",
          max(G.KNOBS[G.KEYS.index("win_end")].hi, 0) < 955 and G.KNOBS[G.KEYS.index("max_rr")].lo > G.KNOBS[G.KEYS.index("min_rr")].hi
          and G.KNOBS[G.KEYS.index("room_f")].hi <= 1.0)
    before = json.dumps(m, sort_keys=True)
    g = tuple(k.n - 1 for k in G.KNOBS)
    p = G.lit_params(g, m)
    check("b. genome -> params writes the genome's values and leaves the loaded model untouched",
          json.dumps(m, sort_keys=True) == before and p["cisd1m"] == 40 and p["window"][0][1] == 945 and p["t_check"]["at"] == 40)
    check("b. diff() names exactly the knobs that differ from live", set(G.diff(g)) == {k.key for k in G.KNOBS if G.live_genome()[G.KNOBS.index(k)] != k.n - 1})


# ------------------------------------------------------------------------------------------------ c. H1 only
def part_c():
    from engine import lit
    from tools.prometheus import fitness as FT
    F, A, AC = FT._mods()
    seen = {"sess": [], "trades": [], "evalidx": []}
    orig_run_x, orig_eval = lit.run_x, A.run_eval

    def spy_run_x(M, C, P, sessions=None, **kw):
        seen["sess"].append(list(sessions) if sessions is not None else None)
        T = orig_run_x(M, C, P, sessions, **kw)
        seen["trades"] += [t["day"] for t in T]
        return T

    def spy_eval(seq, by, *a, **kw):
        seen["evalidx"] += list(seq)
        return orig_eval(seq, by, *a, **kw)
    lit.run_x, A.run_eval = spy_run_x, spy_eval
    try:
        rng = random.Random(11)
        gs = [G.live_genome()] + [tuple(rng.randrange(k.n) for k in G.KNOBS) for _ in range(3)]
        out = [FT.h1_metrics(g) for g in gs]
    finally:
        lit.run_x, A.run_eval = orig_run_x, orig_eval
    a, z = FT.SPANS["H1"]
    sess = [d for s in seen["sess"] for d in (s or ["ALL"])]
    check(f"c. every session handed to run_x is a 2026 H1 session ({len(sess)} over {len(gs)} genomes)",
          sess and all(a <= d <= z for d in sess), [d for d in sess if not a <= d <= z][:3])
    check(f"c. every trade the fitness saw is in 2026 H1 ({len(seen['trades'])})", all(a <= d <= z for d in seen["trades"]))
    dates = [A.S26[i] for i in seen["evalidx"]]
    check(f"c. every eval session the fitness simulated is in 2026 H1 ({len(dates)} session steps)",
          dates and all(a <= d <= z for d in dates), max(dates) if dates else None)
    check("c. no H2 date anywhere in the fitness evaluation (latest trade / eval day <= 2026-06-30)",
          max(seen["trades"] + dates) <= "2026-06-30")
    try:
        FT.assert_h1([{"day": "2026-07-01"}])
        raised = False
    except AssertionError:
        raised = True
    check("c. assert_h1 refuses an H2 row", raised)
    L = out[0]
    check("c. live genome on H1 = run lit_live's H1 (80 trades, +$33,901, PF 4.98)", (L["n"], L["net"], L["pf"]) == (80, 33901, 4.98), L)
    check("c. live genome on the H1 eval path = 2-week pass/fail 57.1 / 1.7 (lit_adv_manage.evals)", (L["p10"], L["f10"]) == (57.1, 1.7), L)
    ref = FT.Fitness(persist=False)
    check("c. the live strategy scores fitness 1.0", abs(ref(G.live_genome())[0] - 1.0) < 1e-9)
    check("c. eval_cfg(live) == lit_adv_manage.CFG (the live eval sizing)", FT.eval_cfg(G.live_genome()) == A.CFG)
    low = FT.score({"pm": ref.ref["pm"], "p10": ref.ref["p10"], "f10": ref.ref["f10"], "tpw": 1.0}, ref.ref)
    check("c. fewer than 2 trades a week is penalised (1/wk: fitness 0.5)", abs(low - 0.5) < 1e-9, low)


# ------------------------------------------------------------------------------------------------ d. outputs
TEXT_OK = re.compile(r"^[^<>\n\r&]*$")


def part_d():
    p = os.path.join(PAGE, "forge.json")
    check("d. forge.json exists", os.path.exists(p))
    if not os.path.exists(p):
        return
    raw = open(p, "rb").read()
    check(f"d. forge.json <= 1 MB ({len(raw):,} bytes)", len(raw) <= 1_000_000)
    d = json.loads(raw)
    need = ("v", "app", "built", "seed", "pop", "gens_n", "knobs", "live", "genomes", "gens", "champion", "verdict", "honesty", "seeds", "proposal")
    check("d. forge.json has every top-level key", all(k in d for k in need), [k for k in need if k not in d])
    check("d. app 'prometheus', v 1, not demo", d.get("app") == "prometheus" and d.get("v") == 1 and d.get("demo") is False)
    check("d. gens_n generations of pop creatures", len(d["gens"]) == d["gens_n"] and all(len(g) == d["pop"] for g in d["gens"]))
    ks = {c["k"] for g in d["gens"] for c in g}
    check("d. every creature's genome is in genomes, on the grid, with h1 / h2 / y numbers and a map point",
          ks <= set(d["genomes"]) and all(G.in_bounds(tuple(v["v"])) and {"h1", "h2", "y", "xy"} <= set(v) for v in d["genomes"].values()))
    ids = {c["id"] for g in d["gens"] for c in g}
    check("d. creature ids unique; parents refer to the generation before",
          len(ids) == sum(len(g) for g in d["gens"]) and all(set(c["p"]) <= {x["id"] for x in d["gens"][i - 1]}
                                                             for i, g in enumerate(d["gens"]) if i for c in g))
    check("d. the champion and its lineage exist; the live genome is in genomes", d["champion"]["id"] in ids
          and set(d["champion"]["line"]) <= ids and d["live"]["k"] in d["genomes"] and d["live"]["k"] == G.key(G.live_genome()))
    check("d. generations listed fittest first", all(all(a["f"] >= b["f"] for a, b in zip(g, g[1:])) for g in d["gens"]))
    j = os.path.join(PAGE, "jarvis.json")
    c = json.load(open(j, encoding="utf-8")) if os.path.exists(j) else {}
    texts = [c.get("name", ""), c.get("status", {}).get("label", "")] + [str(x.get(k, "")) for x in c.get("kpis", []) for k in ("label", "value", "delta")] + c.get("lines", [])
    check("d. jarvis.json: the Jarvis card contract (v 1, name, status, <= 3 kpis / lines, t, theme, <= 8 KB, plain text)",
          c.get("v") == 1 and 0 < len(c.get("name", "")) <= 40 and c.get("status", {}).get("level") in ("ok", "warn", "bad", "off")
          and len(c["status"].get("label", "")) <= 48 and len(c.get("kpis", [])) <= 3 and len(c.get("lines", [])) <= 3
          and all(len(x["label"]) <= 20 and len(str(x["value"])) <= 24 and len(str(x.get("delta", ""))) <= 16 for x in c["kpis"])
          and all(len(x) <= 120 for x in c["lines"]) and isinstance(c.get("t"), int) and re.fullmatch(r"#[0-9a-f]{6}", c.get("theme", ""))
          and os.path.getsize(j) <= 8192 and all(TEXT_OK.match(t) for t in texts), c)
    html = open(os.path.join(PAGE, "index.html"), encoding="utf-8").read()
    check("d. the page's theme-color = jarvis.json theme", f'<meta name="theme-color" content="{c.get("theme")}">' in html)
    r = os.path.join(ROOT, "research", "prometheus", "forge_results.json")
    rr = json.load(open(r, encoding="utf-8")) if os.path.exists(r) else {}
    check("d. research/prometheus/forge_results.json: seeds, hall of fame with H1 / H2 / 2021-25, honesty",
          rr.get("seed_champions") and rr.get("hall_of_fame") and all({"H1", "H2", "2021-25"} <= set(h) for h in rr["hall_of_fame"])
          and "spearman_h1_h2_fit" in rr.get("honesty", {}))
    runs = [os.path.join(ROOT, "research", "runs", f"prometheus_s{s}.json") for s in rr.get("seeds", [])]
    check("d. every seed's champion is stored as a runlib run (research/runs/prometheus_s*.json)", runs and all(os.path.exists(x) for x in runs))
    js = open(os.path.join(PAGE, "forge.js"), encoding="utf-8").read()
    check("d. three.js from ../jarvis/ (no CDN), reduced motion, and the auto LITE steps of the OLYMPUS render core (onQuality) in the page",
          "from '../jarvis/three.module.min.js'" in js and "prefers-reduced-motion" in js and "../olympus/render.js" in js and "onQuality" in js and "http" not in
          js.replace("https://demetrades2000-coder.github.io", ""))


# ------------------------------------------------------------------------------------------------ e. the page in Chromium
class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def _site(with_data=True):
    base = tempfile.mkdtemp(prefix="prometheus_page_")
    os.makedirs(os.path.join(base, "jarvis"))
    for f in ["three.module.min.js", "icon-192.png"] + [os.path.basename(x) for x in glob.glob(os.path.join(ROOT, "tools", "web_public", "jarvis", "*.woff2"))]:
        shutil.copy(os.path.join(ROOT, "tools", "web_public", "jarvis", f), os.path.join(base, "jarvis", f))
    shutil.copytree(PAGE, os.path.join(base, "prometheus"))
    shutil.copytree(os.path.join(ROOT, "tools", "web_public", "olympus"), os.path.join(base, "olympus"))   # the OLYMPUS kit
    if not with_data:
        for f in ("forge.json", "jarvis.json"):
            p = os.path.join(base, "prometheus", f)
            if os.path.exists(p):
                os.remove(p)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=base))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return base, srv, f"http://127.0.0.1:{srv.server_address[1]}/prometheus/"


def part_e():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("e. Playwright is installed", False)
        return
    os.makedirs(SHOTS, exist_ok=True)
    sites = [_site(True), _site(False)]
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            _page_checks(br, sites[0][2], sites[1][2])
            br.close()
    finally:
        for base, srv, _ in sites:
            srv.shutdown()
            shutil.rmtree(base, ignore_errors=True)


def _new(br, url, errs, reduced=False):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=False,
                         reduced_motion="reduce" if reduced else "no-preference")
    ctx.add_init_script("try { localStorage.setItem('jfx', 'low'); } catch (e) {}")   # software GL: LITE keeps frames and screenshots quick
    p = ctx.new_page()
    p.set_default_timeout(150000)                       # software GL on a busy box: a screenshot can wait for a slow frame
    p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
    p.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" else None)
    p.on("requestfailed", lambda r: errs.append("requestfailed: " + r.url))
    p.goto(url)
    p.wait_for_function("window.__forge && window.__forge.ready", timeout=150000)
    p.wait_for_timeout(600)
    return ctx, p


def _orb_free(p):
    """No button / input / card reaches into the bottom-right 80 x 160 px (Jarvis's orb)."""
    return p.evaluate("""() => {
      const W = innerWidth, H = innerHeight, box = {l: W - 80, t: H - 160, r: W, b: H};
      const hit = [...document.querySelectorAll('button, input, a:not(.oly-home), .card:not([hidden])')].filter((e) => {
        const r = e.getBoundingClientRect(); if (!r.width || !r.height || e.closest('[hidden]')) return false;
        return r.right > box.l && r.left < box.r && r.bottom > box.t && r.top < box.b; });
      return hit.map((e) => e.id || e.className || e.tagName); }""")


def _page_checks(br, url, url_nodata):
    errs = []
    ctx, p = _new(br, url + "?autoplay=0", errs)
    check("e. the page loads forge.json (not the demo) at 390 x 844", p.evaluate("window.__forge.demo") is False)
    check("e. no sideways scroll", p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    check("e. the bottom-right 80 x 160 px stays free for Jarvis's orb", not _orb_free(p), _orb_free(p))
    p.screenshot(path=os.path.join(SHOTS, "01_gen1.png"))
    n = p.evaluate("Number(document.getElementById('gen').max) + 1")
    p.evaluate("(v) => { const s = document.getElementById('gen'); s.value = String(v); s.dispatchEvent(new Event('input', {bubbles: true})); }", 5)
    p.wait_for_timeout(300)
    check("e. the generation slider moves the forge (gen 6 of n in the HUD)", p.evaluate("window.__forge.gen") == 5
          and p.inner_text("#s-gen") == f"6/{n}", p.inner_text("#s-gen"))
    hud = p.evaluate("[...document.querySelectorAll('.st b')].map((e) => e.textContent)")
    check("e. the HUD shows best H1 $/mo, its H2 $/mo, p10/f10, trades/week (no blanks)", all(x and x != "—" for x in hud), hud)
    ch = p.evaluate("window.__forge.champion")
    p.evaluate("(v) => { const s = document.getElementById('gen'); s.value = String(v); s.dispatchEvent(new Event('input', {bubbles: true})); }", n - 1)
    p.wait_for_timeout(500)
    p.screenshot(path=os.path.join(SHOTS, "02_last_gen.png"))
    ids = p.evaluate("window.__forge.ids()")
    target = ch if ch in ids else ids[0]
    pt = p.evaluate("(id) => window.__forge.screenOf(id)", target)
    p.mouse.click(pt["x"], pt["y"])
    p.wait_for_timeout(300)
    opened = p.is_visible("#card")
    title = p.inner_text("#card-h") if opened else ""
    picked = re.search(r"#(\d+)", title)
    check("e. a tap on a flame opens its creature card", opened and "Creature #" in title, title)
    body = p.inner_text("#card-b") if opened else ""
    check("e. the card shows its H1 / H2 / 2021-25 numbers and the knob diff vs live",
          all(s in body for s in ("2026 H1", "2026 H2", "2021-25", "$ / month", "Knob", "Live", "This", "Last entry (ET)")), body[:300])
    if picked:
        pc = p.evaluate("(id) => window.__forge.screenOf(id)", int(picked.group(1)))
        check("e. the card belongs to the flame under the tap (within 40 px)", abs(pc["x"] - pt["x"]) <= 40 and abs(pc["y"] - pt["y"]) <= 40)
    check("e. the card stays clear of the orb corner", not _orb_free(p), _orb_free(p))
    check("g. the card answers 'Would this change live?' with the reasons and H1 / H2 pass marks",
          "Would this change live?" in body and "H1" in body and "Only the owner changes live" in body, body[:200])
    p.screenshot(path=os.path.join(SHOTS, "03_creature_card.png"))
    p.click("#cardX")
    lp = p.evaluate("window.__forge.screenOf('live')")
    p.mouse.click(lp["x"], lp["y"])
    p.wait_for_timeout(300)
    check("e. the live reference flame opens the LIVE LIT card", p.is_visible("#card") and "LIVE LIT" in p.inner_text("#card-h").upper(),
          p.inner_text("#card-h") if p.is_visible("#card") else "")
    p.click("#truthBtn")
    p.wait_for_timeout(300)
    tb = p.inner_text("#truth-b") if p.is_visible("#truth") else ""
    check("e. the Verdict panel: champion vs live, every seed, the H1->H2 rank correlation", p.is_visible("#truth")
          and "Seed" in tb and "Rank correlation" in tb and "bootstrap" in tb, tb[:200])
    p.screenshot(path=os.path.join(SHOTS, "04_verdict.png"))
    p.click("#truthX")
    p.click("#play")
    try:
        p.wait_for_function("window.__forge.gen >= 1", timeout=90000)     # software GL on a busy box: a step needs a few slow frames
    except Exception:
        pass
    g_after = p.evaluate("window.__forge.gen")
    check("e. Play runs the time-lapse (generations advance)", g_after >= 1, g_after)
    p.screenshot(path=os.path.join(SHOTS, "05_timelapse.png"))
    _upgrade_checks(p)
    fps, lite = p.evaluate("window.__forge.fps"), p.evaluate("window.__forge.lite")
    print(f"     (headless software GL: {fps} fps, LITE {lite})", flush=True)
    ctx.close()
    check("e. no page errors, console errors or failed requests (forge.json)", not errs, errs[:5])

    errs2 = []
    ctx, p = _new(br, url_nodata + "?autoplay=0", errs2)
    check("e. no forge.json: the demo fixture loads, marked DEMO DATA", p.evaluate("window.__forge.demo") is True and p.is_visible("#demo"))
    p.screenshot(path=os.path.join(SHOTS, "06_demo.png"))
    ctx.close()
    bad = [e for e in errs2 if "forge.json" not in e and "jarvis.json" not in e and "404" not in e]
    check("e. the demo runs without page errors (only the missing forge.json 404)", not bad, bad[:5])

    errs4 = []
    ctx, p = _new(br, url + "?lite=1&autoplay=0", errs4)
    check("e. ?lite=1 forces LITE (the auto LITE switch: under ~45 fps, then 1x pixels under ~30 fps)", p.evaluate("window.__forge.lite") is True
          and not errs4, errs4[:3])
    ctx.close()

    errs3 = []
    ctx, p = _new(br, url, errs3, reduced=True)
    p.wait_for_timeout(2500)
    check("e. reduced motion: no autoplay, the forge stays still", p.evaluate("window.__forge.gen") == 0)
    p.evaluate("(v) => { const s = document.getElementById('gen'); s.value = String(v); s.dispatchEvent(new Event('input', {bubbles: true})); }", 3)
    check("e. reduced motion: the slider still steps generations", p.evaluate("window.__forge.gen") == 3)
    p.screenshot(path=os.path.join(SHOTS, "07_reduced_motion.png"))
    ctx.close()
    check("e. reduced motion: no errors", not errs3, errs3[:5])


THEME_STUB = """(() => { const scene = %s;
  window.OLYMPUS = { app: 'x', fx: () => 'high', chosen: () => true, lite: () => false, reduced: () => false, dpr: () => 1, setFx() {}, onFx() {},
    mode() {}, hidden: () => document.hidden, track: (r) => r, stats: () => ({}), ready() {}, fail() {}, state: () => 'ready',
    theme: () => ({ bg: '#000814', accent: '#4da3ff', mix: 0.5, harmony: 0.3, glass: 'rgba(0, 0, 0, .7)', line: 'rgba(1, 1, 1, .1)', text: '#ffffff', dim: '#cccccc' }),
    onTheme(cb) { window.__onTheme = cb; } };
  if (scene) window.OLYMPUS.themeScene = (o) => { window.__themeScene = o; return () => {}; }; })()"""


def _filter_checks(p, d):
    """g. the half-year pass / fail filter + the 'would this change live?' verdict (2026-11-03 upgrade)."""
    live = d["genomes"][d["live"]["k"]]

    def passes(g, half):
        a, b = g[half], live[half]
        return a["pm"] > b["pm"] and (a["p10"] - a["f10"]) >= (b["p10"] - b["f10"]) - 0.05 and a["tpw"] >= 2
    gl = p.evaluate("window.__forge.gen")
    ids = p.evaluate("window.__forge.ids()")
    by_id = {c["id"]: c for gen in d["gens"] for c in gen}
    want = {f: [i for i in ids if cond(d["genomes"][by_id[i]["k"]])] for f, cond in (
        ("h1", lambda g: passes(g, "h1")), ("h2", lambda g: passes(g, "h2")), ("both", lambda g: passes(g, "h1") and passes(g, "h2")),
        ("fail2", lambda g: not passes(g, "h2")))}
    p.evaluate("window.__forge.setFilter('h2')")
    p.wait_for_timeout(200)
    got = [i for i in ids if p.evaluate("(i) => window.__forge.flameVis(i)", i) == 1]
    check(f"g. filter 'Pass H2' keeps exactly the creatures that pass H2 lit ({len(want['h2'])} of {len(ids)} in generation {gl + 1})", sorted(got) == sorted(want["h2"]), (got, want["h2"]))
    p.evaluate("window.__forge.setFilter('fail2')")
    got = [i for i in ids if p.evaluate("(i) => window.__forge.flameVis(i)", i) == 1]
    check("g. filter 'H2 fail' lights the complement", sorted(got) == sorted(want["fail2"]), (got, want["fail2"]))
    txt = p.inner_text("#chipn")
    check("g. the filter line says how many match", f"{len(want['fail2'])} of {len(ids)}" in txt, txt)
    p.evaluate("window.__forge.setFilter('all')")
    check("g. 'All' lights every creature again", all(p.evaluate("(i) => window.__forge.flameVis(i)", i) == 1 for i in ids))
    check("g. the chips stay clear of the orb corner", not _orb_free(p), _orb_free(p))
    w = p.evaluate("(id) => { window.__forge.openCard(id); return document.getElementById('chg').className + '|' + document.getElementById('chg').innerText; }", d["champion"]["id"])
    real = bool(d["verdict"]["real_margin"])
    check("g. the champion's verdict follows forge.json (no real H2 margin -> 'NO, LIVE STAYS')",
          ("chg-box no" in w and "LIVE STAYS" in w.upper()) == (not real), w[:160])
    p.click("#cardX")


def _upgrade_checks(p):
    d = json.load(open(os.path.join(PAGE, "forge.json"), encoding="utf-8"))
    live = d["genomes"][d["live"]["k"]]
    p.click("#play")                                     # pause the time-lapse
    p.wait_for_timeout(200)
    calls = p.evaluate("window.__forge.calls")
    check(f"f. every flame in one draw call: {calls} draw calls a frame incl. the render core's bloom + finish (was 84; <= 60)", 0 < calls <= 60, calls)
    tiers = {}
    for lv in ("high", "low"):
        p.evaluate("(l) => window.__forge.setQuality(l)", lv)
        p.wait_for_timeout(700)
        tiers[lv] = p.evaluate("window.__forge.passes")
    check(f"g. the arena runs on the OLYMPUS render core: high = scene + bloom + finish, low = scene + finish ({tiers})",
          tiers == {"high": ["scene", "bloom", "finish"], "low": ["scene", "finish"]}, tiers)
    bt, bs = p.inner_text("#bn-t"), p.inner_text("#bn-s")
    want = "LIVE LIT STILL BEST" if not d["proposal"] else "A CANDIDATE TO REVIEW"
    check("f. the verdict banner: the honest title with the H1 -> H2 numbers and live's H2 $/mo",
          bt == want and f"${live['h2']['pm']:,}" in bs and "H1" in bs and "H2" in bs and p.is_visible("#banner"), (bt, bs))
    p.click("#linBtn")
    p.wait_for_timeout(300)
    n = sum(len(g) for g in d["gens"])
    got = p.evaluate("""() => ({ dots: document.querySelectorAll('#lin-b circle').length, champ: document.querySelectorAll('#lin-b circle.champ').length,
        anc: document.querySelectorAll('#lin-b circle.anc, #lin-b circle.main').length, panel: window.__forge.panel })""")
    check("f. Lineage: every creature a dot, the champion and its ancestry marked", p.is_visible("#truth") and got["panel"] == "lineage"
          and got["dots"] == n and got["champ"] == 1 and got["anc"] >= len(d["champion"]["line"]) - 1, got)
    p.screenshot(path=os.path.join(SHOTS, "08_lineage.png"))
    dot = p.evaluate("(id) => window.__forge.lineageDot(id)", d["champion"]["id"])
    p.mouse.click(dot["x"], dot["y"])
    p.wait_for_timeout(300)
    check("f. Lineage: a tap on the champion's dot opens its card (one sheet: the panel closes)", p.is_visible("#card")
          and "Champion" in p.inner_text("#card-h") and not p.is_visible("#truth"), p.inner_text("#card-h") if p.is_visible("#card") else "")
    _filter_checks(p, d)
    p.click("#hallBtn")
    p.wait_for_timeout(300)
    rows = p.evaluate("[...document.querySelectorAll('#hall-b tbody tr')].map((r) => r.dataset.id)")
    best = max(c["f"] for g in d["gens"] for c in g)
    check("f. Hall of Champions: live first, then the fittest distinct genomes (the run's best fitness on top)", p.is_visible("#truth")
          and rows[:1] == ["live"] and len(rows) >= 2 and abs(next(c["f"] for g in d["gens"] for c in g if str(c["id"]) == rows[1]) - best) < 1e-9, rows)
    check("f. the bottom sheet stays clear of the orb corner", not _orb_free(p), _orb_free(p))
    p.screenshot(path=os.path.join(SHOTS, "09_hall.png"))
    p.click(f"#hall-b tbody tr[data-id='{rows[1]}']")
    p.wait_for_timeout(300)
    check("f. Hall: a tap on a row opens that creature's card", p.is_visible("#card") and f"#{rows[1]}" in p.inner_text("#card-h"))
    p.click("#cardX")
    got = p.evaluate("""() => { applyTheme({ accent: '#33ccff', '--gold': '#ffee00' }); const cs = getComputedStyle(document.documentElement);
        return [cs.getPropertyValue('--fire').trim(), cs.getPropertyValue('--gold').trim()]; }""")
    check("f. applyTheme(tokens): the page's colours follow the theme", got == ["#33ccff", "#ffee00"], got)
    p.evaluate("applyTheme({ accent: '#ff7a1a', '--gold': '#ffc24a' })")
    ctx = p.context.browser.new_context(viewport={"width": 390, "height": 844})
    ctx.add_init_script(THEME_STUB % "true")
    q = ctx.new_page()
    q.set_default_timeout(150000)
    q.goto(p.url)
    q.wait_for_function("window.__forge && window.__forge.ready", timeout=150000)
    got = q.evaluate("() => ({ scene: !!(window.__themeScene && window.__themeScene.scene && window.__themeScene.scene.fog), "
                     "renderer: !!(window.__themeScene && window.__themeScene.renderer) })")
    check("f. OLYMPUS themes: with the kit's themeScene the arena (its fog) is handed to the kit", got == {"scene": True, "renderer": True}, got)
    ctx.close()


# ------------------------------------------------------------------------------------------------------------ h (2026-11-04: forgeplus.js)
PLUS_JS = r"""
import fs from 'node:fs';
const D = '__PAGE__/';
const Core = await import(D + 'forgecore.js'), P = await import(D + 'forgeplus.js');
const real = JSON.parse(fs.readFileSync(D + 'forge.json', 'utf8')), out = {};
const F = new Core.Forge(real), L = F.live, champ = real.champion;
const o = P.overfit(F, champ.k); out.over = { lost: o.lost, meter: o.meter, label: o.label, g1: o.gainH1, g2: o.gainH2, h1: o.h1, h2: o.h2, live: o.isLive };
out.liveOver = P.overfit(F, real.live.k).label;
const pop = P.populationOverfit(F); out.pop = pop;
const br = P.breeding(F); out.breed = { n: br.length, sizes: br.map((r) => r.size), up: br.every((r, i) => !i || r.best >= br[i - 1].best - 1e-9 || true), newBest: br.filter((r) => r.newBest).length,
  mut: br.reduce((a, r) => a + r.mutations, 0), line: br.reduce((a, r) => a + r.line, 0), champLine: real.champion.line.length, elites: br[1].elites, kinds: br[1].elites + br[1].children + br[1].random + br[1].sparks + br[1].live };
const vh = P.verdictHistory(F); out.vh = { n: vh.rows.length, same: vh.rows.every((r) => F.wouldChange(r.id).level === r.level), sum: vh.yes + vh.maybe + vh.no };
const sv = P.survivors(F, 50); out.surv = { n: sv.length, both: sv.every((r) => F.halfPass(r.k).h1 && F.halfPass(r.k).h2), sorted: sv.every((r, i) => !i || sv[i - 1].worst >= r.worst), ranks: sv.map((r) => r.rank).join(',') === sv.map((_, i) => i + 1).join(',') };
let want = 0; const seen = new Set(); for (const G of real.gens) for (const c of G) { if (seen.has(c.k) || c.k === real.live.k) continue; seen.add(c.k); const p = F.halfPass(c.k); if (p.h1 && p.h2) want++; } out.survWant = want;
out.search = { id: P.search(F, '#' + champ.id)[0].id, champ: P.search(F, 'champion')[0].id, live: P.search(F, 'live')[0].id, gen: P.search(F, 'gen 3').every((h) => h.gen === 2) && P.search(F, 'gen 3').length > 0,
  knob: P.search(F, 'be_r').length > 0, h2: P.search(F, 'pass h2').every((h) => F.halfPass(h.k).h2), nothing: P.search(F, 'zzqxv').length, blank: P.search(F, '  ').length, cap: P.search(F, 'child').length <= 25 };
const c = P.compare(F, champ.id, 'live'); out.cmp = { rows: c.rows.length, text: c.text.length > 10, same: P.compare(F, 'live', 'live').aWins, bad: P.compare(F, 99999, 'live'), h2: c.h2Winner };
const sl = P.shareLines(F, champ.id); out.share = { title: sl.title, level: sl.level, bars: sl.bars.length, foot: sl.foot, demo: sl.demo };
const demo = new Core.Forge(Core.demoData(7)); const dd = P.overfit(demo, demo.d.champion.k); out.demo = [dd.meter >= 0, P.breeding(demo).length, P.verdictHistory(demo).rows.length, P.survivors(demo, 5).length >= 0, P.shareLines(demo, demo.d.champion.id).demo, P.shareLines(demo, demo.d.champion.id).foot.toUpperCase().includes('DEMO')];
console.log(JSON.stringify(out));
"""


def part_h():
    """The 2026-11-04 tools: the overfitting meter, the breeding table, the verdict history, the survivors, search, compare and the share card lines.
    All pure functions over forge.json (node), checked against the numbers in the file."""
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        check("h. node is available for forgeplus.js", False)
        return
    f = os.path.join(tempfile.mkdtemp(prefix="forge_plus_"), "p.mjs")
    open(f, "w", encoding="utf-8").write(PLUS_JS.replace("__PAGE__", PAGE.replace(os.sep, "/")))
    r = subprocess.run([node, f], capture_output=True, text=True, timeout=120)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("h. forgeplus.js runs in node", False, (r.stdout + r.stderr)[-500:])
        return
    d = json.load(open(os.path.join(PAGE, "forge.json"), encoding="utf-8"))
    G, L = d["genomes"][d["champion"]["k"]], d["genomes"][d["live"]["k"]]
    g1, g2 = G["h1"]["pm"] - L["h1"]["pm"], G["h2"]["pm"] - L["h2"]["pm"]
    lost = max(0, min(150, round(100 * (g1 - g2) / g1))) if g1 > 0 else (0 if g2 >= 0 else 100)
    ov = o["over"]
    check(f"h. the overfitting meter is the champion's own numbers: H1 gain {g1:+.0f} $/mo over live, H2 gain {g2:+.0f}, {lost}% of the H1 gain lost -> {ov['label']}",
          ov["g1"] == g1 and ov["g2"] == g2 and ov["lost"] == lost and ov["meter"] == min(100, lost) and ov["h1"] == G["h1"]["pm"] and ov["h2"] == G["h2"]["pm"] and ov["label"].upper() in ("HEALTHY", "WARM", "OVERFIT", "BURNT", "NO GAIN")
          and (ov["label"].upper() != "HEALTHY" if lost >= 20 else True) and o["liveOver"].upper() == "NO GAIN", ov)
    P = o["pop"]
    live_k = d["live"]["k"]
    keys = [k for k in d["genomes"] if k != live_k]
    b1 = [k for k in keys if d["genomes"][k]["h1"]["pm"] > L["h1"]["pm"]]
    bb = [k for k in b1 if d["genomes"][k]["h2"]["pm"] > L["h2"]["pm"]]
    check(f"h. the whole-run overfitting: {len(b1)} variants beat live on H1 and {len(bb)} of them on H2 (counted again from forge.json), the Spearman rank number is the file's",
          P["variants"] == len(keys) and P["beatH1"] == len(b1) and P["beatBoth"] == len(bb) and P["spearman"] == d["honesty"]["spearman_h1_h2_pm"], P)
    b = o["breed"]
    check("h. breeding: one row per generation of 24, elites are copied, the champion's line is counted, new-best generations marked",
          b["n"] == d["gens_n"] and set(b["sizes"]) == {d["pop"]} and b["line"] == b["champLine"] and b["kinds"] == d["pop"] and b["elites"] == 2 and b["newBest"] >= 1, b)
    check("h. the verdict history: one verdict per generation's best, each exactly what the card's 'would this change live?' says, and the counts add up",
          o["vh"]["n"] == d["gens_n"] and o["vh"]["same"] and o["vh"]["sum"] == d["gens_n"], o["vh"])
    sv = o["surv"]
    check(f"h. survivors: only creatures that beat live on BOTH halves ({sv['n']}, the same count as an independent pass), best worst-half first, ranked 1..n", sv["both"] and sv["sorted"] and sv["ranks"] and sv["n"] == min(50, o["survWant"]), (sv, o["survWant"]))
    se = o["search"]
    check("h. search: '#id', 'champion', 'live', 'gen 3', a knob name, 'pass h2' all find the right creatures; nonsense and blanks find nothing; at most 25 hits",
          se["id"] == d["champion"]["id"] and se["champ"] == d["champion"]["id"] and se["live"] == "live" and se["gen"] and se["knob"] and se["h2"] and se["nothing"] == 0 and se["blank"] == 0 and se["cap"], se)
    c = o["cmp"]
    check("h. compare: nine rows with a winner each, a plain verdict, a creature against itself is a tie, an unknown id is null", c["rows"] == 9 and c["text"] and c["same"] == 0 and c["bad"] is None, c)
    sh = o["share"]
    check("h. the share card says what it is: the title, the verdict, three bars (creature against live) and the 'not advice' footer", sh["title"].upper().startswith("CHAMPION #") and sh["level"] in ("yes", "maybe", "no") and sh["bars"] == 3 and "not advice" in sh["foot"] and sh["demo"] is False, sh)
    check("h. the demo fixture works everywhere (never blank) and the share card says DEMO", all(x for x in o["demo"][:1]) and o["demo"][1] == 20 and o["demo"][2] == 20 and o["demo"][4] is True and o["demo"][5] is True, o["demo"])


def _plus_checks(br, url):
    """The Tools panel and the smithy in the browser (390 x 844)."""
    d = json.load(open(os.path.join(PAGE, "forge.json"), encoding="utf-8"))
    errs = []
    ctx, p = _new(br, url + "?autoplay=0", errs)
    tabs = p.evaluate("[...document.querySelectorAll('.tabs button')].map(b => [b.id, Math.round(b.getBoundingClientRect().height)])")
    check("i. the dock has four buttons: Verdict, Lineage, Hall, Tools (each 44 px tall or more), the orb corner free", [t[0] for t in tabs] == ["truthBtn", "linBtn", "hallBtn", "plusBtn"] and all(t[1] >= 44 for t in tabs) and not _orb_free(p), (tabs, _orb_free(p)))
    p.click("#plusBtn")
    p.wait_for_function("!document.getElementById('plus').hidden && document.getElementById('plus-b').innerText.length > 100")
    t = p.inner_text("#plus-b")
    check("i. Tools opens on the overfitting METER: the champion, a dial, the in-sample / new-data numbers, the whole run, a share button", "Champion #" in t and "H1: the data the forge trained on" in t and "THE WHOLE RUN" in t.upper() and p.query_selector("#plus-b .dial") is not None and p.query_selector("[data-share]") is not None, t[:120])
    check("i. the Tools panel keeps the orb corner free and does not scroll the page sideways", not _orb_free(p) and p.evaluate("document.documentElement.scrollWidth <= innerWidth"), _orb_free(p))
    p.click('[data-ptab="breed"]')
    rows = p.evaluate("document.querySelectorAll('#plus-b .gens li').length")
    p.click("#plus-b .gens li:nth-child(7) button")
    p.wait_for_timeout(200)
    check("i. BREEDING: a row per generation (20); tapping one puts the arena on that generation", rows == d["gens_n"] and p.evaluate("window.__forge.gen") == 6, (rows, p.evaluate("window.__forge.gen")))
    p.click('[data-ptab="verdicts"]')
    cells = p.evaluate("document.querySelectorAll('#plus-b .vgrid button').length")
    check("i. VERDICTS: one dot per generation and a list, 'No, live stays' for this run", cells == d["gens_n"] and "NO, LIVE STAYS" in p.inner_text("#plus-b").upper(), cells)
    p.click("#plus-b .vlist li:first-child button")
    p.wait_for_selector("#card:not([hidden])")
    check("i. a verdict row opens that creature's card: with the overfitting strip (a meter, its word, SHARE, COMPARE)", p.query_selector("#ofit .om") is not None and p.inner_text("#ofit b").upper() in ("HEALTHY", "WARM", "OVERFIT", "BURNT", "NO GAIN") and p.query_selector("#cardShare") is not None and p.is_hidden("#plus"))
    p.click("#cardX")
    p.click("#plusBtn")
    p.click('[data-ptab="search"]')
    p.fill("#fq", "champion")
    p.wait_for_timeout(150)
    hit = p.evaluate("[...document.querySelectorAll('#fqr [data-open]')].map(b => b.dataset.open)")
    check("i. SEARCH: 'champion' finds the champion; the chips fill the box; no match says so in the count", str(d["champion"]["id"]) in hit and p.evaluate("document.activeElement.id") == "fq", hit[:4])
    p.fill("#fq", "zzqxv")
    check("i. ... nothing found: '0 found'", "0 found" in p.inner_text("#fqn"))
    p.fill("#fq", "#" + str(d["champion"]["id"]))
    p.click('#fqr [data-cmp="a"]')
    p.click('[data-ptab="search"]') if p.evaluate("__forge.plus.state.tab") != "compare" else None
    p.fill("#fq", "live") if p.evaluate("__forge.plus.state.tab") == "search" else None
    p.click('#fqr [data-cmp="b"]') if p.evaluate("__forge.plus.state.tab") == "search" else p.click('[data-id="live"]')
    p.wait_for_selector("#plus-b table.cmp")
    st = p.evaluate("[__forge.plus.state, JSON.parse(localStorage.getItem('forge.compare'))]")
    check("i. COMPARE: A = the champion, B = live: nine rows, winners marked, the overfitting row, a verdict sentence; kept under 'forge.compare'",
          p.evaluate("document.querySelectorAll('#plus-b table.cmp')[0].querySelectorAll('tbody tr').length") >= 10 and p.evaluate("document.querySelectorAll('#plus-b td.w').length") >= 1 and len(p.inner_text("#cmpv")) > 10 and st[0]["a"] == d["champion"]["id"] and st[0]["b"] == "live" and st[1]["a"] == d["champion"]["id"], st)
    p.click('[data-ptab="meter"]')
    p.click("[data-share]")
    p.wait_for_selector("#fshare:not([hidden])")
    p.wait_for_function("() => { const i = document.querySelector('#fshare img'); return i && i.complete && i.naturalWidth > 0; }")
    size = p.evaluate("(() => { const i = document.querySelector('#fshare img'); return [i.naturalWidth, i.naturalHeight, i.src.slice(0, 5)]; })()")
    check("i. the share card is a 1080 x 1350 picture drawn on the phone (a blob, nothing uploaded)", size == [1080, 1350, "blob:"], size)
    p.click("#fshareX")
    keys = sorted(p.evaluate("Object.keys(localStorage)"))
    check("i. this phone keeps only its quality choice and 'forge.compare'", set(keys) <= {"forge.compare", "jfx"}, keys)
    w = p.evaluate("window.__forge.works")
    check("i. the smithy is in the scene (anvil, hammer, hearth) and the hammer is working", w is not None and len(w["pos"]) == 2, w)
    check("i. no console errors in the Tools", not errs, errs[:3])
    ctx.close()
    errs2 = []
    ctx, p = _new(br, url + "?autoplay=0&q=high", errs2)
    p.wait_for_function("window.__forge.works && window.__forge.works.fx.length >= 3", timeout=240000)
    w = p.evaluate("window.__forge.works")
    check(f"i. on HD the smithy has the OLYMPUS effects (embers, heat haze, smoke, light shafts): {w['fx']}", {"embers", "heatShimmer", "volumetricFog", "godRays"} <= set(w["fx"]), w)
    p.wait_for_function("window.__forge.works.strikes >= 1", timeout=420000)     # the beat runs on the frame clock (capped per frame): a 1 fps software GL needs minutes
    check("i. the hammer strikes (the ingot flares, sparks fly)", p.evaluate("window.__forge.works.strikes") >= 1)
    calls = p.evaluate("window.__forge.calls")
    check(f"i. the forge scene stays inside its draw-call budget on HD ({calls} <= 90)", 0 < calls <= 90, calls)
    check("i. no console errors on HD", not errs2, errs2[:3])
    ctx.close()


def part_i():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("i. Playwright is installed", False)
        return
    base, srv, url = _site(True)
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            _plus_checks(br, url)
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(base, ignore_errors=True)


def main(argv):
    fast, page = "fast" in argv, "page" in argv           # page: d + e only (the page, ~1 min)
    if "plus" in argv:                                    # plus: the 2026-11-04 tools (node) and their page checks
        part_h()
        part_i()
        print(f"\n{sum(RES)}/{len(RES)} passed", flush=True)
        return 0 if all(RES) else 1
    h0 = model_hashes()
    if not page:
        part_a(real=not fast)
        part_b()
    if not fast and not page:
        part_c()
    part_d()
    if not page:
        part_h()
    if not fast:
        part_e()
        part_i()
    check("live_model*.json unchanged by the whole test", model_hashes() == h0)
    print(f"\n{sum(RES)}/{len(RES)} passed", flush=True)
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
