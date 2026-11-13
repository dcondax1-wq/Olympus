#!/usr/bin/env python3
"""KALSHI PAPER (team K1): a forward paper tester for the Kalshi ideas of research/writeups/kalshi-edge-2026-11-13.md.
PAPER ONLY: it reads Kalshi's PUBLIC market data (no key, no account, GET only) and free weather data (api.weather.gov),
it never places, changes or cancels an order and never reads a key. Stdlib only, Python 3.9+.

Each run (every 15 minutes is plenty):
  1. settles open paper signals whose market has a result (public /markets/<ticker>);
  2. logs new signals of the frozen rules in research/kalshi_edge_K1/paper_rules.json (1 contract each, taker price,
     Kalshi fee 0.07 p(1-p) rounded up to the cent):
       wx_lock     on the settle day, a daily-high bracket the thermometer has already ruled out (buy NO) or an
                   'above X' already reached (buy YES), when it still costs <= max_cost;
       idx_model   Nasdaq-100 hourly above/below priced from NQ futures bars (optional --bars CSV/CSV.GZ of 1-minute
                   NinjaTrader/TradingView bars: time,open,high,low,close; no bars = this rule only waits);
  3. keeps a FORECAST LOG (no money): the NWS forecast high per city next to the market's prices, settled later with
     the official high, so the forecast-vs-market question gets its own forward evidence;
  4. writes one JSON ledger the site can read (--out, default research/kalshi_edge_K1/paper/k1_paper.json).

  python tools/kalshi_paper.py                    one run (network: api.elections.kalshi.com, api.weather.gov)
  python tools/kalshi_paper.py --out DIR/k1_paper.json [--bars data/nt_bars/MNQ_1m.csv]
  python tools/kalshi_paper.py --summary          print the ledger's table, no network
  python tools/kalshi_paper.py --selftest         offline checks with a stub API
"""
from __future__ import annotations

import argparse
import calendar
import csv
import datetime as dt
import gzip
import io
import json
import math
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = os.path.join(ROOT, "research", "kalshi_edge_K1", "paper_rules.json")
DEFAULT_OUT = os.path.join(ROOT, "research", "kalshi_edge_K1", "paper", "k1_paper.json")
K = "https://api.elections.kalshi.com/trade-api/v2"
NWS = "https://api.weather.gov"
UA = "kalshi-paper-research (read-only)"
MAX_CLOSED = 4000

# city code -> (Kalshi series, station, lat, lon, standard-time UTC offset)
CITIES = {
    "NY": ("KXHIGHNY", "KNYC", 40.7789, -73.9692, -5), "CHI": ("KXHIGHCHI", "KMDW", 41.7861, -87.7522, -6),
    "MIA": ("KXHIGHMIA", "KMIA", 25.7881, -80.3169, -5), "AUS": ("KXHIGHAUS", "KAUS", 30.1945, -97.6699, -6),
    "LAX": ("KXHIGHLAX", "KLAX", 33.9382, -118.3866, -8), "DEN": ("KXHIGHDEN", "KDEN", 39.8466, -104.6562, -7),
    "PHIL": ("KXHIGHPHIL", "KPHL", 39.8733, -75.2268, -5),
}


# ---------------------------------------------------------------- network (GET only, polite)
class Net:
    def __init__(self, gap=0.35):
        self.gap, self.last = gap, {}

    def get(self, url, params=None, tries=6):
        if params:
            url += "?" + urllib.parse.urlencode(params)
        host = urllib.parse.urlparse(url).netloc
        for k in range(tries):
            w = self.gap - (time.time() - self.last.get(host, 0))
            if w > 0:
                time.sleep(w)
            self.last[host] = time.time()
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/geo+json, application/json"})
                return json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(1.5 * (k + 1))
                    continue
                if e.code in (400, 404):
                    return None
                time.sleep(1 + k)
            except Exception:
                time.sleep(1 + k)
        return None


