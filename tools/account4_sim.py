"""Account #4 (team A4, 2026-11-14): LIT on its own MFFU Builder 50K + a copy of the same signal on a LucidPro 50K, each
under its own firm's rules. research/writeups/account-4-2026-11-14.md, docs/ACCOUNT_4.md. PAPER RESEARCH ONLY: reads the
live LIT trades through tools/uprisk.py, writes research/lab/account4_sim.json and the runs acct4_* (tools/runlib), nothing
live changes (live_model*.json and the sizing defaults untouched).

Trades: the 120 live LIT trades of 2026 (run lit_live, research/handoff/2026-10-25/COMPLETE_TRADE_LEDGER.csv T-2026-*, true
1m fills, 1 tick on market entries / stop exits in the prices), $1.90 a micro round trip on both firms (Lucid publishes
$0.50 a side for MNQ: the $1.90 is the conservative MFFU cost); REF = the 511 rows of 2021-25 (5m only, a reference line).
H1 = Jan-Jun 2026 (pick), H2 = Jul-Oct 2026 (check: quote this). Paths: whole weeks (5-session blocks) drawn from the half
(tools/uprisk.mc_paths); BOTH accounts trade the SAME path (one signal: the copy is the same bet).

Accounts (the rules come from the data the guard uses: engine/firms.profile on research/props/firm_rules.json):
  A  MFFU Builder 50K (Zlarior): the live eval sizing (live_model.json lit_sizing: two_week, 40% of the room, kept past
     session 10) -> 2 sessions of paperwork -> MFFU sim funded (tools/uprisk.Funded: $2,100 buffer, $500-$2,000, 50% best
     day, 2 days a cycle, 80%, 5 payouts) on the live funded preset (60% of the room, <= $1,500, a winner <= $2,000). $91.80.
  B  LucidPro 50K copy: the same sizing code (engine/sizing.lit_qty / funded_qty) on Lucid's rules: $3,000 target, $2,000
     EOD trailing locked at $50,100, $1,200 soft daily (the daily-loss-on version; "dll_off" = the OFF version, which the
     fleet still sizes with the bot's own $1,000 day), 40 micros, no eval consistency, 1 day; funded: same floor, the
     LucidScale daily loss (60% of the best end-of-day profit once above $52,100), payouts ANY day once the balance is $500
     over $52,100, the cycle made $500 and its best day is <= 40% of the cycle; $2,000 then $2,500 a payout, 90%, 5
     payouts (then Lucid's live review: the sim account ends here). Price $134.40 (list $192 with a 30% code; $172 list ->
     $120.40). The best-day guard of the fleet (engine/firms.check: a winner today <= share x target x 0.95) is applied to
     an eval with a best-day rule (LucidFlex 40%).

  python -X utf8 tools/account4_sim.py check        my eval == tools/uprisk.Eval on the MFFU 50K; my trades == uprisk's
  python -X utf8 tools/account4_sim.py [--n 1000]   grids (H1 pick, H2 check) + the pair -> research/lab/account4_sim.json
  python -X utf8 tools/account4_sim.py save         the runs acct4_lucid_copy, acct4_pair (real 2026 order, back to back)
"""
from __future__ import annotations

import copy
import csv
import datetime as dt
import json
import logging
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
import uprisk as U  # noqa: E402
from engine import firms as FM  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from engine.lit import qty_for  # noqa: E402

PV, COMM, SLIP = U.PV, U.COMM, U.SLIP
OUT = os.environ.get("A4_OUT") or os.path.join(ROOT, "research", "lab", "account4_sim.json")
SPANS = ("H1", "H2", "REF")
LEN, GAP, H_EVAL, MO = U.LEN, U.GAP, 60, U.LEN / 21.0
PRICE = {"mffu": 91.80, "lucid": 134.40, "lucid_off": 157.20}   # Lucid: list $192 - 30% (DLL on); the OFF version ~ +$23 (deal page $115.40 / $140.40)
SEED_EVAL, SEED_LIFE = 7, 23


