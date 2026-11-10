"""Tiny polite client for Kalshi PUBLIC market data (no key, read-only) + disk cache."""
import json, os, time, urllib.request, urllib.parse, hashlib
B = "https://api.elections.kalshi.com/trade-api/v2"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(CACHE, exist_ok=True)
_last = [0.0]


def get(path, params=None, base=B):
    url = base + path + (("?" + urllib.parse.urlencode(params)) if params else "")
    fn = os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest() + ".json")
    if os.path.exists(fn):
        return json.load(open(fn))
    for k in range(6):
        w = 0.25 - (time.time() - _last[0])
        if w > 0:
            time.sleep(w)
        _last[0] = time.time()
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-client"}), timeout=25)
            d = json.load(r)
            json.dump(d, open(fn, "w"))
            return d
        except Exception:
            time.sleep(1.5 * (k + 1))
    return None
