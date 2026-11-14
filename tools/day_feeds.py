#!/usr/bin/env python3
"""DAY FEEDS (team X2 "connect the day", 2026-11-14): the free internet feeds of the morning brief, fetched by the PC next to your
calendars (tools/calendar_sync.py calls gather() every 15 minutes; each feed is asked at most once an hour). No key, no account.

  weather    api.weather.gov (the US National Weather Service, free, no key): the forecast for your city and its active alerts.
             Your city is set once (CONNECT_DAY.bat or --city): "39.96,-83.00", or a name like "Columbus, OH" that is looked up ONCE
             with Open-Meteo's free geocoder (no key) and saved as numbers; after that only the numbers go to weather.gov.
  headlines  the official RSS feeds of the Federal Reserve (press releases) and the BLS (CPI, jobs, PPI releases), filtered to what
             moves NQ (FOMC, rates, CPI, jobs, PPI, GDP, retail sales, PCE). "rss": [...] in calendars.json replaces the list ([] = off).
  The market's own calendar (holidays, early closes, CPI / FOMC days) is already in the repo: tools/web_public/pythia/events.json.

Nothing personal is sent: a generic User-Agent, no cookie, no name. Results go into data/day/day.json (private) only.
  python tools/day_feeds.py --print          what the feeds say now (uses the network)
Test: python -X utf8 -m tests.test_calendar_sync --only=i
"""
from __future__ import annotations

import datetime as dt
import email.utils
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

UA = "olympus-day/1 (personal weather and news check)"
WEATHER_API = "https://api.weather.gov"
GEOCODER = "https://geocoding-api.open-meteo.com/v1/search"
DEFAULT_RSS = ("https://www.federalreserve.gov/feeds/press_all.xml", "https://www.bls.gov/feed/bls_latest.rss")
EVERY_S = 55 * 60
MAX_FEED_BYTES = 1024 * 1024
MAX_HEADLINES = 8
HEADLINE_DAYS = 3
TIMEOUT_S = 15
TAGS = (("fed", r"\b(fomc|federal open market|federal funds|interest rates?|monetary policy|beige book|powell|discount rate|balance sheet)\b"),
        ("cpi", r"\b(cpi|consumer price|inflation|pce|personal consumption)\b"),
        ("jobs", r"\b(employment situation|nonfarm|payrolls?|jobs report|unemployment|jolts|job openings|jobless claims)\b"),
        ("ppi", r"\b(ppi|producer price)\b"),
        ("gdp", r"\b(gdp|gross domestic product|retail sales)\b"),
        ("nq", r"\b(nasdaq|treasury yields?|stock market)\b"))
STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
          "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
          "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
          "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
          "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
          "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
          "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia", "PR": "Puerto Rico"}


def _clean(s, n=140) -> str:
    t = re.sub(r"<[^>]*>", " ", str(s or ""))
    return re.sub(r"[\x00-\x1f<>]", " ", re.sub(r"\s+", " ", t)).strip()[:n]


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def get(url: str, opener=None, accept: str = "application/json", limit: int = MAX_FEED_BYTES) -> bytes:
    """One GET. opener(url, headers, timeout) -> (status, bytes) for tests. Raises on failure."""
    headers = {"User-Agent": UA, "Accept": accept}
    if not str(url).startswith("https://"):
        raise ValueError("https only")
    if opener is not None:
        status, body = opener(url, headers, TIMEOUT_S)
    else:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:      # noqa: S310  (https only, checked above)
            status, body = r.status, r.read(limit + 1)
    if status != 200:
        raise OSError(f"HTTP {status}")
    body = body if isinstance(body, (bytes, bytearray)) else str(body).encode("utf-8")
    if len(body) > limit:
        raise OSError("too large")
    return bytes(body)


def _json(url, opener=None, accept="application/geo+json"):
    return json.loads(get(url, opener, accept).decode("utf-8", "replace"))


# ------------------------------------------------------------------------------------------------ your city (once)
LATLON_RX = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$")


