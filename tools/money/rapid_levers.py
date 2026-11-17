"""Three new levers for 2-3 MFFU Rapid EOD 50K accounts (owner 2026-11-16, buying 2 maybe 3). PAPER RESEARCH ONLY: reads
stored trades, writes research/lab/rapid_levers.json, changes nothing live. Write-up: research/writeups/rapid-levers-2026-11-16.md.
Builds on tools/money/stack_one_account.py (same trades, costs, sizing, news rule, Monte Carlo paths).

  1 DECORRELATE  2-3 Rapid EODs on the SAME session paths: identical copies (all LIT + ATLAS) vs a different mix per account
                 (ATLAS + BLITZ, LIT + BLITZ, the LIT Asia slot, the sh_asia / sh_trend stop-hunt paper strategies).
                 Scores: total $ a month, P(no account pays in 6 months), P(first payout of any account by session 21 / 32
                 = calendar day ~30 / ~45), combined max drawdown (sum of the accounts' daily trading P&L).
  2 ASIA SLOT    LIT + the Asia slot (18:00-02:00 entries of run lit_more_ent_asia_slot_rr3, sized as LIT or at $300) + ATLAS
                 on the Rapid EOD eval and funded.
  3 MECHANICS    (a) eval give-up / re-buy ($94) when room < $X, session > Y, or the 30% rule pushes the needed profit too far;
                 (b) funded withdrawal: everything above the $2,100 buffer daily / keep a $X cushion / weekly / fixed requests,
                 with the help-center payout rules (daily, $500 min, >= $500 net profit since the last payout, no cap, 90%);
                 (c) eval day-profit cap: none / today's 30% size guard / stop for the day at +$X / a looser balance-aware guard.

Streams (all stored, futures data only; costs $1.90 a micro + 1 tick in the stored prices):
  LIT, ATLAS, BLITZ  = stack_one_account.data()
  ASIA               = tools/atlas.account_units(members ["ASIA"]) (never opposite LIT, an overlapping one dropped)
  SHA / SHT          = tools/atlas_v2.sh_units() through tools/atlas.no_hedge_real (never opposite LIT)

    python -X utf8 tools/money/rapid_levers.py            # all three -> research/lab/rapid_levers.json
    python -X utf8 tools/money/rapid_levers.py --n 200    # quicker
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import stack_one_account as SOA  # noqa: E402
import account4_sim as A4  # noqa: E402
import uprisk as U  # noqa: E402
from engine import firms as FM  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from engine.lit import qty_for  # noqa: E402

PV, COMM, SLIP = SOA.PV, SOA.COMM, SOA.SLIP
OUT = os.path.join(ROOT, "research", "lab", "rapid_levers.json")
SPANS, LEN, H_EVAL, MO = SOA.SPANS, SOA.LEN, SOA.H_EVAL, SOA.MO
PRICE = SOA.PRICE["rapid_eod"]
GAP = A4.GAP
PRI = {"LIT": 0, "ASIA": 1, "ATLAS": 2, "BLITZ": 3, "SHA": 4, "SHT": 5}


# ================================================================================================ streams
_X = {}


def streams():
    """day -> the extra trades (ASIA, SHA, SHT) beside stack_one_account's OTHER (ATLAS, BLITZ)."""
    if not _X:
        from tools import atlas as A
        from tools import atlas_v2 as V
        by = {}

        def add(u, nm):
            t = {"day": u["day"], "risk": float(u["risk"]), "tgt": float(u["tgt"] or 0) or None, "pts": float(u["pts"]),
                 "w1": float(min(0.0, u["w1"])), "entry_t": int(u["entry_t"]), "exit_t": int(u["exit_t"]), "dir": int(u["dir"]),
                 "strat": nm, "tf": 1 if u["day"] >= "2026-01-01" else 5}
            by.setdefault(t["day"], []).append(t)
        for u in A.account_units({**A.BASE, "members": ["ASIA"]}):
            add(u, "ASIA")
        sh = V.sh_units()
        for nm in ("SHA", "SHT"):
            for u in A.no_hedge_real(sorted(sh[nm], key=lambda x: x["entry_t"])):
                add(u, nm)
        _X["by"] = by
    return _X["by"]


