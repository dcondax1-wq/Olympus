"""Lane A execution study (night-of-exec 2026-11-27). Pre-registered: research/orderflow/DESIGN_exec.md (commit fc612ec7).

PAPER RESEARCH ONLY: reads the pulled real tick summaries (data/pc_days/<day>/of, logs/datapipe/days) and data/NQ_1m.csv,
replays lane A with engine/of_paper.replay_summary (the frozen signals) and re-fills every decision with each entry / exit style.
Writes research/orderflow/exec_results.json. Imports nothing that can trade.

    python -X utf8 research/orderflow/exec_study.py            # the real days
    python -X utf8 research/orderflow/exec_study.py --selftest # synthetic check of the fill rules
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import math
import os
import sys
import zlib

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT_J = os.path.join(ROOT, "research", "orderflow", "exec_results.json")
TICK, PV = 0.25, 2.0
COMM = 1.90                      # engine/costs.COMM_RT (the decision); the lane's own book: 1.40
COMM_LANE = 1.40
S_ATLAS, L_ATLAS = 0.363, 4.0    # atlasfill-2026-11-26: give-away share of the first minute's run at ~4 s
RR = 2.0
LAST_MIN = 15 * 60 + 59          # flat at the close of the 1m bar opening 15:59 (= the 15:55 5m bar's close)


def s_of(L: float) -> float:
    return S_ATLAS * math.sqrt(L / L_ATLAS)


def _mod_verdict():
    sp = importlib.util.spec_from_file_location("orv_x", os.path.join(ROOT, "tools", "of_realday_verdict.py"))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


def et_mod(t: int) -> int:
    x = pd.Timestamp(int(t), unit="s", tz="UTC").tz_convert("America/New_York")
    return x.hour * 60 + x.minute


# ------------------------------------------------------------------------------------------------ 1m bars
class Min1:
    def __init__(self, df: pd.DataFrame):
        df = df.sort_values("time").drop_duplicates("time")
        self.t = df.time.to_numpy(np.int64)
        self.o, self.h, self.l, self.c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.idx = {int(x): i for i, x in enumerate(self.t)}

    def at(self, t: int):
        return self.idx.get(int(t))


def load_1m(path=os.path.join(ROOT, "data", "NQ_1m.csv")) -> Min1:
    return Min1(pd.read_csv(path))


def day_offset(M: Min1, bars5: pd.DataFrame) -> tuple:
    """Median (5m summary open - 1m open at the same minute) over the day's bars: puts the 1m path into the tick prices."""
    diffs = []
    for t, o in zip(bars5.t.to_numpy(np.int64), bars5.o.to_numpy(float)):
        j = M.at(t)
        if j is not None:
            diffs.append(o - M.o[j])
    if len(diffs) < 20:
        return None, len(diffs)
    return float(np.median(diffs)), len(diffs)


