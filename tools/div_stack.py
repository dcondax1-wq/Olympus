"""The diversifier on prop accounts (2026-10-26, research/writeups/diversifier-search.md): the noise-area momentum strategy
of tools/div_search.py (joint pick na_vm125_1000_n99_fixed, "NA") on MFFU evals and funded accounts, alone and next to
LIT (Zlarior), and a copied 7-account funded stack with the odds of months with no payout. Paper research only.

Engines: tools/uprisk.py (its Eval / Funded are checked bit for bit against engine/sizing + engine/funded_life; the MFFU
Builder rules; LIT units = the 120 live 2026 trades of run lit_live + the 511 2021-25 reference rows, $1.90 a micro). NA
units = tools/div_search.run (5m CME NQ1!, 1 tick in on entry / stop / EOD exits); the NA micros are sized here:
    q = floor(min(f x room, cap, soft-daily-loss left) / ((stop + 2 ticks) x $2 + $1.90)), max the plan's micros, 0 = skip
(size follows the stop; f = share of the room to the floor risked on one NA trade). LIT keeps its live sizing (eval:
two_week room_f 0.8, no weekly stop; funded: 60% of the room, <= $1,500, winner <= $2,000; 25K at half scale).
On one account LIT's trades come first each day (95 of 120 enter 02:00-08:00) and NA's after (10:00-15:55); a LIT trade
still open after 10:00 is not modelled as overlapping (sequential approximation).

Monte Carlo: 1,000 paths of sessions drawn in blocks from the half (5-session blocks as tools/uprisk.py, seed 23; 21-session
blocks as the dry-spell check, because a 5-session block breaks long cold stretches apart). Spans: 2026 H1 (Jan-Jun), H2
(Jul-Oct, the check), 2025, 2021-24; LIT's 2021-25 rows are 5m-only (reference).

    python -X utf8 tools/div_stack.py solo      # NA alone: eval (50K / 25K) and funded grids
    python -X utf8 tools/div_stack.py mix       # LIT + NA on one funded account
    python -X utf8 tools/div_stack.py stack     # 7-account stacks: $/month net of evals + months with no payout
    python -X utf8 tools/div_stack.py all       # -> research/second/div_stack.json
"""
from __future__ import annotations

import collections
import copy
import datetime as dt
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import uprisk as U  # noqa: E402
import div_search as DS  # noqa: E402
from engine.lit import qty_for  # noqa: E402
from engine import sizing as SZ  # noqa: E402

OUT = os.path.join(ROOT, "research", "second", "div_stack.json")
PV, COMM, SLIP = 2.0, 1.90, 0.25
NA_ID = "na_vm125_1000_n99_fixed"
U.SPAN.update({"2025": ("2025-01-01", "2025-12-31"), "2021-24": ("2021-11-01", "2024-12-31")})
SPANS = ("H1", "H2", "2025", "2021-24")
PRICE = {"builder50k": 91.80, "builder25k": 63.00}
LIT_E50 = U.ecfg_of({})                                   # live: two_week room_f 0.8, no eval weekly stop (live_model.json)
LIT_E25 = U.ecfg_of({}, plan="builder25k")
LIT_F50, LIT_F25 = U.UP50, U.UP25                         # live funded sizing (60% room, <= $1,500, winner <= $2,000)


# ================================================================================================ units
def na_units(cid=NA_ID):
    G = dict(DS.na_grid())
    B = DS.D()
    by = collections.defaultdict(list)
    for w in DS.run(G[cid]):
        day = B.days[w["k"]]
        by[day].append({"day": day, "src": "na", "risk": float(w["risk"]), "risk_pts": float(w["risk"]), "tgt": None, "tgt_pts": None,
                        "pts": float(w["pts"]), "w1": float(min(0.0, w["mae"])), "size_mult": 1.0, "et": int(B.t[w["k"], w["j"] + 1]),
                        "xt": int(B.t[w["k"], w["exit_j"]]) + (0 if w["exit"] == "EOD" else 300)})
    return by


