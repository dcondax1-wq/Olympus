"""LIT untested bias / regime ideas (owner, 2026-10-18: "Remember our strategy is LIT based nothing that goes outside, try every
single one of these and go find more we haven't tested").

Wraps engine/lit.py (not edited) through tools/lit_tightstop.py on the live LIT settings (live_model.json "lit" = lit_final +
loss pack) with the live eval sizing ($800 up to a 25-pt stop, then 800x25/stop, weekly stop, never more than 60% of the room to
the MFFU max-loss floor: engine/sizing.py lit_qty mode "eval" = run lit_tight_eval_800_25_room60). The setups, the fill, the
stop and the target are the live ones. Only which trades are taken (skip variants: the setup is dropped and the day stays free
for a later LIT setup, like the Monday rule) or their size (one rounding with the weekly stop, floor 1, max 40, room cap after)
changes:

  1. VIX regime sizing: x hi_m when the prior VIX close >= hi (18 / 20 / 22), x lo_m (0.75) when it is < 15.
  2. Target-aware eval sizing: "trim" = when the eval-size trade's target $ already covers what is still needed to +$3,000,
     micros so a target hit just passes (x buf), never above the eval size; "press" = when the room to the trailing floor is
     >= press_room $ and the target is <= press_r x the stop, micros so a target hit passes (never below the eval size, capped
     at 60% of the room, a full stop-out inside the $1,000 soft daily loss, 40 micros).
  3. Weekly profile: on Thursday/Friday, when the week-to-date high (low) at the trigger bar was made inside the high/low-of-
     week window (Tue 03:00 - Wed 11:30 ET, engine in_how_window; "tw" = all of Tuesday + Wednesday), trades toward it (longs
     under a made high, shorts over a made low) are skipped or sized x wp_m. Both extremes in the window: no rule.
  4. Asia range gate: Asia range (18:00-24:00 of the trading day) / daily ATR(14) vs its p20 / p80 of the last 20 days: skip or
     x 0.5 below p20 (lo), above p80 (hi), or both.
  5. Event days: monthly OPEX (third Friday), month-end (last session of the month), quarter-end (last session of Mar/Jun/Sep/
     Dec): skip / x 0.5. Big-tech earnings: no report dates in data/news/events.csv (macro only) -> not tested.

  python tools/lit_t_bias.py check   # defaults == run lit_live (120 trades 2026) and == the baseline eval run numbers
  python tools/lit_t_bias.py grid    # every variant -> research/lit/t_bias_results.json
  python tools/lit_t_bias.py save    # store every variant as run lit_u_bias_* (rl.save, family other, tags lit, lit_untested, lit_bias)
Pick on 2026 H1 (Jan 2 - Jun 30), check on 2026 H2 (Jul 1 - Oct 16); 2021-25 is a reference line (5m only, no 1m data).
1 CPU process. Paper research only.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import math
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_tightstop as TS  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "t_bias_results.json")
SESS, SPAN = F.SESS, F.SPAN
PV, COMM, SLIP, MAXQ = lit.PV, lit.COMM, lit.SLIP, lit.MAX_MICROS
LIVE = TS.LIVE
PLAN, DLL = TS.PLAN, TS.DLL
RULE = ("lit", 800, 25.0)          # live eval sizing: $800 up to a 25-pt stop, then 800x25/stop
ROOM_K = 0.6                       # + never more than 60% of the room to the trailing max-loss floor

BDEF = {
    "vix_hi": None, "vix_hi_m": 1.0, "vix_lo": None, "vix_lo_m": 1.0,
    "tgt_trim": False, "trim_buf": 1.0, "press_room": None, "press_r": None,
    "wp": None, "wp_win": "how", "wp_m": 0.5,
    "asia": None, "asia_m": 0.0, "asia_p": (20, 80), "asia_n": 20,
    "ev": (), "ev_m": 0.0,
}


def B_of(P=None):
    return {**BDEF, **(P or {})}


# ================================================================================================ market features (causal)
_FE = {}


def feats():
    """Per trading day k: prior VIX close, Asia range / ATR(14 days) flags, event flags; known before 02:00 ET."""
    if "f" in _FE:
        return _FE["f"]
    M, _C = F.market(LIVE["ref"], LIVE["extra_boxes"])
    nd = len(M.days)
    rng = np.zeros(nd); asia = np.full(nd, np.nan); tr = np.zeros(nd)
    pc = None
    for k, (d, s, e) in enumerate(M.days):
        hi, lo = float(M.h[s:e].max()), float(M.l[s:e].min())
        tr[k] = max(hi - lo, abs(hi - pc), abs(lo - pc)) if pc is not None else hi - lo
        pc = float(M.c[e - 1])
        md = M.mod[s:e]
        ii = np.flatnonzero(md >= 1080)
        if len(ii) >= 6:
            asia[k] = float(M.h[s + ii].max() - M.l[s + ii].min())
    ratio = np.full(nd, np.nan)
    for k in range(14, nd):
        a = tr[k - 14:k].mean()
        if a > 0 and not np.isnan(asia[k]):
            ratio[k] = asia[k] / a
    # event days from the session calendar (SESS = every trading session in the data)
    days = [d for d, _s, _e in M.days]
    allset = sorted(set(days) | set(SESS))
    month_end, q_end = set(), set()
    for a, b in zip(allset, allset[1:] + ["9999-99-99"]):
        if a[:7] != b[:7]:
            month_end.add(a)
            if int(a[5:7]) in (3, 6, 9, 12):
                q_end.add(a)
    opex = set()
    for d in allset:
        x = dt.date.fromisoformat(d)
        if x.weekday() == 4 and 15 <= x.day <= 21:
            opex.add(d)
    _FE["f"] = {"M": M, "ratio": ratio, "month_end": month_end, "q_end": q_end, "opex": opex}
    return _FE["f"]


def asia_flag(k, P):
    """'lo' / 'hi' / None: today's Asia range ratio vs the p_lo / p_hi of the last asia_n days."""
    f = feats()
    r = f["ratio"]
    n = P["asia_n"]
    if k < n + 14 or np.isnan(r[k]):
        return None
    hist = r[k - n:k]
    hist = hist[~np.isnan(hist)]
    if len(hist) < n // 2:
        return None
    lo, hi = np.percentile(hist, P["asia_p"][0]), np.percentile(hist, P["asia_p"][1])
    return "lo" if r[k] < lo else "hi" if r[k] > hi else None


