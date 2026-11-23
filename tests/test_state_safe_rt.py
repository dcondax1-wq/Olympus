"""Red team on night-statesafe (2026-11-23): no false pause on a healthy day, no .bak from another day, no incomplete .bak.
Temp files only, nothing armed, no network.

    python -X utf8 -m tests.test_state_safe_rt        (< 1 s)

1. rotate() COPIES the good file to .bak: the state file is never missing between the renames (FOUND: it was moved away
   first, so every reader saw no live_state.json for a moment, and a save whose 2nd rename failed left only the .bak).
2. a save whose final rename fails after rotate(): the good file is still there -> the next start reads it, nothing damaged,
   no pause (with the move, the next day's start read "missing + yesterday's .bak" = entries paused all day).
3. healthy restart: the main file is used, never the .bak; a first start (no files) = clean, not damaged.
4. a .bak from yesterday is never used for today (old_bak only).
5. bak_complete(): an order for this account in the OIF audit log after the .bak was saved = the .bak may miss it (False);
   an order before it, another account's order, or no audit log (paper) = fine (True).
6. an extra account (engine/multi_account) locked by a damaged-state pause that then reaches its REAL daily loss gets the
   real loss lock (no state_damaged flag), so the keep-alive (which skips damaged-state pauses on purpose) is stopped by it
   (FOUND: check_lock skipped any lock of today, so the damaged-state pause kept standing in for the real loss lock).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import state_safe as S  # noqa: E402
from engine.live import trading_day  # noqa: E402

RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:300]) if info and not ok else ''}")
    RES.append(bool(ok))


def _w(p, d):
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(d, fh)


def main():
    import datetime as dt
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    t_today = int(dt.datetime(2026, 11, 24, 10, 0, tzinfo=ET).timestamp())
    today, yday = trading_day(t_today), trading_day(t_today - 86400)
    day_of = (lambda b: b.get("day"))
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "live_state.json")
        _w(p, {"day": today, "n": 1, "saved_at": t_today})
        S.rotate(p, True)
        check("1. rotate copies: the state file is still there and the .bak holds the same good copy",
              os.path.exists(p) and json.load(open(S.bak_of(p))) == json.load(open(p)) and not os.path.exists(S.bak_of(p) + ".tmp"))

        q = os.path.join(tmp, "s2.json")
        _w(q, {"day": yday, "n": 1})                       # yesterday's last good save
        S.rotate(q, True)                                 # today's first save: rotate, then the final rename fails
        check("2. a failed final rename after rotate(): the good file is still on disk",
              os.path.exists(q))
        got = S.load(q, day_of, today)
        check("2. the next start reads it (not damaged): no false pause", got["src"] == "main" and not got["damaged"], got)

        got = S.load(p, day_of, today)
        check("3. healthy restart: the main file, never the .bak", got["src"] == "main" and not got["damaged"], got)
        got = S.load(os.path.join(tmp, "none.json"), day_of, today)
        check("3. first start (no files): clean, not damaged", got["blob"] is None and not got["damaged"], got)

        r = os.path.join(tmp, "s3.json")
        open(r, "w").write("{torn")
        _w(S.bak_of(r), {"day": yday, "n": 7})
        got = S.load(r, day_of, today)
        check("4. a .bak from yesterday is never today's state (old_bak only)",
              got["blob"] is None and got["damaged"] and (got["old_bak"] or {}).get("n") == 7, got)

        au = os.path.join(tmp, "oif_audit.log")
        stamp = lambda t: dt.datetime.fromtimestamp(t, ET).strftime("%Y-%m-%d %H:%M:%S")
        with open(au, "w", encoding="utf-8") as fh:
            fh.write(f"{stamp(t_today - 600)} ET  Sim101  entry  PLACE;Sim101;MNQ;BUY;1;MARKET;;;DAY;;id1;;\n")
            fh.write(f"{stamp(t_today + 120)} ET  Sim999  entry  PLACE;Sim999;MNQ;BUY;1;MARKET;;;DAY;;id2;;\n")
        bak = {"day": today, "saved_at": t_today}
        check("5. order BEFORE the .bak was saved: complete", S.bak_complete(bak, today, trading_day, au, "Sim101"))
        check("5. another account's later order: still complete", S.bak_complete(bak, today, trading_day, au, "Sim101"))
        with open(au, "a", encoding="utf-8") as fh:
            fh.write(f"{stamp(t_today + 60)} ET  Sim101  entry  PLACE;Sim101;MNQ;SELL;1;MARKET;;;DAY;;id3;;\n")
        check("5. an order for this account AFTER the .bak was saved: NOT complete",
              not S.bak_complete(bak, today, trading_day, au, "Sim101"))
        check("5. no audit log (paper): complete", S.bak_complete(bak, today, trading_day, None, None))
    from engine import multi_account as MA
    a = object.__new__(MA.Account)
    a.id, a.name, a.rules = "fund", "Fund 50K", {"dll": 1000.0}
    a.lock = {"day": today, "reason": "the state file was damaged today", "t": t_today, "state_damaged": True}
    a.day_pnl = lambda d: -1200.0 if d == today else 0.0
    a.log = lambda *x, **k: None
    a.router = type("R", (), {"notify": lambda self, *x, **k: None})()
    a.check_lock(t_today + 60)
    check("6. extras: a damaged-state pause + a REAL daily loss -> the real loss lock (no state_damaged flag)",
          a.lock and "daily loss" in a.lock["reason"] and not a.lock.get("state_damaged"), a.lock)
    real = dict(a.lock)
    a.check_lock(t_today + 120)
    check("6. extras: a real loss lock stays as it is", a.lock == real, a.lock)
    ok = sum(RES)
    print(f"\nstate safe red team: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
