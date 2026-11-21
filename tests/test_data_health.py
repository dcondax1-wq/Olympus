"""Data health (tools/data_health.py + the DATA line of tools/board.py read) and the ES feed patch for the lead
(research/handoff/2026-11-20/datahealth/ninjatrader_es_feed.patch), day-brief 2026-11-20.

    python -X utf8 -m tests.test_data_health
Temp folders only; the patch is applied to a COPY of engine/ (the live engine/ninjatrader.py is never touched here).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
PATCH = os.path.join(ROOT, "research", "handoff", "2026-11-20", "datahealth", "ninjatrader_es_feed.patch")
RES = []

from tools import data_health as DH  # noqa: E402


def check(name, ok, info=None):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:400]) if not ok and info is not None else ''}", flush=True)
    RES.append(bool(ok))


def at(y, m, d, hh=0, mm=0):
    return dt.datetime(y, m, d, hh, mm, tzinfo=ET)


def write_csv(path, rows, head="time,open,high,low,close,volume"):
    with open(path, "w") as fh:
        fh.write(head + "\n")
        for r in rows:
            fh.write(",".join(str(x) for x in r) + "\n")


def main():
    now = at(2026, 11, 20, 14, 0)                         # Friday afternoon: Thursday is the newest finished session
    # 1. sessions behind: weekends and CME closures do not count
    check("last finished session Fri 14:00 = Thu", DH.last_session(now) == dt.date(2026, 11, 19))
    check("last finished session Fri 17:30 = Fri", DH.last_session(at(2026, 11, 20, 17, 30)) == dt.date(2026, 11, 20))
    check("Monday 10:00 -> Friday (weekend skipped)", DH.last_session(at(2026, 11, 23, 10)) == dt.date(2026, 11, 20))
    check("Thu bar on Fri 14:00: 0 behind", DH.sessions_behind(dt.date(2026, 11, 19), now) == 0)
    check("Mon bar on Fri 14:00: 3 behind (Tue, Wed, Thu) = not stale yet", DH.sessions_behind(dt.date(2026, 11, 16), now) == 3)
    check("Christmas (CME closed) is not a session", DH.sessions_behind(dt.date(2026, 12, 24), at(2026, 12, 28, 18)) == 1)
    check("the 18:00 bar belongs to the next trading day", DH.trading_day(at(2026, 11, 19, 18, 5)) == dt.date(2026, 11, 20))

    with tempfile.TemporaryDirectory() as d:
        t_fresh = int(at(2026, 11, 19, 15, 55).timestamp())
        t_old = int(at(2026, 10, 16, 15, 55).timestamp())
        write_csv(os.path.join(d, "NQ_5m.csv"), [(t_fresh - 300, 1, 1, 1, 1, 1), (t_fresh, 1, 1, 1, 1, 1)])
        write_csv(os.path.join(d, "ES_5m.csv"), [(t_old, 1, 1, 1, 1, 1)])
        write_csv(os.path.join(d, "VIX_1d.csv"), [("2026-11-19", 1, 1, 1, 1)], head="date,open,high,low,close")
        write_csv(os.path.join(d, "tv_mnq_5m_2026-10-16.csv"), [(t_old, 1, 1, 1, 1, 1)])
        with open(os.path.join(d, "notes.csv"), "w") as fh:
            fh.write("a,b\n1,2\n")
        rows = DH.check(now, d)
        by = {r["file"]: r for r in rows}
        check("files read: unix-time and date files, one-off tv_ exports and non-price csv skipped",
              sorted(by) == ["ES_5m.csv", "NQ_5m.csv", "VIX_1d.csv"], sorted(by))
        check("NQ fresh, VIX fresh, ES stale (24 sessions) with the why", not by["NQ_5m.csv"]["stale"] and not by["VIX_1d.csv"]["stale"]
              and by["ES_5m.csv"]["stale"] and by["ES_5m.csv"]["sessions"] == 24 and "ES" in (by["ES_5m.csv"]["why"] or ""), by)
        ln = DH.line(rows)
        check("the DATA line: fresh count + the stale file named with its age", ln.startswith("DATA  2 of 3 files fresh")
              and "STALE: ES_5m end 10-16 (24 sessions)" in ln, ln)
        check("all fresh -> one short line", DH.line([r for r in rows if not r["stale"]]).endswith("all within 3 sessions"))
        sh = os.path.join(d, "shared.jsonl")
        n1 = DH.note_stale(rows, sh, now=int(now.timestamp()))
        n2 = DH.note_stale(rows, sh, now=int(now.timestamp()) + 60)
        lines = open(sh).read().splitlines()
        rec = json.loads(lines[0])
        check("one Board note (claude_note) for the newly stale file, never twice for the same newest day",
              len(n1) == 1 and not n2 and len(lines) == 1 and rec["kind"] == "claude_note" and "ES_5m" in rec["text"]
              and rec["data"]["keys"] == ["data_stale:ES_5m.csv:2026-10-16"], (n1, n2, lines))
        write_csv(os.path.join(d, "ES_5m.csv"), [(t_old + 3 * 86400, 1, 1, 1, 1, 1)])
        n3 = DH.note_stale(DH.check(now, d), sh, now=int(now.timestamp()) + 120)
        check("a newer (still stale) newest day is a new note", len(n3) == 1 and "2026-10-19" in n3[0]["text"], n3)
        check("the note fits the Board's 300 characters", all(len(json.loads(x)["text"]) <= 300 for x in open(sh)))

    # 2. board.py read prints the DATA line (offline, no note posted)
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "board.py"), "read", "--offline", "--no-data-notes"],
                       capture_output=True, text=True, cwd=ROOT, timeout=300)
    check("board.py read: the last line is the DATA line", r.returncode == 0 and r.stdout.strip().splitlines()[-1].startswith("DATA  "),
          r.stdout[-300:] + r.stderr[-300:])

    # 3. the ES feed patch is IN the live engine/ninjatrader.py (weekend landing 2026-11-21, red-team cleared): the selftest stays
    #    green with its ES line, and the MNQ bot asks the add-on for MES too (NQ signal: ES), rolling on Dec 10
    st = subprocess.run([sys.executable, "-X", "utf8", "-m", "engine.ninjatrader", "--selftest"], cwd=ROOT, capture_output=True,
                        text=True, timeout=600)
    out = st.stdout
    check("selftest with the ES feed: no FAIL, the ES line passes", st.returncode == 0 and "[FAIL]" not in out
          and "[PASS] LE_Feed: the ES research contract rides along" in out, out[-600:] + st.stderr[-300:])
    code = ("import datetime as d, engine.ninjatrader as n; print(n.feed_instruments({'signal_root':'MNQ'}, d.date(2026,11,20)),"
            " n.feed_instruments({'signal_root':'NQ'}, d.date(2026,12,10)))")
    fi = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    check("MNQ bot asks the add-on for MES too; NQ signal for ES; both roll on Dec 10",
          "['MNQ 12-26', 'MES 12-26'] ['MNQ 03-27', 'NQ 03-27', 'ES 03-27']" in fi.stdout, fi.stdout + fi.stderr)
    live = open(os.path.join(ROOT, "engine", "ninjatrader.py"), encoding="utf-8").read()
    check("the live engine/ninjatrader.py carries the ES feed (feed_es)", "feed_es" in live)

    n = sum(RES)
    print(f"\ndata health: {n}/{len(RES)} {'PASS' if n == len(RES) else 'FAIL'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
