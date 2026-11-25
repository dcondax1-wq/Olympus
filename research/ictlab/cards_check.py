"""Post-hoc check of the card candidates (labelled post-hoc, not counted as tries): HALF mode = x1 with the concept, x0.5 without
(the eval-friendly version of UP / ONLY). Reads research/ictlab/trades.json + results.json, writes research/ictlab/cards_check.json."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ict_lab as L  # noqa: E402

TR = json.load(open(os.path.join(HERE, "trades.json")))
RES = json.load(open(os.path.join(HERE, "results.json")))["variants"]
SP = {"LIT": (RES["LIT_BASE"], L.LIT_END, (3000.0, 2000.0)), "ATLAS": (RES["ATLAS_BASE"], L.ATLAS_END, (1500.0, 1000.0))}
CHECK = [("LIT", ["F_TDO"]), ("LIT", ["F_SB", "F_TDO", "F_DOL"]), ("ATLAS", ["F_SB"]), ("ATLAS", ["F_KZ"]), ("ATLAS", ["F_QT90"]),
         ("ATLAS", ["F_TDO"]), ("ATLAS", ["F_PO3"]), ("ATLAS", ["F_SB", "F_IPDA20"]), ("ATLAS", ["F_KZ", "F_DOL"]),
         ("ATLAS", ["F_SB", "F_TDO", "F_DOL"])]


def main():
    out = {}
    for kind, keys in CHECK:
        base, end, ev = SP[kind]
        BT = [t for t in TR[kind] if t["sd"] <= end and t["sd"] >= ("2021-11-08" if kind == "LIT" else "2021-11-01")]
        S = sorted({m for m in base["months"]})
        # sessions: every weekday session in the base span (from the trades file we only have trade days; rebuild from months)
        import pandas as pd
        days = [d.date().isoformat() for d in pd.bdate_range(S[0] + "-01", end)]
        L.WF = L.wf_blocks(last=end[:7])
        mi = L.months_between(days[0][:7], days[-1][:7])
        mask = np.array([L.has(t["f"], keys) for t in BT])
        base_rows = [(t["sd"], t["usd"]) for t in BT]
        rows = [(t["sd"], t["usd"] * (1.0 if m else 0.5)) for t, m in zip(BT, mask)]
        b = L.score_variant(base_rows, [], days, mi, kind, ev)
        r = L.score_variant(rows, base_rows, days, mi, kind, ev)
        r.pop("_months"), b.pop("_months")
        nm = f"{kind}_{'+'.join(keys)}_HALF"
        out[nm] = {"years_delta": r["years_delta"], "wf": r["wf"], "all": r["all"], "y2026": r["y2026"],
                   "h1_2026_delta": r["h1_2026"]["net"] - b["h1_2026"]["net"], "h2_2026_delta": r["h2_2026"]["net"] - b["h2_2026"]["net"],
                   "eval_all": r["eval_all"], "eval_2026": r["eval_2026"], "base_eval_all": b["eval_all"],
                   "base_eval_2026": b["eval_2026"], "base_all": b["all"], "base_y2026": b["y2026"]}
        print(nm, json.dumps(out[nm]))
    json.dump(out, open(os.path.join(HERE, "cards_check.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
