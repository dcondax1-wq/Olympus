"""night-nq-of 2026-11-27: the NQ ORDER FLOW room (tools/web_public/nq/orderflow.html / .js / .css). PAPER research page.
  a. static: read only (no innerHTML / storage / sends), no outside URL but the PC feed, OLYMPUS NIGHT (no cyan, no brown / olive),
     reduced motion honoured, PAPER on the page, BLITZ never named
  b. node (orderflow.js model): empty = honest 'no order-flow day yet'; a recorded day from of_room.json; today LIVE from the status
     ext "ofp" (reads win over the room, stale post ignored); verdict words (TOO FEW honest, SIMULATED labelled); forward ring n / 20
  c. browser 390x844 + 1440x900 (fixture of_room.json built by tools/build_of_room.py from SIMULATED days + a mocked status post):
     ladder rungs with reads + NOW line, tape, paper rows, lane B, verdict card, ring; empty state; taps >= 44, no sideways scroll,
     nothing off the site, no console error. --shots -> research/handoff/2026-11-27/night-nq-of/shots/
Run: python -X utf8 -m tests.test_nq_of [--shots]
"""
from __future__ import annotations

import datetime as dt
import gzip
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402

check = AK.check
NQ = os.path.join(ROOT, "tools", "web_public", "nq")
SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-27", "night-nq-of", "shots")
ET = ZoneInfo("America/New_York")


def load(path, name):
    sp = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


def fixture_room() -> dict:
    """of_room.json built by the REAL builder from simulated pulled days (labelled sim in its verdict)."""
    Sim = load("research/orderflow/of_sim.py", "nqof_sim")
    V = load("tools/of_realday_verdict.py", "nqof_v")
    RB = load("tools/build_of_room.py", "nqof_rb")
    W = Sim.world(8, "planted", seed=61, lvl=True)
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "data", "pc_days")
        for d in W["days"]:
            od = os.path.join(src, d, "of"); os.makedirs(od)
            R = W["R"][d]
            with gzip.open(os.path.join(od, "NQ_bars5m.csv.gz"), "wt") as fh:
                R["bars"].to_csv(fh, index=False)
            with gzip.open(os.path.join(od, "NQ_fp5m.csv.gz"), "wt") as fh:
                R["fp"].to_csv(fh, index=False)
            json.dump(R["meta"], open(os.path.join(od, "NQ_meta.json"), "w"))
            rows = []
            for t in W["lit"]:
                if t["day"] == d:
                    rows += [{"bot": "zlarior", "src": "main", "side": "buy" if t["dir"] == 1 else "sell", "entry_t": t["tn"], "stop": 1.0},
                             {"bot": "zlarior", "src": "main", "side": "exit", "entry_t": t["tn"], "t": t["tn"] + 900, "pnl": t["pnl"]}]
            with gzip.open(os.path.join(src, d, "trades.jsonl.gz"), "wt") as fh:
                fh.write("\n".join(json.dumps(r) for r in rows))
        os.makedirs(os.path.join(td, "research", "orderflow"))
        V.run(src=src, lit=W["lit"], out_json=os.path.join(td, "research", "orderflow", "real_verdict.json"),
              out_md=os.path.join(td, "v.md"), label="sim-planted", say=lambda *_: None)
        room = RB.build(td)
    return room


def real_room():
    """The REAL room: the committed nq/of_room.json (the last real tick day) + the verdict block this checkout's
    build_of_room makes from research/orderflow/real_verdict.json (51 real days, 2026-11-27). None when they are missing."""
    try:
        room = json.load(open(os.path.join(NQ, "of_room.json"), encoding="utf-8"))
        RB = load("tools/build_of_room.py", "nqof_rb_real")
        b = RB.build(ROOT)
        v = b.get("verdict")
        if v and v.get("label") == "real":
            room["verdict"] = v
        room["control"] = b.get("control")
        return room
    except (OSError, ValueError):
        return None