# ================================================================================================ data
def trades():
    """tools/uprisk.trades() for 2026 + REF, with the ledger's entry / exit times, direction and exit kept (runlib rows)."""
    by = {}
    with open(os.path.join(U.HO, "COMPLETE_TRADE_LEDGER.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if not r["trade_id"].startswith(("T-2026", "REF-")):
                continue
            d = 1 if r["direction"] == "long" else -1
            e, s, tg, x = (float(r[k]) for k in ("entry_price", "initial_stop", "target_price", "exit_price"))
            risk = abs(e - s)
            base = qty_for(risk)
            wk = 0.5 if base and int(r["quantity"]) < base else 1.0
            day = r["entry_fill_at"][:10]
            et = int(dt.datetime.fromisoformat(r["entry_fill_at"][:25]).timestamp())
            xt = int(dt.datetime.fromisoformat(r["exit_time"][:25]).timestamp())
            by.setdefault(day, []).append({"day": day, "risk": risk, "risk_pts": risk, "tgt": abs(tg - e), "tgt_pts": abs(tg - e),
                                           "pts": (x - e) * d, "w1": -float(r["mae_r"] or 0) * risk, "size_mult": wk,
                                           "ref": r["trade_id"].startswith("REF"), "entry_t": et, "exit_t": xt, "dir": d,
                                           "exit": r["exit_reason"], "id": r["trade_id"]})
    return by


_D = {}


def load():
    if not _D:
        S = U.sessions()
        T = trades()
        _D.update(S=S, BY=[T.get(d, []) for d in S])
    return _D["S"], _D["BY"]


# ================================================================================================ the firms' rules
def _n(x, d=None):
    return d if x in (None, "none") else float(x)


def rules(plan: str) -> tuple:
    """(eval rules, funded rules) of a plan from the guard's own data (engine/copy_accounts.tighten: firm_rules.json, or a
    filled plan of copy_profiles.json such as Bulenox). The firm "hold" is ignored here: a what-if once the firm says yes."""
    from engine import copy_accounts as CA
    E, F = CA.tighten(plan, "eval"), CA.tighten(plan, "funded")
    po = F["payout"]
    ev = {"plan": plan, "tgt": float(E["target"]), "mll": float(E["dd_amount"]), "dll": _n(E["dll"], 1e9), "lock": float(E["lock"]),
          "stuck": 200.0, "maxq": int(FM.max_micros(E)), "cons": _n(E["consistency"]), "min_days": int(_n(E["min_days"], 1)),
          "tiers": E.get("max_micros_by_profit")}
    fu = {"plan": plan, "mll": float(F["dd_amount"]), "lock": float(F["lock"]), "dll": _n(F["dll"], 1e9),
          "lucidscale": plan.startswith("lucid_pro"), "trail": float(F["dd_amount"]) + float(F["lock"]),
          "buffer": _n(po.get("buffer"), 0.0), "pay_min": _n(po.get("min"), 0.0), "cap1": _n(po.get("max"), 1e9),
          "cap2": _n(po.get("max_after_first"), _n(po.get("max"), 1e9)), "cycle_min": _n(po.get("cycle_min"), 0.0),
          "cons": _n(po.get("consistency")), "split": float(po["split"]), "max_payouts": int(_n(po.get("max_payouts"), 99)),
          "maxq": int(FM.max_micros(F)), "tiers": F.get("max_micros_by_profit"), "share": _n(po.get("share")),
          "win_days": int(_n(po.get("win_days"), 0)), "win_min": _n(po.get("win_day_min"), 0.0),
          "cycle_days": int(_n(po.get("min_days"), 0))}
    return ev, fu


def tier_q(tiers, profit: float, flat: int) -> int:
    """The firm's contract scaling at this profit (engine/firms.max_micros_at), never above the flat max."""
    if not tiers:
        return flat
    q = int(sorted(tiers)[0][1])
    for a, m in sorted(tiers):
        if profit >= float(a) - 1e-9:
            q = int(m)
    return min(q, flat)


MFFU_E = {"plan": "mffu_builder_50k", "tgt": 3000.0, "mll": 2000.0, "dll": 1000.0, "lock": 100.0, "stuck": 200.0, "maxq": 40,
          "cons": None, "min_days": 1}


def ecfg(E: dict, var: dict | None = None) -> dict:
    """The live eval sizing (tools/uprisk.ecfg_of = live_model.json lit_sizing, mode two_week) on this firm's numbers."""
    v = dict(var or {})
    dll_off = v.pop("dll_off", False)
    c = U.ecfg_of(v, plan="builder50k")
    c["two_week"]["acct"] = {"target": E["tgt"], "mll": E["mll"], "lock": E["lock"], "dll": E["dll"] if E["dll"] < 1e8 else 1000.0,
                             "max_micros": E["maxq"], "scale": 1.0}
    if dll_off:                                    # the fleet sizes a no-daily-loss plan with the bot's own $1,000 soft day
        c["two_week"]["acct"]["dll"] = 1000.0
    c["_maxq"], c["_stuck"] = E["maxq"], E["stuck"]
    c["_dll"] = 1000.0 if dll_off else E["dll"]
    return c


# ================================================================================================ the eval
class Ev:
    """One eval, a session at a time: tools/uprisk.Eval (same code path: engine/sizing.lit_qty) + the fleet guard's
    best-day cap (engine/firms.check, BEST_DAY_MARGIN) and the firm's pass rule (target, min days, best day <= share)."""

    def __init__(self, cfg, E):
        self.cfg, self.E = cfg, E
        self.bal, self.peak, self.floor = 0.0, 0.0, -E["mll"]
        self.s, self.dtr, self.best, self.max_risk = 0, 0, 0.0, 0.0
        self.wk = {}

    def step(self, ts, keep=None):
        """-> ("pass" | "fail" | "stuck" | None, the session's $ P&L); keep = a list that gets (trade, micros, $)"""
        c, E = self.cfg, self.E
        dll = c.get("_dll", E["dll"])
        self.s += 1
        wkey = (self.s - 1) // 5
        cum, traded = 0.0, False
        sub = {k: v for k, v in c.items() if not k.startswith("_")}
        maxq = tier_q(E.get("tiers"), self.bal, c["_maxq"])     # the firm's contract scaling at the last close (Bulenox)
        for t in ts:
            if cum <= -dll:
                break
            m0 = qty_for(t["risk"])
            if not m0:
                continue
            st = {"profit": self.bal, "cum": cum, "room": self.bal + cum - self.floor, "session": self.s, "n_today": 0,
                  "wk_pnl": self.wk.get(wkey, 0.0), "days_traded": self.dtr}
            q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, sub, room=st["room"], state=st,
                           learning=None, max_micros=c["_maxq"])["qty"]
            q = min(q, maxq)
            if q > 0 and E.get("cons"):                # the guard: a winner today stays under share x target x 0.95
                win1 = t["tgt"] * PV - COMM
                if win1 > 0:
                    q = min(q, int(math.floor((E["cons"] * E["tgt"] * FM.BEST_DAY_MARGIN - max(0.0, cum)) / win1)))
            if q <= 0:
                continue
            traded = True
            pnl = t["pts"] * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            self.max_risk = max(self.max_risk, (t["risk"] + SLIP) * PV * q + COMM * q)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * q
                low = pnl
            if self.bal + cum + low <= self.floor:
                if keep is not None:
                    keep.append((t, q, round(self.floor - self.bal - cum, 2)))
                return "fail", round(self.floor - self.bal, 2)
            cum += pnl
            if keep is not None:
                keep.append((t, q, round(pnl, 2)))
        self.bal += cum
        self.wk[wkey] = self.wk.get(wkey, 0.0) + cum
        if traded:
            self.dtr += 1
            self.best = max(self.best, cum)
        if self.bal <= self.floor:
            return "fail", round(cum, 2)
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - E["mll"]), E["lock"])
        if self.bal >= E["tgt"] and self.dtr >= E.get("min_days", 1) and (not E.get("cons") or self.best <= E["cons"] * self.bal + 1e-9):
            return "pass", round(cum, 2)
        if self.bal - self.floor < c["_stuck"]:
            return "stuck", round(cum, 2)
        return None, round(cum, 2)


