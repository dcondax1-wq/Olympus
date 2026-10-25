"""Bot Brain: what the LIT bot is thinking right now, as one structured, read-only snapshot (owner 2026-10-21: "just to see
what the bot is thinking, like exactly what it's thinking").

Pure functions over what the live loop already computed: engine/lit_live.run()'s result and its market (Market,
candidates, the executor's raw result, via run(keep=...)), the live LIT params, the sizing switch and the bot's health /
guards. Nothing here decides, sizes or routes anything: every verdict below is re-read from the engine's own output
(signals, pending limits, trades) or from the same filter functions (engine/lit.py setup_ok's checks, monday_block,
targets_x) on the same numbers, so the Brain can never disagree with what the bot did (tests/test_brain.py checks it on
replayed 2026 days).

    b = build(res, P, now, keep=keep, ctx={...}, log=BrainLog(...))      # full snapshot (PC API /api/next/brain)
    c = compact(b)                                                       # phone budget (heartbeat / live.json / data.json)
    b = replay(day, t)                                                   # any past 2026 day / time from data/NQ_5m.csv + 1m

Contents (every number next to its rule):
  stage     where LIT is in its pipeline (Levels -> Sweep -> Inducement -> Displacement -> 5m CISD -> Limit armed ->
            1m CISD wait -> Entry -> In trade -> Done for today) + one plain sentence of what it waits for next
  watch     the setup forming now per side (the current 2-hour leg): levels it swept, depth vs 0.5 ATR, inducement,
            best displacement vs 0.8 ATR, the CISD level a 5m close must clear
  levels    every LIT level of today: price, distance in pts / ATR, side, taken or not, how deep a sweep went
  setups    every 5m CISD candidate today with each rule check (value vs threshold) and its status: armed / filled /
            no fill / rejected (the rule) / blocked (1 trade a day)
  sizing    the sizing mode's math in words and numbers (two_week: what is left to +$3,000, $ per micro at the target,
            60% room cap, soft daily loss cap, max 40) -> micros and $ at risk; weekly stop; eval session; pass lock
  trade     the open trade's management: stop, breakeven trigger (+1R), the 15-minute check, target, 8R bank, 15:55 flat
  guards    feed ages, guards on/off and whether one blocks, clock drift, news today, VIX/VXN band, market hours
  log       a time-stamped narration of today's state changes (data/brain/YYYY-MM-DD.jsonl on the PC, last 200 lines)
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import threading
import time
from zoneinfo import ZoneInfo

import numpy as np

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAIN_DIR = os.path.join(ROOT, "data", "brain")          # gitignored: one JSONL thought log per trading day
VERSION = 1
KIND = "le-brain"
LOG_KEEP = 200
LEG = 24                                                   # engine/lit.py candidates(): the leg is the last 24 5m bars
PV, COMM, SLIP = 2.0, 1.90, 0.25

STAGES = [
    ("levels", "Levels", "The map: every liquidity level LIT watches today (session boxes, previous day / week / month highs and "
                         "lows, opening gaps, equal highs / lows)."),
    ("sweep", "Sweep", "Price trades through a level (takes the stops resting there) by at least 0.5 ATR."),
    ("inducement", "Inducement", "Before the sweep, a smaller swing near the level was taken first: early traders trapped "
                                 "(within 1 ATR of the level, at most 36 bars old)."),
    ("displacement", "Displacement", "A strong candle back the other way: body at least 0.8 ATR."),
    ("cisd5", "5m CISD", "Change in state of delivery: a 5-minute close back through the open of the last run of candles into "
                         "the sweep extreme. This is the setup."),
    ("limit", "Limit armed", "A limit order at the CISD level, valid 30 minutes (6 bars of 5m)."),
    ("cisd1m", "1m CISD wait", "Once the limit is tapped, the bot waits up to 20 one-minute bars for a 1-minute CISD to confirm."),
    ("entry", "Entry", "Entry at the next 1-minute open, routed about 3 s after the 1m CISD close."),
    ("trade", "In trade", "Managing: breakeven at +1R, the 15-minute check, the VIX-band target (banked at 8R), flat at 15:55."),
    ("done", "Done for today", "One trade a day, or the 02:00-15:30 entry window is over."),
]
STAGE_N = {k: i + 1 for i, (k, _l, _h) in enumerate(STAGES)}
HELP = {k: h for k, _l, h in STAGES}
HELP.update({
    "atr": "ATR = average true range of the last 14 five-minute bars: how far NQ normally moves in one bar right now.",
    "depth": "How far price went beyond the swept level, in ATR. LIT needs at least 0.5 ATR: a real stop run, not a touch.",
    "idm": "Inducement: a minor swing low (for a long) above the swept level, taken out on the way down before the sweep.",
    "disp": "Displacement: the biggest candle body between the sweep extreme and the trigger, in ATR. LIT needs 0.8.",
    "window": "Entries only between 02:00 and 15:30 ET (the entry bar's time).",
    "stop": "Stop 1 tick beyond the sweep extreme (the protected low / high). LIT trades only 8-80 point stops.",
    "target": "Target: the 18:00 open +/- one VIX one-day move (the VIX band). It must be at least 1.5R away; banked at 8R.",
    "monday": "Monday rule: once Monday took Friday's high, only shorts; once it took Friday's low, only longs.",
    "day": "One trade a day: once a setup filled, later setups that day are skipped.",
    "be": "Breakeven: at +1R the stop moves to the entry + 1.25 pts (covers the commission and a tick).",
    "t_check": "15-minute check: 15 minutes after the fill, if the trade never reached +0.5R and closes more than 0.3R "
               "below the entry, it is cut at the next 1-minute open.",
    "two_week": "Two-week eval sizing: 'one winner passes' - micros so the target pays what is left to +$3,000, capped at "
                "60% of the room to the trailing floor, the $1,000 soft daily loss and 40 micros.",
    "wk_stop": "Weekly stop: after 2 stop-outs in a calendar week, half size for the rest of that week (not used in two_week mode).",
    "vix": "VIX one-day move = VIX / 100 / sqrt(252) x the 18:00 open: the market's own expected daily range.",
})
CHECK_LABEL = {"day": "1 trade a day", "window": "Entry window 02:00-15:30", "depth": "Sweep depth >= 0.5 ATR",
               "idm": "Inducement taken first", "disp": "Displacement >= 0.8 ATR", "monday": "Monday rule",
               "stop": "Stop 8-80 pts", "target": "Target >= 1.5R"}
KIND_LABEL = {"pd": "Previous day", "pw": "Previous week", "pm": "Previous month", "gap": "Opening gap", "asia": "Asia box",
              "london": "London box", "ny": "New York box", "pre": "Premarket box", "x_ny": "New York box",
              "buildup": "Equal highs / lows", "vix": "VIX band (target)"}


# ------------------------------------------------------------------------------------------------ small helpers
def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def _hm(t):
    return _et(t).strftime("%H:%M") if t is not None else None


def _mod(t):
    e = _et(t)
    return e.hour * 60 + e.minute


def _p(x):
    return "-" if x is None else f"{float(x):,.2f}"


def _pts(x):
    return "-" if x is None else f"{float(x):+,.1f} pts"


def _r2(x, nd=2):
    try:
        v = float(x)
        return None if not math.isfinite(v) else round(v, nd)
    except (TypeError, ValueError):
        return None


def _usd(x):
    return "-" if x is None else ("-" if x < 0 else "") + f"${abs(float(x)):,.0f}"


def _side(d):
    return "LONG" if int(d) == 1 else "SHORT"


def _hhmm(m):
    return f"{int(m) // 60:02d}:{int(m) % 60:02d}"


def _span(P):
    """(first start, last end) of the entry windows: min / max (today), or in CME trading-day order with all_hours
    (the Asia slot: 18:00-15:30)."""
    if P.get("all_hours"):
        from engine import lit_live
        return lit_live.window_span(P["window"])
    return min(a_ for a_, _ in P["window"]), max(b_ for _, b_ in P["window"])


def _lab(nm, side):
    from engine.lit_brief import _label
    return _label(nm, side)


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return _r2(o, 4)
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, np.bool_):
        return bool(o)
    return o


# ------------------------------------------------------------------------------------------------ the thought log
class BrainLog:
    """Today's thought log: rows keyed by fact (the first time the bot saw it), persisted as data/brain/YYYY-MM-DD.jsonl
    (append-only, one JSON row per line) when `path_dir` is set; in memory otherwise (tests, replays, harness bots)."""

    def __init__(self, path_dir: str | None = None, keep: int = LOG_KEEP):
        self.dir, self.keep = path_dir, keep
        self.day = None
        self.rows: dict = {}
        self.stage = None
        self._lock = threading.Lock()

    def _path(self, day):
        return os.path.join(self.dir, f"{day}.jsonl") if self.dir else None

    def _load(self, day):
        self.day, self.rows, self.stage = day, {}, None
        p = self._path(day)
        if p and os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as fh:
                    for ln in fh:
                        try:
                            r = json.loads(ln)
                        except ValueError:
                            continue
                        if isinstance(r, dict) and r.get("key"):
                            self.rows[r["key"]] = r
                            if r.get("kind") == "stage":
                                self.stage = r.get("stage")
            except OSError:
                pass

    def update(self, day: str, facts: list, now: int) -> list:
        """Add the facts not seen yet today (first-seen time kept); returns the day's log, newest first, last `keep`."""
        with self._lock:
            if day != self.day:
                self._load(day)
            new = []
            for f in facts:
                if f["key"] in self.rows:
                    continue
                r = {**f, "seen": int(now)}
                self.rows[f["key"]] = r
                new.append(r)
                if f.get("kind") == "stage":
                    self.stage = f.get("stage")
            p = self._path(day)
            if p and new:
                try:
                    os.makedirs(self.dir, exist_ok=True)
                    with open(p, "a", encoding="utf-8") as fh:
                        for r in new:
                            fh.write(json.dumps(_jsonable(r), separators=(",", ":")) + "\n")
                except OSError:
                    pass
            rows = sorted(self.rows.values(), key=lambda r: (-int(r["t"]), _KORD.get(r.get("kind"), 9)))
            return rows[:self.keep]


