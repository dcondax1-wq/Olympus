"""Three NEW MFFU Builder levers for money sooner (owner 2026-11-16: "money sooner, MFFU only"). Write-up:
research/writeups/builder-levers-2026-11-16.md. PAPER RESEARCH ONLY: reads stored trades, writes research/lab/builder_levers.json,
changes nothing live (no live_model*.json, second_model.json, engine file).

  1. EVAL RESCUE   from an eval's CURRENT hole (room above the EOD floor, $ still to the target: arguments, the 2026-11-07
                   numbers are the default): continue as is / buy a FRESH eval now and run it in parallel on the same signal
                   (MFFU: 10 evals, but 1 funded Builder 50K: whichever passes first is kept, the other dropped) / a rescue
                   sizing for the hole eval only. Zlarior (LIT, 50K) and ATLAS (25K, zombie-eval rule ON). + a threshold grid
                   (room x to-go) of where the parallel fresh eval pays.
  2. 2ND 25K SLOT  MFFU funds 2 x Builder 25K: ATLAS's own + one more. Which mix on the new 25K gives the first payout
                   soonest and the most $ a month (LIT 25K copy, LIT + ATLAS, ATLAS + BLITZ, LIT + Asia slot, a 2nd ATLAS copy),
                   and how alike it is to ATLAS's own 25K (same paths: daily correlation, both-pay-nothing).
  3. PAYOUT ENGINE the funded Builder 50K (LIT + ATLAS $500 (+ BLITZ $300), the stack-one-account funded mix) under the MFFU
                   funded rules (tools/uprisk.Funded: $2,100 buffer, $500-$2,000 a request, best day <= 50% of the cycle,
                   2 traded days a cycle, 48 h first wait, 80%, 5 payouts): request policy (ask at $500 asap / $1,000 / $1,500
                   today / $2,000 / cycle-timed: $2,000 on cycle day 2 stepping down $500 a day to $500) x a best-day-aware day
                   stop (no new entry once today's P&L >= max(the cycle's earlier P&L, $X): one more win would make today the
                   cycle's >50% day).

Trades, costs, sizing, Monte Carlo: exactly tools/money/stack_one_account.py (LIT live eval two_week / fleet funded UP50 on the
50K, UP25 + the 25K two_week preset on the 25K; ATLAS = tools/atlas.account_units, never opposite LIT, one position, max 2 a
day; its 25K eval at engine/account_b need size + the zombie-eval rule (last bullet 80% of the room, stuck under $200);
BLITZ account C; Asia = the LIT Asia-slot member; $1.90 a micro + 1 tick). Paths: 5-session blocks from H1 = 2026 Jan-Jun
(pick), H2 = Jul-Oct 2026 (check), REF = 2021-11..2025 (reference); every option on the SAME paths. Calendar from 2026-11-17
(tools/money/payout_plan.calendar).

    python -X utf8 tools/money/builder_levers.py                     # all three -> research/lab/builder_levers.json
    python -X utf8 tools/money/builder_levers.py --n 200             # quicker
    python -X utf8 tools/money/builder_levers.py --z-room 1145 --z-togo 3687 --z-session 20 --a-room 822 --a-togo 1678
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stack_one_account as SA  # noqa: E402

ROOT, A4, U = SA.ROOT, SA.A4, SA.U
from engine import account_b as EAB  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from engine.lit import qty_for  # noqa: E402

PV, COMM, SLIP = SA.PV, SA.COMM, SA.SLIP
OUT = os.path.join(ROOT, "research", "lab", "builder_levers.json")
SPANS = ("H1", "H2", "REF")
LEN, GAP, MO = U.LEN, U.GAP, U.LEN / 21.0
START_DAY = "2026-11-17"
PRICE50, PRICE25, PRICE25_CODE = 91.80, 63.00, 43.00
ZLARIOR = {"room": 1145.0, "to_go": 3687.0, "session": 20}       # owner's last report 2026-11-07 (STATE.md)
ATLAS = {"room": 822.0, "to_go": 1678.0, "session": 20}

E50 = dict(A4.MFFU_E)
E25 = {"plan": "mffu_builder_25k", "tgt": 1500.0, "mll": 1000.0, "dll": 600.0, "lock": 100.0, "stuck": 100.0, "maxq": 20,
       "cons": None, "min_days": 1}


def ecfg25(var=None):
    """The live two_week eval sizing on the Builder 25K's numbers (tools/uprisk.ecfg_of builder25k = engine/sizing.TW_25K)."""
    v = dict(var or {})
    c = U.ecfg_of(v, plan="builder25k")
    c["_dll"] = 600.0
    return c


def ecfg50(var=None):
    return A4.ecfg(E50, var)


