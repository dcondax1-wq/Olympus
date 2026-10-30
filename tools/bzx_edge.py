"""BLITZ edge, round 2 (owner 2026-10-30 12:30 ET: "make BLITZ way better: good rules, good strategy, good discretion").
Research only; nothing here is imported by the engine. research/writeups/blitz-edge-2026-10-30b.md, runs bzx_*.

Same trades as today (tools/blitz25k_lib.trades(today's rule, "lit+atlas") = engine/blitz.py v2 as account C, costs in,
2026 1m pick on H1 / check on H2, 2021-25 5m reference). New here:
  FundedX   scalp_na_lib.Funded (MFFU Builder 25K sim-funded) + knobs: size before / after the trailing floor locks at
            start + $100 ("buffer first"), integer-micro later-break size (first break q1, later break q2), funded day loss /
            losing-trade / week stops, payout ask amount and wait, the abandon ("stuck") line
  EvalX     blitz25k_size.Eval + "first winner ends the day" on eval sessions 1..s, the later-break multiplier (t["mult"])
  lifeX     blitz25k_size.life_hybrid with EvalX / FundedX (same Monte Carlo paths: 6 months, 5-session blocks, seed 23)
With every knob off FundedX / EvalX / lifeX = scalp_na_lib.Funded / blitz25k_size.Eval / life_hybrid (`selfcheck`).

    python -X utf8 tools/bzx_edge.py selfcheck
    python -X utf8 tools/bzx_edge.py funded     # direction 1 grid -> research/scalp/bzx_funded.json
    python -X utf8 tools/bzx_edge.py evalx      # direction 2 -> research/scalp/bzx_eval.json
    python -X utf8 tools/bzx_edge.py signals    # direction 3 -> research/scalp/bzx_signals.json
"""
from __future__ import annotations

import collections
import datetime as dt
import itertools
import json
import os
import sys
import time
import warnings

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
warnings.filterwarnings("ignore")
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from tools import ab_edge as A  # noqa: E402

N, K, BS = A.blitz_libs()
A.install_safe_qty()             # "fmax" (f x mult <= the room) for the later-break eval size
OUT = os.path.join(ROOT, "research", "scalp")
PLAN = "25k"
EZ0 = dict(A.PICK_EZ)                                                                   # today's eval size (account_c "speed")
FZ0 = dict(A.PICK_FZ)                                                                   # today's funded size
EZ_LB = {"mode": "frac", "f": 0.4, "cap": 600.0, "push": (5, 1.0), "fmax": 1.0}         # blitz_25k_pick_v2 eval size (+ mult)
LB = (1.75, 0.5)                                                                        # later x / first x
PROCS = 2


def week_of(d):
    return dt.date.fromisoformat(d).isocalendar()[:2]


def is_later(t):
    return t.get("f", {}).get("nth", 1.0) >= 2


# ================================================================================================ funded with knobs
class FundedX(N.Funded):
    """N.Funded + knobs in the size dict fz (absent = today's behaviour):
      f2, cap2      the room share / $ cap once the trailing floor has locked at start + $100 (peak >= $1,100)
      q1, q2        integer micros on a first / later band break (q1 0 = skip first breaks), capped so the trade risks at
                    most rq x room (default 0.5) and 0.9 x the soft daily loss left; q1b / q2b = the same after the lock
      dloss         no new trade once the day is down $X;  nloss: after n losing trades in a day;  wloss: the week down $X
      maxday        at most n trades a day
      ask_max       payout request cap ($250-1,000 MFFU);  ask_wait: request only once balance - buffer >= $X
      r1            skip a 1-micro trade whose stop-out is more than r1 x the room (near the floor: only small stops)
      stuck_k       the abandon line in x the median stop-out (today 2.0; 0 = never abandon, trade until lost)"""

    def __init__(self, plan, sz, stuck, med_risk=None):
        super().__init__(plan, sz, stuck)
        if sz.get("stuck_k") is not None and med_risk is not None:
            self.stuck = float(sz["stuck_k"]) * med_risk
        self.wk, self.wk_pnl = None, 0.0

    def locked(self):
        return self.floor >= self.F["lock"] - 1e-9

    def qty(self, t, room, dp):
        sz, F = self.sz, self.F
        lk = self.locked()
        dll_left = F["dll"] + dp
        if "q1" in sz:
            q = (sz.get("q2b", sz["q2"]) if lk else sz["q2"]) if is_later(t) else (sz.get("q1b", sz["q1"]) if lk else sz["q1"])
            if q <= 0:
                return 0
            lim = min(float(sz.get("rq", 0.5)) * room, 0.9 * dll_left)
            while q > 1 and q * t["risk_pm"] > lim:
                q -= 1
            if q == 1 and t["risk_pm"] > min(0.5 * room, 0.9 * dll_left):
                return 0
            return int(min(q, F["maxq"]))
        z = sz
        if lk and "f2" in sz:
            z = {**sz, "f": sz["f2"], "cap": sz.get("cap2", sz["cap"])}
        q = N.qty(t, room, dp, self.bal, self.P, {**z, "mode": "frac" if z.get("mode") == "need" else z.get("mode", "frac")})
        if q == 1 and sz.get("r1") is not None and t["risk_pm"] > float(sz["r1"]) * room:
            return 0                                   # near the floor: skip a 1-micro trade whose stop is > r1 x the room
        return q

    def step(self, ts, day=None):
        F, sz = self.F, self.sz
        self.k += 1
        dp = 0.0
        traded = False
        tp, dl, nl, md, wl = sz.get("day_tp"), sz.get("dloss"), sz.get("nloss"), sz.get("maxday"), sz.get("wloss")
        if day is not None and wl is not None:
            w = week_of(day)
            if w != self.wk:
                self.wk, self.wk_pnl = w, 0.0
        nlos = ntr = 0
        for t in ts:
            if tp is not None and dp >= tp:
                break
            if (dl is not None and dp <= -dl) or (nl is not None and nlos >= nl) or (md is not None and ntr >= md):
                break
            if wl is not None and self.wk_pnl + dp <= -wl:
                break
            q = self.qty(t, self.bal + dp - self.floor, dp)
            if q <= 0:
                continue
            pnl, low = N.trade_pnl(t, q)
            if self.bal + dp + low <= self.floor:
                self.done = "lost"
                return 0.0
            dp += pnl
            traded = True
            ntr += 1
            nlos += pnl < 0
            if dp <= -F["dll"]:
                break
        self.bal += dp
        self.wk_pnl += dp
        if self.bal <= self.floor:
            self.done = "lost"
            return 0.0
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - F["mll"]), F["lock"])
        if self.bal - self.floor < self.stuck:
            self.done = "stuck"
            return 0.0
        if traded:
            self.cyc.append(dp)
        if self.k < F["first_wait"] or len(self.cyc) < F["cycle_days"]:
            return 0.0
        prof = self.bal - self.last_bal
        if prof <= 0 or max(self.cyc) > F["cons"] * prof:
            return 0.0
        exc = self.bal - F["buffer"]
        if exc < float(sz.get("ask_wait", 0.0)):
            return 0.0
        amt = min(exc, F["pay_max"], float(sz.get("ask_max", F["pay_max"])))
        if amt < F["pay_min"]:
            return 0.0
        self.n_pay += 1
        self.bal -= amt
        self.last_bal, self.cyc = self.bal, []
        if self.n_pay >= F["max_payouts"]:
            self.done = "max"
        return amt * F["split"]


