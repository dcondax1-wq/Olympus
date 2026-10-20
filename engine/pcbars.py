"""No Yahoo (owner 2026-10-19: "I don't want Yahoo. Use NinjaTrader or TradingView data only.").

With `no_yahoo` on (live_model.json "no_yahoo", default true; a start cfg "no_yahoo" overrides it for the PC bot):
  * the PC bot (engine/live.py) reads its history from the TradingView exports (data/NQ_5m.csv, data/NQ_1m.csv) plus its own
    archive of NinjaTrader bars (data/nt_bars/<SYM>_<tf>.csv, gitignored, appended every poll from LE_BarFeed's files),
    and its fresh bars from NinjaTrader only. No Yahoo fallback: when the NinjaTrader feed is missing or stale, NEW entries
    are blocked at once (an open trade keeps its broker brackets and is still managed) and the health block says so.
  * the PC pushes its recent NinjaTrader bars with the heartbeat (engine/heartbeat.py, branch `heartbeat`):
    bars_1m.csv.gz (the last BARS_1M_DAYS days of 1m bars, every push) and bars_5m.csv.gz (the last BARS_5M_DAYS days of
    5m bars, rebuilt at most once an hour; an unchanged file is the same git blob, so it costs nothing to push again).
  * the cloud monitor and the fast-entry watcher (tools/cloud_monitor.py, tools/lit_watch.py) read those bars instead of
    Yahoo (CloudFeed). The cloud keeps what it received in its own store on the dashboard branch (pc_bars_5m.csv + the
    existing bars_1m.csv), so the LIT window (from the previous month's first day) never depends on the PC's 30 days.
    PC bars missing or stale -> the cloud paper bot takes no new paper entries and says
    "waiting for NinjaTrader bars from the PC".
  * VIX / VXN daily closes (the LIT target band) come from CBOE's own history files instead of Yahoo (engine/news.py).

Price basis: TradingView NQ1! (the exports) and NinjaTrader MNQ on the same contract month print the same prices (a tick
apart at most on a bar's extremes, the same closes). merge_basis() checks every overlap: when the newer source sits a
constant amount away from the older one (a contract roll: 100-300 points), the older bars are shifted by it (back-adjusted)
so levels from before the roll stay on the traded contract's prices; otherwise nothing is shifted. NinjaTrader's "Merge back
adjusted" history is exactly constant; two contracts' own prices (the chart switched after NinjaTrader's rollover date, or
merge policy "Do not merge") drift a few points a day with the price, so a roll-sized offset (>= ROLL_MIN) that is steady
over the last ROLL_TAIL shared bars counts too (fixed 2026-10-20: the 1-pt rule missed it and left a ~300-pt step in the
window; tests/test_roll.py scenario C). The December 2026 roll, step by step: docs/ROLL_DEC_2026.md.
"""
from __future__ import annotations

import gzip
import io
import json
import os
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
COLS = ["time", "open", "high", "low", "close", "volume"]
NO_YAHOO_DEFAULT = True

ARCHIVE_DIR = os.path.join(DATA_DIR, "nt_bars")
ARCHIVE_KEEP_DAYS = {"1m": 40, "5m": 120}

BARS_1M = "bars_1m.csv.gz"            # heartbeat branch: the PC's recent NinjaTrader 1m bars
BARS_5M = "bars_5m.csv.gz"            # heartbeat branch: the PC's NinjaTrader 5m bars (LIT window backfill)
HB_FILES = (BARS_1M, BARS_5M)
BARS_1M_DAYS = 3                      # ~2 trading days (a Monday push still reaches back into Friday)
BARS_5M_DAYS = 40                     # NinjaTrader's 5m history (LE_BarFeed keeps ~29 trading days)
BARS_5M_EVERY_S = 3600
STORE_5M = "pc_bars_5m.csv"           # the cloud's own store of PC 5m bars (dashboard branch)
STORE_1M = "bars_1m.csv"              # the cloud's 1m store (dashboard branch, 12 days; tools/cloud_monitor.py)
STORE_5M_DAYS = 75
CLOUD_STALE_S = 15 * 60               # the PC's newest 1m bar closed more than this ago in a session: waiting for the PC
WAITING = "waiting for NinjaTrader bars from the PC"
ROLL_MIN = 40.0                       # a quarterly roll gap is ~1% of NQ (Sep 2026: 295.75 pts); one contract: a tick or two
ROLL_TAIL = 120                       # two contracts' own prices: judge the offset on the last 120 shared bars only ...
ROLL_TOL = 0.03                       # ... where it may wander 3% of itself (the spread moves with the price, carry ~ price)


