"""LIT big ideas (2026-10-19): four ideas never tested on LIT, judged by the LIT rule (2026 only; pick on Jan-Jun = H1, check on
Jul-Oct = H2; adopt only if BOTH halves improve in net $ AND in the MFFU 50K 2-week pass rate under the live sizing, 2-4 trades
a week, costs in).

  1 scale   scale-in / pyramiding: once the trade is at +1R and the stop is at breakeven, add micros on a trigger in the trade's
            direction ("imm" next 1m open after BE | "cisd" a 1m CISD after a pullback | "pull" a resting limit at entry + p R);
            the add's stop is the trade's stop (breakeven), optionally moved to the add's own breakeven once the add is +1 of
            its own risk ("rat"); total open risk never above the original $ risk, the $1,000 soft daily loss or 60% of the
            room; max 40 micros; one or two adds. Also "start at half the two-week size + add at +1R".
  2 trend   trend-day mode: a trend-day flag from facts known at the 5m setup bar (overnight range / 20-day ATR, the 18:00-open
            distance already covered in VIX moves, the swept level is PDH/PDL/PWH/PWL/PMH/PML, displacement size, VIX); on
            flagged days a later bank (12R / 15R / none), breakeven at 2R, or the next VIX band step (18:00 open +/- 2 moves).
            Thresholds fitted on H1, applied frozen to H2.
  3 vol     volatility-regime size tilt: x mult by the VIX / VXN prior close or the 5m ATR regime at the setup.
  4 news    LIT setups whose sweep extreme prints 0-15 min after a 08:30 / 10:00 / 14:00 US release (data/news/events.csv):
            size tilts, and a second trade that day only for them.

Executor: tools/lit_adv_manage.py (engine/lit.py on the live LIT settings; options off == the live unit trades == run lit_live,
120/120). Fills: 1m bars; stop / BE checked before target in a bar, stop exits 1 tick worse; market adds at the next 1m open +
1 tick; a resting add limit fills on a touch, and in the bar it fills the add is assumed stopped if the bar also reaches the stop
and never credited with the target. Sizing: the live lit_sizing (engine/sizing.lit_qty: two_week for 10 sessions, then
safe_eval, no reset), $1.90 a micro. Eval scoring: lit_adv_manage.evals / mc / b2b with run_eval replaced by run_eval_x below
(identical when a trade has no adds / no multiplier).

  python -X utf8 tools/lit_big_ideas.py check     # executor == live; add simulator with no add == live
  python -X utf8 tools/lit_big_ideas.py grid      # all four ideas -> research/lit/big_ideas.json
  python -X utf8 tools/lit_big_ideas.py save      # rl.save the runs lit_big_*
Paper only. Edits no engine file.
"""
from __future__ import annotations

import bisect
import collections
import csv
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from tools import lit_adv_manage as A  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "big_ideas.json")
PV, SLIP = A.PV, A.SLIP
ECOMM = A.ECOMM
DLL = A.A50["dll"]
RES = {}


def _dump():
    json.dump(RES, open(OUT, "w"), indent=1, default=float)


# ================================================================================================ eval with adds / tilts
def _cap(t, st):
    """Largest micros the live caps allow for this trade (two_week: 60% room + soft daily loss; safe_eval: 60% room), max 40."""
    r = float(t["risk"])
    c = [40, int(0.6 * max(0.0, st["room"]) / (r * PV))]
    if st["session"] <= int(A.CFG.get("two_week_until") or 10):
        c.append(int(max(0.0, DLL + st["cum"]) / ((r + SZ.TW_DLL_SLIP) * PV + ECOMM)))
    return max(1, min(c))


