"""Apply the pre-registered judgement (research/execpol/DESIGN.md) to results.json, mechanically.
    python -X utf8 research/execpol/judge.py  -> research/execpol/verdict.json + a table
Rule 2's "worst span under next" is read on the two 2026 spans (1m bars): on 5m bars a cancel of 5 min or less leaves no bar
after the entry bar, so "next" is undefined there (it shows 0 fills)."""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "results.json"), encoding="utf-8"))["results"]
MEAS = {"ATLAS": 12, "LIT": 2}
S_DEP = ("MKT", "ML2", "ML4", "ML8", "HYB-2")
SP26 = ("2026 H1", "2026 Jul-Oct")
ALL = SP26 + ("2021-25",)


def g(bot, sp, pol, s, var="base"):
    return R[bot][sp][f"{pol}|s{s if pol in S_DEP else 0}|{var}"]


def judge(bot):
    sm, sh = MEAS[bot], MEAS[bot] // 2
    pols = sorted({k.split("|")[0] for k in R[bot]["2026 H1"]} - {"MKT"})
    out = {}
    for p in pols:
        c1 = all(g(bot, sp, p, sm)["net_usd"] > g(bot, sp, "MKT", sm)["net_usd"] for sp in ALL)
        c2a = all(max(g(bot, sp, p, sh)["net_usd"], g(bot, sp, p, sh, "next")["net_usd"]) > g(bot, sp, "MKT", sh)["net_usd"] for sp in SP26)
        c2b = all(g(bot, sp, p, sm, "next")["net_usd"] >= g(bot, sp, "MKT", sm)["net_usd"] - 0.10 * abs(g(bot, sp, "MKT", sm)["net_usd"])
                  for sp in SP26)
        c3 = all((g(bot, sp, p, sm)["missed_winner_share"] or 0) <= 0.25 for sp in ALL)
        gain = {sp: g(bot, sp, p, sm)["net_usd"] - g(bot, sp, "MKT", sm)["net_usd"] for sp in ALL}
        out[p] = {"1_beats_mkt_all_spans": c1, "2a_beats_at_half_slip": c2a, "2b_next_within_10pct": c2b, "3_missed_winners_le_25pct": c3,
                  "adopt": c1 and c2a and c2b and c3, "gain_vs_mkt_usd": gain}
    return out


def main():
    V = {b: judge(b) for b in R}
    json.dump(V, open(os.path.join(HERE, "verdict.json"), "w"), indent=1)
    for b, vs in V.items():
        print(f"\n{b}: policy  | 1 all spans | 2a half slip | 2b next | 3 winners | ADOPT | $ vs market (H1 / Jul-Oct / 2021-25)")
        for p, v in vs.items():
            gn = " / ".join(f"{v['gain_vs_mkt_usd'][sp]:+,}" for sp in ALL)
            print(f"  {p:8s} | {'Y' if v['1_beats_mkt_all_spans'] else '-':^11} | {'Y' if v['2a_beats_at_half_slip'] else '-':^12} | "
                  f"{'Y' if v['2b_next_within_10pct'] else '-':^7} | {'Y' if v['3_missed_winners_le_25pct'] else '-':^9} | "
                  f"{'YES' if v['adopt'] else 'no':^5} | {gn}")


if __name__ == "__main__":
    main()