def lit_windows():
    """day -> [(entry epoch, exit epoch)] of every LIT trade (research/handoff/2026-10-25/COMPLETE_TRADE_LEDGER.csv; 2021-25
    exits are 5m bar ends)."""
    import csv
    out = collections.defaultdict(list)
    with open(os.path.join(U.HO, "COMPLETE_TRADE_LEDGER.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            e = dt.datetime.fromisoformat(r["entry_fill_at"][:25]).timestamp()
            x = dt.datetime.fromisoformat(r["exit_time"][:25]).timestamp()
            out[r["entry_fill_at"][:10]].append((int(e), int(x)))
    return out


def mixed(BYL, BYN, S, rule="no_overlap"):
    """One account's day: LIT's trades, then NA's. rule "no_overlap" (default, the account-B rule of the PC route: one
    position, LIT first): an NA trade is dropped when its time in the market overlaps a LIT trade (NA would be blocked
    while LIT holds, or closed when LIT enters); "none" = the sequential approximation."""
    if rule == "none":
        return [BYL[i] + BYN[i] for i in range(len(S))]
    W = lit_windows()
    out = []
    for i, d in enumerate(S):
        iv = W.get(d, [])
        keep = [t for t in BYN[i] if not any(t["et"] < x and e < t["xt"] for e, x in iv)]
        out.append(BYL[i] + keep)
    return out


_L = {}


def load(cid=NA_ID):
    if cid not in _L:
        S, BYL = U.load()
        for x in BYL:
            for t in x:
                t["src"] = "lit"
        NA = na_units(cid)
        BYN = [NA.get(d, []) for d in S]
        _L[cid] = (S, BYL, BYN, mixed(BYL, BYN, S))
    return _L[cid]


def paths(S, span, n=U.N_MC, length=U.LEN, seed=23, block=5):
    a, z = U.span_ix(S, span)
    rng = np.random.default_rng(seed)
    P = []
    for _ in range(n):
        s = []
        while len(s) < length:
            b = int(rng.integers(a, z - block + 1))
            s.extend(range(b, b + block))
        P.append(s[:length])
    return P


# ================================================================================================ sizing of an NA trade
def na_q(t, room, nc, maxq, dll_left=None):
    usd = min(float(nc["f"]) * max(0.0, room), float(nc["cap"]))
    if dll_left is not None:
        usd = min(usd, max(0.0, dll_left))
    loss1 = (t["risk"] + SLIP * 2) * PV + COMM
    return max(0, min(int(maxq), int(usd / loss1 + 1e-9)))


# ================================================================================================ accounts
class Eval(U.Eval):
    """uprisk.Eval with an NA dispatch: lit = LIT's live eval sizing on (True) / off; nc = the NA rule (None = no NA)."""

    def __init__(self, cfg, plan="builder50k", nc=None, lit=True):
        super().__init__(cfg, plan)
        self.nc, self.lit = nc, lit

    def step(self, ts):
        c, E = self.cfg, self.E
        self.s += 1
        wkey = (self.s - 1) // 5
        cum = 0.0
        sub = {k: v for k, v in c.items() if not k.startswith("_")}
        traded = False
        for t in ts:
            if cum <= -E["dll"]:
                break
            room = self.bal + cum - self.floor
            if t.get("src") == "na":
                if not self.nc:
                    continue
                q = na_q(t, room, self.nc, c["_maxq"], E["dll"] + cum)
            else:
                if not self.lit:
                    continue
                m0 = qty_for(t["risk"])
                if self.sc != 1.0:
                    m0 = max(1, int(m0 * self.sc)) if m0 else 0
                if not m0:
                    continue
                st = {"profit": self.bal, "cum": cum, "room": room, "session": self.s, "n_today": 0,
                      "wk_pnl": self.wk.get(wkey, 0.0), "days_traded": self.dtr}
                q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, sub, room=st["room"],
                               state=st, learning=None, max_micros=c["_maxq"])["qty"]
                q = min(q, c["_maxq"])
            if q <= 0:
                continue
            traded = True
            pnl = t["pts"] * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            self.max_risk = max(self.max_risk, (t["risk"] + SLIP) * PV * q + COMM * q)
            if cum + low <= -E["dll"]:
                pnl = -E["dll"] - cum - SLIP * PV * q
                low = pnl
            if self.bal + cum + low <= self.floor:
                return "fail"
            cum += pnl
        self.bal += cum
        self.wk[wkey] = self.wk.get(wkey, 0.0) + cum
        self.dtr += 1 if traded else 0
        if self.bal <= self.floor:
            return "fail"
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - E["mll"]), E["lock"])
        if self.bal >= E["tgt"]:
            return "pass"
        if self.bal - self.floor < c["_stuck"]:
            return "stuck"
        if c["_reset"] and self.s >= c["_reset"]:
            return "reset"
        return None


