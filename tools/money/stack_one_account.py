"""More strategies on ONE MFFU account (owner 2026-11-16: "it shouldn't take 2 months to get a payout ... there are definitely
trading bots better than us"). Write-up: research/writeups/stack-one-account-2026-11-16.md. PAPER RESEARCH ONLY: reads stored
trades, writes research/lab/stack_one_account.json, changes nothing live (no live_model*.json, no engine file).

Question: put LIT (Zlarior) + ATLAS (+ BLITZ) trades on the SAME account (Builder 50K, and separately a Rapid EOD 50K) so the
account has more winning days. Does the eval pass sooner, does the first funded payout come sooner, and is it more $ a month?

Trades (all stored, nothing re-tuned; futures data only, CME NQ1! bars):
  LIT    the 120 live trades of 2026 + 511 REF 2021-25 (run lit_live ledger, tools/account4_sim.trades: 1m fills in 2026, 5m in
         2021-25), sized exactly as the live bot: eval = live_model.json lit_sizing two_week (tools/account4_sim.ecfg), funded =
         the fleet MFFU preset tools/uprisk.UP50 (60% of the room, <= $1,500, a winner <= $2,000).
  ATLAS  the live ATLAS (EMA London pullback + MACD sweep + S/R NY reclaim, tools/atlas.BASE) through tools/atlas.account_units:
         never opposite LIT (no entry while LIT holds / has an armed setup the other way; LIT entering opposite closes ATLAS
         first = HEDGE, 1 tick) - the engine/account_b.py rule; then ATLAS's own one position + max 2 a day.
  BLITZ  the noise-area scalp as account C (tools/blitz25k_lib.trades, mode "lit+atlas": never opposite LIT or ATLAS, closed
         first); 1m in 2026, 5m in 2021-25.
  Costs: $1.90 a micro round trip, 1 tick on market fills / stops (in the stored prices), a soft-daily-loss cut at its level.

Sizing of the added strategies (LIT keeps its live size): $ risk a trade = min(usd, f x room to the floor, the soft daily loss
left today), micros = that / one full stop-out of 1 micro ((stop + 1 tick) x $2 + $1.90): one full stop-out never exceeds the
soft daily loss ($1,000; the Rapid EOD has none, the bot's own $1,000 is used). Same sizes in the eval and the funded account.
On the Rapid EOD eval the fleet's 30% best-day guard caps every trade so a win keeps the day under 30% x $3,000 x 0.95.

Accounts: MFFU Builder 50K (tools/account4_sim.Ev / tools/uprisk.Funded: $3,000 target, $2,000 EOD trailing, $1,000 soft DLL,
buffer $2,100, $500 min, 50% best day, 2 days a cycle, 80%, 5 payouts, price $91.80) and MFFU Rapid EOD 50K (engine/copy_accounts
rules: $3,000 target, $2,000 EOD trailing, 30% best day + 4 days in the eval; funded: daily payouts above the $2,100 buffer, $500
min, 90%, no consistency; Tier-1 news flat 2 min before to 2 min after - LIT / ATLAS / BLITZ alike; price $94).

Monte Carlo (identical paths for every mix): 5-session blocks drawn from the span, eval 2,000 paths x 60 sessions (seed 7),
funded and the 6-month account slot (eval -> 2 sessions paperwork -> funded -> lost / 5 payouts -> buy again) 1,000 x 126
(seed 23). Spans: H1 = 2026 Jan-Jun (pick), H2 = Jul-Oct 2026 (check), REF = 2021-11 .. 2025 (reference).

    python -X utf8 tools/money/stack_one_account.py            # all -> research/lab/stack_one_account.json
    python -X utf8 tools/money/stack_one_account.py --n 300    # quicker
Simplifications: trades of a day are played in entry order with the day's closed P&L (two overlapping same-direction trades are
not netted); the news rule flattens at the 1m (5m before 2026) open 2 minutes before the release, an entry inside the window
is skipped.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import math
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import account4_sim as A4  # noqa: E402
import uprisk as U  # noqa: E402
from engine import firms as FM  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from engine.lit import qty_for  # noqa: E402

PV, COMM, SLIP = U.PV, U.COMM, U.SLIP
OUT = os.path.join(ROOT, "research", "lab", "stack_one_account.json")
SPANS = ("H1", "H2", "REF")
LEN, GAP, H_EVAL, MO = U.LEN, U.GAP, 60, U.LEN / 21.0
PRICE = {"builder": 91.80, "rapid_eod": 94.00}
SOFT_DLL = 1000.0


# ================================================================================================ trades
def _atlas():
    from tools import atlas as A
    out, cur, busy, nday = [], None, 0, 0
    for t in A.account_units(A.BASE):
        if t["day"] != cur:
            cur, busy, nday = t["day"], 0, 0
        if t["entry_t"] < busy or nday >= 2:           # ATLAS: one position, max 2 a day (engine/account_b)
            continue
        busy, nday = t["exit_t"], nday + 1
        out.append({"day": t["day"], "risk": float(t["risk"]), "tgt": float(t["tgt"] or 0) or None, "pts": float(t["pts"]),
                    "w1": float(min(0.0, t["w1"])), "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]),
                    "strat": "ATLAS", "src": t["src"]})
    return out


def _blitz():
    from tools import blitz25k_lib as BL
    TT = BL.trades(None, "lit+atlas")
    out = []
    for tf, keep in ((1, lambda d: d >= "2026-01-01"), (5, lambda d: d < "2026-01-01")):
        for t in TT[tf]:
            if not keep(t["day"]):
                continue
            out.append({"day": t["day"], "risk": float(t["risk_pts"]), "tgt": None, "pts": float(t["pts"]),
                        "w1": -float(t["mae_pts"]), "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]),
                        "strat": "BLITZ", "tf": tf})
    return out


_D = {}


def data():
    """S (sessions), LIT by session (account4_sim), the ATLAS / BLITZ trades by day."""
    if not _D:
        S, BY = A4.load()
        L = [[{**t, "strat": "LIT", "tf": 1 if not t["ref"] else 5} for t in ts] for ts in BY]
        by = collections.defaultdict(list)
        for t in _atlas() + _blitz():
            by[t["day"]].append(t)
        _D.update(S=S, LIT=L, OTHER=by)
    return _D


def mix_by(mix, news=False):
    """Per session: the trades of the strategies in `mix`, in entry order (LIT first on a tie)."""
    D = data()
    pr = {"LIT": 0, "ATLAS": 1, "BLITZ": 2}
    out = []
    for i, d in enumerate(D["S"]):
        ts = list(D["LIT"][i]) if "LIT" in mix else []
        ts += [t for t in D["OTHER"].get(d, ()) if t["strat"] in mix]
        ts.sort(key=lambda t: (t["entry_t"], pr[t["strat"]]))
        out.append(news_rule(ts) if news else ts)
    return out


# ================================================================================================ the Rapid EOD funded news rule
_NB = {}


def news_rule(ts, pre=2, post=2):
    """Tier-1 releases (CPI, NFP, FOMC, minutes; tools/lit_mffu_rapid_stack.tier1): an entry inside [release - 2, release + 2)
    min is skipped; a trade open at release - 2 min is flattened at that minute's open (1 tick), worst open from the bars."""
    import lit_mffu_rapid_stack as RS
    from zoneinfo import ZoneInfo
    if "cal" not in _NB:
        _NB["cal"] = RS.tier1()
    cal = _NB["cal"]
    out = []
    for t in ts:
        rel = cal.get(t["day"])
        if not rel:
            out.append(t)
            continue
        d0 = dt.datetime.fromisoformat(t["day"]).replace(tzinfo=ZoneInfo("America/New_York"))
        act, tt = "keep", t
        for mins in sorted(rel):
            r = int((d0 + dt.timedelta(minutes=mins)).timestamp())
            w0, w1 = r - pre * 60, r + post * 60
            if w0 <= t["entry_t"] < w1:
                act = "skip"
                break
            if t["entry_t"] < w0 < t["exit_t"]:
                tf = 1 if t["day"] >= "2025-12-29" and t.get("tf") == 1 else 5
                T, O, H, L = RS.bars(tf)
                i0 = int(np.searchsorted(T, t["entry_t"] - (t["entry_t"] % (tf * 60))))
                j = int(np.searchsorted(T, w0 - (w0 % (tf * 60))))
                if i0 >= len(T) or j >= len(T) or j <= i0:
                    act = "skip"
                    break
                ent, px, dr = O[i0], O[j], t["dir"]
                pts = dr * (px - ent) - SLIP
                adv = (np.min(L[i0:j]) - ent) if dr > 0 else (ent - np.max(H[i0:j]))
                tt = {**t, "pts": round(float(pts), 2), "w1": round(float(min(0.0, adv, pts)), 2), "exit_t": int(T[j]), "news": True}
                act = "flat"
                break
        if act == "keep":
            out.append(t)
        elif act == "flat":
            out.append(tt)
    return out