class YahooBlocked(RuntimeError):
    """Raised by the Yahoo fetch while no_yahoo is on (never reached by the bot's own paths; a guard for anything else)."""


def no_yahoo(cfg: dict | None = None) -> bool:
    """Is Yahoo switched off? cfg["no_yahoo"] (a start cfg) > LE_NO_YAHOO=0/1 > live_model.json "no_yahoo" > on."""
    if cfg and cfg.get("no_yahoo") is not None:
        return bool(cfg["no_yahoo"])
    env = os.environ.get("LE_NO_YAHOO", "")
    if env in ("0", "1"):
        return env == "1"
    try:
        if os.environ.get("LE_LIVE_MODEL"):
            lm = json.loads(os.environ["LE_LIVE_MODEL"])
        else:
            with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as fh:
                lm = json.load(fh)
        v = lm.get("no_yahoo")
        return NO_YAHOO_DEFAULT if v is None else bool(v)
    except Exception:
        return NO_YAHOO_DEFAULT


# ---------------------------------------------------------------------- frames
def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=COLS)


def _is_tidy(df) -> bool:
    try:
        return list(df.columns) == COLS and df["time"].dtype == "int64" and all(df[c].dtype == "float64" for c in COLS[1:]) \
            and df["time"].is_monotonic_increasing and df["time"].is_unique and not df[COLS[1:5]].isna().to_numpy().any()
    except Exception:
        return False


def tidy(df) -> pd.DataFrame:
    """time int64 (bar open, unix s), float OHLCV, de-duplicated (last wins), sorted. Bad rows dropped. A frame that is
    already tidy is returned as it is (no copy)."""
    if df is None or not len(df):
        return _empty()
    if _is_tidy(df):
        return df
    df = df[[c for c in COLS if c in df.columns]].copy()
    if "volume" not in df.columns:
        df["volume"] = 0.0
    for c in COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["time", "open", "high", "low", "close"])
    df["volume"] = df["volume"].fillna(0.0)
    df["time"] = df["time"].astype("int64")
    for c in COLS[1:]:
        df[c] = df[c].astype(float)
    return df.drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)


def aggregate(df, secs: int) -> pd.DataFrame:
    """1m -> 5m / 15m / 1h (bar open times on the secs grid)."""
    df = tidy(df)
    if not len(df):
        return df
    g = (df["time"] // secs) * secs
    out = df.groupby(g).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                            volume=("volume", "sum"))
    out.index.name = "time"
    out = out.reset_index()
    out["time"] = out["time"].astype("int64")
    return out


def basis_shift(old, new, min_overlap: int = 20) -> float:
    """How far `new` sits from `old` on their overlapping bars: a constant offset (a contract roll) or 0.0.
    Same contract (NQ1! vs MNQ, or the same file twice): 0.0."""
    if old is None or new is None or not len(old) or not len(new):
        return 0.0
    a = old[["time", "close"]].drop_duplicates("time", keep="last")
    b = new[["time", "close"]].drop_duplicates("time", keep="last")
    m = a.merge(b, on="time", suffixes=("_o", "_n"))
    if len(m) < min_overlap:
        return 0.0
    m = m.tail(600)
    d = (m["close_n"] - m["close_o"]).to_numpy(dtype=float)
    med = float(np.median(d))
    if abs(med) < 2.0:                                   # same contract: MNQ and NQ a tick or two apart at most
        return 0.0
    if float(np.mean(np.abs(d - med) <= 1.0)) >= 0.7:    # a constant offset: NinjaTrader's back-adjusted merge, a re-anchor
        return round(med * 4) / 4.0                      # on the tick grid
    # Two contracts' own prices (the chart switched after NinjaTrader's rollover date, or merge policy "Do not merge"):
    # their spread is the carry, ~1% of the price, so it moves with the price (a few points a day) and is never constant
    # to 1 pt over 600 bars. A roll-sized offset that is steady over the last ROLL_TAIL shared bars is still a roll.
    tail = d[-ROLL_TAIL:]
    mt = float(np.median(tail))
    if abs(mt) >= ROLL_MIN and len(tail) >= min_overlap and \
            float(np.mean(np.abs(tail - mt) <= max(1.0, ROLL_TOL * abs(mt)))) >= 0.8:
        return round(mt * 4) / 4.0
    return 0.0                                           # no steady offset: not a roll, never shift on noise


