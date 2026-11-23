"""PANTHEON sources: free, key-less public data, fetched once a night (CRONOS) with a cache and the repo's own files as fallback.

Every source is a `Source` (id, url, parser). `Store.series(id)` returns its parsed data and records where it came from:
  network   fetched now (and written to the cache, data/pantheon_cache/, gitignored)
  cache     the network failed: the last good download
  local     no cache either: the repo's own file (data/VIX_1d.csv, VXN_1d.csv, CBOE_vol_1d.csv, GEX_1d.csv, news/*)
  fixture   tests only: a recorded response (tests/fixtures/pantheon/), never the network
  missing   nothing: the god that needs it shows "offline"
Parsers are pure (text in, pandas out) and tested on the recorded fixtures. No API keys, no paid plans, never Yahoo.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import io
import json
import os
import urllib.request

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data")
CACHE = os.path.join(DATA, "pantheon_cache")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) nq-liquidity-engine-pantheon/1.0 (research; contact via GitHub)"}
START = "2015-01-01"                    # enough history for a 5-year percentile at the start of the 2021-26 test window
TIMEOUT = 45

FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}"
CBOE = "https://cdn-api.cboe.com/api/global/us_indices/daily_prices/{sym}_History.csv"   # Nov 2026: cdn.cboe.com 307s here
CFTC_TFF = ("https://publicreporting.cftc.gov/resource/gpe5-46if.json?$select=report_date_as_yyyy_mm_dd,{cols}"
            "&$where=cftc_contract_market_code=%27{code}%27%20AND%20report_date_as_yyyy_mm_dd%3E=%27{start}%27"
            "&$order=report_date_as_yyyy_mm_dd&$limit=5000")
SQUEEZE = "https://squeezemetrics.com/monitor/static/DIX.csv"
TREASURY = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{year}/all"
            "?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv")
FF_WEEK = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
NQ_MINI = "209742"                      # CFTC contract market code: NASDAQ MINI (E-mini Nasdaq-100), CME


# ------------------------------------------------------------------------------------------------------------ parsers
def parse_fred(text: str) -> pd.Series:
    """FRED fredgraph.csv: `observation_date,<ID>` (older files: `DATE,<ID>`); "." or "" = no value."""
    df = pd.read_csv(io.StringIO(text))
    if df.shape[1] < 2:
        raise ValueError("FRED csv: expected two columns")
    s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").to_numpy(), index=pd.to_datetime(df.iloc[:, 0]), name=df.columns[1])
    return s.dropna().sort_index()


def parse_cboe(text: str) -> pd.Series:
    """CBOE daily_prices CSV: `DATE,OPEN,HIGH,LOW,CLOSE` (mm/dd/yyyy) or `DATE,<SYM>` (SKEW): the close (last column)."""
    df = pd.read_csv(io.StringIO(text))
    if "DATE" not in df.columns:
        raise ValueError("CBOE csv: no DATE column")
    s = pd.Series(pd.to_numeric(df.iloc[:, -1], errors="coerce").to_numpy(), index=pd.to_datetime(df["DATE"], format="%m/%d/%Y"))
    return s[s > 0].dropna().sort_index()


TFF_COLS = {"open_interest_all": "oi", "asset_mgr_positions_long": "am_long", "asset_mgr_positions_short": "am_short",
            "lev_money_positions_long": "lev_long", "lev_money_positions_short": "lev_short",
            "dealer_positions_long_all": "dealer_long", "dealer_positions_short_all": "dealer_short"}


def parse_cftc_tff(text: str) -> pd.DataFrame:
    """CFTC Traders in Financial Futures (Socrata JSON rows) -> one row per report date (Tuesday positions)."""
    rows = json.loads(text)
    if not isinstance(rows, list):
        raise ValueError("CFTC: expected a JSON list")
    recs = []
    for r in rows:
        if not isinstance(r, dict) or "report_date_as_yyyy_mm_dd" not in r:
            continue
        rec = {"date": pd.Timestamp(r["report_date_as_yyyy_mm_dd"][:10])}
        for k, v in TFF_COLS.items():
            rec[v] = pd.to_numeric(r.get(k), errors="coerce")
        recs.append(rec)
    if not recs:
        raise ValueError("CFTC: no report rows")
    df = pd.DataFrame(recs).dropna(subset=["oi"]).drop_duplicates("date", keep="last").set_index("date").sort_index()
    df["am_net"] = df["am_long"] - df["am_short"]
    df["lev_net"] = df["lev_long"] - df["lev_short"]
    df["am_net_pct"] = 100.0 * df["am_net"] / df["oi"]
    df["lev_net_pct"] = 100.0 * df["lev_net"] / df["oi"]
    return df


def parse_squeeze(text: str) -> pd.DataFrame:
    """SqueezeMetrics DIX.csv / data/GEX_1d.csv: `date,price,dix,gex` (S&P 500 dark-pool index and gamma exposure)."""
    df = pd.read_csv(io.StringIO(text))
    need = {"date", "dix", "gex"}
    if not need <= set(df.columns):
        raise ValueError("DIX csv: missing columns")
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")[["dix", "gex"]].apply(pd.to_numeric, errors="coerce").dropna().sort_index()


TENORS = ["1 Mo", "2 Mo", "3 Mo", "4 Mo", "6 Mo", "1 Yr", "2 Yr", "3 Yr", "5 Yr", "7 Yr", "10 Yr", "20 Yr", "30 Yr"]


def parse_treasury(text: str) -> pd.DataFrame:
    """US Treasury daily par yield curve CSV (one year): Date (mm/dd/yyyy) + one column per tenor, newest first."""
    df = pd.read_csv(io.StringIO(text))
    if "Date" not in df.columns:
        raise ValueError("Treasury csv: no Date column")
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
    cols = [c for c in TENORS if c in df.columns]
    if not cols:
        raise ValueError("Treasury csv: no tenor columns")
    return df.set_index("Date")[cols].apply(pd.to_numeric, errors="coerce").sort_index()


def parse_ff_week(text: str) -> pd.DataFrame:
    """ForexFactory's free weekly calendar JSON -> US high-impact events: when (ET), title."""
    rows = json.loads(text)
    if not isinstance(rows, list):
        raise ValueError("FF calendar: expected a JSON list")
    out = []
    for r in rows:
        if not isinstance(r, dict) or r.get("country") != "USD" or r.get("impact") != "High":
            continue
        try:
            t = pd.Timestamp(r["date"]).tz_convert("America/New_York").tz_localize(None)
        except (KeyError, ValueError, TypeError):
            continue
        out.append({"when": t, "event": str(r.get("title") or "").strip()[:80], "source": "forexfactory"})
    return pd.DataFrame(out, columns=["when", "event", "source"])