# ================================================================================================ sizing of the added strategies
def stack_q(t, z, room, cum, maxq, dll=SOFT_DLL):
    """$ = min(usd, f x room, the soft daily loss left today); micros = $ / one full stop-out of 1 micro."""
    s = z.get(t["strat"])
    if not s:
        return 0
    loss1 = (t["risk"] + SLIP) * PV + COMM
    usd = min(float(s["usd"]), float(s["f"]) * max(0.0, room), dll + min(0.0, cum))
    return max(0, min(int(maxq), int(usd // loss1)))


def cons_cap(q, t, cons, tgt, cum):
    """The fleet's best-day guard (engine/firms.BEST_DAY_MARGIN): a winner keeps today under cons x target x 0.95."""
    if q <= 0 or not cons:
        return q
    win1 = (t["tgt"] or 2.0 * t["risk"]) * PV - COMM
    if win1 <= 0:
        return q
    return min(q, int(math.floor((cons * tgt * FM.BEST_DAY_MARGIN - max(0.0, cum)) / win1)))


# ================================================================================================ the eval
class Ev(A4.Ev):
    """tools/account4_sim.Ev (LIT: engine/sizing.lit_qty, the live two_week) + the added strategies at stack_q."""

    def __init__(self, cfg, E, z):
        super().__init__(cfg, E)
        self.z = z

    def step(self, ts, keep=None):
        c, E = self.cfg, self.E
        dll = c.get("_dll", E["dll"])
        self.s += 1
        wkey = (self.s - 1) // 5
        cum, traded = 0.0, False
        sub = {k: v for k, v in c.items() if not k.startswith("_")}
        for t in ts:
            if cum <= -dll:
                break
            room = self.bal + cum - self.floor
            if t["strat"] == "LIT":
                m0 = qty_for(t["risk"])
                if not m0:
                    continue
                st = {"profit": self.bal, "cum": cum, "room": room, "session": self.s, "n_today": 0,
                      "wk_pnl": self.wk.get(wkey, 0.0), "days_traded": self.dtr}
                q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, sub, room=room, state=st,
                               learning=None, max_micros=c["_maxq"])["qty"]
                q = min(q, c["_maxq"])
            else:
                q = stack_q(t, self.z, room, cum, c["_maxq"], min(dll, SOFT_DLL))
            q = cons_cap(q, t, E.get("cons"), E["tgt"], cum)
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
class BuilderFunded(U.Funded):
    """tools/uprisk.Funded (MFFU Builder sim funded, bit-checked against engine/sizing + engine/funded_life); only the size of
    an added-strategy trade changes."""

    def __init__(self, cfg, z):
        super().__init__("builder50k", cfg)
        self.z = z

    def qty(self, t, st):
        if t["strat"] == "LIT":
            return super().qty(t, st)
        return stack_q(t, self.z, st["room"], st["cum"], self.A["max_micros"], min(self.A["dll"], SOFT_DLL))


class Builder(A4.Mffu):
    def __init__(self, fcfg, z):
        self.f = BuilderFunded(fcfg, z)
        self.split = 0.8


class Rapid(A4.Lucid):
    """tools/account4_sim.Lucid with the Rapid EOD rules (daily payouts above the buffer, no consistency, 90%) + stack_q."""

    def __init__(self, fcfg, R, z):
        super().__init__(fcfg, R, ask=500.0)
        self.z = z

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
               "cycle_target": round(max(0.0, R["buffer"] + min(cap, 2000.0) - self.cyc_start), 2)}
        cum = 0.0
        for t in ts:
            if cum <= -dll:
                break
            room = round(self.bal + cum - self.floor, 2)
            if t["strat"] == "LIT":
                st = {"room": room, "cum": cum, "locked": self.floor >= R["lock"] - 1e-9, "bal": self.bal, **cyc}
                q = min(SZ.funded_qty(t, st, c, acct=A), mq)
            else:
                q = stack_q(t, self.z, room, cum, mq, min(dll, SOFT_DLL))
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
        above = self.bal - R["buffer"]
        if above >= R["pay_min"] and self.bal - self.cyc_start > 0:
            amt = round(min(cap, above), 2)
            self.pays.append(amt)
            self.bal -= amt
            self.cyc, self.cyc_start = [], self.bal
            if len(self.pays) >= R["max_payouts"]:
                self.state = "grad"
                return "grad", amt * self.split, round(cum, 2)
            return "paid", amt * self.split, round(cum, 2)
        return None, None, round(cum, 2)


# ================================================================================================ the account plans
def plan(kind, z):
    """spec for a 6-month slot: eval rules E, eval sizing, funded maker, price, the per-session trades to use (eval / funded)."""
    if kind == "builder":
        E = A4.MFFU_E
        return {"E": E, "ecfg": A4.ecfg(E), "z": z, "price": PRICE["builder"], "fund": lambda: Builder(U.UP50, z)}
    E, F = A4.rules("mffu_rapid_eod_50k")
    E = {**E, "stuck": 200.0}
    F = {**F, "dll": SOFT_DLL}                     # no DLL on the plan: the bot's own $1,000 soft day
    return {"E": E, "ecfg": A4.ecfg(E, {"dll_off": True}), "z": z, "price": PRICE["rapid_eod"], "fund": lambda: Rapid(U.UP50, F, z),
            "news": True}


class Slot(A4.Slot):
    """tools/account4_sim.Slot with this file's eval; funded sessions use the news-ruled trades when the plan has the rule."""

    def _buy(self):
        self.cost += self.sp["price"]
        self.evals += 1
        self.e = Ev(self.sp["ecfg"], self.sp["E"], self.sp["z"])


def run_slots(BYe, BYf, paths, spec):
    R = []
    for seq in paths:
        s = Slot(spec)
        for k, si in enumerate(seq[:LEN]):
            s.step(k, BYe[si] if s.e is not None else BYf[si])
        R.append(s.out())
    return R


# ================================================================================================ scores
def eval_stats(BY, paths, spec):
    res = []
    for seq in paths:
        e = Ev(spec["ecfg"], spec["E"], spec["z"])
        out, used = "open", len(seq[:H_EVAL])
        for k, si in enumerate(seq[:H_EVAL]):
            r, _ = e.step(BY[si])
            if r:
                out, used = ("pass" if r == "pass" else "fail"), k + 1
                break
        res.append((out, used, e.max_risk))
    n = len(res)
    pas = [u for o, u, _ in res if o == "pass"]
    return {"p10": round(100.0 * sum(1 for u in pas if u <= 10) / n, 1),
            "f10": round(100.0 * sum(1 for o, u, _ in res if o == "fail" and u <= 10) / n, 1),
            "p60": round(100.0 * len(pas) / n, 1), "f60": round(100.0 * sum(1 for o, _, _ in res if o == "fail") / n, 1),
            "pass_med": float(np.median(pas)) if pas else None, "max_risk": round(max(r[2] for r in res))}


def funded_stats(BY, paths, spec):
    out = []
    for seq in paths:
        f = spec["fund"]()
        owner, lost, first, npay = 0.0, None, None, 0
        for k, si in enumerate(seq[:LEN]):
            ev, x, _ = f.step(BY[si])
            if ev in ("paid", "grad"):
                owner += x
                npay += 1
                first = first or k + 1
            if ev in ("lost", "grad"):
                lost = k + 1 if ev == "lost" else None
                break
        out.append((owner, lost, first, npay))
    n = len(out)
    o = np.array([x[0] for x in out])
    fr = [x[2] for x in out if x[2]]
    return {"per_month": round(float(o.mean()) / MO), "lost_6m": round(100.0 * sum(1 for x in out if x[1]) / n, 1),
            "first_med": float(np.median(fr)) if fr else None, "any_pay": round(100.0 * len(fr) / n, 1),
            "payouts": round(float(np.mean([x[3] for x in out])), 2)}


def plain_stats(BY, S, span, usd):
    """The real days of the span in order, every trade at a fixed $ risk (LIT usd["LIT"], ATLAS / BLITZ their own), costs in."""
    a, z = U.span_ix(S, span)
    pnl, days = [], []
    for si in range(a, z):
        d = 0.0
        for t in BY[si]:
            q = max(1, int(usd[t["strat"]] // ((t["risk"] + SLIP) * PV + COMM)))
            p = t["pts"] * PV * q - COMM * q
            pnl.append(p)
            d += p
        days.append(d)
    p = np.array(pnl) if pnl else np.zeros(1)
    eq = np.cumsum(days)
    gl = -p[p < 0].sum()
    ns = z - a
    return {"trades": len(pnl), "tpw": round(len(pnl) / (ns / 5.0), 2), "win": round(100.0 * float((p > 0).mean()), 1),
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum())),
            "per_month": round(float(p.sum()) / (ns / 21.0)),
            "max_dd": round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())),
            "win_days_pw": round(sum(1 for x in days if x > 0) / (ns / 5.0), 2)}


