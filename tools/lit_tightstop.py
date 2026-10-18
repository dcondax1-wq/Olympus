"""LIT tight stops and upsizing (owner, 2026-10-18: "upsizing and less stops. We don't need 50-60 point stops, especially if we
trade more micros or 1 NQ. Figure it out.").

Wraps engine/lit.py (not edited) on the live LIT settings (live_model.json "lit" = lit_final + loss pack: Monday rule and
weekly stop). Same LIT signals: the same setups, the same limit at the 5m CISD level, the same 1m CISD confirmation and the
same fill; the setup is still cancelled when the 5m sweep extreme breaks before the fill. Only what happens after the fill
changes:

  1. stop placement (stop_mode): ext = 1 tick beyond the 5m sweep extreme (live) | tap = beyond the 1m protected swing that
     made the 1m CISD (lowest 1m low from the limit tap to the confirmation) | cisd5 = beyond the 5m CISD (trigger) candle (or
     the tap low if lower) | post5 = beyond the lowest 5m low after the sweep bar up to the trigger (the 5m higher low) |
     idm = beyond the inducement low | frac = a share (stop_k) of the sweep-extreme distance | atr = the extreme stop capped
     at stop_k x ATR(5m) | pts = the extreme stop capped at stop_k points (fixed distance: breaks the CLAUDE.md stop rule,
     research line only). A tight stop is never wider than the extreme stop and never under tight_min points.
  2. stop caps (cap, cap_mode): skip = no trade when the extreme stop is wider than cap (planned and at the fill; the day stays
     free for a later setup) | tap_skip = use the 1m protected-swing stop when the extreme is wider than cap, skip if that is
     still wider | tap_cap = the same, but a still-wider tap stop is cut to cap points.
  3. refined entries (e2): after the 1m CISD, a limit (not market) at the 1m CISD level (cisd), the top / middle of the 1m FVG
     of the move (fvg / fvg_ce), the last down-close 1m candle's open / middle (ob / ob50) or the 50% of the 1m leg (fib50),
     valid e2_wait 1m bars; cancelled if the target trades or the sweep extreme breaks first.
  Targets stay the live ones (VIX band price, >= 1.5R and banked at 8R measured on the extreme stop: tgt_ref "orig"), so the
  trade set is identical for every stop; tgt_ref "own" measures them on the new stop. Breakeven at 1R of the stop in use
  (be_ref "own") or of the extreme stop's distance ("orig").
  4. sizing (applied to the unit trades, exact): the LIT rule ($ up to a reference stop, then $ x ref / stop), flat $ at any
     stop, fixed MNQ, fixed NQ minis ($20/pt, $4.50 a round trip each); then the weekly stop of the pack (half size after 2
     stop-outs in the ISO week, floor 1 micro; 1 NQ halves to 5 MNQ); max 40 micros / 4 minis; the MFFU $1,000 soft daily
     loss limit flattens a trade at -$1,000. Optional room cap (safe-eval: never risk more than k x the room to the trailing
     max-loss floor).
  Eval = MFFU Builder 50K started on every session of the span (only that span's sessions), $3,000 target, $2,000 EOD
  trailing max loss (intraday breach fails, locks at +$100), 60-session horizon.

  python tools/lit_tightstop.py check     # stop_mode ext + LIT sizing == run lit_live (120 trades 2026, +$41,734)
  python tools/lit_tightstop.py grid      # every stop/entry variant x every size -> research/lit/tight_results.json
  python tools/lit_tightstop.py honest    # winners stopped by the tight stops, trade by trade vs the live stop
  python tools/lit_tightstop.py save      # store the runs lit_tight_* (rl.save, family other, tags lit, lit_tight)
Pick on 2026 H1 (Jan 2 - Jun 30), check on 2026 H2 (Jul 1 - Oct 16); 2021-25 is a reference line (5m only, no 1m data).
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

OUT = os.path.join(ROOT, "research", "lit", "tight_results.json")
OUT_HONEST = os.path.join(ROOT, "research", "lit", "tight_honest.json")
OUT_ROOM = os.path.join(ROOT, "research", "lit", "tight_room.json")
SESS = F.SESS
SPAN = dict(F.SPAN)
PV, COMM, SLIP, MAXQ = lit.PV, lit.COMM, lit.SLIP, lit.MAX_MICROS
NQ_COMM = 4.50              # per NQ mini round trip (engine/instruments.py mini_comm_rt)
PLAN = PLANS["builder_50k"]
DLL = 1000.0
LIVE = {**lit.DEFAULTS, **json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]}

TDEF = {
    "stop_mode": "ext", "stop_k": None, "stop_atr": 0.0, "tight_min": 8.0,
    "cap": None, "cap_mode": "skip",
    "tgt_ref": "orig", "be_ref": "own",
    "e2": None, "e2_wait": 15,
}


def P_of(P=None):
    return {**LIVE, **TDEF, **(P or {})}


# ================================================================================================ executor (unit size)
def _tight(M, B, z, P, entry, stop0, tapped, kconf, lo_d):
    """Direction-space stop of the chosen mode (never wider than stop0, at least tight_min wide), and its source."""
    mode, k_ = P["stop_mode"], P["stop_k"]
    buf = P["stop_buf"] + P["stop_atr"] * z["atr_ext"]
    d = z["dir"]
    tap_lo = float(lo_d[tapped:kconf + 1].min()) if tapped is not None else None
    lo5 = M.l if d == 1 else -M.h
    st = None
    if mode == "ext":
        return stop0, "ext"
    if mode == "tap":
        st = tap_lo - buf if tap_lo is not None else None
    elif mode == "cisd5":
        a = float(lo5[z["i"]])
        st = (min(a, tap_lo) if tap_lo is not None else a) - buf
    elif mode == "post5":
        a = float(lo5[z["ext_i"] + 1:z["i"] + 1].min())
        st = (min(a, tap_lo) if tap_lo is not None else a) - buf
    elif mode == "idm":
        lev = max(z["sw"].values()); at = float(M.atr[z["sweep_i"]])
        dm, age, _ = P["idm_a"] or (1.0, 36, 1)
        px = [lev + dd * at for dd, aa in z["idm_a"] if dd <= dm and aa <= age]
        st = (min(px) - buf) if px else None
    elif mode == "frac":
        st = entry - k_ * (entry - stop0)
    elif mode == "atr":
        st = entry - k_ * z["atr_ext"]
    elif mode == "pts":
        st = entry - k_
    else:
        raise ValueError(mode)
    if st is None or st >= entry:
        return stop0, "fallback"
    st = min(st, entry - P["tight_min"])
    return max(stop0, st), ("ext" if st <= stop0 else mode)


def _e2_limit(c_d, o_d, hi_d, lo_d, lowk, k, mode):
    """Refined-entry limit (direction space) after the 1m CISD confirmed on bar k (protected low at lowk)."""
    if mode == "cisd":
        cz = lit._cisd_level(c_d, o_d, lowk)
        return cz[0] if cz else None
    if mode in ("fvg", "fvg_ce"):
        for j in range(k, lowk + 1, -1):
            top, bot = float(lo_d[j]), float(hi_d[j - 2])
            if top > bot and (j == k or lo_d[j + 1:k + 1].min() > bot):
                return top if mode == "fvg" else 0.5 * (top + bot)
        return None
    if mode in ("ob", "ob50"):
        j = lowk
        while j > lowk - 3 and not (c_d[j] < o_d[j]):
            j -= 1
        if not (c_d[j] < o_d[j]):
            return None
        return float(o_d[j]) if mode == "ob" else 0.5 * (float(o_d[j]) + float(c_d[j]))
    if mode == "fib50":
        top = float(hi_d[lowk:k + 1].max())
        return 0.5 * (top + float(lo_d[lowk]))
    raise ValueError(mode)


def tsim(M, B, z, entry_px, tgt_lvl, fb, stop0, P):
    """lit.simulate_x (research mode, 1m CISD entry) at 1 micro, with the tight-stop / cap / refined-entry options."""
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
    fill = tapped = kconf = lowk = None
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
                kconf = k
                if P["e2"] is None:
                    fill = k + 1; entry = float(o_d[k + 1]) + SLIP; limit_fill = False
                break
        k += 1
    e2_lim = None
    if P["e2"] is not None and kconf is not None:
        L = _e2_limit(c_d, o_d, hi_d, lo_d, lowk, kconf, P["e2"])
        if L is None or L <= stop0:
            return None
        e2_lim = L = min(L, float(c_d[kconf]))
        for b in range(kconf + 1, min(B.n, kconf + 1 + P["e2_wait"])):
            if B.day[b] != s_day or B.mod[b] >= flat or B.mod[b] >= 1080:
                break
            if lo_d[b] <= L:
                fill = b; entry = min(L, float(o_d[b])); limit_fill = True
                break
            if hi_d[b] >= tgt_lvl:
                break
    if fill is None:
        return None
    risk0 = entry - stop0
    if risk0 <= 0 or lit.qty_for(risk0) < 1:
        return None
    kc = kconf if kconf is not None else fill - 1
    stop, src = _tight(M, B, z, P, entry, stop0, tapped, kc, lo_d)
    if P["cap"] is not None and entry - stop0 > P["cap"]:
        cm = P["cap_mode"]
        if cm == "skip":
            return None
        Pt = {**P, "stop_mode": "tap"}
        st, src = _tight(M, B, z, Pt, entry, stop0, tapped, kc, lo_d)
        if entry - st > P["cap"]:
            if cm == "tap_skip":
                return None
            st, src = entry - P["cap"], "cap"
        stop = st
    risk = entry - stop
    if risk <= 0:
        return None
    rb = risk0 if P["tgt_ref"] == "orig" else risk
    if fb:
        tg = entry + P["fallback_rr"] * rb
    else:
        dist = tgt_lvl - entry
        if dist < P["min_rr"] * rb:
            return None
        tg = entry + (min(dist, P["max_rr"] * rb) if P["max_rr"] else dist)
    be_r = P["be_r"]
    be_d = None if be_r is None else be_r * (risk if P["be_ref"] == "own" else risk0)
    cur, be_done, mfe, mae, worst = stop, False, 0.0, 0.0, 0.0
    mfe0 = 0.0
    k = fill
    exit_px = kind = None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        mae = max(mae, (entry - lo_d[k]) / risk)
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("BE" if be_done else "STOP"); break
        if not (k == fill and limit_fill):
            mfe = max(mfe, (hi_d[k] - entry) / risk)
            if hi_d[k] >= tg:
                exit_px, kind = tg, "TARGET"; break
            if be_d is not None and not be_done and hi_d[k] >= entry + be_d:
                cur, be_done = entry, True
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        k += 1
    if exit_px is None:
        return None
    xi5 = int(np.searchsorted(M.t, B.t[k], side="right") - 1)
    return {"day": z["day"], "entry_t": int(B.t[fill]), "exit_t": int(B.t[k]) + B.secs, "exit_i": xi5, "dir": d,
            "risk_pts": round(risk, 2), "risk0": round(risk0, 2), "exit": kind, "trigger": "LIT-" + ("1m" if B.secs == 60 else "5m"),
            "mfe": round(mfe, 3), "mae": round(min(mae, 1.0 + SLIP / risk), 3), "bars_held": int(k - fill + 1), "regime": "",
            "half": False, "legs": [(1.0, exit_px - entry)], "w1": worst, "w2": 0.0, "part": False, "stop_src": src,
            "entry_px": round(entry * d, 2), "stop_px": round(stop * d, 2), "stop0_px": round(stop0 * d, 2),
            "target_px": round(tg * d, 2), "e2_px": round(e2_lim * d, 2) if e2_lim is not None else None,
            "limit_fill": limit_fill, "swept": z["swept"], "tf": B.secs // 60, "i": z["i"], "ext_i": z["ext_i"]}


def trun(P=None, sessions=SESS):
    """Unit-size trades of one variant on the live LIT settings (lit._run_core research mode + the TDEF options)."""
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
        if P["cap"] is not None and P["cap_mode"] == "skip" and risk > P["cap"]:
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
        t = tsim(M, B, z, ep, ep + tp, fb, stop0, P)
        if t is None:
            continue
        busy = t["exit_i"]; per_day[z["day"]] += 1
        out.append(t)
    return out


_U = {}


def unit(P=None):
    key = json.dumps(P or {}, sort_keys=True, default=str)
    if key not in _U:
        _U[key] = trun(P)
        wk_marks(_U[key])
    return _U[key]


def wk_marks(U):
    """The pack's weekly stop: x0.5 once 2 STOP exits of this variant finished earlier in the ISO week (engine week_stops)."""
    n_st, m_st = LIVE["wk_stop"] or (10 ** 9, 1.0)
    for t in U:
        wk = lit.iso_week(t["day"])
        n = sum(1 for x in U if x is not t and x["exit"] == "STOP" and lit.iso_week(x["day"]) == wk and x["exit_t"] <= t["entry_t"])
        t["wk_m"] = float(m_st) if n >= n_st else 1.0