def trade_pnl(t, q, qfull, st):
    """$ P&L and worst open $ of one trade at q base micros (+ its adds). qfull = the base micros before a start multiplier."""
    adds = t.get("adds")
    if not adds:
        pnl = A.leg_pnl(t, q)
        return pnl, min(0.0, t["w1"] * PV * q - ECOMM * q, pnl), q
    budget = min(qfull * t["risk"] * PV, 0.6 * max(0.0, st["room"]), DLL + st["cum"])
    tot = q
    g = q * t["pts"] * PV
    lows = [q * t["w_pre"] * PV]
    qa = []
    for a in adds:
        per = (a["rk"] + SLIP) * PV + ECOMM
        open_r = sum(qq * rk * PV for qq, rk in zip(qa, a["prev_rk"]))
        room_q = int(max(0.0, budget - open_r) / per) if per > 0 else 0
        f = t.get("add_f", 1.0)
        want = room_q if f == "max" else int(f * qfull + 1e-9)
        n = max(0, min(want, room_q, 40 - tot))
        qa.append(n)
        tot += n
        g += n * a["pts"] * PV
        lows.append((q * a["w_ph"] + sum(qq * (a["w_ph"] - b["dist"]) for qq, b in zip(qa, adds))) * PV)
    pnl = g - ECOMM * tot
    return pnl, min(0.0, min(lows) - ECOMM * tot, pnl), tot


def run_eval_x(seq, by, horizon=20, keep=None, cfg=None):
    """lit_adv_manage.run_eval + per-trade size multiplier t["m"] (cut: int(q x m), min 1; up: capped by the live caps) and adds."""
    cfg = cfg or A.CFG
    tgt, mll, dll, lockv = A.A50["target"], A.A50["mll"], A.A50["dll"], A.A50["lock"]
    bal = peak = 0.0
    floor = -mll
    for kk, si in enumerate(seq[:horizon]):
        cum = 0.0
        for t in by[si]:
            if cum <= -dll:
                break
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": kk + 1, "n_today": 0}
            m0 = lit.qty_for(t["risk"])
            q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, cfg, room=st["room"], state=st,
                           learning=None)["qty"] if m0 else 0
            if q <= 0:
                continue
            qfull = q
            m = float(t.get("m", 1.0))
            if m < 1.0 - 1e-9:
                q = max(1, int(q * m + 1e-9))
            elif m > 1.0 + 1e-9:
                q = max(q, min(int(q * m + 1e-9), _cap(t, st)))
            pnl, low, tot = trade_pnl(t, q, qfull, st)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * tot
                low = pnl
            rec = {**{k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "exit", "risk", "tgt")}, "qty": tot, "pnl": round(pnl, 2),
                   "low": round(low, 2), "risk_usd": round(t["risk"] * PV * q, 2)}
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


A.run_eval = run_eval_x          # lit_adv_manage.evals / mc / b2b now use it (identical for plain trades)


def score(U):
    return A.score(U)


def short(o):
    return {s: {k: o[s].get(k) for k in ("n", "tpw", "wk2", "win", "pf", "net", "per_month", "dd", "p10", "f10", "p20", "f20",
                                          "pass_med", "cost")} | {"mc_p10": o[s]["mc"]["p10"], "mc_f10": o[s]["mc"]["f10"]}
            for s in ("H1", "H2")}


def line(nm, o):
    def f(s):
        x = o[s]
        return (f"{x['tpw']}/wk win {x['win']} PF {x['pf']} {x['net']:+,} (${x['per_month']:,}/mo) DD {x['dd']:,} "
                f"2w {x['p10']}/{x['f10']} mc {x['mc_p10']}/{x['mc_f10']}")
    return f"{nm[:44]:44s} H1[{f('H1')}] H2[{f('H2')}]"


def better(o, b):
    return all(o[s]["net"] > b[s]["net"] and o[s]["p10"] > b[s]["p10"] for s in ("H1", "H2"))


def record(group, nm, U, extra=None, quiet=False):
    o = short(score(U))
    if extra:
        o["info"] = extra
    RES.setdefault(group, {})[nm] = o
    if not quiet:
        print(line(nm, o), flush=True)
    return o


