"""Real-account views (2026-10-28; engine/live_board.py "real", realcore.js on both dashboards, PAPER vs REAL labels).

  a. live_board.ledger_check: a booked eval day with no real trade is flagged with the room it would leave if it is a
     ledger error (the 2026-10-27 -$965.20 day of refused orders -> "$140 left" was fake); days up to the anchor, days
     with a real trade and $0 days are not; ATLAS: today's booked $ vs its real trades
  b. _orders: compact rows, refused ones keep the reason; real_block keeps live rows only and adds the H2 cone
  c. build(): the board carries "real" and lit/atlas carry days / orders / eval_start (never raises without inputs)
  d. the real heartbeat (origin/heartbeat, when fetched): the 10-27 day is flagged, room_if_error > room
  e. static: realcore.js byte-identical on both apps, read-only (no fetch / POST); PC page #real wired (routes, app.js,
     index.html, cc.js slots), phone real.js after board.js, caches bumped, tradepics / boardcore label PAPER + REAL
  f. node render: RealUI.today / safety / results / realOf / csv on a synthetic board; BoardUI paper row shows REAL

    python -X utf8 -m tests.test_real_ui
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import live_board as LB  # noqa: E402

N = {"pass": 0, "fail": 0}


def check(name, cond, info=None):
    N["pass" if cond else "fail"] += 1
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or info is None else f"  -> {info}"))


def rd(*p):
    return open(os.path.join(ROOT, *p), encoding="utf-8").read()


NOW = 1793202477          # 2026-10-28 11:47 ET
LIT = {"id": "lit", "room": 140.4, "mll": 2000.0, "anchor": {"as_of": "2026-10-23"}, "eval_start": "2026-10-19",
       "days": [["0000-00-00", -100.0], ["2026-10-22", -50.0], ["2026-10-27", -965.2], ["2026-10-28", -437.0], ["2026-10-29", 0.0]]}
ROWS = [{"acct": "lit", "src": "live", "day": "2026-10-28", "entry_t": 1793173380, "side": "SHORT", "qty": 5, "usd": -437.0},
        {"acct": "atlas", "src": "live", "day": "2026-10-28", "entry_t": 1793181600, "side": "LONG", "qty": 4, "usd": -249.6, "member": "EMA"},
        {"acct": "atlas", "src": "paper", "day": "2026-10-27", "entry_t": 1793086200, "side": "LONG", "qty": 7, "usd": 3878.7, "member": "MACD"}]


def part_a():
    c = LB.ledger_check(LIT, {"today_pnl": -249.6}, [r for r in ROWS if r["src"] == "live"], NOW)
    check("a. the 10-27 -$965.20 day with no real trade is flagged, only it", [x["day"] for x in c] == ["2026-10-27"], c)
    check("a. room if it is a ledger error: 140.40 + 965.20 = 1,105.60 (capped at the $2,000 max loss)",
          c and c[0]["room_if_error"] == 1105.6 and "ledger error" in c[0]["text"] and "MFFU" in c[0]["text"], c)
    c2 = LB.ledger_check({**LIT, "days": [["2026-10-27", -1900.0]], "room": 1000.0}, {}, [], NOW)
    check("a. the room after a doubted day never goes above the max loss", c2 and c2[0]["room_if_error"] == 2000.0, c2)
    c3 = LB.ledger_check(LIT, {}, ROWS + [{"acct": "lit", "src": "live", "day": "2026-10-27", "usd": -965.2}], NOW)
    check("a. a day with a real trade is not flagged", not [x for x in c3 if x["acct"] == "lit"], c3)
    c4 = LB.ledger_check(LIT, {"today_pnl": -500.0}, [r for r in ROWS if r["src"] == "live"], NOW)
    check("a. ATLAS: booked today -$500 vs real trades -$249.60 -> flagged", any(x["acct"] == "atlas" for x in c4), c4)
    check("a. ATLAS: booked = real -> no ATLAS flag", not any(x["acct"] == "atlas" for x in LB.ledger_check(LIT, {"today_pnl": -249.6}, ROWS, NOW)))
    check("a. empty inputs -> []", LB.ledger_check({}, {}, [], NOW) == [])


def part_b():
    o = LB._orders([{"t": 1, "side": "sell", "qty": 5, "entry_t": 9, "ok": False, "error": "account does not exist"},
                    {"t": 2, "side": "exit", "qty": 5, "entry_t": 9, "ok": True, "pnl": -437.0, "reason": "STOP"}, {"x": 1}])
    check("b. _orders: refused row keeps the reason, exit keeps $ + reason, junk dropped",
          len(o) == 2 and o[0]["ok"] is False and "does not exist" in o[0]["error"] and o[1]["pnl"] == -437.0 and o[1]["reason"] == "STOP", o)
    band = {"bands": {"H2": {"from": "2026-07-01", "to": "2026-10-16", "usd_eval": [[float(i) for i in range(1, 100)] for _ in range(60)]}}}
    rb = LB.real_block(LIT, {}, ROWS, band, NOW)
    check("b. real_block: live rows only", [r["src"] for r in rb["trades"]] == ["live", "live"], rb["trades"])
    check("b. real_block: the H2 cone (session, p5, p25, p50, p75, p95) from 0 to >= 15 sessions",
          rb.get("cone", {}).get("cols") == ["session", "p5", "p25", "p50", "p75", "p95"] and rb["cone"]["rows"][0] == [0, 0, 0, 0, 0, 0]
          and len(rb["cone"]["rows"]) >= 16 and "H2" in rb["cone"]["src"], rb.get("cone", {}).get("cols"))


def part_c():
    b = LB.build({}, NOW)
    check("c. build() without inputs never raises and has a 'real' block", isinstance(b.get("real"), dict) and "trades" in b["real"], b.get("real"))
    hb = {"t": NOW, "present": True, "second": {"route": {"account_b": {"eval": {"start": "2026-10-26", "balance": 24750.4, "today": -249.6},
                                                                         "routed": [{"t": NOW - 99, "side": "buy", "qty": 4, "entry_t": NOW - 100, "ok": True}]}}}}
    b2 = LB.build({"pc": hb}, NOW)
    check("c. atlas carries eval_start + orders; lit carries days / orders keys",
          b2["atlas"].get("eval_start") == "2026-10-26" and b2["atlas"].get("orders") and "days" in b2["lit"] and "orders" in b2["lit"], (b2["atlas"].get("orders"), list(b2["lit"])))


def part_g():
    prog = {"atlas": {"week": {"n": 3, "lo": 3, "hi": 4, "status": "met", "usd": 2947.5,
                               "days": [{"day": "2026-10-27", "n": 1, "usd": 3878.7}, {"day": "2026-10-28", "n": 1, "usd": -499.2}]}}}
    done = LB.real_week(prog, ROWS, {}, {"eval_start": "2026-10-26", "badge": "LIVE"})
    w = prog["atlas"]["week"]
    check("g. the ATLAS week strip counts REAL trades: the paper +$3,878.70 (7 micros) day becomes 0 / $0, today -$249.60",
          done == {"atlas": 1} and w["days"][0] == {"day": "2026-10-27", "n": 0, "usd": 0.0} and w["days"][1]["usd"] == -249.6
          and w["n"] == 1 and w["status"] == "on_pace" and w["src"] == "real", w)
    p2 = {"atlas": {"week": {"n": 2, "days": [{"day": "2026-10-27", "n": 2, "usd": 10.0}]}}}
    check("g. an account without a real start keeps its week as it was", LB.real_week(p2, ROWS, {}, {}) == {} and p2["atlas"]["week"]["n"] == 2)


def part_d():
    r = subprocess.run(["git", "show", "origin/heartbeat:heartbeat.json"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        check("d. real heartbeat (skipped: git fetch origin heartbeat)", True)
        return None
    hb = json.loads(r.stdout)
    t0 = time.time()
    b = LB.from_heartbeat(hb, now=int(hb.get("t") or time.time()))
    check(f"d. from_heartbeat builds 'real' in {time.time() - t0:.1f} s", isinstance(b.get("real"), dict) and not b["real"].get("error"), b.get("real"))
    ch = b["real"].get("checks") or []
    lit = b.get("lit") or {}
    if any(d == "2026-10-27" for d, _ in lit.get("days") or []) and not any(r.get("day") == "2026-10-27" for r in b["real"]["trades"] if r.get("acct") == "lit"):
        check("d. the heartbeat's 2026-10-27 day is flagged; room if error > room", any(c["day"] == "2026-10-27" and c["room_if_error"] > (lit.get("room") or 0) for c in ch), ch)
    else:
        check("d. heartbeat without the doubted day: no lit check", not [c for c in ch if c["acct"] == "lit" and c["day"] == "2026-10-27"], ch)
    check("d. every real trade is a live row", all(r.get("src") == "live" for r in b["real"]["trades"]))
    return b


def part_e():
    a, p = rd("tools", "web_public", "realcore.js"), rd("web_next", "js", "next", "realcore.js")
    check("e. realcore.js byte-identical on both apps", a == p)
    check("e. realcore.js read-only: no fetch / XHR / POST", "fetch(" not in a and "XMLHttpRequest" not in a and "POST" not in a)
    check("e. boardcore.js + tradepics.js still byte-identical", rd("tools", "web_public", "boardcore.js") == rd("web_next", "js", "next", "boardcore.js")
          and rd("tools", "web_public", "tradepics.js") == rd("web_next", "js", "next", "tradepics.js"))
    routes, app, idx, cc, real = rd("web_next", "js", "next", "routes.js"), rd("web_next", "js", "app.js"), rd("web_next", "index.html"), rd("web_next", "js", "next", "cc.js"), rd("web_next", "js", "next", "real.js")
    check("e. PC: 'real' in the Main group + the tab bar, page module, page section",
          "'atlas', 'real', 'modules'" in routes and "'data', 'scale', 'lab', 'intel'" in routes and "TABS = ['cc', 'zlarior', 'atlas', 'real', 'modules']" in routes and "real: realPage" in app and 'id="page-real"' in idx)
    check("e. PC Home: the Today + Safety slots and fillRealHome after each render; old eval cards folded",
          'id="ccReal"' in cc and 'id="ccSafe"' in cc and "fillRealHome().catch" in cc and "cc-evals" in cc and "realcore.js?v=" in real)
    check("e. PC real.js only GETs (through board.js)", "method: 'POST'" not in real and "fetch(" not in real)
    pidx, psw, sw = rd("tools", "web_public", "index.html"), rd("tools", "web_public", "sw.js"), rd("web_next", "sw.js")
    check("e. phone: real.js loads after board.js; boardcore v2 / tradepics v2", 'src="real.js?v=' in pidx and pidx.index("board.js?v=") < pidx.index("real.js?v=")
          and "boardcore.js?v=2" in rd("tools", "web_public", "board.js") and "tradepics.js?v=2" in pidx)
    check("e. caches bumped: phone le-public-v40+, PC le-shell-next-v23+",
          int(re.search(r"le-public-v(\d+)", psw).group(1)) >= 40 and int(re.search(r"le-shell-next-v(\d+)", sw).group(1)) >= 23)
    tp, bc = rd("web_next", "js", "next", "tradepics.js"), rd("web_next", "js", "next", "boardcore.js")
    check("e. pictures say PAPER + the REAL twin; the trade log paper rows show REAL", "PAPER ${" in tp and "realOf" in tp and "REAL: no order on the account" in bc and "bd-real" in bc)
    check("e. FEATURES.md registry lists 50 features", os.path.exists(os.path.join(ROOT, "web_next", "FEATURES.md"))
          and len(re.findall(r"^\| *\d+ *\|", rd("web_next", "FEATURES.md"), re.M)) >= 50)


def part_f(b):
    node = shutil.which("node")
    if not node:
        check("f. node render (skipped: no node)", True)
        return
    for pth in ("tools/web_public/realcore.js", "tools/web_public/real.js", "tools/web_public/tradepics.js", "tools/web_public/boardcore.js"):
        r = subprocess.run([node, "--check", os.path.join(ROOT, pth)], capture_output=True, text=True)
        check(f"f. node --check {pth}", r.returncode == 0, r.stderr[-300:])
    for pth in ("web_next/js/next/real.js", "web_next/js/next/cc.js", "web_next/js/next/board.js", "web_next/js/next/routes.js"):
        r = subprocess.run([node, "--input-type=module", "--check"], input=rd(*pth.split("/")), capture_output=True, text=True)
        check(f"f. node --check {pth}", r.returncode == 0, r.stderr[-300:])
    td = "2026-10-28"
    B = {"t": NOW, "data_t": NOW, "today": td, "running": True, "blocks": [{"text": "Eval near the floor: $140 left", "fix": "x", "scope": "both", "kind": "other"}],
         "health": {"items": [{"key": "nt", "label": "NinjaTrader", "value": "connected", "ok": True}]},
         "lit": {"id": "lit", "name": "Zlarior", "badge": "LIVE", "broker": "MFFU-50K", "balance": 48308.6, "floor": 48168.2, "room": 140.4, "room_frac": 0.07, "mll": 2000,
                 "to_target": 4691.4, "target_balance": 53000, "profit": -1691.4, "today_pnl": -437.0, "dll": 1000, "dll_used": 437, "session": 8, "sessions": 10,
                 "max_day": 1, "done_today": True, "window": {"open": True, "open_t": NOW - 3600, "close_t": NOW + 3600, "hours": "02:00-15:30 ET"},
                 "eval_start": "2026-10-19", "days": [["2026-10-27", -965.2], ["2026-10-28", -437.0]],
                 "orders": [{"t": NOW - 8000, "side": "sell", "qty": 5, "entry_t": 1793173380, "ok": False, "error": "fill not reported yet"},
                            {"t": NOW - 7000, "side": "exit", "qty": 5, "entry_t": 1793173380, "ok": True, "pnl": -437.0, "reason": "STOP"}], "blocks": []},
         "atlas": {"id": "atlas", "name": "ATLAS", "badge": "LIVE", "configured": True, "balance": 24750.4, "floor": 24000, "room": 750.4, "room_frac": 0.75, "mll": 1000,
                   "to_target": 1749.6, "target_balance": 26500, "profit": -249.6, "today_pnl": -249.6, "dll": 600, "session": 3, "max_day": 2, "eval_start": "2026-10-26",
                   "position": {"side": "LONG", "qty": 2, "entry": 100.0, "stop": 90.0, "target": 150.0, "unrealized_usd": 20.0},
                   "orders": [{"t": NOW - 5000, "side": "buy", "qty": 4, "entry_t": 1793181600, "ok": False, "error": "account does not exist"}], "blocks": []},
         "progress": {"lit": {"expected": {"per_session": 118.9, "per_month": 2497, "trades_per_week": 2.56}, "actual": {"per_month_pace": -4440, "sessions": 8},
                              "odds": {"rows": {"H2": {"p10": 58.6, "f10": 20.9, "pass_med": 5}}}},
                      "atlas": {"expected": {"per_month": 1194, "trades_per_week": 1.6}, "actual": {"per_month_pace": -1747, "sessions": 3}}},
         "trades": ROWS,
         "real": {"trades": [r for r in ROWS if r["src"] == "live"],
                  "checks": [{"acct": "lit", "day": "2026-10-27", "usd": -965.2, "room_if_error": 1105.6, "text": "Zlarior's eval books -$965 on 2026-10-27 but no real trade"}],
                  "cone": {"rows": [[i, -100.0 * i, -20.0 * i, 50.0 * i, 120.0 * i, 300.0 * i] for i in range(16)]}}}
    tmp = tempfile.mkdtemp(prefix="le_real_ui_")
    bp = os.path.join(tmp, "b.json")
    json.dump(B, open(bp, "w"))
    js = r"""
