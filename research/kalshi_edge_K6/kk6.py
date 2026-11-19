"""K6 polite read-only client: Kalshi PUBLIC market data (no key, GET only, never an order) and free official public
sources (US Treasury, FRED csv downloads, NY Fed). One request at a time per host, at most 1 a second (5 Kalshi helpers
share this IP), back-off on 429. Disk cache (gzip) in $K6_CACHE or /home/user/kalshi_cache/knew1 (outside the repo)."""
import sys, calendar, gzip, hashlib, json, math, os, threading, time, urllib.error, urllib.parse, urllib.request

B = "https://api.elections.kalshi.com/trade-api/v2"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CACHE = os.environ.get("K6_CACHE") or "/home/user/kalshi_cache/knew1"
os.makedirs(CACHE, exist_ok=True)
GAP = float(os.environ.get("K6_GAP", "1.05"))
_last, _lock = {}, threading.Lock()
STATS = {"net": 0, "cache": 0, "429": 0, "fail": 0}


def get(path, params=None, base=B, cache=True, tries=10, raw=False, retry400=True):
    url = (base + path if not path.startswith("http") else path) + (("?" + urllib.parse.urlencode(params)) if params else "")
    fn = os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest() + (".txt.gz" if raw else ".json.gz"))
    if cache and os.path.exists(fn):
        STATS["cache"] += 1
        try:
            with gzip.open(fn, "rt") as fh:
                return fh.read() if raw else json.load(fh)
        except Exception:
            pass
    if os.environ.get("K6_OFFLINE"):
        return None
    host = urllib.parse.urlparse(url).netloc
    for k in range(tries):
        with _lock:
            w = GAP - (time.time() - _last.get(host, 0))
            if w > 0:
                time.sleep(w)
            _last[host] = time.time()
        try:
            hd = {"User-Agent": "research-client (read-only)"} if "kalshi" in host else {}   # FRED drops custom agents
            r = urllib.request.urlopen(urllib.request.Request(url, headers=hd), timeout=60).read().decode("utf-8", "replace")
            d = r if raw else json.loads(r)
            STATS["net"] += 1
            if cache:
                tmp = fn + ".%d.tmp" % threading.get_ident()
                with gzip.open(tmp, "wt") as fh:
                    fh.write(r)
                os.replace(tmp, fn)
            return d
        except urllib.error.HTTPError as e:
            if e.code == 429:
                STATS["429"] += 1
                with _lock:
                    _last[host] = time.time() + min(10, 1.0 * (k + 1))
                continue
            if e.code in (400, 404):
                if k >= 2 or not retry400:     # seen transiently under load: two more tries, then give up
                    STATS["fail"] += 1
                    return None
                time.sleep(3)
                continue
            time.sleep(2 + 2 * k)
        except Exception as e:
            STATS["err"] = STATS.get("err", 0) + 1
            if STATS["err"] % 20 == 1:
                print("kk6 error", repr(e)[:200], url[:120], file=sys.stderr, flush=True)
            time.sleep(2 + 2 * k)
    STATS["fail"] += 1
    return None


def ts(s):
    return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))


def fl(x):
    try:
        return float(x)
    except Exception:
        return None


def cents(x):
    v = fl(x)
    return None if v is None else int(round(v * 100))


def g(m, *names):
    for n in names:
        if m.get(n) is not None:
            return m[n]
    return None


def fee_order(p, stake=10.0, rate=0.07):
    """Kalshi taker fee for one order of C = floor(stake / p) contracts at price p (dollars): 0.07 x C x p x (1-p),
    rounded UP to the cent. Returns (contracts, fee dollars)."""
    c = max(1, int(stake // max(p, 0.01)))
    return c, math.ceil(round(rate * c * p * (1 - p) * 100, 6)) / 100.0


def pnl_per_dollar(p, won, stake=10.0):
    """Taker buy at the ask p: profit per $1 of cost (price + fee), fee rounded up per $10 order."""
    c, fe = fee_order(p, stake)
    cost = c * p + fe
    return (c * (1.0 if won else 0.0) - cost) / cost


def markets(series, historical=False, extra=None, max_pages=400):
    """every market of a series (live listing: status=settled unless extra overrides; historical: /historical/markets)."""
    out, cur, n = [], "", 0
    while n < max_pages:
        p = {"series_ticker": series, "limit": 1000}
        if not historical and not (extra and "status" in extra):
            p["status"] = "settled"
        p.update(extra or {})
        if cur:
            p["cursor"] = cur
        d = get(("/historical" if historical else "") + "/markets", p)
        n += 1
        if not d or not d.get("markets"):
            break
        out += d["markets"]
        cur = d.get("cursor") or ""
        if not cur:
            break
    return out