# ================================================================================================ executor (arun copy + hooks)
def run(tmode=None, news2=None, flag=None):
    """lit_adv_manage.arun on 2026 with hooks.
    tmode(z, ep, risk, best) -> None (live) or {"tgt_add": pts beyond the band, "max_rr": R or None, "be": R}
    news2(z, first) -> True to allow this setup as the day's second trade (first = the day's first trade, already exited)
    flag(z) -> a tag stored on the trade (t["tag"])."""
    cx = A.ctx(); M = cx.M
    P = A.LIVE
    out, busy, first = [], -1, {}
    nday = collections.Counter()
    for z in cx.C:
        if z["day"] < "2026-01-01":
            continue
        if z["entry_i"] <= busy:
            continue
        if nday[z["day"]] >= 1:
            if news2 is None or nday[z["day"]] >= 2 or not news2(z, first[z["day"]]):
                continue
        if not lit.setup_ok(z, P, None):
            continue
        if P.get("monday") and lit.monday_block(M, z):
            continue
        ep = min(float(z["ref_d"]), z["trig_c"])
        stop0 = z["ext_d"] - P["stop_buf"]
        risk = ep - stop0
        if not (P["min_stop"] <= risk <= P["max_stop"]):
            continue
        sh = z["entry_d"] - ep
        TT = {c: [x + sh for x in v] for c, v in lit.targets_x(M, z, P).items()}
        best = None
        for c in P["classes"]:
            for dist in TT.get(c, []):
                if dist >= P["min_rr"] * risk:
                    if best is None or dist < best:
                        best = dist
                    break
        if best is None:
            continue
        use1 = P["tf"] == "1m" and int(M.day_of[z["entry_i"]]) in cx.B1.full
        tm = tmode(z, ep, risk, best) if tmode else None
        X = A.X_of({})
        old_rr = P["max_rr"]
        if tm:
            vm = M.ctx[z["k"]].get("vix_move") or 0.0
            tp_raw = best + tm.get("tgt_add", 0.0) * vm
            P["max_rr"] = tm.get("max_rr", old_rr)
            tp = min(tp_raw, P["max_rr"] * risk) if P["max_rr"] else tp_raw
            if tm.get("be"):
                X = A.X_of({"be": {"r": tm["be"]}})
        else:
            tp = min(best, P["max_rr"] * risk) if P["max_rr"] else best
        try:
            t = A.asim(X, z, ep, ep + tp, False, stop0, use1, None)
        finally:
            P["max_rr"] = old_rr
        if t is None:
            continue
        t["tm"] = bool(tm)
        t["z_k"] = z["k"]
        if flag:
            t["tag"] = flag(z)
        busy = t["exit_i"]
        nday[z["day"]] += 1
        first.setdefault(z["day"], t)
        out.append(t)
    return out


_LIVE = None


def live():
    global _LIVE
    if _LIVE is None:
        _LIVE = run()
    return _LIVE


