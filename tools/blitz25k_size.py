"""BLITZ on its own MFFU Builder 25K (account C): eval-speed sizing and the whole account slot (research/writeups/blitz-25k.md).
Research only.

The eval engine is tools/scalp_na_lib.run_eval (checked equal with every new knob off: `selfcheck`) plus four sizing knobs:
  push      (s, f2): from eval session s on (not passed yet) the room share goes from f to f2 - "get it decided by session 10"
  day_loss  no new BLITZ trade once the day is down $X (the soft daily loss stays $600)
  maxday    at most n BLITZ trades a day in the eval (the rest of the day's signals are skipped)
  tneed     micros so that the trade's TARGET pays what the eval still needs (one winner passes), capped by f x room
The slot = scalp_na_lib.life (buy the eval $63, pass, 2 sessions of paperwork, the funded 25K with its own size, payouts 80%,
a new eval after a fail / stuck / lost / 5 payouts; 6-month Monte Carlo paths in 5-session blocks, seed 23) with this eval.

    python -X utf8 tools/blitz25k_size.py selfcheck   # this eval engine = scalp_na_lib.run_eval (knobs off)
    python -X utf8 tools/blitz25k_size.py grid        # rules x eval sizes x funded sizes -> b25_grid_size.json (local) + b25_size.json
"""
from __future__ import annotations

import collections
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
from tools import scalp_na_lib as N  # noqa: E402
from tools import blitz25k_lib as K  # noqa: E402

K.install_qty()                   # the funded accounts (scalp_na_lib.Funded) size with blitz25k_lib.qty too ("mult", "tneed")
OUT = os.path.join(ROOT, "research", "scalp")
PLAN = N.PLANS["25k"]


# ================================================================================================ eval with the extra knobs
class Eval:
    def __init__(self, sz, stuck, plan="25k"):
        self.P, self.sz, self.stuck = N.PLANS[plan], sz, stuck
        self.bal = self.peak = 0.0
        self.floor = -self.P["mll"]
        self.s = 0

    def size(self):
        z = self.sz
        p = z.get("push")
        if p and self.s >= p[0]:
            return {**z, "f": p[1], "cap": p[2] if len(p) > 2 else z["cap"]}
        return z

    def step(self, ts, keep=None):
        P = self.P
        self.s += 1
        z = self.size()
        dp, n = 0.0, 0
        dl, md, tp = z.get("day_loss"), z.get("maxday"), z.get("day_tp")
        for t in ts:
            if (tp is not None and dp >= tp) or (dl is not None and dp <= -dl) or (md is not None and n >= md):
                break
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
            if keep is not None:
                keep.append({**t, "qty": q, "pnl": round(pnl, 2)})
            if self.bal + dp >= P["target"]:
                return "pass"
            if dp <= -P["dll"]:
                break
        self.bal += dp
        if self.bal <= self.floor:
            return "fail"
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - P["mll"]), P["lock"])
        if self.bal - self.floor < self.stuck:
            return "stuck"
        return None


def _by(T):
    by = collections.defaultdict(list)
    for t in T:
        by[t["day"]].append(t)
    return by


def _stuck(T):
    return 2.0 * float(np.median([t["risk_pm"] for t in T])) if T else 60.0


def run_eval(days, by, sz, horizon=20, stuck=60.0, keep=None):
    E = Eval(sz, stuck)
    for k, d in enumerate(days[:horizon]):
        r = E.step(by.get(d, ()), keep)
        if r == "pass":
            return "PASS", k + 1
        if r in ("fail", "stuck"):
            return ("FAIL" if r == "fail" else "STUCK"), k + 1
    return "OPEN", min(len(days), horizon)


