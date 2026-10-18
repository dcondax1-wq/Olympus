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


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "grid":
        grid()
