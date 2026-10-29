"""Structure management for LIT (owner 2026-10-28 night: "trade like a person, not a fixed rr; learn market structure").

Same live LIT trades as tools/lit_rev_exit.py (tools/lit_final.run with live_model.json "lit": 631 trades, 120 in 2026, == run
lit_live). Only what happens after the fill changes (and, for the "htf" ideas, which trades are kept); the executor is
lit_rev_exit.manage (the post-fill part of engine/lit.simulate_x) extended with structure rules from engine/structure.py.
With every new option off it gives every live trade's exit and points exactly (`check`).

Structure (engine/structure.Tracker, closed bars only): 5m swings / BOS / CHoCH / protected swing on the Market's 5m bars
(2021-26), 15m and 1h resampled from them, 1m on the true 1m bars (2026). An event is usable from its bar's close
(known_t); a rule decides at a 1m close (5m on 2021-25 days) and acts from the next bar.

New options (X):
  tgt     {"mode": "cap"|"pool", "set": "lit"|"lit1h"|"1h", "min_r": R, "front": ticks}: the next opposing liquidity pool
          (a long: an untaken buy-side level above the entry, known before the fill; LIT's own levels = engine/lit.Market.levels,
          "1h" = unbroken 1h swing highs / lows) at least min_r R away. "cap": target = the nearer of the VIX band and that
          pool; "pool": the pool instead of the band (no pool: the band). The target sits `front` ticks in front of the pool;
          never beyond 8R (the live bank).
  part    {"min_r": R, "f": share, "be": bool, "set": ...}: take `f` of the position off at the first opposing pool >= min_r R
          (limit at the pool - 1 tick), the rest runs to the live target; be = the rest's stop to entry + 1.25 then.
  strail  {"tf": "5m"|"15m"|"1m", "k": R, "kinds": "bos"|"any", "lock": bool}: after a break IN the trade's direction on tf
          (BOS; "any" = a CHoCH in favour too), once the best point is >= k R, the stop moves to 1 tick beyond the new
          protected swing (the origin of the breaking leg), only ever tighter and below the close; lock = only once that is past
          entry + 1.25.
  choch   {"tf": ..., "k": R, "act": "exit"|"be", "kinds": "choch"|"any"}: a CHoCH AGAINST the trade on tf (any = a BOS against
          too) once the best point is >= k R -> out at the next open - 1 tick ("exit") or the stop to entry + 1.25 ("be").
  htf     {"tf": "1h"|"15m"|"both", "mode": "skip_against"|"only_with"|"size", "up": m, "down": m}: the trend of tf at the
          fill (the last break known by then). skip_against = drop a trade whose tf trend is against it; only_with = keep only
          trades with the trend; size = x up with the trend / x down against it (LIT size rule only, rounded down, 1..40).
          A dropped trade is approximate (live LIT might take a later setup that day): the trade list shrinks.

Money and judging = tools/lit_rev_exit.py (the LIT size rule as run lit_live; the live eval path two_week on MFFU 50K evals,
fresh-eval odds on every session, 2,000-path MC). LIT rule: pick on 2026 H1, check on H2; 2021-25 reference only.

  python -X utf8 tools/structure_manage.py check     # options off == live trades; event / pool counts
  python -X utf8 tools/structure_manage.py grid      # every variant -> research/lit/structure_results.json
  python -X utf8 tools/structure_manage.py save      # rl.save runs lit_struct_*
Paper research only; engine/ trading code and live_model*.json untouched.
"""
from __future__ import annotations

import collections
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine import structure as ST  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_rev_exit as RX  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "structure_results.json")
PV, COMM, SLIP, TICK = lit.PV, lit.COMM, lit.SLIP, lit.TICK
LIVE = RX.LIVE
BE_OFF = RX.BE_OFF
SPANS = RX.SPANS


# ================================================================================================ structure events
_EV: dict = {}


def events(tf):
    """engine/structure.frame_events of one timeframe over the whole history (5m Market bars; 15m / 1h resampled; 1m = the
    true 1m executor bars of 2026)."""
    if tf in _EV:
        return _EV[tf]
    c = RX.cx()
    if tf == "1m":
        B = c[60].B
        E = ST.frame_events(B.t, B.o, B.h, B.l, B.c, 60)
    else:
        M = c["M"]
        if tf == "5m":
            E = ST.frame_events(M.t, M.o, M.h, M.l, M.c, 300)
        else:
            secs = ST.TF_SECS[tf]
            rows = [[int(a), float(b), float(d), float(e), float(f)] for a, b, d, e, f in zip(M.t, M.o, M.h, M.l, M.c)]
            R = ST.resample(rows, secs, 300)
            A = np.array(R)
            E = ST.frame_events(A[:, 0].astype(np.int64), A[:, 1], A[:, 2], A[:, 3], A[:, 4], secs)
    _EV[tf] = E
    return E