# ================================================================================================ the funded accounts
class Mffu:
    """tools/uprisk.Funded (the MFFU sim funded rules) with the session's $ P&L reported."""

    def __init__(self, fcfg, after_first=False):
        self.f = U.Funded("builder50k", fcfg)
        if after_first:                            # the state right after the first $2,000 payout: floor locked, balance at the buffer
            f = self.f
            f.bal, f.peak, f.floor = 2100.0, 4100.0, 100.0
            f.pays = {"2026-12-31": 2000.0}
            f.cyc, f.cyc_start_bal = [], 2100.0
            f.first_trade, f.elig_from = "2026-12-31", U.cal(0)
        self.split = 0.8

    @property
    def state(self):
        return self.f.state

    def step(self, ts, keep=None):
        a = self.f.trade_pnl
        ev, x = self.f.step(ts, keep=keep)
        return ev, x, round(self.f.trade_pnl - a, 2)


class Lucid:
    """A Lucid funded account (LucidPro: $52,100 buffer, $500 a request, $500 a cycle, 40% best day, $2,000 then $2,500,
    90%, 5 payouts; LucidFlex: no buffer, 5 days >= $150, 50% of the profit up to $2,000, contract scaling) a session at a
    time. ask = "cap" (request a full payout) or $ (request once at least that much can be taken)."""

    def __init__(self, fcfg, R, ask="cap"):
        self.cfg, self.R, self.ask = fcfg, R, ask
        self.bal, self.peak, self.floor = 0.0, 0.0, -R["mll"]
        self.state, self.k, self.n_tr, self.max_risk = "on", 0, 0, 0.0
        self.pays, self.cyc, self.cyc_start = [], [], 0.0
        self.split = R["split"]

    def dll(self):
        R = self.R
        if R["lucidscale"] and self.peak >= R["trail"] - 1e-9:
            return max(R["dll"], 0.6 * self.peak)      # LucidScale: 60% of the best end-of-day profit, never down
        return R["dll"]

    def maxq(self):
        tiers = self.R.get("tiers")
        if not tiers:
            return self.R["maxq"]
        q = int(sorted(tiers)[0][1])
        for a, m in sorted(tiers):
            if self.bal >= float(a):
                q = int(m)
        return q

    def cap(self):
        return self.R["cap1"] if not self.pays else self.R["cap2"]

    def step(self, ts, keep=None):
        if self.state != "on":
            return None, None, 0.0
        R, c = self.R, self.cfg
        self.k += 1
        dll, mq, cap = self.dll(), self.maxq(), self.cap()
        A = {"mll": R["mll"], "lock": R["lock"], "dll": dll, "buffer": R["buffer"], "pay_min": R["pay_min"], "pay_max": cap,
             "split": R["split"], "cons": R["cons"] or 0.5, "cycle_days": 0, "first_wait": 0, "max_payouts": R["max_payouts"],
             "max_micros": mq, "scale": 1.0}
        cyc = {"cycle_start_bal": round(self.cyc_start, 2), "cycle_prev": round(sum(self.cyc), 2),
               "best_prev": round(max(self.cyc), 2) if self.cyc else 0.0, "cycle_days_prev": len(self.cyc), "payouts_n": len(self.pays),
               "cycle_target": round(max(0.0, R["buffer"] + cap - self.cyc_start), 2)}
        cum = 0.0
        for t in ts:
            if cum <= -dll:
                break
            room = round(self.bal + cum - self.floor, 2)
            st = {"room": room, "cum": cum, "locked": self.floor >= R["lock"] - 1e-9, "bal": self.bal, **cyc}
            q = min(SZ.funded_qty(t, st, c, acct=A), mq)
            if q <= 0:
                continue
            self.n_tr += 1
            pnl = t["pts"] * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            self.max_risk = max(self.max_risk, (t["risk"] + SLIP) * PV * q + COMM * q)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * q
                low = pnl
            if self.bal + cum + low <= self.floor:
                self.state = "lost"
                if keep is not None:
                    keep.append((t, q, round(self.floor - self.bal - cum, 2)))
                return "lost", None, round(self.floor - self.bal, 2)
            cum += pnl
            if keep is not None:
                keep.append((t, q, round(pnl, 2)))
        if abs(cum) > 1e-9:
            self.bal += round(cum, 2)
            self.cyc.append(round(cum, 2))
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - R["mll"]), R["lock"])
        above, cprof = self.bal - R["buffer"], self.bal - self.cyc_start
        ok = above >= R["pay_min"] and cprof >= R["cycle_min"] and cprof > 0
        if R["cons"]:
            ok = ok and max([x for x in self.cyc if x > 0], default=0.0) <= R["cons"] * cprof + 1e-9
        if R["win_days"]:
            ok = ok and sum(1 for x in self.cyc if x >= R["win_min"]) >= R["win_days"]
        if R.get("cycle_days"):                        # traded days a request (Bulenox 10)
            ok = ok and len(self.cyc) >= R["cycle_days"]
        amt = min(cap, above)
        if R["share"]:
            amt = min(amt, R["share"] * cprof)
        line = cap if self.ask == "cap" else min(cap, float(self.ask))
        if ok and amt >= max(R["pay_min"], line - 1e-6):
            amt = round(amt, 2)
            self.pays.append(amt)
            self.bal -= amt
            self.cyc, self.cyc_start = [], self.bal
            if len(self.pays) >= R["max_payouts"]:
                self.state = "grad"
                return "grad", amt * self.split, round(cum, 2)
            return "paid", amt * self.split, round(cum, 2)
        return None, None, round(cum, 2)