_MB = {}


def mix_by(mix, news=False):
    key = (tuple(sorted(mix)), news)
    if key not in _MB:
        D, X = SOA.data(), streams()
        out = []
        for i, d in enumerate(D["S"]):
            ts = list(D["LIT"][i]) if "LIT" in mix else []
            ts += [t for t in D["OTHER"].get(d, ()) if t["strat"] in mix]
            ts += [t for t in X.get(d, ()) if t["strat"] in mix]
            ts.sort(key=lambda t: (t["entry_t"], PRI[t["strat"]]))
            out.append(SOA.news_rule(ts) if news else ts)
        _MB[key] = out
    return _MB[key]


def lit_like(t, z):
    return t["strat"] == "LIT" or z.get(t["strat"]) == "lit"


def q_add(t, z, room, cum, maxq, dll):
    s = z.get(t["strat"])
    if not isinstance(s, dict):
        return 0
    return SOA.stack_q(t, z, room, cum, maxq, dll)


# ================================================================================================ the eval (+ day-cap modes)
class Ev(SOA.Ev):
    """stack_one_account.Ev + LIT-sized added streams + the day-cap mode:
    "guard" = today's fleet guard (a winner keeps the day under 30% x $3,000 x 0.95), "none", ("stop", X) = no new entry
    once the day is up $X (guard kept), ("stop_only", X) = the stop without the guard, "loose" = the guard on
    max(30% x target, 30/70 x the balance) x 0.95 (the most the pass rule still allows at today's balance)."""

    def __init__(self, cfg, E, z, cap="guard"):
        super().__init__(cfg, E, z)
        self.cap = cap

    def _cap(self, q, t, cum):
        E, c = self.E, self.cap
        if c == "none" or (isinstance(c, tuple) and c[0] == "stop_only"):
            return q
        if c == "loose":
            lim = max(E["cons"] * E["tgt"], E["cons"] / (1 - E["cons"]) * max(0.0, self.bal)) * FM.BEST_DAY_MARGIN
            win1 = (t["tgt"] or 2.0 * t["risk"]) * PV - COMM
            return q if win1 <= 0 else min(q, int(math.floor((lim - max(0.0, cum)) / win1)))
        return SOA.cons_cap(q, t, E.get("cons"), E["tgt"], cum)

    def step(self, ts, keep=None):
        c, E, z = self.cfg, self.E, self.z
        dll = c.get("_dll", E["dll"])
        self.s += 1
        wkey = (self.s - 1) // 5
        cum, traded = 0.0, False
        sub = {k: v for k, v in c.items() if not k.startswith("_")}
        stop_x = self.cap[1] if isinstance(self.cap, tuple) else None
        for t in ts:
            if cum <= -dll or (stop_x is not None and cum >= stop_x):
                break
            room = self.bal + cum - self.floor
            if lit_like(t, z):
                m0 = qty_for(t["risk"])
                if not m0:
                    continue
                st = {"profit": self.bal, "cum": cum, "room": room, "session": self.s, "n_today": 0,
                      "wk_pnl": self.wk.get(wkey, 0.0), "days_traded": self.dtr}
                q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, sub, room=room, state=st,
                               learning=None, max_micros=c["_maxq"])["qty"]
                q = min(q, c["_maxq"])
            else:
                q = q_add(t, z, room, cum, c["_maxq"], min(dll, SOA.SOFT_DLL))
            q = self._cap(q, t, cum)
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

    def need(self):
        """$ still needed: the target, or more when the best day needs a bigger total (best <= 30% of the profit)."""
        return max(self.E["tgt"], self.best / self.E["cons"]) - self.bal

    def give_up(self, g):
        if not g:
            return False
        if "room" in g and self.bal - self.floor < g["room"]:
            return True
        if "s" in g and self.s >= g["s"]:
            return True
        if "need" in g and self.need() > g["need"]:
            return True
        return False