# ================================================================================================ pools at the fill
_DAYK = {}


def day_k(day):
    if not _DAYK:
        M = RX.cx()["M"]
        for k, (d, s, e) in enumerate(M.days):
            _DAYK[str(d)] = k
    return _DAYK.get(str(day))


def opposing_pools(t, sets="lit"):
    """Untaken opposing pools known before the fill, as direction-space distances from the entry (> 0), nearest first:
    [(dist_pts, price, label)]."""
    c = RX.cx()
    M = c["M"]
    d = t["dir"]
    entry = float(t["entry_px"])
    nf = int(np.searchsorted(M.t, int(t["entry_t"]) - 300, side="right"))      # 5m bars closed before the fill
    out = []
    if sets in ("lit", "lit1h"):
        k = day_k(t["day"])
        if k is not None:
            for side, px, ki, nm, cls in M.levels(k):
                if (d == 1 and side != "high") or (d == -1 and side != "low"):
                    continue
                if ki >= nf - 0 or (px - entry) * d <= 0:
                    continue
                a = max(int(ki) + 1, 0)
                if a < nf:
                    if d == 1 and float(M.h[a:nf].max()) >= px:
                        continue
                    if d == -1 and float(M.l[a:nf].min()) <= px:
                        continue
                out.append(((px - entry) * d, float(px), nm))
    if sets in ("1h", "lit1h"):
        E = events("1h")
        side = 1 if d == 1 else -1
        m = (E["sw_side"] == side) & (E["sw_known"] <= int(t["entry_t"])) & (E["sw_t"] >= int(t["entry_t"]) - 7 * 86400)
        for st, px in zip(E["sw_t"][m], E["sw_px"][m]):
            if (px - entry) * d <= 0:
                continue
            a = int(np.searchsorted(M.t, int(st) + 3600))
            if a < nf:
                if d == 1 and float(M.h[a:nf].max()) >= px:
                    continue
                if d == -1 and float(M.l[a:nf].min()) <= px:
                    continue
            out.append(((float(px) - entry) * d, float(px), "1h_swing"))
    out.sort()
    return out


# ================================================================================================ executor (post-fill)
class EvCursor:
    """Walks one frame's events forward in time: new() = the events known by `close_t` not seen yet."""

    def __init__(self, E, t_from):
        self.E = E
        self.p = int(np.searchsorted(E["known_t"], int(t_from), side="right"))

    def new(self, close_t):
        E = self.E
        q = int(np.searchsorted(E["known_t"], int(close_t), side="right"))
        out = range(self.p, q)
        self.p = max(self.p, q)
        return out


def manage(X, BX, fill, d, entry, stop, tg, s_day, risk, part=None):
    """lit_rev_exit.manage (stop before target in a bar, BE at 1R -> entry + 1.25, the 15-minute check, flat 15:55) + the
    structure rules. Returns (exit kind, exit pts (weighted over the legs), worst pts, mfe R, exit k, legs)."""
    X = X or {}
    B = BX.B
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    flat = LIVE["flat_mod"]
    on1 = B.secs == 60
    tc = LIVE.get("t_check") if on1 else None
    be_r = LIVE["be_r"]
    cur, be_done, mfe, worst = stop, False, 0.0, 0.0
    moved, tag, cut = False, None, None
    curs = {}
    for key in ("strail", "choch"):
        o = X.get(key)
        if o:
            tf = o.get("tf", "5m")
            if tf == "1m" and not on1:
                tf = "5m"
            curs[key] = (EvCursor(events(tf), int(B.t[fill])), events(tf))
    banked = None              # (share, pts) of the partial
    pf = None
    if part:
        pf = part
    k = fill
    exit_px = kind = None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if cut is not None:
            exit_px, kind = float(o_d[k]) - SLIP, cut; break
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            px = min(cur, float(o_d[k])) if moved else cur
            exit_px, kind = px - SLIP, (tag if moved else ("BE" if be_done else "STOP")); break
        mfe = max(mfe, (hi_d[k] - entry) / risk)
        if pf is not None and banked is None and hi_d[k] >= pf["px"]:
            banked = (pf["f"], pf["px"] - entry)
            if pf.get("be") and entry + BE_OFF > cur:
                cur, moved, tag = entry + BE_OFF, True, "BE"
                be_done = True
        if hi_d[k] >= tg:
            exit_px, kind = tg, "TARGET"; break
        if be_r is not None and not be_done and hi_d[k] >= entry + be_r * risk:
            if entry + BE_OFF > cur:
                cur = entry + BE_OFF
                if moved:
                    tag = "BE"
            be_done = True
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if tc and not be_done and round((B.t[k] - B.t[fill]) / 60.0) + 1 == int(tc.get("at", 15)) \
                and mfe < float(tc.get("mfe", 0.5)) and c_d[k] < entry - float(tc.get("x", 0.3)) * risk:
            if k + 1 < B.n and B.day[k + 1] == s_day:
                cut = "CUT_T15"
                k += 1
                continue
        close_t = int(B.t[k]) + B.secs
        nxt_ok = k + 1 < B.n and B.day[k + 1] == s_day
        # ---- structure rules at the close of bar k
        if "choch" in curs:
            o = X["choch"]
            cu, E = curs["choch"]
            fire = False
            for i in cu.new(close_t):
                if int(E["dir"][i]) == -d and (o.get("kinds", "choch") == "any" or int(E["kind"][i]) == 2):
                    fire = True
            if fire and mfe >= float(o.get("k", 1.0)) and nxt_ok:
                if o.get("act", "exit") == "exit":
                    cut = "CHOCH"
                    k += 1
                    continue
                lvl = entry + BE_OFF
                if lvl > cur:
                    if c_d[k] <= lvl:
                        cut = "CHOCH_BE"
                        k += 1
                        continue
                    cur, moved, tag = lvl, True, "CHOCH_BE"
        if "strail" in curs:
            o = X["strail"]
            cu, E = curs["strail"]
            for i in cu.new(close_t):
                if int(E["dir"][i]) != d:
                    continue
                if o.get("kinds", "bos") == "bos" and int(E["kind"][i]) != 1:
                    continue
                if mfe < float(o.get("k", 0.0)):
                    continue
                lvl = float(E["prot"][i]) * d - TICK
                if (not o.get("lock") or lvl >= entry + BE_OFF) and lvl > cur and lvl < c_d[k]:
                    cur, moved, tag = lvl, True, "TRAIL"
        k += 1
    if exit_px is None:
        return None
    pts_rest = exit_px - entry
    if banked is not None:
        f = banked[0]
        legs = [(f, banked[1]), (1.0 - f, pts_rest)]
        pts = f * banked[1] + (1.0 - f) * pts_rest
    else:
        legs = [(1.0, pts_rest)]
        pts = pts_rest
    return kind, pts, worst, mfe, k, legs


