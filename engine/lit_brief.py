"""LIT day analyst: the morning briefing, the intraday log and the end-of-day recap (cloud monitor + phone app).

Pure functions, no network. From the bars the cloud monitor already loads (5m; the 1m-based decisions come in through the
live loop's result), the LIT engine (engine/lit.py Market / levels / candidates, the same builders engine/lit_live.py and the
litkit "Levels" / "Day plan" panels use), the news hub file (data/news/hub.json, tools/news_hub.py; fallback the stored
calendar data/news/events.csv), the VIX band and the eval state (state eval / eval_2wk, engine/sizing.py):

    brief = build(df5, now, params=lm["lit"], live=res, prev=old_state.get("brief"), news=hub, ev=..., clock=...)

  morning  built on the first run after 01:30 ET, refreshed once after 07:30 ET: the LIT map (Asia / London / NY trap boxes,
           PDH/PDL, PWH/PWL, PMH/PML, NWOG/NDOG, build-ups: untaken or taken, which side was taken overnight), the Monday
           rule, the weekly stop, the VIX one-day band (target), today's high-impact USD news, the eval (session N of 10, $ to
           the target, room to the floor, max micros + $ risk at a typical stop) and a one-line game plan in plain words
  now      every run: price, model state, levels left above / below, what the bot waits for
  log      every run: what changed (level swept + depth in ATR, box closed, 5m CISD with its inducement and displacement,
           setup armed / rejected and the rule, limit tapped, entry, exit), newest first, kept for the day; `new` marks the
           entries this run added
  recap    after 16:00 ET: the day's result, what the setups did, a lesson line (engine/lit_learn.py cause codes, read-only)
  prev     yesterday's recap (shown until today's exists)

Look-ahead: everything is computed from the 5m bars that closed by `now` (bars after `now` are cut here) and from the live
loop's result at `now`; tests/test_lit_brief.py checks it. Never sends a notification.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import statistics as stx
from zoneinfo import ZoneInfo

import numpy as np

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = 1
MORNING_AT = 90          # 01:30 ET: first morning briefing
REFRESH_AT = 450         # 07:30 ET: refreshed once
RECAP_AT = 960           # 16:00 ET: end-of-day recap
LOG_MAX = 90
# the trap boxes the briefing names (engine/lit.py SESSIONS keys; litkit / lit_dash_extra BOXES)
BOXES = [("asia20", "Asia", 1200, 1440), ("lon23", "Frankfurt", 120, 180), ("lon34", "London", 180, 240),
         ("pre", "Premarket", 240, 570), ("ny89", "NY 08-09", 480, 540)]
# level name priority for the map (first wins when two names share a price)
PRIO = ["pdh", "pdl", "pwh", "pwl", "pmh", "pml", "asia20_h", "asia20_l", "lon34_h", "lon34_l", "lon23_h", "lon23_l",
        "ny89_h", "ny89_l", "pre_h", "pre_l", "nwog", "ndog"]
NEWS_KW = ("cpi", "fomc", "nfp", "non-farm", "payroll", "pce", "gdp", "fed chair", "powell", "warsh", "ppi", "retail", "ism",
           "jolts", "rate decision", "minutes", "unemployment rate", "employment")


# ------------------------------------------------------------------------------------------------ small helpers
def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def _hm(t):
    return _et(t).strftime("%H:%M")


def _mod(t):
    e = _et(t)
    return e.hour * 60 + e.minute


def tday(t) -> str:
    return str((_et(t) + dt.timedelta(hours=6)).date())


def _px(x):
    return f"{float(x):,.2f}".rstrip("0").rstrip(".") if x is not None else "-"


def _usd(x):
    return ("-" if x < 0 else "") + f"${abs(float(x)):,.0f}"


def _susd(x):
    return ("+" if x > 0 else "-" if x < 0 else "") + f"${abs(float(x)):,.0f}"


def _rel(mod):
    """Minutes since 18:00 ET (the trading day's order)."""
    return (int(mod) - 1080) % 1440


def _side(d):
    return "LONG" if d == 1 else "SHORT"


def _f(x, nd=2):
    try:
        return round(float(x), nd)
    except (TypeError, ValueError):
        return None


def _label(nm, side):
    from engine.lit_live import _sweep_names
    if nm in ("bu_h", "bu_l"):
        return "equal highs" if side == "high" else "equal lows"
    if nm in ("nwog", "ndog"):
        return f"{nm.upper()} {'top' if side == 'high' else 'bottom'}"
    return _sweep_names([nm])[0]


def _join(xs, n=3):
    xs = list(dict.fromkeys(xs))
    if len(xs) <= n:
        return ", ".join(xs[:-1]) + (" and " if len(xs) > 1 else "") + xs[-1] if xs else ""
    return ", ".join(xs[:n]) + f" +{len(xs) - n} more"


# ------------------------------------------------------------------------------------------------ market at `now`
def market_at(df5, now, params=None, sym="NQ"):
    """(Market, candidates) of the LIT window on the 5m bars that closed by `now` (same window rule as engine/lit_live.py)."""
    from engine import lit, lit_live
    from engine.data import from_frame
    P = {**lit.DEFAULTS, **(params or {})}
    d = lit_live._clean5(df5)
    d = d[d["time"] + 300 <= int(now)]
    if not len(d):
        return None, [], P
    w = d[d["time"] >= lit_live.window_start(int(d["time"].max()))]
    M = lit.Market(bars=from_frame(sym, "5m", w), extra_boxes=P.get("extra_boxes") or [])
    C = lit.candidates(M, ref=P["ref"])
    return M, C, P


def _box_open(nm, now):
    """True while session box `nm` (engine/lit.py SESSIONS key + _h/_l) is still forming at `now` (not a level yet)."""
    from engine import lit
    base = nm.rsplit("_", 1)[0]
    w = lit.SESSIONS.get(base) or (lit.EXTRA_BOXES.get(base) or (None, None))[:2]
    if not w or w[0] is None or now is None:
        return False
    rn, ra, rz = _rel(_mod(now)), _rel(w[0]), _rel(w[1] % 1440)
    return ra <= rn < rz or rn < ra


def level_map(M, k, last, now=None):
    """Every LIT level of day k known by bar `last` and untaken when the day began: status untaken / taken (first breach
    bar, depth of the sweep leg in ATR). A session box still forming at `now` is not a level yet. Duplicates by price
    collapse to the higher-priority name."""
    x = M.ctx[k]
    s = x["s"]
    rows, seen = [], {}
    L = sorted(M.levels(k), key=lambda z: (PRIO.index(z[3]) if z[3] in PRIO else 99))
    for side, px, ki, nm, cls in L:
        if ki > last or (cls in ("asia", "london", "ny", "pre", "x_ny") and _box_open(nm, now)):
            continue
        a = max(ki + 1, s - 600)
        if side == "high":
            pre = M.h[a:s]
            hit = np.flatnonzero(M.h[max(a, s):last + 1] > px)
        else:
            pre = M.l[a:s]
            hit = np.flatnonzero(M.l[max(a, s):last + 1] < px)
        if len(pre) and ((side == "high" and pre.max() > px) or (side == "low" and pre.min() < px)):
            continue                                   # traded through before today: not today's liquidity
        key = (side, round(float(px), 2))
        if key in seen:
            seen[key]["also"].append(_label(nm, side))
            continue
        r = {"name": nm, "label": _label(nm, side), "side": "H" if side == "high" else "L", "price": round(float(px), 2),
             "kind": cls, "known_t": int(M.t[ki]) + 300 if ki >= 0 else None, "taken": False, "also": []}
        if len(hit):
            j = max(a, s) + int(hit[0])
            # depth of the sweep leg: from the breach until a close back across the level (the reclaim) or 2 hours
            z = min(last, j + 24)
            back = np.flatnonzero(M.c[j:z + 1] < px) if side == "high" else np.flatnonzero(M.c[j:z + 1] > px)
            z = j + int(back[0]) if len(back) else z
            ext = M.h[j:z + 1].max() - px if side == "high" else px - M.l[j:z + 1].min()
            r.update(taken=True, taken_i=int(j), taken_t=int(M.t[j]), depth_atr=round(float(ext) / max(float(M.atr[j]), 1e-9), 2),
                     depth_pts=round(float(ext), 2))
        seen[key] = r
        rows.append(r)
    return rows


def boxes(M, k, last, now):
    """The trap boxes' status today: not yet / forming / done (high, low, each side taken or not)."""
    x = M.ctx[k]
    s = x["s"]
    rn = _rel(_mod(now))
    out = []
    for nm, lab, a, z in BOXES:
        ra, rz = _rel(a), _rel(z % 1440)
        b = {"key": nm, "label": lab, "window": f"{a // 60:02d}:{a % 60:02d}-{(z % 1440) // 60:02d}:{z % 60:02d}"}
        if nm in x and x[nm][2] <= last and not _box_open(nm + "_h", now):
            hi, lo, ki = x[nm]
            hj = np.flatnonzero(M.h[ki + 1:last + 1] > hi)
            lj = np.flatnonzero(M.l[ki + 1:last + 1] < lo)
            b.update(status="done", high=round(hi, 2), low=round(lo, 2), done_t=int(M.t[ki]) + 300,
                     high_taken_t=int(M.t[ki + 1 + hj[0]]) if len(hj) else None,
                     low_taken_t=int(M.t[ki + 1 + lj[0]]) if len(lj) else None)
        elif ra <= rn < rz:
            seg_h, seg_l = M.h[s:last + 1], M.l[s:last + 1]
            md = M.mod[s:last + 1]
            m = (md >= a) & (md < z) if z != 1440 else (md >= a)
            b.update(status="forming", high=round(float(seg_h[m].max()), 2) if m.any() else None,
                     low=round(float(seg_l[m].min()), 2) if m.any() else None)
        else:
            b.update(status="not yet" if rn < ra else "missing")
        out.append(b)
    return out


# ------------------------------------------------------------------------------------------------ news / eval inputs
def _events_csv(day):
    p = os.path.join(ROOT, "data", "news", "events.csv")
    out = []
    try:
        with open(p, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("date") == day and r.get("impact") == "high":
                    out.append({"time": r.get("time_et") or "", "title": r.get("event") or "", "impact": "high", "source": "calendar"})
    except OSError:
        pass
    return out


def news_today(day, hub=None):
    """High-impact USD events of calendar date `day`: the news hub (data/news/hub.json) when it covers the day, else the
    stored calendar (data/news/events.csv)."""
    ev = []
    if hub and isinstance(hub, dict):
        rng = hub.get("range") or {}
        covered = (rng.get("from") or "9") <= day <= (rng.get("to") or "0") or any(e.get("date") == day for e in hub.get("events") or [])
        if covered:
            for e in hub.get("events") or []:
                if e.get("date") != day or e.get("impact") != "high" or (e.get("country") not in (None, "USD")):
                    continue
                ev.append({"time": e.get("time_et") or "", "title": e.get("title") or "", "impact": "high",
                           "kind": e.get("kind_label") or e.get("kind"), "source": "news hub",
                           **({"blackout": f"{e.get('blackout_start')}-{e.get('blackout_end')}"} if e.get("blackout_start") else {})})
            if ev or covered:
                return _dedupe_news(ev), "news hub"
    return _dedupe_news(_events_csv(day)), "calendar"


def _dedupe_news(ev):
    seen, out = set(), []
    for e in sorted(ev, key=lambda e: e["time"]):
        k = (e["time"], e["title"].lower())
        if k not in seen:
            seen.add(k); out.append(e)
    return out


def news_text(ev):
    if not ev:
        return "No high-impact USD news today."
    big = [e for e in ev if any(w in e["title"].lower() for w in NEWS_KW)] or ev
    names = _join([f"{e['title']} {e['time']}" for e in big], 4)
    return (f"High-impact USD news today: {names}. LIT does not pause for news: price can spike through a level and the stop "
            f"in seconds around a release; a sweep made by the release still counts as a sweep.")


_STOP = {}


def typical_stop():
    """Median planned stop (pts) of the live LIT 2026 run (research/runs/lit_live.json); 46 when it is missing."""
    if "v" not in _STOP:
        v = 46.0
        try:
            with open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8") as fh:
                r = json.load(fh)
            i = r["trade_cols"].index("risk_pts")
            T = [t[i] for t in r["trades"] if str(t[0]).startswith("2026")]
            if T:
                v = round(float(stx.median(T)), 1)
        except Exception:
            pass
        _STOP["v"] = v
    return _STOP["v"]


def size_today(stop, tgt, clock=None, ev=None, lit_sizing=None, params=None, wk_mult=1.0):
    """Max micros and $ risk of one LIT entry today at a `stop`-pt stop and a `tgt`-pt target, with the live sizing switch
    (lit_sizing.mode; two_week = engine/sizing.two_week_qty on the eval clock's state)."""
    from engine import lit, sizing
    ls = lit_sizing or {}
    mode = ls.get("mode") or "normal"
    why = []
    q0 = lit.qty_for(stop, (params or {}).get("risk_usd", 800.0), (params or {}).get("risk_ref_stop", 20.0))
    q0 = max(1, int(q0 * wk_mult + 1e-9)) if wk_mult < 1 else q0
    q = q0
    if mode == "two_week" and clock and clock.get("session"):
        cum = 0.0
        st = {"profit": float(clock.get("profit") or 0.0) - cum, "cum": cum, "room": clock.get("room"), "session": clock.get("session")}
        q = sizing.two_week_qty({"risk_pts": stop, "tgt_pts": tgt, "size_mult": wk_mult}, st, ls.get("two_week"), why=why)
    elif mode != "normal":
        room = (ev or {}).get("cushion")
        r = sizing.lit_qty(q0, {"risk_pts": stop, "size_why": []}, ls, room=room, learning=None)
        q, why = int(r["qty"]), list(r.get("reasons") or [])
    risk = q * ((stop + lit.SLIP) * lit.PV + lit.COMM)
    return {"mode": mode, "stop": stop, "tgt": round(tgt, 1), "qty": int(q), "risk_usd": round(risk), "why": why}


# ------------------------------------------------------------------------------------------------ MFFU account warnings
_RULES = {}


def mffu_rules():
    """The few MFFU Builder 50K rules the brief warns about (research/lit/mffu_rules.json; defaults when it is missing)."""
    if "v" not in _RULES:
        r = {"inactivity_days": 7, "flat": "16:10", "half_day_auto": False}
        try:
            with open(os.path.join(ROOT, "research", "lit", "mffu_rules.json"), encoding="utf-8") as fh:
                e = json.load(fh)["builder_50k"]["eval"]
            r["inactivity_days"] = int(((e.get("inactivity") or {}).get("value") or {}).get("days") or 7)
            r["flat"] = str(((e.get("trading_hours") or {}).get("value") or {}).get("must_be_flat") or "16:10 ET").split()[0]
            r["half_day_auto"] = bool(((e.get("holidays_early_close") or {}).get("value") or {}).get("auto_liquidation"))
        except Exception:
            pass
        _RULES["v"] = r
    return _RULES["v"]


def mffu_notes(now, day, ledger=None, clock=None, eval_start=None, flat_mod=955):
    """In-app MFFU warnings (in-app only): the must-be-flat time (+ the CME early halt on a half-day), the 7-day
    inactivity rule (5+ calendar days since the last fill on the eval ledger) and what to do once the eval passed."""
    from engine.lit_live import early_close
    R = mffu_rules()
    out = []
    fm = f"{flat_mod // 60:02d}:{flat_mod % 60:02d}"
    out.append({"kind": "flat", "level": "info",
                "text": f"MFFU: be flat by {R['flat']} ET (auto-liquidation then); the bot flattens at {fm} ET."})
    ec = early_close(day)
    if ec is not None:
        h = f"{ec // 60:02d}:{ec % 60:02d}"
        out.append({"kind": "half_day", "level": "warn",
                    "text": f"CME half-day: trading halts at {h} ET. MFFU does {'' if R['half_day_auto'] else 'NOT '}auto-flatten at the "
                            f"early halt: be flat before {h} ET (the NinjaTrader route flattens 5 min before)."})
    st = (clock or {}).get("status")
    if st == "passed":
        out.append({"kind": "passed", "level": "good",
                    "text": "Eval passed - switch sizing to funded (tell Claude) and check MFFU marked it passed; if not by next "
                            "morning, place one 1-micro trade (minimum days)."})
    started = eval_start and str(eval_start) <= str(day)
    if started and st not in ("passed", "failed"):
        fills = [int(v.get("entry_t") or 0) for v in ledger or [] if str(v.get("day") or "") >= str(eval_start) and v.get("entry_t")]
        ref = dt.date.fromisoformat(str(max(dt.date.fromisoformat(str(eval_start)[:10]), *(_et(t).date() for t in fills)) if fills
                                    else str(eval_start)[:10]))
        n = (_et(now).date() - ref).days
        if n >= 5:
            out.append({"kind": "inactivity", "level": "warn", "days": n,
                        "text": (f"No trade for {n} days - MFFU can close the account at {R['inactivity_days']}: place 1 MNQ by hand "
                                 f"today (MFFU inactivity rule)." if n >= R["inactivity_days"] - 1 else
                                 f"No trade for {n} days - place 1 MNQ by hand before day {R['inactivity_days']} (MFFU inactivity rule).")
                        if fills else f"No trade for {n} days since the eval started - place 1 MNQ by hand before day "
                                      f"{R['inactivity_days']} (MFFU inactivity rule)."})
    return out


# ------------------------------------------------------------------------------------------------ setup verdicts
def reject_reason(M, z, P):
    """The first LIT rule a 5m CISD candidate fails (engine/lit.py setup_ok / monday_block / stop range / target), or None
    when it passes every filter (then only the 1-trade-a-day / one-at-a-time rule can stop it)."""
    from engine import lit
    if not any(a <= z["mod"] < b for a, b in P["window"]):
        a = min(x for x, _ in P["window"]); b = max(y for _, y in P["window"])
        return "window", f"outside the {a // 60:02d}:{a % 60:02d}-{b // 60:02d}:{b % 60:02d} ET entry window"
    names = set(P["sweep_names"]) if P.get("sweep_names") else None
    if names is None:
        dep = z["depth_atr"]
    else:
        sw = [p for nm, p in z["sw"].items() if nm in names]
        dep = (max(sw) - z["ext_d"]) / max(z["atr_ext"], 1e-9) if sw else 0.0
    if dep < P["depth"]:
        return "depth", f"sweep only {float(dep):.2f} ATR deep (LIT needs {P['depth']:g})"
    if z["disp"] < P["disp"]:
        return "disp", f"displacement {float(z['disp']):.2f} ATR (LIT needs {P['disp']:g})"
    if P.get("idm_a"):
        dm, age, cnt = P["idm_a"]
        if sum(1 for dd, aa in z["idm_a"] if dd <= dm and aa <= age) < cnt:
            return "idm", f"no inducement swing taken first (within {dm:g} ATR of the level, {int(age)} bars)"
    if P.get("nwog_discount") and z["nwog_side"] == 1:
        return "nwog", "wrong side of the NWOG midpoint"
    if P.get("mw_filter") and z.get("mw_break") and z["mw_break"] != z["dir"]:
        return "mw", "against the Monday-Wednesday range break"
    if P.get("monday") and lit.monday_block(M, z):
        return "monday", f"Monday rule: Friday's {'high' if z['dir'] == 1 else 'low'} taken, {'shorts' if z['dir'] == 1 else 'longs'} only"
    ep = min(float(z["ref_d"]), z["trig_c"])
    risk = ep - (z["ext_d"] - P["stop_buf"])
    if not (P["min_stop"] <= risk <= P["max_stop"]):
        return "stop", f"stop {risk:.1f} pts (LIT trades {P['min_stop']:g}-{P['max_stop']:g})"
    sh = z["entry_d"] - ep
    TT = {c: [v + sh for v in vs] for c, vs in lit.targets_x(M, z, P).items()}
    ok = any(dist >= P["min_rr"] * risk for c in P["classes"] for dist in TT.get(c, []))
    if not ok and not P.get("fallback_rr"):
        best = max([d for vs in TT.values() for d in vs], default=None)
        return "target", ("no target 1.5R away: the VIX band is " + (f"{best / risk:.1f}R away" if best else "already behind the entry"))
    return None


# ------------------------------------------------------------------------------------------------ the brief
def _overnight(levels, M, k, now):
    """Levels taken from 18:00 until 08:00 ET (or now): which side's liquidity went first."""
    s = M.ctx[k]["s"]
    cut = int(M.t[s]) + 14 * 3600                       # 18:00 + 14 h = 08:00 ET
    tk = [r for r in levels if r["taken"] and r["taken_t"] < min(cut, now)]
    hi = [r["label"] for r in sorted(tk, key=lambda r: r["taken_t"]) if r["side"] == "H"]
    lo = [r["label"] for r in sorted(tk, key=lambda r: r["taken_t"]) if r["side"] == "L"]
    if hi and lo:
        txt = f"Both sides taken overnight: highs ({_join(hi)}) and lows ({_join(lo)})."
        side = "both"
    elif hi:
        txt = f"Buy-side liquidity (highs) taken overnight: {_join(hi)}. Lows untouched."
        side = "highs"
    elif lo:
        txt = f"Sell-side liquidity (lows) taken overnight: {_join(lo)}. Highs untouched."
        side = "lows"
    else:
        txt = "Nothing taken overnight: every level is still in play."
        side = "none"
    return {"side": side, "highs": hi, "lows": lo, "text": txt}


def _plan_line(price, levels, mon, band, wk, done, news_ev, open_pos=None):
    up = sorted([r for r in levels if not r["taken"] and r["side"] == "H" and r["price"] > price], key=lambda r: r["price"])[:2]
    dn = sorted([r for r in levels if not r["taken"] and r["side"] == "L" and r["price"] < price], key=lambda r: -r["price"])[:2]
    if open_pos:
        return (f"In a {_side(open_pos['dir'])} trade from {_px(open_pos['entry'])}: stop {_px(open_pos['stop'])}, target "
                f"{_px(open_pos['target'])}. No new setup today (1 trade a day).")
    if done:
        return "Today's trade is done (1 trade a day). Nothing more to do until tomorrow."
    parts = []
    shorts = mon != "low"
    longs = mon != "high"
    if shorts and up:
        nm = _join([f"{r['label']} {_px(r['price'])}" for r in up])
        parts.append(f"{nm} above {'is' if len(up) == 1 else 'are'} untaken; a sweep of {'it' if len(up) == 1 else 'them'} by "
                     f"half an ATR, then a 5m CISD down is the short setup" + (f", target {_px(band[0])} (VIX band low)" if band else ""))
    if longs and dn:
        nm = _join([f"{r['label']} {_px(r['price'])}" for r in dn])
        parts.append(f"{nm} below {'is' if len(dn) == 1 else 'are'} untaken; a sweep then a 5m CISD up is the long setup"
                     + (f", target {_px(band[1])} (VIX band high)" if band else ""))
    if not parts:
        parts.append("No untaken level near the price on the allowed side; the bot waits for a new level (a box or equal "
                     "highs/lows) to form and be swept")
    s = ". ".join(p[0].upper() + p[1:] for p in parts) + "."
    if mon in ("high", "low"):
        s += f" Monday rule: {'shorts' if mon == 'high' else 'longs'} only today."
    if wk and wk.get("mult", 1) < 1:
        s += f" Weekly stop is on: {wk['mult']:g}x size."
    if news_ev:
        s += f" Careful around {_join([e['time'] + ' ' + e['title'] for e in news_ev], 2)}."
    return s


def morning(M, k, last, now, P, live=None, news=None, ev=None, clock=None, lit_sizing=None, params=None):
    from engine import lit
    x = M.ctx[k]
    day = str(M.days[k][0])
    price = float(M.c[last])
    levels = level_map(M, k, last, now)
    bx = boxes(M, k, last, now)
    ovn = _overnight(levels, M, k, now)
    mon = lit.monday_state(M, k, last) if P.get("monday") else None
    mon_txt = (None if mon is None else
               "Monday: Friday's high taken - shorts only" if mon == "high" else
               "Monday: Friday's low taken - longs only" if mon == "low" else
               "Monday: Friday's high and low both taken - no side rule" if mon == "both" else
               "Monday: Friday's high/low not taken yet - both sides (the first one taken decides)")
    st = (live or {}).get("state") or {}
    wk = ((st.get("lit_rules") or {}).get("weekly_stop")) or None
    vm, o18 = x.get("vix_move"), x.get("open18")
    vk = float(P.get("vix_k", 1.0))
    band = [round(o18 - vk * vm, 2), round(o18 + vk * vm, 2)] if vm else None
    vix = {"vix": _f(x.get("vix")), "move": _f(vm), "open18": _f(o18), "low": band[0] if band else None, "high": band[1] if band else None,
           "text": (f"18:00 open {_px(o18)}, VIX {x.get('vix'):.2f} = a one-day move of {vm:.0f} pts: target band "
                    f"{_px(band[0])} (shorts) / {_px(band[1])} (longs)") if vm else "VIX close missing: no target band, no trade"}
    cal = str(_et(now).date())
    nev, nsrc = news_today(cal, news)
    stop = typical_stop()
    ls = lit_sizing or {}
    wkm = 1.0 if (ls.get("mode") == "two_week" and (ls.get("two_week") or {}).get("wk") is False) else float((wk or {}).get("mult") or 1.0)
    sz = size_today(stop, float(vm or 2 * stop), clock, ev, lit_sizing, params, wk_mult=wkm)
    evl = {"session": (clock or {}).get("session"), "limit": (clock or {}).get("limit", 10), "status": (clock or {}).get("status"),
           "to_target": (clock or {}).get("to_target", (ev or {}).get("to_target")), "room": (clock or {}).get("room", (ev or {}).get("cushion")),
           "balance": (ev or {}).get("balance"), "floor": (ev or {}).get("trailing_mll"), "max_micros": sz["qty"], "risk_usd": sz["risk_usd"],
           "stop": stop, "mode": sz["mode"], "why": sz["why"][-2:]}
    if evl["session"]:
        evl["text"] = (f"Eval session {evl['session']} of {evl['limit']}: {_usd(evl['to_target'] or 0)} to the target, "
                       f"{_usd(evl['room'] or 0)} of room to the floor. Today's size at a typical {stop:g}-pt stop: "
                       f"{sz['qty']} micros, {_usd(sz['risk_usd'])} at risk.")
    else:
        evl["text"] = (f"Eval {(clock or {}).get('text') or 'clock unknown'}. Size at a typical {stop:g}-pt stop: {sz['qty']} micros, "
                       f"{_usd(sz['risk_usd'])} at risk.")
    try:                                        # live Monte Carlo of this eval from today's state (engine/eval_mc.py, ~1 s)
        from engine import eval_mc
        mc = eval_mc.from_clock(clock, lit_sizing, seed=int(day.replace("-", "")))
    except Exception as e:                      # the odds must never break the brief
        mc = {"error": e.__class__.__name__, "text": f"eval Monte Carlo unavailable ({e.__class__.__name__})"}
    if mc:
        evl["mc"] = mc
    pos = st.get("position")
    done = bool(st.get("day_trades")) and not pos
    plan = _plan_line(price, levels, mon, band, wk, done, nev, pos)
    return {"day": day, "built_t": int(now), "built": _hm(now), "stage": "early" if _mod(now) < REFRESH_AT else "full",
            "price": round(price, 2), "levels": levels, "boxes": bx, "overnight": ovn,
            "monday": {"on": bool(P.get("monday")), "today": mon, "text": mon_txt},
            "weekly_stop": wk, "vix": vix, "news": nev, "news_src": nsrc, "news_text": news_text(nev), "eval": evl, "plan": plan,
            "untaken": {"above": sum(1 for r in levels if not r["taken"] and r["side"] == "H"),
                        "below": sum(1 for r in levels if not r["taken"] and r["side"] == "L")}}


def _facts(M, C, k, last, now, P, live):
    """Every fact of today known at `now`, as log rows {key, t, kind, text}."""
    day = str(M.days[k][0])
    out = []
    levels = level_map(M, k, last, now)
    for b in boxes(M, k, last, now):
        if b["status"] == "done":
            out.append({"key": f"box:{b['key']}", "t": b["done_t"], "kind": "box",
                        "text": f"{b['label']} box closed ({b['window']}): high {_px(b['high'])}, low {_px(b['low'])}, "
                                f"{b['high'] - b['low']:.0f} pts"})
    by_bar = {}
    for r in levels:
        if r["taken"]:
            by_bar.setdefault(r["taken_i"], []).append(r)
    for j, rs in by_bar.items():
        dep = max(r["depth_atr"] for r in rs)
        side = "high" if rs[0]["side"] == "H" else "low"
        names = _join([f"{r['label']} {_px(r['price'])}" for r in rs], 4)
        out.append({"key": f"sweep:{j}:{side}", "t": int(M.t[j]), "kind": "sweep",
                    "text": f"Swept {names} ({dep:.2f} ATR deep; " + ("deep enough for LIT)" if dep >= P["depth"] else
                                                                             f"LIT needs {P['depth']:g})")})
    sig = {(int(s["t"]), int(s["dir"])): s for s in (live or {}).get("signals") or []}
    st = (live or {}).get("state") or {}
    setups = list((st.get("setups") or {}).values())
    for z in C:
        if z["day"] != day or z["i"] > last:
            continue
        d = z["dir"]
        t_cl = int(M.t[z["i"]]) + 300
        idm = [a for a in z.get("idm_a") or [] if (not P.get("idm_a")) or (a[0] <= P["idm_a"][0] and a[1] <= P["idm_a"][1])]
        from engine.lit_live import _sweep_names
        sw = _join(_sweep_names(z["swept"]), 3)
        out.append({"key": f"cisd:{z['i']}:{d}", "t": t_cl, "kind": "cisd",
                    "text": f"5m CISD {'up' if d == 1 else 'down'} closed at {_px(z['ref_d'] * d)}: swept {sw} "
                            f"({z['depth_atr']:.2f} ATR); inducement: {len(idm)} swing{'s' if len(idm) != 1 else ''} taken first; "
                            f"displacement {z['disp']:.2f} ATR"})
        s = sig.get((int(M.t[z["entry_i"]]), d))
        if s is not None:
            stt = s.get("status")
            exp = next((x.get("expires_t") for x in setups if int(x.get("arm_t") or 0) == int(s["t"])), None) \
                or int(s["t"]) + int(P.get("wait", 6)) * 300
            if stt in ("pending", "filled", "entering", "no fill"):
                out.append({"key": f"armed:{z['i']}:{d}", "t": t_cl, "kind": "armed",
                            "text": f"Setup armed: {_side(d)} limit {_px(s['limit_px'])}, stop {_px(s['stop_px'])} ({s['risk_pts']:.1f} pts), "
                                    f"target {_px(s['target_px'])} ({s['rr']:.1f}R, {s['target_label']}), valid until {_hm(exp)} ET"})
            if stt == "no fill" and exp <= now:
                out.append({"key": f"expired:{z['i']}:{d}", "t": int(exp), "kind": "expired",
                            "text": f"{_side(d)} limit {_px(s['limit_px'])} did not fill (no tap in 30 min, or no 1m CISD within "
                                    f"{P.get('cisd1m') or 20} bars of the tap): setup over"})
            continue
        why = reject_reason(M, z, P)
        txt = why[1] if why else "a trade was already open or done today (1 trade a day)"
        out.append({"key": f"reject:{z['i']}:{d}", "t": t_cl, "kind": "rejected", "rule": why[0] if why else "day",
                    "text": f"{_side(d)} setup rejected: {txt}"})
    for x in setups:
        if x.get("tapped_t"):
            out.append({"key": f"tap:{x['arm_t']}", "t": int(x["tapped_t"]), "kind": "tap",
                        "text": f"Limit {_px(x['limit'])} tapped at {_hm(x['tapped_t'])}; waiting for a 1m CISD to enter "
                                f"(stop {_px(x['stop'])})"})
    en = st.get("enter_now")
    if en:
        out.append({"key": f"now:{en['entry_t']}", "t": int(en.get("cisd_t") or en["entry_t"]), "kind": "entry",
                    "text": f"Entering {_side(en['dir'])} at market now: 1m CISD closed; stop {_px(en['stop'])}, target {_px(en['target'])}"})
    for e in (live or {}).get("events") or []:
        if e["type"] in ("entry", "exit") and tday(e["t"]) == day and int(e["t"]) <= now:
            out.append({"key": f"{e['type']}:{int(e['t'])}", "t": int(e["t"]), "kind": e["type"], "text": e["text"]})
    return [r for r in out if r["t"] <= now]


_KORD = {"exit": 0, "entry": 1, "tap": 2, "expired": 3, "armed": 4, "rejected": 5, "cisd": 6, "sweep": 7, "box": 8}


def merge_log(prev_log, facts, now):
    old = {r["key"]: r for r in prev_log or []}
    out = []
    for f in facts:
        o = old.pop(f["key"], None)
        out.append({**f, "seen": (o or {}).get("seen", int(now)), "new": o is None})
    for o in old.values():                              # an earlier fact the window no longer shows: kept for the day
        out.append({**o, "new": False})
    out.sort(key=lambda r: (-int(r["t"]), _KORD.get(r["kind"], 9)))
    return out[:LOG_MAX]


def now_block(M, k, last, now, P, live):
    st = (live or {}).get("state") or {}
    levels = level_map(M, k, last, now)
    price = float(M.c[last])
    up = sorted([r for r in levels if not r["taken"] and r["side"] == "H" and r["price"] > price], key=lambda r: r["price"])[:3]
    dn = sorted([r for r in levels if not r["taken"] and r["side"] == "L" and r["price"] < price], key=lambda r: -r["price"])[:3]
    tk = [r for r in levels if r["taken"]]
    return {"t": int(now), "at": _hm(now), "price": round(price, 2), "bar_t": int(M.t[last]),
            "model_state": st.get("model_state"), "taken": len(tk), "levels": len(levels),
            "above": [{"label": r["label"], "price": r["price"], "dist": round(r["price"] - price, 2)} for r in up],
            "below": [{"label": r["label"], "price": r["price"], "dist": round(r["price"] - price, 2)} for r in dn]}


def recap(M, C, k, last, now, P, live, log, ledger_today=None, learning=None):
    day = str(M.days[k][0])
    trades = [t for t in (live or {}).get("trades") or [] if t.get("day") == day]
    rows = []
    for t in trades:
        lr = next((v for v in (ledger_today or []) if abs(int(v.get("entry_t") or 0) - int(t["entry_t"])) < 60), None)
        usd = float(lr["usd"]) if lr and lr.get("usd") is not None else float(t["pnl"])
        rows.append({"side": _side(t["dir"]), "entry_t": int(t["entry_t"]), "entry": t["entry"], "exit": t["exit_reason"],
                     "r": round(float(t["pnl_r"]), 2), "usd": round(usd, 2), "qty": int(lr["qty"]) if lr and lr.get("qty") else int(t["qty"]),
                     "paper": bool(lr)})
    pnl = round(sum(r["usd"] for r in rows), 2)
    n_cisd = sum(1 for r in log if r["kind"] == "cisd")
    n_arm = sum(1 for r in log if r["kind"] == "armed")
    rej = {}
    for r in log:
        if r["kind"] == "rejected":
            rej[r.get("rule") or "?"] = rej.get(r.get("rule") or "?", 0) + 1
    n_sw = sum(1 for r in log if r["kind"] == "sweep")
    RULE = {"depth": "shallow sweep", "disp": "weak displacement", "idm": "no inducement", "monday": "Monday rule", "stop": "stop out of range",
            "target": "no 1.5R target", "window": "outside the window", "day": "1 trade a day", "nwog": "NWOG side", "mw": "Mon-Wed rule"}
    rej_txt = ", ".join(f"{n} {RULE.get(k_, k_)}" for k_, n in sorted(rej.items(), key=lambda kv: -kv[1]))
    if rows:
        res_txt = "; ".join(f"{r['side']} {r['qty']} micros {r['exit']} {r['r']:+.2f}R {_susd(r['usd'])}" for r in rows)
        text = f"{len(rows)} trade{'s' if len(rows) > 1 else ''}: {res_txt}. Day {_susd(pnl)}."
    else:
        text = "No trade today."
    setups = (f"{n_sw} sweep{'s' if n_sw != 1 else ''}, {n_cisd} 5m CISD{'s' if n_cisd != 1 else ''}, {n_arm} armed"
              + (f", rejected: {rej_txt}" if rej_txt else "") + ".")
    lesson = None
    try:
        from engine import lit_learn
        for t in trades:
            if (t.get("learn") or {}).get("f") is None and not t.get("post"):
                continue
            rec = lit_learn.record(t, "brief", f=(t.get("learn") or {}).get("f"), post=t.get("post"))
            if rec.get("cause"):
                lesson = f"Loss cause: {lit_learn.CAUSES.get(rec['cause'], rec['cause'])}."
            elif float(t["pnl_r"]) > 0:
                lesson = f"Winner: the sweep held and price ran to {t.get('target_label') or 'the target'}."
    except Exception:
        lesson = None
    if lesson is None:
        if rows:
            r = rows[0]
            lesson = ("Winner: the sweep was the turning point." if r["usd"] > 0 else
                      "Stopped: the sweep was not the day's turning point (the stop sits just past the sweep extreme)."
                      if r["exit"] == "STOP" else f"Closed {r['exit']}.")
        elif n_cisd == 0:
            lesson = "No 5m CISD after a sweep today: no setup formed. Waiting is part of the plan (2-4 trades a week)."
        elif n_arm:
            lesson = "A setup was armed but the limit did not fill or the 1m CISD never came: no chase, by rule."
        else:
            top = max(rej.items(), key=lambda kv: kv[1])[0] if rej else None
            lesson = f"Setups formed but none passed the rules (mostly {RULE.get(top, top)}). The filters kept the bot out."
    cm = (learning or {}).get("causes_month") or {}
    if cm.get("by_cause"):
        c0 = sorted(cm["by_cause"], key=lambda c: -c.get("n", 0))[0]
        lesson += f" This month's most common loss cause: {c0['label']} ({c0['n']})."
    return {"day": day, "built_t": int(now), "built": _hm(now), "trades": rows, "pnl": pnl, "text": text, "setups": setups, "lesson": lesson}


def build(df5, now, params=None, live=None, prev=None, news=None, ev=None, clock=None, lit_sizing=None, model_params=None,
          ledger_today=None, learning=None, sym="NQ", ledger=None) -> dict:
    """The brief at `now` (see the module doc). prev = the last brief (state["brief"]); live = engine/lit_live.run() at now."""
    now = int(now)
    prev = prev if isinstance(prev, dict) else {}
    M, C, P = market_at(df5, now, params, sym)
    day_now = tday(now)
    base = {"version": VERSION, "t": now, "at": f"{_et(now):%a %H:%M} ET"}
    if M is None or not M.n:
        return {**prev, **base, "error": "no bars"}
    k = len(M.days) - 1
    last = M.n - 1
    day = str(M.days[k][0])
    nd = dt.date.fromisoformat(day_now)
    while nd.weekday() >= 5:
        nd += dt.timedelta(days=1)
    day_now_txt = str(nd)
    if day != day_now:          # the new trading day has not printed a bar yet (evening / weekend): keep the last brief
        if prev.get("day") == day:
            return {**prev, **base, "waiting": f"next session {day_now_txt}"}
        # no brief of the last session yet (first run, a gap): write it as of that session's end
        end = int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(17, 0), ET).timestamp())
        if end < now:
            b = build(df5, end, params, live, prev, news, ev, clock, lit_sizing, model_params, ledger_today, learning, sym, ledger)
            return {**b, **base, "waiting": f"next session {day_now_txt}"}
        return {**prev, **base, "waiting": f"next session {day_now_txt}"}
    b = {**base, "day": day, "waiting": None}
    if prev.get("day") == day:
        b["morning"], b["log"], b["recap"], b["prev"] = prev.get("morning"), prev.get("log") or [], prev.get("recap"), prev.get("prev")
    else:
        b["morning"], b["log"], b["recap"] = None, [], None
        b["prev"] = {"day": prev.get("day"), "recap": prev.get("recap"), "plan": (prev.get("morning") or {}).get("plan")} if prev.get("day") else prev.get("prev")
    m = _mod(now)
    same_date = str(_et(now).date()) == day
    mo = b["morning"]
    if same_date and m >= MORNING_AT and (mo is None or (mo.get("stage") == "early" and m >= REFRESH_AT)):
        b["morning"] = morning(M, k, last, now, P, live, news, ev, clock, lit_sizing, model_params)
    b["log"] = merge_log(b["log"], _facts(M, C, k, last, now, P, live), now)
    b["now"] = now_block(M, k, last, now, P, live)
    if same_date and m >= RECAP_AT:
        b["recap"] = recap(M, C, k, last, now, P, live, b["log"], ledger_today, learning)
    b["new"] = sum(1 for r in b["log"] if r.get("new"))
    try:
        b["mffu"] = mffu_notes(now, day, ledger, clock, (lit_sizing or {}).get("eval_start"), int(P.get("flat_mod", 955)))
    except Exception as e:                      # a warning must never break the brief
        b["mffu"] = [{"kind": "error", "level": "info", "text": f"MFFU checks unavailable ({e.__class__.__name__})"}]
    if b.get("morning") and b["morning"].get("day") == day:
        b["morning"]["mffu"] = b["mffu"]
    return b