def merge_basis(old, new, min_overlap: int = 20):
    """old + new, new wins on every bar both have; when new sits a constant offset away (a roll), old is shifted onto
    new's basis first. Returns (frame, shift)."""
    old, new = tidy(old), tidy(new)
    if not len(old):
        return new, 0.0
    if not len(new):
        return old, 0.0
    sh = basis_shift(old, new, min_overlap)
    if sh:
        old = old.copy()
        for c in ("open", "high", "low", "close"):
            old[c] = old[c] + sh
    out = pd.concat([old, new]).drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)
    return out, sh


def hist_gap(hist, fresh, secs: int):
    """The hole between the end of `hist` and the start of `fresh` in market hours, or None. (start, end, missing bars)."""
    if hist is None or fresh is None or not len(hist) or not len(fresh):
        return None
    from .live import market_open
    h1, f0 = int(hist["time"].max()), int(fresh["time"].min())
    if f0 <= h1 + secs:
        return None
    if (f0 - h1) // secs > 20000:                         # a long hole: no need to count it minute by minute
        return (h1 + secs, f0, int((f0 - h1) // secs * 23 / 24 * 5 / 7))
    slots = [t for t in range(h1 + secs, f0, secs) if market_open(t) and market_open(t + secs - 1)]
    if len(slots) <= 2:                                   # a quiet minute or two is not a hole
        return None
    return (h1 + secs, f0, len(slots))


# ---------------------------------------------------------------------- compact transport (heartbeat branch)
def _num(x: float) -> str:
    s = f"{x:.2f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def encode(df) -> bytes:
    """Gzipped CSV "time,open,high,low,close,volume" (deterministic bytes: mtime 0, so the same bars are the same blob)."""
    df = tidy(df)
    buf = io.StringIO()
    buf.write(",".join(COLS) + "\n")
    for t, o, h, l, c, v in zip(df["time"].to_numpy(), df["open"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy(),
                                df["close"].to_numpy(), df["volume"].to_numpy()):
        buf.write(f"{int(t)},{_num(o)},{_num(h)},{_num(l)},{_num(c)},{int(v) if float(v).is_integer() else _num(v)}\n")
    return gzip.compress(buf.getvalue().encode("ascii"), compresslevel=9, mtime=0)


def decode(data: bytes | None) -> pd.DataFrame:
    if not data:
        return _empty()
    try:
        raw = gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data
        return tidy(pd.read_csv(io.BytesIO(raw), on_bad_lines="skip"))
    except Exception:
        return _empty()


# ---------------------------------------------------------------------- the PC's NinjaTrader archive
def archive_path(sym: str, tf: str, root: str | None = None) -> str:
    return os.path.join(root or ARCHIVE_DIR, f"{sym}_{tf}.csv")


def archive_read(sym: str, tf: str, root: str | None = None) -> pd.DataFrame:
    p = archive_path(sym, tf, root)
    if not os.path.exists(p):
        return _empty()
    try:
        return tidy(pd.read_csv(p, on_bad_lines="skip"))
    except Exception:
        return _empty()


def archive_add(sym: str, tf: str, df, root: str | None = None, now: int | None = None, prev=None) -> dict:
    """Keep NinjaTrader's closed bars on disk (the PC's own history once LE_BarFeed's 30 days move on). New bars are
    appended; a roll (constant offset on the overlap) back-adjusts the archive and rewrites it; older than
    ARCHIVE_KEEP_DAYS is trimmed when the file is rewritten. prev = the archive as already read (saves a read).
    Returns {"added", "shift", "rewritten"}; never raises."""
    try:
        new = tidy(df)
        if not len(new):
            return {"added": 0, "shift": 0.0, "rewritten": False}
        p = archive_path(sym, tf, root)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        old = tidy(prev) if prev is not None else archive_read(sym, tf, root)
        sh = basis_shift(old, new) if len(old) else 0.0
        last = int(old["time"].max()) if len(old) else None
        keep_s = ARCHIVE_KEEP_DAYS.get(tf, 60) * 86400
        now = int(now if now is not None else time.time())
        if not len(old) or sh or len(old) > 1.3 * (keep_s / 60 if tf == "1m" else keep_s / 300):
            out, sh = merge_basis(old, new)
            out = out[out["time"] >= now - keep_s]
            tmp = p + ".tmp"
            out.to_csv(tmp, index=False)
            os.replace(tmp, p)
            return {"added": len(out) - len(old), "shift": sh, "rewritten": True}
        add = new[new["time"] > last]
        if len(add):
            with open(p, "a", encoding="utf-8", newline="") as fh:
                fh.write("".join(f"{int(t)},{_num(o)},{_num(h)},{_num(l)},{_num(c)},{_num(v)}\n" for t, o, h, l, c, v in
                                 zip(add["time"], add["open"], add["high"], add["low"], add["close"], add["volume"])))
        return {"added": int(len(add)), "shift": 0.0, "rewritten": False}
    except Exception as e:
        return {"added": 0, "shift": 0.0, "rewritten": False, "error": f"{e.__class__.__name__}: {e}"}


# ---------------------------------------------------------------------- PC side: the files pushed with the heartbeat
class PCBars:
    """What the heartbeat pushes (bytes per file name). 1m every push, 5m rebuilt at most once an hour."""

    def __init__(self, sym: str = "NQ", root: str | None = None):
        self.sym, self.root = sym, root
        self._b5 = (0.0, None)

    def _frame(self, bot, tf):
        live = None
        try:
            live = (getattr(bot, "_nt_last", None) or {}).get((self.sym, tf))
        except Exception:
            live = None
        arc = archive_read(self.sym, tf, self.root)
        out, _ = merge_basis(arc, live)
        return out

    def files(self, bot=None, now: float | None = None) -> dict:
        now = float(now if now is not None else time.time())
        out = {}
        f1 = self._frame(bot, "1m")
        if len(f1):
            out[BARS_1M] = encode(f1[f1["time"] >= now - BARS_1M_DAYS * 86400])
        t5, b5 = self._b5
        if b5 is None or now - t5 >= BARS_5M_EVERY_S:
            f5 = self._frame(bot, "5m")
            if len(f5):
                b5 = encode(f5[f5["time"] >= now - BARS_5M_DAYS * 86400])
                self._b5 = (now, b5)
        if b5 is not None:
            out[BARS_5M] = b5
        return out

    @staticmethod
    def meta(files: dict, bot=None) -> dict:
        """The heartbeat.json "bars" block: newest bar times + the forming 1m bar's open (the watcher sizes from it)."""
        m = {"files": sorted(files)}
        b1 = decode(files.get(BARS_1M)) if files.get(BARS_1M) else None
        if b1 is not None and len(b1):
            m.update(last_1m_t=int(b1["time"].max()), n_1m=int(len(b1)))
        try:
            fo = (getattr(bot, "_nt_forming_last", None) or None)
            if fo:
                m["forming_1m"] = [int(fo[0]), float(fo[1])]
        except Exception:
            pass
        return m


# ---------------------------------------------------------------------- cloud side
class CloudFeed:
    """The cloud's bars without Yahoo: the PC's NinjaTrader bars from the heartbeat (hb["files"]) merged into the cloud's
    own store (<out>/pc_bars_5m.csv, <out>/bars_1m.csv). recent(sym, interval, period) is a LiveBot.fetch_recent."""

    def __init__(self, out: str | None, hb: dict | None, now: float | None = None, sym: str = "NQ", save: bool = True):
        self.out, self.sym = out, sym
        self.now = int(now if now is not None else time.time())
        hb = hb or {}
        files = hb.get("files") or {}
        self.hb_present = bool(hb.get("present"))
        self.hb_age = hb.get("age_s")
        self.b1 = decode(files.get(BARS_1M))
        b5 = decode(files.get(BARS_5M))
        meta = hb.get("bars") if isinstance(hb.get("bars"), dict) else {}
        fo = meta.get("forming_1m")
        self.forming = (int(fo[0]), float(fo[1])) if isinstance(fo, (list, tuple)) and len(fo) == 2 else None
        p5 = os.path.join(out, STORE_5M) if out else None
        store5 = _empty()
        if p5 and os.path.exists(p5):
            try:
                store5 = tidy(pd.read_csv(p5, on_bad_lines="skip"))
            except Exception:
                store5 = _empty()
        fresh5, _ = merge_basis(b5, aggregate(self.b1, 300) if len(self.b1) else None)
        if len(fresh5) and len(self.b1):                 # a 5m bar built from 1m is complete only when its last minute is in
            last1 = int(self.b1["time"].max())
            fresh5 = fresh5[fresh5["time"] + 300 <= last1 + 60]
        self.five, self.shift = merge_basis(store5, fresh5)
        self.five = self.five[self.five["time"] >= self.now - STORE_5M_DAYS * 86400].reset_index(drop=True)
        if save and p5 and len(self.five):
            try:
                os.makedirs(out, exist_ok=True)
                self.five.to_csv(p5, index=False)
            except Exception:
                pass
        self.last_1m_t = int(self.b1["time"].max()) if len(self.b1) else None
        self.last_5m_t = int(self.five["time"].max()) if len(self.five) else None

    def status(self) -> dict:
        from .live import market_open
        now = self.now
        age = (now - (self.last_1m_t + 60)) if self.last_1m_t else None
        if not self.hb_present:
            ok, why = False, "no heartbeat from the PC"
        elif self.last_1m_t is None:
            ok, why = False, "the PC sends no NinjaTrader bars (update the PC bot: git pull, restart)"
        elif market_open(now) and market_open(now - CLOUD_STALE_S) and age > CLOUD_STALE_S:
            ok, why = False, f"the PC's newest NinjaTrader 1m bar closed {age // 60} min ago"
        else:
            ok, why = True, "ok"
        return {"ok": ok, "reason": why, "text": "PC NinjaTrader bars" if ok else f"{WAITING} ({why})",
                "last_1m_t": self.last_1m_t, "last_5m_t": self.last_5m_t, "age_1m_s": age, "hb_age_s": self.hb_age,
                "n_1m": int(len(self.b1)), "n_5m": int(len(self.five)), "basis_shift": self.shift, "source": "pc-ninjatrader"}

    def recent(self, sym, interval, period="5d"):
        """LiveBot.fetch_recent for the cloud: the PC's bars (NQ only; ES and anything else: None, never Yahoo)."""
        if sym != self.sym:
            return None
        if interval == "1m":
            return self.b1.copy() if len(self.b1) else None
        secs = {"5m": 300, "15m": 900, "30m": 1800, "1h": 3600}.get(interval)
        if secs is None or not len(self.five):
            return None
        return self.five.copy() if secs == 300 else aggregate(self.five, secs)


# ---------------------------------------------------------------------- a guard for tests / the dry run
def install_yahoo_guard():
    """Make every yfinance / Yahoo HTTP call raise YahooBlocked (tests and the cloud dry run use it to prove none happens).
    Returns an undo function."""
    import sys
    import types
    calls = []

    def _boom(*a, **kw):
        calls.append((a[:1], sorted(kw)[:3]))
        raise YahooBlocked("Yahoo is switched off (no_yahoo)")

    fake = types.ModuleType("yfinance")
    fake.download = _boom
    fake.Ticker = _boom
    fake.__getattr__ = lambda name: _boom                     # noqa: E731  (any other yfinance attribute)
    prev_mod = sys.modules.get("yfinance")
    sys.modules["yfinance"] = fake
    import urllib.request
    orig_open = urllib.request.urlopen

    def _guarded(req, *a, **kw):
        url = req if isinstance(req, str) else getattr(req, "full_url", "")
        if "yahoo" in str(url).lower():
            return _boom(url)
        return orig_open(req, *a, **kw)
    urllib.request.urlopen = _guarded
    req_mod = sys.modules.get("requests")
    orig_req = getattr(req_mod, "request", None) if req_mod else None
    if req_mod is not None and orig_req is not None:
        def _req(method, url, *a, **kw):
            if "yahoo" in str(url).lower():
                return _boom(url)
            return orig_req(method, url, *a, **kw)
        req_mod.request = _req

    def undo():
        if prev_mod is not None:
            sys.modules["yfinance"] = prev_mod
        else:
            sys.modules.pop("yfinance", None)
        urllib.request.urlopen = orig_open
        if req_mod is not None and orig_req is not None:
            req_mod.request = orig_req
    undo.calls = calls
    return undo
