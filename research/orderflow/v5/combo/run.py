"""v5 'combo' in-sample run on the 51 days (DESIGN.md frozen first). PAPER RESEARCH ONLY.

    python -X utf8 research/orderflow/v5/combo/run.py
Writes results.json + frozen.json (best 2 variants by verdict, Holm p, net $; picked by rule, not by hand).
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core as C  # noqa: E402

IS_FIRST, IS_LAST = "2026-09-27", "2026-11-26"
RANK = {"YES-candidate": 0, "weak": 1, "NO": 2, "TOO FEW": 3}


def main():
    D, usable = C.LV.load_days()
    days = [d for d in usable if IS_FIRST <= d <= IS_LAST]
    print(f"days: {len(days)} usable {days[0]}..{days[-1]} (files loaded {len(D)})")
    ctx = C.Context(D)
    cands = C.candidates(D, usable, days, ctx)
    out = {"C0": C.score(cands, days, None)}
    for v in C.VIDS:
        out[v] = C.score(cands, days, C.VARIANTS[v])
    adj = C.holm({v: out[v]["placebo_p"] for v in C.VIDS})
    for v in C.VIDS:
        out[v]["holm_p"] = adj[v]
        out[v]["verdict"] = C.verdict(out[v], adj[v])
    out["C0"]["verdict"] = "control (not scored)"
    print(C.table([(v, out[v]) for v in ["C0"] + C.VIDS]))
    for v in ["C0"] + C.VIDS:
        print(v, "$500-risk", out[v]["usd500"], "halves $", {k: h["usd"] for k, h in out[v]["halves"].items()},
              "halves n", {k: h["trades"] for k, h in out[v]["halves"].items()})
    best = sorted(C.VIDS, key=lambda v: (RANK[out[v]["verdict"]], out[v]["holm_p"] if out[v]["holm_p"] is not None else 9,
                                         -out[v]["net_usd"]))
    pick = best[:2]
    frozen = {"family": "combo", "design": "research/orderflow/v5/combo/DESIGN.md", "frozen_on": "2026-11-27",
              "in_sample_days": days,
              "variants": {v: {"name": C.NAMES[v], "flag": C.VARIANTS[v],
                               "in_sample": {k: out[v][k] for k in ("trades", "per_week", "win_pct", "mean_R", "pf", "net_usd",
                                                                    "usd_month", "max_dd_usd", "gap_R", "placebo_p", "holm_p",
                                                                    "verdict")}} for v in pick},
              "rules": {"base": "lane A = v5/levels/core.v0_candidates (pdh/pdl, onh/onl, orh/orl from 10:00; 09:45-15:00 ET; "
                                "1 tick through + close back; one signal per level per day), book = ABSORBED (OF1 zone 8 ticks, "
                                "|dz| >= 0.20 vz against the push) AND the flag, one position at a time",
                        "entry": "E5 coarse (levels/core.simulate): open beyond level = fill at open; else >=1 tick through = fill at level; else stop in bar = no fill; else next open + 18 ticks",
                        "stop": "1 tick beyond signal bar extreme; stop fill 2 ticks worse", "target": "2R, needs 1 tick through",
                        "flat": "15:55 bar close - 2 ticks", "comm_rt": C.LV.COMM,
                        "AT": "t15 == d and t60 == d; tN = sign(EMA21 - EMA50) of clock-aligned closed N-minute bars (tools/retail_standalone htf/to5)",
                        "LA": f"LIT Market levels of the trading day on the fade side, first breach within {C.SWEEP_WIN} bars ending at the signal bar, depth >= {C.DEPTH_ATR} x ATR14(5m)",
                        "S1": "previous session rv20 ((H-L)/C 20-session mean) > its trailing 252-session median (min 120)",
                        "VX": "last VIX close before the session day > trailing 252-session median (min 120)",
                        "IO": "09:30 bar open strictly inside prior usable day's RTH high-low",
                        "VOTE": ">= 3 of AT, LA, S1, VX, IO",
                        "placebo": "flag shuffle over resolved absorbed candidates; day-level for S1/VX/IO; 5000; Holm over the frozen set",
                        "pass_bar": "YES-candidate: >=20 trades, net>0, PF>=1.2, both halves meanR>0 and gap>0, placebo p<0.10, Holm<0.10"}}
    with open(os.path.join(HERE, "frozen.json"), "w") as fh:
        json.dump(frozen, fh, indent=1)
    slim = [{k: x.get(k) for k in ("day", "t_sig", "level", "L", "d", "absorbed", "how", "fill", "stop", "exit", "why", "R", "usd",
                                   "flags")} for x in cands]
    with open(os.path.join(HERE, "results.json"), "w") as fh:
        json.dump({"scores": out, "frozen": pick, "candidates": slim}, fh, indent=0, default=float)
    print("frozen:", pick)


if __name__ == "__main__":
    main()