# ================================================================================================ all trades
def trades(X=None):
    X = X or {}
    c = RX.cx()
    out = []
    htf = X.get("htf")
    for t in c["T"]:
        BX = c[60] if t["tf"] == 1 else c[300]
        B = BX.B
        d = t["dir"]
        fill = int(np.searchsorted(B.t, t["entry_t"]))
        assert int(B.t[fill]) == t["entry_t"], t["day"]
        entry, stop, tg = t["entry_px"] * d, t["stop_px"] * d, t["target_px"] * d
        risk = entry - stop
        mult = 1.0
        if htf:
            tws = [ST.trend_at(events(x), int(t["entry_t"])) for x in (("1h", "15m") if htf["tf"] == "both" else (htf["tf"],))]
            with_ = all(x == d for x in tws)
            against = all(x == -d for x in tws)
            if htf["mode"] == "skip_against" and against:
                continue
            if htf["mode"] == "only_with" and not with_:
                continue
            if htf["mode"] == "size":
                mult = float(htf.get("up", 1.0)) if with_ else (float(htf.get("down", 1.0)) if against else 1.0)
        tg_live = tg
        if X.get("tgt"):
            o = X["tgt"]
            P = [p for p in opposing_pools(t, o.get("set", "lit")) if p[0] >= float(o.get("min_r", 1.5)) * risk]
            if P:
                pd_ = entry + P[0][0] - float(o.get("front", 1)) * TICK
                if o.get("mode", "cap") == "cap":
                    tg = min(tg_live, pd_)
                else:
                    tg = min(pd_, entry + LIVE["max_rr"] * risk)
        part = None
        if X.get("part"):
            o = X["part"]
            P = [p for p in opposing_pools(t, o.get("set", "lit")) if p[0] >= float(o.get("min_r", 1.0)) * risk]
            if P and entry + P[0][0] - TICK < tg:
                part = {"px": entry + P[0][0] - TICK, "f": float(o.get("f", 0.5)), "be": bool(o.get("be"))}
        r = manage(X, BX, fill, d, entry, stop, tg, int(B.day[fill]), risk, part)
        kind, pts, worst, mfe, kx, legs = r
        out.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": int(B.t[kx]) + B.secs, "dir": d, "exit": kind,
                    "risk": round(risk, 2), "tgt": round(tg - entry, 2), "pts": round(pts, 4), "w1": round(worst, 4),
                    "legs": [(f, round(p, 4)) for f, p in legs], "mfe": round(mfe, 3), "tf": t["tf"], "live_exit": t["exit"],
                    "live_pts": round((t["pnl"] + COMM * t["qty"]) / (PV * t["qty"]), 4), "live_risk": t["risk_pts"],
                    "tight": False, "mult": mult, "tgt_moved": round(tg, 2) != round(tg_live, 2), "part": part is not None})
    return out