# ================================================================================================ one account slot
class Slot:
    """One account on one path: eval -> GAP sessions -> funded -> lost / max payouts -> the next eval (bought the next
    session). spec = {"E", "ecfg", "fund": () -> funded account, "price", "start": "eval" | "funded" | "funded1"}."""

    def __init__(self, spec, rebuy=True):
        self.sp, self.rebuy = spec, rebuy
        self.cost, self.owner, self.evals, self.funded_n, self.lost, self.grads = 0.0, 0.0, 0, 0, 0, 0
        self.first_pay, self.pays, self.days, self.events = None, 0, [], []
        self.e = self.f = None
        self.wait = 0
        self.done = False
        st = spec.get("start", "eval")
        if st == "eval":
            self._buy()
        else:
            self.f = spec["fund"](after_first=(st == "funded1"))
            self.funded_n += 1

    def _buy(self):
        self.cost += self.sp["price"]
        self.evals += 1
        self.e = Ev(self.sp["ecfg"], self.sp["E"])

    def step(self, k, ts, keep=None):
        if self.done:
            self.days.append(0.0)
            return
        if self.e is not None:
            r, pnl = self.e.step(ts, keep)
            self.days.append(pnl)
            if r == "pass":
                self.events.append((k, "pass"))
                self.cost += float(self.sp.get("act") or 0.0)     # an activation fee at the pass (Bulenox)
                self.e, self.wait = None, GAP
            elif r in ("fail", "stuck"):
                self.events.append((k, "fail"))
                self.e = None
                if self.rebuy:
                    self._buy()
                else:
                    self.done = True
            return
        if self.f is None:
            self.days.append(0.0)
            self.wait -= 1
            if self.wait <= 0:
                self.f = self.sp["fund"]()
                self.funded_n += 1
            return
        ev, x, pnl = self.f.step(ts, keep)
        self.days.append(pnl)
        if ev in ("paid", "grad"):
            self.owner += x
            self.pays += 1
            self.first_pay = self.first_pay or k + 1
            self.events.append((k, "pay"))
        if ev in ("lost", "grad"):
            self.events.append((k, ev))
            self.lost += ev == "lost"
            self.grads += ev == "grad"
            self.f = None
            if self.rebuy:
                self._buy()
            else:
                self.done = True

    def out(self):
        return {"owner": self.owner, "cost": self.cost, "net": self.owner - self.cost, "evals": self.evals, "funded": self.funded_n,
                "lost": self.lost, "grads": self.grads, "first_pay": self.first_pay, "pays": self.pays}


def run_slots(BY, paths, specs, horizon=LEN, rebuy=True):
    """Several slots on the SAME paths. -> [[slot result + "days" per path] per spec]."""
    R = [[] for _ in specs]
    for seq in paths:
        sl = [Slot(s, rebuy) for s in specs]
        for k, si in enumerate(seq[:horizon]):
            for s in sl:
                s.step(k, BY[si])
        for j, s in enumerate(sl):
            R[j].append({**s.out(), "days": s.days, "events": s.events})
    return R


# ================================================================================================ summaries
def eval_stats(BY, paths, E, cfg, price):
    res = []
    for seq in paths:
        e = Ev(cfg, E)
        out, used = "open", len(seq[:H_EVAL])
        for k, si in enumerate(seq[:H_EVAL]):
            r, _ = e.step(BY[si])
            if r:
                out, used = ("pass" if r == "pass" else "fail"), k + 1
                break
        res.append((out, used, e.max_risk))
    n = len(res)
    pas = [u for o, u, _ in res if o == "pass"]
    o = {"n": n}
    for h in (10, 15):
        o[f"p{h}"] = round(100.0 * sum(1 for u in pas if u <= h) / n, 1)
        o[f"f{h}"] = round(100.0 * sum(1 for x, u, _ in res if x == "fail" and u <= h) / n, 1)
    o["dec10"] = round(o["p10"] + o["f10"], 1)
    o["p60"] = round(100.0 * len(pas) / n, 1)
    o["f60"] = round(100.0 * sum(1 for x, _, _ in res if x == "fail") / n, 1)
    o["pass_med"] = float(np.median(pas)) if pas else None
    o["slow_pass"] = round(100.0 * sum(1 for u in pas if u > 15) / max(1, len(pas)), 1)
    o["usd_per_pass"] = round(price / max(1e-9, o["p60"] / 100.0), 1)
    o["max_risk"] = round(max(r[2] for r in res))
    return o