def week_profile(M, i, win="how"):
    """On a Thursday/Friday trading day: (high made in the window, low made in the window) of the week-to-date range at bar i;
    None on Monday-Wednesday."""
    k = int(M.day_of[i])
    if M.ctx[k]["dow"] < 3:
        return None
    w = int(M.week_id[i])
    s = i
    while s > 0 and int(M.week_id[s - 1]) == w:
        s -= 1
    jh = s + int(np.argmax(M.h[s:i + 1])); jl = s + int(np.argmin(M.l[s:i + 1]))

    def inwin(j):
        if win == "how":
            return bool(M.how[j])
        return int(M.ctx[int(M.day_of[j])]["dow"]) in (1, 2)       # "tw": the Tuesday or Wednesday trading day
    return inwin(jh), inwin(jl)


def wp_against(M, i, d, P):
    x = week_profile(M, i, P["wp_win"])
    if x is None:
        return False
    hi_in, lo_in = x
    if hi_in == lo_in:
        return False
    return (hi_in and d == 1) or (lo_in and d == -1)


def ev_hit(day, P):
    f = feats()
    return any(day in f[e] for e in P["ev"])


def skip_z(M, z, P):
    """Skip variants (the setup is dropped before the fill; the day stays free)."""
    if P["wp"] == "skip" and wp_against(M, z["i"], z["dir"], P):
        return True
    if P["asia"] and P["asia_m"] == 0.0:
        fl = asia_flag(z["k"], P)
        if fl and (P["asia"] == "both" or P["asia"] == fl):
            return True
    if P["ev"] and P["ev_m"] == 0.0 and ev_hit(z["day"], P):
        return True
    return False


