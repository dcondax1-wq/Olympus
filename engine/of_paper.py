"""The Order Flow pillar's PAPER bot (research/orderflow/DESIGN_paper.md, frozen 76396849). PAPER ONLY: it never routes, sizes or
changes an order or a live setting, and imports no broker / adapter / NinjaTrader / live-loop module (tests/test_of_paper.py).

Reads (read only): the live tick file LE_TickRec writes (Documents\\NinjaTrader 8\\le_ticks\\NQ_<ET day>.csv), its depth file
(le_ticks\\depth\\NQ_<ET day>.csv) when it exists, the stored ticks of the previous day (data/ticks via engine.tickrec, for the
levels), and data/live_state.json (the owner's kill flag, LIT's ledger via engine.oflive.lit_trades_of).
Writes only data/of_paper.json and data/of_paper_cache/ (gitignored).

The market read is the research's own chain: CSV -> engine.tickrec.read_rec_csv -> engine.ofsum.summarize -> of_battery.Day /
of_mill.Ctx -> of_mill.features + of_v3.features. So a live paper decision = what the nightly research sees for that bar.

Lanes:  A  LVL-OF  the pillar's own paper trades: DESIGN2's level fade (prior-day RTH / Globex / opening-range high-low, a 5m bar
               through the level that closes back) taken only when the signal bar was ABSORBED at its extreme (OF1 rule:
               8 ticks, delta into the extreme >= 20% of the zone volume). Fill = first trade after the decision + 1 tick,
               stop 1 tick beyond the signal bar, 2R, flat 15:55. Skipped / busy candidates are tracked as if taken.
        B  LIT-OF  the OF1 read at each real Zlarior entry's sweep: what the filter WOULD have done, with LIT's real result.
        C  timing  (depth days) the book's queue lean / OFI at each decision and the "wait up to 60 s for the queue" price.
Kill: data/live_state.json "kill": true -> no new paper entry, an open paper trade closes at the next trade. Off: LE_OFPAPER=0 or
data/of_paper_off. Runs only 09:25-16:10 ET on weekdays.

    python -X utf8 -m engine.of_paper tick            # one run (the PC: every 5 min from engine/ops_checks, detached)
    python -X utf8 -m engine.of_paper loop            # every 30 s until 16:10 ET (manual / a scheduled task)
    python -X utf8 -m engine.of_paper replay --day 2026-12-01   # a recorded tick day through the same engine (paper)
    python -X utf8 -m engine.of_paper show | selftest
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
STATE_NAME, CACHE_NAME, OFF_NAME = "of_paper.json", "of_paper_cache", "of_paper_off"
LABEL = "OF paper (shadow)"
VERSION = 1
TICK, PV, COMM, SLIP = 0.25, 2.0, 1.40, 0.25            # of_study: MNQ $2 a point, $1.40 a micro round trip, 1 tick
ZONE, ABS_SHARE, RR, RISK_USD, MAXQ = 8, 0.20, 2.0, 500.0, 40
WAIT_S = 60
MAX_ROWS = 600
_M = {}


def _mods():
    """The research modules (of_battery, of_mill, of_v3), loaded once by path."""
    if not _M:
        here = os.path.join(ROOT, "research", "orderflow")
        for k, f in (("M", "of_mill.py"), ("V3", "of_v3.py")):
            sp = importlib.util.spec_from_file_location(f"ofp_{k}", os.path.join(here, f))
            m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
            _M[k] = m
        _M["B"] = _M["M"].B
    return _M["B"], _M["M"], _M["V3"]


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET)


def et_day(t) -> str:
    return _et(t).strftime("%Y-%m-%d")


def _mod(t) -> int:
    e = _et(t)
    return e.hour * 60 + e.minute


def _rj(p, default=None):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def _wj(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, separators=(",", ":"), default=float)
    os.replace(tmp, p)


# ------------------------------------------------------------------------------------------------ market read
def summary_of(x, day: str, depth=None) -> dict | None:
    """Ticks (engine.tickrec frame) -> the research summary dict (bars, fp, meta[, depth])."""
    from . import ofsum
    B, _, _ = _mods()
    files = ofsum.summarize(x, day)
    if not files:
        return None
    R = B._from_bytes(files)
    R["depth"] = ofsum.depth_summary(depth) if depth is not None and len(depth) else None
    return R


def new_state(day: str | None = None) -> dict:
    return {"v": VERSION, "paper": True, "never_routed": True, "label": LABEL, "day": day, "done_t": None, "used": [],
            "rows": [], "lit": [], "t": None, "runs": 0}


def _risk_q(risk: float) -> int:
    return int(min(MAXQ, RISK_USD // (risk * PV))) if risk > 0 else 0


def _resolve(row: dict, bars, ticks_t, ticks_p, t_close_last: int | None, end_of_day: bool):
    """Walk the closed bars after the fill; set exit / R / $ when the stop, the target or 15:55 is reached."""
    if row.get("exit_t") or row.get("fill") is None:
        return
    d, fill, stop = row["d"], row["fill"], row["stop"]
    risk = (fill - stop) * d
    tgt = fill + RR * risk * d
    row["target"] = round(tgt, 2)
    last = None
    for i in range(len(bars)):
        t = int(bars.t.iat[i])
        if t < row["entry_bar_t"] or (t_close_last is not None and t > t_close_last):
            continue
        if bars["mod"].iat[i] > 955:
            break
        last = i
        h, l = float(bars.high.iat[i]), float(bars.low.iat[i])
        if t == row["entry_bar_t"] and row["fill_t_ms"] > t * 1000:     # late fill: only the trades after it in its bar
            m = (ticks_t >= row["fill_t_ms"]) & (ticks_t < (t + 300) * 1000)
            if m.any():
                h, l = float(ticks_p[m].max()), float(ticks_p[m].min())
            else:
                continue
        if (d == 1 and l <= stop) or (d == -1 and h >= stop):
            _close(row, t, stop - SLIP * d, "stop"); return
        if (d == 1 and h >= tgt) or (d == -1 and l <= tgt):
            _close(row, t, tgt, "target"); return
    if last is not None and (end_of_day or (bars["mod"].iat[last] >= 955 and (t_close_last or 0) >= int(bars.t.iat[last]))):
        _close(row, int(bars.t.iat[last]), float(bars.close.iat[last]) - SLIP * d, "flat 15:55")


def _close(row, t, px, why):
    d, fill, stop = row["d"], row["fill"], row["stop"]
    risk = (fill - stop) * d
    q = _risk_q(risk)
    row.update(exit_t=int(t), exit=round(px, 2), why=why, R=round((px - fill) * d / risk, 3),
               usd_1=round((px - fill) * d * PV - COMM, 2),
               usd_500=round((px - fill) * d * PV * q - COMM * q, 2) if q >= 1 else None)


def _kill_close(row, ticks_t, ticks_p, t_kill_ms):
    m = ticks_t >= t_kill_ms
    if m.any():
        k = int(np.argmax(m))
        _close(row, int(ticks_t[k] // 1000), float(ticks_p[k]) - SLIP * row["d"], "KILL")
        row["why"] = "KILL (owner's kill switch)"


def step(S: dict, day: str, R_today: dict, R_prev: dict | None, prev_day: str | None, ticks_t, ticks_p, now: float,
         kill: bool = False, lit: list | None = None, depth=None) -> dict:
    """Process every 5m bar of `day` closed by `now` that this state has not seen. Pure: the same inputs give the same state."""
    B, M, V3 = _mods()
    if S.get("day") != day:
        S.update(new_state(day))
    D = {day: B.Day(day, R_today)}
    days = [day]
    if R_prev is not None and prev_day:
        D[prev_day] = B.Day(prev_day, R_prev)
        days = [prev_day, day]
    Dy = D[day]
    bars = Dy.bars
    last_ms = int(ticks_t[-1]) if len(ticks_t) else 0
    closed = [i for i in range(len(bars)) if int(bars.t.iat[i]) + 300 <= max(last_ms // 1000, 0) or now >= int(bars.t.iat[i]) + 330]
    n_closed = (max(closed) + 1) if closed else 0
    t_close_last = int(bars.t.iat[n_closed - 1]) if n_closed else None
    # the day is over once the 15:55 bar is closed by the clock (16:00:30 ET), or on a later day
    end_of_day = (et_day(now) == day and now >= _et(now).replace(hour=16, minute=0, second=30).timestamp()) or et_day(now) > day
    L = B.levels(D, days, len(days) - 1)
    S["levels"] = [{"name": nm, "px": round(float(lv), 2), "side": int(sd)} for nm, lv, sd in L]
    rth_i = [i for i in range(n_closed) if 570 <= bars["mod"].iat[i] < 960]
    orb = [i for i in rth_i if bars["mod"].iat[i] < 600]
    if len(orb) == 6 and any(bars["mod"].iat[i] >= 600 for i in rth_i):     # the opening range, once it is complete
        S["levels"] += [{"name": "orh", "px": round(float(bars.high.iloc[orb].max()), 2), "side": 1},
                        {"name": "orl", "px": round(float(bars.low.iloc[orb].min()), 2), "side": -1}]
    used = set(S.get("used") or [])
    rows = S["rows"]
    done = S.get("done_t")
    for i in rth_i:
        t = int(bars.t.iat[i])
        if done is not None and t <= done:
            continue
        mod = int(bars["mod"].iat[i])
        if not (585 <= mod <= 900):
            continue
        LL = list(L)
        if mod >= 600 and len(orb) == 6:
            LL += [("orh", float(bars.high.iloc[orb].max()), 1), ("orl", float(bars.low.iloc[orb].min()), -1)]
        for nm, lv, side in LL:
            if nm in used or (nm.startswith("or") and mod < 600):
                continue
            h, l, c = float(bars.high.iat[i]), float(bars.low.iat[i]), float(bars.close.iat[i])
            if side == 1 and h >= lv + TICK and c < lv:
                d = -1
            elif side == -1 and l <= lv - TICK and c > lv:
                d = 1
            else:
                continue
            used.add(nm)
            z = Dy.zone(t, d)
            absorbed = bool(z is not None and z[0] > 0 and z[1] * d < 0 and abs(z[1]) >= ABS_SHARE * z[0])
            busy = any(r.get("taken") and not r.get("exit_t") for r in rows)
            t_dec = max(t + 300, int(now) if S.get("live") and t + 300 > (S.get("t") or 0) else t + 300)
            row = {"id": f"A|{day}|{nm}", "lane": "A", "day": day, "t_sig": t, "level": nm, "level_px": round(lv, 2), "d": d,
                   "vz": None if z is None else int(z[0]), "dz": None if z is None else int(z[1]), "absorbed": absorbed,
                   "taken": bool(absorbed and not busy and not kill),
                   "why_not": None if (absorbed and not busy and not kill) else ("kill" if kill else "busy" if (absorbed and busy) else "not absorbed"),
                   "t_dec": int(t_dec), "stop": round(l - TICK if d == 1 else h + TICK, 2), "entry_bar_t": t + 300,
                   "fill": None, "fill_t_ms": None}
            rows.append(row)
            if row["taken"]:
                busy = True
        S["done_t"] = t
        done = t
    S["used"] = sorted(used)
    # fills (the first trade at / after the decision, + 1 tick), the live entry bar, exits, readings
    ctx = None
    for row in rows:
        if row.get("lane") != "A" or row.get("day") != day:
            continue
        if row["fill"] is None and len(ticks_t):
            m = ticks_t >= row["t_dec"] * 1000
            if m.any():
                k = int(np.argmax(m))
                row["fill"] = round(float(ticks_p[k]) + SLIP * row["d"], 2)
                row["fill_t_ms"] = int(ticks_t[k])
                row["entry_bar_t"] = int(ticks_t[k] // 1000) // 300 * 300
                if (row["fill"] - row["stop"]) * row["d"] <= 0:
                    row.update(exit_t=row["entry_bar_t"], why="no risk (gapped through the stop)", R=None, usd_1=None, usd_500=None)
        if kill and row.get("taken") and row["fill"] is not None and not row.get("exit_t"):
            _kill_close(row, ticks_t, ticks_p, int(now * 1000) if S.get("live") else int(ticks_t[-1]))
        _resolve(row, bars, ticks_t, ticks_p, t_close_last, end_of_day)
        if "f" not in row:
            i = Dy.row_of_t.get(row["t_sig"] + 300)
            if i is not None:
                if ctx is None:
                    ctx = M.Ctx(Dy)
                ext = Dy.row_of_t.get(row["t_sig"])
                f = {**M.features(ctx, i, row["d"], ext, row["level_px"]), **V3.features(ctx, i, row["d"], ext, row["level_px"])}
                row["f"] = {k: (None if v is None or not np.isfinite(v) else round(float(v), 4)) for k, v in f.items()}
        if depth is not None and len(depth) and "timing" not in row and row["fill"] is not None:
            row["timing"] = timing(row, depth, ticks_t, ticks_p)
    # lane B: the OF1 read at each LIT entry's sweep
    have = {r["t"] for r in S["lit"]}
    for tr in lit or []:
        te = int(tr["t"])
        if et_day(te) != day:
            continue
        rec = next((r for r in S["lit"] if r["t"] == te), None)
        if rec is None:
            w = [i for i in range(len(bars)) if te - 1800 <= int(bars.t.iat[i]) and int(bars.t.iat[i]) + 300 <= te]
            if not w:
                continue
            w = w[-6:]
            j = min(w, key=lambda i: bars.low.iat[i]) if tr["d"] == 1 else max(w, key=lambda i: bars.high.iat[i])
            z = Dy.zone(int(bars.t.iat[j]), tr["d"])
            ab = None if z is None or z[0] <= 0 else bool(z[1] * tr["d"] < 0 and abs(z[1]) >= ABS_SHARE * z[0])
            rec = {"id": f"B|{te}", "lane": "B", "t": te, "d": tr["d"], "absorbed": ab,
                   "decision": "take" if ab else ("skip" if ab is False else "no read"), "pnl": None}
            S["lit"].append(rec)
        if tr.get("pnl") is not None:
            rec["pnl"] = tr["pnl"]
    S["rows"] = rows[-MAX_ROWS:]
    S["t"] = int(now)
    S["runs"] = int(S.get("runs") or 0) + 1
    S["kill_seen"] = bool(kill)
    S["today"] = day_summary(S, day)
    S["line"] = line(S)                       # plain text for the Brain room / the EOD notice (they read JSON only)
    return S


def timing(row, depth, ticks_t, ticks_p) -> dict:
    """Lane C: queue lean / OFI at the decision, and the 'wait up to 60 s for the book' price vs the paper fill (+ = better)."""
    t0 = row["t_dec"] * 1000
    dp = depth[(depth.t_ms >= t0) & (depth.t_ms <= t0 + WAIT_S * 1000)]
    if not len(dp):
        return {"read": "no depth"}
    d = row["d"]
    qb, qa = dp.bs1.to_numpy(float), dp.as1.to_numpy(float)
    imb = np.where(qb + qa > 0, (qb - qa) / np.maximum(1, qb + qa), 0.0)
    ask = dp.bp.to_numpy(float) + np.where(dp.ad1.to_numpy() >= 0, dp.ad1.to_numpy(), 1) * TICK
    bid = dp.bp.to_numpy(float)
    lean = np.where(imb * d > 0)[0]
    if len(lean):
        k = int(lean[0])
        alt, why = (ask[k] if d == 1 else bid[k]), "queue leaned our way"
    else:
        m = ticks_t >= t0 + WAIT_S * 1000
        if not m.any():
            return {"read": "waiting"}
        alt, why = float(ticks_p[int(np.argmax(m))]) + SLIP * d, "no lean in 60 s"
    return {"imb1_at_dec": round(float(imb[0] * d), 3), "alt": round(float(alt), 2),
            "ticks_better": round((row["fill"] - alt) * d / TICK, 1), "why": why}


# ------------------------------------------------------------------------------------------------ words
def day_summary(S: dict, day: str | None = None) -> dict:
    day = day or S.get("day")
    A = [r for r in S.get("rows") or [] if r.get("day") == day]
    tk = [r for r in A if r.get("taken")]
    done = [r for r in tk if r.get("R") is not None]
    sk = [r for r in A if not r.get("taken")]
    return {"day": day, "candidates": len(A), "taken": len(tk), "open": sum(1 for r in tk if not r.get("exit_t")),
            "R": round(sum(r["R"] for r in done), 2), "usd_1": round(sum(r.get("usd_1") or 0 for r in done), 2),
            "skipped": len(sk), "skipped_R": round(sum(r["R"] for r in sk if r.get("R") is not None), 2),
            "lit": [{"decision": r["decision"], "pnl": r["pnl"]} for r in S.get("lit") or []]}


def line(S: dict | None) -> str | None:
    """'OF paper: 3 trades today, +1.2R (1 micro +$48); 2 skipped (not absorbed) would have made -0.8R'."""
    if not S or not S.get("today"):
        return None
    s = S["today"]
    if not s["candidates"] and not s["lit"]:
        return f"OF paper: no level signal today ({_et(S['t']):%H:%M} ET)" if S.get("t") else None
    md = dt.date.fromisoformat(s["day"]).strftime("%b %d")
    bits = [f"OF paper {md}: {s['taken']} trade{'s' if s['taken'] != 1 else ''}"
            + (f", {s['R']:+.1f}R (1 micro {'+' if s['usd_1'] >= 0 else '-'}${abs(s['usd_1']):,.0f})" if s["taken"] else "")
            + (f", {s['open']} open" if s["open"] else "")]
    if s["skipped"]:
        bits.append(f"{s['skipped']} skipped (flow said no) would have made {s['skipped_R']:+.1f}R")
    for r in s["lit"]:
        res = "open" if r["pnl"] is None else (f"won ${r['pnl']:,.0f}" if r["pnl"] > 0 else f"lost ${-r['pnl']:,.0f}")
        bits.append(f"Zlarior: flow says {r['decision'].upper()} -> {res}")
    if S.get("kill_seen"):
        bits.append("kill switch on: no new paper entry")
    return "; ".join(bits)


def eod_line(root: str = ROOT, now: float | None = None) -> str | None:
    """The EOD notice's line (engine/ops_checks.eod_notice). Only for today's state. Never raises."""
    try:
        S = _rj(os.path.join(root, "data", STATE_NAME))
        if not S or S.get("day") != et_day(now or time.time()):
            return None
        return line(S)
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------------------------------------ runners
def nt_dir():
    from . import oflive
    return oflive.nt_dir()


def _read_live(day: str, nd: str):
    from . import tickrec
    for root_ in ("NQ", "MNQ"):
        p = os.path.join(nd, "le_ticks", f"{root_}_{day}.csv")
        if os.path.exists(p):
            return tickrec.read_rec_csv(p)
    return None


def _read_depth(day: str, nd: str):
    from . import tickrec
    p = os.path.join(nd, "le_ticks", "depth", f"NQ_{day}.csv")
    if os.path.exists(p):
        try:
            return tickrec.read_depth_csv(p)
        except Exception:  # noqa: BLE001
            return None
    return None


def _prev_summary(day: str, nd: str | None, root: str):
    """The previous tick day's summary (levels), cached once a day under data/of_paper_cache/."""
    from . import tickrec
    cdir = os.path.join(root, "data", CACHE_NAME)
    d0 = dt.date.fromisoformat(day)
    for back in range(1, 5):
        p = (d0 - dt.timedelta(days=back)).isoformat()
        cp = os.path.join(cdir, f"{p}.json")
        if os.path.exists(cp):
            import pandas as pd
            c = _rj(cp)
            if c:
                return p, {"bars": pd.DataFrame(c["bars"]), "fp": pd.DataFrame(c["fp"]), "meta": c["meta"], "depth": None}
        x = None
        if nd:
            x = _read_live(p, nd)
        if x is None:
            try:
                x = tickrec.read_day(p)
            except Exception:  # noqa: BLE001
                x = None
        if x is not None and len(x):
            R = summary_of(x, p)
            if R:
                os.makedirs(cdir, exist_ok=True)
                _wj(cp, {"bars": R["bars"].to_dict("list"), "fp": R["fp"].to_dict("list"), "meta": R["meta"]})
                for f in sorted(os.listdir(cdir))[:-5]:
                    try:
                        os.remove(os.path.join(cdir, f))
                    except OSError:
                        pass
                return p, R
    return None, None