global.window = global; global.setInterval = () => 0; global.scrollTo = () => 0;
global.document = { getElementById: () => ({}), querySelectorAll: () => [], head: { appendChild() {} }, createElement: () => ({}), addEventListener() {} };
require(process.argv[4]); require(process.argv[1]); require(process.argv[3]);
const B = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const t = window.RealUI.today(B, {}), s = window.RealUI.safety(B, { where: 'pc' }), r = window.RealUI.results(B, {});
const paper = B.trades[2], tw = window.RealUI.realOf(paper, B), tw2 = window.RealUI.realOf({ ...paper, entry_t: 1793181700, day: '2026-10-28' }, B);
const c = window.RealUI.csv(window.RealUI.realRows(B));
const bp = window.BoardUI.page({ ...B, trades: [B.trades[2]] }, {});
const t0 = window.RealUI.today({ ...B, real: { trades: [], checks: [] }, atlas: { ...B.atlas, position: null } }, {});
const pic = window.TradePics.title({ key: 'macd_sweep', src: 'paper', qty: 7, usd: 3878.7, r: 7.97, exit_kind: 'TARGET', side: 'LONG', entry_t: 1793086200 });
console.log(JSON.stringify({
  cards: (t.match(/rc-acct /g) || []).length, slot: t.includes('Strategy 3 (research)'), realToday: t.includes('−$437.00'), atlasNow: t.includes('to target'),
  why: t0.includes('No trade yet today') && t.includes('class="rc-tr"'), check: t.includes('Ledger check') && t.includes('$1,106'), eta: t.includes('pass ≈ day'),
  score: t.includes('rc-score'), conflict: t.includes('LIT vs ATLAS'), events: t.includes('What happened today') && t.includes('REFUSED'),
  safe: s.includes('Kill switch') && s.includes('orders'), kpis: r.includes('Win rate') && r.includes('Real net'), cone: r.includes('rc-b1'), log: r.includes('rc-lrh'),
  week: r.includes('This week'), strat: r.includes('ATLAS · EMA'), inc: r.includes('REFUSED'), paperOut: !r.includes('3,879'),
  tw: tw.text, tw2: tw2.text, csvh: c.split('\n')[0], csvn: c.split('\n').length,
  boardReal: bp.includes('REAL: no order on the account') || bp.includes('REAL: 4 micros'), boardDoubt: bp.includes('Ledger check'), pic,
  err: window.RealUI.today({ error: 'boom' }, {}).includes('boom') }));