# ================================================================================================ eval with knobs
class EvalX(BS.Eval):
    """blitz25k_size.Eval + ez knobs: win_stop (s): on eval sessions 1..s the first winning trade ends the day;
    loss2_stop: after 2 losing trades the day ends; first_skip_s (s): on sessions 1..s first breaks are skipped."""

    def step(self, ts, keep=None):
        z0 = self.sz
        ws, fs = z0.get("win_stop"), z0.get("first_skip_s")
        if not ws and not fs and not z0.get("loss2_stop"):
            return super().step(ts, keep)
        P = self.P
        self.s += 1
        z = self.size()
        dp, n, nl = 0.0, 0, 0
        dl, md, tp = z.get("day_loss"), z.get("maxday"), z.get("day_tp")
        for t in ts:
            if (tp is not None and dp >= tp) or (dl is not None and dp <= -dl) or (md is not None and n >= md):
                break
            if z0.get("loss2_stop") and nl >= 2:
                break
            if fs and self.s <= fs and not is_later(t):
                continue
            q = K.qty(t, self.bal + dp - self.floor, dp, self.bal, P, z)
            if q <= 0:
                continue
            pnl, low = N.trade_pnl(t, q)
            n += 1
            if self.bal + dp + low <= self.floor:
                if keep is not None:
                    keep.append({**t, "qty": q, "pnl": round(self.floor - self.bal - dp, 2)})
                return "fail"
            dp += pnl
            nl += pnl < 0
            if keep is not None:
                keep.append({**t, "qty": q, "pnl": round(pnl, 2)})
            if self.bal + dp >= P["target"]:
                return "pass"
            if dp <= -P["dll"]:
                break
            if ws and self.s <= ws and pnl > 0:
                break
        self.bal += dp
        if self.bal <= self.floor:
            return "fail"
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - P["mll"]), P["lock"])
        if self.bal - self.floor < self.stuck:
            return "stuck"
        return None


def run_evalx(days, by, sz, horizon=20, stuck=60.0, keep=None):
    E = EvalX(sz, stuck)
    for k, d in enumerate(days[:horizon]):
        r = E.step(by.get(d, ()), keep)
        if r == "pass":
            return "PASS", k + 1
        if r in ("fail", "stuck"):
            return ("FAIL" if r == "fail" else "STUCK"), k + 1
    return "OPEN", min(len(days), horizon)


def eval_scorex(T, S, sz):
    """blitz25k_size.eval_score with EvalX (p10 / f10 / dec10 / p15 / f15 / p20 / f20 / pass_med / slow_pass)."""
    by, stuck = BS._by(T), BS._stuck(T)
    res = [(run_evalx(S[i:i + 20], by, sz, stuck=stuck), len(S) - i) for i in range(len(S))]
    o = {}
    for H in (10, 15, 20):
        R = [r for r, av in res if av >= H]
        n = len(R) or 1
        o[f"p{H}"] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= H) / n, 1)
        o[f"f{H}"] = round(100.0 * sum(1 for r in R if r[0] in ("FAIL", "STUCK") and r[1] <= H) / n, 1)
    o["dec10"] = round(o["p10"] + o["f10"], 1)
    pas = [r[1] for r, _ in res if r[0] == "PASS"]
    o["pass_med"] = float(np.median(pas)) if pas else None
    o["slow_pass"] = round(100.0 * sum(1 for x in pas if x > 15) / len(pas), 1) if pas else None
    return o


# ================================================================================================ the slot
def lifeX(Te, Tf, S, ez, fz, n=1000, length=126, gap=2, seed=23, plan=PLAN):
    """blitz25k_size.life_hybrid with EvalX / FundedX + why funded accounts end (stuck / lost / 5 payouts / still open)
    and payouts per 6 months."""
    be, bf, se, sf = BS._by(Te), BS._by(Tf), BS._stuck(Te), BS._stuck(Tf)
    med = sf / 2.0
    price = N.PLANS[plan]["price"]
    nets, funded_n, pays, ends = [], [], [], collections.Counter()
    for seq in N.mc_paths(S, n, length, seed=seed):
        cash, nf, wait, acc, npay = -price, 0, 0, EvalX(ez, se, plan), 0
        for d in seq:
            if wait:
                wait -= 1
                continue
            if isinstance(acc, BS.Eval):
                r = acc.step(be.get(d, ()))
                if r == "pass":
                    acc, wait, nf = FundedX(plan, fz, sf, med), gap, nf + 1
                elif r in ("fail", "stuck"):
                    cash -= price
                    acc = EvalX(ez, se, plan)
            else:
                p = acc.step(bf.get(d, ()), d)
                if p:
                    npay += 1
                cash += p
                if acc.done:
                    ends[acc.done] += 1
                    cash -= price
                    acc = EvalX(ez, se, plan)
        if not isinstance(acc, BS.Eval):
            ends["open"] += 1
        nets.append(cash / (length / 21.0))
        funded_n.append(nf)
        pays.append(npay)
    a = np.array(nets)
    tot = max(1, sum(ends.values()))
    return {"life_pm": round(float(a.mean())), "life_p10": round(float(np.percentile(a, 10))), "life_lose": round(100.0 * float((a < 0).mean()), 1),
            "funded_per_6m": round(float(np.mean(funded_n)), 2), "pay_per_6m": round(float(np.mean(pays)), 2),
            "f_end": {k: round(100.0 * v / tot, 1) for k, v in sorted(ends.items())}}


def funded_scorex(T, S, fz, horizon=63, step=3):
    """3-month funded accounts started every 3rd session (scalp_na_lib.funded_score) with FundedX: $ / month to the owner,
    payouts a month, lost %, stuck %."""
    by, stuck = BS._by(T), BS._stuck(T)
    starts = [i for i in range(0, len(S), step) if i + horizon <= len(S)] or list(range(0, max(1, len(S) - 21), step))
    R = []
    for i in starts:
        days = S[i:i + horizon]
        Fx = FundedX(PLAN, fz, stuck, stuck / 2.0)
        paid = 0.0
        for d in days:
            paid += Fx.step(by.get(d, ()), d)
            if Fx.done:
                break
        R.append((paid, Fx.n_pay, Fx.done, len(days)))
    pm = [p / (nd / 21.0) for p, _, _, nd in R]
    return {"fund_pm": round(float(np.mean(pm))), "fund_pay_pm": round(float(np.mean([k / (nd / 21.0) for _, k, _, nd in R])), 2),
            "fund_lost": round(100.0 * sum(1 for r in R if r[2] == "lost") / len(R), 1),
            "fund_stuck": round(100.0 * sum(1 for r in R if r[2] == "stuck") / len(R), 1), "fund_starts": len(R)}


# ================================================================================================ data
TT = SP = None


def prep():
    global TT, SP
    if SP is None:
        from tools import blitz25k_grid as BG
        BG.prep()
        TT, SP = A._prep_blitz()
    return TT, SP


def lb_trades(T, up=LB[0], dn=LB[1]):
    return A.with_mult(T, A.nth_m(T, up, dn))


def score_cfg(ez, fz, n=1000, eval_lb=False, fund_T=None, seed=23):
    """one (eval size, funded size) on H1 / H2 / R: eval every-start, slot, funded-only."""
    out = {}
    for sp, (T, S) in SP.items():
        Te = lb_trades(T) if eval_lb else T
        Tf = fund_T[sp] if fund_T else T
        out[sp] = {"ev": eval_scorex(Te, S, ez), "slot": lifeX(Te, Tf, S, ez, fz, n=n, seed=seed), "fund": funded_scorex(Tf, S, fz)}
    return out


def _job(a):
    name, ez, fz, n, lb = a
    return {"name": name, "ez": ez, "fz": fz, "lb": lb, **score_cfg(ez, fz, n, lb)}


def pmap(jobs):
    from multiprocessing import Pool
    with Pool(PROCS) as P:
        return P.map(_job, jobs, chunksize=4)


def line(r):
    return " | ".join(f"{sp} 2w {r[sp]['ev']['p10']}/{r[sp]['ev']['f10']} slot ${r[sp]['slot']['life_pm']} fund ${r[sp]['fund']['fund_pm']} "
                      f"st {r[sp]['fund']['fund_stuck']}% pay/6m {r[sp]['slot']['pay_per_6m']}" for sp in ("H1", "H2", "R"))