# ================================================================================================ sizing (exact)
def base_q(t, rule):
    """(micros, minis) before the weekly stop. rule: ("lit", usd, ref_stop or None = flat $) | ("mnq", n) | ("nq", n)."""
    kind = rule[0]
    rp = t["risk_pts"]
    if kind == "lit":
        usd, ref = rule[1], rule[2]
        r = usd if (ref is None or rp <= ref) else usd * ref / rp
        return max(1, min(MAXQ, int(r / (rp * PV)))), 0
    if kind == "mnq":
        return min(MAXQ, int(rule[1])), 0
    if kind == "nq":
        return 0, min(4, int(rule[1]))
    raise ValueError(rule)


def qty_of(t, rule, room=None, room_k=None):
    mi, mn = base_q(t, rule)
    m = t.get("wk_m", 1.0)
    if m != 1.0:
        if mn:
            h = mn * m
            mn, mi = (int(h), 0) if abs(h - round(h)) < 1e-9 and h >= 1 else (0, max(1, int(10 * mn * m + 1e-9)))
        else:
            mi = max(1, int(mi * m + 1e-9))
    if room_k is not None and room is not None:
        cap = max(1, int(room_k * room / (t["risk_pts"] * PV)))
        if mi + 10 * mn > cap:
            mi, mn = cap, 0                     # capped below the minis: trade micros
    return mi, mn


