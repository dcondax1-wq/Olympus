"""Rapid EOD 25K launch (2026-11-20, day-rapid): once the owner adds the Rapid at :8444/add-account/, it shows up under its
own label in every place he looks, all from ONE running bot (paper adapter, Sim / made-up names, nothing armed or routed):

    python -X utf8 -m tests.test_rapid_launch          # ~10 s

  a. the bot: the Rapid's LIT lane (id "rapid") runs with the 25K rules; ATLAS's Rapid lane is on the same account
  b. the heartbeat acct block (engine/accounts.pc_activity) has the Rapid, no phrase, no temp paths
  c. the Accounts sections the PC posts (engine/accounts.build_accounts -> live.json "accounts"): a "rapid" row,
     $25,000 start, its own name, not the 50K's
  d. the PC status report (tools/pc_report.full): the Rapid row rides in the core post, and the chart / trades list names it
     "Rapid 25K" (tools/live_trades.ACCOUNTS), never by an id or digits
  e. the trades feed key: LIT's lane id "rapid" and ATLAS's Rapid order tag "acctr" both map to the Rapid, BLITZ stays hidden
  f. the MFFU rules the add box prints = the rules the bot trades (target $1,500, $1,000 EOD, 20 micros, DLL $500 soft pause,
     30% best day, 4 days, funded news ban) and the DLL day stop: a full stop never takes the day under -$500 by sizing
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import multi_account as MA, rapid  # noqa: E402
from engine.tradovate import LIVE_PHRASE  # noqa: E402
from tests.test_rapid import Clock, DAY, T0, make_bot  # noqa: E402

RESULTS = []
P25 = "mffu_rapid_eod_25k"
NAME = "Sim205"


def check(name, cond, info=""):
    RESULTS.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + ("" if cond else f"  -> {str(info)[:400]}"))


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="rapid_launch_")
    keep_path = rapid.PATH
    try:
        rapid.PATH = os.path.join(tmp, "rapid.json")
        blk = {"account": NAME, "eval_start": DAY, "armed": False, "plan": P25}
        rapid.save(blk)
        clock = Clock(T0)
        b = make_bot(os.path.join(tmp, "bot"), clock, rapid.read())
        ln = next((a for a in b.accts.accounts if a.spec.get("lane") == "rapid"), None)
        check("a. the bot runs the Rapid's LIT lane (id 'rapid') with the 25K preset", ln is not None and ln.spec.get("preset") == P25
              and ln.rules.get("target") == 1500.0 and ln.rules.get("mll") == 1000.0, ln and (ln.spec, ln.rules))
        check("a. the lane's day stop is MFFU's $500 DLL and 20 micros max", ln is not None and float(ln.rules.get("dll")) == 500.0
              and int(ln.rules.get("max_micros")) == 20, ln and ln.rules)

        from engine import accounts
        clock.t = T0 + 600
        a = accounts.pc_activity(b, now=clock.t, journal_path=os.path.join(tmp, "none.jsonl"))
        subs = [s.get("id") for s in a.get("accounts") or []]
        blob = json.dumps(a)
        check("b. heartbeat acct block lists the Rapid, no phrase, no temp path", "rapid" in subs and LIVE_PHRASE not in blob
              and tmp not in blob, subs)

        lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
        secs = accounts.build_accounts({"last_run": clock.t, "pc": {"present": True, "t": clock.t - 60, "acct": a}, "ledger": {}}, lm,
                                       now=clock.t)
        rs = next((s for s in secs if s.get("id") == "rapid"), None)
        ev = (rs or {}).get("eval") or {}
        check("c. live.json Accounts: a 'rapid' section on $25,000 (not the 50K's numbers)", rs is not None
              and float(ev.get("start_balance") or (rs.get("plan_rules") or {}).get("start") or 0) == 25000.0, rs and {k: rs.get(k) for k in ("id", "name", "plan", "eval", "plan_rules")})
        check("c. the Rapid section's name / plan says Rapid", rs is not None and "rapid" in (str(rs.get("name")) + str(rs.get("plan"))).lower(),
              rs and (rs.get("name"), rs.get("plan")))

        from tools import pc_report as PR, live_trades as LT
        live = {"v": 1, "kind": "le-live", "t": clock.t, "pc": {"present": True, "running": True}, "accounts": [
            {**s, "kind": s.get("kind") or "eval", "source": s.get("source") or "pc"} for s in secs if s.get("id") == "rapid"]}
        snap = {"t": clock.t, "hb_t": clock.t, "live": live, "hb": {}, "server": True, "nt": True, "market_open": True}
        try:
            core = PR.full(snap)
        except Exception as e:  # noqa: BLE001
            core = {"error": repr(e)}
        ids = [x.get("id") for x in core.get("accounts") or []]
        check("d. PC status report: the Rapid row rides in the core post", "rapid" in ids, (ids, core.get("error")))
        ch = PR._chart_accounts(live)
        labels = [r[1] for r in ch]
        check("d. PC report trades / chart: named 'Rapid 25K', never by an id or digits", "Rapid 25K" in labels
              and not any(NAME in str(x) for x in labels), labels)

        check("e. feed keys: LIT lane 'rapid' and ATLAS's Rapid tag 'acctr' -> the Rapid; BLITZ hidden",
              LT.acct_key("rapid") == "rapid25" and LT.acct_key("acctr") == "rapid25" and LT.acct_key("acctc") is None
              and LT.acct_name("rapid25") == "Rapid 25K")

        P = rapid.plan_info(P25)
        R = MA.PRESETS[P25]["rules"]
        check("f. rules: $1,500 target, $1,000 EOD, 20 micros, 30% best day, 4 days, funded news ban, MFFU DLL $500 (soft pause)",
              (R["target"], R["mll"], R["trail"], R["max_micros"], R["best_day"], R["min_days"], R["news_ban"], P["mffu_dll"])
              == (1500.0, 1000.0, "eod", 20, 0.3, 4, "funded", 500.0), (R, P))
        check("f. payouts: $1,100 buffer, $250 since the last, $500 kept in", (P["buffer"], P["since"], P["cushion"]) == (1100.0, 250.0, 500.0), P)
        worst = []
        for cum in (0.0, -150.0, -400.0, -499.0):
            for risk in (3.0, 8.0, 20.0, 60.0):
                q, usd, loss1 = rapid.stack_qty(risk, 1000.0, cum, 20, 500.0, 250.0)
                worst.append(cum - q * loss1)
        check("f. ATLAS's Rapid size: a full stop (1 tick) never takes the day under -$500, whatever LIT lost first",
              min(worst) >= -500.0 - 1e-6, min(worst))
        # owner YES 2026-11-20 (card rapid-atlas-size-10t): the 25K's ATLAS lane sizes on stop + 10 ticks (its real fills)
        slip = float(rapid.PLANS["mffu_rapid_eod_25k"].get("atlas_slip") or 0)
        worst10 = []
        for cum in (0.0, -150.0, -400.0, -499.0):
            for risk in (3.0, 8.0, 20.0, 60.0):
                q, usd, loss1 = rapid.stack_qty(risk, 1000.0, cum, 20, 500.0, 250.0, slip)
                worst10.append(cum - q * ((risk + 2.5) * 2 + 1.9))
                q1, _, _ = rapid.stack_qty(risk, 1000.0, cum, 20, 500.0, 250.0)
                worst10.append(-1e9 if q > q1 else 0)        # never bigger than the 1-tick size
        check("f. 10-tick sizing (atlas_slip 2.5 on the 25K): a REAL-fill full stop keeps the day >= -$500, never above the old size",
              slip == 2.5 and min(worst10) >= -500.0 - 1e-6, (slip, min(worst10)))
    finally:
        rapid.PATH = keep_path
        MA.ADAPTER_FACTORY = None
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(1 for _, ok in RESULTS if ok)
    print(f"\n{n}/{len(RESULTS)} passed")
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
