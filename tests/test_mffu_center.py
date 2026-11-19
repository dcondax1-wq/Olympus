"""The MFFU account center (tools/web_public/business/mffu.html + mffucenter.js + mffu.js, night-mffu2 2026-11-18, owner: "everything
on the accounts to the point where I barely even have to open MFFU on Safari. I need notifications when trades are taken, on which
account"). A fixture PC feed (core + ext posts, the shapes tools/pc_report.py posts) on a busy Thursday morning, Nov 19 10:12 ET.

  a. static: the page's scripts in order, textContent only, no outside address, GET only, no storage; the owner's names
  b. node: ownerName = engine/mffu_view.owner_name (the same table); MFFU's numbers = research/lit/mffu_rules.json; the CME holiday
     hours = engine/cme_calendar.py; the Tier-1 news = mffu_rules.json
  c. node, center(): 3 cards (Zlarior 50K, ATLAS 25K funded, Zlarior 25K #2), chips, MFFU's $0-based funded balance, the open trades
     with live $, today's trades with $, every rule's state (OK / close / broken / not yet), the payout checklist, "as of" times;
     then the bad days: daily loss close, max loss close, a hedge across accounts, a trade after 4:10 PM, 7 idle days, PC silent
     (every number "from then"), no PC feed (SNAPSHOT, never live), nothing (plan only)
  d. Chromium 390 x 844 at scale 2 (run under flock -w 2400 /tmp/olympus_browser.lock; --static skips it): the page fed the fixture
     through the mocked ntfy poll: the Right-now card, 3 cards with names / chips / open trades / rules / trades, taps >= 44 px, no
     sideways scroll, nothing fetched off the site, no console error; --shots saves the phone shots to research/handoff/2026-11-18/mffu2/

    python -X utf8 -m tests.test_mffu_center [--static] [--shots]
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402
from tests.test_mffu_view import NAME_CASES  # noqa: E402

check = AK.check
WEB = os.path.join(ROOT, "tools", "web_public")
BIZ = os.path.join(WEB, "business")
SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-18", "mffu2")
ET = ZoneInfo("America/New_York")


def et(y, mo, d, h, mi, s=0) -> int:
    return int(dt.datetime(y, mo, d, h, mi, s, tzinfo=ET).timestamp())


NOW = et(2026, 11, 19, 10, 12)                 # the page's clock (?at=): Thursday 10:12 AM ET
T = et(2026, 11, 19, 10, 10)                   # the bot's heartbeat in the core post
ENTRY = et(2026, 11, 19, 9, 42)                # LIT's long on both Zlarior accounts
A_IN, A_OUT = et(2026, 11, 19, 3, 5), et(2026, 11, 19, 4, 20)   # ATLAS's EMA short this morning


def fixture():
    """(core, [ext]) as tools/pc_report.py posts them: Zlarior 50K + 25K #2 long 6 / 3 micros from 9:42, ATLAS funded +$186 today."""
    lit = {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "method": "LIT", "badge": "LIVE", "source": "PC bot", "balance": 49192.78,
           "floor": 48168.2, "room": 1024.58, "mll": 2000.0, "to_target": 3807.22, "target_balance": 53000.0, "profit": -807.22, "today_pnl": 0.0,
           "week_pnl": -129.4, "status": "open", "session": 25, "dll": 1000.0, "dll_used": 0.0, "trades_today": 1, "max_day": 1,
           "position": {"side": "LONG", "qty": 6, "entry": 27390.0, "stop": 27370.0, "target": 27480.0, "be": False, "entry_t": ENTRY, "unrealized_r": 0.6}}
    atlas = {"id": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K funded", "method": "EMA · MACD · S/R", "badge": "LIVE", "source": "PC bot (account B)",
             "balance": 25073.2, "floor": 24000.0, "room": 1073.2, "mll": 1000.0, "profit": 73.2, "today_pnl": 186.0, "status": "funded", "session": 4,
             "dll": 600.0, "trades_today": 1, "max_day": 2}
    ev = lambda b, f, r, today, s: {"start_balance": s, "balance": b, "profit": round(b - s, 2), "to_target": round(s + (3000 if s == 50000 else 1500) - b, 2),
                                    "target_balance": s + (3000 if s == 50000 else 1500), "floor": f, "room": r, "mll": 2000.0 if s == 50000 else 1000.0,
                                    "dll": 1000.0 if s == 50000 else 600.0, "dll_used": 0.0, "today": today, "session": 25 if s == 50000 else 3, "status": "open"}
    core = {"v": 1, "kind": "le-live", "lite": True, "src": "pc_report", "t": T, "every_s": 300, "price": 27402.0, "day_pnl": 0.0,
            "model_state": "LIT: in a long from 9:42", "pc_verdict": {"code": "TRADING", "label": "TRADING YOUR EVAL", "level": "good", "t": T},
            "pc": {"running": True, "adapter": "ninjatrader", "position": True, "present": True, "t": T, "age_s": 0, "silent": False},
            "reporter": {"t": T + 40, "server": True, "nt": True, "market_open": True, "mode": "LIVE", "problems": []},
            "board": {"v": 1, "kind": "le-board", "t": T, "data_t": T, "where": "live", "today": "2026-11-19", "running": True, "level": "good",
                      "lit": lit, "atlas": atlas, "lines": []},
            "accounts": [{"id": "mffu50k_eval", "name": "MFFU 50K Eval", "plan": "Builder 50K", "kind": "eval", "source": "pc", "badge": "LIVE",
                          "conn": {"present": True, "t": T, "running": True, "connected": True}, "eval": ev(49192.78, 48168.2, 1024.58, 0.0, 50000.0),
                          "pnl": {"today": 0.0}, "running": True, "trades": [], "days": []},
                         {"id": "b25k_2", "name": "Zlarior Builder 25K #2", "plan": "Builder 25K", "kind": "eval", "source": "pc", "badge": "LIVE",
                          "conn": {"present": True, "t": T, "running": True, "connected": True}, "eval": ev(25000.0, 24000.0, 1000.0, 0.0, 25000.0),
                          "pnl": {"today": 0.0}, "running": True, "trades": [], "days": []}]}
    mf = {"t": T, "a": [
        {"id": "mffu50k_eval", "nm": "Zlarior 50K", "sd": "2026-10-19", "l4": "6016", "td": 1, "lt": "2026-11-16", "bd": ["2026-11-16", -129], "wd": ["2026-11-16", -129],
         "eq": [-678, -807], "n": 1, "al": -129, "bt": -129, "wt": -129, "ct": 1},
        {"id": "b25k_2", "nm": "Zlarior 25K #2", "sd": "2026-11-18", "l4": "6019"},
        {"id": "atlas", "nm": "ATLAS 25K funded", "sd": "2026-11-17", "l4": "6018", "td": 2, "lt": "2026-11-19", "bd": ["2026-11-19", 186], "wd": ["2026-11-18", -113],
         "eq": [0, -113, 73], "n": 2, "w": 1, "pf": 1.65, "aw": 186, "al": -113, "bt": 186, "wt": -113, "ct": 4,
         "f": {"cp": 73, "bd": 186, "cd": 2, "ef": "2026-11-20", "pn": 0, "mr": 0, "st": "consistency"}}]}
    at = {"t": T, "a": [
        {"id": "mffu50k_eval", "l4": "6016", "tr": [[et(2026, 11, 16, 9, 56), et(2026, 11, 16, 10, 40), 1, 1, 27799.5, 27735.25, 28174.0, "STOP", -129.4, -1.01],
                                                     [ENTRY, None, 1, 6, 27390.0, 27370.0, 27480.0, None, None, None]]},
        {"id": "b25k_2", "l4": "6019", "tr": [[ENTRY, None, 1, 3, 27390.25, 27370.0, 27480.0, None, None, None]]},
        {"id": "atlas", "l4": "6018", "tr": [[et(2026, 11, 18, 9, 30), et(2026, 11, 18, 9, 50), -1, 2, 27395.5, 27422.5, 27179.5, "STOP", -112.8, -1.04],
                                             [A_IN, A_OUT, -1, 2, 27420.0, 27446.0, 27373.5, "TARGET", 186.0, 1.79]]}]}
    life = {"acc": {"atlas": {"label": "ATLAS 25K", "stage": "funded", "since": T - 86400, "bal": 25073.2},
                    "lit": {"label": "Zlarior 50K", "stage": "eval", "since": T - 86400, "bal": 49192.78},
                    "x:b25k_2": {"label": "Zlarior Builder 25K #2", "stage": "eval", "since": T - 86400, "bal": 25000.0}}, "ev": []}
    ext = {"v": 1, "kind": "le-live-ext", "src": "pc_report", "t": T, "rt": T + 38, "part": 0, "of": 1, "x": {"life": life, "mf": mf, "at": at}}
    return core, [ext]