def _atlas_v(cfg=None):
    """ATLAS's account-B variant: tools/atlas.BASE (+ top-level sizing keys, e.g. safe_cap / two_week_until)."""
    from tools import atlas as AT
    V = copy.deepcopy(AT.BASE)
    if cfg:
        V["cfg"] = dict(cfg)
    return V


# ================================================================================================ sizing
def size(t, st, z, room, cum, maxq, dll, lit_cfg=None, sess=None, acct=None):
    """Micros of one trade. z[strat] = ("lit", cfg) LIT's live eval sizing | ("need", V, last_bullet) ATLAS's account-B eval
    need size + the zombie last bullet | ("stack", usd, f) SA.stack_q | ("fq", cfg) funded_qty (funded only, via the account)."""
    s = z.get(t["strat"])
    if not s:
        return 0
    kind = s[0]
    if kind == "lit":
        m0 = qty_for(t["risk"])
        if not m0:
            return 0
        sub = {k: v for k, v in s[1].items() if not k.startswith("_")}
        q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"] or 2.0 * t["risk"], "size_mult": 1.0}, sub, room=room,
                       state=st, learning=None, max_micros=maxq)["qty"]
        return min(int(q), maxq)
    if kind == "need":
        from tools import atlas as AT
        q = AT.q_variant({**t, "tgt": t["tgt"] or 2.0 * t["risk"]}, st, s[1])
        lb = s[2]
        if q <= 0 and lb and qty_for(float(t["risk"])):
            loss1 = (float(t["risk"]) + SZ.TW_DLL_SLIP) * SZ.TW_PV + SZ.TW_COMM
            if loss1 <= float(lb) * room:
                q = int(EAB.dll_guard({"qty": 1, "reasons": []}, float(t["risk"]), AT.spec()["rules"], st)["qty"])
        return min(int(q), maxq)
    if kind == "stack":
        return SA.stack_q(t, {t["strat"]: {"usd": s[1], "f": s[2]}}, room, cum, maxq, dll)
    raise ValueError(kind)


# ================================================================================================ the eval (any start state)
class GEv:
    """One MFFU Builder eval a session at a time (= stack_one_account.Ev / account4_sim.Ev) with a pluggable sizer per
    strategy and any start state (balance vs start, room above the EOD floor, session, days traded)."""

    def __init__(self, E, z, stuck=None, start=None):
        self.E, self.z = E, z
        self.stuck = float(stuck if stuck is not None else E["stuck"])
        self.bal, self.peak, self.floor = 0.0, 0.0, -E["mll"]
        self.s, self.dtr, self.max_risk = 0, 0, 0.0
        self.wk = {}
        if start:
            self.bal = float(E["tgt"]) - float(start["to_go"])
            self.floor = self.bal - float(start["room"])
            self.peak = self.floor + E["mll"]
            self.s = self.dtr = int(start.get("session", 0))

    def step(self, ts):
        E = self.E
        dll = E["dll"]
        self.s += 1
        wkey = (self.s - 1) // 5
        cum, traded = 0.0, False
        for t in ts:
            if cum <= -dll:
                break
            room = self.bal + cum - self.floor
            st = {"profit": self.bal, "cum": cum, "room": room, "session": self.s, "n_today": 0,
                  "wk_pnl": self.wk.get(wkey, 0.0), "days_traded": self.dtr}
            q = size(t, st, self.z, room, cum, E["maxq"], min(dll, SA.SOFT_DLL))
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
        if self.bal <= self.floor:
            return "fail", round(cum, 2)
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - E["mll"]), E["lock"])
        if self.bal >= E["tgt"]:
            return "pass", round(cum, 2)
        if self.bal - self.floor < self.stuck:
            return "stuck", round(cum, 2)
        return None, round(cum, 2)


# ================================================================================================ the funded account
def ask_line(policy, ncyc):
    if policy == "cycle":                  # $2,000 on the 2nd traded day of the cycle, $500 less each day after, >= $500
        return max(500.0, 2000.0 - 500.0 * max(0, ncyc - 2))
    if policy == "cycle25":
        return max(250.0, 1000.0 - 250.0 * max(0, ncyc - 2))
    return None


