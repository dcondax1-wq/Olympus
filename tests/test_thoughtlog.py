"""THOUGHT LOG (engine/thoughtlog.py; day-thoughtlog 2026-11-27). No network, temp folders only, ~2 s.
  a. collect: today's ATLAS lobe lines (their own times) + OF lane lines appended once (same bot + text = one row), BLITZ / acct_c never,
     yesterday's lines never, ids masked (MFFUEVBLDR123456 -> ...3456), the row + byte caps hold, off the PC = no write, never raises
  b. day_rows / pack: LIT's persisted day log (engine/brain.BrainLog file) + the collected rows, oldest first, gzip JSONL; none = None
  c. wiring: pc_report calls collect() in its try/except after the glog block (the report task, never the poll loop); datafeed packs
     thoughts.jsonl.gz into the day zip and the cloud's DAY_FILE accepts it; data/thoughts/ is gitignored
    python -X utf8 -m tests.test_thoughtlog
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import thoughtlog as TL  # noqa: E402

RES = []
ET = ZoneInfo("America/New_York")


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:600]}"))


def ts(day, hm):
    return int(dt.datetime.fromisoformat(f"{day}T{hm}:00").replace(tzinfo=ET).timestamp())


def hb_of(lines):
    return {"second": {"strategies": {
        "ema_lon_vix": {"short": "EMA", "brain": {"log": [{"t": t, "text": x} for t, x in lines]}},
        "blitz_x": {"short": "BLITZ", "brain": {"log": [{"t": lines[0][0], "text": "blitz secret"}]}},
        "acct_c_y": {"short": "C", "brain": {"log": [{"t": lines[0][0], "text": "hidden lane"}]}}}}}


def main():
    day = "2026-11-27"
    now = ts(day, "10:00")
    with tempfile.TemporaryDirectory() as tmp:
        fold, brain = os.path.join(tmp, "th"), os.path.join(tmp, "brain")
        TL.of_rows = lambda root=None, now=None: [(ts(day, "09:40"), "OF paper: opening-range high swept, absorbed -> taken")]   # no repo files
        hb = hb_of([(ts(day, "03:10"), "EMA: pullback to the 50 forming on MFFUEVBLDR123456"), (ts(day, "03:15"), "EMA: no - body"),
                    (ts("2026-11-26", "11:00"), "EMA: yesterday's line")])
        n1 = TL.collect(hb, now=now, folder=fold)
        n2 = TL.collect(hb, now=now + 900, folder=fold)
        rows = TL.read_rows(day, fold)
        check("a. today's ATLAS lines + the OF line written once (2nd run adds nothing); BLITZ / acct_c / yesterday never",
              n1 == 3 and n2 == 0 and [r["bot"] for r in rows] == ["atlas", "atlas", "of"] and not any("blitz" in r["text"].lower() or "hidden" in r["text"] or "yesterday" in r["text"] for r in rows), rows)
        check("a. ids masked: MFFUEVBLDR123456 -> ...3456", "MFFUEVBLDR123456" not in json.dumps(rows) and "3456" in rows[0]["text"], rows[0])
        many = hb_of([(ts(day, "04:00") + i, f"EMA: line {i}") for i in range(TL.MAX_ROWS + 50)])
        TL.collect(many, now=now, folder=fold)
        check("a. the row cap holds", len(TL.read_rows(day, fold)) == TL.MAX_ROWS, len(TL.read_rows(day, fold)))
        check("a. never raises on junk; off the PC (no folder, LE_THOUGHTLOG unset on Linux) = no write",
              all(TL.collect(j, now=now, folder=fold) >= 0 for j in (None, 1, "x", [], {"second": 5})) and (os.name == "nt" or TL.collect(hb, now=now) == 0))
        # LIT's own day log, as engine/brain.BrainLog persists it
        from engine.brain import BrainLog
        lg = BrainLog(brain)
        lg.update(day, [{"key": "sw1", "t": ts(day, "02:30"), "hm": "02:30", "kind": "sweep", "text": "Swept PDH 26,435.75 (7.70 ATR deep; deep enough: ✓)"},
                        {"key": "rj1", "t": ts(day, "02:45"), "hm": "02:45", "kind": "rejected", "text": "Swept equal highs 26,741.5 (0.18 ATR deep; ✗ LIT needs 0.5)"}], now)
        dr = TL.day_rows(day, folder=os.path.join(tmp, "th2"), brain_dir=brain)
        check("b. day_rows: LIT's persisted log (kind kept), oldest first", [(r["bot"], r["kind"]) for r in dr] == [("lit", "sweep"), ("lit", "rejected")], dr)
        b = TL.pack(day, folder=fold, brain_dir=brain)
        got = [json.loads(x) for x in gzip.decompress(b).decode("utf-8").splitlines()] if b else []
        check("b. pack: gzip JSONL, LIT + ATLAS + OF, oldest first, <= PACK_ROWS; an empty day = None",
              got and {r["bot"] for r in got} == {"lit", "atlas", "of"} and all(got[i]["t"] <= got[i + 1]["t"] for i in range(len(got) - 1)) and len(got) <= TL.PACK_ROWS
              and TL.pack("2026-11-01", folder=fold, brain_dir=brain) is None, len(got))
    rep, df, gi = (open(os.path.join(ROOT, p), encoding="utf-8").read() for p in ("tools/pc_report.py", "engine/datafeed.py", ".gitignore"))
    from engine import datafeed as DF
    i = rep.index("out[\"glog\"] = gl")
    check("c. pc_report: collect() in its own try/except right after the glog block (the 15-minute report task)",
          "thoughtlog.collect(hb)" in rep[i:i + 900] and "except Exception" in rep[i:i + 900])
    check("c. datafeed packs thoughts.jsonl.gz (try/except, < 200 KB); DAY_FILE accepts it; data/thoughts/ gitignored",
          'files["thoughts.jsonl.gz"] = th' in df and DF.DAY_FILE.match("days/2026-11-27/thoughts.jsonl.gz") and "data/thoughts/" in gi)
    check("c. the trading day: 18:00 ET and later = the next weekday; Fri evening = Monday",
          TL.trading_day(ts("2026-11-26", "18:30")) == "2026-11-27" and TL.trading_day(ts("2026-11-27", "18:30")) == "2026-11-30")
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
