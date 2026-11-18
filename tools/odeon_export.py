"""ODEON exporter: the trades the 3D replay theater plays (tools/web_public/odeon/, owner 2026-11-03).

Writes tools/web_public/odeon/trades.json: the last ~60 trades of the bots, each with its 1m bars (from before the setup to the
exit) and a plain-language caption track. Read-only: nothing here decides, sizes or routes a trade.

Sources (futures only, never Yahoo):
  LIT     research/lab/replays.json "charts" (tools/lit_chart_data.py: the engine's own swept levels, inducement, sweep,
          5m CISD, limit, tap, 1m CISD, entry, stop, target, breakeven and exit of every 2026 live-settings replay trade)
          + research/lab/backtest_live.json (MFE, the exit name)
  ATLAS   the members' stored research trades (research/second/ema_best.json, md_best.json, sr_best.json) and, when a
          trade has a picture, its plain-words setup line (research/lab/chart_examples/index.json, the "alt" text up to
          "Result:", which engine/trade_chart.py builds from what the bot saw at the entry)
  real (data) every account's live trades of the PC's data branch (tools/live_trades.py: data/pc_days/<day>/trades.jsonl.gz
          + bars/<ROOT>_1m.csv.gz, pulled by tools/data_pull.py), reel id real.<account key>.<day_HHMM>_<side>, "ak" = the account
  paper / real  the cloud's own trades since the PC feed (2026-10-19 on): research/odeon/cloud_trades.json, a snapshot of the
          `dashboard` branch's state.json (the cloud paper ledger + the PC account's closed MFFU eval trades from its
          heartbeat), refreshed by `--snapshot`; or --data <site data.json> (the published file: live.ledger + accounts)
          instead. Each gets its backtest / paper twin (same entry time) when there is one
  bars    data/NQ_1m.csv (TradingView CME NQ1! 1m, moved onto the 5m file's price basis window by window, as
          engine/lit.py bars_1m does), data/NQ_5m.csv when a window has no 1m bars, any --bars CSV (time,open,high,low,close:
          e.g. the PC's NinjaTrader MNQ archive), the data.json's live.bars1, and for the cloud's trades the PC's own
          NinjaTrader MNQ 1m bars around each one (research/odeon/pc_bars_1m.csv.gz, from the dashboard branch's bars_1m.csv
          and research/feed/nt_mnq_1m.csv.gz of tools/hb_bars.py)
A trade without bars is left out (it cannot be played).

Caption track ("events"): one row per moment, {t, k, text, refs}. t is the second the fact is known (a bar's close, a fill),
refs every time the text depends on; the exporter never writes a caption before its refs (no look-ahead), the outcome is
only in the exit row, and the rows are sorted by t. Times are epoch seconds (UTC); `off` is the trade day's ET offset.
Bars: quarter points relative to p0 (price = (p0 + v) / 4), times t0 + dt * s.

The output is deterministic (no clock, sorted keys, fixed float rounding): the same inputs give the same bytes.

  python tools/odeon_export.py                      # 42 LIT + 14 ATLAS + the cloud's trades -> tools/web_public/odeon/trades.json
  python tools/odeon_export.py --snapshot           # first refresh research/odeon/ from the dashboard branch (git fetch origin dashboard)
  python tools/odeon_export.py --data site/data.json --bars data/nt_bars/MNQ_1m.csv --out /tmp/trades.json
"""
from __future__ import annotations

import argparse
import bisect
import csv
import datetime as dt
import gzip
import io
import json
import os
import re
import subprocess
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in __import__("sys").path:
    __import__("sys").path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
OUT = os.path.join(ROOT, "tools", "web_public", "odeon", "trades.json")
REPLAYS = os.path.join(ROOT, "research", "lab", "replays.json")
BACKTEST = os.path.join(ROOT, "research", "lab", "backtest_live.json")
EXAMPLES = os.path.join(ROOT, "research", "lab", "chart_examples", "index.json")
BARS_1M = os.path.join(ROOT, "data", "NQ_1m.csv")
BARS_5M = os.path.join(ROOT, "data", "NQ_5m.csv")
SNAP = os.path.join(ROOT, "research", "odeon")
CLOUD = os.path.join(SNAP, "cloud_trades.json")          # the cloud's paper ledger + the PC's eval trades (a snapshot)
CLOUD_BARS = os.path.join(SNAP, "pc_bars_1m.csv.gz")     # the PC's NinjaTrader MNQ 1m bars around them
NT_1M = os.path.join(ROOT, "research", "feed", "nt_mnq_1m.csv.gz")
ATLAS = (("ema_lon_vix", "EMA", "London EMA trend pullback", "research/second/ema_best.json"),
         ("macd_sweep", "MACD", "MACD divergence at a liquidity sweep", "research/second/md_best.json"),
         ("sr_nyreclaim", "S/R", "NY sweep-and-reclaim", "research/second/sr_best.json"))
PRE = 120 * 60            # bars from 2 h before the entry ...
PRE_SETUP = 20 * 60       # ... or 20 min before the first sweep, whichever is earlier
PRE_MAX = 5 * 3600        # never more than 5 h before the entry
TAIL = 3 * 60             # 3 bars after the exit bar (the burst needs a little room)
MICRO = 2.0               # $ per point per MNQ micro
OUTCOME = re.compile(r"\b(target hit|stopped out|breakeven stop|flat at the close|not moving, cut|win|loss|profit)\b|[+−-]\$\d",
                     re.I)  # words that give the result away: only the exit row may hold them


# ---------------------------------------------------------------- formatting
def px(x: float) -> str:
    return f"{float(x):,.2f}"