class GF(U.Funded):
    """tools/uprisk.Funded (MFFU Builder sim funded) + per-strategy sizing + a request policy + a best-day-aware day stop.
    z[strat] = ("fq", None) = the account's funded preset (engine/sizing.funded_qty) | ("stack", usd, f)."""

    def __init__(self, plan, cfg, z, ask=None, policy=None, dstop=None):
        super().__init__(plan, cfg, ask)
        self.P = dict(self.P)
        self.z, self.policy, self.dstop = z, policy, dstop
        self.split = self.P["split"]

    def qty(self, t, st):
        if self.dstop is not None and st["cum"] >= max(float(st.get("cycle_prev") or 0.0), float(self.dstop)):
            return 0                       # one more win would make today > 50% of the cycle: done for the day
        s = self.z.get(t["strat"])
        if not s:
            return 0
        if s[0] == "fq":
            tt = t if t.get("tgt") else {**t, "tgt": 2.0 * t["risk"]}
            return super().qty({**tt, "tgt_pts": tt["tgt"], "risk_pts": tt["risk"]}, st)
        return SA.stack_q(t, {t["strat"]: {"usd": s[1], "f": s[2]}}, st["room"], st["cum"], self.A["max_micros"],
                          min(self.A["dll"], SA.SOFT_DLL))

    def _fast_track(self, day):
        a = ask_line(self.policy, len(self.cyc))
        if a is not None:
            self.P["ask_above"] = a
        return super()._fast_track(day)


# ================================================================================================ one account seat on a path
class Seat:
    """Evals (1, or several in parallel on the same signal) -> GAP sessions -> funded -> lost / 5 payouts -> a fresh eval.
    Only ONE of the parallel evals can be funded (MFFU: 1 Builder 50K; for a 25K the rule is applied the same way): the first
    pass is kept, the others are dropped. A failed / stuck eval is dropped; with none left a fresh one is bought."""

    def __init__(self, mk_eval, mk_fund, price, starts, cost0=0.0):
        self.mk_eval, self.mk_fund, self.price = mk_eval, mk_fund, price
        self.evals = list(starts)
        self.cost, self.owner, self.n_evals = cost0, 0.0, len(starts)
        self.f, self.wait = None, 0
        self.first_pass = self.first_pay = None
        self.pays, self.lost = 0, 0
        self.days = []

    def _fresh(self):
        self.cost += self.price
        self.n_evals += 1
        self.evals = [self.mk_eval(None)]

    def step(self, k, ts_e, ts_f):
        if self.evals:
            keep, passed, pnl = [], False, 0.0
            for i, e in enumerate(self.evals):
                r, p = e.step(ts_e)
                if i == 0:
                    pnl = p
                if r == "pass" and not passed:
                    passed = True
                elif r is None:
                    keep.append(e)
            self.days.append(pnl)
            if passed:
                self.first_pass = self.first_pass or k + 1
                self.evals, self.wait = [], GAP
            elif not keep:
                self._fresh()
            else:
                self.evals = keep
            return
        if self.f is None:
            self.days.append(0.0)
            self.wait -= 1
            if self.wait <= 0:
                self.f = self.mk_fund()
            return
        a = self.f.trade_pnl
        ev, x = self.f.step(ts_f)
        self.days.append(round(self.f.trade_pnl - a, 2))
        if ev in ("paid", "grad"):
            self.owner += x
            self.pays += 1
            self.first_pay = self.first_pay or k + 1
        if ev in ("lost", "grad"):
            self.lost += ev == "lost"
            self.f = None
            self._fresh()


def seat_stats(R, cal, price=None):
    n = len(R)
    net = np.array([r.owner - r.cost for r in R])
    fp = [r.first_pay for r in R if r.first_pay]
    ps = [r.first_pass for r in R if r.first_pass]
    p60 = [r.first_pass for r in R if r.first_pass and r.first_pass <= 60]
    med_fp = float(np.median(fp)) if fp else None
    return {"pass60": round(100.0 * len(p60) / n, 1), "pass_med": float(np.median(ps)) if ps else None,
            "pass_p10": round(100.0 * sum(1 for x in ps if x <= 10) / n, 1),
            "first_pay_med": med_fp, "first_pay_date": cal[int(round(med_fp)) - 1] if med_fp else None,
            "no_pay_6m": round(100.0 * sum(1 for r in R if not r.first_pay) / n, 1),
            "net_m": round(float(net.mean()) / MO), "owner_m": round(float(np.mean([r.owner for r in R])) / MO),
            "fees_6m": round(float(np.mean([r.cost for r in R])), 1), "evals": round(float(np.mean([r.n_evals for r in R])), 2),
            "pays": round(float(np.mean([r.pays for r in R])), 2)}


def run_seats(BYe, BYf, paths, makers):
    """makers: name -> () -> Seat; all on the SAME paths. -> name -> [Seat]."""
    out = {k: [] for k in makers}
    for seq in paths:
        ss = {k: m() for k, m in makers.items()}
        for k, si in enumerate(seq[:LEN]):
            for nm, s in ss.items():
                s.step(k, BYe[nm][si] if isinstance(BYe, dict) else BYe[si], BYf[nm][si] if isinstance(BYf, dict) else BYf[si])
        for nm, s in ss.items():
            out[nm].append(s)
    return out


