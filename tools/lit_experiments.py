"""LIT experiments (owner, 2026-10-18: "test other things", trade it like a person with risk management on a 50K).

Wraps engine/lit.py (not edited) and tools/lit_final.py (cached market + candidates). Start point = LIT final
(research/lit/lit_final.json). Judged on 2026: pick on H1 (Jan 2 - Jun 30), check on H2 (Jul 1 - Oct 16), adopt only if both
halves improve; 2021-25 is a reference line (5m only, no 1m data).

  A  sizing and risk like a prop trader      risk $ per trade (scaled and flat), setup grade A/B/C, smaller until the week's
                                             first winner, bigger once the eval is up $1,000+, risk capped by the room left to
                                             the MFFU $2,000 trailing max loss (EOD trailing, intraday breach, locks at +$100)
  B  a second session (New York)             NY killzones 09:30-11:30 / 13:30-15:30, London + NY boxes as the swept liquidity,
                                             only when London did not trade / only when London won / always; 1 vs 2 a day
  C  draws on liquidity as targets            weekly / monthly highs-lows, NWOG/NDOG, Asia/London extremes, equal highs/lows,
                                             the VIX (current) and VXN bands, partials at the first pool then the HTF draw
  D  stops                                    sweep extreme (current) vs the protected 1m swing (low since the tap) vs the post-
                                             sweep higher low vs the swept pool vs the inducement, with buffers

  python tools/lit_experiments.py check      # xrun(final) == engine/lit.run_x(final) trade for trade; eval_game == rl.score
  python tools/lit_experiments.py A|B|C|D    # one family -> research/lit/experiments_results.json
  python tools/lit_experiments.py all        # A B C D
  python tools/lit_experiments.py combo      # the H1 picks combined, + 2021-25 reference
  python tools/lit_experiments.py save       # store the runs lit_x_* (rl.save, family other, tag lit)
1 CPU process.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine.analytics import PLANS  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "experiments_results.json")
SESS = F.SESS
SPAN = F.SPAN
PV, COMM, SLIP, MAXQ = lit.PV, lit.COMM, lit.SLIP, lit.MAX_MICROS
PLAN = PLANS["builder_50k"]

# extra options on top of lit.DEFAULTS (all default to today's behaviour)
XDEF = {
    "stop_mode": "ext",     # ext = beyond the 5m sweep extreme (current) | tap = beyond the low since the limit tap (1m protected
                            # swing, needs cisd1m) | post = beyond the lowest low after the extreme bar up to the fill (the higher low)
                            # | level = beyond the swept pool | idm = beyond the deepest qualifying inducement low below the entry
    "stop_atr": 0.0,        # extra buffer in ATR(14, 5m at the extreme) on top of stop_buf
    "partial": None,        # {"classes": [...], "min_r": 1.0, "frac": 0.5, "be": True}: close frac at the nearest pool of
                            # these classes >= min_r R from the fill (before the main target), stop to breakeven after it
    "after": None,          # {day: unix t}: only setups whose entry bar opens after t (a second-session leg)
    "days": None,           # set of days the run may trade (None = all)
}
FINAL = F.final_params()


def P_of(P):
    return {**lit.DEFAULTS, **XDEF, **FINAL, **(P or {})}


# ------------------------------------------------------------------------------------------------ executor (unit size)
def _targets(M, z, P, classes):
    T = {c: z["targets"].get(c, []) for c in classes if c not in ("vix", "vxn")}
    x = M.ctx[z["k"]]
    for c in ("vix", "vxn"):
        if c in classes:
            vm = x.get(c + "_move")
            if vm:
                p = x["open18"] * z["dir"] + P["vix_k"] * vm
                if p > z["entry_d"]:
                    T[c] = [round(p - z["entry_d"], 2)]
    return T


def _nearest(TT, classes, min_d):
    best = best_c = None
    for c in classes:
        for dist in TT.get(c, []):
            if dist >= min_d:
                if best is None or dist < best:
                    best, best_c = dist, c
                break
    return best, best_c


def _plan_stop(M, z, P):
    """Direction-space stop known at the setup (ext / level / idm), or None (then ext)."""
    buf = P["stop_buf"] + P["stop_atr"] * z["atr_ext"]
    ext = z["ext_d"] - buf
    mode = P["stop_mode"]
    if mode == "level":
        return max(z["sw"].values()) - buf
    if mode == "idm" and z.get("idm_a"):
        lev = max(z["sw"].values()); a = float(M.atr[z["sweep_i"]])
        dm, age, _ = P["idm_a"] or (1.0, 36, 1)
        px = [lev + dd * a for dd, aa in z["idm_a"] if dd <= dm and aa <= age]
        if px:
            return min(px) - buf
    return ext


def xsim(M, B, z, entry_px, tgt, stop, P, p1_lvl=None):
    """lit.simulate_x (research mode) at 1 micro, plus the stop modes tap/post, partials and per-leg points for exact
    re-sizing. Returns a unit trade or None."""
    d = z["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    t0 = int(M.t[z["entry_i"]])
    k0 = int(np.searchsorted(B.t, t0))
    s_day = int(M.day_of[z["entry_i"]])
    if k0 >= B.n:
        return None
    flat = P["flat_mod"]
    wait_s = P["wait"] * 300
    cis = P.get("cisd1m")
    if cis and B.secs == 300:
        cis = max(1, cis // 5)
    tgt_cancel = entry_px + tgt[1] if tgt[0] == "pts" else tgt[1]
    limit_fill = True
    fill = tapped = None
    k = k0
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= flat or B.mod[k] >= 1080:
            break
        if tapped is None and B.t[k] >= t0 + wait_s:
            break
        if lo_d[k] <= stop:
            if tapped is None and lo_d[k] <= entry_px and not cis:
                fill = k; entry = min(entry_px, float(o_d[k]))
            break
        if tapped is None and lo_d[k] <= entry_px:
            if cis:
                tapped = k
            else:
                fill = k; entry = min(entry_px, float(o_d[k])); break
        if tapped is None and hi_d[k] >= tgt_cancel:
            break
        if tapped is not None:
            if k - tapped > cis:
                break
            lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
            cz = lit._cisd_level(c_d, o_d, lowk)
            if cz is not None and k > lowk and c_d[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == s_day:
                fill = k + 1; entry = float(o_d[k + 1]) + SLIP; limit_fill = False; break
        k += 1
    if fill is None:
        return None
    buf = P["stop_buf"] + P["stop_atr"] * z["atr_ext"]
    if P["stop_mode"] in ("tap", "post") and not limit_fill:
        if P["stop_mode"] == "tap":
            lo = float(lo_d[tapped:fill].min())
        else:
            a = int(np.searchsorted(B.t, int(M.t[z["ext_i"]]) + 300))
            lo = float(lo_d[a:fill].min()) if fill > a else float(lo_d[tapped:fill].min())
        st = min(lo - buf, entry - P["min_stop"])           # at least min_stop wide
        stop = max(stop, st)                                # never wider than the extreme stop
    risk = entry - stop
    if risk <= 0:
        return None
    if tgt[0] == "pts":
        tg = entry + tgt[1]
    else:
        if tgt[2]:
            tg = entry + P["fallback_rr"] * risk
        else:
            dist = tgt[1] - entry
            if dist < P["min_rr"] * risk:
                return None
            tg = entry + (min(dist, P["max_rr"] * risk) if P["max_rr"] else dist)
    p1 = None
    if p1_lvl is not None and P["partial"]:
        if p1_lvl - entry >= P["partial"].get("min_r", 1.0) * risk and p1_lvl < tg:
            p1 = p1_lvl
    be_r = P["be_r"]
    cur, be_done, mfe, mae, worst, worst2 = stop, False, 0.0, 0.0, 0.0, 0.0
    part = False
    k = fill
    exit_px = kind = None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        mae = max(mae, (entry - lo_d[k]) / risk)
        if part:
            worst2 = min(worst2, lo_d[k] - entry)
        else:
            worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("BE" if be_done else "STOP"); break
        if not (k == fill and limit_fill):
            mfe = max(mfe, (hi_d[k] - entry) / risk)
            if hi_d[k] >= tg:
                if p1 is not None and not part:
                    part = True
                exit_px, kind = tg, "TARGET"; break
            if p1 is not None and not part and hi_d[k] >= p1:
                part = True
                if P["partial"].get("be", True):
                    cur, be_done = max(cur, entry), True
            if be_r is not None and not be_done and hi_d[k] >= entry + be_r * risk:
                cur, be_done = entry, True
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        k += 1
    if exit_px is None:
        return None
    f = P["partial"]["frac"] if part else 0.0
    legs = [(f, p1 - entry), (1.0 - f, exit_px - entry)] if part else [(1.0, exit_px - entry)]
    xi5 = int(np.searchsorted(M.t, B.t[k], side="right") - 1)
    return {"day": z["day"], "entry_t": int(B.t[fill]), "exit_t": int(B.t[k]) + B.secs, "exit_i": xi5, "dir": d,
            "risk_pts": round(risk, 2), "exit": kind, "trigger": "LIT-" + ("1m" if B.secs == 60 else "5m"), "mfe": round(mfe, 3),
            "mae": round(min(mae, 1.0 + SLIP / risk), 3), "bars_held": int(k - fill + 1), "regime": "", "half": False,
            "legs": legs, "w1": worst, "w2": worst2, "part": part,
            "entry_px": round(entry * d, 2), "stop_px": round(stop * d, 2), "target_px": round(tg * d, 2), "swept": z["swept"],
            "tf": B.secs // 60, "ext_i": z["ext_i"], "sweep_i": z["sweep_i"],
            # setup features known at entry (for grade sizing)
            "f_disp": z["disp"], "f_depth": z["depth_atr"], "f_how": bool(z["how"]), "f_vec": bool(z["vec"]),
            "f_idm": sum(1 for dd, aa in z["idm_a"] if dd <= 1.0 and aa <= 36), "f_cls": z["swept_cls"], "f_mod": z["mod"],
            "f_wk_ext": bool(z["wk_ext"])}


def xrun(P=None, sessions=SESS):
    """Unit-size trades of one variant (lit._run_core research mode + the XDEF options)."""
    P = P_of(P)
    names = set(P["sweep_names"]) if P.get("sweep_names") else None
    sset = set(sessions) if sessions else None
    M, C = F.market(P["ref"], P["extra_boxes"])
    B5 = F.bars(M, "5m")
    B1 = F.bars(M, "1m") if P["tf"] == "1m" else None
    after, days = P.get("after") or {}, P.get("days")
    out, busy, per_day = [], -1, collections.Counter()
    pclasses = (P["partial"] or {}).get("classes")
    for z in C:
        if sset is not None and z["day"] not in sset:
            continue
        if days is not None and z["day"] not in days:
            continue
        if z["day"] in after and int(M.t[z["entry_i"]]) <= after[z["day"]]:
            continue
        if z["entry_i"] <= busy or per_day[z["day"]] >= P["max_per_day"]:
            continue
        if not lit.setup_ok(z, P, names):
            continue
        ep = min(float(z["ref_d"]), z["trig_c"])
        stop = _plan_stop(M, z, P)
        risk = ep - stop
        if not (P["min_stop"] <= risk <= P["max_stop"]):
            continue
        sh = z["entry_d"] - ep
        allc = list(P["classes"]) + [c for c in (pclasses or []) if c not in P["classes"]]
        TT = {c: [x + sh for x in v] for c, v in _targets(M, z, P, allc).items()}
        best, _ = _nearest(TT, P["classes"], P["min_rr"] * risk)
        fb = False
        if best is None:
            if not P["fallback_rr"]:
                continue
            tp, fb = P["fallback_rr"] * risk, True
        else:
            tp = min(best, P["max_rr"] * risk) if P["max_rr"] else best
        p1 = None
        if pclasses:
            b1, _ = _nearest(TT, pclasses, P["partial"].get("min_r", 1.0) * risk)
            if b1 is not None and b1 < tp:
                p1 = ep + b1
        use1 = P["tf"] == "1m" and B1 is not None and int(M.day_of[z["entry_i"]]) in B1.full
        B = B1 if use1 else B5
        tgt = ("lvl", ep + tp, fb) if P.get("cisd1m") else ("pts", tp)
        t = xsim(M, B, z, ep, tgt, stop, P, p1)
        if t is None or lit.qty_for(t["risk_pts"]) < 1:     # as run_x: no micro at the LIT rule -> no trade (stop > ~89 pts)
            continue
        busy = t["exit_i"]; per_day[z["day"]] += 1
        out.append(t)
    return out


# ------------------------------------------------------------------------------------------------ sizing (exact, integer micros)
def base_qty(t, risk_usd=800.0, ref_stop=20.0):
    """$risk_usd up to a ref_stop-pt stop, then risk_usd*ref_stop/stop (ref_stop None = flat $ at any stop); max 40."""
    rp = t["risk_pts"]
    r = risk_usd if (ref_stop is None or rp <= ref_stop) else risk_usd * ref_stop / rp
    return max(0, min(MAXQ, int(r / (rp * PV))))


def at_qty(t, q):
    """The unit trade at q micros (P&L, commission, slippage linear; a partial splits the micros, 1 micro = all runner)."""
    q = int(q)
    if len(t["legs"]) == 2 and q >= 2:
        f = t["legs"][0][0]
        q1 = min(q - 1, max(1, int(q * f + 0.5)))
        qs = [q1, q - q1]
    elif len(t["legs"]) == 2:
        qs = [0, 1]
    else:
        qs = [q]
    pts = sum(n * p for n, (_, p) in zip(qs, t["legs"]))
    pnl = pts * PV - COMM * q
    lows = [0.0, t["w1"] * PV * q - COMM * q, pnl]
    if len(t["legs"]) == 2 and t["part"]:
        lows.append((qs[0] * t["legs"][0][1] + qs[1] * t["w2"]) * PV - COMM * q)
    rp = t["risk_pts"]
    unit = sum(f * p for f, p in t["legs"]) * PV - COMM
    return {**t, "qty": q, "pnl": round(pnl, 2), "low": round(min(lows), 2), "risk_usd": round(rp * PV * q, 2),
            "r": round(unit / (rp * PV), 3), "mult": 1.0}


def sized(T, qfn=None, mult=None):
    """Fixed (state-free except own finished trades) sizing. qfn(t, ctx) -> micros (0 = skip); default the LIT rule.
    mult(t, ctx) -> multiplier on the LIT rule's micros (floor 1)."""
    out = []
    srt = sorted(T, key=lambda t: t["entry_t"])
    for t in srt:
        ctx = {"done": [x for x in out if x["exit_t"] <= t["entry_t"]]}
        q0 = base_qty(t)
        if qfn is not None:
            q = qfn(t, ctx)
        else:
            q = q0
            if mult is not None:
                m = mult(t, ctx)
                q = 0 if m <= 0 else (max(1, int(q0 * m + 1e-9)) if m < 1 else min(MAXQ, int(q0 * m + 1e-9)))
        if q < 1:
            continue
        x = at_qty(t, q)
        x["mult"] = round(q / q0, 3) if q0 else 1.0
        x["half"] = q < q0
        out.append(x)
    return out


