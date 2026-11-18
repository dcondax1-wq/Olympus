"""Rapid EOD 25K: which LIT lane rule under the 30% best-day rule (owner buys the 25K this week, 2026-11-18). PAPER RESEARCH
ONLY: reads stored trades, writes research/lab/rapid25_lit_lane.json, changes nothing live.
Write-up: research/writeups/rapid25-lit-lane-2026-11-18.md.

Same accounts, trades, costs ($1.90 a micro + 1 tick) and Monte Carlo paths as tools/money/rapid25.py "25K, keep $500"
(eval 2,000 x 60 sessions seed 7, 6-month slot 1,000 x 126 seed 23, eval -> funded -> re-buy). Only the eval's LIT lane
changes (the 30% best-day rule is eval-only; MFFU checks it at the PASS, research/lit/mffu_rules.json rapid_eod_50k.eval
"best day <= 30% of the profit; not a breach, trade more days"; the 25K uses the same rule). ATLAS keeps today's guard.

  a  skip      today: LIT size, then the guard (1 micro's TARGET winner must keep the day <= 30% x $1,500 x 0.95 = $427
               incl. today's closed $); < 1 micro -> no trade.
  b  bank1     as a, but when the guard says 0: take 1 micro and bank (limit exit) at the day's remaining room
               (cap $ = $427 - today's closed $, exit at entry +/- (cap $ + $1.90) / $2 pts). Filled only if the trade's
               own best excursion (ledger mfe_r x stop) went 1 tick through that price; else the trade's own outcome.
               Taken only if the bank is >= MIN_R x the stop (no tiny banks for a full stop).
  b+ bankq     as b but at LIT's full size (no guard cut), banked at the remaining room (bigger stop-outs).
  c  over1     when the guard says 0: take 1 micro at the normal target; the day may break 30%, the pass then needs
               profit >= best day / 0.3 (MFFU: not a breach, trade more days).
  c+ none      LIT without the guard at all (full size, normal target).
  d  atlas     LIT off in the eval (ATLAS only); LIT + ATLAS once funded (no best-day rule there).

    python -X utf8 tools/money/rapid25_lit_lane.py            # -> research/lab/rapid25_lit_lane.json
    python -X utf8 tools/money/rapid25_lit_lane.py --n 200    # quicker
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import rapid_levers as RL  # noqa: E402
import rapid25 as R25  # noqa: E402
import stack_one_account as SOA  # noqa: E402
import uprisk as U  # noqa: E402
from engine import firms as FM  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from engine.lit import qty_for  # noqa: E402

OUT = os.path.join(ROOT, "research", "lab", "rapid25_lit_lane.json")
PV, COMM, SLIP, TICK = RL.PV, RL.COMM, RL.SLIP, 0.25
MIN_R = 1.0
_MFE = {}


def mfe_pts(t) -> float | None:
    """The trade's best excursion in points (ledger mfe_r x the stop), None if unknown."""
    if not _MFE:
        with open(os.path.join(U.HO, "COMPLETE_TRADE_LEDGER.csv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                try:
                    risk = abs(float(r["entry_price"]) - float(r["initial_stop"]))
                    _MFE[r["trade_id"]] = float(r["mfe_r"] or 0) * risk
                except (TypeError, ValueError):
                    pass
    return _MFE.get(t.get("id"))


def bank_pts(cap_usd: float, q: int) -> float:
    """The limit exit (points from the entry, rounded DOWN to a tick) whose fill pays <= cap $ on q micros after costs."""
    return math.floor((cap_usd + COMM * q) / (PV * q) / TICK) * TICK


def banked(t, q, cap_usd, min_r=MIN_R):
    """-> (pts, banked?) of the trade with a limit exit at the cap, or None when the bank is too small to take."""
    bp = bank_pts(cap_usd, q)
    if bp <= 0 or bp < min_r * t["risk"] or (t["tgt"] and bp >= t["tgt"]):
        return None
    m = mfe_pts(t)
    if m is None:
        return None
    if m >= bp + TICK - 1e-9:
        return bp, True
    return min(t["pts"], bp), False


class LaneEv(RL.Ev):
    """rapid_levers.Ev ("guard") with the LIT lane rule `lane` (ATLAS keeps the guard)."""

    def __init__(self, cfg, E, z, lane="skip", min_r=MIN_R, stats=None):
        super().__init__(cfg, E, z, "guard")
        self.lane, self.min_r, self.st = lane, min_r, stats if stats is not None else {}

    def _n(self, k):
        self.st[k] = self.st.get(k, 0) + 1

    def step(self, ts, keep=None):
        c, E, z = self.cfg, self.E, self.z
        dll = c.get("_dll", E["dll"])
        self.s += 1
        wkey = (self.s - 1) // 5
        cum, traded = 0.0, False
        sub = {k: v for k, v in c.items() if not k.startswith("_")}
        for t in ts:
            if cum <= -dll:
                break
            room = self.bal + cum - self.floor
            pts = t["pts"]
            if RL.lit_like(t, z):
                if self.lane == "atlas":
                    continue
                m0 = qty_for(t["risk"])
                if not m0:
                    continue
                st = {"profit": self.bal, "cum": cum, "room": room, "session": self.s, "n_today": 0,
                      "wk_pnl": self.wk.get(wkey, 0.0), "days_traded": self.dtr}
                q0 = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, sub, room=room, state=st,
                                learning=None, max_micros=c["_maxq"])["qty"]
                q0 = min(q0, c["_maxq"])
                if q0 <= 0:
                    continue
                self._n("lit_sized")
                qg = SOA.cons_cap(q0, t, E["cons"], E["tgt"], cum)
                cap_usd = E["cons"] * E["tgt"] * FM.BEST_DAY_MARGIN - max(0.0, cum)
                q = qg
                if self.lane == "none":
                    q = q0
                elif qg < q0 and self.lane in ("bank1", "bankq", "over1"):
                    if self.lane == "over1":
                        q = max(qg, 1)
                        if qg <= 0:
                            self._n("lit_over")
                    elif self.lane == "bank1" and qg <= 0 or self.lane == "bankq":
                        qb = 1 if self.lane == "bank1" else q0
                        b = banked(t, qb, cap_usd, self.min_r) if cap_usd > 0 else None
                        if b is not None:
                            q, pts = qb, b[0]
                            self._n("lit_bank_hit" if b[1] else "lit_bank_miss")
                if q <= 0:
                    self._n("lit_skip")
                    continue
                self._n("lit_taken")
            else:
                q = RL.q_add(t, z, room, cum, c["_maxq"], min(dll, SOA.SOFT_DLL))
                q = self._cap(q, t, cum)
            if q <= 0:
                continue
            traded = True
            pnl = pts * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            self.max_risk = max(self.max_risk, (t["risk"] + SLIP) * PV * q + COMM * q)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * q
                low = pnl
            if self.bal + cum + low <= self.floor:
                return "fail", round(self.floor - self.bal, 2)
            cum += pnl
        self.bal += cum
        self.wk[wkey] = self.wk.get(wkey, 0.0) + cum
        if traded:
            self.dtr += 1
            self.best = max(self.best, cum)
        if self.bal <= self.floor:
            return "fail", round(cum, 2)
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - E["mll"]), E["lock"])
        if self.bal >= E["tgt"] and self.dtr >= E.get("min_days", 1) and self.best <= E["cons"] * self.bal + 1e-9:
            return "pass", round(cum, 2)
        if self.bal - self.floor < c["_stuck"]:
            return "stuck", round(cum, 2)
        return None, round(cum, 2)


