"""v5 / targets OUT-OF-SAMPLE: scores the frozen exits (frozen.json) on every real summary day NOT in the 51 in-sample days.

PAPER RESEARCH ONLY. Same signals, E5 entry, costs and fill rules as study.py (imported, unchanged).
    python -X utf8 research/orderflow/v5/targets/oos.py            # reads data/pc_days (+ logs/datapipe/days)
    python -X utf8 research/orderflow/v5/targets/oos.py --src DIR  # another folder of <day>/of summaries
Writes research/orderflow/v5/targets/oos_results.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sp = importlib.util.spec_from_file_location("v5t_study", os.path.join(HERE, "study.py"))
S = importlib.util.module_from_spec(sp); sp.loader.exec_module(S)


def paired_p(a, b, seed=5, n=20000):
    d = np.asarray(a, float) - np.asarray(b, float)
    if not len(d):
        return None
    s = np.random.default_rng(seed).choice([-1, 1], (n, len(d)))
    return round(float(((s * d).mean(1) >= d.mean() - 1e-12).mean()), 4)


def run(src=None, say=print):
    F = json.load(open(os.path.join(HERE, "frozen.json"), encoding="utf-8"))
    is_days = set(F["in_sample_days"])
    frozen = [f["id"] for f in F["frozen"]]
    days, sigs, modes = S.load(src, exclude_days=is_days)
    if not days:
        say("No out-of-sample day yet (every usable day is one of the 51 in-sample days). Pull the new days first.")
        return {"days": 0}
    vids = ["B2R"] + frozen
    fills, res = S.score_all(sigs, vids)
    nm = {m: sum(1 for d in days if modes[d] == m) for m in ("1m", "5m")}
    say(f"OOS: {len(days)} days {days[0]}..{days[-1]} (1m path {nm['1m']}, 5m path {nm['5m']}); {len(sigs)} signals, "
        f"taken {sum(s['taken'] for s in sigs)}, E5-filled taken {sum(1 for s, f in zip(sigs, fills) if s['taken'] and f)}")
    out = {v: S.summarize(v, sigs, res, days, base=None if v == "B2R" else res["B2R"]) for v in vids}
    H = S.holm({v: out[v]["placebo_p"] for v in frozen})
    tk = [i for i, s in enumerate(sigs) if s["taken"] and res["B2R"][i] is not None]
    for v in frozen:
        out[v]["holm_p"] = H.get(v)
        out[v]["verdict"] = S.verdict(out[v]) if out[v]["trades"] else "NO"
        out[v]["paired_p_vs_B2R"] = paired_p([res[v][i]["usd_1"] for i in tk], [res["B2R"][i]["usd_1"] for i in tk])
    if not tk:
        say("No resolved taken trade out of sample.")
        return {"days": len(days), "trades": 0}
    S.table(out, vids, say)
    for v in frozen:
        say(f"{v}: paired sign-flip p (beats 2R by chance) = {out[v]['paired_p_vs_B2R']}; vs 2R by half "
            f"{[h.get('d_usd_vs_B2R') for h in out[v]['halves']]}")
    if nm["1m"] and nm["5m"]:
        for m in ("1m", "5m"):
            dm = [d for d in days if modes[d] == m]
            ii = [i for i, s in enumerate(sigs) if s["day"] in set(dm)]
            if len(dm) >= 4 and any(sigs[i]["taken"] and res["B2R"][i] for i in ii):
                sub = [sigs[i] for i in ii]
                rr = {v: [res[v][i] for i in ii] for v in vids}
                o2 = {v: S.summarize(v, sub, rr, dm, base=None if v == "B2R" else rr["B2R"]) for v in vids}
                say(f"-- {m} path days only ({len(dm)}):")
                S.table(o2, vids, say)
    rec = {"made": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "frozen": F["frozen"], "days": days,
           "modes": modes, "variants": out}
    json.dump(rec, open(os.path.join(HERE, "oos_results.json"), "w", encoding="utf-8"), indent=1, default=float)
    say("wrote research/orderflow/v5/targets/oos_results.json")
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    a = ap.parse_args(argv)
    run(a.src)
    return 0


if __name__ == "__main__":
    sys.exit(main())
