"""Polite read-only client for Kalshi PUBLIC market data (no key, never an order) + free public sources (IEM, NWS), with a disk cache.
Cache: research/kalshi_edge_K1/cache (gitignored). One request at a time per host, >= KK_GAP s apart, back-off on 429
(other research sessions share the IP, so 429s happen: everybody waits)."""
import calendar, gzip, hashlib, json, math, os, threading, time, urllib.error, urllib.parse, urllib.request

B = "https://api.elections.kalshi.com/trade-api/v2"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CACHE = os.environ.get("KK_CACHE") or os.path.join(HERE, "cache")
os.makedirs(CACHE, exist_ok=True)
GAP = float(os.environ.get("KK_GAP", "0.3"))
_last, _lock = {}, threading.Lock()
STATS = {"net": 0, "cache": 0, "429": 0, "fail": 0}


def get(path, params=None, base=B, cache=True, tries=12, gap=None, raw=False, headers=None):
    url = (base + path if not path.startswith("http") else path) + (("?" + urllib.parse.urlencode(params)) if params else "")
    fn = os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest() + (".txt.gz" if raw else ".json.gz"))
    if cache and os.path.exists(fn):
        STATS["cache"] += 1
        try:
            with gzip.open(fn, "rt") as fh:
                return fh.read() if raw else json.load(fh)
        except Exception:
            pass
    host = urllib.parse.urlparse(url).netloc
    g = GAP if gap is None else gap
    h = {"User-Agent": "research-client"}
    h.update(headers or {})
    for k in range(tries):
        with _lock:
            w = g - (time.time() - _last.get(host, 0))
            if w > 0:
                time.sleep(w)
            _last[host] = time.time()
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60).read().decode()
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
                    _last[host] = time.time() + min(20, 1.0 * (k + 1))
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
    return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))


def fl(x):
    try:
        return float(x)
    except Exception:
        return None


def cents(x):
    v = fl(x)
    return None if v is None else int(round(v * 100))


def fee_c(p_c, maker=False):
    """Kalshi fee in cents for ONE contract at price p_c cents, rounded UP to the cent (conservative: 1-lot orders).
    taker 0.07*p*(1-p); maker 0.0175*p*(1-p) (only some series charge makers; assumed charged everywhere = conservative)."""
    p = p_c / 100.0
    r = 0.0175 if maker else 0.07
    return math.ceil(round(r * p * (1 - p) * 100, 6))


def all_markets(series, historical=False, extra=None, max_pages=200):
    out, cur, n = [], "", 0
    while n < max_pages:
        p = {"series_ticker": series, "limit": 1000}
        if not historical:
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