def ndjson(core, exts) -> str:
    lines = [{"event": "message", "time": e["rt"], "message": json.dumps(e)} for e in exts]
    lines.append({"event": "message", "time": core["reporter"]["t"], "message": json.dumps(core)})
    return "\n".join(json.dumps(x) for x in lines) + "\n"


def part_a():
    h, js, cj = (AK.read(os.path.join(BIZ, f)) for f in ("mffu.html", "mffu.js", "mffucenter.js"))
    order = re.findall(r'<script src="([^"?]+)', h)
    want = ["../olympus/themes.js", "../olympus/a11y.js", "../pc_feed.js", "payoutcoach.js", "mffumodel.js", "mffucenter.js", "../edge_chip.js", "mffu.js"]
    check("a. mffu.html: AGORA look, one h1, a polite status line, back to Business, the scripts in order (feed, coach, model, center, edge chip, page)",
          'data-theme="agora"' in h and "viewport-fit=cover" in h and h.count("<h1") == 1 and 'aria-live="polite"' in h and 'href="./"' in h and order == want, order)
    bad = r"\.innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|new Function|https?://|method:|XMLHttpRequest|WebSocket|sendBeacon|document\.cookie|localStorage|sessionStorage"
    check("a. mffu.js / mffucenter.js: textContent only, no markup from data, no outside address, GET only, no storage; the center has no fetch at all",
          not re.search(bad, js + cj) and "textContent" in js and "fetch(" not in cj, re.findall(bad, js + cj)[:4])
    check("a. the owner's names, never the broker id: Zlarior 50K / Zlarior 25K #2 / ATLAS 25K funded come from the PC's nm or ownerName",
          "mf.nm" in cj and "ownerName(" in cj and not re.search(r"MFFU(EV|SF)", js + cj + h))


