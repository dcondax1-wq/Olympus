#!/usr/bin/env python3
"""K7 step 1: every SETTLED market of the picked series (live /markets + /historical/markets), compact rows, PUBLIC GET only.
    python research/kalshi_edge_K7/lists.py            # all families in universe.py (resumable: a saved series is skipped)
Writes /home/user/kalshi_cache/knew2/lists/<SERIES>.json.gz (not in the repo)."""
import datetime as dt
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kapi  # noqa: E402
import universe  # noqa: E402

OUT = os.path.join(kapi.CACHE, "lists")
MAX_PAGES = int(os.environ.get("K7_MAX_PAGES", "4"))   # per endpoint (live / historical): newest 4,000 + newest older 4,000
os.makedirs(OUT, exist_ok=True)


def ts(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def compact(m, hist):
    return {"t": m["ticker"], "e": m.get("event_ticker"), "open": ts(m.get("open_time")), "close": ts(m.get("close_time")),
            "exp": ts(m.get("expected_expiration_time")), "late": ts(m.get("latest_expiration_time")),
            "occ": ts(m.get("occurrence_datetime")), "sett": ts(m.get("settlement_ts")), "cce": m.get("can_close_early"),
            "res": m.get("result"), "vol": kapi.fnum(m.get("volume_fp") or m.get("volume")), "mt": m.get("market_type"),
            "st": m.get("strike_type"), "sub": (m.get("yes_sub_title") or "")[:40], "hist": hist,
            "title": (m.get("title") or "")[:90]}


def listing(series):
    rows = {}
    for hist in (False, True):
        cur = None
        for _ in range(MAX_PAGES):
            p = {"series_ticker": series, "limit": 1000}
            if not hist:
                p["status"] = "settled"
            if cur:
                p["cursor"] = cur
            d = kapi.get(("/historical" if hist else "") + "/markets", p, cache=False)
            if not d or not d.get("markets"):
                break
            for m in d["markets"]:
                if m.get("result") in ("yes", "no") and m.get("market_type", "binary") == "binary":
                    rows[m["ticker"]] = compact(m, hist)
            cur = d.get("cursor")
            if not cur:
                break
    return sorted(rows.values(), key=lambda r: r["close"] or 0)


def main():
    pick = universe.pick()
    todo = [(fam, s["t"]) for fam, L in pick.items() for s in L]
    for i, (fam, s) in enumerate(todo):
        fn = os.path.join(OUT, s + ".json.gz")
        if os.path.exists(fn):
            continue
        rows = listing(s)
        tmp = fn + ".tmp"
        with gzip.open(tmp, "wt") as fh:
            json.dump(rows, fh)
        os.replace(tmp, fn)
        first = dt.datetime.fromtimestamp(rows[0]["close"], dt.timezone.utc).date() if rows else None
        last = dt.datetime.fromtimestamp(rows[-1]["close"], dt.timezone.utc).date() if rows else None
        print("%3d/%d %-15s %-26s markets %6d events %5d  %s .. %s  net %d" % (i + 1, len(todo), fam, s, len(rows),
              len({r["e"] for r in rows}), first, last, kapi.STATS["net"]), flush=True)


if __name__ == "__main__":
    main()