def part_a():
    html = AK.read(os.path.join(NQ, "orderflow.html")); js = AK.read(os.path.join(NQ, "orderflow.js")); css = AK.read(os.path.join(NQ, "orderflow.css"))
    allf = html + js + css
    check("a. the three files exist; the page loads orderflow.js as a module + the PC feed", "orderflow.js" in html and "pc_feed.js" in html and 'type="module"' in html)
    check("a. read only: no innerHTML / storage / sends", not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|localStorage|sessionStorage|sendBeacon|method:\s*['\"]POST", js), "")
    check("a. no outside URL (only of_room.json + the site's own pc_feed)", not re.search(r"https?://(?!www\.w3\.org)", js + html))
    check("a. OLYMPUS NIGHT colours, no cyan / brown / olive", all(c in css for c in ("#9d59ee", "#f1c14b", "#77db89", "#16131e"))
          and not re.search(r"#0ff\b|#00ffff|cyan|#22d3ee|#06b6d4|olive|#808000|brown|#8b4513", css, re.I))
    check("a. prefers-reduced-motion stops every animation", "prefers-reduced-motion: reduce" in css and "animation: none !important" in css)
    check("a. PAPER on the page; BLITZ never named", "PAPER" in html and "PAPER" in js and "blitz" not in allf.lower())


NODE = r"""
import * as O from '%(js)s';
const out = {};
const day = (t) => O.etParts(t).day;
const now = %(now)d;
const room = %(room)s;
out.empty = O.model({ room: null, lite: null, nowS: now });
out.recorded = O.model({ room, lite: null, nowS: now });
const today = day(now);
const lv = (room.levels || []).map((x) => [x.name, x.px, x.read === 'absorbed' ? 'a' : x.read === 'not absorbed' ? 'n' : 'u']);
lv[0] && (lv[0][2] = 'a');
const ofp = { p: 1, d: today, t: now - 120, n: 2, o: 1, R: 1.4, lv, lb: [['10:05', 'take', 'won'], ['13:40', 'skip', 'lost']], ln: 'OF paper: 2 trades, +1.4R' };
out.live = O.model({ room, lite: { t: now - 120, price: (room.levels[0] || {}).px - 3, ofp }, nowS: now });
out.stale = O.model({ room, lite: { t: now - 5 * 3600, price: 1, ofp: { ...ofp, t: now - 5 * 3600 } }, nowS: now });
out.yday = O.model({ room, lite: { t: now - 60, ofp: { ...ofp, d: '2020-01-01' } }, nowS: now });
out.kinds = ['YES: x', 'NO: y', 'TOO FEW: 3 of 40 resolved', 'REJECTED', 'PASS (candidate)', '', 'waiting: 3 of 40 tick days'].map(O.verdictKind);
const real = { ...room, verdict: { ...room.verdict, label: 'real', days: 3, absorption: 'TOO FEW: 12 of 40 resolved level signals', of1_lit: 'TOO FEW' } };
out.real = O.model({ room: real, lite: null, nowS: now });
out.scrub = O.model({ room: { ...room, line: 'OF paper: 1 trade, +2.0R (1 micro +$96); Zlarior: flow says SKIP -> won $934' }, lite: null, nowS: now }).line;
const ctl = { ladder: { step: 0, step_name: 'paper forward', status: 'watching', n: 0, need: 30, gates: [{ k: 'mean R', need: '>= +0.20R', v: null }] },
  backtest: { days: 43, per_week: 4.53, win_pct: 51.3, mean_R: 0.51, pf: 2.4, usd_1: 2931, max_dd: 542, half_old: 0.905, half_new: 0.095, later: { trades: 26, usd_1: -561 } },
  oos: { pending: true, when: 'tonight 10:30 PM ET' }, v5: [{ rank: 1, family: 'targets', variant: 'T3R', verdict: 'Weak', watch: true }] };
out.ctl = O.model({ room: { ...room, control: ctl }, lite: null, nowS: now });
const lane = { on: true, account: 'Sim102', cap: 1, used: 1, day: today, trades: [{ t: '10:05', dir: 'long', qty: 2, status: 'closed', pnl: 96.5 },
  { t: '11:40', dir: 'short', status: 'refused', why: 'day cap: 1 entry a day already used' }] };
out.lane = O.model({ room: { ...room, control: ctl }, lite: { t: now - 60, ofl: lane }, nowS: now });
out.laneStale = O.model({ room: { ...room, control: { ...ctl, lane: { ...lane, on: false } } }, lite: { t: now - 6 * 3600, ofl: lane }, nowS: now });
out.why = O.whyWords({ status: 'refused', why: 'day cap: 1 entry a day already used' });
out.realroom = %(realroom)s ? O.model({ room: %(realroom)s, lite: null, nowS: now }) : null;
out.fmt = [O.fmtR(1.25), O.fmtR(-0.5), O.fmtUsd(-48.3), O.fmtPx(25665)];
console.log(JSON.stringify(out));
"""


def part_b(room, now):
    with tempfile.TemporaryDirectory() as td:
        drv = os.path.join(td, "drv.mjs")
        open(drv, "w").write(NODE % {"js": "file://" + os.path.join(NQ, "orderflow.js"), "now": now, "room": json.dumps(room), "realroom": json.dumps(real_room())})
        r = subprocess.run(["node", drv], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        check("b. node ran", False, r.stderr[-400:]); return
    e, rec, lv = o["empty"], o["recorded"], o["live"]
    check("b. empty: honest 'no order-flow day yet', red chip, no stats, verdict 'Not scored yet'", e["state"] == "empty" and e["chip"]["level"] == "bad"
          and "No order-flow day" in e["line"] and not e["stats"] and e["verdict"]["rows"][0]["v"] == "Not scored yet", e)
    check("b. recorded day: its date in the chip, levels sorted high -> low with reads, paper rows, lane B, NO price line",
          rec["state"] == "recorded" and room["day"] in rec["chip"]["text"] and rec["levels"] and all(rec["levels"][i]["px"] >= rec["levels"][i + 1]["px"] for i in range(len(rec["levels"]) - 1))
          and rec["rows"] == room["rows"] and rec["price"] is None, {k: rec[k] for k in ("state", "chip", "price")})
    check("b. today LIVE from ext ofp: green chip, the live reads win, NOW price, stats 2 trades +1.4R, lane B from the PC",
          lv["state"] == "live" and lv["chip"]["level"] == "ok" and lv["levels"][0]["read"] == "absorbed" and lv["price"] is not None
          and lv["stats"][0]["v"] == "2" and lv["stats"][1]["v"] == "+1.4R" and [x["says"] for x in lv["lit"]] == ["take", "skip"], lv)
    check("b. a stale PC post (5 h) or yesterday's ofp is never shown as live", o["stale"]["state"] == "recorded" and o["yday"]["state"] == "recorded")
    check("b. verdict words: YES / NO / TOO FEW / REJECTED / PASS / none / waiting", o["kinds"] == ["yes", "no", "few", "no", "yes", "none", "few"], o["kinds"])
    v = rec["verdict"]
    check("b. a SIMULATED verdict is labelled a test, never shown as the market", "test" in v["chip"] and "SIMULATED" in v["note"], v)
    rv = o["real"]["verdict"]
    check("b. a real TOO FEW verdict stays honest (gold, '12 of 40')", rv["level"] == "warn" and rv["rows"][0]["cls"] == "few" and "12 of 40" in rv["rows"][0]["v"], rv)
    check("b. no $ of a real Zlarior trade in the line (public page): won $934 -> won", "$934" not in o["scrub"] and "+$96" in o["scrub"] and "won" in o["scrub"], o["scrub"])
    check("b. forward ring n / 20 from the room", rec["ring"]["need"] == 20 and rec["ring"]["n"] == room["forward"]["n"])
    rr = o.get("realroom")
    if rr and (rr["verdict"] or {}).get("a"):
        v = rr["verdict"]
        check("b. REAL verdict (51 days): absorption = CANDIDATE (gold, never green), chip 'N real days · candidate', OF1 on Zlarior TOO FEW with its count",
              v["rows"][0]["v"].startswith("CANDIDATE") and v["level"] == "warn" and "real days · candidate" in v["chip"]
              and v["rows"][1]["cls"] == "few" and "of 20 trades" in v["rows"][1]["v"] and v["a"]["taken"]["n"] > 0, v)
    else:
        check("b. (no real verdict in this checkout: skipped)", True)
    c = o["ctl"]
    check("b. control room: ring = ladder 0 of 30 first-of-day trades; backtest + oos pending + v5 carried", c["ring"]["need"] == 30 and c["ring"]["n"] == 0
          and c["ring"]["label"] == "first-of-day trades" and c["backtest"]["pf"] == 2.4 and c["oos"]["pending"] and c["v5"][0]["watch"], c["ring"])
    ln = o["lane"]["lane"]
    check("b. practice lane from the live post 'ofl': ON Sim102, day cap 1 of 1, today's trade + the refused one", ln["src"] == "live" and ln["on"]
          and ln["account"] == "Sim102" and ln["used"] == 1 and ln["cap"] == 1 and ln["today"] and len(ln["trades"]) == 2, ln)
    check("b. a stale live lane (6 h) falls back to the room's copy", o["laneStale"]["lane"]["src"] == "room" and not o["laneStale"]["lane"]["on"], o["laneStale"]["lane"])
    check("b. refused for the day cap reads 'skipped: day cap (1 a day)'", o["why"] == "skipped: day cap (1 a day)", o["why"])
    check("b. formats: +1.3R / −0.5R / −$48 / 25,665.00", o["fmt"] == ["+1.3R", "−0.5R", "−$48", "25,665.00"], o["fmt"])


def ndjson(lite) -> str:
    return json.dumps({"event": "message", "time": lite["t"], "message": json.dumps(lite)}) + "\n"


def part_c(room, now):
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("  (playwright not installed: browser part skipped)"); return
    at = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = dt.datetime.fromtimestamp(now, ET).strftime("%Y-%m-%d")
    live_room = json.loads(json.dumps(room))
    live_room["day"] = today
    lv = [[x["name"], x["px"], {"absorbed": "a", "not absorbed": "n"}.get(x["read"], "u")] for x in live_room["levels"]]
    lite = {"v": 1, "kind": "le-live", "lite": True, "src": "pc_report", "t": now - 140, "reporter": {"t": now - 140}, "price": (live_room["levels"][len(lv) // 2]["px"] + 2.0) if lv else 25000.0,
            "ofp": {"p": 1, "d": today, "t": now - 140, "n": sum(1 for r in room["rows"] if r["taken"]), "o": 0, "R": (room.get("today") or {}).get("R"),
                    "lv": lv, "lb": [[x["t"], x["flow_says"], x["result"]] for x in room["lit"]], "ln": room.get("line") or ""},
            "ofl": {"on": True, "account": "Sim102", "cap": 1, "used": 1, "day": today,
                    "trades": [{"t": "10:05", "dir": "long", "qty": 2, "status": "closed", "pnl": 96.5, "why": "target"},
                               {"t": "11:40", "dir": "short", "status": "refused", "why": "day cap: 1 entry a day already used"}]}}
    shots = "--shots" in sys.argv
    read = """() => ({ state: document.getElementById('app').dataset.state, chip: document.getElementById('src').textContent, rungs: document.querySelectorAll('.rung').length,
        now: !!document.querySelector('.now-line'), reads: [...document.querySelectorAll('.rung-read')].map((e) => e.textContent), tape: document.querySelectorAll('.tape-dot, .tape-take').length, lanes: document.querySelectorAll('.tape-lane').length,
        trades: document.querySelectorAll('.of-trade').length, paper: [...document.querySelectorAll('.of-tag.p')].length, lit: document.querySelectorAll('#lit li').length,
        ring: document.getElementById('ringN').textContent, verdict: document.getElementById('vgrid').textContent, verChip: document.getElementById('verChip').textContent,
        txt: document.getElementById('app').textContent })"""
    rr = real_room()
    runs = [("live-390", 390, 844, live_room, lite)]
    if rr:
        runs += [("real-390", 390, 844, rr, None), ("real-1440", 1440, 900, rr, None)]
    for name, w, h, rm, post in tuple(runs) + (( "recorded-390", 390, 844, room, None), ("empty-390", 390, 844, None, None),
                                 ("live-1440", 1440, 900, live_room, lite), ("recorded-1440", 1440, 900, room, None)):
        srv, origin = AK.serve({"/nq/of_room.json": json.dumps(rm) if rm is not None else None, "/home.json": None})
        try:
            with AK.browser() as br:
                ctx, p, errs, seen, off = AK.page(br, origin, w=w, h=h, mock={"json?poll=1": ndjson(post) if post else ""})
                p.goto(f"{origin}/nq/orderflow.html?at={at}")
                p.wait_for_function("window.NQ_OF && window.NQ_OF.ready()", timeout=60000)
                p.wait_for_timeout(900)
                p.evaluate("document.getAnimations().forEach((a) => { try { a.finish(); } catch (e) {} })")
                o = p.evaluate(read)
                if name.startswith("live"):
                    lt = p.evaluate("() => ({ chip: document.getElementById('laneChip').textContent, rows: [...document.querySelectorAll('#laneTrades li')].map((e) => e.textContent), on: document.getElementById('lane').dataset.on })")
                    check(f"c. {name}: practice lane ON · Sim102, today's trade (+$97 sim) and 'skipped: day cap (1 a day)'", lt["chip"] == "ON · Sim102" and lt["on"] == "1"
                          and len(lt["rows"]) == 2 and "+$97" in lt["rows"][0] and "skipped: day cap" in lt["rows"][1], lt)
                    check(f"c. {name}: LIVE chip, ladder rungs with reads + the gold NOW line, tape dots, lane B rows, verdict (sim = test)",
                          o["state"] == "live" and o["chip"].startswith("LIVE") and o["rungs"] == len(lv) and o["now"] and o["tape"] == len(room["rows"])
                          and o["lit"] == len(room["lit"]) and "test" in o["verChip"] and o["lanes"] == len(lv), o)
                elif name.startswith("real"):
                    ctl = p.evaluate("""() => ({ gate: document.getElementById('gateTxt').textContent, checks: document.querySelectorAll('#gateChecks li').length,
                        tiles: [...document.querySelectorAll('#btTiles .of-tile b')].map((e) => e.textContent), later: document.getElementById('btLater').textContent,
                        oos: document.getElementById('oosBig').textContent, v5: document.querySelectorAll('#v5List li').length, watch: document.querySelectorAll('#v5List li[data-watch="1"]').length,
                        lane: document.getElementById('laneTrades').textContent, ring: document.getElementById('ringOf').textContent })""")
                    check(f"c. {name}: control room: ladder 'of 30 first-of-day', 4 gate rows, backtest tiles (4.5/wk, 51%, +0.5R, 2.40, +$2,931, $542), later trades lose, "
                          "oos 'Tonight 10:30 PM ET', v5 8 rows with 2 WATCH, lane 'no report yet' state",
                          "of 30 first-of-day" in ctl["gate"] and ctl["checks"] == 4 and ctl["tiles"][:6] == ["4.5/wk", "51%", "+0.5R", "2.40", "+$2,931", "$542"]
                          and "lose" in ctl["later"] and ctl["oos"].startswith("Tonight 10:30 PM ET") and ctl["v5"] == 8 and ctl["watch"] == 2
                          and "PC" in ctl["lane"] and ctl["ring"] == "of 30", ctl)
                    cmp = p.evaluate("() => [...document.querySelectorAll('.of-cmp-num')].map((e) => e.textContent)")
                    check(f"c. {name}: the REAL verdict card: CANDIDATE + taken vs skipped bars with R, win % and $ at 1 MNQ",
                          "CANDIDATE" in o["verdict"] and len(cmp) == 2 and "won" in cmp[0] and "1 MNQ" in cmp[0] and "real days" in o["verChip"], (o["verdict"], cmp))
                elif name.startswith("recorded"):
                    check(f"c. {name}: the last recorded day, its paper rows tagged PAPER, no NOW line (no live price)",
                          o["state"] == "recorded" and room["day"] in o["chip"] and o["trades"] == len(room["rows"]) and o["paper"] == sum(1 for r in room["rows"] if r["taken"])
                          and not o["now"], o)
                else:
                    check("c. empty-390: the honest empty state ('no order-flow day yet', verdict not scored yet)",
                          o["state"] == "empty" and "no order-flow day yet" in o["chip"] and "Not scored yet" in o["verdict"], o)
                check(f"c. {name}: taps >= 44 px, no sideways scroll, nothing off the site, no console error",
                      not AK.taps(p) and AK.no_sideways(p) and not off and not errs, (AK.taps(p)[:4], off[:3], errs[:3]))
                if shots:
                    os.makedirs(SHOTS, exist_ok=True)
                    p.screenshot(path=os.path.join(SHOTS, f"after-{name}.png"), full_page=True)
                ctx.close()
        finally:
            srv.shutdown()


def main():
    part_a()
    room = fixture_room()
    now = int(dt.datetime(2026, 11, 26, 11, 20, tzinfo=ET).timestamp())   # in the past: pc_feed drops posts from the future
    part_b(room, now)
    part_c(room, now)
    return AK.finish()


if __name__ == "__main__":
    sys.exit(main())