# ================================================================================================ commands
def cmd_selfcheck():
    prep()
    bad = 0
    for sp, (T, S) in SP.items():
        a = BS.life_hybrid(T, T, S, EZ0, FZ0, n=300)
        b = lifeX(T, T, S, EZ0, FZ0, n=300)
        Te = lb_trades(T)
        c = BS.life_hybrid(Te, T, S, EZ_LB, FZ0, n=300)
        d = lifeX(Te, T, S, EZ_LB, FZ0, n=300)
        e0, e1 = BS.eval_score(Te, S, EZ_LB), eval_scorex(Te, S, EZ_LB)
        f0, f1 = BS.funded_score(T, S, FZ0), funded_scorex(T, S, FZ0)
        ok = a["life_pm"] == b["life_pm"] and c["life_pm"] == d["life_pm"] and all(e0[k] == e1[k] for k in ("p10", "f10", "p20", "pass_med")) \
            and f0["fund_pm"] == f1["fund_pm"] and f0["fund_stuck"] == f1["fund_stuck"]
        bad += not ok
        print(sp, "today", a["life_pm"], b["life_pm"], "| later-break", c["life_pm"], d["life_pm"], "| eval", e0["p10"], e1["p10"], e0["f10"], e1["f10"],
              "| funded", f0, f1, "OK" if ok else "DIFF", flush=True)
    print("selfcheck", "OK" if not bad else f"{bad} differ")


def funded_grid():
    G = [("today", FZ0)]
    base = dict(FZ0)
    # 1a buffer first: today's size until the floor locks, then bigger
    for f2, c2 in itertools.product((0.2, 0.3, 0.45, 0.6), (300.0, 450.0, 600.0)):
        G.append((f"lock -> f{f2} cap{int(c2)}", {**base, "f2": f2, "cap2": c2}))
    for f2, c2 in itertools.product((0.2, 0.3, 0.45), (300.0, 450.0)):
        G.append((f"lock -> f{f2} cap{int(c2)}, no day tp", {"mode": "frac", "f": 0.1, "cap": 150.0, "f2": f2, "cap2": c2}))
    # 1b integer micros by first / later break, before / after the lock
    for q1, q2, q1b, q2b in ((0, 1, 0, 1), (1, 2, 1, 2), (0, 1, 1, 2), (1, 1, 1, 2), (1, 1, 2, 3), (1, 2, 2, 3), (0, 1, 0, 2), (1, 1, 1, 3),
                             (0, 2, 0, 2), (1, 2, 1, 3), (0, 1, 1, 1), (1, 1, 2, 2)):
        for rq in (0.25, 0.5):
            G.append((f"micros first {q1}->{q1b} later {q2}->{q2b} rq{rq}", {**base, "q1": q1, "q2": q2, "q1b": q1b, "q2b": q2b, "rq": rq}))
    # 1c day / week stops
    for dl in (150.0, 250.0, 350.0):
        G.append((f"day loss {int(dl)}", {**base, "dloss": dl}))
    for nl in (1, 2, 3):
        G.append((f"{nl} losing trades a day", {**base, "nloss": nl}))
    for md in (2, 3, 4):
        G.append((f"max {md} trades a day", {**base, "maxday": md}))
    for wl in (250.0, 400.0, 600.0):
        G.append((f"week loss {int(wl)}", {**base, "wloss": wl}))
    # 1d payout ask
    for am in (250.0, 500.0, 750.0):
        G.append((f"ask max {int(am)}", {**base, "ask_max": am}))
    for aw in (500.0, 750.0, 1000.0):
        G.append((f"ask wait {int(aw)}", {**base, "ask_wait": aw}))
    # 1e the abandon line
    for sk in (0.0, 1.0, 1.5, 3.0):
        G.append((f"stuck {sk}x", {**base, "stuck_k": sk}))
    G.append(("no day tp", {"mode": "frac", "f": 0.1, "cap": 150.0}))
    return G


def cmd_funded(n_screen=600, n_final=1000):
    t0 = time.time()
    prep()
    G = funded_grid()
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "rows": {}}
    for lb, ez in ((False, EZ0), (True, EZ_LB)):
        jobs = [(nm, ez, fz, n_screen, lb) for nm, fz in G]
        R = pmap(jobs)
        base = R[0]
        key = "lb" if lb else "today_eval"
        out["rows"][key] = R
        print(f"\n== eval {'later-break' if lb else 'today'} ({len(R)} funded sizes, {time.time() - t0:.0f}s)")
        for r in R:
            beat = all(r[sp]["slot"]["life_pm"] > base[sp]["slot"]["life_pm"] for sp in ("H1", "H2", "R"))
            r["beats_all"] = beat
            print(f"{'*' if beat else ' '} {r['name']:44s} {line(r)}", flush=True)
    A.dump(out, os.path.join(OUT, "bzx_funded.json"))
    print(f"done {time.time() - t0:.0f}s")


def shuffled_later(T, seed):
    """the same trades with the first / later labels permuted within the span (the share of later breaks kept)."""
    rng = np.random.default_rng(seed)
    lab = np.array([is_later(t) for t in T])
    lab = rng.permutation(lab)
    return [{**t, "f": {**t.get("f", {}), "nth": 2.0 if x else 1.0}} for t, x in zip(T, lab)]


def _fjob2(a):
    """(name, ez, fz, n, lb, seed, shuffle_seed): the slot with the eval trades (later-break mult if lb) and the funded
    trades (later labels shuffled if shuffle_seed is not None)."""
    name, ez, fz, n, lb, seed, ss = a
    out = {"name": name, "ez": ez, "fz": fz, "lb": lb, "seed": seed, "ss": ss}
    for sp, (T, S) in SP.items():
        Te = lb_trades(T) if lb else T
        Tf = shuffled_later(T, ss) if ss is not None else T
        out[sp] = {"slot": lifeX(Te, Tf, S, ez, fz, n=n, seed=seed), "fund": funded_scorex(Tf, S, fz)}
    return out


def fz_name(z):
    if "q1" in z:
        s = f"first {z['q1']}->{z.get('q1b', z['q1'])} later {z['q2']}->{z.get('q2b', z['q2'])} micros, <= {int(100 * z.get('rq', 0.5))}% room"
    else:
        s = f"f{z['f']} cap{int(z['cap'])}"
    for k in ("dloss", "stuck_k", "nloss", "wloss"):
        if k in z:
            s += f" {k} {z[k]}"
    return s