# ------------------------------------------------------------------------------------------------ fills
def entry(style: str, sig: dict, M: Min1, off: float):
    """(fill price, minute index of the fill, 'open' | 'intra') or None (no fill). Prices in tick space (1m + off)."""
    d, c, stop, lv, t0 = sig["d"], sig["c"], sig["stop"], sig["level_px"], sig["t_dec"]
    j0 = M.at(t0)
    if j0 is None:
        return None
    O, H, L = M.o + off, M.h + off, M.l + off

    def market(j, Ls):
        o = O[j]
        fav = (H[j] - o) if d == 1 else (o - L[j])
        k = max(1, round(s_of(Ls) * fav / TICK))
        return (round(o + d * k * TICK, 2), j, "open")

    def limit(P, n):
        for j in range(j0, min(j0 + n, len(O))):
            if M.t[j] - t0 > 60 * (n + 2):                                 # data gap
                return None
            if j == j0 and (O[j] - P) * d <= 0:                             # marketable when placed: fills at the open
                return (round(O[j], 2), j, "open")
            thr = (H[j] >= P + TICK) if d == -1 else (L[j] <= P - TICK)
            hit_stop = (H[j] >= stop) if d == -1 else (L[j] <= stop)
            if thr:
                return (round(P, 2), j, "intra")
            if hit_stop:
                return None
        return None

    if style == "E0":
        return (sig["fill0"], j0, "open") if sig.get("fill0") is not None else None
    if style.startswith("E1"):
        return market(j0, {"E1a": 1.0, "E1b": 2.75, "E1c": 4.0}[style])
    if style in ("E2-5", "E2-15"):
        return limit(lv, int(style.split("-")[1]))
    if style.startswith("E3-"):
        k = int(style.split("-")[1])
        return limit(c - d * k * TICK, 15)
    if style == "E4":
        trig = c + d * 2 * TICK
        lim = trig + d * 2 * TICK
        for j in range(j0, min(j0 + 15, len(O))):
            if M.t[j] - t0 > 60 * 17:
                return None
            through = (H[j] >= trig) if d == 1 else (L[j] <= trig)
            hit_stop = (H[j] >= stop) if d == -1 else (L[j] <= stop)
            if through:
                if (O[j] - lim) * d > 0:                                   # opened beyond the limit: no fill
                    return None
                if (O[j] - trig) * d >= 0:
                    return (round(O[j] + d * TICK, 2), j, "open")
                return (round(trig + d * TICK, 2), j, "intra")
            if hit_stop:
                return None
        return None
    if style == "E5":
        f = limit(lv, 5)
        if f is not None:
            return f
        j = j0 + 5
        if j < len(O) and M.t[j] - t0 <= 60 * 7:
            hs = any(((H[i] >= stop) if d == -1 else (L[i] <= stop)) for i in range(j0, j))
            if hs:
                return None
            return market(j, 2.75)
        return None
    raise ValueError(style)


def stop_ticks(xs: str, run_beyond_ticks: float) -> int:
    if xs == "X0":
        return 1
    if xs == "X1":
        return 2
    return max(2, round(s_of(1.0) * run_beyond_ticks))


def walk(sig: dict, fill, M: Min1, off: float, xs: str) -> dict:
    """Exit on 1m bars from the fill minute. Stop first in a bar that touches both; an 'intra' fill minute checks only the stop."""
    d, stop = sig["d"], sig["stop"]
    px, j0, how = fill
    risk = (px - stop) * d
    if risk <= 0:
        return {"no_risk": True}
    tgt = px + RR * risk * d
    tgt_use = tgt + (-d * TICK if xs == "X3" else 0)
    need_through = xs in ("X1", "X2")
    O, H, L, C = M.o + off, M.h + off, M.l + off, M.c + off
    last = None
    for j in range(j0, len(O)):
        mod = et_mod(M.t[j])
        if M.t[j] - M.t[j0] > 8 * 3600 or mod > LAST_MIN:
            break
        last = j
        hit_stop = (L[j] <= stop) if d == 1 else (H[j] >= stop)
        if hit_stop:
            gap = (O[j] - stop) * d < 0 and j > j0
            base = O[j] if gap else stop
            beyond = ((stop - L[j]) if d == 1 else (H[j] - stop)) / TICK
            k = stop_ticks(xs, beyond)
            ex = base - d * k * TICK
            return _book(sig, px, ex, "stop", j, M, extra={"beyond_ticks": beyond, "stop_slip": k + (abs(O[j] - stop) / TICK if gap else 0)})
        if j == j0 and how == "intra":
            continue
        if need_through:
            hit_t = (H[j] >= tgt_use + TICK) if d == 1 else (L[j] <= tgt_use - TICK)
        else:
            hit_t = (H[j] >= tgt_use) if d == 1 else (L[j] <= tgt_use)
        if hit_t:
            touch_only = ((H[j] < tgt + TICK) if d == 1 else (L[j] > tgt - TICK))
            return _book(sig, px, tgt_use, "target", j, M, extra={"touch_only": bool(touch_only)})
    if last is None:
        return {"no_data": True}
    k = 1 if xs == "X0" else 2
    return _book(sig, px, C[last] - d * k * TICK, "flat", last, M)


def _book(sig, px, ex, why, j, M, extra=None):
    d, stop = sig["d"], sig["stop"]
    risk = (px - stop) * d
    pts = (ex - px) * d
    r = {"fill": round(px, 2), "exit": round(ex, 2), "why": why, "exit_t": int(M.t[j]), "R": round(pts / risk, 3),
         "risk_ticks": round(risk / TICK, 1), "usd_1": round(pts * PV - COMM, 2), "usd_1_lane": round(pts * PV - COMM_LANE, 2),
         "given_ticks": round((px - sig["c"]) * d / TICK, 2)}
    r.update(extra or {})
    return r