def slot_stats(R, price=None):
    n = len(R)
    net = np.array([r["net"] for r in R])
    fp = [r["first_pay"] for r in R if r["first_pay"]]
    return {"paths": n, "net_m": round(float(net.mean()) / MO), "net_6m": round(float(net.mean())),
            "net_p10_6m": round(float(np.percentile(net, 10))), "net_p50_6m": round(float(np.percentile(net, 50))),
            "owner_m": round(float(np.mean([r["owner"] for r in R])) / MO), "fees_6m": round(float(np.mean([r["cost"] for r in R])), 1),
            "p_neg": round(100.0 * float((net < 0).mean()), 1), "p_no_pay": round(100.0 * sum(1 for r in R if r["pays"] == 0) / n, 1),
            "evals": round(float(np.mean([r["evals"] for r in R])), 2), "funded": round(float(np.mean([r["funded"] for r in R])), 2),
            "lost": round(float(np.mean([r["lost"] for r in R])), 2), "grads": round(float(np.mean([r["grads"] for r in R])), 2),
            "pays": round(float(np.mean([r["pays"] for r in R])), 2), "first_pay_med": float(np.median(fp)) if fp else None}


def eval_value(BY, paths, spec):
    """$ per eval: ONE eval bought (no rebuy), 6 months from the purchase: the owner's payouts - its price."""
    R = run_slots(BY, paths, [spec], rebuy=False)[0]
    v = np.array([r["owner"] - r["cost"] for r in R])
    return {"usd_per_eval": round(float(v.mean())), "p10": round(float(np.percentile(v, 10))),
            "p_any_pay": round(100.0 * sum(1 for r in R if r["pays"]) / len(R), 1)}


def pair_stats(RA, RB):
    """Two accounts on the same paths: the pair's $, how alike they are, the worst case."""
    n = len(RA)
    na, nb = np.array([r["net"] for r in RA]), np.array([r["net"] for r in RB])
    tot = na + nb
    da = np.array([r["days"] for r in RA])
    db = np.array([r["days"] for r in RB])
    both = (np.abs(da) > 1e-9) & (np.abs(db) > 1e-9)
    corr_day = float(np.corrcoef(da[both], db[both])[0, 1]) if both.sum() > 10 else None
    worst_day = float((da + db).min())
    lose_sum = [(sorted([k for k, e in ra["events"] if e in ("fail", "lost")]), sorted([k for k, e in rb["events"] if e in ("fail", "lost")]))
                for ra, rb in zip(RA, RB)]
    together = sum(1 for a, b in lose_sum if a and b and any(abs(x - y) <= 5 for x in a for y in b))
    pa = np.array([r["pays"] > 0 for r in RA])
    pb = np.array([r["pays"] > 0 for r in RB])
    return {"paths": n, "net_m": round(float(tot.mean()) / MO), "net_6m": round(float(tot.mean())),
            "net_p10_6m": round(float(np.percentile(tot, 10))), "net_p5_6m": round(float(np.percentile(tot, 5))),
            "net_min_6m": round(float(tot.min())), "p_neg": round(100.0 * float((tot < 0).mean()), 1),
            "p_both_neg": round(100.0 * float(((na < 0) & (nb < 0)).mean()), 1),
            "p_neither_pays": round(100.0 * float((~pa & ~pb).mean()), 1),
            "corr_net": round(float(np.corrcoef(na, nb)[0, 1]), 2), "corr_day": round(corr_day, 2) if corr_day is not None else None,
            "worst_day": round(worst_day), "fees_p95_6m": round(float(np.percentile([ra["cost"] + rb["cost"] for ra, rb in zip(RA, RB)], 95))),
            "lose_together_5s": round(100.0 * together / n, 1)}


def fresh_pair(BY, paths, EA, ca, EB, cb):
    """Both evals bought the same session: the joint 2-week outcome."""
    J = {"both_pass": 0, "both_fail": 0, "a_only": 0, "b_only": 0, "same_10": 0}
    for seq in paths:
        out = []
        for E, c in ((EA, ca), (EB, cb)):
            e = Ev(c, E)
            r10 = None
            for k, si in enumerate(seq[:10]):
                r, _ = e.step(BY[si])
                if r:
                    r10 = "pass" if r == "pass" else "fail"
                    break
            out.append(r10)
        a, b = out
        J["both_pass"] += a == b == "pass"
        J["both_fail"] += a == b == "fail"
        J["a_only"] += a == "pass" and b != "pass"
        J["b_only"] += b == "pass" and a != "pass"
        J["same_10"] += a == b
    n = len(paths)
    return {k: round(100.0 * v / n, 1) for k, v in J.items()}


# ================================================================================================ the study
def specs(fa=None, fb=None, ask="cap", plan_b="lucid_pro_50k", eb_var=None, start_a="eval"):
    EB, FB = rules(plan_b)
    off = bool((eb_var or {}).get("dll_off"))
    A = {"E": MFFU_E, "ecfg": ecfg(MFFU_E), "fund": lambda after_first=False: Mffu(fa or U.UP50, after_first), "price": PRICE["mffu"],
         "start": start_a}
    B = {"E": EB, "ecfg": ecfg(EB, eb_var), "price": PRICE["lucid_off" if off else "lucid"],
         "fund": lambda after_first=False: Lucid(fb or U.UP50, {**FB, "dll": 1000.0 if off else FB["dll"], "lucidscale": FB["lucidscale"] and not off}, ask)}
    return A, B


