"""ATLAS real fills (2026-11-20, night-atlasfills): why ATLAS's real NinjaTrader entries fill 9-15 ticks worse than its
backtest, what that does to the money at 3 / 6 / 10 ticks a side, and 6 pre-registered fixes.
Design (committed before any run): research/second/atlas_fills_design.md. Write-up: research/writeups/atlas-fills-2026-11-20.md.

RESEARCH ONLY. Nothing here touches second_model.json, data/account_b.json, live_model*.json or any engine file.

  python -X utf8 tools/atlas_fills.py why        # every real fill vs its model price + the bars around it -> atlas_fills_why.json
  python -X utf8 tools/atlas_fills.py costs      # funded 25K + fixed view + Rapid 25K lane at 1 / 3 / 6 / 10 ticks a side
  python -X utf8 tools/atlas_fills.py fixes      # F1-F6 at 3 / 6 / 10 ticks a side, the gate
  python -X utf8 tools/atlas_fills.py posthoc    # P1 / P2 (added after the fixes ran: shown, never eligible)
  python -X utf8 tools/atlas_fills.py card       # "real slippage so far" data block (tools/fill_cost.py) for the phone
  python -X utf8 tools/atlas_fills.py all

Cost model (design): N ticks PER SIDE in total (the backtest's 1 tick included): entry N ticks worse than the 5m open, every
non-target exit N ticks worse than its level, a target (resting limit) 0. Sizes unchanged (the bot sizes from the model).
Trades: tools/atlas_more.py's units (the live ATLAS: never opposite LIT incl. its armed setups) -> a fix acts on the units
(a skipped / unfilled signal leaves the slot free for a later one) -> ATLAS's own one position + max 2 a day.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)

ET = ZoneInfo("America/New_York")
DATE = "2026-11-20"
TICK = 0.25
OUT = os.path.join(ROOT, "research", "second", "atlas_fills.json")
OUT_WHY = os.path.join(ROOT, "research", "second", "atlas_fills_why.json")
DESIGN = "research/second/atlas_fills_design.md"
COSTS = (1, 3, 6, 10)                  # ticks a side, total
MEASURED = {"entry": 13, "exit": 1}    # the 3 fills' mean vs the 5m open (12.7); no real exit price exists
JUDGE = (6, 10)
FIXES = {
    "F1_limit_at_open": {"kind": "limit", "x": 0, "timeout": 5},
    "F2_limit_4t": {"kind": "limit", "x": 4, "timeout": 5},
    "F3_enter_1m_close": {"kind": "late1m"},
    "F4_skip_fast_bar": {"kind": "fast", "ratio": 2.0, "n": 20},
    "F5_member_window": {"kind": "window", "pick_n": 6},
    "F6_london_pause": {"kind": "hours", "from_min": 8 * 60},
}
_C = {}


def _AM():
    from tools import atlas_more as AM
    return AM


def et_min(t):
    x = dt.datetime.fromtimestamp(int(t), ET)
    return x.hour * 60 + x.minute


# ================================================================================================ job 1: the real fills
def _bars_day(pc_days, day):
    p = os.path.join(pc_days, day, "bars", "MNQ_1m.csv.gz")
    if not os.path.exists(p):
        return {}
    out = {}
    with gzip.open(p, "rt") as fh:
        for r in csv.DictReader(fh):
            try:
                out[int(float(r["time"]))] = tuple(float(r[k]) for k in ("open", "high", "low", "close", "volume"))
            except (KeyError, ValueError):
                continue
    return out


def real_fills(pc_days=None):
    """Every live entry row with a broker fill price (data/pc_days, the PC's data branch): model price, the 1m bar open the
    backtests fill at, the fill, ticks worse, $ at the real size, seconds from the open to the ledger row, the bars around."""
    from tools import live_trades as LT
    pc_days = pc_days or LT.PC_DAYS
    out = []
    for day in LT.days(pc_days):
        rows = LT._jsonl_gz(os.path.join(pc_days, day, "trades.jsonl.gz"))
        B = None
        for r in rows:
            if r.get("mode") != "live" or r.get("side") not in ("buy", "sell"):
                continue
            legs = [lg for lg in ((r.get("result") or {}).get("legs") or []) if isinstance(lg, dict) and lg.get("filled") and lg.get("fill_px")]
            if not legs or r.get("entry") is None:
                continue
            if LT.HIDDEN.search(str(r.get("bot") or "")):
                continue
            B = B if B is not None else _bars_day(pc_days, day)
            d = 1 if r["side"] == "buy" else -1
            q = sum(int(lg["filled"]) for lg in legs)
            fill = sum(float(lg["fill_px"]) * int(lg["filled"]) for lg in legs) / q
            et_ = int(r["entry_t"])
            bar = B.get(et_)
            o = bar[0] if bar else None
            prev = [B.get(et_ - 60 * k) for k in range(1, 6)]
            prev5 = [p for p in prev if p]
            sig_rng = (max(p[1] for p in prev5) - min(p[2] for p in prev5)) if len(prev5) == 5 else None
            base20 = []
            for j in range(1, 21):
                blk = [B.get(et_ - 300 * j - 60 * k) for k in range(1, 6)]
                if all(blk):
                    base20.append(max(b[1] for b in blk) - min(b[2] for b in blk))
            bot = "ATLAS" if str(r.get("bot")) == "atlas" or "acctb" in str(r.get("src") or "") else "Zlarior"
            fav = ((bar[1] - o) if d == 1 else (o - bar[2])) if bar else None
            out.append({
                "day": day, "bot": bot, "member": r.get("strategy") or "", "et": dt.datetime.fromtimestamp(et_, ET).strftime("%H:%M"),
                "entry_t": et_, "side": "BUY" if d == 1 else "SELL", "qty": q, "model": float(r["entry"]), "open": o, "fill": round(fill, 2),
                "ticks_vs_model": round((fill - float(r["entry"])) * d / TICK, 1),
                "ticks_vs_open": round((fill - o) * d / TICK, 1) if o is not None else None,
                "usd_vs_model": round((fill - float(r["entry"])) * d * 2.0 * q, 2),
                "ledger_s_after_open": int(r.get("t") or 0) - et_ if r.get("t") else None,
                "stop": r.get("stop"), "risk_pts_model": round(abs(float(r["entry"]) - float(r["stop"])), 2) if r.get("stop") else None,
                "slip_share_of_risk": round(abs(fill - float(r["entry"])) / abs(float(r["entry"]) - float(r["stop"])), 3) if r.get("stop") else None,
                "entry_bar": {"o": bar[0], "h": bar[1], "l": bar[2], "c": bar[3], "v": bar[4]} if bar else None,
                "entry_bar_fav_pts": round(fav, 2) if fav is not None else None,
                "fill_share_of_fav": round(((fill - o) * d) / fav, 2) if fav else None,
                "prev_1m_range": round(prev[0][1] - prev[0][2], 2) if prev[0] else None,
                "prev_1m_move_dir": round((prev[0][3] - prev[0][0]) * d, 2) if prev[0] else None,
                "prev_1m_vol": prev[0][4] if prev[0] else None, "entry_1m_vol": bar[4] if bar else None,
                "signal_5m_range": round(sig_rng, 2) if sig_rng is not None else None,
                "signal_5m_ratio": round(sig_rng / float(np.median(base20)), 2) if sig_rng is not None and len(base20) >= 10 else None,
                "signal_5m_move_dir": round((prev[0][3] - prev[4][0]) * d, 2) if len(prev5) == 5 else None,
                "around": [[dt.datetime.fromtimestamp(et_ + 60 * k, ET).strftime("%H:%M"), *B[et_ + 60 * k][:4]]
                           for k in range(-3, 4) if (et_ + 60 * k) in B],
            })
    return sorted(out, key=lambda x: x["entry_t"])


def population():
    """Where the live fills' entry conditions sit among ATLAS's 2026 backtest entries (signal 5m bar range / its 20-bar
    median, the last 1m bar's range, the entry 1m bar's move in the trade's direction, the minute of the hour)."""
    AM = _AM()
    B5, B1 = AM._bars()
    U = AM.base_units()
    rng5 = B5.h - B5.l
    out = []
    for u in U:
        if u["day"] < "2026-01-01":
            continue
        k = int(np.searchsorted(B5.t, int(u["entry_t"])))
        if k < 21 or k >= len(B5.t) or int(B5.t[k]) != int(u["entry_t"]):
            continue
        ratio = float(rng5[k - 1] / max(1e-9, np.median(rng5[k - 21:k - 1])))
        j = int(np.searchsorted(B1.t, int(u["entry_t"])))
        p1 = float(B1.h[j - 1] - B1.l[j - 1]) if 0 < j < len(B1.t) and int(B1.t[j]) == int(u["entry_t"]) else None
        d = int(u["dir"])
        fav = (float(B1.h[j] - B1.o[j]) if d == 1 else float(B1.o[j] - B1.l[j])) if p1 is not None else None
        out.append({"src": u["src"], "ratio": ratio, "prev1m": p1, "fav": fav, "m": et_min(u["entry_t"]) % 60, "R": float(u["pts"]) / float(u["risk"])})
    return out


def cmd_why(log=print):
    F = real_fills()
    P = population()
    pct = lambda arr, x: round(100.0 * float(np.mean(np.asarray(arr) <= x)), 1) if x is not None and len(arr) else None  # noqa: E731
    ra = [p["ratio"] for p in P]
    p1 = [p["prev1m"] for p in P if p["prev1m"] is not None]
    fv = [p["fav"] for p in P if p["fav"] is not None]
    for f in F:
        f["pct_signal_ratio_2026"] = pct(ra, f.get("signal_5m_ratio"))
        f["pct_prev_1m_range_2026"] = pct(p1, f.get("prev_1m_range"))
        f["pct_entry_fav_2026"] = pct(fv, f.get("entry_bar_fav_pts"))
    at = [f for f in F if f["bot"] == "ATLAS"]
    summ = {"atlas_n": len(at), "atlas_ticks_vs_model": [f["ticks_vs_model"] for f in at],
            "atlas_ticks_vs_open": [f["ticks_vs_open"] for f in at],
            "atlas_mean_vs_model": round(float(np.mean([f["ticks_vs_model"] for f in at])), 1) if at else None,
            "atlas_usd_per_micro": round(float(np.mean([f["ticks_vs_model"] for f in at])) * TICK * 2.0, 2) if at else None,
            "pop_2026": {"n": len(P), "signal_ratio_med": round(float(np.median(ra)), 2) if ra else None,
                         "prev_1m_range_med": round(float(np.median(p1)), 2) if p1 else None,
                         "entry_fav_med": round(float(np.median(fv)), 2) if fv else None,
                         "share_signal_ratio_over_2": round(100.0 * float(np.mean(np.asarray(ra) > 2.0)), 1) if ra else None,
                         "minute_of_hour": dict(sorted(collections.Counter(p["m"] for p in P).items()))}}
    out = {"date": DATE, "fills": F, "summary": summ}
    with open(OUT_WHY, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    for f in F:
        log(f"{f['day']} {f['et']} {f['bot']:7s} {f['member']:5s} {f['side']} {f['qty']}  model {f['model']:,.2f} open {f['open']} fill "
            f"{f['fill']:,.2f}  {f['ticks_vs_model']:+.0f}t vs model ({f['ticks_vs_open']:+.0f} vs open) ${f['usd_vs_model']:+.2f}  "
            f"row +{f['ledger_s_after_open']}s  fav {f['entry_bar_fav_pts']} (fill {f['fill_share_of_fav']})  prev1m {f['prev_1m_range']} "
            f"(p{f['pct_prev_1m_range_2026']})  sig5m x{f['signal_5m_ratio']} (p{f['pct_signal_ratio_2026']})  vol {f['prev_1m_vol']}->{f['entry_1m_vol']}")
    log(json.dumps(summ))
    log(f"wrote {os.path.relpath(OUT_WHY, ROOT)}")
    return out


# ================================================================================================ trades at a cost / with a fix
def units():
    return _AM().base_units()


def is_target(u):
    return str(u.get("exit", "")).upper() == "TARGET"


def priced(u, s_entry, s_exit):
    """one unit at s_entry ticks on the entry and s_exit ticks on a non-target exit (totals; the stored unit has 1 + 1)."""
    ex = 0.0 if is_target(u) else (s_exit - 1) * TICK
    pts = float(u["pts"]) - (s_entry - 1) * TICK - ex
    w1 = min(0.0, float(u["w1"]) - (s_entry - 1) * TICK, pts)
    return {**u, "pts": round(pts, 4), "w1": round(w1, 4)}


def _bars():
    return _AM()._bars()


def _open5(u):
    B5, _ = _bars()
    k = int(np.searchsorted(B5.t, int(u["entry_t"])))
    return k, float(B5.o[k])


def limit_fill(u, x, n, timeout=5):
    """F1 / F2: (filled unit | None). The market at arrival is n ticks past the open (dir space: higher = worse)."""
    if n <= x:
        return priced(u, n, n)
    B5, B1 = _bars()
    d = int(u["dir"])
    k5, o = _open5(u)
    Lq = o * d + x * TICK                       # the limit in dir space
    need = Lq - TICK                            # a trade 1 tick through the limit (dir space low)
    et_ = int(u["entry_t"])
    fill_m = None
    on1 = et_ >= int(B1.t[0]) + 86400
    if on1:
        j = int(np.searchsorted(B1.t, et_))
        if j < len(B1.t) and int(B1.t[j]) == et_:
            for m in range(timeout):
                if j + m >= len(B1.t) or int(B1.t[j + m]) >= et_ + 60 * timeout:
                    break
                lo_q = float(B1.l[j + m]) * d if d == 1 else -float(B1.h[j + m])
                c_q = float(B1.c[j + m]) * d
                if (m == 0 and c_q <= need) or (m > 0 and lo_q <= need):
                    fill_m = m
                    break
        else:
            on1 = False
    if not on1:
        c_q = float(B5.c[k5]) * d
        if c_q <= need:
            fill_m = timeout - 1
    if fill_m is None:
        return None
    if is_target(u) and int(u["exit_t"]) < et_ + 60 * (fill_m + 1):
        return None                              # the runner left before the limit filled
    return priced(u, x, n)


def late_1m(u, n):
    """F3: market at the 2nd 1m bar's open (+60 s); same stop / target prices; None = skipped (stop / target in minute 1)."""
    B5, B1 = _bars()
    et_ = int(u["entry_t"])
    if et_ < int(B1.t[0]) + 86400:
        return "untestable"
    j = int(np.searchsorted(B1.t, et_))
    if j + 1 >= len(B1.t) or int(B1.t[j]) != et_ or int(B1.t[j + 1]) != et_ + 60:
        return "untestable"
    d = int(u["dir"])
    _, o = _open5(u)
    e_q = o * d + TICK                          # the stored entry (dir space)
    s_q = e_q - float(u["risk"])
    t_q = e_q + float(u["tgt"]) if u.get("tgt") else None
    lo_q = float(B1.l[j]) if d == 1 else -float(B1.h[j])
    hi_q = float(B1.h[j]) if d == 1 else -float(B1.l[j])
    if lo_q <= s_q or (t_q is not None and hi_q >= t_q):
        return None
    if int(u["exit_t"]) <= et_ + 60:
        return None
    e2 = float(B1.o[j + 1]) * d + n * TICK
    risk = e2 - s_q
    if risk <= 0.5:
        return None
    x_q = e_q + float(u["pts"]) + (0.0 if is_target(u) else 0.0)
    ex = 0.0 if is_target(u) else (n - 1) * TICK
    pts = x_q - e2 - ex
    w1 = min(0.0, float(u["w1"]) + (e_q - e2), pts)
    w1 = max(w1, -(risk + n * TICK))
    return {**u, "entry_t": et_ + 60, "risk": round(risk, 4), "tgt": round(t_q - e2, 4) if t_q is not None else u.get("tgt"),
            "pts": round(pts, 4), "w1": round(w1, 4)}


def fast_ratio(u, nbar=20):
    B5, _ = _bars()
    k, _ = _open5(u)
    if k < nbar + 1:
        return None
    rng = B5.h[k - nbar - 1:k] - B5.l[k - nbar - 1:k]
    return float(rng[-1] / max(1e-9, np.median(rng[:-1])))


def windows_pick(n, log=print):
    """F5: each member's [a, b) ET hour window with the most 2026 Jan-Jun fixed-view $ at n ticks (member alone, $250 a trade)."""
    U = [priced(u, n, n) for u in units()]
    out = {}
    for m in sorted({u["src"] for u in U}):
        Um = [u for u in U if u["src"] == m and "2026-01-01" <= u["day"] <= "2026-06-30"]
        hrs = sorted({et_min(u["entry_t"]) // 60 for u in Um})
        best = None
        for a in hrs:
            for b in range(a + 2, hrs[-1] + 2):
                L = [u for u in Um if a <= et_min(u["entry_t"]) // 60 < b]
                usd = sum(int(250.0 // ((u["risk"] + TICK) * 2.0 + 1.9)) * (u["pts"] * 2.0 - 1.9) for u in L)
                if best is None or usd > best[2] + 1e-9:
                    best = (a, b, usd, len(L))
        out[m] = {"from_h": best[0], "to_h": best[1], "h1_usd": round(best[2]), "n": best[3], "hours": hrs}
        log(f"  F5 pick {m}: {best[0]:02d}:00-{best[1]:02d}:00 ET (member hours {hrs[0]}-{hrs[-1]}), Jan-Jun ${best[2]:,.0f} on {best[3]}")
    return out


def fix_units(name, n, pick=None, london_half=False):
    """The units of fix `name` at n ticks a side (None = today's market entry). -> (units, notes)."""
    F = FIXES.get(name) or {}
    out, note = [], collections.Counter()
    for u in units():
        nn = n
        if london_half and et_min(u["entry_t"]) >= 8 * 60:
            nn = max(1, int(round(n / 2)))
        k = F.get("kind")
        if k == "limit":
            v = limit_fill(u, F["x"], nn, F["timeout"])
            if v is None:
                note["unfilled"] += 1
                continue
            out.append(v)
            continue
        if k == "late1m":
            v = late_1m(u, nn)
            if v == "untestable":
                note["untestable_5m_only"] += 1
                out.append(priced(u, nn, nn))
                continue
            if v is None:
                note["skipped_min1"] += 1
                continue
            out.append(v)
            continue
        if k == "fast":
            r = fast_ratio(u, F["n"])
            if r is not None and r > F["ratio"]:
                note["skipped_fast"] += 1
                continue
        if k == "window":
            w = (pick or {}).get(u["src"])
            h = et_min(u["entry_t"]) // 60
            if w and not (w["from_h"] <= h < w["to_h"]):
                note["outside_window"] += 1
                continue
        if k == "hours" and et_min(u["entry_t"]) < F["from_min"]:
            note["london_skipped"] += 1
            continue
        out.append(priced(u, nn, nn))
    return out, dict(note)


POST_HOC = {   # added after the fixes ran (shown, never eligible): what the 3 real trades and F1 / F3 suggested
    "P1_limit_1m_then_market": "a limit at the open for 60 s (minute 1 closes 1 tick through it = filled at the open), else market at "
                               "the 2nd 1m open (+ N ticks); 2026 only",
    "P2_F3_at_3t": "F3 (enter on the 1m close) IF an entry off the 5m boundary slips like Zlarior's (3 ticks) while today's slips N",
}


def p1_units(n):
    """P1 (post-hoc): limit at the open 60 s, else chase at market at the 2nd 1m open. 2026 only (5m-only spans = market)."""
    _, B1 = _bars()
    out = []
    for u in units():
        et_ = int(u["entry_t"])
        j = int(np.searchsorted(B1.t, et_))
        if et_ < int(B1.t[0]) + 86400 or j >= len(B1.t) or int(B1.t[j]) != et_:
            out.append(priced(u, n, n))
            continue
        d = int(u["dir"])
        _, o = _open5(u)
        if float(B1.c[j]) * d <= o * d - TICK:
            out.append(priced(u, 0, n))
            continue
        v = late_1m(u, n)
        if isinstance(v, dict):
            out.append(v)
    return out


def cmd_posthoc(log=print):
    out = {"date": DATE, "note": "post-hoc: shown, never eligible (design: research/second/atlas_fills_design.md)", "rows": {}}
    for n in JUDGE:
        r1 = score_funded(to_T(p1_units(n)))
        U3, _ = fix_units("F3_enter_1m_close", 3)
        r2 = score_funded(to_T(U3))
        out["rows"][f"{n}t"] = {"P1_limit_1m_then_market": r1, "P2_F3_at_3t_vs_today_at_n": r2}
        for nm, r in (("P1", r1), ("P2", r2)):
            f, x = r["funded"], r["fixed"]
            log(f"{nm} today at {n}t: funded " + " | ".join(f"{sp} ${f[sp]['per_month']} dead {f[sp]['dead_6m']}" for sp in f)
                + "  fixed " + " | ".join(f"{sp} {x[sp]['tpw']}/wk PF {x[sp]['pf']} ${x[sp]['per_month']}" for sp in x))
    _save("posthoc", out)
    return out


def to_T(U):
    AM = _AM()
    from tools import atlas_revive as RV
    return AM.to_T(RV.one_pos(U))


# ================================================================================================ scoring
def ctx(n_paths=600):
    if "ctx" not in _C:
        import builder_levers as BL
        from tools import atlas_health as AH
        from tools import uprisk as U
        AM = _AM()
        S = AM.sessions()
        PF = {sp: U.mc_paths(S, sp, n_paths, length=BL.LEN, seed=BL.A4.SEED_LIFE) for sp in BL.SPANS}
        RS = AH.real_starts(S)
        _C["ctx"] = (S, PF, RS)
    return _C["ctx"]


def score_funded(T):
    AM = _AM()
    S, PF, RS = ctx()
    r = AM.score(AM.IDEAS["A1_stuck_off"], T, S, PF, RS, quick=True)
    keep = ("per_month", "first_med", "no_pay_6m", "dead_6m", "lost_6m", "stuck_6m", "idle_6m", "payouts")
    return {"fixed": r["fixed"], "funded": {sp: {k: r["funded"][sp][k] for k in keep} for sp in r["funded"]},
            "today_state": {sp: {k: r["today_state"][sp][k] for k in keep} for sp in r["today_state"]}}


def rapid_rows(T, n_paths=1000, with_off=True):
    """tools/money/rapid25.py "25K, keep $500" with ATLAS's trades = T (LIT unchanged); + the same account with ATLAS off."""
    import rapid25 as R25
    import rapid_levers as RL
    import stack_one_account as SOA
    from tools import uprisk as U
    import account4_sim as A4
    AT = [{"day": t["day"], "risk": float(t["risk"]), "tgt": t.get("tgt"), "pts": float(t["pts"]), "w1": float(t["w1"]),
           "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]), "strat": "ATLAS", "src": t["src"]} for t in T]
    SOA._atlas = lambda: AT
    SOA._blitz = lambda: []
    SOA._D.clear()
    RL._MB.clear()
    S = SOA.data()["S"]
    if "rp" not in _C:
        _C["rp"] = {s: U.mc_paths(S, s, n_paths, length=RL.LEN, seed=A4.SEED_LIFE) for s in RL.SPANS}
    PF = _C["rp"]
    spec = R25.acct("25k", ("cushion", 500))
    out = {"on": {s: RL.group_stats(R25.run_group([spec], PF[s])) for s in RL.SPANS}}
    if with_off:
        off = dict(spec)
        off["BYe"], off["BYf"], off["mix_f"] = RL.mix_by(("LIT",)), RL.mix_by(("LIT",), news=True), ("LIT",)
        out["off"] = {s: RL.group_stats(R25.run_group([off], PF[s])) for s in RL.SPANS}
    keep = ("net_m", "first_any_med", "p_none_pays", "lost_6m", "dd_med")
    return {k: {s: {x: v[s][x] for x in keep} for s in v} for k, v in out.items()}


def cmd_costs(log=print, rapid=True):
    t0 = time.time()
    out = {"date": DATE, "design": DESIGN, "costs": {}, "measured": None}
    T1 = to_T(units())
    AM = _AM()
    T0, _ = AM.idea_T(AM.IDEAS["today"])
    assert [(t["entry_t"], round(t["pts"], 3)) for t in T1] == [(t["entry_t"], round(t["pts"], 3)) for t in T0], "base != atlas_more"
    rows = [(f"{n}t", n, n) for n in COSTS] + [("measured", MEASURED["entry"], MEASURED["exit"])]
    for lab, ne, nx in rows:
        T = to_T([priced(u, ne, nx) for u in units()])
        r = score_funded(T)
        if rapid:
            r["rapid"] = rapid_rows(T, with_off=(lab == "1t"))
            if lab != "1t":
                r["rapid"]["off"] = out["costs"]["1t"]["rapid"]["off"]
        out["costs"][lab] = r
        f, x, td = r["funded"], r["fixed"], r["today_state"]
        log(f"{lab:9s} fixed " + " | ".join(f"{sp} {x[sp]['tpw']}/wk PF {x[sp]['pf']} ${x[sp]['net']:,} ${x[sp]['per_month']}/mo dd {x[sp]['max_dd']}" for sp in x))
        log(f"{'':9s} funded " + " | ".join(f"{sp} ${f[sp]['per_month']}/mo 1st {f[sp]['first_med']} dead {f[sp]['dead_6m']}%" for sp in f)
            + "  today's acct " + " | ".join(f"{sp} ${td[sp]['per_month']} dead {td[sp]['dead_6m']}%" for sp in td))
        if rapid:
            rp = r["rapid"]
            log(f"{'':9s} rapid LIT+ATLAS " + " | ".join(f"{s} ${rp['on'][s]['net_m']}/mo 1st {rp['on'][s]['first_any_med']} none {rp['on'][s]['p_none_pays']}%" for s in rp["on"])
                + "  LIT alone " + " | ".join(f"{s} ${rp['off'][s]['net_m']}" for s in rp["off"]) + f"  [{time.time() - t0:.0f}s]")
    out["verdict"] = {lab: worth(r) for lab, r in out["costs"].items()}
    out["took_s"] = round(time.time() - t0)
    _save("costs", out)
    for lab, v in out["verdict"].items():
        log(f"worth running at {lab}: funded {v['funded']}  rapid {v.get('rapid')}")
    return out


def worth(r):
    f, x = r["funded"], r["fixed"]
    ok_f = all(f[sp]["per_month"] > 50 for sp in ("H1", "H2")) and all((x[sp]["pf"] or 0) >= 1.2 for sp in ("H1", "H2"))
    v = {"funded": ok_f, "ref_pf": x["2021-24"]["pf"], "ref_2025_pf": x["2025"]["pf"]}
    if r.get("rapid"):
        rp = r["rapid"]
        v["rapid"] = all(rp["on"][s]["net_m"] > rp["off"][s]["net_m"] for s in ("H1", "H2"))
        v["rapid_gain"] = {s: rp["on"][s]["net_m"] - rp["off"][s]["net_m"] for s in rp["on"]}
    return v


def gate(fx, base, fx3, base3, testable=True):
    why = []
    for n in JUDGE:
        a, b = fx[n], base[n]
        fa, fb = a["funded"], b["funded"]
        for sp in ("H1", "H2"):
            if fa[sp]["per_month"] < fb[sp]["per_month"] + 10:
                why.append(f"{n}t {sp} funded ${fb[sp]['per_month']} -> ${fa[sp]['per_month']}/mo (needs +$10)")
        if fa["REF"]["per_month"] < fb["REF"]["per_month"] - 5:
            why.append(f"{n}t 2021-25 funded ${fb['REF']['per_month']} -> ${fa['REF']['per_month']}/mo")
        for sp in ("H1", "H2", "REF"):
            if fa[sp]["dead_6m"] > fb[sp]["dead_6m"] + 0.5:
                why.append(f"{n}t {sp} dead {fb[sp]['dead_6m']} -> {fa[sp]['dead_6m']}%")
        xa, xb = a["fixed"], b["fixed"]
        for sp in ("H1", "H2"):
            if (xa[sp]["pf"] or 0) < (xb[sp]["pf"] or 0):
                why.append(f"{n}t {sp} PF {xb[sp]['pf']} -> {xa[sp]['pf']}")
        for sp in ("H1", "H2", "2025", "2021-24"):
            if xa[sp]["per_month"] < xb[sp]["per_month"] - 10:
                why.append(f"{n}t {sp} fixed ${xb[sp]['per_month']} -> ${xa[sp]['per_month']}/mo")
        for sp in ("H1", "H2"):
            if not (2.0 <= xa[sp]["tpw"] <= 4.1):
                why.append(f"{n}t {sp} {xa[sp]['tpw']} trades a week")
    for sp in ("H1", "H2"):
        if fx3["funded"][sp]["per_month"] < base3["funded"][sp]["per_month"] - 10:
            why.append(f"3t {sp} funded ${base3['funded'][sp]['per_month']} -> ${fx3['funded'][sp]['per_month']}/mo")
    if not testable:
        why.append("2021-25 cannot be tested (1m bars only in 2026)")
    return (not why), why


def cmd_fixes(log=print):
    t0 = time.time()
    out = {"date": DATE, "design": DESIGN, "judge_ticks": list(JUDGE), "base": {}, "fixes": {}}
    base = {}
    for n in (3,) + JUDGE:
        base[n] = score_funded(to_T([priced(u, n, n) for u in units()]))
    out["base"] = {f"{n}t": v for n, v in base.items()}
    pick = windows_pick(FIXES["F5_member_window"]["pick_n"], log)
    out["f5_pick"] = pick
    for nm in FIXES:
        res, notes = {}, {}
        for n in (3,) + JUDGE:
            U, note = fix_units(nm, n, pick=pick)
            res[n] = score_funded(to_T(U))
            notes[f"{n}t"] = note
        ok, why = gate(res, base, res[3], base[3], testable=(nm != "F3_enter_1m_close"))
        row = {"spec": FIXES[nm], "notes": notes, "gate_ok": ok, "gate_why": why, **{f"{n}t": v for n, v in res.items()}}
        if nm == "F6_london_pause":
            lh = {}
            for n in JUDGE:
                Ub, _ = fix_units("none", n, london_half=True)
                Uf, _ = fix_units(nm, n, london_half=True)
                lh[f"{n}t"] = {"base": score_funded(to_T(Ub))["funded"], "fix": score_funded(to_T(Uf))["funded"]}
            row["view_london_n_ny_half"] = lh
        out["fixes"][nm] = row
        for n in (3,) + JUDGE:
            f, b, x = res[n]["funded"], base[n]["funded"], res[n]["fixed"]
            log(f"{nm:20s} {n:2d}t funded " + " | ".join(f"{sp} ${b[sp]['per_month']}->${f[sp]['per_month']} dead {b[sp]['dead_6m']}->{f[sp]['dead_6m']}" for sp in f)
                + "  fixed " + " | ".join(f"{sp} {x[sp]['tpw']}/wk PF {x[sp]['pf']} ${x[sp]['per_month']}" for sp in x) + f"  {notes[f'{n}t']}")
        log(f"{'':20s} {'PASS' if ok else 'no: ' + '; '.join(why)[:500]}  [{time.time() - t0:.0f}s]")
    out["passers"] = [nm for nm, r in out["fixes"].items() if r["gate_ok"]]
    out["took_s"] = round(time.time() - t0)
    _save("fixes", out)
    log(f"passers: {out['passers']}")
    return out


def _save(key, block):
    cur = {}
    if os.path.exists(OUT):
        try:
            cur = json.load(open(OUT, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            cur = {}
    cur[key] = block
    cur["date"] = DATE
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(cur, fh, indent=1, default=float)


def cmd_card(log=print):
    """the phone's line per bot from the pulled days (the ZEUS card gets it via tools/learn_night.card_doc)."""
    from tools import fill_cost as FC
    out = {k: FC.block(fl) for k, fl in FC.from_rows().items()}
    for k, b in sorted(out.items()):
        log(f"{k:8s} {b['line'] if b else '-'}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["why", "costs", "fixes", "posthoc", "card", "all"])
    ap.add_argument("--no-rapid", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd in ("why", "all"):
        cmd_why()
    if a.cmd in ("costs", "all"):
        cmd_costs(rapid=not a.no_rapid)
    if a.cmd in ("fixes", "all"):
        cmd_fixes()
    if a.cmd in ("posthoc", "all"):
        cmd_posthoc()
    if a.cmd in ("card", "all"):
        cmd_card()
    return 0


if __name__ == "__main__":
    sys.exit(main())