# ------------------------------------------------------------------------------------------------ eval game (state sizing)
def eval_game(T, span="2026", sizer=None, horizon=60, day_stop=None, b2b=True):
    """Start a fresh MFFU Builder 50K eval on every session of the span (as rl.eval_speed): $3,000 target, $2,000 max loss
    trailing the end-of-day balance high (an intraday low through it fails), locked at start + $100. sizer(t, st) -> micros,
    st = {"profit", "room" (balance - max-loss line, at the trade), "day_pnl", "n", "wins", "week_win", "peak"}; day_stop =
    no new trade once the day is down that many $. Also plays evals back to back (a new one the session after each ends)
    and returns that path's trades for the $ columns."""
    a, z = SPAN[span]
    ss = [d for d in SESS if a <= d <= z]
    by = collections.defaultdict(list)
    for t in sorted(T, key=lambda t: t["entry_t"]):
        if a <= t["day"] <= z:
            by[t["day"]].append(t)
    sizer = sizer or (lambda t, st: base_qty(t))

    def play(i0, H, keep=None):
        bal = PLAN["start"]; peak = bal; mll = bal - PLAN["mll"]; lock = PLAN["start"] + PLAN["lock_above"]
        n = wins = 0; wk_win = set()
        for k in range(i0, min(len(ss), i0 + H)):
            d = ss[k]
            cum = low = 0.0
            wk = dt.date.fromisoformat(d).isocalendar()[:2]
            for t in by.get(d, []):
                if day_stop is not None and cum <= -day_stop:
                    break
                st = {"profit": bal + cum - PLAN["start"], "room": bal + cum - mll, "day_pnl": cum, "n": n, "wins": wins,
                      "week_win": wk in wk_win, "peak": peak}
                q = int(sizer(t, st))
                if q < 1:
                    continue
                x = at_qty(t, min(MAXQ, q))
                low = min(low, cum + x["low"]); cum += x["pnl"]; low = min(low, cum)
                n += 1
                if x["pnl"] > 0:
                    wins += 1; wk_win.add(wk)
                if keep is not None:
                    keep.append(x)
            if bal + low <= mll or bal + cum <= mll:
                return "FAIL", k - i0 + 1
            bal += cum
            peak = max(peak, bal)
            mll = min(max(mll, peak - PLAN["mll"]), lock)
            if bal - PLAN["start"] >= PLAN["target"]:
                return "PASS", k - i0 + 1
        return "OPEN", min(len(ss), i0 + H) - i0

    res = [play(i, horizon) for i in range(len(ss))]
    N = len(res) or 1
    pct = lambda c: round(100 * c / N, 1)
    o = {}
    for H in (10, 20):
        o[f"p{H}"] = pct(sum(1 for r, n in res if r == "PASS" and n <= H))
        o[f"f{H}"] = pct(sum(1 for r, n in res if r == "FAIL" and n <= H))
    P_ = sum(1 for r, _ in res if r == "PASS"); F_ = sum(1 for r, _ in res if r == "FAIL")
    o["pass_rate"] = round(100 * P_ / (P_ + F_), 1) if P_ + F_ else None
    pas = [n for r, n in res if r == "PASS"]
    o["pass_med"] = float(np.median(pas)) if pas else None
    dec = [n for r, n in res if r != "OPEN"]
    # resets until a pass (renewal): expected sessions = mean length of a decided eval / pass rate; evals bought = 1 / pass rate
    o["exp_sess"] = round(float(np.mean(dec)) / (P_ / len(dec)), 1) if P_ else None
    o["evals_per_pass"] = round(len(dec) / P_, 2) if P_ else None
    if b2b:
        k, pa, fa, path = 0, 0, 0, []
        while k < len(ss):
            r, n = play(k, len(ss), keep=path)
            if r == "OPEN":
                break
            pa += r == "PASS"; fa += r == "FAIL"; k += n
        o["b2b"] = f"{pa}/{fa}"
        o["_path"] = path
    return o


