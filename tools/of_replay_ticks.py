"""Real tick-day summaries -> an LE_TickRec-style live CSV, so a recorded REAL day can be replayed through the lane's live path
(day-ofready2 2026-11-27: the Monday dry run). Research / test only; it never trades.

The cloud holds the PC's 5m summaries (data/pc_days/<day>/of/: bars + footprint), not the raw ticks. This rebuilds a tick tape whose
engine.ofsum.summarize gives back the SAME bars (open / high / low / close, volume, buy / sell / unknown) and the SAME footprint
(bid / ask / unknown volume per price per bar), which is all the lane A decision reads (levels, the sweep, the absorption zone).
What it cannot rebuild: the order of trades inside a 5m bar (taken as open -> the nearer extreme -> the other -> close), trade
sizes (each footprint cell = up to 3 trades) and the block / sign-run columns. So decisions match the paper bot on the summary;
intrabar fill paths (E5 limit / stop first) are a plausible path, not the real one.

    python -X utf8 tools/of_replay_ticks.py --day 2026-11-23 --out "C:/.../le_ticks/NQ_2026-11-23.csv" [--shift-to 2026-11-30]
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TICK = 0.25
PER_CELL = 3


def _split(v: int, k: int) -> list:
    k = max(1, min(int(k), int(v)))
    base, rem = divmod(int(v), k)
    return [base + (1 if i < rem else 0) for i in range(k)]


def ticks_from_summary(R: dict, shift_s: int = 0) -> pd.DataFrame:
    """{bars, fp} (engine.ofsum.read) -> DataFrame t_ns, price, size, bid, ask (sorted). shift_s moves every time (a re-dated day)."""
    bars = R["bars"].reset_index(drop=True)
    fp = R["fp"]
    cols = {c: c for c in bars.columns}
    o_, h_, l_, c_ = (cols.get(x, y) for x, y in (("o", "open"), ("h", "high"), ("l", "low"), ("c", "close")))
    rows = []
    by = {int(b): g for b, g in fp.groupby("bar")}
    for i in range(len(bars)):
        t0 = int(bars.t.iat[i]) + shift_s
        o, h, l, c = (float(bars[x].iat[i]) for x in (o_, h_, l_, c_))
        lo_k = int(round(l / TICK))
        g = by.get(i)
        if g is None:
            continue
        cells = []                                       # (price, side, size)
        for k, b, a, u in zip(g.k.to_numpy(int), g.b.to_numpy(int), g.a.to_numpy(int), g.u.to_numpy(int)):
            px = (lo_k + int(k)) * TICK
            for side, v in ((-1, b), (1, a), (0, u)):
                if v > 0:
                    cells += [(px, side, s) for s in _split(v, PER_CELL)]
        if not cells:
            continue
        down_first = abs(o - l) <= abs(h - o)            # the nearer extreme first: open -> ext1 -> ext2 (-> close)
        e1, e2 = (l, h) if down_first else (h, l)

        def rank(px):
            if min(o, e1) - 1e-9 <= px <= max(o, e1) + 1e-9:
                return (0, abs(px - o))                  # leg 1: from the open towards the first extreme
            return (1, abs(px - e1))                     # leg 2: from the first extreme towards the other
        cells.sort(key=lambda x: (rank(x[0]), x[1]))
        oi = next((j for j, x in enumerate(cells) if abs(x[0] - o) < 1e-9), None)
        if oi is not None:
            cells.insert(0, cells.pop(oi))
        ci = next((j for j in range(len(cells) - 1, 0, -1) if abs(cells[j][0] - c) < 1e-9), None)
        if ci is not None:
            cells.append(cells.pop(ci))
        n = len(cells)
        ts = t0 * 10**9 + (np.arange(n) * (299 * 10**9 // max(1, n))).astype(np.int64) + 10**6
        for (px, side, s), t in zip(cells, ts):
            bid, ask = (px, px + TICK) if side < 0 else (px - TICK, px) if side > 0 else (px - TICK, px + TICK)
            rows.append((int(t), px, int(s), bid, ask))
    x = pd.DataFrame(rows, columns=["t_ns", "price", "size", "bid", "ask"])
    return x.sort_values("t_ns", kind="stable").reset_index(drop=True)


def write_rec_csv(x: pd.DataFrame, path: str) -> str:
    """LE_TickRec's live CSV (t_ms,price,size,bid,ask), as engine.tickrec.read_rec_csv reads it."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    t = x.t_ns.to_numpy(np.int64) // 1_000_000
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("t_ms,price,size,bid,ask\n")
        for a, p, s, b, k in zip(t, x.price.to_numpy(), x["size"].to_numpy(), x.bid.to_numpy(), x.ask.to_numpy()):
            fh.write(f"{a},{p:.2f},{s},{b:.2f},{k:.2f}\n")
    return path


def shift_seconds(day: str, to: str) -> int:
    return int((dt.date.fromisoformat(to) - dt.date.fromisoformat(day)).days) * 86400


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shift-to")
    ap.add_argument("--src", default=os.path.join(ROOT, "data", "pc_days"))
    a = ap.parse_args(argv)
    from engine import ofsum
    R = ofsum.read(os.path.join(a.src, a.day))
    if not R:
        print(f"no summary for {a.day} in {a.src}")
        return 1
    x = ticks_from_summary(R, shift_seconds(a.day, a.shift_to) if a.shift_to else 0)
    write_rec_csv(x, a.out)
    print(f"{a.day}: {len(x)} trades -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