def at_size(t, mi, mn, cum=0.0):
    """The unit trade at mi micros + mn minis (P&L, commission and slippage exact), then the soft daily loss limit."""
    q = mi + 10 * mn
    pts = t["legs"][0][1]
    comm = COMM * mi + NQ_COMM * mn
    pnl = pts * PV * q - comm
    low = min(0.0, t["w1"] * PV * q - comm, pnl)
    ru = t["risk_pts"] * PV * q
    x = {**t, "qty": q, "minis": mn, "micros": mi, "pnl": round(pnl, 2), "low": round(low, 2), "risk_usd": round(ru, 2),
         "r": round(pnl / ru, 3) if ru else 0.0, "mult": t.get("wk_m", 1.0), "half": t.get("wk_m", 1.0) < 1}
    worst = max(x["low"], -(t["risk_pts"] + SLIP) * PV * q - comm)
    if DLL and cum + worst <= -DLL:
        # MFFU closes the position when the day reaches -$1,000 (open P&L included): flat there with 1 tick of slippage,
        # whether the trade would have recovered (worse) or run on to a bigger stop loss (better: the loss is capped)
        p2 = round(-DLL - cum - SLIP * PV * q, 2)
        x.update(pnl=p2, low=min(p2, 0.0), exit="DLL", r=round(p2 / ru, 3) if ru else 0.0)
    return x