LANES = {
    "a  skip (today)": "skip",
    "b  1 micro, bank at the room": "bank1",
    "b+ full size, bank at the room": "bankq",
    "c  1 micro, let the day break 30%": "over1",
    "c+ no guard on LIT": "none",
    "d  LIT off in the eval (ATLAS only)": "atlas",
}


def spec(lane, min_r=MIN_R, stats=None):
    sp = R25.acct("25k", ("cushion", 500))
    E, ec, z = sp["E"], sp["ecfg"], sp["z"]
    sp["ev"] = lambda: LaneEv(ec, E, z, lane, min_r, stats)
    return sp


def study(n=1000, log=print, lanes=None, min_rs=(MIN_R,)):
    S = SOA.data()["S"]
    PE = {s: U.mc_paths(S, s, 2 * n, length=RL.H_EVAL, seed=R25.A4.SEED_EVAL) for s in RL.SPANS}
    PF = {s: U.mc_paths(S, s, n, length=RL.LEN, seed=R25.A4.SEED_LIFE) for s in RL.SPANS}
    out = {"date": "2026-11-18", "n": n, "spans": U.SPAN, "price": R25.PRICE["25k"], "min_r": list(min_rs), "rows": {}}
    t0 = time.time()
    rows = []
    for nm, ln in (lanes or LANES).items():
        if ln in ("bank1", "bankq"):
            rows += [(nm if len(min_rs) == 1 else f"{nm} (>= {mr:g}R)", ln, mr) for mr in min_rs]
        else:
            rows.append((nm, ln, MIN_R))
    for nm, ln, mr in rows:
        r = {}
        for s in RL.SPANS:
            stv = {}
            sp_e = spec(ln, mr, stv)
            ev = RL.eval_stats(sp_e, PE[s])
            sl = RL.group_stats(R25.run_group([spec(ln, mr)], PF[s]))
            r[s] = {"eval": ev, "slot": sl, "lit_counts_eval_paths": stv}
        out["rows"][nm] = r
        log(f"{nm:44s} " + " | ".join(f"{s} ev {r[s]['eval']['pass_med']} f10 {r[s]['eval']['f10']} f60 {r[s]['eval']['f60']} "
                                       f"1st {r[s]['slot']['first_any_med']} ${r[s]['slot']['net_m']}" for s in RL.SPANS)
            + f"  {time.time() - t0:.0f}s")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--min-r", type=float, nargs="*", default=[MIN_R])
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args(argv)
    out = study(a.n, min_rs=tuple(a.min_r))
    if not a.no_save:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print("wrote", os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