def lit_size(U):
    """tools/lit_rev_exit.lit_size + the htf size multiplier (rounded down, 1..40)."""
    L = RX.lit_size(U)
    out = []
    for u, l in zip(sorted(U, key=lambda u: u["entry_t"]), L):
        m = float(u.get("mult", 1.0))
        if abs(m - 1.0) < 1e-9:
            out.append(l)
            continue
        q = max(1, min(lit.MAX_MICROS, int(l["qty"] * m + 1e-9)))
        pnl = u["pts"] * PV * q - COMM * q
        low = min(0.0, u["w1"] * PV * q - COMM * q, pnl)
        out.append({**l, "qty": q, "pnl": round(pnl, 2), "low": round(low, 2), "r": round(pnl / (u["risk"] * PV * q), 3),
                    "risk_usd": round(u["risk"] * PV * q, 2)})
    return out


def changed(L, base_L):
    """Per span: trades whose $ changed vs live (keyed by entry time; dropped trades count as changed to $0)."""
    bm = {l["entry_t"]: l for l in base_L}
    lm = {l["entry_t"]: l for l in L}
    out = {}
    for span in ("H1", "H2", "2021-25"):
        a, z = SPANS[span]
        sv = kl = nch = drop = 0
        sv_usd = kl_usd = oth = drop_usd = 0.0
        for et, b in bm.items():
            if not (a <= b["day"] <= z):
                continue
            l = lm.get(et)
            if l is None:
                drop += 1; drop_usd -= b["pnl"]
                continue
            du = l["pnl"] - b["pnl"]
            if abs(du) < 0.5:
                continue
            nch += 1
            if b["pnl"] < 0 and du > 0:
                sv += 1; sv_usd += du
            elif b["pnl"] > 0 and du < 0:
                kl += 1; kl_usd += du
            else:
                oth += du
        out[span] = {"changed": nch, "losers_saved": sv, "saved_usd": round(sv_usd), "winners_cut": kl, "cut_usd": round(kl_usd),
                     "other_usd": round(oth), "dropped": drop, "dropped_usd": round(drop_usd)}
    return out


def evaluate(X, base_L=None, with_eval=True):
    U = trades(X)
    L = lit_size(U)
    U26 = [u for u in U if u["day"] >= "2026"]
    o = {"X": X, "lit": {s: RX.lit_stats(L, s) for s in ("H1", "H2", "2021-25")}}
    if with_eval and not (X.get("htf") or {}).get("mode") == "size":
        o["eval"] = {s: RX.eval_path(U26, s) for s in ("H1", "H2")}
    if base_L is not None:
        o["chg"] = changed(L, base_L)
    o["n_moved"] = {"tgt": sum(1 for u in U26 if u.get("tgt_moved")), "part": sum(1 for u in U26 if u.get("part")),
                    "exits": dict(collections.Counter(u["exit"] for u in U26))}
    return o, U, L


def line(nm, o):
    def f(s):
        return f"PF {s['pf']} net {s['net']:+,} DD {s['dd']:,} 2w {s['p10']}/{s['f10']} tpw {s['tpw']}"
    e = o.get("eval")
    ev = (f" | EVAL H1[{f(e['H1'])} mc {e['H1']['mc']['p10']}/{e['H1']['mc']['f10']}] H2[{f(e['H2'])} mc {e['H2']['mc']['p10']}/"
          f"{e['H2']['mc']['f10']}]") if e else ""
    return f"{nm[:34]:34s} LIT H1[{f(o['lit']['H1'])}] H2[{f(o['lit']['H2'])}] 21-25[{f(o['lit']['2021-25'])}]{ev}"


