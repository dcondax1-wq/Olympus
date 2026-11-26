"""OF SEND NOW (owner 2026-11-26: "give me one simple line of code to get you the order flow"). PC side, after the update.

    python -X utf8 tools/of_send_now.py

1. Checks the tick recorder (LE_TickRec in NinjaTrader): on / recording / which version / backfill (days, oldest, errors, holes).
2. Imports the recorder's files and builds the order-flow summary of EVERY finished tick day on disk (engine/ofsum, oldest first).
3. Sends them NOW through the signed data feed (engine/datafeed: ntfy, <= 1.85 MB a page, newest days first, never past the
   8-answers-a-day cap minus 2 kept for normal pulls). Capped? It says so; the next run sends the rest (logs/datafeed/of_push.json).
4. Prints: sent N days (oldest X, newest Y); depth recording: yes/no; next: ...
READ-ONLY towards the bot: never trades, arms, routes or changes a setting. Refuses 01:50-16:00 ET on weekdays (the bot trades).
The cloud side: `python tools/data_pull.py --of` takes the pushed pages (kept 3 h on ntfy) and runs the order-flow battery.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import secrets
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
STATE_NAME = "of_push.json"


def say(msg: str) -> None:
    print(msg, flush=True)


def _old_code() -> str | None:
    """None when this PC has the code this needs; else what is missing (= the update did not run)."""
    try:
        from engine import datafeed as DF, ofsum, tickrec  # noqa: F401
    except Exception as e:  # noqa: BLE001
        return f"import failed ({e.__class__.__name__})"
    for mod, names in ((DF, ("build_of", "_answer_of", "OF_PAGES")), (ofsum, ("summarize", "write_day", "depth_summary")),
                       (tickrec, ("build_summaries", "holes", "ingest_depth"))):
        for n in names:
            if not hasattr(mod, n):
                return f"{mod.__name__}.{n} missing"
    return None


def recorder_report(nd: str | None, now: float) -> dict:
    """Plain facts about LE_TickRec on this PC (installed file, compiled version running, backfill)."""
    from engine import tickrec as T
    out = {"enabled": T.is_enabled(), "nt_dir": bool(nd)}
    if not nd:
        return out
    cs = os.path.join(nd, "bin", "Custom", "AddOns", "LE_TickRec.cs")
    try:
        src = open(cs, encoding="utf-8", errors="replace").read()
        out["installed"] = True
        out["installed_new"] = "DAY-OFMAX" in src
    except OSError:
        out["installed"] = False
        out["installed_new"] = False
    sp = os.path.join(nd, T.REC_DIR, "le_tickrec_status.txt")
    try:
        out["status_age_s"] = int(now - os.path.getmtime(sp))
    except OSError:
        out["status_age_s"] = None
    st = T.recorder_status(nd) or {}
    out["status"] = st
    out["running_new"] = "bf_unknown" in st                         # only the day-ofmax build writes these keys
    out["depth"] = st.get("depth")
    return out


def _state_path(feed_work: str) -> str:
    return os.path.join(feed_work, STATE_NAME)


def _low_priority() -> None:
    """red team 2026-11-26: ATLAS can hold a trade in the evening (Asia members, 18:00-02:00 ET): this line's imports, summaries
    (up to 3 h) and uploads run BELOW_NORMAL on Windows, like the autopilot, so the bot's polls keep the CPU. Never raises."""
    try:
        if os.name == "nt":
            import ctypes
            k = ctypes.windll.kernel32
            k.SetPriorityClass(k.GetCurrentProcess(), 0x00004000)
    except Exception:  # noqa: BLE001
        pass