def cmd_funded2(n=1000):
    """direction 1, stage 2: the integer-micro later-break funded size (the eval adopt-candidate's mechanism in whole
    micros: a later break 2-3 micros while that risks <= rq x the room, a first break 1), its neighbours, uniform-size
    controls (the same micros on every trade), shuffled first / later labels (20 draws), 3 Monte Carlo seeds, on today's
    and the later-break eval."""
    t0 = time.time()
    prep()
    base = dict(FZ0)
    fam = []
    for q2, q1b, q2b, rq in itertools.product((2, 3), (1, 2), (2, 3, 4), (0.2, 0.25, 0.3, 0.35, 0.5)):
        if q2b < q2:
            continue
        fam.append({**base, "q1": 1, "q2": q2, "q1b": q1b, "q2b": q2b, "rq": rq})
    ctrl = []
    for q, qb, rq in itertools.product((1, 2, 3), (1, 2, 3), (0.25, 0.5)):
        if qb >= q and (q, qb) != (1, 1):
            ctrl.append({**base, "q1": q, "q2": q, "q1b": qb, "q2b": qb, "rq": rq})
    extra = [{**base, "q1": 1, "q2": 2, "q1b": 1, "q2b": 2, "rq": 0.25, "stuck_k": 1.0}, {**base, "q1": 1, "q2": 2, "q1b": 1, "q2b": 2, "rq": 0.25, "stuck_k": 0.0},
             {**base, "q1": 1, "q2": 2, "q1b": 1, "q2b": 2, "rq": 0.25, "dloss": 150.0}, {**base, "stuck_k": 1.0}, {**base, "dloss": 150.0}]
    out = {"built": time.strftime("%Y-%m-%d %H:%M")}
    for lb, ez in ((True, EZ_LB), (False, EZ0)):
        jobs = [("today", ez, base, n, lb, 23, None)] + [(fz_name(z), ez, z, n, lb, 23, None) for z in fam + ctrl + extra]
        R = pmap2(jobs)
        b = R[0]
        for r in R:
            r["d"] = {sp: r[sp]["slot"]["life_pm"] - b[sp]["slot"]["life_pm"] for sp in ("H1", "H2", "R")}
            r["beats_all"] = all(v > 0 for v in r["d"].values())
        key = "lb" if lb else "today_eval"
        out[key] = R
        nf = [r for r in R[1:len(fam) + 1]]
        print(f"\n== eval {key}: base " + " | ".join(f"{sp} ${b[sp]['slot']['life_pm']}" for sp in ("H1", "H2", "R")) + f" ({time.time() - t0:.0f}s)")
        print(f"   family: {sum(r['beats_all'] for r in nf)}/{len(nf)} beat today in H1, H2 and R; H1 better {sum(r['d']['H1'] > 0 for r in nf)}, "
              f"H2 {sum(r['d']['H2'] > 0 for r in nf)}, R {sum(r['d']['R'] > 0 for r in nf)}; mean d " +
              " / ".join(f"{np.mean([r['d'][sp] for r in nf]):+.0f}" for sp in ("H1", "H2", "R")))
        for r in sorted(R, key=lambda r: -r["H1"]["slot"]["life_pm"]):
            print(f"{'*' if r['beats_all'] else ' '} {r['name']:62s} d {r['d']['H1']:+4d} {r['d']['H2']:+4d} {r['d']['R']:+4d} | " +
                  " | ".join(f"{sp} ${r[sp]['slot']['life_pm']} lose {r[sp]['slot']['life_lose']}% pay {r[sp]['slot']['pay_per_6m']} end {r[sp]['slot']['f_end']}"
                             for sp in ("H1", "H2", "R")), flush=True)
    A.dump(out, os.path.join(OUT, "bzx_funded2.json"))
    print(f"done {time.time() - t0:.0f}s")


def cmd_fcheck(n=1000):
    """the funded candidates: 3 Monte Carlo seeds and 20 shuffled first / later label draws (does the later-break label
    matter, or only the extra micros?)."""
    t0 = time.time()
    prep()
    C = json.load(open(os.path.join(OUT, "bzx_fcands.json")))
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "rows": []}
    for c in C:
        fz, ez, lb = c["fz"], (EZ_LB if c["lb"] else EZ0), c["lb"]
        jobs = []
        for seed in (23, 24, 25):
            jobs.append(("base", ez, FZ0, n, lb, seed, None))
            jobs.append(("cand", ez, fz, n, lb, seed, None))
        for ss in range(20):
            jobs.append(("shuf", ez, fz, 600, lb, 23, 100 + ss))
        jobs.append(("base600", ez, FZ0, 600, lb, 23, None))
        jobs.append(("cand600", ez, fz, 600, lb, 23, None))
        R = pmap2(jobs)
        seeds = {}
        for seed in (23, 24, 25):
            b = next(r for r in R if r["name"] == "base" and r["seed"] == seed)
            x = next(r for r in R if r["name"] == "cand" and r["seed"] == seed)
            seeds[seed] = {sp: [b[sp]["slot"]["life_pm"], x[sp]["slot"]["life_pm"]] for sp in ("H1", "H2", "R")}
        b6 = next(r for r in R if r["name"] == "base600")
        c6 = next(r for r in R if r["name"] == "cand600")
        sh = [r for r in R if r["name"] == "shuf"]
        shu = {sp: {"mean": round(float(np.mean([r[sp]["slot"]["life_pm"] for r in sh]))), "share_ge": round(float(np.mean([r[sp]["slot"]["life_pm"] >= c6[sp]["slot"]["life_pm"] for r in sh])), 2),
                    "real": c6[sp]["slot"]["life_pm"], "base": b6[sp]["slot"]["life_pm"]} for sp in ("H1", "H2", "R")}
        row = {"name": c["name"], "fz": fz, "lb": lb, "seeds": seeds, "shuffled": shu}
        out["rows"].append(row)
        print(f"{c['name']} (eval {'later-break' if lb else 'today'}): seeds {seeds} | shuffled labels {shu} ({time.time() - t0:.0f}s)", flush=True)
    A.dump(out, os.path.join(OUT, "bzx_fcheck.json"))


QSP = {}


def quarters():
    """2026 H1 split in its two quarters (the pick is made on H1 only: the variant that beats today in BOTH quarters by the
    most, i.e. max of min(d Q1, d Q2))."""
    if not QSP:
        T, S = SP["H1"]
        for nm, lo, hi in (("Q1", "2026-01-01", "2026-03-31"), ("Q2", "2026-04-01", "2026-06-30")):
            Sq = [d for d in S if lo <= d <= hi]
            QSP[nm] = ([t for t in T if lo <= t["day"] <= hi], Sq)
    return QSP


def _f3job(a):
    name, fz, n, seed = a
    out = {"name": name, "fz": fz}
    for sp, (T, S) in {**quarters(), **SP}.items():
        out[sp] = lifeX(lb_trades(T), T, S, EZ_LB, fz, n=n, seed=seed)["life_pm"]
    return out


def cmd_funded3(n=600):
    """direction 1, stage 3: the H1-only pick. Family = later-break integer micros (first 1 [-> 1/2 after the lock], later
    2-3 [-> 2-3], <= 20-50% of the room) x the abandon line (2.0 today / 1.5 / 1.0 / 0 = never) on the later-break eval;
    pick = the best worst-quarter gain in 2026 Q1 / Q2 vs today; then H2 and 2021-25 are the check (3 seeds)."""
    t0 = time.time()
    prep()
    quarters()
    base = dict(FZ0)
    G = [("today", base)]
    for (q2, q2b), q1b, rq, sk in itertools.product(((2, 2), (2, 3), (3, 3)), (1, 2), (0.2, 0.25, 0.3, 0.35, 0.5), (None, 1.5, 1.0, 0.0)):
        z = {**base, "q1": 1, "q2": q2, "q1b": q1b, "q2b": q2b, "rq": rq}
        if sk is not None:
            z["stuck_k"] = sk
        G.append((fz_name(z), z))
    for sk in (1.5, 1.0, 0.0):
        G.append((fz_name({**base, "stuck_k": sk}), {**base, "stuck_k": sk}))
    from multiprocessing import Pool
    with Pool(PROCS) as P:
        R = P.map(_f3job, [(nm, z, n, 23) for nm, z in G], chunksize=4)
    b = R[0]
    for r in R:
        r["d"] = {sp: r[sp] - b[sp] for sp in ("Q1", "Q2", "H1", "H2", "R")}
        r["h1_score"] = min(r["d"]["Q1"], r["d"]["Q2"])
    R.sort(key=lambda r: -r["h1_score"])
    print(f"base " + " ".join(f"{sp} ${b[sp]}" for sp in ("Q1", "Q2", "H1", "H2", "R")) + f" ({time.time() - t0:.0f}s)")
    for r in R[:25]:
        print(f"{r['name']:70s} worstQ {r['h1_score']:+4d} | " + " ".join(f"{sp} {r['d'][sp]:+4d}" for sp in ("Q1", "Q2", "H1", "H2", "R")), flush=True)
    nb = sum(1 for r in R[1:] if r["h1_score"] > 0)
    nall = sum(1 for r in R[1:] if r["h1_score"] > 0 and r["d"]["H2"] > 0 and r["d"]["R"] > 0)
    print(f"{nb} of {len(R) - 1} beat today in both H1 quarters; {nall} of those also in H2 and R")
    pick = R[0]
    seeds = {}
    with Pool(PROCS) as P:
        S3 = P.map(_f3job, [("base", base, 1000, s) for s in (23, 24, 25)] + [("pick", pick["fz"], 1000, s) for s in (23, 24, 25)])
    for s, bb, pp in zip((23, 24, 25), S3[:3], S3[3:]):
        seeds[s] = {sp: [bb[sp], pp[sp]] for sp in ("Q1", "Q2", "H1", "H2", "R")}
    print("pick", pick["name"], "seeds (today, pick):", seeds)
    A.dump({"built": time.strftime("%Y-%m-%d %H:%M"), "rows": R, "pick": pick, "pick_seeds": seeds, "n_both_quarters": nb, "n_all": nall},
           os.path.join(OUT, "bzx_funded3.json"))
    print(f"done {time.time() - t0:.0f}s")


