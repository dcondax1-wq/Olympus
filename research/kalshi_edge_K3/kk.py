"""Team K3: polite read-only client for Kalshi PUBLIC market data (no key, GET only) and other free public sources.
Never places an order, never sends a key. Requests to one host are >= MIN_GAP s apart (about 3-4 per second), back-off on 429.
Cache: research/kalshi_edge_K3/cache (gitignored)."""
import calendar, hashlib, json, math, os, threading, time, urllib.error, urllib.parse, urllib.request

B = "https://api.elections.kalshi.com/trade-api/v2"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CACHE = os.path.join(HERE, "cache")
os.makedirs(CACHE, exist_ok=True)
os.makedirs(DATA, exist_ok=True)
MIN_GAP = float(os.environ.get("KK_GAP", "0.28"))
_last = {}
_lock = threading.Lock()
STATS = {"net": 0, "cache": 0, "429": 0, "fail": 0}


def get(path, params=None, base=B, cache=True, tries=8, raw=False):
    url = (base + path if not path.startswith("http") else path) + (("?" + urllib.parse.urlencode(params)) if params else "")
    fn = os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest() + (".txt" if raw else ".json"))
    if cache and os.path.exists(fn):
        STATS["cache"] += 1
        try:
            return open(fn).read() if raw else json.load(open(fn))
        except Exception:
            pass
    host = urllib.parse.urlparse(url).netloc
    for k in range(tries):
        with _lock:
            w = MIN_GAP - (time.time() - _last.get(host, 0))
            if w > 0:
                time.sleep(w)
            _last[host] = time.time()
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-client"}), timeout=60)
            body = r.read().decode("utf-8", "replace")
            d = body if raw else json.loads(body)
            STATS["net"] += 1
            if cache:
                tmp = fn + ".%d.tmp" % threading.get_ident()
                open(tmp, "w").write(body)
                os.replace(tmp, fn)
            return d
        except urllib.error.HTTPError as e:
            if e.code == 429:
                STATS["429"] += 1
                with _lock:
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


def c(x):
    """dollar string -> integer cents"""
    v = fl(x)
    return None if v is None else int(round(v * 100))


def fee_c(p_c, n=1, rate=0.07):
    """Kalshi taker fee in cents for ONE order of n contracts at price p_c cents: ceil(rate * n * p * (1-p)), to the cent."""
    p = p_c / 100.0
    return math.ceil(round(rate * n * p * (1 - p) * 100, 9))