def node(script: str) -> dict:
    p = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=90)
    m = [ln for ln in p.stdout.splitlines() if ln.startswith("@@")]
    return json.loads(m[-1][2:]) if m else {"error": (p.stderr or p.stdout)[-800:]}


def part_b():
    from engine import cme_calendar as CC
    rules = json.loads(AK.read(os.path.join(ROOT, "research", "lit", "mffu_rules.json")))
    r = node(f"""
      const X = require({json.dumps(os.path.join(BIZ, "mffucenter.js"))});
      const cases = {json.dumps(NAME_CASES)};
      console.log('@@' + JSON.stringify({{ names: cases.map((c) => [X.ownerName(...c[0]), c[1]]), rules: X.RULES, cme: X.CME, t1: X.T1, flat: X.FLAT,
        junk: [X.ownerName(), X.ownerName(null, 5, [1], {{}}), X.ownerName('x', 'MFFUEVBLDR000006016', '', 'eval')],
        td: [X.tradingDay({et(2026, 11, 18, 17, 59)}), X.tradingDay({et(2026, 11, 18, 18, 0)})], asof: X.asOf({T}, {NOW}), asof2: X.asOf({T - 86400 * 2}, {NOW}),
        asof3: X.asOf({et(2026, 11, 7, 16, 10)}, {NOW}), end: [X.dayEnd({NOW}).text, X.dayEnd({et(2026, 11, 19, 16, 30)}).text, X.dayEnd({et(2026, 11, 21, 12, 0)}).text,
        X.dayEnd({et(2026, 11, 19, 19, 0)}).text] }}));""")
    bad = [x for x in r.get("names") or [] if x[0] != x[1]]
    check(f"b. ownerName (page) = engine/mffu_view.owner_name (PC) on all {len(NAME_CASES)} cases; junk is a plain word, never an id",
          r.get("names") and not bad and r.get("junk", [None])[0] == "Zlarior" and all(isinstance(x, str) and "6016" not in x for x in r.get("junk") or [1]), bad or r.get("error"))
    R, L = r.get("rules") or {}, rules["limits"]
    b5, b2 = R.get("builder50k") or {}, R.get("builder25k") or {}
    keys = {"target": "target", "mll": "mll", "lock": "lock", "dll": "dll", "max_micros": "max_micros", "max_minis": "max_minis", "buffer": "buffer", "pay_min": "pay_min",
            "pay_max": "pay_max", "split": "split", "cons": "cons", "cycle_days": "cycle_days", "max_payouts": "max_payouts", "inactivity_days": "inactivity_days"}
    diff = [(n, k, P.get(k), L[lk].get(v)) for n, P, lk in (("50K", b5, "builder_50k"), ("25K", b2, "builder_25k")) for k, v in keys.items() if P.get(k) != L[lk].get(v)]
    check("b. Builder 50K / 25K numbers = research/lit/mffu_rules.json limits (target, max loss, lock, daily loss, contracts, buffer, payout min / max, split, 50%, 2 days, 5 payouts, 7 days)",
          not diff and b5.get("first_above") == 500 and b2.get("first_above") == 250 and b5.get("min_days") == 1 and b5.get("eval_cons") is None, diff)
    re5, rr = R.get("rapideod50k") or {}, rules["rapid_eod_50k"]
    ev5, sf5 = rr["eval"].get("value", rr["eval"]), rr["sim_funded"].get("value", rr["sim_funded"])
    check("b. Rapid EOD 50K = mffu_rules.json (target, max loss, 30% best day, 4 days, 3 minis / 30 micros, no daily loss, funded: buffer, $500 minimum, 90%, news banned)",
          re5.get("target") == ev5["target"] and re5.get("mll") == ev5["mll"] and re5.get("eval_cons") == ev5["consistency"] and re5.get("min_days") == ev5["min_days"]
          and re5.get("max_micros") == ev5["max_contracts"]["micros"] and re5.get("dll") is None and re5.get("buffer") == sf5["buffer"] and re5.get("pay_min") == sf5["payout_min"]
          and re5.get("split") == sf5["split"] and re5.get("news_funded") is False and (R.get("rapideod25k") or {}).get("target") == 1500, re5)
    check("b. flat at 4:10 PM ET and the 6 PM open = mffu_rules.json limits (flat_by_mod 970, open_mod 1080); the bot is flat 3:55 PM",
          (r.get("flat") or {}).get("mffu") == L["builder_50k"]["flat_by_mod"] == 970 and r["flat"].get("open") == L["builder_50k"]["open_mod"] and r["flat"].get("bot") == 955)
    cme = r.get("cme") or []
    off = [(h["day"], h.get("halt"), CC.early_close(h["day"]), bool(h.get("closed")), CC.full_closure(h["day"])) for h in cme
           if (h.get("halt") != CC.early_close(h["day"])) or (bool(h.get("closed")) != CC.full_closure(h["day"]))]
    check(f"b. the {len(cme)} holiday days = engine/cme_calendar.py (Thanksgiving 1:00 PM, Nov 27 + Christmas Eve 1:15 PM, Christmas + New Year closed, MLK, Presidents)",
          len(cme) >= 7 and not off, off)
    t1 = rules["tier1_news_2026"]["value"]["rest_of_2026"]
    mine = [f"{d} {t}" for d, t, _ in r.get("t1") or []]
    check("b. the Tier-1 news days = mffu_rules.json tier1_news_2026 (FOMC minutes / jobs / FOMC / CPI)", mine == [x[:16] for x in t1], (mine, t1))
    check("b. ET helpers: 6 PM starts the next trading day; 'as of 10:10 AM ET' today, 'Tue 10:10 AM ET' this week, 'Nov 7, 4:10 PM ET' older",
          r.get("td") == ["2026-11-18", "2026-11-19"] and r.get("asof") == "as of 10:10 AM ET" and r.get("asof2") == "as of Tue 10:10 AM ET"
          and r.get("asof3") == "as of Nov 7, 4:10 PM ET", (r.get("td"), r.get("asof"), r.get("asof2"), r.get("asof3")))
    e = r.get("end") or ["", "", "", ""]
    check("b. MFFU's day: 'ends at 4:10 PM ET (in 5 h 58 min)', closed after 4:10, the weekend, after 6 PM = tomorrow's 4:10 PM",
          "in 5 h 58 min" in e[0] and "closed" in e[1] and "Weekend" in e[2] and "in 21 h 10 min" in e[3], e)


