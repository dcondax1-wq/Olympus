"""THOUGHT LOG (day-thoughtlog 2026-11-27): every bot's thoughts of a CME day, kept on the PC and sent with the day's data.

Why: the PC's status post carries only the newest ~8 thought lines a bot (engine/brain_glance.logs, ext block "glog"), so a busy
morning loses its early reasons, and a past day in nq/story.html could only show the replay twin. This keeps the whole day:

  lit     LIT's own day log, already persisted by the live process (engine/brain.BrainLog -> data/brain/<day>.jsonl, every fact
          once with its time); read here at pack time only (nothing new is written on LIT's path)
  atlas   the ATLAS lobes' brain log lines (hb["second"]["strategies"][k]["brain"]["log"], each with its time), collected
  of      the order-flow lane's lines (engine/brain_feed.of_bot: the PAPER bot / journal / recorder lines), collected

collect(hb) runs (on the PC: enabled(); a test passes its own folder) inside the 15-minute report task (tools/pc_report.full), a separate scheduled process: never inside the bot's
poll loop, so it cannot delay a poll. It appends only the lines not seen yet today to data/thoughts/<day>.jsonl (gitignored):
deduped (same bot + same text = one row, the first time seen), capped (MAX_ROWS rows, MAX_BYTES bytes a day), ids masked
(engine/notify.mask_ids: an account id becomes "...1234"), never raises. BLITZ / hidden lanes are never read.

pack(day) builds days/<day>/thoughts.jsonl.gz for engine/datafeed (the day zip the cloud pulls: tools/data_pull.py ->
data/pc_days/<day>/): {"t", "bot": lit|atlas|of, "kind", "text"} rows, oldest first, ids masked, names scrubbed, <= PACK_ROWS.
Paper / logging only: it never trades, sizes, arms, routes or changes a setting.

    python -X utf8 -m engine.thoughtlog status [--day YYYY-MM-DD]
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import re
import sys
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "data", "thoughts")
ET = ZoneInfo("America/New_York")
MAX_ROWS = 600              # collected rows a day (ATLAS + OF); a normal day writes ~50-150
MAX_BYTES = 150_000         # the day file's size cap
PACK_ROWS = 1200            # rows in the packed file (LIT's log + the collected rows)
LINE_N = 220                # characters a line
SKIP = ("blitz", "acct_c")  # hidden / paper lanes never read


def trading_day(t) -> str:
    """The CME day of a moment: 18:00 ET and later belongs to the next weekday (= engine/datapipe.trading_day)."""
    e = dt.datetime.fromtimestamp(int(t), ET)
    d = e.date() + dt.timedelta(days=1) if e.hour >= 18 else e.date()
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d.isoformat()


def _d(x):
    return x if isinstance(x, dict) else {}


def _l(x):
    return x if isinstance(x, list) else []


def _mask(s) -> str:
    try:
        from .notify import mask_ids
        s = mask_ids(s)
    except Exception:  # noqa: BLE001 - the digit rule below still cuts a long id
        pass
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    s = re.sub(r"\b[A-Z]{2,}\d{5,}\b", lambda m: "..." + m.group(0)[-4:], s)       # any ACCT123456-shaped id left
    return s[:LINE_N]


def atlas_rows(hb) -> list:
    """[(t, text)] of the ATLAS lobes' brain logs in the heartbeat (each line has its own time)."""
    out = []
    for k, s in _d(_d(_d(hb).get("second")).get("strategies")).items():
        if any(x in str(k).lower() for x in SKIP):
            continue
        s = _d(s)
        for x in _l(_d(s.get("brain")).get("log")):
            if isinstance(x, dict) and x.get("text") and isinstance(x.get("t"), (int, float)) and x["t"] > 0:
                out.append((int(x["t"]), f"{s.get('short') or k}: {x['text']}"))
    return out


def of_rows(root: str = ROOT, now=None) -> list:
    """[(t, text)] of the order-flow lane's current lines (engine/brain_feed.of_bot); a line's own HH:MM when it has one, else now."""
    try:
        from .brain_feed import of_bot
        think = _l(_d(of_bot(root)).get("think"))
    except Exception:  # noqa: BLE001
        return []
    now = int(now or time.time())
    out = []
    for ln in think:
        ln = str(ln or "")
        m = re.match(r"^(\d\d):(\d\d) (.*)$", ln)
        t = now
        if m:
            e = dt.datetime.fromtimestamp(now, ET)
            c = e.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
            t = int((c - dt.timedelta(days=1)).timestamp()) if c > e + dt.timedelta(minutes=5) else int(c.timestamp())
            ln = m.group(3)
        if ln.startswith("tick recorder") or ln.startswith("study looks"):
            continue                                     # status lines, not thoughts
        out.append((t, ln))
    return out


