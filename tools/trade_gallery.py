"""Trade gallery: annotated chart images of strategy trades, drawn the way an ICT/SMC futures trader reads a chart.

Each image (1400x800, dark) shows the trade's day on NQ1! CME futures bars (TradingView data via strategy_lab.bars,
never CFD), 06:30-15:55 ET, with:
  - the 07:00-09:25 ATM range box, its high/low carried forward
  - prior-day (CME day) high/low, Asia (20:00-24:00) and London (02:00-05:00) highs/lows; a line fades once taken
  - NY killzones 09:30-11:30 and 13:30-15:30
  - the sweep: the bar that took the level that set the trade up
  - FVG / IFVG zones near the entry that were still live at the decision bar (causal: closed bars only)
  - entry arrow, stop, target, exit marker + reason; title with date, side, R, $, size, setup; a text panel
    (setup, exit, and the bot's per-trade "thoughts" when a narrative output exists)

Trade sources (detected per trade):
  engine  Liquidity Engine testbed trades (strategy_lab.engine_trades format: entry_t = fill bar open, no prices).
          The day is replayed through engine.backtest.run with the testbed params (20-day live window, exactly as
          strategy_lab.engine_trades) to recover entry/stop/target/exits/sweep/zone; matched on entry_t + dir + pnl.
          If the replay does not match (or --no-replay), prices are estimated from the bars and labeled "est.".
  atm     tools/lab_models/atm.py trades (entry_t = signal close). Sweep, extreme, leg origin, 50% line and the
          inverted FVG are rebuilt from the bars with ATM_RULES.md R2-R5. For trades on a frame below 5m (1m ATM)
          a second "_zoom" image is drawn on that frame.
  lab     any other strategy_lab trade list (entry/stop/exit/exit_t): sweep = most extreme bar of the last 36 bars.

USAGE
  python tools/trade_gallery.py --trades research/lab/conf_testbed_orig1day.json --key ytd --name orig1day --n 10
  python tools/trade_gallery.py --trades research/lab/ATM_trades_base_tier.json --name ATM_base --all
  python tools/trade_gallery.py --trades research/lab/ATM_trades_1m_best.json --name ATM_1m_best --all
  python tools/trade_gallery.py --index-only
Output: research/lab/gallery/<name>_<YYYY-MM-DD>_<HHMM>.png, thumbs/, _manifest_<name>.json, index.html
"""
from __future__ import annotations

import argparse
import datetime as dt
import gc
import glob
import html
import json
import math
import os
import random
import re
import sys
import textwrap
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

import tools.strategy_lab as SL  # noqa: E402  (read-only use: bars())

LAB = os.path.join(ROOT, "research", "lab")
GAL = os.path.join(LAB, "gallery")
ET = SL.ET
TICK = 0.25
WIN = (390, 955)                    # bars opening 06:30 .. 15:50 ET (last close 15:55)
KZ = [(570, 690, "NY AM killzone"), (810, 930, "NY PM killzone")]
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
COL = dict(bg="#0d1117", ax="#10151c", grid="#222a35", text="#d9dee7", muted="#8b95a7", up="#26a69a", dn="#ef5350",
           atm="#f2c94c", pd="#b197fc", asia="#4dabf7", lon="#ffa94d", kz="#5c7cfa", fvg_up="#20c997", fvg_dn="#ff6b6b",
           ifvg="#e64980", trig="#ffd43b", long="#40c057", short="#fa5252", stop="#ff6b6b", tgt="#51cf66", be="#ffa94d",
           sweep="#ffd43b", win="#51cf66", loss="#ff6b6b", flat="#adb5bd", panel="#151b24", entry="#f8f9fa")
POOL_NAMES = {"PDH": "prior-day high", "PDL": "prior-day low", "PWH": "prior-week high", "PWL": "prior-week low",
              "ASH": "Asia high", "ASL": "Asia low", "LOH": "London high", "LOL": "London low", "ONH": "overnight high",
              "ONL": "overnight low", "H1H": "1H swing high", "H1L": "1H swing low", "ITH": "15m swing high",
              "ITL": "15m swing low", "EQH": "equal highs", "EQL": "equal lows", "PRH": "prior RTH high",
              "PRL": "prior RTH low", "AS": "Asia", "LO": "London", "ON": "overnight", "EQ": "equal highs/lows"}
ENGINE_EXIT = {
    "TARGET": "Target filled: price delivered to the planned draw.",
    "STOP": "Initial stop hit: the swept extreme did not hold.",
    "BE/TRAIL": "Ran to +1R, stop moved to break-even (+1 tick); price came back and took it.",
    "SIGNAL giveback": "Giveback rule: was up at least +0.5R, then a 5m close back through entry, out at that close.",
    "TIME STOP": "Time stop: no +0.5R within 30 minutes, out at the close.",
    "TIME": "Session flat at 15:55: neither stop nor target hit.",
    "EOD": "End of day.",
    "NEWS FLAT": "Flattened ahead of a news release.",
    "NOON UNPROTECTED": "Noon exit: stop still below entry at 12:00.",
    "IFVG FAIL": "IFVG failure: closed back through the trigger zone.",
}
LAB_EXIT = {"target": "Target filled.", "stop": "Stopped: price went beyond the sweep extreme.",
            "time": "Flat at 15:55: neither stop nor target hit.", "be": "Break-even stop after the partial.",
            "market": "Market exit.", "open": "Still open at the end of the data."}
ATM_CONF = [("trend_1h_with", "1H trend with"), ("smt", "SMT vs ES"), ("nq_rs_with", "NQ stronger than ES"),
            ("open_loc_with", "09:30 open on swept half"), ("ifvg_big", "IFVG >= 0.25 ATR"), ("v_fast", "fast V (<=2 bars)"),
            ("lrlr", "clean path (<=1 zone)"), ("tgt_pool", "target is a pool")]
INTRABAR = ("TARGET", "STOP", "BE/TRAIL", "TP1")