CENTER = """
  const F = require(%(feed)s), M = require(%(mm)s), C = require(%(coach)s), X = require(%(center)s);
  const plan = require(%(plan)s);
  const fx = %(fx)s, NOW = %(now)s;
  const lite0 = F.merge(fx.core, fx.exts);
  const run = (lite, now, extra) => X.center(Object.assign({ lite, plan, coach: C, M, today: X.etDate(now || NOW) }, extra || {}), now || NOW);
  const pick = (r) => ({ feed: r.feed, decoder: r.decoder, open: r.open.map((o) => [o.name, o.side, o.qty, o.pnl_usd, o.risk_usd, o.reward_usd]),
    latest: r.latest.map((x) => [x.name, x.side, x.usd, x.open]), planned: r.planned.map((p) => [p.key, p.rules.slice(0, 30)]), day: r.day,
    accts: r.accounts.map((a) => ({ key: a.key, name: a.name, chip: a.chip, plan: a.plan, l4: a.l4, src: a.src, money: a.money, target: a.target || null, dll: a.dll,
      pos: a.position && { side: a.position.side, qty: a.position.qty, pnl: a.position.pnl_usd, how: a.position.pnl_how, risk: a.position.risk_usd, src: a.position.src, t: a.position.t },
      today: a.today.map((x) => [x.side, x.qty, x.usd, x.exit, x.open]), recent: a.recent.length, last: a.last_trade,
      rules: Object.fromEntries(a.rules.map((x) => [x.key, [x.state, x.text]])),
      payout: a.payout && { text: a.payout.text, checks: Object.fromEntries(a.payout.checks.map((x) => [x.key, [x.state, x.text]])), status: a.payout.status, req: a.payout.request_today },
      stats: a.stats && { n: a.stats.n, pf: a.stats.pf, ct: a.stats.ct } })) });
  const out = { base: pick(run(lite0)) };
  const mod = (f) => { const l = JSON.parse(JSON.stringify(lite0)); f(l); return l; };
  out.dll = pick(run(mod((l) => { l.board.lit.today_pnl = -560; l.board.lit.dll_used = 560; l.accounts[0].eval.today = -560; l.accounts[0].eval.dll_used = 560; })));
  out.mll = pick(run(mod((l) => { l.board.lit.room = 380; l.board.lit.floor = 48812.78; l.accounts[0].eval.room = 380; l.accounts[0].eval.floor = 48812.78; })));
  out.hedge = pick(run(mod((l) => { l.board.atlas.position = { side: 'SHORT', qty: 2, entry: 27410, stop: 27436, target: 27360, entry_t: fx.now - 300 }; })));
  out.late = pick(run(mod((l) => { const t = fx.late; l.t = t; l.reporter.t = t + 30; l.board.t = l.board.data_t = t; l.accounts.forEach((a) => (a.conn.t = t)); }), fx.late + 60));
  out.idle = pick(run(lite0, fx.idle));
  out.silent = pick(run(lite0, NOW + 3 * 3600));
  out.snap = pick(run(null, NOW, { board: { kind: 'olympus-board', t: NOW - 86400, accounts: [{ key: 'zlarior', balance: 49000, src: 'PC live', src_t: NOW - 86400 }] } }));
  out.none = pick(run(null, NOW));
  out.twice = pick(run(mod((l) => { l.accounts[0].eval.balance = 49192.5; })));
  console.log('@@' + JSON.stringify(out));
"""