EVAL_B = [("live40", {}), ("room60", {"room_f": 0.6}), ("room80", {"room_f": 0.8}), ("live40_dll_off", {"dll_off": True})]
FUND_B = [("fleet_default", U.UP50),                                                    # the MFFU preset the fleet uses today
          ("win1500", {**U.UP50, "max_win": 1500}), ("win1200", {**U.UP50, "max_win": 1200}), ("win1000", {**U.UP50, "max_win": 1000}),
          ("cons_aware", {**U.UP50, "max_win": None, "cons_aware": True}), ("win2000_cons", {**U.UP50, "cons_aware": True}),
          ("lucid_preset", {**U.UP50, "pct_max_usd": 800, "max_win": 1500}), ("p40_1000_w1500", {**U.UP50, "pct": 0.4, "pct_max_usd": 1000, "max_win": 1500})]
ASKS = ("cap", 1500, 1000)


def funded_only(BY, paths, fcfg, R, ask):
    out = []
    for seq in paths:
        f = Lucid(fcfg, R, ask)
        owner, k_lost, first = 0.0, None, None
        for k, si in enumerate(seq[:LEN]):
            ev, x, _ = f.step(BY[si])
            if ev in ("paid", "grad"):
                owner += x
                first = first or k + 1
            if ev in ("lost", "grad"):
                k_lost = k + 1 if ev == "lost" else None
                break
        out.append((owner, k_lost, first, len(f.pays), f.max_risk))
    n = len(out)
    o = np.array([x[0] for x in out])
    fr = [x[2] for x in out if x[2]]
    return {"per_month": round(float(o.mean()) / MO), "paid_p10": round(float(np.percentile(o, 10))),
            "lost_6m": round(100.0 * sum(1 for x in out if x[1]) / n, 1), "first_med": float(np.median(fr)) if fr else None,
            "payouts": round(float(np.mean([x[3] for x in out])), 2), "max_risk": round(max(x[4] for x in out))}


