"""LIT adopt-candidates on the PC route: the 15-minute check (t_check) and breakeven at entry + 1.25 (be_off), replayed
through the PC paper bot (engine/live.py LiveBot, model LIT, paper adapter with route_stop_moves) on 2026 sessions, with
a clock that runs on during each poll (tests/test_lit_timing.py). Both options stay OFF in live_model.json; this proves the
route does what the backtest does once they are switched on.

    python -X utf8 -m tests.test_lit_exit_route              # 13 CUT_T15 trades + 6 breakeven trades (~4 min, one process)
    python -X utf8 -m tests.test_lit_exit_route --only=2026-01-13,2026-03-04

Checks per trade (backtest = tools/lit_final.py run on the 2026 sessions = engine/lit.py run_x, the same code as run lit_live):
  t_check  the exit is routed (reason CUT_T15) <= LIMIT_S after the close of the 15-minute check bar, i.e. at the open of
           the backtest's exit bar (the backtest exits at that open - 1 tick), with the backtest's exit time, and the routed
           P&L equals the backtest's at the routed size (the price comes from the forming bar's open, as the entry does).
  be_off   the breakeven CHANGE is routed <= LIMIT_S after the close of the 1m bar that reached +1R, at exactly
           entry + 1.25 pts (long) / entry - 1.25 (short) on the tick grid = the backtest's breakeven stop; the BE exit
           P&L equals the backtest's.
Why the cut used to look late: before this fix the live loop priced the cut from the check bar's close (the ledger's exit
price / P&L was an estimate) and reported its exit one bar early; the cut itself was already routed on the check bar's
close (2-3 s) on all 13 trades. Exact now: research/writeups/lit-live-fills.md "Exits on the route".
Writes research/lit/live_exit_route.json.
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from engine import live  # noqa: E402
from tests.test_lit_timing import Clock, hm  # noqa: E402

LIMIT_S = 10.0
T15 = {"at": 15, "x": 0.3, "mfe": 0.5}
BE_OFF = 1.25
OUT = os.path.join(ROOT, "research", "lit", "live_exit_route.json")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""), flush=True)
    return bool(ok)


def live_lit():
    """The live LIT params with the three upgrades stripped, so each one is replayed on its own (they are switched on
    together in live_model.json since 2026-10-20; tests.test_lit_live checks the combination)."""
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    return {k: v for k, v in P.items() if k not in ("t_check", "scale_in", "be_off")}


def backtest(P, days=None):
    """The 2026 backtest trades of P (all 2026 sessions, so the weekly stop sees the whole week), optionally only `days`."""
    from tools import lit_final as F
    S26 = [d for d in F.SESS if d >= "2026-01-01"]
    T = F.run(P, S26)
    return [t for t in T if not days or t["day"] in days]


def be_close_t(t, b1):
    """Close time of the 1m bar whose high (long) / low (short) first reaches the fill + 1R (the backtest's breakeven bar)."""
    d = int(t["dir"])
    k = int(np.searchsorted(b1.t, int(t["entry_t"])))
    e_d = float(t["entry_px"]) * d
    hi_d = b1.h if d == 1 else -b1.l
    k += 1 if t.get("limit_fill") else 0
    while k < len(b1.t) and float(hi_d[k]) < e_d + float(t["risk_pts"]):
        k += 1
    return int(b1.t[k]) + 60 if k < len(b1.t) else None


class Harness:
    """LiveBot (paper adapter, route_stop_moves on) driven on its own minute-aligned schedule over chosen windows."""

    def __init__(self, P, t_from):
        from tests.test_live_dryrun import Replay
        os.environ["LE_LIVE_MODEL"] = json.dumps({"model": "lit", "sym": "NQ", "label": "LIT route test", "lit": P,
                                                  "params": {"risk_usd": 800, "risk_ref_stop": 20.0, "max_micros": 40}})
        self.rp = rp = Replay()
        df1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
        rp.frames[("NQ", "1m")] = df1[df1["time"] >= t_from - 70 * 86400].reset_index(drop=True)
        self.o1 = o1 = dict(zip(df1["time"].astype("int64"), df1["open"].astype(float)))
        self.clock = clock = Clock()

        def forming_1m(sym, interval, period="5d"):
            t = int(clock()) - int(clock()) % 60
            if sym == "NQ" and interval == "1m" and t in o1:
                return pd.DataFrame([{"time": t, "open": o1[t], "high": o1[t], "low": o1[t], "close": o1[t], "volume": 0.0}])
            return pd.DataFrame()
        rp.recent_hook = forming_1m
        rp.install_globals()

    def run(self, windows):
        """One fresh bot over the merged windows [(a, z)]; returns it (ledger, log)."""
        rp, clock = self.rp, self.clock
        windows = sorted(windows)
        merged = []
        for a, z in windows:
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], z))
            else:
                merged.append((a, z))
        bot = rp.bot(start_now=merged[0][0] - 60)
        bot.clock = clock
        bot._remember = lambda *a_, **kw: None
        bot.adapter.route_stop_moves = True          # paper adapter: also route the breakeven CHANGE (as NinjaTrader does)
        bot.errors_seen = []
        for a, z in merged:
            wake = live.next_wake(a)
            while wake <= z:
                rp.now = int(wake)
                clock.base, clock.t0, clock.running = wake, time.perf_counter(), True
                try:
                    bot.poll_once()
                except Exception as e:
                    bot.errors_seen.append(f"{hm(wake)} {e.__class__.__name__}: {e}")
                clock.running = False
                clock.base = wake
                wake = live.next_wake(wake)
        return bot

    def close(self):
        self.rp.cleanup()
        os.environ.pop("LE_LIVE_MODEL", None)