# ================================================================================================ the funded account (+ payout policy)
class Rapid(SOA.Rapid):
    """stack_one_account.Rapid + LIT-sized added streams + the withdrawal policy, on the help-center rules (2026-11-16:
    daily, $2,100 buffer, $500 min, no cap, 90%, no consistency) + >= $500 net profit since the last payout (third-party
    plan guides; a no-op for "all", which leaves exactly the buffer).
    pol: "all" | ("cushion", X) keep X above the buffer | ("weekly", X) every 5th session, keep X | ("fixed", A) ask A."""

    def __init__(self, fcfg, R, z, pol="all"):
        super().__init__(fcfg, R, z)
        self.pol = pol

    def step(self, ts, keep=None):
        if self.state != "on":
            return None, None, 0.0
        R, c, z = self.R, self.cfg, self.z
        self.k += 1
        dll, mq, cap = self.dll(), self.maxq(), self.cap()
        A = {"mll": R["mll"], "lock": R["lock"], "dll": dll, "buffer": R["buffer"], "pay_min": R["pay_min"], "pay_max": cap,
             "split": R["split"], "cons": R["cons"] or 0.5, "cycle_days": 0, "first_wait": 0, "max_payouts": R["max_payouts"],
             "max_micros": mq, "scale": 1.0}
        cyc = {"cycle_start_bal": round(self.cyc_start, 2), "cycle_prev": round(sum(self.cyc), 2),
               "best_prev": round(max(self.cyc), 2) if self.cyc else 0.0, "cycle_days_prev": len(self.cyc), "payouts_n": len(self.pays),
               "cycle_target": round(max(0.0, R["buffer"] + min(cap, 2000.0) - self.cyc_start), 2)}
        cum = 0.0
        for t in ts:
            if cum <= -dll:
                break
            room = round(self.bal + cum - self.floor, 2)
            if lit_like(t, z):
                st = {"room": room, "cum": cum, "locked": self.floor >= R["lock"] - 1e-9, "bal": self.bal, **cyc}
                q = min(SZ.funded_qty(t, st, c, acct=A), mq)
            else:
                q = q_add(t, z, room, cum, mq, min(dll, SOA.SOFT_DLL))
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
                return "lost", None, round(self.floor - self.bal, 2)
            cum += pnl
        if abs(cum) > 1e-9:
            self.bal += round(cum, 2)
            self.cyc.append(round(cum, 2))
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - R["mll"]), R["lock"])
        p = self.pol
        keep_x = 0.0
        if isinstance(p, tuple) and p[0] in ("cushion", "weekly"):
            keep_x = float(p[1])
        if isinstance(p, tuple) and p[0] == "weekly" and self.k % 5:
            return None, None, round(cum, 2)
        avail = self.bal - R["buffer"] - keep_x
        if isinstance(p, tuple) and p[0] == "fixed":
            avail = float(p[1]) if self.bal - R["buffer"] >= float(p[1]) else 0.0
        since = self.bal - self.cyc_start if self.pays else self.bal
        if avail >= R["pay_min"] and since >= R.get("since", R["pay_min"]) - 1e-9:   # since: the 25K's $250 rule
            amt = round(min(cap, avail), 2)
            self.pays.append(amt)
            self.bal -= amt
            self.cyc, self.cyc_start = [], self.bal
            return "paid", amt * self.split, round(cum, 2)
        return None, None, round(cum, 2)


# ================================================================================================ one Rapid EOD account
def acct(mix_e, mix_f=None, z=None, cap="guard", give=None, pol="all"):
    """spec of one Rapid EOD 50K account slot (eval -> 2 sessions -> funded -> lost -> buy again)."""
    E, F = A4.rules("mffu_rapid_eod_50k")
    E = {**E, "stuck": 200.0}
    F = {**F, "dll": SOA.SOFT_DLL}
    z = z or {}
    mix_f = mix_f or mix_e
    ec = A4.ecfg(E, {"dll_off": True})
    return {"E": E, "ecfg": ec, "z": z, "cap": cap, "give": give, "pol": pol,
            "BYe": mix_by(mix_e), "BYf": mix_by(mix_f, news=True), "mix_f": mix_f,
            "fund": lambda: Rapid(U.UP50, F, z, pol), "ev": lambda: Ev(ec, E, z, cap)}