_KORD = {"exit": 0, "trade": 1, "entry": 2, "tap": 3, "expired": 4, "armed": 5, "rejected": 6, "blocked": 6, "cisd": 7, "sweep": 8,
         "stage": 9, "box": 10}


def read_day_log(day: str, path_dir: str = BRAIN_DIR, keep: int = LOG_KEEP) -> list:
    """A persisted day's log (newest first), [] when none."""
    lg = BrainLog(path_dir, keep)
    lg._load(day)
    return sorted(lg.rows.values(), key=lambda r: (-int(r["t"]), _KORD.get(r.get("kind"), 9)))[:keep]


# ------------------------------------------------------------------------------------------------ levels
def _levels(M, k, last, now, P, price, atr):
    from engine import lit_brief
    rows = []
    for r in lit_brief.level_map(M, k, last, now):
        dist = round(r["price"] - price, 2)
        row = {"label": r["label"], "also": r.get("also") or [], "price": r["price"], "side": r["side"], "kind": r["kind"],
               "kind_label": KIND_LABEL.get(r["kind"], r["kind"]), "dist": dist, "dist_atr": _r2(dist / atr) if atr else None,
               "known_hm": _hm(r["known_t"]) if r.get("known_t") else None, "taken": bool(r["taken"])}
        if r["taken"]:
            row.update(taken_t=r["taken_t"], taken_hm=_hm(r["taken_t"]), depth_atr=r.get("depth_atr"), depth_pts=r.get("depth_pts"),
                       deep_ok=bool((r.get("depth_atr") or 0) >= P["depth"]))
        rows.append(row)
    rows.sort(key=lambda r: -r["price"])
    return rows


def _nearest(levels, price, n=3):
    up = sorted([r for r in levels if not r["taken"] and r["price"] >= price], key=lambda r: r["price"])[:n]
    dn = sorted([r for r in levels if not r["taken"] and r["price"] < price], key=lambda r: -r["price"])[:n]
    f = lambda r: {"label": r["label"], "price": r["price"], "dist": r["dist"], "dist_atr": r["dist_atr"], "kind": r["kind"]}
    return {"above": [f(r) for r in up], "below": [f(r) for r in dn]}


def _near_txt(near):
    parts = [f"{r['label']} {_p(r['price'])} ({r['dist']:+,.0f} pts)" for r in (near["below"][:1] + near["above"][:1])]
    parts += [f"{r['label']} {_p(r['price'])} ({r['dist']:+,.0f} pts)" for r in (near["below"][1:2] + near["above"][1:2])]
    return ", ".join(parts[:4]) if parts else "no untaken level left"


# ------------------------------------------------------------------------------------------------ the setup forming now
def _watch(M, k, last, P, mon):
    """Per side, the setup the current leg (last 24 closed 5m bars) is building, with the same steps as lit.candidates():
    swept levels (first breach inside the leg, below the extreme), depth vs the nearest swept level, the I-a inducements,
    the best displacement body since the extreme and the CISD level a 5m close must clear. Informational: the setup
    itself only counts once lit.candidates() lists it (the 'setups' block)."""
    from engine import lit
    x = M.ctx[k]
    s = x["s"]
    at = M.atr
    L = M.levels(k)
    out = []
    a = max(0, last - LEG)
    for d in (1, -1):
        if d == 1:
            hi_d, lo_d, c_d, o_d, swing_lo = M.h, M.l, M.c, M.o, M.fl
        else:
            hi_d, lo_d, c_d, o_d, swing_lo = -M.l, -M.h, -M.c, -M.o, M.fh
        side = "long" if d == 1 else "short"
        lvl_word = "low" if d == 1 else "high"
        w = {"dir": d, "side": _side(d), "allowed": not (mon == "high" and d == 1) and not (mon == "low" and d == -1)}
        if last <= a:
            continue
        ee = a + int(np.argmin(lo_d[a:last + 1]))
        ext = float(lo_d[ee])
        atr_e = max(float(at[ee]), 1e-9)
        swept = []
        for sd, px, ki, nm, cls in L:
            if (sd == "low") != (d == 1) or ki >= ee:
                continue
            p = px * d
            fb = lit._first_breach(lo_d, max(ki, s - 600), last + 1, p)
            if ee - LEG <= fb <= ee and ext < p:
                swept.append((p, ki, nm, cls, fb, sd))
        w.update(ext=round(ext * d, 2), ext_t=int(M.t[ee]), ext_hm=_hm(int(M.t[ee])), atr=round(atr_e, 2))
        if not swept:
            w.update(stage="sweep", swept=[], depth_atr=None)
            out.append(w)
            continue
        lev_near = max(z[0] for z in swept)
        sb = min(z[4] for z in swept)
        depth = (lev_near - ext) / atr_e
        names = list(dict.fromkeys(_lab(z[2], z[5]) for z in sorted(swept, key=lambda z: -z[0])))
        # I-a inducement (engine/lit.py candidates): fractal swings beyond the swept level, untouched until the final run
        idm = []
        leg_top = int(ee - np.argmax(hi_d[max(ee - 36, s - 600):ee + 1][::-1])) if ee > s else ee
        import bisect
        lo_i2 = bisect.bisect_left(swing_lo, sb - 72)
        for m in swing_lo[lo_i2:bisect.bisect_left(swing_lo, ee)]:
            m = int(m)
            if lo_d[m] <= lev_near:
                continue
            sg = lo_d[m + 1:ee + 1] < lo_d[m]
            if not sg.any():
                continue
            tk = m + 1 + int(np.argmax(sg))
            if tk < max(leg_top, m + 3) or tk > ee:
                continue
            idm.append((round((lo_d[m] - lev_near) / max(float(at[sb]), 1e-9), 3), int(sb - m)))
        dm, age, cnt = P.get("idm_a") or (None, None, 0)
        good = [z for z in idm if dm is None or (z[0] <= dm and z[1] <= age)]
        idm_ok = len(good) >= int(cnt or 0)
        body = [(c_d[j] - o_d[j]) / max(float(at[j]), 1e-9) for j in range(ee + 1, last + 1)]
        disp = max(body) if body else 0.0
        cz = lit._cisd_level(c_d, o_d, ee) if P["ref"] == "cisd" else None
        rp = cz[0] if cz else None
        closed = bool(rp is not None and last > ee and c_d[ee + 1:last + 1].max() > rp)
        w.update(swept=names, swept_px=[round(z[0] * d, 2) for z in sorted(swept, key=lambda z: -z[0])][:4],
                 level=round(lev_near * d, 2), depth_atr=round(depth, 3), depth_pts=round(lev_near - ext, 2),
                 need_pts=round(max(0.0, P["depth"] * atr_e - (lev_near - ext)), 2), depth_ok=bool(depth >= P["depth"]),
                 idm_n=len(good), idm_all=len(idm), idm_best=min((z[0] for z in good), default=None),
                 idm_age=min((z[1] for z in good), default=None), idm_ok=bool(idm_ok),
                 disp=round(float(disp), 3), disp_ok=bool(disp >= P["disp"]),
                 cisd=round(rp * d, 2) if rp is not None else None,
                 cisd_dist=round((rp - float(c_d[last])) , 2) if rp is not None else None,
                 cisd_closed=closed, word=lvl_word,
                 stop_preview=round((rp - (ext - P["stop_buf"])), 2) if rp is not None else None)
        if closed:
            w["stage"] = "cisd5"
        elif not w["depth_ok"]:
            w["stage"] = "sweep"
        elif not idm_ok:
            w["stage"] = "inducement"
        elif not w["disp_ok"]:
            w["stage"] = "displacement"
        else:
            w["stage"] = "cisd5"
        w["text"] = _watch_text(w, P, side)
        out.append(w)
    return out