def size_m(t, P):
    """Size multiplier of the sizing variants (on top of the weekly stop, one rounding)."""
    M = feats()["M"]
    i = t["i"]; k = int(M.day_of[i])
    m = 1.0
    v = M.ctx[k].get("vix")
    if v is not None:
        if P["vix_hi"] is not None and v >= P["vix_hi"]:
            m *= P["vix_hi_m"]
        elif P["vix_lo"] is not None and v < P["vix_lo"]:
            m *= P["vix_lo_m"]
    if P["wp"] == "size" and wp_against(M, i, t["dir"], P):
        m *= P["wp_m"]
    if P["asia"] and P["asia_m"] > 0.0:
        fl = asia_flag(k, P)
        if fl and (P["asia"] == "both" or P["asia"] == fl):
            m *= P["asia_m"]
    if P["ev"] and P["ev_m"] > 0.0 and ev_hit(t["day"], P):
        m *= P["ev_m"]
    return m


# ================================================================================================ unit trades (= TS.trun + skip hook)
def brun(P=None, sessions=SESS):
    P = B_of(P)
    LP = TS.P_of({})
    names = set(LP["sweep_names"]) if LP.get("sweep_names") else None
    sset = set(sessions) if sessions else None
    M, C = F.market(LP["ref"], LP["extra_boxes"])
    B5 = F.bars(M, "5m")
    B1 = F.bars(M, "1m") if LP["tf"] == "1m" else None
    out, busy, per_day = [], -1, collections.Counter()
    for z in C:
        if sset is not None and z["day"] not in sset:
            continue
        if z["entry_i"] <= busy or per_day[z["day"]] >= LP["max_per_day"]:
            continue
        if not lit.setup_ok(z, LP, names):
            continue
        if LP.get("monday") and lit.monday_block(M, z):
            continue
        if skip_z(M, z, P):
            continue
        ep = min(float(z["ref_d"]), z["trig_c"])
        stop0 = z["ext_d"] - LP["stop_buf"]
        risk = ep - stop0
        if not (LP["min_stop"] <= risk <= LP["max_stop"]):
            continue
        sh = z["entry_d"] - ep
        TT = {c: [x + sh for x in v] for c, v in lit.targets_x(M, z, LP).items()}
        best = None
        for c in LP["classes"]:
            for dist in TT.get(c, []):
                if dist >= LP["min_rr"] * risk:
                    if best is None or dist < best:
                        best = dist
                    break
        fb = False
        if best is None:
            if not LP["fallback_rr"]:
                continue
            tp, fb = LP["fallback_rr"] * risk, True
        else:
            tp = min(best, LP["max_rr"] * risk) if LP["max_rr"] else best
        use1 = LP["tf"] == "1m" and B1 is not None and int(M.day_of[z["entry_i"]]) in B1.full
        B = B1 if use1 else B5
        t = TS.tsim(M, B, z, ep, ep + tp, fb, stop0, LP)
        if t is None:
            continue
        busy = t["exit_i"]; per_day[z["day"]] += 1
        out.append(t)
    return out


_U = {}
SKIP_KEYS = ("wp", "wp_win", "asia", "asia_m", "asia_p", "asia_n", "ev", "ev_m")


def unit(P=None):
    P = B_of(P)
    sk = {k: P[k] for k in SKIP_KEYS} if skip_any(P) else {}
    key = json.dumps(sk, sort_keys=True, default=str)
    if key not in _U:
        U = brun(P) if sk else TS.unit()
        if sk:
            TS.wk_marks(U)
        _U[key] = U
    out = []
    for t in _U[key]:
        x = dict(t)
        x["bm"] = size_m(x, P)
        out.append(x)
    return out


def skip_any(P):
    return (P["wp"] == "skip") or (P["asia"] and P["asia_m"] == 0.0) or (P["ev"] and P["ev_m"] == 0.0)