def sized(U, rule):
    out = []
    for t in sorted(U, key=lambda t: t["entry_t"]):
        cum = sum(y["pnl"] for y in out if y["day"] == t["day"])
        if cum <= -DLL:
            continue
        mi, mn = qty_of(t, rule)
        out.append(at_size(t, mi, mn, cum))
    return out


# ================================================================================================ scoring
def _play(ss, by, i0, H, rule, room_k, keep=None):
    bal = PLAN["start"]; peak = bal; mll = bal - PLAN["mll"]; lock = PLAN["start"] + PLAN["lock_above"]
    for k in range(i0, min(len(ss), i0 + H)):
        cum = low = 0.0
        for t in by.get(ss[k], []):
            if DLL and cum <= -DLL:
                break
            mi, mn = qty_of(t, rule, room=bal + cum - mll, room_k=room_k)
            x = at_size(t, mi, mn, cum)
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


def evals(U, rule, span, room_k=None, horizon=60):
    a, z = SPAN[span]
    ss = [d for d in SESS if a <= d <= z]
    by = collections.defaultdict(list)
    for t in sorted(U, key=lambda t: t["entry_t"]):
        if a <= t["day"] <= z:
            by[t["day"]].append(t)
    res = [_play(ss, by, i, horizon, rule, room_k) for i in range(len(ss))]
    N = len(res) or 1
    o = {}
    for H in (10, 20):
        o[f"p{H}"] = round(100 * sum(1 for r, n in res if r == "PASS" and n <= H) / N, 1)
        o[f"f{H}"] = round(100 * sum(1 for r, n in res if r == "FAIL" and n <= H) / N, 1)
    P_ = sum(1 for r, _ in res if r == "PASS"); F_ = sum(1 for r, _ in res if r == "FAIL")
    o["pass_rate"] = round(100 * P_ / (P_ + F_), 1) if P_ + F_ else None
    pas = [n for r, n in res if r == "PASS"]
    o["pass_med"] = float(np.median(pas)) if pas else None
    dec = [n for r, n in res if r != "OPEN"]
    o["exp_sess"] = round(float(np.mean(dec)) / (P_ / len(dec)), 1) if P_ else None
    k, pa, fa, path = 0, 0, 0, []
    while k < len(ss):
        r, n = _play(ss, by, k, len(ss), rule, room_k, keep=path)
        if r == "OPEN":
            break
        pa += r == "PASS"; fa += r == "FAIL"; k += n
    o["b2b"] = f"{pa}/{fa}"
    return o, path