def cmd_funded4(n=600):
    """direction 1, stage 4: near-the-floor skip (a 1-micro trade only while its stop-out is <= r1 x the room), alone and
    with the abandon line; the same H1-only pick (worst quarter) and checks as funded3."""
    t0 = time.time()
    prep()
    quarters()
    base = dict(FZ0)
    G = [("today", base)]
    for r1, sk in itertools.product((0.15, 0.2, 0.25, 0.3, 0.35), (None, 1.0, 0.0)):
        z = {**base, "r1": r1}
        if sk is not None:
            z["stuck_k"] = sk
        G.append((f"skip 1-micro stop > {r1} x room" + (f", abandon {sk}x" if sk is not None else ""), z))
    from multiprocessing import Pool
    with Pool(PROCS) as P:
        R = P.map(_f3job, [(nm, z, n, 23) for nm, z in G], chunksize=2)
    b = R[0]
    for r in R:
        r["d"] = {sp: r[sp] - b[sp] for sp in ("Q1", "Q2", "H1", "H2", "R")}
        r["h1_score"] = min(r["d"]["Q1"], r["d"]["Q2"])
    R.sort(key=lambda r: -r["h1_score"])
    for r in R:
        print(f"{r['name']:50s} worstQ {r['h1_score']:+4d} | " + " ".join(f"{sp} {r['d'][sp]:+4d}" for sp in ("Q1", "Q2", "H1", "H2", "R")), flush=True)
    A.dump({"built": time.strftime("%Y-%m-%d %H:%M"), "rows": R}, os.path.join(OUT, "bzx_funded4.json"))
    print(f"done {time.time() - t0:.0f}s")


def _sjob(a):
    """(label, kind, arg, fz, n): kind 'placebo' (random directions, seed arg), 'slip' (arg ticks a side), 'late' (1 bar),
    'year' (2021-25 by calendar year arg). The eval is the later-break size in every case; base = today's funded size."""
    lab, kind, arg, fz, n = a
    out = {"label": lab, "kind": kind, "arg": arg, "fz": fz}
    if kind == "year":
        T, S = SP["R"]
        Sy = [d for d in S if d[:4] == arg]
        Ty = [t for t in T if t["day"][:4] == arg]
        out["Y"] = {"base": lifeX(lb_trades(Ty), Ty, Sy, EZ_LB, FZ0, n=n)["life_pm"], "cand": lifeX(lb_trades(Ty), Ty, Sy, EZ_LB, fz, n=n)["life_pm"]}
        return out
    if kind == "placebo":
        TTp = K.trades({}, "lit+atlas", placebo=arg)
        for tf in (1, 5):
            A.attach(N.bars(tf), TTp[tf])
    elif kind == "late":
        TTp = A.blitz_trades({"late": 1})
    else:
        TTp = TT
    for sp, tf in K.SPANS:
        T, S = K.span(TTp, sp, tf)
        if kind == "slip":
            T = A.slip(T, arg)
        out[sp] = {"base": lifeX(lb_trades(T), T, S, EZ_LB, FZ0, n=n)["life_pm"], "cand": lifeX(lb_trades(T), T, S, EZ_LB, fz, n=n)["life_pm"],
                   "later_share": round(float(np.mean([is_later(t) for t in T])), 3)}
    return out


def cmd_fstress(n=600):
    """the funded candidates (later-break eval) under random directions (8 seeds), +1 / +2 ticks a side, 1 bar late, and
    2021-25 by year: does the funded gain need BLITZ's edge, and does it survive real fills?"""
    t0 = time.time()
    prep()
    C = {c["name"].split(" ")[0]: c["fz"] for c in json.load(open(os.path.join(OUT, "bzx_fcands.json"))) if c["lb"]}
    jobs = []
    for nm in ("C1", "C3", "H1-top"):
        fz = C[nm]
        jobs += [(nm, "placebo", sd, fz, n) for sd in range(8)]
        jobs += [(nm, "slip", 1, fz, n), (nm, "slip", 2, fz, n), (nm, "late", 1, fz, n)]
        jobs += [(nm, "year", y, fz, n) for y in ("2022", "2023", "2024", "2025")]
    from multiprocessing import Pool
    with Pool(PROCS) as P:
        R = P.map(_sjob, jobs, chunksize=1)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "rows": R, "summary": {}}
    for nm in ("C1", "C3", "H1-top"):
        rr = [r for r in R if r["label"] == nm]
        pl = [r for r in rr if r["kind"] == "placebo"]
        sm = {"placebo": {sp: {"base": round(float(np.mean([r[sp]["base"] for r in pl]))), "cand": round(float(np.mean([r[sp]["cand"] for r in pl])))} for sp in ("H1", "H2", "R")}}
        for r in rr:
            if r["kind"] in ("slip", "late"):
                sm[f"{r['kind']}{r['arg']}"] = {sp: [r[sp]["base"], r[sp]["cand"]] for sp in ("H1", "H2", "R")}
            if r["kind"] == "year":
                sm[f"y{r['arg']}"] = [r["Y"]["base"], r["Y"]["cand"]]
        out["summary"][nm] = sm
        print(nm, json.dumps(sm), flush=True)
    A.dump(out, os.path.join(OUT, "bzx_fstress.json"))
    print(f"done {time.time() - t0:.0f}s")


def pmap2(jobs):
    from multiprocessing import Pool
    with Pool(PROCS) as P:
        return P.map(_fjob2, jobs, chunksize=2)


def _ejob(a):
    name, ez, fz, n, lb = a
    return {"name": name, "ez": ez, "fz": fz, "lb": lb, **score_cfg(ez, fz, n, lb)}


def cmd_evalx(n=1000, fz_extra=None):
    """direction 2: eval-stage ideas on today's and the later-break eval size, with today's funded size (and the funded pick
    from cmd_funded if passed): first winner ends the day on sessions 1..s, skip first breaks on sessions 1..s, 2 losers end
    the day."""
    t0 = time.time()
    prep()
    if fz_extra is None and os.path.exists(os.path.join(OUT, "bzx_fcands.json")):
        fz_extra = json.load(open(os.path.join(OUT, "bzx_fcands.json")))[0]["fz"]          # C1
    fzs = [("funded today", FZ0)] + ([("funded C1", fz_extra)] if fz_extra else [])
    jobs = []
    for (fn, fz), (en, ez, lb) in itertools.product(fzs, (("eval today", EZ0, False), ("eval later-break", EZ_LB, True))):
        jobs.append((f"{en} | {fn}", ez, fz, n, lb))
        for s in (2, 3, 4, 5, 6):
            jobs.append((f"{en} + win stop s1-{s} | {fn}", {**ez, "win_stop": s}, fz, n, lb))
        for s in (4, 99):
            jobs.append((f"{en} + skip first breaks s1-{s} | {fn}", {**ez, "first_skip_s": s}, fz, n, lb))
        jobs.append((f"{en} + 2 losers end the day | {fn}", {**ez, "loss2_stop": True}, fz, n, lb))
    R = pmap(jobs)
    for r in R:
        print(f"{r['name']:58s} " + " | ".join(f"{sp} 2w {r[sp]['ev']['p10']}/{r[sp]['ev']['f10']} dec {r[sp]['ev']['dec10']} p20/f20 {r[sp]['ev']['p20']}/"
                                                f"{r[sp]['ev']['f20']} med {r[sp]['ev']['pass_med']} slow {r[sp]['ev']['slow_pass']} slot ${r[sp]['slot']['life_pm']}"
                                                for sp in ("H1", "H2", "R")), flush=True)
    A.dump({"built": time.strftime("%Y-%m-%d %H:%M"), "rows": R}, os.path.join(OUT, "bzx_eval.json"))
    print(f"done {time.time() - t0:.0f}s")
    return R