class Slot:
    def __init__(self, sp):
        self.sp = sp
        self.cost, self.owner, self.evals, self.funded_n, self.lost, self.gaveup = 0.0, 0.0, 0, 0, 0, 0
        self.first_pay, self.first_pass, self.pays, self.days = None, None, 0, []
        self.f, self.wait = None, 0
        self._buy()

    def _buy(self):
        self.cost += PRICE
        self.evals += 1
        self.e = self.sp["ev"]()

    def step(self, k, si):
        sp = self.sp
        if self.e is not None:
            r, pnl = self.e.step(sp["BYe"][si])
            self.days.append(pnl)
            if r == "pass":
                self.first_pass = self.first_pass or k + 1
                self.e, self.wait = None, GAP
            elif r in ("fail", "stuck"):
                self._buy()
            elif self.e.give_up(sp["give"]):
                self.gaveup += 1
                self._buy()
            return
        if self.f is None:
            self.days.append(0.0)
            self.wait -= 1
            if self.wait <= 0:
                self.f = sp["fund"]()
                self.funded_n += 1
            return
        ev, x, pnl = self.f.step(sp["BYf"][si])
        self.days.append(pnl)
        if ev == "paid":
            self.owner += x
            self.pays += 1
            self.first_pay = self.first_pay or k + 1
        if ev == "lost":
            self.lost += 1
            self.f = None
            self._buy()


def run_group(specs, paths):
    """Several accounts on the SAME paths (they trade the same days). -> per path: the slots."""
    out = []
    for seq in paths:
        sl = [Slot(s) for s in specs]
        for k, si in enumerate(seq[:LEN]):
            for s in sl:
                s.step(k, si)
        out.append(sl)
    return out


def group_stats(G):
    n = len(G)
    net = np.array([sum(s.owner - s.cost for s in g) for g in G])
    first = [min([s.first_pay for s in g if s.first_pay] or [999]) for g in G]
    dd = []
    for g in G:
        d = np.sum([s.days for s in g], axis=0)
        eq = np.cumsum(d)
        dd.append(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min()))
    fp_each = [s.first_pay for g in G for s in g if s.first_pay]
    return {"net_m": round(float(net.mean()) / MO), "net_p10_m": round(float(np.percentile(net, 10)) / MO),
            "p_none_pays": round(100.0 * sum(1 for f in first if f == 999) / n, 1),
            "p_pay_by_21": round(100.0 * sum(1 for f in first if f <= 21) / n, 1),
            "p_pay_by_32": round(100.0 * sum(1 for f in first if f <= 32) / n, 1),
            "first_any_med": float(np.median([f for f in first if f < 999])) if any(f < 999 for f in first) else None,
            "first_each_med": float(np.median(fp_each)) if fp_each else None,
            "dd_med": round(float(np.median(dd))), "dd_p10": round(float(np.percentile(dd, 10))),
            "fees_6m": round(float(np.mean([sum(s.cost for s in g) for g in G]))),
            "lost_6m": round(100.0 * sum(1 for g in G for s in g if s.lost) / (n * len(G[0])), 1),
            "gaveup": round(float(np.mean([sum(s.gaveup for s in g) for g in G])), 2),
            "evals": round(float(np.mean([sum(s.evals for s in g) for g in G])), 2)}


def eval_stats(sp, paths):
    res = []
    for seq in paths:
        e = sp["ev"]()
        out, used = "open", len(seq[:H_EVAL])
        for k, si in enumerate(seq[:H_EVAL]):
            r, _ = e.step(sp["BYe"][si])
            if r:
                out, used = ("pass" if r == "pass" else "fail"), k + 1
                break
        res.append((out, used))
    n = len(res)
    pas = [u for o, u in res if o == "pass"]
    return {"p10": round(100.0 * sum(1 for u in pas if u <= 10) / n, 1),
            "f10": round(100.0 * sum(1 for o, u in res if o == "fail" and u <= 10) / n, 1),
            "p60": round(100.0 * len(pas) / n, 1), "f60": round(100.0 * sum(1 for o, _ in res if o == "fail") / n, 1),
            "pass_med": float(np.median(pas)) if pas else None}