def _watch_text(w, P, side):
    d = w["dir"]
    sw = ", ".join(w["swept"][:3])
    if w["stage"] == "sweep" and w.get("depth_atr") is not None:
        beyond = w["ext"] - d * w["need_pts"]
        return (f"Swept {sw} by {w['depth_atr']:.2f} ATR ({w['depth_pts']:.1f} pts). LIT needs >= {P['depth']:g} ATR "
                f"({P['depth'] * w['atr']:.1f} pts): price must go {w['need_pts']:.1f} pts further "
                f"({'below' if d == 1 else 'above'} {_p(beyond)}) for a {side} setup.")
    if w["stage"] == "inducement":
        dm, age, _c = P.get("idm_a") or (1.0, 36, 1)
        return (f"Swept {sw} by {w['depth_atr']:.2f} ATR (ok), but no inducement swing was taken first (needs a swing "
                f"{'low' if d == 1 else 'high'} within {dm:g} ATR of the level, at most {int(age)} bars old; found "
                f"{w['idm_all']} outside the rule). A deeper leg can still take one.")
    if w.get("cisd") is None:
        return f"Swept {sw}: waiting for a run of candles into the extreme to define the CISD level."
    move = abs(w["cisd_dist"])
    if w["stage"] == "displacement":
        return (f"{side.capitalize()} setup forming: swept {sw} ({w['depth_atr']:.2f} ATR, ok), inducement ok. Waiting for a "
                f"strong 5m candle (body >= {P['disp']:g} ATR = {P['disp'] * w['atr']:.1f} pts; best so far {w['disp']:.2f} ATR) "
                f"and a close {'above' if d == 1 else 'below'} {_p(w['cisd'])} (the CISD level, {move:.1f} pts away).")
    if w.get("cisd_closed"):
        return f"5m CISD already closed through {_p(w['cisd'])}: see the setup card."
    return (f"{side.capitalize()} setup forming: swept {sw} ok, inducement ok, displacement {w['disp']:.2f} ATR ok. Waiting for "
            f"a 5m close {'above' if d == 1 else 'below'} {_p(w['cisd'])} (the CISD level, {move:.1f} pts away).")


# ------------------------------------------------------------------------------------------------ setups (candidates)
def _origin_index(M, C, t):
    """Index in C of the candidate a trade came from (finished / open trades carry its trigger bar "i", an entry being
    routed now its setup time "sig_t")."""
    for j, z in enumerate(C):
        if z["day"] != t.get("day") or int(z["dir"]) != int(t.get("dir", 0)):
            continue
        if "i" in t and int(z["i"]) == int(t["i"]):
            return j
        if "i" not in t and t.get("sig_t") is not None and int(M.t[z["entry_i"]]) == int(t["sig_t"]):
            return j
    return None


def _checks(M, z, P, day_block):
    """Each LIT rule on candidate z, in the executor's order (engine/lit.py _run_core): value, threshold, pass."""
    from engine import lit
    d = z["dir"]
    out = []
    out.append({"key": "day", "ok": not day_block, "value": "free" if not day_block else "taken",
                "text": "no trade yet today" if not day_block else "a setup earlier today already filled (1 trade a day)"})
    inw = any(a_ <= z["mod"] < b_ for a_, b_ in P["window"])
    a0, b0 = _span(P)
    out.append({"key": "window", "ok": inw, "value": _hhmm(z["mod"]), "need": f"{_hhmm(a0)}-{_hhmm(b0)}",
                "text": f"entry bar {_hhmm(z['mod'])} ET " + ("inside" if inw else "outside") + f" {_hhmm(a0)}-{_hhmm(b0)} ET"})
    dep_pts = z["depth_atr"] * z["atr_ext"]
    out.append({"key": "depth", "ok": z["depth_atr"] >= P["depth"], "value": round(z["depth_atr"], 2), "need": P["depth"],
                "text": f"{z['depth_atr']:.2f} ATR = {dep_pts:.1f} pts beyond the level (needs >= {P['depth']:g} ATR = "
                        f"{P['depth'] * z['atr_ext']:.1f} pts)"})
    out.append({"key": "disp", "ok": z["disp"] >= P["disp"], "value": round(z["disp"], 2), "need": P["disp"],
                "text": f"biggest body {z['disp']:.2f} ATR (needs >= {P['disp']:g})"})
    if P.get("idm_a"):
        dm, age, cnt = P["idm_a"]
        good = [(dd, aa) for dd, aa in (z.get("idm_a") or []) if dd <= dm and aa <= age]
        best = min(good) if good else None
        txt = (f"{len(good)} swing{'s' if len(good) != 1 else ''} taken first" +
               (f", nearest {best[0]:.2f} ATR from the level, {best[1]} bars before the sweep" if best else "") +
               f" (needs {int(cnt)} within {dm:g} ATR and {int(age)} bars; {len(z.get('idm_a') or [])} seen in all)")
        out.append({"key": "idm", "ok": len(good) >= cnt, "value": len(good), "need": int(cnt), "text": txt})
    if P.get("monday"):
        blk = bool(lit.monday_block(M, z))
        mon = "Monday" if M.ctx[z["k"]]["dow"] == 0 else "not Monday"
        out.append({"key": "monday", "ok": not blk, "value": "blocked" if blk else "ok",
                    "text": (f"Monday: Friday's {'high' if d == 1 else 'low'} taken first, so only "
                             f"{'shorts' if d == 1 else 'longs'} today") if blk else f"{mon}: no side rule against this {_side(d).lower()}"})
    ep = min(float(z["ref_d"]), z["trig_c"])
    stop = z["ext_d"] - P["stop_buf"]
    risk = ep - stop
    out.append({"key": "stop", "ok": P["min_stop"] <= risk <= P["max_stop"], "value": round(risk, 2),
                "need": f"{P['min_stop']:g}-{P['max_stop']:g}",
                "text": f"limit {_p(ep * d)}, stop {_p(stop * d)} (1 tick beyond the extreme {_p(z['ext_d'] * d)}) = {risk:.1f} pts "
                        f"(trades {P['min_stop']:g}-{P['max_stop']:g})"})
    sh = z["entry_d"] - ep
    TT = {c: [v + sh for v in vs] for c, vs in lit.targets_x(M, z, P).items()}
    best = None
    for c in P["classes"]:
        for dist in TT.get(c, []):
            if dist >= P["min_rr"] * risk and (best is None or dist < best):
                best = dist
                break
    far = max([v for vs in TT.values() for v in vs], default=None)
    if best is not None:
        tp = min(best, P["max_rr"] * risk) if P["max_rr"] else best
        banked = bool(P["max_rr"] and best > P["max_rr"] * risk)
        out.append({"key": "target", "ok": True, "value": round(best / risk, 2) if risk > 0 else None, "need": P["min_rr"],
                    "text": f"VIX band {_p((ep + best) * d)} = {best / risk:.1f}R away (needs >= {P['min_rr']:g}R)"
                            + (f"; banked at {P['max_rr']:g}R = {_p((ep + tp) * d)}" if banked else ""),
                    "price": round((ep + tp) * d, 2), "rr": round(tp / risk, 2) if risk > 0 else None})
    else:
        out.append({"key": "target", "ok": bool(P.get("fallback_rr")), "value": round(far / risk, 2) if far and risk > 0 else None,
                    "need": P["min_rr"], "text": ("VIX band only " + (f"{far / risk:.1f}R away" if far and risk > 0 else
                                                                       "behind the entry") + f" (needs >= {P['min_rr']:g}R)")})
    for c in out:
        c["label"] = CHECK_LABEL.get(c["key"], c["key"])
    return out