# ================================================================================================ direction 3: signal facts
def sig_feats():
    """per trade, known at the signal close: rvol (the signal bar's volume / the same minute's mean over the prior 14
    sessions), sg_reg (today's noise band sigma at that minute / its mean over the prior 60 sessions), band_atr (band
    half-width / the 5m ATR), opp_prev (the check 30 minutes earlier closed beyond the OTHER band), opp_any (any earlier
    check today beyond the other band)."""
    prep()
    for tf in (1, 5):
        B = N.bars(tf)
        F = N.signals(B, 1.0, 30, (630, 930), 1.5)
        sg, op = N._noise(B)
        v, m, t_ = B["v"], B["mod"], B["t"]
        bymod = collections.defaultdict(list)
        for i in np.where(m >= 570)[0]:
            bymod[int(m[i])].append(i)
        pos = {}
        for mm, L in bymod.items():
            for k, i in enumerate(L):
                pos[i] = (mm, k)
        ev = max(1, int(round(30 / tf)))
        rows = {int(i): (int(F["day"][q]), float(F["dir"][q])) for q, i in enumerate(F["sig"])}
        byday = collections.defaultdict(list)
        for i, (di, d) in rows.items():
            byday[di].append((i, d))
        bq = {int(i): q for q, i in enumerate(F["sig"])}
        for t in TT[tf]:
            i = int(np.searchsorted(t_, t["sig_t"]))
            f = t["f"]
            mm, k = pos.get(i, (None, None))
            if mm is not None and k >= 10:
                L = bymod[mm]
                prev = [L[j] for j in range(max(0, k - 14), k)]
                mv = float(np.mean(v[prev]))
                f["rvol"] = float(v[i] / mv) if mv > 0 else np.nan
                prev60 = [L[j] for j in range(max(0, k - 60), k)]
                s60 = np.nanmean(sg[prev60])
                f["sg_reg"] = float(sg[i] / s60) if s60 == s60 and s60 > 0 else np.nan
            else:
                f["rvol"] = f["sg_reg"] = np.nan
            q = bq.get(i)
            f["band_atr"] = float(F["band_atr"][q]) if q is not None else np.nan
            di = int(B["day"][i])
            d = float(t["dir"])
            ear = [(j, dd) for j, dd in byday.get(di, ()) if j < i]
            f["opp_any"] = 1.0 if any(dd != d for _, dd in ear) else 0.0
            f["opp_prev"] = 1.0 if any(j == i - ev and dd != d for j, dd in ear) else 0.0
            f["n_opp"] = float(sum(1 for _, dd in ear if dd != d))


SIG_FACTS = ("rvol", "sg_reg", "band_atr", "opp_any", "opp_prev", "prev_trend", "prev_win", "last10")


def prev_feats():
    """BLITZ's own recent past, known before the trade: prev_trend (the previous session had a later band break, any side:
    yesterday was a trend day), prev_win (BLITZ's trades on its previous trading day summed > 0 R), last10 (mean R of the
    last 10 BLITZ trades closed before this entry)."""
    for tf in (1, 5):
        B = N.bars(tf)
        F = N.signals(B, 1.0, 30, (630, 930), 1.5)
        dates = list(B["dates"])
        later_days = {dates[int(F["day"][q])] for q in range(len(F["sig"])) if F["nth"][q] >= 2}
        T = sorted(TT[tf], key=lambda t: t["entry_t"])
        sess = sorted({d for d in dates})
        pos = {d: k for k, d in enumerate(sess)}
        byday = collections.defaultdict(float)
        for t in T:
            byday[t["day"]] += t["pnl_pm"] / t["risk_pm"]
        tdays = sorted(byday)
        closed = []
        for t in T:
            k = pos.get(t["day"])
            prevd = sess[k - 1] if k else None
            t["f"]["prev_trend"] = (1.0 if prevd in later_days else 0.0) if prevd else np.nan
            j = int(np.searchsorted(tdays, t["day"])) - 1
            t["f"]["prev_win"] = (1.0 if byday[tdays[j]] > 0 else 0.0) if j >= 0 else np.nan
            done = [x for x in closed if x[0] <= t["entry_t"]]
            t["f"]["last10"] = float(np.mean([x[1] for x in done[-10:]])) if len(done) >= 10 else np.nan
            closed.append((t["exit_t"], t["pnl_pm"] / t["risk_pm"]))


def tilt(T, nm, cut, sign, up, dn):
    """x up where sign x (fact - cut) >= 0 (high side for sign +1), x dn on the other side; NaN -> 1."""
    x = np.array([t["f"].get(nm, np.nan) for t in T], float)
    mlt = np.ones(len(T))
    ok = x == x
    hi = ok & (x >= cut) if sign > 0 else ok & (x < cut)
    lo = ok & ~hi
    mlt[hi], mlt[lo] = up, dn
    return mlt


def r_view(T, S, m, usd=150.0):
    return A.rview(T, S, m, usd=usd)


