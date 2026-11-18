"""ZEUS audit trail: one timeline of who did what to the bot (read-only; docs/ZEUS_FEATURES.md).

Serious trading systems keep one place that answers "who closed my trade / who stopped the bot / what order went out at
10:31?". ZEUS already writes those facts, in five places; this module only READS them and merges them, newest last:

  data/phone_safety_log.jsonl   every phone safety press, done or refused (engine/phone_safety.py)
  data/handsoff.jsonl           kill / stop / flatten / pause from the PC or phone, manual trades / closes / size changes
                                seen by the reconcile guard, settings edits, unplanned restarts (engine/handsoff.py)
  data/board/events.jsonl       bot started / stopped, order rejected, PASSED / FAILED / LOCKED, payout ready (engine/board_events.py)
  logs/ninjatrader_oif.log      every order line the bot wrote to NinjaTrader (engine/ninjatrader.py); the account field is
                                dropped here (account names stay private)
  data/autoupdate.json          the code updates and roll-backs (engine/autoupdate.py history)

Nothing here writes, routes, arms or sizes anything; a missing or broken file is skipped.
  python -X utf8 -m engine.audit_trail            the last 30 lines
  python -X utf8 -m engine.audit_trail --n 100 --json
Tests: python -X utf8 -m tests.test_phone_safety (section c)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATHS = {
    "phone": os.path.join(ROOT, "data", "phone_safety_log.jsonl"),
    "handsoff": os.path.join(ROOT, "data", "handsoff.jsonl"),
    "board": os.path.join(ROOT, "data", "board", "events.jsonl"),
    "orders": os.path.join(ROOT, "logs", "ninjatrader_oif.log"),
    "update": os.path.join(ROOT, "data", "autoupdate.json"),
}
BOARD_KINDS = ("bot_started", "bot_stopped", "order_rejected", "eval_passed", "eval_failed", "account_locked", "payout_ready",
               "payout_requested")
TAIL_BYTES = 256 * 1024
OIF_RX = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) ET\s+\S.*?\s{2}(oif_\S+)\s{2}(.+)$")


def _tail_lines(path: str, nbytes: int = TAIL_BYTES) -> list:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - nbytes))
            data = fh.read().decode("utf-8", "replace")
    except OSError:
        return []
    lines = data.splitlines()
    return lines[1:] if size > nbytes else lines


def _jsonl(path: str) -> list:
    out = []
    for ln in _tail_lines(path):
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict) and isinstance(r.get("t"), (int, float)):
            out.append(r)
    return out


def oif_text(line: str) -> str:
    """'PLACE;<acct>;MNQ 12-26;BUY;2;MARKET;0;0;DAY;;id;;' -> 'order PLACE BUY 2 MNQ 12-26 MARKET' (no account)."""
    f = str(line).strip().split(";")
    cmd = f[0].upper() if f else "?"
    if cmd == "PLACE" and len(f) >= 6:
        px = f" @ {f[7] or f[6]}" if len(f) > 7 and (f[7] not in ("", "0") or f[6] not in ("", "0")) else ""
        return f"order PLACE {f[3]} {f[4]} {f[2]} {f[5]}{px}"
    if cmd in ("CLOSEPOSITION", "REVERSEPOSITION") and len(f) >= 3:
        return f"order {cmd} {f[2]}"
    if cmd == "CANCEL":
        return "order CANCEL (one order)"
    if cmd == "CHANGE":
        return "order CHANGE (stop / target moved)"
    if cmd in ("CANCELALLORDERS", "FLATTENEVERYTHING"):
        return f"order {cmd}"
    return f"order {cmd}"


def _et_ts(s: str):
    try:
        return int(dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ET).timestamp())
    except ValueError:
        return None


def collect(paths: dict | None = None, since=None) -> list:
    """[{t, src, what}] from every source, oldest first. since: unix seconds (default: no limit)."""
    p = {**PATHS, **(paths or {})}
    rows = []
    phone = _jsonl(p["phone"])
    for r in phone:
        rows.append({"t": int(r["t"]), "src": "phone", "what": f"phone {str(r.get('action') or '?').upper()}: "
                     f"{r.get('status') or '?'} - {str(r.get('msg') or '')[:120]}"})
    phone_t = [int(r["t"]) for r in phone]
    for r in _jsonl(p["handsoff"]):
        if r.get("src") == "phone" and any(abs(int(r["t"]) - t) <= 5 for t in phone_t):
            continue                                   # the same press, already listed from the phone log
        det = str(r.get("detail") or "")[:120]
        rows.append({"t": int(r["t"]), "src": str(r.get("src") or "pc")[:16],
                     "what": f"{str(r.get('kind') or '?').replace('_', ' ')} ({r.get('src') or 'pc'})" + (f": {det}" if det else "")})
    for r in _jsonl(p["board"]):
        if r.get("kind") in BOARD_KINDS:
            rows.append({"t": int(r["t"]), "src": "bot", "what": f"{str(r['kind']).replace('_', ' ')}: {str(r.get('text') or '')[:120]}"})
    for ln in _tail_lines(p["orders"]):
        m = OIF_RX.match(ln)
        if m:
            t = _et_ts(m.group(1))
            if t is not None:
                rows.append({"t": t, "src": "orders", "what": oif_text(m.group(3))})
    try:
        with open(p["update"], encoding="utf-8") as fh:
            hist = (json.load(fh) or {}).get("history") or []
    except Exception:  # noqa: BLE001
        hist = []
    for h in hist:
        if isinstance(h, dict) and isinstance(h.get("t"), (int, float)) and h.get("status") not in (None, "up_to_date"):
            old, new = str(h.get("old") or "")[:7], str(h.get("new") or "")[:7]
            rows.append({"t": int(h["t"]), "src": "update",
                         "what": f"code update {h.get('status')}" + (f" {old} -> {new}" if old and new and old != new else "")
                         + (f": {str(h.get('reason'))[:80]}" if h.get("reason") else "")})
    if since is not None:
        rows = [r for r in rows if r["t"] >= since]
    rows.sort(key=lambda r: r["t"])
    return rows


def recent(n: int = 30, now=None, paths: dict | None = None, days: int = 7) -> list:
    now = time.time() if now is None else now
    return collect(paths, since=now - days * 86400)[-int(n):]


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="ZEUS audit trail: who did what to the bot (read-only)")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rows = recent(a.n, days=a.days)
    if a.json:
        print(json.dumps(rows, indent=1))
        return 0
    if not rows:
        print("ZEUS audit trail: nothing in the last %d days." % a.days)
    for r in rows:
        print(f"{dt.datetime.fromtimestamp(r['t'], ET).strftime('%a %d %b %H:%M:%S')} ET  {r['src']:<8} {r['what']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