def funded_stats(sp, paths):
    out = []
    for seq in paths:
        f = sp["fund"]()
        owner, lost, first = 0.0, None, None
        for k, si in enumerate(seq[:LEN]):
            ev, x, _ = f.step(sp["BYf"][si])
            if ev == "paid":
                owner += x
                first = first or k + 1
            if ev == "lost":
                lost = k + 1
                break
        out.append((owner, lost, first))
    n = len(out)
    fr = [x[2] for x in out if x[2]]
    return {"per_month": round(float(np.mean([x[0] for x in out])) / MO), "lost_6m": round(100.0 * sum(1 for x in out if x[1]) / n, 1),
            "first_med": float(np.median(fr)) if fr else None, "no_pay": round(100.0 * (n - len(fr)) / n, 1)}


def plain(sp, span):
    usd = {"LIT": 500.0}
    for k, v in sp["z"].items():
        usd[k] = 500.0 if v == "lit" else float(v["usd"])
    for k in PRI:
        usd.setdefault(k, 0.0)
    return SOA.plain_stats(mix_by(sp["mix_f"]), SOA.data()["S"], span, usd)


def one(sp, PE, PF, plain_too=True):
    """Per span: trades (fixed $), eval, funded alone, and the 6-month slot of this one account."""
    o = {}
    for s in SPANS:
        r = {"eval": eval_stats(sp, PE[s]), "funded": funded_stats(sp, PF[s]), "slot": group_stats(run_group([sp], PF[s]))}
        if plain_too:
            r["plain"] = plain(sp, s)
        o[s] = r
    return o


# ================================================================================================ the levers
def Z(**kw):
    """Z(ATLAS=500, BLITZ=300, ASIA="lit"|300, SHA=300, SHT=300) -> the added-strategy sizing (30% of the room cap)."""
    return {k: (v if v == "lit" else {"usd": float(v), "f": 0.3}) for k, v in kw.items()}


LA = ("LIT", "ATLAS")
MIXES = {                                                   # name -> (strategies, sizing)
    "LIT + ATLAS": (LA, Z(ATLAS=500)),
    "ATLAS + BLITZ": (("ATLAS", "BLITZ"), Z(ATLAS=500, BLITZ=300)),
    "LIT + BLITZ": (("LIT", "BLITZ"), Z(BLITZ=300)),
    "LIT + Asia(LIT size) + ATLAS": (("LIT", "ASIA", "ATLAS"), Z(ATLAS=500, ASIA="lit")),
    "LIT + Asia $300 + ATLAS": (("LIT", "ASIA", "ATLAS"), Z(ATLAS=500, ASIA=300)),
    "ATLAS + sh_asia + sh_trend": (("ATLAS", "SHA", "SHT"), Z(ATLAS=500, SHA=300, SHT=300)),
    "LIT + sh_asia + sh_trend": (("LIT", "SHA", "SHT"), Z(SHA=300, SHT=300)),
    "ATLAS + BLITZ + sh_asia": (("ATLAS", "BLITZ", "SHA"), Z(ATLAS=500, BLITZ=300, SHA=300)),
}
GROUPS = {                                                  # lever 1: the accounts bought together
    "2x identical (LIT + ATLAS)": ("LIT + ATLAS", "LIT + ATLAS"),
    "2x: LIT + ATLAS | ATLAS + BLITZ": ("LIT + ATLAS", "ATLAS + BLITZ"),
    "2x: LIT + ATLAS | LIT + BLITZ": ("LIT + ATLAS", "LIT + BLITZ"),
    "2x: LIT + ATLAS | ATLAS + sh_asia + sh_trend": ("LIT + ATLAS", "ATLAS + sh_asia + sh_trend"),
    "3x identical (LIT + ATLAS)": ("LIT + ATLAS",) * 3,
    "3x: LIT + ATLAS | ATLAS + BLITZ | LIT + BLITZ": ("LIT + ATLAS", "ATLAS + BLITZ", "LIT + BLITZ"),
    "3x: LIT + ATLAS | LIT + Asia + ATLAS | ATLAS + BLITZ": ("LIT + ATLAS", "LIT + Asia(LIT size) + ATLAS", "ATLAS + BLITZ"),
    "3x: LIT + ATLAS | ATLAS + sh | LIT + BLITZ": ("LIT + ATLAS", "ATLAS + sh_asia + sh_trend", "LIT + BLITZ"),
    "3x: LIT + ATLAS | ATLAS + BLITZ + sh_asia | LIT + sh": ("LIT + ATLAS", "ATLAS + BLITZ + sh_asia", "LIT + sh_asia + sh_trend"),
}
ASIA_ROWS = {                                               # lever 2: name -> (eval mix, funded mix)
    "LIT + ATLAS (base)": ("LIT + ATLAS", "LIT + ATLAS"),
    "LIT + Asia(LIT size) + ATLAS": ("LIT + Asia(LIT size) + ATLAS", "LIT + Asia(LIT size) + ATLAS"),
    "LIT + Asia $300 + ATLAS": ("LIT + Asia $300 + ATLAS", "LIT + Asia $300 + ATLAS"),
    "Asia(LIT size) in the eval only": ("LIT + Asia(LIT size) + ATLAS", "LIT + ATLAS"),
}
GIVE = {"never (today)": None, "room < $500": {"room": 500}, "room < $800": {"room": 800}, "room < $1,000": {"room": 1000},
        "session > 30": {"s": 30}, "session > 45": {"s": 45}, "30%-rule need > $4,000": {"need": 4000},
        "30%-rule need > $3,000": {"need": 3000}}
