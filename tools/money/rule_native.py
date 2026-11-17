"""Rule-native search (2026-11-17): pick by what MFFU pays on, not by PF / net $. PAPER RESEARCH ONLY: reads stored trades and
CME NQ1! bars (data/NQ_1m.csv 2026, data/NQ_5m.csv 2021-25), writes research/lab/rule_native.json, changes nothing live.
Write-up: research/writeups/rule-native-2026-11-17.md.

Why: MFFU pays on WINNING DAYS. Rapid EOD eval = best day <= 30% of the profit (4+ days); its funded account pays daily above
the $2,100 buffer. Builder funded = best day <= 50% of the cycle, $2,600 above start for the first payout. LIT is lumpy (about
2.5 trades a week, 8R winners), which fights these rules. So every variant here is scored by the owner's two numbers:
  * days until the FIRST payout (median over ALL 6-month paths from the day the eval is bought; "never" counts as never), and
  * P(no payout in 6 months),
plus $ a month after fees, on MFFU Rapid EOD 50K and Builder 50K, with the same Monte Carlo paths as
tools/money/stack_one_account.py / rapid_levers.py (eval 2,000 x 60, slot 1,000 x 126, 5-session blocks, seeds 7 / 23).

Base rows (today's plan, STATE.md 2026-11-17):
  Rapid EOD 50K  LIT + ATLAS $500 from day one, the 30% best-day size guard in the eval, funded keeps $1,000 above the buffer.
  Builder 50K    LIT eval (live two_week), then LIT + ATLAS $500 once funded (stack-one-account candidate; LIT alone shown too).

Variant families (all on stored trades; costs $1.90 a micro + 1 tick are in the stored prices; stops unchanged = 1 tick beyond
the sweep / structure extreme, size follows the stop):
  A  LIT second, smaller target: take a share p of the position at k x R (limit, no slip), the rest runs the live plan
     (BE + costs, 15-min check, VIX-band target banked at 8R). Hit = a bar AFTER the entry bar reached it before the exit
     (the exit bar counts only for winners). Scopes: everywhere, or only where the consistency rule bites (Rapid: the eval;
     Builder: the funded account). The Rapid 30% guard sizes on the smaller max win (the bot knows its plan).
  B  ATLAS high-win-rate: half off at 1R, or a fixed 1R target.
  C  a scalp layer: BLITZ (the noise-area scalp, never opposite LIT / ATLAS) at $300, first signal of the day only (2-8 a
     week), with its live exit, a fixed 1R or 0.5R target (high win rate); all signals shown as a reference (> 8 a week).
  D  daily profit lock for the add-ons: no new ATLAS / BLITZ entry once the day is up $300 / $600 (LIT untouched).
  alone rows: the scalp layer alone on its own account.
Verdict rule ("rule-native pass"), against the base row, in BOTH Jan-Jun (pick) and Jul-Oct 2026 (check):
  median days to the first payout earlier by more than the seed noise (or equal and P(no pay) >= 1 point lower), P(no pay) no
  worse than +1 point, $ a month no more than 10% lower; and in 2021-25: the trades at fixed $ do not lose money and the slot
  $ a month is no more than $25 below the base. The new layer itself must trade 2-8 times a week.
Chance check: the base row re-run on two other seed pairs gives the Monte Carlo noise; the count of H1 winners that also win
H2 is compared with the coin-flip expectation (half of them).

    python -X utf8 tools/money/rule_native.py            # all -> research/lab/rule_native.json (~25 min on 4 cores)
    python -X utf8 tools/money/rule_native.py --n 200    # quicker
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import multiprocessing as mp
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
import rapid_levers as RL  # noqa: E402
import account4_sim as A4  # noqa: E402
import uprisk as U  # noqa: E402
from engine import firms as FM  # noqa: E402

PV, COMM, SLIP = SOA.PV, SOA.COMM, SOA.SLIP
OUT = os.path.join(ROOT, "research", "lab", "rule_native.json")
SPANS, LEN, H_EVAL, MO = SOA.SPANS, SOA.LEN, SOA.H_EVAL, SOA.MO
DAYS_PER_SESSION = 7.0 / 5.0
NEVER = 999


# ================================================================================================ the two hooks (patched in)
_stack_q0, _cons_cap0 = SOA.stack_q, SOA.cons_cap


def stack_q(t, z, room, cum, maxq, dll=SOA.SOFT_DLL):
    """stack_one_account.stack_q + family D: no new add-on entry once the day is up z["_lock"] $."""
    lk = z.get("_lock")
    if lk is not None and cum >= lk:
        return 0
    return _stack_q0(t, z, room, cum, maxq, dll)


def cons_cap(q, t, cons, tgt, cum):
    """The fleet's best-day guard on the trade's planned max win (t["tg"] = the smaller max win of a partial plan)."""
    if "tg" in t:
        t = {**t, "tgt": t["tg"]}
    return _cons_cap0(q, t, cons, tgt, cum)


SOA.stack_q, SOA.cons_cap = stack_q, cons_cap


# ================================================================================================ MFE from the bars
_B = {}


def bars(tf):
    if tf not in _B:
        import pandas as pd
        b = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv" if tf == 1 else "NQ_5m.csv"))
        _B[tf] = (b["time"].to_numpy(np.int64), b["open"].to_numpy(float), b["high"].to_numpy(float), b["low"].to_numpy(float))
    return _B[tf]


def _mfe(e, d, t0, t1, tf, win, include_first):
    """Best favourable points (dir space) on bars after the entry up to the exit bar (the exit bar only for a winner)."""
    T, O, H, L = bars(tf)
    s = tf * 60
    k0 = int(np.searchsorted(T, t0 - (t0 % s)))
    kx = int(np.searchsorted(T, t1 - (t1 % s)))
    a = k0 if include_first else k0 + 1
    b = kx + 1 if win else kx
    if b <= a:
        return 0.0
    return float((H[a:b].max() - e) if d > 0 else (e - L[a:b].min()))


_M = {}


def mfe_map():
    """(strat, entry_t, dir) -> MFE points. LIT: ledger entry price; ATLAS: entry from the stored path (po); BLITZ: mfe_pts."""
    if _M:
        return _M
    with open(os.path.join(U.HO, "COMPLETE_TRADE_LEDGER.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if not r["trade_id"].startswith(("T-2026", "REF-")):
                continue
            d = 1 if r["direction"] == "long" else -1
            e, x = float(r["entry_price"]), float(r["exit_price"])
            t0 = int(dt.datetime.fromisoformat(r["entry_fill_at"][:25]).timestamp())
            t1 = int(dt.datetime.fromisoformat(r["exit_time"][:25]).timestamp())
            tf = 5 if r["trade_id"].startswith("REF") else 1
            _M[("LIT", t0, d)] = _mfe(e, d, t0, t1, tf, (x - e) * d > 0, False)
    from tools import atlas as A
    T1 = bars(1)[0]
    for u in A.account_units(A.BASE):
        pt = u["pt"]
        if not len(pt):
            continue
        k1 = int(np.searchsorted(T1, int(pt[0])))
        tf = 1 if u["day"] >= "2026-01-01" and k1 < len(T1) and T1[k1] == pt[0] else 5
        T, O, _, _ = bars(tf)
        k = int(np.searchsorted(T, int(pt[0])))
        if k >= len(T) or T[k] != pt[0]:
            continue
        d = int(u["dir"])
        e = (O[k] * d - float(u["po"][0])) * d
        _M[("ATLAS", int(u["entry_t"]), d)] = _mfe(e, d, int(pt[0]), int(u["exit_t"]), tf, float(u["pts"]) > 0, True)
    from tools import blitz25k_lib as BL
    for tf, TT in BL.trades(None, "lit+atlas").items():
        for t in TT:
            if (t["day"] >= "2026-01-01") != (tf == 1):
                continue
            _M[("BLITZ", int(t["entry_t"]), int(t["dir"]))] = float(t["mfe_pts"])
    return _M


# ================================================================================================ trade transforms
def tx_trade(t, rule):
    """rule = ("part", p, k): p of the position off at k x R | ("fixed", k): the whole trade out at k x R."""
    m = mfe_map().get((t["strat"], int(t["entry_t"]), int(t["dir"])))
    r = float(t["risk"])
    full = float(t["tgt"]) if t.get("tgt") else None
    if rule[0] == "part":
        _, p, k = rule
        o = {**t, "tg": p * k * r + (1 - p) * (full if full else 2.0 * r)}
        if m is not None and m >= k * r - 1e-9 and (full is None or k * r < full):
            o["pts"] = p * k * r + (1 - p) * float(t["pts"])
            o["part_hit"] = True
        return o
    _, k = rule
    o = {**t, "tgt": k * r}
    if m is not None and m >= k * r - 1e-9:
        o["pts"] = k * r
    return o


def transform(BY, rules=None, per_day=None):
    """Per-session trade lists with the rules applied ({strat: rule}); per_day = {strat: max trades a day} (its first ones)."""
    rules, per_day = rules or {}, dict(per_day or {})
    out = []
    for ts in BY:
        seen, row = {}, []
        for t in ts:
            s = t["strat"]
            if s in per_day:
                if seen.get(s, 0) >= per_day[s]:
                    continue
                seen[s] = seen.get(s, 0) + 1
            row.append(tx_trade(t, rules[s]) if s in rules else t)
        out.append(row)
    return out


# ================================================================================================ the variants
L, LA, LAB = ("LIT",), ("LIT", "ATLAS"), ("LIT", "ATLAS", "BLITZ")


def V(name, fam, kind, me, mf, z, rules=None, scope="both", first=None, layer=None):
    """kind rapid | builder; me / mf = eval / funded strategies; z = add-on sizing (+ "_lock"); rules = {strat: rule};
    scope both | eval | funded = where the rules apply; first = {strat: max trades a day};
    layer = the new layer's strategy (its own trades/week + 2021-25 checks)."""
    return {"name": name, "fam": fam, "kind": kind, "me": me, "mf": mf, "z": z, "rules": rules or {}, "scope": scope,
            "first": first or {}, "layer": layer}