def parse_events(text: str) -> pd.DataFrame:
    """data/news/events.csv (built by data/build_news.py from bls.gov / federalreserve.gov): high-impact rows -> when, event."""
    df = pd.read_csv(io.StringIO(text))
    df = df[df["impact"].astype(str).str.lower() == "high"]
    when = pd.to_datetime(df["date"] + " " + df["time_et"].fillna("08:30").astype(str), errors="coerce")
    return pd.DataFrame({"when": when, "event": df["event"].astype(str), "source": df.get("source", "events.csv")}).dropna(subset=["when"])


# ------------------------------------------------------------------------------------------------------------ local fallbacks
def _local_csv(name):
    p = os.path.join(DATA, name)
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def local_cboe(sym: str) -> pd.Series | None:
    """The repo's own CBOE files (VIX_1d.csv, VXN_1d.csv, CBOE_vol_1d.csv) as a fallback for the CBOE fetch."""
    if sym in ("VIX", "VXN"):
        df = pd.read_csv(io.StringIO(_local_csv(f"{sym}_1d.csv")))
        return pd.Series(df["close"].to_numpy(), index=pd.to_datetime(df["date"])).dropna().sort_index()
    col = {"VIX9D": "vix9d", "VIX3M": "vix3m", "SKEW": "skew"}.get(sym)
    if not col:
        return None
    df = pd.read_csv(io.StringIO(_local_csv("CBOE_vol_1d.csv")))
    return pd.Series(pd.to_numeric(df[col], errors="coerce").to_numpy(), index=pd.to_datetime(df["date"])).dropna().sort_index()


