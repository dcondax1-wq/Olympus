"""NQ LIVE screen (day-livedash 2026-11-26; owner: "I want to see live trades on the dashboard, where we're at").
tools/web_public/nq/live.html + live.js (page) + livecore.js (pure rules) + live.css.

  a. static: the files, read only (no innerHTML / storage / sends), no outside URL but the PC feed, OLYMPUS NIGHT colours, 15-30 s poll,
     linked from the NQ dashboard and Home's Right-now card
  b. node (livecore.js, with nqdesk / clock7 / acctcore as the page uses them):
     the REAL PC post of 2026-11-22 (tests/fixtures/nq_live): 4 accounts, ATLAS +$401 funded, health in words, flat, LIT 4/10 from the glance;
     an open LIT long on 2 accounts (ext "at" + the chart post + board.lit.position): one card, live $ and R from the newest price, the accounts;
     the Brain feed (bf) wins over the glance; a PC quiet 3 h is red; today's trades + week / month
  c. browser 390x844 (ntfy mocked with the status post + a real pack_bars chart post): the trade card pulses with the chart's entry /
     stop / target lines, 4 account tiles, setups, today's list; flat; stale. --shots -> research/handoff/2026-11-26/livedash/shots/
Run: python -X utf8 -m tests.test_nq_live [--shots]
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402

check = AK.check
WEB = os.path.join(ROOT, "tools", "web_public")
NQ = os.path.join(WEB, "nq")
FIX = os.path.join(ROOT, "tests", "fixtures", "nq_live", "real_post_2026-11-22.json")
SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-26", "livedash", "shots")
ET = ZoneInfo("America/New_York")


def et(y, m, d, hh=0, mm=0) -> int:
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


NOW = et(2026, 11, 24, 10, 42)            # Tue 11-24 10:42 ET
T = NOW - 4 * 60                          # the PC posted 4 min ago
ENTRY_T = et(2026, 11, 24, 10, 5)         # LIT long in at 10:05 ET


def real():
    with open(FIX, encoding="utf-8") as f:
        return json.load(f)


def retime(p, t):
    """the real post as if the PC had posted at t (every 'now' time moved; the old trade rows stay where they were)"""
    p = copy.deepcopy(p)
    p["t"] = t
    p["reporter"]["t"] = t + 30
    p["pc_verdict"]["t"] = t
    p["pc"]["t"] = t
    p["pc"]["glance"]["t"] = t - 60
    for k in ("mf", "at"):
        p[k]["t"] = t
    p["board"]["t"] = p["board"]["data_t"] = t
    for a in p["accounts"]:
        a["conn"]["t"] = t
    p.pop("sg", None), p.pop("svk", None)
    return p


def trade_post(t=T, bf=False):
    """a LIT long 3 MNQ on the 50K + 2 on the 25K #2, entered 10:05 at 25,650, stop 25,630, target 25,760; price 25,668 now"""
    p = retime(real(), t)
    p["price"] = 25668.0
    p["pc"]["glance"]["bots"][0].update({"stage": "In trade (9/10)", "px": 25664.0})
    for a in p["at"]["a"]:
        pass
    p["at"]["a"] += [{"id": "mffu50k_eval", "l4": "6016", "tr": [[ENTRY_T - 3600 * 24 * 1, ENTRY_T - 3600 * 23, -1, 3, 25800.0, 25820.0, 25700.0, "TARGET", 300.0, 5.0],
                                                                  [ENTRY_T, None, 1, 3, 25650.0, 25630.0, 25760.0, None, None, None]]},
                     {"id": "b25k_2", "l4": "6019", "tr": [[ENTRY_T, None, 1, 2, 25650.0, 25630.0, 25760.0, None, None, None]]}]
    # ATLAS closed one this morning: short 1 at 25,700 -> stop 25,712 (-$24 + fees)
    p["at"]["a"][0]["tr"].append([et(2026, 11, 24, 9, 35), et(2026, 11, 24, 9, 50), -1, 1, 25700.0, 25712.0, 25600.0, "STOP", -26.4, -1.1])
    p["board"]["lit"]["position"] = {"side": "LONG", "qty": 3, "entry": 25650.0, "stop": 25630.0, "target": 25760.0, "entry_t": ENTRY_T, "unrealized_r": 0.5}
    p["accounts"][0]["pnl"]["week"] = 300.0
    if bf:
        p["bf"] = {"v": 1, "t": t - 30, "bots": {
            "lit": {"think": ["10:38 long 3 MNQ from 25,650.00, stop 25,630.00"], "next": {"setup": "LONG sweep + shift of the 09:30 low",
                    "steps": [{"name": str(i), "done": i < 9} for i in range(1, 11)], "waiting_for": "managing: BE at +1R", "dist_pts": 18.0}},
            "atlas": {"think": ["10:30 S/R: watching PDH"], "next": {"setup": "S/R short at PDH", "steps": "2/5", "waiting_for": "a sweep of PDH 25,742",
                      "dist_pts": 74.0, "window": "until 12:00 ET"}}}}
    return p