def eval_quick(BY, paths, mk, h=60):
    """From the eval's start state: pass / fail within 10 sessions and the eventual pass (60), one eval, no rebuy."""
    res = []
    for seq in paths:
        e = mk()
        out, used = "open", h
        for k, si in enumerate(seq[:h]):
            r, _ = e.step(BY[si])
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


# ================================================================================================ the strategy sets
def Zlit50(var=None):
    return {"LIT": ("lit", ecfg50(var))}


def Zatlas25(cfg=None, lb=0.8):
    return {"ATLAS": ("need", _atlas_v(cfg), lb)}


F50_LIT = {"LIT": ("fq", None)}
F50_LA = {"LIT": ("fq", None), "ATLAS": ("stack", 500.0, 0.3)}
F50_LAB = {"LIT": ("fq", None), "ATLAS": ("stack", 500.0, 0.3), "BLITZ": ("stack", 300.0, 0.3)}


def by_mix(mix):
    """Per session, the trades of the strategies in mix (LIT / ATLAS / BLITZ from stack_one_account, ASIA = LIT Asia slot)."""
    base = SA.mix_by(tuple(m for m in mix if m != "ASIA"))
    if "ASIA" not in mix:
        return base
    S = SA.data()["S"]
    by = {}
    for u in _asia():
        by.setdefault(u["day"], []).append(u)
    return [sorted(base[i] + by.get(d, []), key=lambda t: t["entry_t"]) for i, d in enumerate(S)]


_AS = []


def _asia():
    if not _AS:
        from tools import second_mix as M
        for u in M.units()["Asia"]:
            _AS.append({"day": u["day"], "risk": float(u["risk"]), "tgt": float(u["tgt"] or 0) or None, "pts": float(u["pts"]),
                        "w1": float(min(0.0, u["w1"])), "entry_t": int(u["entry_t"]), "exit_t": int(u["exit_t"]),
                        "dir": int(u["dir"]), "strat": "ASIA"})
    return _AS


def plain(BY, span, usd):
    S = SA.data()["S"]
    return SA.plain_stats(BY, S, span, {**{"LIT": 0, "ATLAS": 0, "BLITZ": 0, "ASIA": 0}, **usd})


# ================================================================================================ lever 1: eval rescue
RESCUE50 = {"room 25%": {"room_f": 0.25}, "room 30%": {"room_f": 0.3}, "room 55%": {"room_f": 0.55}, "room 70%": {"room_f": 0.7}}
RESCUE25 = {"safe cap 20%": {"safe_cap": 0.2}, "safe cap 50%": {"safe_cap": 0.5}, "need size kept (two_week to 80)": {"two_week_until": 80},
            "no last bullet": None}   # ATLAS past eval session 10 sizes in safe_eval at 30% of the room (account_b)


def lever1_makers(acct, st, rescue=True):
    """Seats for one account from its hole st: continue / + parallel fresh / rescue sizings (hole eval only)."""
    if acct == "Z":
        E, price = E50, PRICE50
        mk_ev = lambda zz=None, s=None: GEv(E, zz or Zlit50(), start=s)            # noqa: E731
        mk_f = lambda: GF("builder50k", U.UP50, F50_LIT)                           # noqa: E731
        R = RESCUE50
        zr = {k: Zlit50(v) for k, v in R.items()}
    else:
        E, price = E25, PRICE25_CODE
        mk_ev = lambda zz=None, s=None: GEv(E, zz or Zatlas25(), stuck=200.0, start=s)   # noqa: E731
        mk_f = lambda: GF("builder25k", U.UP25, {"ATLAS": ("fq", None)})           # noqa: E731
        R = RESCUE25
        zr = {k: (Zatlas25(v) if v else Zatlas25(lb=None)) for k, v in R.items()}
    fresh = lambda _=None: mk_ev()                                                  # noqa: E731
    M = {"continue": lambda: Seat(fresh, mk_f, price, [mk_ev(s=st)]),
         "+ fresh eval now": lambda: Seat(fresh, mk_f, price, [mk_ev(s=st), mk_ev()], cost0=price),
         "restart fresh (drop the hole)": lambda: Seat(fresh, mk_f, price, [mk_ev()], cost0=price)}
    if rescue:
        for k, z in zr.items():
            M[f"rescue {k}"] = (lambda z=z: Seat(fresh, mk_f, price, [mk_ev(zz=z, s=st)]))
    return M