# ---------------------------------------------------------------- helpers
def fee_c(p_c: int) -> int:
    """taker fee for ONE contract at p_c cents, rounded up to the cent."""
    return math.ceil(round(0.07 * (p_c / 100) * (1 - p_c / 100) * 100, 6))


def cents(x):
    try:
        return int(round(float(x) * 100))
    except (TypeError, ValueError):
        return None


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts(s):
    return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))


def c2f(c):
    return c * 9 / 5 + 32


def metar_temp_f(raw, fallback_c):
    m = re.search(r"\sT([01])(\d{3})([01])(\d{3})", raw or "")
    if m:
        return c2f((-1 if m.group(1) == "1" else 1) * int(m.group(2)) / 10)
    return None if fallback_c is None else c2f(fallback_c)


def load_rules(path=RULES):
    try:
        return json.load(open(path))
    except Exception:
        return {"rules": {}}


def load_ledger(path):
    try:
        d = json.load(open(path))
        if d.get("kind") == "kalshi_paper_k1":
            return d
    except Exception:
        pass
    return {"v": 1, "kind": "kalshi_paper_k1", "paper_only": True, "started": None, "updated": None, "open": [], "closed": [],
            "forecast_log": [], "summary": {}, "status": {}}


def write_json(path, d):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        json.dump(d, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)


# ---------------------------------------------------------------- weather
def local_day(now, tz):
    return (dt.datetime.fromtimestamp(now, dt.timezone.utc) + dt.timedelta(hours=tz)).date()


def event_for(series, day):
    mon = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"][day.month - 1]
    return f"{series}-{day.year % 100:02d}{mon}{day.day:02d}"


def max_so_far(net, station, day, tz, now):
    """max whole-degree reading since local-standard midnight, from the station's own reports (exact T group)."""
    start = calendar.timegm(day.timetuple()) - tz * 3600
    d = net.get(f"{NWS}/stations/{station}/observations", {"start": iso(start), "end": iso(now)})
    vals = []
    for f in (d or {}).get("features", []):
        p = f.get("properties", {})
        t = metar_temp_f(p.get("rawMessage"), (p.get("temperature") or {}).get("value"))
        if t is not None and ts(p.get("timestamp", "1970-01-01T00:00:00")) <= now - 600:
            vals.append(t)
    if len(vals) < 4:
        return None
    return int(math.floor(max(vals) + 0.5))


def bracket_dead_or_won(st, fs, cs, m, margin):
    """'no' if the bracket can no longer win, 'yes' if it has already won, else None."""
    if st == "between" and cs is not None and cs <= m - 1 - margin:
        return "no"
    if st == "less" and cs is not None and m >= cs + margin:
        return "no"
    if st == "greater" and fs is not None and m >= fs + 1 + margin:
        return "yes"
    return None


def wx_lock(net, led, rule, now):
    out = []
    for city, (series, station, lat, lon, tz) in CITIES.items():
        day = local_day(now, tz)
        hloc = (now - (calendar.timegm(day.timetuple()) - tz * 3600)) / 3600
        if hloc < rule.get("from_hour", 10):
            continue
        d = net.get(f"{K}/markets", {"event_ticker": event_for(series, day), "limit": 100})
        ms = [m for m in (d or {}).get("markets", []) if m.get("status") in ("active", "open")]
        if not ms:
            continue
        m = max_so_far(net, station, day, tz, now)
        if m is None:
            continue
        for mk in ms:
            side = bracket_dead_or_won(mk.get("strike_type"), mk.get("floor_strike"), mk.get("cap_strike"), m, rule.get("margin", 1))
            if not side:
                continue
            yb, ya = cents(mk.get("yes_bid_dollars")), cents(mk.get("yes_ask_dollars"))
            cost = (100 - yb) if side == "no" and yb else ya if side == "yes" else None
            if cost is None or not (1 <= cost <= rule.get("max_cost", 98)):
                continue
            out.append({"rule": "wx_lock", "ticker": mk["ticker"], "side": side, "price_c": cost, "fee_c": fee_c(cost),
                        "close": mk.get("close_time"), "why": f"{city} max so far {m}F, hour {hloc:.1f} local std"})
    return out