# ------------------------------------------------------------------------------------------------------------ the registry
@dataclasses.dataclass(frozen=True)
class Source:
    id: str                 # e.g. "fred:DGS10"
    name: str               # what it is, plain
    url: str
    parser: object
    fixture: str            # file name under tests/fixtures/pantheon/ and the cache
    local: object = None    # () -> parsed data from the repo's own files, or None
    note: str = ""


def _fred(sid, name, note=""):
    return Source(f"fred:{sid}", name, FRED.format(sid=sid, start=START), parse_fred, f"fred_{sid}.csv", note=note)


def _cboe(sym, name):
    return Source(f"cboe:{sym}", name, CBOE.format(sym=sym), parse_cboe, f"cboe_{sym}.csv",
                  local=lambda: local_cboe(sym))


def _treasury_url(today=None):
    return TREASURY.format(year=(today or dt.date.today()).year)


SOURCES: tuple = (
    _fred("WALCL", "Fed balance sheet (total assets, weekly, $m)"),
    _fred("RRPONTSYD", "Fed overnight reverse repo (daily, $bn)"),
    _fred("WTREGEN", "Treasury General Account (weekly, $m)"),
    _fred("DGS10", "10-year Treasury yield (%)"),
    _fred("DGS2", "2-year Treasury yield (%)"),
    _fred("T10Y2Y", "10y minus 2y spread (%)"),
    _fred("DFF", "Effective fed funds rate (%)"),
    _fred("DTWEXBGS", "Broad trade-weighted US dollar index"),
    _fred("BAMLH0A0HYM2", "ICE BofA US high-yield option-adjusted spread (%)",
          note="FRED keeps only the last 3 years of ICE index data"),
    _fred("NFCI", "Chicago Fed National Financial Conditions Index (weekly)"),
    _fred("CBBTCUSD", "Bitcoin in USD (Coinbase, daily). Not futures data: display only"),
    _cboe("VIX", "Cboe VIX (S&P 500 30-day implied vol)"),
    _cboe("VIX9D", "Cboe VIX9D (9-day implied vol)"),
    _cboe("VIX3M", "Cboe VIX3M (3-month implied vol)"),
    _cboe("VXN", "Cboe VXN (Nasdaq-100 implied vol)"),
    _cboe("SKEW", "Cboe SKEW (tail-risk pricing)"),
    Source("cftc:tff_nq", "CFTC Traders in Financial Futures: E-mini Nasdaq-100 (weekly, Tuesday positions)",
           CFTC_TFF.format(code=NQ_MINI, start=START, cols=",".join(TFF_COLS)), parse_cftc_tff, "cftc_tff_nq.json"),
    Source("squeeze:dix", "SqueezeMetrics DIX + GEX (S&P 500 dark pools and dealer gamma, daily)", SQUEEZE, parse_squeeze,
           "squeeze_dix.csv", local=lambda: parse_squeeze(_local_csv("GEX_1d.csv"))),
    Source("treasury:curve", "US Treasury daily par yield curve (this year)", "", parse_treasury, "treasury_curve.csv"),
    Source("ff:week", "ForexFactory weekly calendar (free JSON): US high-impact events", FF_WEEK, parse_ff_week, "ff_week.json",
           local=lambda: parse_ff_week(_local_csv(os.path.join("news", "ff_thisweek.json")))),
    Source("local:events", "Curated US high-impact calendar (bls.gov, federalreserve.gov): data/news/events.csv", "",
           parse_events, "events.csv", local=lambda: parse_events(_local_csv(os.path.join("news", "events.csv")))),
)
BY_ID = {s.id: s for s in SOURCES}