def _no_fill_why(M, z, sig, P):
    """Why an armed limit did not become a trade (5m bars inside the limit's 30 minutes; the executor decides on 1m)."""
    d = z["dir"]
    lo_d = M.l if d == 1 else -M.h
    hi_d = M.h if d == 1 else -M.l
    lim, stop, tgt = sig["limit_px"] * d, sig["stop_px"] * d, sig["target_px"] * d
    a = int(z["entry_i"])
    nmax = min(M.n_closed if hasattr(M, "n_closed") else M.n, a + int(P["wait"]))
    tapped = None
    for j in range(a, nmax):
        if lo_d[j] <= stop and tapped is None:
            return f"the sweep extreme broke at {_hm(int(M.t[j]))} before a fill (setup dead)"
        if tapped is None and lo_d[j] <= lim:
            tapped = j
            break
        if hi_d[j] >= tgt:
            return f"price ran to the target at {_hm(int(M.t[j]))} without coming back to the limit (cancelled)"
    if tapped is not None:
        return (f"limit tapped at {_hm(int(M.t[tapped]))} but no 1m CISD within {P.get('cisd1m') or 20} one-minute bars "
                f"(or the extreme broke first)")
    return f"price never came back to the limit {_p(sig['limit_px'])} in {int(P['wait']) * 5} minutes"


def _setups(M, C, R, res, P, k, last, now):
    day = str(M.days[k][0])
    sigs = {(int(s["t"]), int(s["dir"])): s for s in (R.get("signals") or [])}
    pend = {(int(p["t0"]), int(p["dir"])): p for p in (R.get("pending") or [])}
    raw = [t for t in (R.get("trades") or []) if t.get("day") == day] + [t for t in (R.get("enter_now") or []) if t.get("day") == day]
    origins = [j for j in (_origin_index(M, C, t) for t in raw) if j is not None]
    out = []
    for j, z in enumerate(C):
        if z["day"] != day or z["i"] > last:
            continue
        d = z["dir"]
        t_cl = int(M.t[z["i"]]) + 300
        day_block = any(o < j for o in origins)
        checks = _checks(M, z, P, day_block)
        sig = sigs.get((int(M.t[z["entry_i"]]), d))
        row = {"id": f"{z['i']}:{d}", "t": t_cl, "hm": _hm(t_cl), "dir": d, "side": _side(d),
               "swept": _sweep_names(z["swept"]), "ext": round(z["ext_d"] * d, 2), "cisd": round(z["ref_d"] * d, 2),
               "atr": round(z["atr_ext"], 2), "checks": checks}
        first_fail = next((c for c in checks if not c["ok"]), None)
        if sig is not None:
            st = sig.get("status")
            row["plan"] = {"limit": sig["limit_px"], "stop": sig["stop_px"], "stop_pts": sig["risk_pts"], "target": sig["target_px"],
                           "rr": sig["rr"], "target_label": sig["target_label"], "armed_t": int(sig["t"]), "armed_hm": _hm(int(sig["t"])),
                           "expires_t": int(sig["t"]) + int(P["wait"]) * 300, "expires_hm": _hm(int(sig["t"]) + int(P["wait"]) * 300)}
            p = pend.get((int(sig["t"]), d))
            if st == "pending":
                if p and p.get("tapped_t"):
                    row["plan"]["tapped_t"] = int(p["tapped_t"])
                    row["plan"]["tapped_hm"] = _hm(int(p["tapped_t"]))
                    dl = int(p["tapped_t"]) + int(P.get("cisd1m") or 20) * 60
                    row["plan"]["cisd_deadline_hm"] = _hm(dl)
                    row.update(status="tapped", status_text=f"Limit tapped at {_hm(int(p['tapped_t']))}: waiting for a 1m CISD "
                                                            f"until about {_hm(dl)}")
                else:
                    row.update(status="armed", status_text=f"Limit {_p(sig['limit_px'])} armed until {row['plan']['expires_hm']} ET")
            elif st == "entering":
                row.update(status="entering", status_text="1m CISD closed: entering at market now")
            elif st == "filled":
                t = next((t for t in raw if int(t.get("i", -1)) == int(z["i"]) and int(t["dir"]) == d), None)
                if t is not None:
                    row["trade"] = {"entry_t": int(t["entry_t"]), "entry_hm": _hm(int(t["entry_t"])), "entry": t["entry_px"],
                                    "exit": t.get("exit"), "r": t.get("r"), "pnl": t.get("pnl"), "qty": t.get("qty"),
                                    "kind": "limit" if t.get("limit_fill") else "1m CISD"}
                    ex = t.get("exit")
                    row.update(status="filled", status_text=(f"Filled {_hm(int(t['entry_t']))} at {_p(t['entry_px'])}" +
                                                            (" - still open" if ex == "OPEN" else f" - {ex} {float(t['r']):+.2f}R")))
                else:
                    row.update(status="filled", status_text="Filled")
            else:
                why = _no_fill_why(M, z, sig, P)
                row.update(status="no_fill", status_text=f"No fill (limit window ended {row['plan']['expires_hm']} ET): {why}")
        elif first_fail is not None and first_fail["key"] == "day":
            row.update(status="blocked", rule="day", status_text="Blocked: a trade already filled today (1 trade a day)")
        elif first_fail is not None:
            row.update(status="rejected", rule=first_fail["key"], status_text=f"Rejected: {first_fail['label']} - {first_fail['text']}")
        else:
            row.update(status="blocked", rule="day", status_text="Skipped: a trade was open or done today")
        out.append(row)
    return out


def _sweep_names(names):
    from engine.lit_live import _sweep_names as f
    return f(names)


# ------------------------------------------------------------------------------------------------ sizing
def _sizing(focus, ctx, P, x, price):
    from engine import lit, lit_brief, sizing
    ls = (ctx or {}).get("lit_sizing") or {}
    mode = ls.get("mode") or "normal"
    st = (ctx or {}).get("eval_state")
    room = (st or {}).get("room") if st else (ctx or {}).get("room")
    if focus:
        risk, tgt = float(focus["risk"]), float(focus["tgt"])
        what = focus["what"]
    else:
        risk = lit_brief.typical_stop()
        tgt = float(x.get("vix_move") or 0.0) or 2.5 * risk
        what = f"a typical {risk:.0f}-pt stop with the target one VIX move away ({tgt:.0f} pts) - no setup is live"
    q0 = lit.qty_for(risk, 800.0, 20.0)
    wk_m = float((focus or {}).get("size_mult") or 1.0)
    trade = {"risk_pts": risk, "tgt_pts": tgt, "size_mult": wk_m, "size_why": list((focus or {}).get("size_why") or [])}
    try:
        r = sizing.lit_qty(max(1, int(q0 * wk_m + 1e-9)) if wk_m < 1 else q0, trade, ls, room=room, state=st,
                           learning=(ctx or {}).get("learning", "auto"))
        qty, reasons = int(r["qty"]), list(r.get("reasons") or [])
        fallback = r.get("fallback")
    except Exception as e:
        qty, reasons, fallback = q0, [f"sizing unavailable ({e.__class__.__name__})"], None
    loss1 = (risk + SLIP) * PV + COMM
    out = {"mode": mode, "what": what, "risk_pts": round(risk, 2), "tgt_pts": round(tgt, 2), "qty": qty,
           "risk_usd": round(qty * loss1, 0), "win_usd": round(qty * (tgt * PV - COMM), 0), "reasons": reasons, "fallback": fallback,
           "lit_rule_qty": int(q0), "eval_state": st, "steps": []}
    S = out["steps"]
    anc = (st or {}).get("anchor") if isinstance((st or {}).get("anchor"), dict) else None
    if anc and room is not None:             # the MFFU dashboard numbers the eval book starts from (engine/eval_life --anchor)
        bal = 50000.0 + float(st.get("profit") or 0) + float(st.get("cum") or 0)
        S.append({"label": "MFFU anchor", "value": f"{anc['as_of']}",
                  "text": f"MFFU balance ${anc['balance']:,.2f} / floor ${anc['floor']:,.2f} after {anc['as_of']}; now balance "
                          f"${bal:,.2f}, floor ${bal - float(room):,.2f}, room ${float(room):,.2f}"})
    bk = (st or {}).get("broker") if isinstance((st or {}).get("broker"), dict) else None
    if bk:                                   # the real balance from NinjaTrader (engine/broker_balance.py): room = min(ledger, real)
        from engine import broker_balance
        S.append({"label": "Real balance", "value": _usd(bk["equity"]), "text": broker_balance.line(bk)})
        out["broker_line"] = broker_balance.line(bk)
    if mode == "two_week" and st:
        A = sizing.TW_50K
        c = {**sizing.TW_DEFAULT, **(ls.get("two_week") or {})}
        profit, cum = float(st.get("profit") or 0), float(st.get("cum") or 0)
        need = A["target"] - profit - cum
        per = tgt * PV - COMM
        q_need = math.ceil(need * float(c["need_buf"]) / per - 1e-9) if per > 0 and need > 0 else 0
        S.append({"label": "Left to +$3,000", "value": _usd(need), "text": f"eval profit {_usd(profit)} + today {_usd(cum)}: {_usd(need)} still needed"})
        S.append({"label": "$ per micro at the target", "value": _usd(per),
                  "text": f"{tgt:.1f} pts x $2 - $1.90 commission = {_usd(per)} a micro"})
        S.append({"label": "One winner passes", "value": f"{q_need} micros", "text": f"ceil({_usd(need)} / {_usd(per)}) = {q_need} micros"})
        if c.get("room_f") and room is not None:
            cap = int(float(c["room_f"]) * max(0.0, float(room)) / (risk * PV))
            S.append({"label": "60% room cap", "value": f"{cap} micros",
                      "text": f"60% of the {_usd(room)} room to the trailing floor / ({risk:.1f} pts x $2) = {cap}"})
        if c.get("dll_cap"):
            ld = (risk + sizing.TW_DLL_SLIP) * PV + COMM
            cap2 = int(max(0.0, A["dll"] + cum) / ld)
            S.append({"label": "Soft daily loss cap", "value": f"{cap2} micros",
                      "text": f"($1,000 {'+' if cum >= 0 else '-'} {_usd(abs(cum))} today) / (({risk:.1f} + 0.5) pts x $2 + $1.90) = {cap2}"})
        S.append({"label": "Max", "value": "40 micros", "text": "never more than 40 micros, never fewer than 1"})
    else:
        S.append({"label": "LIT rule", "value": f"{q0} micros", "text": f"$800 up to a 20-pt stop, then 800 x 20 / {risk:.1f} = {q0}"})
        if room is not None and mode in ("safe_eval", "eval"):
            cap = int(0.6 * max(0.0, float(room)) / (risk * PV))
            S.append({"label": "60% room cap", "value": f"{cap} micros", "text": f"60% of the {_usd(room)} room / ({risk:.1f} x $2)"})
    S.append({"label": "Result", "value": f"{qty} micros", "text": f"{qty} micros x ({risk:.1f} + 0.25) pts x $2 + $1.90 = "
                                                                  f"{_usd(out['risk_usd'])} at risk; the target pays {_usd(out['win_usd'])}"})
    return out