class Funded(U.Funded):
    """uprisk.Funded with an NA dispatch (lit = False: NA only)."""

    def __init__(self, plan, cfg, nc=None, lit=True, ask=None):
        super().__init__(plan, cfg, ask)
        self.nc, self.lit = nc, lit

    def qty(self, t, st):
        if t.get("src") == "na":
            if not self.nc:
                return 0
            return na_q(t, st["room"], self.nc, self.A["max_micros"], float(self.A["dll"]) + st["cum"])
        if not self.lit:
            return 0
        return super().qty(t, st)


# ================================================================================================ studies
def eval_mc(BY, P, mk, price, horizon=60):
    R = []
    for seq in P:
        e = mk()
        out, used = "open", len(seq[:horizon])
        for k, si in enumerate(seq[:horizon]):
            r = e.step(BY[si])
            if r:
                out, used = r, k + 1
                break
        R.append((out, used, e.max_risk))
    n = len(R)
    pas = [u for o, u, _ in R if o == "pass"]
    pev = 100.0 * len(pas) / n
    return {"p10": round(100.0 * sum(1 for u in pas if u <= 10) / n, 1),
            "f10": round(100.0 * sum(1 for o, u, _ in R if o in ("fail", "stuck", "reset") and u <= 10) / n, 1),
            "p15": round(100.0 * sum(1 for u in pas if u <= 15) / n, 1),
            "p_ever": round(pev, 1), "fail_ever": round(100.0 * sum(1 for o, _, _ in R if o in ("fail", "stuck")) / n, 1),
            "pass_med": float(np.median(pas)) if pas else None,
            "slow_pass": round(100.0 * sum(1 for u in pas if u > 15) / max(1, len(pas)), 1),
            "usd_per_pass": round(price / max(1e-9, pev / 100.0), 1), "max_risk": round(max(r[2] for r in R))}


def funded_mc(BY, P, mk, plan, horizon=U.LEN):
    R = []
    for seq in P:
        f = mk()
        pay_at, lost = [], None
        for k, si in enumerate(seq[:horizon]):
            ev, x = f.step(BY[si])
            if ev in ("paid", "grad"):
                pay_at.append((k + 1, x))
            if ev == "lost":
                lost = k + 1
                break
            if ev == "grad":
                break
        R.append({"f": f, "pay_at": pay_at, "lost": lost})
    n = len(R)
    paid = np.array([sum(x for _, x in r["pay_at"]) for r in R])
    fr = [r["pay_at"][0][0] for r in R if r["pay_at"]]
    mo = horizon / 21.0
    months = [[sum(x for k, x in r["pay_at"] if m * 21 < k <= (m + 1) * 21) for m in range(int(mo))] for r in R]
    return {"per_month": round(float(paid.mean()) / mo), "paid_p10": round(float(np.percentile(paid, 10))),
            "loss_6m": round(100.0 * sum(1 for r in R if r["lost"]) / n, 1), "first_med": float(np.median(fr)) if fr else None,
            "any_pay": round(100.0 * len(fr) / n, 1), "payouts": round(float(np.mean([len(r["pay_at"]) for r in R])), 2),
            "trade_pnl_m": round(float(np.mean([r["f"].trade_pnl for r in R])) / mo),
            "hold_cons": round(float(np.mean([r["f"].hold["cons"] for r in R])), 1),
            "months_paying": round(float(np.mean([sum(1 for v in m if v > 0) for m in months])), 2),
            "max_risk": round(max(r["f"].max_risk for r in R)), "trades_6m": round(float(np.mean([r["f"].n_tr for r in R])), 1)}


