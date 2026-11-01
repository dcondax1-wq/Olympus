"""Kalshi in Jarvis (owner 2026-11-01: "where is kalshi ... figure out a way to have it there").

The Kalshi bot runs only on the owner's PC. It writes a small status file (the contract: docs/KALSHI_PUBLISH.md, or
`python -m engine.kalshi_publish --sample`); this pushes that file as kalshi.json, one orphan commit force-pushed to the
branch `kalshi` of the public Pages repo nq-dashboard: the same route, push function and PC git login as the NQ bot's
live.json (engine/live_publish.push), in its own scratch git dir (data/kalshi_pub.git, gitignored). The phone's Kalshi page
(tools/web_public/kalshi/, <site>/kalshi/) and the Jarvis Kalshi card read it from raw.githubusercontent.com.

Read-only and separate from the NQ bot: it never talks to Kalshi, never places anything, and never runs inside the NQ
bot's server. Only the contract's keys leave the PC; credential-looking keys are dropped and local paths redacted
(live_publish.scrub), lists are capped, and the file must stay under MAX_BYTES.

    python -m engine.kalshi_publish --sample                   a sample status file (the contract)
    python -m engine.kalshi_publish --src <file> --once        check the file and push it once (prints the result)
    python -m engine.kalshi_publish --src <file> --loop        every 60 s: push when the file changed (else every 10 min)
LE_KALSHI_SRC sets the default --src; LE_LIVE_REPO overrides the target repo (as for live.json).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from . import live_publish as lp

ROOT = lp.ROOT
BRANCH = "kalshi"
FILE = "kalshi.json"
SCRATCH = os.path.join(ROOT, "data", "kalshi_pub.git")      # gitignored scratch git dir (objects pruned)
MAX_BYTES = 200 * 1024
EVERY_S = 60
KEEPALIVE_S = 600

TOP = ("name", "mode", "status", "running", "t", "balance", "today_pnl", "week_pnl", "total_pnl", "note")
NUM = ("balance", "today_pnl", "week_pnl", "total_pnl")
POS = ("ticker", "title", "side", "contracts", "avg_price", "price", "value", "pnl", "closes")
TRADE = ("t", "ticker", "title", "side", "action", "contracts", "price", "pnl")
CAPS = {"positions": 60, "trades": 40, "days": 120}


def _num(v):
    try:
        f = float(v)
        return round(f, 4) if f == f and abs(f) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _txt(v, n=160):
    return None if v is None else str(v)[:n]


def _row(r, keys):
    if not isinstance(r, dict):
        return None
    out = {}
    for k in keys:
        v = r.get(k)
        if v is None:
            continue
        out[k] = _num(v) if k in ("contracts", "avg_price", "price", "value", "pnl", "t") else _txt(v)
    return out or None


def clean(raw: dict, now: float | None = None) -> dict:
    """The status file -> kalshi.json: only the contract's keys, numbers as numbers, lists capped, secrets dropped, paths
    redacted. Never raises on junk (returns a card with an error note instead)."""
    now = float(now or time.time())
    try:
        src = lp.scrub(raw if isinstance(raw, dict) else {})
        out = {"v": 1, "kind": "kalshi"}
        for k in TOP:
            v = src.get(k)
            if k == "running":
                out[k] = None if v is None else bool(v)
            elif k == "t":
                out[k] = int(_num(v) or now)
            elif k in NUM:
                out[k] = _num(v)
            else:
                out[k] = _txt(v)
        out["positions"] = [x for x in (_row(r, POS) for r in (src.get("positions") or [])[:CAPS["positions"]]) if x]
        out["trades"] = [x for x in (_row(r, TRADE) for r in (src.get("trades") or [])[:CAPS["trades"]]) if x]
        days = []
        for d in (src.get("days") or [])[-CAPS["days"]:]:
            if isinstance(d, (list, tuple)) and len(d) >= 2 and _num(d[1]) is not None:
                days.append([_txt(d[0], 10), _num(d[1])])
            elif isinstance(d, dict) and _num(d.get("pnl")) is not None:
                days.append([_txt(d.get("day") or d.get("date"), 10), _num(d.get("pnl"))])
        out["days"] = days
        out["pub_t"] = int(now)
        return out
    except Exception as e:
        return {"v": 1, "kind": "kalshi", "t": int(now), "pub_t": int(now), "running": None,
                "note": f"status file could not be read: {e.__class__.__name__}", "positions": [], "trades": [], "days": []}


def read(src: str, now: float | None = None) -> tuple[dict | None, str | None]:
    """(kalshi.json payload, error). The status file's own "t" is when the Kalshi bot wrote it (else the file's time)."""
    try:
        with open(src, encoding="utf-8") as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        return None, "status file not found"
    except Exception as e:
        return None, f"status file is not JSON: {e.__class__.__name__}"
    if not isinstance(raw, dict):
        return None, "status file is not a JSON object"
    if raw.get("t") is None:
        try:
            raw = {**raw, "t": int(os.path.getmtime(src))}
        except OSError:
            pass
    p = clean(raw, now)
    size = len(json.dumps(p, separators=(",", ":"), default=str).encode("utf-8"))
    while size > MAX_BYTES and (p["trades"] or p["days"] or p["positions"]):
        for k in ("trades", "days", "positions"):
            if p[k]:
                p[k] = p[k][: len(p[k]) // 2]
                break
        size = len(json.dumps(p, separators=(",", ":"), default=str).encode("utf-8"))
    return p, None


def push_once(src: str, url: str | None = None, git_dir: str = SCRATCH, push_fn=None, now: float | None = None) -> dict:
    """Read the status file and push it as kalshi.json to the branch `kalshi`. {"ok", "error"|"commit", "bytes"}."""
    p, err = read(src, now)
    if err:
        return {"ok": False, "error": err}
    url = url or lp.target_url()
    return (push_fn or lp.push)(p, url, branch=BRANCH, git_dir=git_dir, prune=True, file=FILE)


def loop(src: str, every: float = EVERY_S, keepalive: float = KEEPALIVE_S, log=print, clock=time.time, sleep=time.sleep,
         push_fn=None, url: str | None = None, git_dir: str = SCRATCH, max_rounds: int | None = None) -> None:
    """Push when the status file changed (checked every `every` s), and at least every `keepalive` s."""
    last_sig, last_t, n = None, 0.0, 0
    while max_rounds is None or n < max_rounds:
        n += 1
        try:
            st = os.stat(src)
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            sig = None
        now = clock()
        if sig is not None and (sig != last_sig or now - last_t >= keepalive):
            r = push_once(src, url=url, git_dir=git_dir, push_fn=push_fn, now=now)
            log(f"kalshi publish: {'ok ' + str(r.get('commit')) if r.get('ok') else 'FAILED ' + lp._redact(str(r.get('error')))}")
            if r.get("ok"):
                last_sig, last_t = sig, now
        elif sig is None:
            log("kalshi publish: waiting for the status file")
        sleep(every)


SAMPLE = {
    "name": "Kalshi bot", "mode": "paper", "running": True, "status": "Watching 12 markets", "t": 1793548800,
    "balance": 512.34, "today_pnl": 18.5, "week_pnl": 42.1, "total_pnl": 112.34,
    "positions": [{"ticker": "KXHIGHNY-26NOV02-B58.5", "title": "NYC high 58-59°F on Nov 2", "side": "yes", "contracts": 10,
                   "avg_price": 0.42, "price": 0.55, "value": 5.5, "pnl": 1.3, "closes": "2026-11-02T23:59:00Z"}],
    "trades": [{"t": 1793545200, "ticker": "KXHIGHNY-26NOV02-B58.5", "title": "NYC high 58-59°F on Nov 2", "side": "yes",
                "action": "buy", "contracts": 10, "price": 0.42, "pnl": None}],
    "days": [["2026-10-30", 12.4], ["2026-10-31", -3.1], ["2026-11-01", 18.5]],
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Publish the Kalshi bot's status file to the phone (Jarvis).")
    ap.add_argument("--src", default=os.environ.get("LE_KALSHI_SRC"), help="the Kalshi bot's status JSON file")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true")
    g.add_argument("--loop", action="store_true")
    g.add_argument("--sample", action="store_true")
    g.add_argument("--check", action="store_true", help="show what would be published (no push)")
    a = ap.parse_args(argv)
    if a.sample:
        print(json.dumps(SAMPLE, indent=2, ensure_ascii=False))
        return 0
    if not a.src:
        print("give --src <the Kalshi bot's status file> (or set LE_KALSHI_SRC)")
        return 2
    if a.check:
        p, err = read(a.src)
        print(err or json.dumps(p, indent=2, ensure_ascii=False))
        return 1 if err else 0
    if a.loop:
        loop(a.src)
        return 0
    r = push_once(a.src)
    print(json.dumps(r))
    if r.get("ok"):
        print("phone reads it at:", f"https://raw.githubusercontent.com/{lp.owner_of(lp.target_url()) or 'demetrades2000-coder'}"
              f"/{lp.PAGES_REPO}/{BRANCH}/{FILE}")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