# ------------------------------------------------------------------------------------------------ scoring helpers
SP = ("H1", "H2", "2026", "2021-25")


def sc(T, spans=SP):
    """F.score of sized trades (H1 / H2 / 2026 / 2021-25): net, $/mo, PF, win, tpw, DD, evals, pass rate, net without top 3."""
    o = F.score(T, spans=spans)
    for s in spans:
        if s in o and o[s].get("n"):
            g = eval_game(T, s, lambda t, st: t["qty"], b2b=False)
            o[s]["exp_sess"], o[s]["evals_per_pass"] = g["exp_sess"], g["evals_per_pass"]
    return o


def sc_state(T, sizer, spans=("H1", "H2", "2026"), day_stop=None):
    """State sizing: eval odds from eval_game; $ columns from the back-to-back eval path."""
    out = {}
    for s in spans:
        g = eval_game(T, s, sizer, day_stop=day_stop)
        path = g.pop("_path")
        p = np.array([t["pnl"] for t in path] or [0.0]); gl = -p[p < 0].sum()
        eq = np.cumsum(p); dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if len(path) else 0.0
        a, z = SPAN[s]
        nd = len([d for d in SESS if a <= d <= z])
        out[s] = {"n": len(path), "tpw": round(len(path) / (nd / 5), 2), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
                  "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (nd / 21)), "dd": round(dd),
                  "win": round(100 * float((p > 0).mean()), 1) if path else None, **g}
    return out