# ------------------------------------------------------------------------------------------------ trade management
def _trade(pos, raw_open, P, price, now, routed_qty=None):
    if not pos:
        return None
    d = int(pos["dir"])
    entry, stop0, stop, tgt = float(pos["entry"]), float(pos["stop0"]), float(pos["stop"]), float(pos["target"])
    risk = float(pos["risk_pts"])
    qty = int(routed_qty or pos["qty"])
    r_now = d * (price - entry) / risk if risk else 0.0
    be_px = entry + d * float(P.get("be_r") or 1.0) * risk
    out = {"side": _side(d), "dir": d, "entry_t": int(pos["entry_t"]), "entry_hm": _hm(int(pos["entry_t"])), "entry": entry,
           "stop0": stop0, "stop": stop, "target": tgt, "risk_pts": round(risk, 2), "qty": qty, "qty_model": int(pos["qty"]),
           "price": price, "r_now": round(r_now, 2), "usd_now": round(d * (price - entry) * PV * qty, 0),
           "risk_usd": round(qty * ((risk + SLIP) * PV + COMM), 0), "target_label": pos.get("target_label"),
           "be": {"done": bool(pos.get("be")), "trigger": round(be_px, 2), "pts_away": round(d * (be_px - price), 2),
                  "new_stop": round(entry + d * float(P.get("be_off") or 0.0), 2),
                  "text": ("Breakeven done: stop moved to " + _p(stop) if pos.get("be") else
                           f"Breakeven at +1R = {_p(be_px)} ({abs(be_px - price):.1f} pts away): stop then moves to "
                           f"{_p(entry + d * float(P.get('be_off') or 0.0))} (entry + {float(P.get('be_off') or 0):g})")},
           "target_r": round(d * (tgt - entry) / risk, 2) if risk else None,
           "bank": {"r": P.get("max_rr"), "price": round(entry + d * float(P["max_rr"]) * risk, 2) if P.get("max_rr") else None},
           "flat": {"at": _hhmm(P["flat_mod"]), "text": f"Flat at {_hhmm(P['flat_mod'])} ET if still open"}}
    mfe = float((raw_open or {}).get("mfe") or 0.0)
    out["mfe_r"] = round(mfe, 2)
    tc = P.get("t_check")
    if tc:
        at_s = int(pos["entry_t"]) + int(tc.get("at", 15)) * 60
        thr = entry - d * float(tc.get("x", 0.3)) * risk
        state = ("waiting" if now < at_s else "passed")
        if pos.get("be"):
            state = "not needed (breakeven done)" if now < at_s else "passed"
        out["t_check"] = {"at_t": at_s, "at_hm": _hm(at_s), "state": state, "mfe_need": tc.get("mfe", 0.5), "x": tc.get("x", 0.3),
                          "cut_below": round(thr, 2),
                          "text": (f"At {_hm(at_s)} ET: cut if the trade never reached +{float(tc.get('mfe', 0.5)):g}R (best so far "
                                   f"{mfe:+.2f}R) and the 1m close is {'below' if d == 1 else 'above'} {_p(thr)} "
                                   f"(-{float(tc.get('x', 0.3)):g}R)") if state == "waiting" else
                                  (f"15-minute check passed at {_hm(at_s)} (the trade stayed in)" if state == "passed" else
                                   "15-minute check not needed: breakeven already moved the stop")}
    return out


# ------------------------------------------------------------------------------------------------ guards / context
def _guards(ctx, x, now, P, day):
    from engine import lit_live
    c = ctx or {}
    h = c.get("health") or {}
    feed = h.get("feed") or {}
    gc = c.get("guards_cfg") or {}
    block = []
    if feed.get("block"):
        block.append(f"FEED STALE: {feed['block']}")
    if h.get("kill"):
        block.append("Kill switch is on: no new entries")
    if c.get("eval_life") and (c["eval_life"].get("status") in ("passed", "failed")):
        block.append(f"Eval {c['eval_life']['status']}: no new trade on this eval")
    if c.get("clock_problem"):
        block.append(c["clock_problem"])
    if c.get("daily_loss_hit"):
        block.append(c["daily_loss_hit"])
    e = _et(now)
    mod = e.hour * 60 + e.minute
    closed = lit_live._closed(now)
    a0, b0 = _span(P)
    ah = bool(P.get("all_hours"))
    win = (not closed) and (any(a_ <= mod < b_ for a_, b_ in P["window"]) if ah else a0 <= mod < b0)
    not_yet = (lit_live.tday(mod) < lit_live.tday(a0)) if ah else (mod < a0 or mod >= 1080)
    ec = lit_live.early_close(day) if day else None
    news = c.get("news") or []
    G = [{"key": k, "label": lab, "on": bool(gc.get(k, dflt)) if gc else dflt}
         for k, lab, dflt in (("order_sanity", "Order sanity (micros, stop side, 1.5R, max $ risk)", True),
                              ("dup_entry", "One entry per signal, 1 a day", True),
                              ("daily_loss", "Soft daily loss $1,000", True), ("room_alarm", "Room alarm push ($800 / $400)", True),
                              ("reconcile", "NinjaTrader position reconcile", True), ("clock", "PC clock drift <= 5 s", True),
                              ("calendar", "CME calendar (closures, early close)", True), ("news", "News blackout (off for LIT)", False))]
    return {"blocking": block, "blocked": bool(block), "guards": G,
            "feed": {"source": feed.get("used") or feed.get("source"), "age_1m_s": feed.get("age_1m_s"), "age_5m_s": feed.get("age_5m_s"),
                     "stale": feed.get("stale"), "no_yahoo": feed.get("no_yahoo")} if feed else None,
            "poll": {"age_s": (h.get("poll") or {}).get("age_s"), "ms": (h.get("poll") or {}).get("poll_ms"),
                     "errors": (h.get("poll") or {}).get("consecutive_errors")} if h.get("poll") else None,
            "clock_drift_s": c.get("clock_drift_s"), "account": (h.get("account") or {}).get("label"),
            "market": {"open": not closed, "entry_window": win, "window": f"{_hhmm(a0)}-{_hhmm(b0)} ET", "now_hm": _hm(now),
                       "early_close": _hhmm(ec) if ec is not None else None,
                       "text": ("Market closed (Globex reopens 18:00 ET)" if closed else
                                f"Entry window open ({_hhmm(a0)}-{_hhmm(b0)} ET)" if win else
                                f"Market open, entry window {'not open yet' if not_yet else 'over'} "
                                f"({_hhmm(a0)}-{_hhmm(b0)} ET)")},
            "news": news[:8],
            "vix": {"vix": _r2(x.get("vix")), "vxn": _r2(x.get("vxn")), "move": _r2(x.get("vix_move")), "open18": _r2(x.get("open18")),
                    "up": _r2((x.get("open18") or 0) + (x.get("vix_move") or 0)) if x.get("vix_move") else None,
                    "dn": _r2((x.get("open18") or 0) - (x.get("vix_move") or 0)) if x.get("vix_move") else None}}


