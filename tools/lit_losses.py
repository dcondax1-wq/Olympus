"""LIT losses: anatomy of every lit_final losing trade in 2026, loss rules (skip / size / management), and timeframes.

Owner order 2026-10-18: a LIT strategy a real trader would trade, profitable AND consistent within 2026. Analyse where and why
the losses happen, turn the strongest patterns into rules, "think where I wouldn't think". Judged on 2026 only: every rule is
picked on 2026 H1 (Jan-Jun) and checked on 2026 H2 (Jul-Oct 16); 2021-25 is a reference line. Adopt only what helps both halves.

Wraps engine/lit.py (not edited): the executor below (sim2 / run2) is a copy of lit.simulate_x / lit._run_core (non-live) with
extra, default-off options; with none set it reproduces lit_final trade for trade (`check`).

  python tools/lit_losses.py check       # run2(lit_final) == tools/lit_final.run(lit_final)
  python tools/lit_losses.py anatomy     # every 2026 trade with its features -> research/lit/losses_anatomy.json
  python tools/lit_losses.py rules       # rule search (pick H1, check H2)   -> research/lit/losses_rules.json
  python tools/lit_losses.py tf          # timeframes (5m/15m setup, 1m/3m entry, 1H/4H bias, top-down, adaptive)
  python tools/lit_losses.py save        # store the adopt candidates as runs lit_loss_* (family other, tag lit)
  python tools/lit_losses.py live        # the adopted pack as engine options (live_model.json lit) -> run lit_live
1 CPU process.
"""
from __future__ import annotations

import bisect
import collections
import datetime as dt
import json
import math
import os
import pickle
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine.data import DATA_DIR, load, resample  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import runlib as rl  # noqa: E402

ET = ZoneInfo("America/New_York")
OUTD = os.path.join(ROOT, "research", "lit")
TICK, PV, COMM, SLIP = lit.TICK, lit.PV, lit.COMM, lit.SLIP
P0 = F.final_params()