def life(BY, seqs, mk_eval, mk_funded, price, horizon, gap=U.GAP):
    """One account slot (uprisk.life with factories), keeping every payout's session."""
    R = []
    for seq in seqs:
        cost, owner, evals, funded_n, losts = price, 0.0, 1, 0, 0
        e, f, wait = mk_eval(), None, 0
        pays = []
        for k, si in enumerate(seq[:horizon]):
            if f is None and wait == 0:
                r = e.step(BY[si])
                if r == "pass":
                    wait = gap
                    funded_n += 1
                elif r in ("fail", "stuck", "reset"):
                    cost += price
                    evals += 1
                    e = mk_eval()
            elif f is None:
                wait -= 1
                if wait == 0:
                    f = mk_funded()
            else:
                ev, x = f.step(BY[si])
                if ev in ("paid", "grad"):
                    owner += x
                    pays.append((k + 1, x))
                if ev in ("lost", "grad"):
                    losts += ev == "lost"
                    f = None
                    cost += price
                    evals += 1
                    e = mk_eval()
        R.append({"owner": owner, "cost": cost, "net": owner - cost, "evals": evals, "funded": funded_n, "lost": losts, "pays": pays})
    return R


def book(S, span, slots, n=U.N_MC, offset=5, horizon=252, block=5, seed=23):
    """slots = [(label, BY, mk_eval, mk_funded, price)], slot j bought offset*j sessions after slot 0, all on the SAME market
    path. -> $ a month net of every eval, P(loss), and the dry spells of the whole stack (no payout from any account)."""
    L = horizon + offset * (len(slots) - 1)
    P = paths(S, span, n, length=L, seed=seed, block=block)
    per = []
    for j, (_, BY, me, mf, price) in enumerate(slots):
        sub = [seq[offset * j: offset * j + horizon] for seq in P]
        R = life(BY, sub, me, mf, price, horizon)
        for r in R:                                    # payout sessions on the stack clock (slot j started offset*j later)
            r["pays"] = [(k + offset * j, x) for k, x in r["pays"]]
        per.append(R)
    M = horizon // 21
    net = np.array([sum(per[j][i]["net"] for j in range(len(slots))) for i in range(n)])
    pm = np.zeros((n, M))
    for i in range(n):
        for j in range(len(slots)):
            for k, x in per[j][i]["pays"]:
                m = (k - 1) // 21                   # calendar months of the stack clock; later payouts are outside
                if m < M:
                    pm[i, m] += x
    zero = pm <= 0
    dry456 = float(np.mean(zero[:, 3:6].all(axis=1)))
    dry3 = []
    for i in range(n):
        z = zero[i, 3:]
        dry3.append(any(z[a:a + 3].all() for a in range(max(0, len(z) - 2))))
    last = zero[:, 3:]
    longest = []
    for i in range(n):
        b = c = 0
        for v in last[i]:
            c = c + 1 if v else 0
            b = max(b, c)
        longest.append(b)
    mo = horizon / 21.0
    return {"slots": [s[0] for s in slots], "net_m": round(float(net.mean()) / mo), "net_p10_m": round(float(np.percentile(net, 10)) / mo),
            "p_neg": round(100.0 * float((net < 0).mean()), 1),
            "dry_m4_6": round(100.0 * dry456, 1), "dry3_after_m3": round(100.0 * float(np.mean(dry3)), 1),
            "zero_months_after_m3": round(100.0 * float(last.mean()), 1), "longest_dry_mean": round(float(np.mean(longest)), 2),
            "month_p10_after_m3": round(float(np.percentile(pm[:, 3:], 10))),
            "evals": round(float(np.mean([sum(per[j][i]["evals"] for j in range(len(slots))) for i in range(n)])), 2),
            "lost": round(float(np.mean([sum(per[j][i]["lost"] for j in range(len(slots))) for i in range(n)])), 2),
            "eval_cost_m": round(float(np.mean([sum(per[j][i]["cost"] for j in range(len(slots))) for i in range(n)])) / mo)}