def variants():
    a5 = RL.Z(ATLAS=500)
    ab = RL.Z(ATLAS=500, BLITZ=300)
    out = []
    for kind in ("rapid", "builder"):
        me = LA if kind == "rapid" else L
        rule_scope = "eval" if kind == "rapid" else "funded"
        out.append(V("base", "base", kind, me, LA, a5))
        out.append(V("LIT alone", "ref", kind, L, L, {}))
        for p, k in ((0.5, 1.0), (0.5, 2.0), (0.5, 3.0), (1 / 3, 2.0)):
            pk = f"{round(p * 100)}% at {k:g}R"
            out.append(V(f"A LIT {pk}, everywhere", "A", kind, me, LA, a5, {"LIT": ("part", p, k)}, "both"))
            out.append(V(f"A LIT {pk}, {rule_scope} only", "A", kind, me, LA, a5, {"LIT": ("part", p, k)}, rule_scope))
        out.append(V("B ATLAS half at 1R", "B", kind, me, LA, a5, {"ATLAS": ("part", 0.5, 1.0)}, "both"))
        out.append(V("B ATLAS fixed 1R", "B", kind, me, LA, a5, {"ATLAS": ("fixed", 1.0)}, "both"))
        mfb = LAB
        meb = LAB if kind == "rapid" else L
        for nm, rl in (("live exit", None), ("fixed 1R", ("fixed", 1.0)), ("fixed 0.5R", ("fixed", 0.5))):
            out.append(V(f"C + BLITZ $300 first a day, {nm}", "C", kind, meb, mfb, ab, {"BLITZ": rl} if rl else {}, "both",
                         first={"BLITZ": 1}, layer="BLITZ"))
        for m in (2, 3):
            out.append(V(f"C + BLITZ $300 max {m} a day, live exit", "C", kind, meb, mfb, ab, first={"BLITZ": m}, layer="BLITZ"))
        out.append(V("C + BLITZ $300 every signal (ref, >8/wk)", "Cref", kind, meb, mfb, ab, layer="BLITZ"))
        for x in (300, 600):
            out.append(V(f"D add-on lock at +${x}", "D", kind, me, LA, {**a5, "_lock": float(x)}))
        out.append(V("alone: BLITZ $300 first a day, fixed 1R", "alone", kind, ("BLITZ",), ("BLITZ",), RL.Z(BLITZ=300),
                     {"BLITZ": ("fixed", 1.0)}, "both", first={"BLITZ": 1}, layer="BLITZ"))
        out.append(V("alone: ATLAS $500", "alone", kind, ("ATLAS",), ("ATLAS",), a5, layer="ATLAS"))
    return out