def row(nm, o, spans=("H1", "H2", "2026", "2021-25")):
    def f(s):
        if not s or not s.get("n"):
            return "n=0"
        return (f"n={s['n']} {s['tpw']}/wk PF {s['pf']} net {s['net']:+,} DD {s['dd']:,} 2w {s.get('p10')}/{s.get('f10')} "
                f"1m {s.get('p20')}/{s.get('f20')} pr {s.get('pass_rate')} med {s.get('pass_med')} E {s.get('exp_sess')}")
    return f"{nm:34s} " + " | ".join(f"{k}[{f(o.get(k))}]" for k in spans if k in o)


def _load():
    return json.load(open(OUT)) if os.path.exists(OUT) else {}


def _store(fam, nm, rec):
    res = _load()
    res.setdefault(fam, {})[nm] = rec
    json.dump(res, open(OUT, "w"), indent=1, default=str)


_U = {}


def unit(P=None):
    key = json.dumps(P or {}, sort_keys=True, default=str)
    if key not in _U:
        _U[key] = xrun(P)
    return _U[key]


# ------------------------------------------------------------------------------------------------ check
def check():
    T0 = F.run(FINAL)
    U = unit()
    T1 = sized(U)
    a = [(t["day"], t["entry_t"], round(t["pnl"], 2), round(t["low"], 2)) for t in T0]
    b = [(t["day"], t["entry_t"], round(t["pnl"], 2), round(t["low"], 2)) for t in T1]
    same = sum(1 for x, y in zip(a, b) if x[:2] == y[:2] and abs(x[2] - y[2]) < 0.03 and abs(x[3] - y[3]) < 0.03)
    print(f"run_x final {len(a)} trades net {sum(x[2] for x in a):,.0f} | xrun {len(b)} net {sum(x[2] for x in b):,.0f} | same {same}")
    for x, y in zip(a, b):
        if not (x[:2] == y[:2] and abs(x[2] - y[2]) < 0.03):
            print("diff", x, y); break
    o = sc(T1, ("H1", "H2", "2026"))
    for s in ("H1", "H2", "2026"):
        g = eval_game(U, s, b2b=True); g.pop("_path")
        print(s, "rl:", {k: o[s][k] for k in ("p10", "f10", "p20", "f20", "pass_rate", "pass_med", "b2b")}, "| eval_game:", g)


