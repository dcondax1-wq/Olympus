"""Chart records of every LIT replay trade: the exact bars and every marker a TradingView-style Long/Short drawing needs.

One record per trade, rebuilt from the same engine run as research/lab/backtest_live.json (tools/lit_final.run on the live
parameters = engine/lit.py run_x), so every price and time is the engine's own:
  levels   the swept liquidity levels (name, label, price, the bar the level became known)
  sweep    the first bar that breached a swept level, the sweep extreme (price, bar)
  idm      the inducement swings (fractal beyond the level, <= 1 ATR, <= 36 bars before the sweep) and the bar that took them
  cisd5    the 5m CISD level (open of the last opposite-close run into the extreme) and the 5m bar that closed through it
  limit    the limit price (CISD level, or the trigger close when lower), placed at the next 5m open, valid `wait` 5m bars;
           the bar that tapped it
  cisd1    the 1m CISD after the tap: its level and the 1m bar that closed through it (the fill is the next 1m open)
  entry / stop / target / be / exit   fill bar + price, stop 1 tick beyond the extreme, target, breakeven move bar, exit bar,
           kind (TARGET / STOP / BE / EOD) and price
  boxes    Asia 20:00-00:00, London 02:00-05:00, NY 08:00-09:00 session boxes (high / low of the whole box) inside the window
  b5 / b1  5m bars from 2 h before the sweep to 1 h after the exit; 1m bars from 20 min before the limit to 1 h after the
           fill (1m-executed trades only). Prices are integer quarter points relative to p0 (price = (p0 + v) / 4), times are
           t0 + dt * s (epoch seconds; dt = bar steps, gaps kept).
Times are epoch seconds (UTC); `off` is the ET offset of the trading day in seconds (display = t + off). Futures data only
(TradingView CME NQ1! 5m data/NQ_5m.csv + 1m data/NQ_1m.csv through engine/lit.py bars_1m, on the 5m price basis).

  from tools.lit_chart_data import build;  recs = build(since="2026-01-01")      # {id: record}
Record id = <date>_<HHMM ET of the fill>_<long|short> (also the PNG name of tools/lit_trade_charts.py).
"""
from __future__ import annotations

import bisect
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
BOXES = (("Asia", "asia20", 1200, 1440), ("London", "lon25", 120, 300), ("NY", "ny89", 480, 540))
SHORT = {"pdh": "PDH", "pdl": "PDL", "pwh": "PWH", "pwl": "PWL", "pmh": "PMH", "pml": "PML", "nwog": "NWOG", "ndog": "NDOG",
         "bu_h": "EQH", "bu_l": "EQL"}


def trade_id(day: str, entry_t: int, side: str) -> str:
    return f"{day}_{dt.datetime.fromtimestamp(int(entry_t), ET):%H%M}_{side.lower()}"


def level_label(name: str) -> str:
    if name in SHORT:
        return SHORT[name]
    from engine.lit_live import LBL
    base, hl = (name.rsplit("_", 1) + [""])[:2]
    return f"{LBL.get(base, base)} {'H' if hl == 'h' else 'L' if hl == 'l' else ''}".strip()


def q4(x: float) -> float:
    return round(float(x) * 4) / 4