def lever1(PF, PE, st_z, st_a, cal, n_grid, log=print):
    BYl, BYa = by_mix(("LIT",)), by_mix(("ATLAS",))
    out = {"zlarior": {}, "atlas": {}, "plain": {}, "grid50": [], "grid25": []}
    for sp in SPANS:
        out["plain"][sp] = {"LIT ($500 a trade)": plain(BYl, sp, {"LIT": 500.0}), "ATLAS ($250 a trade)": plain(BYa, sp, {"ATLAS": 250.0})}
    for acct, st, BY, key in (("Z", st_z, BYl, "zlarior"), ("A", st_a, BYa, "atlas")):
        M = lever1_makers(acct, st)
        for sp in SPANS:
            t0 = time.time()
            R = run_seats(BY, BY, PF[sp], M)
            row = {nm: seat_stats(v, cal) for nm, v in R.items()}
            E = E50 if acct == "Z" else E25
            mk = (lambda: GEv(E, Zlit50(), start=st)) if acct == "Z" else (lambda: GEv(E, Zatlas25(), stuck=200.0, start=st))
            row["_hole_eval"] = eval_quick(BY, PE[sp], mk)
            mkf = (lambda: GEv(E, Zlit50())) if acct == "Z" else (lambda: GEv(E, Zatlas25(), stuck=200.0))
            row["_fresh_eval"] = eval_quick(BY, PE[sp], mkf)
            for k, v in (RESCUE50 if acct == "Z" else RESCUE25).items():
                z = Zlit50(v) if acct == "Z" else (Zatlas25(v) if v else Zatlas25(lb=None))
                row[f"_hole_eval rescue {k}"] = eval_quick(BY, PE[sp], lambda z=z: GEv(E, z, stuck=None if acct == "Z" else 200.0, start=st))
            out[key][sp] = row
            for nm, x in row.items():
                if not nm.startswith("_"):
                    log(f"  L1 {key:7s} {sp:3s} {nm:30s} pass60 {x['pass60']:5.1f} med {x['pass_med']} 1st pay {x['first_pay_med']} "
                        f"({x['first_pay_date']}) nopay {x['no_pay_6m']}% ${x['net_m']}/mo fees ${x['fees_6m']}")
            for nm, x in row.items():
                if nm.startswith("_"):
                    log(f"     {nm[1:]:40s} {x}")
            log(f"     ({time.time() - t0:.0f}s)")
    # threshold grid: where does a parallel fresh eval pay (first payout sooner AND more $ a month) in H1 and H2?
    for acct, BY, rooms, togos, grid in (("Z", BYl, (300, 600, 900, 1145, 1500), (1500, 2500, 3000, 3687, 4200), "grid50"),
                                         ("A", BYa, (250, 400, 600, 822), (900, 1300, 1678, 2100), "grid25")):
        E = E50 if acct == "Z" else E25
        for room in rooms:
            for tg in togos:
                bal = E["tgt"] - tg
                floor = bal - room
                if floor < -E["mll"] - 1e-9 or floor > E["lock"] + 1e-9 or bal <= floor:
                    continue
                st = {"room": float(room), "to_go": float(tg), "session": 20}
                M = lever1_makers(acct, st, rescue=False)
                cell = {"room": room, "to_go": tg}
                for sp in ("H1", "H2"):
                    R = run_seats(BY, BY, PF[sp][:n_grid], {k: M[k] for k in ("continue", "+ fresh eval now")})
                    a, b = seat_stats(R["continue"], cal), seat_stats(R["+ fresh eval now"], cal)
                    cell[sp] = {"cont_fp": a["first_pay_med"], "par_fp": b["first_pay_med"], "cont_m": a["net_m"], "par_m": b["net_m"],
                                "cont_nopay": a["no_pay_6m"], "par_nopay": b["no_pay_6m"]}
                cell["pays"] = all((cell[sp]["par_fp"] or 999) < (cell[sp]["cont_fp"] or 999) and cell[sp]["par_m"] >= cell[sp]["cont_m"]
                                   for sp in ("H1", "H2"))
                out[grid].append(cell)
                log(f"  L1 grid {acct} room {room:5} to-go {tg:5} H1 {cell['H1']} H2 {cell['H2']} -> {'PAYS' if cell['pays'] else 'no'}")
    return out


