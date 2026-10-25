"""A1 audit (2026-10-25): intrabar ambiguity of the 2026 LIT trades (run lit_live = tools/lit_final.run on live_model "lit").

engine/lit.py simulate_x walks each bar as: stop check (current stop) -> target -> breakeven move (acts from the next bar).
Ambiguous bars (the order of the high and the low inside one bar is unknown):
  A  stop and target both touched           -> engine: STOP (already the bad way); good-way bound = TARGET
  B  breakeven stop and target both touched -> engine: BE (already the bad way); good-way bound = TARGET
  C  +1R (breakeven trigger) and entry + be_off both touched, the original stop not -> engine keeps the trade open with the
     stop at BE from the next bar (the GOOD way if the high came first and the low after); bad-way bound = a BE exit in
     that bar (entry + be_off - 1 tick).
  F  the 1m entry bar (market fill at its open) is included; a 5m limit-fill bar gets no target / BE credit (already bad).
    python -X utf8 research/handoff/2026-10-25/a1_intrabar.py   -> a1_intrabar.json / a1_intrabar_trades.csv
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

from engine import lit  # noqa: E402


def main():
    from tools import lit_final as F
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    PP = {**lit.DEFAULTS, **P}
    M, C = F.market(PP["ref"], PP["extra_boxes"])
    B1, B5 = F.bars(M, "1m"), F.bars(M, "5m")
    T = [t for t in F.run(P) if t["day"] >= "2026-01-01"]
    be_off, be_r = float(PP["be_off"]), float(PP["be_r"])
    rows = []
    for t in T:
        B = B1 if int(t["tf"]) == 1 else B5
        d = int(t["dir"])
        hi, lo, c, o = B.dirs(d)
        e, st, tg = d * t["entry_px"], d * t["stop_px"], d * t["target_px"]
        risk = e - st
        k0 = int(np.searchsorted(B.t, int(t["entry_t"])))
        k1 = int(np.searchsorted(B.t, int(t["exit_t"]) - B.secs))
        cur, be_done = st, False
        A = Bb = Cc = 0
        c_k = None
        kind_seen = None
        for k in range(k0, min(k1, B.n - 1) + 1):
            credit = not (k == k0 and t.get("limit_fill", int(t["tf"]) == 5 and False))
            st_hit = lo[k] <= cur
            tg_hit = hi[k] >= tg
            if st_hit:
                if tg_hit and credit:
                    if be_done:
                        Bb += 1
                    else:
                        A += 1
                kind_seen = "BE" if be_done else "STOP"
                break
            if tg_hit and credit:
                kind_seen = "TARGET"
                break
            if credit and not be_done and hi[k] >= e + be_r * risk:
                be_done = True
                if lo[k] <= e + be_off:
                    Cc += 1
                    c_k = k
                cur = e + be_off
        q = int(t["qty"])
        pnl = float(t["pnl"])
        be_pnl = round(((be_off - lit.SLIP) * lit.PV - lit.COMM) * q, 2)
        tgt_pnl = round(((tg - e) * lit.PV - lit.COMM) * q, 2)
        bad = (be_pnl - pnl) if Cc else 0.0
        good = (tgt_pnl - pnl) if (A or Bb) else 0.0
        rows.append({"day": t["day"], "tf": int(t["tf"]), "dir": d, "qty": q, "exit": t["exit"], "pnl": round(pnl, 2),
                     "walk_exit": kind_seen, "A_stop_and_target": A, "B_be_and_target": Bb, "C_be_trigger_and_be_level": Cc,
                     "C_bar_t": int(B.t[c_k]) if c_k is not None else None,
                     "bad_way_delta": round(bad, 2), "good_way_delta": round(good, 2)})
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(HERE, "a1_intrabar_trades.csv"), index=False)
    agree = int((df["walk_exit"].fillna("none") == df["exit"].replace({"CUT_T15": "none", "EOD": "none"})).sum())
    out = {"trades": len(df), "walk_agrees_with_engine_exit": agree,
           "A_stop_and_target_same_bar": int((df["A_stop_and_target"] > 0).sum()),
           "B_be_stop_and_target_same_bar": int((df["B_be_and_target"] > 0).sum()),
           "C_be_trigger_and_be_level_same_bar": int((df["C_be_trigger_and_be_level"] > 0).sum()),
           "C_trades_by_exit": df[df["C_be_trigger_and_be_level"] > 0]["exit"].value_counts().to_dict(),
           "bad_way_bound_usd": round(float(df["bad_way_delta"].sum()), 2),
           "good_way_bound_usd": round(float(df["good_way_delta"].sum()), 2),
           "net_2026": round(float(df["pnl"].sum()), 2),
           "net_2026_all_ambiguous_bad": round(float(df["pnl"].sum() + df["bad_way_delta"].sum()), 2),
           "H1": {"bad": round(float(df[df.day <= "2026-06-30"]["bad_way_delta"].sum()), 2), "net": round(float(df[df.day <= "2026-06-30"]["pnl"].sum()), 2)},
           "H2": {"bad": round(float(df[df.day > "2026-06-30"]["bad_way_delta"].sum()), 2), "net": round(float(df[df.day > "2026-06-30"]["pnl"].sum()), 2)}}
    json.dump(out, open(os.path.join(HERE, "a1_intrabar.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))
    print(df[(df.A_stop_and_target + df.B_be_and_target + df.C_be_trigger_and_be_level) > 0].to_string())


if __name__ == "__main__":
    main()
