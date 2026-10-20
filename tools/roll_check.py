"""Contract-roll check for the PC bot (run it on the PC after switching the NinjaTrader chart, and any day in roll week).

    python tools/roll_check.py                 # reads NinjaTrader's le_feed files, data/nt_bars and data/NQ_5m.csv
    python tools/roll_check.py --folder "D:\\NinjaTrader 8"

It answers, in plain words:
  1. Which contract the bot sends orders to today (engine/ninjatrader.nt_instrument: MNQ 12-26 until Wed 2026-12-09,
     MNQ 03-27 from Thu 2026-12-10) and which contract the chart's bars are on (worked out from the price basis: the
     TradingView history is anchored on the contract in data/NQ_rolls.json; the NinjaTrader archive and the chart file
     either sit on that basis, 0 pts, or one roll gap (~1%) away).
  2. Whether NinjaTrader's own history has a contract jump inside it (a ~1% jump at an 18:00 weekday open or inside a
     session): then NinjaTrader's merge policy is not "Merge back adjusted" (Tools > Options > Market data), and the bot
     cannot repair it (its levels would be ~300 pts off for weeks).
  3. How far the bot will shift the older bars (the roll gap it detected), as a sanity number (200-350 pts for NQ in 2026).
Verdict OK / ACTION lines at the end; exit code 1 when an ACTION is needed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import pcbars  # noqa: E402

JUMP_PCT = 0.006               # a 0.6% bar-to-bar jump (NQ ~150+ pts; a roll is ~1%) in roll week = a contract switch


def contract_name(code: str | None, root: str = "MNQ") -> str | None:
    """'NQZ26' -> 'MNQ 12-26'."""
    if not code:
        return None
    m = {"H": 3, "M": 6, "U": 9, "Z": 12}[code[-3]]
    return f"{root} {m:02d}-{code[-2:]}"


def next_name(name: str | None) -> str | None:
    """'MNQ 12-26' -> 'MNQ 03-27'."""
    if not name:
        return None
    root, my = name.split(" ")
    m, y = int(my[:2]), int(my[3:])
    m, y = (m + 3, y) if m < 12 else (3, y + 1)
    return f"{root} {m:02d}-{y:02d}"


def in_roll_window(day: dt.date) -> bool:
    """From 12 days before a quarterly expiry (3rd Friday of Mar / Jun / Sep / Dec) to the day after it."""
    if day.month not in (3, 6, 9, 12):
        return False
    d15 = dt.date(day.year, day.month, 15)
    tf = d15 + dt.timedelta(days=(4 - d15.weekday()) % 7)
    return tf - dt.timedelta(days=12) <= day <= tf + dt.timedelta(days=1)


def jumps(df: pd.DataFrame, pct: float = JUMP_PCT):
    """Contract jumps inside a bar file: |open - previous close| >= pct of the price in a roll window (12 days before a
    quarterly expiry to the day after), at a weekday 18:00 open or inside a session. Sunday / holiday re-opens are left
    out (weekend news moves NQ that much), and so is everything outside roll windows (after-hours news moves NQ at an
    18:00 open: data/NQ_5m.csv 2021-10 -> 2026-10 has 4 weekday jumps >= 0.6%, none in a roll window). Returns
    [(time, jump)]."""
    df = pcbars.tidy(df)
    if len(df) < 2:
        return []
    t = df["time"].to_numpy()
    o, c = df["open"].to_numpy(), df["close"].to_numpy()
    d = o[1:] - c[:-1]
    gap_s = t[1:] - t[:-1]
    et = pd.to_datetime(t[1:], unit="s", utc=True).tz_convert("America/New_York")
    sunday_open = (et.weekday == 6) | (gap_s > 30 * 3600)          # weekend / holiday re-open
    big = np.abs(d) >= pct * np.abs(c[:-1])
    ix = [i for i in np.flatnonzero(big & ~sunday_open) if in_roll_window((et[i] + pd.Timedelta(hours=6)).date())]
    return [(int(t[i + 1]), float(d[i])) for i in ix]


def diagnose(tv5, arc5, feed5, today: dt.date, anchor: str | None, order_name: str | None = None) -> dict:
    """The roll check on frames (testable). tv5 = data/NQ_5m.csv, arc5 = data/nt_bars/NQ_5m.csv, feed5 = LE_BarFeed's
    MNQ_5m.csv, anchor = the TradingView files' contract (NQ_rolls.json "anchor"). Returns {lines, actions, chart, order}."""
    from engine.ninjatrader import nt_instrument
    order = order_name or nt_instrument("MNQ", today)
    tv_c = contract_name(anchor)
    lines, actions = [], []
    lines.append(f"Orders go to: {order} (today {today:%a %Y-%m-%d}; the bot switches by itself 8 days before expiry)")
    s_tv_arc = pcbars.basis_shift(tv5, arc5) if len(arc5) else 0.0
    s_arc_feed = pcbars.basis_shift(arc5, feed5) if len(arc5) and len(feed5) else 0.0
    s_tv_feed = pcbars.basis_shift(tv5, feed5) if len(feed5) else 0.0
    # the chart's contract from the basis chain TradingView -> archive -> chart file
    def _ov(x, y):
        return len(x) and len(y) and len(x[["time"]].merge(y[["time"]], on="time")) >= 20

    if _ov(tv5, arc5) and _ov(arc5, feed5):
        chain, known = s_tv_arc + s_arc_feed, True
    elif _ov(tv5, feed5):
        chain, known = s_tv_feed, True
    else:
        chain, known = 0.0, False
    feed_jumps = jumps(feed5.tail(40 * 288)) if len(feed5) else []
    if not len(feed5):
        chart = None
        actions.append("no LE_BarFeed MNQ_5m.csv: is NinjaTrader running with the LE_BarFeed chart? (FEED STALE blocks entries)")
    elif feed_jumps:
        chart = None
        lines.append("Chart contract: unknown (its history jumps from one contract to the other, see below)")
    elif not known:
        chart = None
        lines.append("Chart contract: unknown (the files share no bars: let the bot run one poll, or load 30 days on the chart)")
    elif abs(chain) < pcbars.ROLL_MIN:
        chart = tv_c
    else:
        chart = next_name(tv_c)
    if chart:
        lines.append(f"Chart bars are on: {chart}" + (f" (TradingView history {tv_c} + one roll, {chain:+.2f} pts)" if chart != tv_c
                                                       else f" (same basis as the TradingView history, {tv_c})"))
        if chart != order and chart == next_name(order) and nt_instrument("MNQ", today + dt.timedelta(days=1)) == chart:
            lines.append(f"Orders switch to {chart} by themselves at midnight ET: the chart is already there (good, the "
                         "evening before is the right time)")
        elif chart != order:
            actions.append(f"the chart is on {chart} but orders go to {order}: switch the NinjaTrader chart to {order} "
                           "(then save the workspace)")
    for nm, df in (("NinjaTrader chart file", feed5), ("NinjaTrader archive (data/nt_bars)", arc5)):
        js = jumps(df.tail(40 * 288)) if len(df) else []
        if js:
            t, j = js[-1]
            actions.append(f"{nm} has a contract jump of {j:+.2f} pts at "
                           f"{pd.Timestamp(t, unit='s', tz='UTC').tz_convert('America/New_York'):%a %m-%d %H:%M} ET: NinjaTrader "
                           "is not merging back-adjusted (Tools > Options > Market data > Merge policy = Merge back adjusted), "
                           "then reload the chart (and delete data/nt_bars/NQ_*.csv so the bot rebuilds its archive)")
    if len(arc5) and s_arc_feed:
        lines.append(f"The bot will shift its archive by {s_arc_feed:+.2f} pts onto the chart's contract on its next poll")
    if s_tv_arc or (not len(arc5) and s_tv_feed):
        sh = s_tv_arc or s_tv_feed
        lines.append(f"TradingView history ({tv_c}) is shifted {sh:+.2f} pts onto NinjaTrader's contract by the bot"
                     + ("" if 150 <= abs(sh) <= 400 else "  <- unusual size, check"))
        if not 150 <= abs(sh) <= 400:
            actions.append(f"the roll gap {sh:+.2f} pts is outside 150-400 pts: check the chart contract")
    return {"lines": lines, "actions": actions, "chart": chart, "order": order}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python tools/roll_check.py")
    ap.add_argument("--folder", default=None, help="Documents\\NinjaTrader 8 (default: found by engine/ninjatrader.py)")
    ap.add_argument("--data", default=os.path.join(ROOT, "data"))
    a = ap.parse_args(argv)
    from engine import ninjatrader as nt
    folder = a.folder or nt.default_folder()
    feeder = nt.NinjaTraderBars(folder=folder)
    feed_p = feeder.file_for("NQ", 5)
    feed5 = pcbars.tidy(feeder.load(feed_p)) if feed_p else pcbars.tidy(None)
    tv5 = pcbars.tidy(pd.read_csv(os.path.join(a.data, "NQ_5m.csv")))
    arc5 = pcbars.archive_read("NQ", "5m", os.path.join(a.data, "nt_bars"))
    anchor = None
    try:
        anchor = json.load(open(os.path.join(a.data, "NQ_rolls.json"), encoding="utf-8")).get("anchor")
    except Exception:
        pass
    r = diagnose(tv5, arc5, feed5, dt.datetime.now(nt.ET).date(), anchor)
    print("\n".join(r["lines"]))
    if r["actions"]:
        print("\nACTION:")
        for x in r["actions"]:
            print("  - " + x)
        return 1
    print("\nOK: chart, orders and history are on one contract (or the bot shifts them onto it).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