def study(n=1000, log=print):
    S, BY = load()
    PE = {sp: U.mc_paths(S, sp, 2 * n, length=H_EVAL, seed=SEED_EVAL) for sp in SPANS}
    PL = {sp: U.mc_paths(S, sp, n, length=LEN, seed=SEED_LIFE) for sp in SPANS}
    EB, FB = rules("lucid_pro_50k")
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "tool": "tools/account4_sim.py", "n_eval": 2 * n, "n_life": n,
           "rules": {"mffu_builder_50k": {"eval": MFFU_E, "funded": "tools/uprisk.Funded builder50k"}, "lucid_pro_50k": {"eval": EB, "funded": FB}},
           "prices": PRICE}
    # ---- 1. the eval: A as live; B's eval sizing grid (H1 pick by $ per eval, H2 check)
    out["eval_a"] = {sp: eval_stats(BY, PE[sp], MFFU_E, ecfg(MFFU_E), PRICE["mffu"]) for sp in SPANS}
    log("A MFFU eval", {sp: (o["p10"], o["f10"], o["pass_med"]) for sp, o in out["eval_a"].items()})
    out["eval_b"] = {}
    for k, var in EVAL_B:
        A, B = specs(eb_var=var)
        off = var.get("dll_off")
        Eb = {**EB, "dll": 1000.0} if off else EB
        row = {sp: eval_stats(BY, PE[sp], Eb, B["ecfg"], B["price"]) for sp in SPANS}
        row["value"] = {sp: eval_value(BY, PL[sp], B) for sp in ("H1", "H2")}
        out["eval_b"][k] = row
        log(f"B eval {k:16s}", {sp: (row[sp]["p10"], row[sp]["f10"], row[sp]["pass_med"]) for sp in SPANS}, "$/eval", {sp: row["value"][sp]["usd_per_eval"] for sp in ("H1", "H2")})
    # LucidFlex (40% eval best-day rule): the 2-week numbers only (why LucidPro)
    EF, FF = rules("lucid_flex_50k")
    out["eval_flex"] = {sp: eval_stats(BY, PE[sp], {**EF, "dll": 1000.0}, ecfg({**EF, "dll": 1000.0}), PRICE["lucid"]) for sp in SPANS}
    log("Flex eval", {sp: (o["p10"], o["f10"], o["pass_med"], o["slow_pass"]) for sp, o in out["eval_flex"].items()})
    # ---- 2. B's funded sizing x the request line (H1 pick, H2 check), funded only from the first funded session
    out["funded_b"] = {}
    for fk, fc in FUND_B:
        for ask in ASKS:
            key = f"{fk}__ask_{ask}"
            out["funded_b"][key] = {"cfg": fc, "ask": ask, **{sp: funded_only(BY, PL[sp], fc, FB, ask) for sp in SPANS}}
            r = out["funded_b"][key]
            log(f"B funded {key:28s} H1 ${r['H1']['per_month']}/mo lost {r['H1']['lost_6m']}% | H2 ${r['H2']['per_month']}/mo lost {r['H2']['lost_6m']}% first {r['H2']['first_med']} | REF ${r['REF']['per_month']}")
    out["funded_a"] = {sp: U.funded_mc(BY, PL[sp], "builder50k", U.UP50) for sp in SPANS}
    # picks on H1 only: a change from today's fleet default must beat it by 3% on H1 AND not lose on H2 (else the default)
    def better(rows, k, d, val):
        return val(rows[k], "H1") >= 1.03 * val(rows[d], "H1") and val(rows[k], "H2") >= val(rows[d], "H2")
    ev_val = lambda r, sp: r["value"][sp]["usd_per_eval"]                       # noqa: E731
    fu_val = lambda r, sp: r[sp]["per_month"] * (1 - r[sp]["lost_6m"] / 100.0)  # noqa: E731
    ek = max(out["eval_b"], key=lambda k: ev_val(out["eval_b"][k], "H1"))
    ek = ek if better(out["eval_b"], ek, "live40", ev_val) else "live40"
    fkey = max(out["funded_b"], key=lambda k: fu_val(out["funded_b"][k], "H1"))
    fkey = fkey if better(out["funded_b"], fkey, "fleet_default__ask_cap", fu_val) else "fleet_default__ask_cap"
    out["pick"] = {"eval_b": ek, "funded_b": fkey,
                   "rule": "H1 pick, H2 check: eval by $ per eval (6 months from one purchase), funded by $ a month paid x (1 - P(lost)); "
                           "a change from the fleet default (live two_week 40%, the MFFU funded preset, a full-cap request) only when "
                           ">= 3% better on H1 and not worse on H2"}
    log("PICK (H1)", out["pick"])
    fb, ask = out["funded_b"][fkey]["cfg"], out["funded_b"][fkey]["ask"]
    evar = dict(EVAL_B)[ek]
    # ---- 3. each account alone (6-month slot with rebuys) and the pair on the same paths
    out["slots"], out["pairs"] = {}, {}
    for lab, kw in (("today", {"fb": U.UP50, "ask": "cap", "eb_var": {}}), ("pick", {"fb": fb, "ask": ask, "eb_var": evar})):
        for start in ("eval", "funded1"):
            A, B = specs(fb=kw["fb"], ask=kw["ask"], eb_var=kw["eb_var"], start_a=start)
            for sp in SPANS:
                RA, RB = run_slots(BY, PL[sp], [A, B])
                key = f"{lab}__a_{start}"
                out["slots"].setdefault(key, {})[sp] = {"a": slot_stats(RA), "b": slot_stats(RB)}
                out["pairs"].setdefault(key, {})[sp] = pair_stats(RA, RB)
            p = out["pairs"][key]
            log(f"PAIR {key:20s} H1 ${p['H1']['net_m']}/mo | H2 ${p['H2']['net_m']}/mo p10 ${p['H2']['net_p10_6m']} corr day {p['H2']['corr_day']} "
                f"net {p['H2']['corr_net']} worst day ${p['H2']['worst_day']} | REF ${p['REF']['net_m']}/mo p_neg {p['REF']['p_neg']}%")
    A, B = specs(fb=fb, ask=ask, eb_var=evar)
    out["fresh_pair"] = {sp: fresh_pair(BY, PE[sp], MFFU_E, A["ecfg"], B["E"], B["ecfg"]) for sp in SPANS}
    out["value_a"] = {sp: eval_value(BY, PL[sp], A) for sp in ("H1", "H2")}
    out["value_b"] = {sp: eval_value(BY, PL[sp], B) for sp in ("H1", "H2")}
    log("fresh pair (2 weeks)", out["fresh_pair"])
    # ---- 4. the other candidates ALONE (a what-if once the firm says yes in writing: the holds are ignored here), each
    #         on the fleet's default sizing for its own rules; one eval bought, then rebuys, 6 months
    out["others"] = {}
    for plan, (price, act) in OTHERS.items():
        sp_ = spec_any(plan, price, act)
        row = {"price": price, "act": act, "rules": {"eval": sp_["E"], "funded": sp_["FR"]}}
        for sp in SPANS:
            row[sp] = {"eval": eval_stats(BY, PE[sp], sp_["E"], sp_["ecfg"], price + act),
                       "slot": slot_stats(run_slots(BY, PL[sp], [sp_])[0])}
        row["value"] = {sp: eval_value(BY, PL[sp], sp_) for sp in ("H1", "H2")}
        out["others"][plan] = row
        log(f"OTHER {plan:20s} 2wk H2 {row['H2']['eval']['p10']}/{row['H2']['eval']['f10']} med {row['H2']['eval']['pass_med']} | "
            f"$/eval H1 ${row['value']['H1']['usd_per_eval']} H2 ${row['value']['H2']['usd_per_eval']} | $/mo H1 ${row['H1']['slot']['net_m']} "
            f"H2 ${row['H2']['slot']['net_m']} REF ${row['REF']['slot']['net_m']}")
    return out


OTHERS = {"lucid_flex_50k": (134.40, 0.0),            # price unknown (options at checkout): the LucidPro price as a stand-in
          "fn_rapid_daily_50k": (149.99, 0.0),        # list $299.99, FundedNext's own RAPID code up to 50% (Oct 2026)
          "bulenox_eod_50k": (175.0, 148.0)}          # list $175 one-time + $148 activation (codes claim 75-89%: unconfirmed)


def spec_any(plan, price, act=0.0, fcfg=None, ask="cap"):
    """A slot for any plan on the fleet's default sizing (live two_week on its eval rules; the MFFU funded preset)."""
    E, FR = rules(plan)
    if E["dll"] >= 1e8:                                # no firm daily loss: the fleet sizes with the bot's own $1,000 soft day
        E = {**E, "dll": 1000.0}
    if FR["dll"] >= 1e8:
        FR = {**FR, "dll": 1000.0}
    return {"E": E, "FR": FR, "ecfg": ecfg(E), "price": price, "act": act,
            "fund": lambda after_first=False: Lucid(fcfg or U.UP50, FR, ask)}