# ================================================================================================ the study
def Z(atlas=None, blitz=None, f=0.3):
    z = {}
    if atlas:
        z["ATLAS"] = {"usd": atlas, "f": f}
    if blitz:
        z["BLITZ"] = {"usd": blitz, "f": f}
    return z


L, LA, LB, LAB = ("LIT",), ("LIT", "ATLAS"), ("LIT", "BLITZ"), ("LIT", "ATLAS", "BLITZ")
MIXES = {                                           # name -> (strategies in the eval, strategies funded, sizing of the added ones)
    "LIT alone": (L, L, {}),
    "LIT + ATLAS $250": (LA, LA, Z(atlas=250)),
    "LIT + ATLAS $500": (LA, LA, Z(atlas=500)),
    "LIT + BLITZ $150": (LB, LB, Z(blitz=150)),
    "LIT + BLITZ $300": (LB, LB, Z(blitz=300)),
    "LIT + ATLAS $250 + BLITZ $150": (LAB, LAB, Z(atlas=250, blitz=150)),
    "LIT + ATLAS $500 + BLITZ $300": (LAB, LAB, Z(atlas=500, blitz=300)),
    "LIT eval; funded + ATLAS $500": (L, LA, Z(atlas=500)),
    "LIT eval; funded + ATLAS $500 + BLITZ $300": (L, LAB, Z(atlas=500, blitz=300)),
}
RAPID_MIXES = ("LIT alone", "LIT + ATLAS $250", "LIT + ATLAS $500", "LIT + ATLAS $250 + BLITZ $150", "LIT + ATLAS $500 + BLITZ $300",
               "LIT eval; funded + ATLAS $500")


