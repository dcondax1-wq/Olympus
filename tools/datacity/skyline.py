"""The big city (2026-11-03): every tested combination as one compact row (the skyline), the district sections the page lays
out from data (the same plug-in contract any new data source uses), the Today layer, the weather (VIX) and the Harbor (the
live bot's own trades). Pure functions of a Study; learn.py writes them into city.json.

Skyline row (city.json "skyline": {"cols", "rows"}): numbers only, decoded by the page with "dict" (the same words as
report.label, so a compact building's card says exactly what a full one says):
  t   trigger index (F.TRIGS)          w   window index, -1 any time, 100 + slot for a 15-minute slot
  k1  k2  a "while" state as family index x 16 + value (FAMS), -1 none
  d   district index (G.DISTRICTS)     cls class index (CLS)
  e   $ per trade per micro (whole $)  r   R per trade x 100       wr  win %         n  trades   tpw  trades a week x 100
  e26 n26  2026 $ and trades           eo  no   2021-25 $ and trades
  fl  flags: 1 FDR, 2 rising, 4 decaying, 8 fired on the last session (trigger + states true), 16 armed (its day-level
      states are true on the last session, no trigger)
"""
from __future__ import annotations

import json
import os

import numpy as np

from . import bars as B
from . import features as F
from . import grid as G

FAMS = list(F.FAMILIES) + ["mon"]
CLS = ("gold", "green", "amber", "grey")
COLS = ("t", "w", "k1", "k2", "d", "cls", "e", "r", "wr", "n", "tpw", "e26", "n26", "eo", "no", "fl")
FL_FDR, FL_RISE, FL_DECAY, FL_FIRED, FL_ARMED = 1, 2, 4, 8, 16
SECTION_META = {          # key -> (name on the street sign, what lives there, sign colour)
    "times": ("TIMES", "Every 15-minute slot and session open, long and short", "#7fe9ff"),
    "confluences": ("CONFLUENCES", "Every trigger (sweeps, breaks, FVG, IFVG, CISD, displacement, VWAP, gap fill, news)", "#ffd36b"),
    "week": ("THE WEEK", "Weekday x session, and weekday x every 15-minute slot", "#9ad1ff"),
    "seasons": ("SEASONS", "Month of the year, the turn of the month, OpEx week", "#ffb38a"),
    "volatility": ("VOLATILITY", "VIX and VXN levels, the ATR regime, the VIX curve and the VIX trend", "#ff7ad9"),
    "gaps": ("GAPS", "Gap up / down at the RTH open, filled or still open", "#8affc1"),
    "orange": ("OPENING RANGE", "Narrow / normal / wide 09:30-09:45 range, price beyond or inside it", "#ffa24a"),
    "esnq": ("ES-NQ", "ES-NQ SMT and relative strength (ES bars from 2025-04 only: never green in 2021-25)", "#b9a6ff"),
    "while": ("WHILE-STATES", "VWAP side, EMA trend, London vs Asia, day type, DST, news day", "#e9ecf6"),
}
VIX_WEATHER = ((15, "clear"), (20, "haze"), (25, "rain"), (1e9, "storm"))


def dictionary(win_label) -> dict:
    """The words the page needs to decode a skyline row into the same label report.label writes."""
    from .report import MONTHS
    return {"trigs": [list(t) for t in F.TRIGS], "wins": list(F.WIN_NAMES), "win_lab": [win_label[w] for w in F.WIN_NAMES],
            "any": win_label["all"], "fams": [[f, list(F.STATES[f]) if f != "mon" else list(MONTHS)] for f in FAMS],
            "slot_trigs": list(G.SLOT_TRIGS), "districts": list(G.DISTRICTS), "cls": list(CLS), "cols": list(COLS),
            "flags": {"fdr": FL_FDR, "rising": FL_RISE, "decaying": FL_DECAY, "fired": FL_FIRED, "armed": FL_ARMED}}


def code(c) -> list:
    """[t, w, k1, k2] of a combination."""
    k = [FAMS.index(f) * 16 + int(v) for f, v in c["conds"]] + [-1, -1]
    return [F.TRIG_ID[c["trig"]], 100 + c["slot"] if c["slot"] >= 0 else c["win"], k[0], k[1]]


# ------------------------------------------------------------------------------------------------ the Today layer
class Today:
    """What was true on the last complete session: every day-level state (weekday, month, VIX, the VIX curve ...) and which
    combinations fired (their trigger AND states were true at some bar of it)."""

    def __init__(self, grid: G.Grid):
        self.last = len(grid.days) - 1
        self.day = str(grid.days[-1]) if len(grid.days) else None
        on = np.flatnonzero(grid.ev["day"] == self.last)
        self.states = {}
        if len(on):
            j = int(on[0])
            for f in F.DAY_FAMILIES:
                v = int(grid.mon[j]) if f == "mon" else int(grid.ev["s_" + f][j])
                if v >= 0:
                    self.states[f] = v

    def flag(self, c, s) -> int:
        if s.get("n", 0) and s.get("ld") == self.last:
            return FL_FIRED
        if c["conds"] and all(f in F.DAY_FAMILIES and self.states.get(f) == v for f, v in c["conds"]):
            return FL_ARMED
        return 0

    def summary(self, combos, rows, shown) -> dict:
        fl = [self.flag(combos[i], rows[i]) for i in shown]
        words = {f: (F.STATES[f][v] if f != "mon" else _month(v)) for f, v in self.states.items()}
        return {"day": self.day, "states": words, "fired": sum(1 for x in fl if x == FL_FIRED),
                "armed": sum(1 for x in fl if x == FL_ARMED),
                "note": "Lit on the last complete session in the data (the PC's NinjaTrader bars, incremental run): fired = "
                        "its trigger and states were all true; armed = its day-level states were true, no trigger."}


