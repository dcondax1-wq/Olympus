"""BLITZ pillar test on the MFFU Rapid EOD 25K (pre-registered: research/pillars/DESIGN.md). PAPER RESEARCH ONLY.
    python -X utf8 research/pillars/blitz_rapid.py [--ne 2000 --ns 1000]  -> research/pillars/blitz_rapid.json
"""
from __future__ import annotations
import argparse, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "onebook")); sys.path.insert(0, ROOT)
import book as B  # noqa
R, RL, SOA, U = B.R, B.RL, B.SOA, B.U
PLAN = "mffu_rapid_eod_25k"
LA, LAB = ("LIT", "ATLAS"), ("LIT", "ATLAS", "BLITZ")
GAP = 30 * 60

# near-cap half size (V3): wrap the add-on sizer once
_qa = RL.q_add
def q_add(t, z, room, cum, maxq, dll):
    if t["strat"] == "BLITZ" and B.CFG.get("near_cap") and cum >= B.CFG["near_cap"]:
        z = {**z, "BLITZ": {"usd": z["BLITZ"]["usd"] * 0.5, "f": z["BLITZ"]["f"] * 0.5}}
    return _qa(t, z, room, cum, maxq, dll)
RL.q_add = q_add


def one_pos(ts):
    o = [t for t in ts if t["strat"] != "BLITZ"]
    return [t for t in ts if t["strat"] != "BLITZ" or not any(t["entry_t"] < u["exit_t"] and u["entry_t"] < t["exit_t"] for u in o)]


def gap_after(ts):
    L = [u for u in ts if u["strat"] == "LIT"]
    return [t for t in ts if t["strat"] != "BLITZ" or not any(u["entry_t"] <= t["entry_t"] <= u["exit_t"] + GAP for u in L)]


def gap_both(ts):
    L = [u for u in ts if u["strat"] == "LIT"]
    return [t for t in ts if t["strat"] != "BLITZ" or not any(u["entry_t"] - GAP <= t["entry_t"] <= u["exit_t"] + GAP for u in L)]


def stop_after_loss(ts):
    out, stop = [], None
    for t in ts:
        if t["strat"] == "BLITZ":
            if stop is not None and t["entry_t"] >= stop:
                continue
            if t["pts"] < 0 and stop is None:
                stop = t["exit_t"]
        out.append(t)
    return out


def chain(*fs):
    def f(ts):
        for g in fs:
            ts = g(ts)
        return ts
    return f


VARS = {  # name -> (eval mix, funded mix, blitz $, day filter on the eval list, knobs)
    "V0 today LIT+ATLAS": (LA, LA, None, None, {}),
    "V1 + BLITZ $300 eval (built lane)": (LAB, LA, 300, one_pos, {}),
    "V1r V1 without one-position drop (ref)": (LAB, LA, 300, None, {}),
    "V2 no BLITZ from LIT entry to LIT exit+30m": (LAB, LA, 300, chain(one_pos, gap_after), {}),
    "V2b no BLITZ within 30m of a LIT trade (look-ahead, diag)": (LAB, LA, 300, chain(one_pos, gap_both), {}),
    "V3 BLITZ half size once day >= 50% of best-day cap": (LAB, LA, 300, one_pos, {"near_cap": "half"}),
    "V4 BLITZ stops for the day after its first loser": (LAB, LA, 300, chain(one_pos, stop_after_loss), {}),
    "V5 BLITZ $150": (LAB, LA, 150, one_pos, {}),
    "OWN BLITZ alone (eval + funded)": (("BLITZ",), ("BLITZ",), 300, None, {}),
}


def build(name):
    me, mf, bu, f, kn = VARS[name]
    key = "PIL|" + name
    lanes = {"BLITZ": bu} if bu else {}
    B.EXTRA[key] = (me, mf, dict(kn), None, lanes)
    sp = B.build(PLAN, key)
    if f:
        sp["BYe"] = [f(ts) for ts in sp["BYe"]]
    if kn.get("near_cap"):
        E = sp["E"]
        sp["knobs"] = {**sp["knobs"], "near_cap": 0.5 * E["cons"] * E["tgt"] * 0.95}
    return sp


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--ne", type=int, default=2000); ap.add_argument("--ns", type=int, default=1000)
    a = ap.parse_args(); t0 = time.time()
    S = SOA.data()["S"]
    PE = {s: U.mc_paths(S, s, a.ne, length=R.H_EVAL, seed=7) for s in R.SPANS}
    PF = {s: U.mc_paths(S, s, a.ns, length=R.LEN, seed=23) for s in R.SPANS}
    rows = {}
    for name in VARS:
        sp = build(name)
        B.CFG.clear(); B.CFG.update(sp["knobs"])
        r = {}
        for s in R.SPANS:
            ev = R.eval_run(sp, PE[s]); sl = R.slot_run(sp, PF[s]); sl["per_month"] = round(sl["net_6m"] / 6.0)
            usd = dict(sp["usd"])
            if "BLITZ" in VARS[name][0]:
                usd["BLITZ"] = float(VARS[name][2])
            fx = SOA.plain_stats(sp["BYe"], S, s, usd)          # eval book at fixed $, no account rules
            nb = sum(1 for i in range(*U.span_ix(S, s)) for t in sp["BYe"][i] if t["strat"] == "BLITZ")
            r[s] = {"eval": ev, "slot": sl, "fixed_eval_book": fx, "blitz_trades": nb}
        B.CFG.clear()
        rows[name] = r
        print(name, " | ".join(f"{s} pass {r[s]['eval']['pass']} fail {r[s]['eval']['fail']} med {r[s]['eval']['med_days']} "
                                f"${r[s]['slot']['per_month']}/mo nB {r[s]['blitz_trades']}" for s in R.SPANS), f"[{time.time()-t0:.0f}s]", flush=True)
    # BLITZ alone, fixed $ (no account rules)
    BYb = RL.mix_by(("BLITZ",))
    fixed = {f"${u}": {s: SOA.plain_stats(BYb, S, s, {"LIT": 0, "ATLAS": 0, "BLITZ": float(u)}) for s in R.SPANS} for u in (150, 300)}
    out = {"design": "research/pillars/DESIGN.md", "plan": PLAN, "n_eval": a.ne, "n_slot": a.ns, "rows": rows, "blitz_fixed": fixed}
    json.dump(out, open(os.path.join(HERE, "blitz_rapid.json"), "w"), indent=1, default=float)
    print(json.dumps(fixed))


if __name__ == "__main__":
    main()
