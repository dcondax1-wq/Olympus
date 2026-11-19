#!/usr/bin/env python3
"""Polite GET-only client for Kalshi's PUBLIC market data (no key, no account, never an order).
At most 1 request per second (5 research helpers share one IP); responses cached (gzip) under KALSHI_CACHE
(default /home/user/kalshi_cache/krew/http). Stdlib only."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import threading
import time
import urllib.parse
import urllib.request

K = "https://api.elections.kalshi.com/trade-api/v2"
UA = "rewards-maker-research (read-only)"
CACHE = os.environ.get("KALSHI_CACHE", "/home/user/kalshi_cache/krew/http")
GAP = float(os.environ.get("KALSHI_GAP", "1.05"))        # seconds between requests (>= 1.0: the shared-IP rule)
_lock, _last = threading.Lock(), [0.0]
STATS = {"net": 0, "cache": 0, "fail": 0}


RATE_FILE = os.environ.get("KALSHI_RATE_FILE", "/home/user/kalshi_cache/krew/.rate")


def _wait_turn():
    """one request a second across ALL of this team's processes (a flock'd file holds the last request time)."""
    with _lock:
        try:
            import fcntl
            os.makedirs(os.path.dirname(RATE_FILE), exist_ok=True)
            with open(RATE_FILE, "a+") as fh:
                fcntl.flock(fh, fcntl.LOCK_EX)
                fh.seek(0)
                try:
                    last = float(fh.read().strip() or 0)
                except ValueError:
                    last = 0.0
                w = last + max(GAP, 1.0) - time.time()
                if w > 0:
                    time.sleep(w)
                fh.seek(0)
                fh.truncate()
                fh.write("%.3f" % time.time())
                fh.flush()
                fcntl.flock(fh, fcntl.LOCK_UN)
            _last[0] = time.time()
            return
        except (ImportError, OSError):
            pass
        w = _last[0] + max(GAP, 1.0) - time.time()
        if w > 0:
            time.sleep(w)
        _last[0] = time.time()


def url(path, params=None):
    return K + path + ("?" + urllib.parse.urlencode(params) if params else "")


def get(path, params=None, cache=True):
    """GET a public endpoint; None on 400/404 or after retries. `cache` False = always fresh (not stored)."""
    u = url(path, params)
    fn = os.path.join(CACHE, hashlib.md5(u.encode()).hexdigest() + ".json.gz")
    if cache and os.path.exists(fn):
        try:
            with gzip.open(fn, "rt") as f:
                STATS["cache"] += 1
                return json.load(f)
        except (OSError, ValueError):
            pass
    for k in range(5):
        _wait_turn()
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40)
            d = json.load(r)
            STATS["net"] += 1
            if cache:
                os.makedirs(CACHE, exist_ok=True)
                with gzip.open(fn, "wt") as f:
                    json.dump(d, f)
            return d
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None)
            if code in (400, 404):
                STATS["fail"] += 1
                return None
            time.sleep(3.0 * (k + 1) + (10 if code == 429 else 0))
    STATS["fail"] += 1
    return None


def paged(path, params, key, cursor_key="cursor", max_pages=200, cache=True):
    out, cur = [], None
    for _ in range(max_pages):
        q = dict(params)
        if cur:
            q["cursor"] = cur
        d = get(path, q, cache=cache) or {}
        rows = d.get(key) or []
        out += rows
        cur = d.get(cursor_key) or d.get("next_cursor")
        if not cur or not rows:
            break
    return out