# ================================================================================================ lever 2: the 2nd Builder 25K
MIX25 = {   # name -> (strategies, eval sizers, funded sizers, fixed $ a trade for the plain view)
    "LIT 25K copy": (("LIT",), lambda: {"LIT": ("lit", ecfg25())}, {"LIT": ("fq", None)}, {"LIT": 250.0}),
    "LIT + ATLAS $250": (("LIT", "ATLAS"), lambda: {"LIT": ("lit", ecfg25()), "ATLAS": ("stack", 250.0, 0.3)},
                         {"LIT": ("fq", None), "ATLAS": ("stack", 250.0, 0.3)}, {"LIT": 250.0, "ATLAS": 250.0}),
    "ATLAS + BLITZ $150": (("ATLAS", "BLITZ"), lambda: {"ATLAS": ("need", _atlas_v(), 0.8), "BLITZ": ("stack", 150.0, 0.3)},
                           {"ATLAS": ("fq", None), "BLITZ": ("stack", 150.0, 0.3)}, {"ATLAS": 250.0, "BLITZ": 150.0}),
    "LIT + Asia slot": (("LIT", "ASIA"), lambda: {"LIT": ("lit", ecfg25()), "ASIA": ("lit", ecfg25())},
                        {"LIT": ("fq", None), "ASIA": ("fq", None)}, {"LIT": 250.0, "ASIA": 250.0}),
    "LIT eval; funded + ATLAS $250": (("LIT", "ATLAS"), lambda: {"LIT": ("lit", ecfg25())},
                                      {"LIT": ("fq", None), "ATLAS": ("stack", 250.0, 0.3)}, {"LIT": 250.0, "ATLAS": 250.0}),
    "2nd ATLAS copy": (("ATLAS",), lambda: {"ATLAS": ("need", _atlas_v(), 0.8)}, {"ATLAS": ("fq", None)}, {"ATLAS": 250.0}),
}


def lever2(PF, PE, st_a, cal, log=print):
    out = {}
    BY = {nm: by_mix(m[0]) for nm, m in MIX25.items()}
    BY["ATLAS own 25K"] = by_mix(("ATLAS",))
    mk = {}
    for nm, (_, ze, zf, _) in MIX25.items():
        stuck = 200.0 if "ATLAS" in ze() and ze()["ATLAS"][0] == "need" else None
        mk[nm] = (lambda ze=ze, zf=zf, stuck=stuck: Seat(lambda _=None: GEv(E25, ze(), stuck=stuck),
                                                           lambda: GF("builder25k", U.UP25, zf), PRICE25, [GEv(E25, ze(), stuck=stuck)],
                                                           cost0=PRICE25))
    mk["ATLAS own 25K"] = lambda: Seat(lambda _=None: GEv(E25, Zatlas25(), stuck=200.0), lambda: GF("builder25k", U.UP25, {"ATLAS": ("fq", None)}),
                                       PRICE25_CODE, [GEv(E25, Zatlas25(), stuck=200.0, start=st_a)])
    for sp in SPANS:
        t0 = time.time()
        R = run_seats(BY, BY, PF[sp], mk)
        own = R["ATLAS own 25K"]
        row = {"ATLAS own 25K": seat_stats(own, cal)}
        for nm in MIX25:
            x = seat_stats(R[nm], cal)
            x["eval"] = eval_quick(BY[nm], PE[sp], lambda nm=nm: GEv(E25, MIX25[nm][1](), stuck=200.0 if "ATLAS" in nm and "LIT" not in nm else None))
            x["plain"] = plain(BY[nm], sp, MIX25[nm][3])
            cs = [np.corrcoef(a.days, b.days)[0, 1] for a, b in zip(R[nm], own) if np.std(a.days) > 0 and np.std(b.days) > 0]
            x["corr_vs_atlas"] = round(float(np.nanmean(cs)), 2) if cs else None
            x["both_no_pay"] = round(100.0 * sum(1 for a, b in zip(R[nm], own) if not a.first_pay and not b.first_pay) / len(own), 1)
            pf = [min(a.first_pay or 999, b.first_pay or 999) for a, b in zip(R[nm], own)]
            pf = [p for p in pf if p < 999]
            x["pair_first_pay_med"] = float(np.median(pf)) if pf else None
            x["pair_net_m"] = round(float(np.mean([a.owner - a.cost + b.owner - b.cost for a, b in zip(R[nm], own)])) / MO)
            row[nm] = x
            p, e = x["plain"], x["eval"]
            log(f"  L2 {sp:3s} {nm:20s} {p['tpw']}/wk PF {p['pf']} ${p['per_month']}/mo dd {p['max_dd']} | eval med {e['pass_med']} "
                f"2wk {e['p10']}/{e['f10']} | 1st pay {x['first_pay_med']} nopay {x['no_pay_6m']}% ${x['net_m']}/mo | corr {x['corr_vs_atlas']} "
                f"both-nopay {x['both_no_pay']}% pair ${x['pair_net_m']}/mo pair 1st {x['pair_first_pay_med']}")
        out[sp] = row
        log(f"  L2 {sp} ATLAS own 25K {row['ATLAS own 25K']}  ({time.time() - t0:.0f}s)")
    return out


