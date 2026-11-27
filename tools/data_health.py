"""DATA HEALTH (day-brief 2026-11-20, TOP25 idea #5): how fresh is every price file in data/?

    python tools/data_health.py            # one line per file + the Board line
    python tools/board.py read             # prints the DATA line (and posts a Board note for a file that just went stale)

For each data/<NAME>.csv price file (NQ / ES bars from TradingView + the PC, VIX / VXN / CBOE vol / GEX daily closes): the
newest bar, its CME trading day, and how many completed CME sessions have passed since (weekends and CME full closures do not
count; engine/cme_calendar). Stale = more than 3 sessions behind. A file that turns stale gets ONE Board note (kind
claude_note, data.keys ["data_stale:<file>:<newest day>", ...], data/board/shared.jsonl; one note for all newly stale
files): the same file at the same newest day is never noted twice. Futures and CBOE files only (no Yahoo); one-off exports (tv_*.csv) are skipped. Read only otherwise.
Test: python -X utf8 -m tests.test_data_health
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
DATA = os.path.join(ROOT, "data")
ET = ZoneInfo("America/New_York")
STALE_SESSIONS = 3
SKIP = re.compile(r"^(tv_|_)")
WHY = {"ES": "ES research bars come from the PC's ES / MES feed: run python tools/data_pull.py --latest (the PC must be on)",
       "VIX": "CBOE daily close: run python tools/context_refresh.py", "VXN": "CBOE daily close: run python tools/context_refresh.py",
       "CBOE": "CBOE vol closes: run python tools/context_refresh.py", "GEX": "SqueezeMetrics GEX: run python tools/context_refresh.py",
       "1d": "daily bars: python tools/data_pull.py --latest rebuilds them from the 1h bars (import_futures.build_daily)"}


def _last_line(path: str) -> str | None:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            n = fh.tell()
            fh.seek(max(0, n - 4096))
            lines = [x for x in fh.read().decode("utf-8", "replace").splitlines() if x.strip()]
        return lines[-1] if lines else None
    except OSError:
        return None


def _header(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.readline().strip().lower()
    except OSError:
        return ""


def trading_day(t: dt.datetime) -> dt.date:
    """CME day of an ET moment (18:00 ET starts the next day)."""
    return (t + dt.timedelta(hours=6)).date()


def newest(path: str):
    """(newest bar as an ET datetime or a date, its trading day) or (None, None)."""
    h = _header(path)
    last = _last_line(path)
    if not last or not h:
        return None, None
    first = last.split(",")[0].strip()
    try:
        if h.startswith("time"):
            e = dt.datetime.fromtimestamp(int(float(first)), ET)
            return e, trading_day(e)
        if h.startswith("date"):
            d = dt.date.fromisoformat(first[:10])
            return d, d
    except ValueError:
        pass
    return None, None


def _closed(d: dt.date) -> bool:
    if d.weekday() >= 5:
        return True
    try:
        from engine import cme_calendar
        return bool(cme_calendar.full_closure(d.isoformat()))
    except Exception:  # noqa: BLE001
        return False


def last_session(now: dt.datetime) -> dt.date:
    """The newest CME session that has finished (17:00 ET) by `now`."""
    d = now.date() if now.hour >= 17 else now.date() - dt.timedelta(days=1)
    while _closed(d):
        d -= dt.timedelta(days=1)
    return d


def sessions_behind(day: dt.date, now: dt.datetime) -> int:
    end = last_session(now)
    n, d = 0, day + dt.timedelta(days=1)
    while d <= end:
        if not _closed(d):
            n += 1
        d += dt.timedelta(days=1)
    return n


def check(now=None, data_dir: str = DATA) -> list:
    now = dt.datetime.fromtimestamp(int(now), ET) if isinstance(now, (int, float)) else (now or dt.datetime.now(ET))
    out = []
    for name in sorted(os.listdir(data_dir)):
        if not name.endswith(".csv") or SKIP.match(name):
            continue
        p = os.path.join(data_dir, name)
        e, day = newest(p)
        if day is None:
            continue
        n = sessions_behind(day, now)
        stem = name[:-4]
        why = WHY.get(stem.split("_")[0]) or (WHY["1d"] if stem.endswith("_1d") and stem.split("_")[0] in ("NQ", "ES") else None)
        out.append({"file": name, "day": day.isoformat(), "sessions": n, "stale": n > STALE_SESSIONS,
                    "why": why if n > STALE_SESSIONS else None})
    return out


def line(rows: list) -> str:
    """The Board's one line: fresh files grouped, stale ones named with their age."""
    if not rows:
        return "DATA  no price files found in data/"
    fresh = [r for r in rows if not r["stale"]]
    stale = [r for r in rows if r["stale"]]
    fd = max((r["day"] for r in fresh), default=None)
    head = f"DATA  {len(fresh)} of {len(rows)} files fresh" + (f" (newest {fd[5:]})" if fd else "")
    if not stale:
        return head + ": all within 3 sessions"
    grp = {}
    for r in stale:
        grp.setdefault((r["day"], r["sessions"]), []).append(r["file"][:-4])
    bits = [f"{', '.join(v)} end {d[5:]} ({n} sessions)" for (d, n), v in sorted(grp.items(), key=lambda kv: (kv[0][0], kv[1]))]
    return head + " | STALE: " + "; ".join(bits)


