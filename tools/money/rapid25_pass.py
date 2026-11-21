"""Rapid EOD 25K: the fastest rule-legal pass (2026-11-21, day-rapid). PAPER RESEARCH ONLY: reads stored trades, writes
research/lab/rapid25_pass.json, changes nothing live. Design (committed first): research/second/rapid25_pass_design.md.
Write-up: research/writeups/rapid25-pass-2026-11-21.md.

Rows A0-A7 = (LIT lane rule, ATLAS lane rule) in the eval; the funded stage is unchanged. Engine = rapid25_lit_lane.LaneEv
(+ an ATLAS lane rule and an inactivity count) inside money_plan.RSeat via rapid25_launch.life_row; ATLAS at 10 ticks a side.

    python -X utf8 tools/money/rapid25_pass.py run [--n 1000]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "tools"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)

OUT = os.path.join(ROOT, "research", "lab", "rapid25_pass.json")
DESIGN = "research/second/rapid25_pass_design.md"
SPANS = ("H1", "H2", "REF")
ROWS = {"A0_today": ("skip", "guard"), "A1_lit_bank1": ("bank1", "guard"), "A2_lit_bankq": ("bankq", "guard"),
        "A3_lit_over1": ("over1", "guard"), "A4_atlas_bank1": ("skip", "bank1"), "A5_both_bank1": ("bank1", "bank1"),
        "A6_no_guard": ("none", "none"), "A7_atlas_only": ("atlas", "guard"),
        "A8_balance_aware": ("skip", "loose")}       # amendment: the guard on both lanes balance-aware (rapid_levers "loose")
INACTIVE = 5                 # trading days in a row without a trade = MFFU's 7-calendar-day inactivity rule


def _mods():
    import rapid25_lit_lane as RLL
    import rapid_levers as RL
    import stack_one_account as SOA
    return RLL, RL, SOA


def make_ev_class():
    RLL, RL, SOA = _mods()

    class PassEv(RLL.LaneEv):
        """LaneEv (the LIT lane rule) + an ATLAS lane rule ("guard" today / "bank1" / "none") + the longest run of
        sessions without a trade."""

        def __init__(self, cfg, E, z, lane="skip", alane="guard"):
            super().__init__(cfg, E, z, lane)
            self.alane, self.gap, self.maxgap = alane, 0, 0

        def _cap(self, q, t, cum):
            if self.alane == "none":
                return q
            return super()._cap(q, t, cum)

        def step(self, ts, keep=None):
            if self.alane == "bank1":
                ts = [self._atlas_bank(t) if not RL.lit_like(t, self.z) else t for t in ts]
            d0 = self.dtr
            out = super().step(ts, keep)
            if self.dtr > d0:
                self.gap = 0
            else:
                self.gap += 1
                self.maxgap = max(self.maxgap, self.gap)
            return out

        def _atlas_bank(self, t):
            return {**t, "_bank": True}

    # the ATLAS bank: the guard's 0 becomes 1 micro with its exit at the day's cap (only when the trade reached it)
    base_cap = RLL.LaneEv._cap if hasattr(RLL.LaneEv, "_cap") else RL.Ev._cap

    def _cap_bank(self, q, t, cum):
        if self.alane == "none":
            return q
        qg = base_cap(self, q, t, cum)
        if qg > 0 or q <= 0 or self.alane != "bank1":
            return qg
        E = self.E
        from engine import firms as FM
        cap_usd = E["cons"] * E["tgt"] * FM.BEST_DAY_MARGIN - max(0.0, cum)
        if cap_usd <= 0:
            return 0
        bp = RLL.bank_pts(cap_usd, 1)
        if bp <= 0 or bp < RLL.MIN_R * t["risk"] or (t["tgt"] and bp >= t["tgt"]):
            return 0
        if t["pts"] >= bp:                     # reached the bank: paid at the bank, not the target
            t["pts"] = bp
        self.st["atlas_bank"] = self.st.get("atlas_bank", 0) + 1
        return 1

    PassEv._cap = _cap_bank
    return PassEv


def spec(row):
    import rapid25 as R25
    RLL, RL, SOA = _mods()
    lane, alane = ROWS[row]
    sp = dict(R25.acct("25k", ("cushion", 500.0)))
    E, ec, z = sp["E"], sp["ecfg"], sp["z"]
    Ev = make_ev_class()
    if alane == "loose":                       # A8: rapid_levers' balance-aware guard ("loose") on LIT and ATLAS alike
        class LooseEv(RL.Ev):
            def __init__(self, *a):
                super().__init__(*a)
                self.gap, self.maxgap = 0, 0

            def step(self, ts, keep=None):
                d0 = self.dtr
                out = super().step(ts, keep)
                self.gap = 0 if self.dtr > d0 else self.gap + 1
                self.maxgap = max(self.maxgap, self.gap)
                return out
        sp["ev"] = lambda: LooseEv(ec, E, z, "loose")
        return sp
    sp["ev"] = lambda: Ev(ec, E, z, lane, alane)
    return sp


def eval_row(sp, PE):
    import rapid_levers as RL
    out = {}
    for s in SPANS:
        res = []
        for seq in PE[s]:
            e = sp["ev"]()
            o, used = "open", len(seq[:RL.H_EVAL])
            for k, si in enumerate(seq[:RL.H_EVAL]):
                r, _ = e.step([dict(t) for t in sp["BYe"][si]])
                if r:
                    o, used = ("pass" if r == "pass" else "fail"), k + 1
                    break
            res.append((o, used, e.maxgap))
        n = len(res)
        pas = [u for o, u, _ in res if o == "pass"]
        out[s] = {"p60": round(100.0 * len(pas) / n, 1), "f60": round(100.0 * sum(1 for o, _, _ in res if o == "fail") / n, 1),
                  "pass_med": float(np.median(pas)) if pas else None,
                  "pass_p25": float(np.percentile(pas, 25)) if pas else None, "pass_p75": float(np.percentile(pas, 75)) if pas else None,
                  "inactive": round(100.0 * sum(1 for _, _, g in res if g >= INACTIVE) / n, 1),
                  "maxgap_med": float(np.median([g for _, _, g in res]))}
    return out


def judge(R):
    H = ("H1", "H2")
    a0 = R["A0_today"]
    out, ok = {}, []
    for k, r in R.items():
        if k == "A0_today":
            continue
        why = []
        for s in H:
            if r["life"][s]["usd_m"] < 0.95 * a0["life"][s]["usd_m"]:
                why.append(f"{s} ${a0['life'][s]['usd_m']} -> ${r['life'][s]['usd_m']}/mo")
            if r["eval"][s]["f60"] > a0["eval"][s]["f60"] + 1.0:
                why.append(f"{s} eval fail {a0['eval'][s]['f60']} -> {r['eval'][s]['f60']}%")
        if r["life"]["REF"]["usd_m"] < a0["life"]["REF"]["usd_m"] - 10:
            why.append(f"REF ${a0['life']['REF']['usd_m']} -> ${r['life']['REF']['usd_m']}/mo")
        fast = all((r["eval"][s]["pass_med"] or 999) <= (a0["eval"][s]["pass_med"] or 999) - 2 for s in H)
        idle = all(r["eval"][s]["inactive"] <= a0["eval"][s]["inactive"] - 5 for s in H)
        if not (fast or idle):
            why.append("not 2+ sessions faster in both halves nor -5 pts inactivity")
        out[k] = {"qualifies": not why, "why_not": why}
        if not why:
            ok.append(k)
    win = min(ok, key=lambda k: sum(R[k]["eval"][s]["pass_med"] or 999 for s in H)) if ok else None
    return {"rows": out, "winner": win}


def cmd_run(n=1000, log=print):
    import rapid25_launch as RLA
    AR = RLA._AR()
    t0 = time.time()
    AR.rapid_patch(AR.T_at(1))
    PE = RLA.eval_paths(n)
    AR.rapid_patch(AR.T_at(10))
    res = {"date": "2026-11-21", "design": DESIGN, "n_paths": n, "cost": "ATLAS 10 ticks a side", "rows": {}}
    for k in ROWS:
        sp = spec(k)
        r = {"eval": eval_row(sp, PE), "life": RLA.life_row(sp, n)}
        res["rows"][k] = r
        log(f"{k:15s} " + " | ".join(f"{s} pass {r['eval'][s]['p60']}% in~{r['eval'][s]['pass_med']} fail {r['eval'][s]['f60']}% "
                                    f"idle {r['eval'][s]['inactive']}% ${r['life'][s]['usd_m']}/mo 1st {r['life'][s]['first_date']} "
                                    f"lost {r['life'][s]['lost_6m']}%" for s in SPANS) + f"  [{time.time() - t0:.0f}s]")
    res["judge"] = judge(res["rows"])
    res["took_s"] = round(time.time() - t0)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    log(json.dumps(res["judge"], indent=1))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run",))
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    cmd_run(a.n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