# ================================================================================================ executor (copy + options)
def sim2(M, B, cand, entry_px, tgt, stop, P, X=None):
    """lit.simulate_x (live=False) plus default-off options in X:
      be_to   None | "idm" | float  at +be_r R move the stop to the inducement level (if below the entry) / to -x R, not to BE
      trail   (r, k)  after the trade has reached +r R, trail the stop 1 tick beyond each confirmed k-fractal of B (1m)
      part    (frac, px)  bank `frac` of the micros at direction-space price px (e.g. the swept box's opposite side)
    Confirmation window: cisd1m minutes -> round(cisd1m*60/B.secs) bars (= the engine's n on 1m and n//5 on 5m)."""
    X = X or {}
    d = cand["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    t0 = int(M.t[cand["entry_i"]])
    k0 = int(np.searchsorted(B.t, t0))
    s_day = int(M.day_of[cand["entry_i"]])
    if k0 >= B.n:
        return None
    flat = P["flat_mod"]
    wait_s = X.get("wait_secs") or P["wait"] * 300
    cis = P.get("cisd1m")
    if cis:
        cis = cis if B.secs == 60 else max(1, int(round(cis * 60 / B.secs)) if B.secs != 300 else cis // 5)
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
    q = lit.qty_for(risk)
    if q < 1:
        return None
    be_r = P["be_r"]
    be_to = X.get("be_to")
    trail = X.get("trail")
    part = X.get("part")
    qa, part_px, part_done = 0, None, False
    if part and q >= 2 and part[1] is not None and entry + 0.5 * risk <= part[1] < tg:
        qa = max(1, int(round(q * part[0]))); qa = min(qa, q - 1); part_px = part[1]
    cur, be_done, mfe, mae, worst = stop, False, 0.0, 0.0, 0.0
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
            if part_px is not None and not part_done and hi_d[k] >= part_px:
                part_done = True
            if hi_d[k] >= tg:
                exit_px, kind = tg, "TARGET"; break
            if be_r is not None and not be_done and hi_d[k] >= entry + be_r * risk:
                be_done = True
                if be_to is None:
                    cur = entry
                elif be_to == "idm":
                    ip = X.get("_idm_px")
                    cur = max(cur, ip - TICK) if (ip is not None and ip < entry) else entry
                else:
                    cur = max(cur, entry - float(be_to) * risk)
            if trail and mfe >= trail[0] and k - trail[1] * 2 >= fill:
                kk = trail[1]; j = k - kk
                if lo_d[j] < lo_d[j - kk:j].min() and lo_d[j] <= lo_d[j + 1:k + 1].min():
                    cur = max(cur, float(lo_d[j]) - TICK)
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        k += 1
    if exit_px is None:
        return None
    if part_done:
        pnl = (part_px - entry) * PV * qa + (exit_px - entry) * PV * (q - qa) - COMM * q
    else:
        pnl = (exit_px - entry) * PV * q - COMM * q
    low = min(0.0, worst * PV * q - COMM * q, pnl)
    xi5 = int(np.searchsorted(M.t, B.t[k], side="right") - 1)
    ei5 = int(np.searchsorted(M.t, B.t[fill], side="right") - 1)
    return {"day": cand["day"], "entry_t": int(B.t[fill]), "exit_t": int(B.t[k]) + B.secs, "exit_i": xi5, "dir": d,
            "r": round(pnl / (risk * PV * q), 3), "pnl": round(pnl, 2), "risk_pts": round(risk, 2), "qty": q,
            "risk_usd": round(risk * PV * q, 2), "half": False, "exit": kind, "trigger": "LIT-%dm" % (B.secs // 60),
            "mfe": round(float(mfe), 3), "mae": round(float(min(mae, 1.0 + SLIP / risk)), 3), "bars_held": int(k - fill + 1),
            "regime": "", "mult": 1.0, "low": round(float(low), 2), "entry_px": round(entry * d, 2), "stop_px": round(stop * d, 2),
            "target_px": round(tg * d, 2), "swept": cand["swept"], "ind_n": cand["ind_n"], "vec": cand["vec"], "i": cand["i"],
            "ext_i": cand["ext_i"], "ref_i": cand["ref_i"], "sweep_i": cand["sweep_i"], "entry_i": ei5, "tf": B.secs // 60,
            "limit_fill": limit_fill, "part_done": part_done, "fill_k": int(fill), "exit_k": int(k), "plan_rr": round((tg - entry) / risk, 2),
            "limit_px": round(entry_px * d, 2)}


def run2(M, cands, P=None, sessions=None, B1=None, B5=None, X=None):
    """lit._run_core (live=False) with hooks in X: skip(z) -> True drops the setup (the day stays free for a later one),
    bars(z, B1, B5) -> the executor bars (timeframe switch), part_of(z) -> (frac, px), plus sim2's options. Each trade
    carries its setup as t["_z"]."""
    X = X or {}
    P = {**lit.DEFAULTS, **(P or {})}
    names = set(P["sweep_names"]) if P.get("sweep_names") else None
    sset = set(sessions) if sessions else None
    out, busy, per_day = [], -1, collections.Counter()
    buf = P["stop_buf"]
    skip = X.get("skip")
    for z in cands:
        if sset is not None and z["day"] not in sset:
            continue
        if z["entry_i"] <= busy or per_day[z["day"]] >= P["max_per_day"]:
            continue
        if not lit.setup_ok(z, P, names):
            continue
        if skip is not None and skip(z):
            continue
        ep = min(float(z["ref_d"]), z["trig_c"])
        stop = z["ext_d"] - buf
        risk = ep - stop
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
        if X.get("tgt_fn"):
            tp = X["tgt_fn"](z, ep, risk, tp)
            if tp is None:
                continue
        if X.get("bars"):
            B = X["bars"](z, B1, B5)
        else:
            use1 = P["tf"] == "1m" and B1 is not None and int(M.day_of[z["entry_i"]]) in B1.full
            B = B1 if use1 else B5
        tgt = ("lvl", ep + tp, fb) if P.get("cisd1m") else ("pts", tp)
        XX = dict(X)
        if X.get("part_of"):
            XX["part"] = X["part_of"](z)
        if X.get("be_to") == "idm":
            XX["_idm_px"] = idm_px(M, z)
        t = sim2(M, B, z, ep, tgt, stop, P, XX)
        if t is None:
            continue
        busy = t["exit_i"]; per_day[z["day"]] += 1
        m = P["how_out"] if (P["how_out"] != 1.0 and not z["how"]) else 1.0
        if m != 1.0:
            t = lit.scale_trade(t, m)
        t["_z"] = z
        out.append(t)
    return out


def idm_px(M, z):
    """Direction-space price of the nearest qualifying inducement swing (the one closest to the swept level, within the
    final's idm_a gate), or None."""
    dm, age, _ = P0["idm_a"]
    lev = max(z["sw"].values()) if z.get("sw") else None
    if lev is None:
        return None
    q = [dd for dd, aa in z["idm_a"] if dd <= dm and aa <= age]
    if not q:
        return None
    return lev + max(q) * float(M.atr[z["sweep_i"]])


# ================================================================================================ data
_S = {}


def base():
    if "M" not in _S:
        M, C = F.market(P0["ref"], P0["extra_boxes"])
        _S.update(M=M, C=C, B1=F.bars(M, "1m"), B5=F.bars(M, "5m"))
    return _S["M"], _S["C"], _S["B1"], _S["B5"]


def run(X=None, P=None, cands=None):
    M, C, B1, B5 = base()
    return run2(M, cands if cands is not None else C, {**P0, **(P or {})}, F.SESS, B1=B1, B5=B5, X=X)


def check():
    M, C, B1, B5 = base()
    A = F.run(P0)
    Bt = run()
    ka = [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"]) for t in A]
    kb = [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"]) for t in Bt]
    print("lit_final via tools/lit_final:", len(A), round(sum(t["pnl"] for t in A if t["day"] >= "2026")),
          "| run2:", len(Bt), round(sum(t["pnl"] for t in Bt if t["day"] >= "2026")), "| identical:", ka == kb)
    return ka == kb


# ================================================================================================ features
def _ema(x, n):
    a = 2.0 / (n + 1); out = np.empty_like(x); out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = out[i - 1] + a * (x[i] - out[i - 1])
    return out


def context():
    """Everything the features need, computed once: ES aligned to the NQ 5m bars, 1H / 4H bars (EMA20, k=2 fractals),
    news calendar, per-day range / VIX move."""
    if "ctx" in _S:
        return _S["ctx"]
    M, C, B1, B5 = base()
    es = pd.read_csv(os.path.join(DATA_DIR, "ES_5m.csv")).drop_duplicates("time").set_index("time")
    al = es.reindex(M.t)
    ES = {"h": al["high"].values, "l": al["low"].values, "c": al["close"].values}
    H = {}
    for tf, secs in (("1h", 3600), ("4h", 14400)):
        b = resample(M.b, tf)
        ema = _ema(b.c, 20)
        fh, fl = lit.fractals(b.h, b.l)
        close_t = b.t + secs
        # last HTF bar closed by the close of 5m bar i
        last = np.searchsorted(close_t, M.t + 300, side="right") - 1
        H[tf] = {"b": b, "ema": ema, "fh": fh, "fl": fl, "last": last}
    ev = pd.read_csv(os.path.join(DATA_DIR, "news", "events.csv"))
    news = collections.defaultdict(list)
    for r in ev.itertuples():
        hh, mm = (int(x) for x in str(r.time_et).split(":")) if ":" in str(r.time_et) else (8, 30)
        news[r.date].append((hh * 60 + mm, r.event, r.impact))
    # weeks with CPI / FOMC
    wk = collections.defaultdict(set)
    for d, L in news.items():
        y, w, _ = dt.date.fromisoformat(d).isocalendar()
        for _m, e, _i in L:
            if "CPI" in e:
                wk[(y, w)].add("CPI")
            if "FOMC" in e:
                wk[(y, w)].add("FOMC")
            if "Non-Farm" in e or "NFP" in e:
                wk[(y, w)].add("NFP")
    day_rng = {}
    for k, (d, s, e) in enumerate(M.days):
        x = M.ctx[k]
        day_rng[k] = (float(M.h[s:e].max() - M.l[s:e].min()), x.get("vix_move"))
    _S["ctx"] = dict(ES=ES, H=H, news=news, wk=wk, day_rng=day_rng)
    return _S["ctx"]


def nearest_level(z):
    if not z.get("sw"):
        return None, None
    nm = max(z["sw"], key=lambda k: z["sw"][k])
    return nm, z["sw"][nm]


def level_group(nm):
    if nm is None:
        return "none"
    if nm.startswith("asia"):
        return "Asia box"
    if nm.startswith("lon"):
        return "London box"
    if nm.startswith("ny"):
        return "NY box"
    if nm.startswith("pre"):
        return "premarket box"
    if nm in ("pdh", "pdl"):
        return "prev day H/L"
    if nm in ("pwh", "pwl"):
        return "prev week H/L"
    if nm in ("pmh", "pml"):
        return "prev month H/L"
    if nm in ("nwog", "ndog"):
        return "opening gap"
    if nm.startswith("bu_"):
        return "equal highs/lows"
    return nm


def feat(z):
    """Setup features known at the trigger bar close (usable as rules)."""
    M, C, B1, B5 = base()
    X = context()
    i, ee, sb, d, k = z["i"], z["ext_i"], z["sweep_i"], z["dir"], z["k"]
    x = M.ctx[k]; s = x["s"]
    hi_d, lo_d, c_d = (M.h, M.l, M.c) if d == 1 else (-M.l, -M.h, -M.c)
    f = {}
    f["mod"] = z["mod"]
    f["hour"] = z["mod"] // 60
    f["since_lon"] = z["mod"] - 180
    f["dow"] = z["dow"]
    nm, lev = nearest_level(z)
    f["level"] = nm; f["level_grp"] = level_group(nm)
    f["n_swept"] = len(z["swept"])
    f["swept_cls"] = "+".join(z["swept_cls"])
    f["depth"] = z["depth_atr"]
    q = [(dd, aa) for dd, aa in z["idm_a"] if dd <= P0["idm_a"][0] and aa <= P0["idm_a"][1]]
    f["idm_n"] = len(q)
    f["idm_age"] = min(aa for dd, aa in q) if q else None
    f["idm_dist"] = min(dd for dd, aa in q) if q else None
    f["disp"] = z["disp"]
    f["leg_bars"] = z["bars"]
    ep = min(float(z["ref_d"]), z["trig_c"])
    f["stop_plan"] = round(ep - (z["ext_d"] - P0["stop_buf"]), 2)
    f["atr"] = round(float(M.atr[i]), 2)
    vm = x.get("vix_move")
    f["vix"] = x.get("vix")
    f["vix_move"] = round(vm, 1) if vm else None
    rng = float(M.h[s:i + 1].max() - M.l[s:i + 1].min())
    f["rng_used"] = round(rng / vm, 3) if vm else None            # range so far / VIX one-day move
    f["ext_vs_open"] = z["vix_ext"]                                # (18:00 open - extreme) / VIX move (direction space)
    op = x["open18"] * d
    f["pd18"] = round((ep - op) / vm, 3) if vm else None          # entry vs 18:00 open in VIX moves (<0 = discount)
    o00 = M.open_00[i]
    f["pd00"] = None if np.isnan(o00) else round((ep - o00 * d) / max(M.atr[i], 1e-9), 2)   # vs midnight open, ATR
    f["room_r"] = round((op + vm - ep) / max(f["stop_plan"], 1e-9), 2) if vm else None        # VIX band distance in R
    # day so far: was the other side (target side) already extended?  up_used = (day high so far - open) / move
    if vm:
        f["fav_used"] = round((hi_d[s:i + 1].max() - op) / vm, 3)        # how far the trade's side already ran today
        f["adv_used"] = round((op - lo_d[s:i + 1].min()) / vm, 3)        # how far against (the sweep side)
    # ES SMT at the sweep: did ES also break its own prior 3h low when NQ did?
    a0, a1 = max(s - 600, ee - 36), ee - 3
    ES = X["ES"]
    if a1 > a0 and not np.isnan(ES["l"][a0:ee + 3]).all():
        esl = ES["l"] if d == 1 else -ES["h"]
        esl = esl if d == 1 else esl
        e_lo_d = (ES["l"] if d == 1 else -ES["h"])
        prior_nq = lo_d[a0:a1].min(); prior_es = np.nanmin(e_lo_d[a0:a1])
        nq_ll = lo_d[ee] < prior_nq
        es_ll = np.nanmin(e_lo_d[ee - 2:min(ee + 3, i + 1)]) < prior_es
        f["smt"] = "na" if not nq_ll else ("both swept" if es_ll else "ES held (SMT)")
        ec = ES["c"] if d == 1 else -ES["c"]
        if not (np.isnan(ec[ee]) or np.isnan(ec[i])):
            f["es_leg"] = round(float((ec[i] - ec[ee]) / abs(ec[ee]) / max((c_d[i] - lo_d[ee]) / abs(lo_d[ee]), 1e-9)), 2)
    # HTF trend / bias
    for tf in ("1h", "4h"):
        h = X["H"][tf]; j = int(h["last"][i])
        if j < 25:
            continue
        cl = h["b"].c[j] * d; em = h["ema"][j] * d
        f[f"trend_{tf}"] = 1 if cl > em else -1                         # +1 = with the trade
        f[f"candle_{tf}"] = 1 if (h["b"].c[j] - h["b"].o[j]) * d > 0 else -1
        f[f"slope_{tf}"] = 1 if (h["ema"][j] - h["ema"][j - 3]) * d > 0 else -1
    # 1H draw: nearest unswept 1H fractal high above vs low below (direction space)
    h = X["H"]["1h"]; j = int(h["last"][i]); b = h["b"]
    if j > 30:
        px = c_d[i]
        up = dn = None
        hh, ll = (b.h, b.l) if d == 1 else (-b.l, -b.h)
        fu, fdn = (h["fh"], h["fl"]) if d == 1 else (h["fl"], h["fh"])
        for jj in fu[(fu >= j - 120) & (fu <= j - 2)][::-1]:
            lvl = hh[jj]
            if lvl > px and hh[jj + 1:j + 1].max() < lvl:
                dd_ = lvl - px; up = dd_ if up is None else min(up, dd_)
        for jj in fdn[(fdn >= j - 120) & (fdn <= j - 2)][::-1]:
            lvl = ll[jj]
            if lvl < px and ll[jj + 1:j + 1].min() > lvl:
                dd_ = px - lvl; dn = dd_ if dn is None else min(dn, dd_)
        f["draw_1h"] = "with" if (up is not None and (dn is None or up < dn)) else ("against" if dn is not None else "none")
    # news
    nd = X["news"].get(z["day"], [])
    hi_ev = [(m, e) for m, e, im in nd if im == "high"]
    f["news_day"] = bool(hi_ev)
    f["news_after"] = any(m > z["mod"] and m - z["mod"] <= 180 for m, e in hi_ev)   # high-impact release within 3h after entry
    y, w, _ = dt.date.fromisoformat(z["day"]).isocalendar()
    f["cpi_wk"] = "CPI" in X["wk"].get((y, w), set()); f["fomc_wk"] = "FOMC" in X["wk"].get((y, w), set())
    # previous day: range vs its VIX move
    if k > 0:
        r0, v0 = X["day_rng"][k - 1]
        f["prev_rng"] = round(r0 / v0, 2) if v0 else None
    # VIX change into today
    if k > 0 and M.ctx[k - 1].get("vix") and x.get("vix"):
        f["vix_chg"] = round(x["vix"] - M.ctx[k - 1]["vix"], 2)
    # earlier setups today in the same direction (a second sweep)
    f["prior_same"] = sum(1 for zz in _cands_day(z["day"]) if zz["dir"] == d and zz["i"] < i)
    f["prior_opp"] = sum(1 for zz in _cands_day(z["day"]) if zz["dir"] != d and zz["i"] < i)
    f["climax_sweep"] = z["vec_sweep"]; f["vec"] = z["vec"]
    f["how"] = z["how"]
    f["first_wk"] = bool(x.get("first_of_week"))
    f["nwog_side"] = z["nwog_side"]
    return f


def _cands_day(day):
    if "cbd" not in _S:
        M, C, B1, B5 = base()
        g = collections.defaultdict(list)
        for z in C:
            if lit.setup_ok(z, P0):
                g[z["day"]].append(z)
        _S["cbd"] = g
    return _S["cbd"][day]


def outcome(t):
    """Hindsight facts of a finished trade (not usable as rules)."""
    M, C, B1, B5 = base()
    z = t["_z"]; d = z["dir"]; k = z["k"]; x = M.ctx[k]; s, e = x["s"], x["e"]
    lo_d = M.l if d == 1 else -M.h
    hi_d = M.h if d == 1 else -M.l
    o = {"exit": t["exit"], "r": t["r"], "pnl": t["pnl"], "mfe": t["mfe"], "mae": t["mae"],
         "mins": round((t["exit_t"] - t["entry_t"]) / 60), "plan_rr": t.get("plan_rr"), "qty": t["qty"], "risk": t["risk_pts"],
         "fill_vs_limit_r": round((t["entry_px"] - t["limit_px"]) * d / t["risk_pts"], 3), "limit_fill": t.get("limit_fill")}
    ei = t["entry_i"]
    o["low_held"] = bool(lo_d[ei:e].min() > lo_d[s:ei + 1].min() - 1e-9) or bool(np.argmin(lo_d[s:e]) + s <= z["ext_i"])
    o["day_ext_is_sweep"] = bool(int(np.argmin(lo_d[s:e])) + s == z["ext_i"])
    o["fav_made_before"] = bool(int(np.argmax(hi_d[s:e])) + s < ei)    # the day's high (long) was already in before entry
    et = dt.datetime.fromtimestamp(t["entry_t"], ET)
    o["entry_et"] = et.strftime("%Y-%m-%d %H:%M")
    return o


# ================================================================================================ anatomy
def _st(T):
    p = np.array([t["pnl"] for t in T]) if T else np.zeros(0)
    gl = -p[p < 0].sum()
    h1 = sum(t["pnl"] for t in T if t["day"] <= "2026-06-30"); h2 = sum(t["pnl"] for t in T if t["day"] >= "2026-07-01")
    return {"n": len(T), "win": round(100 * float((p > 0).mean()), 1) if len(p) else None,
            "stop": round(100 * sum(t["exit"] == "STOP" for t in T) / len(T), 1) if T else None,
            "net": round(float(p.sum())), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
            "avg": round(float(p.mean())) if len(p) else None, "h1": round(h1), "h2": round(h2),
            "n1": sum(t["day"] <= "2026-06-30" for t in T), "n2": sum(t["day"] >= "2026-07-01" for t in T)}


NUM = ["mod", "since_lon", "depth", "idm_age", "idm_dist", "disp", "leg_bars", "stop_plan", "atr", "vix", "vix_move", "rng_used",
       "ext_vs_open", "pd18", "pd00", "room_r", "fav_used", "adv_used", "es_leg", "prev_rng", "vix_chg", "prior_same", "prior_opp",
       "n_swept", "idm_n"]
CAT = ["hour", "dow", "level_grp", "swept_cls", "smt", "trend_1h", "trend_4h", "candle_1h", "candle_4h", "slope_1h", "slope_4h",
       "draw_1h", "news_day", "news_after", "cpi_wk", "fomc_wk", "climax_sweep", "vec", "how", "first_wk", "nwog_side", "dir",
       "streak_before", "prev_trade"]
HIND = ["mfe", "mins", "plan_rr", "qty", "risk", "fill_vs_limit_r", "low_held", "day_ext_is_sweep", "fav_made_before"]


def table(T, rows):
    """rows: list of (feature, values per trade). Numeric -> terciles (2026 edges); categorical -> per value."""
    out = {}
    for nm, vals, kind in rows:
        pairs = [(v, t) for v, t in zip(vals, T) if v is not None and not (isinstance(v, float) and math.isnan(v))]
        if not pairs:
            continue
        g = {}
        if kind == "num":
            xs = np.array([float(v) for v, _ in pairs])
            e1, e2 = np.quantile(xs, [1 / 3, 2 / 3])
            for lab, fn in ((f"low (<= {e1:.3g})", lambda v: v <= e1), (f"mid", lambda v: e1 < v <= e2), (f"high (> {e2:.3g})", lambda v: v > e2)):
                g[lab] = _st([t for v, t in pairs if fn(float(v))])
            w = [float(v) for v, t in pairs if t["pnl"] > 0]; s = [float(v) for v, t in pairs if t["exit"] == "STOP"]
            b = [float(v) for v, t in pairs if t["exit"] == "BE"]
            g["_median"] = {"winners": round(float(np.median(w)), 3) if w else None, "stops": round(float(np.median(s)), 3) if s else None,
                            "breakevens": round(float(np.median(b)), 3) if b else None}
        else:
            for v in sorted({str(v) for v, _ in pairs}):
                g[v] = _st([t for vv, t in pairs if str(vv) == v])
        out[nm] = g
    return out


def annotate(T):
    """feat + outcome + sequence facts on each trade (in place), 2026 and earlier alike."""
    T = sorted(T, key=lambda t: t["entry_t"])
    streak = 0; prev = None
    for t in T:
        f = feat(t["_z"]); f["dir"] = t["dir"]
        f["streak_before"] = "0" if streak == 0 else "1-2" if streak <= 2 else "3-5" if streak <= 5 else "6+"
        f["streak_n"] = streak
        f["prev_trade"] = "none" if prev is None else ("win" if prev["pnl"] > 0 else prev["exit"].lower())
        t["_f"] = f
        streak = 0 if t["pnl"] > 0 else streak + 1
        prev = t
    for t in T:
        if t["day"] >= "2026":
            t["_o"] = outcome(t)
    return T


def anatomy():
    T = annotate(run())
    T26 = [t for t in T if t["day"] >= "2026"]
    rows = [(nm, [t["_f"].get(nm) for t in T26], "num") for nm in NUM] + [(nm, [t["_f"].get(nm) for t in T26], "cat") for nm in CAT]
    hrows = [(nm, [t["_o"].get(nm) for t in T26], "num" if nm in ("mfe", "mins", "plan_rr", "qty", "risk", "fill_vs_limit_r") else "cat")
             for nm in HIND]
    rep = {"all": _st(T26), "by_exit": {k: _st([t for t in T26 if t["exit"] == k]) for k in ("TARGET", "EOD", "BE", "STOP")},
           "setup": table(T26, rows), "hindsight": table(T26, hrows)}
    # losers in detail
    L = [t for t in T26 if t["pnl"] <= 0]
    rep["stops_mfe"] = {"median": float(np.median([t["mfe"] for t in T26 if t["exit"] == "STOP"])),
                        "share_mfe_ge_0.5": round(100 * np.mean([t["mfe"] >= 0.5 for t in T26 if t["exit"] == "STOP"]), 1),
                        "median_mins": float(np.median([t["_o"]["mins"] for t in T26 if t["exit"] == "STOP"])),
                        "share_within_15min": round(100 * np.mean([t["_o"]["mins"] <= 15 for t in T26 if t["exit"] == "STOP"]), 1)}
    rep["be_mfe_median"] = float(np.median([t["mfe"] for t in T26 if t["exit"] == "BE"]))
    rep["loss_dollars"] = {"stops": round(sum(t["pnl"] for t in T26 if t["exit"] == "STOP")), "be": round(sum(t["pnl"] for t in T26 if t["exit"] == "BE")),
                           "eod_neg": round(sum(t["pnl"] for t in T26 if t["exit"] == "EOD" and t["pnl"] <= 0))}
    keep = ["day", "dir", "exit", "r", "pnl", "risk_pts", "qty", "mfe", "plan_rr"]
    rep["trades"] = [{**{k: t[k] for k in keep}, **{k: _j(v) for k, v in t["_f"].items()}, **{"o_" + k: _j(v) for k, v in t["_o"].items()}}
                     for t in T26]
    json.dump(rep, open(os.path.join(OUTD, "losses_anatomy.json"), "w"), indent=1, default=_j)
    _print_anatomy(rep)
    return rep


def _j(v):
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, np.bool_):
        return bool(v)
    return v


def _print_anatomy(rep):
    print("ALL 2026", rep["all"]); print("by exit", rep["by_exit"]); print("stops", rep["stops_mfe"], "BE mfe", rep["be_mfe_median"], rep["loss_dollars"])
    for sec in ("setup", "hindsight"):
        for nm, g in rep[sec].items():
            print(f"--- {nm}  {g.get('_median', '')}")
            for lab, s in g.items():
                if lab == "_median":
                    continue
                print(f"   {lab:28s} n={s['n']:3d} ({s['n1']}/{s['n2']}) win={s['win']} stop%={s['stop']} net={s['net']:+7,} PF={s['pf']} H1={s['h1']:+7,} H2={s['h2']:+7,}")


# ================================================================================================ rules (pick on H1, check on H2)
_FC = {}


def fz(z):
    key = (z["day"], z["i"], z["dir"])
    if key not in _FC:
        _FC[key] = feat(z)
    return _FC[key]


def fast(T):
    """H1 / H2 / 2026 / 2021-25 quick lines (n, trades/wk, PF, net, DD, net without the 3 best)."""
    o = F.score(T, fast=True)
    for nm in o:
        a, z = F.SPAN[nm]
        pn = sorted((t["pnl"] for t in T if a <= t["day"] <= z), reverse=True)
        o[nm]["x3"] = round(sum(pn[3:]))
        p = np.array(pn or [0.0]); o[nm]["win"] = round(100 * float((p > 0).mean()), 1)
    return o


def scaled(T, mult):
    """mult(t) -> size multiplier (exact re-size, floor 1 micro); 0 = not traded (only for rules that can't free the day)."""
    out = []
    for t in T:
        m = mult(t)
        if m == 1.0:
            out.append(t)
        elif m > 0:
            out.append({**lit.scale_trade(t, m), "_z": t["_z"]})
    return out


def with_f(T):
    for t in T:
        t["_f"] = fz(t["_z"])
    return T


def seq_mults(T, fn):
    """fn(history of finished trades, this trade) -> multiplier; history = trades exited before this entry."""
    T = sorted(T, key=lambda t: t["entry_t"])
    out = []
    for t in T:
        hist = [x for x in T if x["exit_t"] <= t["entry_t"]]
        m = fn(hist, t)
        out.append(t if m == 1.0 else {**lit.scale_trade(t, m), "_z": t["_z"]})
    return out


_BASE = {}


def base_trades():
    if "T" not in _BASE:
        _BASE["T"] = with_f(run())
    return _BASE["T"]


def box_opp(z):
    """Direction-space price of the opposite side of the nearest swept session box (long swept asia20_l -> asia20 high),
    or for PDL / PWL / PML the PDH / PWH / PMH."""
    M, C, B1, B5 = base()
    x = M.ctx[z["k"]]; d = z["dir"]
    best = None
    for nm in z["swept"]:
        root = nm[:-2] if nm.endswith(("_h", "_l")) else nm
        if root in x and isinstance(x[root], tuple):
            hi, lo, _ki = x[root]
            p = hi if d == 1 else -lo
        elif nm in ("pdl", "pdh", "pwl", "pwh", "pml", "pmh"):
            opp = nm[:2] + ("h" if d == 1 else "l")
            if opp not in x:
                continue
            p = x[opp] * d
        else:
            continue
        best = p if best is None else min(best, p)
    return best


def variants():
    """name -> (family, builder). builder() -> trades. Families: skip (setup dropped, the day stays free), size (multiplier),
    seq (size from the trade history), mgmt (exit management), param (a lit_final setting)."""
    V = collections.OrderedDict()
    sk = lambda pred: (lambda: with_f(run({"skip": lambda z: pred(fz(z), z)})))
    sz = lambda mult: (lambda: scaled(base_trades(), lambda t: mult(t["_f"], t)))
    # 1. stop size (wide stop = small size, and those lose)
    for x in (40, 45, 50, 55, 60):
        V[f"stop: skip planned stop > {x}"] = ("skip", sk(lambda f, z, x=x: f["stop_plan"] > x))
        V[f"stop: half size if stop > {x}"] = ("size", sz(lambda f, t, x=x: 0.5 if t["risk_pts"] > x else 1.0))
    # 2. inducement age / distance
    for a in (8, 12, 18, 24, 30):
        V[f"inducement age <= {a} bars"] = ("param", (lambda a=a: with_f(run(P={"idm_a": [1.0, a, 1]}))))
    for a in (8, 12, 18):
        V[f"half size if inducement older than {a} bars"] = ("size", sz(lambda f, t, a=a: 0.5 if (f["idm_age"] or 99) > a else 1.0))
    # 3. ES agreement (SMT)
    V["ES: skip when ES did not also sweep"] = ("skip", sk(lambda f, z: f.get("smt") in ("ES held (SMT)", "na")))
    V["ES: half when ES did not also sweep"] = ("size", sz(lambda f, t: 0.5 if f.get("smt") in ("ES held (SMT)", "na") else 1.0))
    V["ES: skip true SMT (ES held)"] = ("skip", sk(lambda f, z: f.get("smt") == "ES held (SMT)"))
    V["ES: 1.5x when ES also swept"] = ("size", sz(lambda f, t: 1.5 if f.get("smt") == "both swept" else 1.0))
    V["ES: 2x when ES also swept"] = ("size", sz(lambda f, t: 2.0 if f.get("smt") == "both swept" else 1.0))
    # 4. calendar / news
    V["CPI week: half size"] = ("size", sz(lambda f, t: 0.5 if f["cpi_wk"] else 1.0))
    V["CPI week: skip"] = ("skip", sk(lambda f, z: f["cpi_wk"]))
    V["FOMC week: half size"] = ("size", sz(lambda f, t: 0.5 if f["fomc_wk"] else 1.0))
    V["CPI or FOMC week: half size"] = ("size", sz(lambda f, t: 0.5 if (f["cpi_wk"] or f["fomc_wk"]) else 1.0))
    V["news day: half size"] = ("size", sz(lambda f, t: 0.5 if f["news_day"] else 1.0))
    V["Monday: half size"] = ("size", sz(lambda f, t: 0.5 if f["dow"] == 0 else 1.0))
    V["Friday: half size"] = ("size", sz(lambda f, t: 0.5 if f["dow"] == 4 else 1.0))
    V["Monday + Friday: half size"] = ("size", sz(lambda f, t: 0.5 if f["dow"] in (0, 4) else 1.0))
    V["Monday: skip"] = ("skip", sk(lambda f, z: f["dow"] == 0))
    # 5. time since the London open (03:00 ET)
    for m in (300, 360, 420):
        V[f"time: no entry {m // 60:02d}:00-08:00"] = ("skip", sk(lambda f, z, m=m: m <= f["mod"] < 480))
    V["time: half size 05:00-06:00"] = ("size", sz(lambda f, t: 0.5 if 300 <= f["mod"] < 360 else 1.0))
    V["time: half size after 07:00"] = ("size", sz(lambda f, t: 0.5 if f["mod"] >= 420 else 1.0))
    # 6. exhaustion: range already used vs the VIX move; trade side already ran
    for x in (0.8, 1.0, 1.2):
        V[f"exhaustion: skip if range so far > {x} VIX moves"] = ("skip", sk(lambda f, z, x=x: (f["rng_used"] or 0) > x))
    for x in (0.4, 0.6):
        V[f"exhaustion: skip if the trade side already ran > {x} moves"] = ("skip", sk(lambda f, z, x=x: (f.get("fav_used") or 0) > x))
    # 7. premium / discount vs the 18:00 and midnight opens
    V["premium: skip long above / short below the 18:00 open"] = ("skip", sk(lambda f, z: (f["pd18"] or 0) > 0))
    V["premium: half size above 18:00 open"] = ("size", sz(lambda f, t: 0.5 if (f["pd18"] or 0) > 0 else 1.0))
    V["premium: skip long above / short below the midnight open"] = ("skip", sk(lambda f, z: f["pd00"] is not None and f["pd00"] > 0))
    # 8. displacement / sweep candle
    for x in (1.3, 1.5):
        V[f"displacement: skip body > {x} ATR"] = ("skip", sk(lambda f, z, x=x: f["disp"] > x))
    V["climax sweep candle: half size"] = ("size", sz(lambda f, t: 0.5 if f["climax_sweep"] else 1.0))
    V["leg <= 2 bars (V-turn): half size"] = ("size", sz(lambda f, t: 0.5 if f["leg_bars"] <= 2 else 1.0))
    # 9. HTF trend / draw
    V["4H candle with the trade: half size"] = ("size", sz(lambda f, t: 0.5 if f.get("candle_4h") == 1 else 1.0))
    V["4H trend (EMA20) against: half size"] = ("size", sz(lambda f, t: 0.5 if f.get("trend_4h") == -1 else 1.0))
    V["1H trend (EMA20) against: half size"] = ("size", sz(lambda f, t: 0.5 if f.get("trend_1h") == -1 else 1.0))
    V["1H draw against: half size"] = ("size", sz(lambda f, t: 0.5 if f.get("draw_1h") == "against" else 1.0))
    V["1H draw against: skip"] = ("skip", sk(lambda f, z: f.get("draw_1h") == "against"))
    # 10. day after a big day, VIX falling
    for x in (1.6, 2.0):
        V[f"day after a big day (range > {x} VIX moves): half"] = ("size", sz(lambda f, t, x=x: 0.5 if (f.get("prev_rng") or 0) > x else 1.0))
    V["VIX fell into today (> 0.4): half"] = ("size", sz(lambda f, t: 0.5 if (f.get("vix_chg") or 0) < -0.4 else 1.0))
    # 11. second sweep of the same side today
    V["second setup same side today: skip"] = ("skip", sk(lambda f, z: f["prior_same"] > 0))
    V["first setup of the day only (any side): skip later"] = ("skip", sk(lambda f, z: f["prior_same"] + f["prior_opp"] > 0))
    # 12. sequence rules (size from the trade history)
    V["after a stop-out: half size until the next winner"] = ("seq", lambda: seq_mults(base_trades(), lambda H, t: 0.5 if _since_win(H) else 1.0))
    V["half size until the first winner of the week"] = ("seq", lambda: seq_mults(base_trades(), _week_first_win))
    for n in (2, 3, 5):
        V[f"after {n}+ non-winners in a row: half size"] = ("seq", lambda n=n: seq_mults(base_trades(), lambda H, t, n=n: 0.5 if _streak(H) >= n else 1.0))
    V["after a winner: 1.5x the next trade"] = ("seq", lambda: seq_mults(base_trades(), lambda H, t: 1.5 if (H and H[-1]["pnl"] > 0) else 1.0))
    V["weekly stop: half size after 2 stop-outs in the week"] = ("seq", lambda: seq_mults(base_trades(), _week_stops))
    V["eval: half size after the account is down $1,000 from its peak"] = ("seq", lambda: seq_mults(base_trades(), _dd_half))
    # 13. management
    V["scale out 50% at the swept box's opposite side"] = ("mgmt", lambda: with_f(run({"part_of": lambda z: (0.5, box_opp(z))})))
    for r in (2.0, 3.0):
        V[f"scale out 50% at {r:.0f}R"] = ("mgmt", lambda r=r: with_f(run({"part_of": lambda z, r=r: (0.5, _r_px(z, r))})))
    for r, k in ((3.0, 2), (3.0, 3), (2.0, 3), (4.0, 3)):
        V[f"trail behind 1m swings (k={k}) after {r:.0f}R"] = ("mgmt", lambda r=r, k=k: with_f(run({"trail": (r, k)})))
    V["at +1R stop to the inducement (not to BE)"] = ("mgmt", lambda: with_f(run({"be_to": "idm"})))
    V["at +1R stop to -0.5R (not to BE)"] = ("mgmt", lambda: with_f(run({"be_to": 0.5})))
    V["breakeven at 2R instead of 1R"] = ("param", lambda: with_f(run(P={"be_r": 2.0})))
    return V


def _r_px(z, r):
    """Marker for 'r R from the real fill' (resolved inside sim2 via the planned limit: limit + r * planned risk)."""
    ep = min(float(z["ref_d"]), z["trig_c"]); risk = ep - (z["ext_d"] - P0["stop_buf"])
    return ep + r * risk


def _since_win(H):
    """A stop-out since the last winner."""
    for x in reversed(H):
        if x["pnl"] > 0:
            return False
        if x["exit"] == "STOP":
            return True
    return False


def _streak(H):
    n = 0
    for x in reversed(H):
        if x["pnl"] > 0:
            break
        n += 1
    return n


def _week_first_win(H, t):
    wk = dt.date.fromisoformat(t["day"]).isocalendar()[:2]
    won = any(dt.date.fromisoformat(x["day"]).isocalendar()[:2] == wk and x["pnl"] > 0 for x in H)
    return 1.0 if won else 0.5


def _week_stops(H, t):
    wk = dt.date.fromisoformat(t["day"]).isocalendar()[:2]
    n = sum(1 for x in H if dt.date.fromisoformat(x["day"]).isocalendar()[:2] == wk and x["exit"] == "STOP")
    return 0.5 if n >= 2 else 1.0


def _dd_half(H, t):
    eq = np.cumsum([x["pnl"] for x in H]) if H else np.zeros(1)
    pk = max(0.0, float(eq.max())) if len(eq) else 0.0
    return 0.5 if (len(eq) and pk - float(eq[-1]) >= 1000) else 1.0


def rules(only=None):
    T0 = base_trades()
    base = fast(T0)
    print("BASE", _fl(base), flush=True)
    res = collections.OrderedDict()
    for nm, (fam, fn) in variants().items():
        if only and only not in nm:
            continue
        T = fn()
        o = fast(T)
        d1 = o["H1"]["net"] - base["H1"]["net"]; d2 = o["H2"]["net"] - base["H2"]["net"]
        res[nm] = {"family": fam, **o, "dH1": d1, "dH2": d2}
        print(f"{nm:62s} dH1={d1:+7,} dH2={d2:+7,} | {_fl(o)}", flush=True)
    json.dump({"base": base, "variants": res}, open(os.path.join(OUTD, "losses_rules.json" if not only else "losses_rules_part.json"), "w"), indent=1, default=_j)
    return base, res


def _fl(o):
    return " ".join(f"{k}[n={v['n']} {v['tpw']}/wk PF={v['pf']} net={v['net']:+,} x3={v['x3']:+,} DD={v['dd']:,}]" for k, v in o.items())


# ================================================================================================ timeframes
def bars_nm(B1, secs):
    """n-minute executor bars (3m) built from the cleaned true-1m bars; same day index / full-coverage set."""
    bk = B1.t // secs * secs
    key = bk * 10000 + (B1.day + 1)
    first = np.r_[True, key[1:] != key[:-1]]
    st = np.flatnonzero(first); en = np.r_[st[1:], B1.n]
    o = B1.o[st]; c = B1.c[en - 1]
    h = np.maximum.reduceat(B1.h, st); l = np.minimum.reduceat(B1.l, st)
    t = bk[st]
    mod = B1.mod[st] - (B1.t[st] - t) // 60
    return lit.XBars(t, o, h, l, c, mod, B1.day[st], secs, B1.full)


def remap(B, M_from, M_to):
    dmap = {d: k for k, (d, s, e) in enumerate(M_to.days)}
    tr = np.array([dmap.get(M_from.days[k][0], -1) for k in range(len(M_from.days))] + [-1])
    day = tr[np.asarray(B.day)]       # -1 -> the appended -1
    full = {int(tr[k]) for k in (B.full or ()) if tr[k] >= 0}
    return lit.XBars(B.t, B.o, B.h, B.l, B.c, B.mod, day, B.secs, full if B.full is not None else None)


def market15():
    if "M15" not in _S:
        M, C, B1, B5 = base()
        b15 = resample(load("NQ", "5m"), "15m")
        p = os.path.join(F.CACHE, f"litloss_m15_cands_{rl._data_key().replace(':', '_')}.pkl")
        M15 = lit.Market(bars=b15)
        if os.path.exists(p):
            C15 = pickle.load(open(p, "rb"))
        else:
            C15 = lit.candidates(M15, leg=8, sweep_win=8, ref_back=12, ind_back=12, ref="cisd")
            pickle.dump(C15, open(p, "wb"))
        _S.update(M15=M15, C15=C15, B1_15=remap(B1, M, M15), B5_15=remap(B5, M, M15))
        _S["B3_15"] = bars_nm(_S["B1_15"], 180)
    return _S["M15"], _S["C15"], _S["B1_15"], _S["B5_15"], _S["B3_15"]


def b3():
    if "B3" not in _S:
        M, C, B1, B5 = base()
        _S["B3"] = bars_nm(B1, 180)
    return _S["B3"]


def run_tf(setup="5m", entry="1m", skip=None, P=None, X=None, sessions=None, entry_fn=None):
    """setup 5m | 15m (detector on that timeframe; leg / sweep window / inducement age scaled to the same clock time);
    entry 1m | 3m | 5m (executor bars on days with full 1m coverage); entry_fn(z) -> "1m"/"3m" = adaptive switch."""
    X = dict(X or {})
    if setup == "5m":
        M, C, B1, B5 = base(); B3 = b3() if (entry == "3m" or entry_fn) else None
        PP = {**P0, **(P or {})}
    else:
        M, C, B1, B5, B3 = market15()
        PP = {**P0, "idm_a": [1.0, 12, 1], **(P or {})}
        X.setdefault("wait_secs", PP["wait"] * 300)
    pick = {"1m": B1, "3m": B3, "5m": None}

    def bars(z, _B1, _B5):
        e = entry_fn(z) if entry_fn else entry
        if e == "5m" or int(M.day_of[z["entry_i"]]) not in B1.full:
            return B5
        return pick[e]
    X["bars"] = bars
    if skip:
        X["skip"] = skip
    return run2(M, C, PP, sessions or F.SESS, B1=B1, B5=B5, X=X)


def htf_draw(M, z, tf):
    """Draw on liquidity from 1H / 4H: +1 if the nearest unswept HTF swing is on the trade's side (target side)."""
    X = context()
    h = X["H"][tf]; i = z["i"]; d = z["dir"]
    j = int(np.searchsorted(h["b"].t + (3600 if tf == "1h" else 14400), M.t[i] + M.b.secs, side="right") - 1)
    b = h["b"]
    if j < 30:
        return 0
    hh, ll = (b.h, b.l) if d == 1 else (-b.l, -b.h)
    fu, fdn = (h["fh"], h["fl"]) if d == 1 else (h["fl"], h["fh"])
    px = (M.c[i]) * d
    up = dn = None
    lim = 120 if tf == "1h" else 60
    for jj in fu[(fu >= j - lim) & (fu <= j - 2)]:
        if hh[jj] > px and hh[jj + 1:j + 1].max() < hh[jj]:
            up = hh[jj] - px if up is None else min(up, hh[jj] - px)
    for jj in fdn[(fdn >= j - lim) & (fdn <= j - 2)]:
        if ll[jj] < px and ll[jj + 1:j + 1].min() > ll[jj]:
            dn = px - ll[jj] if dn is None else min(dn, px - ll[jj])
    if up is None and dn is None:
        return 0
    return 1 if (up is not None and (dn is None or up < dn)) else -1


def htf_bias(M, z, tf):
    """+1 if the last closed 1H / 4H candle closed in the trade's direction, -1 against."""
    X = context(); h = X["H"][tf]; i = z["i"]
    secs = 3600 if tf == "1h" else 14400
    j = int(np.searchsorted(h["b"].t + secs, M.t[i] + M.b.secs, side="right") - 1)
    if j < 1:
        return 0
    return 1 if (h["b"].c[j] - h["b"].o[j]) * z["dir"] > 0 else -1


def tf_variants():
    V = collections.OrderedDict()
    V["setup 5m / entry 1m (= lit_final)"] = lambda: run_tf("5m", "1m")
    V["setup 5m / entry 3m"] = lambda: run_tf("5m", "3m")
    V["setup 5m / entry 5m"] = lambda: run_tf("5m", "5m")
    V["setup 15m / entry 1m"] = lambda: run_tf("15m", "1m")
    V["setup 15m / entry 3m"] = lambda: run_tf("15m", "3m")
    V["setup 15m / entry 1m, limit valid 60 min"] = lambda: run_tf("15m", "1m", X={"wait_secs": 3600})
    V["setup 15m / entry 5m"] = lambda: run_tf("15m", "5m")
    # bias / draw from 1H / 4H as filters (top-down step 1), on both setup timeframes and both entries
    for st in ("5m", "15m"):
        for en in ("1m", "3m"):
            for tf in ("1h", "4h"):
                def mk(st=st, en=en, tf=tf, kind="draw"):
                    M = base()[0] if st == "5m" else market15()[0]
                    return run_tf(st, en, skip=lambda z: htf_draw(M, z, tf) == -1)
                V[f"top-down: {tf.upper()} draw -> setup {st} -> entry {en}"] = mk
                def mkb(st=st, en=en, tf=tf):
                    M = base()[0] if st == "5m" else market15()[0]
                    return run_tf(st, en, skip=lambda z: htf_bias(M, z, tf) == -1)
                V[f"top-down: {tf.upper()} candle bias -> setup {st} -> entry {en}"] = mkb
    # adaptive entry timeframe: high-range setups on 3m, quiet ones on 1m (and the mirror)
    for q in (16.3, 19.0, 22.1):
        V[f"adaptive: ATR(5m) > {q} -> entry 3m, else 1m"] = lambda q=q: run_tf("5m", "1m", entry_fn=lambda z, q=q: "3m" if z["atr"] > q else "1m")
        V[f"adaptive (mirror): ATR(5m) > {q} -> entry 1m, else 3m"] = lambda q=q: run_tf("5m", "1m", entry_fn=lambda z, q=q: "1m" if z["atr"] > q else "3m")
    M = base()[0]
    for q in (296.0, 319.0):
        V[f"adaptive: VIX move > {q:.0f} pts -> entry 3m, else 1m"] = lambda q=q: run_tf("5m", "1m", entry_fn=lambda z, q=q: "3m" if (M.ctx[z["k"]].get("vix_move") or 0) > q else "1m")
    # adaptive setup timeframe per day (known at 18:00): high VIX-move day -> 15m setup, quiet -> 5m
    for q in (296.0, 319.0):
        def ad(q=q):
            hi = [d for k, (d, s, e) in enumerate(M.days) if (M.ctx[k].get("vix_move") or 0) > q]
            hs = set(hi)
            a = run_tf("15m", "1m", sessions=[d for d in F.SESS if d in hs])
            b = run_tf("5m", "1m", sessions=[d for d in F.SESS if d not in hs])
            return sorted(a + b, key=lambda t: t["entry_t"])
        V[f"adaptive: VIX move > {q:.0f} pts -> setup 15m, else 5m (entry 1m)"] = ad
    return V


def tf(only=None):
    base_o = fast(base_trades())
    res = collections.OrderedDict()
    for nm, fn in tf_variants().items():
        if only and only not in nm:
            continue
        T = fn()
        o = fast(T)
        res[nm] = {**o, "dH1": o["H1"]["net"] - base_o["H1"]["net"], "dH2": o["H2"]["net"] - base_o["H2"]["net"]}
        print(f"{nm:66s} dH1={res[nm]['dH1']:+7,} dH2={res[nm]['dH2']:+7,} | {_fl(o)}", flush=True)
    json.dump({"base": base_o, "variants": res}, open(os.path.join(OUTD, "losses_tf.json"), "w"), indent=1, default=_j)
    return res


# ================================================================================================ refine the survivors + combos
def week_stops(n, m):
    def fn(H, t):
        wk = dt.date.fromisoformat(t["day"]).isocalendar()[:2]
        k = sum(1 for x in H if dt.date.fromisoformat(x["day"]).isocalendar()[:2] == wk and x["exit"] == "STOP")
        return m if k >= n else 1.0
    return fn


def after_win(m, nxt=1):
    def fn(H, t):
        return m if any(x["pnl"] > 0 for x in H[-nxt:]) else 1.0
    return fn


def build(cfg):
    """cfg: idm_age (int|None), stop_half (pts|None), wk_stop ((n, mult)|None), after_win ((mult, next)|None), min_rr."""
    P = {}
    if cfg.get("idm_age"):
        P["idm_a"] = [1.0, cfg["idm_age"], 1]
    if cfg.get("min_rr"):
        P["min_rr"] = cfg["min_rr"]
    skips = []
    if cfg.get("monday"):
        skips.append(lambda z: (lambda f: f["mon_took_fri"] in ("high", "low") and ((f["mon_took_fri"] == "high") != (z["dir"] == -1)))(feat_m(z)))
    T = run({"skip": (lambda z: any(fn(z) for fn in skips))} if skips else None, P=P)
    if cfg.get("es_mult"):
        T = scaled(T, lambda t: cfg["es_mult"] if fz(t["_z"]).get("smt") == "both swept" else 1.0)
    if cfg.get("stop_half"):
        T = scaled(T, lambda t: 0.5 if t["risk_pts"] > cfg["stop_half"] else 1.0)
    fns = []
    if cfg.get("wk_stop"):
        fns.append(week_stops(*cfg["wk_stop"]))
    if cfg.get("after_win"):
        fns.append(after_win(*cfg["after_win"]))
    if fns:
        T0 = sorted(T, key=lambda t: t["entry_t"])
        mult = {}
        for t in T0:
            H = [x for x in T0 if x["exit_t"] <= t["entry_t"]]
            m = 1.0
            for fn in fns:
                m *= fn(H, t)
            mult[(t["day"], t["entry_t"])] = m
        T = [t if mult[(t["day"], t["entry_t"])] == 1.0 else {**lit.scale_trade(t, mult[(t["day"], t["entry_t"])]), "_z": t["_z"]} for t in T0]
    return T


GRIDS = {
    "inducement age (bars)": [("idm_age", a) for a in (8, 12, 18, 24, 30)],
    "half size above a stop of (pts)": [("stop_half", x) for x in (45, 50, 55, 60, 65, 70)],
    "weekly stop: after n stop-outs in the week, size x": [("wk_stop", (n, m)) for n in (1, 2, 3) for m in (0.5, 0.25)],
    "after a winner, size x the next trade(s)": [("after_win", (m, k)) for m in (1.25, 1.5, 2.0) for k in (1, 2)],
    "minimum room to the VIX band (R)": [("min_rr", x) for x in (2.0, 3.0, 4.0, 5.0)],
}


def refine():
    base_o = fast(base_trades())
    out = {"base": base_o, "grids": {}, "picks": {}}
    for fam, grid in GRIDS.items():
        rows = []
        for key, val in grid:
            o = fast(build({key: val}))
            rows.append({"key": key, "val": val, **o, "dH1": o["H1"]["net"] - base_o["H1"]["net"], "dH2": o["H2"]["net"] - base_o["H2"]["net"]})
            print(f"{fam:52s} {str(val):12s} dH1={rows[-1]['dH1']:+7,} dH2={rows[-1]['dH2']:+7,} | {_fl(o)}", flush=True)
        ok = [r for r in rows if r["H1"]["tpw"] >= 2.0]
        pick = max(ok, key=lambda r: r["H1"]["net"])
        out["grids"][fam] = rows
        out["picks"][fam] = {"key": pick["key"], "val": pick["val"], "dH1": pick["dH1"], "dH2": pick["dH2"],
                             "H2_tpw": pick["H2"]["tpw"], "both": pick["dH1"] > 0 and pick["dH2"] > 0 and pick["H2"]["tpw"] >= 2.0}
        print("  PICK on H1:", out["picks"][fam], flush=True)
    json.dump(out, open(os.path.join(OUTD, "losses_refine.json"), "w"), indent=1, default=_j)
    return out


COMBOS = {
    "lit_final": {},
    "A inducement <= 12 bars": {"idm_age": 12},
    "M Monday after Friday's H/L taken: only back toward the other side": {"monday": True},
    "W weekly stop: 3 stop-outs in the week -> quarter size": {"wk_stop": (3, 0.25)},
    "W2 weekly stop: 2 stop-outs in the week -> half size": {"wk_stop": (2, 0.5)},
    "S half size above a 60-pt stop": {"stop_half": 60},
    "C after a winner 1.5x the next trade": {"after_win": (1.5, 1)},
    "C2 after a winner 2x the next 2 trades": {"after_win": (2.0, 2)},
    "E 1.5x when ES also swept": {"es_mult": 1.5},
    "A+M": {"idm_age": 12, "monday": True},
    "A+M+W": {"idm_age": 12, "monday": True, "wk_stop": (3, 0.25)},
    "A+M+W2": {"idm_age": 12, "monday": True, "wk_stop": (2, 0.5)},
    "A+M+W+S": {"idm_age": 12, "monday": True, "wk_stop": (3, 0.25), "stop_half": 60},
    "A+M+W+C": {"idm_age": 12, "monday": True, "wk_stop": (3, 0.25), "after_win": (1.5, 1)},
    "A+M+W+C2": {"idm_age": 12, "monday": True, "wk_stop": (3, 0.25), "after_win": (2.0, 2)},
    "A18+M+W": {"idm_age": 18, "monday": True, "wk_stop": (3, 0.25)},
}


def ror(T, nm):
    """Return on risk: net $ / total $ put at risk (edge per dollar risked; size-neutral)."""
    a, z = F.SPAN[nm]
    TT = [t for t in T if a <= t["day"] <= z]
    r = sum(t["risk_usd"] for t in TT)
    return round(100 * sum(t["pnl"] for t in TT) / r, 1) if r else None


def combos(names=None):
    res = collections.OrderedDict()
    for nm, cfg in COMBOS.items():
        if names and nm not in names:
            continue
        T = build(cfg)
        o = F.score(T)
        for sp in o:
            o[sp]["ror"] = ror(T, sp)
            mo = collections.defaultdict(float)
            for t in T:
                if F.SPAN[sp][0] <= t["day"] <= F.SPAN[sp][1]:
                    mo[t["day"][:7]] += t["pnl"]
            o[sp]["worst_month"] = round(min(mo.values())) if mo else None
            st = mx = 0
            for t in sorted([t for t in T if F.SPAN[sp][0] <= t["day"] <= F.SPAN[sp][1]], key=lambda t: t["entry_t"]):
                st = st + 1 if t["pnl"] <= 0 else 0; mx = max(mx, st)
            o[sp]["max_nowin_run"] = mx
        res[nm] = {"cfg": cfg, **o}
        print(nm, " | ".join(f"{k}[{F.fmt({k: v})[len(k) + 1:-1]} ror={v['ror']}% wm={v['worst_month']} run={v['max_nowin_run']} f20={v['f20']} p20={v['p20']} $/mo={v['per_month']}]" for k, v in o.items()), flush=True)
    json.dump(res, open(os.path.join(OUTD, "losses_combos.json"), "w"), indent=1, default=_j)
    return res


# ================================================================================================ masters-study filters (research/lit/masters.md)
def tf_relaxed_variants():
    V = collections.OrderedDict()
    for dep, dis, age, mx in ((0.3, 0.6, 24, 120.0), (0.25, 0.5, 36, 150.0), (0.4, 0.7, 24, 100.0)):
        for en in ("1m", "3m"):
            P = {"depth": dep, "disp": dis, "idm_a": [1.0, age, 1], "max_stop": mx}
            V[f"setup 15m relaxed (depth {dep}, disp {dis}, idm age {age}, max stop {mx:.0f}) / entry {en}"] = (lambda P=P, en=en: run_tf("15m", en, P=P))
    return V


def tf_relaxed():
    base_o = fast(base_trades())
    res = collections.OrderedDict()
    for nm, fn in tf_relaxed_variants().items():
        o = fast(fn())
        res[nm] = {**o, "dH1": o["H1"]["net"] - base_o["H1"]["net"], "dH2": o["H2"]["net"] - base_o["H2"]["net"]}
        print(f"{nm:66s} dH1={res[nm]['dH1']:+7,} dH2={res[nm]['dH2']:+7,} | {_fl(o)}", flush=True)
    p = os.path.join(OUTD, "losses_tf.json")
    J = json.load(open(p)); J["variants"].update(res); json.dump(J, open(p, "w"), indent=1, default=_j)
    return res


def _holidays():
    """US exchange holidays + early-close days (CME equity futures halt early / thin): the 9 NYSE holidays, Good Friday, the
    day after Thanksgiving, Christmas Eve, July 3 (weekday) - as trading-day dates."""
    from pandas.tseries.holiday import (AbstractHolidayCalendar, GoodFriday, Holiday, USLaborDay, USMartinLutherKingJr,
                                        USMemorialDay, USPresidentsDay, USThanksgivingDay, nearest_workday)
    class Cal(AbstractHolidayCalendar):
        rules = [Holiday("NY", month=1, day=1, observance=nearest_workday), USMartinLutherKingJr, USPresidentsDay, GoodFriday,
                 USMemorialDay, Holiday("J19", month=6, day=19, start_date="2022-01-01", observance=nearest_workday),
                 Holiday("J4", month=7, day=4, observance=nearest_workday), USLaborDay, USThanksgivingDay,
                 Holiday("XM", month=12, day=25, observance=nearest_workday)]
    H = {d.strftime("%Y-%m-%d") for d in Cal().holidays("2021-01-01", "2026-12-31")}
    E = set()
    for y in range(2021, 2027):
        tg = [d for d in Cal().holidays(f"{y}-11-01", f"{y}-11-30") if d.month == 11][0]
        E.add((tg + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
        for md in ("12-24", "07-03"):
            d = pd.Timestamp(f"{y}-{md}")
            if d.dayofweek < 5:
                E.add(d.strftime("%Y-%m-%d"))
    return H, E


def feat_m(z):
    """Masters features (setup time, no look-ahead)."""
    key = ("m", z["day"], z["i"], z["dir"])
    if key in _FC:
        return _FC[key]
    M, C, B1, B5 = base()
    i, ee, sb, d, k = z["i"], z["ext_i"], z["sweep_i"], z["dir"], z["k"]
    x = M.ctx[k]; s = x["s"]
    hi_d, lo_d, c_d = (M.h, M.l, M.c) if d == 1 else (-M.l, -M.h, -M.c)
    swing_hi, swing_lo = (M.fh, M.fl) if d == 1 else (M.fl, M.fh)
    f = {}
    # D2 engineered liquidity: a 5m swing high (long) in the last session + today that came within x% of a still-unbroken
    # target pool without taking it
    pools = [z["entry_d"] + dist for cls, L in z["targets"].items() if cls != "buildup" for dist in L]
    px = abs(M.c[i])
    best = None
    a0 = max(s, sb - 72)                       # the 6 hours before the trap, inside today's session
    for j in swing_hi[(swing_hi >= a0) & (swing_hi <= sb)]:
        hj = hi_d[j]
        for p in pools:
            gap = (p - hj) / px * 100
            if 0.005 <= gap and (best is None or gap < best):
                best = gap
    f["eng_gap_pct"] = best
    # D6 time confluence of the sweep extreme minute (1m when available)
    t5 = int(M.t[ee])
    j0 = int(np.searchsorted(B1.t, t5)); j1 = int(np.searchsorted(B1.t, t5 + 300))
    if j1 - j0 == 5:
        seg = B1.l[j0:j1] if d == 1 else -B1.h[j0:j1]
        m = int(B1.mod[j0 + int(np.argmin(seg))]); f["ext_min_src"] = "1m"
    else:
        m = int(M.mod[ee]) + 2; f["ext_min_src"] = "5m"
    f["ext_mod"] = m
    key_t = (480, 570, 600, 1200)
    f["t_key5"] = any(abs(m - kt) <= 5 for kt in key_t)
    f["t_key2"] = any(abs(m - kt) <= 2 for kt in key_t)
    f["t_3min"] = (m % 15) <= 2 or (m % 15) >= 12
    # D9 outside day yesterday
    if k >= 2:
        (d1, s1, e1), (d2, s2, e2) = M.days[k - 1], M.days[k - 2]
        f["outside_yday"] = bool(M.h[s1:e1].max() > M.h[s2:e2].max() and M.l[s1:e1].min() < M.l[s2:e2].min())
    # D1 two lines: nearest respected unswept 5m swing low below price before the sweep (respected = price moved >= kATR away)
    for kk in (1.0, 2.0):
        ref = sb - 1; pxr = c_d[ref]; line = None
        for j in swing_lo[(swing_lo >= max(0, s - 864)) & (swing_lo <= ref - 2)][::-1]:
            lv = lo_d[j]
            if lv >= pxr or lo_d[j + 1:ref + 1].min() < lv:
                continue
            if hi_d[j:ref + 1].max() - lv < kk * M.atr[j]:
                continue
            if line is None or lv > line:
                line = lv
        f[f"two_lines_{kk:g}"] = None if line is None else bool(z["ext_d"] < line)
    # D13 same-direction BOS legs since midnight before the trigger: closes above distinct confirmed fractal highs
    a = s + int(np.argmax(M.mod[s:i + 1] < 1080)) if (M.mod[s:i + 1] < 1080).any() else i
    legs = 0; broken = set()
    fh = swing_hi[(swing_hi >= a - 24) & (swing_hi < i)]
    for j in fh:
        cc = c_d[j + 3:i]
        if len(cc) and (cc > hi_d[j]).any():
            first = j + 3 + int(np.argmax(cc > hi_d[j]))
            if first >= a and first < z["ext_i"]:
                broken.add((first, float(hi_d[j])))
    lv = -np.inf
    for first, h_ in sorted(broken):          # successive breaks of higher swing highs (one leg each)
        if h_ > lv:
            legs += 1; lv = h_
    f["legs_before"] = legs
    # D16 Monday took Friday's high (long target side for a short) before the trigger
    f["mon_took_fri"] = None
    if x["dow"] == 0 and "pdh" in x:
        took_hi = M.h[s:i + 1].max() > x["pdh"]; took_lo = M.l[s:i + 1].min() < x["pdl"]
        f["mon_took_fri"] = ("high" if took_hi else "") + ("low" if took_lo else "") or "none"
    H, E = _holidays()
    f["holiday"] = z["day"] in H; f["early_close"] = z["day"] in E
    _FC[key] = f
    return f


def monday_target(z, ep, risk, tp):
    """D16: Monday that took Friday's high (low): a short (long) targets Friday's low (high), >= min_rr, banked at max_rr."""
    M = base()[0]; x = M.ctx[z["k"]]
    f = feat_m(z)
    if x["dow"] != 0 or not f["mon_took_fri"] or f["mon_took_fri"] == "none":
        return tp
    if z["dir"] == -1 and "high" in f["mon_took_fri"]:
        dist = (-x["pdl"]) - ep
    elif z["dir"] == 1 and "low" in f["mon_took_fri"]:
        dist = x["pdh"] - ep
    else:
        return tp
    if dist < P0["min_rr"] * risk:
        return tp
    return min(dist, P0["max_rr"] * risk)


def masters_variants():
    V = collections.OrderedDict()
    sk = lambda pred: (lambda: with_f(run({"skip": lambda z: pred(feat_m(z), z)})))
    sz = lambda mult: (lambda: scaled(base_trades(), lambda t: mult(feat_m(t["_z"]), t)))
    for x in (0.02, 0.05, 0.1, 0.3):
        V[f"D2 engineered liquidity within {x}%: half size without"] = ("size", sz(lambda f, t, x=x: 1.0 if (f["eng_gap_pct"] is not None and f["eng_gap_pct"] <= x) else 0.5))
        V[f"D2 engineered liquidity within {x}%: skip without"] = ("skip", sk(lambda f, z, x=x: not (f["eng_gap_pct"] is not None and f["eng_gap_pct"] <= x)))
    for lab, key in (("+-5 min of 08:00/09:30/10:00/20:00", "t_key5"), ("+-2 min of 08:00/09:30/10:00/20:00", "t_key2"), ("3-minute rule (15m candle edges)", "t_3min")):
        for m in (0.5, 0.75):
            V[f"D6 time confluence {lab}: {m}x without"] = ("size", sz(lambda f, t, key=key, m=m: 1.0 if f[key] else m))
    V["D6 time confluence (key times +-5 or 3-minute rule): 0.5x without"] = ("size", sz(lambda f, t: 1.0 if (f["t_key5"] or f["t_3min"]) else 0.5))
    V["D9 day after an outside day: half size"] = ("size", sz(lambda f, t: 0.5 if f.get("outside_yday") else 1.0))
    V["D9 day after an outside day: skip"] = ("skip", sk(lambda f, z: bool(f.get("outside_yday"))))
    for kk in (1.0, 2.0):
        V[f"D1 two lines (respected = {kk:g} ATR): only sweeps of the nearest line"] = ("skip", sk(lambda f, z, kk=kk: f[f"two_lines_{kk:g}"] is False))
        V[f"D1 two lines (respected = {kk:g} ATR): half size otherwise"] = ("size", sz(lambda f, t, kk=kk: 0.5 if f[f"two_lines_{kk:g}"] is False else 1.0))
    for n in (3, 4):
        V[f"D13 {n}+ same-direction legs since midnight: skip"] = ("skip", sk(lambda f, z, n=n: f["legs_before"] >= n))
        V[f"D13 {n}+ same-direction legs since midnight: half"] = ("size", sz(lambda f, t, n=n: 0.5 if f["legs_before"] >= n else 1.0))
    V["D8 bank holidays and early-close days off"] = ("skip", sk(lambda f, z: f["holiday"] or f["early_close"]))
    V["D16 Monday took Friday's high/low: target Friday's opposite extreme"] = ("mgmt", lambda: with_f(run({"tgt_fn": monday_target})))
    V["D16 Monday took Friday's high/low: only trade back toward the other side"] = ("skip", sk(
        lambda f, z: f["mon_took_fri"] in ("high", "low") and ((f["mon_took_fri"] == "high") != (z["dir"] == -1))))
    return V


def masters():
    base_o = fast(base_trades())
    T26 = [t for t in base_trades() if t["day"] >= "2026"]
    facts = {}
    for key in ("eng_gap_pct", "t_key5", "t_3min", "outside_yday", "two_lines_1", "two_lines_2", "legs_before", "mon_took_fri", "holiday", "early_close"):
        vals = [feat_m(t["_z"]).get(key) for t in T26]
        if key == "eng_gap_pct":
            vals = [None if v is None else ("<=0.1%" if v <= 0.1 else "<=0.3%" if v <= 0.3 else ">0.3%") for v in vals]
        if key == "legs_before":
            vals = [str(min(v, 4)) for v in vals]
        facts[key] = table(T26, [(key, vals, "cat")])[key] if any(v is not None for v in vals) else {}
        for lab, s_ in facts[key].items():
            print(f"  {key:14s} {lab:10s} n={s_['n']:3d} ({s_['n1']}/{s_['n2']}) win={s_['win']} net={s_['net']:+7,} PF={s_['pf']} H1={s_['h1']:+7,} H2={s_['h2']:+7,}", flush=True)
    res = collections.OrderedDict()
    for nm, (fam, fn) in masters_variants().items():
        o = fast(fn())
        res[nm] = {"family": fam, **o, "dH1": o["H1"]["net"] - base_o["H1"]["net"], "dH2": o["H2"]["net"] - base_o["H2"]["net"]}
        print(f"{nm:72s} dH1={res[nm]['dH1']:+7,} dH2={res[nm]['dH2']:+7,} | {_fl(o)}", flush=True)
    json.dump({"base": base_o, "facts_2026": facts, "variants": res}, open(os.path.join(OUTD, "losses_masters.json"), "w"), indent=1, default=_j)
    return res


# ================================================================================================ Reim's boxes (decoded to NY time)
class MarketReim(lit.Market):
    """lit.Market plus Reim's Asia box 18:05-01:00 ET (crosses midnight, which lit.Market's boxes can't), class asia, named
    asia_reim. Known once the 00:55 bar closed. London 03-04 (lon34) and NY 08-09 (ny89) already exist."""

    def _context(self):
        super()._context()
        mod = self.mod
        for x in self.ctx:
            s, e = x["s"], x["e"]
            md = mod[s:e]
            ii = np.flatnonzero((md >= 1085) | (md < 60))
            if len(ii) >= 2:
                x["asia_reim"] = (float(self.h[s + ii].max()), float(self.l[s + ii].min()), int(s + ii[-1]))
            else:
                x.pop("asia_reim", None)


def market_reim():
    if "MR" not in _S:
        lit.EXTRA_BOXES.setdefault("asia_reim", (1085, 60, "asia"))      # runtime registration only (engine/lit.py untouched)
        M = MarketReim(extra_boxes=["asia_reim"])
        p = os.path.join(F.CACHE, f"litloss_reim_cands_{rl._data_key().replace(':', '_')}.pkl")
        if os.path.exists(p):
            C = pickle.load(open(p, "rb"))
        else:
            C = lit.candidates(M, ref="cisd")
            pickle.dump(C, open(p, "wb"))
        M0, C0, B1, B5 = base()
        _S.update(MR=M, CR=C, B1R=remap(B1, M0, M), B5R=remap(B5, M0, M))
    return _S["MR"], _S["CR"], _S["B1R"], _S["B5R"]


REIM_SET = ["asia_reim_h", "asia_reim_l", "lon34_h", "lon34_l", "ny89_h", "ny89_l", "pdh", "pdl", "pwh", "pwl"]


def reim():
    base_o = fast(base_trades())
    M, C, B1, B5 = market_reim()
    res = collections.OrderedDict()
    for nm, P in (("Reim Asia box 18:05-01:00 added to every level", {"extra_boxes": ["asia_reim"]}),
                  ("Reim's levels only (Asia 18:05-01:00, London 03-04, NY 08-09, PDH/PDL, PWH/PWL)", {"extra_boxes": ["asia_reim"], "sweep_names": REIM_SET}),
                  ("Reim's levels + PMH/PML", {"extra_boxes": ["asia_reim"], "sweep_names": REIM_SET + ["pmh", "pml"]})):
        T = run2(M, C, {**P0, **P}, F.SESS, B1=B1, B5=B5)
        o = fast(T)
        res[nm] = {**o, "dH1": o["H1"]["net"] - base_o["H1"]["net"], "dH2": o["H2"]["net"] - base_o["H2"]["net"]}
        print(f"{nm:80s} dH1={res[nm]['dH1']:+7,} dH2={res[nm]['dH2']:+7,} | {_fl(o)}", flush=True)
    p = os.path.join(OUTD, "losses_masters.json")
    J = json.load(open(p)) if os.path.exists(p) else {}
    J["reim_boxes"] = res
    json.dump(J, open(p, "w"), indent=1, default=_j)
    return res


# ================================================================================================ store runs
SAVES = [
    ("lit_loss_pack", "LIT final + loss rules: Monday rule + weekly stop (2 stop-outs -> half size)", {"monday": True, "wk_stop": (2, 0.5)}, "adopt-candidate"),
    ("lit_loss_weekly_stop", "LIT final + weekly stop: after 2 stop-outs in a week, half size for the rest of it", {"wk_stop": (2, 0.5)}, "adopt-candidate"),
    ("lit_loss_monday", "LIT final + Monday rule: once Monday took Friday's high (low), only shorts (longs)", {"monday": True}, "adopt-candidate"),
    ("lit_loss_after_win", "LIT final + 1.5x size on the trade after a winner", {"after_win": (1.5, 1)}, "promising"),
    ("lit_loss_pack_win", "LIT final + Monday rule + weekly stop + 1.5x after a winner", {"monday": True, "wk_stop": (2, 0.5), "after_win": (1.5, 1)}, "promising"),
    ("lit_loss_idm12", "LIT final + inducement no older than 12 bars (1 hour)", {"idm_age": 12}, "rejected"),
]


def save():
    for rid, title, cfg, status in SAVES:
        T = build(cfg)
        S = rl.score(T, F.SESS)
        o = F.score(T)
        h = lambda s: (f"n={s['n']} {s['tpw']}/wk win {s['win']}% PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,} "
                       f"eval 2wk {s['p10']}/{s['f10']} 1mo {s['p20']}/{s['f20']} pass rate {s['pass_rate']}%")
        clean = [{k: v for k, v in t.items() if not k.startswith("_")} for t in T]
        rl.save(rid, title, "other", "Owner order 2026-10-18: where and why does LIT lose, and which loss rules help both halves of 2026?",
                params={**P0, "loss_rules": {k: list(v) if isinstance(v, tuple) else v for k, v in cfg.items()}}, trades=clean, scored=S,
                status=status,
                verdict=f"2026 H1 (pick) {h(o['H1'])}; 2026 H2 (check) {h(o['H2'])}; 2026 {h(o['2026'])}; 2021-25 reference only {h(o['2021-25'])}",
                notes="tools/lit_losses.py build(cfg) on top of lit_final (engine/lit.py run_x, research/lit/lit_final.json); weekly stop and "
                      "after-winner sizing re-size finished trades exactly (floor 1 micro); Monday rule skips the setup (the day stays free).",
                writeup="lit-losses", tags=["lit", "lit_loss"])
        print("saved", rid, F.fmt(o), flush=True)


def save_live():
    """The adopted pack inside the engine (engine/lit.py options "monday" + "wk_stop", live_model.json "lit"): checks it
    equals build(lit_loss_pack) trade for trade and stores it as run lit_live (the live LIT settings)."""
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    P = {**lit.DEFAULTS, **lm["lit"]}
    T = F.run(P)
    ref = build({"monday": True, "wk_stop": (2, 0.5)})
    ka = [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"], t["qty"]) for t in T]
    kb = [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"], t["qty"]) for t in sorted(ref, key=lambda t: t["entry_t"])]
    same = ka == kb
    print("engine options == build(lit_loss_pack):", same, len(ka), len(kb), flush=True)
    if not same:
        raise SystemExit("the engine options do not reproduce lit_loss_pack")
    S = rl.score(T, F.SESS)
    o = F.score(T)
    h = lambda s: (f"n={s['n']} {s['tpw']}/wk win {s['win']}% PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,} "
                   f"eval 2wk {s['p10']}/{s['f10']} 1mo {s['p20']}/{s['f20']} pass rate {s['pass_rate']}%")
    clean = [{k: v for k, v in t.items() if not k.startswith("_") and k not in ("size_why", "size_mult")} for t in T]
    rl.save("lit_live", "LIT live: lit_final + loss pack (Monday rule, weekly stop) as engine options", "other",
            "The live LIT settings (live_model.json, 2026-10-18): the adopted loss pack inside engine/lit.py",
            params=P, trades=clean, scored=S, status="adopt-candidate",
            verdict=f"ADOPTED 2026-10-18 (the live LIT). 2026 H1 (pick) {h(o['H1'])}; 2026 H2 (check) {h(o['H2'])}; 2026 {h(o['2026'])}; 2021-25 reference only {h(o['2021-25'])}",
            notes="engine/lit.py run_x with monday=True, wk_stop=[2, 0.5] (live_model.json lit); identical to lit_loss_pack "
                  "(tools/lit_losses.py build) trade for trade. The live loop (engine/lit_live.py) runs the same code: "
                  "tests/test_lit_live.py.", writeup="lit-losses", tags=["lit", "lit_loss", "live"])
    print("saved lit_live", F.fmt(o), flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    {"check": check, "anatomy": anatomy, "rules": rules, "refine": refine, "combos": combos, "tf": tf, "tf_relaxed": tf_relaxed,
     "masters": masters, "reim": reim, "save": save, "live": save_live}[cmd]()
