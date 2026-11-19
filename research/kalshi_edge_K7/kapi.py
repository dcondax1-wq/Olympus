"""K7: polite read-only client for Kalshi PUBLIC market data (GET only, no key, never an order).

At most 1 request per second across all K7 processes (a lock file holds the time of the last request), back-off on 429.
Small responses (listings) are cached gzipped in /home/user/kalshi_cache/knew2/ (KK7_CACHE); candle responses are not
cached raw (too big): the harvester stores compact arrays instead."""
import fcntl
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.parse

import requests

KAL = "https://api.elections.kalshi.com/trade-api/v2"
CACHE = os.environ.get("KK7_CACHE", "/home/user/kalshi_cache/knew2")
os.makedirs(CACHE, exist_ok=True)
GAP = float(os.environ.get("KK7_GAP", "1.05"))     # seconds between requests (shared IP: 1 per second at most)
LOCK = os.path.join(CACHE, ".rate.lock")
STATS = {"net": 0, "cache": 0, "err": 0}
_S = None


def _sess():
    global _S
    if _S is None:
        _S = requests.Session()
        _S.headers["User-Agent"] = "research-client (read-only)"
    return _S


def _wait_slot():
    """Block until GAP seconds have passed since the last request of ANY K7 process, then claim the slot."""
    with open(LOCK, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        try:
            last = float(fh.read().strip() or 0)
        except ValueError:
            last = 0.0
        w = last + GAP - time.time()
        if w > 0:
            time.sleep(w)
        fh.seek(0)
        fh.truncate()
        fh.write("%.3f" % time.time())
        fh.flush()
        fcntl.flock(fh, fcntl.LOCK_UN)


def get(path, params=None, cache=True, tries=8):
    url = (path if path.startswith("http") else KAL + path) + (("?" + urllib.parse.urlencode(params)) if params else "")
    fn = os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest() + ".json.gz")
    if cache and os.path.exists(fn):
        try:
            with gzip.open(fn, "rt") as fh:
                STATS["cache"] += 1
                return json.load(fh)
        except Exception:
            pass
    if os.environ.get("KK7_OFFLINE"):
        return None
    for k in range(tries):
        _wait_slot()
        try:
            r = _sess().get(url, timeout=60)
        except Exception as e:  # network hiccup
            STATS["err"] += 1
            print("net error", type(e).__name__, file=sys.stderr, flush=True)
            time.sleep(3 * (k + 1))
            continue
        if r.status_code == 200:
            STATS["net"] += 1
            d = r.json()
            if cache:
                tmp = fn + ".%d.tmp" % os.getpid()
                with gzip.open(tmp, "wt") as fh:
                    json.dump(d, fh)
                os.replace(tmp, fn)
            return d
        if r.status_code in (400, 404):
            STATS["err"] += 1
            return None
        STATS["err"] += 1
        if r.status_code == 429:
            time.sleep(5 * (k + 1))
        else:
            time.sleep(3 * (k + 1))
    return None


def fnum(x):
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return None