# ================================================================================================ A. sizing / risk
def grade(t, th):
    """Setup grade points: big displacement, deep sweep, 2+ inducements, inside the high/low-of-week window."""
    pts = int(t["f_disp"] >= th["disp"]) + int(t["f_depth"] >= th["depth"]) + int(t["f_idm"] >= 2) + int(bool(t["f_how"]))
    return "A" if pts >= 3 else "B" if pts == 2 else "C"


def fam_A():
    U = unit()
    h1 = [t for t in U if "2026-01-01" <= t["day"] <= "2026-06-30"]
    th = {"disp": float(np.median([t["f_disp"] for t in h1])), "depth": float(np.median([t["f_depth"] for t in h1]))}
    print("grade thresholds (H1 medians):", th)
    res = {"grade_thresholds": th}
    # grade mix and R by grade (2026 halves) - information
    for s in ("H1", "H2", "2021-25"):
        a, z = SPAN[s]
        g = collections.defaultdict(list)
        for t in U:
            if a <= t["day"] <= z:
                g[grade(t, th)].append(at_qty(t, base_qty(t))["pnl"])
        res[f"grade_mix_{s}"] = {k: {"n": len(v), "net": round(sum(v)), "pf": round(sum(x for x in v if x > 0) / max(1e-9, -sum(x for x in v if x < 0)), 2)}
                                 for k, v in sorted(g.items())}
        print(s, res[f"grade_mix_{s}"])
    _store("A", "_info", res)
    V = collections.OrderedDict()
    for R in (400, 600, 700, 800, 900, 1000, 1200, 1500, 2000):
        V[f"risk ${R} to 20 pt, scaled"] = ("fixed", lambda t, c, R=R: max(1, base_qty(t, R, 20.0)))
    for R, ref in ((800, 30.0), (800, 40.0), (600, 30.0), (600, 40.0), (500, 40.0)):
        V[f"risk ${R} to {int(ref)} pt, scaled"] = ("fixed", lambda t, c, R=R, ref=ref: max(1, base_qty(t, R, ref)))
    for R in (200, 300, 400, 500, 600, 800, 1000):
        V[f"risk ${R} flat at any stop"] = ("fixed", lambda t, c, R=R: max(1, base_qty(t, R, None)))
    for m in ((1.5, 1.0, 0.5), (2.0, 1.0, 0.5), (1.25, 1.0, 0.75), (1.0, 1.0, 0.5), (1.5, 1.0, 1.0), (2.0, 1.5, 1.0)):
        V[f"grade A{m[0]} B{m[1]} C{m[2]}"] = ("mult", lambda t, c, m=m: dict(zip("ABC", m))[grade(t, th)])
    for m in (0.5, 0.75):
        V[f"x{m} until the week's first winner"] = ("state", lambda t, st, m=m: base_qty(t) if st["week_win"] else max(1, int(base_qty(t) * m)))
        V[f"x{m} after the week's first winner"] = ("state", lambda t, st, m=m: max(1, int(base_qty(t) * m)) if st["week_win"] else base_qty(t))
    for up, m in ((1000, 1.5), (1000, 2.0), (1500, 1.5), (2000, 0.5), (1000, 0.5)):
        V[f"x{m} once the eval is up ${up}+"] = ("state", lambda t, st, up=up, m=m: min(MAXQ, max(1, int(base_qty(t) * m))) if st["profit"] >= up else base_qty(t))
    for k in (0.15, 0.25, 0.35, 0.5):
        V[f"risk <= {int(k*100)}% of room to max loss"] = ("state", lambda t, st, k=k: max(1, min(base_qty(t), int(k * st["room"] / (t["risk_pts"] * PV)))))
    for R, k in ((600, 0.35), (800, 0.35), (1000, 0.35), (600, 0.5), (800, 0.5), (1000, 0.25)):
        V[f"flat ${R}, cap {int(k*100)}% of room"] = ("state", lambda t, st, R=R, k=k: max(1, min(base_qty(t, R, None), int(k * st["room"] / (t["risk_pts"] * PV)))))
    # money left to target: risk what is needed to finish in ~2 winners (avg winner ~ 5R): never more than flat $R
    for R in (600, 1000):
        V[f"flat ${R}, cap at 40% of the $ left to target"] = ("state", lambda t, st, R=R: min(base_qty(t, R, None), max(1, int(0.4 * (PLAN['target'] - st['profit']) / (t['risk_pts'] * PV)))))
    for nm, (kind, fn) in V.items():
        if kind == "state":
            o = sc_state(U, fn)
        else:
            T = sized(U, qfn=fn) if kind == "fixed" else sized(U, mult=fn)
            o = sc(T, ("H1", "H2", "2026"))
        rec = {"kind": kind, **o}
        _store("A", nm, rec)
        print(row(nm, o), flush=True)