# ================================================================================================ scoring
def _lists(v):
    mix = RL.mix_by
    eb, fb = mix(v["me"]), mix(v["mf"], news=(v["kind"] == "rapid"))
    re_ = v["rules"] if v["scope"] in ("both", "eval") else {}
    rf = v["rules"] if v["scope"] in ("both", "funded") else {}
    return transform(eb, re_, v["first"]), transform(fb, rf, v["first"])


def spec(v):
    BYe, BYf = _lists(v)
    if v["kind"] == "rapid":
        sp = RL.acct(v["me"], v["mf"], v["z"], cap="guard", pol=("cushion", 1000))
        sp["BYe"], sp["BYf"] = BYe, BYf
        return sp
    sp = SOA.plan("builder", v["z"])
    sp["BYe"], sp["BYf"] = BYe, BYf
    return sp


def slot_paths(v, sp, paths):
    """-> per path: (first payout session or NEVER, owner $ - fees $)."""
    out = []
    if v["kind"] == "rapid":
        for g in RL.run_group([sp], paths):
            s = g[0]
            out.append((s.first_pay or NEVER, s.owner - s.cost))
        return out
    for seq in paths:
        s = SOA.Slot(sp)
        for k, si in enumerate(seq[:LEN]):
            s.step(k, sp["BYe"][si] if s.e is not None else sp["BYf"][si])
        o = s.out()
        out.append((o["first_pay"] or NEVER, o["net"]))
    return out


