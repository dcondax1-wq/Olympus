"""LIT untested stop ideas (owner, 2026-10-18: "Remember our strategy is LIT based nothing that goes outside, try every single one
of these and go find more we haven't tested").

Wraps engine/lit.py (not edited) on the live LIT settings (live_model.json "lit" = lit_final + loss pack) with the live eval
sizing ($800 up to a 25-pt stop, then 800x25/stop, weekly stop, never more than 60% of the room to the MFFU max-loss floor:
engine/sizing.py lit_qty mode "eval" = run lit_tight_eval_800_25_room60). The setups, the limit at the 5m CISD level, the 1m CISD
confirmation, the fill, the cancel-when-the-sweep-extreme-breaks-before-the-fill rule and the target level are the live ones.
Only the stop (where it sits, how it triggers) and the stop moves after the fill change:

  1. close-based stop (cstop=N): the trade is closed only when a candle of the executor (1m; 5m on days without 1m bars)
     CLOSES beyond the live stop (1 tick past the sweep extreme), at the next bar's open + 1 tick of slippage; a hard
     emergency stop N pts further out is always working. cstop_size "emerg" = size on the emergency stop (size follows the
     stop: the real worst case), "ext" = live size (the worst case is N pts bigger than the size assumes).
  2. stop behind the next liquidity (liq=kind): 1 tick past the nearest resting liquidity beyond the sweep extreme, known at
     the trigger bar: "frac" = untouched confirmed 5m fractal low (k=2, last 2 days), "eq" = untouched equal lows (LIT build-up,
     engine buildups()), "lit" = untouched LIT level (session boxes, PDL/PWL/PML, gaps, build-ups), "any" = the nearest of all.
     Capped at liq_cap (80) pts from the fill: liq_over "cut" = cut to the cap, "ext" = keep the live stop when it is farther.
  3. volatility buffer (buf_atr=k): stop = sweep extreme - k x ATR(14, 5m at the extreme) instead of 1 tick (capped at 80 pts).
     For 2 and 3, rref "orig" = target and breakeven measured on the live stop's R (same trades), "own" = on the new stop
     (1.5R minimum and the 8R bank re-measured, breakeven at 1R of the new stop).
  4. time-based breakeven: be_time=(minutes, level R, "cum"|"run"): no breakeven at +1R; the stop goes to breakeven once
     the bars that CLOSED at/above +level R add up to `minutes` (cum) or run in a row for `minutes` (run).
     be_after=m: breakeven at the first +1R touch that comes m minutes or more after the fill.
     be_close=True (extra idea): breakeven only when a bar CLOSES at/above +1R (not on a wick touch).
  5. profit lock (lock=(x, keep)): once price has covered x of the way from the fill to the target, the stop goes to
     fill + keep x the open profit at that point (keep 0.5 = lock half), on top of the 1R breakeven.

  python tools/lit_t_stops.py check   # defaults == run lit_live (120 trades 2026) and == the baseline eval run numbers
  python tools/lit_t_stops.py grid    # every variant -> research/lit/t_stops_results.json
  python tools/lit_t_stops.py save    # store the chosen runs lit_u_stops_* (rl.save, family other, tags lit, lit_untested, lit_stops)
Pick on 2026 H1 (Jan 2 - Jun 30), check on 2026 H2 (Jul 1 - Oct 16); 2021-25 is a reference line (5m only, no 1m data).
1 CPU process. Paper research only.
"""
from __future__ import annotations

import bisect
import collections
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_tightstop as TS  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "t_stops_results.json")
SESS, SPAN = F.SESS, F.SPAN
PV, COMM, SLIP = lit.PV, lit.COMM, lit.SLIP
LIVE = TS.LIVE
RULE = ("lit", 800, 25.0)          # live eval sizing: $800 up to a 25-pt stop, then 800x25/stop
ROOM_K = 0.6                       # + never more than 60% of the room to the trailing max-loss floor

SDEF = {
    "cstop": None, "cstop_size": "emerg",
    "liq": None, "liq_cap": 80.0, "liq_over": "cut", "liq_back": 576,
    "buf_atr": 0.0, "rref": "orig",
    "be_time": None, "be_after": None, "be_close": False,
    "lock": None,
}


def P_of(P=None):
    return {**LIVE, **SDEF, **(P or {})}


# ================================================================================================ the scoring's at_size, with the real worst case
_at_size0 = TS.at_size


