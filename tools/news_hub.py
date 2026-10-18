"""News hub: every scheduled release and headline that moves the US dollar and index futures, from free sources,
scored for USD impact and mapped onto the bot's killzones and news blackout.  Output: data/news/hub.json.

    python tools/news_hub.py --out data/news/hub.json [--days 10] [--past 2] [--offline] [--now 2026-10-20T09:00]
    python -m tools.news_hub --selftest           # fixtures under tests/fixtures/news/, no network

Calendar sources (each optional; a failure is logged in hub.json "sources" and the rest still builds)
  ForexFactory weekly JSON (this + next week)     nfs.faireconomy.media/ff_calendar_thisweek.json | _nextweek.json
  Fed FOMC meeting calendar                      federalreserve.gov/monetarypolicy/fomccalendars.htm (data/build_news.py parser)
  BLS release schedule                           bls.gov/schedule/news_release/   (CPI, jobs report, PPI, JOLTS, ...)
  BEA release schedule                           bea.gov/news/schedule           (GDP, PCE / personal income, trade)
  Treasury auctions (announced)                  treasurydirect.gov/TA_WS/securities/announced?format=json
  Fed speeches + press releases (RSS)            federalreserve.gov/feeds/speeches.xml | press_all.xml
  Engine calendar (always available, offline)    engine/calendar_week.py SCHEDULE + data/news/events.csv + ff_archive.csv
Headline sources: Fed, BLS, BEA, Treasury, White House, MarketWatch, CNBC, FXStreet, Investing.com, ForexLive (RSS).

Every raw fetch is saved to data/news/raw/<slug>.<ext>; --offline rebuilds from those files (or from the
data/news/ff_thisweek.json snapshot and the engine calendar when nothing else exists).  No API keys, no paid services,
plain GETs with a UA and a 15 s timeout, public data only.

hub_for_dashboard(path) returns the compact version tools/build_web_dashboard.py embeds in data.json.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import email.utils
import html as html_mod
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

NEWS_DIR = os.path.join(ROOT, "data", "news")
RAW_DIR = os.path.join(NEWS_DIR, "raw")
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "news")
DEFAULT_OUT = os.path.join(NEWS_DIR, "hub.json")
ET_TZ = ZoneInfo("America/New_York")
# same browser UA as engine/news.py and data/build_news.py (bls.gov answers 403 to bare scripts); one GET per source per run
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
TIMEOUT = 15
MAX_RAW_BYTES = 3_000_000          # a raw file bigger than this is not kept (the pages we read are 20-400 KB)
HEADLINE_HOURS = 48
HEADLINE_MAX = 80

# ------------------------------------------------------------------ bot rules (engine/model.py DEFAULTS when importable)
BOT = {"news_before_min": 15, "news_after_min": 30, "fomc_pm_off": True, "news_flatten_min": 5,
       "entry_windows": [[570, 690], [810, 930]], "flat_mod": 955, "fomc_pm_cutoff": 780}


def bot_params():
    p = dict(BOT)
    try:
        from engine.model import DEFAULTS
        p.update({k: DEFAULTS[k] for k in ("news_before_min", "news_after_min", "fomc_pm_off", "news_flatten_min",
                                           "entry_windows", "flat_mod") if k in DEFAULTS})
    except Exception:
        pass
    return p


# ------------------------------------------------------------------ sources
# calendar sources: slug, name, urls (first that answers wins), ext, parser name, fallback files for --offline
CAL_SOURCES = [
    {"slug": "ff_thisweek", "name": "ForexFactory this week", "ext": "json", "parser": "ff",
     "urls": ["https://nfs.faireconomy.media/ff_calendar_thisweek.json"],
     "fallback": [os.path.join(NEWS_DIR, "ff_thisweek.json")]},
    {"slug": "ff_nextweek", "name": "ForexFactory next week", "ext": "json", "parser": "ff",
     "urls": ["https://nfs.faireconomy.media/ff_calendar_nextweek.json"]},
    {"slug": "fomc_calendar", "name": "Fed FOMC calendar", "ext": "htm", "parser": "fomc",
     "urls": ["https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"]},
    {"slug": "bls_schedule", "name": "BLS release schedule", "ext": "htm", "parser": "bls",
     "urls": ["https://www.bls.gov/schedule/news_release/"]},
    {"slug": "bea_schedule", "name": "BEA release schedule", "ext": "htm", "parser": "bea",
     "urls": ["https://www.bea.gov/news/schedule"]},
    {"slug": "treasury_auctions", "name": "Treasury auctions (TreasuryDirect)", "ext": "json", "parser": "treasury",
     "urls": ["https://www.treasurydirect.gov/TA_WS/securities/announced?format=json&pagesize=50"]},
    {"slug": "fed_speeches", "name": "Fed speeches (RSS)", "ext": "xml", "parser": "fed_speeches",
     "urls": ["https://www.federalreserve.gov/feeds/speeches.xml"]},
    {"slug": "fed_press", "name": "Fed press releases (RSS)", "ext": "xml", "parser": "fed_press",
     "urls": ["https://www.federalreserve.gov/feeds/press_all.xml"]},
]
# headline feeds: slug, display name, urls, source weight added to the relevance score
HEADLINE_FEEDS = [
    {"slug": "fed_press", "name": "Federal Reserve", "urls": ["https://www.federalreserve.gov/feeds/press_all.xml"], "weight": 20},
    {"slug": "fed_speeches", "name": "Fed speeches", "urls": ["https://www.federalreserve.gov/feeds/speeches.xml"], "weight": 20},
    {"slug": "bls_rss", "name": "BLS", "urls": ["https://www.bls.gov/feed/news_release/bls.rss", "https://www.bls.gov/feed/bls_latest.rss"], "weight": 15},
    {"slug": "bea_rss", "name": "BEA", "urls": ["https://apps.bea.gov/rss/rss.xml"], "weight": 15},
    {"slug": "treasury_press", "name": "US Treasury",
     "urls": ["https://home.treasury.gov/news/press-releases/feed", "https://home.treasury.gov/rss/press.xml"], "weight": 10},
    {"slug": "whitehouse", "name": "White House", "urls": ["https://www.whitehouse.gov/news/feed/", "https://www.whitehouse.gov/feed/"], "weight": 5},
    {"slug": "mw_top", "name": "MarketWatch", "urls": ["https://feeds.content.dowjones.io/public/rss/mw_topstories"], "weight": 0},
    {"slug": "mw_pulse", "name": "MarketWatch Pulse", "urls": ["https://feeds.content.dowjones.io/public/rss/mw_marketpulse"], "weight": 0},
    {"slug": "cnbc_top", "name": "CNBC", "urls": ["https://www.cnbc.com/id/100003114/device/rss/rss.html"], "weight": 0},
    {"slug": "cnbc_markets", "name": "CNBC Markets", "urls": ["https://www.cnbc.com/id/20910258/device/rss/rss.html"], "weight": 0},
    {"slug": "fxstreet", "name": "FXStreet", "urls": ["https://www.fxstreet.com/rss/news"], "weight": 5},
    {"slug": "investing", "name": "Investing.com", "urls": ["https://www.investing.com/rss/news_25.rss"], "weight": 0},
    {"slug": "forexlive", "name": "ForexLive", "urls": ["https://www.forexlive.com/feed"], "weight": 5},
]

# ------------------------------------------------------------------ event kinds, USD impact scores
# first match wins (lower-cased title); order matters
KINDS = [
    ("holiday", ["bank holiday", "market holiday", "early close"]),
    ("fomc_pc", ["press conference", "fomc press"]),
    ("fomc_min", ["fomc minutes", "fomc meeting minutes", "meeting minutes", "minutes of the federal open market"]),
    ("fomc", ["fomc statement", "federal funds rate", "fomc rate", "rate decision", "fomc economic projections",
              "fomc meeting", "interest rate decision", "monetary policy statement"]),
    ("treasury_sec", ["treasury sec", "bessent"]),
    ("potus", ["president trump", "trump speaks", "white house press"]),
    ("fed_chair", ["fed chair", "chair powell", "chairman powell", "chair warsh", "chairman warsh", "powell speaks",
                   "warsh speaks", "powell testif", "warsh testif", "fed chairman"]),
    ("fed_speaker", ["fomc member", "fed governor", "fed president", "fed vice chair", "vice chair", "governor ", "fed's ",
                     "speaks", "speech", "testif", "remarks"]),
    ("adp", ["adp "]),
    ("cpi", ["cpi", "consumer price"]),
    ("nfp", ["non-farm", "nonfarm", "payroll", "employment situation", "unemployment rate", "average hourly earnings",
             "jobs report"]),
    ("pce", ["pce", "personal income", "personal consumption", "personal spending"]),
    ("gdp", ["gdp", "gross domestic"]),
    ("ppi", ["ppi", "producer price"]),
    ("retail", ["retail sales"]),
    ("ism_m", ["ism manufacturing"]),
    ("ism_s", ["ism services", "ism non-manufacturing"]),
    ("claims", ["unemployment claims", "jobless claims", "initial claims"]),
    ("jolts", ["jolts", "job openings"]),
    ("umich", ["umich", "uom ", "michigan"]),
    ("cb", ["cb consumer confidence", "consumer confidence"]),
    ("eci", ["employment cost"]),
    ("productivity", ["productivity"]),
    ("real_earnings", ["real earnings"]),
    ("import_prices", ["import price", "import and export price", "u.s. import"]),
    ("trade", ["trade balance", "international trade", "goods trade"]),
    ("pmi", ["pmi"]),
    ("durables", ["durable"]),
    ("housing", ["housing starts", "building permits", "home sales", "nahb", "pending home"]),
    ("auction_30y", ["30-year bond", "30-y bond", "30y bond"]),
    ("auction_10y", ["10-year note", "10-y note", "10y note", "10-y bond", "10y bond"]),
    ("auction_20y", ["20-year bond", "20-y bond"]),
    ("auction_other", ["-year note", "-year bond", "-year tips", "tips auction", "note auction", "bond auction", "auction"]),
    ("regional_fed", ["philly fed", "empire state", "richmond", "kansas city fed", "dallas fed", "chicago fed", "beige book"]),
]
USD_SCORE = {
    "fomc": 100, "fomc_pc": 90, "fomc_min": 60, "cpi": 95, "nfp": 95, "pce": 80, "gdp": 70, "ism_m": 65, "ism_s": 65,
    "retail": 65, "ppi": 55, "claims": 45, "jolts": 50, "adp": 50, "umich": 40, "cb": 45, "eci": 40, "productivity": 25,
    "real_earnings": 15, "import_prices": 20, "trade": 20, "pmi": 35, "durables": 30, "housing": 20, "regional_fed": 25,
    "auction_30y": 40, "auction_10y": 40, "auction_20y": 30, "auction_other": 20, "fed_chair": 70, "fed_speaker": 35,
    "potus": 45, "treasury_sec": 35, "holiday": 0,
}
IMPACT_SCORE = {"high": 60, "medium": 35, "low": 15, "holiday": 0}
KIND_LABEL = {
    "fomc": "FOMC decision", "fomc_pc": "FOMC press conference", "fomc_min": "FOMC minutes", "cpi": "CPI", "nfp": "Jobs report",
    "pce": "PCE", "gdp": "GDP", "ism_m": "ISM Manufacturing", "ism_s": "ISM Services", "retail": "Retail Sales", "ppi": "PPI",
    "claims": "Jobless claims", "jolts": "JOLTS", "adp": "ADP", "umich": "UMich sentiment", "cb": "CB confidence",
    "eci": "Employment Cost Index", "productivity": "Productivity", "real_earnings": "Real earnings",
    "import_prices": "Import prices", "trade": "Trade balance", "pmi": "PMI", "durables": "Durable goods", "housing": "Housing",
    "regional_fed": "Regional Fed survey", "auction_30y": "30-yr auction", "auction_10y": "10-yr auction",
    "auction_20y": "20-yr auction", "auction_other": "Treasury auction", "fed_chair": "Fed chair", "fed_speaker": "Fed speaker",
    "potus": "President", "treasury_sec": "Treasury Secretary", "holiday": "Holiday", "other": "Other",
}
# above-forecast actual = USD bullish for these kinds; USD bearish for INVERSE kinds (claims, unemployment rate)
USD_UP_ON_BEAT = {"cpi", "ppi", "nfp", "pce", "gdp", "retail", "ism_m", "ism_s", "jolts", "adp", "umich", "cb", "pmi",
                  "durables", "housing", "eci", "import_prices", "regional_fed", "productivity"}
INVERSE = {"claims"}
# a single data release can appear as several FF lines (CPI m/m, Core CPI m/m, ...): same release key per day for these
RELEASE_KINDS = set(USD_SCORE) - {"fed_chair", "fed_speaker", "potus", "treasury_sec", "auction_other", "holiday"}

# headline relevance keywords -> points (summed, capped at 100) and tone hints
REL = [
    (30, r"\bfed\b|\bfomc\b|powell|warsh|rate (cut|hike|decision|path)|interest rates?"),
    (25, r"inflation|\bcpi\b|\bpce\b|payrolls?|jobs report|nonfarm|non-farm|unemployment"),
    (20, r"yields?|treasur(y|ies)|\bdollar\b|\busd\b|tariffs?|recession|\bgdp\b|\bbond market\b"),
    (15, r"nasdaq|nvidia|\bapple\b|microsoft|\bvix\b|retail sales|\bism\b|jobless claims|auction|earnings|\bqqq\b"),
    (10, r"stocks?|s&p|wall street|futures|equities|\bdow\b|tech"),
    (10, r"shutdown|debt ceiling|default|downgrade|\bwar\b|missile|attack|sanction|china|\boil\b"),
]
REL_RE = [(pts, re.compile(rx, re.I)) for pts, rx in REL]
TONE = [
    ("hawkish", r"hawkish|rate hike|hikes? rates|higher for longer|hot(ter)? (inflation|cpi|print)|inflation (rises|jumps|accelerates|surges|climbs|heats)|"
                r"yields? (rise|jump|surge|climb|spike)|dollar (rises|gains|strengthens|climbs|jumps|surges)|strong(er)? (jobs|payrolls|hiring)|"
                r"fewer cuts|no cut|hold(s)? rates|sticky inflation|prices (rise|jump|surge)"),
    ("dovish", r"dovish|rate cut|cuts? rates|cut(s|ting)? interest|inflation (cools|slows|eases|falls|drops)|yields? (fall|drop|slide|tumble|slip)|"
               r"dollar (falls|weakens|slides|drops|slips)|weak(er)? (jobs|payrolls|hiring)|jobs miss|unemployment (rises|jumps|climbs)|"
               r"layoffs|easing|more cuts|lower rates|slowing economy"),
    ("risk-off", r"sell-?off|\bplunge|\btumble|\bslump|\bcrash|\brout\b|\bfears?\b|\bpanic|\bwar\b|\battack|missile|tariff|shutdown|"
                 r"\bdefault|downgrade|recession|\bslides?\b|\bsinks?\b|\bdrops?\b|\bfalls?\b|\blose|\blosses|\bworst\b|warning|crisis|turmoil"),
    ("risk-on", r"rall(y|ies)|record high|all-time high|\bsurge|\bsoar|\bgains?\b|rebound|\bjumps?\b|\bclimbs?\b|\brises?\b|\bbest\b|optimism|"
                r"\bboost|\bbeats?\b|upbeat|strong earnings|\bbull"),
]
TONE_RE = [(name, re.compile(rx, re.I)) for name, rx in TONE]
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                                      "october", "november", "december"], 1)}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
TAG_RE = re.compile(r"<[^>]+>")
DATE_RE = re.compile(r"(?:(?:mon|tues?|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?|sun)(?:day)?\.?,?\s+)?"
                     r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", re.I)
TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\s*([ap])\.?m\.?", re.I)
NUM_RE = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")


# ------------------------------------------------------------------ small helpers
def _text(s: str) -> str:
    return html_mod.unescape(TAG_RE.sub(" ", s or "")).replace("\xa0", " ").strip()


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def et_dt(t: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET_TZ)


def _mod(x: dt.datetime) -> int:
    return x.hour * 60 + x.minute


def classify(title: str) -> str:
    low = f" {(title or '').lower()} "
    for kind, frags in KINDS:
        if any(f in low for f in frags):
            return kind
    return "other"


def usd_score(kind: str, impact: str | None) -> int:
    base = USD_SCORE.get(kind)
    imp = (impact or "").lower()
    if base is None:
        base = IMPACT_SCORE.get(imp, 15)
    if imp == "high":
        base = max(base, 60)
    return int(max(0, min(100, base)))


def impact_from_score(score: int) -> str:
    return "high" if score >= 65 else "medium" if score >= 40 else "low"


def _num(s):
    if s is None:
        return None
    m = NUM_RE.search(str(s))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def surprise(kind: str, actual, forecast, title: str = ""):
    """(actual - forecast, 'above'|'below'|'inline', USD hint) when both are numeric."""
    a, f = _num(actual), _num(forecast)
    if a is None or f is None:
        return None, None, None
    d = round(a - f, 3)
    side = "inline" if abs(d) < 1e-9 else "above" if d > 0 else "below"
    hint = None
    inverse = kind in INVERSE or "unemployment rate" in (title or "").lower()
    if side != "inline" and (kind in USD_UP_ON_BEAT or inverse):
        up = (d > 0) != inverse
        hint = "USD+" if up else "USD-"
    return d, side, hint


def relevance(title: str, source_weight: int = 0) -> int:
    pts = source_weight + sum(p for p, rx in REL_RE if rx.search(title or ""))
    return int(max(0, min(100, pts)))


def tone(title: str) -> str:
    t = title or ""
    for name, rx in TONE_RE:
        if rx.search(t):
            return name
    return "neutral"


def parse_when(date_text: str, time_text: str | None, default_hhmm=(8, 30)) -> dt.datetime | None:
    """'Tuesday, October 20, 2026' + '08:30 AM' -> aware ET datetime (default time when none is given)."""
    m = DATE_RE.search(date_text or "")
    if not m:
        return None
    mon = MONTHS.get(m.group(1).lower()) or MONTHS.get(m.group(1).lower()[:3])
    if not mon:
        return None
    hh, mm = default_hhmm
    tm = TIME_RE.search(time_text or "")
    if tm:
        hh, mm = int(tm.group(1)) % 12, int(tm.group(2))
        if tm.group(3).lower() == "p":
            hh += 12
    try:
        return dt.datetime(int(m.group(3)), mon, int(m.group(2)), hh, mm, tzinfo=ET_TZ)
    except ValueError:
        return None


def parse_rfc_or_iso(s: str) -> int | None:
    s = _ws(s or "")
    if not s:
        return None
    try:
        return int(email.utils.parsedate_to_datetime(s).timestamp())
    except Exception:
        pass
    try:
        x = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if x.tzinfo is None:
            x = x.replace(tzinfo=dt.timezone.utc)
        return int(x.timestamp())
    except Exception:
        return None


def _rows(html: str):
    """Table rows of an HTML page as lists of cell texts (tolerant: regex, no parser dependency)."""
    out = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", html or "", re.S | re.I):
        cells = [_ws(_text(c)) for c in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row, re.S | re.I)]
        links = re.findall(r'href="([^"]+)"', row, re.I)
        if cells:
            out.append((cells, links[0] if links else None))
    return out


# ------------------------------------------------------------------ fetch + raw cache
def http_get(url: str, timeout: int = TIMEOUT) -> bytes:
    headers = {"User-Agent": UA, "Accept": "application/json, application/xml, text/xml, text/html;q=0.9, */*;q=0.8"}
    try:
        import requests
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.content
    except ImportError:
        import urllib.request
        return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout).read()


def fetch(src: dict, offline: bool, raw_dir: str = RAW_DIR, save_raw: bool = True):
    """(raw bytes or None, source info). Online: first URL that answers, saved to raw_dir/<slug>.<ext>.
    Offline (or after a failed fetch): the saved raw file, else the source's fallback files."""
    ext = src.get("ext", "xml")
    path = os.path.join(raw_dir, f"{src['slug']}.{ext}")
    info = {"name": src["name"], "slug": src["slug"], "url": src["urls"][0], "ok": False, "n": 0}
    raw = None
    if not offline:
        errs = []
        for url in src["urls"]:
            try:
                raw = http_get(url)
                if not raw or len(raw) < 20:
                    raise ValueError("empty response")
                info["url"] = url
                info["fetched"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
                break
            except Exception as e:                      # noqa: BLE001 - every source is optional
                raw = None
                errs.append(f"{type(e).__name__}: {str(e)[:110]}")
        if raw is None:
            info["error"] = " | ".join(errs)[:400]
        elif save_raw and len(raw) <= MAX_RAW_BYTES:
            try:
                os.makedirs(raw_dir, exist_ok=True)
                with open(path, "wb") as fh:
                    fh.write(raw)
            except OSError as e:
                info["raw_save_error"] = str(e)[:120]
    if raw is None:
        for p in [path] + list(src.get("fallback", [])):
            if os.path.exists(p):
                try:
                    with open(p, "rb") as fh:
                        raw = fh.read()
                    info["cached"] = os.path.relpath(p, ROOT).replace(os.sep, "/")
                    info["cached_age_h"] = round((time.time() - os.path.getmtime(p)) / 3600, 1)
                    break
                except OSError:
                    continue
    return raw, info


# ------------------------------------------------------------------ calendar parsers: list of raw events
# raw event = {t, title, country, impact?, kind?, forecast, previous, actual, source, url}
def parse_ff(raw: bytes, source="ForexFactory"):
    out = []
    for e in json.loads(raw.decode("utf-8", "ignore") or "[]"):
        try:
            t = int(dt.datetime.fromisoformat(e["date"]).timestamp())
        except Exception:
            continue
        ccy, imp = e.get("country", ""), (e.get("impact") or "").lower()
        title = e.get("title", "")
        kind = classify(title)
        fed_low = imp == "low" and kind in ("fed_chair", "fed_speaker", "treasury_sec", "potus", "fomc_min")
        if ccy != "USD" or not (imp in ("high", "medium", "holiday") or fed_low):
            continue
        out.append({"t": t, "title": title, "country": ccy, "impact": imp, "kind": kind, "forecast": e.get("forecast", ""),
                    "previous": e.get("previous", ""), "actual": e.get("actual", ""), "source": source,
                    "url": "https://www.forexfactory.com/calendar"})
    return out


def parse_fomc_html(html: str):
    """(date, has_projections) pairs from the Fed's FOMC calendar page. Reuses data/build_news.py when importable."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("build_news", os.path.join(ROOT, "data", "build_news.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "parse_fomc_html"):
            return mod.parse_fomc_html(html)
    except Exception:
        pass
    out = []
    parts = re.split(r"(\d{4}) FOMC Meetings", html)
    for k in range(1, len(parts) - 1, 2):
        year, body = int(parts[k]), parts[k + 1]
        for mon, day in re.findall(r'fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<', body, re.S):
            mon, day = mon.strip(), day.strip()
            if "notation" in day.lower() or "unscheduled" in day.lower() or "cancel" in day.lower():
                continue
            nums = re.findall(r"\d+", day)
            last_mon = mon.split("/")[-1].strip().lower()
            m = MONTHS.get(last_mon) or MONTHS.get(last_mon[:3])
            if not nums or not m:
                continue
            out.append((f"{year}-{m:02d}-{int(nums[-1]):02d}", "*" in day))
    return sorted(set(out))


def parse_fomc(raw: bytes, source="Federal Reserve"):
    out = []
    for date, proj in parse_fomc_html(raw.decode("utf-8", "ignore")):
        y, m, d = map(int, date.split("-"))
        t0 = dt.datetime(y, m, d, 14, 0, tzinfo=ET_TZ)
        out.append({"t": int(t0.timestamp()), "title": "FOMC rate decision" + (" + projections" if proj else ""), "country": "USD",
                    "impact": "high", "kind": "fomc", "source": source, "url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"})
        out.append({"t": int((t0 + dt.timedelta(minutes=30)).timestamp()), "title": "FOMC press conference", "country": "USD",
                    "impact": "high", "kind": "fomc_pc", "source": source, "url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"})
    return out


BLS_KEEP = ["consumer price index", "employment situation", "producer price index", "job openings", "real earnings",
            "import", "employment cost", "productivity"]
BEA_KEEP = ["gross domestic product", "personal income", "trade", "pce"]


def _schedule_rows(html: str, keep, source, base_url, default_hhmm=(8, 30)):
    out = []
    for cells, link in _rows(html):
        text = " | ".join(cells)
        low = text.lower()
        if not any(k in low for k in keep):
            continue
        when = parse_when(text, text, default_hhmm)
        if not when:
            continue
        title = next((c for c in cells if any(k in c.lower() for k in keep)), cells[-1])
        if DATE_RE.search(title) and len(cells) > 1:      # a single-cell row: keep only the release name part
            title = DATE_RE.sub("", title)
        title = _ws(TIME_RE.sub("", title)).strip(" -|,")
        url = link if (link or "").startswith("http") else (base_url + link if link else base_url)
        out.append({"t": int(when.timestamp()), "title": title, "country": "USD", "kind": classify(title), "source": source, "url": url})
    return out


def parse_bls(raw: bytes, source="BLS"):
    return _schedule_rows(raw.decode("utf-8", "ignore"), BLS_KEEP, source, "https://www.bls.gov")


def parse_bea(raw: bytes, source="BEA"):
    return _schedule_rows(raw.decode("utf-8", "ignore"), BEA_KEEP, source, "https://www.bea.gov")


def parse_treasury(raw: bytes, source="TreasuryDirect"):
    out = []
    data = json.loads(raw.decode("utf-8", "ignore") or "[]")
    if isinstance(data, dict):
        data = data.get("securities") or data.get("data") or []
    for s in data:
        typ = str(s.get("securityType") or s.get("type") or "")
        if typ.lower() not in ("note", "bond", "tips"):
            continue                                      # bills and FRNs are noise for NQ
        ad = str(s.get("auctionDate") or "")[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ad):
            continue
        y, m, d = map(int, ad.split("-"))
        term = str(s.get("securityTerm") or s.get("originalSecurityTerm") or "").strip()
        amt = _num(s.get("offeringAmount"))
        title = f"{term} {typ} auction" + (f" (${amt / 1e9:.0f}bn)" if amt else "") + (" reopening" if str(s.get("reopening", "")).lower() == "yes" else "")
        out.append({"t": int(dt.datetime(y, m, d, 13, 0, tzinfo=ET_TZ).timestamp()), "title": title, "country": "USD",
                    "kind": classify(title), "source": source,
                    "url": "https://www.treasurydirect.gov/auctions/upcoming/", "cusip": s.get("cusip")})
    return out


def parse_rss(raw: bytes):
    """[{title, link, t}] from RSS 2.0 or Atom. Titles are plain text."""
    out = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        try:
            root = ET.fromstring(raw.decode("utf-8", "ignore").encode("utf-8"))
        except ET.ParseError:
            return out
    for it in root.iter():
        tag = it.tag.rsplit("}", 1)[-1].lower()
        if tag not in ("item", "entry"):
            continue
        title = link = date = None
        for ch in it:
            ct = ch.tag.rsplit("}", 1)[-1].lower()
            if ct == "title":
                title = _ws(_text(ch.text or ""))
            elif ct == "link":
                link = (ch.text or "").strip() or ch.attrib.get("href", "")
            elif ct in ("pubdate", "date", "published", "updated", "issued") and not date:
                date = ch.text
        if title:
            out.append({"title": title, "link": link or "", "t": parse_rfc_or_iso(date) or 0})
    return out


def parse_fed_speeches(raw: bytes, source="Fed speeches"):
    out = []
    for it in parse_rss(raw):
        low = it["title"].lower()
        kind = "fed_chair" if (("chair" in low and "vice" not in low) or "powell" in low or "warsh" in low) else "fed_speaker"
        if it["t"]:
            out.append({"t": it["t"], "title": it["title"], "country": "USD", "kind": kind, "source": source, "url": it["link"],
                        "actual": "delivered"})
    return out


def parse_fed_press(raw: bytes, source="Federal Reserve"):
    """Only the press releases that are scheduled market events (FOMC statement, minutes); the rest are headlines."""
    out = []
    for it in parse_rss(raw):
        low = it["title"].lower()
        if "fomc statement" in low:
            kind, title = "fomc", "FOMC statement released"
        elif "minutes of the federal open market" in low or "fomc minutes" in low:
            kind, title = "fomc_min", "FOMC minutes released"
        else:
            continue
        if it["t"]:
            out.append({"t": it["t"], "title": title, "country": "USD", "impact": "high", "kind": kind, "source": source,
                        "url": it["link"], "actual": "released"})
    return out


PARSERS = {"ff": parse_ff, "fomc": parse_fomc, "bls": parse_bls, "bea": parse_bea, "treasury": parse_treasury,
           "fed_speeches": parse_fed_speeches, "fed_press": parse_fed_press}


def engine_calendar(start: dt.date, end: dt.date):
    """engine/calendar_week.py SCHEDULE + data/news/events.csv + ff_archive.csv: always available offline."""
    from engine import calendar_week as cw
    out = []
    for r in cw.collect(start, end, "low", use_feed=False):
        y, m, d = map(int, r["date"].split("-"))
        hh, mm = map(int, str(r["time_et"])[:5].split(":"))
        out.append({"t": int(dt.datetime(y, m, d, hh, mm, tzinfo=ET_TZ).timestamp()), "title": r["event"], "country": "USD",
                    "impact": r["impact"], "kind": classify(r["event"]), "source": "engine calendar (" + r["source"] + ")",
                    "url": "", "confidence": r.get("confidence")})
    return out


# ------------------------------------------------------------------ normalise, merge, score
SOURCE_RANK = {"ForexFactory": 0, "Federal Reserve": 1, "Fed speeches": 1, "BLS": 1, "BEA": 1, "TreasuryDirect": 1}


def _rank(ev):
    return SOURCE_RANK.get(ev.get("source", "").split(" (")[0], 2)


def _release_key(ev, date):
    kind = ev["kind"]
    if kind in RELEASE_KINDS:
        return (date, kind)
    return (date, kind, et_dt(ev["t"]).strftime("%H:%M"), (ev.get("title") or "")[:24].lower())


def normalise(ev: dict, p: dict) -> dict:
    x = et_dt(ev["t"])
    kind = ev.get("kind") or classify(ev.get("title", ""))
    score = usd_score(kind, ev.get("impact"))
    impact = (ev.get("impact") or "").lower() or impact_from_score(score)
    if kind == "holiday":
        impact, score = "holiday", 0
    hi = impact == "high"
    b0 = x - dt.timedelta(minutes=p["news_before_min"]) if hi else None
    b1 = x + dt.timedelta(minutes=p["news_after_min"]) if hi else None
    m = _mod(x)
    kz = [i for i, (a, z) in enumerate(p["entry_windows"]) if a <= m < z]
    kz_hit = hi and any(_mod(b0) < z and _mod(b1) > a for a, z in p["entry_windows"]) and b0.date() == x.date()
    sp, side, hint = surprise(kind, ev.get("actual"), ev.get("forecast"), ev.get("title", ""))
    return {"t": int(ev["t"]), "date": x.strftime("%Y-%m-%d"), "time_et": x.strftime("%H:%M"), "weekday": x.strftime("%a"),
            "label": x.strftime("%a %b %d %H:%M"), "title": ev.get("title", ""), "kind": kind, "kind_label": KIND_LABEL.get(kind, "Other"),
            "impact": impact, "usd_score": score, "country": ev.get("country", "USD"),
            "forecast": ev.get("forecast", "") or "", "previous": ev.get("previous", "") or "", "actual": ev.get("actual", "") or "",
            "surprise": sp, "surprise_side": side, "usd_hint": hint, "source": ev.get("source", ""), "sources": [ev.get("source", "")],
            "url": ev.get("url", "") or "", "blackout": bool(hi), "blackout_start": b0.strftime("%H:%M") if hi else None,
            "blackout_end": b1.strftime("%H:%M") if hi else None, "blackout_start_t": int(b0.timestamp()) if hi else None,
            "blackout_end_t": int(b1.timestamp()) if hi else None, "in_killzone": bool(kz), "killzone": ["AM", "PM"][kz[0]] if kz else None,
            "blackout_hits_killzone": bool(kz_hit), **({"confidence": ev["confidence"]} if ev.get("confidence") else {})}


def merge_events(raw_events, p, start_t, end_t):
    """Normalise, window, dedupe across sources (ForexFactory > official > engine calendar), sort."""
    evs = [normalise(e, p) for e in raw_events if e.get("t") and start_t <= int(e["t"]) < end_t and e.get("country", "USD") == "USD"]
    evs.sort(key=lambda e: (_rank(e), e["t"]))
    kept, by_key = [], {}
    for e in evs:
        k = _release_key(e, e["date"])
        if k in by_key:
            keep = by_key[k]
            same_source = keep["source"].split(" (")[0] == e["source"].split(" (")[0]
            if same_source and e["kind"] in RELEASE_KINDS and e["title"] != keep["title"] and e["source"].startswith("ForexFactory"):
                kept.append(e)                             # CPI m/m + Core CPI m/m ...: separate FF lines of one release
                continue
            if e["source"] not in keep["sources"]:
                keep["sources"].append(e["source"])
            if not keep["url"] and e["url"]:
                keep["url"] = e["url"]
            if e["impact"] == "high" and keep["impact"] != "high":      # any source calling it high = the bot blacks out
                keep.update(normalise({**e, "title": keep["title"], "forecast": keep["forecast"], "previous": keep["previous"],
                                       "actual": keep["actual"], "source": keep["source"], "url": keep["url"] or e["url"]}, p),
                            sources=keep["sources"])
            for f in ("actual", "forecast", "previous"):
                if not keep[f] and e.get(f):
                    keep[f] = e[f]
            continue
        by_key[k] = e
        kept.append(e)
    kept.sort(key=lambda e: (e["t"], -e["usd_score"], e["title"]))
    return kept


# ------------------------------------------------------------------ headlines
def build_headlines(items_by_feed, now: int, hours=HEADLINE_HOURS, limit=HEADLINE_MAX):
    seen, out = set(), []
    cutoff = now - hours * 3600
    for feed, items in items_by_feed:
        for it in items:
            t = it.get("t") or 0
            if t and (t < cutoff or t > now + 3 * 3600):
                continue
            key = re.sub(r"[^a-z0-9]+", " ", it["title"].lower()).strip()[:90]
            if not key or key in seen:
                continue
            seen.add(key)
            out.append({"t": int(t), "time_et": et_dt(t).strftime("%a %H:%M") if t else "", "title": it["title"][:220],
                        "source": feed["name"], "url": it.get("link", "")[:400], "score": relevance(it["title"], feed.get("weight", 0)),
                        "tone": tone(it["title"])})
    out.sort(key=lambda h: (-h["score"], -h["t"]))
    out = out[:limit]
    out.sort(key=lambda h: -h["t"])
    return out


# ------------------------------------------------------------------ days: "what it means for the bot"
def _merge_windows(wins):
    """[(start_min, end_min, label)] -> merged, sorted, labels joined."""
    wins = sorted(wins)
    out = []
    for a, b, lab in wins:
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b), out[-1][2] + ([lab] if lab not in out[-1][2] else []))
        else:
            out.append((a, b, [lab]))
    return out


def _hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def _short(e):
    return KIND_LABEL.get(e["kind"], "") if e["kind"] in KIND_LABEL and e["kind"] != "other" else re.sub(r"\s*(m/m|y/y|q/q)$", "", e["title"])[:30]


def day_rows(events, start: dt.date, end: dt.date, today: dt.date, p: dict, notes_by_day=None):
    notes_by_day = notes_by_day or {}
    by_day = {}
    for e in events:
        by_day.setdefault(e["date"], []).append(e)
    rows = []
    d = start
    while d <= end:
        ds = d.isoformat()
        evs = by_day.get(ds, [])
        if d.weekday() >= 5 and not evs:
            d += dt.timedelta(days=1)
            continue
        hi = [e for e in evs if e["impact"] == "high"]
        fomc = any(e["kind"] in ("fomc", "fomc_pc") for e in evs)
        holiday = next((e for e in evs if e["kind"] == "holiday"), None)
        wins = _merge_windows([(_mod(et_dt(e["blackout_start_t"])), _mod(et_dt(e["blackout_end_t"])), _short(e)) for e in hi
                               if e["blackout_start_t"] and et_dt(e["blackout_start_t"]).date() == d])
        blackouts = [f"{_hhmm(a)}-{_hhmm(b)} {', '.join(labs)}" for a, b, labs in wins]
        if fomc and p.get("fomc_pm_off", True):
            blackouts.append(f"{_hhmm(p.get('fomc_pm_cutoff', 780))}-16:00 FOMC afternoon: no entries")
        kz_hits = [f"{_hhmm(max(a, w0))}-{_hhmm(min(b, w1))}" for a, b, _ in wins for w0, w1 in p["entry_windows"] if a < w1 and b > w0]
        # plain-language summary
        label = d.strftime("%a %b %d")
        if holiday and not hi:
            summary = f"{label}: US holiday ({holiday['title']}). Thin trade, no bot setups expected."
        elif fomc:
            parts = [f"{_short(e)} {e['time_et']}" for e in hi if e["kind"] not in ("fomc", "fomc_pc")]
            summary = (f"{label}: FOMC day. Decision 14:00, press conference 14:30 ET. The bot takes no entries after "
                       f"{_hhmm(p.get('fomc_pm_cutoff', 780))} ET and closes anything open before 13:55; the AM killzone runs as normal.")
            if parts:
                summary += " Also high-impact: " + ", ".join(parts) + "."
        elif hi:
            parts = list(dict.fromkeys(f"{_short(e)} {e['time_et']}" for e in hi))
            summary = f"{label}: {len(parts)} high-impact release{'s' if len(parts) > 1 else ''}: " + ", ".join(parts) + ". "
            if kz_hits:
                summary += "The bot will not enter " + ", ".join(dict.fromkeys(kz_hits)) + " (blackout inside a killzone)."
            else:
                summary += "Blackout " + ", ".join(f"{_hhmm(a)}-{_hhmm(b)}" for a, b, _ in wins) + ": outside the killzones, entries are not affected."
                if any(e["time_et"] == "08:30" for e in hi):
                    summary += " Expect the 08:30 move to set up the first sweep."
        else:
            med = [e for e in evs if e["impact"] == "medium"]
            summary = f"{label}: no high-impact USD release." + (f" Medium: {', '.join(dict.fromkeys(_short(e) + ' ' + e['time_et'] for e in med[:4]))}." if med else "") + \
                      " Bot trades both killzones normally."
        if notes_by_day.get(ds):
            summary += " " + notes_by_day[ds]
        speakers = [e for e in evs if e["kind"] in ("fed_chair", "fed_speaker")]
        rows.append({"date": ds, "label": label, "weekday": d.strftime("%a"), "is_today": d == today, "past": d < today,
                     "n_events": len(evs), "n_high": len(hi), "n_medium": sum(1 for e in evs if e["impact"] == "medium"),
                     "fomc": fomc, "holiday": bool(holiday), "blackouts": blackouts, "killzone_pauses": list(dict.fromkeys(kz_hits)),
                     "fed_speakers": [e["title"] for e in speakers][:6], "usd_load": int(sum(e["usd_score"] for e in evs)),
                     "max_usd_score": max([e["usd_score"] for e in evs] or [0]), "heaviest": False, "summary": summary})
        d += dt.timedelta(days=1)
    # heaviest day per ISO week (by total USD load)
    weeks = {}
    for r in rows:
        wk = dt.date.fromisoformat(r["date"]).isocalendar()[:2]
        if r["usd_load"] > weeks.get(wk, (0, None))[0]:
            weeks[wk] = (r["usd_load"], r["date"])
    for load, ds in weeks.values():
        if load > 0:
            next(r for r in rows if r["date"] == ds)["heaviest"] = True
    return rows


def bot_now(events, now: int, p: dict):
    """Is the bot blocked right now, and what blocks it next."""
    x = et_dt(now)
    cur = [e for e in events if e["blackout"] and e["blackout_start_t"] <= now < e["blackout_end_t"]]
    fomc_today = any(e["kind"] in ("fomc", "fomc_pc") and e["date"] == x.strftime("%Y-%m-%d") for e in events)
    pm_off = bool(fomc_today and p.get("fomc_pm_off", True) and _mod(x) >= p.get("fomc_pm_cutoff", 780))
    reasons = [f"News blackout: {e['title']} at {e['time_et']} ET (until {e['blackout_end']})" for e in cur]
    if pm_off:
        reasons.append("FOMC day: no afternoon entries")
    nxt = next((e for e in events if e["blackout"] and e["blackout_start_t"] > now), None)
    return {"in_blackout": bool(reasons), "reasons": reasons, "fomc_today": fomc_today, "fomc_pm_off": pm_off,
            "next_blackout": None if not nxt else {"title": nxt["title"], "date": nxt["date"], "start": nxt["blackout_start"],
                                                   "end": nxt["blackout_end"], "start_t": nxt["blackout_start_t"], "in_s": nxt["blackout_start_t"] - now},
            "rules": {"before_min": p["news_before_min"], "after_min": p["news_after_min"], "fomc_pm_off": p.get("fomc_pm_off", True),
                      "flatten_min": p.get("news_flatten_min"), "killzones": ["09:30-11:30", "13:30-15:30"]}}


# ------------------------------------------------------------------ build
def build(days=10, past=2, offline=False, now=None, raw_dir=RAW_DIR, save_raw=True, headlines=True, log=print):
    p = bot_params()
    now = int(now or time.time())
    today = et_dt(now).date()
    start, end = today - dt.timedelta(days=past), today + dt.timedelta(days=days)
    start_t = int(dt.datetime.combine(start, dt.time.min, ET_TZ).timestamp())
    end_t = int(dt.datetime.combine(end + dt.timedelta(days=1), dt.time.min, ET_TZ).timestamp())
    sources, raw_events, notes = [], [], []

    # fetch everything in parallel: one GET per distinct source (the Fed feeds serve both the calendar and the headlines)
    jobs = {}
    for s in CAL_SOURCES + (HEADLINE_FEEDS if headlines else []):
        jobs.setdefault(s["slug"], {**s, "ext": s.get("ext", "xml")})
    fetched = {}
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch, s, offline, raw_dir, save_raw): slug for slug, s in jobs.items()}
        for fut in cf.as_completed(futs):
            slug = futs[fut]
            try:
                fetched[slug] = fut.result()
            except Exception as e:          # noqa: BLE001
                s = jobs[slug]
                fetched[slug] = (None, {"name": s["name"], "slug": slug, "url": s["urls"][0], "ok": False, "n": 0, "error": str(e)[:200]})

    def result(s):
        raw, info = fetched[s["slug"]]
        return raw, {**info, "name": s["name"]}

    for s in CAL_SOURCES:
        raw, info = result(s)
        info["kind"] = "calendar"
        if raw is not None:
            try:
                evs = PARSERS[s["parser"]](raw)
                inwin = [e for e in evs if start_t <= e["t"] < end_t]
                info.update(ok=True, n=len(inwin), n_parsed=len(evs))
                if not evs:
                    info.update(ok=False, error=(info.get("error") or "") + " no rows parsed (page layout changed?)")
                raw_events += evs
            except Exception as e:          # noqa: BLE001
                info.update(ok=False, error=f"parse: {type(e).__name__}: {str(e)[:150]}")
        elif not info.get("error"):
            info["error"] = "no raw file (run online once)" if offline else "fetch failed"
        sources.append(info)
    try:
        eng = engine_calendar(start, end)
        raw_events += eng
        sources.append({"name": "Engine calendar (calendar_week + events.csv)", "slug": "engine_calendar", "kind": "calendar", "ok": True,
                        "n": len(eng), "url": "engine/calendar_week.py"})
    except Exception as e:                  # noqa: BLE001
        sources.append({"name": "Engine calendar (calendar_week + events.csv)", "slug": "engine_calendar", "kind": "calendar", "ok": False,
                        "n": 0, "error": str(e)[:200]})

    events = merge_events(raw_events, p, start_t, end_t)

    items_by_feed = []
    for f in HEADLINE_FEEDS if headlines else []:
        raw, info = result(f)
        info["kind"] = "headlines"
        if raw is not None:
            items = parse_rss(raw)
            info.update(ok=bool(items), n=len(items))
            if not items:
                info["error"] = (info.get("error") or "") + " no items parsed"
            items_by_feed.append((f, items))
        elif not info.get("error"):
            info["error"] = "no raw file (run online once)" if offline else "fetch failed"
        sources.append(info)
    hl = build_headlines(items_by_feed, now) if headlines else []

    try:
        from engine.calendar_week import DAY_NOTES
    except Exception:
        DAY_NOTES = {}
    days_rows = day_rows(events, start, end, today, p, DAY_NOTES)
    upcoming_hi = [e for e in events if e["t"] > now and e["impact"] == "high"]
    nxt = upcoming_hi[0] if upcoming_hi else (max((e for e in events if e["t"] > now), key=lambda e: e["usd_score"], default=None))
    heavy = [r for r in days_rows if r["heaviest"] and not r["past"]]
    if heavy:
        h = heavy[0]
        notes.append(f"Heaviest day ahead: {h['label']} (USD load {h['usd_load']}" + (", FOMC" if h["fomc"] else "") + ").")
    fomc_days = [r["label"] for r in days_rows if r["fomc"] and not r["past"]]
    if fomc_days:
        notes.append("FOMC: " + ", ".join(fomc_days) + ". No bot entries after 13:00 ET on those days.")
    failed = [s["name"] for s in sources if not s["ok"]]
    if failed:
        notes.append(("Offline build: " if offline else "Sources unavailable: ") + ", ".join(failed) + ".")
    cached = [s["name"] for s in sources if s.get("cached")]
    if cached:
        notes.append("From cached files: " + ", ".join(cached) + ".")
    if today <= dt.date(2026, 11, 1) <= end:
        notes.append("US clocks go back Sun Nov 1: times stay ET wall-clock; European releases land an hour later in ET from Oct 26.")
    hub = {"built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "built_t": int(time.time()), "now_t": now,
           "tz": "America/New_York", "range": {"from": start.isoformat(), "to": end.isoformat(), "days": days, "past": past},
           "offline": bool(offline), "sources": sources, "events": events, "headlines": hl, "days": days_rows, "next": nxt,
           "bot_now": bot_now(events, now, p), "notes": notes,
           "model": {"usd_score": USD_SCORE, "impact_floor": IMPACT_SCORE, "blackout": f"{p['news_before_min']} min before to "
                     f"{p['news_after_min']} min after every high-impact USD release; FOMC days: no entries after "
                     f"{_hhmm(p.get('fomc_pm_cutoff', 780))} ET", "killzones": ["09:30-11:30", "13:30-15:30"]}}
    ok = sum(1 for s in sources if s["ok"])
    log(f"news hub: {len(events)} events {start}..{end}, {len(hl)} headlines, {ok}/{len(sources)} sources ok" + (" (offline)" if offline else ""))
    return hub


def write(hub: dict, out: str):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(hub, fh, separators=(",", ":"), ensure_ascii=False, default=str)
    return out


def hub_for_dashboard(path: str = DEFAULT_OUT, days=7, headlines=40, now=None) -> dict:
    """Compact hub for data.json: events yesterday..+7 days, top headlines, days, next, bot_now. Never raises."""
    try:
        with open(path, encoding="utf-8") as fh:
            hub = json.load(fh)
    except Exception as e:                  # noqa: BLE001
        return {"error": f"{os.path.relpath(path, ROOT) if os.path.isabs(path) else path} unavailable ({type(e).__name__}): "
                         "run python tools/news_hub.py --out data/news/hub.json", "events": [], "headlines": [], "days": [], "next": None}
    return compact(hub, days, headlines, now)


def compact(hub: dict, days=7, headlines=40, now=None) -> dict:
    """The data.json cut of an already loaded hub."""
    now = int(now or time.time())
    today = et_dt(now).date()
    lo, hi = (today - dt.timedelta(days=1)).isoformat(), (today + dt.timedelta(days=days)).isoformat()
    ev_keys = ("t", "date", "time_et", "weekday", "title", "kind", "kind_label", "impact", "usd_score", "forecast", "previous", "actual",
               "surprise_side", "usd_hint", "source", "url", "blackout", "blackout_start", "blackout_end", "in_killzone", "killzone",
               "blackout_hits_killzone")
    evs = [{k: e.get(k) for k in ev_keys} for e in hub.get("events", []) if lo <= e.get("date", "") <= hi]
    hl = sorted(hub.get("headlines", []), key=lambda h: (-h.get("score", 0), -h.get("t", 0)))[:headlines]
    hl.sort(key=lambda h: -h.get("t", 0))
    hl = [{k: h.get(k) for k in ("t", "time_et", "title", "source", "url", "score", "tone")} for h in hl]
    days_rows = [{k: r.get(k) for k in ("date", "label", "weekday", "is_today", "past", "n_high", "n_medium", "fomc", "holiday", "blackouts",
                                        "killzone_pauses", "heaviest", "summary")} for r in hub.get("days", []) if r.get("date", "") >= lo]
    return {"built": hub.get("built"), "built_t": hub.get("built_t"), "tz": hub.get("tz", "America/New_York"), "offline": hub.get("offline"),
            "next": hub.get("next"), "bot_now": hub.get("bot_now"), "days": days_rows, "events": evs, "headlines": hl,
            "sources": [{"name": s.get("name"), "ok": s.get("ok"), "n": s.get("n"), "kind": s.get("kind")} for s in hub.get("sources", [])],
            "notes": hub.get("notes", [])}


# ------------------------------------------------------------------ selftest (fixtures, no network)
_FAILS: list = []


def _assert(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        _FAILS.append(msg)


def selftest() -> int:
    fails = _FAILS
    fails.clear()
    p = bot_params()
    now = int(dt.datetime(2026, 10, 19, 9, 0, tzinfo=ET_TZ).timestamp())     # Mon 09:00 ET
    print("news_hub selftest  (fixtures:", os.path.relpath(FIXTURES, ROOT) + ")")

    print("classify / score")
    _assert(classify("Core CPI m/m") == "cpi" and usd_score("cpi", "high") == 95, "CPI -> cpi 95")
    _assert(classify("Non-Farm Employment Change") == "nfp" and classify("Employment Situation for September 2026") == "nfp", "NFP variants -> nfp")
    _assert(classify("FOMC Statement") == "fomc" and classify("FOMC Press Conference") == "fomc_pc" and classify("FOMC Meeting Minutes") == "fomc_min", "FOMC kinds")
    _assert(classify("Fed Chairman Warsh Speaks") == "fed_chair" and usd_score("fed_chair", "low") == 70, "Fed chair speech 70")
    _assert(classify("FOMC Member Hammack Speaks") == "fed_speaker" and usd_score("fed_speaker", "low") == 35, "Fed speaker 35")
    _assert(classify("10-Year Note auction ($39bn)") == "auction_10y" and usd_score("auction_10y", None) == 40, "10-yr auction 40")
    _assert(classify("Unemployment Claims") == "claims" and usd_score("claims", "medium") == 45, "claims 45")
    _assert(classify("Philly Fed Manufacturing Index") == "regional_fed", "Philly Fed -> regional_fed")
    _assert(classify("Bank Holiday") == "holiday" and usd_score("holiday", "holiday") == 0, "holiday 0")
    _assert(usd_score("other", "high") == 60 and usd_score("other", "medium") == 35, "unknown kind falls back to impact")
    _assert(surprise("cpi", "0.4%", "0.3%") == (0.1, "above", "USD+"), "CPI above forecast = USD+")
    _assert(surprise("claims", "250K", "230K")[2] == "USD-", "claims above forecast = USD-")
    _assert(surprise("nfp", "", "150K") == (None, None, None), "no actual -> no surprise")

    print("headline relevance / tone")
    _assert(relevance("Fed's Powell says inflation progress has stalled, yields jump") >= 75, "Fed+inflation+yields scores high")
    _assert(relevance("Celebrity chef opens new restaurant") == 0, "irrelevant headline scores 0")
    _assert(tone("Fed signals rate cut as inflation cools") == "dovish", "dovish tone")
    _assert(tone("Hot CPI print pushes yields higher, dollar gains") == "hawkish", "hawkish tone")
    _assert(tone("Nasdaq plunges 3% as tariff fears return") == "risk-off", "risk-off tone")
    _assert(tone("Stocks rally to record high on Nvidia earnings") == "risk-on", "risk-on tone")
    _assert(tone("Treasury announces auction schedule") == "neutral", "neutral tone")

    print("parsers")
    def fx(name):
        with open(os.path.join(FIXTURES, name), "rb") as fh:
            return fh.read()
    ff = parse_ff(fx("ff_thisweek.json"))
    _assert(len(ff) == 10 and all(e["country"] == "USD" for e in ff), f"ForexFactory: 10 USD rows kept (high/medium + Fed speaker + holiday), got {len(ff)}")
    _assert(any(e["kind"] == "fed_speaker" and e["impact"] == "low" for e in ff), "FF low-impact Fed speaker kept")
    _assert(not any(e["title"] == "Housing Starts" for e in ff) and not any(e["country"] == "GBP" for e in ff), "FF low-impact data and other currencies dropped")
    _assert(classify("ADP Non-Farm Employment Change") == "adp", "ADP is not the jobs report")
    _assert(surprise("nfp", "4.4%", "4.3%", "Unemployment Rate")[2] == "USD-", "unemployment rate above forecast = USD-")
    fomc = parse_fomc(fx("fomc_calendar.htm"))
    _assert(len(fomc) == 4 and fomc[0]["title"].startswith("FOMC rate decision") and "projections" in fomc[2]["title"], f"FOMC calendar: 2 meetings -> 4 rows, got {len(fomc)}")
    _assert(et_dt(fomc[0]["t"]).strftime("%Y-%m-%d %H:%M") == "2026-10-28 14:00" and et_dt(fomc[1]["t"]).strftime("%H:%M") == "14:30", "FOMC 14:00 / 14:30 ET")
    bls = parse_bls(fx("bls_schedule.htm"))
    kinds = sorted({e["kind"] for e in bls})
    _assert(len(bls) == 6 and kinds == ["cpi", "import_prices", "jolts", "nfp", "ppi", "real_earnings"], f"BLS schedule: 6 rows {kinds}")
    jolts = next(e for e in bls if e["kind"] == "jolts")
    _assert(et_dt(jolts["t"]).strftime("%Y-%m-%d %H:%M") == "2026-11-03 10:00", "BLS JOLTS Tue Nov 3 10:00 ET")
    bea = parse_bea(fx("bea_schedule.htm"))
    _assert(len(bea) == 3 and {e["kind"] for e in bea} == {"gdp", "pce", "trade"}, f"BEA schedule: GDP, PCE, trade ({len(bea)})")
    tr = parse_treasury(fx("treasury_auctions.json"))
    _assert(len(tr) == 3 and {e["kind"] for e in tr} == {"auction_10y", "auction_30y", "auction_other"}, f"Treasury: notes/bonds only ({len(tr)}), bills dropped")
    _assert(et_dt(tr[0]["t"]).strftime("%H:%M") == "13:00", "auctions at 13:00 ET")
    sp = parse_fed_speeches(fx("fed_speeches.xml"))
    _assert(len(sp) == 2 and {e["kind"] for e in sp} == {"fed_chair", "fed_speaker"}, "Fed speeches RSS: chair + governor")
    pr = parse_fed_press(fx("fed_press.xml"))
    _assert(len(pr) == 1 and pr[0]["kind"] == "fomc_min", "Fed press RSS: only the FOMC minutes become an event")
    rss = parse_rss(fx("mw_top.xml"))
    _assert(len(rss) == 5 and all(i["t"] for i in rss), "MarketWatch RSS: 5 items with dates")
    atom = parse_rss(fx("atom_sample.xml"))
    _assert(len(atom) == 2 and atom[0]["link"].startswith("http"), "Atom feed parsed (link href)")

    print("blackout / killzone")
    cpi = normalise({"t": int(dt.datetime(2026, 11, 10, 8, 30, tzinfo=ET_TZ).timestamp()), "title": "CPI m/m", "impact": "high", "kind": "cpi", "source": "ForexFactory"}, p)
    _assert(cpi["blackout"] and (cpi["blackout_start"], cpi["blackout_end"]) == ("08:15", "09:00") and not cpi["in_killzone"] and not cpi["blackout_hits_killzone"],
            "CPI 08:30 -> blackout 08:15-09:00, before the killzone")
    dec = normalise({"t": int(dt.datetime(2026, 10, 28, 14, 0, tzinfo=ET_TZ).timestamp()), "title": "FOMC Statement", "impact": "high", "kind": "fomc", "source": "ForexFactory"}, p)
    _assert(dec["in_killzone"] and dec["killzone"] == "PM" and (dec["blackout_start"], dec["blackout_end"]) == ("13:45", "14:30") and dec["blackout_hits_killzone"],
            "FOMC 14:00 -> 13:45-14:30 inside the PM killzone")
    ism = normalise({"t": int(dt.datetime(2026, 11, 2, 10, 0, tzinfo=ET_TZ).timestamp()), "title": "ISM Manufacturing PMI", "impact": "high", "kind": "ism_m", "source": "ForexFactory"}, p)
    _assert(ism["in_killzone"] and ism["killzone"] == "AM" and ism["blackout_hits_killzone"], "ISM 10:00 inside the AM killzone")
    med = normalise({"t": int(dt.datetime(2026, 11, 5, 8, 30, tzinfo=ET_TZ).timestamp()), "title": "Unemployment Claims", "impact": "medium", "kind": "claims", "source": "ForexFactory"}, p)
    _assert(not med["blackout"] and med["blackout_start"] is None, "medium impact: no blackout")

    print("full build from fixtures")
    hub = build(days=14, past=2, offline=True, now=now, raw_dir=FIXTURES, save_raw=False, log=lambda *a: None)
    _assert(hub["range"] == {"from": "2026-10-17", "to": "2026-11-02", "days": 14, "past": 2}, "range = past 2 .. next 14 days")
    srcs = {s["slug"]: s for s in hub["sources"]}
    _assert(all(srcs[k]["ok"] for k in ("ff_thisweek", "fomc_calendar", "bls_schedule", "bea_schedule", "treasury_auctions", "engine_calendar")),
            "every fixture-backed calendar source ok")
    _assert(not srcs["ff_nextweek"]["ok"] and "no raw file" in srcs["ff_nextweek"].get("error", ""), "missing raw file -> ok=false with an error, build continues")
    dates = [e["date"] for e in hub["events"]]
    _assert(dates == sorted(dates) and all("2026-10-17" <= d <= "2026-11-02" for d in dates), "events sorted and inside the range")
    fomc_rows = [e for e in hub["events"] if e["kind"] in ("fomc", "fomc_pc") and e["date"] == "2026-10-28"]
    _assert(len(fomc_rows) == 2 and all(len(e["sources"]) >= 2 for e in fomc_rows), f"FOMC Oct 28 deduped across FF + Fed + engine calendar ({len(fomc_rows)} rows, sources {[e['sources'] for e in fomc_rows]})")
    cpi_rows = [e for e in hub["events"] if e["kind"] == "cpi"]
    _assert(len(cpi_rows) == 2 and {e["title"] for e in cpi_rows} == {"CPI m/m", "Core CPI m/m"} and all(e["usd_score"] == 95 for e in cpi_rows),
            f"CPI: FF headline + core lines kept, BLS/engine rows folded in ({[e['title'] for e in cpi_rows]})")
    gdp = [e for e in hub["events"] if e["kind"] == "gdp"]
    _assert(len(gdp) == 1 and gdp[0]["impact"] == "high" and gdp[0]["blackout"], "GDP from BEA + engine calendar: one high-impact row with a blackout")
    auc = [e for e in hub["events"] if e["kind"].startswith("auction")]
    _assert(len(auc) == 3 and all(not e["blackout"] for e in auc), "3 auctions, none a blackout")
    _assert(hub["next"] and hub["next"]["kind"] == "cpi" and hub["next"]["date"] == "2026-10-20" and hub["next"]["time_et"] == "08:30" or
            (hub["next"] and hub["next"]["impact"] == "high" and hub["next"]["t"] > now), f"next = next high-impact event ({hub['next'] and hub['next']['title']} {hub['next'] and hub['next']['label']})")
    days = {r["date"]: r for r in hub["days"]}
    _assert("2026-10-17" in days and "2026-10-18" not in days and "2026-10-19" in days and days["2026-10-19"]["is_today"],
            "Saturday with a Fed speech listed, Sunday without events skipped, today flagged")
    d28 = days["2026-10-28"]
    _assert(d28["fomc"] and "13:00-16:00 FOMC afternoon: no entries" in d28["blackouts"] and any(b.startswith("13:45-15:00") for b in d28["blackouts"]),
            f"FOMC day blackouts merged 13:45-15:00 + afternoon off: {d28['blackouts']}")
    _assert("no entries after 13:00" in d28["summary"], "FOMC day summary says no entries after 13:00")
    d20 = days["2026-10-20"]
    _assert(d20["n_high"] >= 1 and d20["blackouts"] and d20["blackouts"][0].startswith("08:15-09:00") and not d20["killzone_pauses"] and "not affected" in d20["summary"],
            f"CPI day: 08:15-09:00 blackout, entries not affected: {d20['blackouts']} / {d20['summary'][:80]}")
    d02 = days["2026-11-02"]
    _assert(d02["killzone_pauses"] == ["09:45-10:30"] and "will not enter 09:45-10:30" in d02["summary"], f"ISM day: bot will not enter 09:45-10:30 ({d02['killzone_pauses']})")
    _assert(any(r["heaviest"] for r in hub["days"]) and d28["heaviest"], "heaviest day per week flagged (FOMC week -> Oct 28)")
    _assert(any(n.startswith("Heaviest day ahead") for n in hub["notes"]) and any(n.startswith("FOMC:") for n in hub["notes"]), "notes: heaviest day + FOMC dates")
    bn = hub["bot_now"]
    _assert(bn["in_blackout"] is False and bn["next_blackout"] and bn["rules"]["before_min"] == p["news_before_min"], "bot_now at 09:00 Tue: clear, next blackout known")
    bn2 = bot_now(hub["events"], int(dt.datetime(2026, 10, 28, 14, 10, tzinfo=ET_TZ).timestamp()), p)
    _assert(bn2["in_blackout"] and bn2["fomc_pm_off"] and len(bn2["reasons"]) >= 2, "bot_now at FOMC 14:10: blackout + afternoon off")
    hl = hub["headlines"]
    _assert(4 <= len(hl) <= HEADLINE_MAX and hl == sorted(hl, key=lambda h: -h["t"]), f"headlines within 48 h, newest first ({len(hl)})")
    _assert(not any("Celebrity" in h["title"] for h in hl) or any(h["score"] == 0 for h in hl), "low-relevance items present only if room")
    titles = [h["title"] for h in hl]
    _assert(len(titles) == len(set(titles)), "headlines deduped")
    _assert(any(h["source"] == "Federal Reserve" and h["score"] >= 50 for h in hl), "Fed press release scored with the source weight")
    _assert(all(set(("t", "title", "source", "url", "score", "tone")) <= set(h) for h in hl), "headline schema")
    need = {"built", "built_t", "tz", "sources", "events", "headlines", "days", "next", "notes", "bot_now"}
    _assert(need <= set(hub), f"hub schema keys {sorted(need - set(hub))}")
    ev_keys = {"t", "date", "time_et", "title", "kind", "impact", "usd_score", "country", "forecast", "previous", "actual", "surprise", "source", "blackout", "in_killzone", "url"}
    _assert(all(ev_keys <= set(e) for e in hub["events"]), "event schema")
    # hub_for_dashboard round trip
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), "news_hub_selftest.json")
    write(hub, tmp)
    comp = hub_for_dashboard(tmp, now=now)
    _assert(comp["events"] and all("2026-10-18" <= e["date"] <= "2026-10-26" for e in comp["events"]) and len(comp["headlines"]) <= 40 and comp["next"],
            f"hub_for_dashboard: events yesterday..+7d ({len(comp['events'])}), top headlines, next")
    _assert("error" in hub_for_dashboard(os.path.join(tempfile.gettempdir(), "does_not_exist.json")), "hub_for_dashboard never raises on a missing file")
    json.dumps(comp)
    try:
        os.remove(tmp)
    except OSError:
        pass
    print(f"\n{'ALL PASSED' if not fails else str(len(fails)) + ' FAILED'}: {sum(1 for _ in fails) and fails or ''}")
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--days", type=int, default=10, help="days ahead (default 10)")
    ap.add_argument("--past", type=int, default=2, help="days back (default 2)")
    ap.add_argument("--offline", action="store_true", help="rebuild from data/news/raw/ (and the ff_thisweek.json snapshot) without the network")
    ap.add_argument("--now", default=None, help="pretend it is this ET time, e.g. 2026-10-20T09:00 (tests)")
    ap.add_argument("--no-headlines", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--print", action="store_true", help="print the day summaries and the next event")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    now = int(dt.datetime.fromisoformat(a.now).replace(tzinfo=ET_TZ).timestamp()) if a.now else None
    hub = build(days=a.days, past=a.past, offline=a.offline, now=now, headlines=not a.no_headlines)
    write(hub, a.out)
    bad = [f"{s['name']}: {s.get('error', '')[:80]}" for s in hub["sources"] if not s["ok"]]
    print(f"wrote {os.path.relpath(a.out, ROOT) if os.path.isabs(a.out) else a.out}" + (f"  ({len(bad)} sources failed)" if bad else ""))
    for b in bad:
        print("   -", b)
    if a.print:
        for r in hub["days"]:
            print(("* " if r["is_today"] else "  ") + r["summary"])
        if hub["next"]:
            print("next:", hub["next"]["label"], hub["next"]["title"], "USD", hub["next"]["usd_score"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