def eval_score(v, sp, paths):
    res = []
    for seq in paths:
        e = sp["ev"]() if v["kind"] == "rapid" else SOA.Ev(sp["ecfg"], sp["E"], sp["z"])
        out, used = "open", len(seq[:H_EVAL])
        for k, si in enumerate(seq[:H_EVAL]):
            r, _ = e.step(sp["BYe"][si])
            if r:
                out, used = ("pass" if r == "pass" else "fail"), k + 1
                break
        res.append((out, used))
    n = len(res)
    pas = [u for o, u in res if o == "pass"]
    return {"pass_med": float(np.median(pas)) if pas else None, "p60": round(100.0 * len(pas) / n, 1),
            "p10": round(100.0 * sum(1 for u in pas if u <= 10) / n, 1),
            "f10": round(100.0 * sum(1 for o, u in res if o == "fail" and u <= 10) / n, 1)}


def rule_score(P):
    f = np.array([x[0] for x in P], float)
    net = np.array([x[1] for x in P], float)
    med = float(np.median(f))
    return {"first_med_s": None if med >= NEVER else med, "first_med_days": None if med >= NEVER else round(med * DAYS_PER_SESSION),
            "p_no_pay": round(100.0 * float((f >= NEVER).mean()), 1), "p_pay_30d": round(100.0 * float((f <= 21).mean()), 1),
            "per_month": round(float(net.mean()) / MO)}


def plain(BY, span, z):
    """The real days of the span in order, fixed $ a trade (LIT $500, ATLAS / BLITZ their z $), costs in."""
    usd = {"LIT": 500.0}
    for k, s in z.items():
        if isinstance(s, dict):
            usd[k] = float(s["usd"])
    S = SOA.data()["S"]
    a, b = U.span_ix(S, span)
    pnl, days, wins = [], [], 0
    for si in range(a, b):
        d = 0.0
        for t in BY[si]:
            q = max(1, int(usd.get(t["strat"], 500.0) // ((t["risk"] + SLIP) * PV + COMM)))
            p = t["pts"] * PV * q - COMM * q
            pnl.append(p)
            d += p
        days.append(d)
    p = np.array(pnl) if pnl else np.zeros(1)
    eq = np.cumsum(days)
    gl = -p[p < 0].sum()
    ns = b - a
    return {"trades": len(pnl), "tpw": round(len(pnl) / (ns / 5.0), 2), "win": round(100.0 * float((p > 0).mean()), 1),
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum())),
            "per_month": round(float(p.sum()) / (ns / 21.0)),
            "max_dd": round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())),
            "win_days_pw": round(sum(1 for x in days if x > 0) / (ns / 5.0), 2)}