def note_stale(rows: list, path: str | None = None, now=None, write=True) -> list:
    """ONE Board note naming every file that is stale at a newest day not noted before (data.keys = one key per file, so a
    file is never noted twice for the same newest day). -> [the note] or []."""
    from engine import board_events as B
    path = path or B.shared_file()
    seen = set()
    try:
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    d = json.loads(ln).get("data") or {}
                except ValueError:
                    continue
                seen.update(k for k in (d.get("keys") or []) if isinstance(k, str))
    except OSError:
        pass
    new = [r for r in rows if r["stale"] and f"data_stale:{r['file']}:{r['day']}" not in seen]
    if not new:
        return []
    grp = {}
    for r in new:
        grp.setdefault((r["day"], r["sessions"]), []).append(r["file"][:-4])
    text = "Data stale (more than 3 sessions): " + "; ".join(f"{', '.join(v)} end {d} ({n} sessions)" for (d, n), v in sorted(grp.items()))
    whys = sorted({r["why"].split(" (")[0] for r in new if r.get("why")})
    if whys:
        text += ". Why: " + "; ".join(whys)
    rec = B.make("claude_note", "", text, {"keys": [f"data_stale:{r['file']}:{r['day']}" for r in new]}, src="claude", t=now)
    if rec is None:
        return []
    if write:
        B.append(rec, path)
    return [rec]


def note_fresh(rows: list, path: str | None = None, now=None, write=True) -> list:
    """day-healthqa 2026-11-27: the stale note never got an "all clear", so an old "Data stale ..." stayed the newest data event on
    the Board for days (the 00:02 note on Nov 27 named files that were fresh again a few hours later). When EVERY file is fresh and
    the newest data note is a stale one, ONE note says so (keys ["data_fresh:<newest day>"]; never twice for the same day). -> [note] | []."""
    if not rows or any(r.get("stale") for r in rows):
        return []
    from engine import board_events as B
    path = path or B.shared_file()
    last = None
    try:
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    d = json.loads(ln)
                except ValueError:
                    continue
                ks = [k for k in ((d.get("data") or {}).get("keys") or []) if isinstance(k, str)]
                if any(k.startswith(("data_stale:", "data_fresh:")) for k in ks):
                    last = ks
    except OSError:
        return []
    if not last or not any(k.startswith("data_stale:") for k in last):
        return []
    newest = max(str(r["day"]) for r in rows)
    text = f"Data fresh again: all {len(rows)} price files within {STALE_SESSIONS} sessions (newest {newest}). The earlier 'Data stale' note no longer applies."
    rec = B.make("claude_note", "", text, {"keys": [f"data_fresh:{newest}"]}, src="claude", t=now)
    if rec is None:
        return []
    if write:
        B.append(rec, path)
    return [rec]


def main(argv=None) -> int:
    rows = check()
    for r in rows:
        print(f"  {r['file']:<20} {r['day']}  {r['sessions']:>3} sessions" + ("  STALE" if r["stale"] else "")
              + (f"  ({r['why']})" if r.get("why") else ""))
    print(line(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
