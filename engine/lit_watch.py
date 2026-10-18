"""Armed-setup watcher for the cloud monitor (PC off): notice a LIT entry within about a minute of the bar the feed shows,
instead of at the next half-hourly run.

A LIT entry builds up in steps (engine/lit.py): sweep of a level -> inducement -> protected extreme -> 5m CISD close (the
limit is placed: "armed") -> limit tapped within 30 min -> 1m CISD within 20 bars -> enter at the next 1m open. The cloud
monitor (tools/cloud_monitor.py) runs every 30 min; on its own it sees an entry 0-30 min late (plus GitHub's start delay).
The signal-to-entry gap is only 11 min at the median in 2026 (10% within 2 min), so watching only armed limits would
still miss most fills between two runs. This module therefore also recognises a setup that is FORMING: a qualifying
sweep extreme (depth, inducement, stop size, room to the VIX-band target, Monday rule) whose 5m CISD has not closed yet.
While a setup is forming or armed, tools/lit_watch.py keeps the job alive and polls every 30 s; it stops once nothing is
forming or armed, the day's trade is in, or its time cap is reached, so it only costs Actions minutes on such stretches.

Nothing here decides a trade: every entry still comes from engine/lit_live.run (the backtest's own executor), so the
paper ledger and the notification carry the backtest's bar, price, stop, target and micros (tests/test_lit_watch.py).

  brewing(M, P)          forming setups at the last closed 5m bar of a lit.Market (both sides)
  market(df5, P)         the live loop's Market (same window as engine/lit_live.run)
  armed_line(state, ..)  the phone / README line: "LONG setup armed, limit 21,345.00, until 09:52 ET" (or forming)
  signature(res)         what has to change between two polls before the watcher runs the full monitor
  alive(res, brew)       keep watching? (reason)
Paper only: nothing here routes anything.
"""
from __future__ import annotations

import bisect
import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np

from engine import lit

ET = ZoneInfo("America/New_York")
LEG, SWEEP_WIN = 24, 24            # = lit.candidates defaults (leg, sweep_win)


def _hm(t):
    return dt.datetime.fromtimestamp(int(t), ET).strftime("%H:%M")


def market(df5, P=None, sym="NQ"):
    """The lit.Market engine/lit_live.run builds from the merged 5m history (previous-month window, same hygiene)."""
    from engine import lit_live
    from engine.data import from_frame
    P = {**lit.DEFAULTS, **(P or {})}
    df5 = lit_live._clean5(df5)
    last_t = int(df5["time"].max())
    w = df5[df5["time"] >= lit_live.window_start(last_t)]
    return lit.Market(bars=from_frame(sym, "5m", w), extra_boxes=P.get("extra_boxes") or [])


