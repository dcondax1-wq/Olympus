"""ntfy budget (2026-11-20 09:45 ET: the PC went silent; ntfy.sh's per-IP day cap of 250 was spent). tools/pc_report.py, offline, ~1 s.
  a. this morning's REAL ext posts (tests/fixtures/ntfy_morning_2026-11-20.json.gz, the public topic 22:15 -> 09:45 ET, ATLAS's short open
     03:45 -> 07:15 = 3.5 h): with the old hash every run was an ext run (47 of 47: the Kalshi blocks' clocks and paper sums change every
     15 min); with the fixed ext_hash only real news (the entry, the exit, a brief event, a Kalshi fill) plus every 2nd run (EXT_EVERY_S)
  b. a whole UTC day (96 runs) with a trade open 4 hours: core + ext + chart + trade alerts stay well under NTFY_DAY_CAP - TRADE_ALERT_RESERVE
  c. ntfy's OWN count (GET /v1/account): parsed; near the reserve the ext and the chart candles hold back (the core still goes); the old
     counter alone (this file's posts + instant alerts) could not see the other programs' posts (Kalshi, data feed, learning, self-heal ...)
    python -X utf8 -m tests.test_ntfy_budget
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import pc_report as R  # noqa: E402

RES = []
FX = os.path.join(ROOT, "tests", "fixtures", "ntfy_morning_2026-11-20.json.gz")


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:900]}"))


def old_hash(exts):
    """ext_hash as the PC ran it this morning (only the open trade's live $ and block "t" left out: batch 2)"""
    keep = [{k: ({a: b for a, b in v.items() if a != "t"} if isinstance(v, dict) else v) for k, v in (e.get("x") or {}).items() if k != "glance"} for e in exts]
    return hashlib.sha1(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()


def replay(runs, hash_fn):
    """the run_once rule: an ext run when the news changed or EXT_EVERY_S passed since the last one -> (ext runs, [et times])"""
    last_h = last_t = None
    out = []
    for r in runs:
        h = hash_fn(r["exts"])
        if h != last_h or last_t is None or r["rt"] - last_t >= R.EXT_EVERY_S:
            out.append(r["rt"])
            last_h, last_t = h, r["rt"]
    return out


def main():
    runs = json.load(gzip.open(FX, "rt"))["runs"]
    old = replay(runs, old_hash)
    new = replay(runs, R.ext_hash)
    check(f"a. this morning (47 runs, 22:15 -> 09:45 ET): the PC's old hash made EVERY run an ext run ({len(old)} of {len(runs)}, 2 posts each)",
          len(old) == len(runs) == 47, len(old))
    check(f"a. the fixed ext_hash: {len(new)} ext runs (about every 3rd run + the real news: the entry 04:00, the exit 07:15, brief events), so {2 * (len(old) - len(new))} posts saved",
          len(new) <= 24 and len(new) >= 15, len(new))
    k = [r for r in runs if r["exts"]]
    a, b = k[-2]["exts"], k[-1]["exts"]
    check("a. the Kalshi clocks and paper sums are no longer news (two runs that differ only there hash the same); a new Kalshi fill still is",
          R.ext_hash(a) == R.ext_hash(b) and old_hash(a) != old_hash(b)
          and R.ext_hash(a) != R.ext_hash([{**e, "x": {**e["x"], "kalshi_rewards": {**(e["x"].get("kalshi_rewards") or {}), "fills": 99}}}
                                             if "kalshi_rewards" in (e.get("x") or {}) else e for e in a]))
    # b. a whole UTC day: 96 runs, the trade open 4 h (its live $ moves every run), the ext's other news 6 times, alerts + chart
    def day(hash_fn):
        last_h = last_t = None
        posts = 0
        for i in range(96):
            t = 1795000000 + i * 900
            news = sum(1 for j in (10, 30, 40, 50, 70, 85) if i >= j)
            tr_open = 20 <= i < 36
            x = {"at": {"t": t, "a": [{"id": "atlas", "tr": [[1, None if tr_open else 2, -1, 1, 26380.75, 26379.5, 26122.75, None if tr_open else "TARGET",
                                                             10.0 * i if tr_open else 514.18, 0.1 * i if tr_open else 6.6]]}]},
                 "kalshi_rewards": {"updated": str(t), "net": 39 + i * 0.3, "days": i / 96, "fills": news}, "kalshi_live": {"u": str(t)}, "brd": {"ev": news}}
            exts = [{"part": 0, "x": x}, {"part": 1, "x": {"mf": {"a": [news]}}}]
            h = hash_fn(exts)
            if h != last_h or last_t is None or t - last_t >= R.EXT_EVERY_S:
                posts += len(exts)
                last_h, last_t = h, t
            posts += 1                                       # the core
        return posts + R.BARS_DAY_MAX + 10                   # + the chart's daily share + ~10 trade alerts / pushes
    n_old, n_new = day(old_hash), day(R.ext_hash)
    check(f"b. a whole UTC day with a trade open 4 h: {n_new} posts (was {n_old} with the old hash) <= NTFY_DAY_CAP - TRADE_ALERT_RESERVE - 30 "
          f"= {R.NTFY_DAY_CAP - R.TRADE_ALERT_RESERVE - 30} (room for the other programs)",
          n_old > R.NTFY_DAY_CAP and n_new <= R.NTFY_DAY_CAP - R.TRADE_ALERT_RESERVE - 30, (n_new, n_old))
    # c. ntfy's own count
    acct = {"username": "*", "limits": {"basis": "ip", "messages": 250}, "stats": {"messages": 231, "messages_remaining": 19, "reset_at": 1795264269}}
    calls = []

    def http(method, url, body=None, headers=None, timeout=10):
        calls.append((method, url))
        return (200, json.dumps(acct)) if url.endswith("/v1/account") else (500, "")
    q = R.ntfy_quota("https://ntfy.sh", http=http)
    check("c. ntfy_quota reads ntfy's own per-IP count with one GET (not a message)", q == {"used": 231, "remaining": 19, "limit": 250, "reset_at": 1795264269}
          and calls == [("GET", "https://ntfy.sh/v1/account")], (q, calls))
    check("c. near the reserve: 19 left -> 2 ext posts + the core would leave 16 >= 12: go; 14 left -> hold (the core still goes); unknown -> the old counter decides",
          R.quota_holds(q, 2) is False and R.quota_holds({"remaining": 14}, 2) is True and R.quota_holds(None, 2) is False)
    check("c. ntfy down or a junk answer -> None (never raises)", R.ntfy_quota("https://ntfy.sh", http=lambda *a, **k: (0, "")) is None
          and R.ntfy_quota("https://ntfy.sh", http=lambda *a, **k: (200, "nope")) is None)
    due, why = R.bars_due({}, {"t": 1795000000, "n": 50}, 1795000100, True, remaining=12)
    check("c. the chart candles hold too when ntfy says the reserve is near", due is False and "kept for trade alerts" in why, why)


if __name__ == "__main__":
    main()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    sys.exit(0 if ok == n else 1)
