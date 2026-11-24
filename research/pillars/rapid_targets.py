"""Rapid EOD 25K: LIT fixed 1.5R / 2R target in the EVAL only (pre-registered: research/pillars/RAPID_TARGETS_DESIGN.md).
PAPER RESEARCH ONLY.  python -X utf8 research/pillars/rapid_targets.py [--ne 2000 --ns 1000] -> rapid_targets.json
Same engine and paths as research/pillars/blitz_rapid.py (row V0 = today's LIT + ATLAS).
"""
from __future__ import annotations
import argparse, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import blitz_rapid as P  # noqa: E402
from tools import stops_targets_time as STT  # noqa: E402

R, SOA, U = P.R, P.SOA, P.U
VARS = {"V0 today LIT+ATLAS (band)": None, "T15 LIT 1.5R in the eval": "R1.5", "T20 LIT 2R in the eval": "R2"}


def swap(sp, tgt):
    """Replace the eval book's LIT trades by the re-walked ones at target tgt (matched on entry_t)."""
    Um = {u["entry_t"]: u for u in STT.units({"tgt": tgt})}
    n = 0
    out = []
    for ts in sp["BYe"]:
        row = []
        for t in ts:
            if t["strat"] == "LIT":
                u = Um[int(t["entry_t"])]
                assert abs(u["risk"] - t["risk"]) < 0.01, (t["day"], u["risk"], t["risk"])
                t = {**t, "tgt": u["tgt"], "tgt_pts": u["tgt"], "pts": u["pts"], "w1": u["w1"], "exit_t": u["exit_t"],
                     "exit": u["exit"]}
                n += 1
            row.append(t)
        out.append(row)
    sp["BYe"] = out
    return n


def check(sp):
    """With the band (options off) the re-walk equals the stored LIT eval trades."""
    Um = {u["entry_t"]: u for u in STT.units()}
    bad = [t for ts in sp["BYe"] for t in ts if t["strat"] == "LIT"
           and (abs(Um[int(t["entry_t"])]["pts"] - t["pts"]) > 0.02 or abs(Um[int(t["entry_t"])]["tgt"] - t["tgt"]) > 0.02)]
    return len(bad)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--ne", type=int, default=2000); ap.add_argument("--ns", type=int, default=1000)
    a = ap.parse_args(); t0 = time.time()
    S = SOA.data()["S"]
    PE = {s: U.mc_paths(S, s, a.ne, length=R.H_EVAL, seed=7) for s in R.SPANS}
    PF = {s: U.mc_paths(S, s, a.ns, length=R.LEN, seed=23) for s in R.SPANS}
    rows = {}
    for name, tg in VARS.items():
        sp = P.build("V0 today LIT+ATLAS")
        info = {"check_mismatch": check(sp)} if tg is None else {"lit_swapped": swap(sp, tg)}
        P.B.CFG.clear(); P.B.CFG.update(sp["knobs"])
        r = {"info": info}
        for s in R.SPANS:
            ev = R.eval_run(sp, PE[s]); sl = R.slot_run(sp, PF[s]); sl["per_month"] = round(sl["net_6m"] / 6.0)
            fx = SOA.plain_stats(sp["BYe"], S, s, dict(sp["usd"]))
            r[s] = {"eval": ev, "slot": sl, "fixed_eval_book": fx}
        P.B.CFG.clear()
        rows[name] = r
        print(name, info, " | ".join(f"{s} pass {r[s]['eval']['pass']} fail {r[s]['eval']['fail']} med {r[s]['eval']['med_days']} "
                                     f"${r[s]['slot']['per_month']}/mo" for s in R.SPANS), f"[{time.time()-t0:.0f}s]", flush=True)
    b = rows["V0 today LIT+ATLAS (band)"]
    for name, r in rows.items():
        if name.startswith("V0"):
            continue
        ok = all(r[s]["eval"]["pass"] > b[s]["eval"]["pass"] and r[s]["eval"]["fail"] <= b[s]["eval"]["fail"] + 1.0
                 and r[s]["slot"]["per_month"] >= b[s]["slot"]["per_month"] for s in ("H1", "H2"))
        ok = ok and r["REF"]["slot"]["net_6m"] >= b["REF"]["slot"]["net_6m"] - 100
        r["verdict"] = "worth a card (owner yes needed)" if ok else "rejected"
    out = {"design": "research/pillars/RAPID_TARGETS_DESIGN.md", "plan": P.PLAN, "n_eval": a.ne, "n_slot": a.ns, "rows": rows}
    json.dump(out, open(os.path.join(HERE, "rapid_targets.json"), "w"), indent=1, default=float)
    for name, r in rows.items():
        print(name, r.get("verdict", "baseline"))


if __name__ == "__main__":
    main()
