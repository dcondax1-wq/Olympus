"""Out-of-sample scorer for the FROZEN v5 delta variants (frozen.json). Scores every usable day in data/pc_days that is NOT one
of the 51 in-sample days, with the exact frozen rules. PAPER ONLY. Usage: python -X utf8 research/orderflow/v5/delta/oos.py"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import core as X  # noqa: E402


def main():
    fz = json.load(open(os.path.join(HERE, "frozen.json")))
    sha = hashlib.sha256(open(os.path.join(HERE, "core.py"), "rb").read()).hexdigest()
    if sha != fz["core_sha256"]:
        print("WARNING: core.py changed since the freeze (sha differs) - this is NOT the frozen rule set.")
    c = fz["constants"]
    assert (X.MKT_TICKS, X.COMM, X.STOP_SLIP, X.MIN_STOP) == (c["MKT_TICKS"], c["COMM_rt"], c["STOP_SLIP"], c["MIN_STOP_TICKS"])
    D, usable = X.load_days()
    ins = set(fz["in_sample"]["days"])
    days = [d for d in usable if d not in ins]
    n_rth = len(X.rth_days(D, days))
    print(f"out-of-sample usable days: {len(days)} ({days[0] if days else '-'} .. {days[-1] if days else '-'}), RTH days {n_rth}")
    if not n_rth:
        print("no new days yet"); return
    rows = []
    for v, meta in fz["variants"].items():
        X.SPECS.setdefault(v, meta["spec"])
        r = X.run_variant(D, days, v, spec=meta["spec"])
        rows.append((v, X.score(r, days, n_rth, v)))
    hp = X.holm({v: s["placebo_p"] for v, s in rows})
    for v, s in rows:
        s["holm_p"] = hp[v]; s["verdict"] = X.verdict(s, hp[v])
    print(X.table(rows))
    for v, s in rows:
        ins_s = fz["variants"][v]["in_sample"]
        print(f"  {v}: in-sample mean R {ins_s['mean_R']} gap {ins_s['gap_R']} ${ins_s['net_usd']:+,.0f} | OOS mean R {s['mean_R']} "
              f"gap {s['gap_R']} ${s['net_usd']:+,.0f} ($500 risk {s['usd500']:+,.0f}); halves $ {s['halves']['older']['usd']:+,.0f}"
              f" / {s['halves']['newer']['usd']:+,.0f}")
    print("bar:", fz["oos_bar"])
    json.dump({v: s for v, s in rows}, open(os.path.join(HERE, "oos_results.json"), "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
