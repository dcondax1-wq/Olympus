"""PAYOUT POLICY for the funded Builder 25K (owner 2026-11-17: ATLAS's 25K eval passed, "make the most of payouts").
PAPER RESEARCH ONLY: reads stored trades, writes research/lab/payout25.json; changes nothing live.

When and how much to request, every policy on the SAME Monte Carlo paths as tools/money/funded25.py (builder_levers seeds,
600 paths of 126 sessions, costs in, the live one-account rule for LIT + ATLAS), MFFU Builder 25K sim funded rules
(engine/funded_life builder25k = research/lit/mffu_rules.json: $25,000 start, $1,000 EOD trailing, floor locks at
start + $100 and sits there after the 1st payout, $600 soft DLL, 20 micros, payouts above the $1,100 buffer, $250 min /
$1,000 max a request, 80%, best day <= 50% of the cycle's profit, 2 traded days a cycle, 48 h first wait, 5 sim payouts).

Policies (amount = min($1,000, what sits above the buffer) unless a cushion is kept):
  today: ask at $750        the bot's line today (engine/funded_life ask_above 750)
  asap: $250                ask the first day MFFU allows ($250 above the buffer)
  ask at $500 / $1,000      wait until $500 / the $1,000 max sits above the buffer
  cushion $300 / $500       ask what sits above buffer + cushion (>= $250): the cushion stays as extra room
  consistency <= 40%        ask as soon as allowed, but only when the best day is <= 40% of the cycle (comfortably met)
  cycle-timed               $1,000 on the cycle's 2nd traded day, $250 less each day after, >= $250 (builder_levers cycle25)

Measured per policy: $ a month to the owner (80%, 6 months, sim payouts only: after the 5th the account moves to live, not
counted), first payout (median sessions + the date from --start), P(no payout in 6 months), P(account lost: floor hit or
stuck under $100 of room), payouts. Pick on H1 (2026 Jan-Jun), check on H2 (Jul-Oct 2026), show 2021-25.

    python -X utf8 tools/money/payout25.py [--n 600] [--start 2026-11-19]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import builder_levers as BL  # noqa: E402
import funded25 as F25  # noqa: E402

SA, U, np = BL.SA, BL.U, BL.np
OUT = os.path.join(BL.ROOT, "research", "lab", "payout25.json")
STUCK = 100.0

POLICIES = {
    "today: ask at $750": {"ask": 750.0},
    "asap: $250": {"ask": 250.0},
    "ask at $500": {"ask": 500.0},
    "ask at $1,000 (max)": {"ask": 1000.0},
    "cushion $300": {"ask": 250.0, "cushion": 300.0},
    "cushion $500": {"ask": 250.0, "cushion": 500.0},
    "consistency <= 40%": {"ask": 250.0, "cons": 0.4},
    "cycle-timed": {"ask": None, "cycle": "cycle25"},
}
MIXES = {k: F25.MIXES[k] for k in ("ATLAS alone (today)", "LIT + ATLAS $250")}


class PolicyFunded(BL.GF):
    """builder_levers.GF (the funded 25K + per-strategy sizing) with a request policy: ask line, cushion, consistency margin."""

    def __init__(self, plan, cfg, z, pol):
        super().__init__(plan, cfg, z, ask=pol.get("ask"), policy=pol.get("cycle"))
        self.pol = pol

    def _fast_track(self, day):
        tr = super()._fast_track(day)
        if tr["status"] not in ("ready", "eligible"):
            return tr
        P, pol = self.P, self.pol
        above = tr["above_buffer"]
        amt = min(float(P["pay_max"]), above - float(pol.get("cushion") or 0.0))
        ok = amt >= float(P["pay_min"]) and above >= float(P["ask_above"])
        if ok and pol.get("cons") is not None:
            cprof, best = sum(self.cyc), max(self.cyc) if self.cyc else 0.0
            ok = cprof > 0 and best <= float(pol["cons"]) * cprof + 1e-9
        tr = dict(tr)
        tr["status"] = "ready" if ok else "eligible"
        tr["max_request"] = round(amt, 2) if ok else tr["max_request"]
        return tr


def run(BY, paths, mk):
    """builder_levers.funded_run + stuck accounts counted as lost + the first payout's amount."""
    out = []
    for seq in paths:
        f = mk()
        owner, first, first_amt, npay, dead = 0.0, None, None, 0, False
        for k, si in enumerate(seq[:BL.LEN]):
            ev, x = f.step(BY[si])
            if ev in ("paid", "grad"):
                owner += x
                npay += 1
                if first is None:
                    first, first_amt = k + 1, x / f.split
            if ev == "lost":
                dead = True
                break
            if ev == "grad":
                break
        if not dead and f.state == "on":
            floor = max(f.floor, f.A["lock"]) if f.pays else f.floor
            dead = f.bal - floor < STUCK
        out.append((owner, first, npay, dead, first_amt))
    n = len(out)
    fr = [x[1] for x in out if x[1]]
    fa = [x[4] for x in out if x[4]]
    return {"per_month": round(float(np.mean([x[0] for x in out])) / BL.MO), "first_med": float(np.median(fr)) if fr else None,
            "first_p75": float(np.percentile(fr, 75)) if fr else None, "first_amt_med": round(float(np.median(fa))) if fa else None,
            "no_pay_6m": round(100.0 * (n - len(fr)) / n, 1), "lost_6m": round(100.0 * sum(1 for x in out if x[3]) / n, 1),
            "payouts": round(float(np.mean([x[2] for x in out])), 2), "paid_6m": round(float(np.mean([x[0] for x in out])))}