# ================================================================================================ grids
def nc(f, cap, plan="builder50k"):
    k = 1.0 if plan == "builder50k" else 0.5
    return {"f": f, "cap": cap * k}


def run_solo(n, out):
    S, BYL, BYN, BYM = load()
    res = {"eval": {}, "funded": {}}
    for plan in ("builder50k", "builder25k"):
        ecfg = LIT_E50 if plan == "builder50k" else LIT_E25
        fl = LIT_F50 if plan == "builder50k" else LIT_F25
        PE = {sp: paths(S, sp, n, length=60) for sp in SPANS}
        PF = {sp: paths(S, sp, n) for sp in SPANS}
        rows = {"lit_live": {sp: eval_mc(BYL, PE[sp], lambda: Eval(ecfg, plan), PRICE[plan]) for sp in SPANS}}
        for f in (0.05, 0.1, 0.15, 0.2, 0.3, 0.4):
            c = nc(f, 2000, plan)
            rows[f"na_f{int(f * 100)}"] = {sp: eval_mc(BYN, PE[sp], lambda: Eval(ecfg, plan, nc=c, lit=False), PRICE[plan]) for sp in SPANS}
        res["eval"][plan] = rows
        for k, r in rows.items():
            print(f"eval {plan} {k:10s} " + " | ".join(f"{sp} p10 {r[sp]['p10']:>5} f10 {r[sp]['f10']:>5} ever {r[sp]['p_ever']:>5} med {r[sp]['pass_med']}"
                                                         for sp in SPANS), flush=True)
        frows = {"lit_live": {sp: funded_mc(BYL, PF[sp], lambda: Funded(plan, fl), plan) for sp in SPANS}}
        for f, cap in ((0.05, 300), (0.1, 300), (0.1, 500), (0.15, 500), (0.2, 750), (0.3, 1000)):
            c = nc(f, cap, plan)
            frows[f"na_f{int(f * 100)}_c{cap}"] = {sp: funded_mc(BYN, PF[sp], lambda: Funded(plan, fl, nc=c, lit=False), plan) for sp in SPANS}
        res["funded"][plan] = frows
        for k, r in frows.items():
            print(f"funded {plan} {k:14s} " + " | ".join(f"{sp} ${r[sp]['per_month']:>5}/mo lost {r[sp]['loss_6m']:>5}% first {r[sp]['first_med']}"
                                                           for sp in SPANS), flush=True)
    out["solo"] = res


def run_mix(n, out):
    S, BYL, BYN, BYM = load()
    res = {}
    for plan in ("builder50k", "builder25k"):
        fl = LIT_F50 if plan == "builder50k" else LIT_F25
        PF = {sp: paths(S, sp, n) for sp in SPANS}
        rows = {"lit_only": {sp: funded_mc(BYL, PF[sp], lambda: Funded(plan, fl), plan) for sp in SPANS}}
        for f, cap in ((0.02, 100), (0.03, 100), (0.03, 150), (0.03, 200), (0.04, 150), (0.05, 250), (0.05, 400), (0.1, 400)):
            c = nc(f, cap, plan)
            rows[f"lit+na_f{int(f * 100)}_c{cap}"] = {sp: funded_mc(BYM, PF[sp], lambda: Funded(plan, fl, nc=c), plan) for sp in SPANS}
        res[plan] = rows
        for k, r in rows.items():
            print(f"mix {plan} {k:18s} " + " | ".join(f"{sp} ${r[sp]['per_month']:>5}/mo lost {r[sp]['loss_6m']:>4}% first {r[sp]['first_med']} "
                                                       f"pays {r[sp]['payouts']} mo+ {r[sp]['months_paying']} cons {r[sp]['hold_cons']}"
                                                       for sp in SPANS), flush=True)
    out["mix"] = res