def score_mix(name, kind, PE, PF, log=print):
    se, sf, z = MIXES[name]
    spec = plan(kind, z)
    BYe = mix_by(se)
    BYf = mix_by(sf, news=bool(spec.get("news")))
    S = data()["S"]
    usd = {"LIT": 500.0, "ATLAS": (z.get("ATLAS") or {}).get("usd", 0.0), "BLITZ": (z.get("BLITZ") or {}).get("usd", 0.0)}
    o = {}
    for sp in SPANS:
        t0 = time.time()
        r = {"plain": plain_stats(mix_by(sf), S, sp, usd), "eval": eval_stats(BYe, PE[sp], spec), "funded": funded_stats(BYf, PF[sp], spec)}
        sl = A4.slot_stats(run_slots(BYe, BYf, PF[sp], spec))
        r["slot"] = {k: sl[k] for k in ("net_m", "owner_m", "fees_6m", "p_neg", "p_no_pay", "evals", "first_pay_med", "pays")}
        o[sp] = r
        log(f"  {kind:9s} {name:32s} {sp:3s} {line(r)}  ({time.time() - t0:.0f}s)")
    return o


def line(r):
    p, e, f, s = r["plain"], r["eval"], r["funded"], r["slot"]
    return (f"{p['tpw']:.1f}/wk PF {p['pf']} ${p['per_month']:,}/mo dd ${p['max_dd']:,} | eval med {e['pass_med']} "
            f"2wk {e['p10']}/{e['f10']} | funded 1st {f['first_med']} nopay {round(100 - f['any_pay'], 1)}% lost {f['lost_6m']}% "
            f"${f['per_month']}/mo | "
            f"slot ${s['net_m']}/mo 1st {s['first_pay_med']}")