POL = {"all above buffer, daily (today)": "all", "keep $500 cushion": ("cushion", 500), "keep $1,000 cushion": ("cushion", 1000),
       "keep $2,000 cushion": ("cushion", 2000), "weekly, all above buffer": ("weekly", 0), "fixed $1,000 requests": ("fixed", 1000)}
CAPS = {"30% size guard (today)": "guard", "none": "none", "guard + stop day at +$500": ("stop", 500),
        "guard + stop day at +$700": ("stop", 700), "stop day at +$700 only": ("stop_only", 700), "loose guard (balance-aware)": "loose"}


def spec_of(name, **kw):
    m, z = MIXES[name]
    return acct(m, m, z, **kw)


def study(n=1000, log=print):
    S = SOA.data()["S"]
    PE = {s: U.mc_paths(S, s, 2 * n, length=H_EVAL, seed=A4.SEED_EVAL) for s in SPANS}
    PF = {s: U.mc_paths(S, s, n, length=LEN, seed=A4.SEED_LIFE) for s in SPANS}
    out = {"date": "2026-11-16", "n": n, "spans": U.SPAN, "mixes": {}, "groups": {}, "asia": {}, "give": {}, "pol": {}, "cap": {}}
    t0 = time.time()
    for nm in MIXES:
        out["mixes"][nm] = one(spec_of(nm), PE, PF)
        log(f"mix {nm:34s} " + " | ".join(f"{s} 1st {out['mixes'][nm][s]['slot']['first_any_med']} ${out['mixes'][nm][s]['slot']['net_m']}"
                                           for s in SPANS) + f"  {time.time() - t0:.0f}s")
    for g, members in GROUPS.items():
        out["groups"][g] = {s: group_stats(run_group([spec_of(m) for m in members], PF[s])) for s in SPANS}
        log(f"group {g:52s} " + " | ".join(f"{s} ${out['groups'][g][s]['net_m']} none {out['groups'][g][s]['p_none_pays']}%" for s in SPANS))
    for nm, (me, mf) in ASIA_ROWS.items():
        (m1, z1), (m2, z2) = MIXES[me], MIXES[mf]
        out["asia"][nm] = one(acct(m1, m2, {**z2, **z1}), PE, PF)
        log(f"asia {nm:34s} " + " | ".join(f"{s} eval {out['asia'][nm][s]['eval']['pass_med']} ${out['asia'][nm][s]['slot']['net_m']}" for s in SPANS))
    for nm, g in GIVE.items():
        out["give"][nm] = {s: group_stats(run_group([spec_of("LIT + ATLAS", give=g)], PF[s])) for s in SPANS}
        log(f"give {nm:28s} " + " | ".join(f"{s} ${out['give'][nm][s]['net_m']} 1st {out['give'][nm][s]['first_any_med']}" for s in SPANS))
    for nm, p in POL.items():
        sp = spec_of("LIT + ATLAS", pol=p)
        out["pol"][nm] = {s: {"funded": funded_stats(sp, PF[s]), "slot": group_stats(run_group([sp], PF[s]))} for s in SPANS}
        log(f"pol {nm:32s} " + " | ".join(f"{s} ${out['pol'][nm][s]['slot']['net_m']} lost {out['pol'][nm][s]['funded']['lost_6m']}%" for s in SPANS))
    for nm, c in CAPS.items():
        sp = spec_of("LIT + ATLAS", cap=c)
        out["cap"][nm] = {s: {"eval": eval_stats(sp, PE[s]), "slot": group_stats(run_group([sp], PF[s]))} for s in SPANS}
        log(f"cap {nm:32s} " + " | ".join(f"{s} eval {out['cap'][nm][s]['eval']['pass_med']} {out['cap'][nm][s]['eval']['p10']}/{out['cap'][nm][s]['eval']['f10']} ${out['cap'][nm][s]['slot']['net_m']}" for s in SPANS))
    out["verdict"] = verdict(out)
    return out