# ================================================================================================ sizing + MFFU eval play
def qty(t, P, st):
    """(micros, minis=0, why). st = {"bal", "cum", "room"} of the eval at this entry."""
    mi, _ = TS.base_q(t, RULE)
    m = t.get("wk_m", 1.0) * t.get("bm", 1.0)
    if abs(m - 1.0) > 1e-9:
        mi = max(1, min(MAXQ, int(mi * m + 1e-9)))
    rp = t["risk_pts"]
    room = st["room"]
    cap = max(1, int(ROOM_K * room / (rp * PV))) if room is not None else MAXQ
    q = min(mi, cap)
    if P["tgt_trim"] or P["press_room"] is not None:
        need = PLAN["target"] - (st["bal"] + st["cum"] - PLAN["start"])
        tg = abs(t["target_px"] - t["entry_px"])
        per = tg * PV - COMM
        if need > 0 and per > 0:
            qn = max(1, int(math.ceil(need * P["trim_buf"] / per - 1e-9)))
            if P["tgt_trim"] and q * per >= need * P["trim_buf"]:
                q = min(q, qn)
            elif (P["press_room"] is not None and room is not None and room >= P["press_room"]
                  and tg <= P["press_r"] * rp and q * per < need):
                dll = max(1, int((DLL + min(0.0, st["cum"])) / ((rp + SLIP) * PV + COMM)))
                q = max(q, min(qn, cap, dll, MAXQ))
    return q, 0


def _play(ss, by, i0, H, P, keep=None):
    bal = PLAN["start"]; peak = bal; mll = bal - PLAN["mll"]; lock = PLAN["start"] + PLAN["lock_above"]
    for k in range(i0, min(len(ss), i0 + H)):
        cum = low = 0.0
        for t in by.get(ss[k], []):
            if DLL and cum <= -DLL:
                break
            mi, mn = qty(t, P, {"bal": bal, "cum": cum, "room": bal + cum - mll})
            x = TS.at_size(t, mi, mn, cum)
            low = min(low, cum + x["low"]); cum += x["pnl"]; low = min(low, cum)
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


def evals(U, span, P, horizon=60):
    """= TS.evals (every session of the span starts an eval; back-to-back path for the money stats) with qty() above."""
    a, z = SPAN[span]
    ss = [d for d in SESS if a <= d <= z]
    by = collections.defaultdict(list)
    for t in sorted(U, key=lambda t: t["entry_t"]):
        if a <= t["day"] <= z:
            by[t["day"]].append(t)
    res = [_play(ss, by, i, horizon, P) for i in range(len(ss))]
    N = len(res) or 1
    o = {}
    for H in (10, 20):
        o[f"p{H}"] = round(100 * sum(1 for r, n in res if r == "PASS" and n <= H) / N, 1)
        o[f"f{H}"] = round(100 * sum(1 for r, n in res if r == "FAIL" and n <= H) / N, 1)
    P_ = sum(1 for r, _ in res if r == "PASS"); F_ = sum(1 for r, _ in res if r == "FAIL")
    o["pass_rate"] = round(100 * P_ / (P_ + F_), 1) if P_ + F_ else None
    pas = [n for r, n in res if r == "PASS"]
    o["pass_med"] = float(np.median(pas)) if pas else None
    k, pa, fa, path = 0, 0, 0, []
    while k < len(ss):
        r, n = _play(ss, by, k, len(ss), P, keep=path)
        if r == "OPEN":
            break
        pa += r == "PASS"; fa += r == "FAIL"; k += n
    o["b2b"] = f"{pa}/{fa}"
    return o, path


SP = ("H1", "H2", "2026", "2021-25")


def score(U, P, spans=SP):
    P = B_of(P)
    out = {}
    for s in spans:
        e, path = evals(U, s, P)
        st = TS.stats(path, s)
        a, z = SPAN[s]
        TT = [t for t in path if a <= t["day"] <= z]
        w = [t["pnl"] for t in TT if t["pnl"] > 0]; ls = [t["pnl"] for t in TT if t["pnl"] <= 0]
        st["avg_win"] = round(float(np.mean(w))) if w else 0
        st["avg_loss"] = round(float(np.mean(ls))) if ls else 0
        st["touched"] = sum(1 for t in TT if abs(t.get("bm", 1.0) - 1.0) > 1e-9)
        out[s] = {**st, **e}
    return out


def row(nm, o, spans=("H1", "H2", "2021-25")):
    def f(s):
        if not s or not s.get("n"):
            return "n=0"
        return (f"n={s['n']} {s['tpw']}/wk win {s['win']} PF {s['pf']} net {s['net']:+,} ${s['per_month']:,}/mo DD {s['dd']:,} "
                f"w {s['avg_win']} l {s['avg_loss']} 2w {s['p10']}/{s['f10']} 1m {s['p20']}/{s['f20']} pr {s['pass_rate']} "
                f"med {s['pass_med']} t{s['touched']}")
    return f"{nm:34s} " + " | ".join(f"{k}[{f(o.get(k))}]" for k in spans if k in o)


