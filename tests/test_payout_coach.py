"""PAYOUT COACH (engine/payout_coach.py + tools/web_public/business/payoutcoach.js / payoutcard.js) and the funded 25K payout
policy research (tools/money/payout25.py -> research/lab/payout25.json). docs/FUNDED_25K_PLAYBOOK.md.

  a. the coach on MFFU Builder 25K rules: before the first trade, under the $1,100 buffer + $250, the 2-day minimum, the 50% best
     day (and "a $1,000 day more and you'd need $Y more"), allowed under $1,000 (the plan waits), READY at the full $1,000,
     5 payouts, lost, the 30% tax pot, the floor at start + $100 after a payout, the 7-day inactivity countdown
  b. the coach agrees with engine/funded_life.track (MFFU's own checks) on the request amount and eligibility
  c. the JS copy (node) gives the same numbers and lines as Python on every case
  d. the pages: both load payoutcoach.js + payoutcard.js, text only (no innerHTML / fetch / outside address in the coach files),
     storage only in try/catch, ATLAS's row in accounts.json has a funded block, BLITZ never gets a card
  e. the research file: every policy x both mixes x H1 / H2 / 2021-25, the pick (ask at the $1,000 max) holds on H2

    python -X utf8 -m tests.test_payout_coach
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import funded_life as FL, payout_coach as PC  # noqa: E402

RESULTS = []
BIZ = os.path.join(ROOT, "tools", "web_public", "business")
BOARD = os.path.join(ROOT, "tools", "web_public", "board")


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""), flush=True)
    return bool(cond)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


S0 = {"cycle_start_balance": 25000, "first_trade": "2026-11-19", "payouts_n": 0}
CASES = {
    "no trade yet": ({"balance": 25000, "cycle_start_balance": 25000, "payouts_n": 0}, "2026-11-18"),
    "under the buffer": ({**S0, "balance": 25900, "best_day": 400, "cycle_days": 3, "last_trade": "2026-11-24"}, "2026-11-25"),
    "1 day only": ({**S0, "balance": 26500, "best_day": 1500, "cycle_days": 1, "last_trade": "2026-11-19"}, "2026-11-20"),
    "best day too big": ({**S0, "balance": 26600, "best_day": 1000, "cycle_days": 3, "last_trade": "2026-11-24"}, "2026-11-25"),
    "allowed $300": ({**S0, "balance": 26400, "best_day": 500, "cycle_days": 3, "last_trade": "2026-11-24"}, "2026-11-25"),
    "ready $1,000": ({**S0, "balance": 27350, "best_day": 900, "cycle_days": 6, "last_trade": "2026-12-04"}, "2026-12-08"),
    "2nd cycle ready": ({"balance": 27200, "cycle_start_balance": 26100, "best_day": 450, "cycle_days": 4, "first_trade": "2026-11-19",
                         "last_trade": "2026-12-15", "payouts_n": 1}, "2026-12-16"),
    "graduated": ({**S0, "balance": 26300, "best_day": 100, "cycle_days": 2, "payouts_n": 5, "last_trade": "2027-02-01"}, "2027-02-02"),
    "lost": ({**S0, "balance": 24000, "room": 0, "best_day": 0, "cycle_days": 4, "last_trade": "2026-11-27"}, "2026-11-28"),
    "idle 5 days": ({**S0, "balance": 26000, "best_day": 300, "cycle_days": 4, "last_trade": "2026-11-20"}, "2026-11-25"),
    "50K ready": ({**S0, "cycle_start_balance": 50000, "balance": 54300, "best_day": 1200, "cycle_days": 5, "last_trade": "2026-12-04"}, "2026-12-07"),
    "first wait": ({**S0, "balance": 26600, "best_day": 600, "cycle_days": 2, "first_trade": "2026-11-20", "last_trade": "2026-11-23"}, "2026-11-23"),
}
PLAN_OF = {"50K ready": "builder50k"}


def part_a():
    c = {k: PC.coach(s, PLAN_OF.get(k, "builder25k"), t) for k, (s, t) in CASES.items()}
    x = c["no trade yet"]
    check("a. no trade yet: not yet, first request 2 days after the first trade", x["status"] == "not_yet" and any("no funded trade" in w for w in x["why"]))
    x = c["under the buffer"]
    check("a. $900 profit: not yet, need $450 more ($1,100 buffer + $250 minimum)", x["status"] == "not_yet" and x["need_more"] == 450 and x["request_today"] == 0
          and "need $450 more" in x["text"], x["text"])
    x = c["1 day only"]
    check("a. one traded day: not yet (2 needed), and the one $1,500 day breaks the 50% rule", x["status"] == "not_yet" and x["cycle_days"] == 1
          and any("1 of 2 traded days" in w for w in x["why"]) and not x["cons_ok"], x["why"])
    x = c["best day too big"]
    check("a. best day $1,000 of a $1,600 cycle = 62.5%: not yet, $400 more on other days", not x["cons_ok"] and x["best_pct"] == 62.5 and x["cons_need"] == 400
          and x["need_more"] == 400 and x["status"] == "not_yet", (x["best_pct"], x["cons_need"]))
    x = c["allowed $300"]
    check("a. $300 above the buffer, rules met: MFFU allows $300, the plan waits $700 for the full $1,000", x["status"] == "allowed" and x["request_today"] == 300
          and x["plan_wait"] == 700 and x["to_you"] == 240 and x["tax_pot"] == 72 and x["net"] == 168, x["text"])
    check("a. the 50% line: safe new best day = the cycle's profit ($1,400); a $1,000 day still fine", x["safe_day"] == 1400 and x["big_day_need"] == 0)
    x = c["ready $1,000"]
    check("a. READY: request $1,000 ($800 to you, $240 tax pot, $560 net); after it the floor sits at $25,100 -> room $1,250",
          x["status"] == "ready" and x["request_today"] == 1000 and x["to_you"] == 800 and x["tax_pot"] == 240 and x["net"] == 560
          and x["after_balance"] == 26350 and x["after_room"] == 1250, x)
    check("a. a $1,000 day more on a $2,350 cycle: still under 50% ($0 more)", x["big_day_need"] == 0)
    x = c["2nd cycle ready"]
    check("a. 2nd cycle: cycle profit from the balance after the 1st payout ($1,100), $1,000 READY, no first-trade wait",
          x["cycle_profit"] == 1100 and x["status"] == "ready" and x["request_today"] == 1000, x["why"])
    y = PC.coach({**CASES["best day too big"][0]}, "builder25k", "2026-11-25")
    big = PC.coach({**S0, "balance": 25800, "best_day": 300, "cycle_days": 3}, "builder25k", "2026-11-25")
    check("a. 'a $1,000 day more and you'd need $Y more': $800 cycle -> $200 more on other days", big["big_day_need"] == 200
          and any("A $1,000 day more and you'd need $200 more" in ln for ln in PC.lines(big)), PC.lines(big))
    check("a. best day $1,000 of $1,600 (62.5%): one more $1,000 day fixes it ($2,600 cycle, 38%) -> $0 more", y["big_day_need"] == 0)
    z = PC.coach({**S0, "balance": 26100, "best_day": 900, "cycle_days": 3}, "builder25k", "2026-11-25")
    check("a. best day $900 of $1,100: a $300 day -> still $400 more ($1,800 needed)", z["cons_need"] == 700
          and PC.coach({**S0, "balance": 26400, "best_day": 900, "cycle_days": 4}, "builder25k", "2026-11-26")["cons_need"] == 400)
    check("a. 5 payouts: graduated (live, you present)", c["graduated"]["status"] == "graduated")
    check("a. room 0: lost", c["lost"]["status"] == "lost")
    x = c["idle 5 days"]
    check("a. inactivity: last trade Nov 20 -> trade by Nov 26 at the latest, 1 day left, warning on", x["trade_by"] == "2026-11-26" and x["idle_left"] == 1
          and x["idle_warn"] and x["idle_days"] == 5, (x["trade_by"], x["idle_left"]))
    x = c["50K ready"]
    check("a. 50K: $2,100 buffer, $2,000 max: $4,300 profit -> request $2,000", x["status"] == "ready" and x["request_today"] == 2000 and x["to_you"] == 1600)
    x = c["first wait"]
    check("a. first trade Fri Nov 20 -> first request Mon Nov 23 is allowed (2 days, next weekday)", x["eligible_from"] == "2026-11-23" and x["eligible"])
    x2 = PC.coach({**CASES["first wait"][0]}, "builder25k", "2026-11-21")
    check("a. ... and not on Sat Nov 21", not x2["eligible"] and any("first request from 2026-11-23" in w for w in x2["why"]))
    check("a. no balance: asks for it", not PC.coach({}, "builder25k", "2026-11-20")["ok"])
    return c


def part_b():
    # the same account as engine/funded_life.track (MFFU's checks): days P&L -> tracker -> coach state
    seqs = [({"2026-11-19": 400.0, "2026-11-20": 350.0, "2026-11-23": 500.0, "2026-11-24": 300.0}, {}, "2026-11-24"),
            ({"2026-11-19": 1200.0, "2026-11-20": 200.0}, {}, "2026-11-23"),
            ({"2026-11-19": 600.0, "2026-11-20": 500.0, "2026-11-23": 450.0, "2026-11-24": 520.0, "2026-11-25": 480.0}, {}, "2026-11-25"),
            ({"2026-11-19": 600.0, "2026-11-20": 500.0, "2026-11-23": 450.0, "2026-11-24": 520.0, "2026-12-01": 300.0, "2026-12-02": 420.0},
             {"2026-11-24": 1000.0}, "2026-12-02"),
            ({"2026-11-19": -300.0, "2026-11-20": 200.0}, {}, "2026-11-20")]
    ok = True
    info = []
    for days, pays, today in seqs:
        t = FL.track(days, pays, "builder25k", today=today, start="2026-11-19")
        st = PC.from_tracker(t, last_trade=max(days))
        st["first_trade"] = t["first_trade"]
        c = PC.coach(st, "builder25k", today)
        same = c["eligible"] == t["eligible"] and abs(c["request_today"] - t["max_request"]) < 0.01 and c["cycle_days"] == t["cycle_days"] \
            and abs(c["cycle_profit"] - t["cycle_profit"]) < 0.01 and c["cons_ok"] == t["cons_ok"]
        ok &= same
        info.append((today, c["eligible"], t["eligible"], c["request_today"], t["max_request"]))
    check("b. coach == engine/funded_life.track (eligible, request $, cycle profit, days, 50% rule) on 5 account histories", ok, info)
    sub = {k: t.get(k) for k in ("buffer_balance", "above_buffer", "cycle_profit", "best_day", "cycle_days", "eligible_from", "payouts_n")}
    st = PC.from_tracker(sub)
    check("b. from the PC feed's funded subset (no balance field): balance = buffer balance + above the buffer",
          st["balance"] == round(t["buffer_balance"] + t["above_buffer"], 2) and st["eligible_from"] == t["eligible_from"], st)


def node_js(cases):
    js = os.path.join(BIZ, "payoutcoach.js")
    payload = json.dumps({k: [s, PLAN_OF.get(k, "builder25k"), t] for k, (s, t) in cases.items()})
    script = (f"const C = require({json.dumps(js)}); const cases = {payload}; const out = {{}};"
              "for (const k in cases) { const [s, p, t] = cases[k]; const c = C.coach(s, p, t); out[k] = { c, lines: C.lines(c) }; }"
              "process.stdout.write(JSON.stringify(out));")
    p = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    if p.returncode:
        raise RuntimeError(p.stderr[-800:])
    return json.loads(p.stdout)


def part_c():
    js = node_js(CASES)
    keys = ("ok", "status", "request_today", "need_more", "cycle_profit", "best_pct", "cons_ok", "cons_need", "safe_day", "big_day_need",
            "eligible", "eligible_from", "plan_wait", "to_you", "tax_pot", "net", "after_balance", "after_room", "trade_by", "idle_left",
            "idle_warn", "text")
    bad = []
    for k, (s, t) in CASES.items():
        py = PC.coach(s, PLAN_OF.get(k, "builder25k"), t)
        j = js[k]["c"]
        for f in keys:
            a, b = py.get(f), j.get(f)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
                if abs(a - b) > 0.005:
                    bad.append((k, f, a, b))
            elif a != b:
                bad.append((k, f, a, b))
        if py.get("ok") and PC.lines(py) != js[k]["lines"]:
            bad.append((k, "lines", PC.lines(py), js[k]["lines"]))
        if py.get("why") is not None and py["why"] != j.get("why"):
            bad.append((k, "why", py["why"], j.get("why")))
    check(f"c. JS payoutcoach.js == engine/payout_coach.py on {len(CASES)} cases (numbers, why, lines)", not bad, bad[:3])


def part_d():
    acc, bh = read(os.path.join(BIZ, "accounts.html")), read(os.path.join(BOARD, "index.html"))
    check("d. My Accounts loads payoutcoach.js + payoutcard.js before accounts.js and has the coach box",
          re.search(r'payoutcoach\.js\?v=\d+".*payoutcard\.js\?v=\d+".*accounts\.js\?v=\d+"', acc, re.S) and 'id="coach"' in acc)
    check("d. Board loads ../business/payoutcoach.js + payoutcard.js and has the Payouts box",
          "../business/payoutcoach.js?v=" in bh and "../business/payoutcard.js?v=" in bh and 'id="payouts"' in bh)
    bad = r"\.innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|new Function|fetch\(|XMLHttpRequest|WebSocket|sendBeacon|https?://"
    core, card = read(os.path.join(BIZ, "payoutcoach.js")), read(os.path.join(BIZ, "payoutcard.js"))
    check("d. coach files: no markup from data, no fetch, no outside address; the card draws with textContent",
          not re.search(bad, core) and not re.search(bad, card) and "textContent" in card)
    check("d. coach core is pure (no DOM, no storage)", not re.search(r"document\.|localStorage|window\.(?!PAYOUT)", core.replace("typeof window", "")))
    n_ls = card.count("localStorage.")
    check("d. the card: one storage key, every read and write in try/catch", n_ls == 2 and "business.payout.v1" in card
          and all("try {" in ln for ln in card.splitlines() if "localStorage." in ln))
    check("d. never requests a payout: the card says you request it in the MFFU dashboard", "the bot never does" in card and "MFFU dashboard" in card)
    plan = json.loads(read(os.path.join(BIZ, "accounts.json")))
    at = {a["key"]: a for a in plan["accounts"]}.get("atlas") or {}
    f = at.get("funded") or {}
    check("d. accounts.json: ATLAS has a funded block (balance, cycle start, best day, days, first / last trade, payouts n)",
          all(k in f for k in ("balance", "cycle_start_balance", "best_day", "cycle_days", "first_trade", "last_trade", "payouts_n", "as_of")))
    check("d. BLITZ never gets a coach card", "/blitz/i.test(String(a.key))" in card)
    check("d. inputs: 16px+ font, 44px taps", "min-height: 44px" in acc and "font-size: 16px" in acc and "min-height: 44px" in bh)


def part_e():
    p = os.path.join(ROOT, "research", "lab", "payout25.json")
    if not check("e. research/lab/payout25.json exists (python -X utf8 tools/money/payout25.py)", os.path.exists(p)):
        return
    d = json.loads(read(p))
    from tools.money import payout25 as P25  # noqa: F401  (import check only)
    pols = set(P25.POLICIES)
    full = all(set(d["rows"][sp][mx]) == pols for sp in ("H1", "H2", "REF") for mx in ("ATLAS alone (today)", "LIT + ATLAS $250"))
    check(f"e. {len(pols)} policies x 2 mixes x H1 / H2 / 2021-25 on the same {d['n']} paths", full and d["n"] >= 600)
    pick = d["pick"]
    check("e. the pick (on H1, held on H2): ask at the $1,000 max for both mixes",
          all(pick[m]["adopt"] == "ask at $1,000 (max)" and pick[m]["h2_holds"] for m in pick), pick)
    r = d["rows"]
    ok = all(r[sp][m]["ask at $1,000 (max)"]["per_month"] >= r[sp][m]["today: ask at $750"]["per_month"]
             and r[sp][m]["ask at $1,000 (max)"]["lost_6m"] <= r[sp][m]["today: ask at $750"]["lost_6m"] for sp in ("H1", "H2") for m in pick)
    check("e. $1,000 max >= today's $750 line on $ a month and <= on lost, both 2026 halves, both mixes", ok)
    check("e. the coach's plan = the research pick", PC.POLICY["key"] == "max" and "full max" in PC.POLICY["text"])


def main():
    part_a()
    part_b()
    part_c()
    part_d()
    part_e()
    n, ok = len(RESULTS), sum(RESULTS)
    print(f"\n{ok}/{n} passed")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