def _kill(root) -> bool:
    return bool((_rj(os.path.join(root, "data", "live_state.json"), {}) or {}).get("kill"))


def off(root: str = ROOT) -> bool:
    return os.environ.get("LE_OFPAPER") == "0" or os.path.exists(os.path.join(root, "data", OFF_NAME))


def in_window(now: float) -> bool:
    e = _et(now)
    return e.weekday() < 5 and 9 * 60 + 25 <= e.hour * 60 + e.minute <= 16 * 60 + 10


def tick(now: float | None = None, root: str = ROOT, nd: str | None = None, force: bool = False) -> dict:
    """One live run. Never raises."""
    try:
        now = float(now or time.time())
        if off(root):
            return {"off": True}
        if not force and not in_window(now):
            return {"skipped": "outside 09:25-16:10 ET weekdays"}
        nd = nd or nt_dir()
        if not nd:
            return {"skipped": "no NinjaTrader folder"}
        day = et_day(now)
        x = _read_live(day, nd)
        if x is None or not len(x):
            return {"skipped": "no live tick file today (recorder off?)"}
        x = x[x.t_ns <= int(now * 1e9)]
        dp = _read_depth(day, nd)
        R = summary_of(x, day, dp)
        pday, Rp = _prev_summary(day, nd, root)
        sp = os.path.join(root, "data", STATE_NAME)
        S = _rj(sp) or new_state(day)
        S["live"] = True
        from . import oflive
        lit = oflive.lit_trades_of(day, root)
        tt = (x.t_ns.to_numpy(np.int64) // 1_000_000)
        S = step(S, day, R, Rp, pday, tt, x.price.to_numpy(float), now, kill=_kill(root), lit=lit, depth=dp)
        _wj(sp, S)
        return {"ok": True, "line": line(S), "today": S["today"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{e.__class__.__name__}: {str(e)[:160]}"}


def replay_frame(x, day: str, R_prev=None, prev_day=None, lit=None, depth=None, kill_at: float | None = None) -> dict:
    """A whole recorded day through the SAME step(), one run per 5m close (+1 s): the research's execution exactly."""
    t0 = int(x.t_ns.iloc[0] // 10**9) // 300 * 300
    t_end = int(x.t_ns.iloc[-1] // 10**9) + 600
    S = new_state(day)
    tt_all = x.t_ns.to_numpy(np.int64) // 1_000_000
    px_all = x.price.to_numpy(float)
    for now in range(t0 + 301, t_end + 1, 300):
        mod = _mod(now)
        if mod < 9 * 60 + 25 or mod > 16 * 60 + 10:
            continue
        m = tt_all <= now * 1000
        if not m.any():
            continue
        R = summary_of(x[m], day, depth[depth.t_ms <= now * 1000] if depth is not None else None)
        S = step(S, day, R, R_prev, prev_day, tt_all[m], px_all[m], now, kill=bool(kill_at and now >= kill_at), lit=lit, depth=depth)
    return S


def replay_summary(R_today: dict, day: str, R_prev=None, prev_day=None, lit=None) -> dict:
    """A recorded day from its 5m SUMMARY only (what the cloud receives; raw ticks stay on the PC) through the same step():
    decisions at each bar close, fills at the next bar's open + 1 tick (= replay_frame / of_study._sim_df). Lane C needs the raw
    depth snapshots, so it is empty here."""
    b = R_today["bars"]
    if not len(b):
        return new_state(day)
    tt = b.t.to_numpy(np.int64) * 1000
    px = b.o.to_numpy(float)
    now = int(b.t.iloc[-1]) + 600
    if et_day(now) == day and _mod(now) < 16 * 60 + 1:
        now = int(_et(now).replace(hour=16, minute=1).timestamp())
    return step(new_state(day), day, R_today, R_prev, prev_day, tt, px, now, lit=lit)


def replay(day: str, root: str = ROOT) -> dict:
    from . import tickrec
    x = tickrec.read_day(day)
    if x is None:
        return {"error": f"no stored ticks for {day}"}
    from . import ofsum
    x = ofsum.pick_root(x)
    pday, Rp = _prev_summary(day, None, root)
    S = replay_frame(x, day, Rp, pday)
    return {"line": line(S), "today": S["today"], "rows": S["rows"]}


def loop(root: str = ROOT, every: float = 30.0):
    while True:
        r = tick(root=root)
        if r.get("line"):
            print(_et(time.time()).strftime("%H:%M:%S"), r["line"], flush=True)
        if _mod(time.time()) > 16 * 60 + 10 or r.get("off"):
            return
        time.sleep(every)


def selftest() -> bool:
    """Replay of a synthetic planted day = research's LVL entries + _sim_df exactly (the full proof: tests/test_of_paper.py)."""
    B, M, _ = _mods()
    sp = importlib.util.spec_from_file_location("ofp_sim", os.path.join(ROOT, "research", "orderflow", "of_sim.py"))
    Sim = importlib.util.module_from_spec(sp); sp.loader.exec_module(Sim)
    rng = np.random.default_rng(5)
    days = ["2026-11-02", "2026-11-03"]
    p = 80_000
    xs = {}
    for d in days:
        xs[d], _, _, p = Sim.simulate_day(d, p, rng)
    Rp = summary_of(xs[days[0]], days[0])
    S = replay_frame(xs[days[1]], days[1], Rp, days[0])
    Rt = summary_of(xs[days[1]], days[1])
    D = {days[0]: B.Day(days[0], Rp), days[1]: B.Day(days[1], Rt)}
    ref = [r for r in M.entry_rows(D, days, [], []) if r[0] == "LVL" and r[1] == days[1]]
    mine = [r for r in S["rows"] if r.get("usd_500") is not None]
    ok = len(ref) == len(mine) and all(abs(a[4] - b["usd_500"]) < 0.02 and a[3] == b["d"] for a, b in zip(ref, mine))
    print("of_paper selftest:", "OK" if ok else "FAIL", f"| research LVL {len(ref)} = paper {len(mine)} |", line(S))
    return bool(ok)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="engine.of_paper")
    ap.add_argument("cmd", choices=("tick", "loop", "replay", "show", "selftest"))
    ap.add_argument("--day")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        return 0 if selftest() else 1
    if a.cmd == "tick":
        print(json.dumps(tick(force=a.force), default=str)[:600]); return 0
    if a.cmd == "loop":
        loop(); return 0
    if a.cmd == "replay":
        r = replay(a.day or et_day(time.time() - 86400))
        print(r.get("line") or r); return 0
    S = _rj(os.path.join(ROOT, "data", STATE_NAME))
    print(line(S) or "no OF paper state yet"); return 0


if __name__ == "__main__":
    sys.exit(main())