def eval_score(T, S, sz, paths=False):
    """scalp_na_lib.eval_score with this eval: p10 / f10 / dec10 / p15 / f15 / p20 / f20 / pass_med / slow_pass (+ the
    back-to-back path: passes and fails, eval $ a month)."""
    by, stuck = _by(T), _stuck(T)
    res = [(run_eval(S[i:i + 20], by, sz, stuck=stuck), len(S) - i) for i in range(len(S))]
    o = {}
    for H in (10, 15, 20):
        R = [r for r, av in res if av >= H]
        n = len(R) or 1
        o[f"p{H}"] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= H) / n, 1)
        o[f"f{H}"] = round(100.0 * sum(1 for r in R if r[0] in ("FAIL", "STUCK") and r[1] <= H) / n, 1)
    o["dec10"] = round(o["p10"] + o["f10"], 1)
    o["dec15"] = round(o["p15"] + o["f15"], 1)
    pas = [r[1] for r, _ in res if r[0] == "PASS"]
    o["pass_med"] = float(np.median(pas)) if pas else None
    o["slow_pass"] = round(100.0 * sum(1 for x in pas if x > 15) / len(pas), 1) if pas else None
    o["pass20"] = round(100.0 * len(pas) / max(1, len(res)), 1)
    if paths:
        k, Kp, n = 0, [], collections.Counter()
        while k < len(S):
            r, used = run_eval(S[k:], by, sz, len(S) - k, stuck, keep=Kp)
            n[r] += 1
            if r == "OPEN":
                break
            k += used
        o["b2b"] = f"{n['PASS']}/{n['FAIL'] + n['STUCK']}"
        o["med_qty"] = float(np.median([x["qty"] for x in Kp])) if Kp else 0
    return o


def life(T, S, ez, fz, n=1000, length=126, gap=2, seed=23, plan="25k"):
    """scalp_na_lib.life with this module's eval (ez may carry push / day_loss / maxday / tneed)."""
    by, stuck = _by(T), _stuck(T)
    price = N.PLANS[plan]["price"]
    nets, funded_n, first, evals = [], [], [], []
    for seq in N.mc_paths(S, n, length, seed=seed):
        cash, nf, wait, acc, fp, ne = -price, 0, 0, Eval(ez, stuck, plan), None, 1
        for k, d in enumerate(seq):
            if wait:
                wait -= 1
                continue
            if isinstance(acc, Eval):
                r = acc.step(by.get(d, ()))
                if r == "pass":
                    acc, wait, nf = N.Funded(plan, fz, stuck), gap, nf + 1
                elif r in ("fail", "stuck"):
                    cash -= price
                    ne += 1
                    acc = Eval(ez, stuck, plan)
            else:
                paid = acc.step(by.get(d, ()))
                if paid and fp is None:
                    fp = k + 1
                cash += paid
                if acc.done:
                    cash -= price
                    ne += 1
                    acc = Eval(ez, stuck, plan)
        nets.append(cash / (length / 21.0))
        funded_n.append(nf)
        evals.append(ne)
        if fp:
            first.append(fp)
    a = np.array(nets)
    return {"life_pm": round(float(a.mean())), "life_p10": round(float(np.percentile(a, 10))), "life_lose": round(100.0 * float((a < 0).mean()), 1),
            "funded_per_6m": round(float(np.mean(funded_n)), 2), "evals_per_6m": round(float(np.mean(evals)), 2),
            "first_pay_med": float(np.median(first)) if first else None}


def funded_score(T, S, fz):
    return N.funded_score(T, S, "25k", fz)


def cmd_selfcheck():
    TT = K.trades({}, None)
    bad = 0
    for sp, tf in K.SPANS:
        T, S = K.span(TT, sp, tf)
        for z in ({"mode": "frac", "f": 0.4, "cap": 600.0}, {"mode": "frac", "f": 0.6, "cap": 600.0}, {"mode": "frac", "f": 0.3, "cap": 300.0, "day_tp": 400.0}):
            a = N.eval_score(T, S, "25k", z, paths=False)
            b = eval_score(T, S, z)
            d = {k: (a[k], b[k]) for k in ("p10", "f10", "p15", "f15", "p20", "f20", "pass_med", "slow_pass") if a[k] != b[k]}
            bad += bool(d)
            print(sp, z, "same" if not d else d)
        la = N.life(T, S, "25k", {"mode": "frac", "f": 0.6, "cap": 600.0}, {"mode": "frac", "f": 0.1, "cap": 150.0, "day_tp": 400.0}, n=200)
        lb = life(T, S, {"mode": "frac", "f": 0.6, "cap": 600.0}, {"mode": "frac", "f": 0.1, "cap": 150.0, "day_tp": 400.0}, n=200)
        print(sp, "life", la["life_pm"], lb["life_pm"], la["funded_per_6m"], lb["funded_per_6m"])
        bad += la["life_pm"] != lb["life_pm"]
    print("selfcheck", "OK" if not bad else f"{bad} differ")