def pick(rows, mix):
    """H1: the most $ a month to the owner with no more lost and at most +2 points of no-payout vs today (ties: sooner first
    payout). Then H2 must also not lose $ vs today with the same guards, else today is kept."""
    base = "today: ask at $750"

    def ok(sp, nm):
        r, b = rows[sp][mix][nm], rows[sp][mix][base]
        return r["lost_6m"] <= b["lost_6m"] + 0.5 and r["no_pay_6m"] <= b["no_pay_6m"] + 2.0

    cand = [nm for nm in POLICIES if ok("H1", nm)]
    best = max(cand, key=lambda nm: (rows["H1"][mix][nm]["per_month"], -(rows["H1"][mix][nm]["first_med"] or 999)))
    h2 = ok("H2", best) and rows["H2"][mix][best]["per_month"] >= rows["H2"][mix][base]["per_month"]
    return {"h1_pick": best, "h2_holds": bool(h2), "adopt": best if h2 else base}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--start", default="2026-11-19", help="first funded session (for the first-payout date)")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args(argv)
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    import payout_plan as PP
    t0 = time.time()
    S = SA.data()["S"]
    PF = {sp: U.mc_paths(S, sp, a.n, length=BL.LEN, seed=BL.A4.SEED_LIFE) for sp in BL.SPANS}
    BYa = BL.by_mix(("ATLAS",))
    BYs, ov = F25.by_shared()
    cal = PP.calendar(BL.LEN + 5, start=a.start)
    out = {"date": "2026-11-17", "n": a.n, "start": a.start, "spans": U.SPAN, "overlap": ov, "policies": POLICIES, "rows": {}}
    for sp in BL.SPANS:
        out["rows"][sp] = {}
        for mx, (z, shared) in MIXES.items():
            row = {}
            for pn, pol in POLICIES.items():
                r = run(BYs if shared else BYa, PF[sp], lambda z=z, pol=pol: PolicyFunded("builder25k", U.UP25, z, pol))
                r["first_date"] = cal[int(r["first_med"]) - 1] if r["first_med"] else None
                row[pn] = r
                print(f"{sp:3s} {mx:20s} {pn:22s} ${r['per_month']:>4}/mo 1st {r['first_med']} ({r['first_date']}, "
                      f"${r['first_amt_med']}) nopay {r['no_pay_6m']}% lost {r['lost_6m']}% pays {r['payouts']} "
                      f"({time.time() - t0:.0f}s)", flush=True)
            out["rows"][sp][mx] = row
    out["pick"] = {mx: pick(out["rows"], mx) for mx in MIXES}
    print(json.dumps(out["pick"], indent=1))
    if not a.no_save:
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=float)
        print("wrote", os.path.relpath(OUT, BL.ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
