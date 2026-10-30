"""BLITZ, the whole 2026 backtest on its own MFFU Builder 25K (owner 2026-10-30: "backtest all the data from 2026 and give
me data, eval passed, profit"). Research only; nothing here is imported by the engine. research/writeups/blitz-2026-backtest.md.

The rule, the anti-hedge account C and the sizes are what the bot will run (engine/blitz.py VERSION 2, engine/account_c.py):
  trades  tools/blitz25k_lib.trades(today's rule, "lit+atlas"): 2026 on 1m bars (Jan 2 - Oct 16), 2021-25 on 5m bars;
          never opposite LIT / ATLAS, closed first at their opposite entry; $1.90 a micro, 1 tick on market / stop fills
  eval    account_c SIZE_EVAL "speed": 40% of the room to the trailing floor, at most $600 a trade (0.9 x the soft daily
          loss left), 100% of the room from eval session 5; pass at +$1,500, fail at the $1,000 EOD trailing floor (locked
          at start + $100), stuck under 2 x the median stop-out (the bot pushes "buy a new one")
  funded  account_c SIZE_FUNDED: 10% of the room, at most $150 a trade, no new trade after +$400 on the day; MFFU payouts
          (balance - $1,100 buffer, $250-$1,000, 80% to the owner, 2 traded days a cycle, 50% best-day rule, 5 payouts)
Outputs:
  1. the trades at a fixed $150 a trade (2026 halves, 2026 whole, 2021-25): trades / week, % weeks with 2+, win %, PF, net,
     $ / month, max DD, and every 2026 month
  2. the eval on every start (a new 25K bought on every 2026 session): p10 / f10 / dec10 / p15 / f15 / pass_med / slow_pass
  3. the real calendar path: one account slot from 2026-01-02 (buy the $63 eval, trade it, pass -> 2 sessions of paperwork
     -> funded -> payouts -> lost / stuck / 5 payouts -> buy the next eval; a fail / stuck -> buy the next one at once),
     every eval and funded account with its dates, trades, $ and result, and the $ to the owner net of every eval bought
  4. the 6-month Monte Carlo slot (tools/blitz25k_size.life, 1,000 paths in 5-session blocks) for 2026 H1 / H2 / 2021-25

    python -X utf8 tools/blitz_2026_backtest.py       # -> research/scalp/blitz_2026_backtest.json + run blitz_2026_backtest
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
import warnings

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
warnings.filterwarnings("ignore")
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from tools import scalp_na_lib as N  # noqa: E402
from tools import scalp_mo_lib as M  # noqa: E402
from tools import blitz25k_lib as K  # noqa: E402
from tools import blitz25k_grid as BG  # noqa: E402
from tools import blitz25k_size as BS  # noqa: E402

OUT = os.path.join(ROOT, "research", "scalp", "blitz_2026_backtest.json")
PRICE = 63.0                                                    # the owner's Builder 25K price (one-time, $0 activation)
EZ = {"mode": "frac", "f": 0.4, "cap": 600.0, "push": (5, 1.0)}   # engine/account_c SIZE_EVAL ("speed")
FZ = {"mode": "frac", "f": 0.1, "cap": 150.0, "day_tp": 400.0}    # engine/account_c SIZE_FUNDED
GAP = 2                                                         # sessions of MFFU paperwork between the pass and funded
USD = 150.0


def fixed(T, S):
    o = N.stats(T, S, USD, 20)
    o["wk2"] = K.wk2(T, S)
    return o


def months(T):
    out = collections.OrderedDict()
    for t in sorted(T, key=lambda x: x["entry_t"]):
        q = max(1, min(20, int(USD / t["risk_pm"])))
        p = N.trade_pnl(t, q)[0]
        m = out.setdefault(t["day"][:7], {"n": 0, "wins": 0, "net": 0.0, "days": set()})
        m["n"] += 1
        m["wins"] += p > 0
        m["net"] += p
        m["days"].add(t["day"])
    return {k: {"n": v["n"], "win": round(100.0 * v["wins"] / v["n"], 1), "net": round(v["net"]), "days": len(v["days"])}
            for k, v in out.items()}


def path(T, S):
    """One account slot on the real calendar from S[0] (see the docstring). -> every account + the totals."""
    by, stuck = BS._by(T), BS._stuck(T)
    accts, cash, wait = [], -PRICE, 0
    cur = {"kind": "eval", "n": 1, "start": S[0], "trades": 0, "pnl": 0.0, "acc": BS.Eval(EZ, stuck), "keep": []}
    for k, d in enumerate(S):
        if wait:
            wait -= 1
            if not wait:
                cur = {"kind": "funded", "n": cur["n"], "start": S[k + 1] if k + 1 < len(S) else d, "pnl": 0.0,
                       "acc": N.Funded("25k", FZ, stuck), "paid": 0.0, "payouts": 0}
            continue
        acc = cur["acc"]
        if cur["kind"] == "eval":
            r = acc.step(by.get(d, ()), cur["keep"])
            cur["trades"] = len(cur["keep"])
            cur["pnl"] = round(sum(x["pnl"] for x in cur["keep"]), 2)
            if r:
                accts.append({"kind": "eval", "n": cur["n"], "start": cur["start"], "end": d, "sessions": acc.s, "trades": cur["trades"],
                              "pnl": cur["pnl"], "result": {"pass": "PASSED", "fail": "FAILED", "stuck": "STUCK"}[r],
                              "max_qty": max([x["qty"] for x in cur["keep"]] or [0])})
                if r == "pass":
                    wait = GAP
                    cur = {"kind": "wait", "n": cur["n"]}
                else:
                    cash -= PRICE
                    cur = {"kind": "eval", "n": cur["n"] + 1, "start": S[k + 1] if k + 1 < len(S) else d, "trades": 0, "pnl": 0.0,
                           "acc": BS.Eval(EZ, stuck), "keep": []}
        else:
            bal0 = acc.bal
            paid = acc.step(by.get(d, ()))
            cur["pnl"] = round(cur["pnl"] + (acc.bal - bal0) + (paid / 0.8 if paid else 0.0), 2)
            if paid:
                cash += paid
                cur["paid"] += paid
                cur["payouts"] += 1
            if acc.done:
                accts.append({"kind": "funded", "n": cur["n"], "start": cur["start"], "end": d, "sessions": acc.k, "pnl": cur["pnl"],
                              "paid": round(cur["paid"], 2), "payouts": cur["payouts"],
                              "result": {"lost": "LOST", "stuck": "STUCK", "max": "5 PAYOUTS"}[acc.done]})
                cash -= PRICE
                cur = {"kind": "eval", "n": cur["n"] + 1, "start": S[k + 1] if k + 1 < len(S) else d, "trades": 0, "pnl": 0.0,
                       "acc": BS.Eval(EZ, stuck), "keep": []}
    if cur["kind"] == "eval" and cur["acc"].s:
        a = cur["acc"]
        accts.append({"kind": "eval", "n": cur["n"], "start": cur["start"], "end": S[-1], "sessions": a.s, "trades": cur["trades"],
                      "pnl": cur["pnl"], "result": "OPEN", "max_qty": max([x["qty"] for x in cur["keep"]] or [0]),
                      "room": round(a.bal - a.floor, 2), "to_target": round(N.PLANS["25k"]["target"] - a.bal, 2)})
    elif cur["kind"] == "funded":
        a = cur["acc"]
        accts.append({"kind": "funded", "n": cur["n"], "start": cur["start"], "end": S[-1], "sessions": a.k, "pnl": cur["pnl"],
                      "paid": round(cur["paid"], 2), "payouts": cur["payouts"], "result": "OPEN", "balance": round(a.bal, 2),
                      "room": round(a.bal - a.floor, 2)})
    ev = [a for a in accts if a["kind"] == "eval"]
    fu = [a for a in accts if a["kind"] == "funded"]
    bought = len(ev)
    paid = round(sum(a.get("paid", 0.0) for a in fu), 2)
    months_n = len(S) / 21.0
    return {"accounts": accts, "evals_bought": bought, "fees": round(bought * PRICE, 2),
            "passed": sum(1 for a in ev if a["result"] == "PASSED"), "failed": sum(1 for a in ev if a["result"] == "FAILED"),
            "stuck": sum(1 for a in ev if a["result"] == "STUCK"), "open": sum(1 for a in ev if a["result"] == "OPEN"),
            "pass_sessions": [a["sessions"] for a in ev if a["result"] == "PASSED"],
            "funded": len(fu), "payouts": sum(a.get("payouts", 0) for a in fu), "paid_to_owner": paid,
            "net_to_owner": round(paid - bought * PRICE, 2), "per_month": round((paid - bought * PRICE) / months_n),
            "sessions": len(S), "from": S[0], "to": S[-1]}


def main():
    BG.prep()
    TT = K.trades({}, "lit+atlas")
    B1, B5 = N.bars(1), N.bars(5)
    H1, H2, R = N.sessions(B1, "H1"), N.sessions(B1, "H2"), N.sessions(B5, "R")
    Y = H1 + H2
    T1 = [t for t in TT[1] if Y[0] <= t["day"] <= Y[-1]]
    TR = N.span_trades(TT[5], R)
    spans = {"2026 H1": (N.span_trades(T1, H1), H1), "2026 H2": (N.span_trades(T1, H2), H2), "2026": (T1, Y), "2021-25": (TR, R)}
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "rule": "engine/blitz.py VERSION 2 as account C (never opposite LIT / ATLAS)",
           "eval_size": EZ, "funded_size": FZ, "price": PRICE, "data": {"2026": f"{Y[0]}..{Y[-1]} 1m", "2021-25": f"{R[0]}..{R[-1]} 5m"},
           "fixed_150": {}, "eval_every_start": {}, "path": {}, "mc_slot": {}}
    for nm, (T, S) in spans.items():
        out["fixed_150"][nm] = fixed(T, S)
        out["eval_every_start"][nm] = BS.eval_score(T, S, EZ, paths=False)
        print(nm, json.dumps(out["fixed_150"][nm]), json.dumps(out["eval_every_start"][nm]), flush=True)
    out["months_2026"] = months(T1)
    for nm in ("2026", "2026 H1", "2026 H2", "2021-25"):
        T, S = spans[nm]
        p = path(T, S)
        out["path"][nm] = p
        print(nm, "path:", {k: v for k, v in p.items() if k != "accounts"}, flush=True)
    for nm in ("2026 H1", "2026 H2", "2021-25"):
        T, S = spans[nm]
        out["mc_slot"][nm] = BS.life(T, S, EZ, FZ, n=1000)
        print(nm, "mc slot:", out["mc_slot"][nm], flush=True)
    # every 2026 trade at $150 (the dashboard / report list)
    rows = []
    for t in sorted(T1, key=lambda x: x["entry_t"]):
        q = max(1, min(20, int(USD / t["risk_pm"])))
        rows.append([t["day"], int(t["entry_t"]), int(t["exit_t"]), int(t["dir"]), round(t["pnl_pm"] / t["risk_pm"], 3),
                     round(N.trade_pnl(t, q)[0], 2), round(t["risk_pts"], 2), q, t["exit_kind"]])
    out["trade_cols"] = ["day", "entry_t", "exit_t", "dir", "r", "pnl_150", "stop_pts", "qty_150", "exit"]
    out["trades_2026"] = rows
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=lambda o: list(o) if isinstance(o, (set, tuple)) else str(o))
    print("->", os.path.relpath(OUT, ROOT))
    # the run library (tools/runlib.py): every trade at $150, 2021-25 on 5m + 2026 on 1m, as the earlier BLITZ runs
    from tools import runlib as rl
    Ts = M.runlib_trades(TR + T1, USD, 20)
    for t in Ts:
        t["trigger"] = "blitz"
    p26 = out["path"]["2026"]
    e26 = out["eval_every_start"]["2026"]
    f26 = out["fixed_150"]["2026"]
    rl.save("blitz_2026_backtest", "BLITZ: the whole 2026 backtest on its own 25K (live rule, account C, live eval / funded sizes)", "other",
            "Owner 2026-10-30: backtest BLITZ on all of 2026 - trades, profit, evals passed / failed, funded payouts.",
            params={**K.TODAY, "account_c": "never opposite LIT / ATLAS"}, sizing={"fixed_usd": USD, "eval_25k": EZ, "funded_25k": FZ},
            trades=Ts, scored=rl.score(Ts, sorted(set(R) | set(Y))), status="info",
            verdict=(f"2026 at $150 a trade: {f26['n']} trades ({f26['tpw']}/wk, {f26['wk2']}% weeks 2+), win {f26['win']}%, PF {f26['pf']}, "
                     f"net ${f26['net']:,} (${f26['per_month']}/mo), DD ${f26['dd']:,}. 25K eval on every 2026 start: 2-week pass / fail "
                     f"{e26['p10']} / {e26['f10']}, decided {e26['dec10']}%, median {e26['pass_med']} sessions to pass. Calendar path from "
                     f"{p26['from']}: {p26['evals_bought']} evals bought, {p26['passed']} passed, {p26['failed']} failed, {p26['stuck']} stuck, "
                     f"{p26['payouts']} payouts, ${p26['paid_to_owner']:,} paid, net ${p26['net_to_owner']:,} after fees."),
            notes="tools/blitz_2026_backtest.py; research/scalp/blitz_2026_backtest.json", writeup="blitz-2026-backtest",
            tags=["scalp", "blitz", "account_c", "25k", "2026"])
    print("-> run blitz_2026_backtest")


if __name__ == "__main__":
    main()