"""
    r = subprocess.run([node, "-e", js, os.path.join(ROOT, "tools", "web_public", "realcore.js"), bp,
                        os.path.join(ROOT, "tools", "web_public", "boardcore.js"), os.path.join(ROOT, "tools", "web_public", "tradepics.js")], capture_output=True, text=True)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {"stderr": r.stderr[-600:]}
    check("f. Today: two real account cards + the Strategy 3 slot, today's real $, ledger-check banner with the room if error",
          o.get("cards") == 2 and o.get("slot") and o.get("realToday") and o.get("check"), o)
    check("f. Today: why no trade, pass ETA, health score, LIT vs ATLAS line, what happened today (REFUSED order)",
          all(o.get(k) for k in ("why", "eta", "score", "conflict", "events")), o)
    check("f. Safety card: kill switch link (PC) + orders confirmed", o.get("safe"), o)
    check("f. Results: KPIs, backtest cone, trade log, week card, $ by strategy, incidents; the paper +$3,879 never appears",
          all(o.get(k) for k in ("kpis", "cone", "log", "week", "strat", "inc", "paperOut")), o)
    check("f. realOf: the paper MACD 10-27 trade -> no order; a paper twin near the real EMA fill -> REAL 4 micros -$250",
          o.get("tw") == "REAL: no order on the account" and o.get("tw2") == "REAL: 4 micros, −$250", (o.get("tw"), o.get("tw2")))
    check("f. CSV: header with running_usd, one row per real trade", o.get("csvh", "").endswith("usd,running_usd") and o.get("csvn") == 3, (o.get("csvh"), o.get("csvn")))
    check("f. BoardUI: paper rows show their REAL twin, the floor alert carries the ledger doubt", o.get("boardReal") and o.get("boardDoubt"), o)
    check("f. TradePics title: 'PAPER 7 micros +$3,879'", "PAPER 7 micros +$3,879" in (o.get("pic") or ""), o.get("pic"))
    check("f. error box", o.get("err"), o)
    shutil.rmtree(tmp, ignore_errors=True)


def main():
    part_a()
    part_b()
    part_c()
    part_g()
    b = part_d()
    part_e()
    part_f(b)
    tot = N["pass"] + N["fail"]
    print(f"real ui: {N['pass']}/{tot} {'ALL PASS' if not N['fail'] else 'FAIL'}")
    return 1 if N["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
