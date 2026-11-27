"""Run the pre-registered v5 exhaustion family on the 51 in-sample days -> results.json + the table. PAPER ONLY."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core as X  # noqa: E402


def main():
    D, usable = X.LC.load_days()
    days = [d for d in usable if "2026-09-27" <= d <= "2026-11-26"]
    pools = {d: X.pool_day(D[d]) for d in days}
    rows, sens, out = [], {}, {"days": days, "n_days": len(days), "variants": {}}
    for vid in X.VIDS:
        c = X.run_variant(D, days, vid, pools=pools)
        rows.append((vid, X.score(c, days)))
        c1 = X.run_variant(D, days, vid, mkt_ticks=1, pools=pools)
        s1 = X.score(c1, days)
        sens[vid] = {k: s1[k] for k in ("trades", "mean_R", "pf", "net_usd", "gap_R", "placebo_p")}
    hp = X.holm({v: s["placebo_p"] for v, s in rows})
    for v, s in rows:
        s["holm_p"] = hp[v]; s["verdict"] = X.verdict(s, hp[v])
        out["variants"][v] = {"name": X.NAMES[v], **s, "sens_open_plus1": sens[v]}
    print(f"days {len(days)} {days[0]}..{days[-1]}  pool {sum(len(p) for p in pools.values())}")
    print(X.table(rows))
    print("\npool as if all taken (info):")
    for v, s in rows:
        print(f"  {v}: resolved {s['resolved']} mean R {s['pool_all_R']} ${s['pool_all_usd']:+,.0f}; not-label mean R "
              f"{s['notabs_mean_R']}; targets {s['targets']}; no_room {s['no_room']}; $500 {s['usd500']:+,.0f}")
    print("\nsensitivity, entry = next open + 1 tick (info only):")
    for v in X.VIDS:
        print("  ", v, sens[v])
    with open(os.path.join(X.HERE, "results.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)


if __name__ == "__main__":
    main()