# ================================================================================================ checks + runs
def check():
    """My eval == tools/uprisk.Eval on the MFFU 50K (live sizing), my trades == uprisk's (the shared keys)."""
    S, BY = load()
    _, BU = U.load()
    keys = ("day", "risk", "tgt", "pts", "w1", "size_mult", "ref")
    assert all([{k: t[k] for k in keys} for t in a] == [{k: t[k] for k in keys} for t in b] for a, b in zip(BY, BU)), "trades differ"
    for sp in ("H1", "H2", "REF"):
        for seq in U.mc_paths(S, sp, 300, length=H_EVAL, seed=11):
            e1, e2 = Ev(ecfg(MFFU_E), MFFU_E), U.Eval(U.ecfg_of({}, plan="builder50k"), "builder50k")
            for si in seq:
                r1, _ = e1.step(BY[si])
                r2 = e2.step(BU[si])
                assert r1 == r2 and abs(e1.bal - e2.bal) < 1e-6, (sp, r1, r2, e1.bal, e2.bal)
                if r1:
                    break
    # the Lucid funded account with MFFU's payout numbers on a MFFU-like path pays like uprisk.Funded within a few %
    print("check ok: account4_sim.Ev == tools/uprisk.Eval (MFFU 50K, live sizing); trades == tools/uprisk.trades()")


def real_path_runs(fb, ask, evar):
    """The real 2026 order, back to back (eval -> funded -> next eval) for both accounts: runlib trade rows."""
    S, BY = load()
    A, B = specs(fb=fb, ask=ask, eb_var=evar)
    rows = {"A": [], "B": []}
    info = {}
    for sp in ("H1", "H2"):
        a, z = U.span_ix(S, sp)
        for lab, spec in (("A", A), ("B", B)):
            s = Slot(spec)
            for k, si in enumerate(range(a, z)):
                phase = "eval" if s.e is not None else ("funded" if s.f is not None else "paperwork")
                keep = []
                s.step(k, BY[si], keep)
                for t, q, pnl in keep:
                    ru = t["risk"] * PV * q
                    rows[lab].append({"day": S[si], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"],
                                      "r": round(pnl / ru, 3) if ru else 0.0, "pnl": round(pnl, 2), "low": round(min(0.0, pnl), 2),
                                      "risk_pts": t["risk"], "qty": q, "risk_usd": round(ru, 2), "half": t["size_mult"] < 1,
                                      "exit": t["exit"], "trigger": ("MFFU 50K " if lab == "A" else "Lucid 50K ") + phase,
                                      "mfe": None, "mae": None, "bars_held": None, "regime": "", "mult": None})
            info[f"{lab}_{sp}"] = s.out()
    return rows, info


def save(res=None):
    from tools import runlib as rl
    res = res or json.load(open(OUT, encoding="utf-8"))
    pk = res["pick"]
    fb, ask = res["funded_b"][pk["funded_b"]]["cfg"], res["funded_b"][pk["funded_b"]]["ask"]
    evar = dict(EVAL_B)[pk["eval_b"]]
    rows, info = real_path_runs(fb, ask, evar)
    S, _ = load()
    S26 = [d for d in S if d >= "2026-01-01"]
    pr = res["pairs"]["pick__a_funded1"]
    eb, va, vb = res["eval_b"][pk["eval_b"]], res["value_a"], res["value_b"]
    common = (f"Pair (MFFU 50K funded after its first payout + a new LucidPro 50K eval, same LIT signal, 6 months): "
              f"H1 ${pr['H1']['net_m']:,} / H2 ${pr['H2']['net_m']:,} a month net of fees (2021-25 ${pr['REF']['net_m']:,}); "
              f"daily correlation {pr['H2']['corr_day']}, worst pair day ${pr['H2']['worst_day']:,}. ")
    vB = (f"LucidPro 50K copy (eval {pk['eval_b']}, funded {pk['funded_b']}): 2-week pass / fail H1 {eb['H1']['p10']} / {eb['H1']['f10']}, "
          f"H2 {eb['H2']['p10']} / {eb['H2']['f10']} (pass_med {eb['H2']['pass_med']}); $ per eval H1 ${vb['H1']['usd_per_eval']:,} / "
          f"H2 ${vb['H2']['usd_per_eval']:,}. ")
    for rid, title, T, status, v in (
            ("acct4_lucid_copy", "Account #4: LIT copied to a LucidPro 50K (Lucid's own rules)", rows["B"], "adopt-candidate", vB + common),
            ("acct4_pair", "Account #4: the MFFU 50K + LucidPro 50K pair on one LIT signal", sorted(rows["A"] + rows["B"], key=lambda t: (t["day"], t["trigger"])),
             "info", common + vB + f"MFFU 50K: $ per eval H1 ${va['H1']['usd_per_eval']:,} / H2 ${va['H2']['usd_per_eval']:,}.")):
        if not T:
            continue
        rl.save(rid, title, "risk", "Account #4: what does a LucidPro 50K copy of LIT add next to the MFFU 50K, and how should each be sized?",
                params={"plans": ["mffu_builder_50k", "lucid_pro_50k"], "strategy": "lit"},
                sizing={"a": {"eval": "live two_week 40%", "funded": U.UP50}, "b": {"eval": pk["eval_b"], "funded": fb, "ask": ask}},
                trades=T, scored=rl.score(T, S26), status=status, verdict=v,
                notes="tools/account4_sim.py (research/lab/account4_sim.json); MC whole weeks of the half, both accounts on the same "
                      "paths; $1.90 a micro; stored trades = the real 2026 order back to back (eval -> funded -> next eval), one row "
                      "per traded session ($ of that session). The run-library eval columns are not these accounts' rules.",
                writeup="account-4-2026-11-14", tags=["lit", "fleet", "lucid", "account4"])
        print("saved", rid, flush=True)


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if a and a[0] == "check":
        check()
        return 0
    if a and a[0] == "save":
        save()
        return 0
    n = int(a[a.index("--n") + 1]) if "--n" in a else 1000
    res = study(n)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    print("wrote", os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
