"""ICT 2022 Mentorship model (research/lab/M22_RULES.md), straight rules on 5m NQ or ES futures.

  1 bias      daily draw on liquidity from the prior daily candle vs the one before it (close beyond its H/L = continue,
              swept its H/L and closed back inside = reverse, otherwise no bias = no trade)
  2 time      killzones 08:30-11:00 and 13:30-15:55 ET; the raid, the MSS and the fill all happen inside one killzone
  3 raid      a 5m bar trades >= 1 tick through an untaken pool: PDH/PDL, Asia H/L (20:00-00:00), London H/L
              (02:00-05:00), or a 15m short-term swing high/low of the current session
  4 MSS       a 5m candle CLOSES beyond the last 5m short-term swing (3-candle fractal) that formed before the raid
              extreme, i.e. the swing that started the move into the raid
  5 displace  the leg from the raid extreme through the MSS candle (+1 bar) must leave a fair value gap; no FVG = no trade
  6 entry     limit at the near edge of the FIRST FVG of that leg (bull: candle-3 low; bear: candle-3 high); fills only
              if a later bar trades through it by 1 tick
  7 stop      1 tick beyond the raid extreme
  8 target    nearest untaken opposite pool (same pool set as rule 3) beyond the entry; none -> -2 SD projection of the
              manipulation leg (swing that started the move -> raid extreme). Variant: fixed 2R.
  9 cancel    unfilled at the end of the killzone, target traded before the fill, or a newer setup arms
 10 risk      $350 fixed, max 2 trades/day, done after a winner or 2 losers, daily stop -$700, flat 15:55 ET

Causal: decisions on closed 5m bars; a limit armed at bar k's close can fill from bar k+1. On the fill bar only the stop
is checked (stop first); from the next bar stop is checked before target. Last unfinished trade -> exit_kind 'open'.
"""
from __future__ import annotations

import collections
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.strategy_lab import make_trade, size  # noqa: E402

NAME = "ict2022"
TICK = 0.25

PARAMS = {
    "sym": "NQ",
    "windows": [[510, 660], [810, 955]],   # ET minutes [start, end): 08:30-11:00 AM, 13:30-15:55 PM killzones
    "bias": True,                 # rule 1 on/off (variant)
    "pools": ["PD", "AS", "LO", "S15"],   # prior day, Asia, London, 15m short-term swings of the session
    "sweep_ticks": 1,             # raid = trade >= N ticks through the pool
    "entry": "edge",              # edge (first touch of the FVG) | ce (50% of the FVG)
    "stop_ticks": 1,              # beyond the raid extreme
    "fill_ticks": 1,              # limit fills only on a trade-through of N ticks
    "target": "liq",              # liq (opposite pool, -SD fallback) | rr (fixed R)
    "sd": 2.0,                    # standard-deviation projection used when no pool is left
    "rr": 2.0,
    "target_ticks": 1,            # limit target needs a trade-through of N ticks
    "flat_mod": 950,              # flat at the close of the 15:50 bar (= 15:55 ET)
    "max_trades_day": 2,
    "max_losses_day": 2,
    "stop_after_win": True,
    "daily_stop": -700.0,
    "risk_usd": 350.0,
}

AS_W = (1200, 1440)   # 20:00-00:00 ET (evening part of the trading day)
LO_W = (120, 300)     # 02:00-05:00 ET


def _bounds(day):
    cut = np.flatnonzero(day[1:] != day[:-1]) + 1
    s = np.r_[0, cut]
    e = np.r_[cut, len(day)]
    return list(zip(day[s], s, e))


def _bias(prev1, prev2):
    """prev = (high, low, close) of the daily (18:00-17:00) candle. Returns +1, -1 or 0 (no bias)."""
    if prev1 is None or prev2 is None:
        return 0
    h1, l1, c1 = prev1
    h2, l2, _ = prev2
    if c1 > h2:
        return 1
    if c1 < l2:
        return -1
    up, dn = h1 > h2, l1 < l2
    if up and not dn:
        return -1
    if dn and not up:
        return 1
    return 0