def study(n=1000, log=print):
    S = data()["S"]
    PE = {sp: U.mc_paths(S, sp, 2 * n, length=H_EVAL, seed=A4.SEED_EVAL) for sp in SPANS}
    PF = {sp: U.mc_paths(S, sp, n, length=LEN, seed=A4.SEED_LIFE) for sp in SPANS}
    out = {"date": "2026-11-16", "n": n, "spans": U.SPAN, "builder": {}, "rapid_eod": {}}
    for name in MIXES:
        out["builder"][name] = score_mix(name, "builder", PE, PF, log)
    for name in RAPID_MIXES:
        out["rapid_eod"][name] = score_mix(name, "rapid_eod", PE, PF, log)
    out["verdict"] = verdict(out)
    return out


def verdict(out):
    """Three checks against LIT alone in EACH 2026 half: the 6-month slot pays more a month after fees, the funded first payout
    comes no later, the eval fails no more often in 2 weeks (+0.5 point of Monte Carlo noise). A mix "beats LIT alone" only when
    all three hold in both halves; 2021-25 is shown, not required (LIT has no edge there)."""
    v = {}
    for kind in ("builder", "rapid_eod"):
        base = out[kind]["LIT alone"]
        for name, r in out[kind].items():
            if name == "LIT alone":
                continue
            chk = {}
            for sp in ("H1", "H2"):
                a, b = r[sp], base[sp]
                chk[sp] = {"more_money": a["slot"]["net_m"] > b["slot"]["net_m"],
                           "payout_no_later": (a["funded"]["first_med"] or 999) <= (b["funded"]["first_med"] or 999),
                           "no_more_2wk_fails": a["eval"]["f10"] <= b["eval"]["f10"] + 0.5}
            ok = all(all(c.values()) for c in chk.values())
            v[f"{kind}: {name}"] = {"beats_lit_alone_both_halves": ok, "checks": chk}
    return v


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.time()
    out = study(a.n)
    for k, x in out["verdict"].items():
        bad = [f"{sp} {c}" for sp, cc in x["checks"].items() for c, ok in cc.items() if not ok]
        print(f"{k:58s} {'BEATS LIT alone' if x['beats_lit_alone_both_halves'] else 'no: ' + ', '.join(bad)}")
    if not a.no_save:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print("wrote", os.path.relpath(OUT, ROOT))
    print(f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