_PATHS = {}


def paths(n, seeds=(A4.SEED_EVAL, A4.SEED_LIFE)):
    key = (n, seeds)
    if key not in _PATHS:
        S = SOA.data()["S"]
        _PATHS[key] = ({s: U.mc_paths(S, s, 2 * n, length=H_EVAL, seed=seeds[0]) for s in SPANS},
                       {s: U.mc_paths(S, s, n, length=LEN, seed=seeds[1]) for s in SPANS})
    return _PATHS[key]


def score(args):
    v, n, seeds = args
    t0 = time.time()
    PE, PF = paths(n, seeds)
    sp = spec(v)
    o = {"v": {k: v[k] for k in ("name", "fam", "kind", "scope", "layer")}}
    BYp = sp["BYe"] if v["scope"] == "eval" else sp["BYf"]
    for s in SPANS:
        pp = slot_paths(v, sp, PF[s])
        r = {"eval": eval_score(v, sp, PE[s]), "rule": rule_score(pp), "plain": plain(BYp, s, v["z"]), "_pp": pp}
        if v["layer"]:
            r["layer"] = plain([[t for t in ts if t["strat"] == v["layer"]] for ts in BYp], s, v["z"])
        hits = [t for ts in BYp[slice(*U.span_ix(SOA.data()["S"], s))] for t in ts if t.get("part_hit")]
        r["part_hits"] = len(hits)
        o[s] = r
    o["secs"] = round(time.time() - t0)
    return o


# ================================================================================================ verdict
def noise(n, pool):
    """The base rows on two other seed pairs: the Monte Carlo spread of the rule-native numbers."""
    base = [v for v in variants() if v["fam"] == "base"]
    jobs = [(v, n, sd) for sd in ((8, 24), (9, 25)) for v in base]
    R = pool.map(score, jobs) if pool else list(map(score, jobs))
    out = {}
    for r in R:
        out.setdefault(r["v"]["kind"], []).append(r)
    return out


def paired(a, b):
    """Same paths: variant a vs base b. Mean first-payout session (never = 127) difference and P(no pay) difference, +- 1 SE."""
    fa = np.minimum(np.array([x[0] for x in a], float), LEN + 1)
    fb = np.minimum(np.array([x[0] for x in b], float), LEN + 1)
    d = fa - fb
    na, nb = (fa > LEN).astype(float), (fb > LEN).astype(float)
    dn = 100.0 * (na - nb)
    n = len(d)
    return {"first_diff_s": round(float(d.mean()), 2), "first_se": round(float(d.std(ddof=1) / math.sqrt(n)), 2),
            "nopay_diff": round(float(dn.mean()), 2), "nopay_se": round(float(dn.std(ddof=1) / math.sqrt(n)), 2),
            "earlier_2se": bool(d.mean() < -2 * d.std(ddof=1) / math.sqrt(n))}


def verdict(res, nz):
    """res: kind -> name -> score. A variant passes when it beats the base in BOTH 2026 halves on the rule-native numbers and
    holds in 2021-25 (see the module doc)."""
    v, bands = {}, {}
    for kind, rows in res.items():
        b = rows["base"]
        band = bands[kind] = {}
        for s in ("H1", "H2"):
            m = [x[s]["rule"]["first_med_s"] or NEVER for x in nz.get(kind, [])] + [b[s]["rule"]["first_med_s"] or NEVER]
            pn = [x[s]["rule"]["p_no_pay"] for x in nz.get(kind, [])] + [b[s]["rule"]["p_no_pay"]]
            band[s] = {"first": max(1.0, float(max(m) - min(m))), "nopay": max(1.0, float(max(pn) - min(pn)))}
        for name, r in rows.items():
            if name == "base":
                continue
            chk = {}
            for s in ("H1", "H2"):
                a, c = r[s]["rule"], b[s]["rule"]
                fa, fc = a["first_med_s"] or NEVER, c["first_med_s"] or NEVER
                earlier = (fc - fa) > band[s]["first"] or (fa <= fc and c["p_no_pay"] - a["p_no_pay"] >= band[s]["nopay"])
                chk[s] = {"earlier": bool(earlier), "no_pay_ok": a["p_no_pay"] <= c["p_no_pay"] + band[s]["nopay"],
                          "money_ok": a["per_month"] >= c["per_month"] - 0.10 * abs(c["per_month"])}
            ref = r["REF"]
            chk["REF"] = {"trades_not_losing": (ref.get("layer") or ref["plain"])["net"] >= 0,
                          "slot_ok": ref["rule"]["per_month"] >= b["REF"]["rule"]["per_month"] - 25}
            if r["v"]["layer"]:
                chk["REF"]["layer_2_8_wk"] = all(2.0 <= r[s]["layer"]["tpw"] <= 8.0 for s in SPANS)
            h1_win = all(chk["H1"].values())
            ok = all(all(c.values()) for c in chk.values())
            pr = {s: paired(r[s]["_pp"], b[s]["_pp"]) for s in SPANS}
            v[f"{kind}: {name}"] = {"pass": ok, "h1_win": h1_win, "h2_win": all(chk["H2"].values()), "checks": chk, "paired": pr,
                                    "paired_earlier_both": pr["H1"]["earlier_2se"] and pr["H2"]["earlier_2se"]}
    return v, bands