def with_news(brief, hub, now=None):
    """The brief with today's news re-read from a fresher hub (tools/build_web_dashboard.py runs after the news step)."""
    try:
        mo = (brief or {}).get("morning")
        if not mo or not hub:
            return brief
        cal = str(_et(mo["built_t"]).date())
        nev, src = news_today(cal, hub)
        if src == "news hub":
            mo = {**mo, "news": nev, "news_src": src, "news_text": news_text(nev)}
            return {**brief, "morning": mo}
    except Exception:
        pass
    return brief


# ------------------------------------------------------------------------------------------------ README + cloud hook
def readme_lines(b) -> list:
    if not b or not b.get("day"):
        return []
    L = ["## LIT day brief", f"*{b['day']} - updated {b.get('at')} - the bot's own analysis, paper only, no notifications*", ""]
    mo = b.get("morning")
    if mo:
        L += [f"**Game plan** ({'refreshed' if mo['stage'] == 'full' else 'built'} {mo['built']} ET): {mo['plan']}", "",
              f"- Overnight: {mo['overnight']['text']}", f"- Target: {mo['vix']['text']}", f"- News: {mo['news_text']}",
              f"- Eval: {mo['eval']['text']}"]
        if (mo["eval"].get("mc") or {}).get("text"):
            L.append(f"- Eval odds: {mo['eval']['mc']['text']}")
        L += [f"- {'**' if w['level'] in ('warn', 'good') else ''}{w['text']}{'**' if w['level'] in ('warn', 'good') else ''}"
              for w in b.get("mffu") or []]
        if mo["monday"].get("text"):
            L.append(f"- {mo['monday']['text']}")
        if mo.get("weekly_stop"):
            L.append(f"- Weekly stop: {mo['weekly_stop'].get('text')}")
        bx = [f"{x['label']} {x['status']}" + (f" {_px(x['high'])}/{_px(x['low'])}" if x.get("high") is not None else "") for x in mo["boxes"]]
        L.append("- Boxes: " + "; ".join(bx))
        lv = [r for r in mo["levels"] if r["kind"] != "buildup" or not r["taken"]][:14]
        L += ["", "| Level | Price | Status |", "|---|---:|---|"]
        L += [f"| {r['label']} | {r['price']:,.2f} | {'taken ' + _hm(r['taken_t']) + f' ({r['depth_atr']:.1f} ATR)' if r['taken'] else 'untaken'} |"
              for r in sorted(lv, key=lambda r: -r["price"])]
    else:
        L.append("Morning briefing: built on the first run after 01:30 ET.")
    if b.get("recap"):
        r = b["recap"]
        L += ["", f"**End of day:** {r['text']} Setups: {r['setups']} Lesson: {r['lesson']}"]
    lg = b.get("log") or []
    L += ["", "**Today's log** (newest first)"] + [f"- {_hm(x['t'])} {x['kind']}{' (new)' if x.get('new') else ''}: {x['text']}" for x in lg[:15]] \
        + ([] if lg else ["- nothing yet"])
    return L + [""]


