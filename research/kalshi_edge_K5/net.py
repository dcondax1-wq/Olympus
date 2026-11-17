"""K5 (copied from K4): tiny polite GET-only client for Kalshi and Polymarket PUBLIC data (no key, read only) with a disk cache."""
import hashlib
import json
import os
import sys
import threading
import time
import urllib.parse

import requests

KAL = "https://api.elections.kalshi.com/trade-api/v2"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
os.makedirs(CACHE, exist_ok=True)
_last = {}
_lock = threading.Lock()
_tl = threading.local()
ERR = {}


def _sess():
    if not hasattr(_tl, "s"):
        _tl.s = requests.Session()
        _tl.s.headers["User-Agent"] = "research-client (read-only)"
    return _tl.s


def get(url, params=None, gap=0.12, cache=True):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    fn = os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest() + ".json")
    if cache and os.path.exists(fn):
        with open(fn) as f:
            return json.load(f)
    host = urllib.parse.urlparse(url).netloc
    for k in range(6):
        with _lock:  # reserve the next free slot for this host
            now = time.time()
            slot = max(now, _last.get(host, 0.0) + gap)
            _last[host] = slot
            w = slot - now
        if w > 0:
            time.sleep(w)
        try:
            r = _sess().get(url, timeout=30)
            if r.status_code in (400, 404):
                if cache:
                    with open(fn, "w") as f:
                        json.dump(None, f)
                return None
            if r.status_code != 200:
                ERR[r.status_code] = ERR.get(r.status_code, 0) + 1
                if sum(ERR.values()) % 50 == 1:
                    print("http errors", ERR, file=sys.stderr, flush=True)
                time.sleep(2.0 * (k + 1))
                continue
            d = r.json()
            if cache:
                with open(fn, "w") as f:
                    json.dump(d, f)
            return d
        except Exception as e:  # network hiccup
            ERR[type(e).__name__] = ERR.get(type(e).__name__, 0) + 1
            time.sleep(1.5 * (k + 1))
    return None
