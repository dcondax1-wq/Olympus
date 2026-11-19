#!/usr/bin/env python3
"""Red team (2026-11-18): a polite GET-only client for Kalshi's PUBLIC market data (no key, no account, never an order).
At most ONE request per second across all my processes (a lock file holds the last request time), gzip cache outside the
repo in /home/user/kalshi_cache/kred/http (override with KRED_CACHE). Stdlib only."""
from __future__ import annotations

import fcntl
import gzip
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request

K = "https://api.elections.kalshi.com/trade-api/v2"
UA = "read-only research client"
CACHE = os.environ.get("KRED_CACHE", "/home/user/kalshi_cache/kred")
GAP = 1.05                     # seconds between requests (the brief: at most 1 per second)
LOCK = os.path.join(CACHE, "rate.lock")
COUNT = [0]


def _wait_turn():
    os.makedirs(CACHE, exist_ok=True)
    with open(LOCK, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        try:
            last = float(f.read().strip() or 0)
        except ValueError:
            last = 0.0
        w = last + GAP - time.time()
        if w > 0:
            time.sleep(w)
        f.seek(0)
        f.truncate()
        f.write("%.3f" % time.time())
        f.flush()
        fcntl.flock(f, fcntl.LOCK_UN)


def get(path, params=None, cache=True):
    """GET K + path (JSON) or None on 400/404 / repeated failure. cache=True keeps the answer forever (use it for closed
    history only); cache=False always asks again (live books, active programs)."""
    if any(bad in path for bad in ("/portfolio", "/orders")):
        raise ValueError("read-only client: no portfolio / order endpoints")
    u = K + path + ("?" + urllib.parse.urlencode(params) if params else "")
    fn = os.path.join(CACHE, "http", hashlib.md5(u.encode()).hexdigest() + ".json.gz")
    if cache and os.path.exists(fn):
        with gzip.open(fn, "rt") as f:
            return json.load(f)
    for k in range(5):
        _wait_turn()
        COUNT[0] += 1
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40)
            d = json.load(r)
            if cache:
                os.makedirs(os.path.dirname(fn), exist_ok=True)
                with gzip.open(fn, "wt") as f:
                    json.dump(d, f)
            return d
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None)
            if code in (400, 404):
                return None
            time.sleep(3.0 * (k + 1) if code != 429 else 20.0)
    return None


def paged(path, params, key, cursor_key="cursor", cache=True, max_pages=200):
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