def _month(v):
    from .report import MONTHS
    return MONTHS[v]


# ------------------------------------------------------------------------------------------------ the skyline
def flags(st, i, today: Today) -> int:
    s = st.rows[i]
    tr = st.trend(i)
    return ((FL_FDR if s.get("fdr") else 0) | (FL_RISE if tr == "rising" else 0) | (FL_DECAY if tr == "decaying" else 0)
            | today.flag(st.combos[i], s))


def row(st, i, today: Today) -> list:
    c, s = st.combos[i], st.rows[i]
    r10 = lambda x, k=10: int(round((x or 0) * k))  # noqa: E731, RUF046 (a numpy float rounds to a float)
    return code(c) + [G.DISTRICTS.index(c["district"]), CLS.index(s["cls"]), r10(s["mu"], 1), r10(s["r"], 100),
                      r10(s["win"], 100), s["n"], r10(s["tpw"], 100), r10(s["mu26"], 1), s["n26"], r10(s["muold"], 1), s["nold"],
                      flags(st, i, today)]


def tested(st) -> list:
    """Every distinct combination with 30+ trades, district by district, the strongest first."""
    ids = [i for i, s in enumerate(st.rows) if s.get("n", 0) >= G.MIN_N and "dup_of" not in s]
    ids.sort(key=lambda i: (G.DISTRICTS.index(st.combos[i]["district"]), CLS.index(st.rows[i]["cls"]), -st.rows[i]["t"]))
    return ids


def skyline(st, today: Today, skip=()) -> dict:
    skip = set(skip)
    return {"cols": list(COLS), "rows": [row(st, i, today) for i in tested(st) if i not in skip]}


def sections(guard) -> list:
    """The districts as data: the page lays out whatever sections it gets (new data sources add their own)."""
    out = []
    for k in G.DISTRICTS:
        name, blurb, color = SECTION_META[k]
        g = guard["districts"].get(k, {})
        out.append({"key": k, "name": name, "blurb": blurb, "color": color, "kind": "combos", "tried": g.get("tried", 0),
                    "tested": g.get("tested", 0), "fdr": g.get("fdr", 0), "gold": g.get("gold", 0)})
    return out


# ------------------------------------------------------------------------------------------------ weather and harbor
def weather() -> dict:
    """The last CBOE closes (VIX, VXN, VIX3M) and the sky they make: clear < 15, haze < 20, rain < 25, storm 25+."""
    out = {}
    for name, d in (("vix", B.load_daily("VIX")), ("vxn", B.load_daily("VXN")), ("vix3m", B.load_cboe("vix3m"))):
        if len(d):
            out[name] = round(float(d["close"].iloc[-1]), 2)
            out[name + "_date"] = str(d["date"].iloc[-1])
    v = out.get("vix")
    out["sky"] = next(w for lim, w in VIX_WEATHER if v is None or v < lim) if v is not None else "clear"
    out["source"] = "CBOE's own VIX / VXN / VIX3M closes (data/)"
    return out


PLUGIN_DIR = os.path.join(B.OUT, "plugins")
PLUGIN_MAX_ITEMS = 4000
PLUGIN_MAX_BYTES = 400_000


def collect_plugins(folder=PLUGIN_DIR) -> list:
    """Plug-in districts from other data sources (PANTHEON feeds ...): every research/datacity/plugins/*.json that follows
    the contract in tools/web_public/datacity/data.js ({key, name, blurb, color, items: [{id, lab, value, unit, cls, note,
    sp}]}). Returns [(file name for the page, the cleaned district)]; a bad file is skipped, never fatal."""
    out = []
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        p = os.path.join(folder, name)
        if not name.endswith(".json") or os.path.getsize(p) > PLUGIN_MAX_BYTES:
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
            key = "".join(ch for ch in str(d["key"]) if ch.isalnum() or ch in "_-")[:24]
            items = [{"id": str(x.get("id", k))[:60], "lab": str(x.get("lab", ""))[:160], "value": float(x.get("value", 0) or 0),
                      **{f: x[f] for f in ("unit", "cls", "note") if isinstance(x.get(f), str)},
                      **({"sp": [float(v) for v in x["sp"][:60]]} if isinstance(x.get("sp"), list) else {})}
                     for k, x in enumerate(d["items"][:PLUGIN_MAX_ITEMS]) if isinstance(x, dict)]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if not key or key in G.DISTRICTS or not items:
            continue
        clean = {"v": 1, "key": key, "name": str(d.get("name", key))[:24], "blurb": str(d.get("blurb", ""))[:200],
                 "color": d["color"] if isinstance(d.get("color"), str) and len(d["color"]) == 7 and d["color"][0] == "#" else "#7fe9ff",
                 "items": items}
        out.append((f"district_{key}.json", clean))
    return out


def harbor(root=B.ROOT) -> dict | None:
    """The live bot's trades as ships: run lit_live (the live settings replayed, costs in). Each row [day, dir, R, $, exit]."""
    try:
        with open(os.path.join(root, "research", "runs", "lit_live.json"), encoding="utf-8") as fh:
            run = json.load(fh)
    except (OSError, ValueError):
        return None
    cols = run["trade_cols"]
    T = [dict(zip(cols, t, strict=True)) for t in run["trades"]]
    rows = [[t["day"], int(t["dir"]), round(float(t["r"]), 2), round(float(t["pnl"])), str(t.get("exit") or "")[:8].lower()]
            for t in T]
    return {"title": "Harbor: LIT's trades (run lit_live, the live settings replayed, costs in)", "cols": ["day", "dir", "r", "pnl", "exit"],
            "rows": rows, "note": "One ship a trade: green won, red lost; size = the $. Paper replay, not broker fills."}