def forecast_log(net, led, now):
    """once per city per day: the NWS forecast high for the next daytime period + the market's mids."""
    have = {(x["city"], x["day"]) for x in led["forecast_log"]}
    for city, (series, station, lat, lon, tz) in CITIES.items():
        today = local_day(now, tz)
        if (city, (today + dt.timedelta(days=1)).isoformat()) in have:
            continue
        pt = net.get(f"{NWS}/points/{lat},{lon}")
        fu = ((pt or {}).get("properties") or {}).get("forecast")
        fc = net.get(fu) if fu else None
        hi, day = None, None
        for p in ((fc or {}).get("properties") or {}).get("periods", []):   # the next daytime period, issued before its market's day
            if p.get("isDaytime") and p.get("startTime", "")[:10] >= today.isoformat():
                hi, day = p.get("temperature"), dt.date.fromisoformat(p["startTime"][:10])
                break
        if day is None or (city, day.isoformat()) in have:
            continue
        d = net.get(f"{K}/markets", {"event_ticker": event_for(series, day), "limit": 100})
        mids = {}
        for mk in (d or {}).get("markets", []):
            yb, ya = cents(mk.get("yes_bid_dollars")), cents(mk.get("yes_ask_dollars"))
            if yb is not None and ya is not None:
                mids[mk["ticker"]] = [yb, ya]
        if hi is None and not mids:
            continue
        led["forecast_log"].append({"city": city, "day": day.isoformat(), "t": iso(now), "nws_high": hi,
                                    "issued": ((fc or {}).get("properties") or {}).get("updateTime"), "quotes": mids,
                                    "event": event_for(series, day), "final_high": None})


# ---------------------------------------------------------------- index model (optional bars)
def read_bars(path):
    if not path or not os.path.exists(path):
        return None
    op = gzip.open if path.endswith(".gz") else open
    rows = []
    with op(path, "rt") as fh:
        for r in csv.reader(fh):
            try:
                rows.append((int(float(r[0])), float(r[1]), float(r[4])))
            except (ValueError, IndexError):
                continue
    return sorted(rows) or None


def tcdf(x, nu):
    if not nu:
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))
    # crude but adequate: normal with the t's tail via a Cornish-Fisher-free mapping is not needed here -> numeric integral
    x = x * math.sqrt(nu / (nu - 2))
    n, lo = 2000, -60.0
    c = math.exp(math.lgamma((nu + 1) / 2) - math.lgamma(nu / 2)) / math.sqrt(nu * math.pi)
    hstep = (x - lo) / n
    s = 0.0
    for i in range(n + 1):
        u = lo + i * hstep
        f = c * (1 + u * u / nu) ** (-(nu + 1) / 2)
        s += f * (0.5 if i in (0, n) else 1)
    return min(max(s * hstep, 0.0), 1.0)