def part_c():
    core, exts = fixture()
    late = et(2026, 11, 19, 16, 20)
    fx = {"core": core, "exts": exts, "now": NOW, "late": late, "idle": et(2026, 11, 26, 11, 0)}
    js = lambda p: json.dumps(p)
    r = node(CENTER % {"feed": js(os.path.join(WEB, "pc_feed.js")), "mm": js(os.path.join(BIZ, "mffumodel.js")), "coach": js(os.path.join(BIZ, "payoutcoach.js")),
                       "center": js(os.path.join(BIZ, "mffucenter.js")), "plan": js(os.path.join(BIZ, "accounts.json")), "fx": json.dumps(fx), "now": NOW})
    if "error" in r:
        check("c. node ran", False, r["error"])
        return
    b = r["base"]
    A = {a["key"]: a for a in b["accts"]}
    z, n, a = A.get("zlarior", {}), A.get("fresh25", {}), A.get("atlas", {})
    check("c. the live feed: 'Live from your PC: last report 10:10 AM ET (just now)' (the PC looked at 10:10:40)", b["feed"]["kind"] == "live"
          and b["feed"]["text"] == "Live from your PC: last report 10:10 AM ET (just now)", b["feed"])
    check("c. 3 cards in the plan's order with the owner's names and MFFU's chips; no Rapid card (plan only), the Rapid rules in the PLAN list",
          [x["key"] for x in b["accts"]] == ["zlarior", "atlas", "fresh25"] and [z.get("name"), a.get("name"), n.get("name")] == ["Zlarior 50K", "ATLAS 25K funded", "Zlarior 25K #2"]
          and [z["chip"]["text"], a["chip"]["text"], n["chip"]["text"]] == ["Evaluation", "Sim Funded", "Evaluation"] and b["planned"] and b["planned"][0][0] == "rapid1"
          and b["planned"][0][1].startswith("Pass: make $1,500 in at least"), ([x["key"] for x in b["accts"]], b["planned"]))
    check("c. which account is which: ...6016 = Zlarior 50K, ...6018 = ATLAS 25K funded, ...6019 = Zlarior 25K #2 (the push alerts name the last 4)",
          b["decoder"] == [["6016", "Zlarior 50K"], ["6018", "ATLAS 25K funded"], ["6019", "Zlarior 25K #2"]], b["decoder"])
    check("c. every card says live + 'as of 10:10 AM ET (2 min ago)'", all(x["src"]["kind"] == "live" and x["src"]["asof"] == "as of 10:10 AM ET" and x["src"]["ago"] == "2 min ago"
                                                                               for x in b["accts"]), [x["src"] for x in b["accts"]])
    zm, am = z.get("money", {}), a.get("money", {})
    check("c. Zlarior 50K: $49,192.78, -$807.22, floor $48,168.20, $1,024.58 left (MFFU's open-loss rule: the +$144 trade does not cut it), $3,807.22 to pass",
          zm.get("balance") == 49192.78 and zm.get("pnl") == -807.22 and zm.get("floor") == 48168.2 and zm.get("room") == 1024.58 and zm.get("room_now") == 1024.58
          and z.get("target", {}).get("left") == 3807.22 and zm.get("peak") == 50168.2, zm)
    check("c. ATLAS funded the MFFU way (from $0): balance +$73.20, floor -$1,000, $1,073.20 left; the bot's ledger $25,073.20 kept apart; no profit target",
          am.get("balance") == 73.2 and am.get("ledger_balance") == 25073.2 and am.get("floor") == -1000 and am.get("room") == 1073.2 and a.get("target") is None, am)
    zp, npos = z.get("pos") or {}, n.get("pos") or {}
    check("c. the open trades: Zlarior 50K LONG 6 (core card) +$144 at NQ 27,402, risk $240; Zlarior 25K #2 LONG 3 (ext 'at' row) +$70.50",
          zp.get("side") == "LONG" and zp.get("qty") == 6 and zp.get("pnl") == 144 and zp.get("risk") == 240 and zp.get("src") == "core" and "27,402" in zp.get("how", "")
          and npos.get("qty") == 3 and npos.get("pnl") == 70.5 and npos.get("src") == "ext" and b["open"][0][:3] == ["Zlarior 50K", "LONG", 6], (zp, npos, b["open"]))
    check("c. today's trades with $: ATLAS SHORT 2 -> TARGET +$186 (this session); the 50K's Nov 16 stop is history, not today; newest trades name the account",
          a.get("today") == [["SHORT", 2, 186.0, "TARGET", False]] and z.get("today") == [] and z.get("recent") == 1 and z.get("last") == "2026-11-19"
          and b["latest"][0] == ["ATLAS 25K funded", "SHORT", 186.0, False], (a.get("today"), z.get("today"), b["latest"]))
    zr, ar = z.get("rules", {}), a.get("rules", {})
    st = lambda R: {k: v[0] for k, v in R.items()}
    check("c. Zlarior 50K rules: max loss / daily loss / contracts (6 of 40) / flat / news / 7-day / hedge OK; holiday CLOSE (Thanksgiving Thu Nov 26 1:00 PM)",
          st(zr) == {"mll": "ok", "dll": "ok", "size": "ok", "flat": "ok", "holiday": "close", "news": "ok", "idle": "ok", "hedge": "ok"}
          and "Thu Nov 26" in zr["holiday"][1] and "1:00 PM" in zr["holiday"][1] and "does NOT close" in zr["holiday"][1] and "6 micros" in zr["size"][1], zr)
    check("c. ATLAS funded rules: all OK but the holiday heads-up; news allowed on Builder sim funded; last trade today",
          st(ar) == {"mll": "ok", "dll": "ok", "size": "ok", "flat": "ok", "holiday": "close", "news": "ok", "idle": "ok", "hedge": "ok"} and "sim funded" in ar["news"][1]
          and "Last trade Thu Nov 19" in ar["idle"][1], ar)
    p = a.get("payout") or {}
    pc = {k: v[0] for k, v in (p.get("checks") or {}).items()}
    check("c. ATLAS payout checklist: buffer / $250 above / 50% best day NOT YET, 2 days OK, 48 h from Fri Nov 20 not yet; the coach says Not yet; $0 requestable",
          pc == {"buffer": "wait", "above": "wait", "days": "ok", "cons": "wait", "wait48": "wait"} and "Fri Nov 20" in p["checks"]["wait48"][1]
          and "$1,026.80 more" in p["checks"]["buffer"][1] and p.get("req") == 0 and str(p.get("text", "")).startswith("Not yet"), p)
    check("c. the 25K #2: its open trade (from 9:42) counts as today's trade for the 7-day rule (no closed trade yet)",
          n.get("rules", {}).get("idle", [None, ""])[0] == "ok" and n.get("last") == "2026-11-19", n.get("rules", {}).get("idle"))
    rd = {x["key"]: x for x in r["dll"]["accts"]}["zlarior"]["rules"]["dll"]
    check("c. a -$560 day on the 50K: daily loss CLOSE ($560 of $1,000, $440 left)", rd[0] == "close" and "$560.00 used" in rd[1] and "$440.00 left" in rd[1], rd)
    rm = {x["key"]: x for x in r["mll"]["accts"]}["zlarior"]["rules"]["mll"]
    check("c. $380 left on the 50K: max loss CLOSE", rm[0] == "close" and "$380.00 left" in rm[1], rm)
    hz = {x["key"]: x for x in r["hedge"]["accts"]}
    check("c. ATLAS short while both Zlarior accounts are long: hedge BROKEN on all three, named in plain words",
          all(hz[k]["rules"]["hedge"][0] == "broken" for k in ("zlarior", "atlas", "fresh25")) and "ATLAS 25K funded SHORT" in hz["atlas"]["rules"]["hedge"][1], hz["atlas"]["rules"]["hedge"])
    lz = {x["key"]: x for x in r["late"]["accts"]}["zlarior"]["rules"]["flat"]
    check("c. the long still open at 4:20 PM ET in the PC's report: 'Flat by 4:10 PM ET' BROKEN", lz[0] == "broken" and "after 4:10 PM" in lz[1], lz)
    iz = {x["key"]: x for x in r["idle"]["accts"]}
    check("c. a week later with no new trade (Thu Nov 26): the 50K's 7-day rule BROKEN (last trade Nov 19 counted), never a false alarm before",
          iz["fresh25"]["rules"]["idle"][0] == "broken" and iz["zlarior"]["rules"]["idle"][0] == "broken" and "7+ days" in iz["zlarior"]["rules"]["idle"][1], iz["zlarior"]["rules"]["idle"])
    s = r["silent"]
    check("c. the PC quiet for 3 h: 'PC SILENT ... not live', every card marked old (never live)", s["feed"]["kind"] == "old" and "PC SILENT" in s["feed"]["text"]
          and "not live" in s["feed"]["text"] and all(x["src"]["kind"] == "old" for x in s["accts"]), s["feed"])
    sn = r["snap"]
    zs = {x["key"]: x for x in sn["accts"]}.get("zlarior", {})
    check("c. no PC feed: the site's copy shows as SNAPSHOT (chip + source), never live; the rest PLAN", sn["feed"]["kind"] == "snapshot" and "NOT LIVE" in sn["feed"]["text"]
          and zs.get("chip", {}).get("text", "").startswith("SNAPSHOT") and zs.get("src", {}).get("kind") == "snapshot" and zs.get("money", {}).get("balance") == 49000
          and not any(x["src"]["kind"] == "live" for x in sn["accts"]), (sn["feed"], zs.get("chip"), zs.get("src")))
    nn = r["none"]
    check("c. nothing at all: 'No numbers yet', plan cards only (PLAN chips), no live, no snapshot", nn["feed"]["kind"] == "none"
          and all(x["src"]["kind"] == "plan" and x["chip"]["text"] == "PLAN" for x in nn["accts"]), [x["chip"] for x in nn["accts"]])
    part_c2(r)