def hhmm(t: int, off: int) -> str:
    return dt.datetime.fromtimestamp(int(t) + int(off), dt.timezone.utc).strftime("%H:%M")


def money(x: float) -> str:
    return ("+" if x > 0 else "−" if x < 0 else "") + f"${abs(float(x)):,.2f}"


def rfmt(r: float) -> str:
    return ("+" if r > 0 else "−" if r < 0 else "") + f"{abs(float(r)):.2f}R"


def et_off(t: int) -> int:
    return int(dt.datetime.fromtimestamp(int(t), ET).utcoffset().total_seconds())


def session_of(t: int, off: int) -> str:
    h = dt.datetime.fromtimestamp(int(t) + int(off), dt.timezone.utc).hour
    return "London" if 2 <= h < 7 else "New York" if 7 <= h < 17 else "Asia"


def micros(q) -> str:
    q = int(q or 1)
    return f"{q} micro" + ("" if q == 1 else "s")


def r2(x):
    return None if x is None else round(float(x), 2)


# ---------------------------------------------------------------- bars
class Tape:
    """Every 1m bar we can use, keyed by epoch second, on the 5m file's price basis; 5m bars as the fallback."""

    def __init__(self, t_min: int, t_max: int, extra=(), live1=None):
        self.b5 = _read_csv(BARS_5M, t_min - 86400, t_max + 86400)
        raw = _read_csv(BARS_1M, t_min - 86400, t_max + 86400)
        self.b1 = _on_5m_basis(raw, self.b5)
        # later sources win for a minute they share (PC archive, the cloud's live bars): they are the live feed's own bars
        for path in extra:
            self.b1.update(_read_csv(path, t_min - 86400, t_max + 86400))
        for row in live1 or []:
            if len(row) >= 5:
                self.b1[int(row[0])] = tuple(float(v) for v in row[1:5])
        self.t1 = sorted(self.b1)
        self.t5 = sorted(self.b5)

    def window(self, a: int, z: int):
        """(secs, [(t, o, h, l, c)]) for [a, z]: 1m bars when they cover >= 80 % of the 5m bars there, else 5m bars."""
        i, j = bisect.bisect_left(self.t1, a), bisect.bisect_right(self.t1, z)
        one = [(t, *self.b1[t]) for t in self.t1[i:j]]
        i5, j5 = bisect.bisect_left(self.t5, a // 300 * 300), bisect.bisect_right(self.t5, z)
        five = [(t, *self.b5[t]) for t in self.t5[i5:j5]]
        if one and len(one) >= 0.8 * 5 * max(1, len(five)):
            return 60, one
        return 300, five


def _read_csv(path: str, a: int, z: int) -> dict:
    out = {}
    if not path or not os.path.exists(path):
        return out
    with (gzip.open(path, "rt", encoding="utf-8") if path.endswith(".gz") else open(path, encoding="utf-8")) as fh:
        rd = csv.reader(fh)
        head = [h.strip().lower() for h in next(rd)]
        ix = [head.index(k) for k in ("time", "open", "high", "low", "close")]
        for row in rd:
            try:
                t = int(float(row[ix[0]]))
            except (ValueError, IndexError):
                continue
            if a <= t <= z:
                out[t] = tuple(float(row[k]) for k in ix[1:])
    return out


def _on_5m_basis(b1: dict, b5: dict) -> dict:
    """Move each 5-minute window of 1m bars onto the 5m file's basis when all four prices differ by one constant (the
    1m file holds a few days on another contract's basis); a window that matches nothing keeps its own prices."""
    by5: dict = {}
    for t in sorted(b1):
        by5.setdefault(t // 300 * 300, []).append(t)
    out = {}
    for w, ts in by5.items():
        k = 0.0
        ref = b5.get(w)
        if ref and len(ts) == 5:
            agg = (b1[ts[0]][0], max(b1[t][1] for t in ts), min(b1[t][2] for t in ts), b1[ts[-1]][3])
            d = [round(r - a, 2) for r, a in zip(ref, agg)]
            if d[0] != 0 and len(set(d)) == 1:
                k = d[0]
        for t in ts:
            out[t] = tuple(round(v + k, 2) for v in b1[t])
    return out


def pack(secs: int, rows) -> dict:
    t0 = rows[0][0]
    p0 = int(min(r[3] for r in rows) * 4)
    q = lambda v: int(round(v * 4)) - p0  # noqa: E731
    return {"t0": t0, "s": secs, "p0": p0, "dt": [(r[0] - t0) // secs for r in rows],
            "o": [q(r[1]) for r in rows], "h": [q(r[2]) for r in rows], "l": [q(r[3]) for r in rows], "c": [q(r[4]) for r in rows]}


def excursions(rows, secs, d, entry, exit_px, t_in, t_out):
    """(MFE, MAE) in points over the bars from the fill to the exit bar; the exit bar counts only up to the exit price."""
    fav, adv = 0.0, 0.0
    for t, o, h, l, c in rows:
        if t + secs <= t_in or t > t_out:
            continue
        hi, lo = (h, l)
        if t <= t_out < t + secs or t == t_out:          # the exit bar: the move stops at the exit price
            if d * (exit_px - entry) >= 0:
                hi, lo = (min(h, exit_px), l) if d > 0 else (h, max(l, exit_px))
            else:
                hi, lo = (h, max(l, exit_px)) if d > 0 else (min(h, exit_px), l)
        f = (hi - entry) if d > 0 else (entry - lo)
        a = (entry - lo) if d > 0 else (hi - entry)
        fav, adv = max(fav, f), max(adv, a)
    return round(fav, 2), round(adv, 2)


def first_cross(rows, secs, a, z, price, d):
    """end time of the first bar in [a, z) that trades through `price` upward (d=1) or downward (d=-1), else None."""
    for t, o, h, l, c in rows:
        if a <= t < z and ((d > 0 and h > price) or (d < 0 and l < price)):
            return t + secs
    return None


def ev(t, k, text, refs=(), **extra):
    refs = sorted({int(r) for r in refs if r is not None} | {int(t)})
    if max(refs) > int(t):
        raise ValueError(f"look-ahead in {k}: t {t} < ref {max(refs)}")
    return {"t": int(t), "k": k, "text": text, "refs": refs, **extra}


# ---------------------------------------------------------------- the caption tracks
def session_marks(a: int, z: int, off: int):
    """London open (02:00 ET) and the New York cash open (09:30 ET) inside the window."""
    out = []
    day0 = (a + off) // 86400 * 86400 - off
    for dd in (0, 86400):
        for mod, k, text in ((120, "london", "London opens (02:00 ET)."), (570, "nyopen", "New York cash open (09:30 ET).")):
            t = day0 + dd + mod * 60
            if a < t < z:
                out.append(ev(t, "session", text))
    return out


def lit_events(rec: dict, rows, secs: int, a: int, t_end: int) -> list:
    off, d = int(rec["off"]), int(rec["d"])
    side = "SHORT" if d < 0 else "LONG"
    hl = "high" if d < 0 else "low"
    E = []
    known = [lv for lv in rec["levels"] if lv.get("t") is None or lv["t"] + 300 <= a]   # a level is known once its bar closed
    if known:
        names = ", ".join(f"{level_name(lv['label'])} {px(lv['px'])}" for lv in known)
        E.append(ev(a, "levels", f"Liquidity on the map: {names}.", [lv["t"] + 300 for lv in known if lv.get("t") is not None],
                    levels=[lv["k"] for lv in known]))
    for lv in rec["levels"]:
        if lv not in known:
            E.append(ev(lv["t"] + 300, "level", f"New liquidity level: the {level_name(lv['label'])} at {px(lv['px'])}.",
                        [lv["t"] + 300], levels=[lv["k"]]))
    for i in rec.get("idm") or []:
        tk = i["taken_t"] + 300
        E.append(ev(tk, "idm", f"Inducement: the swing {hl} at {px(i['px'])} is run at {hhmm(i['taken_t'], off)}.",
                    [tk, i["t"] + 300], price=i["px"]))
    # the sweep: each level at the first bar that trades through it (from the engine's sweep bar on)
    sw = rec["sweep"]
    groups: dict = {}
    for lv in rec["levels"]:
        tc = first_cross(rows, secs, sw["t"], rec["entry"]["t"], lv["px"], -d) or (sw["t"] + 300)
        groups.setdefault(max(tc, (lv.get("t") or 0) + 300), []).append(lv)
    for tc in sorted(groups):
        lvs = groups[tc]
        what = " and ".join(f"the {level_name(lv['label'])} ({px(lv['px'])})" for lv in lvs)
        E.append(ev(tc, "sweep", f"{session_of(tc - secs, off)} sweeps {what} at {hhmm(tc - secs, off)}.", [tc],
                    levels=[lv["k"] for lv in lvs], price=min(lv["px"] for lv in lvs) if d < 0 else max(lv["px"] for lv in lvs)))
    c5 = rec["cisd5"]
    tc5 = c5["t"] + 300
    ext_known = sw["ext_t"] + 300
    E.append(ev(tc5, "disp", f"Displacement {'down' if d < 0 else 'up'}: a {c5['disp']:.2f} ATR candle body away from the sweep.",
                [tc5]))
    E.append(ev(tc5, "cisd5", f"5m CISD at {hhmm(c5['t'], off)}: a close back through {px(c5['px'])}; the sweep {hl} "
                f"{px(sw['ext_px'])} holds.", [tc5, ext_known], price=c5["px"]))
    lim = rec.get("limit")
    if lim:
        mins = round((lim["t1"] - lim["t0"]) / 60)
        E.append(ev(lim["t0"], "limit", f"Limit {side.lower()} at {px(lim['px'])}, good for {mins} minutes.", [lim["t0"], tc5],
                    price=lim["px"]))
        if lim.get("tap_t") and lim["tap_t"] < rec["entry"]["t"]:
            tt = lim["tap_t"] + 60
            E.append(ev(min(tt, rec["entry"]["t"]), "tap", f"Price taps the limit at {hhmm(lim['tap_t'], off)}.",
                        [min(tt, rec["entry"]["t"])]))
    c1 = rec.get("cisd1")
    if c1 and rec.get("tf") == 1:
        E.append(ev(c1["t"] + 60, "cisd1", f"1m CISD at {hhmm(c1['t'], off)}: a close through {px(c1['px'])}.", [c1["t"] + 60],
                    price=c1["px"]))
    en = rec["entry"]
    risk = abs(en["px"] - rec["stop"])
    E.append(ev(en["t"], "entry",
                f"{side.capitalize()} {micros(rec['qty'])} at {px(en['px'])}. Stop {px(rec['stop'])}, 1 tick beyond the sweep {hl} "
                f"{px(sw['ext_px'])} ({risk:.2f} pts, {money(risk * MICRO * int(rec['qty'] or 1)).lstrip('+')} risk). "
                f"Target {px(rec['target'])} ({rec['target_label']}, {rec['plan_rr']:.2f}R).",
                [en["t"], ext_known], price=en["px"]))
    be = rec.get("be")
    if be and be.get("t"):
        tb = min(be["t"] + 60, t_end)
        E.append(ev(tb, "be", "1R reached: the stop moves to breakeven + 1.25 pts (costs).", [tb],
                    price=round(en["px"] + d * 1.25, 2)))
    return E


def exit_event(kind: str, t_bar: int, t_end: int, xpx: float, usd: float, r: float, off: int) -> dict:
    k = (kind or "").upper()
    what = {"TARGET": "Target hit", "STOP": "Stopped out", "BE": "Breakeven stop", "EOD": "Flat at the close",
            "TIME": "Flat at the close", "CUT_T15": "15-minute check: not moving, cut"}.get(k, f"Exit ({kind})")
    return ev(t_end, "exit", f"{what} at {px(xpx)} ({hhmm(t_bar, off)}): {money(usd)}, {rfmt(r)}.", [t_end], price=xpx,
              outcome=outcome_of(k, r))


def outcome_of(kind: str, r: float) -> str:
    if (kind or "").upper() == "BE":
        return "be"
    return "win" if r > 0 else "loss" if r < 0 else "be"


def exit_bar(rows, secs, t_exit, xpx, t_in, exact=False):
    """(bar time, bar end) of the exit. exact (LIT records): the bar that starts at t_exit. Otherwise (research trades
    stamped on 5m bars) the first bar from max(fill, t_exit - 5 min) to t_exit that trades the exit price, else the bar
    holding t_exit."""
    if exact:
        for r in rows:
            if r[0] <= t_exit < r[0] + secs:
                return r[0], r[0] + secs
    for r in rows:
        if max(t_in, t_exit - 300) <= r[0] <= t_exit and r[3] - 0.25 <= xpx <= r[2] + 0.25:
            return r[0], r[0] + secs
    cands = [r for r in rows if r[0] <= t_exit < r[0] + secs]
    return (cands[0][0], cands[0][0] + secs) if cands else (t_exit, t_exit)


LEVEL_WORDS = {"PDH": "previous day high", "PDL": "previous day low", "PWH": "previous week high", "PWL": "previous week low",
               "PMH": "previous month high", "PML": "previous month low", "EQH": "equal highs", "EQL": "equal lows",
               "NWOG": "new week opening gap", "NDOG": "new day opening gap"}


def level_name(label: str) -> str:
    """'Frankfurt H' -> 'Frankfurt high', 'PDH' -> 'previous day high'."""
    if label in LEVEL_WORDS:
        return LEVEL_WORDS[label]
    if label.endswith(" H"):
        return label[:-2] + " high"
    if label.endswith(" L"):
        return label[:-2] + " low"
    return label


# ---------------------------------------------------------------- one trade
def make_trade(tape: Tape, base: dict, events_fn) -> dict | None:
    """base: id, bot, strat, src, day, d, qty, entry {t, px}, stop, target, exit {t, px, kind}, usd, r, risk_pts, off;
    events_fn(rows, secs, a, t_end) -> the setup rows (before the entry); session marks, the exit row are added here."""
    en, xt = base["entry"], base["exit"]
    a = min(en["t"] - PRE, (base.get("setup_t") or en["t"]) - PRE_SETUP)
    a = max(a, en["t"] - PRE_MAX)
    secs, rows = tape.window(a, xt["t"] + TAIL)
    if not rows or rows[0][0] > en["t"] or rows[-1][0] < xt["t"] - 300:
        return None
    a = rows[0][0]
    tb, t_end = exit_bar(rows, secs, xt["t"], xt["px"], en["t"], base.get("exact_exit", False))
    rows = [r for r in rows if r[0] <= t_end + TAIL]
    off = base["off"]
    E = session_marks(a, en["t"], off) + events_fn(rows, secs, a, t_end)
    for e in E:                      # a fact from before the first bar is told when the tape starts (later = never look-ahead)
        e["t"] = max(e["t"], a)
    E.append(exit_event(xt["kind"], tb, t_end, xt["px"], base["usd"], base["r"], off))
    E.sort(key=lambda e: (e["t"], ORDER.index(e["k"]) if e["k"] in ORDER else 99))
    mfe, mae = excursions(rows, secs, base["d"], en["px"], xt["px"], en["t"], tb)
    risk = base["risk_pts"] or abs(en["px"] - base["stop"])
    q = int(base["qty"] or 1)
    out = {k: base[k] for k in ("id", "bot", "strat", "label", "src", "day", "qty", "stop", "target", "off")}
    out.update({
        "side": "LONG" if base["d"] > 0 else "SHORT", "d": base["d"],
        "entry": {"t": en["t"], "px": en["px"]},
        "exit": {"t": tb, "t_end": t_end, "px": xt["px"], "kind": xt["kind"], "outcome": outcome_of(xt["kind"], base["r"])},
        "usd": round(float(base["usd"]), 2), "r": round(float(base["r"]), 2), "risk_pts": round(float(risk), 2),
        "risk_usd": round(float(risk) * MICRO * q, 2), "plan_rr": r2(base.get("plan_rr")), "target_label": base.get("target_label"),
        "mfe_pts": mfe, "mae_pts": mae, "mfe_r": round(mfe / risk, 2) if risk else None, "mae_r": round(mae / risk, 2) if risk else None,
        "mfe_usd": round(mfe * MICRO * q, 2), "mae_usd": round(mae * MICRO * q, 2), "held_min": round((t_end - en["t"]) / 60),
        "levels": base.get("levels") or [], "sweep": base.get("sweep"), "be": base.get("be"),
        "twin": base.get("twin"), "events": E, "bars": pack(secs, rows)})
    return out


ORDER = ["session", "levels", "level", "idm", "sweep", "disp", "cisd5", "limit", "tap", "cisd1", "setup", "entry", "be", "exit"]


def lit_trades(tape: Tape, n: int) -> list:
    with open(REPLAYS, encoding="utf-8") as fh:
        charts = json.load(fh).get("charts") or {}
    recs = sorted(charts.values(), key=lambda r: (r["entry"]["t"], r["id"]))[-n:] if n else []
    out = []
    for rec in recs:
        lvl = [{"k": lv["k"], "label": lv["label"], "name": level_name(lv["label"]), "px": lv["px"], "t": lv.get("t")}
               for lv in rec["levels"]]
        sw = rec["sweep"]
        base = {"id": "lit." + rec["id"], "bot": "LIT", "strat": "LIT", "label": "Zlarior · LIT (the 50K)", "src": "backtest",
                "day": rec["day"], "d": int(rec["d"]), "qty": int(rec["qty"] or 1), "entry": rec["entry"], "stop": rec["stop"],
                "target": rec["target"], "exit": {"t": rec["exit"]["t"], "px": rec["exit"]["px"], "kind": rec["exit_kind"]},
                "usd": rec["pnl"], "r": rec["r"], "risk_pts": rec["risk_pts"], "off": int(rec["off"]), "plan_rr": rec.get("plan_rr"),
                "target_label": rec.get("target_label"), "setup_t": min([sw["t"]] + [i["taken_t"] for i in rec.get("idm") or []]), "levels": lvl, "exact_exit": True,
                "sweep": {"t": sw["t"], "ext_px": sw["ext_px"], "ext_t": sw["ext_t"]},
                "be": ({"t": rec["be"]["t"], "px": round(rec["entry"]["px"] + int(rec["d"]) * 1.25, 2)} if (rec.get("be") or {}).get("t") else None)}
        tr = make_trade(tape, base, lambda rows, secs, a, t_end, rec=rec: lit_events(rec, rows, secs, a, t_end))
        if tr:
            out.append(tr)
    return out


def _alt_setup(alt: str) -> str | None:
    """the 'why it entered' part of a trade picture's alt text (between 'entry <px>: ' and '. Stop'), known at the entry."""
    m = re.search(r"ET, entry [\d,.]+: (.+?)\. Stop ", alt or "")
    return (m.group(1)[0].upper() + m.group(1)[1:] + ".") if m else None


def atlas_trades(tape: Tape, n: int) -> list:
    alts = {}
    if os.path.exists(EXAMPLES):
        with open(EXAMPLES, encoding="utf-8") as fh:
            ix = json.load(fh)
        for key, items in (ix.get("strategies") or {}).items():
            for it in items if isinstance(items, list) else items.get("items", []):
                alts[(key, int(it["entry_t"]))] = it.get("alt")
    T = []
    for key, short, label, path in ATLAS:
        with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
            for t in json.load(fh)["trades"]:
                if str(t["day"]) >= "2026-01-01" and t.get("exit_t"):
                    T.append((int(t["entry_t"]), key, short, label, t))
    T.sort(key=lambda x: (x[0], x[1]))
    out = []
    for et_, key, short, label, t in (T[-n:] if n else []):
        d = int(t["dir"])
        off = et_off(et_)
        side = "short" if d < 0 else "long"
        why = _alt_setup(alts.get((key, et_))) or f"{label}, {side}: {t.get('setup') or 'setup'}."
        kind = str(t.get("exit_kind") or "").upper()
        risk = abs(float(t["entry"]) - float(t["stop"]))
        rr = abs(float(t["target"]) - float(t["entry"])) / risk if risk else None
        tid = f"{t['day']}_{dt.datetime.fromtimestamp(et_, ET):%H%M}_{side}"
        q = int(t.get("qty") or 1)
        base = {"id": f"{key}.{tid}", "bot": "ATLAS", "strat": short, "label": f"ATLAS · {label}", "src": "backtest",
                "day": t["day"], "d": d, "qty": q, "entry": {"t": et_, "px": float(t["entry"])}, "stop": float(t["stop"]),
                "target": round(float(t["target"]), 2), "exit": {"t": int(t["exit_t"]), "px": float(t["exit"]), "kind": kind},
                "usd": float(t["pnl_usd"]), "r": float(t["r"]), "risk_pts": risk, "off": off, "plan_rr": rr,
                "target_label": "plan target"}

        def evs(rows, secs, a, t_end, base=base, why=why):
            en = base["entry"]
            hl = "high" if base["d"] < 0 else "low"
            return [ev(en["t"], "setup", f"{base['strat']} setup: {why}"),
                    ev(en["t"], "entry", f"{base['side_word']} {micros(base['qty'])} at {px(en['px'])}. Stop {px(base['stop'])} "
                       f"beyond the setup {hl} ({base['risk_pts']:.2f} pts, {money(base['risk_pts'] * MICRO * base['qty']).lstrip('+')} risk). "
                       f"Target {px(base['target'])} ({base['plan_rr']:.2f}R).", price=en["px"])]
        base["side_word"] = side.capitalize()
        tr = make_trade(tape, base, evs)
        if tr:
            out.append(tr)
    return out


# ---------------------------------------------------------------- paper / real trades from the published data.json
def live_trades(tape: Tape, data: dict, twins: dict) -> list:
    """The paper ledger (live.ledger) and the MFFU eval's closed trades (accounts), with their twins."""
    rows = []
    led = (data.get("live") or {}).get("ledger") or []
    led = list(led.values()) if isinstance(led, dict) else led
    paper = {}
    for v in led:
        if v.get("entry_t") and v.get("exit_ts") and v.get("entry_px") is not None and v.get("exit_px") is not None:
            paper[int(v["entry_t"])] = v
            rows.append(("paper", {"entry_t": int(v["entry_t"]), "exit_t": int(v["exit_ts"]), "side": v["side"],
                                   "entry": v["entry_px"], "stop": v["stop_px"], "target": v["target_px"], "exit_px": v["exit_px"],
                                   "exit": v.get("exit"), "r": v.get("R"), "pnl": v.get("usd"), "qty": v.get("qty"),
                                   "risk_pts": v.get("risk_pts"), "swept": None}))
    for acc in data.get("accounts") or []:
        if acc.get("kind") == "paper" or "paper" in str(acc.get("name", "")).lower():
            continue
        for t in acc.get("trades") or []:
            if t.get("entry_t") and t.get("exit_t") and t.get("exit_px") is not None:
                rows.append(("real", dict(t)))
    out = []
    for src, t in rows:
        e_t = int(t["entry_t"])
        d = -1 if str(t["side"]).upper() == "SHORT" else 1
        off = et_off(e_t)
        side = "short" if d < 0 else "long"
        risk = float(t.get("risk_pts") or abs(float(t["entry"]) - float(t["stop"])))
        tw = twins.get(e_t)
        if src == "real" and e_t in paper:
            p = paper[e_t]
            tw = {"src": "paper", "r": r2(p.get("R")), "usd": r2(p.get("usd")), "exit": p.get("exit"), "qty": p.get("qty")}
        swept = t.get("swept") or []
        base = {"id": f"{src}.{dt.datetime.fromtimestamp(e_t, ET):%Y-%m-%d_%H%M}_{side}",
                "bot": "LIT", "strat": "LIT", "label": "Zlarior · LIT " + ("(MFFU eval, real)" if src == "real" else "(paper, cloud)"),
                "src": src, "day": f"{dt.datetime.fromtimestamp(e_t, ET):%Y-%m-%d}", "d": d, "qty": int(t.get("qty") or 1),
                "entry": {"t": e_t, "px": float(t["entry"])}, "stop": float(t["stop"]), "target": round(float(t["target"]), 2),
                "exit": {"t": int(t["exit_t"]), "px": float(t["exit_px"]), "kind": str(t.get("exit") or "").upper()},
                "usd": float(t.get("pnl") or 0), "r": float(t.get("r") or 0), "risk_pts": risk, "off": off,
                "plan_rr": abs(float(t["target"]) - float(t["entry"])) / risk if risk else None, "target_label": "VIX band",
                "twin": tw}

        def evs(rows, secs, a, t_end, base=base, swept=swept, side=side):
            en = base["entry"]
            E = []
            if swept:
                E.append(ev(en["t"], "setup", "Swept " + ", ".join(swept) + "."))
            E.append(ev(en["t"], "entry", f"{side.capitalize()} {micros(base['qty'])} at {px(en['px'])}. Stop {px(base['stop'])} "
                        f"({base['risk_pts']:.2f} pts). Target {px(base['target'])} ({(base['plan_rr'] or 0):.2f}R).", price=en["px"]))
            return E
        tr = make_trade(tape, base, evs)
        if tr:
            out.append(tr)
    return out


# ---------------------------------------------------------------- every account's live trades from the PC's data branch
def branch_trades(tape: Tape, rows: list, twins: dict, n: int = 40) -> list:
    """The data branch's closed live trades (tools/live_trades.load: data/pc_days, pulled by tools/data_pull.py) on the PC's own
    NinjaTrader 1m bars of that day. One reel per account and trade ("ak" = the account key); no bars = no reel (the Trading page
    then says the replay comes after the day's upload)."""
    out = []
    for t in rows[-n:]:
        if t.get("e") is None or t.get("s") is None or t.get("x") is None or not t.get("xt"):
            continue
        e_t, d = int(t["t"]), (-1 if t["side"] == "SHORT" else 1)
        side = "short" if d < 0 else "long"
        risk = abs(float(t["e"]) - float(t["s"]))
        tg = float(t["tg"]) if t.get("tg") is not None else float(t["e"]) + d * risk
        base = {"id": f"real.{t['ak']}.{dt.datetime.fromtimestamp(e_t, ET):%Y-%m-%d_%H%M}_{side}", "ak": t["ak"],
                "bot": t["bot"], "strat": t["bot"] if not t.get("m") else t["m"],
                "label": f"{t['an']} · {'Zlarior · LIT' if t['bot'] == 'LIT' else 'ATLAS' + (' ' + t['m'] if t.get('m') else '')} (MFFU, real)",
                "src": "real", "day": t["day"], "d": d, "qty": int(t.get("q") or 1),
                "entry": {"t": e_t, "px": float(t["e"])}, "stop": float(t["s"]), "target": round(tg, 2),
                "exit": {"t": int(t["xt"]), "px": float(t["x"]), "kind": str(t.get("k") or "").upper()},
                "usd": float(t.get("usd") or 0), "r": float(t.get("r") or 0), "risk_pts": risk, "off": et_off(e_t),
                "plan_rr": abs(tg - float(t["e"])) / risk if risk else None, "target_label": "VIX band" if t["bot"] == "LIT" else "target",
                "twin": twins.get(e_t) if t["bot"] == "LIT" else None}

        def evs(rows_, secs, a, t_end, base=base, side=side):
            en = base["entry"]
            return [ev(en["t"], "entry", f"{side.capitalize()} {micros(base['qty'])} at {px(en['px'])}. Stop {px(base['stop'])} "
                       f"({base['risk_pts']:.2f} pts). Target {px(base['target'])} ({(base['plan_rr'] or 0):.2f}R).", price=en["px"])]
        tr = make_trade(tape, base, evs)
        if tr:
            tr["ak"] = t["ak"]
            out.append(tr)
    return out


# ---------------------------------------------------------------- the cloud's own trades (a snapshot of the dashboard branch)
def _git_show(ref: str) -> bytes | None:
    p = subprocess.run(["git", "-C", ROOT, "show", ref], capture_output=True, timeout=120)
    return p.stdout if p.returncode == 0 else None


def snapshot(out_dir: str = SNAP, pad_before: int = 6 * 3600, pad_after: int = 3600) -> dict:
    """research/odeon/: the cloud's paper ledger and the PC account's closed trades (origin/dashboard state.json), as a
    data.json-shaped doc, and the PC's NinjaTrader MNQ 1m bars around each trade (the dashboard's bars_1m.csv, newest, over
    research/feed/nt_mnq_1m.csv.gz). Market data and trade records only: no account secret is in either file."""
    raw = _git_show("origin/dashboard:state.json")
    if raw is None:
        raise SystemExit("no origin/dashboard: run `git fetch origin dashboard` first")
    st = json.loads(raw)
    keep = ("day", "side", "entry_t", "exit_ts", "entry_px", "stop_px", "target_px", "exit_px", "exit", "R", "usd", "qty", "risk_pts")
    ledger = []
    for k, v in sorted(((st.get("ledger") or {}).items() if isinstance(st.get("ledger"), dict) else [])):
        row = {x: v.get(x) for x in keep if x != "entry_t"}
        row["entry_t"] = int(k)
        ledger.append(row)
    acct = (st.get("pc") or {}).get("acct") or {}
    tkeep = ("day", "entry_t", "exit_t", "side", "qty", "entry", "stop", "target", "exit_px", "exit", "r", "pnl", "risk_pts", "swept")
    trades = [{x: t.get(x) for x in tkeep} for t in acct.get("trades") or [] if t.get("entry_t") and t.get("exit_t")]
    data = {"live": {"ledger": ledger}, "accounts": [{"name": "MFFU 50K Builder eval", "kind": "eval", "trades": trades}] if trades else []}
    spans = [(int(r["entry_t"]) - pad_before, int(r["exit_ts"]) + pad_after) for r in ledger if r.get("exit_ts")]
    spans += [(int(t["entry_t"]) - pad_before, int(t["exit_t"]) + pad_after) for t in trades]
    bars = {}
    for src in (gzip.open(NT_1M, "rt", encoding="utf-8").read() if os.path.exists(NT_1M) else "",
                (_git_show("origin/dashboard:bars_1m.csv") or b"").decode("utf-8")):
        rd = csv.reader(io.StringIO(src))
        head = [h.strip().lower() for h in next(rd, [])]
        if not head:
            continue
        ix = [head.index(k) for k in ("time", "open", "high", "low", "close")]
        for row in rd:
            t = int(float(row[ix[0]]))
            if t % 60 == 0 and any(a <= t <= z for a, z in spans):
                bars[t] = [float(row[k]) for k in ix[1:]]                 # the dashboard's (newer) bar wins
    os.makedirs(out_dir, exist_ok=True)
    body = "time,open,high,low,close\n" + "".join(f"{t},{o:g},{h:g},{l:g},{c:g}\n" for t, (o, h, l, c) in sorted(bars.items()))
    with open(os.path.join(out_dir, os.path.basename(CLOUD_BARS)), "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, filename="") as gz:   # the same bars give the same bytes
            gz.write(body.encode("utf-8"))
    doc = {"v": 1, "kind": "odeon-cloud", "source": "origin/dashboard state.json (cloud paper ledger + the PC's eval trades) as of "
           + str(st.get("last_run") or "?"), "bars": f"{len(bars)} PC NinjaTrader MNQ 1m bars ({os.path.basename(CLOUD_BARS)})", "data": data}
    with open(os.path.join(out_dir, os.path.basename(CLOUD)), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True, ensure_ascii=False)
    return doc


# ---------------------------------------------------------------- the bundle
def build(n_lit: int = 42, n_atlas: int = 14, data_path: str | None = None, extra_bars=(), cloud: bool = True,
          pc_days: str | None = None) -> dict:
    """the reels: the last n_lit LIT + n_atlas ATLAS replays, plus the live trades: --data's when given, else the cloud
    snapshot's (research/odeon/, when `cloud` and it is there)"""
    data = None
    if data_path:
        with open(data_path, encoding="utf-8") as fh:
            data = json.load(fh)
    elif cloud and os.path.exists(CLOUD):
        with open(CLOUD, encoding="utf-8") as fh:
            data = json.load(fh)["data"]
        extra_bars = tuple(extra_bars) + (CLOUD_BARS,)
    with open(REPLAYS, encoding="utf-8") as fh:
        charts = json.load(fh).get("charts") or {}
    ts = [r["entry"]["t"] for r in charts.values()] or [0]
    t_min, t_max = min(ts) - 86400, max(ts) + 86400
    if data:
        lt = [int(v.get("entry_t") or 0) for v in ((data.get("live") or {}).get("ledger") or []) if isinstance(v, dict)]
        lt += [int(t.get("entry_t") or 0) for a in data.get("accounts") or [] for t in a.get("trades") or []]
        lt = [x for x in lt if x]
        if lt:
            t_min, t_max = min(t_min, min(lt) - 86400), max(t_max, max(lt) + 86400)
    from tools import live_trades as LT          # the PC's data branch (data/pc_days): every account's live trades + that day's bars
    brows = LT.load(pc_days or LT.PC_DAYS)
    if brows:
        extra_bars = tuple(extra_bars) + tuple(LT.bars_paths(pc_days or LT.PC_DAYS))
        t_min, t_max = min(t_min, brows[0]["t"] - 86400), max(t_max, brows[-1]["t"] + 86400)
    tape = Tape(t_min, t_max, extra_bars, ((data or {}).get("live") or {}).get("bars1"))
    trades = lit_trades(tape, n_lit) + atlas_trades(tape, n_atlas)
    twins = {}
    if data or brows:
        with open(BACKTEST, encoding="utf-8") as fh:
            bt = json.load(fh)["trades"]
        twins = {int(t["entry_t"]): {"src": "backtest", "r": r2(t.get("r")), "usd": r2(t.get("pnl")), "exit": t.get("exit"),
                                     "qty": t.get("qty")} for t in bt}
    if data:
        trades += live_trades(tape, data, twins)
    if brows:
        trades += branch_trades(tape, brows, twins)
    trades.sort(key=lambda t: (t["entry"]["t"], t["id"]), reverse=True)
    seen, uniq = set(), []
    for t in trades:
        if t["id"] not in seen:
            seen.add(t["id"])
            uniq.append(t)
    last = max((t["day"] for t in uniq), default="")
    return {"v": 1, "app": "odeon", "upto": last, "n": len(uniq),
            "source": "TradingView CME NQ1! 1m (data/NQ_1m.csv on the 5m basis; data/NQ_5m.csv where 1m is missing); "
                      "LIT: research/lab/replays.json charts (engine markers); ATLAS: research/second/*_best.json"
                      + ("; paper / real: the cloud's ledger and the PC's eval trades on the PC's NinjaTrader MNQ 1m bars" if data else ""),
            # (+ every account's live trades of the PC's data branch on that day's NinjaTrader bars, when data/pc_days is there)
            "trades": uniq}


def write(bundle: dict, out: str) -> int:
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    txt = json.dumps(bundle, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(txt)
    return len(txt.encode("utf-8"))


def jarvis_card(bundle: dict, now: int) -> dict:
    """the Jarvis live card (docs/JARVIS_APPS.md): reel count, the newest reel, its result"""
    T = bundle["trades"]
    if not T:
        return {"v": 1, "name": "ODEON", "status": {"level": "warn", "label": "Demo reel only"}, "kpis": [], "lines": [], "t": now,
                "open": "#reels", "theme": "#07060c"}
    t = T[0]
    net = sum(x["usd"] for x in T)
    day = dt.date.fromisoformat(t["day"])
    plain = lambda x: x.replace("\u2212", "-")  # noqa: E731
    return {"v": 1, "name": "ODEON", "status": {"level": "ok", "label": f"{len(T)} reels ready"},
            "kpis": [{"label": "Reels", "value": str(len(T))}, {"label": "Latest", "value": f"{day:%b} {day.day}"},
                     {"label": "Last reel", "value": plain(rfmt(t["r"])), "delta": plain(money(t["usd"]))}],
            "lines": [plain(f"{t['bot']} {t['side'].lower()} {t['day']}: {money(t['usd'])} ({rfmt(t['r'])})"),
                      plain(f"Net of the {len(T)} reels: {money(net)}")],
            "t": int(now), "open": "#reels", "theme": "#07060c"}


FIXTURE = os.path.join(ROOT, "tools", "web_public", "odeon", "fixture.js")


def write_fixture(bundle: dict, tid: str, path: str = FIXTURE) -> None:
    """the demo reel the page plays when trades.json is missing (and the tests' fixture): one exported trade, frozen"""
    tr = next(t for t in bundle["trades"] if t["id"] == tid)
    body = json.dumps(tr, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("// ODEON demo reel: one real 2026 LIT replay trade, frozen by `python tools/odeon_export.py --fixture <id>`.\n"
                 "// The page plays it when trades.json is missing; tests/test_odeon_page.py checks the page against it.\n"
                 f"export const DEMO = {body};\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ODEON exporter (tools/web_public/odeon/trades.json)")
    ap.add_argument("--lit", type=int, default=42, help="the last N LIT trades (default 42)")
    ap.add_argument("--atlas", type=int, default=14, help="the last N ATLAS member trades (default 14)")
    ap.add_argument("--snapshot", action="store_true", help="first refresh research/odeon/ (the cloud's trades and their PC bars) "
                    "from origin/dashboard")
    ap.add_argument("--data", default=None, help="the site's data.json: adds the paper ledger and the eval's real trades")
    ap.add_argument("--bars", action="append", default=[], help="extra 1m futures bars (CSV time,open,high,low,close)")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--fixture", default=None, help="also freeze this trade id as the demo reel (odeon/fixture.js)")
    a = ap.parse_args(argv)
    if a.snapshot:
        doc = snapshot()
        print(f"snapshot -> {SNAP}: {len(doc['data']['live']['ledger'])} paper trades, "
              f"{sum(len(x['trades']) for x in doc['data']['accounts'])} eval trades, {doc['bars']}")
    bundle = build(a.lit, a.atlas, a.data, a.bars)
    size = write(bundle, a.out)
    print(f"odeon -> {a.out}: {bundle['n']} trades, {size // 1024} KB")
    # the Jarvis card next to the page (its `t` is the build time, so it lives outside the deterministic trades.json)
    import time
    card = os.path.join(os.path.dirname(os.path.abspath(a.out)), "jarvis.json")
    with open(card, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(jarvis_card(bundle, int(time.time())), fh, ensure_ascii=False, indent=1)
    if a.fixture:
        write_fixture(bundle, a.fixture)
        print(f"fixture -> {FIXTURE}: {a.fixture}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
