"""Polite read-only client for Kalshi PUBLIC market data (no key) + other free public sources, with a disk cache.
Never places an order. Requests to one host are >= MIN_GAP s apart, exponential back-off on 429.
Cache dir: $KC_CACHE or research/kalshi_edge_C/cache (gitignored, large)."""
import calendar, hashlib, json, os, threading, time, urllib.error, urllib.parse, urllib.request

B = "https://api.elections.kalshi.com/trade-api/v2"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CACHE = os.environ.get("KC_CACHE") or os.path.join(HERE, "cache")
os.makedirs(CACHE, exist_ok=True)
MIN_GAP = float(os.environ.get("KC_GAP", "0.3"))
_last = {}
_lock = threading.Lock()
STATS = {"net": 0, "cache": 0, "429": 0, "fail": 0}


def get(path, params=None, base=B, cache=True, tries=9, gap=None):
    url = (base + path if not path.startswith("http") else path) + (("?" + urllib.parse.urlencode(params)) if params else "")
    fn = os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest() + ".json")
    if cache and os.path.exists(fn):
        STATS["cache"] += 1
        try:
            return json.load(open(fn))
        except Exception:
            pass
    host = urllib.parse.urlparse(url).netloc
    g = MIN_GAP if gap is None else gap
    for k in range(tries):
        with _lock:
            w = g - (time.time() - _last.get(host, 0))
            if w > 0:
                time.sleep(w)
            _last[host] = time.time()
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-client"}), timeout=40)
            d = json.load(r)
            STATS["net"] += 1
            if cache:
                tmp = fn + ".%d.tmp" % threading.get_ident()
                json.dump(d, open(tmp, "w"))
                os.replace(tmp, fn)
            return d
        except urllib.error.HTTPError as e:
            if e.code == 429:
                STATS["429"] += 1
                with _lock:  # everybody waits: the limit is per IP
                    _last[host] = time.time() + min(30, 1.5 * (k + 1))
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


def settled_markets(series, lo, hi, historical=False):
    """all settled yes/no markets of a series closing in [lo, hi]. historical=True uses /historical/markets."""
    out, cur = [], ""
    while True:
        p = {"series_ticker": series, "limit": 1000, "min_close_ts": lo, "max_close_ts": hi}
        if not historical:
            p["status"] = "settled"
        if cur:
            p["cursor"] = cur
        d = get(("/historical" if historical else "") + "/markets", p)
        if not d or not d.get("markets"):
            break
        out += [m for m in d["markets"] if m.get("result") in ("yes", "no")]
        cur = d.get("cursor") or ""
        if not cur:
            break
    return out