# ================================================================================================ B. second session (New York)
LON_BOX = [f"{n}_{s}" for n in ("lon25", "lon34", "lon23", "asia20", "asia18", "asia19", "pre") for s in "hl"]
NY_BOX = [f"{n}_{s}" for n in ("ny89", "ny830", "ny930", "ny9301030") for s in "hl"]
NYK = [[570, 690], [810, 930]]
LONW = [[120, 480]]


def fam_B():
    L = unit({"window": LONW})
    Lsz = sized(L)
    lon_exit = {t["day"]: t["exit_t"] for t in L}
    lon_win = {t["day"] for t in Lsz if t["pnl"] > 0}
    lon_loss = {t["day"] for t in Lsz if t["pnl"] <= 0}
    o = sc(Lsz); _store("B", "London only 02:00-08:00", o); print(row("London only 02:00-08:00", o), flush=True)
    o = sc(sized(unit())); _store("B", "final (02:00-15:30, 1 a day)", o); print(row("final (02:00-15:30, 1 a day)", o), flush=True)
    NYV = collections.OrderedDict()
    NYV["NY killzones, all levels"] = {"window": NYK}
    NYV["NY killzones, London+Asia+NY boxes"] = {"window": NYK, "sweep_names": LON_BOX + NY_BOX}
    NYV["NY killzones, London+NY boxes+PD"] = {"window": NYK, "sweep_names": LON_BOX + NY_BOX + ["pdh", "pdl"]}
    NYV["NY 08:00-15:30, all levels"] = {"window": [[480, 930]]}
    NYV["NY AM killzone only, all levels"] = {"window": [[570, 690]]}
    allp = ["buildup", "asia", "london", "ny", "pre", "pd", "pw", "pm", "gap"]
    NYV["NY killzones, pools+VIX targets, plain limit"] = {"window": NYK, "classes": allp + ["vix"], "cisd1m": None}
    NYV["NY killzones, pools+VIX targets, no inducement"] = {"window": NYK, "classes": allp + ["vix"], "idm_a": None}
    allS = set(SESS)
    for nyn, NP in NYV.items():
        for rule in ("no London trade", "London won", "London lost", "always (2 a day)"):
            if rule == "no London trade":
                Pn = {**NP, "days": allS - set(lon_exit)}
            elif rule == "London won":
                Pn = {**NP, "days": lon_win, "after": lon_exit}
            elif rule == "London lost":
                Pn = {**NP, "days": lon_loss, "after": lon_exit}
            else:
                Pn = {**NP, "after": lon_exit}
            N = unit(Pn)
            Nsz = sized(N)
            T = sorted(Lsz + Nsz, key=lambda t: t["entry_t"])
            nm = f"London + {nyn} | {rule}"
            o = sc(T)
            o["ny_only"] = F.score(Nsz, spans=("H1", "H2", "2026", "2021-25"), fast=True)
            _store("B", nm, o)
            print(row(nm, o), "| NY leg", {k: (v["n"], v["net"], v["pf"]) for k, v in o["ny_only"].items()}, flush=True)
    # a hard eval-day loss stop only matters with 2 trades a day: the "always" rule with a day stop
    NP = {"window": NYK, "after": lon_exit}
    T = sorted(Lsz + sized(unit(NP)), key=lambda t: t["entry_t"])
    U2 = sorted(L + unit(NP), key=lambda t: t["entry_t"])
    for ds in (300, 500):
        o = sc_state(U2, None, day_stop=ds)
        _store("B", f"London + NY killzones always, day stop ${ds}", o); print(row(f"London + NYk always, day stop ${ds}", o), flush=True)