def part_c2(r):
    tw = r.get("twice") or {}
    check("c. the 50K's ledger row a few cents off its board card (seen twice): still ONE Zlarior 50K card, 3 cards in all",
          [x["key"] for x in tw.get("accts") or []] == ["zlarior", "atlas", "fresh25"], [x["key"] for x in tw.get("accts") or []])


def part_d():
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("  (playwright not installed: browser part skipped)")
        return
    core, exts = fixture()
    nd = ndjson(core, exts)
    at = dt.datetime.fromtimestamp(NOW, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844, mock={"json?poll=1": nd})
            p.goto(f"{origin}/business/mffu.html?at={at}")
            p.wait_for_function("window.MFFU_PAGE && window.MFFU_PAGE.ready", timeout=60000)
            p.wait_for_timeout(300)
            o = p.evaluate("""() => ({ st: document.getElementById('status').textContent, stc: document.getElementById('status').className,
                keys: [...document.querySelectorAll('#list .mf')].map((c) => c.dataset.key), h: [...document.querySelectorAll('#list .mf h2')].map((e) => e.textContent),
                chips: [...document.querySelectorAll('#list .mf-top .mf-st')].map((e) => e.textContent), now: document.getElementById('now').textContent,
                rows: [...document.querySelectorAll('#now .acct-row')].map((e) => e.getAttribute('href')), txt: document.getElementById('list').textContent,
                pos: document.querySelectorAll('#list .mf-pos').length, rules: document.querySelectorAll('#list .rule').length,
                closeRules: [...document.querySelectorAll('#list .rule.close')].map((e) => e.dataset.rule), eq: document.querySelectorAll('canvas.eq').length,
                planned: document.getElementById('plannedBox').hidden, plannedTxt: document.getElementById('planned').textContent })""")
            check("d. the page fed the fixture: 'Live from your PC' (green), 3 cards Zlarior 50K / ATLAS 25K funded / Zlarior 25K #2 with MFFU's chips",
                  "Live from your PC" in o["st"] and "live" in o["stc"] and o["keys"] == ["zlarior", "atlas", "fresh25"]
                  and o["h"] == ["Zlarior 50K", "ATLAS 25K funded", "Zlarior 25K #2"] and o["chips"] == ["Evaluation", "Sim Funded", "Evaluation"], o)
            check("d. Right now: each account one tap away (+ the rule to watch), the 2 open longs with live $, the newest trades by account, which-account-is-which (...6016 = Zlarior 50K)",
                  o["rows"] == ["#acct-zlarior", "#acct-atlas", "#acct-fresh25"] and "Zlarior 50K · 9:42 AM · LONG 6 micros at 27,390" in o["now"]
                  and "+$144.00 now" in o["now"] and "+$70.50 now" in o["now"] and "watch: Holiday hours" in o["now"]
                  and "ATLAS 25K funded · 3:05 AM · SHORT 2 micros at 27,420" in o["now"] and "…6016 = Zlarior 50K" in o["now"]
                  and "ends at 4:10 PM ET" in o["now"], o["now"][:600])
            check("d. the cards: 2 open trades (+$144.00 now at NQ 27,402), MFFU balance +$73.20 from $0, the payout checklist, the rules (holiday = close), equity lines",
                  o["pos"] == 2 and "+$144.00" in o["txt"] and "NQ 27,402" in o["txt"] and "+$73.20" in o["txt"] and "bot ledger $25,073.20" in o["txt"]
                  and "Buffer $1,100 cleared" in o["txt"] and "48 hours after the first funded trade" in o["txt"] and o["rules"] >= 24
                  and set(o["closeRules"]) == {"holiday"} and "TARGET +$186.00" in o["txt"] and "as of 10:10 AM ET" in o["txt"] and o["eq"] >= 1, (o["closeRules"], o["txt"][:400]))
            check("d. the PLAN list: the Rapid EOD 25K with its rules", not o["planned"] and "Rapid EOD 25K" in o["plannedTxt"] and "news" in o["plannedTxt"], o["plannedTxt"][:200])
            check("d. 390 px: taps >= 44 px, no sideways scroll, nothing fetched off the site (the ntfy poll is mocked), no console error",
                  not AK.taps(p) and AK.no_sideways(p) and not off and not errs and p.mocked, (AK.taps(p)[:4], off[:3], errs[:3]))
            if "--shots" in sys.argv:                  # the owner's phone shots (only on request: a plain run never rewrites them)
                os.makedirs(SHOTS, exist_ok=True)
                p.screenshot(path=os.path.join(SHOTS, "mffu-center-390.png"), full_page=True)
                p.screenshot(path=os.path.join(SHOTS, "mffu-center-390-top.png"), full_page=False)
                p.evaluate("document.getElementById('acct-atlas').scrollIntoView()")
                p.screenshot(path=os.path.join(SHOTS, "mffu-center-390-atlas.png"), full_page=False)
            ctx.close()
            # the PC quiet for 3 hours: the page says PC SILENT and never 'Live'
            at3 = dt.datetime.fromtimestamp(NOW + 3 * 3600, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844, mock={"json?poll=1": nd})
            p.goto(f"{origin}/business/mffu.html?at={at3}")
            p.wait_for_function("window.MFFU_PAGE && window.MFFU_PAGE.ready", timeout=60000)
            o = p.evaluate("""() => ({ st: document.getElementById('status').textContent, src: [...document.querySelectorAll('#list .mf-src')].map((e) => e.className + '|' + e.textContent) })""")
            check("d. the PC silent 3 h: the status says PC SILENT (not live), every card's source line says 'PC silent' with its time, none says Live",
                  "PC SILENT" in o["st"] and o["src"] and all("old" in s and "PC silent" in s and "as of 10:10 AM ET" in s for s in o["src"]) and not any("Live from" in s for s in o["src"]), o)
            ctx.close()
            # no PC feed at all: the published site copy only -> SNAPSHOT, never live
            ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844, mock={"json?poll=1": ""})
            p.goto(f"{origin}/business/mffu.html?at={at}")
            p.wait_for_function("window.MFFU_PAGE && window.MFFU_PAGE.ready", timeout=60000)
            o = p.evaluate("""() => ({ st: document.getElementById('status').textContent, src: [...document.querySelectorAll('#list .mf-src')].map((e) => e.textContent),
                chips: [...document.querySelectorAll('#list .mf-top .mf-st')].map((e) => e.textContent), now: document.getElementById('now').textContent })""")
            check("d. no PC feed: 'NOT LIVE' / 'No numbers yet' status, no card says Live (SNAPSHOT or PLAN chips only), open trades 'unknown'",
                  re.search(r"NOT LIVE|No numbers yet", o["st"]) and o["src"] and not any(s.startswith("Live from") for s in o["src"])
                  and all(c.startswith(("SNAPSHOT", "PLAN")) for c in o["chips"]) and "Open trades: unknown without the PC feed" in o["now"] and not errs, o)
            ctx.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    part_b()
    part_c()
    if "--static" not in sys.argv:
        part_d()
    return AK.finish()


if __name__ == "__main__":
    sys.exit(main())