def stats(T, span):
    a, z = SPAN[span]
    ss = [d for d in SESS if a <= d <= z]
    TT = sorted([t for t in T if a <= t["day"] <= z], key=lambda t: t["entry_t"])
    if not TT:
        return {"n": 0}
    p = np.array([t["pnl"] for t in TT]); gl = -p[p < 0].sum()
    eq = np.cumsum(p); dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())
    dayp = collections.defaultdict(float); dayl = collections.defaultdict(float)
    for t in TT:
        dayl[t["day"]] = min(dayl[t["day"]], dayp[t["day"]] + t["low"]); dayp[t["day"]] += t["pnl"]
    wk = collections.Counter(lit.iso_week(t["day"]) for t in TT)
    allwk = {lit.iso_week(d) for d in ss}
    R = np.array([t["pnl"] / t["risk_usd"] for t in TT])
    return {"n": len(TT), "tpw": round(len(TT) / (len(ss) / 5), 2), "wk2": round(100 * sum(wk[w] >= 2 for w in allwk) / len(allwk)),
            "win": round(100 * float((p > 0).mean()), 1), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (len(ss) / 21)), "dd": round(dd),
            "avg_r": round(float(R.mean()), 3), "tot_r": round(float(R.sum()), 1),
            "stop_pct": round(100 * sum(t["exit"] in ("STOP", "DLL") for t in TT) / len(TT), 1),
            "be_pct": round(100 * sum(t["exit"] == "BE" for t in TT) / len(TT), 1),
            "tgt_pct": round(100 * sum(t["exit"] == "TARGET" for t in TT) / len(TT), 1),
            "med_stop": float(np.median([t["risk_pts"] for t in TT])), "med_q": float(np.median([t["qty"] for t in TT])),
            "med_risk": round(float(np.median([t["risk_usd"] for t in TT]))), "max_risk": round(max(t["risk_usd"] for t in TT)),
            "worst_day": round(min(dayp.values())), "worst_low": round(min(dayl.values())),
            "dll_days": sum(1 for v in dayl.values() if v <= -DLL + 1e-6)}


SP = ("H1", "H2", "2026", "2021-25")


def score(U, rule, room_k=None, spans=SP):
    out = {}
    for s in spans:
        e, path = evals(U, rule, s, room_k)
        T = sized(U, rule) if room_k is None else path
        out[s] = {**stats(T, s), **e}
    return out


def row(nm, o, spans=("H1", "H2", "2021-25")):
    def f(s):
        if not s or not s.get("n"):
            return "n=0"
        return (f"n={s['n']} {s['tpw']}/wk win {s['win']} PF {s['pf']} net {s['net']:+,} ${s['per_month']:,}/mo DD {s['dd']:,} "
                f"stop {s['med_stop']} q {s['med_q']} ${s['med_risk']} 2w {s['p10']}/{s['f10']} 1m {s['p20']}/{s['f20']} "
                f"pr {s['pass_rate']} med {s['pass_med']} wd {s['worst_day']}")
    return f"{nm:30s} " + " | ".join(f"{k}[{f(o.get(k))}]" for k in spans if k in o)