# ================================================================================================ the 2026-10-28 trade
def today(X):
    """The first live LIT trade (2026-10-28, -$437) replayed under X on the PC's NinjaTrader 1m bars (heartbeat branch):
    structure from those bars only."""
    import pandas as pd
    try:
        B, et, dix = RX.today_bars()
    except Exception as e:
        return {"error": f"{e.__class__.__name__}: {e}"[:120]}
    BX = RX.Bx(B)
    B5 = RX.five(B)
    tf_ev = {"1m": ST.frame_events(B.t, B.o, B.h, B.l, B.c, 60), "5m": ST.frame_events(B5.t, B5.o, B5.h, B5.l, B5.c, 300)}
    rows = [[int(a), float(b), float(c_), float(d_), float(e_)] for a, b, c_, d_, e_ in zip(B5.t, B5.o, B5.h, B5.l, B5.c)]
    for tf in ("15m", "1h"):
        A = np.array(ST.resample(rows, ST.TF_SECS[tf], 300))
        tf_ev[tf] = ST.frame_events(A[:, 0].astype(np.int64), A[:, 1], A[:, 2], A[:, 3], A[:, 4], ST.TF_SECS[tf])
    saved = dict(_EV)
    _EV.clear(); _EV.update(tf_ev)
    try:
        TD = RX.TODAY
        d = TD["dir"]
        ts = lambda s: int(pd.Timestamp(s, tz="America/New_York").timestamp())
        fill = int(np.searchsorted(B.t, ts(TD["entry_et"])))
        entry, stop, tg = TD["entry"] * d, TD["stop"] * d, TD["target"] * d
        risk = entry - stop
        if X.get("htf"):
            tws = [ST.trend_at(_EV[x], int(B.t[fill])) for x in (("1h", "15m") if X["htf"]["tf"] == "both" else (X["htf"]["tf"],))]
            if X["htf"]["mode"] in ("skip_against", "only_with"):
                if (X["htf"]["mode"] == "skip_against" and all(x == -d for x in tws)) or (X["htf"]["mode"] == "only_with" and not all(x == d for x in tws)):
                    return {"exit": "SKIPPED", "usd": 0, "trend": tws}
        r = manage({k: v for k, v in X.items() if k in ("strail", "choch")}, BX, fill, d, entry, stop, tg, int(B.day[fill]), risk)
        kind, pts, worst, mfe, kx, legs = r
        q = TD["qty"]
        return {"exit": kind, "exit_et": str(et.iloc[kx])[:16], "pts": round(pts, 2), "qty": q, "usd": round(pts * PV * q - 1.90 * q),
                "mfe_r": round(float(mfe), 2)}
    finally:
        _EV.clear(); _EV.update(saved)


# ================================================================================================ variants
def variants():
    V = collections.OrderedDict()
    V["live"] = {}
    # 1. target = the next opposing pool (instead of / capped by the VIX band)
    for st in ("lit", "lit1h", "1h"):
        for mode in ("cap", "pool"):
            for mr in (1.5, 2.0, 3.0):
                V[f"tgt_{mode}_{st}_r{mr}"] = {"tgt": {"mode": mode, "set": st, "min_r": mr, "front": 1}}
    # 2. a partial at the first opposing pool
    for st in ("lit", "lit1h"):
        for mr in (1.0, 2.0):
            for be in (False, True):
                V[f"part_{st}_r{mr}{'_be' if be else ''}"] = {"part": {"set": st, "min_r": mr, "f": 0.5, "be": be}}
    # 3. structure trail: after a BOS in favour, the stop to the new protected swing
    for tf in ("5m", "15m", "1m"):
        for k in (0.0, 1.0, 2.0):
            for kinds in ("bos", "any"):
                V[f"strail_{tf}_k{k}_{kinds}"] = {"strail": {"tf": tf, "k": k, "kinds": kinds}}
        V[f"strail_{tf}_lock"] = {"strail": {"tf": tf, "k": 0.0, "kinds": "bos", "lock": True}}
    # 4. exit / BE on a CHoCH against the trade after +X R
    for tf in ("5m", "15m", "1m"):
        for k in (0.5, 1.0, 1.5, 2.0):
            for act in ("exit", "be"):
                if act == "be" and k >= 1.0:
                    continue          # the live 1R breakeven already sits at entry + 1.25 there: identical to live
                V[f"choch_{tf}_k{k}_{act}"] = {"choch": {"tf": tf, "k": k, "act": act}}
        V[f"choch_{tf}_k0.75_be"] = {"choch": {"tf": tf, "k": 0.75, "act": "be"}}
        V[f"choch_{tf}_k0.75_exit"] = {"choch": {"tf": tf, "k": 0.75, "act": "exit"}}
    # 3b. the 15m trail from +0.5R, and the 2026-10-28 shape: BE on any break against (BOS or CHoCH) after +0.75R
    V["strail_15m_k0.5_any"] = {"strail": {"tf": "15m", "k": 0.5, "kinds": "any"}}
    V["strail_15m_k1.0_any_lock"] = {"strail": {"tf": "15m", "k": 1.0, "kinds": "any", "lock": True}}
    for tf in ("5m", "1m"):
        V[f"breakany_{tf}_k0.75_be"] = {"choch": {"tf": tf, "k": 0.75, "act": "be", "kinds": "any"}}
    # 5. higher-timeframe structure agreement at the entry
    for tf in ("1h", "15m", "both"):
        V[f"htf_{tf}_skip_against"] = {"htf": {"tf": tf, "mode": "skip_against"}}
        V[f"htf_{tf}_only_with"] = {"htf": {"tf": tf, "mode": "only_with"}}
        V[f"htf_{tf}_size"] = {"htf": {"tf": tf, "mode": "size", "up": 1.5, "down": 0.5}}
    return V