def rows_for(bot, ent):
    led = [r for r in bot.ledger if r.get("entry_t") == ent]
    return (next((r for r in led if r["side"] in ("buy", "sell")), None), [r for r in led if r["side"] == "modify"],
            [r for r in led if r["side"] == "add"], next((r for r in led if r["side"] == "exit"), None))


def t_check_part(only=None):
    print("== 1. 15-minute check (t_check) on the PC route", flush=True)
    P = {**live_lit(), "t_check": T15}
    T = [t for t in backtest(P, only) if t["exit"] == "CUT_T15"]
    H = Harness(P, min(t["entry_t"] for t in T))
    out = []
    try:
        for t in T:
            ent, xt = int(t["entry_t"]), int(t["exit_t"])
            chk_close = xt - 60                    # the check bar closes at the open of the backtest's exit bar
            bot = H.run([(ent - 360, ent + 40), (chk_close - 90, chk_close + 40)])
            e_row, _, _, x_row = rows_for(bot, ent)
            q = int(e_row["qty"]) if e_row else None
            want = round(t["pnl"] * q / t["qty"], 2) if q else None
            r = {"day": t["day"], "dir": t["dir"], "entry": hm(ent), "check_close": hm(chk_close), "bt_exit_t": hm(xt),
                 "bt_exit_px": t.get("exit_px"), "bt_pnl": t["pnl"], "qty_bt": t["qty"], "qty_routed": q,
                 "routed_t": hm(x_row["t"]) if x_row else None, "delay_s": (x_row["t"] - chk_close) if x_row else None,
                 "reason": x_row and x_row.get("reason"), "routed_exit_t": hm(x_row["exit_t"]) if x_row and x_row.get("exit_t") else None,
                 "routed_pnl": x_row and x_row.get("pnl"), "want_pnl": want, "errors": bot.errors_seen[:2]}
            ok = x_row is not None and r["reason"] == "CUT_T15" and 0 <= r["delay_s"] <= LIMIT_S and int(x_row["exit_t"]) == xt \
                and q == int(t["qty"]) and abs(float(x_row["pnl"]) - want) < 0.01
            r["ok"] = ok
            out.append(r)
            check(f"{t['day']}: CUT_T15 routed {r['delay_s']} s after the check bar closed, exit time / P&L = backtest",
                  ok, "" if ok else json.dumps(r))
    finally:
        H.close()
    return out


def be_off_part(only=None, n=6):
    print(f"== 2. breakeven at entry + {BE_OFF} pts (be_off) on the PC route", flush=True)
    from engine.data import load, load_ltf
    P = {**live_lit(), "be_off": BE_OFF}
    T = [t for t in backtest(P, only) if t["exit"] == "BE" and t.get("tf") == 1]
    if not only:                                   # spread over the year, longs and shorts
        T = [T[i] for i in sorted(set(np.linspace(0, len(T) - 1, n).round().astype(int)))]
    b1, _ = load_ltf("NQ", load("NQ", "5m"))
    H = Harness(P, min(t["entry_t"] for t in T))
    out = []
    try:
        for t in T:
            d, ent, xt = int(t["dir"]), int(t["entry_t"]), int(t["exit_t"])
            bc = be_close_t(t, b1)
            bot = H.run([(ent - 360, ent + 40), (bc - 90, bc + 40), (xt - 60, xt + 40)])
            e_row, m_rows, _, x_row = rows_for(bot, ent)
            want_stop = live.tick_px(float(t["entry_px"]) + d * BE_OFF, d)
            m = m_rows[0] if m_rows else None
            q = int(e_row["qty"]) if e_row else None
            want = round(t["pnl"] * q / t["qty"], 2) if q else None
            r = {"day": t["day"], "dir": d, "entry_px": t["entry_px"], "be_bar_close": hm(bc), "want_stop": want_stop,
                 "routed_stop": m and m["stop"], "be_routed": hm(m["t"]) if m else None, "be_delay_s": (m["t"] - bc) if m else None,
                 "modifies": len(m_rows), "bt_pnl": t["pnl"], "routed_pnl": x_row and x_row.get("pnl"), "want_pnl": want,
                 "exit_reason": x_row and x_row.get("reason"), "errors": bot.errors_seen[:2]}
            ok = m is not None and abs(float(m["stop"]) - want_stop) < 1e-9 and 0 <= r["be_delay_s"] <= LIMIT_S and len(m_rows) == 1 \
                and x_row is not None and r["exit_reason"] == "BE" and abs(float(x_row["pnl"]) - want) < 0.01
            r["ok"] = ok
            out.append(r)
            check(f"{t['day']} {'long' if d == 1 else 'short'}: breakeven CHANGE to {want_stop} (entry {'+' if d == 1 else '-'} "
                  f"{BE_OFF}) routed {r['be_delay_s']} s after the +1R bar closed; BE exit P&L = backtest", ok, "" if ok else json.dumps(r))
    finally:
        H.close()
    return out


def main():
    only = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)
    t0 = time.time()
    res = {"limit_s": LIMIT_S, "t_check": T15, "be_off": BE_OFF}
    res["t_check_rows"] = t_check_part(only)
    res["be_off_rows"] = be_off_part(only)
    n_ok = sum(ok for _, ok in RESULTS)
    res.update(passed=n_ok, checks=len(RESULTS), seconds=round(time.time() - t0))
    if not only:
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)
    print(f"{n_ok}/{len(RESULTS)} checks passed in {res['seconds']} s" + ("" if only else f" -> {os.path.relpath(OUT, ROOT)}"))
    sys.exit(0 if n_ok == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
