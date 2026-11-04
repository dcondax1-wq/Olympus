"""ATHENA 'Read the chart' drills (tools/web_public/athena/drills.json, 2026-11-04): 10 setups for the Train tab, built offline from REAL replayed data.

  7 of the 10 are real LIT replay trades (research/lab/backtest_live.json, the live settings), 3 are real days on which the replay took no trade.
  Each one carries the 5m candles of the real day (data/NQ_5m.csv, TradingView CME NQ1!), in integer quarter-points like research/lab/replays.json.
  The owner sees the candles up to the moment the bot decided, answers "does the bot take this?" and "where is the stop?", then sees the rest.

    python tools/athena_drills.py            (writes tools/web_public/athena/drills.json)
    python tools/athena_drills.py --check    (exit 1 when the committed file is stale; exit 0 and a note when the sources are not on this machine)

Deterministic: a fixed seed, no clock. Nothing is invented: the entry, stop, target, exit and $ are the replay's own numbers, the "why" lines are the
trade's own report (engine/lit.py), and the stop choices are three plain alternatives computed from the entry and the real stop.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import random
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BT = os.path.join(ROOT, "research", "lab", "backtest_live.json")
BARS = os.path.join(ROOT, "data", "NQ_5m.csv")
OUT = os.path.join(ROOT, "tools", "web_public", "athena", "drills.json")
ET = ZoneInfo("America/New_York")
SEED = 20261104
PATTERN = "YNYYNYYNYY"                       # 7 trades, 3 flat days, mixed so no long run of one answer
WANT = ["TARGET", "TARGET", "STOP", "STOP", "BE", "TARGET", "CUT_T15"]          # the mix of the 7 trades (the outcome of each, so the owner sees wins, losses and breakeven)
LOOKBACK = 36                                # 5m bars (3 hours) shown before the decision
MAX_AFTER = 72                               # at most 6 hours of reveal


def q4(x: float) -> int:
    return int(round(float(x) * 4))


def load_bars(days: set[str]) -> dict[str, list]:
    """5m bars (epoch, o, h, l, c) of the wanted ET days plus the day before (the London / Asia part of a 02:00 entry starts the evening before)"""
    want = set()
    for d in days:
        t = dt.date.fromisoformat(d)
        want.add(d)
        want.add((t - dt.timedelta(days=1)).isoformat())
        want.add((t - dt.timedelta(days=2)).isoformat())
        want.add((t - dt.timedelta(days=3)).isoformat())
    out: dict[str, list] = {}
    with open(BARS, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            t = int(float(row["time"]))
            d = dt.datetime.fromtimestamp(t, ET).strftime("%Y-%m-%d")
            if d in want:
                out.setdefault(d, []).append((t, float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])))
    return out


def window(bars_by_day: dict, t_end: int, t_from: int, t_to: int) -> list:
    """the bars with open time in [t_from, t_to), from the days loaded (sorted)"""
    allb = sorted(b for v in bars_by_day.values() for b in v)
    return [b for b in allb if t_from <= b[0] < t_to]


def clean(bars: list) -> bool:
    """continuous 5m bars, no roll gap (a jump of more than 2% between bars means a contract change inside the window)"""
    if len(bars) < LOOKBACK:
        return False
    for a, b in zip(bars, bars[1:]):
        if b[0] - a[0] > 3600 or abs(b[1] - a[4]) / a[4] > 0.02:
            return False
    return True


KINDS = ["real", "tight", "wide", "fixed"]


def stop_choices(side: str, entry: float, stop: float, rng: random.Random) -> tuple[list[int], int, list[str]]:
    """4 stops to pick from: the real one and three plain alternatives on the same side. -> (prices in quarter-points, index of the real one, the kind of each)"""
    risk = abs(entry - stop)
    sgn = -1 if side == "LONG" else 1
    fixed = 10.0 if risk >= 18 else 30.0                      # "a fixed distance", far from the real one
    alts = [entry + sgn * risk * 0.4, entry + sgn * risk * 2.0, entry + sgn * fixed]
    prices = [stop] + [round(a * 4) / 4 for a in alts]
    # keep them apart (at least 2 points between any two), else widen the odd one
    for i in range(1, 4):
        while any(abs(prices[i] - prices[j]) < max(2.0, 0.15 * risk) for j in range(i)):
            prices[i] = round((prices[i] + sgn * max(2.0, 0.25 * risk)) * 4) / 4
    order = list(range(4))
    rng.shuffle(order)
    shuffled = [prices[k] for k in order]
    return [q4(p) for p in shuffled], order.index(0), [KINDS[k] for k in order]


def trade_drill(t: dict, bars_by_day: dict, rng: random.Random) -> dict | None:
    et, xt = int(t["entry_t"]), int(t["exit_t"])
    t_from = (et // 300) * 300 - LOOKBACK * 300
    bars = window(bars_by_day, et, t_from, xt + 1800)
    # the bars known at the decision: those that CLOSED by the entry time
    known = [b for b in bars if b[0] + 300 <= et]
    if len(known) < LOOKBACK or not clean(bars):
        return None
    known = known[-LOOKBACK:]
    start = known[0][0]
    shown = [b for b in bars if b[0] >= start][:LOOKBACK + MAX_AFTER]
    if shown[-1][0] + 300 < xt:                                    # the exit is off the end of the reveal
        return None
    n_known = LOOKBACK
    xi = max(i for i, b in enumerate(shown) if b[0] <= xt)
    stops, ans, kinds = stop_choices(t["side"], t["entry"], t["stop"], rng)
    e = dt.datetime.fromtimestamp(et, ET)
    x = dt.datetime.fromtimestamp(xt, ET)
    return {
        "id": f"{t['day']}_{e.strftime('%H%M')}_{t['side'].lower()}", "day": t["day"], "take": True, "side": t["side"],
        "t0": start,
        "m0": dt.datetime.fromtimestamp(start, ET).hour * 60 + dt.datetime.fromtimestamp(start, ET).minute, "n_known": n_known,
        "o": [q4(b[1]) for b in shown], "h": [q4(b[2]) for b in shown], "l": [q4(b[3]) for b in shown], "c": [q4(b[4]) for b in shown],
        "entry_i": n_known, "exit_i": xi, "entry_time": e.strftime("%H:%M"), "exit_time": x.strftime("%H:%M"),
        "entry": q4(t["entry"]), "stop": q4(t["stop"]), "target": q4(t["target"]), "exit_price": q4(t["exit_price"]), "exit": t["exit"],
        "sweep_ext": q4(t["sweep_ext"]), "stops": stops, "answer": ans, "kinds": kinds,
        "risk_pts": t["risk_pts"], "qty": t["qty"], "risk_usd": t["risk_usd"], "r": t["r"], "pnl": t["pnl"],
        "pools": list(t.get("pools") or [])[:4], "why": list((t.get("report") or {}).get("why") or [])[:3],
    }


def flat_drill(day: str, minute: int, bars_by_day: dict) -> dict | None:
    d0 = dt.datetime.combine(dt.date.fromisoformat(day), dt.time(0, 0), tzinfo=ET)
    cut = int((d0 + dt.timedelta(minutes=minute - minute % 5)).timestamp())
    t_from = cut - LOOKBACK * 300
    end = int((d0 + dt.timedelta(minutes=15 * 60 + 30)).timestamp())
    bars = window(bars_by_day, cut, t_from, end)
    known = [b for b in bars if b[0] + 300 <= cut]
    if len(known) < LOOKBACK or not clean(bars) or len(bars) < LOOKBACK + 12:
        return None
    start = known[-LOOKBACK][0]
    shown = [b for b in bars if b[0] >= start][:LOOKBACK + MAX_AFTER]
    s = dt.datetime.fromtimestamp(start, ET)
    return {
        "id": f"{day}_flat", "day": day, "take": False, "side": None, "m0": s.hour * 60 + s.minute, "n_known": LOOKBACK,
        "t0": start,
        "o": [q4(b[1]) for b in shown], "h": [q4(b[2]) for b in shown], "l": [q4(b[3]) for b in shown], "c": [q4(b[4]) for b in shown],
        "cut_time": dt.datetime.fromtimestamp(cut, ET).strftime("%H:%M"),
    }


def build() -> dict | None:
    if not (os.path.exists(BT) and os.path.exists(BARS)):
        return None
    with open(BT, encoding="utf-8") as fh:
        bt = json.load(fh)
    rng = random.Random(SEED)
    trades = [t for t in bt["trades"] if t["day"] >= "2026-01-01" and t.get("trigger") == "LIT" and 0 < int(t["exit_t"]) - int(t["entry_t"]) <= 5 * 3600 and t["exit_price"]]
    flat_days = [d["date"] for d in bt["days"] if d["date"] >= "2026-01-01" and d["trades"] == 0]
    bars = load_bars({t["day"] for t in trades} | set(flat_days))
    picked, used = [], set()
    for want in WANT:
        pool = [t for t in trades if t["exit"] == want and t["day"] not in used]
        rng.shuffle(pool)
        for t in pool:
            d = trade_drill(t, bars, rng)
            if d:
                picked.append(d)
                used.add(t["day"])
                break
    minutes = sorted({int(d["entry_time"][:2]) * 60 + int(d["entry_time"][3:]) for d in picked}) or [600]
    rng.shuffle(flat_days)
    flats = []
    for day in flat_days:
        if day in used or dt.date.fromisoformat(day).weekday() > 4:
            continue
        m = rng.choice([x for x in minutes if 4 * 60 <= x <= 13 * 60] or [600])
        d = flat_drill(day, m, bars)
        if d:
            flats.append(d)
            used.add(day)
        if len(flats) == 3:
            break
    ys, ns = list(picked), list(flats)
    out = []
    for ch in PATTERN:
        src = ys if ch == "Y" else ns
        if src:
            out.append(src.pop(0))
    out += ys + ns
    return {"v": 1, "kind": "olympus-athena-drills", "scale": 4, "step_s": 300,
            "source": "research/lab/backtest_live.json (LIT replay, live settings) + data/NQ_5m.csv (TradingView CME NQ1! 5m)",
            "note": "Real days from the replay. Prices are quarter-points x 4. The result is the replay's, at the bot's normal size.", "drills": out}


def main(argv) -> int:
    data = build()
    if data is None:
        print("sources not on this machine (research/lab/backtest_live.json, data/NQ_5m.csv): nothing built")
        return 0 if "--check" in argv else 1
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n"
    if "--check" in argv:
        try:
            old = open(OUT, encoding="utf-8").read()
        except OSError:
            old = ""
        print("drills.json is up to date" if old == text else "drills.json is STALE: run python tools/athena_drills.py")
        return 0 if old == text else 1
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {OUT}: {len(data['drills'])} drills ({sum(1 for d in data['drills'] if d['take'])} trades, {sum(1 for d in data['drills'] if not d['take'])} flat days), {len(text) // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