# ================================================================================================ the grid
def eval_specs(with_tneed=False):
    G = []
    for f, cap in itertools.product((0.3, 0.4, 0.5, 0.6, 0.8, 1.0), (400.0, 600.0)):
        G.append({"mode": "frac", "f": f, "cap": cap})
    for f, cap, push in itertools.product((0.3, 0.4, 0.5), (600.0,), ((5, 0.8), (6, 1.0), (8, 1.0))):
        G.append({"mode": "frac", "f": f, "cap": cap, "push": push})
    for f, dl in itertools.product((0.5, 0.6, 0.8), (250.0, 350.0)):
        G.append({"mode": "frac", "f": f, "cap": 600.0, "day_loss": dl})
    for f, md in itertools.product((0.5, 0.6, 0.8), (2, 3)):
        G.append({"mode": "frac", "f": f, "cap": 600.0, "maxday": md})
    if with_tneed:
        for f in (0.4, 0.6, 0.8, 1.0):
            G.append({"mode": "tneed", "f": f, "cap": 600.0})
    return G


def fund_specs():
    G = [{"mode": "frac", "f": f, "cap": c} for f, c in itertools.product((0.1, 0.2, 0.3, 0.45), (150.0, 300.0, 450.0))]
    return G + [{**z, "day_tp": 400.0} for z in G]


def zname(z):
    s = f"{z['mode']} f{z['f']} cap{int(z['cap'])}"
    if z.get("push"):
        s += f" push s{z['push'][0]}->f{z['push'][1]}"
    if z.get("day_loss"):
        s += f" dayloss{int(z['day_loss'])}"
    if z.get("maxday"):
        s += f" max{z['maxday']}/day"
    if z.get("day_tp"):
        s += f" dtp{int(z['day_tp'])}"
    return s


RULES = {}
TTS = {}


def _evjob(a):
    rk, z = a
    out = {"rule": rk, "z": z, "name": zname(z)}
    for sp, tf in K.SPANS:
        T, S = K.span(TTS[rk], sp, tf)
        out[sp] = eval_score(T, S, z)
    return out


def _lfjob(a):
    rk, ez, fz, n = a
    out = {"rule": rk, "ez": ez, "fz": fz, "name": f"eval[{zname(ez)}] funded[{zname(fz)}]"}
    for sp, tf in K.SPANS:
        T, S = K.span(TTS[rk], sp, tf)
        out[sp] = life(T, S, ez, fz, n=n)
    return out


def load_rules(cmode="lit+atlas"):
    """the rules that go to sizing: today's + the stage-2 H1 picks (the local grid b25_grid_mgmt.json), all as account C."""
    R = {"today": {}}
    G = json.load(open(os.path.join(OUT, "b25_grid_mgmt.json")))["rows"]
    ok = [r for r in G if r["H1"]["tpw"] >= 3.0 and r["H1"]["wk2"] >= 70.0]

    def fam(r):
        v = r["v"]
        if v.get("sw_trail", 0) == 0 and v.get("choch", 0) == 0:
            return "clock" if v.get("tgt") is None else "target"
        return "structure"
    for f in ("clock", "target", "structure"):
        b = max((r for r in ok if fam(r) == f), key=lambda r: r["H1"]["t_r"])
        R[f"h1t_{f}"] = b["v"]
    R["h1_eval60"] = max(ok, key=lambda r: r["H1"]["f60"]["p10"] - r["H1"]["f60"]["f10"])["v"]
    R["h1_eval40"] = max(ok, key=lambda r: r["H1"]["f40"]["p10"] - r["H1"]["f40"]["f10"])["v"]
    return R


