"""K8 live re-check: extend the public tape cache (Kalshi PUBLIC GET only, no key, <= 1 request/s, generic User-Agent).
Seeds research/kalshi_k8_live/data/tape.jsonl from the earlier caches, then adds only the missing settled leg markets.
    python research/kalshi_k8_live/fetch.py [--start 2026-11-16] [--end 2026-11-21]
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, sys, urllib.request, urllib.error
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from engine import kalshi_adapt as KA, kalshi_clock as KC  # noqa: E402
TAPE = os.path.join(HERE, "data", "tape.jsonl")
SEEDS = [os.path.join(ROOT, "research", "kalshi_k8_day", "data", "tape.jsonl"),
         os.path.join(ROOT, "research", "kalshi_k8_monday", "data", "tape_fresh.jsonl")]


def _http(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": "python-research-client/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def seed():
    have = KA.read_tape(TAPE)
    add = 0
    os.makedirs(os.path.dirname(TAPE), exist_ok=True)
    with open(TAPE, "a", encoding="utf-8") as fh:
        for p in SEEDS:
            for t, r in KA.read_tape(p).items():
                if t not in have:
                    have[t] = r
                    fh.write(json.dumps(r, separators=(",", ":")) + "\n")
                    add += 1
    return add


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-11-16")
    ap.add_argument("--end", default=dt.date.today().isoformat())
    a = ap.parse_args(argv)
    seeded = seed()
    cfg = KC.load_config()[0]
    pub = KA.Public(http=_http, gap=1.05)
    r = KA.fetch_tape(pub, TAPE, dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end), cfg)
    print(json.dumps({"seeded": seeded, **r, "errors": pub.errors, "rows": len(KA.read_tape(TAPE))}))


if __name__ == "__main__":
    main()