# ------------------------------------------------------------------------------------------------ the stage + sentence
def _stage(res, R, setups, watch, near, P, now, day, k_today_ok, guards, mon):
    from engine import lit_live
    st = res["state"]
    pos, en = st.get("position"), st.get("enter_now")
    pend = [s for s in setups if s.get("status") in ("armed", "tapped")]
    e = _et(now)
    mod = e.hour * 60 + e.minute
    a0, b0 = _span(P)
    ah = bool(P.get("all_hours"))
    # done once the day's cap is filled (1 a day today; 2 with the Asia slot / London + NY switches)
    done_today = sum(1 for s in setups if s.get("status") == "filled") >= max(1, int(P.get("max_per_day") or 1)) and not pos and not en
    if lit_live._closed(now):
        return "closed", ("Market closed. Next session opens 18:00 ET; LIT can enter from 02:00 ET (the London sweep)." if not ah else
                          f"Market closed. Next session opens 18:00 ET; LIT can enter from {_hhmm(a0)} ET.", None)
    if not k_today_ok:
        return "levels", (f"New session: waiting for the first bars of {day}. Entries from {_hhmm(a0)} ET.", None)
    if pos:
        d = int(pos["dir"])
        be_px = float(pos["entry"]) + d * float(P.get("be_r") or 1.0) * float(pos["risk_pts"])
        if pos.get("be"):
            w = (f"In a {_side(d)} trade from {_p(pos['entry'])}: stop at breakeven {_p(pos['stop'])}, waiting for the target "
                 f"{_p(pos['target'])} or the 15:55 flat.")
        else:
            w = (f"In a {_side(d)} trade from {_p(pos['entry'])}: waiting for +1R at {_p(be_px)} to move the stop to breakeven; "
                 f"stop {_p(pos['stop'])}, target {_p(pos['target'])}.")
        return "trade", (w, d)
    if en:
        return "entry", (f"Entering {_side(en['dir'])} at market now: the 1m CISD closed at {_hm(en['entry_t'] - 60)}; "
                         f"{en['qty']} micros, stop {_p(en['stop'])}, target {_p(en['target'])}.", int(en["dir"]))
    if pend:
        s = pend[0]
        if s["status"] == "tapped":
            return "cisd1m", (f"{s['side']} limit {_p(s['plan']['limit'])} was tapped at {s['plan']['tapped_hm']}: waiting for a 1-minute "
                              f"CISD close (until about {s['plan']['cisd_deadline_hm']}) to enter; stop {_p(s['plan']['stop'])}.", s["dir"])
        return "limit", (f"{s['side']} limit armed at {_p(s['plan']['limit'])} until {s['plan']['expires_hm']} ET: waiting for price to "
                         f"pull back to it (stop {_p(s['plan']['stop'])}, target {_p(s['plan']['target'])}, {s['plan']['rr']:.1f}R).", s["dir"])
    if done_today:
        t = next(s for s in setups if s.get("status") == "filled")
        tr = t.get("trade") or {}
        return "done", (f"Done for today: one trade a day ({t['side']} {tr.get('exit') or ''} {float(tr.get('r') or 0):+.2f}R). "
                        + ("Next chance tomorrow from 02:00 ET." if not ah else f"Next chance from {_hhmm(a0)} ET."), t["dir"])
    if (lit_live.tday(mod) >= lit_live.tday_end(b0)) if ah else (b0 <= mod < 1080):
        return "done", (f"Entry window closed at {_hhmm(b0)} ET with no trade today. Next chance tomorrow from {_hhmm(a0)} ET.", None)
    pre = (lit_live.tday(mod) < lit_live.tday(a0)) if ah else (mod >= 1080 or mod < a0)
    best = None
    for w in watch:
        if not w.get("allowed", True):
            continue
        rank = STAGE_N.get(w["stage"], 2) + (0.5 if w.get("depth_atr") is not None else 0)
        if w.get("cisd_closed"):
            rank = 0          # already a candidate (see setups); does not drive the sentence
        if best is None or rank > best[0]:
            best = (rank, w)
    lead = f"Before {_hhmm(a0)} ET (no entries yet): " if pre else ""
    monday = ""
    if mon in ("high", "low"):
        monday = f" Monday rule: Friday's {mon} was taken, so {'shorts' if mon == 'high' else 'longs'} only."
    rule = f"{P['depth']:g} ATR"
    atr_pts = None
    if watch:
        atr_pts = watch[0].get("atr")
    if best is None or best[1]["stage"] == "sweep" and best[1].get("depth_atr") is None:
        need = f" (= {P['depth'] * atr_pts:.1f} pts)" if atr_pts else ""
        return "sweep", (f"{lead}Waiting for price to sweep a level by >= {rule}{need}. Nearest: {_near_txt(near)}.{monday}", None)
    w = best[1]
    return w["stage"], (lead + w["text"] + monday, w["dir"])


def _stages(key, setups):
    n = STAGE_N.get(key, 0)
    traded = any(s.get("status") == "filled" for s in setups)
    out = []
    for i, (k, lab, _h) in enumerate(STAGES):
        j = i + 1
        if key == "closed":
            stt = "todo"
        elif key == "done":
            stt = "now" if j == 10 else "done" if (traded or j == 1) else "skip"
        else:
            stt = "done" if j < n else "now" if j == n else "todo"
        out.append({"key": k, "label": lab, "state": stt, "n": j})
    return out


# ------------------------------------------------------------------------------------------------ the log facts
def _facts(M, C, k, last, now, P, res, setups, trade, stage_key, stage_text):
    from engine import lit_brief
    rows = []
    try:
        base = lit_brief._facts(M, C, k, last, now, P, res)
    except Exception:
        base = []
    for f in base:
        txt = f["text"]
        if f["kind"] == "sweep":
            txt = txt.replace("deep enough for LIT)", "deep enough: ✓)").replace("LIT needs", "✗ LIT needs")
        elif f["kind"] == "rejected":
            txt = "✗ " + txt
        elif f["kind"] in ("armed", "entry"):
            txt = "✓ " + txt
        rows.append({"key": f["key"], "t": int(f["t"]), "kind": f["kind"], "text": txt, **({"rule": f["rule"]} if f.get("rule") else {})})
    for s in setups:
        if s.get("status") == "blocked":
            rows.append({"key": f"blocked:{s['id']}", "t": s["t"], "kind": "blocked", "text": f"{s['side']} setup skipped: 1 trade a day"})
    if trade:
        if trade["be"]["done"]:
            rows.append({"key": f"be:{trade['entry_t']}", "t": int(now), "kind": "trade",
                         "text": f"✓ +1R reached: stop moved to breakeven {_p(trade['stop'])}"})
        tc = trade.get("t_check") or {}
        if tc.get("state") == "passed":
            rows.append({"key": f"tchk:{trade['entry_t']}", "t": int(tc["at_t"]), "kind": "trade",
                         "text": f"✓ 15-minute check passed (best {trade['mfe_r']:+.2f}R): the trade stays in"})
    rows.append({"key": f"stage:{stage_key}:{M.days[k][0]}", "t": int(now), "kind": "stage", "stage": stage_key,
                 "text": f"Now: {dict((a, b) for a, b, _ in STAGES).get(stage_key, stage_key)} - {stage_text}"})
    for r in rows:
        r["hm"] = _hm(r["t"])
    return [r for r in rows if r["t"] <= now]