def idx_model(net, led, rule, now, bars):
    if not bars:
        led["status"]["idx_model"] = "waiting for NinjaTrader bars (pass --bars)"
        return []
    if now - bars[-1][0] > 180:
        led["status"]["idx_model"] = "bars stale (older than 3 min): no new signals"
        return []
    out = []
    et_off = -4 if 3 <= dt.datetime.utcfromtimestamp(now).month <= 10 else -5   # rough; Kalshi tickers carry the hour anyway
    d = net.get(f"{K}/events", {"series_ticker": "KXNASDAQ100U", "status": "settled", "limit": 3})
    last = None
    for e in (d or {}).get("events", []):
        md = net.get(f"{K}/markets", {"event_ticker": e["event_ticker"], "limit": 1})
        mk = ((md or {}).get("markets") or [None])[0]
        if mk and mk.get("expiration_value"):
            last = (ts(mk["close_time"]), float(mk["expiration_value"]))
            break
    if not last or now - last[0] > 3 * 86400:
        led["status"]["idx_model"] = "no recent settlement to measure the basis"
        return []
    tb = [b[0] for b in bars]
    import bisect
    i = bisect.bisect_right(tb, last[0]) - 1
    if i < 0 or last[0] - tb[i] > 120:
        led["status"]["idx_model"] = "no bar at the last settlement time"
        return []
    basis = bars[i][1] - last[1]
    F = bars[-1][2] - basis
    rv = [math.log(bars[k][2] / bars[k - 1][2]) for k in range(max(1, len(bars) - 60), len(bars))]
    v_rv = sum(x * x for x in rv) / max(len(rv), 1)
    d = net.get(f"{K}/events", {"series_ticker": "KXNASDAQ100U", "status": "open", "limit": 10})
    for e in (d or {}).get("events", []):
        md = net.get(f"{K}/markets", {"event_ticker": e["event_ticker"], "limit": 1000})
        for mk in (md or {}).get("markets", []):
            ct = ts(mk["close_time"])
            mins = (ct - now) / 60
            if not (rule.get("min_minutes", 8) <= mins <= rule.get("max_minutes", 32)) or mk.get("strike_type") != "greater_or_equal":
                continue
            K_ = float(mk["floor_strike"]) - 0.01
            var = rule["b_rv"] * v_rv * mins + rule["a_imp"] * (rule.get("vxn", 20) / 100) ** 2 / (252 * 390) * mins
            if var <= 0:
                continue
            p = 1 - tcdf(math.log(K_ / F) / math.sqrt(var), rule.get("nu"))
            yb, ya = cents(mk.get("yes_bid_dollars")), cents(mk.get("yes_ask_dollars"))
            if ya and 1 <= ya <= 99 and 100 * p - ya - fee_c(ya) >= rule["thr_c"]:
                out.append({"rule": "idx_model", "ticker": mk["ticker"], "side": "yes", "price_c": ya, "fee_c": fee_c(ya), "close": mk["close_time"],
                            "why": f"model {p:.3f} vs ask {ya}c, F {F:.1f}"})
            elif yb and 1 <= yb <= 99 and 100 * (1 - p) - (100 - yb) - fee_c(100 - yb) >= rule["thr_c"]:
                out.append({"rule": "idx_model", "ticker": mk["ticker"], "side": "no", "price_c": 100 - yb, "fee_c": fee_c(100 - yb),
                            "close": mk["close_time"], "why": f"model {p:.3f} vs bid {yb}c, F {F:.1f}"})
    led["status"]["idx_model"] = f"ok, F {F:.1f}, basis {basis:.1f}"
    return out


# ---------------------------------------------------------------- ledger
def settle(net, led, now):
    still = []
    for s in led["open"]:
        if s.get("close") and ts(s["close"]) > now:
            still.append(s)
            continue
        d = net.get(f"{K}/markets/{s['ticker']}")
        mk = (d or {}).get("market") or {}
        res = mk.get("result")
        if res not in ("yes", "no"):
            still.append(s)
            continue
        won = res == s["side"]
        s["result"], s["won"], s["settled"] = res, won, iso(now)
        s["pnl_c"] = (100 if won else 0) - s["price_c"] - s["fee_c"]
        led["closed"].append(s)
    led["open"] = still
    led["closed"] = led["closed"][-MAX_CLOSED:]
    for f in led["forecast_log"]:
        if f.get("final_high") is None and f["day"] < (dt.datetime.utcfromtimestamp(now) - dt.timedelta(days=1)).date().isoformat():
            md = net.get(f"{K}/markets", {"event_ticker": f["event"], "limit": 1})
            mk = ((md or {}).get("markets") or [None])[0]
            if mk and mk.get("expiration_value"):
                try:
                    f["final_high"] = float(mk["expiration_value"])
                except ValueError:
                    pass
    led["forecast_log"] = led["forecast_log"][-3000:]


