"""Run the pre-registered v5 delta family on the 51 in-sample days -> results.json + the table. PAPER ONLY."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core as X  # noqa: E402


def main():
    D, usable = X.load_days()
    days = [d for d in usable if X.IS_FIRST <= d <= X.IS_LAST]
    n_rth = len(X.rth_days(D, days))
    rows, out = [], {"days": days, "n_days": len(days), "rth_days": n_rth, "variants": {}}
    allrows = {}
    for vid in X.VIDS:
        r = X.run_variant(D, days, vid)
        allrows[vid] = r
        rows.append((vid, X.score(r, days, n_rth, vid)))
    hp = X.holm({v: s["placebo_p"] for v, s in rows})
    for v, s in rows:
        s["holm_p"] = hp[v]; s["verdict"] = X.verdict(s, hp[v])
        out["variants"][v] = {"name": X.NAMES[v], "spec": X.SPECS[v], **s,
                              "book": [{k: x.get(k) for k in ("day", "i", "d", "fill", "stop", "how", "why", "R", "usd")}
                                       for x in X.book(allrows[v])]}
    print(f"days {len(days)} {days[0]}..{days[-1]}  rth days {n_rth}")
    print(X.table(rows))
    print("\ninfo (pool as if all taken / unlabelled / fills / exits):")
    for v, s in rows:
        print(f"  {v}: pool R {s['pool_all_R']} unlab R {s['unlab_mean_R']} how {s['how']} why {s['why']} "
              f"halves $ {s['halves']['older']['usd']:+,.0f} / {s['halves']['newer']['usd']:+,.0f}")
    with open(os.path.join(X.HERE, "results.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)


if __name__ == "__main__":
    main()