def _insert_readme(path, lines):
    try:
        with open(path, encoding="utf-8") as fh:
            txt = fh.read()
    except OSError:
        return
    sec = "\n".join(lines) + "\n"
    mark = "## Nearest liquidity pools"
    i = txt.find(mark)
    if i < 0:
        i = txt.rfind("\n---\n")
        i = i + 1 if i >= 0 else len(txt)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(txt[:i] + sec + "\n" + txt[i:])


def cloud_hook(out, new_state, old_state, res, df_all, now, lm):
    """tools/cloud_monitor.py: the brief into new_state["brief"] and a section into <out>/README.md. LIT only."""
    if (lm or {}).get("model") != "lit":
        return None
    hub = None
    try:
        with open(os.path.join(ROOT, "data", "news", "hub.json"), encoding="utf-8") as fh:
            hub = json.load(fh)
    except Exception:
        hub = None
    today = tday(now)
    led = [{**v, "entry_t": int(k)} for k, v in (new_state.get("ledger") or {}).items() if v.get("day") == today and str(k).isdigit()]
    b = build(df_all, now, params=lm.get("lit"), live=res, prev=(old_state or {}).get("brief"), news=hub, ev=new_state.get("eval"),
              clock=new_state.get("eval_2wk"), lit_sizing=lm.get("lit_sizing"), model_params=lm.get("params"), ledger_today=led,
              learning=new_state.get("learning"), sym=lm.get("sym") or "NQ",
              ledger=[{**v, "entry_t": int(k)} for k, v in (new_state.get("ledger") or {}).items() if str(k).isdigit()])
    new_state["brief"] = b
    _insert_readme(os.path.join(out, "README.md"), readme_lines(b))
    return b