def _at_size(t, mi, mn, cum=0.0):
    """TS.at_size, but the MFFU $1,000 daily-loss check uses the trade's real worst case (a close-based stop can lose more
    than its sizing distance; risk_max = emergency stop distance)."""
    if "risk_max" not in t or t["risk_max"] <= t["risk_pts"]:
        return _at_size0(t, mi, mn, cum)
    t2 = {**t, "risk_pts": t["risk_max"]}
    x = _at_size0(t2, mi, mn, cum)
    ru = t["risk_pts"] * PV * (mi + 10 * mn)
    x.update(risk_pts=t["risk_pts"], risk_usd=round(ru, 2), r=round(x["pnl"] / ru, 3) if ru else 0.0)
    return x


TS.at_size = _at_size              # this process only (TS._play / TS.sized look it up by name)


# ================================================================================================ stop placement (ideas 2, 3)
def _liq_stop(M, z, P, stop0):
    """Direction-space stop 1 tick past the nearest untouched liquidity beyond the sweep extreme (known at the trigger bar),
    or None when there is none in the lookback."""
    d, i, kind = z["dir"], z["i"], P["liq"]
    lo_d = M.l if d == 1 else -M.h
    ext = float(z["ext_d"])
    cands = []
    s0 = max(0, i - P["liq_back"])
    if kind in ("frac", "any"):
        sw = M.fl if d == 1 else M.fh
        a, b = bisect.bisect_left(sw, s0), bisect.bisect_left(sw, i - 1)   # confirmed 2 bars after the swing bar
        for j in sw[a:b]:
            j = int(j)
            if j + 2 > i:
                continue
            p = float(lo_d[j])
            if p < ext and lo_d[j + 1:i + 1].min() > p:
                cands.append(p)
    if kind in ("eq", "lit", "any"):
        side = "low" if d == 1 else "high"
        if kind == "eq":
            L = [(px, ki) for sd, px, ki in M.bu if sd == side and s0 <= ki <= i]
        else:
            L = [(px, ki) for sd, px, ki, nm, cls in M.levels(z["k"]) if sd == side and ki <= i]
        for px, ki in L:
            p = float(px) * d
            st = max(int(ki) + 1, s0)
            if p < ext and (st > i or lo_d[st:i + 1].min() > p):
                cands.append(p)
    if not cands:
        return None
    return max(cands) - P["stop_buf"]


def _stop(M, z, P, entry, stop0):
    """(stop, source) in direction space; never closer than the live stop, capped at liq_cap pts from the fill."""
    if P["liq"]:
        st = _liq_stop(M, z, P, stop0)
        if st is None:
            return stop0, "ext"
        if entry - st > P["liq_cap"]:
            if P["liq_over"] == "ext":
                return stop0, "ext"
            st = entry - P["liq_cap"]
        return min(st, stop0), "liq"
    if P["buf_atr"]:
        st = stop0 - P["buf_atr"] * float(z["atr_ext"])
        st = max(st, entry - P["liq_cap"])
        return min(st, stop0), "atr"
    return stop0, "ext"