def set_city(cfg: dict, text: str, geocode=None, opener=None) -> str:
    """cfg["city"] = {"name", "lat", "lon"} from "39.96,-83.00" or "Columbus, OH" (looked up once). Returns the place name."""
    m = LATLON_RX.match(str(text or ""))
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("those numbers are not a place on Earth")
        cfg["city"] = {"name": f"{lat:.2f},{lon:.2f}", "lat": round(lat, 4), "lon": round(lon, 4)}
        return cfg["city"]["name"]
    name = _clean(text, 80)
    if not name:
        raise ValueError("type a city like Columbus, OH")
    city, _, state = name.partition(",")
    state = state.strip()
    want = STATES.get(state.upper(), state).lower() if state else ""
    if geocode is not None:
        res = geocode(city.strip(), state)
    else:
        q = urllib.parse.urlencode({"name": city.strip(), "count": 10, "language": "en", "format": "json", "countryCode": "US"})
        res = _json(f"{GEOCODER}?{q}", opener, "application/json").get("results") or []
    pick = None
    for r in res if isinstance(res, list) else []:
        if not isinstance(r, dict) or _num(r.get("latitude")) is None or _num(r.get("longitude")) is None:
            continue
        if not want or str(r.get("admin1") or "").lower() == want or str(r.get("admin1_code") or "").lower() == state.lower():
            pick = r
            break
    if not pick:
        raise ValueError(f"could not find {name} (try the numbers: Google Maps, long-press your town, copy the two numbers)")
    place = f"{_clean(pick.get('name'), 40)}, {STATES_REV.get(str(pick.get('admin1') or ''), _clean(pick.get('admin1'), 20))}".strip(", ")
    cfg["city"] = {"name": place, "lat": round(float(pick["latitude"]), 4), "lon": round(float(pick["longitude"]), 4)}
    return place


STATES_REV = {v: k for k, v in STATES.items()}


# ------------------------------------------------------------------------------------------------ the weather (api.weather.gov)
def weather(city: dict, now_s: float, state: dict, opener=None) -> dict:
    """{"src", "place", "t", "periods": [{name, temp, unit, short, rain, wind, day}], "alerts": [{event, headline, severity}]}; raises on failure"""
    lat, lon = _num(city.get("lat")), _num(city.get("lon"))
    if lat is None or lon is None:
        raise ValueError("no city set")
    key = f"{lat:.4f},{lon:.4f}"
    pts = state.get("points") if isinstance(state.get("points"), dict) else {}
    if pts.get("key") != key or not str(pts.get("forecast") or "").startswith(WEATHER_API + "/"):
        p = _json(f"{WEATHER_API}/points/{key}", opener).get("properties") or {}
        rel = ((p.get("relativeLocation") or {}).get("properties") or {})
        fc = str(p.get("forecast") or "")
        if not fc.startswith(WEATHER_API + "/"):
            raise OSError("weather.gov has no forecast for this place (US only)")
        pts = {"key": key, "forecast": fc, "place": _clean(f"{rel.get('city', '')}, {rel.get('state', '')}".strip(", "), 60)}
        state["points"] = pts
    fc = _json(pts["forecast"], opener).get("properties") or {}
    periods = []
    for x in (fc.get("periods") or [])[:4]:
        if not isinstance(x, dict):
            continue
        periods.append({"name": _clean(x.get("name"), 24), "temp": _num(x.get("temperature")), "unit": _clean(x.get("temperatureUnit"), 2) or "F",
                        "short": _clean(x.get("shortForecast"), 80), "rain": _num((x.get("probabilityOfPrecipitation") or {}).get("value")),
                        "wind": _clean(x.get("windSpeed"), 24), "day": x.get("isDaytime") is True})
    alerts = []
    try:
        al = _json(f"{WEATHER_API}/alerts/active?point={key}", opener)
        for f in (al.get("features") or [])[:3]:
            pr = (f or {}).get("properties") or {}
            if pr.get("event"):
                alerts.append({"event": _clean(pr.get("event"), 60), "headline": _clean(pr.get("headline"), 160), "severity": _clean(pr.get("severity"), 16)})
    except Exception:  # noqa: BLE001  (alerts are a bonus: the forecast stands without them)
        pass
    if not periods:
        raise OSError("weather.gov sent no forecast periods")
    return {"src": "api.weather.gov", "place": city.get("name") if not pts.get("place") else pts["place"], "t": int(now_s), "periods": periods, "alerts": alerts}