def _path(day, folder=None):
    return os.path.join(folder or DIR, f"{day}.jsonl")


def read_rows(day: str, folder: str | None = None) -> list:
    rows = []
    try:
        with open(_path(day, folder), encoding="utf-8") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get("text"):
                    rows.append(r)
    except OSError:
        pass
    return rows


def enabled() -> bool:
    """On the PC (Windows) only, like engine/datapipe: LE_THOUGHTLOG=1 forces it elsewhere (tests), LE_THOUGHTLOG=0 turns it off."""
    v = os.environ.get("LE_THOUGHTLOG")
    return v != "0" and (os.name == "nt" or v == "1")


def collect(hb, root: str = ROOT, now=None, folder: str | None = None) -> int:
    """Append today's new ATLAS / OF lines to data/thoughts/<day>.jsonl. Returns rows written; never raises."""
    try:
        if folder is None and not enabled():
            return 0
        now = int(now or time.time())
        day = trading_day(now)
        cand = [("atlas", t, x) for t, x in atlas_rows(hb)] + [("of", t, x) for t, x in of_rows(root, now)]
        cand = [(b, t, _mask(x)) for b, t, x in cand if trading_day(t) == day]
        if not cand:
            return 0
        have = read_rows(day, folder)
        seen = {(r.get("bot"), r.get("text")) for r in have}
        p = _path(day, folder)
        size = os.path.getsize(p) if os.path.exists(p) else 0
        new = []
        for b, t, x in sorted(cand, key=lambda z: z[1]):
            if (b, x) in seen or not x:
                continue
            seen.add((b, x))
            new.append({"t": t, "bot": b, "text": x})
        room = MAX_ROWS - len(have)
        new = new[:max(0, room)]
        if not new:
            return 0
        data = "".join(json.dumps(r, separators=(",", ":"), ensure_ascii=False) + "\n" for r in new)
        if size + len(data.encode("utf-8")) > MAX_BYTES:
            return 0
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(data)
        return len(new)
    except Exception:  # noqa: BLE001 - logging only: never into the report
        return 0


def day_rows(day: str, root: str = ROOT, folder: str | None = None, brain_dir: str | None = None, names=()) -> list:
    """The day's thoughts, oldest first: LIT's persisted log + the collected ATLAS / OF rows; ids masked, names scrubbed."""
    rows = []
    try:
        from .brain import read_day_log, BRAIN_DIR
        for r in read_day_log(day, brain_dir or BRAIN_DIR, keep=PACK_ROWS):
            if isinstance(r, dict) and r.get("text") and isinstance(r.get("t"), (int, float)):
                rows.append({"t": int(r["t"]), "bot": "lit", "kind": str(r.get("kind") or ""), "text": _mask(r["text"])})
    except Exception:  # noqa: BLE001
        pass
    for r in read_rows(day, folder):
        if isinstance(r.get("t"), (int, float)) and r.get("bot") in ("atlas", "of"):
            rows.append({"t": int(r["t"]), "bot": r["bot"], "kind": "", "text": _mask(r["text"])})
    if names:
        try:
            from .datapipe import scrub_text
            rows = [{**r, "text": scrub_text(r["text"], names)} for r in rows]
        except Exception:  # noqa: BLE001
            pass
    rows.sort(key=lambda r: (r["t"], r["bot"]))
    return rows[-PACK_ROWS:]


def pack(day: str, root: str = ROOT, folder: str | None = None, brain_dir: str | None = None, names=()) -> bytes | None:
    """days/<day>/thoughts.jsonl.gz for the day zip; None when the day has no thoughts."""
    try:
        rows = day_rows(day, root, folder, brain_dir, names)
        if not rows:
            return None
        return gzip.compress("".join(json.dumps(r, separators=(",", ":"), ensure_ascii=False) + "\n" for r in rows).encode("utf-8"), mtime=0)
    except Exception:  # noqa: BLE001
        return None


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    day = a[a.index("--day") + 1] if "--day" in a else trading_day(time.time())
    rows = day_rows(day)
    by = {}
    for r in rows:
        by[r["bot"]] = by.get(r["bot"], 0) + 1
    print(f"thoughtlog {day}: {len(rows)} rows {by}; file {_path(day)} ({os.path.getsize(_path(day)) if os.path.exists(_path(day)) else 0} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
