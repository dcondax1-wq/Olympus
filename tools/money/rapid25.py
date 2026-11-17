"""MFFU Rapid EOD 25K vs Rapid EOD 50K for LIT + ATLAS on one account (owner 2026-11-17, buying tonight). PAPER RESEARCH
ONLY: reads stored trades, writes research/lab/rapid25.json, changes nothing live. Write-up:
research/writeups/rapid-25k-vs-50k-2026-11-17.md.

Same tooling as tools/money/rapid_levers.py (same trades, costs $1.90 a micro + 1 tick, Tier-1 news rule on the funded
account, 30% best-day size guard in the eval, Monte Carlo paths seed 7 / 23). Only the plan changes.

Rules (myfundedfutures.com/plans/rapid-eod product data, read 2026-11-17):
  25K  target $1,500, EOD MLL $1,000 (locks at +$100 on the first payout), 30% best day (eval only), 4 days, 2 / 20,
       funded buffer $1,100, $500 min payout, >= $250 net since the last payout, no cap, daily, 90%. $162 list, $97.20 CLUB.
  50K  target $3,000, EOD MLL $2,000, 30%, 4 days, 3 / 30, buffer $2,100, $500 min, >= $500 since last, 90%. $275 / $165 CLUB.
Sizing:
  50K  = the live preset mffu_rapid_eod_50k: eval LIT two_week (room_f 0.4, live_model.json), ATLAS $500 at 30% of the room,
         funded uprisk UP50 (60% of the room, <= $1,500, a winner <= $2,000), keep $1,000 above the buffer, soft day $1,000.
  25K  = the same rules at the 25K's numbers: eval LIT two_week on the 25K target / MLL / 20 micros, ATLAS $250 (engine/lit25),
         funded UP25 (60% of the room, <= $750, a winner <= $1,000), keep $500 (half), soft day $500.

    python -X utf8 tools/money/rapid25.py            # -> research/lab/rapid25.json
    python -X utf8 tools/money/rapid25.py --n 200    # quicker
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import rapid_levers as RL  # noqa: E402
import stack_one_account as SOA  # noqa: E402
import account4_sim as A4  # noqa: E402
import uprisk as U  # noqa: E402

OUT = os.path.join(ROOT, "research", "lab", "rapid25.json")
PRICE = {"50k": 165.0, "25k": 97.20}          # CLUB 40% off ($275 / $162 list), plan page 2026-11-17


def rules(size):
    """(eval, funded) from research/props/firm_rules.json (engine/copy_accounts.tighten); matches the plan page 2026-11-17."""
    E, F = A4.rules(f"mffu_rapid_eod_{size}")
    E = {**E, "stuck": 100.0 if size == "25k" else 200.0}
    F = {**F, "dll": 500.0 if size == "25k" else SOA.SOFT_DLL, "since": 250.0 if size == "25k" else 500.0}
    return E, F


def acct(size, pol, atlas=None):
    E, F = rules(size)
    soft = 500.0 if size == "25k" else 1000.0
    z = RL.Z(ATLAS=atlas or (250 if size == "25k" else 500))
    ec = A4.ecfg(E, {"dll_off": True})
    ec["two_week"]["acct"]["dll"] = soft
    ec["_dll"] = soft
    fcfg = U.UP25 if size == "25k" else U.UP50
    mix = RL.LA
    return {"E": E, "ecfg": ec, "z": z, "cap": "guard", "give": None, "pol": pol, "price": PRICE[size],
            "BYe": RL.mix_by(mix), "BYf": RL.mix_by(mix, news=True), "mix_f": mix,
            "fund": lambda: RL.Rapid(fcfg, F, z, pol), "ev": lambda: RL.Ev(ec, E, z, "guard")}


class Slot(RL.Slot):
    def _buy(self):
        self.cost += self.sp["price"]
        self.evals += 1
        self.e = self.sp["ev"]()


def run_group(specs, paths):
    out = []
    for seq in paths:
        sl = [Slot(s) for s in specs]
        for k, si in enumerate(seq[:RL.LEN]):
            for s in sl:
                s.step(k, si)
        out.append(sl)
    return out


ROWS = {
    "50K, keep $1,000 (live preset)": [("50k", ("cushion", 1000))],
    "50K, take all above $2,100": [("50k", "all")],
    "25K, keep $500": [("25k", ("cushion", 500))],
    "25K, keep $1,000": [("25k", ("cushion", 1000))],
    "25K, take all above $1,100": [("25k", "all")],
    "25K, ATLAS $500 (50K size), keep $500": [("25k", ("cushion", 500), 500)],
    "2x 25K (same days), keep $500": [("25k", ("cushion", 500)), ("25k", ("cushion", 500))],
}


def study(n=1000, log=print):
    S = SOA.data()["S"]
    PE = {s: U.mc_paths(S, s, 2 * n, length=RL.H_EVAL, seed=A4.SEED_EVAL) for s in RL.SPANS}
    PF = {s: U.mc_paths(S, s, n, length=RL.LEN, seed=A4.SEED_LIFE) for s in RL.SPANS}
    out = {"date": "2026-11-17", "n": n, "spans": U.SPAN, "price": PRICE, "rows": {}}
    t0 = time.time()
    for nm, members in ROWS.items():
        specs = [acct(*m) for m in members]
        r = {}
        for s in RL.SPANS:
            r[s] = {"slot": RL.group_stats(run_group(specs, PF[s]))}
            if len(specs) == 1:
                r[s]["eval"] = RL.eval_stats(specs[0], PE[s])
                r[s]["funded"] = RL.funded_stats(specs[0], PF[s])
        out["rows"][nm] = r
        log(f"{nm:40s} " + " | ".join(f"{s} ${r[s]['slot']['net_m']} 1st {r[s]['slot']['first_any_med']} none {r[s]['slot']['p_none_pays']}%"
                                      + (f" ev {r[s]['eval']['pass_med']} f60 {r[s]['eval']['f60']}" if 'eval' in r[s] else "")
                                      for s in RL.SPANS) + f"  {time.time() - t0:.0f}s")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args(argv)
    out = study(a.n)
    if not a.no_save:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print("wrote", os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