def summarize(led):
    out = {}
    for s in led["closed"]:
        r = out.setdefault(s["rule"], {"n": 0, "won": 0, "pnl_usd_1lot": 0.0, "staked_usd": 0.0})
        r["n"] += 1
        r["won"] += 1 if s["won"] else 0
        r["pnl_usd_1lot"] = round(r["pnl_usd_1lot"] + s["pnl_c"] / 100, 2)
        r["staked_usd"] = round(r["staked_usd"] + s["price_c"] / 100, 2)
    for r in out.values():
        r["edge_per_usd"] = round(r["pnl_usd_1lot"] / r["staked_usd"], 4) if r["staked_usd"] else None
        r["verdict"] = "collecting" if r["n"] < 100 else ("positive so far" if r["pnl_usd_1lot"] > 0 else "not positive")
    for name in ("wx_lock", "idx_model"):
        out.setdefault(name, {"n": 0, "won": 0, "pnl_usd_1lot": 0.0, "staked_usd": 0.0, "edge_per_usd": None, "verdict": "collecting"})
    led["summary"] = out
    led["open_n"] = len(led["open"])
    return out


def run(out_path, bars_path=None, now=None, net=None, rules_path=RULES):
    net = net or Net()
    now = int(now or time.time())
    led = load_ledger(out_path)
    rules = load_rules(rules_path).get("rules", {})
    led["started"] = led["started"] or iso(now)
    led["status"] = {}
    settle(net, led, now)
    seen = {(s["rule"], s["ticker"]) for s in led["open"] + led["closed"]}
    new = []
    if rules.get("wx_lock", {}).get("on", True):
        new += wx_lock(net, led, rules.get("wx_lock", {}), now)
    if rules.get("idx_model", {}).get("on"):
        new += idx_model(net, led, rules["idx_model"], now, read_bars(bars_path))
    else:
        led["status"]["idx_model"] = "off (no edge in research; see the writeup)"
    added = 0
    for s in new:
        if (s["rule"], s["ticker"]) in seen:
            continue
        s["t"] = iso(now)
        led["open"].append(s)
        seen.add((s["rule"], s["ticker"]))
        added += 1
    if rules.get("forecast_log", {}).get("on", True):
        forecast_log(net, led, now)
    summarize(led)
    led["updated"] = iso(now)
    led["note"] = "PAPER ONLY. 1 contract per signal, taker price, Kalshi fee included. Public data only; no orders, no keys."
    write_json(out_path, led)
    return led, added


def print_summary(led):
    print("rule         n   won   P&L $ (1 lot)  staked $  per $1  verdict")
    for k, r in sorted(led.get("summary", {}).items()):
        e = "" if r.get("edge_per_usd") is None else f"{r['edge_per_usd']:+.3f}"
        print(f"{k:<11} {r['n']:>4} {r['won']:>5} {r['pnl_usd_1lot']:>13.2f} {r['staked_usd']:>9.2f} {e:>7}  {r['verdict']}")
    print("open signals:", len(led.get("open", [])), "| forecast log rows:", len(led.get("forecast_log", [])))