def cmd_grid(procs=3, n_screen=300, n_final=1000, top_e=6):
    from multiprocessing import Pool
    from tools import blitz25k_grid as BG
    t0 = time.time()
    BG.prep()
    RULES.update(load_rules())
    RULES["today_alone"] = {}
    RULES["posthoc_atr1_hold45"] = {"stop": "atr", "k": 1.0, "hold": 45, "trail": None}     # info only: found by looking at H2 / 2021-25
    for rk, v in RULES.items():
        TTS[rk] = K.trades(v, None if rk == "today_alone" else "lit+atlas")
        print(rk, BG.vname(v), {sp: len(K.span(TTS[rk], sp, tf)[0]) for sp, tf in K.SPANS}, flush=True)
    jobs = [(rk, z) for rk, v in RULES.items() for z in eval_specs(v.get("tgt") == "liq")]
    with Pool(procs) as P:
        E = P.map(_evjob, jobs, chunksize=4)
    print(f"{len(E)} eval sizes in {time.time() - t0:.0f}s", flush=True)
    # per rule: the top eval sizes on H1 (2-week pass - fail, then pass rate in 20) go to the slot grid
    L = []
    for rk in RULES:
        es = sorted([e for e in E if e["rule"] == rk], key=lambda e: -(e["H1"]["p10"] - e["H1"]["f10"] + 0.25 * e["H1"]["p20"]))[:top_e]
        L += [(rk, e["z"], fz, n_screen) for e in es for fz in fund_specs()]
    with Pool(procs) as P:
        LF = P.map(_lfjob, L, chunksize=2)
    print(f"{len(LF)} slots in {time.time() - t0:.0f}s", flush=True)
    picks = {}
    for rk in RULES:
        rows = sorted([r for r in LF if r["rule"] == rk], key=lambda r: -r["H1"]["life_pm"])
        b = rows[0]
        fin = _lfjob((rk, b["ez"], b["fz"], n_final))
        ev = {sp: eval_score(*K.span(TTS[rk], sp, tf), b["ez"], paths=True) for sp, tf in K.SPANS}
        fd = {sp: funded_score(*K.span(TTS[rk], sp, tf), b["fz"]) for sp, tf in K.SPANS}
        picks[rk] = {"v": RULES[rk], "ez": b["ez"], "fz": b["fz"], "name": b["name"], "slot": {sp: fin[sp] for sp, _ in K.SPANS}, "eval": ev, "funded": fd,
                     "n_pos_all": sum(1 for r in rows if all(r[sp]["life_pm"] > 0 for sp, _ in K.SPANS)), "n": len(rows)}
        print(f"\n== {rk}: {BG.vname(RULES[rk])}\n   pick (H1 slot $): {b['name']}")
        for sp, _ in K.SPANS:
            e, s, f = ev[sp], fin[sp], fd[sp]
            print(f"   {sp:3s} slot ${s['life_pm']:>5}/mo (p10 ${s['life_p10']}, lose {s['life_lose']}%, funded {s['funded_per_6m']}/6m, evals {s['evals_per_6m']}/6m) | "
                  f"2w {e['p10']}/{e['f10']} dec10 {e['dec10']} 3w {e['p15']}/{e['f15']} 4w {e['p20']}/{e['f20']} med {e['pass_med']} slow {e['slow_pass']}% b2b {e['b2b']} | "
                  f"funded ${f.get('fund_pm')}/mo lost {f.get('fund_lost')}% stuck {f.get('fund_stuck')}%", flush=True)
        print(f"   {picks[rk]['n_pos_all']}/{len(rows)} slot settings make money in H1, H2 and 2021-25")
    json.dump({"evals": E, "slots": LF}, open(os.path.join(OUT, "b25_grid_size.json"), "w"), default=float)
    # eval-only views: best 2-week decided / pass per rule on H1
    ev_best = {}
    for rk in RULES:
        es = [e for e in E if e["rule"] == rk]
        ev_best[rk] = {"max_p10_minus_f10": max(es, key=lambda e: e["H1"]["p10"] - e["H1"]["f10"]),
                       "max_dec10": max(es, key=lambda e: (e["H1"]["dec10"], e["H1"]["p10"]))}
    json.dump({"rules": RULES, "picks": picks, "eval_best": ev_best}, open(os.path.join(OUT, "b25_size.json"), "w"), default=float, indent=1)
    print(f"done in {time.time() - t0:.0f}s")