# ================================================================================================ lever 3: funded 50K payout engine
POLICIES = {"ask $1,500 (today)": (None, None), "ask $500 asap": (500.0, None), "ask $1,000": (1000.0, None),
            "ask $2,000 (cap)": (2000.0, None), "cycle-timed": (None, "cycle")}
DSTOPS = {"no day stop": None, "best-day stop $500": 500.0, "best-day stop $1,000": 1000.0}
FMIX = {"LIT alone": (("LIT",), F50_LIT), "LIT + ATLAS $500": (("LIT", "ATLAS"), F50_LA),
        "LIT + ATLAS $500 + BLITZ $300": (("LIT", "ATLAS", "BLITZ"), F50_LAB)}


def funded_run(BY, paths, mk):
    out = []
    for seq in paths:
        f = mk()
        owner, first, npay, lost = 0.0, None, 0, False
        days = []
        for k, si in enumerate(seq[:LEN]):
            a = f.trade_pnl
            ev, x = f.step(BY[si])
            days.append(f.trade_pnl - a)
            if ev in ("paid", "grad"):
                owner += x
                npay += 1
                first = first or k + 1
            if ev in ("lost", "grad"):
                lost = ev == "lost"
                break
        out.append((owner, first, npay, lost, f.hold["cons"]))
    n = len(out)
    fr = [x[1] for x in out if x[1]]
    return {"per_month": round(float(np.mean([x[0] for x in out])) / MO), "first_med": float(np.median(fr)) if fr else None,
            "first_p75": float(np.percentile(fr, 75)) if fr else None,
            "no_pay_6m": round(100.0 * (n - len(fr)) / n, 1), "lost_6m": round(100.0 * sum(1 for x in out if x[3]) / n, 1),
            "payouts": round(float(np.mean([x[2] for x in out])), 2), "paid_6m": round(float(np.mean([x[0] for x in out])))}


def lever3(PF, cal, st_z, log=print):
    out = {}
    BY = {nm: by_mix(m[0]) for nm, m in FMIX.items()}
    for sp in SPANS:
        out[sp] = {}
        for mx, (mix, z) in FMIX.items():
            for pn, (ask, pol) in POLICIES.items():
                for dn, ds in DSTOPS.items():
                    if mx == "LIT alone" and dn != "no day stop":
                        continue
                    t0 = time.time()
                    r = funded_run(BY[mx], PF[sp], lambda: GF("builder50k", U.UP50, z, ask=ask, policy=pol, dstop=ds))
                    out[sp][f"{mx} | {pn} | {dn}"] = r
                    log(f"  L3 {sp:3s} {mx:30s} {pn:20s} {dn:22s} 1st {r['first_med']} (p75 {r['first_p75']}) nopay {r['no_pay_6m']}% "
                        f"lost {r['lost_6m']}% pays {r['payouts']} ${r['per_month']}/mo ({time.time() - t0:.0f}s)")
        out[sp]["_plain"] = {mx: plain(BY[mx], sp, {"LIT": 500.0, "ATLAS": 500.0, "BLITZ": 300.0}) for mx in FMIX}
    return out


def lever3_chain(PF, cal, st_z, picks, log=print):
    """Zlarior from its real hole: LIT eval -> funded with the picked funded mix + policy: the calendar of the first payout."""
    BYe = by_mix(("LIT",))
    out = {}
    for sp in SPANS:
        M, BYf = {}, {}
        for key, pk in picks.items():
            mx, pn, dn = pk[:3]
            par = len(pk) > 3 and pk[3]
            mix, z = FMIX[mx]
            ask, pol = POLICIES[pn]
            ds = DSTOPS[dn]
            M[key] = (lambda z=z, ask=ask, pol=pol, ds=ds, par=par: Seat(
                lambda _=None: GEv(E50, Zlit50()), lambda: GF("builder50k", U.UP50, z, ask=ask, policy=pol, dstop=ds), PRICE50,
                [GEv(E50, Zlit50(), start=st_z)] + ([GEv(E50, Zlit50())] if par else []), cost0=PRICE50 if par else 0.0))
            BYf[key] = by_mix(mix)
        R = run_seats({k: BYe for k in M}, BYf, PF[sp], M)
        out[sp] = {k: seat_stats(v, cal) for k, v in R.items()}
        for k, x in out[sp].items():
            log(f"  L3 chain {sp} {k:40s} 1st pay {x['first_pay_med']} ({x['first_pay_date']}) nopay {x['no_pay_6m']}% ${x['net_m']}/mo")
    return out


