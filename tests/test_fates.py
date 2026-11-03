"""FATES (tools/fates/ + tools/web_public/fates/, 2026-11-03): the Monte Carlo of the owner's evals and money, drawn as
threads of fate. Checks:
  a. MFFU rules on hand-made paths: an intraday touch of the floor fails, the floor trails the best close and locks at
     start + $100, target + min days = pass (not before the min days), 7 quiet calendar days close the account, the
     owner's keep-alive on quiet day 6 keeps it open, the soft daily loss caps a trade, the bot's stuck rule, the plan
     numbers come from research/lit/mffu_rules.json
  b. the bootstrap: deterministic (same seed, same futures; another seed, others), blocks of 5 real days, every real
     day equally likely, the per-session mean kept (2026 P&L of the live-settings replay, within 3 standard errors)
  c. the engine: Zlarior's eval == tools/uprisk.Eval and ATLAS's == tools/atx_edge.Eval on the same futures (the
     engines the money plan and the ATLAS research use); the ledger == research/lab/backtest_live.json; a small build
     twice = the same JSON; the money of a book adds up from its events
  d. the JSON: schema, <= 1 MB, today's live start, both samples, threads <= 400; jarvis.json = docs/JARVIS_APPS.md
     contract with "Pass odds this eval: x%"
  e. the page in Chromium at 390 x 844 (a temp copy of the site layout): no errors, the HUD = the fixture's numbers,
     DEMO without fates.json, the scenario / sample / accounts / 6M-12M toggles and the #route, a tap follows a thread day
     by day, Spin again, prefers-reduced-motion (no animation), LITE, no sideways scroll, the orb's corner free
    python -X utf8 -m tests.test_fates                 (~1-2 min; temp folders only)
FATES_SHOTS=<dir> also saves screenshots of every scenario on the real tools/web_public/fates/fates.json.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import functools
import glob
import http.server
import json
import math
import os
import shutil
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.fates import export as EX  # noqa: E402
from tools.fates import rules as RU  # noqa: E402
from tools.fates import sim as SI  # noqa: E402
from tools.fates import sources as SO  # noqa: E402

WEB = os.path.join(ROOT, "tools", "web_public")
FATES = os.path.join(WEB, "fates")
SHOTS = os.environ.get("FATES_SHOTS")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


D = dt.date


# ------------------------------------------------------------------------------------------------ a. rules
class Stub:
    """A bot that plays a fixed script: day -> (pnl, worst, traded)."""
    stuck = None

    def __init__(self, script):
        self.script = script

    def play_eval(self, units, book, real_day=None):
        return self.script.get(real_day, (0.0, 0.0, False))


def test_rules():
    R = RU.load_rules("builder50k")
    J = json.load(open(RU.RULES_FILE, encoding="utf-8"))["limits"]["builder_50k"]
    check("a. 50K plan from mffu_rules.json: target / max loss / lock / daily loss / 7 days / $91.80",
          (R.target, R.mll, R.lock, R.dll, R.inactivity_days, R.price) == (J["target"], J["mll"], J["lock"], J["dll"], 7, 91.80), R)
    R25 = RU.load_rules("builder25k")
    check("a. 25K plan: $1,500 target, $1,000 max loss, $600 daily loss, $63", (R25.target, R25.mll, R25.dll, R25.price) == (1500, 1000, 600, 63.0), R25)

    b = RU.EvalBook(R)
    o = b.close_session(D(2026, 11, 3), +500.0, -2000.0, True)
    check("a. an intraday touch of the floor fails even if the day closes green (open losses count)", o == RU.FAIL and b.bal == b.floor, (o, b))
    b = RU.EvalBook(R)
    o = b.close_session(D(2026, 11, 3), -2000.0, -2000.0, True)
    check("a. a close at the floor fails", o == RU.FAIL, o)
    b = RU.EvalBook(R)
    o = b.close_session(D(2026, 11, 3), -1999.0, -1999.0, True)
    check("a. $1 above the floor is still open", o is None and abs(b.room - 1.0) < 1e-6, (o, b.room))
    b = RU.EvalBook(R)
    b.close_session(D(2026, 11, 3), 1500.0, -100.0, True)
    check("a. the floor trails the best close (+$1,500 -> floor -$500)", b.floor == -500.0, b.floor)
    b.close_session(D(2026, 11, 4), -800.0, -900.0, True)
    check("a. the floor never moves down", b.floor == -500.0, b.floor)
    b.close_session(D(2026, 11, 5), 1500.0, 0.0, True)
    check("a. the floor locks at start + $100", b.floor == 100.0, (b.bal, b.floor))

    b = RU.EvalBook(R)
    o = b.close_session(D(2026, 11, 3), 3000.0, -50.0, True)
    check("a. target reached with the min days (1) = PASS", o == RU.PASS, o)
    R2 = dataclasses.replace(R, min_days=2)
    b = RU.EvalBook(R2)
    o1 = b.close_session(D(2026, 11, 3), 3100.0, 0.0, True)
    o2 = b.close_session(D(2026, 11, 4), -2.4, -2.4, True)
    check("a. target on day 1 with min 2 days: open, then PASS on the 2nd traded day", o1 is None and o2 == RU.PASS, (o1, o2))

    b = RU.EvalBook(R, last_trade=D(2026, 11, 2))          # traded Monday
    outs = [b.close_session(d, 0.0, 0.0, False) for d in (D(2026, 11, 3), D(2026, 11, 4), D(2026, 11, 5), D(2026, 11, 6), D(2026, 11, 9))]
    check("a. 7 quiet calendar days close the account (Mon trade -> closed the next Mon)", outs == [None, None, None, None, RU.CLOSED], outs)
    b = RU.EvalBook(R, last_trade=D(2026, 11, 2))
    outs = [b.close_session(d, 0.0, 0.0, d == D(2026, 11, 6)) for d in (D(2026, 11, 3), D(2026, 11, 6), D(2026, 11, 9), D(2026, 11, 12))]
    check("a. a trade restarts the 7-day count", outs == [None, None, None, None], outs)

    days = [D(2026, 11, 3), D(2026, 11, 4), D(2026, 11, 5), D(2026, 11, 6), D(2026, 11, 9)]
    st = Stub({})
    for ka, want in ((False, RU.CLOSED), (True, None)):
        b = RU.EvalBook(R, last_trade=D(2026, 11, 2))
        res = [SI.eval_session(st, b, [], d.isoformat(), d, ka) for d in days]
        outs = [o for o, _ in res]
        if ka:
            check("a. the owner's keep-alive (1 MNQ on quiet day 6) keeps the eval open and costs $2.40",
                  all(o is None for o in outs) and sum(k for _, k in res) == 1 and abs(b.bal + RU.KEEPALIVE_COST) < 1e-9, (outs, res, b.bal))
        else:
            check("a. without the keep-alive the same quiet week closes it", outs[-1] == want, outs)

    p, lo = RU.apply_dll(-700.0, -500.0, -600.0, 1000.0, 2.5)
    check("a. the soft daily loss closes a trade at the limit plus slippage", (p, lo) == (-302.5, -302.5), (p, lo))
    p, lo = RU.apply_dll(0.0, 300.0, -100.0, 1000.0, 2.5)
    check("a. a trade inside the daily loss is untouched", (p, lo) == (300.0, -100.0), (p, lo))
    b = RU.EvalBook(R, stuck_below=200.0)
    o = b.close_session(D(2026, 11, 3), -1850.0, -1850.0, True)
    check("a. the bot's stuck rule: under $200 of room the eval is over", o == RU.STUCK, (o, b.room))


# ------------------------------------------------------------------------------------------------ b. bootstrap
def test_bootstrap():
    import numpy as np
    a, b, c = SI.bootstrap(206, 50, 126, 23), SI.bootstrap(206, 50, 126, 23), SI.bootstrap(206, 50, 126, 24)
    check("b. same seed, same futures; another seed, other futures", (a == b).all() and not (a == c).all())
    blocks = a[:, :125].reshape(50, 25, 5)
    steps = (blocks[:, :, 1:] - blocks[:, :, :-1]) % 206
    check("b. futures are made of 5 consecutive real days", (steps == 1).all())
    big = SI.bootstrap(206, 4000, 126, 7).ravel()
    freq = np.bincount(big, minlength=206) / big.size
    check("b. every real day equally likely (circular blocks: no edge day under-drawn)", abs(freq.max() * 206 - 1) < 0.08 and abs(freq.min() * 206 - 1) < 0.08,
          (freq.min() * 206, freq.max() * 206))
    bt = json.load(open(SO.BACKTEST_LIVE, encoding="utf-8"))
    x = np.array([d["pnl"] for d in bt["days"] if "2026-01-01" <= d["date"] <= "2026-10-16"])
    P = SI.bootstrap(len(x), 4000, 126, 23)
    m = float(x[P].mean())
    se = float(x.std()) / math.sqrt(P.size / 5)
    check(f"b. the bootstrap keeps the per-session mean (2026 live replay ${x.mean():.1f} vs ${m:.1f} a session, 3 SE = ${3 * se:.1f})",
          abs(m - x.mean()) < 3 * se, (m, x.mean(), se))


# ------------------------------------------------------------------------------------------------ c. engine
def test_engine():
    import uprisk as U
    lit = SO.LitSource()
    chk = lit.check_against_replay()
    check("c. Zlarior's trade units = run lit_live's trades (research/lab/backtest_live.json)", chk["same_days"] and chk["replay_trades"] == chk["ledger_trades"], chk)
    S = lit.sessions()
    cal = [D(2026, 11, 3) + dt.timedelta(days=i) for i in range(400) if (D(2026, 11, 3) + dt.timedelta(days=i)).weekday() < 5]
    R50 = dataclasses.replace(RU.load_rules("builder50k"), inactivity_days=10 ** 6)
    for per in ("2026", "2021-25"):
        Dd = SO.period_dates(S, per)
        P = SI.bootstrap(len(Dd), 120, 60, 5)
        r = SI.run_eval(lit, R50, SI.Start(), Dd, P, cal, keepalive=False)
        bad = 0
        for i, seq in enumerate(P):
            e, out, used = U.Eval(lit.ecfg, "builder50k"), "open", 60
            for k, si in enumerate(seq):
                o = e.step(lit.units(Dd[si]))
                if o:
                    out, used = o, k + 1
                    break
            bad += (out, used) != (r["out"][i], r["at"][i])
        check(f"c. Zlarior eval == tools/uprisk.Eval on 120 futures ({per})", bad == 0, bad)
    atlas = SO.AtlasSource()
    x = atlas._libs()
    R25 = dataclasses.replace(RU.load_rules("builder25k"), inactivity_days=10 ** 6)
    Dd = SO.period_dates(S, "2026")
    P = SI.bootstrap(len(Dd), 60, 60, 5)
    r = SI.run_eval(atlas, R25, SI.Start(), Dd, P, cal, keepalive=False)
    bad = 0
    with atlas.active():
        for i, seq in enumerate(P):
            e, out, used = x["X"].Eval(x["M"]), "open", 60
            for k, si in enumerate(seq):
                o, _ = e.step(atlas.units(Dd[si]), Dd[si])
                if o:
                    out, used = o, k + 1
                    break
            bad += (out, used) != (r["out"][i], r["at"][i])
    check("c. ATLAS eval == tools/atx_edge.Eval on 60 futures (2026)", bad == 0, bad)

    from tools.fates import build as B
    live = os.path.join(FATES, "fixture.json")
    fx = json.load(open(live, encoding="utf-8"))
    tmp = tempfile.mkdtemp(prefix="fates_t_")
    try:
        lj = os.path.join(tmp, "live.json")
        bots = fx["live"]["bots"]
        json.dump({"t": fx["live"]["t"] or 1793671913, "board": {
            "lit": {"room": bots["zlarior"]["room"], "to_target": bots["zlarior"]["to_target"], "session": bots["zlarior"]["session"], "quiet_days": 5},
            "atlas": {"room": bots["atlas"]["room"], "to_target": bots["atlas"]["to_target"], "session": bots["atlas"]["session"], "quiet_days": 5}}},
            open(lj, "w"))
        docs = [B.build(n=40, n_threads=12, seed=23, live_path=lj, fetch=False, periods=("2026", "2021-25"), log=lambda *a: None) for _ in range(2)]
        strip = lambda d: json.dumps({k: v for k, v in d.items() if k not in ("built", "t", "build_seconds")}, sort_keys=True)  # noqa: E731
        check("c. a build is deterministic (same seed, same JSON twice)", strip(docs[0]) == strip(docs[1]))
        d = docs[0]
        z = d["scenarios"]["eval:zlarior:2026"]
        check("c. today's live start: Zlarior session 12, room and target from live.json, peak = floor + $2,000",
              z["start"]["session"] == 12 and abs(z["start"]["profit"] - (3000 - bots["zlarior"]["to_target"])) < 0.01
              and abs(z["start"]["floor"] - (z["start"]["profit"] - bots["zlarior"]["room"])) < 0.01
              and abs(z["start"]["peak"] - (z["start"]["floor"] + 2000)) < 0.01, z["start"])
        s = z["summary"]
        check("c. the odds add up to 100% (pass + fail + closed + open)", abs(s["pass"] + s["fail"] + s["closed"] + s["open"] - 100) < 0.2, s)
        check("c. p10 <= p15 <= pass, f10 <= f15, dec10 = p10 + f10", s["p10"] <= s["p15"] <= s["pass"] and s["f10"] <= s["f15"]
              and abs(s["dec10"] - s["p10"] - s["f10"]) < 0.2, s)
        m = d["scenarios"]["money:2026"]
        ok = True
        for flat in m["threads"]["ev"]:
            v = sum(flat[i + 3] for i in range(0, len(flat), 4))
            ok &= isinstance(v, int)
        b1, b6 = m["books"]["1"], m["books"]["6"]
        check("c. money: 6 accounts buy more evals than 1, events in fours", ok and b6["12m"]["evals"] > b1["12m"]["evals"], (b1, b6))
        bad = EX.validate(d)
        check("c. the small build passes the schema", not bad, bad)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ d. JSON
def test_json():
    p = os.path.join(FATES, "fates.json")
    check("d. tools/web_public/fates/fates.json exists", os.path.exists(p))
    if not os.path.exists(p):
        return None
    size = os.path.getsize(p)
    d = json.load(open(p, encoding="utf-8"))
    bad = EX.validate(d)
    check(f"d. fates.json passes the schema and is <= 1 MB ({size / 1e3:.0f} KB)", not bad and size <= 1_000_000, bad)
    keys = set(d["scenarios"])
    want = {f"eval:{b}:{p}" for b in ("zlarior", "atlas") for p in ("2026", "2021-25")} | {"money:2026", "money:2021-25"}
    check("d. both bots' evals and the money paths, on the 2026 and the 2021-25 samples", want <= keys, keys)
    check("d. ~400 threads a scenario", all(len(d["scenarios"][k]["threads"].get("b", d["scenarios"][k]["threads"].get("ev", []))) <= 400 for k in want)
          and len(d["scenarios"]["eval:zlarior:2026"]["threads"]["b"]) == d["threads"] == 400, d["threads"])
    check("d. 1-6 accounts in each money scenario", all(set(d["scenarios"][f"money:{p}"]["books"]) == set("123456") for p in ("2026", "2021-25")))
    check("d. every period labelled (2026 vs 2021-25)", all(d["periods"][p]["label"] for p in ("2026", "2021-25")) and "weaker" in d["periods"]["2021-25"]["label"])
    jv = json.load(open(os.path.join(FATES, "jarvis.json"), encoding="utf-8"))
    raw = open(os.path.join(FATES, "jarvis.json"), "rb").read()
    lines_ok = all(isinstance(x, str) and len(x) <= 120 and "<" not in x and "\n" not in x for x in jv.get("lines", []))
    kp_ok = len(jv.get("kpis", [])) <= 3 and all(len(k["label"]) <= 20 and len(str(k["value"])) <= 24 and len(str(k.get("delta", ""))) <= 16 for k in jv["kpis"])
    pz = d["scenarios"]["eval:zlarior:2026"]["summary"]["pass"]
    check("d. jarvis.json: the docs/JARVIS_APPS.md contract (v, name, status, kpis, lines, t, theme, <= 8 KB)",
          jv["v"] == 1 and jv["name"] == "FATES" and jv["status"]["level"] in ("ok", "warn", "bad", "off") and len(jv["status"]["label"]) <= 48
          and lines_ok and kp_ok and isinstance(jv["t"], int) and jv["theme"] == "#07050f" and len(raw) <= 8192, jv)
    check("d. jarvis.json says \"Pass odds this eval: x%\" with the 2026 number", jv["lines"][0].startswith(f"Pass odds this eval: {EX.pct(pz)}"), jv["lines"][0])
    return d


# ------------------------------------------------------------------------------------------------ e. the page
def pct(x):
    return f"{math.floor(float(x) + 0.5)}%"


def usd(x):
    v = math.floor(float(x) + 0.5)
    return ("−" if v < 0 else "") + f"${abs(v):,}"


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def site(with_data: str | None):
    """A temp copy of the site layout: <tmp>/fates/ (+ fates.json = with_data) and <tmp>/jarvis/ (three.js, fonts, icon)."""
    tmp = tempfile.mkdtemp(prefix="fates_site_")
    os.makedirs(os.path.join(tmp, "fates"))
    os.makedirs(os.path.join(tmp, "jarvis"))
    for n in os.listdir(FATES):
        if n not in ("fates.json",):
            shutil.copy(os.path.join(FATES, n), os.path.join(tmp, "fates", n))
    if with_data:
        shutil.copy(with_data, os.path.join(tmp, "fates", "fates.json"))
    for n in ("three.module.min.js", "orbitron.woff2", "rajdhani-500.woff2", "rajdhani-700.woff2", "icon-192.png"):
        shutil.copy(os.path.join(WEB, "jarvis", n), os.path.join(tmp, "jarvis", n))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=tmp))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return tmp, srv, f"http://127.0.0.1:{srv.server_address[1]}/fates/"


def hud_text(p):
    return p.evaluate("""() => Object.fromEntries([...document.querySelectorAll('.tile')].map((t) => [t.dataset.id,
        { l: t.querySelector('.l').textContent, v: t.querySelector('.v').textContent, s: t.querySelector('.s').textContent }]))""")


def expect_eval(s, span="12m"):
    m = s["summary"]
    mm = m["money"][span]
    return {"pass": pct(m["pass"]), "fail": pct(m["fail"]), "days": str(math.floor(m["pass_med"] + 0.5)) if m["pass_med"] is not None else "—",
            "money": usd(mm["pm_p50"]), "money_s": f"p10 {usd(mm['pm_p10'])} · p90 {usd(mm['pm_p90'])}", "pay30": pct(m["money"]["pay30"])}


def expect_money(s, n, span="12m"):
    b = s["books"][str(n)]
    return {"pass": pct(b["ahead"]), "fail": pct(b["behind"]), "money": usd(b[span]["pm_p50"]), "pay30": pct(b["pay30"]),
            "days": str(math.floor(b["first_pay_med"] + 0.5)) if b["first_pay_med"] is not None else "—"}


def same(h, e):
    return all(h[k]["v"] == e[k] for k in ("pass", "fail", "days", "money", "pay30")) and ("money_s" not in e or h["money"]["s"] == e["money_s"])


def test_page():
    from playwright.sync_api import sync_playwright
    fx = json.load(open(os.path.join(FATES, "fixture.json"), encoding="utf-8"))
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    args = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
    tmp, srv, url = site(None)
    tmp2, srv2, url2 = site(os.path.join(FATES, "fixture.json"))
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=args)
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            p = ctx.new_page()
            errs = []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
            p.on("response", lambda r: errs.append(f"{r.status} {r.url}") if r.status >= 400 and not r.url.split("?")[0].endswith("/fates/fates.json") else None)
            ready = lambda: p.wait_for_function("window.__fates && window.__fates.ready", timeout=30000)  # noqa: E731

            # the demo: no fates.json -> fixture.json, DEMO badge, the HUD = the fixture's numbers
            p.goto(url + "?full=1")
            ready()
            h = hud_text(p)
            ez = expect_eval(fx["scenarios"]["eval:zlarior:2026"])
            check("e. no fates.json: the fixture loads with a DEMO badge", p.is_visible("#demo") and p.evaluate("__fates.demo"))
            check("e. HUD = the fixture (Zlarior, 2026): pass / fail / days / $ a month p10-p50-p90 / payout <= 30 days", same(h, ez), (h, ez))
            check("e. WebGL scene up with ~400 threads in one draw call", p.evaluate("__fates.webgl") and p.evaluate("__fates.threads.length") == len(fx["scenarios"]["eval:zlarior:2026"]["threads"]["b"]),
                  p.evaluate("__fates.probe()"))
            meta = p.evaluate("({tc: document.querySelector('meta[name=theme-color]').content, vp: document.querySelector('meta[name=viewport]').content})")
            check("e. its own theme-color (= jarvis.json theme) and viewport-fit=cover", meta["tc"] == "#07050f" and "viewport-fit=cover" in meta["vp"], meta)
            css = open(os.path.join(FATES, "fates.css"), encoding="utf-8").read()
            check("e. safe areas on all four sides and reduced motion in the CSS", all(f"safe-area-inset-{s}" in css for s in ("top", "right", "bottom", "left"))
                  and "prefers-reduced-motion" in css)

            # toggles
            p.click("#scen button[data-scen=atlas]")
            h = hud_text(p)
            check("e. ATLAS toggle: #atlas/2026 and its numbers", p.evaluate("location.hash") == "#atlas/2026" and same(h, expect_eval(fx["scenarios"]["eval:atlas:2026"])), h)
            p.click("#period button[data-period='2021-25']")
            h = hud_text(p)
            check("e. 2021-25 toggle: its numbers and the weaker-edge warning", same(h, expect_eval(fx["scenarios"]["eval:atlas:2021-25"])) and p.is_visible("#weak"), h)
            p.click("#scen button[data-scen=money]")
            p.click("#accts button[data-n='4']")
            h = hud_text(p)
            check("e. Money, 4 accounts (2021-25): the book's numbers and #money-4/2021-25",
                  p.evaluate("location.hash") == "#money-4/2021-25" and same(h, expect_money(fx["scenarios"]["money:2021-25"], 4)) and p.is_visible("#acctsRow"), h)
            p.click("#period button[data-period='2026']")
            p.click("#span button[data-span='6m']")
            h = hud_text(p)
            check("e. 6M toggle: the 6-month $ a month", same(h, expect_money(fx["scenarios"]["money:2026"], 4, "6m")) and "6 mo" in h["money"]["l"], h)
            p.click("#span button[data-span='12m']")
            for n in range(1, 7):
                p.click(f"#accts button[data-n='{n}']")
                if not same(hud_text(p), expect_money(fx["scenarios"]["money:2026"], n)):
                    break
            check("e. accounts 1-6 each show their own book", n == 6 and same(hud_text(p), expect_money(fx["scenarios"]["money:2026"], 6)), n)
            p.goto(url + "?full=1#zlarior/2021-25")
            ready()
            check("e. a #route opens its scenario", same(hud_text(p), expect_eval(fx["scenarios"]["eval:zlarior:2021-25"])))

            # follow a thread
            p.goto(url + "?full=1#zlarior/2026")
            ready()
            time.sleep(6.5)
            pt = None
            for i in range(0, 40):
                q = p.evaluate(f"__fates.pointOf({i}, 3)")
                if q and 20 < q["x"] < 370 and 330 < q["y"] < 760:
                    pt = (i, q)
                    break
            if pt:
                p.mouse.click(pt[1]["x"], pt[1]["y"])
                time.sleep(0.8)
            sel = p.evaluate("__fates.sel")
            rows = p.evaluate("document.querySelectorAll('#fRows li').length")
            check("e. tapping a thread follows it day by day (panel with one row a session)", pt is not None and sel >= 0 and p.is_visible("#follow")
                  and rows == len(fx["scenarios"]["eval:zlarior:2026"]["threads"]["b"][sel]), (pt, sel, rows))
            p.click("#fClose")
            check("e. closing the panel", not p.is_visible("#follow") and p.evaluate("__fates.sel") == -1)
            k0 = p.evaluate("__fates.probe().k")
            p.click("#spin")
            time.sleep(0.25)
            k1 = p.evaluate("__fates.probe().k")
            check("e. Spin again re-animates the threads from today", k0 > 50 and k1 < k0, (k0, k1))

            # corner, scroll
            free = p.evaluate("""() => { const W = innerWidth, H = innerHeight, hit = [];
                for (let x = W - 78; x < W; x += 13) for (let y = H - 158; y < H; y += 13) {
                  const el = document.elementFromPoint(x, y); if (el && el.closest('button, a, .follow, .tile, .seg, .hint')) hit.push([x, y, el.className]); }
                return hit; }""")
            check("e. the bottom-right 80 x 160 px stays free for Jarvis's orb", not free, free[:4])
            for w in (375, 390, 430):
                p.set_viewport_size({"width": w, "height": 844})
                time.sleep(0.2)
                sw = p.evaluate("document.documentElement.scrollWidth")
                if sw > w:
                    break
            check("e. no sideways scroll at 375 / 390 / 430 px", sw <= w, (w, sw))
            p.set_viewport_size({"width": 390, "height": 844})

            # fates.json present: no DEMO
            p.goto(url2 + "?full=1")
            ready()
            check("e. with fates.json: no DEMO badge, the same numbers", not p.is_visible("#demo") and same(hud_text(p), ez))

            # LITE
            p.goto(url + "?lite=1")
            ready()
            check("e. LITE: at most 160 threads and the LITE tag", p.evaluate("__fates.threads.length") <= 160 and p.is_visible("#lite"))
            check("e. no page errors, no failed request (only the demo's missing fates.json)", not errs and not p.evaluate("__fates.errors"), errs[:3])
            ctx.close()

            # reduced motion
            ctx = br.new_context(viewport={"width": 390, "height": 844}, reduced_motion="reduce")
            p = ctx.new_page()
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto(url + "?full=1")
            ready()
            time.sleep(0.4)
            pr = p.evaluate("__fates.probe()")
            check("e. prefers-reduced-motion: every thread drawn at once, nothing animates", p.evaluate("__fates.reduced") and pr["k"] >= 60, pr)
            check("e. no page errors (reduced motion)", not errs, errs[:3])
            ctx.close()

            if SHOTS:
                shots(br, SHOTS)
            br.close()
    finally:
        for s in (srv, srv2):
            s.shutdown()
        for t in (tmp, tmp2):
            shutil.rmtree(t, ignore_errors=True)


def shots(br, out):
    """Screenshots of every scenario on the real fates.json (FATES_SHOTS=<dir>)."""
    os.makedirs(out, exist_ok=True)
    tmp, srv, url = site(os.path.join(FATES, "fates.json"))
    try:
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3)
        p = ctx.new_page()
        for name, route, tap in (("01_zlarior_2026", "#zlarior/2026", False), ("02_atlas_2026", "#atlas/2026", False),
                                 ("03_zlarior_2021-25", "#zlarior/2021-25", False), ("04_atlas_2021-25", "#atlas/2021-25", False),
                                 ("05_money_2_2026", "#money-2/2026", False), ("06_money_6_2026", "#money-6/2026", False),
                                 ("07_money_6_2021-25", "#money-6/2021-25", False), ("08_follow_zlarior", "#zlarior/2026", True)):
            p.goto(url + "?full=1" + route)
            p.wait_for_function("window.__fates && window.__fates.ready", timeout=30000)
            time.sleep(7)
            if tap:
                for i in range(40):
                    q = p.evaluate(f"__fates.pointOf({i}, 4)")
                    if q and 20 < q["x"] < 370 and 330 < q["y"] < 700:
                        p.mouse.click(q["x"], q["y"])
                        break
                time.sleep(4)
            p.screenshot(path=os.path.join(out, name + ".png"))
            print("   shot", name, flush=True)
        ctx.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    t0 = time.time()
    test_rules()
    test_bootstrap()
    test_engine()
    test_json()
    test_page()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed ({time.time() - t0:.0f}s)")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