def chance(vd):
    """Of the variants that win on Jan-Jun, how many also win on Jul-Oct, vs a coin flip (half)."""
    out = {}
    for kind in ("rapid", "builder"):
        rows = {k: x for k, x in vd.items() if k.startswith(kind) and "alone" not in k and "LIT alone" not in k}
        h1 = [k for k, x in rows.items() if x["h1_win"]]
        both = [k for k in h1 if rows[k]["h2_win"]]
        out[kind] = {"tested": len(rows), "h1_winners": len(h1), "also_h2": len(both), "coin_flip_expect": round(len(h1) / 2.0, 1),
                     "h2_winners_any": sum(1 for x in rows.values() if x["h2_win"]),
                     "paired_earlier_h1": sum(1 for x in rows.values() if x["paired"]["H1"]["earlier_2se"]),
                     "paired_earlier_both": sum(1 for x in rows.values() if x["paired_earlier_both"])}
    return out


def study(n=1000, procs=4, log=print):
    SOA.data()
    RL.streams()
    mfe_map()
    VV = variants()
    for v in VV:
        _lists(v)                                   # warm the caches before the fork
    paths(n)
    jobs = [(v, n, (A4.SEED_EVAL, A4.SEED_LIFE)) for v in VV]
    ctx = mp.get_context("fork")
    with ctx.Pool(procs) as pool:
        R = []
        for r in pool.imap(score, jobs):
            R.append(r)
            log(f"{r['v']['kind']:7s} {r['v']['name']:48s} " + " | ".join(
                f"{s} 1st {r[s]['rule']['first_med_days']}d nopay {r[s]['rule']['p_no_pay']}% ${r[s]['rule']['per_month']}"
                for s in SPANS) + f"  ({r['secs']}s)")
        nz = noise(n, pool)
    res = {}
    for r in R:
        res.setdefault(r["v"]["kind"], {})[r["v"]["name"]] = r
    vd, band = verdict(res, nz)
    for rows in res.values():
        for r in rows.values():
            for sp_ in SPANS:
                r[sp_].pop("_pp", None)
    return {"date": "2026-11-17", "n": n, "spans": U.SPAN, "results": res,
            "noise": {k: [{s: x[s]["rule"] for s in SPANS} for x in xs] for k, xs in nz.items()}, "noise_band": band,
            "verdict": vd, "chance": chance(vd)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.time()
    out = study(a.n, a.procs)
    for k, x in out["verdict"].items():
        bad = [f"{s}.{c}" for s, cc in x["checks"].items() for c, ok in cc.items() if not ok]
        pr = x["paired"]
        print(f"{k:60s} {'PASS' if x['pass'] else 'no: ' + ', '.join(bad)}  | paired 1st H1 {pr['H1']['first_diff_s']:+.1f}+-{pr['H1']['first_se']} "
              f"H2 {pr['H2']['first_diff_s']:+.1f}+-{pr['H2']['first_se']} nopay {pr['H1']['nopay_diff']:+.1f}/{pr['H2']['nopay_diff']:+.1f}")
    print("chance:", json.dumps(out["chance"]))
    if not a.no_save:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=float)
        print("wrote", os.path.relpath(OUT, ROOT))
    print(f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