# ---------------------------------------------------------------- selftest (offline)
class Stub:
    """a fake public API: one NY event with 3 brackets, the station has read 60F, a settled market for the ledger."""
    def __init__(self, now):
        self.now = now
        self.calls = []

    def get(self, url, params=None, tries=1):
        self.calls.append(url)
        if "/stations/" in url:
            return {"features": [{"properties": {"timestamp": iso(self.now - 3600 * k), "rawMessage": f"KNYC 0000Z RMK AO2 T0{150 + k:03d}0100",
                                                 "temperature": {"value": 15.0}}} for k in range(1, 7)]}
        if url.endswith("/markets") and params and params.get("event_ticker", "").startswith("KXHIGHNY"):
            return {"markets": [
                {"ticker": "KXHIGHNY-X-B57.5", "status": "active", "strike_type": "between", "floor_strike": 57, "cap_strike": 58,
                 "yes_bid_dollars": "0.03", "yes_ask_dollars": "0.05", "close_time": iso(self.now + 7200), "expiration_value": "62"},
                {"ticker": "KXHIGHNY-X-T60", "status": "active", "strike_type": "greater", "floor_strike": 58, "cap_strike": None,
                 "yes_bid_dollars": "0.95", "yes_ask_dollars": "0.97", "close_time": iso(self.now + 7200)},
                {"ticker": "KXHIGHNY-X-B63.5", "status": "active", "strike_type": "between", "floor_strike": 63, "cap_strike": 64,
                 "yes_bid_dollars": "0.20", "yes_ask_dollars": "0.24", "close_time": iso(self.now + 7200)}]}
        if "/markets/KXHIGHNY-X-B57.5" in url:
            return {"market": {"result": "no"}}
        if "/markets/KXHIGHNY-X-T60" in url:
            return {"market": {"result": "yes"}}
        return None


def selftest():
    ok = []

    def check(name, cond):
        ok.append(bool(cond))
        print(("[PASS] " if cond else "[FAIL] ") + name)
    check("fee 50c = 2c, 97c = 1c, 99c = 1c", fee_c(50) == 2 and fee_c(97) == 1 and fee_c(99) == 1)
    check("dead bracket below the max", bracket_dead_or_won("between", 57, 58, 61, 1) == "no")
    check("bracket next to the max is not dead with margin 1", bracket_dead_or_won("between", 59, 60, 61, 1) is None)
    check("'above 58' reached at 61", bracket_dead_or_won("greater", 58, None, 61, 1) == "yes")
    check("T group parsed", abs(metar_temp_f("X RMK T01560100", None) - 60.08) < 0.01)
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "k1.json")
        rules = os.path.join(td, "r.json")
        json.dump({"rules": {"wx_lock": {"on": True, "margin": 1, "max_cost": 98, "from_hour": 0}, "forecast_log": {"on": False}}}, open(rules, "w"))
        now = 1794200000
        st = Stub(now)
        led, added = run(out, now=now, net=st, rules_path=rules)
        check("two lock signals (dead 57-58 NO at 97c, above-58 YES at 97c); 63-64 untouched", added == 2 and
              {s["ticker"] for s in led["open"]} == {"KXHIGHNY-X-B57.5", "KXHIGHNY-X-T60"})
        check("no order endpoint ever called", not any("/orders" in u or "/portfolio" in u for u in st.calls))
        led, added = run(out, now=now + 60, net=Stub(now + 60), rules_path=rules)
        check("same signal never logged twice", added == 0 and len(led["open"]) == 2)
        led, added = run(out, now=now + 8000, net=Stub(now + 8000), rules_path=rules)
        s = led["summary"]["wx_lock"]
        check("settled after close: 2 won, +2c each after the 1c fee", s["n"] == 2 and s["won"] == 2 and abs(s["pnl_usd_1lot"] - 0.04) < 1e-9)
        check("idx_model off without bars", "idx_model" in led["status"])
        check("ledger is paper-only JSON", led["paper_only"] is True and led["kind"] == "kalshi_paper_k1")
    print("ALL OK" if all(ok) else "FAILED")
    return 0 if all(ok) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--bars", default="")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.summary:
        print_summary(load_ledger(a.out))
        return 0
    led, added = run(a.out, a.bars or None)
    print(f"kalshi_paper: {added} new signal(s), {len(led['open'])} open, {len(led['closed'])} settled -> {a.out}")
    print_summary(led)
    return 0


if __name__ == "__main__":
    sys.exit(main())