# ================================================================================================ idea 1: scale-in path simulator
def padd(t, R):
    """Re-play one live trade on its 1m path with adds. R = {"trig": "none"|"imm"|"cisd"|"pull", "p": pull level (R above entry),
    "pb": min pullback depth (R) for cisd, "n": adds (1-2), "rat": move the stop to the latest add's breakeven once that add is
    +1 of its own risk, "min_rk": min add risk pts}. Returns the base fields (pts, exit, w1) + w_pre + adds."""
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
    cur, be_done = stop0, False
    worst = 0.0
    adds = []          # dicts: px, dist, rk, prev_rk, k, w_ph
    pend = False       # market add at the next open
    lim = None         # resting add limit
    base_k = None      # bar from which a cisd pullback is searched
    rat_lvl = None     # (trigger price, new stop)
    exit_px = kind = None
    k = k0

    def _fill(px, kk):
        a = {"px": px, "dist": px - entry, "rk": px - cur, "prev_rk": [b["px"] - cur for b in adds], "k": kk, "w_ph": 0.0}
        adds.append(a)
        return a

    w_pre = 0.0
    while k < B.n:
        if B.day[k] != sday or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c[k]) - SLIP, "EOD"; break
        fresh_lim = False
        if pend:
            pend = False
            px = float(o[k]) + SLIP
            if px < tg and px - cur >= R.get("min_rk", 2.0):
                _fill(px, k)
                if R.get("rat"):
                    rat_lvl = (px + (px - cur), px)
        if lim is not None and lo[k] <= lim and len(adds) < nmax:
            px = min(lim, float(o[k]))
            if px - cur >= R.get("min_rk", 2.0):
                _fill(px, k); fresh_lim = True
                if R.get("rat"):
                    rat_lvl = (px + (px - cur), px)
            lim = None
        lw = float(lo[k]) - entry
        worst = min(worst, lw)
        if adds:
            adds[-1]["w_ph"] = min(adds[-1]["w_ph"], lw)
        else:
            w_pre = min(w_pre, lw)
        if lo[k] <= cur:
            exit_px, kind = cur - SLIP, ("BE" if be_done else "STOP"); break
        if not (k == k0 and limit_fill):
            if hi[k] >= tg:
                exit_px, kind = tg, "TARGET"
                if fresh_lim:                       # order inside the bar unknown: the add is not credited with the target
                    a = adds.pop()
                    if adds:
                        adds[-1]["w_ph"] = min(adds[-1]["w_ph"], a["w_ph"])
                    else:
                        w_pre = min(w_pre, a["w_ph"])
                break
        if B.mod[k] >= flat:
            exit_px, kind = float(c[k]) - SLIP, "EOD"; break
        # ---- end of bar k decisions (act from bar k + 1)
        if not be_done and not (k == k0 and limit_fill) and hi[k] >= be_lvl:
            cur, be_done = max(cur, entry), True
            base_k = k
            if trig == "imm" and nmax >= 1:
                pend = True
            elif trig == "pull":
                lim = entry + R.get("p", 0.5) * risk
        elif be_done and rat_lvl is not None and hi[k] >= rat_lvl[0]:
            cur = max(cur, rat_lvl[1]); rat_lvl = None
        if be_done and trig == "cisd" and len(adds) < nmax and not pend and k > base_k:
            seg = lo[base_k + 1:k + 1]
            lowk = base_k + 1 + int(np.argmin(seg))
            hmax = float(hi[base_k:lowk + 1].max())
            if k > lowk and hmax - lo[lowk] >= R.get("pb", 0.25) * risk:
                cz = lit._cisd_level(c, o, lowk)
                if cz is not None and c[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == sday:
                    pend = True
                    base_k = k + 1
        elif be_done and trig == "imm" and len(adds) < nmax and adds and not pend and rat_lvl is None and k > adds[-1]["k"] \
                and len(adds) == 1 and nmax == 2:
            pend = True                              # 2nd immediate add once the first add's stop moved (needs rat)
        k += 1
    if exit_px is None:
        return None
    for a in adds:
        a["pts"] = exit_px - a["px"]
    return {"pts": round(exit_px - entry, 4), "exit": kind, "w1": round(worst, 4), "w_pre": round(w_pre, 4),
            "adds": [{k_: (round(v, 4) if isinstance(v, float) else v) for k_, v in a.items()} for a in adds]}


def scale_units(R, start=1.0, f=1.0):
    out = []
    for t in live():
        x = dict(t)
        if t["on1"] and R.get("trig", "none") != "none":
            s = padd(t, R)
            x.update(pts=s["pts"], exit=s["exit"], w1=s["w1"], w_pre=s["w_pre"], adds=s["adds"], legs=[(1.0, s["pts"])], add_f=f)
        x["m"] = start
        out.append(x)
    return out


def check():
    U = live()
    ref = A.unit()
    ka = [(t["day"], t["entry_t"], t["exit"], round(t["pts"], 2), t["risk"], round(t["tgt"], 2)) for t in ref]
    kb = [(t["day"], t["entry_t"], t["exit"], round(t["pts"], 2), t["risk"], round(t["tgt"], 2)) for t in U]
    print(f"executor: {sum(1 for a, b in zip(ka, kb) if a == b)}/{len(ka)} equal to lit_adv_manage.unit() ({len(kb)} trades)")
    bad = 0
    for t in U:
        if not t["on1"]:
            continue
        s = padd(t, {"trig": "none"})
        if s["exit"] != t["exit"] or abs(s["pts"] - t["pts"]) > 1e-6 or abs(s["w1"] - t["w1"]) > 1e-6:
            bad += 1; print("padd mismatch", t["day"], t["exit"], t["pts"], t["w1"], s)
    print(f"add simulator with no add: {sum(1 for t in U if t['on1']) - bad}/{sum(1 for t in U if t['on1'])} equal")
    o = short(score(U))
    print(line("live", o))
    return o


def grid1(b):
    print("== idea 1: scale-in")
    g = "scale"
    trigs = [("imm", {"trig": "imm"}), ("cisd pb0.25", {"trig": "cisd", "pb": 0.25}), ("cisd pb0.5", {"trig": "cisd", "pb": 0.5}),
             ("pull 0.25R", {"trig": "pull", "p": 0.25}), ("pull 0.5R", {"trig": "pull", "p": 0.5}),
             ("pull 0.75R", {"trig": "pull", "p": 0.75})]
    for nm, R in trigs:
        for rat in (False, True):
            for n in ((1, 2) if R["trig"] == "cisd" or (R["trig"] == "imm" and rat) else (1,)):
                for f in (0.5, 1.0, "max"):
                    for start in (1.0, 0.5):
                        RR = {**R, "rat": rat, "n": n}
                        U = scale_units(RR, start, f)
                        lab = f"{nm}{' rat' if rat else ''} n{n} add {f} start {start}"
                        na = sum(1 for t in U if t.get("adds"))
                        record(g, lab, U, {"R": RR, "start": start, "f": f, "trades_with_add": na})
    for start in (0.5, 0.75):
        record(g, f"no add, start {start}", scale_units({"trig": "none"}, start, 1.0), {"start": start})


# ================================================================================================ idea 2: trend-day mode
_F = None


def feats():
    """Per 2026 setup z (keyed by z["i"]): facts known at the 5m setup bar close."""
    global _F
    if _F is not None:
        return _F
    cx = A.ctx(); M = cx.M
    rng = np.array([float(M.h[s:e].max() - M.l[s:e].min()) for _, s, e in M.days])
    tr5 = np.array([float(np.mean(M.h[s:e] - M.l[s:e])) for _, s, e in M.days])
    vix = [M.ctx[k].get("vix") for k in range(len(M.days))]
    F = {}
    for z in cx.C:
        if z["day"] < "2026-01-01":
            continue
        k = z["k"]; x = M.ctx[k]; s = x["s"]; i = z["i"]; d = z["dir"]
        a20 = float(rng[max(0, k - 20):k].mean()) if k > 0 else np.nan
        t20 = float(tr5[max(0, k - 20):k].mean()) if k > 0 else np.nan
        vm = x.get("vix_move")
        v20 = [v for v in vix[max(0, k - 20):k] if v]
        F[i] = {"on_rng": float(M.h[s:i + 1].max() - M.l[s:i + 1].min()) / a20,
                "cov": (float(M.c[i]) - x["open18"]) * d / vm if vm else np.nan,
                "lvl_htf": 1.0 if any(n.startswith(("pd", "pw", "pm")) for n in z["swept"]) else 0.0,
                "disp": float(z["disp"]),
                "vix": x.get("vix") or np.nan, "vxn": x.get("vxn") or np.nan,
                "vix_rel": (x.get("vix") or np.nan) / (np.mean(v20) if v20 else np.nan),
                "atr_rel": float(z["atr"]) / t20 if t20 else np.nan,
                "mod": int(M.mod[z["ext_i"]]), "ext_t": int(M.t[z["ext_i"]])}
    _F = F
    return F


TMODES = {"bank12": {"max_rr": 12.0}, "bank15": {"max_rr": 15.0}, "nobank": {"max_rr": None}, "be2": {"be": 2.0},
          "be2 nobank": {"be": 2.0, "max_rr": None}, "band2": {"tgt_add": 1.0}, "band2 nobank": {"tgt_add": 1.0, "max_rr": None},
          "band2 be2": {"tgt_add": 1.0, "be": 2.0}}
TFEATS = ["on_rng", "cov", "lvl_htf", "disp", "vix"]


def _qs(fn, qs):
    F = feats()
    v = [F[t["z_i"]][fn] for t in live() if t["day"] <= "2026-06-30" and np.isfinite(F[t["z_i"]][fn])]
    return [float(np.quantile(v, q)) for q in qs]


def grid2(b):
    print("== idea 2: trend-day mode")
    g = "trend"
    F = feats()
    # every mode on every trade (the ceiling of each mode)
    for mn, tm in TMODES.items():
        record(g, f"ALL days {mn}", run(tmode=lambda z, ep, r, best, tm=tm: tm), {"mode": mn})
    # classifier: feature x threshold x side, fitted on H1
    QS = (0.2, 0.33, 0.5, 0.67, 0.8)
    fit = []
    for fn in TFEATS:
        ths = [0.5] if fn == "lvl_htf" else _qs(fn, QS)
        for qi, th in enumerate(ths):
            for side in ((">=",) if fn == "lvl_htf" else (">=", "<=")):
                for mn, tm in TMODES.items():
                    def hook(z, ep, r, best, fn=fn, th=th, side=side, tm=tm):
                        v = F[z["i"]][fn]
                        if not np.isfinite(v):
                            return None
                        return tm if ((v >= th) if side == ">=" else (v <= th)) else None
                    U = run(tmode=hook)
                    nf = sum(1 for t in U if t["tm"])
                    lab = f"{fn} {side} {th:.3g} (q{QS[qi] if fn != 'lvl_htf' else '-'}) {mn}"
                    o = record(g, lab, U, {"feat": fn, "th": th, "side": side, "q": None if fn == "lvl_htf" else QS[qi], "mode": mn,
                                           "flagged": nf}, quiet=True)
                    fit.append((lab, o))
    # H1 pick: both p10 and net up on H1, best H1 p10 then net
    cand = [(lab, o) for lab, o in fit if o["H1"]["p10"] > b["H1"]["p10"] and o["H1"]["net"] > b["H1"]["net"]]
    cand.sort(key=lambda x: (x[1]["H1"]["p10"], x[1]["H1"]["net"]), reverse=True)
    RES.setdefault("trend_pick", {})["h1_top"] = [lab for lab, _ in cand[:10]]
    print(f"H1 candidates (p10 and net up in H1): {len(cand)} of {len(fit)}; held in H2 (both up): "
          f"{sum(1 for _, o in cand if o['H2']['p10'] > b['H2']['p10'] and o['H2']['net'] > b['H2']['net'])}")
    for lab, o in cand[:10]:
        print(line(lab, o))
    print("strict adopt (both halves, both metrics):")
    for lab, o in fit:
        if better(o, b):
            print(line(lab, o))


# ================================================================================================ idea 3: volatility-regime tilt
def tilt_units(fn, th, hi_m, lo_m):
    F = feats()
    out = []
    for t in live():
        v = F[t["z_i"]][fn]
        m = 1.0 if not np.isfinite(v) else (hi_m if v >= th else lo_m)
        out.append({**t, "m": m})
    return out


def grid3(b):
    print("== idea 3: volatility-regime size tilt")
    g = "vol"
    shapes = [("hi x0.75 / lo x1.25", 0.75, 1.25), ("hi x1.25 / lo x0.75", 1.25, 0.75), ("hi x0.5", 0.5, 1.0), ("lo x0.5", 1.0, 0.5),
              ("hi x1.5", 1.5, 1.0), ("lo x1.5", 1.0, 1.5), ("hi x0.67 / lo x1.5", 0.67, 1.5), ("hi x1.5 / lo x0.67", 1.5, 0.67)]
    QS = (0.33, 0.5, 0.67)
    for fn in ("vix", "vxn", "vix_rel", "atr_rel"):
        ths = [(f"q{q}", th) for q, th in zip(QS, _qs(fn, QS))]
        if fn in ("vix", "vxn"):
            ths += [(f"{lv}", float(lv)) for lv in ((16, 18, 20, 22) if fn == "vix" else (20, 22, 24, 26))]
        for tl, th in ths:
            for sn, hm, lm in shapes:
                U = tilt_units(fn, th, hm, lm)
                nh = sum(1 for t in U if t["m"] == hm)
                record(g, f"{fn} >= {th:.3g} ({tl}) {sn}", U, {"feat": fn, "th": th, "hi_m": hm, "lo_m": lm, "n_hi": nh}, quiet=True)
    R = RES[g]
    good = [k for k, o in R.items() if better(o, b)]
    print(f"{len(good)} of {len(R)} tilts better in both halves on net $ and 2-week pass")
    for k in sorted(R, key=lambda k: min(R[k]['H1']['p10'] - b['H1']['p10'], R[k]['H2']['p10'] - b['H2']['p10']), reverse=True)[:12]:
        print(line(k, R[k]))


# ================================================================================================ idea 4: news-event setups
_EV = None


def events(impacts=("high",), times=(510, 600, 840)):
    global _EV
    if _EV is None:
        _EV = list(csv.DictReader(open(os.path.join(ROOT, "data", "news", "events.csv"), encoding="utf-8")))
    E = collections.defaultdict(list)
    for r in _EV:
        h, m = r["time_et"].split(":")
        mm = int(h) * 60 + int(m)
        if r["impact"] in impacts and mm in times:
            E[r["date"]].append(mm)
    return E


def is_news(z, E, win=15):
    F = feats()
    m = F[z["i"]]["mod"]
    return any(rel <= m < rel + win for rel in E.get(z["day"], []))


def grid4(b):
    print("== idea 4: news-event setups")
    g = "news"
    for imp_lab, imps in (("high", ("high",)), ("high+med", ("high", "medium"))):
        for win in (10, 15, 20):
            E = events(imps)
            fl = lambda z, E=E, win=win: is_news(z, E, win)          # noqa: E731
            U = run(flag=fl)
            nn = sum(1 for t in U if t["tag"])
            for m in (0.5, 0.75, 1.25, 1.5):
                record(g, f"[{imp_lab} {win}m] live set, news trades x{m}", [{**t, "m": m if t["tag"] else 1.0} for t in U],
                       {"news_trades": nn}, quiet=True)
            for cond in ("any", "stop"):
                def n2(z, first, E=E, win=win, cond=cond):
                    return is_news(z, E, win) and (cond == "any" or first["exit"] == "STOP")
                U2 = run(news2=n2, flag=fl)
                n_x = len(U2) - len(U)
                for m in (1.0, 0.5):
                    seen = set()
                    V = []
                    for t in U2:
                        second = t["day"] in seen
                        seen.add(t["day"])
                        V.append({**t, "m": m if second else 1.0})
                    record(g, f"[{imp_lab} {win}m] + 2nd trade if news ({cond}) x{m}", V, {"extra": n_x}, quiet=True)
            print(f"[{imp_lab} {win}m] news-flagged live trades {nn}", flush=True)
    R = RES[g]
    for k in R:
        print(line(k, R[k]))


def diag4():
    """How news setups trade at unit size (all setups that fill alone would need the setup cache; here: the live set and the
    extra second trades), per half."""
    E = events(("high",))
    out = {}
    for win in (15,):
        fl = lambda z: is_news(z, E, win)                         # noqa: E731
        U2 = run(news2=lambda z, first: is_news(z, E, win), flag=fl)
        for h, (a, zz) in (("H1", A.SPANS["H1"]), ("H2", A.SPANS["H2"])):
            T = [t for t in U2 if a <= t["day"] <= zz and t["tag"]]
            out[h] = {"n": len(T), "R": round(sum(t["pts"] / t["risk"] for t in T), 2),
                      "exits": dict(collections.Counter(t["exit"] for t in T))}
    RES["news_diag"] = out
    print("news-flagged trades (live + 2nd), unit R:", out)


# ================================================================================================ main
def grid(which=None):
    global RES
    RES = json.load(open(OUT)) if os.path.exists(OUT) else {}
    b = check()
    RES["base"] = b
    for k, fn in (("1", grid1), ("2", grid2), ("3", grid3), ("4", grid4)):
        if which and k not in which:
            continue
        fn(b)
        _dump()
    if not which or "4" in which:
        diag4()
    _dump()
    print("->", OUT)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "grid":
        grid(sys.argv[2:] or None)