def _swings15(t, h, l, a, b):
    """15m short-term swings of the session [a, b): list of (price, side, avail_idx). A 15m fractal at m is confirmed when
    15m bar m+1 completes (its last 5m bar), and can be raided from the following 5m bar."""
    bk = t[a:b] // 900
    cut = np.flatnonzero(bk[1:] != bk[:-1]) + 1
    s = np.r_[0, cut] + a
    e = np.r_[cut, len(bk)] + a          # exclusive end (5m index) of each 15m bar
    H = np.array([h[x:y].max() for x, y in zip(s, e)])
    L = np.array([l[x:y].min() for x, y in zip(s, e)])
    out = []
    for m in range(1, len(H) - 1):
        avail = e[m + 1]                 # first 5m bar after 15m bar m+1 completed
        if avail >= b:
            break
        if H[m] > H[m - 1] and H[m] > H[m + 1]:
            out.append((float(H[m]), "H", int(avail), "S15H"))
        if L[m] < L[m - 1] and L[m] < L[m + 1]:
            out.append((float(L[m]), "L", int(avail), "S15L"))
    return out


def _session_pools(mod, h, l, a, b, name, w):
    m = (mod[a:b] >= w[0]) & (mod[a:b] < w[1]) if w[0] < w[1] else None
    idx = np.flatnonzero(m) + a
    if len(idx) == 0:
        return []
    avail = int(idx[-1]) + 1
    if avail >= b:
        return []
    return [(float(h[idx].max()), "H", avail, name + "H"), (float(l[idx].min()), "L", avail, name + "L")]


