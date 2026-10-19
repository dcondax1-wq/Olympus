"""LIT all hours (owner, 2026-10-18: "The bot should ALWAYS be looking for trades based off LIT. We should be trading all of LIT.").

CME NQ trades 18:00 ET Sunday-Friday to 17:00 ET (1-hour halt). The live LIT enters 02:00-15:30, 1 trade a day, flat 15:55.
This study runs the exact live LIT (live_model.json "lit": 1m CISD entries, stop 1 tick beyond the sweep extreme, VIX-band
target, BE 1R, Monday rule, weekly stop) through engine/lit.py run_x with the default-off all-hours options:
  candidates(evening=True)  setups on the whole trading day (from 18:30 ET), in trading-day order
  all_hours                 executor in trading-day order: an 18:00-02:00 entry is held at most to 15:55 of the same trading day
                            (never through the 17:00 halt; MFFU: flat before the 16:10 close)
  per_session               max trades per Asia (18:00-02:00) / London (02:00-08:00) / NY (08:00-17:00) session
  stop_after_loss           no new trade that day after a STOP exit (a later one only after a TARGET / BE = re-arming)
One trade at a time, the next one only after the previous exited.

Scoring: money at the LIT rule size + the weekly stop (= run lit_live), costs in; the MFFU Builder 50K 2-week eval under
lit_sizing mode two_week (config C, run lit_2wk_rec; tools/lit_2wk.py run_eval, exact MFFU rules) on a fresh eval started on
every session of the half, plus its 4,000-path Monte Carlo. Pick on 2026 H1, check on H2; 2021-25 is a reference line (no 1m).

  python tools/lit_all_hours.py check    # evening candidates + live window == run lit_live (120 trades 2026)
  python tools/lit_all_hours.py grid     # every variant -> research/lit/all_hours.json
  python tools/lit_all_hours.py save     # rl.save the runs lit_hours_*
1 process. Paper only.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import pickle
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_2wk as W  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "all_hours.json")
CACHE = os.path.join(ROOT, "research", "runs", "_cache")
LIVE = {**lit.DEFAULTS, **json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]}
SESS = F.SESS
TW = {**W.NEED, "room_f": 0.6, "wk": False}          # lit_sizing two_week = config C (run lit_2wk_rec)

# windows (entry-bar ET minutes)
WIN = {
    "live": [[120, 930]],                              # 02:00-15:30
    "full": [[1080, 1440], [0, 930]],                  # 18:00-15:30
    "asia_only_add": [[1080, 1440], [0, 120]],         # 18:00-02:00 only (the added part on its own)
    "w19": [[1140, 1440], [0, 930]],                   # 19:00-15:30
    "w20": [[1200, 1440], [0, 930]],                   # 20:00-15:30 (after the Asia box starts)
    "w00": [[0, 930]],                                 # 00:00-15:30
    "late": [[120, 950]],                              # 02:00-15:50 (15:30-16:00 extension; flat stays 15:55)
    "full_late": [[1080, 1440], [0, 950]],             # 18:00-15:50
}
SESS3 = [[1080, 120], [120, 480], [480, 1080]]
COUNT = {
    "1day": {},
    "1sess": {"max_per_day": 3, "per_session": [SESS3, 1]},
    "1sess_sal": {"max_per_day": 3, "per_session": [SESS3, 1], "stop_after_loss": True},
    "2day_sal": {"max_per_day": 2, "stop_after_loss": True},
    "2day": {"max_per_day": 2},
    "rearm_sal": {"max_per_day": 9, "stop_after_loss": True},
    "rearm": {"max_per_day": 9},
    "asia_plus": {"max_per_day": 2, "per_session": [[[1080, 120], [120, 1080]], 1]},   # 1 Asia + the live day trade
    "asia_plus_sal": {"max_per_day": 2, "per_session": [[[1080, 120], [120, 1080]], 1], "stop_after_loss": True},
}


def market():
    M, _ = F.market("cisd", ())
    p = os.path.join(CACHE, f"litallhours_v1_cisd_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p):
        C = pickle.load(open(p, "rb"))
    else:
        C = lit.candidates(M, ref="cisd", evening=True)
        pickle.dump(C, open(p, "wb"))
    return M, C


def P_of(win="live", count="1day", extra=None):
    P = {**LIVE, "window": WIN[win], **COUNT[count], **(extra or {})}
    if win not in ("live", "late", "w00"):
        P["all_hours"] = True
    return P


def run(P):
    M, C = market()
    return lit.run_x(M, C, P, SESS, B1=F.bars(M, "1m"), B5=F.bars(M, "5m"))


# ------------------------------------------------------------------------------------------------ scoring
def unit(T):
    """run_x trades -> tools/lit_2wk unit trades (per micro, exact: P&L, slippage and commission are linear in micros)."""
    U = []
    for t in T:
        q = t["qty"]
        U.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "risk": t["risk_pts"],
                  "tgt": round(abs(t["target_px"] - t["entry_px"]), 2), "pts": (t["pnl"] + lit.COMM * q) / (lit.PV * q),
                  "w1": (t["low"] + lit.COMM * q) / (lit.PV * q), "exit": t["exit"], "wk_m": t.get("size_mult", 1.0),
                  "tf": t["tf"]})
    return U


def eval2wk(T, key):
    U = unit(T)
    by = collections.defaultdict(list)
    for t in U:
        by[t["day"]].append(t)
    W._D[key] = {"sess": SESS, "by": [by.get(s, []) for s in SESS], "trades": U,
                 "dow": np.array([dt.date.fromisoformat(s).weekday() for s in SESS])}
    o = {}
    for s in ("H1", "H2", "2026", "2021-25"):
        o[s] = W.exact(TW, s, key)
    for s in ("H1", "H2"):
        o["mc_" + s] = W.mc(TW, s, key)
    return o


def money(T):
    o = F.score(T)
    for nm, (a, z) in F.SPAN.items():
        dd = collections.defaultdict(float)
        for t in T:
            if a <= t["day"] <= z:
                dd[t["day"]] += t["pnl"]
        o[nm]["worst_day"] = round(min(dd.values())) if dd else 0
        TT = [t for t in T if a <= t["day"] <= z]
        o[nm]["n_evening"] = sum(1 for t in TT if (lit_mod(t["entry_t"]) >= 1080 or lit_mod(t["entry_t"]) < 120))
        o[nm]["n_extra"] = 0
    return o


def lit_mod(ts):
    import pandas as pd
    x = pd.Timestamp(int(ts), unit="s", tz="UTC").tz_convert("America/New_York")
    return x.hour * 60 + x.minute


def variant(win, count, extra=None):
    key = f"{win}|{count}" + (("|" + json.dumps(extra, sort_keys=True)) if extra else "")
    T = run(P_of(win, count, extra))
    return key, T, {"money": money(T), "eval": eval2wk(T, key)}


def line(key, o):
    m, e = o["money"], o["eval"]
    f = lambda s: (f"n {m[s]['n']} tpw {m[s]['tpw']} PF {m[s]['pf']} net {m[s]['net']:+,} 2wk {e[s]['p10']}/{e[s]['f10']}")
    return f"{key:28s} H1[{f('H1')}] H2[{f('H2')}] ref21-25 PF {m['2021-25']['pf']} {m['2021-25']['net']:+,}"


def check():
    T = run(P_of())
    r = rl.load("lit_live")
    Tr = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
    a = {(t["day"], int(t["entry_t"])): round(t["pnl"], 2) for t in Tr if t["day"] >= "2026"}
    b = {(t["day"], int(t["entry_t"])): round(t["pnl"], 2) for t in T if t["day"] >= "2026"}
    same = sum(1 for k in a if k in b and abs(a[k] - b[k]) < 0.02)
    print(f"lit_live 2026 {len(a)} trades {sum(a.values()):+,.0f} | evening candidates + live window {len(b)} "
          f"{sum(b.values()):+,.0f} | identical {same}", flush=True)
    e = eval2wk(T, "chk")
    print("two_week C:", {s: (e[s]["p10"], e[s]["f10"]) for s in e}, flush=True)


def grid(jobs=None):
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    jobs = jobs or ([(w, "1day") for w in WIN] + [("live", c) for c in COUNT if c != "1day"] +
                    [("full", c) for c in COUNT if c != "1day"] + [("w20", c) for c in COUNT if c != "1day"])
    for win, count, *ex in jobs:
        key = f"{win}|{count}" + (("|" + json.dumps(ex[0], sort_keys=True)) if ex else "")
        if key in res:
            continue
        key, T, o = variant(win, count, ex[0] if ex else None)
        res[key] = o
        json.dump(res, open(OUT, "w"), indent=1, default=float)
        print(line(key, o), flush=True)
    return res


# ------------------------------------------------------------------------------------------------ owner's F-BoS notes
def market_bu():
    """Evening candidates with the previous trading day's 16:30-17:00 build-up box as an extra liquidity level (class
    "bu1630", known from the 18:00 open on), so a false break of one side at the 18:00 open is a LIT sweep. Research only:
    Market.levels is wrapped on this instance (engine untouched)."""
    M, _ = F.market("cisd", ())
    p = os.path.join(CACHE, f"litallhours_bu1630_v1_cisd_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p):
        return M, pickle.load(open(p, "rb"))
    orig = M.levels
    def levels(k):
        L = orig(k)
        if k > 0:
            ps, pe = M.days[k - 1][1], M.days[k - 1][2]
            ii = [i for i in range(max(ps, pe - 12), pe) if 990 <= M.mod[i] < 1020]
            if len(ii) >= 2:
                s = M.days[k][1]
                L.append(("high", float(M.h[ii].max()), s - 1, "bu1630_h", "bu1630"))
                L.append(("low", float(M.l[ii].min()), s - 1, "bu1630_l", "bu1630"))
        return L
    M.levels = levels
    try:
        C = lit.candidates(M, ref="cisd", evening=True)
    finally:
        M.levels = orig
    pickle.dump(C, open(p, "wb"))
    return M, C


def _evening(z):
    return z["mod"] >= 1080 or z["mod"] < 120


def cycle_dir(M, C):
    """The LIT cycle running before the Asia open: the direction of the previous trading day's last LIT setup that passed the
    live filters (any time of that day), per trading day."""
    P = {**LIVE, "window": [[0, 1440]]}
    last = {}
    for z in C:
        if not _evening(z) and lit.setup_ok(z, P):
            last[z["day"]] = z["dir"]
    days = [d for d, _, _ in M.days]
    return {days[i]: last.get(days[i - 1]) for i in range(1, len(days))}


def fbos_variant(kind, count="1day"):
    """kind: fbos     = live 02:00-15:30 setups + 18:00-20:00 setups that swept the 16:30-17:00 build-up (F-BoS -> Asia run)
             fbos_all = the same with the F-BoS setups allowed 18:00-02:00
             cycle    = live setups + 18:00-02:00 setups only in the direction of the LIT cycle before the Asia open
             fbos_cycle = F-BoS setups (18:00-20:00) + otherwise cycle-direction setups 18:00-02:00
    Same executor (all_hours, window 18:00-15:30), first come first served, one trade at a time."""
    M, C = market()
    Mb, Cb = market_bu()
    base = [z for z in C if not _evening(z)]
    fb = [z for z in Cb if _evening(z) and "bu1630" in z["swept_cls"]]
    fb20 = [z for z in fb if 1080 <= z["mod"] < 1200]
    cyc = cycle_dir(M, C)
    ev_cyc = [z for z in C if _evening(z) and cyc.get(z["day"]) == z["dir"]]
    if kind == "fbos":
        CC = base + fb20
    elif kind == "fbos_all":
        CC = base + fb
    elif kind == "cycle":
        CC = base + ev_cyc
    elif kind == "fbos_cycle":
        fb_days = {z["day"] for z in fb20}
        CC = base + fb20 + [z for z in ev_cyc if z["day"] not in fb_days]
    else:
        raise ValueError(kind)
    CC.sort(key=lambda z: (z["entry_t"], -z["dir"]))
    P = P_of("full", count)
    T = lit.run_x(M, CC, P, SESS, B1=F.bars(M, "1m"), B5=F.bars(M, "5m"))
    key = f"{kind}|{count}"
    n_fb = sum(1 for z in fb20 if z["day"] >= "2026")
    o = {"money": money(T), "eval": eval2wk(T, key), "n_fbos_setups_2026": n_fb}
    return key, T, o


def fbos_grid(jobs=(("fbos", "1day"), ("fbos_all", "1day"), ("cycle", "1day"), ("fbos_cycle", "1day"))):
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    for kind, count in jobs:
        key = f"{kind}|{count}"
        if key in res:
            continue
        key, T, o = fbos_variant(kind, count)
        res[key] = o
        json.dump(res, open(OUT, "w"), indent=1, default=float)
        print(line(key, o), "| F-BoS setups 2026:", o["n_fbos_setups_2026"], flush=True)


# ------------------------------------------------------------------------------------------------ trendline / channel liquidity
def market_ts():
    """Evening candidates with trendline/channel liquidity ("TS", owner's notes) as an extra level class "ts": a 5m fractal low
    whose two previous fractal lows and two previous fractal highs are each lower than the one before (a falling channel's
    last low), known 2 bars after the swing (fractal confirmation); mirror for a rising channel's last high. Sweeping it and
    running the other way is then a LIT setup. Research only (Market.levels wrapped on this instance)."""
    M, _ = F.market("cisd", ())
    p = os.path.join(CACHE, f"litallhours_ts_v1_cisd_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p):
        return M, pickle.load(open(p, "rb"))
    import bisect
    fl, fh = np.asarray(M.fl), np.asarray(M.fh)
    orig = M.levels

    def chan(k):
        s, e = M.days[k][1], M.days[k][2]
        L = []
        for side, F_, O_, arr, oarr in (("low", fl, fh, M.l, M.h), ("high", fh, fl, M.h, M.l)):
            sg = 1 if side == "low" else -1          # falling channel for lows (lower lows, lower highs); rising for highs
            a, z = bisect.bisect_left(F_, s - 72), bisect.bisect_left(F_, e)
            for q in range(max(a, 2), z):
                m = int(F_[q]); p1, p2 = int(F_[q - 1]), int(F_[q - 2])
                if not (sg * arr[m] < sg * arr[p1] < sg * arr[p2]):
                    continue
                j = bisect.bisect_left(O_, m) - 1
                if j < 1:
                    continue
                h1, h2 = int(O_[j]), int(O_[j - 1])
                if not (sg * oarr[h1] < sg * oarr[h2]) or m - p2 > 72:
                    continue
                L.append((side, float(arr[m]), m + 2, "ts_" + side[0], "ts"))
        return L

    def levels(k):
        return orig(k) + chan(k)
    M.levels = levels
    try:
        C = lit.candidates(M, ref="cisd", evening=True)
    finally:
        M.levels = orig
    pickle.dump(C, open(p, "wb"))
    return M, C


def ts_grid(jobs=(("live", "1day"), ("full", "1day"), ("live", "rearm_sal"))):
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    M, _ = market()
    _, Cts = market_ts()
    for win, count in jobs:
        key = f"ts|{win}|{count}"
        if key in res:
            continue
        T = lit.run_x(M, Cts, P_of(win, count), SESS, B1=F.bars(M, "1m"), B5=F.bars(M, "5m"))
        o = {"money": money(T), "eval": eval2wk(T, key),
             "n_ts_trades_2026": sum(1 for t in T if t["day"] >= "2026" and any(x.startswith("ts_") for x in t["swept"]))}
        res[key] = o
        json.dump(res, open(OUT, "w"), indent=1, default=float)
        print(line(key, o), "| trades sweeping a TS level 2026:", o["n_ts_trades_2026"], flush=True)


def trades_of(key):
    """Re-run the trades of a stored variant key (window|count, fbos kind|count, ts|window|count)."""
    parts = key.split("|")
    if parts[0] in ("fbos", "fbos_all", "cycle", "fbos_cycle"):
        return fbos_variant(parts[0], parts[1])[1], P_of("full", parts[1])
    if parts[0] == "ts":
        M, _ = market()
        _, Cts = market_ts()
        P = P_of(parts[1], parts[2])
        return lit.run_x(M, Cts, P, SESS, B1=F.bars(M, "1m"), B5=F.bars(M, "5m")), P
    P = P_of(parts[0], parts[1])
    return run(P), P


def save(picks):
    """picks: [(run id, variant key, status, title, why)]: store each with its trades at the LIT size."""
    res = json.load(open(OUT))
    for rid, key, status, title, why in picks:
        T, P = trades_of(key)
        o = res[key]
        m, e = o["money"], o["eval"]
        h = lambda s: (f"{s}: {m[s]['n']} trades, {m[s]['tpw']}/wk, win {m[s]['win']}%, PF {m[s]['pf']}, net ${m[s]['net']:+,} "
                       f"(${m[s]['per_month']:,}/mo), DD ${m[s]['dd']:,}, worst day ${m[s]['worst_day']:,}; two_week eval 2-wk "
                       f"pass/fail {e[s]['p10']}/{e[s]['f10']}")
        verdict = (why + " " + "; ".join(h(s) for s in ("H1", "H2", "2026")) +
                   f"; Monte Carlo 2-wk H1 {e['mc_H1']['p10']}/{e['mc_H1']['f10']}, H2 {e['mc_H2']['p10']}/{e['mc_H2']['f10']}; "
                   f"2021-25 reference (5m) PF {m['2021-25']['pf']} ${m['2021-25']['net']:+,}.")
        rl.save(rid, title, "sessions", "Owner order 2026-10-18: the bot should always be looking for LIT trades (CME trades "
                "18:00-17:00 ET): entry window, trades per day / session, re-arming after a target or breakeven.",
                params={"variant": key, **{k: P[k] for k in ("window", "all_hours", "per_session", "stop_after_loss", "max_per_day")}},
                sizing={"money": "LIT rule $800/20 + weekly stop (= lit_live)", "eval": {"mode": "two_week", **TW}},
                trades=T, scored=rl.score(T, SESS), status=status, verdict=verdict,
                notes="tools/lit_all_hours.py (engine/lit.py candidates(evening=True) + run_x options all_hours / per_session / "
                      "stop_after_loss). Eval numbers (exact MFFU 50K, two_week config C) in the verdict and in "
                      "research/lit/all_hours.json; the run library's own eval columns use the LIT size. eval=" +
                      json.dumps(e, default=float), writeup="lit-all-hours", tags=["lit", "lit_hours"])
        print("saved", rid, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "grid":
        grid()
    elif cmd == "fbos":
        fbos_grid()