def pick3(o):
    """Per funded mix: the policy x day stop with the soonest first payout in H1 (ties: more $), then the H2 check: adopt only
    when it beats today's (ask $1,500, no day stop) on the first payout AND $ a month in BOTH halves."""
    res = {}
    for mx in FMIX:
        base = f"{mx} | ask $1,500 (today) | no day stop"
        cands = [k for k in o["H1"] if k.startswith(mx + " |") and not k.startswith("_")]
        best = min(cands, key=lambda k: ((o["H1"][k]["first_med"] or 999), -o["H1"][k]["per_month"]))
        ok = {sp: (o[sp][best]["first_med"] or 999) < (o[sp][base]["first_med"] or 999) and o[sp][best]["per_month"] >= o[sp][base]["per_month"]
              for sp in ("H1", "H2")}
        best_m = max(cands, key=lambda k: o["H1"][k]["per_month"])
        ok_m = {sp: o[sp][best_m]["per_month"] > o[sp][base]["per_month"] and (o[sp][best_m]["first_med"] or 999) <= (o[sp][base]["first_med"] or 999)
                for sp in ("H1", "H2")}
        res[mx] = {"base": base, "fastest_h1": best, "fastest_beats_today_both": all(ok.values()), "checks": ok,
                   "richest_h1": best_m, "richest_beats_today_both": all(ok_m.values()), "checks_rich": ok_m}
    return res


# ================================================================================================ main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--n-grid", type=int, default=300)
    ap.add_argument("--z-room", type=float, default=ZLARIOR["room"])
    ap.add_argument("--z-togo", type=float, default=ZLARIOR["to_go"])
    ap.add_argument("--z-session", type=int, default=ZLARIOR["session"])
    ap.add_argument("--a-room", type=float, default=ATLAS["room"])
    ap.add_argument("--a-togo", type=float, default=ATLAS["to_go"])
    ap.add_argument("--a-session", type=int, default=ATLAS["session"])
    ap.add_argument("--only", default="123")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args(argv)
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    import payout_plan as PP
    cal = PP.calendar(LEN + 5, START_DAY)
    st_z = {"room": a.z_room, "to_go": a.z_togo, "session": a.z_session}
    st_a = {"room": a.a_room, "to_go": a.a_togo, "session": a.a_session}
    t0 = time.time()
    S = SA.data()["S"]
    PE = {sp: U.mc_paths(S, sp, a.n, length=60, seed=A4.SEED_EVAL) for sp in SPANS}
    PF = {sp: U.mc_paths(S, sp, a.n, length=LEN, seed=A4.SEED_LIFE) for sp in SPANS}
    out = {"date": "2026-11-16", "n": a.n, "n_grid": a.n_grid, "start_day": START_DAY, "zlarior": st_z, "atlas": st_a, "spans": U.SPAN}
    prev = {}
    if os.path.exists(OUT) and a.only != "123":
        prev = json.load(open(OUT, encoding="utf-8"))
    if "1" in a.only:
        out["lever1"] = lever1(PF, PE, st_z, st_a, cal, a.n_grid)
    if "2" in a.only:
        out["lever2"] = lever2(PF, PE, st_a, cal)
    if "3" in a.only:
        o3 = lever3(PF, cal, st_z)
        out["lever3"] = o3
        out["lever3_pick"] = pick3(o3)
        picks = {"today: LIT eval, funded LIT alone, ask $1,500": ("LIT alone", "ask $1,500 (today)", "no day stop"),
                 "LIT eval, funded + ATLAS $500, ask $1,500": ("LIT + ATLAS $500", "ask $1,500 (today)", "no day stop")}
        picks["+ fresh 50K eval now (parallel), funded LIT alone"] = ("LIT alone", "ask $1,500 (today)", "no day stop", True)
        picks["+ fresh 50K eval now (parallel), funded + ATLAS $500"] = ("LIT + ATLAS $500", "ask $1,500 (today)", "no day stop", True)
        picks["+ fresh 50K eval now (parallel), funded + ATLAS $500 + BLITZ $300"] = ("LIT + ATLAS $500 + BLITZ $300", "ask $1,500 (today)",
                                                                                       "no day stop", True)
        for mx, p in out["lever3_pick"].items():
            if mx != "LIT alone":
                _, pn, dn = p["fastest_h1"].split(" | ")
                picks[f"LIT eval, funded {mx}, {pn}, {dn}"] = (mx, pn, dn)
        out["lever3_chain"] = lever3_chain(PF, cal, st_z, picks)
        for mx, p in out["lever3_pick"].items():
            print(f"L3 pick {mx}: fastest {p['fastest_h1']} beats today both halves: {p['fastest_beats_today_both']} {p['checks']}; "
                  f"richest {p['richest_h1']}: {p['richest_beats_today_both']} {p['checks_rich']}")
    for k, v in prev.items():
        out.setdefault(k, v)
    if not a.no_save:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=float)
        print("wrote", os.path.relpath(OUT, ROOT))
    print(f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
