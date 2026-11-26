"""When does each lane start inside the poll? (big-atlasfill 2026-11-26, the every-lane audit). PAPER RESEARCH ONLY.
Runs research/speed/replay_harness.run (the real LiveBot, paper, frozen clock, LE_BarFeed files) with ATLAS on account B and
wraps the lane methods of engine.live.LiveBot IN THIS PROCESS ONLY to stamp the time since poll start when each one begins.
    python -X utf8 research/atlasfill/lane_offsets.py [--days 2026-11-17,2026-11-18] -> research/atlasfill/lane_offsets.json
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research", "speed"))
OUT = os.path.join(HERE, "lane_offsets.json")
LANES = (("_route_signals", "LIT (50K + extra accounts' LIT lanes)"), ("_save_state", "state save"),
         ("_account_c_tick", "BLITZ account C"), ("_rapid_blitz_tick", "BLITZ on the Rapid"), ("_learn_es", "ES learning refresh"),
         ("_brain_tick", "Bot Brain"), ("_second_route_tick", "second route (LIT account)"),
         ("_account_b_tick", "ATLAS account B + Rapid ATLAS + combo lanes"), ("_fleet_tick", "fleet"),
         ("_keepalive_tick", "keep-alive"), ("_second_tick", "second strategies (paper)"))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", default="2026-11-17,2026-11-18")
    a = ap.parse_args(argv)
    from engine import live
    import replay_harness as RH
    T = {"t0": None, "now": None}
    stamps = {}                               # lane -> [(poll t, ms since poll start)]
    po = live.LiveBot.poll_once

    def poll_once(self, *x, **k):
        T["t0"], T["now"] = time.perf_counter(), int(self.clock())
        return po(self, *x, **k)
    live.LiveBot.poll_once = poll_once
    for name, _ in LANES:
        f = getattr(live.LiveBot, name)

        def w(self, *x, __f=f, __n=name, **k):
            if T["t0"] is not None and T["now"] % 300 < 20:
                stamps.setdefault(__n, []).append((T["now"], round((time.perf_counter() - T["t0"]) * 1000, 1)))
            return __f(self, *x, **k)
        setattr(live.LiveBot, name, w)
    extra = {"account_b": {"account": "SimATLAS", "plan": "builder25k", "strategies": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"],
                           "sizing": "need", "eval_start": "2026-11-02", "stage": "funded", "funded_start": "2026-11-02",
                           "funded_balance": 25000.0}}
    res = RH.run(a.days.split(","), cfg_extra=extra)
    out = {"days": a.days, "polls": res["polls"], "errors": res["n_errors"], "atlas_trades": len(res.get("ledger_atlas") or []),
           "note": "ms since poll start on THIS machine (the PC is slower: LIT's path measured 0.57 s there); 5m-close polls only; "
                   "first call per poll (_save_state runs more than once)", "lanes": {}}
    for name, label in LANES:
        s = stamps.get(name) or []
        first = {}
        for t, ms in s:
            first.setdefault(t, ms)
        v = list(first.values())
        if v:
            out["lanes"][label] = {"n_polls": len(v), "median_ms": statistics.median(v), "p90_ms": sorted(v)[int(0.9 * (len(v) - 1))]}
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1)
    for k, v in out["lanes"].items():
        print(f"{v['median_ms']:>8} ms med {v['p90_ms']:>8} p90  {k}")
    print({k: out[k] for k in ("polls", "errors", "atlas_trades")})


if __name__ == "__main__":
    main()