def _pack(B, a: int, z: int):
    """bars B[a:z] packed: quarter points relative to p0, time steps relative to t0."""
    if z <= a:
        return None
    t = B.t[a:z].astype(np.int64)
    p0 = int(np.floor(float(B.l[a:z].min()) * 4))
    f = lambda arr: [int(round(float(v) * 4)) - p0 for v in arr[a:z]]
    s = int(B.secs)
    return {"t0": int(t[0]), "s": s, "p0": p0, "dt": [int((x - t[0]) // s) for x in t],
            "o": f(B.o), "h": f(B.h), "l": f(B.l), "c": f(B.c)}


def _walk(M, B, z, ep, tgt_px, stop, P):
    """simulate_x's entry + management walk (direction space), keeping the bars it decides on. Returns a dict or None."""
    from engine import lit
    d = z["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    t0 = int(M.t[z["entry_i"]])
    k0 = int(np.searchsorted(B.t, t0))
    s_day = int(M.day_of[z["entry_i"]])
    flat, wait_s = P["flat_mod"], P["wait"] * 300
    cis = P.get("cisd1m")
    if cis and B.secs == 300:
        cis = max(1, cis // 5)
    limit_fill, fill, tapped, cz_lvl, conf = True, None, None, None, None
    entry = None
    k = k0
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= flat or B.mod[k] >= 1080:
            break
        if tapped is None and B.t[k] >= t0 + wait_s:
            break
        if lo_d[k] <= stop:
            if tapped is None and lo_d[k] <= ep and not cis:
                fill = k; entry = min(ep, float(o_d[k]))
            break
        if tapped is None and lo_d[k] <= ep:
            if cis:
                tapped = k
            else:
                fill = k; entry = min(ep, float(o_d[k])); break
        if tapped is None and hi_d[k] >= tgt_px:
            break
        if tapped is not None:
            if k - tapped > cis:
                break
            lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
            cz = lit._cisd_level(c_d, o_d, lowk)
            if cz is not None and k > lowk and c_d[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == s_day:
                fill = k + 1; entry = float(o_d[k + 1]) + lit.SLIP; limit_fill = False
                cz_lvl, conf = (float(cz[0]), int(cz[1])), k
                break
        k += 1
    if fill is None:
        return None
    return {"fill": fill, "entry": entry, "tapped": tapped if tapped is not None else (fill if limit_fill else None),
            "limit_fill": limit_fill, "cz": cz_lvl, "conf": conf, "t0": t0, "k0": k0}


def _manage(B, d, fill, entry, stop, tg, be_r, limit_fill):
    """breakeven bar and exit bar of the management walk (simulate_x's rules)."""
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    risk = entry - stop
    cur, be_k, k = stop, None, fill
    s_day = B.day[fill]
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            return be_k, k - 1
        if lo_d[k] <= cur:
            return be_k, k
        if not (k == fill and limit_fill):
            if hi_d[k] >= tg:
                return be_k, k
            if be_r is not None and be_k is None and hi_d[k] >= entry + be_r * risk:
                cur, be_k = entry, k
        if B.mod[k] >= 955:
            return be_k, k
        k += 1
    return be_k, B.n - 1


def build(since: str = "2026-01-01", until: str = "9999", params: dict | None = None, verbose: bool = True) -> dict:
    from engine import lit
    from tools import lit_final as F
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    P = {**lit.DEFAULTS, **(params if params is not None else (lm.get("lit") or {}))}
    T = sorted(F.run(P), key=lambda t: t["entry_t"])
    M, C = F.market(P["ref"], P["extra_boxes"])
    B5 = F.bars(M, "5m")
    B1 = F.bars(M, "1m") if P["tf"] == "1m" else None
    cand = {(z["i"], z["dir"]): z for z in C}
    out, bad = {}, []
    for t in T:
        if not (since <= t["day"] <= until):
            continue
        z = cand[(t["i"], t["dir"])]
        d = int(z["dir"])
        side = "LONG" if d == 1 else "SHORT"
        kday = int(M.day_of[z["entry_i"]])
        use1 = B1 is not None and kday in B1.full
        B = B1 if use1 else B5
        # the plan, exactly as _run_core builds it
        ep = min(float(z["ref_d"]), z["trig_c"])
        stop = z["ext_d"] - P["stop_buf"]
        risk_plan = ep - stop
        sh = z["entry_d"] - ep
        TT = {c: [x + sh for x in v] for c, v in lit.targets_x(M, z, P).items()}
        best = None
        for c in P["classes"]:
            for dist in TT.get(c, []):
                if dist >= P["min_rr"] * risk_plan:
                    if best is None or dist < best:
                        best = dist
                    break
        tp = (P["fallback_rr"] * risk_plan) if best is None else (min(best, P["max_rr"] * risk_plan) if P["max_rr"] else best)
        w = _walk(M, B, z, ep, ep + tp, stop, P)
        entry_t = int(B.t[w["fill"]]) if w else None
        if not w or entry_t != int(t["entry_t"]) or abs(w["entry"] * d - t["entry_px"]) > 1e-6:
            bad.append((t["day"], t["entry_t"], entry_t))
            continue
        entry = w["entry"]
        tg = t["target_px"] * d
        be_k, xk = _manage(B, d, w["fill"], entry, stop, tg, P["be_r"], w["limit_fill"])
        if int(B.t[xk]) + B.secs != int(t["exit_t"]):
            bad.append((t["day"], t["entry_t"], "exit", int(B.t[xk]) + B.secs, t["exit_t"]))
            continue
        q = int(t["qty"])
        pts = (t["pnl"] / q + lit.COMM) / lit.PV
        exit_px = q4(t["entry_px"] + d * pts)
        kind = t["exit"]
        # swept levels, with the bar each became known (session boxes) or None (prior day / week / month, gaps, build-ups)
        L = M.levels(z["k"])
        lv = []
        for nm, pd_ in sorted(z["sw"].items(), key=lambda kv: -kv[1]):
            px = pd_ * d
            ki = next((x[2] for x in L if x[3] == nm and abs(x[1] - px) < 1e-6), None)
            lv.append({"k": nm, "label": level_label(nm), "px": round(px, 2),
                       "t": int(M.t[ki]) if ki is not None and ki >= z["k"] and ki >= 0 and nm[:2] not in ("pd", "pw", "pm") else None})
        # inducement swings that count (P["idm_a"] = [max dist ATR, max age bars, min count])
        hi5, lo5, c5, o5 = B5.dirs(d)
        gate = P.get("idm_a") or [9e9, 10 ** 9, 0]
        idm = []
        for dist, age in z.get("idm_a") or []:
            if dist <= gate[0] and age <= gate[1]:
                m = z["sweep_i"] - age
                seg = lo5[m + 1:z["ext_i"] + 1] < lo5[m]
                tk = m + 1 + int(np.argmax(seg)) if seg.any() else None
                idm.append({"t": int(M.t[m]), "px": round(float(lo5[m]) * d, 2), "taken_t": int(M.t[tk]) if tk is not None else None})
        # window: 5m from 2 h before the sweep to 1 h after the exit
        sweep_t = int(M.t[z["sweep_i"]])
        a5 = int(np.searchsorted(M.t, sweep_t - 7200))
        z5 = int(np.searchsorted(M.t, int(t["exit_t"]) + 3600))
        rec_b1 = None
        if use1:
            a1 = int(np.searchsorted(B1.t, w["t0"] - 1200))
            z1 = int(np.searchsorted(B1.t, max(entry_t + 1200, min(int(t["exit_t"]) + 300, entry_t + 3600))))
            rec_b1 = _pack(B1, a1, z1)
        w0, w1 = int(M.t[a5]), int(M.t[z5 - 1]) + 300
        boxes = []
        x = M.ctx[z["k"]]
        for lab, nm, ma, mb in BOXES:
            if nm not in x:
                continue
            hi, lo, ki = x[nm]
            e_t = int(M.t[ki]) + 300
            s_t = e_t - 300 * ((mb - ma) // 5) if mb > ma else e_t
            # exact start = first bar of the box inside the day
            s, e = x["s"], x["e"]
            md = M.mod[s:e]
            ii = np.flatnonzero((md >= ma) & (md < mb))
            ii = ii[md[ii] >= 1080] if ma >= 1080 else ii[md[ii] < 1080]
            if len(ii):
                s_t = int(M.t[s + ii[0]])
            if e_t > w0 and s_t < w1:
                boxes.append({"k": lab, "t0": s_t, "t1": e_t, "hi": round(hi, 2), "lo": round(lo, 2)})
        off = int(dt.datetime.fromtimestamp(entry_t, ET).utcoffset().total_seconds())
        rid = trade_id(t["day"], entry_t, side)
        lim = {"px": round(ep * d, 2), "t0": w["t0"], "t1": w["t0"] + P["wait"] * 300,
               "tap_t": int(B.t[w["tapped"]]) if w["tapped"] is not None else None}
        rec = {
            "id": rid, "day": t["day"], "side": side, "d": d, "tf": int(B.secs // 60), "off": off,
            "qty": q, "risk_usd": round(t["risk_usd"], 2), "risk_pts": round(t["risk_pts"], 2), "pnl": round(t["pnl"], 2),
            "r": round(t["r"], 3), "exit_kind": kind, "entry_kind": "limit" if w["limit_fill"] else ("1m CISD" if B.secs == 60 else "5m CISD"),
            "size_why": t.get("size_why") or [],
            "entry": {"t": entry_t, "px": round(entry * d, 2)},
            "stop": round(stop * d, 2), "target": round(t["target_px"], 2),
            "plan_rr": round((t["target_px"] - t["entry_px"]) * d / t["risk_pts"], 2),
            "target_label": "VIX band" + (" (banked at %gR)" % P["max_rr"] if P.get("max_rr") and abs(tp - P["max_rr"] * risk_plan) < 1e-6 else ""),
            "be": {"t": int(B.t[be_k])} if be_k is not None else None,
            "exit": {"t": int(B.t[xk]), "t_end": int(t["exit_t"]), "px": exit_px, "kind": kind},
            "levels": lv,
            "sweep": {"t": sweep_t, "ext_px": round(z["ext_d"] * d, 2), "ext_t": int(M.t[z["ext_i"]]), "depth_atr": z["depth_atr"]},
            "idm": idm,
            "cisd5": {"px": round(float(z["ref_d"]) * d, 2), "ref_t": int(M.t[z["ref_i"]]), "t": int(M.t[z["i"]]), "disp": z["disp"]},
            "limit": lim,
            "cisd1": ({"px": round(w["cz"][0] * d, 2), "ref_t": int(B.t[w["cz"][1]]), "t": int(B.t[w["conf"]])} if w["cz"] else None),
            "boxes": boxes, "b5": _pack(B5, a5, z5), "b1": rec_b1,
        }
        out[rid] = rec
    if verbose:
        print(f"chart records: {len(out)} trades ({since} .. {until})" + (f", {len(bad)} not matched: {bad[:5]}" if bad else ""))
    if bad:
        raise RuntimeError(f"{len(bad)} trades did not reproduce exactly: {bad[:5]}")
    return out


def unpack(b):
    """packed bars -> list of (t, o, h, l, c) floats (for the PNG tool and tests)."""
    if not b:
        return []
    p0 = b["p0"]
    return [(b["t0"] + b["dt"][i] * b["s"], (p0 + b["o"][i]) / 4, (p0 + b["h"][i]) / 4, (p0 + b["l"][i]) / 4, (p0 + b["c"][i]) / 4)
            for i in range(len(b["dt"]))]


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-01-01")
    ap.add_argument("--out", default=None, help="write the records to this JSON file")
    a = ap.parse_args()
    R = build(a.since)
    if a.out:
        json.dump(R, open(a.out, "w"), separators=(",", ":"))
        print(a.out, os.path.getsize(a.out) // 1024, "KB")