# ================================================================================================ C. targets / draws on liquidity
def fam_C():
    V = collections.OrderedDict()
    V["VIX band (final)"] = {}
    V["VXN band (Nasdaq vol)"] = {"classes": ["vxn"]}
    V["VXN band x0.8"] = {"classes": ["vxn"], "vix_k": 0.8}
    V["weekly H/L (PWH/PWL)"] = {"classes": ["pw"]}
    V["weekly + monthly H/L"] = {"classes": ["pw", "pm"]}
    V["PDH/PWH/PMH (lit_A)"] = {"classes": ["pd", "pw", "pm"]}
    V["NWOG/NDOG edges"] = {"classes": ["gap"]}
    V["Asia + London extremes"] = {"classes": ["asia", "london"]}
    V["equal highs/lows (build-ups)"] = {"classes": ["buildup"]}
    V["nearest of VIX band or PW/PM"] = {"classes": ["vix", "pw", "pm"]}
    V["nearest of VIX band or gap"] = {"classes": ["vix", "gap"]}
    V["nearest of VIX band or build-up"] = {"classes": ["vix", "buildup"]}
    V["VIX band, no bank"] = {"max_rr": None}
    V["VIX band, bank 6R"] = {"max_rr": 6.0}
    V["VIX band, bank 10R"] = {"max_rr": 10.0}
    allp = ["buildup", "asia", "london", "ny", "pre", "pd", "pw", "pm", "gap"]
    for pc_nm, pc in (("first pool (any)", allp), ("first session pool (Asia/London/NY/pre)", ["asia", "london", "ny", "pre"]),
                      ("first PD/PW/PM", ["pd", "pw", "pm"]), ("first build-up", ["buildup"])):
        for frac, mr in ((0.5, 1.0), (0.5, 2.0), (0.33, 2.0), (0.5, 3.0)):
            V[f"half at {pc_nm} >= {mr}R (frac {frac}), runner to VIX"] = {"partial": {"classes": pc, "min_r": mr, "frac": frac, "be": True}}
    for frac, mr in ((0.5, 2.0),):
        V["half at first pool >= 2R, runner to VIX no bank"] = {"partial": {"classes": allp, "min_r": mr, "frac": frac, "be": True}, "max_rr": None}
        V["half at first pool >= 2R, runner to PW/PM"] = {"partial": {"classes": allp, "min_r": mr, "frac": frac, "be": True}, "classes": ["pw", "pm"], "max_rr": None}
    for nm, P in V.items():
        o = sc(sized(unit(P)))
        _store("C", nm, {"params": P, **o})
        print(row(nm, o), flush=True)