def run(now: float | None = None, env=None, http_fn=None, sleep=None, nd: str | None = None, dp_work: str | None = None,
        feed_work: str | None = None, max_zip: int | None = None) -> int:
    _low_priority()
    missing = _old_code()
    if missing:
        say("Run the update line first (UPDATE.bat), then this line again. (This PC has older code: " + missing + ")")
        return 2
    from engine import datafeed as DF, datapipe as DP, tickrec as T
    now = float(now if now is not None else time.time())
    if DF.in_session(now):
        say("The bot is trading now (01:50-16:00 ET on weekdays): run this line after 16:05 ET.")
        return 3
    nd = nd if nd is not None else T.nt_dir()
    dp_work = dp_work or DP.WORK
    feed_work = feed_work or DF.WORK
    max_zip = max_zip or DF.MAX_ZIP
    # 1. the recorder
    rr = recorder_report(nd, now)
    st = rr.get("status") or {}
    if not rr["nt_dir"]:
        say("[FIX] NinjaTrader's folder (Documents\\NinjaTrader 8) is not on this PC user: nothing to send.")
        return 4
    if not rr.get("installed"):
        say("[FIX] The tick recorder is not installed: copy ninjatrader\\LE_TickRec.cs into "
            "Documents\\NinjaTrader 8\\bin\\Custom\\AddOns\\, then NinjaScript Editor, F5.")
    elif not rr.get("installed_new"):
        say("[FIX] NinjaTrader has the OLD recorder file: copy ninjatrader\\LE_TickRec.cs into "
            "Documents\\NinjaTrader 8\\bin\\Custom\\AddOns\\ again, then NinjaScript Editor, F5 (adds depth + fixes the Sep 14 stop).")
    elif not rr.get("running_new"):
        say("[FIX] The new recorder file is in place but not compiled yet: NinjaTrader, New > NinjaScript Editor, press F5.")
    else:
        say("[OK]  Tick recorder: the new version is running (depth + backfill fix).")
    if not rr["enabled"]:
        say("[FIX] The tick recorder is switched OFF: python -X utf8 -m engine.tickrec enable")
    age = rr.get("status_age_s")
    if age is None or age > 120:
        say("[FIX] NinjaTrader is not writing the recorder's status (" + ("no status file" if age is None else f"last {age // 60} min ago")
            + "): is NinjaTrader open and connected?")
    if st:
        say(f"[..]  Backfill: {st.get('backfill', '?')}, {st.get('backfill_days', '?')} days fetched, oldest {st.get('oldest') or '-'}, "
            f"errors {st.get('bf_errors', '0')}" + (f", unknown contracts {st['bf_unknown']}" if "bf_unknown" in st else ""))
    # 2. import + summaries of every finished day
    ing = T.ingest(nd)
    days = T.nq_days()
    say(f"[..]  Tick days on disk: {len(days)}" + (f" ({days[0]} .. {days[-1]}), gaps {T.holes(days)} weekdays" if days else "")
        + (f"; imported {ing.get('files', 0)} new file(s)" if ing.get("ok") else ""))
    if not days:
        say("Nothing to send yet: no tick days on disk. Next: leave NinjaTrader open tonight; the recorder fetches past days by itself.")
        return 5
    b = T.build_summaries(budget_s=3 * 3600, out_root=os.path.join(dp_work, "days"))
    base = os.path.join(dp_work, "days")
    ready = sorted(d for d in (os.listdir(base) if os.path.isdir(base) else [])
                   if os.path.exists(os.path.join(base, d, "of", "NQ_meta.json")))
    say(f"[..]  Order-flow summaries ready: {len(ready)} days (built now {b.get('made', 0)}, failed {b.get('failed', 0)})")
    if not ready:
        say("Nothing to send: no finished tick day yet (today's day counts after midnight ET).")
        return 5
    # 3. send: newer than what went before, then older (the backfill grows backwards); within today's cap
    spath = _state_path(feed_work)
    try:
        prev = json.load(open(spath, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        prev = {}
    lo = (dt.datetime.fromtimestamp(now, DF.ET).date() - dt.timedelta(days=DF.DAYS_BACK_OF - 5)).isoformat()
    ranges = []
    if prev.get("newest") and prev.get("oldest"):
        if ready[-1] > prev["newest"]:
            ranges.append(((dt.date.fromisoformat(prev["newest"]) + dt.timedelta(days=1)).isoformat(), None))
        if ready[0] < prev["oldest"]:
            ranges.append((lo, (dt.date.fromisoformat(prev["oldest"]) - dt.timedelta(days=1)).isoformat()))
    else:
        ranges.append((lo, None))
    if not ranges:
        say(f"Already sent: every summary ({ready[0]} .. {ready[-1]}) went to Claude before. Next: nothing to do; new days go nightly.")
        return 0
    sent_days, oldest, newest, more, why = 0, prev.get("oldest"), prev.get("newest"), False, None
    today = dt.datetime.fromtimestamp(now, DF.ET).date().isoformat()
    used = sum(1 for x in (DF._state(feed_work).get("sent") or []) if x.get("day") == today)
    if DF.DAILY_CAP - DF.OF_RESERVE - used <= 0:
        say(f"Not sent: today's sending cap is used ({used} answers today, {DF.DAILY_CAP} a day, 2 kept for the bars). "
            "Next: run this line again tomorrow after 16:05 ET.")
        return 6
    for since, until in ranges:
        used = sum(1 for x in (DF._state(feed_work).get("sent") or []) if x.get("day") == today)
        if DF.DAILY_CAP - DF.OF_RESERVE - used <= 0:      # red team 2026-11-26: the 2nd range too (_answer_of sends >= 1 page)
            more = True
            break
        rid = "push" + secrets.token_hex(5)
        r = DF._answer_of({"id": rid, "since": since, "until": until, "what": "of"}, int(now), feed_work, env, http_fn, dp_work,
                          max_zip, [], sleep, pages=DF.DAILY_CAP)
        if not r.get("ok"):
            why = r.get("why") or "not sent"
            break
        sent_days += int(r.get("days") or 0)
        for d in (r.get("first"), r.get("last")):
            if d:
                oldest = d if not oldest or d < oldest else oldest
                newest = d if not newest or d > newest else newest
        if r.get("more"):
            more = True
            break
    if oldest and newest:
        os.makedirs(feed_work, exist_ok=True)
        json.dump({"oldest": oldest, "newest": newest, "t": int(now)}, open(spath, "w", encoding="utf-8"))
    depth = "yes" if rr.get("depth") == "on" else ("no (NinjaTrader gives no depth to the add-on)" if rr.get("depth") == "unavailable"
                                                   else "no (new recorder not running yet)")
    if why and not sent_days:
        cap = "8 answers today already" in str(why) or "rate" in str(why).lower() or "413" in str(why)
        say(f"Not sent: {why}. Next: " + ("run this line again tomorrow after 16:05 ET." if cap else "check the internet, then run this line again."))
        return 6
    nxt = ("run this line again tomorrow after 16:05 ET for the rest (today's sending cap is used up)." if more else
           "nothing; Claude pulls them within 3 hours. Leave NinjaTrader open tonight so the backfill keeps going.")
    say(f"sent {sent_days} days (oldest {oldest}, newest {newest}); depth recording: {depth}; next: {nxt}")
    return 0


def main(argv=None) -> int:
    try:
        return run()
    except KeyboardInterrupt:
        return 130
    except Exception as e:  # noqa: BLE001
        say(f"OF send stopped: {e.__class__.__name__}: {str(e)[:160]}. Nothing in the bot changed. Send this line to Claude.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