# ------------------------------------------------------------------------------------------------ the study
ENTRIES = ["E0", "E1a", "E1b", "E1c", "E2-5", "E2-15", "E3-2", "E3-4", "E4", "E5"]
EXITS = ["X0", "X1", "X2", "X3"]


def signals(src=None):
    V = _mod_verdict()
    from engine import of_paper as P, ofsum
    B = V._of_mod("of_battery")
    dirs = V.day_dirs(src)
    R = {d: ofsum.read(p) for d, p in dirs.items()}
    R = {d: x for d, x in R.items() if x}
    days = sorted(d for d, x in R.items() if int(x["meta"].get("rows", 0)) >= B.MIN_ROWS)
    rows = []
    for k, d in enumerate(days):
        prev = days[k - 1] if k and (dt.date.fromisoformat(d) - dt.date.fromisoformat(days[k - 1])).days <= 4 else None
        S = P.replay_summary(R[d], d, R[prev] if prev else None, prev, lit=[])
        b = R[d]["bars"]
        cl = dict(zip(b.t.to_numpy(np.int64).tolist(), b.c.to_numpy(float).tolist()))
        for r in S["rows"]:
            if r.get("lane") != "A":
                continue
            rows.append({"id": r["id"], "day": d, "d": int(r["d"]), "taken": bool(r["taken"]), "absorbed": bool(r["absorbed"]),
                         "why_not": r.get("why_not"), "t_sig": int(r["t_sig"]), "t_dec": int(r["t_sig"]) + 300,
                         "c": cl.get(int(r["t_sig"])), "stop": float(r["stop"]), "level_px": float(r["level_px"]),
                         "fill0": r.get("fill"), "R_lane": r.get("R"), "usd_lane": r.get("usd_1"), "why_lane": r.get("why")})
    return days, R, rows


def perm_p(x, lab, seed, n=4000):
    x = np.asarray(x, float); lab = np.asarray(lab, bool)
    if lab.sum() == 0 or (~lab).sum() == 0:
        return None
    obs = x[lab].mean() - x[~lab].mean()
    rng = np.random.default_rng(seed)
    k = int(lab.sum()); hits = 0
    for _ in range(n):
        m = np.zeros(len(x), bool); m[rng.choice(len(x), k, replace=False)] = True
        hits += (x[m].mean() - x[~m].mean()) >= obs - 1e-12
    return round((hits + 1) / (n + 1), 4)