def _f(x):
    """numpy -> plain float (JSON/print safe)."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def hm(ts):
    return dt.datetime.fromtimestamp(int(ts), ET).strftime("%H:%M")


def px(v):
    return "n/a" if v is None else f"{v:,.2f}"


# ------------------------------------------------------------------------------------------------ bars
class Frame:
    """Full NQ1! history of one timeframe as arrays, with CME-day bounds, Wilder ATR14 and k=2 fractal pivots."""

    def __init__(self, tf):
        df = SL.bars("NQ", f"{tf}m")
        self.tf, self.secs = int(tf), 60 * int(tf)
        self.t = df["time"].to_numpy(np.int64)
        self.o = df["open"].to_numpy(float)
        self.h = df["high"].to_numpy(float)
        self.l = df["low"].to_numpy(float)
        self.c = df["close"].to_numpy(float)
        self.mod = df["mod"].to_numpy(int)
        day = df["day"].to_numpy()
        del df
        SL._BARS.pop(("NQ", f"{tf}m"), None)        # keep one copy in memory, not two
        cut = np.flatnonzero(day[1:] != day[:-1]) + 1
        self.starts, self.ends = np.r_[0, cut], np.r_[cut, len(day)]
        self.days = [str(x) for x in day[self.starts]]
        self.di = {d: k for k, d in enumerate(self.days)}
        del day
        pc = np.r_[self.c[0], self.c[:-1]]
        tr = np.maximum(self.h - self.l, np.maximum(np.abs(self.h - pc), np.abs(self.l - pc)))
        self.atr = pd.Series(tr).ewm(alpha=1.0 / 14, adjust=False).mean().to_numpy()
        h, l = self.h, self.l
        sh, sl = np.ones(len(h), bool), np.ones(len(h), bool)
        for j in (1, 2):
            sh &= (h > np.r_[np.full(j, np.inf), h[:-j]]) & (h >= np.r_[h[j:], np.full(j, np.inf)])
            sl &= (l < np.r_[np.full(j, -np.inf), l[:-j]]) & (l <= np.r_[l[j:], np.full(j, -np.inf)])
        self.psh, self.psl = sh, sl

    def idx(self, ts):
        """Index of the bar that opens exactly at ts (None if missing)."""
        j = int(np.searchsorted(self.t, ts))
        return j if j < len(self.t) and self.t[j] == ts else None

    def at(self, ts):
        """Index of the bar containing ts (open <= ts < open + secs), else the last bar before ts."""
        return max(0, int(np.searchsorted(self.t, ts, side="right")) - 1)

    def bounds(self, day):
        k = self.di.get(day)
        if k is None:
            return None
        return k, int(self.starts[k]), int(self.ends[k])


_FR = {}


def frame(tf):
    if tf not in _FR:
        _FR[tf] = Frame(tf)
    return _FR[tf]


def frame_has_day(tf, day):
    try:
        return frame(tf).bounds(day) is not None
    except Exception:
        return False


# ------------------------------------------------------------------------------------------------ levels / zones
def day_levels(F, k):
    """[(label, side, price, available_index, color)] for PDH/PDL, Asia, London and ATM H/L of CME day k."""
    a, b = int(F.starts[k]), int(F.ends[k])
    mod = F.mod[a:b]
    out = []
    if k > 0:
        a0, b0 = int(F.starts[k - 1]), int(F.ends[k - 1])
        out += [("PDH", "H", float(F.h[a0:b0].max()), a, COL["pd"]), ("PDL", "L", float(F.l[a0:b0].min()), a, COL["pd"])]
    for nm, (s0, s1), col, need in (("Asia", (1200, 1440), COL["asia"], 4), ("London", (120, 300), COL["lon"], 4),
                                    ("ATM", (420, 570), COL["atm"], max(2, (150 // F.tf) // 2))):
        ix = np.flatnonzero((mod >= s0) & (mod < s1)) + a
        if len(ix) >= need:
            out += [(nm + " H", "H", float(F.h[ix].max()), int(ix[-1]) + 1, col),
                    (nm + " L", "L", float(F.l[ix].min()), int(ix[-1]) + 1, col)]
    return out


def taken_at(F, side, level, j0, j1):
    """First bar index in [j0, j1) that trades through level by >= 1 tick, else None."""
    if j0 >= j1:
        return None
    hit = np.flatnonzero(F.h[j0:j1] >= level + TICK) if side == "H" else np.flatnonzero(F.l[j0:j1] <= level - TICK)
    return j0 + int(hit[0]) if len(hit) else None


def live_fvgs(F, j0, i_dec, min_sz):
    """3-candle FVGs whose third candle closed in [j0, i_dec], with their state at the close of bar i_dec.
    Bullish FVG (low[k3] > high[k1]): inverted by a close below its bottom (becomes a bearish IFVG), filled by a
    wick to its bottom. Bearish mirrors. An IFVG dies on a close back beyond its far side. Returns live ones only."""
    o, h, l, c = F.o, F.h, F.l, F.c
    out = []
    for k3 in range(max(j0, 2) + 2, i_dec + 1):
        for kind, bot, top in ((1, h[k3 - 2], l[k3]), (-1, h[k3], l[k3 - 2])):
            if top - bot < min_sz:
                continue
            state, inv = "fvg", None
            for j in range(k3 + 1, i_dec + 1):
                if state == "fvg":
                    if (kind == 1 and c[j] < bot) or (kind == -1 and c[j] > top):
                        state, inv = "ifvg", j
                        continue
                    if (kind == 1 and l[j] <= bot) or (kind == -1 and h[j] >= top):
                        state = "filled"
                        break
                elif (kind == 1 and c[j] > top) or (kind == -1 and c[j] < bot):
                    state = "dead"
                    break
            if state in ("fvg", "ifvg"):
                # support (+1) or resistance (-1) as of now: an inverted bullish gap is resistance
                pol = kind if state == "fvg" else -kind
                out.append({"lo": float(bot), "hi": float(top), "k1": k3 - 2, "k3": k3, "state": state, "inv": inv,
                            "pol": pol, "t0": int(F.t[k3 - 2])})
    return out


# ------------------------------------------------------------------------------------------------ trade loading
def load_trades(path, key=None):
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    meta = {"params": d.get("params") if isinstance(d, dict) else None}
    obj = d
    if key:
        obj = d[key]
    if isinstance(obj, dict):
        if "trades" in obj:
            obj = obj["trades"]
        else:
            raise SystemExit(f"{path}: no trade list under key {key!r}; keys: {list(obj)[:20]}")
    if not isinstance(obj, list):
        raise SystemExit(f"{path}: not a trade list")
    return obj, meta


def kind_of(t):
    if isinstance(t.get("info"), dict) and "atm_h" in t["info"]:
        return "atm"
    if "entry" not in t and ("trigger" in t or "f" in t):
        return "engine"
    return "lab"


def select(trades, n, all_=False, seed=7):
    """[(group, trade)]: best n and worst n by R, plus n random from the rest (seeded); everything with all_."""
    idx = list(range(len(trades)))
    if all_ or len(trades) <= 2 * n:
        return [("all", trades[i]) for i in sorted(idx, key=lambda i: trades[i]["entry_t"])]
    key = lambda i: (trades[i].get("r") or 0.0, trades[i].get("pnl") or 0.0)
    srt = sorted(idx, key=key)
    worst, best = srt[:n], srt[::-1][:n]
    rest = [i for i in idx if i not in set(best) | set(worst)]
    rnd = sorted(random.Random(seed).sample(rest, min(n, len(rest))))
    out = [("best", trades[i]) for i in sorted(best, key=lambda i: -key(i)[0])]
    out += [("worst", trades[i]) for i in sorted(worst, key=lambda i: key(i)[0])]
    out += [("random", trades[i]) for i in rnd]
    return out


# ------------------------------------------------------------------------------------------------ thoughts
def load_thoughts(extra=None):
    """Per-trade narrative ("trader brain") output keyed by (entry_t, dir): {'thoughts', 'head', 'bias', 'brain'}.
    Sources: research/lab/NARRATIVE_*.json and *narrative*/*thought* JSON (any record carrying entry_t + dir with a
    'thoughts' string, directly or under ver.<version>), plus research/lab/NARRATIVE_EXAMPLES.md (headings
    '### YYYY-MM-DD HH:MM ET: Long ...'). Matching is exact on entry time + side, never on the day alone."""
    out = {}
    files = sorted(set(glob.glob(os.path.join(LAB, "*arrative*.json")) + glob.glob(os.path.join(LAB, "*ARRATIVE*.json"))
                       + glob.glob(os.path.join(LAB, "*hought*.json")) + glob.glob(os.path.join(LAB, "narrative", "*.json"))))
    if extra and extra.endswith(".json"):
        files.append(extra)

    def side_of(x):
        try:
            return int(x)
        except (TypeError, ValueError):
            return {"long": 1, "short": -1}.get(str(x).lower())

    def put(rec):
        if rec.get("entry_t") is None:
            return
        src = str(rec.get("source") or "")
        fam = "atm" if "atm" in src.lower() else ("engine" if src else None)
        key = (int(rec["entry_t"]), side_of(rec.get("dir", rec.get("d"))), fam)
        vers = rec.get("ver") if isinstance(rec.get("ver"), dict) else ({"": rec} if "thoughts" in rec else {})
        v1 = None
        heads = []
        for vn, vv in vers.items():
            if not isinstance(vv, dict) or not vv.get("thoughts"):
                continue
            if v1 is None:
                v1 = (vn, vv)
            sc = vv.get("score")
            heads.append(f"{vn + ': ' if vn else ''}{vv.get('decision', '')} grade {vv.get('grade', '?')}"
                         + (f" ({sc:+.2f})" if isinstance(sc, (int, float)) else ""))
        if v1 is None:
            return
        th = v1[1]["thoughts"]
        th = " ".join(map(str, th)) if isinstance(th, list) else str(th)
        rec_out = {"thoughts": th, "head": "; ".join(heads)}
        nar = rec.get("nar") or {}
        if nar.get("bias"):
            dr = nar.get("draw") or {}
            rec_out["bias"] = (f"Pre-market bias {str(nar['bias']).upper()} (conviction {nar.get('conviction', 0):.2f}), "
                               f"day type {nar.get('day_type', '?')}" + (f"; draw {dr.get('nice') or dr.get('label')} "
                                                                         f"{dr['price']:,.2f}" if dr.get("price") else ""))
        br = rec.get("brain") or {}
        if br.get("log"):
            rec_out["brain"] = (f"Brain's own management: {br.get('r', 0):+.2f}R; "
                                + "; ".join(f"{hm(x[0])} {x[1]}" for x in br["log"][:3]))
        out[key] = rec_out

    def walk(x, depth=0):
        if depth > 5:
            return
        if isinstance(x, dict):
            if x.get("entry_t") is not None and ("ver" in x or "thoughts" in x):
                put(x)
                return
            for v in x.values():
                if isinstance(v, (dict, list)):
                    walk(v, depth + 1)
        elif isinstance(x, list):
            for v in x:
                walk(v, depth + 1)

    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                walk(json.load(fh))
        except Exception:
            pass
    mds = [os.path.join(LAB, "NARRATIVE_EXAMPLES.md")] + ([extra] if extra and extra.endswith(".md") else [])
    for md in mds:
        if not os.path.exists(md):
            continue
        with open(md, encoding="utf-8") as fh:
            text = fh.read()
        for sec in re.split(r"\n(?=#{2,4} )", text):
            head = sec.split("\n", 1)[0]
            m = re.search(r"(20\d\d-\d\d-\d\d)\s+(\d\d):(\d\d)", head)
            if not m:
                continue
            side = 1 if re.search(r"\blong\b", head, re.I) else (-1 if re.search(r"\bshort\b", head, re.I) else None)
            ts = int(dt.datetime(*map(int, m.group(1).split("-")), int(m.group(2)), int(m.group(3)), tzinfo=ET).timestamp())
            body = sec.split("\n", 1)[1] if "\n" in sec else ""
            mt = re.search(r"\*\*At entry:([^*]*)\*\*\s*(.+?)(?:\n\s*\n|\Z)", body, re.S)
            if not mt or (ts, side, None) in out:
                continue
            out[(ts, side, None)] = {"thoughts": re.sub(r"\s+", " ", mt.group(2)).strip()[:700], "head": mt.group(1).strip()}
    return out


def thought_for(t, TH, kind=None):
    """Exact match on entry time + side, preferring a record from the same family (ATM model vs engine)."""
    k = (int(t["entry_t"]), int(t.get("dir", 0) or 0))
    fam = "atm" if kind == "atm" else "engine"
    return TH.get(k + (fam,)) or TH.get(k + (None,))


# ------------------------------------------------------------------------------------------------ engine replay
_REPLAY_LOG = []


def engine_replay(t, params):
    """Re-run the Liquidity Engine on the trade's 20-day live window (strategy_lab.engine_trades / five_year.live_jobs)
    and return the full trade record that matches entry_t + dir (+ pnl within $1), else None."""
    try:
        from engine.backtest import run
    except Exception as e:                       # engine mid-edit or broken: fall back to estimates
        _REPLAY_LOG.append(f"import failed: {e}")
        return None
    day = t["day"]
    a = (dt.date.fromisoformat(day) - dt.timedelta(days=20)).isoformat()
    try:
        r = run("NQ", "5m", {**(params or {}), "days_from": a, "days_to": day}, light=True)
    except Exception as e:
        _REPLAY_LOG.append(f"{day}: replay failed: {e}")
        return None
    hit = None
    for x in r["trades"]:
        if int(x["entry_t"]) == int(t["entry_t"]) and int(x["dir"]) == int(t["dir"]):
            hit = x
            break
    del r
    if hit is None or abs(float(hit["pnl"]) - float(t["pnl"])) > 1.0:
        _REPLAY_LOG.append(f"{day}: no exact match")
        return None
    keep = ("entry", "stop", "stop0", "target", "target_label", "exits", "signal_t", "signal_price", "sweep_ext", "pools",
            "zone", "conf_tags", "grade", "qty_label", "trigger", "trigger_tf", "features", "mfe", "mae", "open_loc",
            "risk_pts", "rr", "htf_trend", "m15_trend", "regime", "partial_px", "partial_done", "pd_pos", "exit_reason",
            "checklist", "draw", "stop_src", "bars_held")
    out = {}
    for k in keep:
        v = hit.get(k)
        if isinstance(v, np.generic):
            v = v.item()
        out[k] = v
    out["exits"] = [{"t": int(e["t"]), "qty": int(e["qty"]), "price": float(e["price"]), "reason": str(e["reason"])}
                    for e in hit.get("exits", [])]
    if out.get("zone") is not None:
        out["zone"] = [float(z) for z in out["zone"]]
    return out


# ------------------------------------------------------------------------------------------------ view models
def _size_label(q, label=None):
    if label:
        return str(label)
    q = int(q or 0)
    if q >= 10 and q % 10 == 0:
        return f"{q // 10} NQ ({q} MNQ eq.)"
    return f"{q} MNQ"


def _sweep_generic(F, i_dec, d, levels, lookback=36):
    """Most extreme bar of the last `lookback` bars (low for longs) and the most significant level it took."""
    a = max(0, i_dec - lookback + 1)
    j = a + (int(np.argmin(F.l[a:i_dec + 1])) if d == 1 else int(np.argmax(F.h[a:i_dec + 1])))
    price = float(F.l[j] if d == 1 else F.h[j])
    side = "L" if d == 1 else "H"
    rank = {"PDH": 0, "PDL": 0, "London H": 2, "London L": 2, "Asia H": 3, "Asia L": 3, "ATM H": 1, "ATM L": 1}
    took = []
    for nm, sd, lv, av, _ in levels:
        if sd != side or av > j:
            continue
        first = taken_at(F, sd, lv, av, j + 1)
        if first == j:
            took.append((rank.get(nm, 5), nm, lv))
    took.sort()
    return j, price, [nm for _, nm, _ in took]


def engine_view(t, F, params, replay=True):
    d = int(t["dir"])
    f = t.get("f") or {}
    x = engine_replay(t, params) if replay else None
    k, a, b = F.bounds(t["day"])
    levels = day_levels(F, k)
    i_fill = F.idx(int(t["entry_t"]))
    if i_fill is None:
        i_fill = F.at(int(t["entry_t"]))
    v = {"kind": "engine", "est": [], "dir": d, "day": t["day"], "entry_t": int(t["entry_t"]), "r": _f(t.get("r")),
         "pnl": _f(t.get("pnl")), "qty": t.get("qty"), "trigger": t.get("trigger") or t.get("setup"),
         "grade": t.get("grade"), "regime": t.get("regime"), "f": f}
    risk = float(t.get("risk_pts") or 0.0)
    if x is not None:
        v.update(entry=float(x["entry"]), stop0=float(x.get("stop0") or x["stop"]), stopf=float(x["stop"]),
                 target=_f(x.get("target")), target_label=x.get("target_label"), sweep_px=_f(x.get("sweep_ext")),
                 pools=list(x.get("pools") or []), zone=x.get("zone"), tags=list(x.get("conf_tags") or []),
                 qty_label=x.get("qty_label"), trigger_tf=x.get("trigger_tf"), sig_t=int(x["signal_t"]),
                 mfe=_f(x.get("mfe")), mae=_f(x.get("mae")), open_loc=x.get("open_loc"), feats=x.get("features") or {},
                 htf=x.get("htf_trend"), m15=x.get("m15_trend"), partial_px=_f(x.get("partial_px")),
                 stop_src=x.get("stop_src"))
        risk = float(x.get("risk_pts") or risk)
        exits = []
        for e in x["exits"]:
            mid = any(e["reason"].startswith(s) for s in INTRABAR)
            exits.append({"t": e["t"] + (F.secs // 2 if mid else F.secs), "bar_t": e["t"], "price": e["price"],
                          "reason": e["reason"], "qty": e["qty"], "disp_t": e["t"] if mid else e["t"] + F.secs})
        v["exits"] = exits
        sig_i = F.idx(v["sig_t"]) or (i_fill - 1)
        # sweep bar = the bar in the last 36 that printed the sweep extreme
        lo = max(a, sig_i - 36)
        seg = F.l[lo:sig_i + 1] if d == 1 else F.h[lo:sig_i + 1]
        if v["sweep_px"] is not None:
            m = np.flatnonzero(np.abs(seg - v["sweep_px"]) < 0.01)
            j = lo + int(m[-1]) if len(m) else lo + int(np.argmin(np.abs(seg - v["sweep_px"])))
        else:
            j = lo + (int(np.argmin(seg)) if d == 1 else int(np.argmax(seg)))
        pl = []
        for p_ in v["pools"]:                     # "EQH·ITH" -> "EQH(ITH)"; drop repeats
            p_ = re.sub(r"^(EQ[HL])\W(\w+)$", r"\1(\2)", str(p_))
            if p_ not in pl:
                pl.append(p_)
        v["pools"] = pl
        v["sweep"] = {"t": int(F.t[j]), "price": float(F.l[j] if d == 1 else F.h[j]),
                      "label": "/".join(pl[:3]) if pl else "sweep"}
    else:
        v["est"].append("prices")
        entry = float(F.o[i_fill]) + d * TICK
        rr = f.get("rr_plan")
        v.update(entry=entry, stop0=entry - d * risk, stopf=entry - d * risk,
                 target=(entry + d * rr * risk) if rr else None, target_label="est. rr_plan" if rr else None,
                 pools=[], zone=None, tags=[], qty_label=None, trigger_tf="5m", sig_t=int(t["entry_t"]) - F.secs,
                 mfe=None, mae=_f(t.get("mae")), feats={}, htf=f.get("htf_trend"))
        q = int(t.get("qty") or 1)
        pts = (float(t["pnl"]) + q * 1.50) / (q * 2.0)
        xp = entry + d * pts
        reason = str(t.get("exit") or "")
        mid = any(reason.startswith(s) for s in INTRABAR)
        j_ex = None
        for j in range(i_fill, b):
            if mid and F.l[j] - 0.01 <= xp <= F.h[j] + 0.01:
                j_ex = j
                break
            if not mid and abs(F.c[j] - d * TICK - xp) <= 0.3:
                j_ex = j
                break
        j_ex = j_ex if j_ex is not None else min(b - 1, i_fill + 6)
        v["exits"] = [{"t": int(F.t[j_ex]) + (F.secs // 2 if mid else F.secs), "bar_t": int(F.t[j_ex]), "price": xp,
                       "reason": reason, "qty": q, "disp_t": int(F.t[j_ex]) + (0 if mid else F.secs)}]
        sig_i = max(a, i_fill - 1)
        j, sp, took = _sweep_generic(F, sig_i, d, levels)
        v["sweep"] = {"t": int(F.t[j]), "price": sp, "label": ("/".join(took) if took else "extreme") + " (est.)"}
    v["risk"] = risk
    v["dec_t"] = v["sig_t"] + F.secs          # decision = signal bar close = fill bar open
    v["entry_x_t"] = int(t["entry_t"])        # fill at the open of the entry bar
    # stop path: initial stop until break-even moved it (be_at_r = 1.0 on a 5m close, effective next bar)
    segs = []
    ex_t = v["exits"][-1]["t"]
    if abs(v["stopf"] - v["stop0"]) > 1e-6 and risk > 0:
        mv = None
        i_last = F.at(v["exits"][-1]["bar_t"])
        for j in range(i_fill, i_last):
            fav = (F.h[j] - v["entry"]) if d == 1 else (v["entry"] - F.l[j])
            if fav / risk >= 1.0:
                mv = int(F.t[j]) + F.secs
                break
        if mv is None:
            mv = v["entry_x_t"] + (ex_t - v["entry_x_t"]) // 2
        segs = [(v["entry_x_t"], mv, v["stop0"], "stop"), (mv, ex_t, v["stopf"], "be")]
    else:
        segs = [(v["entry_x_t"], ex_t, v["stop0"], "stop")]
    v["stop_segs"] = segs
    # trigger zone (the engine's own IFVG / CISD zone)
    v["zones"] = []
    if v.get("zone"):
        zl, zh = sorted(v["zone"])
        v["zones"].append({"lo": zl, "hi": zh, "t0": v["sweep"]["t"], "trigger": True,
                           "label": f"trigger {v['trigger']} zone {zl:,.2f}-{zh:,.2f}"})
    v["setup"] = f"{v['trigger']} {'long' if d == 1 else 'short'}" + (f" (grade {v['grade']})" if v.get("grade") else "")
    return v


def atm_detail(F, i, d, info, stop, v_bars=8, k=2, lookback=48, x_ret=0.5):
    """Rebuild the ATM setup at signal bar i (ATM_RULES.md R2-R5) in direction space (shorts mirrored)."""
    o, h, l, c = F.o, F.h, F.l, F.c
    if d == 1:
        O, H, L, C, piv = o, h, l, c, F.psh
    else:
        O, H, L, C, piv = -o, -l, -h, -c, F.psl
    RH, RL = float(info["atm_h"]), float(info["atm_l"])
    lvl = RL if d == 1 else -RH
    day = F.days[int(np.searchsorted(F.starts, i, side="right")) - 1]
    _, a, b = F.bounds(day)
    iopen = a + int(np.argmax((F.mod[a:b] >= 570) & (F.mod[a:b] < 1080)))
    sw = None
    for j in range(iopen, i + 1):
        if L[j] <= lvl - TICK:
            sw = j
            break
    if sw is None:
        return None
    # extreme: the bar whose low anchors the stop (stop = low[e] - max(2 ticks, 0.1 ATR14[i]))
    buf = max(2 * TICK, 0.1 * float(F.atr[i]))
    anchor = (stop + buf) if d == 1 else -(stop - buf)
    lo = max(sw, i - v_bars)
    cand = [j for j in range(lo, i + 1) if abs(L[j] - anchor) < 0.02]
    e = cand[0] if cand else lo + int(np.argmin(L[lo:i + 1]))
    lo2 = max(0, e - lookback)
    pv = np.flatnonzero(piv[lo2:e]) + lo2
    pv = pv[pv + k <= i]
    org = int(pv[-1]) if len(pv) else (lo2 + int(np.argmax(H[lo2:e])) if e > lo2 else e)
    leg = float(H[org] - L[e])
    thr = float(L[e] + x_ret * leg)
    gaps = []
    for k3 in range(org + 2, e + 1):
        top, bot = L[k3 - 2], H[k3]
        if top - bot < TICK - 1e-9:
            continue
        if k3 + 1 < e and C[k3 + 1:e].max() > top:
            continue
        j0 = max(e, k3 + 1)
        if j0 > i:
            continue
        hit = np.flatnonzero(C[j0:i + 1] > top)
        if not len(hit):
            continue
        jb = j0 + int(hit[0])
        lo_r, hi_r = (float(bot), float(top)) if d == 1 else (float(-top), float(-bot))
        gaps.append({"size": float(top - bot), "lo": lo_r, "hi": hi_r, "k1": k3 - 2, "k3": k3, "inv": jb})
    rec = next((j for j in range(e, i + 1) if C[j] > lvl), None)
    disp = [j for j in range(e, i + 1) if C[j] - O[j] > 0 and (C[j] - O[j] >= float(F.atr[j]) or
                                                               (H[j] - L[j] > 0 and C[j] - O[j] >= 0.6 * (H[j] - L[j])))]
    best = max(gaps, key=lambda g: g["size"]) if gaps else None
    real = lambda arr_d, j: float(arr_d[j]) if d == 1 else float(-arr_d[j])
    for g in gaps:                                       # times for drawing on any frame
        g["t1"], g["inv_t"], g["tf"] = int(F.t[g["k1"]]), int(F.t[g["inv"]]), F.tf
    return {"sweep_t": int(F.t[sw]), "e_t": int(F.t[e]), "org_t": int(F.t[org]), "secs": F.secs, "leg": leg,
            "half": thr if d == 1 else -thr, "gaps": gaps, "best": best, "rec": rec, "disp": disp,
            "ext_px": real(L, e), "org_px": real(H, org), "sweep_px": real(L, sw), "RH": RH, "RL": RL, "src": "rebuilt"}


def atm_detail_info(F, d, info):
    """ATM setup geometry straight from the trade record (1m ladder files carry sweep / extreme / leg / IFVG times)."""
    sw_t = int(info["sweep_t"])
    j = F.idx(sw_t)
    j = F.at(sw_t) if j is None else j
    sweep_px = float(F.l[j] if d == 1 else F.h[j])
    ttf = int(info.get("trigger_tf") or info.get("tf") or F.tf)
    best = None
    if info.get("ifvg_lo") is not None:
        best = {"size": float(info.get("ifvg_pts") or (info["ifvg_hi"] - info["ifvg_lo"])), "lo": float(info["ifvg_lo"]),
                "hi": float(info["ifvg_hi"]), "t1": int(info.get("ifvg_c1_t") or info["ext_t"]),
                "inv_t": int(info.get("ifvg_inv_t") or info["ext_t"]), "tf": ttf}
    leg = float(info.get("leg_pts") or abs(info["leg_origin_px"] - info["ext_px"]))
    ext = float(info["ext_px"])
    return {"sweep_t": sw_t, "e_t": int(info["ext_t"]), "org_t": int(info["leg_origin_t"]), "secs": 60 * ttf, "leg": leg,
            "half": ext + d * 0.5 * leg, "gaps": [best] if best else [], "best": best, "ext_px": ext,
            "org_px": float(info["leg_origin_px"]), "sweep_px": sweep_px, "RH": float(info["atm_h"]),
            "RL": float(info["atm_l"]), "src": "record", "ttf": ttf}


def lab_view(t, F, kind):
    d = int(t["dir"])
    tfs = F.secs
    dec_t = int(t["entry_t"])
    i = F.idx(dec_t - tfs)
    if i is None:
        i = F.at(dec_t - tfs)
    k, a, b = F.bounds(t["day"])
    levels = day_levels(F, k)
    v = {"kind": kind, "est": [], "dir": d, "day": t["day"], "entry_t": dec_t, "r": _f(t.get("r")), "pnl": _f(t.get("pnl")),
         "qty": t.get("qty"), "entry": float(t["entry"]), "stop0": float(t["stop"]), "stopf": float(t["stop"]),
         "target": _f(t.get("target")), "target_label": None, "risk": float(t.get("risk_pts") or abs(t["entry"] - t["stop"])),
         "dec_t": dec_t, "entry_x_t": dec_t, "sig_t": dec_t - tfs, "tags": [], "zones": [], "setup": t.get("setup") or kind,
         "grade": t.get("tier") or t.get("grade"), "qty_label": None, "trigger": t.get("setup")}
    ek = str(t.get("exit_kind") or "")
    ex_t = int(t.get("exit_t") or dec_t)
    mid = ek in ("stop", "target", "be")
    v["exits"] = [{"t": ex_t - (tfs // 2 if mid else 0), "bar_t": ex_t - tfs, "price": float(t["exit"]), "reason": ek,
                   "qty": t.get("qty"), "disp_t": ex_t - tfs if mid else ex_t}]
    v["stop_segs"] = [(dec_t, v["exits"][-1]["t"], v["stop0"], "stop")]
    if kind == "atm":
        info = t["info"]
        tfm = int(info.get("tf") or 5)
        ttf = int(info.get("trigger_tf") or t.get("trigger_tf") or tfm)
        v["setup"] = (f"ATM {'low' if d == 1 else 'high'}-sweep {'long' if d == 1 else 'short'}"
                      + (f" (tier {t.get('tier')}, {t.get('score')}/8)" if t.get("tier") else "")
                      + (f" [{ttf}m trigger]" if tfm < 5 else ""))
        v["target_label"] = f"ATM {'H' if d == 1 else 'L'}" + (f" = {info['tgt_pool']}" if info.get("tgt_pool") else "")
        try:
            det = atm_detail_info(F, d, info) if info.get("sweep_t") else atm_detail(F, i, d, info, float(t["stop"]))
        except Exception as ex_:
            print("   atm detail failed:", ex_)
            det = None
        v["atm"] = det
        if det is not None:
            v["sweep"] = {"t": det["sweep_t"], "price": det["sweep_px"], "label": f"ATM {'low' if d == 1 else 'high'} swept",
                          "secs": F.secs}
            for g in det["gaps"]:
                isb = g is det["best"]
                v["zones"].append({"lo": g["lo"], "hi": g["hi"], "t0": g["t1"], "trigger": isb, "tf": g.get("tf"),
                                   "label": (f"{g.get('tf', F.tf)}m IFVG {g['size']:.2f} pts, inverted "
                                             f"{hm(g['inv_t'] + 60 * int(g.get('tf') or F.tf))}" if isb else "leg FVG (inverted)")})
        else:
            v["est"].append("sweep")
        if t.get("first"):
            fp = t["first"]
            v["first"] = (float(fp[0]), str(fp[1])) if isinstance(fp, (list, tuple)) else None
    else:
        j, sp, took = _sweep_generic(F, i, d, levels)
        v["sweep"] = {"t": int(F.t[j]), "price": sp, "label": ("/".join(took) if took else "extreme") + " (est.)"}
        v["est"].append("sweep")
    return v


# ------------------------------------------------------------------------------------------------ panel text
def panel_lines(v, t, thoughts):
    d = v["dir"]
    side = "LONG" if d == 1 else "SHORT"
    L = []                                     # (style, text): h = heading, b = body, m = muted, g/r = good/bad
    if v["kind"] == "engine":
        tf = v.get("trigger_tf") or "5m"
        L.append(("h", f"SETUP  {v['trigger']} {side} ({tf} trigger)" + (f", grade {v['grade']}" if v.get("grade") else "")))
        pools = ", ".join(f"{p} ({POOL_NAMES.get(p, p)})" for p in v.get("pools") or []) or v["sweep"]["label"]
        side_liq = "sell-side" if d == 1 else "buy-side"
        L.append(("b", f"1) Sweep: {side_liq} raid of {pools}, extreme {px(v['sweep']['price'])} at {hm(v['sweep']['t'])}."))
        if v.get("zone"):
            zl, zh = sorted(v["zone"])
            L.append(("b", f"2) Trigger: {v['trigger']} zone {zl:,.2f}-{zh:,.2f}; signal bar closed {hm(v['dec_t'])}."))
        else:
            L.append(("b", f"2) Trigger: {v['trigger']}; signal bar closed {hm(v['dec_t'])}."))
        tl = v.get("target_label") or ""
        rr = abs((v["target"] - v["entry"]) / v["risk"]) if v.get("target") and v["risk"] else None
        L.append(("b", f"3) Entry {hm(v['entry_x_t'])} open {px(v['entry'])}, stop {px(v['stop0'])} ({v['risk']:.1f} pts)"
                       + (f", target {px(v['target'])} {tl} ({rr:.2f}R)" if rr else "") + "."))
        ctx = []
        f = v.get("f") or {}
        if v.get("htf") is not None:
            ctx.append(f"1H trend {'up' if v['htf'] == 1 else 'down' if v['htf'] == -1 else 'flat'}")
        if v.get("m15") is not None:
            ctx.append(f"15m {'up' if v['m15'] == 1 else 'down' if v['m15'] == -1 else 'flat'}")
        if v.get("regime"):
            ctx.append(f"regime {v['regime']}")
        if f.get("x_with_day") is not None:
            ctx.append("with the day" if f.get("x_with_day") else "against the day")
        if v.get("open_loc"):
            ctx.append(f"open {v['open_loc']} value")
        if ctx:
            L.append(("m", "Context: " + ", ".join(ctx) + "."))
        if v.get("tags"):
            L.append(("m", "Confluences: " + "; ".join(v["tags"][:9]) + ("; ..." if len(v["tags"]) > 9 else "")))
    elif v["kind"] == "atm":
        info = t["info"]
        L.append(("h", f"SETUP  ATM {'low' if d == 1 else 'high'}-sweep {side}, tier {t.get('tier')} (score {t.get('score')}/8)"))
        det = v.get("atm")
        rh, rl = float(info["atm_h"]), float(info["atm_l"])
        L.append(("b", f"Range 07:00-09:25: H {rh:,.2f} / L {rl:,.2f} ({rh - rl:.0f} pts)."))
        tfs = 60 * int(info.get("tf") or 5)
        if det is not None:
            L.append(("b", f"1) Sweep: ATM {'low' if d == 1 else 'high'} taken at {hm(det['sweep_t'])}; "
                           f"extreme {det['ext_px']:,.2f} at {hm(det['e_t'])}."))
            L.append(("b", f"2) Leg {info.get('leg_pts', det['leg']):.0f} pts from the {hm(det['org_t'])} "
                           f"swing {'high' if d == 1 else 'low'} {det['org_px']:,.2f}; 50% = {det['half']:,.2f}."))
            if info.get("minutes_to_reclaim") is not None:
                L.append(("b", f"3) V: back inside the range {info['minutes_to_reclaim']:.0f} min after the extreme; "
                               f"entry {info.get('minutes_to_entry', 0):.0f} min after it."))
            else:
                L.append(("b", f"3) V: back inside the range {info.get('bars_to_reclaim')} bars after the extreme; "
                               f"50% + displacement by bar {info.get('bars_to_v')}."))
            if det["best"]:
                g = det["best"]
                L.append(("b", f"4) {g.get('tf', 5)}m IFVG {g['lo']:,.2f}-{g['hi']:,.2f} ({info.get('ifvg_pts', g['size']):.2f} "
                               f"pts) closed through at {hm(g['inv_t'] + 60 * int(g.get('tf') or 5))}."))
        L.append(("b", f"5) Entry {hm(v['dec_t'])} close {px(v['entry'])}, stop {px(v['stop0'])} ({v['risk']:.1f} pts), "
                       f"target {v['target_label']} {px(v['target'])} = {t.get('rr_opp')}R."))
        conf = t.get("conf") or {}
        L.append(("m", "Confluences: " + "  ".join(("✓ " if conf.get(kk) else "✗ ") + lab for kk, lab in ATM_CONF)))
        extra = []
        if info.get("n_res") is not None:
            extra.append(f"{info['n_res']} resistance zones in the path")
        if info.get("news"):
            extra.append("news: " + ", ".join(map(str, info["news"])))
        if info.get("gap_big"):
            extra.append("big RTH gap")
        if info.get("nq_ret") is not None and info.get("es_ret") is not None:
            extra.append(f"NQ {info['nq_ret']:+.2f}% vs ES {info['es_ret']:+.2f}% since 09:30")
        if extra:
            L.append(("m", "; ".join(extra) + "."))
    else:
        L.append(("h", f"SETUP  {v['setup']} {side}"))
        L.append(("b", f"Entry {hm(v['dec_t'])} {px(v['entry'])}, stop {px(v['stop0'])} ({v['risk']:.1f} pts), "
                       f"target {px(v.get('target'))}."))
        L.append(("b", f"Sweep (est.): {v['sweep']['label']} at {hm(v['sweep']['t'])}."))
    # exit
    ex = v["exits"][-1]
    reason = ex["reason"]
    why = ENGINE_EXIT.get(reason) or LAB_EXIT.get(reason) or reason
    if v["kind"] == "atm" and reason == "target":
        why = f"Target filled: the opposite side of the ATM range ({px(v['target'])}) traded through."
    if reason == "TARGET" and v.get("target_label"):
        why = f"Target filled at {px(v['target'])} ({v['target_label']})."
    res = "g" if (v["pnl"] or 0) > 0 else "r"
    pts = (ex["price"] - v["entry"]) * d
    L.append(("h", f"EXIT  {reason.upper()} {hm(ex['disp_t'])} at {px(ex['price'])} ({pts:+.1f} pts)"))
    L.append((res, f"{v['r']:+.2f}R  /  ${v['pnl']:+,.2f}  on {_size_label(v.get('qty'), v.get('qty_label'))}."))
    L.append(("b", why))
    if len(v["exits"]) > 1:
        L.append(("m", "Fills: " + "; ".join(f"{e['qty']} @ {px(e['price'])} {e['reason']}" for e in v["exits"])))
    mm = []
    if v.get("mfe") is not None:
        mm.append(f"best +{v['mfe']:.2f}R")
    if v.get("mae") is not None:
        mae = min(v["mae"], 1.0) if reason in ("STOP", "stop") else v["mae"]   # the stop bar's overshoot is not held
        mm.append(f"worst -{mae:.2f}R")
    if mm:
        L.append(("m", "In the trade: " + ", ".join(mm) + "."))
    if v["est"]:
        L.append(("m", "Estimated from bars (no exact record): " + ", ".join(v["est"]) + "."))
    if thoughts:
        L.append(("h", "BOT'S THOUGHTS" + (f" ({thoughts['head']})" if thoughts.get("head") else "")))
        if thoughts.get("bias"):
            L.append(("m", thoughts["bias"] + "."))
        L.append(("t", thoughts["thoughts"]))
        if thoughts.get("brain"):
            L.append(("m", thoughts["brain"]))
    return L


def frame_t(v, j):
    return frame(v.get("tf", 5)).t[j]


# ------------------------------------------------------------------------------------------------ drawing
def _spread(items, ymin, ymax, gap):
    """De-overlap right-margin labels: overlapping labels merge into clusters centred on their mean price, so every
    label stays as close as possible to its own price; clusters are kept inside [ymin, ymax]."""
    items = sorted(items, key=lambda x: x[0])
    cl = [[float(min(max(it[0], ymin), ymax)), [it]] for it in items]     # [centre, members]

    def span(c):
        return (len(c[1]) - 1) * gap / 2.0

    changed = True
    while changed:
        changed = False
        for c in cl:
            c[0] = min(max(c[0], ymin + span(c)), ymax - span(c))
        for k in range(len(cl) - 1):
            a_, b_ = cl[k], cl[k + 1]
            if (b_[0] - span(b_)) - (a_[0] + span(a_)) < gap - 1e-9:
                mem = a_[1] + b_[1]
                ctr = float(np.mean([min(max(m[0], ymin), ymax) for m in mem]))
                cl[k:k + 2] = [[ctr, mem]]
                changed = True
                break
    out = []
    for c in cl:
        y0 = c[0] - span(c)
        for j, m in enumerate(c[1]):
            out.append((y0 + j * gap,) + tuple(m[1:]))
    return out


def _zoom_inset(axz, v, F, X=None):
    """Close-up of the trade (sweep -> exit, at most 40 bars) with entry / stop / target / trigger zone."""
    d = v["dir"]
    i_a = max(0, F.at(v["sweep"]["t"]) - 3)
    i_en = F.at(v["entry_x_t"])
    i_b = F.at(v["exits"][-1]["t"] - 1) + 3
    i_b = min(i_b, i_a + 40, len(F.t) - 1)
    if i_b < i_en + 2:
        i_b = min(len(F.t) - 1, i_en + 6)
    tw = F.t[i_a:i_b + 1]
    n = len(tw)

    def XX(T):
        j = int(np.searchsorted(tw, T, side="right")) - 1
        return -0.5 if j < 0 else j - 0.5 + min(1.0, (T - tw[j]) / F.secs)

    oo, hh, ll, cc = F.o[i_a:i_b + 1], F.h[i_a:i_b + 1], F.l[i_a:i_b + 1], F.c[i_a:i_b + 1]
    lo, hi = min(ll.min(), v["stop0"], v["entry"]), max(hh.max(), v["stop0"], v["entry"])
    r0 = hi - lo
    if v.get("target") is not None and abs(v["target"] - v["entry"]) < 1.6 * max(r0, 1e-9):
        lo, hi = min(lo, v["target"]), max(hi, v["target"])
    pad = 0.05 * (hi - lo)
    axz.set_xlim(-0.8, n - 0.2)
    axz.set_ylim(lo - pad, hi + pad)
    for s in axz.spines.values():
        s.set_color(COL["grid"])
    axz.tick_params(colors=COL["muted"], labelsize=6.5, length=2)
    axz.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:,.0f}"))
    axz.yaxis.tick_right()
    mm = F.mod[i_a:i_b + 1]
    tks = [j for j in range(n) if mm[j] % (15 if F.secs >= 300 else 5) == 0][::2]
    axz.set_xticks(tks)
    axz.set_xticklabels([f"{mm[j] // 60:02d}:{mm[j] % 60:02d}" for j in tks])
    for z in v["zones"]:
        if z.get("trigger"):
            x0 = max(-0.5, XX(z["t0"]))
            axz.add_patch(Rectangle((x0, z["lo"]), max(0.8, XX(v["dec_t"]) - x0), z["hi"] - z["lo"], facecolor=COL["trig"],
                                    alpha=0.3, edgecolor=COL["trig"], lw=0.8, zorder=1))
    up = cc >= oo
    xs = np.arange(n)
    axz.vlines(xs, ll, hh, colors=np.where(up, COL["up"], COL["dn"]), lw=0.8, zorder=3)
    axz.bar(xs, np.maximum(np.abs(cc - oo), 0.002 * (hi - lo)), bottom=np.minimum(oo, cc), width=0.62,
            color=np.where(up, COL["up"], COL["dn"]), lw=0, zorder=3)
    x_en, x_ex = XX(v["entry_x_t"]), XX(v["exits"][-1]["t"])
    x_end = max(x_ex, x_en + 3)
    axz.plot([x_en, x_end], [v["entry"]] * 2, color=COL["entry"], lw=0.9, ls=(0, (2, 2)), zorder=4)
    for (t0_, t1_, p_, sty) in v["stop_segs"]:
        axz.plot([XX(t0_), min(XX(t1_), x_end) if XX(t1_) < x_ex - 1e-9 else x_end], [p_, p_],
                 color=COL["stop"] if sty == "stop" else COL["be"], lw=1.3, zorder=4)
    if v.get("target") is not None and lo - pad <= v["target"] <= hi + pad:
        axz.plot([x_en, x_end], [v["target"]] * 2, color=COL["tgt"], lw=1.3, zorder=4)
    axz.scatter([XX(v["sweep"]["t"] + F.secs // 2)], [v["sweep"]["price"] - d * 0.02 * (hi - lo)], marker="*", s=90,
                color=COL["sweep"], edgecolor="black", linewidths=0.4, zorder=6)
    axz.annotate("", xy=(x_en, v["entry"]), xytext=(x_en - 1.2, v["entry"] - d * 0.12 * (hi - lo)),
                 arrowprops=dict(arrowstyle="-|>", color=COL["long"] if d == 1 else COL["short"], lw=1.6), zorder=7)
    for e in v["exits"]:
        if XX(e["t"]) <= n - 0.5:
            wc = COL["win"] if (v["pnl"] or 0) > 0 else COL["loss"]
            axz.scatter([XX(e["t"])], [e["price"]], marker="X", s=50, color=wc, edgecolor="white", linewidths=0.6, zorder=8)
    axz.set_title(f"close-up {hm(tw[0])}-{hm(tw[-1] + F.secs)} ({F.tf}m)", fontsize=7.5, color=COL["muted"], pad=3)


def draw(v, t, F, out_png, out_thumb, title_name, thoughts, window=None, zoom=False, ext_max=10 ** 6, subtitle=""):
    d = v["dir"]
    k, a, b = F.bounds(v["day"])
    mod = F.mod[a:b]
    ex_t = v["exits"][-1]["t"]
    if window is None:
        win = np.flatnonzero((mod >= WIN[0]) & (mod < WIN[1])) + a
        w0, w1 = int(win[0]), int(win[-1])
    else:
        w0, w1 = window
    i_first = F.at(min(v["sweep"]["t"], v["entry_x_t"]))
    i_last = F.at(ex_t - 1)
    w0, w1 = max(a, min(w0, i_first - 2)), min(b - 1, max(w1, min(i_last + 2, w1 + ext_max)))
    tw = F.t[w0:w1 + 1]
    n = len(tw)
    secs = F.secs

    def X(T):
        j = int(np.searchsorted(tw, T, side="right")) - 1
        if j < 0:
            return -0.5
        return j - 0.5 + min(1.0, (T - tw[j]) / secs)

    oo, hh, ll, cc = F.o[w0:w1 + 1], F.h[w0:w1 + 1], F.l[w0:w1 + 1], F.c[w0:w1 + 1]
    lo, hi = float(ll.min()), float(hh.max())
    rng = hi - lo
    for p_ in (v["entry"], v["stop0"], v["stopf"]):
        lo, hi = min(lo, p_), max(hi, p_)
    if v.get("target") is not None and abs(v["target"] - (hi if d == 1 else lo)) < 0.6 * rng:
        lo, hi = min(lo, v["target"]), max(hi, v["target"])
    levels = day_levels(F, k)
    for nm, sd, lv, av, col in levels:            # pull close levels into view
        if lo - 0.12 * rng <= lv <= hi + 0.12 * rng:
            lo, hi = min(lo, lv), max(hi, lv)
    pad = 0.035 * (hi - lo)
    ylo, yhi = lo - pad, hi + pad
    yr = yhi - ylo

    fig = plt.figure(figsize=(14, 8), dpi=100, facecolor=COL["bg"])
    ax = fig.add_axes([0.05, 0.065, 0.64, 0.855], facecolor=COL["ax"])
    ax.set_xlim(-0.8, n - 0.2)
    ax.set_ylim(ylo, yhi)
    for s in ax.spines.values():
        s.set_color(COL["grid"])
    ax.tick_params(colors=COL["muted"], labelsize=8)
    ax.grid(axis="y", color=COL["grid"], lw=0.6, alpha=0.8)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:,.0f}"))
    step = 30 if secs >= 300 else 15
    wm = F.mod[w0:w1 + 1]
    ticks = [j for j in range(n) if wm[j] % step == 0]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{wm[j] // 60:02d}:{wm[j] % 60:02d}" for j in ticks], fontsize=8)
    for j in ticks:
        if wm[j] % 60 == 0:
            ax.axvline(j - 0.5, color=COL["grid"], lw=0.5, alpha=0.6, zorder=0)
    margin = []                                    # (y, text, color)
    offchart = {"above": [], "below": []}

    # killzones
    for m0, m1, lab in KZ:
        js = np.flatnonzero((wm >= m0) & (wm < m1))
        if len(js):
            ax.axvspan(js[0] - 0.5, js[-1] + 0.5, color=COL["kz"], alpha=0.07, lw=0, zorder=0)
            ax.text((js[0] + js[-1]) / 2, yhi - 0.012 * yr, lab, color=COL["kz"], fontsize=7.5, ha="center", va="top",
                    alpha=0.9, zorder=1)
    # ATM box
    atm_ix = np.flatnonzero((wm >= 420) & (wm < 570))
    atm = {nm: lv for nm, sd, lv, av, col in levels if nm.startswith("ATM")}
    if len(atm_ix) and "ATM H" in atm:
        ax.add_patch(Rectangle((atm_ix[0] - 0.5, atm["ATM L"]), atm_ix[-1] - atm_ix[0] + 1, atm["ATM H"] - atm["ATM L"],
                               facecolor=COL["atm"], alpha=0.07, edgecolor="none", zorder=1))
        ax.add_patch(Rectangle((atm_ix[0] - 0.5, atm["ATM L"]), atm_ix[-1] - atm_ix[0] + 1, atm["ATM H"] - atm["ATM L"],
                               facecolor="none", edgecolor=COL["atm"], lw=1.1, alpha=0.8, zorder=2))
        ax.text(atm_ix[0], atm["ATM H"] + 0.006 * yr, f"ATM range 07:00-09:25 ({atm['ATM H'] - atm['ATM L']:.0f} pts)",
                color=COL["atm"], fontsize=7.5, va="bottom", zorder=6)
    # session levels: solid until taken, faint after
    for nm, sd, lv, av, col in levels:
        x0 = max(-0.5, X(int(F.t[min(av, len(F.t) - 1)])) if av > w0 else -0.5)
        if nm.startswith("ATM"):
            x0 = atm_ix[-1] + 0.5 if len(atm_ix) else x0
        tk = taken_at(F, sd, lv, max(av, a), b)
        x_tk = (tk - w0) if (tk is not None and tk <= w1) else n - 0.5
        if tk is not None and tk < w0:
            x_tk = -0.5
        inside = ylo <= lv <= yhi
        if inside:
            if x_tk > x0:
                ax.plot([x0, x_tk], [lv, lv], color=col, lw=1.0, alpha=0.85, zorder=2,
                        ls="-" if not nm.startswith("ATM") else (0, (5, 3)))
            ax.plot([max(x0, x_tk), n - 0.5], [lv, lv], color=col, lw=0.8, alpha=0.3, ls=":", zorder=2)
            if tk is not None and w0 <= tk <= w1:
                ax.plot([x_tk], [lv], marker="x", color=col, ms=5, mew=1.2, zorder=6)
            margin.append((lv, f"{nm} {lv:,.2f}" + (" (hit)" if tk is not None and tk <= F.at(v["dec_t"] - 1) else ""), col))
        else:
            offchart["above" if lv > yhi else "below"].append((abs(lv - (yhi if lv > yhi else ylo)),
                                                               f"{'↑' if lv > yhi else '↓'} {nm} {lv:,.2f}", col))
    # FVG / IFVG zones near the entry, live at the decision bar (causal on this frame)
    i_dec = F.at(v["dec_t"] - 1)
    atr = float(F.atr[i_dec])
    band = max(1.5 * v["risk"], 2.0 * atr)
    ctx = live_fvgs(F, max(a, w0, i_dec - (72 if secs >= 300 else 150)), i_dec, max(3.0 if secs >= 300 else 1.5, 0.1 * atr))
    trig = [z for z in v["zones"] if z.get("trigger")]

    def overl(z, y):
        inter = min(z["hi"], y["hi"]) - max(z["lo"], y["lo"])
        return inter > 0.5 * min(z["hi"] - z["lo"], y["hi"] - y["lo"])

    near = []
    for z in ctx:
        if z["hi"] < v["entry"] - band or z["lo"] > v["entry"] + band:
            continue
        if any(overl(z, y) for y in v["zones"]):
            continue
        dist = 0.0 if z["lo"] <= v["entry"] <= z["hi"] else min(abs(z["lo"] - v["entry"]), abs(z["hi"] - v["entry"]))
        near.append((0 if z["state"] == "ifvg" else 1, dist, z))
    near.sort(key=lambda q: (q[0], q[1]))
    x_dec = X(v["dec_t"])
    x_ex = X(ex_t)
    placed = []
    for _, _, z in near[:4]:
        if z["state"] == "ifvg":
            col, lab = COL["ifvg"], ("bull IFVG" if z["pol"] == 1 else "bear IFVG")
        else:
            col, lab = (COL["fvg_up"], "bull FVG") if z["pol"] == 1 else (COL["fvg_dn"], "bear FVG")
        x0 = X(z["t0"])
        ax.add_patch(Rectangle((x0, z["lo"]), x_dec - x0, z["hi"] - z["lo"], facecolor=col, alpha=0.2, edgecolor=col,
                               lw=0.6, zorder=1, hatch="///" if z["state"] == "ifvg" else None))
        ax.add_patch(Rectangle((x_dec, z["lo"]), max(0.5, x_ex - x_dec), z["hi"] - z["lo"], facecolor=col, alpha=0.06,
                               edgecolor="none", zorder=1))
        if all(abs(z["hi"] - py) > 0.025 * yr or abs(x0 - pxx) > 12 for pxx, py in placed):
            ax.text(x0 + 0.2, z["hi"], lab, color=col, fontsize=6.5, va="bottom", ha="left", zorder=6, alpha=0.95)
            placed.append((x0, z["hi"]))
    for z in v["zones"]:
        col = COL["trig"] if z.get("trigger") else COL["ifvg"]
        x0 = X(z["t0"])
        ax.add_patch(Rectangle((x0, z["lo"]), max(0.8, x_dec - x0), z["hi"] - z["lo"], facecolor=col,
                               alpha=0.28 if z.get("trigger") else 0.14, edgecolor=col, lw=1.2 if z.get("trigger") else 0.6,
                               zorder=2, hatch="\\\\\\" if z.get("trigger") else "///"))
        ax.add_patch(Rectangle((x_dec, z["lo"]), max(0.5, x_ex - x_dec), z["hi"] - z["lo"], facecolor=col, alpha=0.07,
                               edgecolor="none", zorder=1))
        if z.get("trigger"):
            nm_ = (f"{z['tf']}m IFVG" if z.get("tf") else "IFVG") if v["kind"] == "atm" else f"{v.get('trigger') or ''} zone"
            margin.append(((z["lo"] + z["hi"]) / 2, f"{nm_} {z['lo']:,.0f}-{z['hi']:,.0f}", col))
    # candles
    xs = np.arange(n)
    up = cc >= oo
    ax.vlines(xs, ll, hh, colors=np.where(up, COL["up"], COL["dn"]), lw=0.9, zorder=3)
    body = np.maximum(np.abs(cc - oo), 0.0015 * yr)
    ax.bar(xs, body, bottom=np.minimum(oo, cc), width=0.62, color=np.where(up, COL["up"], COL["dn"]), lw=0, zorder=3)
    # trade span + lines
    win_col = COL["win"] if (v["pnl"] or 0) > 0 else (COL["loss"] if (v["pnl"] or 0) < 0 else COL["flat"])
    x_en = X(v["entry_x_t"])
    x_end = max(x_ex, x_en + max(4.0, 0.03 * n))   # short trades: keep the trade lines readable
    ax.axvspan(x_en, x_ex, color=win_col, alpha=0.06, lw=0, zorder=0)
    ax.plot([x_en, x_end], [v["entry"], v["entry"]], color=COL["entry"], lw=0.9, ls=(0, (2, 2)), alpha=0.8, zorder=4)
    for (t0_, t1_, p_, sty) in v["stop_segs"]:
        x1_ = X(t1_) if X(t1_) < x_ex - 1e-9 else x_end
        ax.plot([X(t0_), x1_], [p_, p_], color=COL["stop"] if sty == "stop" else COL["be"], lw=1.6,
                ls=(0, (6, 3)) if sty == "stop" else (0, (2, 2)), zorder=4)
    ax.plot([x_end, n - 0.5], [v["stop0"], v["stop0"]], color=COL["stop"], lw=0.7, alpha=0.3, ls=":", zorder=4)
    margin.append((v["stop0"], f"STOP {v['stop0']:,.2f}", COL["stop"]))
    if abs(v["stopf"] - v["stop0"]) > 1e-6:
        margin.append((v["stopf"], f"BE stop {v['stopf']:,.2f}", COL["be"]))
    margin.append((v["entry"], f"ENTRY {v['entry']:,.2f}", COL["entry"]))
    if v.get("target") is not None:
        tg = v["target"]
        if ylo <= tg <= yhi:
            ax.plot([x_en, x_end], [tg, tg], color=COL["tgt"], lw=1.6, ls=(0, (6, 3)), zorder=4)
            ax.plot([x_end, n - 0.5], [tg, tg], color=COL["tgt"], lw=0.7, alpha=0.3, ls=":", zorder=4)
            margin.append((tg, f"TARGET {tg:,.2f}", COL["tgt"]))
        else:
            offchart["above" if tg > yhi else "below"].append((-1.0, f"{'↑' if tg > yhi else '↓'} TARGET {tg:,.2f}",
                                                               COL["tgt"]))
    if v.get("first"):
        fp, fn = v["first"]
        if ylo <= fp <= yhi:
            ax.plot([x_en, x_ex], [fp, fp], color=COL["tgt"], lw=0.9, ls=":", alpha=0.7, zorder=4)
            margin.append((fp, f"1st pool {fn} {fp:,.2f}", COL["tgt"]))
    # entry arrow
    ecol = COL["long"] if d == 1 else COL["short"]
    ax.annotate("", xy=(x_en, v["entry"]), xytext=(-16, -d * 40), textcoords="offset points",
                arrowprops=dict(arrowstyle="-|>", color=ecol, lw=2.2, mutation_scale=16), zorder=8)
    ax.annotate(f"{'BUY' if d == 1 else 'SELL'} {hm(v['entry_x_t'])}", xy=(x_en, v["entry"]), xytext=(-18, -d * 42),
                textcoords="offset points", color=ecol, fontsize=8.5, weight="bold", ha="right",
                va="top" if d == 1 else "bottom", zorder=8,
                bbox=dict(facecolor=COL["bg"], edgecolor=ecol, alpha=0.85, pad=1.5, lw=0.8))
    # exit marker(s)
    for e in v["exits"]:
        xe = X(e["t"])
        ax.scatter([xe], [e["price"]], marker="X", s=95, color=win_col, edgecolor="white", linewidths=0.8, zorder=9)
    ex = v["exits"][-1]
    fy = (ex["price"] - ylo) / yr                  # keep the label inside the chart
    up_txt = fy < 0.8 if fy < 0.2 or fy > 0.8 else ((ex["price"] >= v["entry"]) if d == 1 else (ex["price"] < v["entry"]))
    ax.annotate(f"EXIT {ex['reason']} {hm(ex['disp_t'])}\n{v['r']:+.2f}R  ${v['pnl']:+,.0f}", xy=(X(ex["t"]), ex["price"]),
                xytext=(14 if X(ex["t"]) < 0.85 * n else -90, 18 if up_txt else -30), textcoords="offset points",
                color=win_col, fontsize=8, weight="bold",
                zorder=9, bbox=dict(facecolor=COL["bg"], edgecolor=win_col, alpha=0.88, pad=2, lw=0.8),
                arrowprops=dict(arrowstyle="-", color=win_col, lw=0.8))
    # sweep marker
    sw = v["sweep"]
    xs_ = X(sw["t"] + secs // 2)
    ys_ = sw["price"] - d * 0.012 * yr
    ax.scatter([xs_], [ys_], marker="*", s=230, color=COL["sweep"], edgecolor="black", linewidths=0.6, zorder=9)
    fy = (ys_ - ylo) / yr
    below = (d == 1 and fy > 0.12) or (d == -1 and fy > 0.85)
    ax.annotate(f"SWEEP {sw['label']}\n{sw['price']:,.2f} @ {hm(sw['t'])}", xy=(xs_, ys_),
                xytext=(-10, -32 if below else 22), textcoords="offset points", color=COL["sweep"], fontsize=7.5,
                ha="right", zorder=9, bbox=dict(facecolor=COL["bg"], edgecolor=COL["sweep"], alpha=0.85, pad=1.5, lw=0.7),
                arrowprops=dict(arrowstyle="-", color=COL["sweep"], lw=0.7))
    # ATM extras: extreme, leg origin, 50% line
    det = v.get("atm")
    if det is not None:
        te, to, hs = det["e_t"], det["org_t"], 30 if secs < 300 else 150
        if abs(te - det["sweep_t"]) >= secs:
            ax.scatter([X(te + hs)], [det["ext_px"] - d * 0.012 * yr], marker="^" if d == 1 else "v", s=60,
                       color=COL["sweep"], zorder=9)
            ax.text(X(te + hs), det["ext_px"] - d * 0.03 * yr, f"extreme {hm(te)}", color=COL["sweep"], fontsize=7,
                    ha="center", va="top" if d == 1 else "bottom", zorder=9)
        ax.scatter([X(to + hs)], [det["org_px"] + d * 0.012 * yr], marker="D", s=30, color=COL["muted"], zorder=9)
        ax.text(X(to + hs), det["org_px"] + d * 0.03 * yr, "leg origin", color=COL["muted"], fontsize=7,
                ha="center", va="bottom" if d == 1 else "top", zorder=9)
        ax.plot([X(to), x_dec], [det["half"], det["half"]], color=COL["muted"], lw=0.8, ls=(0, (1, 2)), zorder=4)
        ax.text(x_dec + 0.3, det["half"], "50% of leg", color=COL["muted"], fontsize=6.5, va="center", zorder=6)
        b_ = det.get("best")
        if b_ is not None:                         # where the body closed through the gap (trigger-frame bar close)
            xi = X(b_["inv_t"] + 60 * int(b_.get("tf") or 5) - 1)
            ax.plot([xi], [b_["hi"] if d == 1 else b_["lo"]], marker="o", ms=5, mfc="none", mec=COL["trig"], mew=1.2, zorder=9)
    # levels beyond the chart: stacked above / below the price ladder, nearest first
    for side_, y0_, sgn, va in (("above", 0.924, 1, "bottom"), ("below", 0.056, -1, "top")):
        for j, (_, txt, col) in enumerate(sorted(offchart[side_])[:5]):
            fig.text(0.693, y0_ + sgn * j * 0.0135, txt, color=col, fontsize=7, va=va, ha="left", alpha=0.9)
    # right-margin price ladder
    gap = 0.03 * yr
    for y, txt, col in _spread([(y, t_, c_) for y, t_, c_ in margin], ylo + 0.01 * yr, yhi - 0.01 * yr, gap):
        ax.annotate(txt, xy=(1.004, y), xycoords=("axes fraction", "data"), fontsize=7.2, color=col, va="center",
                    ha="left", annotation_clip=False,
                    bbox=dict(facecolor=COL["bg"], edgecolor=col, alpha=0.9, pad=1.2, lw=0.6))
    # title
    side = "LONG" if d == 1 else "SHORT"
    wd = DOW[dt.date.fromisoformat(v["day"]).weekday()]
    size = _size_label(v.get("qty"), v.get("qty_label"))
    tfn = f"{F.tf}m"
    fig.text(0.05, 0.962, f"{title_name}  |  {v['day']} ({wd}) {hm(v['entry_x_t'])} ET  |  {side}  |  {v['setup']}",
             fontsize=13.5, weight="bold", color=COL["text"])
    fig.text(0.05, 0.931, f"{v['r']:+.2f}R    ${v['pnl']:+,.2f}    {size}    exit {ex['reason']} {hm(ex['disp_t'])}"
             + (f"    [{', '.join(v['est'])} estimated]" if v["est"] else ""), fontsize=11.5, weight="bold", color=win_col)
    fig.text(0.69, 0.931, f"NQ1! {tfn} bars (TradingView CME futures){'  ' + subtitle if subtitle else ''}", fontsize=8,
             color=COL["muted"], ha="right")
    # panel
    axp = fig.add_axes([0.785, 0.065, 0.205, 0.855])
    axp.set_xlim(0, 1)
    axp.set_ylim(0, 1)
    axp.axis("off")
    axp.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.02", facecolor=COL["panel"],
                                 edgecolor=COL["grid"], lw=0.8, transform=axp.transAxes, zorder=0))
    y = 0.975
    lh = 0.0215
    for sty, txt in panel_lines(v, t, thoughts):
        if sty == "h":
            y -= 0.008
            for ln in textwrap.wrap(txt, 40):
                if y < 0.03:
                    break
                axp.text(0.04, y, ln, fontsize=8.8, weight="bold", color=COL["atm"], va="top", zorder=2)
                y -= lh * 1.08
            continue
        col = {"b": COL["text"], "m": COL["muted"], "g": COL["win"], "r": COL["loss"], "t": "#e7f5ff"}[sty]
        width = 47 if sty != "t" else 46
        for ln in textwrap.wrap(txt, width):
            if y < 0.03:
                axp.text(0.04, 0.012, "...", fontsize=8, color=COL["muted"], va="bottom")
                break
            axp.text(0.04, y, ln, fontsize=8.1, color=col, va="top", zorder=2,
                     style="italic" if sty == "t" else "normal", weight="bold" if sty in ("g", "r") else "normal")
            y -= lh
    if y > 0.30 and not zoom:                     # room left in the panel: close-up of the trade on the same frame
        hgt = min(y - 0.07, 0.40)
        axz = fig.add_axes([0.797, 0.065 + 0.855 * 0.035, 0.152, 0.855 * hgt], facecolor=COL["ax"])
        _zoom_inset(axz, v, F, X=None)
    fig.savefig(out_png, dpi=100, facecolor=COL["bg"])
    fig.savefig(out_thumb, dpi=40, facecolor=COL["bg"], pil_kwargs={"quality": 80})
    plt.close(fig)


# ------------------------------------------------------------------------------------------------ index page
def _stats(trades):
    r = [float(t.get("r") or 0) for t in trades]
    p = [float(t.get("pnl") or 0) for t in trades]
    if not r:
        return {}
    return {"n": len(r), "win": round(100 * sum(x > 0 for x in p) / len(p), 1), "avg_r": round(float(np.mean(r)), 3),
            "net": round(sum(p), 2), "first": min(t["day"] for t in trades), "last": max(t["day"] for t in trades)}


CSS = """
:root{--bg:#0d1117;--card:#151b24;--line:#232b37;--text:#d9dee7;--muted:#8b95a7;--win:#51cf66;--loss:#ff6b6b;--gold:#f2c94c}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
header,section{max-width:1500px;margin:0 auto;padding:16px}
h1{font-size:22px;margin:4px 0 6px}h2{font-size:19px;margin:22px 0 4px;color:var(--gold)}
h3{font-size:15px;margin:16px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
p{margin:6px 0}.muted{color:var(--muted)}a{color:#74c0fc}code{word-break:break-word;color:#c5d6e8}
nav a{display:inline-block;margin:4px 10px 4px 0;padding:6px 10px;border:1px solid var(--line);border-radius:8px;text-decoration:none}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.card{margin:0;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.card.win{border-left:4px solid var(--win)}.card.loss{border-left:4px solid var(--loss)}
.card img{display:block;width:100%;height:auto;background:#000}
figcaption{padding:8px 10px 10px;font-size:14px}
.r.win{color:var(--win);font-weight:700}.r.loss{color:var(--loss);font-weight:700}
.th{margin-top:6px;font-style:italic;color:#c5d6e8;font-size:13px}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:13px;color:var(--muted)}
.legend span:before{content:"";display:inline-block;width:14px;height:10px;margin-right:6px;vertical-align:middle;background:var(--c);border-radius:2px}
.stats{font-size:14px;color:var(--muted)}
@media (max-width:640px){header,section{padding:12px 16px}.grid{grid-template-columns:1fr}h1{font-size:20px}}
"""

LEGEND = [("#f2c94c", "ATM range 07:00-09:25 (box) and its H/L"), ("#b197fc", "prior-day high/low"),
          ("#4dabf7", "Asia high/low (20:00-24:00)"), ("#ffa94d", "London high/low (02:00-05:00)"),
          ("#5c7cfa", "NY killzones 09:30-11:30, 13:30-15:30"), ("#ffd43b", "sweep star / trigger zone"),
          ("#20c997", "bull FVG (live)"), ("#ff6b6b", "bear FVG (live) / stop"), ("#e64980", "IFVG (inverted FVG)"),
          ("#51cf66", "target"), ("#ffa94d", "break-even stop")]


def build_index():
    mans = []
    for f in glob.glob(os.path.join(GAL, "_manifest_*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                mans.append(json.load(fh))
        except Exception:
            pass
    mans.sort(key=lambda m: (m.get("priority", 1), m.get("name", "")))
    e = html.escape
    H = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>",
         "<meta name='viewport' content='width=device-width,initial-scale=1'>",
         "<title>Trade gallery</title><style>" + CSS + "</style></head><body><header>",
         "<h1>Trade gallery: the bot's trades as a trader sees them</h1>",
         f"<p class='muted'>NQ1! CME futures (TradingView data), 06:30-15:55 ET. Built "
         f"{dt.datetime.now(ET).strftime('%Y-%m-%d %H:%M')} ET by <code>tools/trade_gallery.py</code>. "
         "Tap a chart for the full 1400x800 image.</p>",
         "<div class='legend'>" + "".join(f"<span style='--c:{c}'>{e(t)}</span>" for c, t in LEGEND) + "</div>",
         "<p class='muted'>Green arrow = buy, red arrow = sell, X = exit. A level line turns faint once price trades "
         "through it. FVG/IFVG boxes are the ones still live at the decision bar (closed bars only), near the entry. "
         "\"est.\" marks values rebuilt from bars because the trade record did not carry them.</p><nav>"]
    for m in mans:
        H.append(f"<a href='#{e(m['name'])}'>{e(m['title'])} ({len(m['items'])})</a>")
    H.append("</nav></header>")
    for m in mans:
        s = m.get("stats") or {}
        H.append(f"<section id='{e(m['name'])}'><h2>{e(m['title'])}</h2>")
        H.append(f"<p class='stats'>Source <code>{e(m['source'])}</code>{(' key ' + e(m['key'])) if m.get('key') else ''}: "
                 f"{s.get('n', 0)} trades {s.get('first', '')}..{s.get('last', '')}, win {s.get('win', 0)}%, "
                 f"avg {s.get('avg_r', 0):+.3f}R, net ${s.get('net', 0):+,.0f}. Rendered {len(m['items'])} "
                 f"({e(m.get('rule', ''))}).</p>")
        if m.get("note"):
            H.append(f"<p class='muted'>{e(m['note'])}</p>")
        groups = [("all", "All trades"), ("best", "Best (by R)"), ("worst", "Worst (by R)"), ("random", "Random")]
        for g, gl in groups:
            items = [it for it in m["items"] if it["group"] == g]
            if not items:
                continue
            H.append(f"<h3>{gl} ({len(items)})</h3><div class='grid'>")
            for it in items:
                cls = "win" if it["pnl"] > 0 else "loss"
                zoom = f" &middot; <a href='{e(it['zoom'])}'>5m full day</a>" if it.get("zoom") else ""
                th = (f"<div class='th'>{('<b>Brain ' + e(it['brain_head']) + ':</b> ') if it.get('brain_head') else ''}"
                      f"{e(it['thoughts'][:260])}{'...' if len(it['thoughts']) > 260 else ''}</div>") \
                    if it.get("thoughts") else ""
                H.append(
                    f"<figure class='card {cls}'><a href='{e(it['file'])}'><img src='{e(it['thumb'])}' loading='lazy' "
                    f"width='560' height='320' alt='{e(it['alt'])}'></a><figcaption><b>{e(it['day'])} {e(it['hhmm'])} ET "
                    f"&middot; {e(it['side'])}</b> <span class='r {cls}'>{it['r']:+.2f}R &middot; ${it['pnl']:+,.0f}</span><br>"
                    f"{e(it['setup'])} &middot; {e(it['size'])}<br><span class='muted'>exit: {e(it['exit'])}"
                    f"{(' &middot; ' + e(it['est'])) if it.get('est') else ''}</span>{zoom}{th}</figcaption></figure>")
            H.append("</div>")
        H.append("</section>")
    H.append("</body></html>")
    with open(os.path.join(GAL, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(H))
    return os.path.join(GAL, "index.html")


# ------------------------------------------------------------------------------------------------ main
def render_list(path, key, name, n, all_=False, seed=7, title=None, replay=True, thoughts_file=None, note=None,
                tf=None, clean=True):
    trades, meta = load_trades(path, key)
    os.makedirs(os.path.join(GAL, "thumbs"), exist_ok=True)
    if clean:
        for f in glob.glob(os.path.join(GAL, f"{name}_20*.png")) + glob.glob(os.path.join(GAL, "thumbs", f"{name}_20*.jpg")):
            os.remove(f)
    sel = select(trades, n, all_, seed)
    TH = load_thoughts(thoughts_file)
    params = meta.get("params") or {}
    items, t0 = [], time.time()
    for g, t in sel:
        kind = kind_of(t)
        ttf = int(tf or ((t.get("info") or {}).get("tf") or 5))
        hhmm = dt.datetime.fromtimestamp(int(t["entry_t"]), ET).strftime("%H%M")
        base = f"{name}_{t['day']}_{hhmm}"
        try:
            if kind == "engine":
                F = frame(5)
                v = engine_view(t, F, params, replay)
                v["tf"] = 5
            else:
                Ft = frame(ttf) if frame_has_day(ttf, t["day"]) else None
                if Ft is None:
                    print(f"  {t['day']}: no {ttf}m bars for this day; skipped")
                    continue
                v = lab_view(t, Ft, kind)
                v["tf"] = ttf
            th = thought_for(t, TH, kind)
            F5 = frame(5)
            png, thumb = os.path.join(GAL, base + ".png"), os.path.join(GAL, "thumbs", base + ".jpg")
            zoom = None
            if v["tf"] < 5:              # 1m trade: main image on its own bars 07:00-12:00, plus the 5m full day
                Ft = frame(v["tf"])
                k_, a_, b_ = Ft.bounds(t["day"])
                mm = Ft.mod[a_:b_]
                ix = np.flatnonzero((mm >= 420) & (mm < 720)) + a_
                draw(v, t, Ft, png, thumb, name, th, window=(int(ix[0]), int(ix[-1])), zoom=True, ext_max=30,
                     subtitle="07:00-12:00 detail")
                zp = os.path.join(GAL, base + "_day.png")
                draw(v, t, F5, zp, os.path.join(GAL, "thumbs", base + "_day.jpg"), name, th,
                     subtitle=f"full day; trade found on {v['tf']}m bars")
                zoom = os.path.basename(zp)
            else:
                draw(v, t, F5, png, thumb, name, th)
            ex = v["exits"][-1]
            items.append({"file": base + ".png", "thumb": "thumbs/" + base + ".jpg", "group": g, "day": t["day"],
                          "hhmm": f"{hhmm[:2]}:{hhmm[2:]}", "side": "LONG" if v["dir"] == 1 else "SHORT",
                          "r": float(t.get("r") or 0), "pnl": float(t.get("pnl") or 0), "setup": v["setup"],
                          "size": _size_label(v.get("qty"), v.get("qty_label")), "exit": f"{ex['reason']} {hm(ex['disp_t'])}",
                          "est": (", ".join(v["est"]) + " estimated") if v["est"] else "",
                          "thoughts": (th or {}).get("thoughts", ""), "brain_head": (th or {}).get("head", ""),
                          "zoom": zoom, "kind": kind,
                          "alt": f"{name} {t['day']} {'long' if v['dir'] == 1 else 'short'} {float(t.get('r') or 0):+.2f}R"})
            print(f"  {g:6s} {base}  {float(t.get('r') or 0):+.2f}R  {kind}{'  est:' + ','.join(v['est']) if v['est'] else ''}"
                  f"{'  +thoughts' if th else ''}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  FAILED {base}: {e}")
        if len(items) % 8 == 0:
            gc.collect()
    rule = "every trade" if all_ or len(trades) <= 2 * n else f"{n} best + {n} worst by R + {n} random (seed {seed})"
    man = {"name": name, "title": title or name, "source": os.path.relpath(path, ROOT).replace("\\", "/"), "key": key,
           "rule": rule, "stats": _stats(trades), "items": items, "priority": 0 if name.upper().startswith("ATM") else 1,
           "note": note, "generated": dt.datetime.now(ET).isoformat(timespec="seconds"),
           "replay_log": _REPLAY_LOG[-20:]}
    with open(os.path.join(GAL, f"_manifest_{name}.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=1)
    idx = build_index()
    print(f"{name}: rendered {len(items)}/{len(sel)} in {time.time() - t0:.0f}s -> {GAL}  (index {idx})")
    return man


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--trades", help="trade JSON (a list, a dict with 'trades', or a dict keyed by period)")
    ap.add_argument("--key", default=None, help="dict key holding the trades, e.g. ytd")
    ap.add_argument("--name", help="label used in file names (default: file stem)")
    ap.add_argument("--title", default=None, help="section title on the index page")
    ap.add_argument("--note", default=None, help="one-line note under the section title")
    ap.add_argument("--n", type=int, default=10, help="best / worst / random count")
    ap.add_argument("--all", action="store_true", help="render every trade")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--tf", type=int, default=None, help="trade frame in minutes (default: trade info.tf or 5)")
    ap.add_argument("--no-replay", action="store_true", help="engine trades: estimate from bars, skip the replay")
    ap.add_argument("--thoughts", default=None, help="extra narrative file with per-trade thoughts (.json or .md)")
    ap.add_argument("--keep", action="store_true", help="keep old images of this name")
    ap.add_argument("--index-only", action="store_true", help="only rebuild index.html from the manifests")
    a = ap.parse_args()
    os.makedirs(GAL, exist_ok=True)
    if a.index_only:
        print(build_index())
        sys.exit(0)
    if not a.trades:
        ap.error("--trades is required")
    nm = a.name or os.path.splitext(os.path.basename(a.trades))[0]
    render_list(a.trades, a.key, nm, a.n, a.all, a.seed, a.title, not a.no_replay, a.thoughts, a.note, a.tf,
                clean=not a.keep)
