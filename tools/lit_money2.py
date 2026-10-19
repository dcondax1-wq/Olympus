"""LIT money batch 2 (2026-10-19): seven sizing / cost / management ideas, judged by the LIT rule (2026 only; pick on Jan-Jun = H1,
check on Jul-Oct = H2; adopt-candidate only if net $ rises in BOTH halves and MFFU 50K 2-week fails do not rise meaningfully;
costs in; live sizing two_week for 10 sessions then safe_eval, no reset). Write-up: research/writeups/lit-money-batch2.md.

  1 minis    when an order is >= 10 micros, route floor(q/10) NQ minis + the rest in MNQ: re-cost every trade (MFFU NQ round turn
             $4.68 vs 10 x $1.90 = $19.00 for the same exposure); same points, same fills
  2 add2     a second add on top of the scale_in candidate (lit-big-ideas.md): once the 1st add is +1 of its own risk (the stop
             has moved to the 1st add's price), the next 1m pullback >= pb2 R and a 1m CISD close -> add at the next 1m open;
             same caps (open risk of the adds <= the 1st entry's $ risk / 60% room / soft daily loss; 40 micros in all)
  3 m15      15m LIT setups (tools/lit_more.py m15) only during eval sessions 1-10, at x1 / x0.5 / x0.25 of the two_week size,
             1 a day first fill, or "5m keeps its trade" (15m may trade too, max 1 a day per timeframe)
  6 lock     profit lock in steps: once the trade's high reaches entry + X R, the stop moves to entry + Y R (one step, not a trail);
             all sessions or the two_week phase only
  7 tod      size tilt London (entry < 08:00 ET) vs New York (>= 08:00 ET); all sessions or the safe_eval phase only
  4/5        funded compounding and payout policy: tools/lit_money2.py funded (MFFU Builder 50K funded as tools/lit_funded.py)

Executor: tools/lit_big_ideas.py / tools/lit_adv_manage.py (engine/lit.py on live_model.json "lit"; options off == the 120 live
2026 trades == run lit_live). Fills on true 1m bars, stop before target in a bar, stop / BE / lock exits 1 tick worse, adds at
the next 1m open + 1 tick. Edits no engine file.

  python -X utf8 tools/lit_money2.py check     # off == live (eval scorer and the lock / add2 simulators)
  python -X utf8 tools/lit_money2.py grid      # ideas 1 2 3 6 7 -> research/lit/money2.json
  python -X utf8 tools/lit_money2.py funded    # ideas 4 5 -> research/lit/money2_funded.json
  python -X utf8 tools/lit_money2.py save      # rl.save the runs lit_m2_*
Paper only.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from tools import lit_big_ideas as BI  # noqa: E402
from tools import lit_adv_manage as A  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "money2.json")
OUT_F = os.path.join(ROOT, "research", "lit", "money2_funded.json")
PV, SLIP = A.PV, A.SLIP
ECOMM = A.ECOMM                       # $1.90 MNQ round turn (MFFU)
C_NQ = 4.68                           # MFFU NQ round turn (search 2026-10-19, unconfirmed: see the write-up); sens. 4.36 / 5.76
DLL = A.A50["dll"]
ET = ZoneInfo("America/New_York")
RES = {}
G = {"comm": None, "m15_until": None, "m15_mode": "first", "alt_until": None, "mfun": None, "true_low": False}


def _dump():
    json.dump(RES, open(OUT, "w"), indent=1, default=float)


# ================================================================================================ commissions
def comm_micro(q):
    return ECOMM * q


def comm_minis(c_nq=C_NQ, at=10):
    def f(q):
        q = int(q)
        n = q // 10 if q >= at else 0
        return n * c_nq + (q - 10 * n) * ECOMM
    return f


def _comm(q):
    return (G["comm"] or comm_micro)(q)


# ================================================================================================ eval with hooks
def trade_pnl(t, q, qfull, st):
    """lit_big_ideas.trade_pnl with the commission hook and a separate size for the 2nd add (t["add_f2"])."""
    adds = t.get("adds")
    if not adds:
        g = A.leg_pnl(t, q) + ECOMM * q            # gross (leg_pnl takes off $1.90 x q)
        pnl = g - _comm(q)
        return pnl, min(0.0, t["w1"] * PV * q - _comm(q), pnl), q
    f1 = t.get("add_f", 1.0)
    qa = SZ.scale_in_qty(q, qfull, t["risk"], adds[:1], f=f1, state=st)
    if len(adds) > 1:                                # gated 2nd add: the 1st add's stop is at its price -> 0 open risk
        qa += SZ.scale_in_qty(q + qa[0], qfull, t["risk"], [dict(adds[1], prev_rk=[])], f=t.get("add_f2", f1), state=st)
    tot = q + sum(qa)
    g = q * t["pts"] * PV
    lows = [q * t["w_pre"] * PV]
    for i, a in enumerate(adds):
        g += qa[i] * a["pts"] * PV
        w = a["w_ph"] if not G["true_low"] or a.get("tw") is None else a["tw"]
        lows.append((q * w + sum(qq * (w - b["dist"]) for qq, b in zip(qa[:i + 1], adds))) * PV)
    c = _comm(q) + sum(_comm(x) for x in qa if x)
    pnl = g - c
    return pnl, min(0.0, min(lows) - c, pnl), tot


def _cap(t, st):
    return BI._cap(t, st)


def run_eval_g(seq, by, horizon=20, keep=None, cfg=None):
    """lit_big_ideas.run_eval_x + hooks: commission (G comm), 15m trades only in sessions <= G m15_until (1 a day first fill,
    or 1 per timeframe), t["alt"] used in sessions <= G alt_until, a size function G mfun(t, session) -> multiplier."""
    cfg = cfg or A.CFG
    tgt, mll, dll, lockv = A.A50["target"], A.A50["mll"], A.A50["dll"], A.A50["lock"]
    bal = peak = 0.0
    floor = -mll
    for kk, si in enumerate(seq[:horizon]):
        cum = 0.0
        sess = kk + 1
        taken, busy = collections.Counter(), -1
        for t in by[si]:
            if cum <= -dll:
                break
            src = t.get("src", "m5")
            if src == "m15":
                if not G["m15_until"] or sess > G["m15_until"]:
                    continue
            if t["entry_t"] < busy:
                continue
            if G["m15_mode"] == "first" and sum(taken.values()) >= 1:
                continue
            if taken[src] >= 1:
                continue
            if t.get("alt") is not None and G["alt_until"] and sess <= G["alt_until"]:
                t = t["alt"]
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": sess, "n_today": 0}
            m0 = lit.qty_for(t["risk"])
            q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, cfg, room=st["room"], state=st,
                           learning=None)["qty"] if m0 else 0
            if q <= 0:
                continue
            qfull = q
            m = float(t.get("m", 1.0))
            if G["mfun"]:
                m *= G["mfun"](t, sess)
            if m < 1.0 - 1e-9:
                q = max(1, int(q * m + 1e-9))
            elif m > 1.0 + 1e-9:
                q = max(q, min(int(q * m + 1e-9), _cap(t, st)))
            pnl, low, tot = trade_pnl(t, q, qfull, st)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * tot
                low = pnl
            rec = {**{k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "exit", "risk", "tgt")}, "qty": tot, "pnl": round(pnl, 2),
                   "low": round(low, 2), "risk_usd": round(t["risk"] * PV * q, 2), "src": src, "sess": sess,
                   "comm": round(_comm(tot) if not t.get("adds") else 0.0, 2)}
            taken[src] += 1
            busy = t["exit_t"]
            if bal + cum + low <= floor:
                if keep is not None:
                    keep.append(rec)
                return "FAIL", kk + 1
            cum += pnl
            if keep is not None:
                keep.append(rec)
        bal += cum
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if bal >= tgt:
            return "PASS", kk + 1
    return "OPEN", min(len(seq), horizon)


A.run_eval = run_eval_g


def setg(**kw):
    G.update({"comm": None, "m15_until": None, "m15_mode": "first", "alt_until": None, "mfun": None, "true_low": False})
    G.update(kw)


def short(o):
    out = {}
    for s in ("H1", "H2"):
        x = o[s]
        out[s] = {k: x.get(k) for k in ("n", "tpw", "wk2", "win", "pf", "net", "per_month", "dd", "p10", "f10", "p20", "f20",
                                         "pass_med", "cost", "b2b")} | {"mc_p10": x["mc"]["p10"], "mc_f10": x["mc"]["f10"]}
    return out


def line(nm, o):
    def f(s):
        x = o[s]
        return (f"{x['tpw']}/wk PF {x['pf']} {x['net']:+,} (${x['per_month']:,}/mo) DD {x['dd']:,} 2w {x['p10']}/{x['f10']} "
                f"1mo {x['p20']}/{x['f20']} mc {x['mc_p10']}/{x['mc_f10']}")
    return f"{nm[:46]:46s} H1[{f('H1')}] H2[{f('H2')}]"


def record(group, nm, U, extra=None, **g):
    setg(**g)
    try:
        o = short(A.score(U))
    finally:
        setg()
    if extra:
        o["info"] = extra
    RES.setdefault(group, {})[nm] = o
    print(line(nm, o), flush=True)
    return o


# ================================================================================================ 1m path simulator (add2 + lock)
def psim(t, R):
    """One live trade on its 1m path. R: {"trig": "none"|"cisd", "pb": 1st pullback R, "rat": True, "rat_k": 1.0, "n": 1|2,
    "pb2": 2nd pullback R, "rat_k2": R of the 2nd add, "min_rk": 2.0, "xslip": add fill pts worse,
    "lock": [(x R, y R), ...] stop to entry + y R once the high reached entry + x R (end of bar, acts from the next bar)}.
    With trig none and no lock == the live trade; with n 1 == lit_big_ideas.padd (cisd, rat)."""
    cx = A.ctx(); B = cx.B1
    d = t["dir"]
    hi, lo, c, o = B.dirs(d)
    k0 = t["fill_k"]
    entry = t["entry_px"] * d
    stop0 = t["stop_px"] * d
    tg = entry + t["tgt"]
    risk = t["risk"]
    limit_fill = entry <= float(o[k0]) + 1e-9
    sday = B.day[k0]
    flat = A.LIVE["flat_mod"]
    be_lvl = entry + A.LIVE["be_r"] * risk
    trig = R.get("trig", "none")
    nmax = int(R.get("n", 1))
    locks = sorted(R.get("lock") or [])
    cur, be_done = stop0, False
    worst = w_pre = 0.0
    adds = []
    pend = False
    base_k = None
    rat_lvl = None
    n_rat = 0
    exit_px = kind = None
    k = k0
    while k < B.n:
        if B.day[k] != sday or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c[k]) - SLIP, "EOD"; break
        if pend:
            pend = False
            px = float(o[k]) + SLIP + R.get("xslip", 0.0)
            if px < tg and px - cur >= R.get("min_rk", 2.0):
                a = {"px": px, "dist": px - entry, "rk": px - cur, "prev_rk": [b["px"] - cur for b in adds], "k": k, "w_ph": 0.0,
                     "tw": None}
                adds.append(a)
                rk_mult = R.get("rat_k", 1.0) if len(adds) == 1 else R.get("rat_k2", R.get("rat_k", 1.0))
                if R.get("rat") and (len(adds) == 1 or R.get("rat2", True)):
                    rat_lvl = (px + rk_mult * (px - cur), px)
        lw = float(lo[k]) - entry
        worst = min(worst, lw)
        if adds:
            adds[-1]["w_ph"] = min(adds[-1]["w_ph"], lw)
            tw = max(lw, cur - SLIP - entry)          # true worst open: the position cannot be open below its stop
            adds[-1]["tw"] = tw if adds[-1]["tw"] is None else min(adds[-1]["tw"], tw)
        else:
            w_pre = min(w_pre, lw)
        if lo[k] <= cur:
            exit_px = cur - SLIP
            kind = "STOP" if not be_done else ("LOCK" if cur > entry + 1e-9 and not adds else "BE")
            break
        if not (k == k0 and limit_fill):
            if hi[k] >= tg:
                exit_px, kind = tg, "TARGET"; break
        if B.mod[k] >= flat:
            exit_px, kind = float(c[k]) - SLIP, "EOD"; break
        if not be_done and not (k == k0 and limit_fill) and hi[k] >= be_lvl:
            cur, be_done = max(cur, entry), True
            base_k = k
        elif be_done and rat_lvl is not None and hi[k] >= rat_lvl[0]:
            cur = max(cur, rat_lvl[1]); rat_lvl = None; n_rat += 1
            base_k = k                                    # the 2nd add's pullback is searched after the stop moved
        if be_done and locks and not (k == k0 and limit_fill):
            for x, y in locks:
                if hi[k] >= entry + x * risk:
                    cur = max(cur, entry + y * risk)
        if be_done and trig == "cisd" and len(adds) < nmax and not pend and k > base_k and n_rat >= len(adds):
            pb = R.get("pb", 0.25) if not adds else R.get("pb2", R.get("pb", 0.25))
            seg = lo[base_k + 1:k + 1]
            lowk = base_k + 1 + int(np.argmin(seg))
            hmax = float(hi[base_k:lowk + 1].max())
            if k > lowk and hmax - lo[lowk] >= pb * risk:
                cz = lit._cisd_level(c, o, lowk)
                if cz is not None and c[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == sday:
                    pend = True
                    base_k = k + 1
        k += 1
    if exit_px is None:
        return None
    for a in adds:
        a["pts"] = exit_px - a["px"]
    return {"pts": round(exit_px - entry, 4), "exit": kind, "w1": round(worst, 4), "w_pre": round(w_pre, 4),
            "adds": [{k_: (round(v, 4) if isinstance(v, float) else v) for k_, v in a.items()} for a in adds]}


def units_sim(R, f=1.0, f2=None):
    out = []
    for t in BI.live():
        x = dict(t)
        if t["on1"] and (R.get("trig", "none") != "none" or R.get("lock")):
            s = psim(t, R)
            x.update(pts=s["pts"], exit=s["exit"], w1=s["w1"], w_pre=s["w_pre"], legs=[(1.0, s["pts"])])
            if s["adds"]:
                x.update(adds=s["adds"], add_f=f, add_f2=f if f2 is None else f2)
        out.append(x)
    return out


CAND = {"trig": "cisd", "pb": 0.25, "rat": True, "rat_k": 1.0, "min_rk": 2.0, "n": 1}


def check():
    U = BI.live()
    bad = 0
    for t in U:
        if not t["on1"]:
            continue
        s = psim(t, {"trig": "none"})
        if s["exit"] != t["exit"] or abs(s["pts"] - t["pts"]) > 1e-6 or abs(s["w1"] - t["w1"]) > 1e-6:
            bad += 1; print("mismatch", t["day"], t["exit"], t["pts"], s)
    n1 = sum(1 for t in U if t["on1"])
    print(f"simulator off == live: {n1 - bad}/{n1}")
    bad = 0
    for t in U:
        if not t["on1"]:
            continue
        a, b = psim(t, CAND), BI.padd(t, CAND)
        if a["exit"] != b["exit"] or abs(a["pts"] - b["pts"]) > 1e-6 or len(a["adds"]) != len(b["adds"]) or \
                any(abs(x["px"] - y["px"]) > 1e-6 for x, y in zip(a["adds"], b["adds"])):
            bad += 1; print("add1 mismatch", t["day"], a["exit"], b["exit"])
    print(f"simulator 1 add == lit_big_ideas.padd (scale_in candidate): {n1 - bad}/{n1}")
    setg()
    o = short(A.score(U))
    print(line("live (scorer with hooks off)", o))
    o2 = short(A.score(units_sim(CAND)))
    print(line("scale_in candidate", o2))


# ================================================================================================ idea 1: minis
def grid1():
    U = BI.live()
    base = record("minis", "live, all MNQ ($1.90)", U)
    for c in (4.68, 4.36, 5.76):
        record("minis", f"minis at >=10 micros, NQ ${c:.2f}", U, comm=comm_minis(c))
    Us = units_sim(CAND)
    record("minis", "scale_in cand, all MNQ", Us)
    record("minis", "scale_in cand, minis NQ $4.68", Us, comm=comm_minis(4.68))
    # size distribution on the b2b eval path
    info = {}
    for s in ("H1", "H2"):
        setg()
        T, _ = A.b2b(U, s)
        q = np.array([t["qty"] for t in T])
        sav = sum(ECOMM * x - comm_minis(4.68)(x) for x in q)
        info[s] = {"trades": len(q), "q_ge10": int((q >= 10).sum()), "q_med": float(np.median(q)), "q_max": int(q.max()),
                   "saved_b2b": round(float(sav))}
    # at the plain LIT rule size ($800 up to 20 pts)
    for s, (a, z) in (("H1", A.SPANS["H1"]), ("H2", A.SPANS["H2"])):
        qq = [lit.qty_for(t["risk"]) for t in U if a <= t["day"] <= z]
        info[s]["lit_size_saved"] = round(float(sum(ECOMM * x - comm_minis(4.68)(x) for x in qq)))
        info[s]["lit_size_q_ge10"] = sum(1 for x in qq if x >= 10)
    RES["minis"]["_info"] = info
    print(info)


# ================================================================================================ idea 2: second add
def grid2():
    """Both low conventions: "cons" = lit_big_ideas (an add's worst open measured as if price came back to the entry, ignoring the
    moved stop: conservative), "true" = the real worst open price after each add, capped at the stop in force."""
    for tl in (False, True):
        tag = "true lows" if tl else "cons lows"
        record("add2", f"[{tag}] scale_in candidate (1 add)", units_sim(CAND), true_low=tl)
        record("add2", f"[{tag}] 1 add, adds 2 pts worse", units_sim({**CAND, "xslip": 2.0}), true_low=tl)
        for rat2 in (True, False):
            for pb2 in (0.1, 0.25, 0.4):
                for f2 in (0.5, 1.0):
                    R = {**CAND, "n": 2, "pb2": pb2, "rat_k2": 1.0, "rat2": rat2}
                    record("add2", f"[{tag}] 2nd add pb2 {pb2} f2 {f2}{'' if rat2 else ' no 2nd stop move'}", units_sim(R, 1.0, f2),
                           true_low=tl)
            R = {**CAND, "n": 2, "pb2": 0.25, "rat2": rat2}
            sfx = '' if rat2 else ' no 2nd stop move'
            record("add2", f"[{tag}] 2nd add pb2 0.25 f2 0.25{sfx}", units_sim(R, 1.0, 0.25), true_low=tl)
            record("add2", f"[{tag}] 2nd add pb2 0.25 f2 0.5 adds 2 pts worse{sfx}", units_sim({**R, "xslip": 2.0}, 1.0, 0.5),
                   true_low=tl)
        R = {**CAND, "n": 2, "pb2": 0.25}
        for rk in (0.75, 1.5, 2.0):
            record("add2", f"[{tag}] 2nd add pb2 0.25 f2 0.5 rat_k2 {rk}", units_sim({**R, "rat_k2": rk}, 1.0, 0.5), true_low=tl)
    U = units_sim({**CAND, "n": 2, "pb2": 0.25}, 1.0, 1.0)
    n2 = collections.Counter(("H1" if t["day"] <= "2026-06-30" else "H2") for t in U if len(t.get("adds") or []) > 1)
    RES["add2"]["_info"] = {"n_2nd_adds": dict(n2), "n_1st_adds": dict(collections.Counter(
        ("H1" if t["day"] <= "2026-06-30" else "H2") for t in U if t.get("adds")))}
    print(RES["add2"]["_info"])


# ================================================================================================ idea 3: 15m eval booster
_U15 = {}


def u15(P):
    key = json.dumps(P, sort_keys=True)
    if key not in _U15:
        from tools import lit_more as LM
        U = LM.unit(LM.run_on("m15", P), "NQ", "m15")
        out = []
        for u in U:
            if u["day"] < "2026-01-01":
                continue
            out.append({**u, "legs": [(1.0, u["pts"])], "src": "m15", "on1": False})
        _U15[key] = out
    return _U15[key]


P15 = {"live filters idm12": {"idm_a": [1.0, 12, 1]},
       "d0.4 disp0.7 idm12 stop100": {"idm_a": [1.0, 12, 1], "depth": 0.4, "disp": 0.7, "max_stop": 100.0}}


def grid3():
    U = BI.live()
    record("m15", "live (5m only)", U)
    info = {}
    for lab, P in P15.items():
        X = u15(P)
        days5 = {t["day"] for t in U}
        info[lab] = {"n15": len(X), "on_5m_days": sum(1 for x in X if x["day"] in days5)}
        for until in (10, 999):
            for mode in ("first", "pertf"):
                for m in (1.0, 0.5, 0.25):
                    XX = [dict(x, m=m) for x in X]
                    nm = f"15m {lab}, {'eval s1-10' if until == 10 else 'always'}, {mode}, x{m}"
                    record("m15", nm, U + XX, m15_until=until, m15_mode=mode)
        # upper bound: 15m only on days with no 5m trade at all (needs hindsight)
        XX = [x for x in X if x["day"] not in days5]
        record("m15", f"15m {lab}, s1-10, only no-5m days (hindsight)", U + XX, m15_until=10, m15_mode="pertf")
    RES["m15"]["_info"] = info
    print(info)


# ================================================================================================ idea 6: profit lock
LOCKS = {"2R->0.5R": [(2.0, 0.5)], "2R->1R": [(2.0, 1.0)], "3R->1R": [(3.0, 1.0)], "3R->2R": [(3.0, 2.0)], "4R->2R": [(4.0, 2.0)],
         "5R->3R": [(5.0, 3.0)], "6R->4R": [(6.0, 4.0)], "3R->1R,5R->3R": [(3.0, 1.0), (5.0, 3.0)],
         "4R->2R,6R->4R": [(4.0, 2.0), (6.0, 4.0)], "2R->1R,4R->3R,6R->5R": [(2.0, 1.0), (4.0, 3.0), (6.0, 5.0)]}


def grid6():
    U = BI.live()
    record("lock", "live (BE at 1R only)", U)
    for nm, L in LOCKS.items():
        UL = units_sim({"trig": "none", "lock": L})
        record("lock", f"lock {nm}, all sessions", UL)
        UA = [dict(t, alt=a) for t, a in zip(U, UL)]
        record("lock", f"lock {nm}, two_week phase only", UA, alt_until=10)
    # how many trades a lock touches
    info = {}
    for nm, L in LOCKS.items():
        UL = units_sim({"trig": "none", "lock": L})
        ch = [(t["day"], t["exit"], a["exit"], round((a["pts"] - t["pts"]) / t["risk"], 2)) for t, a in zip(U, UL)
              if a["exit"] != t["exit"] or abs(a["pts"] - t["pts"]) > 1e-6]
        info[nm] = {"changed": len(ch), "dR_H1": round(sum(x[3] for x in ch if x[0] <= "2026-06-30"), 2),
                    "dR_H2": round(sum(x[3] for x in ch if x[0] > "2026-06-30"), 2), "list": ch}
    RES["lock"]["_info"] = info
    for nm, v in info.items():
        print(nm, v["changed"], v["dR_H1"], v["dR_H2"])


# ================================================================================================ idea 7: London vs NY tilt
def et_min(t):
    x = dt.datetime.fromtimestamp(int(t["entry_t"]), ET)
    return x.hour * 60 + x.minute


def grid7():
    U = BI.live()
    info = {}
    for s, (a, z) in (("H1", A.SPANS["H1"]), ("H2", A.SPANS["H2"])):
        for lab, cond in (("london", lambda m: m < 480), ("ny", lambda m: m >= 480)):
            R = [t["pts"] / t["risk"] for t in U if a <= t["day"] <= z and cond(et_min(t))]
            info[f"{s}_{lab}"] = {"n": len(R), "tot_r": round(float(np.sum(R)), 2), "avg_r": round(float(np.mean(R)), 3) if R else None,
                                  "win": round(100 * float(np.mean(np.array(R) > 0)), 1) if R else None}
    RES.setdefault("tod", {})["_info"] = info
    print(info)
    record("tod", "live", U)
    for lm, nm_ in ((1.0, 0.5), (1.0, 0.75), (1.0, 1.25), (1.0, 1.5), (0.5, 1.0), (0.75, 1.0), (1.25, 1.0), (1.5, 1.0),
                    (1.25, 0.75), (0.75, 1.25)):
        for phase in ("all", "safe"):
            def mf(t, sess, lm=lm, nm_=nm_, phase=phase):
                if phase == "safe" and sess <= 10:
                    return 1.0
                return lm if et_min(t) < 480 else nm_
            record("tod", f"London x{lm} NY x{nm_}, {phase}", U, mfun=mf)


# ================================================================================================ ideas 4 + 5: funded
def funded(do_save=False):
    from tools import lit_funded as LF
    from tools import lit_2wk as W
    D = W.data()
    AF = dict(SZ.FD_50K)
    REC = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]["funded"]

    def run(sizer, policy, seq, by, keep=None):
        """lit_funded.run_funded with a size hook sizer(t, st) -> micros and a payout policy:
        ("asap", 0) as soon as eligible take min(bal - buffer, $2,000) [today's model]; ("min", 0) take only $500;
        ("full", 0) wait until $2,000 is available, take $2,000; ("hold", h) keep h extra above the buffer, then take the max."""
        mll, dll, lockv = AF["mll"], AF["dll"], AF["lock"]
        bal = peak = 0.0
        floor = -mll
        paid = 0.0
        n_pay, first, last_bal, cyc = 0, None, 0.0, []
        pay_at = []
        max_risk = 0.0
        for k, si in enumerate(seq):
            cum = 0.0
            traded = False
            for t in by[si]:
                if cum <= -dll:
                    break
                st = {"room": bal + cum - floor, "cum": cum, "locked": floor >= lockv - 1e-9, "bal": bal}
                q = sizer(t, st)
                if q <= 0:
                    continue
                traded = True
                cm = ECOMM * q
                pnl = t["pts"] * PV * q - cm
                low = min(0.0, t["w1"] * PV * q - cm, pnl)
                max_risk = max(max_risk, (t["risk"] + SLIP) * PV * q + cm)
                if cum + low <= -dll:
                    pnl = -dll - cum - SLIP * PV * q
                    low = pnl
                if bal + cum + low <= floor:
                    if keep is not None:
                        keep.append(W._rec(t, q, floor - bal - cum, floor - bal - cum))
                    return {"paid": paid, "pay_at": pay_at, "n": n_pay, "first": first, "blown": k + 1, "grad": None,
                            "max_risk": max_risk, "end_bal": bal + cum + low}
                cum += pnl
                if keep is not None:
                    keep.append(W._rec(t, q, pnl, low))
            bal += cum
            peak = max(peak, bal)
            floor = min(max(floor, peak - mll), lockv)
            if traded:
                cyc.append(cum)
            if k + 1 < AF["first_wait"] or len(cyc) < AF["cycle_days"]:
                continue
            prof = bal - last_bal
            if prof <= 0 or (cyc and max(cyc) > AF["cons"] * prof):
                continue
            avail = bal - AF["buffer"]
            pol, h = policy
            if pol == "asap":
                amt = min(avail, AF["pay_max"])
            elif pol == "min":
                amt = AF["pay_min"] if avail >= AF["pay_min"] else 0.0
            elif pol == "full":
                amt = AF["pay_max"] if avail >= AF["pay_max"] else 0.0
            elif pol == "atl":                          # request once at least h is available, take up to $2,000
                amt = min(avail, AF["pay_max"]) if avail >= h else 0.0
            else:
                amt = min(avail - h, AF["pay_max"])
            if amt < AF["pay_min"]:
                continue
            share = amt * AF["split"]
            paid += share
            n_pay += 1
            pay_at.append((k + 1, share))
            first = first or k + 1
            bal -= amt
            last_bal, cyc = bal, []
            if n_pay >= AF["max_payouts"]:
                return {"paid": paid, "pay_at": pay_at, "n": n_pay, "first": first, "blown": None, "grad": k + 1,
                        "max_risk": max_risk, "end_bal": bal}
        return {"paid": paid, "pay_at": pay_at, "n": n_pay, "first": first, "blown": None, "grad": None, "max_risk": max_risk,
                "end_bal": bal}

    def mc(sizer, policy, span):
        R = [run(sizer, policy, s, D["by"]) for s in LF.mc_seqs(span)]
        o = {}
        for lab, h in (("3m", LF.H3), ("6m", LF.H6)):
            lost = [r for r in R if r["blown"] and r["blown"] <= h]
            paid = [sum(x for kk, x in r["pay_at"] if kk <= h) for r in R]
            o[f"loss_{lab}"] = round(100.0 * len(lost) / len(R), 1)
            o[f"paid_{lab}"] = round(float(np.mean(paid)))
            o[f"paid_p10_{lab}"] = round(float(np.percentile(paid, 10)))
            o[f"grad_{lab}"] = round(100.0 * sum(1 for r in R if r["grad"] and r["grad"] <= h) / len(R), 1)
        o["per_month"] = round(o["paid_6m"] / 6.0)
        fr = [r["first"] for r in R if r["first"]]
        o["first_med"] = float(np.median(fr)) if fr else None
        o["max_risk"] = round(max(r["max_risk"] for r in R))
        o["npay_mean"] = round(float(np.mean([r["n"] for r in R])), 2)
        # money still on the account (not withdrawn) at 6 months for live accounts, at 80%: a fair "value left"
        o["left_6m"] = round(float(np.mean([max(0.0, r["end_bal"] - AF["buffer"]) * AF["split"] if not r["blown"] and not r["grad"]
                                            else 0.0 for r in R])))
        return o

    def flat(t, st):
        return SZ.funded_qty(t, st, REC, acct=AF)

    def comp(steps, win_steps=None, pct=None):
        """Compounding: the $ max per trade and the best-day cap step up with the room to the floor."""
        def f(t, st):
            room = st["room"]
            usd = REC["pct_max_usd"]
            for a, u in steps:
                if room >= a:
                    usd = u
            mw = REC["max_win"]
            for a, u in (win_steps or []):
                if room >= a:
                    mw = u
            c = {**REC, "pct_max_usd": usd, "max_win": mw}
            if pct:
                c["pct"] = pct
            return SZ.funded_qty(t, st, c, acct=AF)
        return f

    SIZ = {"flat (live funded: 40% room, max $800, best day $1,500)": flat,
           "comp A: max $1,000 at 3k room, $1,200 at 4k": comp([(3000, 1000), (4000, 1200)]),
           "comp B: max $1,000 at 3k, $1,500 at 4.5k, $2,000 at 6k": comp([(3000, 1000), (4500, 1500), (6000, 2000)]),
           "comp B + best day $2,000 at 4.5k, $3,000 at 6k": comp([(3000, 1000), (4500, 1500), (6000, 2000)],
                                                                 [(4500, 2000), (6000, 3000)]),
           "comp C: 40% of the room, no $ max (40 micros)": comp([(0, 10 ** 6)]),
           "comp C + best day = 50% of (room - $2,000), min $1,500": None}

    def compc_win(t, st):
        mw = max(REC["max_win"], 0.5 * (st["room"] - 2000.0))
        return SZ.funded_qty(t, st, {**REC, "pct_max_usd": 10 ** 6, "max_win": mw}, acct=AF)
    SIZ["comp C + best day = 50% of (room - $2,000), min $1,500"] = compc_win
    POL = {"asap (today's model)": ("asap", 0), "minimum $500 each time": ("min", 0), "wait for a full $2,000": ("full", 0),
           "wait for $1,000+": ("atl", 1000), "wait for $1,500+": ("atl", 1500),
           "hold $1,000 extra": ("hold", 1000), "hold $2,000 extra": ("hold", 2000), "hold $4,000 extra": ("hold", 4000)}
    out = {}
    for sn, sz in SIZ.items():
        for pn, pol in POL.items():
            if sn != list(SIZ)[0] and pn not in ("asap (today's model)", "hold $2,000 extra", "hold $4,000 extra", "wait for a full $2,000"):
                continue
            key = f"{sn} | {pn}"
            out[key] = {"H1": mc(sz, pol, "H1"), "H2": mc(sz, pol, "H2")}
            h1, h2 = out[key]["H1"], out[key]["H2"]
            print(f"{key[:90]:90s} H1 lost6 {h1['loss_6m']:4.1f}% paid6 ${h1['paid_6m']:6,} (${h1['per_month']:,}/mo) 1st {h1['first_med']} "
                  f"pays {h1['npay_mean']} left {h1['left_6m']} risk {h1['max_risk']} | H2 lost6 {h2['loss_6m']:4.1f}% paid6 ${h2['paid_6m']:6,} "
                  f"(${h2['per_month']:,}/mo) 1st {h2['first_med']} pays {h2['npay_mean']} left {h2['left_6m']} risk {h2['max_risk']}", flush=True)
    json.dump(out, open(OUT_F, "w"), indent=1, default=float)
    if not do_save:
        return out
    from tools import runlib as rl

    def b2b(sizer, policy, span, keep):
        a, z = W.span_idx(span)
        k, n, paid = a, collections.Counter(), 0.0
        while k < z:
            r = run(sizer, policy, list(range(k, z)), D["by"], keep=keep)
            paid += r["paid"]
            if r["blown"]:
                n["lost"] += 1; k += r["blown"]
            elif r["grad"]:
                n["graduated"] += 1; k += r["grad"]
            else:
                n["open"] += 1; break
        return {"accounts": sum(n.values()), **n, "paid": round(paid), "per_month": round(paid / ((z - a) / 21.0))}

    FS = [("lit_m2_payout_1500", list(SIZ)[0], "wait for $1,500+", "adopt-candidate",
           "Payout policy on the MFFU Builder 50K funded account (live funded sizing): request a payout only once at least $1,500 "
           "is above the $2,100 buffer (take up to $2,000), instead of as soon as $500 is. Neighbours ($1,000+, a full $2,000) also "
           "pay more and lose fewer accounts in both halves; taking only the $500 minimum each time pays far less."),
          ("lit_m2_payout_min500", list(SIZ)[0], "minimum $500 each time", "rejected",
           "Payout policy: always withdraw only the $500 minimum."),
          ("lit_m2_funded_compound_b", "comp B: max $1,000 at 3k, $1,500 at 4.5k, $2,000 at 6k", "wait for a full $2,000", "rejected",
           "Funded compounding: the $ max per trade steps up as the room above the floor grows (with payouts held to a full $2,000 "
           "so the buffer can build). No gain over flat funded sizing in either half: the $1,500 best-day cap and the payout "
           "resets keep size flat.")]
    for rid, sn, pn, st, why in FS:
        T = []
        bb = {sp: b2b(SIZ[sn], POL[pn], sp, T) for sp in ("H1", "H2")}
        T.sort(key=lambda t: t["entry_t"])
        r = out[f"{sn} | {pn}"]
        ref = out[f"{list(SIZ)[0]} | asap (today's model)"]
        h = lambda s: (f"MC 6 months: account lost {r[s]['loss_6m']}% (today's policy {ref[s]['loss_6m']}%), paid to you "
                       f"${r[s]['paid_6m']:,} (${r[s]['per_month']:,}/mo; today ${ref[s]['paid_6m']:,}), first payout session "
                       f"{r[s]['first_med']} (today {ref[s]['first_med']}), $ left on the account at 6 months (80%) ${r[s]['left_6m']:,}; "
                       f"back to back on real history {bb[s]}")
        Sc = rl.score(T, D["sess"])
        rl.save(rid, f"{sn} | {pn}", "risk", Q, params={"funded": REC, "sizer": sn, "payout_policy": pn},
                sizing={"mode": "funded", **REC}, trades=T, scored=Sc, status=st,
                verdict=f"{why} H1 (pick): {h('H1')}. H2 (check): {h('H2')}.",
                notes="tools/lit_money2.py funded (MFFU Builder 50K funded as tools/lit_funded.py: EOD trailing $2,000 locking at "
                      "+$100, $1,000 soft daily loss, buffer $2,100, $500-$2,000 a request, best day <= 50% of the cycle, 2 traded "
                      "days, 5 sim payouts, 80%; $1.90 a micro). 1,000 Monte Carlo accounts of 126 sessions in 5-session blocks, the "
                      "same paths for every config. Stored trades = the back-to-back funded path; the run library's eval columns are "
                      "not the funded numbers.", writeup="lit-money-batch2", tags=["lit", "lit_m2", "funded"])
        print("saved", rid, flush=True)
    return out


# ================================================================================================ run library
Q = ("LIT money batch 2 (2026-10-19): minis for commission, a second scale-in add, 15m setups as an eval-only booster, a stepped "
     "profit lock, a London / New York size tilt (and funded compounding / payout policy). LIT rule: 2026 only, pick on Jan-Jun, "
     "check on Jul-Oct; adopt-candidate only if both halves gain net $ and 2-week eval fails do not rise meaningfully; live sizing "
     "two_week 10 sessions then safe_eval, $1.90 a micro, no reset.")


def save_runs(S):
    """S = [(id, title, family, status, verdict, units, g)]"""
    from tools import runlib as rl
    for rid, title, fam, st, why, U, g in S:
        setg(**g)
        T = []
        for sp in ("H1", "H2"):
            T += A.b2b(U, sp)[0]
        o = short(A.score(U))
        setg()
        for t in T:
            t["risk_pts"] = t["risk"]; t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
            t.update(half=False, trigger="LIT-1m" if t.get("src") != "m15" else "LIT-15m", mfe=None, mae=None, bars_held=None,
                     regime="", mult=None, tgt_pts=t["tgt"])
        Sc = rl.score(T, A.S26)
        h = lambda s: (f"{o[s]['n']} trades {o[s]['tpw']}/wk win {o[s]['win']}% PF {o[s]['pf']} net ${o[s]['net']:+,} "
                       f"(${o[s]['per_month']:,}/mo) DD ${o[s]['dd']:,}; 2-week pass/fail {o[s]['p10']}/{o[s]['f10']} (Monte Carlo "
                       f"{o[s]['mc_p10']}/{o[s]['mc_f10']}), 1 month {o[s]['p20']}/{o[s]['f20']}, median sessions to pass {o[s]['pass_med']}")
        rl.save(rid, title, fam, Q, params={"lit": "live_model.json lit (unchanged)", "variant": title},
                sizing={"mode": "two_week", **A.CFG}, trades=T, scored=Sc, status=st,
                verdict=f"{why} 2026 H1 (pick): {h('H1')}. 2026 H2 (check): {h('H2')}. 2021-25: no 1m bars, not tested.",
                notes="tools/lit_money2.py (wraps tools/lit_big_ideas.py / lit_adv_manage.py / engine/lit.py; options off == the 120 "
                      "live 2026 trades). Stored trades = the back-to-back eval path per half (a new eval only after a pass or a fail).",
                writeup="lit-money-batch2", tags=["lit", "lit_m2"])
        print("saved", rid, st, flush=True)


def save():
    U = BI.live()
    R2 = {**CAND, "n": 2, "pb2": 0.25, "rat_k2": 1.0}
    X15 = u15(P15["d0.4 disp0.7 idm12 stop100"])
    S = [
        ("lit_m2_base", "LIT live (reference)", "other", "info", "Reference: LIT live with the live sizing.", U, {}),
        ("lit_m2_minis", "NQ minis + MNQ remainder at >= 10 micros (NQ $4.68 round turn)", "risk", "promising",
         "Same trades, same exposure: floor(q/10) NQ minis + the rest in MNQ, $4.68 a mini vs $19.00 for 10 micros ($14.32 saved per "
         "mini). Only 13 (H1) / 2 (H2) of the eval-path trades reach 10 micros, so it saves about $215 / $43 per half ($36 / $12 a "
         "month); the eval-path net moves -$264 / +$43 only because one failing eval fails one session earlier (path noise). Real but "
         "tiny now; needs NQ routing next to MNQ.", U, {"comm": comm_minis(4.68)}),
        ("lit_m2_scale_true_lows", "Scale-in candidate scored with true open lows", "management", "info",
         "The lit-big-ideas scale_in candidate re-scored with the true worst open price after the add (capped at the stop in force) "
         "instead of 'price back at the entry': H1 2-week fails 10.1 -> 7.6 (live 9.2), H2 unchanged.", units_sim(CAND), {"true_low": True}),
        ("lit_m2_add2", "Scale-in + a second add (pb2 0.25, f2 0.5)", "management", "rejected",
         "Second add once the 1st add is +1 of its own risk (stop at the 1st add), then a 1m pullback >= 0.25R and a 1m CISD; true "
         "open lows. H1 gains, H2 loses $17.8k vs one add: the 2nd add comes late, far from the stop, and its stop move turns targets "
         "into breakevens. Every neighbour loses H2 money except f2 0.25 with no 2nd stop move (+$1.0k / +$0.8k: noise).",
         units_sim({**CAND, "n": 2, "pb2": 0.25, "rat_k2": 1.0}, 1.0, 0.5), {"true_low": True}),
        ("lit_m2_m15_eval_half", "15m setups in eval sessions 1-10 only, x0.5, 1 a day first fill", "other", "rejected",
         "15m LIT setups (depth 0.4, disp 0.7, idm 12, stop 100) as an eval-only booster at half the two_week size. 2-week fails "
         "fall (9.2 -> 7.6, 2.9 -> 1.4) and money is +$617 / +$165, but it rests on 4 (H1) / 1 (H2) 15m trades on the eval path, one "
         "of them displacing a +$2,060 5m winner: too thin to adopt.",
         U + [dict(x, m=0.5) for x in X15], {"m15_until": 10, "m15_mode": "first"}),
        ("lit_m2_lock_3r1r", "Profit lock: at +3R the stop goes to +1R", "management", "rejected",
         "One-step profit lock (not a trail). Every lock tested (2R-6R triggers, 0.5R-5R locks, 1-3 steps) loses H1 money: the "
         "big H1 winners dip after +3-6R before the VIX target.", units_sim({"trig": "none", "lock": LOCKS["3R->1R"]}), {}),
        ("lit_m2_tod_l125_ny075", "London x1.25 / New York x0.75 in the safe_eval phase", "risk", "rejected",
         "Time-of-day size tilt from LIT's own trades. NY earns more per trade in H1 (1.05R vs 0.72R) and less in H2 (0.16R vs "
         "0.80R): the sign flips, so no tilt holds; this H1 pick gains +$2.0k / +$0.4k but both its one-sided neighbours lose H1.",
         U, {"mfun": lambda t, s: 1.0 if s <= 10 else (1.25 if et_min(t) < 480 else 0.75)}),
    ]
    over = json.load(open(os.path.join(ROOT, "research", "lit", "money2_save.json"))) if os.path.exists(
        os.path.join(ROOT, "research", "lit", "money2_save.json")) else {}
    S = [(rid, ti, fa, over.get(rid, {}).get("status", st), over.get(rid, {}).get("why", why), U_, g) for rid, ti, fa, st, why, U_, g in S]
    save_runs(S)


def grid(which=None):
    global RES
    if os.path.exists(OUT):
        RES = json.load(open(OUT))
    for w, fn in (("1", grid1), ("2", grid2), ("3", grid3), ("6", grid6), ("7", grid7)):
        if which and w not in which:
            continue
        RES.pop({"1": "minis", "2": "add2", "3": "m15", "6": "lock", "7": "tod"}[w], None)
        fn()
        _dump()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "grid":
        grid(sys.argv[2:] or None)
    elif cmd == "funded":
        funded(do_save=len(sys.argv) > 2 and sys.argv[2] == "save")
    elif cmd == "save":
        save()