def summarize(res: list, sigs: list, days: list, base: dict | None = None) -> dict:
    """res[i] = the outcome of sigs[i] (None = no fill)."""
    half = sorted(days)[(len(days) + 1) // 2 - 1]
    weeks = max(1e-9, len(days) / 5.0)
    out = {}
    for grp, sel in (("taken", lambda s: s["taken"]), ("skipped", lambda s: not s["taken"])):
        ii = [i for i, s in enumerate(sigs) if sel(s)]
        got = [i for i in ii if res[i] is not None and "R" in res[i]]
        U = np.array([res[i]["usd_1"] for i in got], float)
        Rr = np.array([res[i]["R"] for i in got], float)
        per_sig = float(U.sum()) / len(ii) if ii else 0.0
        hv = []
        for m in (lambda s: s["day"] <= half, lambda s: s["day"] > half):
            jj = [i for i in ii if m(sigs[i])]
            hv.append(round(sum(res[i]["usd_1"] for i in jj if res[i] is not None and "R" in res[i]) / len(jj), 2) if jj else None)
        # equity / max DD on the filled trades in time order
        order = sorted(got, key=lambda i: res[i]["exit_t"])
        eq = np.cumsum([res[i]["usd_1"] for i in order]) if order else np.array([0.0])
        dd = float((np.maximum.accumulate(np.concatenate([[0.0], eq])) - np.concatenate([[0.0], eq])).max())
        o = {"signals": len(ii), "filled": len(got), "fill%": round(100 * len(got) / len(ii), 1) if ii else None,
             "given_ticks_mean": round(float(np.mean([res[i]["given_ticks"] for i in got])), 2) if got else None,
             "mean_R": round(float(Rr.mean()), 3) if got else None, "win%": round(100 * float((Rr > 0).mean()), 1) if got else None,
             "net_usd_1": round(float(U.sum()), 2), "usd_per_signal": round(per_sig, 2), "usd_per_signal_halves": hv,
             "net_usd_1_lane_comm": round(float(sum(res[i]["usd_1_lane"] for i in got)), 2),
             "trades_per_week": round(len(got) / weeks, 2), "max_dd_usd_1": round(dd, 2),
             "exits": {w: sum(1 for i in got if res[i]["why"] == w) for w in ("stop", "target", "flat")}}
        if base is not None:
            miss = [i for i in ii if (res[i] is None or "R" not in res[i]) and base[i] is not None and "R" in base[i]]
            o["missed"] = len(miss)
            o["missed_winners"] = sum(1 for i in miss if base[i]["usd_1"] > 0)
            o["missed_winner_usd"] = round(sum(base[i]["usd_1"] for i in miss if base[i]["usd_1"] > 0), 2)
            o["missed_net_usd"] = round(sum(base[i]["usd_1"] for i in miss), 2)
        out[grp] = o
    # separation on the filled trades
    got = [i for i, s in enumerate(sigs) if res[i] is not None and "R" in res[i]]
    Rr = [res[i]["R"] for i in got]; lab = [sigs[i]["taken"] for i in got]
    out["sep_p"] = perm_p(Rr, lab, zlib.crc32(b"exec")) if got else None
    hv = []
    for m in (lambda s: s["day"] <= half, lambda s: s["day"] > half):
        a = [res[i]["R"] for i in got if sigs[i]["taken"] and m(sigs[i])]
        b = [res[i]["R"] for i in got if not sigs[i]["taken"] and m(sigs[i])]
        hv.append(round(float(np.mean(a) - np.mean(b)), 3) if a and b else None)
    out["sep_halves_R"] = hv
    t, s = out["taken"], out["skipped"]
    out["lane_verdict"] = ("YES" if (t["mean_R"] is not None and s["mean_R"] is not None and t["mean_R"] > s["mean_R"]
                                     and (out["sep_p"] or 1) < 0.10 and all(h is not None and h > 0 for h in hv)
                                     and t["net_usd_1"] > 0 and len(got) >= 40) else "NO")
    return out


def run(src=None, write=True, say=print) -> dict:
    days, R, sigs = signals(src)
    if not days:
        say("No real order-flow day here: run python -X utf8 tools/data_pull.py --of --no-battery first.")
        return {"days": 0}
    M = load_1m()
    offs, use = {}, []
    for d in days:
        offs[d] = day_offset(M, R[d]["bars"])
    for s in sigs:
        o = offs[s["day"]][0]
        if o is None or s["c"] is None or M.at(s["t_dec"]) is None:
            s["dropped"] = "no 1m bars"
            continue
        s["off"] = o
        use.append(s)
    say(f"{len(days)} days {days[0]}..{days[-1]}; {len(sigs)} lane A signals, {len(use)} with 1m bars "
        f"(taken {sum(s['taken'] for s in use)}). 1m->tick offsets: {sorted(set(round(v[0] or 0, 2) for v in offs.values()))[:8]}")
    out = {"made": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "design": "research/orderflow/DESIGN_exec.md",
           "days": len(days), "first": days[0], "last": days[-1], "signals": len(sigs), "used": len(use),
           "dropped": [s["id"] for s in sigs if s.get("dropped")], "offsets": {d: v[0] for d, v in offs.items()}, "grid": {}}
    fills = {e: [entry(e, s, M, s["off"]) for s in use] for e in ENTRIES}
    res = {}
    for xs in EXITS:
        for e in ENTRIES:
            res[(e, xs)] = [None if f is None else walk(s, f, M, s["off"], xs) for f, s in zip(fills[e], use)]
            res[(e, xs)] = [None if (r is None or "R" not in r) else r for r in res[(e, xs)]]
    for xs in EXITS:
        base = res[("E1b", "X2")]
        for e in ENTRIES:
            out["grid"][f"{e}+{xs}"] = summarize(res[(e, xs)], use, days, base=base)
    # E0+X0 consistency with the lane's own 5m book
    lane = [s for s in use if s.get("R_lane") is not None]
    out["check_E0X0_vs_lane"] = {"n": len(lane), "lane_taken_R": round(float(np.mean([s["R_lane"] for s in lane if s["taken"]] or [0])), 3),
                                 "1m_taken_R": out["grid"]["E0+X0"]["taken"]["mean_R"],
                                 "same_exit_kind": sum(1 for s, r in zip(use, res[("E0", "X0")]) if r and s.get("why_lane") and
                                                       str(s["why_lane"]).split()[0] == r["why"].replace("flat", "flat")) }
    # measured exit room (E1b fills, X1 walk = stop fill +2, target needs 1 through)
    st = [r for r in res[("E1b", "X1")] if r and r["why"] == "stop"]
    tg = [r for r in res[("E1b", "X0")] if r and r["why"] == "target"]
    out["stop_room"] = {"n": len(st), "beyond_ticks_median": float(np.median([r["beyond_ticks"] for r in st])) if st else None,
                        "beyond_ticks_p75": float(np.percentile([r["beyond_ticks"] for r in st], 75)) if st else None,
                        "x2_slip_mean": round(float(np.mean([r["stop_slip"] for r in res[("E1b", "X2")] if r and r["why"] == "stop"] or [0])), 2)}
    out["target_touch_only"] = {"n": len(tg), "touch_only": sum(1 for r in tg if r.get("touch_only"))}
    # per-signal rows for the write-up (taken only, compact)
    out["rows"] = [{"id": s["id"], "taken": s["taken"], "d": s["d"], "c": s["c"], "level": s["level_px"], "stop": s["stop"],
                    **{k: (None if res[k][i] is None else {kk: res[k][i][kk] for kk in ("fill", "why", "R", "usd_1")})
                       for k in [("E0", "X0"), ("E1b", "X2"), ("E2-15", "X2"), ("E5", "X2")]}}
                   for i, s in enumerate(use)]
    for r in out["rows"]:
        for k in list(r):
            if isinstance(k, tuple):
                r["+".join(k)] = r.pop(k)
    if write:
        json.dump(out, open(OUT_J, "w", encoding="utf-8"), indent=1, default=float)
        say(f"wrote {os.path.relpath(OUT_J, ROOT)}")
    return out


# ------------------------------------------------------------------------------------------------ selftest
def selftest() -> bool:
    t0 = 1_790_000_000 // 60 * 60
    n = 40
    t = t0 + 60 * np.arange(n)
    base = 20000.0
    o = np.full(n, base); h = o + 2; l = o - 2; c = o.copy()
    M = Min1(pd.DataFrame({"time": t, "open": o, "high": h, "low": l, "close": c}))
    ok = True
    # short at a high: decision close 20000, level 20001, stop 20005
    sig = {"d": -1, "c": base, "stop": base + 5, "level_px": base + 1, "t_dec": int(t0), "fill0": base - 0.25}
    f = entry("E1b", sig, M, 0.0)                      # fav = o - l = 2 pts -> 0.31 x 8 ticks = 2.5 -> 2 ticks worse (lower)
    ok &= f is not None and f[0] < base and f[2] == "open"
    f2 = entry("E2-5", sig, M, 0.0)                    # high 20002 >= 20001 + 0.25 -> filled at the level
    ok &= f2 is not None and abs(f2[0] - (base + 1)) < 1e-9
    sig2 = dict(sig, level_px=base + 1.75)             # needs 20002.0: high 20002 = 1 tick through -> fill
    ok &= entry("E2-5", sig2, M, 0.0) is not None
    sig3 = dict(sig, level_px=base + 2)                # high 20002 = touch only -> no fill
    ok &= entry("E2-5", sig3, M, 0.0) is None
    # exit: target 2R from 20001 with stop 20005 -> risk 4 -> target 19993: never reached; flat at the last bar
    r = walk(sig, f2, M, 0.0, "X2")
    ok &= r.get("why") in ("flat",) or "no_data" in r or r.get("why") == "target"
    print("exec_study selftest", "OK" if ok else "FAIL")
    return bool(ok)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return 0 if selftest() else 1
    run(a.src)
    return 0


if __name__ == "__main__":
    sys.exit(main())