def bars_post(now=NOW):
    from tools import pc_report as P
    t0 = et(2026, 11, 24, 7, 0)
    bars, px = [], 25600.0
    for i in range(int((now - 300 - t0) // 300)):
        t = t0 + 300 * i
        o = px
        c = o + (6 if (i % 5) in (0, 1, 3) else -4) * (1 if i < 40 else 0.5)
        bars.append([t, o, max(o, c) + 3, min(o, c) - 3, c])
        px = c
    bars[-1][4] = 25668.0
    opens = [{"k": "z50k", "s": 1, "q": 3, "t": ENTRY_T, "e": 25650.0, "sl": 25630.0, "tp": 25760.0},
             {"k": "z25k2", "s": 1, "q": 2, "t": ENTRY_T, "e": 25650.0, "sl": 25630.0, "tp": 25760.0}]
    accts = {"z50k": ["Zlarior 50K", "LIT", "LIVE"], "z25k2": ["Zlarior 25K #2", "LIT", "LIVE"]}
    return P.pack_bars(bars, opens, [], accts, now=now - 60, day="2026-11-24")


# ------------------------------------------------------------------------------------------------ a. static
def part_a():
    files = {n: open(os.path.join(NQ, n), encoding="utf-8").read() for n in ("live.html", "live.js", "livecore.js", "live.css")}
    js = files["live.js"] + files["livecore.js"]
    check("a. live.html, live.js, livecore.js, live.css exist; the page loads pc_feed.js + live.js", "pc_feed.js" in files["live.html"] and "live.js?v=" in files["live.html"])
    check("a. read only: no innerHTML / insertAdjacentHTML / eval / storage / POST / sendBeacon",
          not re.search(r"innerHTML|insertAdjacentHTML|\beval\(|localStorage|sessionStorage|method:\s*['\"]POST|sendBeacon", js))
    check("a. no outside URL (the PC feed comes from status_feed.json)", not re.search(r"https?://(?!www\.w3\.org)", js + files["live.html"]))
    check("a. OLYMPUS NIGHT: black, cards #16131e, violet #3e255e / #4d2e76 / #9d59ee, gold #f1c14b, mint #77db89; no brown",
          all(c in files["live.css"] for c in ("#000", "#16131e", "#3e255e", "#4d2e76", "#9d59ee", "#f1c14b", "#77db89")))
    m = re.search(r"POLL_MS = (\d+)", files["livecore.js"])
    check("a. the feed is asked every 15-30 s, only while visible", m and 15000 <= int(m.group(1)) <= 30000 and "visibilityState" in files["live.js"], m and m.group(1))
    nq = open(os.path.join(NQ, "index.html"), encoding="utf-8").read()
    gate = open(os.path.join(WEB, "gate", "index.html"), encoding="utf-8").read()
    check("a. linked: the NQ dashboard's first screen and Home's Right-now card open nq/live.html", 'href="live.html"' in nq and 'href="nq/live.html"' in gate)
    check("a. livecore.js is pure (no document / window / fetch)", not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(", re.sub(r"//[^\n]*", "", files["livecore.js"])))


# ------------------------------------------------------------------------------------------------ b. node
DRIVER = r"""
import fs from 'fs'; import path from 'path'; import { createRequire } from 'module';
const dir = process.argv[2], scen = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const D = await import(path.join(dir, 'nqdesk.mjs')), K7 = await import(path.join(dir, 'clock7.mjs')), A = await import(path.join(dir, 'acctcore.mjs'));
const L = await import(path.join(dir, 'livecore.mjs')), B = await import(path.join(dir, 'nqbars.mjs'));
const F = createRequire(import.meta.url)(path.join(dir, 'pc_feed.cjs'));
const biz = JSON.parse(fs.readFileSync(scen.biz, 'utf8')), out = {};
for (const [name, s] of Object.entries(scen.runs)) {
  const t = s.now, lite = s.lite, h = lite ? F.homeOver({}, lite, t, null) : {};
  const cards = A.build(D.accounts(h, biz, t), K7.rows(lite, t), { lite, biz, nowS: t, today: K7.tradingDay(t) }).cards;
  let bars = s.bars ? { ...s.bars } : null;
  if (bars) { const u = B.unpack(bars); bars._last = u.length ? u[u.length - 1] : null; }
  out[name] = L.build({ lite, bars, cards, nowS: t });
}
console.log(JSON.stringify(out));
"""


def node_run(runs):
    tmp = tempfile.mkdtemp(prefix="le_nqlive_")
    try:
        for f in ("nqdesk", "clock7", "acctcore", "livecore", "nqbars"):
            src = open(os.path.join(NQ, f + ".js"), encoding="utf-8").read()
            src = re.sub(r"from '\./(\w+)\.js(\?v=[\w.]+)?'", r"from './\1.mjs'", src)
            open(os.path.join(tmp, f + ".mjs"), "w", encoding="utf-8").write(src)
        shutil.copy(os.path.join(WEB, "pc_feed.js"), os.path.join(tmp, "pc_feed.cjs"))
        open(os.path.join(tmp, "drv.mjs"), "w", encoding="utf-8").write(DRIVER)
        sc = os.path.join(tmp, "scen.json")
        json.dump({"biz": os.path.join(WEB, "business", "accounts.json"), "runs": runs}, open(sc, "w", encoding="utf-8"))
        r = subprocess.run(["node", os.path.join(tmp, "drv.mjs"), tmp, sc], capture_output=True, text=True, timeout=120)
        if r.returncode:
            print(r.stderr[:2000])
            return {}
        return json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_b():
    R = real()
    rt = R["reporter"]["t"]
    out = node_run({
        "real": {"now": rt + 300, "lite": R},
        "trade": {"now": NOW, "lite": trade_post(), "bars": bars_post()},
        "trade_nobars": {"now": NOW, "lite": trade_post()},
        "bf": {"now": NOW, "lite": trade_post(bf=True), "bars": bars_post()},
        "stale": {"now": NOW, "lite": retime(real(), NOW - 3 * 3600)},
        "none": {"now": NOW, "lite": None},
    })
    check("b. node ran the 6 scenarios", len(out) == 6, list(out))
    if len(out) != 6:
        return
    M = out["real"]
    names = [a["name"] for a in M["accounts"]]
    check("b. real post: the 4 accounts (Zlarior 50K, ATLAS 25K, Rapid EOD 25K, Zlarior 25K #2)",
          names == ["Zlarior 50K", "ATLAS 25K", "Rapid EOD 25K", "Zlarior 25K #2"], names)
    A = {a["key"]: a for a in M["accounts"]}
    check("b. real: ATLAS shows MFFU's +$401 funded and $1,699 to the payout; Zlarior $49,214, room $1,046 of $2,000, $3,786 to pass",
          A["atlas"]["balance"] == "+$401" and A["atlas"]["goal"]["text"] == "+$1,699" and A["zlarior"]["balance"] == "$49,214"
          and A["zlarior"]["room"] == "$1,046" and A["zlarior"]["roomOf"] == "$2,000" and A["zlarior"]["goal"]["text"] == "$3,786", A)
    check("b. real: Zlarior + Rapid ARMED, ATLAS ON not armed (said in plain words), PC 5 min ago green",
          A["zlarior"]["state"] == "armed" and A["rapid1"]["state"] == "armed" and A["atlas"]["state"] == "on" and M["pc"]["level"] == "ok"
          and any("ATLAS is running but NOT armed" in x["text"] for x in M["health"]["lines"]), (M["health"], [a["state"] for a in M["accounts"]]))
    S = {s["id"]: s for s in M["setups"]}
    check("b. real: no open trade; LIT step 4/10 Displacement from the glance with its waiting words; ATLAS outside its hours 0/5",
          M["open"] is None and S["lit"]["n"] == 4 and S["lit"]["of"] == 10 and S["lit"]["label"] == "Displacement" and "strong 5m candle" in S["lit"]["wait"]
          and S["lit"]["src"] == "glance" and S["atlas"]["n"] == 0 and S["atlas"]["label"] == "outside its hours", M["setups"])
    check("b. real: ATLAS's month = its 2 November trades (+$514 - $113 = +$401)", round(A["atlas"]["month"]) == 401 and A["atlas"]["monthN"] == 2, A["atlas"])

    O = out["trade"]["open"]
    check("b. trade: ONE open card, LIT LONG 5 MNQ (3 on the 50K + 2 on the 25K #2), entry / stop / target",
          O and O["side"] == "LONG" and O["qty"] == 5 and O["entry"] == 25650 and O["stop"] == 25630 and O["target"] == 25760 and O["bot"] == "lit"
          and sorted(a["name"] for a in O["accounts"]) == ["Zlarior 25K #2", "Zlarior 50K"], O)
    check("b. trade: live $ and R from the newest price (the report's 25,668, 4 min old: newer than the last candle): +18 pts = +$180, +0.9R, risk $200",
          O and O["px"] == 25668 and O["pxSrc"] == "the PC report" and O["pxAge"] == 240 and round(O["usd"]) == 180 and abs(O["r"] - 0.9) < 1e-9 and round(O["riskUsd"]) == 200
          and O["toStop"] == 38 and O["toTarget"] == 92, O)
    check("b. trade: in for 37 min, the accounts in it flagged; the 25K #2 tile says IN TRADE",
          O and round(O["inFor"] / 60) == 37 and {a["key"] for a in out["trade"]["accounts"] if a["inTrade"]} == {"zlarior", "fresh25"}, [(a["key"], a["inTrade"]) for a in out["trade"]["accounts"]])
    O2 = out["trade_nobars"]["open"]
    check("b. no chart post: the same card from the ext 'at' rows + board.lit.position, priced at the report's 25,668 (+$180)",
          O2 and O2["qty"] == 5 and O2["pxSrc"] == "the PC report" and round(O2["usd"]) == 180, O2)
    TD = out["trade"]["today"]
    check("b. today's trades: the open LIT long on both accounts + ATLAS's closed short -$26 (-1.1R); yesterday's not in it",
          sorted((t["name"], t["open"]) for t in TD) == [("ATLAS 25K", False), ("Zlarior 25K #2", True), ("Zlarior 50K", True)]
          and round(out["trade"]["todayUsd"]) == -26, TD)
    A2 = {a["key"]: a for a in out["trade"]["accounts"]}
    check("b. week: the PC's own +$300 for the 50K; ATLAS this week from its trades (-$26)",
          A2["zlarior"]["week"] == 300 and round(A2["atlas"]["week"]) == -26, (A2["zlarior"]["week"], A2["atlas"]["week"]))
    S2 = {s["id"]: s for s in out["trade"]["setups"]}
    check("b. glance setups while in a trade: LIT 9/10 In trade", S2["lit"]["n"] == 9 and S2["lit"]["label"] == "In trade", S2["lit"])
    S3 = {s["id"]: s for s in out["bf"]["setups"]}
    check("b. Brain feed (bf) wins: ATLAS 2/5 'S/R short at PDH', 74 pts away, until 12:00 ET; its own age",
          S3["atlas"]["src"] == "bf" and S3["atlas"]["n"] == 2 and S3["atlas"]["of"] == 5 and S3["atlas"]["dist"] == 74 and S3["atlas"]["window"] == "until 12:00 ET"
          and S3["atlas"]["ageS"] == 270 and out["bf"]["rich"]["bf"] is True, S3["atlas"])
    St = out["stale"]
    check("b. a PC quiet 3 h: red, said in words, every account tile's age red",
          St["pc"]["level"] == "bad" and St["health"]["level"] == "bad" and "quiet" in St["health"]["lines"][0]["text"]
          and all(a["ageLvl"] == "bad" for a in St["accounts"]), St["health"])
    N = out["none"]
    check("b. nothing from the PC: no trade, honest title, plan tiles only", N["open"] is None and N["health"]["title"].startswith("No report"), N["health"])


# ------------------------------------------------------------------------------------------------ c. browser
def ndjson(lite, bars=None) -> str:
    core = {k: v for k, v in lite.items()}
    lines = [{"event": "message", "time": core["reporter"]["t"], "message": json.dumps(core)}]
    if bars:
        lines.append({"event": "message", "time": bars["rt"], "message": json.dumps(bars)})
    return "\n".join(json.dumps(x) for x in lines) + "\n"


def part_c():
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("  (playwright not installed: browser part skipped)")
        return
    at = dt.datetime.fromtimestamp(NOW, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    srv, origin = AK.serve({"/home.json": None})
    shots = "--shots" in sys.argv
    read = """() => ({ trade: !document.getElementById('trade').hidden, flat: !document.getElementById('flat').hidden,
        usd: document.getElementById('tradeUsd').textContent, r: document.getElementById('tradeR').textContent, side: document.getElementById('tradeSide').textContent,
        who: document.getElementById('tradeWho').textContent, anim: getComputedStyle(document.getElementById('trade')).animationName,
        lines: [...document.querySelectorAll('#chart svg text')].map((e) => e.textContent), candles: document.querySelectorAll('#chart svg rect').length,
        accts: [...document.querySelectorAll('.lv-acct')].map((e) => e.dataset.key), inTrade: [...document.querySelectorAll('.lv-acct[data-trade="1"]')].map((e) => e.dataset.key), opens: [...document.querySelectorAll('.lv-open')].map((e) => e.textContent),
        setups: [...document.querySelectorAll('.lv-setup')].map((e) => e.querySelector('.lv-n').textContent), today: document.querySelectorAll('#today li').length,
        pc: document.getElementById('pc').textContent, lvl: document.getElementById('pc').dataset.level, health: document.getElementById('health').textContent,
        txt: document.getElementById('app').textContent })"""
    try:
        with AK.browser() as br:
            for name, lite, bars in (("trade", trade_post(bf=True), bars_post()), ("flat", retime(real(), T), None), ("stale", retime(real(), NOW - 3 * 3600), None)):
                ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844, mock={"json?poll=1": ndjson(lite, bars)})
                p.goto(f"{origin}/nq/live.html?at={at}")
                p.wait_for_function("window.NQ_LIVE && window.NQ_LIVE.ready() && window.NQ_LIVE.S.lite", timeout=60000)
                p.wait_for_timeout(600)
                o = p.evaluate(read)
                if name == "trade":
                    check("c. 390 px, in a trade: the gold card pulses, LONG 5 MNQ · Zlarior, +$180 / +0.9R, both accounts named",
                          o["trade"] and not o["flat"] and o["anim"] == "tradeGlow" and o["usd"] == "+$180" and o["r"].startswith("+0.9R")
                          and "LONG" in o["side"] and "5 MNQ" in o["side"] and "Zlarior 50K (3)" in o["who"] and "Zlarior 25K #2 (2)" in o["who"], o)
                    check("c. the mini chart: candles + TP / SL / IN / NOW lines", o["candles"] > 20 and any(x.startswith("TP 25760") for x in o["lines"])
                          and any(x.startswith("SL 25630") for x in o["lines"]) and any(x.startswith("IN 25650") for x in o["lines"]) and "NOW" in o["lines"], o["lines"])
                    check("c. 4 account tiles, the two in the trade lit; setups 9/10 + 2/5 (Brain feed); 3 rows today",
                          o["accts"] == ["zlarior", "atlas", "rapid1", "fresh25"] and sorted(o["inTrade"]) == ["fresh25", "zlarior"]
                          and o["setups"] == ["9/10", "2/5"] and o["today"] == 3, o)
                    check("c. each tile in the trade shows its own open $ (3 MNQ +$108, 2 MNQ +$72)", o["opens"] == ["+$108 open", "+$72 open"], o["opens"])
                elif name == "flat":
                    check("c. flat: no trade card, 'Flat right now' + who is armed, LIT 4/10, PC 4 min ago green",
                          not o["trade"] and o["flat"] and "Flat right now" in o["txt"] and "Armed: Zlarior 50K" in o["txt"] and o["setups"][0] == "4/10"
                          and o["pc"] == "PC 4 min ago" and o["lvl"] == "ok", o)
                else:
                    check("c. stale: 'PC 3 h ago' red, the health card says the PC is quiet", o["pc"].startswith("PC 3 h") and o["lvl"] == "bad" and "quiet" in o["health"], o)
                check(f"c. {name}: taps >= 44 px, no sideways scroll, nothing off the site (ntfy mocked), no console error",
                      not AK.taps(p) and AK.no_sideways(p) and not off and not errs and p.mocked, (AK.taps(p)[:4], off[:3], errs[:3]))
                if name == "trade":
                    n0 = p.evaluate("window.NQ_LIVE.S.polls")
                    p.wait_for_function(f"window.NQ_LIVE.S.polls > {n0}", timeout=40000)
                    check("c. the 22 s poll asks the feed again by itself (a new ntfy request, past pc_feed's 20 s shared answer)", len(p.mocked) > 2, len(p.mocked))
                if shots:
                    os.makedirs(SHOTS, exist_ok=True)
                    p.evaluate("document.getAnimations().forEach((a) => { try { a.pause(); a.currentTime = 1100; } catch (e) {} })")
                    p.screenshot(path=os.path.join(SHOTS, f"live-390-{name}.png"), full_page=False)
                    if name in ("trade", "flat"):
                        p.screenshot(path=os.path.join(SHOTS, f"live-390-{name}-full.png"), full_page=True)
                ctx.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    part_b()
    part_c()
    return AK.finish()


if __name__ == "__main__":
    sys.exit(main())