# ================================================================================================ check
def check():
    U0 = TS.unit()
    T = TS.sized(U0, ("lit", 800, 20.0))
    L = F.run(LIVE)
    ka = [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"], t["qty"]) for t in sorted(L, key=lambda t: t["entry_t"])]
    kb = [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"], t["qty"]) for t in T]
    bad = [(x, y) for x, y in zip(ka, kb) if not (x[:2] == y[:2] and abs(x[2] - y[2]) < 0.03 and x[3:] == y[3:])]
    n26 = [t for t in T if t["day"] >= "2026"]
    print(f"engine lit_live {len(ka)} trades | wrapper {len(kb)} | mismatches {len(bad) + abs(len(ka) - len(kb))} | "
          f"2026 {len(n26)} trades net {sum(t['pnl'] for t in n26):+,.0f}")
    U1 = brun({})
    same = [(a["day"], a["entry_t"], a["exit"], round(a["legs"][0][1], 2)) for a in U0] == \
           [(a["day"], a["entry_t"], a["exit"], round(a["legs"][0][1], 2)) for a in U1]
    o = score(unit(), {}, spans=("H1", "H2"))
    print(row("baseline (eval sizing)", o, spans=("H1", "H2")))
    ok = (not bad and len(ka) == len(kb) and len(n26) == 120 and same and o["H1"]["net"] == 33305 and o["H2"]["net"] == 10465)
    print("brun == lit_tightstop unit trades:", same, "| CHECK", "OK" if ok else "FAILED")
    return ok


# ================================================================================================ the grid
def variants():
    V = collections.OrderedDict()
    V["base"] = {}
    # 1. VIX regime sizing
    for hi in (18, 20, 22):
        for m in (1.25, 1.5):
            V[f"vix >= {hi} x{m:g}"] = {"vix_hi": float(hi), "vix_hi_m": m}
    V["vix < 15 x0.75"] = {"vix_lo": 15.0, "vix_lo_m": 0.75}
    for hi in (18, 20, 22):
        V[f"vix >= {hi} x1.25, < 15 x0.75"] = {"vix_hi": float(hi), "vix_hi_m": 1.25, "vix_lo": 15.0, "vix_lo_m": 0.75}
    V["vix >= 20 x1.5, < 15 x0.75"] = {"vix_hi": 20.0, "vix_hi_m": 1.5, "vix_lo": 15.0, "vix_lo_m": 0.75}
    # 2. target-aware eval sizing
    V["tgt trim x1.0"] = {"tgt_trim": True, "trim_buf": 1.0}
    V["tgt trim x1.2"] = {"tgt_trim": True, "trim_buf": 1.2}
    for pr in (1500, 2000):
        for r in (2.5, 4.0):
            V[f"tgt press room>={pr} tgt<={r:g}R"] = {"press_room": float(pr), "press_r": r}
    V["tgt trim + press room>=2000 tgt<=4R"] = {"tgt_trim": True, "press_room": 2000.0, "press_r": 4.0}
    # 3. weekly profile (Thu/Fri)
    for win in ("how", "tw"):
        V[f"wp {win} skip toward"] = {"wp": "skip", "wp_win": win}
        V[f"wp {win} x0.5 toward"] = {"wp": "size", "wp_win": win, "wp_m": 0.5}
    V["wp how x0.25 toward"] = {"wp": "size", "wp_win": "how", "wp_m": 0.25}
    # 4. Asia range gate
    for side in ("lo", "hi", "both"):
        V[f"asia {side} skip"] = {"asia": side, "asia_m": 0.0}
        V[f"asia {side} x0.5"] = {"asia": side, "asia_m": 0.5}
    V["asia both x0.5 p10/p90"] = {"asia": "both", "asia_m": 0.5, "asia_p": (10, 90)}
    # 5. event days
    for ev, nm in ((("opex",), "opex"), (("month_end",), "month-end"), (("q_end",), "quarter-end"),
                   (("opex", "month_end"), "opex+month-end")):
        V[f"ev {nm} skip"] = {"ev": ev, "ev_m": 0.0}
        V[f"ev {nm} x0.5"] = {"ev": ev, "ev_m": 0.5}
    return V


def _load():
    return json.load(open(OUT)) if os.path.exists(OUT) else {}


def grid(only=None):
    res = _load()
    for nm, P in variants().items():
        if only and not any(o in nm for o in only):
            continue
        U = unit(P)
        o = score(U, P)
        res[nm] = {"params": P, "score": o}
        print(row(nm, o), flush=True)
        json.dump(res, open(OUT, "w"), indent=1, default=str)
    return res


# ================================================================================================ store runs
IDEA = [("vix", "1. VIX regime sizing"), ("tgt", "2. target-aware eval sizing"), ("wp", "3. weekly profile"),
        ("asia", "4. Asia range gate"), ("ev", "5. event days")]


def _slug(nm):
    s = nm.lower().replace(">=", "ge").replace("<=", "le").replace("<", "lt").replace("+", " plus ")
    return "lit_u_bias_" + re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def _h(s):
    return (f"n={s['n']} {s['tpw']}/wk win {s['win']}% PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,} "
            f"avg win ${s['avg_win']:,} avg loss ${s['avg_loss']:,}; eval 2wk {s['p10']}/{s['f10']} 1mo {s['p20']}/{s['f20']} "
            f"pass rate {s['pass_rate']}% median {s['pass_med']}")


def verdict(o, b):
    d1, d2 = o["H1"]["net"] - b["H1"]["net"], o["H2"]["net"] - b["H2"]["net"]
    tpw = min(o["H1"]["tpw"], o["H2"]["tpw"])
    if d1 > 0 and d2 > 0 and 2 <= tpw <= 4:
        return "ADOPT", d1, d2
    if abs(d1) < 500 and abs(d2) < 500:
        return "NEUTRAL", d1, d2
    return "REJECT", d1, d2


def save_all():
    res = _load()
    b = res["base"]["score"]
    V = variants()
    for nm, rec in res.items():
        P = V[nm]
        o = rec["score"]
        if nm == "base":
            rid, title, status = _slug("base"), "LIT live + eval sizing (reference of the untested-bias study, == lit_tight_eval_800_25_room60)", "info"
            why = "Reference: the live LIT signals with the live eval sizing."
        else:
            v, d1, d2 = verdict(o, b)
            status = {"ADOPT": "adopt-candidate", "NEUTRAL": "info", "REJECT": "rejected"}[v]
            idea = next(t for k, t in IDEA if nm.startswith(k))
            rid, title = _slug(nm), f"LIT untested bias - {idea}: {nm}"
            why = f"{v}: H1 {d1:+,} $ / H2 {d2:+,} $ vs the baseline (LIT live + eval sizing)."
        U = unit(P)
        T = evals(U, "2026", B_of(P))[1] + evals(U, "2021-25", B_of(P))[1]
        T = [{k: v for k, v in t.items() if k not in ("legs",)} for t in T]
        S = rl.score(T, SESS)
        rl.save(rid, title, "other", "Owner 2026-10-18: try every untested LIT idea (bias / regime group) on the live LIT signals.",
                params={**LIVE, **B_of(P), "size": list(RULE), "room_k": ROOM_K}, trades=T, scored=S, status=status,
                verdict=f"{why} 2026 H1 (pick) {_h(o['H1'])}; 2026 H2 (check) {_h(o['H2'])}; 2021-25 reference only {_h(o['2021-25'])}",
                notes="tools/lit_t_bias.py (wraps engine/lit.py through tools/lit_tightstop.py; defaults == run lit_live trade for "
                      "trade and == run lit_tight_eval_800_25_room60). Same LIT setups, fills, stops and targets; only which "
                      "setups are taken or the size changes. Eval sizing: $800 up to a 25-pt stop, then 800x25/stop, weekly "
                      "stop, 60% room cap. Money stats on the back-to-back MFFU eval path.",
                writeup="lit-untested-bias", tags=["lit", "lit_untested", "lit_bias"])
        print("saved", rid, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        sys.exit(0 if check() else 1)
    elif cmd == "grid":
        grid(sys.argv[2:] or None)
    elif cmd == "save":
        save_all()