# ================================================================================================ commands
def check():
    t0 = time.perf_counter()
    c = RX.cx()
    U = trades({})
    bad = [(u["day"], u["exit"], u["live_exit"], u["pts"], u["live_pts"]) for u in U
           if u["exit"] != u["live_exit"] or abs(u["pts"] - u["live_pts"]) > 0.01]
    L = lit_size(U)
    badq = [(l["day"], l["qty"], t["qty"]) for l, t in zip(L, sorted(c["T"], key=lambda t: t["entry_t"])) if l["qty"] != t["qty"]]
    print(f"live trades {len(U)} (2026 {sum(1 for u in U if u['day'] >= '2026')}) | exit/points mismatches {len(bad)} | size mismatches {len(badq)}")
    for b in bad[:8]:
        print("  diff", b)
    print("2026 net", round(sum(l["pnl"] for l in L if l["day"] >= "2026")), "2021-25 net", round(sum(l["pnl"] for l in L if l["day"] < "2026")))
    for tf in ("1m", "5m", "15m", "1h"):
        E = events(tf)
        print(f"  {tf}: {len(E['known_t']):,} breaks ({int((E['kind'] == 2).sum()):,} CHoCH), {len(E['sw_t']):,} swings")
    n_pool = sum(1 for t in c["T"] if t["day"] >= "2026" and opposing_pools(t, "lit"))
    print(f"  2026 trades with an untaken opposing LIT pool beyond the entry: {n_pool}/120")
    print("today live replay:", today({}), f"({time.perf_counter() - t0:.1f} s)")
    return not bad and not badq


def grid(names=None):
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    V = variants()
    base_o, _, base_L = evaluate({})
    base_o["today"] = today({})
    res["live"] = base_o
    print(line("live", base_o), flush=True)
    for nm, X in V.items():
        if nm == "live" or (names and nm not in names) or (nm in res and not names):
            continue
        t1 = time.perf_counter()
        o, U, L = evaluate(X, base_L)
        o["today"] = today(X)
        res[nm] = o
        print(line(nm, o), "| today", o["today"].get("exit"), o["today"].get("usd"), f"({time.perf_counter() - t1:.0f}s)", flush=True)
        json.dump(res, open(OUT, "w"), indent=1, default=str)
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    return res


def gates(o, b):
    """The LIT gate: better than live in 2026 H1 (picked) AND H2 (check) on the LIT size rule AND the eval path (net and 2-week
    pass - fail), 2+ trades a week kept."""
    L, LB = o["lit"], b["lit"]
    ok_l = all(L[s]["net"] > LB[s]["net"] for s in ("H1", "H2"))
    e, eb = o.get("eval"), b.get("eval")
    ok_e = None
    if e and eb:
        ok_e = all(e[s]["net"] >= eb[s]["net"] and (e[s]["p10"] - e[s]["f10"]) >= (eb[s]["p10"] - eb[s]["f10"]) for s in ("H1", "H2"))
    ok_f = all(L[s]["tpw"] >= 2.0 for s in ("H1", "H2"))
    return {"lit": ok_l, "eval": ok_e, "freq": ok_f, "all": bool(ok_l and ok_f and (ok_e is not False))}


def report():
    res = json.load(open(OUT))
    b = res["live"]
    rows = []
    for nm, o in res.items():
        if nm == "live":
            continue
        g = gates(o, b)
        dl = {s: o["lit"][s]["net"] - b["lit"][s]["net"] for s in ("H1", "H2", "2021-25")}
        rows.append((g["all"], dl["H1"] + dl["H2"], nm, dl, g))
    rows.sort(key=lambda r: (not r[0], -r[1]))
    for ok, _, nm, dl, g in rows[:40]:
        print(f"{'PASS' if ok else '    '} {nm:34s} dH1 {dl['H1']:+8,.0f} dH2 {dl['H2']:+8,.0f} d21-25 {dl['2021-25']:+8,.0f} {g}")
    print(f"{sum(1 for r in rows if r[0])} of {len(rows)} variants pass every gate")


SAVE = [   # run id, variant, family (status from the gates at save time)
    ("lit_struct_base", "live", "management"),
    ("lit_struct_tgt_cap_lit_r1.5", "tgt_cap_lit_r1.5", "targets"),
    ("lit_struct_tgt_pool_lit_r3", "tgt_pool_lit_r3.0", "targets"),
    ("lit_struct_tgt_cap_1h_r3", "tgt_cap_1h_r3.0", "targets"),
    ("lit_struct_part_lit_r1", "part_lit_r1.0", "management"),
    ("lit_struct_strail_5m_k1", "strail_5m_k1.0_bos", "management"),
    ("lit_struct_strail_15m_k1_any", "strail_15m_k1.0_any", "management"),
    ("lit_struct_choch_5m_k075_be", "choch_5m_k0.75_be", "management"),
    ("lit_struct_choch_5m_k1_exit", "choch_5m_k1.0_exit", "management"),
    ("lit_struct_choch_15m_k1_exit", "choch_15m_k1.0_exit", "management"),
    ("lit_struct_htf_1h_skip", "htf_1h_skip_against", "filters"),
    ("lit_struct_htf_both_skip", "htf_both_skip_against", "filters"),
    ("lit_struct_htf_1h_size", "htf_1h_size", "risk"),
]