def stacks(BYL, BYN, BYM, na_e, na_f, mix_nc):
    """The owner's plan: ~7 funded accounts at 3 firms. MFFU = 1 x Builder 50K + 2 x Builder 25K (its per-person limit, exact
    rules); LucidPro / FundedNext 50Ks = 4 x '50K-type' (MFFU 50K rules as the proxy, as in uprisk.md)."""
    def L50():
        return ("LIT 50K", BYL, lambda: Eval(LIT_E50), lambda: Funded("builder50k", LIT_F50), PRICE["builder50k"])

    def L25():
        return ("LIT 25K", BYL, lambda: Eval(LIT_E25, "builder25k"), lambda: Funded("builder25k", LIT_F25), PRICE["builder25k"])

    def M50():
        c = nc(*mix_nc)
        return ("LIT+NA 50K", BYM, lambda: Eval(LIT_E50), lambda: Funded("builder50k", LIT_F50, nc=c), PRICE["builder50k"])

    def M25():
        c = nc(*mix_nc, plan="builder25k")
        return ("LIT+NA 25K", BYM, lambda: Eval(LIT_E25, "builder25k"), lambda: Funded("builder25k", LIT_F25, nc=c), PRICE["builder25k"])

    def N50():
        ce, cf = nc(*na_e), nc(*na_f)
        return ("NA 50K", BYN, lambda: Eval(LIT_E50, nc=ce, lit=False), lambda: Funded("builder50k", LIT_F50, nc=cf, lit=False),
                PRICE["builder50k"])

    def N25():
        ce, cf = nc(*na_e, plan="builder25k"), nc(*na_f, plan="builder25k")
        return ("NA 25K", BYN, lambda: Eval(LIT_E25, "builder25k", nc=ce, lit=False),
                lambda: Funded("builder25k", LIT_F25, nc=cf, lit=False), PRICE["builder25k"])
    return {
        "A_7lit": [L50(), L25(), L25(), L50(), L50(), L50(), L50()],
        "B_7mix": [M50(), M25(), M25(), M50(), M50(), M50(), M50()],
        "C_5lit_2na": [L50(), L25(), L25(), L50(), L50(), N50(), N50()],
        "E_3lit_4mix": [L50(), M25(), M25(), L50(), M50(), M50(), L50()],
    }


def run_stack(n, out, na_e=(0.2, 2000), na_f=(0.1, 300), mix_nc=(0.03, 150)):
    S, BYL, BYN, BYM = load()
    res = {}
    for block in (5, 21):
        for name, slots in stacks(BYL, BYN, BYM, na_e, na_f, mix_nc).items():
            row = {sp: book(S, sp, slots, n, block=block) for sp in SPANS}
            res[f"{name}__b{block}"] = row
            print(f"stack b{block:<2} {name:12s} " + " | ".join(
                f"{sp} ${row[sp]['net_m']:>6}/mo p10 ${row[sp]['net_p10_m']:>6} dry4-6 {row[sp]['dry_m4_6']:>5}% dry3 {row[sp]['dry3_after_m3']:>5}% "
                f"zero-mo {row[sp]['zero_months_after_m3']:>5}%" for sp in SPANS), flush=True)
    out["stack"] = {"rows": res, "na_eval": na_e, "na_funded": na_f, "mix": mix_nc}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    what = args[0] if args else "all"
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else U.N_MC
    out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    out.update(built=dt.date.today().isoformat(), n=n, na=NA_ID)
    for w, fn in (("solo", run_solo), ("mix", run_mix), ("stack", run_stack)):
        if what in (w, "all"):
            fn(n, out)
            json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print("->", OUT)


if __name__ == "__main__":
    main()
