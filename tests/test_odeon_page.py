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
Screenshots go to research/handoff/2026-11-03/odeon/ (ODEON_SHOTS=<dir> to change).

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
SHOTS = os.environ.get("ODEON_SHOTS") or os.path.join(ROOT, "research", "handoff", "2026-11-03", "odeon")
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
        lit = next(t for t in T if t["bot"] == "LIT")
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
    need = {"index.html", "odeon.css", "app.js", "data.js", "timeline.js", "scene.js", "director.js", "captions.js", "ui.js", "flat.js", "fixture.js"}
    check("c. the modules (data, timeline, scene, director, captions, ui, app, flat fallback, fixture)", need <= set(files), sorted(need - set(files)))
    html, css = files["index.html"], files["odeon.css"]
    check("c. phone viewport with safe areas, own theme-color, dark scheme", 'viewport-fit=cover' in html and 'name="theme-color" content="#07060c"' in html
          and all(f"env(safe-area-inset-{s}" in css for s in ("top", "right", "bottom", "left")) and "color-scheme: dark" in css)
    code = "".join(v for k, v in files.items() if k != "fixture.js")
    check("c. three.js from ../jarvis/three.module.min.js, nothing from another site, no frame break-out",
          "from '../jarvis/three.module.min.js'" in files["scene.js"] and not re.search(r"https?://(?!demetrades2000-coder\.github\.io|www\.w3\.org)", code)
          and "top.location" not in code, re.findall(r"https?://[^\s'\")]+", code)[:5])
    check("c. prefers-reduced-motion respected (CSS + the director + the effects)", "prefers-reduced-motion" in css and "prefers-reduced-motion" in files["app.js"]
          and "this.reduced" in files["director.js"] and "this.reduced" in files["scene.js"])
    check("c. the orb corner: everything fixed at the bottom keeps a 96 px right inset", "--orb: 96px" in css
          and re.search(r"\.transport \{[^}]*right: calc\(var\(--orb\)", css) and re.search(r"\.cc \{[^}]*right: calc\(var\(--orb\)", css))
    check("c. texts go in as text (no innerHTML)", "innerHTML" not in code)
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
    check("c. jarvis.json follows the Jarvis contract (v 1, status, <= 3 kpis / lines, t, open, theme #07060c)", ok and j["theme"] == "#07060c", j)
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
    p.screenshot(path=os.path.join(SHOTS, name.replace(".png", ".jpg")), type="jpeg", quality=82)


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
                p.wait_for_function("document.body.dataset.ready === 'true'", timeout=30000)
                st = p.evaluate("window.__odeon.state()")
                check(f"d. {tag}: no trades file -> the demo fixture reel (DEMO badge), WebGL theater", st["demo"] and st["id"] == fx["id"]
                      and p.is_visible("#demoBadge") and st["gl"] == "webgl", st)
                time.sleep(0.9)
                shot(p, f"{tag}_0_title.png")
                p.wait_for_function("window.__odeon.state().crossed.includes('sweep')", timeout=60000)
                shot(p, f"{tag}_1_sweep.png")
                p.wait_for_function("window.__odeon.state().crossed.includes('entry')", timeout=60000)
                time.sleep(0.4)
                shot(p, f"{tag}_2_entry.png")
                wait_state(p, "s.T > " + str(fx["entry"]["t"] + 3600), 90)
                shot(p, f"{tag}_3_in_trade.png")
                p.wait_for_function("window.__odeon.state().crossed.includes('exit')", timeout=90000)
                time.sleep(0.3)
                shot(p, f"{tag}_4_exit_burst.png")
                wait_state(p, "s.ended && s.stats", 60)
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
                p.wait_for_function("window.__spoken.length > 0", timeout=30000)
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
                p.wait_for_function("document.body.dataset.ready === 'true'", timeout=30000)
                n = len(tj["trades"])
                p.wait_for_selector("#reels:not([hidden])")
                time.sleep(0.4)
                shot(p, f"{tag}_7_reels.png")
                check(f"d. {tag}: #reels opens the film-reel list with every trade ({n})", p.locator("#reelList .reel").count() == n
                      and not p.evaluate("window.__odeon.state().demo") and no_sideways(p))
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
                p.wait_for_function("window.__odeon.state().crossed.includes('entry')", timeout=60000)
                time.sleep(0.5)
                shot(p, f"{tag}_8_atlas_in_trade.png")
                wait_state(p, "s.ended && s.stats", 90)
                check(f"d. {tag}: the ATLAS reel ends on its stats card ({usd(at['usd'])}, {rr(at['r'])})",
                      p.inner_text("#statUsd") == usd(at["usd"]) and p.inner_text("#statR") == rr(at["r"]), p.inner_text("#statUsd"))
                p.click("#stNext")
                st = p.evaluate("window.__odeon.state()")
                ids = [t["id"] for t in tj["trades"]]
                check(f"d. {tag}: Next reel plays the next one", st["id"] == ids[(ids.index(at["id"]) + 1) % len(ids)] and st["playing"])
                check(f"d. {tag}: no console errors (real reels)", not errs, errs[:5])
                ctx.close()

            # ---- reduced motion, LITE, the 2D fallback
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, reduced_motion="reduce")
            p = ctx.new_page()
            errs = []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            p.goto(base + "?speed=60&lite=1")
            p.wait_for_function("document.body.dataset.ready === 'true'", timeout=30000)
            time.sleep(1.5)
            check("d. reduced motion: flagged, no film grain; ?lite=1: LITE badge", p.evaluate("document.body.dataset.reduced") == "true"
                  and not p.is_visible(".grain") and p.is_visible("#liteBadge") and p.evaluate("window.__odeon.state().lite"))
            st0 = p.evaluate("window.__odeon.state().T")
            time.sleep(1.0)
            check("d. reduced motion still plays the reel", p.evaluate("window.__odeon.state().T") > st0)
            p.goto(base + "?speed=60&flat=1")
            p.wait_for_function("document.body.dataset.ready === 'true'", timeout=30000)
            time.sleep(1.5)
            shot(p, "390x844_9_flat_fallback.png")
            st = p.evaluate("window.__odeon.state()")
            check("d. without WebGL the 2D stage plays the same reel", st["gl"] == "flat" and st["T"] > st["tStart"] and st["n"] == len(tj["trades"]), st)
            check("d. no console errors (reduced motion, LITE, 2D)", not errs, errs[:5])
            ctx.close()
            br.close()
    finally:
        srv.shutdown()


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