def _sim(df, p, keep_state=False):
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    t = df["time"].to_numpy(np.int64)
    mod = df["mod"].to_numpy(int)
    day = df["day"].to_numpy()
    n = len(c)
    sym = p["sym"]
    st_h = np.zeros(n, bool)   # 5m short-term swing high at s (needs s+1)
    st_l = np.zeros(n, bool)
    st_h[1:-1] = (h[1:-1] > h[:-2]) & (h[1:-1] > h[2:])
    st_l[1:-1] = (l[1:-1] < l[:-2]) & (l[1:-1] < l[2:])
    wins = [tuple(w) for w in p["windows"]]
    sw, tk = p["sweep_ticks"] * TICK, TICK

    def win_of(m):
        for k, (x, y) in enumerate(wins):
            if x <= m < y:
                return k
        return -1

    trades, last_state = [], {}
    dbg = collections.Counter()
    daily = []
    bnds = _bounds(day)
    for di, (dname, a, b) in enumerate(bnds):
        daily.append((float(h[a:b].max()), float(l[a:b].min()), float(c[b - 1])))
        prev1 = daily[di - 1] if di >= 1 else None
        prev2 = daily[di - 2] if di >= 2 else None
        bias = _bias(prev1, prev2) if p["bias"] else 0
        allowed = {1, -1} if not p["bias"] else ({bias} if bias else set())
        # ---- liquidity pools for the day: [price, side, avail_idx, name, taken]
        pools = []
        if "PD" in p["pools"] and prev1 is not None:
            pools += [(prev1[0], "H", a, "PDH"), (prev1[1], "L", a, "PDL")]
        if "AS" in p["pools"]:
            pools += _session_pools(mod, h, l, a, b, "AS", AS_W)
        if "LO" in p["pools"]:
            pools += _session_pools(mod, h, l, a, b, "LO", LO_W)
        if "S15" in p["pools"]:
            pools += _swings15(t, h, l, a, b)
        pools = [[pr, sd, av, nm, False] for pr, sd, av, nm in pools]
        n_tr, n_loss, pnl_day, done = 0, 0, 0.0, False
        cand = {1: None, -1: None}      # raid candidates per direction
        pend = None                     # armed limit order
        pos = None                      # open position
        for i in range(a, b):
            m = mod[i]
            wk = win_of(m)
            # ------------------------------------------------ 1) open position: stop first, then target, then time
            if pos is not None:
                d = pos["dir"]
                adv = (pos["entry"] - l[i]) if d == 1 else (h[i] - pos["entry"])
                pos["mae"] = max(pos["mae"], adv)
                ex = None
                if (d == 1 and l[i] <= pos["stop"]) or (d == -1 and h[i] >= pos["stop"]):
                    ex = (pos["stop"], "stop")
                elif i > pos["fill_i"] and ((d == 1 and h[i] >= pos["target"] + p["target_ticks"] * tk) or
                                            (d == -1 and l[i] <= pos["target"] - p["target_ticks"] * tk)):
                    ex = (pos["target"], "target")
                elif m >= p["flat_mod"] and m < 1020:
                    ex = (c[i], "time")
                if ex is not None:
                    tr = make_trade(t[pos["fill_i"]], t[i] + 300, d, pos["entry"], pos["stop"], ex[0], ex[1],
                                    setup=pos["setup"], mae_pts=pos["mae"], sym=sym, risk_usd=p["risk_usd"],
                                    entry_kind="limit", target=pos["target"], tgt_kind=pos["tgt_kind"],
                                    sess=pos["sess"], pool=pos["pool"], plan_r=pos["plan_r"], bias=bias)
                    trades.append(tr)
                    pos = None
                    n_tr += 1
                    pnl_day += tr["pnl"]
                    if tr["pnl"] <= 0:
                        n_loss += 1
                    if ((tr["pnl"] > 0 and p["stop_after_win"]) or n_tr >= p["max_trades_day"] or
                            n_loss >= p["max_losses_day"] or pnl_day <= p["daily_stop"]):
                        done = True
                    cand = {1: None, -1: None}
            # ------------------------------------------------ 2) pending limit: cancel / fill
            if pend is not None and pos is None:
                d = pend["dir"]
                if done or wk != pend["win"]:
                    pend = None
                    dbg["cancel_window"] += 1
                elif (d == 1 and l[i] <= pend["entry"] - p["fill_ticks"] * tk) or \
                        (d == -1 and h[i] >= pend["entry"] + p["fill_ticks"] * tk):
                    pos = {**pend, "fill_i": i, "mae": 0.0}
                    pend = None
                    dbg["fill"] += 1
                    adv = (pos["entry"] - l[i]) if d == 1 else (h[i] - pos["entry"])
                    pos["mae"] = adv
                    if (d == 1 and l[i] <= pos["stop"]) or (d == -1 and h[i] >= pos["stop"]):
                        tr = make_trade(t[i], t[i] + 300, d, pos["entry"], pos["stop"], pos["stop"], "stop",
                                        setup=pos["setup"], mae_pts=pos["mae"], sym=sym, risk_usd=p["risk_usd"],
                                        entry_kind="limit", target=pos["target"], tgt_kind=pos["tgt_kind"],
                                        sess=pos["sess"], pool=pos["pool"], plan_r=pos["plan_r"], bias=bias)
                        trades.append(tr)
                        pos = None
                        n_tr += 1
                        n_loss += 1
                        pnl_day += tr["pnl"]
                        if n_tr >= p["max_trades_day"] or n_loss >= p["max_losses_day"] or pnl_day <= p["daily_stop"]:
                            done = True
                        cand = {1: None, -1: None}
                elif (d == 1 and h[i] >= pend["target"]) or (d == -1 and l[i] <= pend["target"]):
                    pend = None              # ran to the target without us: let it pass
                    dbg["cancel_target"] += 1
            # ------------------------------------------------ 3) pools taken by this bar -> raids
            raided = {1: None, -1: None}
            for q in pools:
                if q[4] or q[2] > i:
                    continue
                if q[1] == "L" and l[i] <= q[0] - sw:
                    q[4] = True
                    raided[1] = q[3] if raided[1] is None else raided[1]
                elif q[1] == "H" and h[i] >= q[0] + sw:
                    q[4] = True
                    raided[-1] = q[3] if raided[-1] is None else raided[-1]
            if done or pos is not None or wk < 0:
                if wk < 0:
                    cand = {1: None, -1: None}
                continue
            # ------------------------------------------------ 4) raid candidates (inside the killzone)
            for d in (1, -1):
                if d not in allowed:
                    continue
                cd = cand[d]
                if cd is not None and cd["win"] != wk:
                    cd = cand[d] = None
                if raided[d] is not None:
                    if cd is None or (d == 1 and l[i] < cd["x"]) or (d == -1 and h[i] > cd["x"]):
                        cand[d] = cd = {"x": l[i] if d == 1 else h[i], "xi": i, "ri": i, "pool": raided[d], "win": wk,
                                        "mss_i": None}
                        dbg["raid"] += 1
                elif cd is not None:
                    if (d == 1 and l[i] < cd["x"]) or (d == -1 and h[i] > cd["x"]):
                        if cd["mss_i"] is None:
                            cd["x"], cd["xi"] = (l[i] if d == 1 else h[i]), i     # deeper raid extreme
                        else:
                            cd = cand[d] = None     # MSS fully retraced through the raid extreme: void
                            continue
                if cd is None:
                    continue
                xi = cd["xi"]
                # swing that started the move into the raid: last 5m short-term swing before the extreme
                if cd["mss_i"] is None:
                    s = xi - 1
                    arr = st_h if d == 1 else st_l
                    while s > a and not arr[s]:
                        s -= 1
                    if s <= a:
                        continue
                    lvl = h[s] if d == 1 else l[s]
                    if i > xi and ((d == 1 and c[i] > lvl) or (d == -1 and c[i] < lvl)):
                        cd["mss_i"], cd["swing"] = i, float(lvl)
                        dbg["mss"] += 1
                    else:
                        continue
                # displacement FVG: first FVG with candle1 >= raid extreme bar and candle3 <= MSS bar + 1
                mi = cd["mss_i"]
                fv = None
                for k in range(xi + 2, min(i, mi + 1) + 1):
                    if d == 1 and l[k] > h[k - 2]:
                        fv = (k, float(h[k - 2]), float(l[k]))       # (c3 idx, gap bottom, gap top)
                        break
                    if d == -1 and h[k] < l[k - 2]:
                        fv = (k, float(h[k]), float(l[k - 2]))
                        break
                if fv is None:
                    if i >= mi + 1:
                        cand[d] = None        # MSS without displacement (no FVG): no trade
                        dbg["no_fvg"] += 1
                    continue
                cand[d] = None
                k3, gb, gt = fv
                if p["entry"] == "ce":
                    entry = round((gb + gt) / 2 / TICK) * TICK
                else:
                    entry = gt if d == 1 else gb
                x = cd["x"]
                stop = x - p["stop_ticks"] * tk if d == 1 else x + p["stop_ticks"] * tk
                risk = abs(entry - stop)
                if (c[i] - entry) * d <= 0:
                    dbg["skip_in_gap"] += 1
                    continue                  # price already back inside the gap at the MSS: no clean retrace entry
                if risk <= 0 or size(risk, p["risk_usd"], sym) < 1:
                    dbg["skip_qty0"] += 1
                    continue
                tgt_kind = "rr"
                if p["target"] == "rr":
                    target = entry + d * p["rr"] * risk
                else:
                    # opposite (external) liquidity = pools that already existed when the raid happened; swings
                    # printed by the raid/displacement itself are internal to the setup, not the draw
                    opp = [q[0] for q in pools if not q[4] and q[2] <= cd["ri"] and q[1] == ("H" if d == 1 else "L")
                           and (q[0] - entry) * d > 0]
                    if opp:
                        target = min(opp) if d == 1 else max(opp)
                        tgt_kind = "liq"
                    else:
                        rng = abs(cd["swing"] - x)
                        target = cd["swing"] + d * p["sd"] * rng
                        tgt_kind = "sd"
                dbg["armed"] += 1
                dbg["replaced"] += pend is not None
                pend = {"dir": d, "entry": float(entry), "stop": float(stop), "target": float(target), "win": wk,
                        "arm_i": i, "setup": f"{'L' if d == 1 else 'S'}_{cd['pool']}", "pool": cd["pool"],
                        "tgt_kind": tgt_kind, "sess": "AM" if wk == 0 else "PM",
                        "plan_r": round(abs(target - entry) / risk, 2)}
                cand = {1: None, -1: None}
                break
        if pos is not None:   # session ended early (half day) -> flat at its last close; end of data -> 'open'
            d = pos["dir"]
            kind = "open" if di == len(bnds) - 1 else "time"
            tr = make_trade(t[pos["fill_i"]], t[b - 1] + 300, d, pos["entry"], pos["stop"], c[b - 1], kind,
                            setup=pos["setup"], mae_pts=pos["mae"], sym=sym, risk_usd=p["risk_usd"],
                            entry_kind="limit", target=pos["target"], tgt_kind=pos["tgt_kind"], sess=pos["sess"],
                            pool=pos["pool"], plan_r=pos["plan_r"], bias=bias)
            trades.append(tr)
        if keep_state and di == len(bnds) - 1:
            last_state = {"day": dname, "bias": {1: "bull", -1: "bear", 0: "none"}[_bias(prev1, prev2)],
                          "untaken_pools": [{"name": q[3], "price": q[0]} for q in pools if not q[4] and q[2] < b],
                          "armed": pend, "position": pos, "done_for_day": done, "trades_today": n_tr,
                          "waiting_for": ("done for the day" if done else "position management" if pos else
                                          "limit fill" if pend else "raid of an untaken pool inside a killzone")}
    last_state["funnel"] = dict(dbg)
    return trades, last_state


def run(bars5, params=None, es5=None, _debug=None):
    p = {**PARAMS, **(params or {})}
    trades, st = _sim(bars5, p)
    if _debug is not None:
        _debug.append(st["funnel"])
    return trades


def state(bars5, params=None, es5=None):
    p = {**PARAMS, **(params or {})}
    days = sorted(set(bars5["day"]))[-3:]
    _, st = _sim(bars5[bars5["day"].isin(days)].reset_index(drop=True), p, keep_state=True)
    st["params"] = p
    return st