# ------------------------------------------------------------------------------------------------ build
def build(res: dict, P: dict, now: int, keep: dict | None = None, ctx: dict | None = None, log: BrainLog | None = None,
          mode: str = "live") -> dict:
    """The full Brain at `now` from lit_live.run()'s result (res) and its market (keep = the dict passed to run(keep=)).
    ctx (all optional): lit_sizing, eval_state, eval_clock, eval_life, health (accounts.pc_health), guards_cfg,
    clock_drift_s, clock_problem, news [{time, title}], routed_qty, learning. Never raises."""
    t0 = time.perf_counter()
    now = int(now)
    try:
        from engine import lit
        P = {**lit.DEFAULTS, **(P or {})}
        keep = keep or {}
        M, C, R = keep.get("M"), keep.get("C"), keep.get("R")
        if M is None or C is None or R is None:
            return {"v": VERSION, "kind": KIND, "mode": mode, "t": now, "error": "no market (the live loop did not hand over its bars)"}
        last = int(getattr(M, "n_closed", M.n)) - 1
        k = int(M.day_of[last])
        x = M.ctx[k]
        day = str(M.days[k][0])
        price = float(M.c[last])
        atr = float(M.atr[last])
        mon = lit.monday_state(M, k, last) if P.get("monday") else None
        levels = _levels(M, k, last, now, P, price, atr)
        near = _nearest(levels, price)
        watch = _watch(M, k, last, P, mon)
        setups = _setups(M, C, R, res, P, k, last, now)
        st = res.get("state") or {}
        pos = st.get("position")
        raw_open = next((t for t in (R.get("trades") or []) if t.get("exit") == "OPEN"), None)
        trade = _trade(pos, raw_open, P, price, now, ((ctx or {}).get("routed_qty") or {}).get(int(pos["entry_t"])) if pos else None)
        from engine.lit_live import trading_date
        k_today_ok = str(trading_date(now)) == day or lit_live_closed(now)
        guards = _guards(ctx, x, now, P, day)
        key, (wait, side) = _stage(res, R, setups, watch, near, P, now, day, k_today_ok, guards, mon)
        if guards["blocked"] and key not in ("trade", "closed", "done"):
            wait += " BLOCKED: " + "; ".join(guards["blocking"]) + " (no new entry while this lasts)."
        # sizing focus: the open trade, the entry being routed, the armed limit, else a preview
        focus = None
        en = st.get("enter_now")
        if pos:
            focus = {"risk": float(pos["risk_pts"]), "tgt": abs(float(pos["target"]) - float(pos["entry"])), "what": "the open trade",
                     "size_mult": pos.get("size_mult"), "size_why": pos.get("size_why")}
        elif en:
            focus = {"risk": float(en["risk_pts"]), "tgt": abs(float(en["target"]) - float(en["entry"])), "what": "the entry being routed now",
                     "size_mult": en.get("size_mult"), "size_why": en.get("size_why")}
        else:
            ps = next((s for s in setups if s.get("status") in ("armed", "tapped")), None)
            if ps:
                pl = ps["plan"]
                focus = {"risk": float(pl["stop_pts"]), "tgt": abs(float(pl["target"]) - float(pl["limit"])),
                         "what": f"the armed {ps['side']} limit (at the limit price; the 1m fill can change it a little)"}
        sizing_b = _sizing(focus, ctx, P, x, price)
        rules = st.get("lit_rules") or {}
        ws = rules.get("weekly_stop")
        sizing_b["weekly_stop"] = ({"stops": ws.get("stops"), "after": ws.get("after"), "mult": ws.get("mult"), "text": ws.get("text")}
                                   if ws else None)
        if sizing_b["mode"] == "two_week" and ws:
            sizing_b["weekly_stop"]["text"] = (ws.get("text") or "") + " (two_week sizing does not use it)"
        ec = (ctx or {}).get("eval_clock")
        el = (ctx or {}).get("eval_life")
        sizing_b["eval"] = {"session": (ec or {}).get("session"), "limit": (ec or {}).get("limit"), "status": (ec or {}).get("status"),
                            "text": (ec or {}).get("text"), "to_target": (ec or {}).get("to_target"), "room": (ec or {}).get("room"),
                            "lock": (el or {}).get("status") in ("passed", "failed"), "life": (el or {}).get("trading")} if (ec or el) else None
        facts = _facts(M, C, k, last, now, P, res, setups, trade, key, wait)
        if log is not None:
            lg = log.update(day, facts, now)
        else:
            lg = sorted(facts, key=lambda r: (-int(r["t"]), _KORD.get(r.get("kind"), 9)))[:LOG_KEEP]
            # a replay shows only the last stage line
        out = {"v": VERSION, "kind": KIND, "mode": mode, "t": now, "at": f"{_et(now):%a %H:%M} ET", "day": day,
               "price": round(price, 2), "bar_t": int(M.t[last]), "bar_hm": _hm(int(M.t[last])), "atr": round(atr, 2),
               "model_state": st.get("model_state"),
               "stage": {"key": key, "n": STAGE_N.get(key, 0), "label": dict((a, b) for a, b, _ in STAGES).get(key, "Market closed"),
                         "waiting": wait, "dir": side},
               "stages": _stages(key, setups), "watch": watch, "levels": levels, "nearest": near,
               "setups": setups, "sizing": sizing_b, "trade": trade, "guards": guards,
               "rules": {"depth": P["depth"], "disp": P["disp"], "idm_a": P.get("idm_a"), "window": P["window"], "wait_min": int(P["wait"]) * 5,
                         "cisd1m": P.get("cisd1m"), "min_stop": P["min_stop"], "max_stop": P["max_stop"], "min_rr": P["min_rr"],
                         "max_rr": P["max_rr"], "be_r": P["be_r"], "be_off": P.get("be_off"), "t_check": P.get("t_check"),
                         "flat": _hhmm(P["flat_mod"]), "max_per_day": P["max_per_day"], "monday": bool(P.get("monday")),
                         "monday_today": mon},
               "day_trades": st.get("day_trades"), "day_pnl": st.get("day_pnl"),
               "log": lg, "help": HELP, "build_ms": None}
        out = _jsonable(out)
        out["build_ms"] = int((time.perf_counter() - t0) * 1000)
        return out
    except Exception as e:                       # the Brain never breaks the live loop
        import traceback
        return {"v": VERSION, "kind": KIND, "mode": mode, "t": now, "error": f"{e.__class__.__name__}: {e}",
                "trace": traceback.format_exc()[-800:]}


def lit_live_closed(now):
    from engine import lit_live
    return lit_live._closed(now)


