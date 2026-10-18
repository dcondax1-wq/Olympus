"""LIT live timing check (research/writeups/lit-live-fills.md, recommendation 1): with a fake clock, how many seconds after the
backtest's moment does the PC paper bot (engine/live.py LiveBot + PaperAdapter, LIT model) send each order?

    python -X utf8 -m tests.test_lit_timing

  1. Units: the poll schedule (engine/live.next_wake: 2 s and 32 s after each minute boundary, LiveBot._sleep_s), a bar counts
     as closed only once its end time has passed (live.clean_bars), the forming bar's open (live.forming_open).
  2. Replays: the bot is driven by its own aligned schedule on 2026 trade days, with a clock that runs on during each poll (the
     real compute time is in the route times). Bars appear as they close; the 1m feed shows the minute that has just started
     (its open), as Yahoo / LE_BarFeed do. Checks:
       entry  route time - the 1m CISD candle's close (= the backtest's fill-bar open)            <= 10 s
       BE     route time of the stop CHANGE - the close of the 1m bar that reached +1R            <= 10 s
       EOD    route time of the 15:55 TIME exit - the close of the 15:55 1m bar (the model's exit) <= 10 s
     and every routed entry is the backtest's (side, micros, stop, target).
Days: 2026-01-02 (BE; the CISD closes inside the 5m bar after the trigger, the "early" path), 2026-04-29 (BE; sizing from the
forming bar's open: from the CISD close it would be 23 micros instead of 27), 2026-09-30 (15:55 EOD exit). One process, ~2 min.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from engine import live  # noqa: E402
from engine.data import load, load_ltf  # noqa: E402

ET = ZoneInfo("America/New_York")
LIMIT_S = 10.0
DAYS = ("2026-01-02", "2026-04-29", "2026-09-30")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""), flush=True)


def et_at(day, hh, mm):
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(hh, mm), ET).timestamp())


def hm(t):
    return dt.datetime.fromtimestamp(int(t), ET).strftime("%H:%M:%S")


def units():
    print("== 1. poll schedule, closed bars, forming bar")
    nw = [live.next_wake(x) for x in (960.0, 961.9, 962.0, 980.0, 992.0, 1019.9)]
    check("next_wake: 2 s and 32 s after each minute boundary", nw == [962.0, 962.0, 992.0, 992.0, 1022.0, 1022.0], str(nw))
    b = live.LiveBot()
    clk = [1000.5]
    b.clock = lambda: clk[0]
    b.cfg = {**live.LIVE_DEFAULTS}
    s1 = b._sleep_s()
    b.cfg = {**live.LIVE_DEFAULTS, "poll_sec": 0.01}
    s2 = b._sleep_s()
    b.cfg = {**live.LIVE_DEFAULTS, "poll_align": False}
    s3 = b._sleep_s()
    check("LiveBot._sleep_s: aligned by default (1000.5 -> 1022), plain poll_sec for harnesses / poll_align false",
          abs(s1 - 21.5) < 1e-9 and s2 == 0.01 and s3 == 60, f"{s1} {s2} {s3}")
    df = pd.DataFrame({"time": [0, 60, 120], "open": [1.0, 2, 3], "high": [1.0, 2, 3], "low": [1.0, 2, 3], "close": [1.0, 2, 3],
                       "volume": [1.0, 1, 1]})
    n_at = [len(live.clean_bars(df, 60, now)[0]) for now in (179, 180, 181)]
    check("clean_bars: the 02:00 bar counts as closed from 02:01:00 on (end time passed), only the forming bar is dropped",
          n_at == [2, 3, 3], str(n_at))
    check("forming_open: the open of the minute still forming, None once it has closed",
          live.forming_open(df, 60, 179) == (120, 3.0) and live.forming_open(df, 60, 180) is None)


class Clock:
    """Fake wall clock: frozen at the wake time between polls, running on (real elapsed time) during a poll."""

    def __init__(self):
        self.base, self.t0, self.running = 0.0, 0.0, False

    def __call__(self):
        return self.base + ((time.perf_counter() - self.t0) if self.running else 0.0)


def replay(P, trades):
    from tests.test_live_dryrun import Replay
    from engine.live import tick_px
    os.environ["LE_LIVE_MODEL"] = json.dumps({"model": "lit", "sym": "NQ", "label": "LIT timing", "lit": P,
                                              "params": {"risk_usd": 800, "risk_ref_stop": 20.0, "max_micros": 40}})
    rp = Replay()
    df1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    rp.frames[("NQ", "1m")] = df1[df1["time"] >= min(t["entry_t"] for t in trades) - 70 * 86400].reset_index(drop=True)
    o1 = dict(zip(df1["time"].astype("int64"), df1["open"].astype(float)))
    clock = Clock()

    def forming_1m(sym, interval, period="5d"):
        t = int(clock()) - int(clock()) % 60
        if sym == "NQ" and interval == "1m" and t in o1:
            return pd.DataFrame([{"time": t, "open": o1[t], "high": o1[t], "low": o1[t], "close": o1[t], "volume": 0.0}])
        return pd.DataFrame()
    rp.recent_hook = forming_1m
    rp.install_globals()
    b1, _ = load_ltf("NQ", load("NQ", "5m"))
    rows = []
    try:
        for t in trades:
            d, ent = int(t["dir"]), int(t["entry_t"])
            # the backtest's breakeven bar: the first 1m bar from the fill whose high (long) reaches the fill + 1R
            k0 = int(np.searchsorted(b1.t, ent))
            e_d = float(b1.o[k0]) * d + 0.25
            hi_d = b1.h if d == 1 else -b1.l
            be_close = None
            if t["exit"] == "BE":
                k = k0
                while k < len(b1.t) and float(hi_d[k]) < e_d + float(t["risk_pts"]):
                    k += 1
                be_close = int(b1.t[k]) + 60
            windows = [(ent - 360, ent + 180)]
            if be_close:
                windows = [(ent - 360, be_close + 120)]
            if t["exit"] == "EOD":
                windows.append((et_at(t["day"], 15, 52), et_at(t["day"], 15, 58)))
            bot = rp.bot(start_now=windows[0][0] - 60)
            bot.clock = clock
            bot.adapter.route_stop_moves = True          # paper adapter: also route the breakeven CHANGE (as NinjaTrader does)
            polls, ms = 0, []
            for a, z in windows:
                wake = live.next_wake(a)
                while wake <= z:
                    rp.now = int(wake)
                    clock.base, clock.t0, clock.running = wake, time.perf_counter(), True
                    try:
                        bot.poll_once()
                    except Exception as e:
                        print("    poll failed", hm(wake), e)
                    clock.running = False
                    ms.append(bot.health.get("poll_ms") or 0)
                    polls += 1
                    clock.base = wake
                    wake = live.next_wake(wake)
            led = bot.ledger
            e_row = next((r for r in led if r["side"] in ("buy", "sell") and int(r["entry_t"]) == ent), None)
            m_row = next((r for r in led if r["side"] == "modify" and int(r["entry_t"]) == ent), None)
            x_row = next((r for r in led if r["side"] == "exit" and int(r["entry_t"]) == ent), None)
            want_side = "buy" if d == 1 else "sell"
            same = e_row is not None and e_row["side"] == want_side and int(e_row["qty"]) == int(t["qty"]) \
                and abs(e_row["stop"] - tick_px(t["stop_px"], d)) < 1e-6 and abs(e_row["target"] - tick_px(t["target_px"], d, target=True)) < 1e-6
            r = {"day": t["day"], "exit": t["exit"], "polls": polls, "poll_ms_mean": int(np.mean(ms)) if ms else None,
                 "entry_close": hm(ent), "entry_routed": hm(e_row["t"]) if e_row else None,
                 "entry_delay_s": (e_row["t"] - ent) if e_row else None, "entry_same_as_backtest": same,
                 "be_bar_close": hm(be_close) if be_close else None, "be_routed": hm(m_row["t"]) if m_row else None,
                 "be_delay_s": (m_row["t"] - be_close) if (m_row and be_close) else None,
                 "eod_exit": hm(t["exit_t"]) if t["exit"] == "EOD" else None,
                 "eod_delay_s": (x_row["t"] - int(t["exit_t"])) if (x_row and t["exit"] == "EOD") else None,
                 "log": [x["text"] for x in list(bot.log) if "MARKET entry sent" in x["text"] or "micros sized" in x["text"]][:3]}
            rows.append(r)
            print("   ", json.dumps(r), flush=True)
    finally:
        rp.cleanup()
        os.environ.pop("LE_LIVE_MODEL", None)
    return rows


def main():
    units()
    print("== 2. LiveBot on LIT with its own aligned poll schedule and a running clock")
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    from tools import lit_final as F
    T = {t["day"]: t for t in F.run(P) if t["day"] in DAYS}
    rows = replay(P, [T[d] for d in DAYS])
    for r in rows:
        check(f"{r['day']}: entry routed <= {LIMIT_S:g} s after the 1m CISD close and identical to the backtest's",
              r["entry_delay_s"] is not None and 0 <= r["entry_delay_s"] <= LIMIT_S and r["entry_same_as_backtest"],
              f"{r['entry_close']} -> {r['entry_routed']} ({r['entry_delay_s']} s)")
        if r["exit"] == "BE":
            check(f"{r['day']}: breakeven CHANGE routed <= {LIMIT_S:g} s after the +1R bar closed",
                  r["be_delay_s"] is not None and 0 <= r["be_delay_s"] <= LIMIT_S, f"{r['be_bar_close']} -> {r['be_routed']} ({r['be_delay_s']} s)")
        if r["exit"] == "EOD":
            check(f"{r['day']}: 15:55 TIME exit routed <= {LIMIT_S:g} s after the 15:55 bar closed",
                  r["eod_delay_s"] is not None and 0 <= r["eod_delay_s"] <= LIMIT_S, f"{r['eod_exit']} ({r['eod_delay_s']} s)")
    out = os.path.join(ROOT, "research", "lit", "live_timing.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"limit_s": LIMIT_S, "days": rows}, fh, indent=1)
    n_ok = sum(ok for _, ok in RESULTS)
    print(f"{n_ok}/{len(RESULTS)} checks passed -> {os.path.relpath(out, ROOT)}")
    sys.exit(0 if n_ok == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
