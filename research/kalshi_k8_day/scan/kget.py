"""Kalshi PUBLIC GET only (no key, no auth header, never POST), >= 1.05 s between requests, every answer cached on disk
(so a rerun of scan.py costs no requests for what it already has). Cache: $SCAN_CACHE (default /home/user/kalshi_cache/scan)."""
from __future__ import annotations
import gzip, hashlib, json, os, time, urllib.error, urllib.parse, urllib.request

BASE = "https://api.elections.kalshi.com/trade-api/v2"
CACHE = os.environ.get("SCAN_CACHE", "/home/user/kalshi_cache/scan")
GAP = 1.05
_last = [0.0]
STATS = {"requests": 0, "cache_hits": 0, "errors": 0, "refused": []}
LOG = os.path.join(CACHE, "_requests.log")


def get(path, params=None, cache=True):
    q = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
    url = BASE + path + ("?" + q if q else "")
    os.makedirs(CACHE, exist_ok=True)
    fp = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + ".json.gz")
    if cache and os.path.exists(fp):
        STATS["cache_hits"] += 1
        with gzip.open(fp, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    for attempt in range(4):
        w = _last[0] + GAP - time.monotonic()
        if w > 0:
            time.sleep(w)
        _last[0] = time.monotonic()
        STATS["requests"] += 1
        with open(LOG, "a") as fh:
            fh.write(f"{time.time():.0f} {url}\n")
        req = urllib.request.Request(url, headers={"User-Agent": "research-scan/1", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                j = json.loads(r.read().decode("utf-8", "replace"))
            if cache:
                with gzip.open(fp, "wt", encoding="utf-8") as fh:
                    json.dump(j, fh)
            return j
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (attempt + 1)); continue
            if e.code in (400, 401, 403, 404):
                STATS["refused"].append([e.code, url]); return None
            STATS["errors"] += 1; time.sleep(2 * (attempt + 1))
        except Exception:  # noqa: BLE001
            STATS["errors"] += 1; time.sleep(2 * (attempt + 1))
    return None