# ------------------------------------------------------------------------------------------------ compact (phone)
def compact(b: dict, log_n: int = 30, n_levels: int = 14, max_bytes: int = 16_000) -> dict:
    """The phone's cut: stage, waiting sentence, nearest levels + today's taken ones, today's setups with their checks,
    sizing, management, guards (short), the last `log_n` log lines. Fits in max_bytes (log, then levels trimmed)."""
    if not isinstance(b, dict) or b.get("error"):
        return {k: b.get(k) for k in ("v", "kind", "mode", "t", "error")} if isinstance(b, dict) else None
    lv = b.get("levels") or []
    price = b.get("price") or 0
    untaken = sorted([r for r in lv if not r.get("taken")], key=lambda r: abs((r.get("price") or 0) - price))[:n_levels]
    taken = [r for r in lv if r.get("taken")][:10]
    keepk = ("label", "price", "side", "kind", "dist", "dist_atr", "taken", "taken_hm", "depth_atr", "depth_pts", "deep_ok")
    lvls = sorted([{k: r.get(k) for k in keepk if r.get(k) is not None} for r in untaken + taken], key=lambda r: -(r.get("price") or 0))
    g = b.get("guards") or {}
    out = {k: b.get(k) for k in ("v", "kind", "mode", "t", "at", "day", "price", "bar_hm", "atr", "stage", "nearest", "rules",
                                 "day_trades", "day_pnl")}
    out["stages"] = [[s["key"], s["state"]] for s in b.get("stages") or []]
    out["levels"] = lvls
    out["watch"] = [{k: w.get(k) for k in ("side", "stage", "text", "depth_atr", "disp", "cisd", "allowed")} for w in b.get("watch") or []]
    S = b.get("setups") or []
    main = [s for s in S if s.get("status") != "blocked"][-8:]
    blocked = [s for s in S if s.get("status") == "blocked"]
    pick = sorted(main + blocked[-max(0, 8 - len(main)):], key=lambda s: s.get("t") or 0)
    out["setups"] = [{**{k: s.get(k) for k in ("id", "hm", "side", "dir", "swept", "status", "status_text", "rule", "plan", "trade")},
                      "checks": [[c["key"], bool(c["ok"]), c.get("text")] for c in s.get("checks") or []]} for s in pick]
    out["setups_n"] = {"all": len(S), "blocked": len(blocked), "shown": len(pick)}
    sz = b.get("sizing") or {}
    out["sizing"] = {k: sz.get(k) for k in ("mode", "what", "qty", "risk_pts", "tgt_pts", "risk_usd", "win_usd", "steps", "weekly_stop", "eval", "broker_line")}
    out["trade"] = b.get("trade")
    out["guards"] = {"blocking": g.get("blocking"), "market": g.get("market"), "feed": g.get("feed"), "vix": g.get("vix"),
                     "news": (g.get("news") or [])[:4], "clock_drift_s": g.get("clock_drift_s"),
                     "off": [x["label"] for x in g.get("guards") or [] if not x.get("on")]}
    out["log"] = [{"hm": r.get("hm"), "kind": r.get("kind"), "text": r.get("text")} for r in (b.get("log") or [])[:log_n]]
    out["compact"] = True
    sz = lambda: len(json.dumps(out, separators=(",", ":"), default=str))
    while sz() > max_bytes and (len(out["log"]) > 8 or len(out["levels"]) > 6 or len(out["setups"]) > 3):
        if len(out["log"]) > 8:
            out["log"] = out["log"][:max(8, len(out["log"]) * 2 // 3)]
        elif len(out["setups"]) > 3:
            out["setups"] = out["setups"][1:]
        else:
            out["levels"] = out["levels"][:max(6, len(out["levels"]) * 2 // 3)]
    if sz() > max_bytes:                         # last resort: the check texts (keys + pass / fail stay)
        for s in out["setups"]:
            s["checks"] = [[c[0], c[1]] for c in s["checks"]]
    return out


# ------------------------------------------------------------------------------------------------ replay (any 2026 day)
_RP: dict = {}
_RP_LOCK = threading.Lock()


def _replay_data():
    """data/NQ_5m.csv + the research-clean 1m bars (engine.data.load_ltf), loaded once (~3 s)."""
    with _RP_LOCK:
        if "df5" not in _RP:
            import pandas as pd
            from engine.data import load, load_ltf
            df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
            b1, _ = load_ltf("NQ", load("NQ", "5m"))
            _RP.update(df5=df5, T5=df5["time"].values, b1=b1)
        return _RP


def _live_params():
    try:
        with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as fh:
            lm = json.load(fh)
        return lm.get("lit") or {}, lm.get("lit_sizing") or {}
    except Exception:
        return {}, {}


def day_bounds(day: str):
    """(18:00 ET the evening before, 17:00 ET) of trading date `day` as unix seconds."""
    d = dt.date.fromisoformat(day)
    a = dt.datetime.combine(d - dt.timedelta(days=1), dt.time(18, 0), ET)
    if d.weekday() == 0:
        a = dt.datetime.combine(d - dt.timedelta(days=1), dt.time(18, 0), ET)      # Sunday evening
    return int(a.timestamp()), int(dt.datetime.combine(d, dt.time(17, 0), ET).timestamp())


def replay(day: str, t: int | None = None, P: dict | None = None, lit_sizing: dict | None = None, _keep: dict | None = None) -> dict:
    """The Brain as it was at `t` (unix; default 16:00 ET) on trading date `day`, rebuilt exactly as the PC bot would
    have seen it: 5m bars closed by t, the research 1m bars closed by t, the forming 1m bar's open, early mode
    (tests/test_lit_live.py's poll). Sizing assumes a fresh eval (session 1, $0, $2,000 room)."""
    import numpy as _np
    from engine import lit_live
    lp, ls = _live_params()
    P = P or lp
    ls = lit_sizing or ls
    a, z = day_bounds(day)
    now = int(t) if t else int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(16, 0), ET).timestamp())
    now = max(a + 300, min(now, z))
    D = _replay_data()
    df5, T5, b1 = D["df5"], D["T5"], D["b1"]
    cut5 = df5.iloc[:int(_np.searchsorted(T5 + 300, now, side="right"))]
    cut5 = cut5[cut5["time"] >= now - 75 * 86400]
    if not len(cut5):
        return {"v": VERSION, "kind": KIND, "mode": "replay", "t": now, "error": f"no bars for {day}"}
    cut1 = b1.slice(0, int(_np.searchsorted(b1.t + 60, now, side="right")))
    jf = int(_np.searchsorted(b1.t, now - now % 60))
    forming = (int(b1.t[jf]), float(b1.o[jf])) if jf < len(b1.t) and int(b1.t[jf]) == now - now % 60 else None
    keep = {} if _keep is None else _keep              # _keep: tests read the market / result the Brain was built from
    res = lit_live.run(cut5, P, one_min=cut1, now=now, forming=forming, early=True, keep=keep)
    keep["res"] = res
    ctx = {"lit_sizing": ls, "learning": None,
           "eval_state": {"profit": 0.0, "cum": 0.0, "room": 2000.0, "session": 1, "n_today": 0, "days_traded": 0},
           "eval_clock": {"session": 1, "limit": 10, "status": "open", "to_target": 3000.0, "room": 2000.0,
                          "text": "replay: sized as a fresh eval (session 1 of 10, $3,000 to go)"},
           "news": _news(day)}
    b = build(res, P, now, keep=keep, ctx=ctx, mode="replay")
    b["replay"] = {"day": day, "from_t": a, "to_t": z, "note": "Replay: the same Brain rebuilt from the stored bars as the PC bot "
                                                                "would have seen them at this minute. Sizing assumes a fresh eval."}
    return b


def replay_frames(day: str) -> list:
    """The scrubber's stops for a day: every 5m close from 18:05 to 16:00 ET (unix)."""
    a, z = day_bounds(day)
    end = int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(16, 0), ET).timestamp())
    D = _replay_data()
    T5 = D["T5"]
    i0, i1 = int(np.searchsorted(T5, a)), int(np.searchsorted(T5, end))
    return [int(x) + 300 for x in T5[i0:i1]]


def sessions_2026() -> list:
    """2026 sessions in the data, newest first, with the stored live run's trade (research/runs/lit_live.json)."""
    D = _replay_data()
    T5 = D["T5"]
    t0 = int(dt.datetime(2026, 1, 1, tzinfo=ET).timestamp())
    days = sorted({str((_et(int(t)) + dt.timedelta(hours=6)).date()) for t in T5[int(np.searchsorted(T5, t0)):]})
    days = [d for d in days if dt.date.fromisoformat(d).weekday() < 5]
    tr = {}
    try:
        with open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8") as fh:
            r = json.load(fh)
        cols = r["trade_cols"]
        for t in r["trades"]:
            row = dict(zip(cols, t))
            if str(row.get("day", "")).startswith("2026"):
                tr[row["day"]] = {"exit": row.get("exit"), "r": _r2(row.get("r")), "pnl": _r2(row.get("pnl"), 0)}
    except Exception:
        pass
    return [{"day": d, "trade": tr.get(d)} for d in reversed(days)]


_NEWS: dict = {}


def _news(day: str) -> list:
    """High-impact USD news of the calendar date (engine/lit_brief.news_today; cached a minute)."""
    hit = _NEWS.get(day)
    if hit and time.time() - hit[0] < 60:
        return hit[1]
    try:
        from engine import lit_brief
        hub = None
        p = os.path.join(ROOT, "data", "news", "hub.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                hub = json.load(fh)
        ev, _src = lit_brief.news_today(day, hub)
        ev = [{"time": e.get("time"), "title": e.get("title")} for e in ev][:8]
    except Exception:
        ev = []
    _NEWS[day] = (time.time(), ev)
    return ev


# ------------------------------------------------------------------------------------------------ the PC bot hook
def bot_ctx(bot, now: int) -> dict:
    """ctx for build() from the PC bot (engine/live.py LiveBot): sizing switch + eval state, health, guards. Never raises."""
    c = {"lit_sizing": getattr(bot, "_lit_sizing", None) or {}}
    for k, fn in (("eval_state", "eval_state"), ("eval_room", "eval_room")):
        try:
            c[k] = getattr(bot, fn)()
        except Exception:
            c[k] = None
    if c.get("eval_state") is None and c.get("eval_room") is not None:
        c["room"] = c["eval_room"]
    st = getattr(bot, "state", None) or {}
    c["eval_clock"] = st.get("eval_2wk")
    c["eval_life"] = st.get("eval_life")
    try:
        from engine import accounts
        c["health"] = accounts.pc_health(bot, now)
    except Exception:
        c["health"] = None
    try:
        from engine import guards
        gc = guards.config(bot)
        c["guards_cfg"] = gc
        c["clock_drift_s"] = _r2(guards._CLOCK.get("drift"), 1)
        c["clock_problem"] = guards.clock_problem(bot, gc)
        if gc.get("daily_loss"):
            pnl = bot.day_pnl_routed()
            if pnl <= -float(gc["daily_loss_usd"]):
                c["daily_loss_hit"] = f"today's routed P&L {_usd(pnl)} reached the soft daily loss"
    except Exception:
        pass
    try:
        rq = {}
        for r in getattr(bot, "ledger", None) or []:
            if r.get("side") in ("buy", "sell") and r.get("entry_t"):
                rq[int(r["entry_t"])] = int(r.get("qty") or 0)
        c["routed_qty"] = rq
    except Exception:
        pass
    from engine.lit_live import trading_date
    c["news"] = _news(str(_et(now).date()))
    _ = trading_date
    return c
