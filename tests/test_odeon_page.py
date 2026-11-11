"""ODEON (tools/web_public/odeon/, owner 2026-11-03): the 3D replay theater of the bots' trades, and its exporter
tools/odeon_export.py (trades.json). Read-only: nothing here touches trading logic.

  a. exporter: deterministic (same inputs -> same bytes, the committed trades.json is current), <= 1.5 MB, <= 60 trades,
     futures bars only (1m / 5m), the paper / real path from a data.json (twins attached)
  b. no look-ahead in the narration: every caption row comes after every time it depends on (refs), rows in time order,
     the outcome ($, R, "target hit" ...) only in the exit row (the last one), each sweep caption only after the bars traded
     through its level, the sweep extreme only once it is known, the entry row at the fill
  c. the page's files: three.js from ../jarvis/, no outside address, safe areas, theme-color, reduced motion, the fixture
     (fixture.js) = one exported trade, jarvis.json in the Jarvis contract (docs/JARVIS_APPS.md) with its theme
  d. Playwright chromium at 390 x 844 and 844 x 390: no console errors; the demo fixture (trades.json missing) plays to the
     end and the stats card shows its $ and R; the captions appear in the fixture's order (all of them in the script); the
     scrubber and the event ticks jump to a time (clock, caption, state); no sideways scroll; Jarvis's orb corner (bottom
     right 80 x 160 px) free; the reels list (filters, pick a reel), the real trades file, an ATLAS reel to its stats card;
     speech only after the Narrate tap; reduced motion; LITE; the 2D fallback without WebGL
  e. the 2026-11-03 day pass: typewriter captions (the whole line in the DOM at once), the lens flare and the slow-motion
     time ramp (letterbox) on the entry, the reels gallery of 3D posters sorted by $ (and by date), Highlights (the five best
     trades back to back, auto-advancing), Oracle's #trade=<day>_<HHMM>_<side> link, applyTheme() and the OLYMPUS theme hook,
     one top bar + one bottom dock
Screenshots go to research/handoff/2026-11-03-day/oracle_odeon/odeon/ (ODEON_SHOTS=<dir> to change).

    python -X utf8 -m tests.test_odeon_page            (~3 min; --no-browser: a, b and c only, ~10 s)
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
from tools import odeon_export as OX  # noqa: E402

WEB = os.path.join(ROOT, "tools", "web_public")
OD = os.path.join(WEB, "odeon")
SHOTS = os.environ.get("ODEON_SHOTS") or os.path.join(ROOT, "research", "handoff", "2026-11-03-day", "oracle_odeon", "odeon")
RES = []
MINUS = "−"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def usd(x):
    v = round(abs(x) * 100) / 100
    return ("" if v == 0 else MINUS if x < 0 else "+") + "$" + f"{v:,.2f}"


def rr(r):
    return ("+" if r > 0 else MINUS if r < 0 else "") + f"{abs(r):.2f}R"


def hhmm(t, off):
    return time.strftime("%H:%M", time.gmtime(t + off))


def bars_of(tr):
    b = tr["bars"]
    return [(b["t0"] + d * b["s"], (b["p0"] + o) / 4, (b["p0"] + h) / 4, (b["p0"] + l) / 4, (b["p0"] + c) / 4)
            for d, o, h, l, c in zip(b["dt"], b["o"], b["h"], b["l"], b["c"])]


def fixture():
    src = open(os.path.join(OD, "fixture.js"), encoding="utf-8").read()
    return json.loads(src.split("export const DEMO = ", 1)[1].rstrip().rstrip(";"))


# ------------------------------------------------------------------ a. the exporter
def part_a():
    tmp = tempfile.mkdtemp(prefix="odeon_")
    try:
        p1, p2 = os.path.join(tmp, "a.json"), os.path.join(tmp, "b.json")
        OX.write(OX.build(), p1)
        OX.write(OX.build(), p2)
        b1, b2 = open(p1, "rb").read(), open(p2, "rb").read()
        check("a. the exporter is deterministic (two runs, same bytes)", b1 == b2, (len(b1), len(b2)))
        committed = open(os.path.join(OD, "trades.json"), "rb").read()
        check("a. the committed odeon/trades.json is current (python tools/odeon_export.py)", committed == b1)
        bundle = json.loads(b1)
        T = bundle["trades"]
        check("a. <= 1.5 MB and <= 60 trades, newest first, both bots", len(b1) <= 1_500_000 and 0 < len(T) <= 60
              and [t["entry"]["t"] for t in T] == sorted((t["entry"]["t"] for t in T), reverse=True)
              and {t["bot"] for t in T} == {"LIT", "ATLAS"}, (len(b1), len(T)))
        check("a. bars are futures 1m (5m fallback) from before the setup to the exit",
              all(t["bars"]["s"] in (60, 300) and bars_of(t)[0][0] <= min(e["t"] for e in t["events"]) and bars_of(t)[0][0] <= t["entry"]["t"] - 3600
                  and bars_of(t)[-1][0] >= t["exit"]["t"] for t in T) and "NQ1!" in bundle["source"] and "yahoo" not in json.dumps(bundle).lower())
        check("a. every reel has $, R, MFE / MAE, time in trade and a stop beyond the entry",
              all(isinstance(t["usd"], (int, float)) and isinstance(t["r"], (int, float)) and t["mfe_r"] is not None and t["mae_r"] is not None
                  and t["held_min"] >= 0 and (t["stop"] - t["entry"]["px"]) * t["d"] < 0 for t in T))
        # the paper / real path: a published data.json with a ledger row and an eval trade on bars the tape has
        lit = next(t for t in T if t["bot"] == "LIT" and t["src"] == "backtest")   # a replay: its bars are in the TradingView files
        e_t = lit["entry"]["t"]
        fake = {"live": {"ledger": [{"day": lit["day"], "side": lit["side"], "entry_t": e_t, "exit_ts": lit["exit"]["t_end"], "entry_px": lit["entry"]["px"],
                                     "stop_px": lit["stop"], "target_px": lit["target"], "exit_px": lit["exit"]["px"], "exit": lit["exit"]["kind"],
                                     "R": lit["r"], "usd": lit["usd"] * 3, "qty": 3, "risk_pts": lit["risk_pts"]}]},
                "accounts": [{"name": "MFFU 50K Eval", "kind": "eval", "trades": [{"day": lit["day"], "entry_t": e_t, "exit_t": lit["exit"]["t_end"],
                                                                                    "side": lit["side"], "qty": 2, "entry": lit["entry"]["px"], "stop": lit["stop"],
                                                                                    "target": lit["target"], "exit_px": lit["exit"]["px"], "exit": lit["exit"]["kind"],
                                                                                    "r": lit["r"], "pnl": lit["usd"] * 2, "risk_pts": lit["risk_pts"],
                                                                                    "swept": ["Frankfurt high"]}]},
                         {"name": "Paper (cloud)", "kind": "paper", "trades": []}]}
        dp = os.path.join(tmp, "data.json")
        json.dump(fake, open(dp, "w"))
        live = OX.build(0, 0, dp)["trades"]
        real = [t for t in live if t["src"] == "real"]
        paper = [t for t in live if t["src"] == "paper"]
        check("a. data.json: the eval's real trade and the paper row become reels with their twins",
              len(real) == 1 and len(paper) == 1 and real[0]["twin"]["src"] == "paper" and real[0]["twin"]["qty"] == 3
              and paper[0]["twin"]["src"] == "backtest" and real[0]["qty"] == 2 and real[0]["events"][-1]["k"] == "exit", [t["id"] for t in live])
        return bundle, live
    finally:
        for f in glob.glob(os.path.join(tmp, "*")):
            os.remove(f)
        os.rmdir(tmp)


# ------------------------------------------------------------------ b. no look-ahead in the narration
def part_b(bundle, extra):
    T = bundle["trades"] + extra
    bad = []
    for t in T:
        E = t["events"]
        ts = [e["t"] for e in E]
        if ts != sorted(ts):
            bad.append((t["id"], "order"))
        for e in E:
            if any(r > e["t"] for r in e["refs"]):
                bad.append((t["id"], e["k"], "ref after caption"))
        if not E or E[-1]["k"] != "exit" or sum(e["k"] == "exit" for e in E) != 1 or E[-1]["t"] != t["exit"]["t_end"]:
            bad.append((t["id"], "exit row"))
        out = [usd(t["usd"]), rr(t["r"]), f"{OX.money(t['usd'])}", "Target hit", "Stopped out", "Breakeven stop", "Flat at the close", "not moving, cut"]
        for e in E[:-1]:
            if any(o in e["text"] for o in out) or OX.OUTCOME.search(e["text"]):
                bad.append((t["id"], e["k"], "outcome before the exit: " + e["text"]))
            if e["t"] > t["exit"]["t_end"]:
                bad.append((t["id"], e["k"], "after the exit"))
        ent = [e for e in E if e["k"] == "entry"]
        if len(ent) != 1 or ent[0]["t"] != t["entry"]["t"]:
            bad.append((t["id"], "entry row"))
        bars = bars_of(t)
        s = t["bars"]["s"]
        for e in E:
            if e["k"] == "sweep":
                seen = [b for b in bars if b[0] + s <= e["t"]]
                for k in e.get("levels") or []:
                    px = next(lv["px"] for lv in t["levels"] if lv["k"] == k)
                    if not any((b[2] > px if t["d"] < 0 else b[3] < px) for b in seen):
                        bad.append((t["id"], "sweep caption before the bars took " + k))
        sw = t.get("sweep")
        if sw:
            ext = OX.px(sw["ext_px"])
            for e in E:
                if ext in e["text"] and e["t"] < sw["ext_t"] + 300:
                    bad.append((t["id"], e["k"], "sweep extreme before it was known"))
    check(f"b. no look-ahead in {len(T)} caption tracks (refs, order, outcome only at the exit, sweeps after the bars, extreme once known)",
          not bad, bad[:6])
    # the exporter itself refuses a caption written before its facts
    try:
        OX.ev(100, "x", "text", [160])
        refused = False
    except ValueError:
        refused = True
    check("b. ev() refuses a caption before its refs", refused)


# ------------------------------------------------------------------ c. the page's files
def part_c():
    files = {n: open(os.path.join(OD, n), encoding="utf-8").read() for n in os.listdir(OD) if n.endswith((".html", ".js", ".css"))}
    need = {"index.html", "odeon.css", "app.js", "data.js", "timeline.js", "scene.js", "director.js", "captions.js", "ui.js", "flat.js", "fixture.js", "arena.js", "strip.js"}
    check("c. the modules (data, timeline, scene, director, captions, ui, app, flat fallback, fixture)", need <= set(files), sorted(need - set(files)))
    html, css = files["index.html"], files["odeon.css"]
    check("c. phone viewport with safe areas, own theme-color, dark scheme", 'viewport-fit=cover' in html and 'name="theme-color" content="#14110e"' in html
          and all(f"env(safe-area-inset-{s}" in css for s in ("top", "right", "bottom", "left")) and "color-scheme: dark" in css)
    code = "".join(v for k, v in files.items() if k != "fixture.js")
    check("c. three.js from ../jarvis/three.module.min.js, nothing from another site, no frame break-out",
          "from '../jarvis/three.module.min.js'" in files["scene.js"] and not re.search(r"https?://(?!demetrades2000-coder\.github\.io|www\.w3\.org)", code)
          and "top.location" not in code, re.findall(r"https?://[^\s'\")]+", code)[:5])
    check("c. prefers-reduced-motion respected (CSS + the director + the effects)", "prefers-reduced-motion" in css and "prefers-reduced-motion" in files["app.js"]
          and "this.reduced" in files["director.js"] and "this.reduced" in files["scene.js"])
    check("c. the orb corner: the bottom dock (captions + transport) keeps a 96 px right inset", "--orb: 96px" in css
          and re.search(r"\.dock \{[^}]*right: calc\(var\(--orb\)", css) and 'id="dock"' in html
          and html.index('id="dock"') < html.index('id="cc"') < html.index('id="transport"') < html.index('id="script"'))
    check("c. texts go in as text (no innerHTML)", "innerHTML" not in code)
    check("e. film effects: typewriter captions, bokeh depth of field, letterbox, lens flare (DOM layers), the slow-motion ramp",
          "function typeset(" in files["captions.js"] and all(f'class="{c}"' in html for c in ("dof", "letterbox", "flare"))
          and "const RAMP = " in files["director.js"] and "@keyframes flare" in css and "BOKEH_VS" in files["scene.js"])
    check("e. the gallery sorts by $ (sortReels), Highlights, Oracle's #trade= route, applyTheme + the OLYMPUS theme hook",
          "export function sortReels(" in files["ui.js"] and "function startHighlights()" in files["app.js"] and "trade=" in files["app.js"]
          and "function applyTheme(tokens)" in files["app.js"] and "onTheme" in files["app.js"] and "applyTheme(" in files["scene.js"]
          and html.count("<header") == 1 and 'id="hlBtn"' in html)
    fx = fixture()
    tj = json.load(open(os.path.join(OD, "trades.json"), encoding="utf-8"))
    same = next((t for t in tj["trades"] if t["id"] == fx["id"]), None)
    check("c. fixture.js is one exported trade (the demo reel)", same is not None and same == fx, fx.get("id"))
    j = json.load(open(os.path.join(OD, "jarvis.json"), encoding="utf-8"))
    raw = open(os.path.join(OD, "jarvis.json"), "rb").read()
    ok = (j.get("v") == 1 and 0 < len(j.get("name", "")) <= 40 and j["status"]["level"] in ("ok", "warn", "bad", "off") and len(j["status"]["label"]) <= 48
          and len(j.get("kpis", [])) <= 3 and all(len(k["label"]) <= 20 and len(str(k["value"])) <= 24 and len(str(k.get("delta", ""))) <= 16 for k in j["kpis"])
          and len(j.get("lines", [])) <= 3 and all(len(x) <= 120 and "<" not in x and "\n" not in x for x in j["lines"])
          and isinstance(j.get("t"), int) and re.fullmatch(r"#[0-9a-f]{6}", j.get("theme", "")) and j.get("open") == "#reels" and len(raw) <= 8192)
    check("c. jarvis.json follows the Jarvis contract (v 1, status, <= 3 kpis / lines, t, open, theme #14110e)", ok and j["theme"] == "#14110e", j)
    return fx, tj


# ------------------------------------------------------------------ d. the browser
MODE = {"trades": "ok"}


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path.split("?")[0].endswith("/odeon/trades.json") and MODE["trades"] == "404":
            self.send_error(404)
            return
        super().do_GET()


SPEECH_STUB = """
window.__spoken = [];
const fake = { speaking: false, pending: false, cancel() {}, speak(u) { window.__spoken.push(u.text); }, getVoices() { return []; } };
try { Object.defineProperty(window, 'speechSynthesis', { value: fake, configurable: true }); } catch (e) {}
if (!window.SpeechSynthesisUtterance) window.SpeechSynthesisUtterance = function (t) { this.text = t; };
"""
CC_WATCH = """
window.__cc = [];
document.addEventListener('DOMContentLoaded', () => {
  const t = document.querySelector('#cc .cc-text');
  new MutationObserver(() => { const s = t.textContent; if (s && window.__cc[window.__cc.length - 1] !== s) window.__cc.push(s); })
    .observe(t, { childList: true, characterData: true, subtree: true });
  // the lens flare is a short animation: on a slow (software GL, loaded) machine the poll can miss the class, so it is recorded
  const f = document.querySelector('#flare');
  window.__flareSeen = false;
  if (f) new MutationObserver(() => { if (f.classList.contains('go')) window.__flareSeen = true; }).observe(f, { attributes: true, attributeFilter: ['class'] });
});
"""


def orb_clear(p):
    """every visible control / panel stays out of the bottom-right 80 x 160 px"""
    return p.evaluate("""() => {
      const W = innerWidth, H = innerHeight, bad = [];
      for (const e of document.querySelectorAll('button, input, .cc, .transport, .hud, .stats, .script, .callout')) {
        if (e.closest('[hidden]') || e.closest('#reels')) continue;
        const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
        if (!r.width || !r.height || cs.visibility === 'hidden' || cs.display === 'none') continue;
        if (r.right > W - 80 && r.bottom > H - 160) bad.push((e.id || e.className) + ' ' + Math.round(r.right) + ',' + Math.round(r.bottom));
      }
      return bad;
    }""")


def no_sideways(p):
    return p.evaluate("document.scrollingElement.scrollWidth <= innerWidth && document.body.scrollWidth <= innerWidth")


def wait_state(p, cond, timeout=90):
    p.wait_for_function(f"window.__odeon && (() => {{ const s = window.__odeon.state(); return {cond}; }})()", timeout=timeout * 1000)


def shot(p, name):
    """a JPEG of the screen (the PNGs were ~700 KB each)"""
    os.makedirs(SHOTS, exist_ok=True)
    p.screenshot(path=os.path.join(SHOTS, name.replace(".png", ".jpg")), type="jpeg", quality=82, timeout=120000)


def run_browser(fx, tj):
    from playwright.sync_api import sync_playwright
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}/odeon/"
    fx_texts = [e["text"] for e in fx["events"]]
    fx_kinds_fwd = [e["k"] for e in fx["events"] if e["t"] > fx["bars"]["t0"]]
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}),
                                    args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--autoplay-policy=no-user-gesture-required"])
            for vw in ({"width": 390, "height": 844}, {"width": 844, "height": 390}):
                tag = f"{vw['width']}x{vw['height']}"
                ctx = br.new_context(viewport=vw, device_scale_factor=2, has_touch=True)
                ctx.add_init_script(SPEECH_STUB)
                ctx.add_init_script(CC_WATCH)
                p = ctx.new_page()
                errs = []
                p.on("pageerror", lambda e, errs=errs: errs.append("pageerror: " + str(e)))
                p.on("console", lambda m, errs=errs: errs.append(m.type + ": " + m.text) if m.type == "error" and "favicon" not in m.text
                     and not (MODE["trades"] == "404" and "404" in m.text) else None)

                # ---- the demo fixture (no trades file): plays to the end, stats card, captions in order
                MODE["trades"] = "404"
                p.goto(base + "?speed=60&lite=0")         # full effects for the screenshots (no auto LITE)
                p.wait_for_function("document.body.dataset.ready === 'true'", timeout=90000)
                st = p.evaluate("window.__odeon.state()")
                check(f"d. {tag}: no trades file -> the demo fixture reel (DEMO badge), WebGL theater", st["demo"] and st["id"] == fx["id"]
                      and p.is_visible("#demoBadge") and st["gl"] == "webgl", st)
                time.sleep(0.9)
                shot(p, f"{tag}_0_title.png")
                p.wait_for_function("window.__odeon.state().crossed.includes('sweep')", timeout=180000)
                shot(p, f"{tag}_1_sweep.png")
                p.wait_for_function("window.__odeon.state().crossed.includes('entry')", timeout=180000)
                fl = p.evaluate("""() => ({ go: document.querySelector('#flare').classList.contains('go'), slow: window.__odeon.state().slow,
                  lb: document.body.dataset.slowmo, spans: document.querySelectorAll('#cc .cc-text > span').length,
                  text: document.querySelector('#cc .cc-text').textContent, typing: document.querySelector('#cc .cc-text').classList.contains('typing') })""")
                try:                                       # the ramp eases in over the next frames (wall-clock seconds)
                    p.wait_for_function("window.__odeon.state().slow < 0.6 && document.body.dataset.slowmo === 'true'", timeout=90000)
                    fl["slowmo"] = True
                except Exception:
                    fl["slowmo"] = False
                check(f"e. {tag}: on the entry: the lens flare, the slow-motion ramp (letterbox in), the caption typed in word by word",
                      (fl["go"] or p.evaluate("window.__flareSeen")) and fl["slowmo"] and fl["typing"] and fl["spans"] == len(fl["text"].split()) and fl["text"] in fx_texts, fl)
                time.sleep(0.4)
                shot(p, f"{tag}_2_entry.png")
                wait_state(p, "s.T > " + str(fx["entry"]["t"] + 3600), 180)
                shot(p, f"{tag}_3_in_trade.png")
                p.wait_for_function("window.__odeon.state().crossed.includes('exit')", timeout=180000)
                time.sleep(0.3)
                shot(p, f"{tag}_4_exit_burst.png")
                wait_state(p, "s.ended && s.stats", 180)
                time.sleep(0.8)
                shot(p, f"{tag}_5_stats.png")
                got_usd, got_r = p.inner_text("#statUsd"), p.inner_text("#statR")
                check(f"d. {tag}: the fixture plays to the end; the stats card shows {usd(fx['usd'])} and {rr(fx['r'])}",
                      got_usd == usd(fx["usd"]) and got_r == rr(fx["r"]) and p.is_visible("#stats"), (got_usd, got_r))
                held = p.inner_text("#stHeld")
                check(f"d. {tag}: stats card: MFE / MAE, time in trade, the twin line", p.inner_text("#stMfe").startswith(rr(fx["mfe_r"]))
                      and str(fx["held_min"] // 60) + " h" in held and "backtest" in p.inner_text("#stTwin").lower(), (p.inner_text("#stMfe"), held))
                st = p.evaluate("window.__odeon.state()")
                seen = p.evaluate("window.__cc")
                idx = [fx_texts.index(s) for s in seen if s in fx_texts]
                check(f"d. {tag}: captions appear in the fixture's order and the script holds every one",
                      st["captions"] == fx_texts and idx == sorted(idx) and len(idx) == len(seen) and st["crossed"] == fx_kinds_fwd
                      and p.evaluate("[...document.querySelectorAll('#transcript li span')].map(s => s.textContent)") == fx_texts,
                      {"seen": seen[:4], "crossed": st["crossed"], "want": fx_kinds_fwd})
                check(f"d. {tag}: no sideways scroll, the orb corner free (with the stats card up)", no_sideways(p) and not orb_clear(p), orb_clear(p))

                # ---- the scrubber and the ticks
                p.evaluate("window.__odeon.pause()")
                frac = 0.5
                p.evaluate(f"(() => {{ const s = document.querySelector('#scrub'); s.value = '{int(frac * 1000)}'; s.dispatchEvent(new Event('input')); }})()")
                st = p.evaluate("window.__odeon.state()")
                want = st["tStart"] + frac * (st["tEnd"] - st["tStart"])
                last = [e for e in fx["events"] if e["t"] <= want][-1]
                try:
                    p.wait_for_function(f"document.querySelector('#clock').textContent.startsWith('{hhmm(want, fx['off'])}')", timeout=10000)
                except Exception:
                    pass
                check(f"d. {tag}: the scrubber jumps to a time (state, clock, caption, stats hidden)",
                      abs(st["T"] - want) < 1 and not st["ended"] and p.inner_text("#clock").startswith(hhmm(want, fx["off"]))
                      and p.inner_text("#cc .cc-text") == last["text"] and not p.is_visible("#stats"), (st["T"], want, p.inner_text("#clock")))
                p.click(".tick.k-entry")
                st = p.evaluate("window.__odeon.state()")
                check(f"d. {tag}: the entry tick jumps to 3 minutes before the fill", abs(st["T"] - (fx["entry"]["t"] - 180)) < 1, st["T"])
                check(f"d. {tag}: speech is silent until the Narrate tap", p.evaluate("window.__spoken.length") == 0)
                p.click("#narrate")
                p.evaluate("window.__odeon.speed(5); window.__odeon.play()")
                p.wait_for_function("window.__spoken.length > 0", timeout=90000)
                check(f"d. {tag}: after the tap the captions are spoken", p.get_attribute("#narrate", "aria-pressed") == "true"
                      and p.evaluate("window.__spoken[0]").replace("C I S D", "CISD") in fx_texts + [fx_texts[-1]])
                p.click("#narrate")
                p.click("#scriptBtn")
                shot(p, f"{tag}_6_script.png")
                check(f"d. {tag}: the script panel, orb corner still free", p.is_visible("#script") and not orb_clear(p), orb_clear(p))
                p.click("#scriptBtn")
                check(f"d. {tag}: no console errors (demo)", not errs, errs[:5])
                errs.clear()

                # ---- the real trades file: reels, filters, an ATLAS reel to its stats card
                MODE["trades"] = "ok"
                p.goto(base + "?speed=60&from=reels#reels")
                p.wait_for_function("document.body.dataset.ready === 'true'", timeout=90000)
                n = len(tj["trades"])
                p.wait_for_selector("#reels:not([hidden])")
                time.sleep(0.4)
                shot(p, f"{tag}_7_reels.png")
                check(f"d. {tag}: #reels opens the film-reel list with every trade ({n})", p.locator("#reelList .reel").count() == n
                      and not p.evaluate("window.__odeon.state().demo") and no_sideways(p))
                cards = p.eval_on_selector_all("#reelList .reel", "els => els.map(e => [e.dataset.id, e.querySelector('.p-usd').textContent])")
                want = sorted(tj["trades"], key=lambda t: (-t["usd"], -t["entry"]["t"]))
                check(f"e. {tag}: the gallery: one 3D poster per reel, best $ first, each poster with its $",
                      [c[0] for c in cards] == [t["id"] for t in want] and all(c[1] == usd(t["usd"]) for c, t in zip(cards, want))
                      and p.evaluate("getComputedStyle(document.querySelector('#reelList')).perspective") != "none", cards[:3])
                p.click(".chip[data-s='new']")
                newest = p.eval_on_selector_all("#reelList .reel", "els => els.map(e => e.dataset.id)")
                check(f"e. {tag}: Newest sorts the posters by date", newest == [t["id"] for t in sorted(tj["trades"], key=lambda t: -t["entry"]["t"])])
                p.click(".chip[data-s='usd']")
                p.click(".chip[data-f='atlas']")
                n_atlas = sum(t["bot"] == "ATLAS" for t in tj["trades"])
                check(f"d. {tag}: the ATLAS filter shows only ATLAS reels ({n_atlas})", p.locator("#reelList .reel").count() == n_atlas
                      and all("ATLAS" in x for x in p.locator("#reelList .r-bot").all_inner_texts()))
                at = next(t for t in tj["trades"] if t["bot"] == "ATLAS")
                p.click(f"#reelList .reel[data-id='{at['id']}']")
                st = p.evaluate("window.__odeon.state()")
                check(f"d. {tag}: picking a reel plays it (hash #reel=<id>, list closed)", st["id"] == at["id"] and st["playing"]
                      and p.evaluate("decodeURIComponent(location.hash)") == "#reel=" + at["id"] and not p.is_visible("#reels"))
                p.evaluate(f"window.__odeon.seek({at['entry']['t'] - 300})")
                p.wait_for_function("window.__odeon.state().crossed.includes('entry')", timeout=180000)
                time.sleep(0.5)
                shot(p, f"{tag}_8_atlas_in_trade.png")
                wait_state(p, "s.ended && s.stats", 180)
                check(f"d. {tag}: the ATLAS reel ends on its stats card ({usd(at['usd'])}, {rr(at['r'])})",
                      p.inner_text("#statUsd") == usd(at["usd"]) and p.inner_text("#statR") == rr(at["r"]), p.inner_text("#statUsd"))
                p.click("#stNext")
                st = p.evaluate("window.__odeon.state()")
                ids = [t["id"] for t in tj["trades"]]
                check(f"d. {tag}: Next reel plays the next one", st["id"] == ids[(ids.index(at["id"]) + 1) % len(ids)] and st["playing"])
                if vw["width"] == 390:
                    # ---- Highlights: the five best trades by $, back to back
                    p.evaluate("window.__odeon.speed(60)")
                    p.click("#reelsBtn")
                    p.click("#hlBtn")
                    top5 = [t["id"] for t in sorted([t for t in tj["trades"] if t["usd"] > 0], key=lambda t: (-t["usd"], -t["entry"]["t"]))[:5]]
                    st = p.evaluate("window.__odeon.state()")
                    check(f"e. {tag}: Highlights plays the five best trades by $ (1/5 first)", st["hl"] and st["hl"]["ids"] == top5 and st["id"] == top5[0]
                          and p.inner_text("#hlBadge") == "HIGHLIGHT 1/5" and not p.is_visible("#reels"), st.get("hl"))
                    p.evaluate("window.__odeon.seek(window.__odeon.state().tEnd - 60)")
                    p.wait_for_function(f"window.__odeon.state().id === '{top5[1]}'", timeout=150000)
                    shot(p, f"{tag}_10_highlights.png")
                    check(f"e. {tag}: after the stats card the next highlight starts by itself (2/5)", p.inner_text("#hlBadge") == "HIGHLIGHT 2/5"
                          and p.evaluate("window.__odeon.state().playing"))
                    # ---- Oracle's link: #trade=<day>_<HHMM>_<side> (any source prefix), and one with no film
                    lit = next(t for t in tj["trades"] if t["bot"] == "LIT" and t["id"] != top5[0])
                    key = lit["id"].split(".", 1)[1]
                    p.goto(base + "?speed=60#trade=" + key)
                    p.wait_for_function("document.body.dataset.ready === 'true'", timeout=90000)
                    st = p.evaluate("window.__odeon.state()")
                    near = p.evaluate(f"window.__odeon.find('{lit['day']}_{hhmm(lit['entry']['t'] + 120, lit['off']).replace(':', '')}_{lit['side'].lower()}')")
                    check(f"e. {tag}: Oracle's #trade= link plays that trade's reel (and a time 2 minutes off finds it too)",
                          st["id"] == lit["id"] and st["playing"] and not st["hl"] and near == lit["id"], [st["id"], lit["id"], near])
                    p.goto(base + "?speed=60#trade=2020-01-02_0930_long")
                    p.wait_for_function("document.body.dataset.ready === 'true'", timeout=90000)
                    p.wait_for_selector("#reels:not([hidden])")
                    check(f"e. {tag}: a trade with no film opens the gallery with a plain note", p.is_visible("#reelNote") and "No film" in p.inner_text("#reelNote"))
                    r = p.evaluate("window.__odeon.applyTheme({ accent: '#ff8800', bg: '#020304' })")
                    check(f"e. {tag}: applyTheme(tokens) recolours the page (accent, background)", r == {"accent": "#ff8800", "bg": "#020304"}
                          and p.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--blue').trim()") == "#ff8800")
                    k0 = p.evaluate("window.__odeon.applyTheme({ id: 'olympus', accent: '#a855f7', bg: '#04050c', mix: 0, harmony: 0 })")
                    check(f"e. {tag}: the OLYMPUS default theme leaves Odeon's own gold as it is", k0 == {"accent": "#c8a24a", "bg": None}, k0)
                    shot(p, f"{tag}_11_no_film_note.png")
                check(f"d. {tag}: no console errors (real reels)", not errs, errs[:5])
                ctx.close()

            # ---- reduced motion, LITE, the 2D fallback
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, reduced_motion="reduce")
            p = ctx.new_page()
            errs = []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            p.goto(base + "?speed=60&lite=1")
            p.wait_for_function("document.body.dataset.ready === 'true'", timeout=90000)
            time.sleep(1.5)
            check("d. reduced motion: flagged, no film grain; ?lite=1: LITE badge", p.evaluate("document.body.dataset.reduced") == "true"
                  and not p.is_visible(".grain") and p.is_visible("#liteBadge") and p.evaluate("window.__odeon.state().lite"))
            check("e. reduced motion: no typewriter (the caption appears whole), no depth-of-field blur, no lens flare",
                  p.evaluate("document.querySelectorAll('#cc .cc-text > span').length") == 0
                  and p.evaluate("getComputedStyle(document.querySelector('.dof')).display") == "none"
                  and p.evaluate("getComputedStyle(document.querySelector('.flare')).display") == "none")
            st0 = p.evaluate("window.__odeon.state().T")
            time.sleep(1.0)
            check("d. reduced motion still plays the reel", p.evaluate("window.__odeon.state().T") > st0)
            p.goto(base + "?speed=60&flat=1")
            p.wait_for_function("document.body.dataset.ready === 'true'", timeout=90000)
            time.sleep(1.5)
            shot(p, "390x844_9_flat_fallback.png")
            st = p.evaluate("window.__odeon.state()")
            check("d. without WebGL the 2D stage plays the same reel", st["gl"] == "flat" and st["T"] > st["tStart"] and st["n"] == len(tj["trades"]), st)
            check("d. no console errors (reduced motion, LITE, 2D)", not errs, errs[:5])
            ctx.close()
            look_checks(br, base, tj)
            br.close()
    finally:
        srv.shutdown()


def look_checks(br, base, tj):
    """h. the 2026-11-03 look pass: the OLYMPUS render core, the amphitheatre, the trade strip (drag to scrub trade by trade), the R ruler
    and the live P&L tag in the scene."""
    html = open(os.path.join(OD, "index.html"), encoding="utf-8").read()
    sc = open(os.path.join(OD, "scene.js"), encoding="utf-8").read()
    ar = open(os.path.join(OD, "arena.js"), encoding="utf-8").read()
    check("h. static: scene.js on the render core, arena.js (cavea, skene, torches, orchestra) on materials.js, the trade strip in the dock",
          "from '../olympus/render.js'" in sc and "from '../olympus/materials.js'" in ar and "createRenderer(" in sc and 'id="strip"' in html
          and html.index('id="dock"') < html.index('id="strip"') < html.index('id="cc"') and os.path.isfile(os.path.join(OD, "strip.js")))
    trades = sorted(tj["trades"], key=lambda t: (t["entry"]["t"], t["id"]))
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, has_touch=False)
    ctx.add_init_script(SPEECH_STUB)
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" and "favicon" not in m.text else None)
    MODE["trades"] = "ok"
    p.goto(base + "?speed=60&autoplay=0")
    p.wait_for_function("document.body.dataset.ready === 'true' && window.__odeon.look()", timeout=60000)
    look = p.evaluate("window.__odeon.look()")
    n = len(trades)
    net = sum(t["usd"] for t in trades)
    bars = p.evaluate("document.querySelectorAll('#strip .st-bars .b').length")
    lab = p.inner_text("#strip .st-lab")
    on = p.evaluate("(() => { const b = document.querySelector('#strip .st-bars .b.on'); return b ? +b.dataset.i : -1; })()")
    cur = p.evaluate("window.__odeon.state().id")
    check(f"h. trade strip: {n} bars in time order, the open reel marked and named in the label (k/{n}, day, side, R, $, running total)",
          p.is_visible("#strip") and bars == n and on >= 0 and cur == trades[on]["id"] and f"/{n}" in lab and "running" in lab, (bars, n, lab, on, cur))
    # drag: press at the bar k, move to the bar j, let go -> the reel of trade j opens
    box = p.locator("#strip .st-bars").bounding_box()
    j = 0 if cur != trades[0]["id"] else n - 1
    x = box["x"] + box["width"] * (j + 0.5) / n
    y = box["y"] + box["height"] / 2
    p.mouse.move(box["x"] + box["width"] * 0.5, y)
    p.mouse.down()
    p.mouse.move(x, y, steps=4)
    mid = p.inner_text("#strip .st-lab")
    p.mouse.up()
    p.wait_for_function(f"window.__odeon.state().id === {json.dumps(trades[j]['id'])}", timeout=90000)
    check("h. trade strip: dragging shows the trade under the finger (day, side, R, $, running total) and letting go opens its reel",
          f"{j + 1}/{n}" in mid and usd(trades[j]["usd"]) in mid and rr(trades[j]["r"]) in mid and usd(sum(t["usd"] for t in trades[:j + 1])) in mid, (mid, trades[j]["id"]))
    p.click("#strip .st-next")
    nxt = trades[(j + 1) % n]["id"]
    p.wait_for_function(f"window.__odeon.state().id === {json.dumps(nxt)}", timeout=90000)
    check("h. trade strip: the arrow steps to the next trade (and the bar under it lights up)", p.evaluate("document.querySelector('#strip .b.on') && +document.querySelector('#strip .b.on').dataset.i") == (j + 1) % n)
    # the R ruler and the live P&L tag
    tr = p.evaluate("window.__odeon.trade()")
    risk = tr["risk_pts"]
    t_r = abs(tr["target"] - tr["entry"]["px"]) / risk
    want = [-1] + list(range(1, min(10, int(t_r + 1e-6)) + 1))
    look = p.evaluate("window.__odeon.look()")
    check("h. the R ruler: -1R (the stop) and every whole R up to the target, standing beside the entry", [r["n"] for r in look["rungs"]] == want, (look["rungs"], want))
    p.evaluate(f"window.__odeon.seek({tr['exit']['t_end'] + 60})")
    p.wait_for_function("window.__odeon.look().tag && window.__odeon.look().tag.on", timeout=90000)       # software GL: a frame can take seconds
    look = p.evaluate("window.__odeon.look()")
    m = re.search(r"([+\u2212])([\d.]+)R", look["tag"]["text"])
    got_r = (-1 if m and m.group(1) == "\u2212" else 1) * float(m.group(2)) if m else None
    check("h. after the exit the R ruler is up and the P&L tag rests on the exit with the trade's R and $",
          look["tag"]["on"] and all(r["on"] for r in look["rungs"]) and got_r is not None and abs(got_r - tr["r"]) <= 0.35 and "$" in look["tag"]["text"], (look["tag"], tr["r"]))
    p.evaluate(f"window.__odeon.seek({tr['entry']['t'] - 600})")
    p.wait_for_function("window.__odeon.look().tag && !window.__odeon.look().tag.on", timeout=90000)
    look = p.evaluate("window.__odeon.look()")
    check("h. before the entry: no ruler, no tag", not look["tag"]["on"] and not any(r["on"] for r in look["rungs"]), look)
    check("h. software GL runs the render core on the LITE tier (scene + finish); the arena is in the scene: marble on physical materials, instanced colonnade, torch and lamp lights",
          look["passes"] == ["scene", "finish"] and look["arena"] and look["kinds"].count("physical") >= 5 and look["kinds"].count("instanced") >= 6 and look["kinds"].count("light") >= 3, look)
    check("h. no console errors with the arena and the strip", not errs, errs[:5])
    shot(p, "390x844_h_strip_lite.png")
    ctx.close()
    # HD tier (?q=high) on a small canvas: bloom + 4x MSAA, three passes
    ctx = br.new_context(viewport={"width": 390, "height": 700}, device_scale_factor=1)
    q = ctx.new_page()
    herr = []
    q.on("pageerror", lambda e: herr.append(str(e)))
    q.goto(base + "?speed=60&autoplay=0&lite=0&q=high")
    q.wait_for_function("document.body.dataset.ready === 'true' && window.__odeon.look() && window.__odeon.look().stats.calls > 0", timeout=150000)
    hd = q.evaluate("window.__odeon.look()")
    check("h. HD tier: scene + bloom + finish with 4x MSAA, the amphitheatre in the same frame, no page error",
          hd["passes"] == ["scene", "bloom", "finish"] and hd["stats"]["samples"] == 4 and hd["stats"]["bloom"] and hd["quality"] == "high" and not herr, (hd["passes"], hd["stats"], herr))
    shot(q, "390x700_h_hd.png")
    ctx.close()


def main():
    no_browser = "--no-browser" in sys.argv
    bundle, extra = part_a()
    part_b(bundle, extra)
    fx, tj = part_c()
    if not no_browser:
        try:
            import playwright  # noqa: F401
        except ImportError:
            print("[SKIP] Playwright missing: browser part skipped")
        else:
            run_browser(fx, tj)
    n_ok = sum(RES)
    print(f"\n{n_ok}/{len(RES)} passed" + (f" -> screenshots in {SHOTS}" if not no_browser else ""))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