# ================================================================================================ executor (unit size)
def ssim(M, B, z, entry_px, tgt_lvl, fb, stop0, P):
    """lit.simulate_x (research mode, 1m CISD entry) at 1 micro, with the stop options of SDEF."""
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
    limit_fill = True
    fill = tapped = None
    k = k0
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= flat or B.mod[k] >= 1080:
            break
        if tapped is None and B.t[k] >= t0 + wait_s:
            break
        if lo_d[k] <= stop0:
            if tapped is None and lo_d[k] <= entry_px and not cis:
                fill = k; entry = min(entry_px, float(o_d[k]))
            break
        if tapped is None and lo_d[k] <= entry_px:
            if cis:
                tapped = k
            else:
                fill = k; entry = min(entry_px, float(o_d[k])); break
        if tapped is None and hi_d[k] >= tgt_lvl:
            break
        if tapped is not None:
            if k - tapped > cis:
                break
            lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
            cz = lit._cisd_level(c_d, o_d, lowk)
            if cz is not None and k > lowk and c_d[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == s_day:
                fill = k + 1; entry = float(o_d[k + 1]) + SLIP; limit_fill = False
                break
        k += 1
    if fill is None:
        return None
    risk0 = entry - stop0
    if risk0 <= 0 or lit.qty_for(risk0) < 1:
        return None
    stop, src = _stop(M, z, P, entry, stop0)
    risk = entry - stop                             # the stop that is working (ideas 2, 3), or the live one
    rb = risk if P["rref"] == "own" else risk0       # R used by the 1.5R minimum, the 8R bank and the 1R breakeven
    if fb:
        tg = entry + P["fallback_rr"] * rb
    else:
        dist = tgt_lvl - entry
        if dist < P["min_rr"] * rb:
            return None
        tg = entry + (min(dist, P["max_rr"] * rb) if P["max_rr"] else dist)
    cst = P["cstop"]
    hard = stop - cst if cst is not None else stop  # idea 1: the emergency stop N pts beyond the close-based stop
    risk_size = (entry - hard) if (cst is not None and P["cstop_size"] == "emerg") else risk
    be_r = P["be_r"]
    be_d = None if be_r is None else be_r * rb
    bt = P["be_time"]
    if bt is not None:
        be_d = None
        bt_need = max(1, int(round(bt[0] * 60 / B.secs)))
        bt_lvl = entry + bt[1] * rb
    bt_n = 0
    be_after_s = None if P["be_after"] is None else P["be_after"] * 60
    lk = P["lock"]
    lk_lvl = entry + lk[0] * (tg - entry) if lk else None
    lk_done = False
    cur, be_done, mfe, mae, worst = stop, False, 0.0, 0.0, 0.0
    soft = cst is not None                          # cur is a close-based stop until breakeven / lock replaces it
    k = fill
    exit_px = kind = None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        mae = max(mae, (entry - lo_d[k]) / risk)
        worst = min(worst, lo_d[k] - entry)
        if soft:
            if lo_d[k] <= hard:
                exit_px, kind = min(hard, float(o_d[k])) - SLIP, "STOP"; break
        elif lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("LOCK" if lk_done else "BE" if be_done else "STOP"); break
        if not (k == fill and limit_fill):
            mfe = max(mfe, (hi_d[k] - entry) / risk)
            if hi_d[k] >= tg:
                exit_px, kind = tg, "TARGET"; break
            if not be_done:
                if bt is not None:
                    if c_d[k] >= bt_lvl:
                        bt_n += 1
                    elif bt[2] == "run":
                        bt_n = 0
                    hit = bt_n >= bt_need
                elif be_d is None:
                    hit = False
                elif P["be_close"]:
                    hit = c_d[k] >= entry + be_d
                else:
                    hit = hi_d[k] >= entry + be_d
                    if hit and be_after_s is not None:
                        hit = (B.t[k] - B.t[fill]) >= be_after_s
                if hit:
                    cur, be_done, soft = max(cur, entry), True, False
            if lk and not lk_done and hi_d[k] >= lk_lvl:
                cur = max(cur, entry + lk[1] * (lk_lvl - entry)); lk_done = True; soft = False
        if soft and c_d[k] <= cur:                  # idea 1: a close beyond the stop -> out at the next bar's open
            if k + 1 < B.n and B.day[k + 1] == s_day and B.mod[k + 1] < 1080:
                k += 1
                worst = min(worst, float(o_d[k]) - entry)
                exit_px, kind = float(o_d[k]) - SLIP, "STOP"
            else:
                exit_px, kind = float(c_d[k]) - SLIP, "STOP"
            break
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        k += 1
    if exit_px is None:
        return None
    xi5 = int(np.searchsorted(M.t, B.t[k], side="right") - 1)
    return {"day": z["day"], "entry_t": int(B.t[fill]), "exit_t": int(B.t[k]) + B.secs, "exit_i": xi5, "dir": d,
            "risk_pts": round(risk_size, 2), "risk_max": round(max(entry - hard, risk_size), 2),
            "risk0": round(risk0, 2), "exit": kind, "trigger": "LIT-" + ("1m" if B.secs == 60 else "5m"),
            "mfe": round(mfe, 3), "mae": round(mae, 3), "bars_held": int(k - fill + 1), "regime": "",
            "half": False, "legs": [(1.0, exit_px - entry)], "w1": worst, "w2": 0.0, "part": False, "stop_src": src,
            "entry_px": round(entry * d, 2), "stop_px": round(stop * d, 2), "stop0_px": round(stop0 * d, 2),
            "hard_px": round(hard * d, 2), "target_px": round(tg * d, 2), "limit_fill": limit_fill, "swept": z["swept"],
            "tf": B.secs // 60, "i": z["i"], "ext_i": z["ext_i"], "be_done": be_done, "lock_done": lk_done}


def srun(P=None, sessions=SESS):
    """Unit-size trades of one variant (TS.trun / lit._run_core research mode with the SDEF options)."""
    P = P_of(P)
    names = set(P["sweep_names"]) if P.get("sweep_names") else None
    sset = set(sessions) if sessions else None
    M, C = F.market(P["ref"], P["extra_boxes"])
    B5 = F.bars(M, "5m")
    B1 = F.bars(M, "1m") if P["tf"] == "1m" else None
    out, busy, per_day = [], -1, collections.Counter()
    for z in C:
        if sset is not None and z["day"] not in sset:
            continue
        if z["entry_i"] <= busy or per_day[z["day"]] >= P["max_per_day"]:
            continue
        if not lit.setup_ok(z, P, names):
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
        fb = False
        if best is None:
            if not P["fallback_rr"]:
                continue
            tp, fb = P["fallback_rr"] * risk, True
        else:
            tp = min(best, P["max_rr"] * risk) if P["max_rr"] else best
        use1 = P["tf"] == "1m" and B1 is not None and int(M.day_of[z["entry_i"]]) in B1.full
        B = B1 if use1 else B5
        t = ssim(M, B, z, ep, ep + tp, fb, stop0, P)
        if t is None:
            continue
        busy = t["exit_i"]; per_day[z["day"]] += 1
        out.append(t)
    return out


_U = {}


def unit(P=None):
    key = json.dumps(P or {}, sort_keys=True, default=str)
    if key not in _U:
        U = srun(P)
        TS.wk_marks(U)
        _U[key] = U
    return _U[key]


# ================================================================================================ scoring (= the baseline run's)
SP = ("H1", "H2", "2026", "2021-25")


def score(U, spans=SP):
    out = {}
    for s in spans:
        e, path = TS.evals(U, RULE, s, ROOM_K)
        st = TS.stats(path, s)
        a, z = SPAN[s]
        TT = [t for t in path if a <= t["day"] <= z]
        w = [t["pnl"] for t in TT if t["pnl"] > 0]; ls = [t["pnl"] for t in TT if t["pnl"] <= 0]
        st["avg_win"] = round(float(np.mean(w))) if w else 0
        st["avg_loss"] = round(float(np.mean(ls))) if ls else 0
        st["lock_pct"] = round(100 * sum(t["exit"] == "LOCK" for t in TT) / len(TT), 1) if TT else 0.0
        out[s] = {**st, **e}
    return out


def row(nm, o, spans=("H1", "H2", "2021-25")):
    def f(s):
        if not s or not s.get("n"):
            return "n=0"
        return (f"n={s['n']} {s['tpw']}/wk win {s['win']} PF {s['pf']} net {s['net']:+,} ${s['per_month']:,}/mo DD {s['dd']:,} "
                f"w {s['avg_win']} l {s['avg_loss']} 2w {s['p10']}/{s['f10']} 1m {s['p20']}/{s['f20']} pr {s['pass_rate']} med {s['pass_med']}")
    return f"{nm:34s} " + " | ".join(f"{k}[{f(o.get(k))}]" for k in spans if k in o)


# ================================================================================================ check
def check():
    U = unit()
    T = TS.sized(U, ("lit", 800, 20.0))
    L = F.run(LIVE)
    ka = [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"], t["qty"]) for t in sorted(L, key=lambda t: t["entry_t"])]
    kb = [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"], t["qty"]) for t in T]
    bad = [(x, y) for x, y in zip(ka, kb) if not (x[:2] == y[:2] and abs(x[2] - y[2]) < 0.03 and x[3:] == y[3:])]
    n26 = [t for t in T if t["day"] >= "2026"]
    print(f"engine lit_live {len(ka)} trades | wrapper {len(kb)} | mismatches {len(bad) + abs(len(ka) - len(kb))} | "
          f"2026 {len(n26)} trades net {sum(t['pnl'] for t in n26):+,.0f}")
    U2 = TS.unit()
    same = [(a["day"], a["entry_t"], a["exit"], round(a["legs"][0][1], 2)) for a in U] == \
           [(a["day"], a["entry_t"], a["exit"], round(a["legs"][0][1], 2)) for a in U2]
    o = score(U, spans=("H1", "H2"))
    print(row("baseline (eval sizing)", o, spans=("H1", "H2")))
    ok = (not bad and len(ka) == len(kb) and len(n26) == 120 and same and o["H1"]["net"] == 33305 and o["H2"]["net"] == 10465)
    print("unit trades == lit_tightstop:", same, "| CHECK", "OK" if ok else "FAILED")
    return ok


# ================================================================================================ the grid
def variants():
    V = collections.OrderedDict()
    V["base"] = {}
    # 1. close-based stop + emergency stop
    for n in (5, 10, 15):
        V[f"close {n} emerg-size"] = {"cstop": float(n), "cstop_size": "emerg"}
        V[f"close {n} live-size"] = {"cstop": float(n), "cstop_size": "ext"}
    # 2. stop behind the next liquidity
    for kind in ("frac", "eq", "lit", "any"):
        for over in ("cut", "ext"):
            V[f"liq {kind} {over} orig"] = {"liq": kind, "liq_over": over, "rref": "orig"}
        V[f"liq {kind} ext own"] = {"liq": kind, "liq_over": "ext", "rref": "own"}
    # 3. volatility buffer
    for kb in (0.05, 0.1, 0.2):
        V[f"buf {kb} ATR orig"] = {"buf_atr": kb, "rref": "orig"}
        V[f"buf {kb} ATR own"] = {"buf_atr": kb, "rref": "own"}
    # 4. time-based breakeven
    for m in (15, 30, 60):
        V[f"be time {m}m >0.5R cum"] = {"be_time": (m, 0.5, "cum")}
        V[f"be time {m}m >0.5R run"] = {"be_time": (m, 0.5, "run")}
    for m in (10, 15, 30):
        V[f"be 1R after {m}m"] = {"be_after": m}
    # extra: breakeven on a close above +1R
    V["be on 1m close >= 1R"] = {"be_close": True}
    # 5. profit lock
    for x in (0.6, 0.75, 0.85):
        V[f"lock 50% at {int(x * 100)}%"] = {"lock": (x, 0.5)}
    return V


def _load():
    return json.load(open(OUT)) if os.path.exists(OUT) else {}


def grid(only=None):
    res = _load()
    for nm, P in variants().items():
        if only and not any(o in nm for o in only):
            continue
        U = unit(P)
        o = score(U)
        res[nm] = {"params": P, "score": o,
                   "src": dict(collections.Counter(t["stop_src"] for t in U if t["day"] >= "2026")),
                   "exits26": dict(collections.Counter(t["exit"] for t in U if t["day"] >= "2026")),
                   "med_stop26": float(np.median([t["risk_pts"] for t in U if t["day"] >= "2026"]))}
        print(row(nm, o), flush=True)
        json.dump(res, open(OUT, "w"), indent=1, default=str)
    return res


# ================================================================================================ store runs
def save(picks):
    """picks: [(id, title, variant name, status, why)]"""
    V = variants()
    for rid, title, vn, status, why in picks:
        U = unit(V[vn])
        T = TS.evals(U, RULE, "2026", ROOM_K)[1] + TS.evals(U, RULE, "2021-25", ROOM_K)[1]
        T = [{k: v for k, v in t.items() if k not in ("legs",)} for t in T]
        S = rl.score(T, SESS)
        o = score(U)
        h = lambda s: (f"n={s['n']} {s['tpw']}/wk win {s['win']}% PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,} "
                       f"avg win ${s['avg_win']:,} avg loss ${s['avg_loss']:,}; eval 2wk {s['p10']}/{s['f10']} 1mo {s['p20']}/{s['f20']} "
                       f"pass rate {s['pass_rate']}% median {s['pass_med']}")
        rl.save(rid, title, "other", "Owner 2026-10-18: try every untested LIT stop idea (stops group) on the live LIT signals.",
                params={**LIVE, **SDEF, **V[vn], "size": list(RULE), "room_k": ROOM_K}, trades=T, scored=S, status=status,
                verdict=f"{why} 2026 H1 (pick) {h(o['H1'])}; 2026 H2 (check) {h(o['H2'])}; 2021-25 reference only {h(o['2021-25'])}",
                notes="tools/lit_t_stops.py (wraps engine/lit.py; defaults == run lit_live trade for trade and == run "
                      "lit_tight_eval_800_25_room60). Same LIT signals, fills and target level; only the stop and stop moves change. "
                      "Eval sizing: $800 up to a 25-pt stop, then 800x25/stop, weekly stop, 60% room cap.",
                writeup="lit-untested-stops", tags=["lit", "lit_untested", "lit_stops"])
        print("saved", rid, row("", o, spans=("H1", "H2")), flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        sys.exit(0 if check() else 1)
    elif cmd == "grid":
        grid(sys.argv[2:] or None)