def cmd_signals(n_pl=400, n_slot=1000):
    """direction 3: each fact as a size tilt (and binary facts as a skip) cut at its 2026 H1 median (binary: 0 / 1); a tilt
    counts when it is better per unit of risk AND in $ at $150 a trade in H1, H2 and 2021-25; shuffled control = the same
    multipliers permuted within the span (n_pl draws): the share of draws as good as the real one; then the 25K eval and the
    slot with the tilt in the eval (on top of the later-break size) and the funded stage (skip = 0 micros)."""
    t0 = time.time()
    prep()
    sig_feats()
    prev_feats()
    H1T = SP["H1"][0]
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "facts": {}, "tilts": []}
    for nm in SIG_FACTS + ("n_opp",):
        row = {}
        for sp, (T, S) in SP.items():
            x = np.array([t["f"].get(nm, np.nan) for t in T], float)
            R = np.array([t["pnl_pm"] / t["risk_pm"] for t in T])
            if nm.startswith("opp") or nm.startswith("prev"):
                row[sp] = {"0": [int((x == 0).sum()), round(float(R[x == 0].mean()), 3)], "1": [int((x == 1).sum()), round(float(R[x == 1].mean()), 3) if (x == 1).any() else None]}
            else:
                h1 = np.array([t["f"].get(nm, np.nan) for t in H1T], float)
                q = np.nanpercentile(h1, [33.3, 66.7])
                b = [R[(x < q[0])], R[(x >= q[0]) & (x < q[1])], R[x >= q[1]]]
                row[sp] = {"terciles_h1": [round(float(v), 3) for v in q], "avg_r": [round(float(v.mean()), 3) if len(v) else None for v in b], "n": [len(v) for v in b]}
        out["facts"][nm] = row
        print(nm, row, flush=True)
    rng = np.random.default_rng(29)
    specs = []
    for nm in ("rvol", "sg_reg", "band_atr", "last10"):
        h1 = np.array([t["f"].get(nm, np.nan) for t in H1T], float)
        for qq in (33.3, 50.0, 66.7):
            cut = float(np.nanpercentile(h1, qq))
            for sign in (1, -1):
                for up, dn in ((1.5, 0.5), (1.25, 0.75), (1.0, 0.5), (1.0, 0.0)):
                    specs.append((nm, cut, sign, up, dn, f"{nm} {'high' if sign > 0 else 'low'} (H1 p{qq:.0f} {cut:.3g}) x{up} / else x{dn}"))
    for nm in ("opp_any", "opp_prev"):
        for up, dn in ((1.0, 0.5), (1.0, 0.0), (1.25, 0.75), (1.5, 0.5)):
            specs.append((nm, 0.5, -1, up, dn, f"no {nm} x{up} / {nm} x{dn}"))
    for nm in ("prev_trend", "prev_win"):
        for sign in (1, -1):
            for up, dn in ((1.0, 0.5), (1.0, 0.0), (1.25, 0.75), (1.5, 0.5)):
                specs.append((nm, 0.5, sign, up, dn, f"{nm}={1 if sign > 0 else 0} x{up} / else x{dn}"))
    base = {sp: r_view(T, S, None) for sp, (T, S) in SP.items()}
    for nm, cut, sign, up, dn, lab in specs:
        r = {"name": lab, "fact": nm, "cut": cut, "sign": sign, "up": up, "dn": dn}
        good = True
        for sp, (T, S) in SP.items():
            m = tilt(T, nm, cut, sign, up, dn)
            v = r_view(T, S, m)
            v["share_lo"] = round(100.0 * float((m < 1).mean()), 1)
            r[sp] = v
            if not (v["r_per_risk"] > base[sp]["r_per_risk"] and v["per_month"] > base[sp]["per_month"]):
                good = False
        r["better_all"] = good
        out["tilts"].append(r)
    nb = sum(r["better_all"] for r in out["tilts"])
    print(f"{nb} of {len(specs)} tilts better per risk AND in $ in H1, H2 and 2021-25", flush=True)
    # shuffled-fact control for the whole grid (the facts permuted within each span; 30 runs)
    cnt = []
    for k in range(30):
        perm = {sp: rng.permutation(len(T)) for sp, (T, S) in SP.items()}
        c = 0
        for nm, cut, sign, up, dn, lab in specs:
            ok = True
            for sp, (T, S) in SP.items():
                m = tilt(T, nm, cut, sign, up, dn)[perm[sp]]
                v = r_view(T, S, m)
                if not (v["r_per_risk"] > base[sp]["r_per_risk"] and v["per_month"] > base[sp]["per_month"]):
                    ok = False
                    break
            c += ok
        cnt.append(c)
    out["grid_placebo"] = {"real": nb, "shuffled_mean": round(float(np.mean(cnt)), 1), "shuffled_p95": float(np.percentile(cnt, 95)), "share_ge": round(float(np.mean(np.array(cnt) >= nb)), 3)}
    print("grid placebo", out["grid_placebo"], flush=True)
    # each survivor: its own shuffle p, then the 25K eval / slot (tilt x the later-break mult in the eval; skip in funded)
    surv = [r for r in out["tilts"] if r["better_all"]]
    surv.sort(key=lambda r: -min(r[sp]["r_per_risk"] - base[sp]["r_per_risk"] for sp in SP))
    for r in surv[:6]:
        r["placebo_p"] = {}
        for sp, (T, S) in SP.items():
            m = tilt(T, r["fact"], r["cut"], r["sign"], r["up"], r["dn"])
            Rr = np.array([t["pnl_pm"] / t["risk_pm"] for t in T])
            real = (m * Rr).sum() / m.sum()
            sh = [(mm * Rr).sum() / mm.sum() for mm in (rng.permutation(m) for _ in range(n_pl))]
            r["placebo_p"][sp] = round(float(np.mean(np.array(sh) >= real)), 3)
        r["slot"] = {}
        for sp, (T, S) in SP.items():
            m = tilt(T, r["fact"], r["cut"], r["sign"], r["up"], r["dn"])
            Te = A.with_mult(T, A.nth_m(T, *LB) * m)
            Tf = [t for t, x in zip(T, m) if x > 0]
            r["slot"][sp] = {"ev": eval_scorex(Te, S, EZ_LB), "slot": lifeX(Te, Tf, S, EZ_LB, FZ0, n=n_slot)["life_pm"]}
        print(f"{r['name']:60s} p {r['placebo_p']} | " + " | ".join(f"{sp} R/risk {r[sp]['r_per_risk']} (base {base[sp]['r_per_risk']}) ${r[sp]['per_month']}/mo "
                                                                  f"PF {r[sp]['pf']} 2w {r['slot'][sp]['ev']['p10']}/{r['slot'][sp]['ev']['f10']} slot ${r['slot'][sp]['slot']}"
                                                                  for sp in SP), flush=True)
    out["base"] = base
    out["base_slot_lb"] = {sp: {"ev": eval_scorex(lb_trades(T), S, EZ_LB), "slot": lifeX(lb_trades(T), T, S, EZ_LB, FZ0, n=n_slot)["life_pm"]} for sp, (T, S) in SP.items()}
    print("base (later-break eval, today's funded)", out["base_slot_lb"], flush=True)
    A.dump(out, os.path.join(OUT, "bzx_signals.json"))
    print(f"done {time.time() - t0:.0f}s")


# ================================================================================================ store the runs
USD = 150.0


def store_trades(T, mults=None):
    """runlib rows at $150 x mult a trade (integer micros, at least 1)."""
    out = []
    for k, t in enumerate(sorted(T, key=lambda x: x["entry_t"])):
        m = 1.0 if mults is None else float(mults(t))
        q = max(1, min(20, int(USD * m / t["risk_pm"]))) if m > 0 else 0
        if q == 0:
            continue
        out.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "r": t["pnl_pm"] / t["risk_pm"],
                    "pnl": round(q * t["pnl_pm"], 2), "risk_pts": t["risk_pts"], "qty": q, "risk_usd": round(q * t["risk_pm"], 2), "half": 0,
                    "exit": t["exit_kind"], "trigger": "blitz", "mfe": None, "mae": t["mae_pts"], "bars_held": t["bars"], "regime": None,
                    "mult": m, "low": q * t["mae_pm"]})
    return out


def fixed_view(mults=None):
    """per span at $150 x mult: trades / week, % weeks 2+, PF, net, $ / month, max DD (scalp_na_lib.stats on the stored rows)."""
    o = {}
    for sp, (T, S) in SP.items():
        Ts = store_trades(T, mults)
        p = np.array([t["pnl"] for t in Ts])
        eq = np.cumsum(p)
        gl = -p[p < 0].sum()
        o[sp] = {"n": len(Ts), "tpw": round(len(Ts) / (len(S) / 5), 2), "wk2": K.wk2(Ts, S), "pf": round(float(p[p > 0].sum() / gl), 2),
                 "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (len(S) / 21)),
                 "dd": round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()))}
    return o