# ================================================================================================ today's rule: the 25K sizing
def today_eval_specs():
    G = [{"mode": "frac", "f": f, "cap": c} for f, c in itertools.product((0.3, 0.4, 0.5, 0.6, 0.8, 1.0), (450.0, 600.0))]
    for f, s, f2 in itertools.product((0.3, 0.4, 0.5), (4, 5, 6, 8, 10), (0.6, 0.8, 1.0)):
        if f2 > f:
            G.append({"mode": "frac", "f": f, "cap": 600.0, "push": (s, f2)})
    for f, k in itertools.product((0.5, 0.8, 1.0), (2.0, 3.0)):
        G.append({"mode": "need", "f": f, "cap": 600.0, "k": k})
    return G


SPEED = {"dec10": 60.0, "slow_pass": 10.0}       # the owner's rule as a constraint: most evals decided in 2 weeks, few slower than 3


def _fast(e):
    return e["dec10"] >= SPEED["dec10"] and (e["slow_pass"] or 0.0) <= SPEED["slow_pass"]


def cmd_today(procs=3, n_screen=300, n_final=1000, top_e=10):
    """today's rule as account C: eval sizes (frac / push / need) -> the top on H1 -> x funded sizes -> slots; two picks on H1:
    "money" = the highest slot $ / month, "speed" = the highest slot $ among eval sizes that meet SPEED on H1. Then: the pick
    at n_final, today's paper size and the scalp-na-mffu slot size for comparison, neighbours, random directions (8 seeds)."""
    from multiprocessing import Pool
    from tools import blitz25k_grid as BG
    t0 = time.time()
    BG.prep()
    RULES["today"] = {}
    TTS["today"] = K.trades({}, "lit+atlas")
    TTS["today_alone"] = K.trades({}, None)
    RULES["today_alone"] = {}
    jobs = [("today", z) for z in today_eval_specs()]
    with Pool(procs) as P:
        E = P.map(_evjob, jobs, chunksize=4)
    print(f"{len(E)} eval sizes in {time.time() - t0:.0f}s", flush=True)
    key = lambda e: -(e["H1"]["p10"] - e["H1"]["f10"] + 0.25 * e["H1"]["p20"])
    top = sorted(E, key=key)[:top_e]
    top_fast = sorted([e for e in E if _fast(e["H1"])], key=key)[:top_e]
    ez_set = {json.dumps(e["z"], sort_keys=True): e["z"] for e in top + top_fast}
    L = [("today", z, fz, n_screen) for z in ez_set.values() for fz in fund_specs()]
    with Pool(procs) as P:
        LF = P.map(_lfjob, L, chunksize=2)
    print(f"{len(LF)} slots in {time.time() - t0:.0f}s", flush=True)
    evk = {json.dumps(e["z"], sort_keys=True): e for e in E}
    money = max(LF, key=lambda r: r["H1"]["life_pm"])
    fastL = [r for r in LF if _fast(evk[json.dumps(r["ez"], sort_keys=True)]["H1"])]
    speed = max(fastL, key=lambda r: r["H1"]["life_pm"]) if fastL else None
    out = {"evals": E, "picks": {}}
    ref = {"paper (engine/blitz.py: 40% / $600)": ({"mode": "frac", "f": 0.4, "cap": 600.0}, {"mode": "frac", "f": 0.1, "cap": 150.0, "day_tp": 400.0}),
           "scalp-na-mffu slot (60% / $600)": ({"mode": "frac", "f": 0.6, "cap": 600.0}, {"mode": "frac", "f": 0.1, "cap": 150.0, "day_tp": 400.0})}
    todo = {"money": (money["ez"], money["fz"])}
    if speed:
        todo["speed"] = (speed["ez"], speed["fz"])
    todo.update(ref)
    for nm, (ez, fz) in todo.items():
        row = {"ez": ez, "fz": fz, "name": f"eval[{zname(ez)}] funded[{zname(fz)}]"}
        for rk in ("today", "today_alone"):
            fin = _lfjob((rk, ez, fz, n_final))
            row[rk] = {sp: {"slot": fin[sp], "eval": eval_score(*K.span(TTS[rk], sp, tf), ez, paths=True),
                            "funded": funded_score(*K.span(TTS[rk], sp, tf), fz)} for sp, tf in K.SPANS}
        out["picks"][nm] = row
        print(f"\n== {nm}: {row['name']}")
        for rk in ("today", "today_alone"):
            for sp, _ in K.SPANS:
                x = row[rk][sp]
                e, s, f = x["eval"], x["slot"], x["funded"]
                print(f"   {rk[:11]:11s} {sp:3s} slot ${s['life_pm']:>5}/mo (p10 ${s['life_p10']}, lose {s['life_lose']}%, funded {s['funded_per_6m']}/6m, "
                      f"evals {s['evals_per_6m']}/6m, 1st pay {s['first_pay_med']}) | 2w {e['p10']}/{e['f10']} dec10 {e['dec10']} 3w {e['p15']}/{e['f15']} "
                      f"4w {e['p20']}/{e['f20']} med {e['pass_med']} slow {e['slow_pass']}% b2b {e['b2b']} qty {e['med_qty']} | funded ${f.get('fund_pm')}/mo "
                      f"lost {f.get('fund_lost')}% stuck {f.get('fund_stuck')}%", flush=True)
    # neighbours of the money pick (eval knobs one step each way, the same funded size), n_screen
    mz = money["ez"]
    nb = []
    for df in (-0.1, 0.1):
        nb.append({**mz, "f": round(mz["f"] + df, 2)})
    if mz.get("push"):
        s, f2 = mz["push"][0], mz["push"][1]
        nb += [{**mz, "push": (s + ds, f2)} for ds in (-2, 2)] + [{**mz, "push": (s, round(f2 + d2, 2))} for d2 in (-0.2, 0.2)]
    nbr = [_lfjob(("today", z, money["fz"], n_screen)) for z in nb]
    out["neighbours"] = nbr
    print("\n== neighbours of the money pick (same funded size):")
    for r in nbr:
        print(f"   {zname(r['ez']):38s} " + " | ".join(f"{sp} ${r[sp]['life_pm']}/mo" for sp, _ in K.SPANS))
    # random directions on the same signal bars (account C), the money pick's sizes, 8 seeds
    pl = []
    for seed in range(8):
        TTS[f"pl{seed}"] = K.trades({}, "lit+atlas", placebo=seed)
        pl.append(_lfjob((f"pl{seed}", money["ez"], money["fz"], n_screen)))
    out["placebo"] = {sp: {"mean": round(float(np.mean([r[sp]["life_pm"] for r in pl]))), "max": max(r[sp]["life_pm"] for r in pl),
                           "real": out["picks"]["money"]["today"][sp]["slot"]["life_pm"]} for sp, _ in K.SPANS}
    print("\n== random directions (8 seeds), slot $/mo:", out["placebo"])
    out["n_slots_positive_all"] = sum(1 for r in LF if all(r[sp]["life_pm"] > 0 for sp, _ in K.SPANS))
    out["n_slots"] = len(LF)
    print(f"{out['n_slots_positive_all']}/{len(LF)} slot settings make money in H1, H2 and 2021-25")
    json.dump({"evals": E, "slots": LF}, open(os.path.join(OUT, "b25_grid_today.json"), "w"), default=float)
    out.pop("evals")
    json.dump(out, open(os.path.join(OUT, "b25_today_sizing.json"), "w"), default=float, indent=1)
    print(f"done in {time.time() - t0:.0f}s")