# ------------------------------------------------------------------------------------------------ headlines (official RSS)
def _when(s) -> float | None:
    s = str(s or "").strip()
    if not s:
        return None
    try:
        return email.utils.parsedate_to_datetime(s).timestamp()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def parse_feed(raw: bytes, source: str) -> list:
    """RSS 2.0 <item> or Atom <entry>: [{title, source, t}]. A file with entity declarations is refused (no XML bombs)."""
    text = raw.decode("utf-8", "replace")
    if "<!ENTITY" in text.upper() or "<!DOCTYPE" in text.upper():
        raise ValueError("feed refused: it declares entities")
    root = ET.fromstring(text)
    out = []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        title = when = None
        for ch in el:
            ct = ch.tag.split("}")[-1]
            if ct == "title":
                title = "".join(ch.itertext())
            elif ct in ("pubDate", "updated", "published", "date") and when is None:
                when = _when(ch.text)
        if title:
            out.append({"title": _clean(title, 140), "source": source, "t": int(when) if when else None})
    return out


def tags_of(title: str) -> list:
    return [k for k, rx in TAGS if re.search(rx, title or "", re.I)]


def headlines(feeds, now_s: float, opener=None) -> dict:
    items, errors = [], []
    for u in feeds:
        host = (urllib.parse.urlsplit(u).hostname or "").lower().replace("www.", "")
        try:
            got = parse_feed(get(u, opener, "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.5"), host)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{host}: {e.__class__.__name__}")
            continue
        for it in got:
            tg = tags_of(it["title"])
            if tg and (it["t"] is None or now_s - it["t"] <= HEADLINE_DAYS * 86400) and (it["t"] is None or it["t"] <= now_s + 86400):
                items.append({**it, "tags": tg})
    items.sort(key=lambda x: -(x["t"] or 0))
    seen, uniq = set(), []
    for it in items:
        k = it["title"].lower()
        if k not in seen:
            seen.add(k)
            uniq.append(it)
    return {"t": int(now_s), "items": uniq[:MAX_HEADLINES], "errors": errors[:4], "src": [((urllib.parse.urlsplit(u).hostname or "").replace("www.", "")) for u in feeds]}


# ------------------------------------------------------------------------------------------------ both, at most once an hour each
def gather(cfg: dict, now_s: float, work_dir: str, opener=None, offline: bool = False, say=print) -> dict:
    """{"weather": ... | None, "headlines": ... | None}: fresh when due, else the last good copy (kept in data/day/feeds.json). Never raises."""
    sp = os.path.join(work_dir, "feeds.json")
    try:
        with open(sp, encoding="utf-8") as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        st = {}
    st = st if isinstance(st, dict) else {}
    out = {}
    city = cfg.get("city") if isinstance(cfg.get("city"), dict) else None
    if city and not offline and now_s - (_num(st.get("weather_try")) or 0) >= EVERY_S:
        st["weather_try"] = int(now_s)
        try:
            st["weather"] = weather(city, now_s, st, opener)
            st.pop("weather_error", None)
        except Exception as e:  # noqa: BLE001
            st["weather_error"] = f"{e.__class__.__name__}: {str(e)[:100]}"
    out["weather"] = st.get("weather") if city else None
    feeds = [u for u in (cfg.get("rss") if isinstance(cfg.get("rss"), list) else DEFAULT_RSS) if isinstance(u, str) and u.startswith("https://")][:6]
    if feeds and not offline and now_s - (_num(st.get("news_try")) or 0) >= EVERY_S:
        st["news_try"] = int(now_s)
        try:
            h = headlines(feeds, now_s, opener)
            if h["items"] or not st.get("headlines"):
                st["headlines"] = h
            else:
                st["headlines"]["errors"] = h["errors"]
        except Exception as e:  # noqa: BLE001
            st["news_error"] = f"{e.__class__.__name__}"
    out["headlines"] = st.get("headlines") if feeds else None
    try:
        os.makedirs(work_dir, exist_ok=True)
        with open(sp + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(st, fh)
        os.replace(sp + ".tmp", sp)
    except OSError:
        pass
    return out


if __name__ == "__main__":
    from tools import calendar_sync as CS
    cfg = CS.load_config()
    if "--print" in sys.argv:
        print(json.dumps(gather(cfg, time.time(), os.path.join(CS.out_dir(), "feeds_check")), indent=1)[:4000])