def verdict(o):
    """Adopt only if better than today's row in BOTH 2026 halves: more $ a month and no worse on the lever's risk score
    (P(no account pays) +1 point / funded lost +1 point / 2-week eval fails +0.5 point)."""
    v = {}

    def both(f):
        return all(f(s) for s in ("H1", "H2"))
    for size, base in (("2x", "2x identical (LIT + ATLAS)"), ("3x", "3x identical (LIT + ATLAS)")):
        b = o["groups"][base]
        for g, r in o["groups"].items():
            if g.startswith(size) and g != base:
                v[f"1 {g}"] = both(lambda s: r[s]["net_m"] > b[s]["net_m"] and r[s]["p_none_pays"] <= b[s]["p_none_pays"] + 1.0)
    b = o["asia"]["LIT + ATLAS (base)"]
    for nm, r in o["asia"].items():
        if nm != "LIT + ATLAS (base)":
            v[f"2 {nm}"] = both(lambda s: r[s]["slot"]["net_m"] > b[s]["slot"]["net_m"] and r[s]["eval"]["f10"] <= b[s]["eval"]["f10"] + 0.5)
    b = o["give"]["never (today)"]
    for nm, r in o["give"].items():
        if nm != "never (today)":
            v[f"3a {nm}"] = both(lambda s: r[s]["net_m"] > b[s]["net_m"])
    b = o["pol"]["all above buffer, daily (today)"]
    for nm, r in o["pol"].items():
        if nm != "all above buffer, daily (today)":
            v[f"3b {nm}"] = both(lambda s: r[s]["slot"]["net_m"] > b[s]["slot"]["net_m"] and r[s]["funded"]["lost_6m"] <= b[s]["funded"]["lost_6m"] + 1.0)
    b = o["cap"]["30% size guard (today)"]
    for nm, r in o["cap"].items():
        if nm != "30% size guard (today)":
            v[f"3c {nm}"] = both(lambda s: r[s]["slot"]["net_m"] > b[s]["slot"]["net_m"] and r[s]["eval"]["f10"] <= b[s]["eval"]["f10"] + 0.5)
    return v


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.time()
    out = study(a.n)
    for k, ok in out["verdict"].items():
        print(f"{k:60s} {'BETTER in both halves' if ok else 'no'}")
    if not a.no_save:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print("wrote", os.path.relpath(OUT, ROOT))
    print(f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