def life_hybrid(Te, Tf, S, ez, fz, n=1000, length=126, gap=2, seed=23, plan="25k"):
    """life() with one rule in the eval (trades Te) and another once funded (trades Tf): the same MC paths."""
    be, bf, se, sf = _by(Te), _by(Tf), _stuck(Te), _stuck(Tf)
    price = N.PLANS[plan]["price"]
    nets, funded_n = [], []
    for seq in N.mc_paths(S, n, length, seed=seed):
        cash, nf, wait, acc = -price, 0, 0, Eval(ez, se, plan)
        for d in seq:
            if wait:
                wait -= 1
                continue
            if isinstance(acc, Eval):
                r = acc.step(be.get(d, ()))
                if r == "pass":
                    acc, wait, nf = N.Funded(plan, fz, sf), gap, nf + 1
                elif r in ("fail", "stuck"):
                    cash -= price
                    acc = Eval(ez, se, plan)
            else:
                cash += acc.step(bf.get(d, ()))
                if acc.done:
                    cash -= price
                    acc = Eval(ez, se, plan)
        nets.append(cash / (length / 21.0))
        funded_n.append(nf)
    a = np.array(nets)
    return {"life_pm": round(float(a.mean())), "life_p10": round(float(np.percentile(a, 10))), "life_lose": round(100.0 * float((a < 0).mean()), 1),
            "funded_per_6m": round(float(np.mean(funded_n)), 2)}