# ================================================================================================ check
def check():
    U = unit()
    T = sized(U, ("lit", 800, 20.0))
    L = F.run(LIVE)
    ka = [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"], t["qty"]) for t in sorted(L, key=lambda t: t["entry_t"])]
    kb = [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"], t["qty"]) for t in T]
    bad = [(x, y) for x, y in zip(ka, kb) if not (x[:2] == y[:2] and abs(x[2] - y[2]) < 0.03 and x[3:] == y[3:])]
    n26 = [t for t in T if t["day"] >= "2026"]
    print(f"engine lit_live {len(ka)} trades | tight ext {len(kb)} | mismatches {len(bad) + abs(len(ka) - len(kb))} | "
          f"2026 {len(n26)} trades net {sum(t['pnl'] for t in n26):+,.0f}")
    for x in bad[:3]:
        print("diff", x)
    o = score(U, ("lit", 800, 20.0), spans=("H1", "H2", "2026"))
    for s in ("H1", "H2", "2026"):
        print(s, {k: o[s][k] for k in ("n", "pf", "net", "dd", "p10", "f10", "p20", "f20", "pass_rate", "pass_med", "b2b", "med_stop", "med_q", "med_risk")})
    return not bad and len(ka) == len(kb)


# ================================================================================================ the grid
def stop_variants():
    V = collections.OrderedDict()
    V["live: sweep extreme + 1 tick"] = {}
    V["1m protected swing + 1 tick"] = {"stop_mode": "tap"}
    V["1m protected swing + 0.1 ATR"] = {"stop_mode": "tap", "stop_atr": 0.1}
    V["1m protected swing + 2 pts"] = {"stop_mode": "tap", "stop_buf": 2.0}
    V["1m protected swing + 1 tick, min 12"] = {"stop_mode": "tap", "tight_min": 12.0}
    V["5m CISD candle + 1 tick"] = {"stop_mode": "cisd5"}
    V["5m higher low + 1 tick"] = {"stop_mode": "post5"}
    V["inducement low + 1 tick"] = {"stop_mode": "idm"}
    for f in (0.25, 0.5, 0.75):
        V[f"{int(f * 100)}% of the extreme distance"] = {"stop_mode": "frac", "stop_k": f}
    for k in (1.0, 1.5, 2.0):
        V[f"extreme, capped at {k:g} ATR"] = {"stop_mode": "atr", "stop_k": k}
    for c in (15, 20, 25, 30, 35, 40):
        V[f"cap {c}: skip wider"] = {"cap": float(c), "cap_mode": "skip"}
        V[f"cap {c}: 1m swing if wider, else skip"] = {"cap": float(c), "cap_mode": "tap_skip"}
        V[f"cap {c}: 1m swing if wider, cut to {c}"] = {"cap": float(c), "cap_mode": "tap_cap"}
        V[f"extreme, capped at {c} pts (fixed)"] = {"stop_mode": "pts", "stop_k": float(c)}
    # target / breakeven measured on the tight stop
    V["1m protected swing, target+BE on own R"] = {"stop_mode": "tap", "tgt_ref": "own"}
    V["1m protected swing, BE at the live 1R"] = {"stop_mode": "tap", "be_ref": "orig"}
    V["50% distance, target+BE on own R"] = {"stop_mode": "frac", "stop_k": 0.5, "tgt_ref": "own"}
    V["50% distance, BE at the live 1R"] = {"stop_mode": "frac", "stop_k": 0.5, "be_ref": "orig"}
    # refined entries (limit after the 1m CISD), stop at the sweep extreme and at the 1m swing
    for e in ("cisd", "fvg", "fvg_ce", "ob", "ob50", "fib50"):
        for w in (10, 20):
            V[f"entry {e} limit {w} bars, extreme stop"] = {"e2": e, "e2_wait": w}
        V[f"entry {e} limit 20 bars, 1m swing stop"] = {"e2": e, "e2_wait": 20, "stop_mode": "tap"}
    return V


SIZES = collections.OrderedDict([
    ("LIT rule $800/20", ("lit", 800, 20.0)),
    ("fast-eval $800/40", ("lit", 800, 40.0)),
    ("flat $400", ("lit", 400, None)), ("flat $600", ("lit", 600, None)), ("flat $800", ("lit", 800, None)),
    ("flat $1,000", ("lit", 1000, None)), ("flat $1,200", ("lit", 1200, None)),
    ("5 MNQ", ("mnq", 5)), ("10 MNQ", ("mnq", 10)), ("20 MNQ", ("mnq", 20)),
    ("1 NQ", ("nq", 1)), ("2 NQ", ("nq", 2)),
])


def _load():
    return json.load(open(OUT)) if os.path.exists(OUT) else {}


def grid(only=None):
    res = _load()
    V = stop_variants()
    for nm, P in V.items():
        if only and not any(o in nm for o in only):
            continue
        U = unit(P)
        rec = {"params": P, "sizes": {}}
        for sn, rule in SIZES.items():
            rec["sizes"][sn] = score(U, rule)
        # unit-level facts (the same at every size)
        rec["n26"] = sum(1 for t in U if t["day"] >= "2026")
        rec["src"] = dict(collections.Counter(t["stop_src"] for t in U if t["day"] >= "2026"))
        res[nm] = rec
        b = rec["sizes"]["LIT rule $800/20"]; f8 = rec["sizes"]["flat $800"]
        print(row(nm + " | LIT", b), flush=True)
        print(row(nm + " | flat800", f8), flush=True)
        json.dump(res, open(OUT, "w"), indent=1, default=str)
    return res


def room_grid():
    """Safe-eval room cap (k x the room to the max-loss floor) on top of the shortlisted stop x size pairs."""
    out = {}
    V = stop_variants()
    for nm in ("live: sweep extreme + 1 tick", "1m protected swing + 1 tick", "1m protected swing + 0.1 ATR",
               "50% of the extreme distance", "5m CISD candle + 1 tick"):
        U = unit(V[nm])
        for sn in ("fast-eval $800/40", "flat $600", "flat $800", "flat $1,000", "flat $1,200", "10 MNQ", "20 MNQ"):
            for k in (0.4, 0.5, 0.6):
                o = score(U, SIZES[sn], room_k=k, spans=("H1", "H2", "2026"))
                out[f"{nm} | {sn} | room {k}"] = o
                print(row(f"{nm[:22]}|{sn}|room{k}", o, spans=("H1", "H2")), flush=True)
        json.dump(out, open(OUT_ROOM, "w"), indent=1, default=str)


# ================================================================================================ honest view
def honest():
    """Trade by trade vs the live stop (same trades): what each tight stop does to the live winners and losers."""
    base = {(t["day"], t["entry_t"]): t for t in unit()}
    rep = {}
    V = stop_variants()
    for nm in ("1m protected swing + 1 tick", "1m protected swing + 0.1 ATR", "5m CISD candle + 1 tick", "5m higher low + 1 tick",
               "inducement low + 1 tick", "25% of the extreme distance", "50% of the extreme distance", "75% of the extreme distance",
               "extreme, capped at 1 ATR", "extreme, capped at 1.5 ATR", "extreme, capped at 25 pts (fixed)"):
        U = unit(V[nm])
        o = {}
        for span in ("H1", "H2", "2026"):
            a, z = SPAN[span]
            pairs = [(base[(t["day"], t["entry_t"])], t) for t in U if a <= t["day"] <= z and (t["day"], t["entry_t"]) in base]
            tr = collections.Counter((b["exit"], t["exit"]) for b, t in pairs)
            bw = [(b, t) for b, t in pairs if b["legs"][0][1] > 0]                       # live winners (points > 0)
            bt = [(b, t) for b, t in pairs if b["exit"] == "TARGET"]
            st_w = sum(1 for b, t in bw if t["exit"] == "STOP")
            # tight-stopped trades that later reached the live target with the live stop
            run_after = sum(1 for b, t in pairs if t["exit"] == "STOP" and b["exit"] == "TARGET")
            rb = np.array([b["legs"][0][1] / b["risk_pts"] for b, _ in pairs]); rt = np.array([t["legs"][0][1] / t["risk_pts"] for _, t in pairs])
            o[span] = {"n": len(pairs), "live_stop_pct": round(100 * np.mean([b["exit"] == "STOP" for b, _ in pairs]), 1),
                       "tight_stop_pct": round(100 * np.mean([t["exit"] == "STOP" for _, t in pairs]), 1),
                       "live_win_pct": round(100 * np.mean([b["legs"][0][1] > 0 for b, _ in pairs]), 1),
                       "tight_win_pct": round(100 * np.mean([t["legs"][0][1] > 0 for _, t in pairs]), 1),
                       "live_winners": len(bw), "live_winners_stopped": st_w, "live_targets": len(bt),
                       "live_targets_stopped": sum(1 for b, t in bt if t["exit"] == "STOP"), "stopped_then_ran_to_target": run_after,
                       "live_avg_r": round(float(rb.mean()), 3), "tight_avg_r": round(float(rt.mean()), 3),
                       "live_tot_r": round(float(rb.sum()), 1), "tight_tot_r": round(float(rt.sum()), 1),
                       "med_stop_live": float(np.median([b["risk_pts"] for b, _ in pairs])),
                       "med_stop_tight": float(np.median([t["risk_pts"] for _, t in pairs])),
                       "transitions": {f"{x}->{y}": n for (x, y), n in sorted(tr.items())}}
        rep[nm] = o
        s = o["2026"]
        print(f"{nm:40s} n={s['n']} stop% {s['live_stop_pct']}->{s['tight_stop_pct']} win% {s['live_win_pct']}->{s['tight_win_pct']} "
              f"winners stopped {s['live_winners_stopped']}/{s['live_winners']} targets stopped {s['live_targets_stopped']}/{s['live_targets']} "
              f"R/trade {s['live_avg_r']}->{s['tight_avg_r']} totR {s['live_tot_r']}->{s['tight_tot_r']} "
              f"H1 {o['H1']['live_tot_r']}->{o['H1']['tight_tot_r']} H2 {o['H2']['live_tot_r']}->{o['H2']['tight_tot_r']}", flush=True)
    json.dump(rep, open(OUT_HONEST, "w"), indent=1, default=str)
    return rep


# ================================================================================================ store runs
EXT, TAP = "live: sweep extreme + 1 tick", "1m protected swing + 1 tick"
SAVES = [   # id, title, stop variant, size rule, room_k, status, why
    ("lit_tight_live_ref", "LIT live (sweep-extreme stop, $800 up to 20 pts) - reference for the tight-stop study", EXT, ("lit", 800, 20.0), None,
     "info", "The live strategy as the study's reference (== run lit_live)."),
    ("lit_tight_tap_lit", "LIT, stop beyond the 1m protected swing (+1 tick), LIT size rule", TAP, ("lit", 800, 20.0), None, "rejected",
     "Median stop 14-17 pts, so the LIT rule puts ~$740 at risk instead of ~$270: the H1 $ come from 2.7x the risk. H2 and 2021-25 lose."),
    ("lit_tight_ext_flat800", "LIT live stop (sweep extreme), flat $800 a trade", EXT, ("lit", 800, None), None, "info",
     "Equal-risk reference for the tight stops: $800 at risk on every trade."),
    ("lit_tight_tap_flat800", "LIT, stop beyond the 1m protected swing, flat $800 a trade (equal risk)", TAP, ("lit", 800, None), None, "rejected",
     "At the same $800 a trade the tight stop wins H1 but loses H2 (and 2021-25) against the sweep-extreme stop: not both halves."),
    ("lit_tight_frac50_flat800", "LIT, stop at 50% of the sweep-extreme distance, flat $800", "50% of the extreme distance", ("lit", 800, None), None,
     "rejected", "Half the stop doubles the stop-outs of trades that later work; H2 loses money."),
    ("lit_tight_cap25_skip", "LIT, skip setups whose sweep-extreme stop is wider than 25 pts", "cap 25: skip wider", ("lit", 800, 20.0), None,
     "rejected", "Only ~0.3 trades a week are left: breaks the 2-4 a week rule."),
    ("lit_tight_cap30_tap", "LIT, 1m protected-swing stop when the sweep-extreme stop is wider than 30 pts (else skip)", "cap 30: 1m swing if wider, else skip",
     ("lit", 800, None), None, "rejected", "Keeps 2.8 trades a week, but at equal risk H2 is below the live stop."),
    ("lit_tight_entry_ob", "LIT, refined entry: limit at the 1m order block after the 1m CISD (10 bars), sweep-extreme stop",
     "entry ob limit 10 bars, extreme stop", ("lit", 800, 20.0), None, "rejected",
     "Shorter stops by ~3 pts only; misses the winners that never come back: H1 -$15k vs live."),
    ("lit_tight_ext_1nq", "LIT live stop (sweep extreme), 1 NQ mini on every trade", EXT, ("nq", 1), None, "rejected",
     "1 NQ on a 45-pt median stop risks ~$900 (up to $1,700, cut by the $1,000 daily limit): 2-week fails 30-40%."),
    ("lit_tight_tap_1nq", "LIT, 1m protected-swing stop, 1 NQ mini on every trade", TAP, ("nq", 1), None, "rejected",
     "Risk is small (~$270-310) but the tight stop's edge is gone in H2 and 2021-25."),
    ("lit_tight_eval_fast_room60", "LIT live stop, $800 up to a 40-pt stop + never more than 60% of the room to the max-loss floor",
     EXT, ("lit", 800, 40.0), 0.6, "adopt-candidate", "Fastest eval with 2-week fails under 10% in both halves (eval-speed mode)."),
    ("lit_tight_eval_800_25_room60", "LIT live stop, $800 up to a 25-pt stop + never more than 60% of the room to the max-loss floor",
     EXT, ("lit", 800, 25.0), 0.6, "adopt-candidate", "Same pass rate as live, faster passes in both halves (balanced eval mode)."),
    ("lit_tight_funded_800_25", "LIT live stop, $800 up to a 25-pt stop (no room cap): funded-account size", EXT, ("lit", 800, 25.0), None,
     "promising", "More $ in both halves than live at a DD near the $2,000 trailing limit; the room cap still guards the first $2,100."),
]


def save(extra=None):
    V = stop_variants()
    for rid, title, vn, rule, rk, status, why in (extra or SAVES):
        U = unit(V[vn])
        if rk is None:
            T = sized(U, rule)
        else:
            T = evals(U, rule, "2026", rk)[1] + [x for x in evals(U, rule, "2021-25", rk)[1]]
        T = [{k: v for k, v in t.items() if k not in ("legs",)} for t in T]
        S = rl.score(T, SESS)
        o = score(U, rule, room_k=rk)
        h = lambda s: (f"n={s['n']} {s['tpw']}/wk win {s['win']}% PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,} "
                       f"median stop {s['med_stop']} pts, {s['med_q']} micros, ${s['med_risk']} at risk; eval 2wk {s['p10']}/{s['f10']} "
                       f"1mo {s['p20']}/{s['f20']} pass rate {s['pass_rate']}% median {s['pass_med']}")
        rl.save(rid, title, "other", "Owner order 2026-10-18: upsizing and fewer wide stops - do tighter stops or more contracts pay on LIT?",
                params={**LIVE, **V[vn], "size": list(rule), "room_k": rk}, trades=T, scored=S, status=status,
                verdict=f"{why} 2026 H1 (pick) {h(o['H1'])}; 2026 H2 (check) {h(o['H2'])}; 2021-25 reference only {h(o['2021-25'])}",
                notes="tools/lit_tightstop.py (wraps engine/lit.py; stop_mode ext + LIT size == run lit_live trade for trade). "
                      "Same LIT signals and fills; the stop, entry limit or size changes. MFFU $1,000 soft daily loss modelled; "
                      "NQ minis at $4.50 a round trip.", writeup="lit-tight-stops-size", tags=["lit", "lit_tight"])
        print("saved", rid, row("", o, spans=("H1", "H2")), flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "grid":
        grid(sys.argv[2:] or None)
    elif cmd == "room":
        room_grid()
    elif cmd == "honest":
        honest()
    elif cmd == "save":
        save()