SKIPPED = (
    {"name": "CBOE put/call ratios", "why": "CBOE's free put/call CSVs (cdn.cboe.com .../totalpc.csv) stopped in Oct 2019; "
                                            "the current daily page has no free file"},
    {"name": "FRED release calendar (economic calendar)", "why": "the FRED API needs a key; ATHENA uses the free ForexFactory "
                                                                 "week + the repo's curated bls.gov / Fed calendar instead"},
    {"name": "CFTC weekly text files (cftc.gov/dea/newcot)", "why": "blocked (403) for scripts; the CFTC public-reporting API "
                                                                     "serves the same report key-less"},
)


# ------------------------------------------------------------------------------------------------------------ the store
class Store:
    """Fetch-once-per-build access to the sources, with the cache and fallbacks; `log[id]` says where each came from."""

    def __init__(self, offline: bool = False, fixtures: str | None = None, cache: str = CACHE, today: dt.date | None = None,
                 opener=None):
        self.offline, self.fixtures, self.cache = offline, fixtures, cache
        self.today = today or dt.date.today()
        self.opener = opener or self._urlopen
        self.log: dict = {}
        self._memo: dict = {}

    @staticmethod
    def _urlopen(url: str) -> bytes:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=TIMEOUT) as r:
            return r.read()

    def _url(self, src: Source) -> str:
        return _treasury_url(self.today) if src.id == "treasury:curve" else src.url

    def _read(self, path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def get(self, sid: str):
        """The parsed data of source `sid`, or None when every route failed (see the module doc)."""
        if sid in self._memo:
            return self._memo[sid]
        src = BY_ID[sid]
        data, how, err = None, "missing", ""
        routes = []
        if self.fixtures:
            routes.append(("fixture", lambda: src.parser(self._read(os.path.join(self.fixtures, src.fixture)))))
        else:
            if not self.offline and self._url(src):
                routes.append(("network", lambda: self._fetch(src)))
            if self._url(src):
                routes.append(("cache", lambda: src.parser(self._read(os.path.join(self.cache, src.fixture)))))
        if src.local is not None:
            routes.append(("local", src.local))
        for name, fn in routes:
            try:
                got = fn()
                if got is None or len(got) == 0:
                    raise ValueError("empty")
                data, how = got, name
                break
            except Exception as e:  # noqa: BLE001 - every route may fail; the next one is tried
                err = err or f"{name}: {e.__class__.__name__}: {str(e)[:120]}"
        newest = None
        if data is not None:
            idx = data["when"] if isinstance(data, pd.DataFrame) and "when" in data.columns else data.index
            newest = str(pd.Timestamp(max(idx)).date()) if len(idx) else None
        self.log[sid] = {"id": sid, "name": src.name, "from": how, "newest": newest, "rows": 0 if data is None else int(len(data)),
                         "error": "" if how in ("network", "fixture") else err, "note": src.note}
        self._memo[sid] = data
        return data

    def prefetch(self, ids=None, workers: int = 6) -> None:
        """Fetch many sources at once (network latency, not CPU, is the cost); results land in the memo."""
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(self.get, ids or list(BY_ID)))

    def _fetch(self, src: Source):
        raw = self.opener(self._url(src))
        text = raw.decode("utf-8", "replace")
        data = src.parser(text)
        if len(data) == 0 and src.id == "treasury:curve":            # early January: this year's file is still empty
            text = self.opener(_treasury_url(self.today.replace(year=self.today.year - 1))).decode("utf-8", "replace")
            data = src.parser(text)
        if len(data):
            try:
                os.makedirs(self.cache, exist_ok=True)
                tmp = os.path.join(self.cache, src.fixture + ".tmp")
                with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(text)
                os.replace(tmp, os.path.join(self.cache, src.fixture))
            except OSError:
                pass
        return data