def cmd_save():
    from tools import runlib as rl
    prep()
    sig_feats()
    prev_feats()
    J = lambda n: json.load(open(os.path.join(OUT, n), encoding="utf-8"))
    F2, F3, FC, FS, EV, SG, F1, F4 = (J("bzx_funded2.json"), J("bzx_funded3.json"), J("bzx_fcheck.json"), J("bzx_fstress.json"), J("bzx_eval.json"),
                                      J("bzx_signals.json"), J("bzx_funded.json"), J("bzx_funded4.json"))
    B1, B5 = N.bars(1), N.bars(5)
    sess = sorted(set(N.sessions(B5, "R")) | set(N.sessions(B1, "H1")) | set(N.sessions(B1, "H2")))
    allT = SP["R"][0] + SP["H1"][0] + SP["H2"][0]
    views = {"today": fixed_view(), "later_x2": fixed_view(lambda t: 2.0 if is_later(t) else 1.0),
             "prev_win": fixed_view(lambda t: 1.0 if t["f"].get("prev_win", 1.0) != 0.0 else 0.5)}
    for k, v in views.items():
        print(k, v, flush=True)
    A.dump(views, os.path.join(OUT, "bzx_fixed150.json"))
    tags = ["scalp", "blitz", "account_c", "25k", "bzx"]
    wu = "blitz-edge-2026-10-30b"
    # 1. funded later-break micros (promising, not adopted)
    pk = F3["pick"]
    c3 = next(r for r in FC["rows"] if r["name"].startswith("C3"))
    c1 = next(r for r in FC["rows"] if r["name"].startswith("C1"))
    s3 = FS["summary"]["C3"]
    v = (f"Funded 25K, later-break size in whole micros (a later band break 2 micros, a first break 1). H1-only pick (best worst quarter of 123): "
         f"'{pk['name']}' = slot d H1 {pk['d']['H1']:+d} / H2 {pk['d']['H2']:+d} / 2021-25 {pk['d']['R']:+d} $ a month vs today's funded size on the "
         f"later-break eval -> fails H2 and 2021-25 (3 seeds). 25 of 123 beat today in both H1 quarters, {F3['n_all']} of those also in H2 and 2021-25. "
         f"Most robust member C3 (later 2 micros while <= 25% of the room, abandon the account at 1 x the median stop instead of 2 x): seeds "
         f"{c3['seeds']}, +1 tick {s3['slip1']}, 1 bar late {s3['late1']}, years 2022-25 {[s3['y' + y] for y in ('2022', '2023', '2024', '2025')]}; "
         f"but not the H1 pick, and random directions get part of the gain ({s3['placebo']}). C1 (later 3 micros, all trades 2 after the lock, <= 50%): "
         f"seeds {c1['seeds']} - 2021-25 ties on seed 24 and loses at +1 / +2 ticks. Promising lead, not an adopt-candidate.")
    rl.save("bzx_funded_later2", "BLITZ funded 25K: later band breaks 2 micros, first breaks 1 (+ abandon at 1x) - promising, H1 pick fails H2", "risk",
            "Owner 2026-10-30: the funded stage is where the 25K slot loses its money (stuck before a payout) - can the funded size fix it?",
            params={**K.TODAY, "account_c": "never opposite LIT / ATLAS"}, sizing={"usd_per_trade": USD, "x": "2 on a later break, 1 on a first break (the funded micro ratio)",
                                                                                   "eval_25k": EZ_LB, "eval_mult": {"later_x": LB[0], "first_x": LB[1]},
                                                                                   "funded_c3": json.load(open(os.path.join(OUT, "bzx_fcands.json")))[2]["fz"], "funded_h1_pick": pk["fz"]},
            trades=store_trades(allT, lambda t: 2.0 if is_later(t) else 1.0), scored=rl.score(store_trades(allT, lambda t: 2.0 if is_later(t) else 1.0), sess),
            status="promising", verdict=v, notes="tools/bzx_edge.py funded2 / funded3 / fcheck / fstress (stored at $150 x the funded micro ratio)",
            writeup=wu, tags=tags + ["funded", "sizing"])
    # 2. funded rules (rejected)
    rows = {r["name"]: r for r in F1["rows"]["lb"]}
    b = rows["today"]
    pick = lambda nm: f"{nm}: " + " / ".join(f"{rows[nm][sp]['slot']['life_pm'] - b[sp]['slot']['life_pm']:+d}" for sp in ("H1", "H2", "R"))
    v = ("Funded 25K rules on the later-break eval, slot $ a month vs today's funded size (H1 / H2 / 2021-25, 600 paths): " +
         "; ".join(pick(nm) for nm in ("lock -> f0.3 cap300", "lock -> f0.2 cap300", "day loss 150", "2 losing trades a day", "max 3 trades a day", "week loss 250",
                                         "ask max 500", "ask wait 750", "stuck 1.0x", "stuck 0.0x", "no day tp")) +
         ". Near the floor, skipping a 1-micro trade whose stop is > 0.2-0.35 x the room: H1 -35 to -149. None better in all three: rejected.")
    rl.save("bzx_funded_rules", "BLITZ funded 25K: buffer-first size, day / week stops, payout ask, abandon line, near-floor skip - rejected", "risk",
            "Buffer-first funded size (bigger once the floor locks), funded day / week stops, payout-ask timing and amount, the abandon line?",
            params={**K.TODAY}, sizing={"usd_per_trade": USD, "eval_25k": EZ_LB, "funded_25k": FZ0}, trades=store_trades(allT), scored=rl.score(store_trades(allT), sess),
            status="rejected", verdict=v, notes="tools/bzx_edge.py funded / funded4", writeup=wu, tags=tags + ["funded"])
    # 3. eval rules (rejected)
    er = {r["name"]: r for r in EV["rows"]}
    e = lambda nm: f"{nm.split(' | ')[0]}: 2w " + " / ".join(f"{er[nm][sp]['ev']['p10']}-{er[nm][sp]['ev']['f10']} slot ${er[nm][sp]['slot']['life_pm']}" for sp in ("H1", "H2", "R"))
    v = ("25K eval ideas (with today's funded size): " + "; ".join(e(nm) for nm in ("eval later-break | funded today", "eval later-break + win stop s1-4 | funded today",
                                                                                      "eval later-break + skip first breaks s1-4 | funded today", "eval later-break + 2 losers end the day | funded today",
                                                                                      "eval today | funded today", "eval today + win stop s1-4 | funded today")) +
         ". The first winner ending the day on sessions 1-4 slows the eval and loses slot $ everywhere; 2 losers ending the day cuts 2-week fails but only delays "
         "them (H1 4-week pass 62.4% vs 70.6%). Rejected.")
    rl.save("bzx_eval_rules", "BLITZ 25K eval: first winner ends the day (sessions 1-4), skip first breaks early, 2 losers end the day - rejected", "risk",
            "Eval-stage ideas not tested before, on top of the later-break eval size",
            params={**K.TODAY}, sizing={"usd_per_trade": USD, "eval_25k": EZ_LB, "funded_25k": FZ0}, trades=store_trades(allT), scored=rl.score(store_trades(allT), sess),
            status="rejected", verdict=v, notes="tools/bzx_edge.py evalx", writeup=wu, tags=tags + ["eval"])
    # 4. signal facts (rejected)
    fx = SG["facts"]
    v = (f"Signal-level facts as size tilts / skips (cut on 2026 H1): 0 of {len(SG['tilts'])} better per unit of risk AND in $ in H1, H2 and 2021-25 "
         f"(shuffled facts give {SG['grid_placebo']['shuffled_mean']} on average). Signal-bar volume vs the same minute's 14-day mean, avg R by H1 tercile "
         f"{fx['rvol']['H1']['avg_r']} / {fx['rvol']['H2']['avg_r']} / {fx['rvol']['R']['avg_r']}; band width / ATR {fx['band_atr']['H1']['avg_r']} / "
         f"{fx['band_atr']['H2']['avg_r']} / {fx['band_atr']['R']['avg_r']}; an earlier opposite-side break today is rare ({fx['opp_any']['H1']['1'][0]} / "
         f"{fx['opp_any']['H2']['1'][0]} / {fx['opp_any']['R']['1'][0]} trades); after a winning BLITZ day {fx['prev_win']['H1']['1'][1]} vs "
         f"{fx['prev_win']['H1']['0'][1]} (H1), {fx['prev_win']['H2']['1'][1]} vs {fx['prev_win']['H2']['0'][1]} (H2) but {fx['prev_win']['R']['1'][1]} vs "
         f"{fx['prev_win']['R']['0'][1]} (2021-25). Stored: x1 after a winning BLITZ day, x0.5 otherwise. Rejected.")
    mpw = lambda t: 1.0 if t["f"].get("prev_win", 1.0) != 0.0 else 0.5
    rl.save("bzx_signal_facts", "BLITZ signal facts: relative volume, band width, opposite break, yesterday's result - rejected", "filters",
            "Signal-level facts not in the rejected list, each as a size tilt with a shuffled control",
            params={**K.TODAY, "tilt": "prev_win x1 / x0.5 (stored example)"}, sizing={"usd_per_trade": USD}, trades=store_trades(allT, mpw),
            scored=rl.score(store_trades(allT, mpw), sess), status="rejected", verdict=v, notes="tools/bzx_edge.py signals", writeup=wu, tags=tags + ["filters"])
    print("-> runs bzx_funded_later2, bzx_funded_rules, bzx_eval_rules, bzx_signal_facts")


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else "selfcheck"
    {"selfcheck": cmd_selfcheck, "funded": cmd_funded, "funded2": cmd_funded2, "fcheck": cmd_fcheck, "funded3": cmd_funded3, "funded4": cmd_funded4, "fstress": cmd_fstress, "save": cmd_save, "evalx": cmd_evalx, "signals": cmd_signals}[cmd]()
