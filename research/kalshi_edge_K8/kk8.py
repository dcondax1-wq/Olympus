"""K8 (commodities): polite read-only client for Kalshi's PUBLIC market-data API (no key, GET only, never an order).

Cache: /home/user/kalshi_cache/kmetal/http (override with K8_CACHE), gzip json, one file per URL.
Speed limit: at most ONE request per second (several research helpers share this IP); back-off on 429.
"""
import calendar, gzip, hashlib, json, math, os, threading, time, urllib.error, urllib.parse, urllib.request

B = "https://api.elections.kalshi.com/trade-api/v2"
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.environ.get("K8_CACHE") or "/home/user/kalshi_cache/kmetal/http"
os.makedirs(CACHE, exist_ok=True)
GAP = max(1.0, float(os.environ.get("K8_GAP", "1.05")))      # never faster than 1 request / second
_last, _lock = [0.0], threading.Lock()
STATS = {"net": 0, "cache": 0, "429": 0, "fail": 0}


RATE_FILE = os.path.join(os.path.dirname(CACHE.rstrip("/")), ".rate")


def _wait_turn():
    """Machine-wide (all K8 processes) pacing: one request per GAP seconds, through a locked timestamp file."""
    import fcntl
    with open(RATE_FILE, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        try:
            last = float(fh.read().strip() or 0)
        except ValueError:
            last = 0.0
        w = GAP - (time.time() - last)
        if w > 0:
            time.sleep(w)
        fh.seek(0)
        fh.truncate()
        fh.write("%.3f" % time.time())
        fh.flush()
        fcntl.flock(fh, fcntl.LOCK_UN)
    _last[0] = time.time()


def _fn(url):
    return os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest() + ".json.gz")


def get(path, params=None, cache=True, tries=10):
    """GET a public market-data path (e.g. '/markets', {'series_ticker': ...}); returns parsed json or None."""
    url = (B + path if not path.startswith("http") else path) + (("?" + urllib.parse.urlencode(params)) if params else "")
    fn = _fn(url)
    if cache and os.path.exists(fn):
        STATS["cache"] += 1
        try:
            with gzip.open(fn, "rt") as fh:
                return json.load(fh)
        except Exception:
            pass
    if os.environ.get("K8_OFFLINE"):
        return None
    for k in range(tries):
        with _lock:
            _wait_turn()
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-client"}),
                                       timeout=60).read().decode()
            d = json.loads(r)
            STATS["net"] += 1
            if cache:
                tmp = fn + ".tmp"
                with gzip.open(tmp, "wt") as fh:
                    fh.write(r)
                os.replace(tmp, fn)
            return d
        except urllib.error.HTTPError as e:
            if e.code == 429:
                STATS["429"] += 1
                time.sleep(min(20, 2 * (k + 1)))
                continue
            if e.code in (400, 404):
                STATS["fail"] += 1
                return None
            time.sleep(2 + 2 * k)
        except Exception:
            time.sleep(2 + 2 * k)
    STATS["fail"] += 1
    return None


def ts(s):
    """ISO time 'YYYY-MM-DDTHH:MM:SSZ' -> unix seconds (UTC)."""
    return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))


def fl(x):
    try:
        return float(x)
    except Exception:
        return None


def fee(p, n=1, rate=0.07):
    """Kalshi taker fee in $ for n contracts at price p (dollars): ceil to the cent of rate*n*p*(1-p)."""
    return math.ceil(round(rate * n * p * (1 - p) * 100, 6)) / 100.0


def fee_per(p, n=10, rate=0.07):
    """Fee per contract ($) when buying n contracts in one order (the rounding spreads over n)."""
    return fee(p, n, rate) / n


def markets(series, status=None, extra=None, max_pages=400, historical=False):
    """All markets of a series (live endpoint; historical=True uses /historical/markets for archived ones)."""
    out, cur = [], ""
    for _ in range(max_pages):
        p = {"series_ticker": series, "limit": 1000}
        if status:
            p["status"] = status
        p.update(extra or {})
        if cur:
            p["cursor"] = cur
        d = get(("/historical" if historical else "") + "/markets", p)
        if not d or not d.get("markets"):
            break
        out += d["markets"]
        cur = d.get("cursor") or ""
        if not cur:
            break
    return out


def candles(series, ticker, start, end, period=1, historical=False):
    """1-minute (period=1) candlesticks of one market between unix start and end."""
    if historical:
        d = get(f"/historical/markets/{ticker}/candlesticks", {"start_ts": start, "end_ts": end, "period_interval": period})
    else:
        d = get(f"/series/{series}/markets/{ticker}/candlesticks", {"start_ts": start, "end_ts": end, "period_interval": period})
    return (d or {}).get("candlesticks") or []


def trades(ticker, min_ts=None, max_ts=None, max_pages=50, historical=False):
    out, cur = [], ""
    for _ in range(max_pages):
        p = {"ticker": ticker, "limit": 1000}
        if min_ts:
            p["min_ts"] = int(min_ts)
        if max_ts:
            p["max_ts"] = int(max_ts)
        if cur:
            p["cursor"] = cur
        d = get("/historical/trades" if historical else "/markets/trades", p)
        if not d or not d.get("trades"):
            break
        out += d["trades"]
        cur = d.get("cursor") or ""
        if not cur or len(d["trades"]) < p["limit"]:      # a short page is the last one (saves an empty request)
            break
    return out