def _hyjob(a):
    fk, fz, n = a
    out = {"funded_rule": fk, "fz": fz, "name": f"funded rule {fk} [{zname(fz)}]"}
    for sp, tf in K.SPANS:
        Te, S = K.span(TTS["today"], sp, tf)
        Tf, _ = K.span(TTS[fk], sp, tf)
        out[sp] = life_hybrid(Te, Tf, S, EZ_PICK, fz, n=n)
    return out


EZ_PICK = {"mode": "frac", "f": 0.4, "cap": 600.0, "push": (5, 1.0)}


def cmd_hybrid(procs=3, n_screen=300, n_final=1000):
    """new idea: today's rule in the eval (the pick's size), a structure-management rule once FUNDED (less stuck at the floor?).
    The funded rule = the stage-3 rule with the best H1 funded $ a month at today's funded size (1 micro, +$400 day stop);
    then the funded size picked on H1 slot $; H2 / 2021-25 = the check, against today's rule funded too."""
    from multiprocessing import Pool
    from tools import blitz25k_grid as BG
    t0 = time.time()
    BG.prep()
    R = load_rules()
    fz0 = {"mode": "frac", "f": 0.1, "cap": 150.0, "day_tp": 400.0}
    TTS["today"] = K.trades({}, "lit+atlas")
    fund = {}
    for rk, v in R.items():
        TTS[rk] = TTS["today"] if rk == "today" else K.trades(v, "lit+atlas")
        fund[rk] = {sp: funded_score(*K.span(TTS[rk], sp, tf), fz0) for sp, tf in K.SPANS}
        print(f"{rk:14s} {BG.vname(v):62s} funded at 1 micro: " + " | ".join(f"{sp} ${fund[rk][sp].get('fund_pm')}/mo stuck {fund[rk][sp].get('fund_stuck')}%"
                                                                          for sp, _ in K.SPANS), flush=True)
    fk = max((k for k in R if k != "today"), key=lambda k: fund[k]["H1"].get("fund_pm", -1))
    print("funded rule picked on H1:", fk, BG.vname(R[fk]), flush=True)
    jobs = [(k, fz, n_screen) for k in ("today", fk) for fz in fund_specs()]
    with Pool(procs) as P:
        H = P.map(_hyjob, jobs, chunksize=2)
    best = {k: max((h for h in H if h["funded_rule"] == k), key=lambda h: h["H1"]["life_pm"]) for k in ("today", fk)}
    out = {"funded_at_1_micro": fund, "funded_rule": fk, "funded_rule_v": R[fk], "rows": H, "final": {}}
    for k, b in best.items():
        fin = _hyjob((k, b["fz"], n_final))
        out["final"][k] = fin
        print(f"== eval today's rule (push), funded {k}: {zname(b['fz'])}: " + " | ".join(f"{sp} slot ${fin[sp]['life_pm']}/mo lose {fin[sp]['life_lose']}% "
                                                                                       f"funded {fin[sp]['funded_per_6m']}/6m" for sp, _ in K.SPANS), flush=True)
    out["n_better_all"] = sum(1 for h in H if h["funded_rule"] == fk and all(h[sp]["life_pm"] > best["today"][sp]["life_pm"] for sp, _ in K.SPANS))
    print(f"{out['n_better_all']} of {len(fund_specs())} funded sizes of the hybrid beat today's best slot in all three spans; {time.time() - t0:.0f}s")
    json.dump(out, open(os.path.join(OUT, "b25_hybrid.json"), "w"), default=float, indent=1)


