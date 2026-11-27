"""The Insta card (day-insta 2026-11-27, owner: "on good days a sick image to post on insta that shows daily PNL").

On a GREEN day the 16:20 ET day summary on Telegram is followed by a 1080 x 1350 picture (engine/png_chart.render_insta: numpy +
zlib, OLYMPUS NIGHT): the big "+$X" day P&L, the date, $ per account BY NAME (never an account number / firm id: notify.mask_ids
on top), trades + win dots, the day's price line with every trade's entry and exit, the "OLYMPUS · NQ" brand.
Real accounts only: a Sim / paper / BLITZ row or fill is never counted. A red or flat day: no card.

    spec(card, day, fills=None, bars=None) -> the render spec | None (not green)     pure
    make(card, day) -> PNG path | None        draws (bars from engine/trade_card.bars, fills from engine/datapipe.day_fills),
                                              saves logs/cards/insta_<day>.png + .json (the /insta re-send). Never raises.
    load(day) -> PNG path | None              /insta [YYYY-MM-DD] (engine/tg_cmd): the saved card, re-drawn from its .json if needed
Sent by engine/alert_bus after the day summary's text (its daemon thread: never blocks, any trouble = no picture).
Off: LE_INSTA=0 or notify_settings.json alerts.trade_cards false. Tests: python -X utf8 -m tests.test_insta_card
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = ("sim", "paper", "demo", "playback", "replay", "blitz", "acctc", "acct_c")
CANDLES = 80
DAY_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _f(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _paper(*words) -> bool:
    """Whole words (red team #39): an MFFU 'Sim Funded' account is a REAL payout account and counts; NinjaTrader's Sim101 /
    Playback101, paper, demo, replay, BLITZ (acctc) never do."""
    s = " ".join(str(w or "") for w in words)
    try:
        from . import tg_pretty
        return tg_pretty._paper_words(s)
    except Exception:
        w = re.sub(r"sim[ _-]*funded", " ", s.lower())
        toks = [t for t in re.split(r"[^a-z0-9]+", w) if t]
        return any(t in PAPER or re.match(r"^(sim|playback)\d+$", t) for t in toks) or "acct_c" in w or "acctc" in w


def _mask(s) -> str:
    try:
        from . import notify
        s = notify.mask_ids(s)
    except Exception:
        pass
    s = re.sub(r"\.\.\.\d{2,}", "", str(s or ""))              # a masked id adds nothing on a public picture: drop it
    s = re.sub(r"[\w-]*\d{5,}[\w-]*", "", s)                    # red team #45: any other id-like run (FFN12345678, 98765432)
    return re.sub(r"\s+", " ", s).strip()


def enabled(env=None) -> bool:
    e = os.environ if env is None else env
    if str(e.get("LE_INSTA", "1")).strip() == "0":
        return False
    try:
        from . import trade_card
        return trade_card.enabled(env)
    except Exception:
        return True


def card_dir() -> str:
    from . import trade_card
    return trade_card.CARD_DIR


def _et_range(day: str) -> tuple:
    from zoneinfo import ZoneInfo
    d = dt.date.fromisoformat(day)
    et = ZoneInfo("America/New_York")
    t0 = int(dt.datetime(d.year, d.month, d.day, 8, 0, tzinfo=et).timestamp())
    t1 = int(dt.datetime(d.year, d.month, d.day, 16, 15, tzinfo=et).timestamp())
    return t0, t1


def marks_of(fills) -> list:
    """Real trades of the day from the fill log rows (engine/datapipe FILL_FIELDS): entries with their exit. BLITZ / Sim never."""
    out = []
    for r in fills or []:
        if not isinstance(r, dict) or str(r.get("leg") or "entry") not in ("entry", ""):
            continue
        if _paper(r.get("lane"), r.get("account"), r.get("book")):
            continue
        t, p = _f(r.get("fill_t") or r.get("entry_t")), _f(r.get("fill_px"))
        if t is None or p is None:
            continue
        xt, xp = _f(r.get("exit_fill_t")), _f(r.get("exit_fill_px"))
        usd = None
        if xp is not None:
            d = 1 if str(r.get("side") or r.get("action") or "").upper() in ("LONG", "BUY") else -1
            usd = (xp - p) * d * 2.0 * (_f(r.get("qty")) or 1)
        out.append({"t": t, "px": p, "xt": xt, "xpx": xp, "usd": usd,
                    "side": "LONG" if str(r.get("side") or r.get("action") or "").upper() in ("LONG", "BUY") else "SHORT"})
    return sorted(out, key=lambda m: m["t"])[:20]


def spec(card: dict, day: str, fills=None, bars=None) -> dict | None:
    """The render spec of a day summary card, or None when the day is not green (real accounts only). Pure."""
    if not isinstance(card, dict) or not DAY_RX.match(str(day or "")):
        return None
    rows = []
    for r in card.get("rows") or []:
        if not isinstance(r, dict) or r.get("sim") or _paper(r.get("name")):
            continue
        t = _f(r.get("today"))
        name = _mask(r.get("name"))[:24] or "Account"     # red team #45: a name that was only an id still counts
        rows.append({"name": name, "today": t or 0.0, "trades": int(_f(r.get("trades")) or 0)})
    tot = round(sum(r["today"] for r in rows), 2)
    if tot <= 0.5:
        return None                                       # red / flat day: no card
    mk = marks_of(fills)
    closed = [m for m in mk if m.get("usd") is not None]
    n = max(sum(r["trades"] for r in rows), len(mk))
    wins = sum(1 for m in closed if m["usd"] > 0)
    losses = sum(1 for m in closed if m["usd"] < 0)
    if not closed:                                        # no fill log: count by account (a green account = a win)
        wins = sum(1 for r in rows if r["today"] > 0 and r["trades"])
        losses = sum(1 for r in rows if r["today"] < 0 and r["trades"])
    rows.sort(key=lambda r: -r["today"])
    b = [(int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4])) for x in bars or []
         if isinstance(x, (list, tuple)) and len(x) >= 5]
    if len(b) > CANDLES:                                  # ~CANDLES candles across 936 px (the site's card shows the same)
        k = -(-len(b) // CANDLES)
        b = [(g[0][0], g[0][1], max(y[2] for y in g), min(y[3] for y in g), g[-1][4]) for g in (b[i:i + k] for i in range(0, len(b), k))]
    week = None
    wk = [_f(r.get("week")) for r in card.get("rows") or [] if isinstance(r, dict) and not r.get("sim") and not _paper(r.get("name"))]
    if any(v is not None for v in wk):
        week = round(sum(v or 0.0 for v in wk), 2)
    d = dt.date.fromisoformat(day)
    return {"day": day, "date": f"{d:%a %b %d %Y}".upper(), "total": tot, "rows": rows, "trades": n, "wins": wins,
            "losses": losses, "week": week, "bars": b, "marks": mk}


def _paths(day: str) -> tuple:
    base = os.path.join(card_dir(), f"insta_{day}")
    return base + ".png", base + ".json"


def draw(sp: dict, day: str) -> str | None:
    from . import png_chart as PC
    png = PC.render_insta(sp)
    if not png:
        return None
    os.makedirs(card_dir(), exist_ok=True)
    p_png, p_js = _paths(day)
    with open(p_png, "wb") as fh:
        fh.write(png)
    with open(p_js, "w", encoding="utf-8") as fh:
        json.dump(sp, fh)
    try:
        from . import trade_card
        trade_card._trim()
    except Exception:
        pass
    return p_png


def make(card: dict, day: str, fills_fn=None, bars_fn=None) -> str | None:
    """Draw today's card (green days only) -> its PNG path, or None. Never raises."""
    try:
        if not enabled() or not DAY_RX.match(str(day or "")):
            return None
        if spec(card, day) is None:
            return None                                   # not green: no bar / fill reads at all
        t0, t1 = _et_range(day)
        try:
            if fills_fn:
                fills = fills_fn(day)
            else:
                from . import datapipe
                fills = datapipe.day_fills(day)
        except Exception:
            fills = []
        try:
            if bars_fn:
                bars = bars_fn(t0, t1)
            else:
                from . import trade_card
                bars = trade_card.bars(t0, t1)
        except Exception:
            bars = []
        mk = marks_of(fills)
        if mk and bars:                                   # the window around the day's trades (+-45 min), never less than 2 h
            a = max(t0, int(min(m["t"] for m in mk)) - 2700)
            z = min(t1, int(max((m.get("xt") or m["t"]) for m in mk)) + 2700)
            if z - a < 7200:
                a, z = max(t0, a - 3600), min(t1, z + 3600)
            bars = [x for x in bars if a <= int(x[0]) <= z]
        sp = spec(card, day, fills, bars)
        return draw(sp, day) if sp else None
    except Exception:
        return None


def load(day: str | None = None) -> str | None:
    """/insta: the saved card of `day` (default: the newest saved), re-drawn from its .json when the PNG is gone. Never raises."""
    try:
        if day is None:
            js = sorted(glob.glob(os.path.join(card_dir(), "insta_*.json")))
            if not js:
                return None
            day = os.path.basename(js[-1])[6:16]
        if not DAY_RX.match(str(day)):
            return None
        p_png, p_js = _paths(day)
        if os.path.exists(p_png):
            return p_png
        if os.path.exists(p_js):
            with open(p_js, encoding="utf-8") as fh:
                return draw(json.load(fh), day)
        return None
    except Exception:
        return None


def caption(card_or_spec: dict) -> str:
    tot = _f((card_or_spec or {}).get("total"))
    return f"\U0001F4F8 Insta card: {'+' if (tot or 0) > 0 else ''}${abs(tot or 0):,.0f} day · ready to post"


def photo(card: dict, day: str) -> tuple | None:
    """(PNG path, caption) for the bus (engine/alert_bus more_photos), or None (not green / off / trouble). Never raises."""
    try:
        p = make(card, day)
        if not p:
            return None
        with open(_paths(day)[1], encoding="utf-8") as fh:
            sp = json.load(fh)
        return p, caption(sp)
    except Exception:
        return None