def save(extra=()):
    res = json.load(open(OUT))
    V = variants()
    b = res["live"]
    picks = list(SAVE) + [(f"lit_struct_{nm}", nm, "management") for nm in extra]
    for rid, nm, fam in picks:
        if nm not in res:
            continue
        o = res[nm]
        U = trades(V[nm]); L = lit_size(U)
        S = rl.score(L, F.SESS)
        g = gates(o, b) if nm != "live" else None
        st = "info" if nm == "live" else ("adopt-candidate" if g["all"] else ("promising" if g["lit"] and g["freq"] else "rejected"))
        h = lambda s: (f"PF {o['lit'][s]['pf']} net {o['lit'][s]['net']:+,} (${o['lit'][s]['per_month']:,}/mo) DD {o['lit'][s]['dd']:,} "
                       f"2w {o['lit'][s]['p10']}/{o['lit'][s]['f10']} tpw {o['lit'][s]['tpw']}")
        ver = f"LIT size: H1 {h('H1')}; H2 {h('H2')}; 2021-25 ref {h('2021-25')}."
        if o.get("eval"):
            e = lambda s: (f"PF {o['eval'][s]['pf']} net {o['eval'][s]['net']:+,} 2w {o['eval'][s]['p10']}/{o['eval'][s]['f10']} "
                           f"(MC {o['eval'][s]['mc']['p10']}/{o['eval'][s]['mc']['f10']}) dec10 {o['eval'][s]['dec10']} med {o['eval'][s]['pass_med']}")
            ver += f" Eval path (two_week): H1 {e('H1')}; H2 {e('H2')}."
        ver += f" 2026-10-28 live trade: {o.get('today', {}).get('exit')} ${o.get('today', {}).get('usd', 0):+,} (live -$437)."
        if g:
            ver += f" Gates: {g}."
        rl.save(rid, f"LIT structure management: {nm}", fam,
                "Owner 2026-10-28: trade like a person, not a fixed RR: structure targets (next opposing pool), partial at the "
                "first pool, trail to the protected swing after a BOS, BE / exit on a CHoCH against, 1h structure agreement",
                params={**LIVE, "x_struct": V[nm]}, trades=L, scored=S, status=st, verdict=ver,
                notes="tools/structure_manage.py: live LIT trades (tools/lit_final.run, == lit_live), post-fill re-managed with "
                      "engine/structure.py (closed bars, no look-ahead) on true 1m bars (2026; 5m in 2021-25), LIT size rule; "
                      "eval columns in the verdict = live two_week sizing.",
                writeup="structure-management", tags=["lit", "structure"])
        print("saved", rid, st)


def advisor_check(out_path=os.path.join(ROOT, "research", "lit", "advisor_backtest.json")):
    """engine/advisor.py (the live shadow) on the 120 LIT trades of 2026 at the LIT size rule, on data/NQ_1m.csv: its $ per
    rule vs this research's variant of the same rule (different code path: 1m-built structure with a 6-day warm-up, the
    advisor's small executor + the difference method). The live tally starts from zero; this is its backtest."""
    import bisect
    import pandas as pd
    from engine import advisor as AD
    c = RX.cx()
    U = trades({})
    L = {l["entry_t"]: l for l in lit_size(U)}
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"), usecols=["time", "open", "high", "low", "close"])
    df = df[df["time"] >= int(c["M"].t[0])].drop_duplicates("time").sort_values("time")
    rows = ST.as_rows(df)
    ts = [r[0] for r in rows]
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    by = collections.defaultdict(lambda: collections.defaultdict(float))
    nf = collections.defaultdict(collections.Counter)
    recs = []
    t0 = time.time()
    for t in sorted(c["T"], key=lambda t: t["entry_t"]):
        if t["day"] < "2026" or t["tf"] != 1:
            continue
        lv = L[t["entry_t"]]
        half = "H1" if t["day"] <= "2026-06-30" else "H2"
        a = bisect.bisect_left(ts, int(t["entry_t"]) - 7 * 86400)
        z = bisect.bisect_left(ts, int(t["entry_t"]) + 86400)
        tr = {"entry_t": int(t["entry_t"]), "exit_t": int(lv["exit_t"]), "dir": int(t["dir"]), "entry": float(t["entry_px"]),
              "stop": float(t["stop_px"]), "target": float(t["target_px"]), "qty": int(lv["qty"]), "usd": float(lv["pnl"]),
              "exit_kind": t["exit"], "day": t["day"]}
        r = AD.score_trade("lit", tr, rows[a:z])
        if r is None:
            nf[half]["no_bars"] += 1
            continue
        recs.append(r)
        nf[half]["n"] += 1
        nf[half]["base_same"] += int(abs(r["base"]["pts"] - ((lv["pnl"] + COMM * lv["qty"]) / (PV * lv["qty"]))) <= 0.3)
        for x in r["advice"]:
            by[x["rule"]][half] += x["delta_usd"]
            nf[half][x["rule"] + "_fired"] += int(x["fired"])
    out = {"t": int(time.time()), "counts": {h: dict(v) for h, v in nf.items()}, "rules": {}}
    b = res.get("live")
    for rid, R in AD.RULES.items():
        o = res.get(R["research"])
        rs = {h: round(by[rid][h]) for h in ("H1", "H2")}
        rv = {h: (o["lit"][h]["net"] - b["lit"][h]["net"]) for h in ("H1", "H2")} if (o and b) else None
        out["rules"][rid] = {"advisor": rs, "research": rv, "variant": R["research"], "label": R["label"],
                             "tally": AD.tally([x for x in recs if x["day"] >= "2026"])[rid]["text"]}
        print(f"{rid:11s} advisor H1 {rs['H1']:+8,} H2 {rs['H2']:+8,} | research ({R['research']}) "
              + (f"H1 {rv['H1']:+8,} H2 {rv['H2']:+8,}" if rv else "-") + f" | fired H1 {nf['H1'][rid + '_fired']} H2 {nf['H2'][rid + '_fired']}")
    print("counts", out["counts"], f"{time.time() - t0:.0f} s")
    json.dump(out, open(out_path, "w"), indent=1)
    return out