def cmd_table(n=1000):
    """the eval-speed / money frontier of today's rule as account C: a few eval sizes, the same funded size (the pick's), all at
    n paths -> b25_size_table.json (the write-up's table)."""
    from tools import blitz25k_grid as BG
    BG.prep()
    TTS["today"] = K.trades({}, "lit+atlas")
    fz = {"mode": "frac", "f": 0.1, "cap": 150.0, "day_tp": 400.0}
    rows = []
    for lab, ez in (("40% of the room, <= $600 (today's paper size)", {"mode": "frac", "f": 0.4, "cap": 600.0}),
                    ("60% of the room, <= $600 (scalp-na-mffu slot)", {"mode": "frac", "f": 0.6, "cap": 600.0}),
                    ("100% of the room, <= $600", {"mode": "frac", "f": 1.0, "cap": 600.0}),
                    ("40%, then 100% from session 5 (pick)", {"mode": "frac", "f": 0.4, "cap": 600.0, "push": (5, 1.0)}),
                    ("40%, then 100% from session 8", {"mode": "frac", "f": 0.4, "cap": 600.0, "push": (8, 1.0)}),
                    ("50%, no new trade after -$250 on the day", {"mode": "frac", "f": 0.5, "cap": 600.0, "day_loss": 250.0}),
                    ("need: what is left to pass / 2, <= 80% of the room", {"mode": "need", "f": 0.8, "cap": 600.0, "k": 2.0})):
        r = {"label": lab, "ez": ez, "fz": fz}
        for sp, tf in K.SPANS:
            T, S = K.span(TTS["today"], sp, tf)
            r[sp] = {"eval": eval_score(T, S, ez, paths=True), "slot": life(T, S, ez, fz, n=n)}
        rows.append(r)
        print(f"{lab:52s} " + " | ".join(f"{sp} 2w {r[sp]['eval']['p10']}/{r[sp]['eval']['f10']} dec {r[sp]['eval']['dec10']} slow {r[sp]['eval']['slow_pass']} "
                                          f"med {r[sp]['eval']['pass_med']} slot ${r[sp]['slot']['life_pm']}" for sp, _ in K.SPANS), flush=True)
    json.dump(rows, open(os.path.join(OUT, "b25_size_table.json"), "w"), default=float, indent=1)


if __name__ == "__main__":
    a = sys.argv[1:]
    {"selfcheck": cmd_selfcheck, "grid": cmd_grid, "today": cmd_today, "table": cmd_table, "hybrid": cmd_hybrid}[a[0] if a else "selfcheck"]()