def brewing(M, P=None, j=None, leg=LEG, sweep_win=SWEEP_WIN):
    """Setups FORMING at closed 5m bar j (default: the last bar of M): for each side, the protected extreme of the last
    `leg` bars swept a LIT level (first breach within `sweep_win` bars before it, >= P depth ATR beyond the nearest swept
    level), has P idm_a inducement, a stop of P min_stop..max_stop from the structure level, room to the VIX-band target
    (>= min_rr) and passes the Monday rule, and no 5m bar has closed beyond the structure level yet. The setup becomes a
    LIT signal on the first 5m close beyond that level with a displacement body >= P disp ATR (not checked here: a forming
    setup is a reason to watch, not a decision). Mirrors lit.candidates / lit._run_core, causally (only bars <= j)."""
    P = {**lit.DEFAULTS, **(P or {})}
    n = int(getattr(M, "n_closed", M.n))
    j = n - 1 if j is None else int(j)
    if j < 0 or j >= n:
        return []
    k = int(M.day_of[j])
    x = M.ctx[k]
    _date, s, e = M.days[k]
    if "pdh" not in x or j - s < 2:
        return []
    win_a = min(a for a, _ in P["window"]); win_z = max(z for _, z in P["window"])
    m = int(M.mod[j])
    if m >= 1080 or m + 10 >= win_z or m + 10 < win_a - 120:     # the earliest entry bar is j + 2 (10 min later)
        return []
    names = set(P["sweep_names"]) if P.get("sweep_names") else None
    L = M.levels(k)
    out = []
    for d in (1, -1):
        if d == 1:
            hi_d, lo_d, c_d, o_d = M.h, M.l, M.c, M.o
            swing_hi, swing_lo = M.fh, M.fl
        else:
            hi_d, lo_d, c_d, o_d = -M.l, -M.h, -M.c, -M.o
            swing_hi, swing_lo = M.fl, M.fh
        a = max(s, j - leg + 1)
        ee = a + int(np.argmin(lo_d[a:j + 1]))
        if P["ref"] == "cisd":
            cz = lit._cisd_level(c_d, o_d, ee)
            if cz is None:
                continue
            rp = cz[0]
        else:                                     # "frac": the last confirmed fractal high before the extreme
            ok = [int(q) for q in swing_hi[:bisect.bisect_left(swing_hi, ee)] if int(q) + 2 <= j]
            if not ok or ok[-1] < ee - 36:
                continue
            rp = float(hi_d[ok[-1]])
        if float(c_d[ee:j + 1].max()) > rp:      # already closed beyond the level: triggered (or dead) for this extreme
            continue
        ext = float(lo_d[ee])
        liq = [(px * d, ki, nm) for side, px, ki, nm, cls in L if (side == "low") == (d == 1)]
        swept = []
        for p, ki, nm in liq:
            if ki >= ee or ext >= p:
                continue
            fb = lit._first_breach(lo_d, max(ki, s - 600), ee + 1, p)
            if ee - sweep_win <= fb <= ee:
                swept.append((p, fb, nm))
        if not swept:
            continue
        at = M.atr
        if names is None:
            lev_near = max(z[0] for z in swept)
        else:
            sw = [z[0] for z in swept if z[2] in names]
            if not sw:
                continue
            lev_near = max(sw)
        if (lev_near - ext) / max(at[ee], 1e-9) < P["depth"]:
            continue
        sb = min(z[1] for z in swept)
        lev_all = max(z[0] for z in swept)
        if P.get("idm_a"):
            dm, age, cnt = P["idm_a"]
            n_idm = 0
            leg_top = int(ee - np.argmax(hi_d[max(ee - 36, s - 600):ee + 1][::-1])) if ee > s else ee
            for q in swing_lo[bisect.bisect_left(swing_lo, sb - 72):bisect.bisect_left(swing_lo, ee)]:
                q = int(q)
                if q + 2 > j or lo_d[q] <= lev_all:
                    continue
                sg = lo_d[q + 1:ee + 1] < lo_d[q]
                if not sg.any():
                    continue
                tk = q + 1 + int(np.argmax(sg))
                if tk < max(leg_top, q + 3) or tk > ee:
                    continue
                dd, aa = (lo_d[q] - lev_all) / max(at[sb], 1e-9), sb - q
                n_idm += dd <= dm and aa <= age
            if n_idm < cnt:
                continue
        stop = ext - P["stop_buf"]
        risk = rp - stop
        if not (P["min_stop"] <= risk <= P["max_stop"]):
            continue
        tgt = None
        if "vix" in P["classes"]:
            vm = x.get("vix_move")
            if vm:
                tgt = x["open18"] * d + P["vix_k"] * vm
                if tgt - rp < P["min_rr"] * risk and not P.get("fallback_rr"):
                    continue
            elif not P.get("fallback_rr") and P["classes"] == ["vix"]:
                continue
        if P.get("monday") and x["dow"] == 0:
            took_hi = bool(M.h[s:j + 1].max() > x["pdh"]); took_lo = bool(M.l[s:j + 1].min() < x["pdl"])
            if took_hi != took_lo and ((took_hi and d == 1) or (took_lo and d == -1)):
                continue
        out.append({"dir": d, "ext": round(ext * d, 2), "ext_t": int(M.t[ee]), "level": round(rp * d, 2),
                    "stop": round(stop * d, 2), "risk_pts": round(risk, 2), "target": round(tgt * d, 2) if tgt is not None else None,
                    "swept": sorted({z[2] for z in swept}), "bar_t": int(M.t[j]), "until_t": int(M.t[ee]) + leg * 300})
    return out


def _today(res):
    return ((res.get("state") or {}).get("lit") or {}).get("today")