def trend_split(out_path=os.path.join(ROOT, "research", "lit", "structure_trend_split.json")):
    """Descriptive (no rule): each strategy's trades split by the structure trend at the entry (with / against / mixed):
    LIT (LIT size, 1h), the ATLAS members (research trades at $500 risk, 15m + 1h), BLITZ (research trades, 5m). The numbers
    behind engine/structure.bias_for's notes."""
    import pandas as pd
    from tools import second_mix as M2
    ev = {tf: events(tf) for tf in ("5m", "15m", "1h")}

    def split(rows, tfs):
        S = collections.defaultdict(lambda: [0, 0.0, 0.0, 0])
        for r in rows:
            tr = [ST.trend_at(ev[tf], int(r["entry_t"])) for tf in tfs]
            g = "with" if all(x == r["dir"] for x in tr) else ("against" if all(x == -r["dir"] for x in tr) else "mixed")
            s = S[g]; s[0] += 1; s[1] += r["usd"]; s[2] += r["R"]; s[3] += int(r["usd"] > 0)
        return {g: {"n": v[0], "usd": round(v[1]), "usd_per": round(v[1] / v[0]), "R_per": round(v[2] / v[0], 2),
                    "win": round(100 * v[3] / v[0])} for g, v in S.items() if v[0]}
    out = {}
    L = lit_size(trades({}))
    for nm, f in (("2026", lambda d: d >= "2026"), ("2021_25", lambda d: d < "2026")):
        out[f"lit_1h_{nm}"] = split([{"entry_t": l["entry_t"], "dir": l["dir"], "usd": l["pnl"], "R": l["pts"] / l["risk"]}
                                     for l in L if f(l["day"])], ("1h",))
    U = M2.units()
    for nm, (a, z) in (("2026", ("2026-01-01", "2026-12-31")), ("2021_25", ("2021-01-01", "2025-12-31"))):
        out[f"atlas_15m1h_{nm}"] = split([{"entry_t": u["entry_t"], "dir": u["dir"], "usd": 500.0 * u["pts"] / u["risk"], "R": u["pts"] / u["risk"]}
                                          for src in ("EMA", "MD", "SR") for u in U[src] if a <= u["day"] <= z], ("15m", "1h"))
    B = json.load(open(os.path.join(ROOT, "research", "scalp", "na_best_trades.json")))["trades"]
    out["blitz_5m_2026"] = split([{"entry_t": int(pd.Timestamp(t["entry_t"], tz="America/New_York").timestamp()),
                                   "dir": 1 if t["dir"] == "long" else -1, "usd": 150.0 * float(t["r"]), "R": float(t["r"])} for t in B], ("5m",))
    json.dump(out, open(out_path, "w"), indent=1)
    for k, v in out.items():
        print(k, v)
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "advisor":
        advisor_check()
    elif cmd == "split":
        trend_split()
    if cmd == "check":
        check()
    elif cmd == "grid":
        grid(sys.argv[2:] or None)
    elif cmd == "report":
        report()
    elif cmd == "save":
        save(sys.argv[2:])
