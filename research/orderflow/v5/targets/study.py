"""v5 / targets: lane A, same entries (E5), different exits. Pre-registered: research/orderflow/v5/targets/DESIGN.md.

PAPER RESEARCH ONLY: reads data/pc_days summaries + data/NQ_1m.csv, imports nothing that trades.
    python -X utf8 research/orderflow/v5/targets/study.py              # the 51 in-sample days -> results.json
    python -X utf8 research/orderflow/v5/targets/study.py --selftest
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import sys
import zlib

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
TICK, PV, COMM = 0.25, 2.0, 1.90
E5_WAIT_MIN, E5_MKT_TICKS = 5, 18
STOP_SLIP, MKT_SLIP, TGT_THR = 2, 2, 1          # ticks: stop-market fill, market exit, limit target needs 1 tick through
ZONE_SHARE = 0.20
OPP_FRONT, OPP_MIN_R = 2, 1.0
IS_FIRST, IS_LAST = "2026-09-27", "2026-11-26"
N_PERM, N_BOOT = 10_000, 10_000

VARIANTS = {   # id -> exit rule. B2R = the reference (not tested); TS30 = descriptive only
    "B2R": {"tgt": ("R", 2.0)},
    "T1R": {"tgt": ("R", 1.0)},
    "T15R": {"tgt": ("R", 1.5)},
    "T3R": {"tgt": ("R", 3.0)},
    "TOPP": {"tgt": ("opp", None)},
    "TRAIL": {"tgt": None, "trail": True},
    "TS60": {"tgt": ("R", 2.0), "time_min": 60},
    "TS30": {"tgt": ("R", 2.0), "time_min": 30},
}
TESTED = ["T1R", "T15R", "T3R", "TOPP", "TRAIL", "TS60"]


def _load(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


X = _load("v5t_exec", os.path.join(ROOT, "research", "orderflow", "exec_study.py"))


def et_mod(t: int) -> int:
    x = pd.Timestamp(int(t), unit="s", tz="UTC").tz_convert("America/New_York")
    return x.hour * 60 + x.minute


class Path:
    """A day's price path in tick space: 1m NinjaTrader bars + offset, or the day's own 5m summary bars."""
    def __init__(self, t, o, h, l, c, sec):
        self.t = np.asarray(t, np.int64); self.o, self.h, self.l, self.c = (np.asarray(a, float) for a in (o, h, l, c))
        self.sec = int(sec)
        self.idx = {int(x): i for i, x in enumerate(self.t)}
        self.mod = np.array([et_mod(x) for x in self.t]) if len(self.t) else np.array([])

    def at(self, t):
        return self.idx.get(int(t))


def path_1m(M, off, t_lo, t_hi):
    a, b = np.searchsorted(M.t, t_lo), np.searchsorted(M.t, t_hi)
    return Path(M.t[a:b], M.o[a:b] + off, M.h[a:b] + off, M.l[a:b] + off, M.c[a:b] + off, 60)


def path_5m(bars):
    return Path(bars.t, bars.o, bars.h, bars.l, bars.c, 300)


# ------------------------------------------------------------------------------------------------ entry E5
def entry_e5(sig, P: Path):
    d, stop, lv, t0 = sig["d"], sig["stop"], sig["level_px"], sig["t_dec"]
    j0 = P.at(t0)
    if j0 is None:
        return None
    n = max(1, E5_WAIT_MIN * 60 // P.sec)
    for j in range(j0, min(j0 + n, len(P.t))):
        if P.t[j] - t0 > P.sec * n + 120:
            return None
        if j == j0 and (P.o[j] - lv) * d <= 0:
            return (round(P.o[j], 2), j, "open", "marketable")
        thr = (P.h[j] >= lv + TICK) if d == -1 else (P.l[j] <= lv - TICK)
        if thr:
            return (round(lv, 2), j, "intra", "level")
        if (P.h[j] >= stop) if d == -1 else (P.l[j] <= stop):
            return None
    j = j0 + n
    if j >= len(P.t) or P.t[j] - t0 > P.sec * n + 120:
        return None
    px = round(P.o[j] + d * E5_MKT_TICKS * TICK, 2)
    if (px - stop) * d <= 0:
        return None
    return (px, j, "open", "market+18")


# ------------------------------------------------------------------------------------------------ exits
def opp_target(sig, px, risk):
    """Nearest opposite-type level >= 1R in profit, limit 2 ticks in front of it; None = fall back to 2R."""
    d = sig["d"]
    best = None
    for nm, lv, side in sig["levels"]:
        # a short (d=-1) faded a high-type level (side 1): opposite = low-type levels (side -1 = d); a long: high-type (side 1 = d)
        if side != d:
            continue
        tg = lv - d * OPP_FRONT * TICK
        if (tg - px) * d >= OPP_MIN_R * risk and (best is None or (tg - px) * d < (best - px) * d):
            best = tg
    return best


def trail_events(sig, Dy, t_fill):
    """[(effective_t, new_stop)] from each closed 5m bar (from the fill's bar on) absorbed at its stop-side extreme."""
    d = sig["d"]
    b = Dy.bars
    out = []
    t5 = int(t_fill) // 300 * 300
    for i in range(len(b)):
        t = int(b.t.iat[i])
        if t < t5 or b["mod"].iat[i] > 955:
            continue
        z = Dy.zone(t, d)
        if z is None or z[0] <= 0 or not (z[1] * d < 0 and abs(z[1]) >= ZONE_SHARE * z[0]):
            continue
        ext = float(b.high.iat[i]) if d == -1 else float(b.low.iat[i])
        out.append((t + 300, round(ext - d * TICK, 2)))
    return out


def walk(sig, fill, P: Path, vid: str, Dy=None):
    V = VARIANTS[vid]
    d, stop0 = sig["d"], sig["stop"]
    px, j0, how, kind = fill
    risk = (px - stop0) * d
    if risk <= 0:
        return None
    tgt, tkind = None, None
    if V.get("tgt"):
        k, v = V["tgt"]
        if k == "R":
            tgt, tkind = px + d * v * risk, f"{v}R"
        else:
            tgt = opp_target(sig, px, risk)
            tkind = "opp"
            if tgt is None:
                tgt, tkind = px + d * 2.0 * risk, "opp->2R"
    ev = trail_events(sig, Dy, int(P.t[j0])) if V.get("trail") and Dy is not None else []
    n_time = (V["time_min"] * 60 // P.sec) if V.get("time_min") else None
    last_mod = 960 - P.sec // 60
    stop, ei, last = stop0, 0, None
    for j in range(j0, len(P.t)):
        if P.t[j] - P.t[j0] > 8 * 3600 or P.mod[j] > last_mod:
            break
        last = j
        while ei < len(ev) and ev[ei][0] <= P.t[j]:
            if (ev[ei][1] - stop) * d > 0:
                stop = ev[ei][1]
            ei += 1
        hit_stop = (P.l[j] <= stop) if d == 1 else (P.h[j] >= stop)
        if hit_stop:
            gap = j > j0 and (P.o[j] - stop) * d < 0
            base = P.o[j] if gap else stop
            return _book(sig, px, base - d * STOP_SLIP * TICK, "stop" if stop == stop0 else "trail", P.t[j], risk, tkind)
        if j == j0 and how == "intra":
            continue
        if tgt is not None:
            hit_t = (P.h[j] >= tgt + TGT_THR * TICK) if d == 1 else (P.l[j] <= tgt - TGT_THR * TICK)
            if hit_t:
                return _book(sig, px, tgt, "target", P.t[j], risk, tkind)
        if n_time is not None and j - j0 + 1 >= n_time:
            return _book(sig, px, P.c[j] - d * MKT_SLIP * TICK, "time", P.t[j], risk, tkind)
    if last is None:
        return None
    return _book(sig, px, P.c[last] - d * MKT_SLIP * TICK, "flat", P.t[last], risk, tkind)


def _book(sig, px, ex, why, t, risk, tkind):
    pts = (ex - px) * sig["d"]
    return {"fill": round(px, 2), "exit": round(float(ex), 2), "why": why, "exit_t": int(t), "R": round(pts / risk, 4),
            "usd_1": round(pts * PV - COMM, 2), "risk_ticks": round(risk / TICK, 1), "tkind": tkind}


# ------------------------------------------------------------------------------------------------ signals + paths
def load(src=None, only_days=None, exclude_days=None, mode="auto"):
    """Lane A signals (the lane's own replay), each with its levels and a price path. mode: auto (1m if covered) | 5m."""
    days, R, sigs = X.signals(src)
    alld = list(days)                                   # the lane's own day chain (rows >= MIN_ROWS) for the prior day
    V = X._mod_verdict()
    B = V._of_mod("of_battery")
    if only_days is not None:
        days = [d for d in days if d in only_days]
    if exclude_days is not None:
        days = [d for d in days if d not in exclude_days]
    keep = set(days)
    M = None
    if mode == "auto":
        try:
            M = X.load_1m()
        except Exception:  # noqa: BLE001
            M = None
    out, modes, Dys = [], {}, {}
    for d in days:
        k = alld.index(d)
        prev = alld[k - 1] if k and (dt.date.fromisoformat(d) - dt.date.fromisoformat(alld[k - 1])).days <= 4 else None
        D = {d: B.Day(d, R[d])}
        dl = [d]
        if prev:
            D[prev] = B.Day(prev, R[prev]); dl = [prev, d]
        Dys[d] = D[d]
        L = list(B.levels(D, dl, len(dl) - 1))
        bars = D[d].bars
        orb = bars[(bars["mod"] >= 570) & (bars["mod"] < 600)]
        P = None
        if M is not None:
            off, _ = X.day_offset(M, R[d]["bars"])
            if off is not None:
                b = R[d]["bars"]
                P = path_1m(M, off, int(b.t.min()), int(b.t.max()) + 300)
                modes[d] = "1m"
        if P is None:
            P = path_5m(R[d]["bars"]); modes[d] = "5m"
        for s in sigs:
            if s["day"] != d:
                continue
            m = et_mod(s["t_sig"])
            LL = list(L)
            if m >= 600 and len(orb) == 6:
                LL += [("orh", float(orb.high.max()), 1), ("orl", float(orb.low.min()), -1)]
            s = dict(s, levels=LL, level=s["id"].split("|")[-1])
            s["_P"], s["_D"] = P, D[d]
            out.append(s)
    return sorted(keep), out, modes


def score_all(sigs, vids):
    fills = [entry_e5(s, s["_P"]) for s in sigs]
    res = {v: [None if f is None else walk(s, f, s["_P"], v, s["_D"]) for s, f in zip(sigs, fills)] for v in vids}
    return fills, res


# ------------------------------------------------------------------------------------------------ stats
def _dd(xs):
    eq = np.concatenate([[0.0], np.cumsum(xs)])
    return float((np.maximum.accumulate(eq) - eq).max())


def placebo_p(R_all, lab, seed):
    R_all = np.asarray(R_all, float); lab = np.asarray(lab, bool)
    k, N = int(lab.sum()), len(R_all)
    if k == 0 or k == N:
        return None
    obs = R_all[lab].mean()
    rng = np.random.default_rng(seed)
    hits = 0
    for c in range(0, N_PERM, 2000):
        m = min(2000, N_PERM - c)
        idx = np.argsort(rng.random((m, N)), axis=1)[:, :k]
        hits += int((R_all[idx].mean(axis=1) >= obs - 1e-12).sum())
    return round((hits + 1) / (N_PERM + 1), 5)


def boot_p(days_of, R, days, seed=11):
    by = {d: [] for d in days}
    for d, r in zip(days_of, R):
        by[d].append(r)
    keys = list(days)
    rng = np.random.default_rng(seed)
    S = np.array([sum(by[d]) for d in keys]); C = np.array([len(by[d]) for d in keys])
    pick = rng.integers(0, len(keys), (N_BOOT, len(keys)))
    s, c = S[pick].sum(1), C[pick].sum(1)
    mean = np.where(c > 0, s / np.maximum(c, 1), 0)
    return round(float((mean <= 0).mean()), 4)


def holm(ps):
    items = sorted((p, k) for k, p in ps.items() if p is not None)
    m, out, run = len(items), {}, 0.0
    for r, (p, k) in enumerate(items):
        run = max(run, min(1.0, (m - r) * p))
        out[k] = round(run, 5)
    return out


def summarize(vid, sigs, res, days, base=None):
    half = days[(len(days) + 1) // 2 - 1]
    weeks, months = len(days) / 5.0, len(days) / 21.0
    rr = res[vid]
    tk = [i for i, s in enumerate(sigs) if s["taken"] and rr[i] is not None]
    sk = [i for i, s in enumerate(sigs) if not s["taken"] and rr[i] is not None]
    order = sorted(tk, key=lambda i: rr[i]["exit_t"])
    U = np.array([rr[i]["usd_1"] for i in tk], float); Rr = np.array([rr[i]["R"] for i in tk], float)
    pos, neg = U[U > 0].sum(), -U[U < 0].sum()
    halves = []
    for sel in (lambda s: s["day"] <= half, lambda s: s["day"] > half):
        jj = [i for i in tk if sel(sigs[i])]
        out = {"n": len(jj), "mean_R": round(float(np.mean([rr[i]["R"] for i in jj])), 3) if jj else None,
               "usd_1": round(float(sum(rr[i]["usd_1"] for i in jj)), 2)}
        if base is not None:
            out["d_usd_vs_B2R"] = round(out["usd_1"] - float(sum(base[i]["usd_1"] for i in jj)), 2)
        halves.append(out)
    allf = tk + sk
    o = {"trades": len(tk), "trades_per_week": round(len(tk) / weeks, 2),
         "win_pct": round(100 * float((Rr > 0).mean()), 1) if len(tk) else None,
         "mean_R": round(float(Rr.mean()), 3) if len(tk) else None,
         "pf": round(float(pos / neg), 2) if neg > 0 else None,
         "net_usd_1": round(float(U.sum()), 2), "usd_month_1": round(float(U.sum()) / months, 2),
         "max_dd_usd_1": round(_dd([rr[i]["usd_1"] for i in order]), 2), "halves": halves,
         "skipped_n": len(sk), "skipped_mean_R": round(float(np.mean([rr[i]["R"] for i in sk])), 3) if sk else None,
         "exits": {w: sum(1 for i in tk if rr[i]["why"] == w) for w in ("stop", "trail", "target", "time", "flat")},
         "placebo_p": placebo_p([rr[i]["R"] for i in allf], [sigs[i]["taken"] for i in allf], zlib.crc32(b"v5targets")),
         "boot_p_mean_le_0": boot_p([sigs[i]["day"] for i in tk], [rr[i]["R"] for i in tk], days) if tk else None,
         "mean_risk_ticks": round(float(np.mean([rr[i]["risk_ticks"] for i in tk])), 1) if tk else None}
    if vid == "TOPP":
        o["topp_fallback_2R"] = sum(1 for i in tk if rr[i]["tkind"] == "opp->2R")
    if base is not None:
        dR = [rr[i]["R"] - base[i]["R"] for i in tk]; dU = [rr[i]["usd_1"] - base[i]["usd_1"] for i in tk]
        o["vs_B2R"] = {"mean_dR": round(float(np.mean(dR)), 3) if dR else None, "net_d_usd": round(float(sum(dU)), 2),
                       "better_both_halves": all(h.get("d_usd_vs_B2R", 0) > 0 for h in halves)}
    return o


def verdict(o):
    hv = o["halves"]
    both = all(h["n"] and h["mean_R"] is not None and h["mean_R"] > 0 and h["usd_1"] > 0 for h in hv)
    if (o.get("placebo_p") or 1) < 0.05 and (o.get("holm_p") or 1) < 0.10 and both and o["trades"] >= 30:
        return "YES-candidate" + (" (exit edge)" if o.get("vs_B2R", {}).get("better_both_halves") else " (same lane A edge, not an exit edge)")
    if both:
        return "weak"
    return "NO"


def table(out, vids, say=print):
    say("| variant | trades | /wk | win % | mean R | PF | $ 1 micro | $/mo | max DD $ | halves R (n) | halves $ | skipped R | placebo p | Holm p | vs 2R $ | verdict |")
    say("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for v in vids:
        o = out[v]
        h = o["halves"]
        say(f"| {v} | {o['trades']} | {o['trades_per_week']} | {o['win_pct']} | {o['mean_R']:+.3f} | {o['pf']} | {o['net_usd_1']:+,.0f} | "
            f"{o['usd_month_1']:+,.0f} | {o['max_dd_usd_1']:,.0f} | {h[0]['mean_R']:+.2f} ({h[0]['n']}) / {h[1]['mean_R']:+.2f} ({h[1]['n']}) | "
            f"{h[0]['usd_1']:+,.0f} / {h[1]['usd_1']:+,.0f} | {o['skipped_mean_R']} | {o['placebo_p']} | {o.get('holm_p', '-')} | "
            f"{o.get('vs_B2R', {}).get('net_d_usd', 0):+,.0f} | {o.get('verdict', 'reference' if v == 'B2R' else 'descriptive')} |")


def run_is(mode="auto", write=True, say=print):
    days, sigs, modes = load(mode=mode)
    days = [d for d in days if IS_FIRST <= d <= IS_LAST]
    sigs = [s for s in sigs if s["day"] in set(days)]
    vids = ["B2R"] + TESTED + ["TS30"]
    fills, res = score_all(sigs, vids)
    say(f"{len(days)} days {days[0]}..{days[-1]} ({sum(1 for d in days if modes[d] == '1m')} on 1m bars); {len(sigs)} signals, "
        f"taken {sum(s['taken'] for s in sigs)}; E5 fills: taken {sum(1 for s, f in zip(sigs, fills) if s['taken'] and f)} "
        f"({sum(1 for s, f in zip(sigs, fills) if s['taken'] and f and f[3] == 'level')} at the level, "
        f"{sum(1 for s, f in zip(sigs, fills) if s['taken'] and f and f[3] == 'market+18')} market+18)")
    out = {v: summarize(v, sigs, res, days, base=None if v == "B2R" else res["B2R"]) for v in vids}
    H = holm({v: out[v]["placebo_p"] for v in TESTED})
    for v in TESTED:
        out[v]["holm_p"] = H.get(v)
        out[v]["verdict"] = verdict(out[v])
    table(out, vids, say)
    rec = {"made": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "mode": mode, "days": days,
           "modes": modes, "n_signals": len(sigs), "variants": out,
           "rows": [{"id": s["id"], "taken": s["taken"], "fill": None if f is None else f[0], "how": None if f is None else f[3],
                     **{v: (None if res[v][i] is None else {k: res[v][i][k] for k in ("R", "usd_1", "why")}) for v in vids}}
                    for i, (s, f) in enumerate(zip(sigs, fills))]}
    if write:
        p = os.path.join(HERE, "results.json" if mode == "auto" else f"results_{mode}.json")
        json.dump(rec, open(p, "w", encoding="utf-8"), indent=1, default=float)
        say(f"wrote {os.path.relpath(p, ROOT)}")
    return rec


# ------------------------------------------------------------------------------------------------ selftest
def selftest():
    t0 = 1_790_000_000 // 300 * 300
    n = 60
    t = t0 + 60 * np.arange(n)
    o = np.full(n, 100.0); h = o + 0.5; l = o - 0.5; c = o.copy()
    # short at 101 level, stop 103; bar 1 trades through the level -> fill 101; then slide down to 95
    h[1] = 101.5; o[2:] = np.linspace(100, 95, n - 2); c[2:] = o[2:]; h[2:] = o[2:] + 0.25; l[2:] = o[2:] - 0.5
    P = Path(t, o, h, l, c, 60)
    sig = {"d": -1, "stop": 103.0, "level_px": 101.0, "t_dec": int(t0), "levels": [("onl", 96.0, -1), ("pdl", 99.0, -1)]}
    ok = True
    f = entry_e5(sig, P)
    ok &= f is not None and f[0] == 101.0 and f[3] == "level"
    r1 = walk(sig, f, P, "T1R")
    ok &= r1 is not None and r1["why"] == "target" and abs(r1["R"] - 1.0) < 1e-9
    ro = walk(sig, f, P, "TOPP")            # risk 2: pdl 99 -> tg 99.5 = 0.75R (< 1R) -> onl 96 -> tg 96.5
    ok &= ro is not None and ro["why"] == "target" and abs(ro["exit"] - 96.5) < 1e-9
    rt = walk(sig, f, P, "TS30")
    ok &= rt is not None and rt["why"] in ("time", "target")
    sig2 = dict(sig, level_px=102.0)        # never trades through 102 in 5 min -> market + 18 ticks at minute 6 (open lower)
    f2 = entry_e5(sig2, P)
    ok &= f2 is not None and f2[3] == "market+18" and f2[0] < P.o[5]
    print("v5 targets selftest", "OK" if ok else "FAIL", f, r1, ro, rt, f2)
    return bool(ok)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--mode", default="auto", choices=["auto", "5m"])
    a = ap.parse_args(argv)
    if a.selftest:
        return 0 if selftest() else 1
    run_is(a.mode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