def traded_today(res) -> bool:
    st = res.get("state") or {}
    return bool(st.get("position") or st.get("enter_now") or int(st.get("day_trades") or 0) > 0)


def signature(res) -> tuple:
    """What the watcher compares poll to poll: the open position, today's trades, the working setups (placed / tapped).
    A change means the full monitor runs (paper ledger, notification, dashboards)."""
    st = res.get("state") or {}
    pos = st.get("position") or {}
    setups = tuple(sorted((side, int(s.get("arm_t") or 0), int(s.get("tapped_t") or 0)) for side, s in (st.get("setups") or {}).items()))
    day = _today(res)
    return (int(pos.get("entry_t") or 0), tuple(sorted(int(t["entry_t"]) for t in res.get("trades") or [] if t.get("day") == day)), setups)


def alive(res, brew=None) -> tuple[bool, str]:
    """(keep watching, why): a working limit / 1m-CISD wait, an entry being decided, or a forming setup, while today has
    no trade yet. A position or a finished trade today ends the watch (LIT takes one trade a day)."""
    st = res.get("state") or {}
    if st.get("position"):
        return False, "in trade"
    if int(st.get("day_trades") or 0) > 0:
        return False, "done for today"
    if st.get("enter_now"):
        return True, "entering"
    if st.get("setups"):
        s = next(iter(st["setups"].values()))
        return True, "tapped, waiting for the 1m CISD" if s.get("tapped_t") else "limit armed"
    if brew:
        return True, "setup forming"
    return False, "nothing armed"


def armed_line(state, brew=None, cisd_bars=20) -> dict | None:
    """The phone / README line for an armed or forming setup (None when there is none):
    {"kind": "armed" | "tapped" | "entering" | "forming", "side", "text", "limit", "stop", "target", "until_t"}."""
    st = state or {}
    if st.get("position"):
        return None
    en = st.get("enter_now")
    if en:
        side = "LONG" if int(en["dir"]) == 1 else "SHORT"
        return {"kind": "entering", "side": side, "limit": None, "stop": en.get("stop"), "target": en.get("target"),
                "until_t": int(en["entry_t"]) + 60,
                "text": f"{side} entering at market now (1m CISD closed {_hm(en['cisd_t'])} ET), stop {float(en['stop']):,.2f}"}
    for side, s in (st.get("setups") or {}).items():
        if not s or s.get("limit") is None:
            continue
        sd = side.upper()
        if s.get("tapped_t"):
            until = int(s["tapped_t"]) + (int(cisd_bars) + 1) * 60
            return {"kind": "tapped", "side": sd, "limit": s["limit"], "stop": s.get("stop"), "target": s.get("target"),
                    "until_t": until, "arm_t": s.get("arm_t"),
                    "text": f"{sd} setup armed: limit {float(s['limit']):,.2f} tapped at {_hm(s['tapped_t'])}, waiting for a 1m CISD "
                            f"until {_hm(until)} ET (stop {float(s['stop']):,.2f})"}
        return {"kind": "armed", "side": sd, "limit": s["limit"], "stop": s.get("stop"), "target": s.get("target"),
                "until_t": int(s["expires_t"]), "arm_t": s.get("arm_t"),
                "text": f"{sd} setup armed, limit {float(s['limit']):,.2f}, until {_hm(s['expires_t'])} ET "
                        f"(stop {float(s['stop']):,.2f}, target {float(s['target']):,.2f})"}
    if brew and not int(st.get("day_trades") or 0):
        b = sorted(brew, key=lambda z: -z["ext_t"])[0]
        sd = "LONG" if b["dir"] == 1 else "SHORT"
        try:
            from engine.lit_live import _sweep_names
            sw = ", ".join(_sweep_names(b["swept"]))
        except Exception:
            sw = ", ".join(b["swept"])
        return {"kind": "forming", "side": sd, "limit": b["level"], "stop": b["stop"], "target": b.get("target"),
                "until_t": b["until_t"],
                "text": f"{sd} setup forming: swept {sw} (extreme {b['ext']:,.2f}); a 5m close {'above' if b['dir'] == 1 else 'below'} "
                        f"{b['level']:,.2f} arms it (stop {b['stop']:,.2f}), until {_hm(b['until_t'])} ET"}
    return None
