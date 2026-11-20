"""What poll-on-tick (engine/fast_entry.py) could be worth a month, from the 4 real fills (day-speed 2026-11-20).

No tick data exists in the repo (futures-only rule, no paid data), so the price path inside the first 3 seconds of a
minute is unknown. Three pre-registered path shapes (research/speed/PREREG.md) bound it:
  jump   : the whole move happens at the first tick           -> earlier saves 0
  sqrt   : move grows like sqrt(time) (diffusion-like)         -> saves 1 - sqrt(t_on / t_off)
  linear : move grows linearly over the first seconds          -> saves 1 - t_on / t_off
and an overshoot-and-revert path can make an earlier fill WORSE (Nov 6: the minute fell 8.5 pts then closed 12 pts up).
    python -X utf8 research/speed/fast_entry_value.py
"""
from __future__ import annotations

import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TICK_USD = 0.50                  # MNQ: $2 a point, 4 ticks a point
POLL_S = 0.50                    # research/speed replay: median entry poll on the real file path (cloud, 3 runs at once)
NT_S = 0.15                      # OIF move + NinjaTrader pick-up + broker / exchange (est.)
T_OFF = 2.0 + POLL_S + NT_S      # today: poll at +2 s
T_ON = 0.15 + 0.05 + POLL_S + NT_S   # fast entry: wake at +0.15 s, first check sees the files (active minute)
# trades a month (2026 Jan 1 - Nov 19 = 10.6 months): ATLAS 163 signals (research/second/atlas_fills_why.json pop_2026),
# LIT 120 trades Jan 2 - Oct 14 = 9.4 months (data/lit_journal.jsonl)
BOTS = {"ATLAS": {"per_month": 163 / 10.6, "micros": 2, "drift_ticks": [9.0, 11.0, 15.0]},
        "LIT (Zlarior)": {"per_month": 120 / 9.4, "micros": 3, "drift_ticks": [3.0]}}


def shares():
    return {"jump": 0.0, "sqrt": 1 - math.sqrt(T_ON / T_OFF), "linear": 1 - T_ON / T_OFF}


def main():
    sh = shares()
    out = {"t_off_s": round(T_OFF, 2), "t_on_s": round(T_ON, 2), "share_saved": {k: round(v, 2) for k, v in sh.items()}, "bots": {}}
    tot = {k: 0.0 for k in sh}
    for name, b in BOTS.items():
        drift = sum(b["drift_ticks"]) / len(b["drift_ticks"])        # ticks past the open beyond the 1 tick the backtest counts
        row = {"n_fills": len(b["drift_ticks"]), "drift_ticks_mean": round(drift, 2), "trades_month": round(b["per_month"], 1),
               "micros": b["micros"]}
        for k, s in sh.items():
            ticks = drift * s
            usd = ticks * TICK_USD * b["micros"] * b["per_month"]
            row[f"ticks_saved_{k}"] = round(ticks, 1)
            row[f"usd_month_{k}"] = round(usd)
            tot[k] += usd
        out["bots"][name] = row
    out["usd_month_total"] = {k: round(v) for k, v in tot.items()}
    print(json.dumps(out, indent=1))
    with open(os.path.join(ROOT, "research", "speed", "fast_entry_value.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