# ================================================================================================ D. stops
def fam_D():
    V = collections.OrderedDict()
    for buf_nm, b, ba in (("1 tick", 0.25, 0.0), ("2 pts", 2.0, 0.0), ("0.1 ATR", 0.25, 0.1), ("0.25 ATR", 0.25, 0.25)):
        V[f"sweep extreme + {buf_nm}"] = {"stop_mode": "ext", "stop_buf": b, "stop_atr": ba}
        V[f"1m protected swing (tap low) + {buf_nm}"] = {"stop_mode": "tap", "stop_buf": b, "stop_atr": ba}
        V[f"post-sweep higher low + {buf_nm}"] = {"stop_mode": "post", "stop_buf": b, "stop_atr": ba}
        V[f"swept pool + {buf_nm}"] = {"stop_mode": "level", "stop_buf": b, "stop_atr": ba}
        V[f"inducement low + {buf_nm}"] = {"stop_mode": "idm", "stop_buf": b, "stop_atr": ba}
    V["1m tap low + 1 tick, min stop 12"] = {"stop_mode": "tap", "min_stop": 12.0}
    V["1m tap low + 1 tick, min stop 15"] = {"stop_mode": "tap", "min_stop": 15.0}
    V["1m tap low + 2 pts, min stop 12"] = {"stop_mode": "tap", "stop_buf": 2.0, "min_stop": 12.0}
    V["swept pool + 2 pts, max stop 60"] = {"stop_mode": "level", "stop_buf": 2.0, "max_stop": 60.0}
    for nm, P in V.items():
        U = unit(P)
        o = sc(sized(U))
        o["median_stop_2026"] = float(np.median([t["risk_pts"] for t in U if t["day"] >= "2026"] or [0]))
        _store("D", nm, {"params": P, **o})
        print(row(nm, o), "| med stop", o["median_stop_2026"], flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd in ("A", "B", "C", "D"):
        globals()["fam_" + cmd]()
    elif cmd == "all":
        for f in (fam_A, fam_B, fam_C, fam_D):
            f()
