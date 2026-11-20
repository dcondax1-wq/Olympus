"""Live bot reliability (night-nqlive 2026-11-20, research/writeups/nq-live-reliability-2026-11-20.md): every way a backtest trade
can fail to reach the account is either fixed, alarmed within 2 minutes, or explained afterwards.

  1. engine/fill_audit "no record = unknown" (tools/live_gap_proposal.classify landed): the Oct 28 2026 short that WAS traded
     live (5 MNQ, -$437) is no longer "missed: PC bot off" but "unknown ... check the broker statement", left out of the
     missed count and $; a day after the PC's first record keeps today's verdict.
  2. the bot's own "NOT routed" lines: kept per day (collect -> notes.json), in the nightly verdict, in the PC's day files
     (engine/datafeed gaps.json, account ids cut), and used as the missed trade's reason; a size-0 skip has its own reason.
  3. MISSED TRADE at once: an entry held back, or one the model took during a gap / before a restart, goes to the private ntfy
     topic (engine/notify.instant_problem, type "problems"); the owner's own pause never alarms; the 15-minute report skips
     its copy.
  4. the fast alarm (engine/fast_alarm.py): bot on a broker account in the entry hours, no good poll for 90 s or the 1m feed
     two bars behind -> one push, one "back"; nothing for paper, outside the hours, on a holiday, in the start grace.
  5. engine/autoupdate: an update / restart never lands while ATLAS (account B) holds a position or an open bracket.

    python -X utf8 -m tests.test_nq_live_reliability
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import shutil
import sys
import tempfile
import zipfile
from collections import deque
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import autoupdate as AU  # noqa: E402
from engine import datafeed as DF  # noqa: E402
from engine import fast_alarm as FAL  # noqa: E402
from engine import fill_audit as FA  # noqa: E402
from engine import notify as NT  # noqa: E402
from engine import watchdog as WD  # noqa: E402
from tools import live_gap_proposal as G  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:300]})" if detail and not cond else ""), flush=True)


def ts(y, m, d, hh, mm, ss=0):
    return int(dt.datetime(y, m, d, hh, mm, ss, tzinfo=ET).timestamp())


def bt_row(t, d=-1, pnl=-347.6):
    return {"entry_t": t, "dir": d, "entry": 29945.0, "stop": 29987.5, "target": 29665.75, "exit_price": 29987.75,
            "exit_reason": "STOP", "qty": 4, "pnl": pnl}


class Bot:
    def __init__(self, now, running=True, adapter="ninjatrader"):
        self.running = running
        self.cfg = {"adapter": adapter, "poll_sec": 60}
        self.health = {"last_ok_poll": now - 5, "last_1m_bar_t": now - now % 60 - 60}
        self.started_at = now - 3600
        self.thread = SimpleNamespace(is_alive=lambda: True)
        self.log = deque(maxlen=400)
        self.seen, self._blocked_entries, self.ledger = set(), set(), []
        self.state, self._open_routed = {}, None

    def add_log(self, t, text):
        self.log.appendleft({"t": t, "type": "risk", "text": text})


# ------------------------------------------------------------------------------------------------ 1. unknown
def t_unknown():
    oct28 = 1793173380                                       # 2026-10-28 03:43 ET, traded live (5 MNQ, -$437)
    notes = {"uptime": [{"t": 1794002400, "running": True}]}  # the PC's first uptime sample: Nov 6
    first = FA.first_record_day(notes, {"2026-11-16"})
    check("first record day = the first uptime / trade day (2026-11-06)", first == "2026-11-06", first)
    row = FA.compare(bt_row(oct28), None, notes, {"2026-11-16"}, first)
    check("Oct 28 (before the PC's records): status unknown, not missed", row["status"] == "unknown", row)
    check("... says check the broker statement", "broker statement" in row["reason"], row["reason"])
    check("... no missed $ (its backtest $ kept as unknown_usd)", "missed_usd" not in row and row["unknown_usd"] == -347.6, row)
    v = G.classify("2026-10-28", None, first)
    check("= the proposal's verdict (tools/live_gap_proposal.classify)", v["status"] == row["status"] and not v["count_as_missed"], v)
    nov10 = ts(2026, 11, 10, 3, 33)
    r2 = FA.compare(bt_row(nov10, 1, -230.8), None, notes, {"2026-11-16"}, first)
    check("Nov 10 (after the first record, no sample that day): still missed", r2["status"] == "missed" and r2["missed_usd"] == -230.8, r2)
    r3 = FA.compare(bt_row(oct28), None, notes, {"2026-11-16"})
    check("compare() without first_record_day = the old verdict (callers unchanged)", r3["status"] == "missed", r3)
    blk = {**notes, "blocked": {str(oct28): {"reason": "feed stale"}}}
    r4 = FA.compare(bt_row(oct28), None, blk, (), "2026-11-06")
    check("a held-back entry before the first record stays missed (its reason is known)", r4["status"] == "missed"
          and r4["reason"] == "feed stale", r4)
    S = FA.summarize([row, r2], now=ts(2026, 11, 20, 0, 0), days=["2026-10-28", "2026-11-10"])
    check("summary: 1 missed ($-231), 1 unknown, the unknown not in missed $", S["missed"] == 1 and S["unknown"] == 1
          and S["missed_usd"] == -230.8, S)
    check("summary headline names the unknown", "unknown" in S["text"], S["text"])
    oct_m = next(m for m in S["months"] if m["month"] == "2026-10")
    check("the unknown is not counted as an extra trade in its month", oct_m["extra"] == 0 and oct_m.get("unknown") == 1, oct_m)
    N = FA.nightly_summary([row], "2026-10-28", None, now=ts(2026, 11, 20, 0, 0))
    check("nightly: verdict 'unknown', never 'differs' (no push)", N["verdict"] == "unknown" and not N["reasons"], N)
    check("nightly: the unknown is not a live trade", N["live_trades"] == 0, N)
    from engine.perf import exec_curve
    c = exec_curve([row, r2])
    check("perf.exec_curve (phone chart): the unknown is not a missed trade, nor its $", c is not None and c["missed"] == 1
          and c["parts"]["missed trades"] == 230.8, c and {k: c[k] for k in ("missed", "parts")})


# ------------------------------------------------------------------------------------------------ 2. NOT routed lines
def t_not_routed():
    now = ts(2026, 11, 18, 10, 0)
    b = Bot(now)
    e1 = ts(2026, 11, 18, 6, 12)
    b.add_log(e1 + 3, "Entry at 06:12 ET at 0 instead of 6: eval room $40 under one micro's stop")
    b.add_log(e1 + 200, "[ATLAS MFFUEVBLDR123456] Entry at 06:12 ET NOT routed on account B: hedging rule")
    b.add_log(e1 + 400, "LIT 1m CISD closed at 06:30 ET: MARKET entry sent at once")
    b.add_log(ts(2026, 11, 18, 9, 0), "Exit STOP for an entry this process never routed (model entered 08:37 ET during a gap): "
                                      "flatten sent in case a broker position exists - verify by hand")
    check("size 0: its own reason (was 'held back by the bot')", FA._block_reason(b, e1).startswith("size 0:"), FA._block_reason(b, e1))
    lines = FA.not_routed_lines(b)
    check("the bot log's not-routed lines are found (size 0, ATLAS, never routed), not the routed one",
          len(lines) == 3 and not any("MARKET entry sent" in x["text"] for x in lines), lines)
    d = tempfile.mkdtemp(prefix="nqrel_")
    try:
        b._blocked_entries.add(e1)
        FA.collect(b, store=d, now=now, state_path=os.path.join(d, "none.json"), nt_state_path=os.path.join(d, "none2.json"),
                   nt_folder=os.path.join(d, "nofolder"))
        N = json.load(open(os.path.join(d, "notes.json"), encoding="utf-8"))
        check("collect keeps them in notes.json not_routed", len(N.get("not_routed") or []) == 3, N.get("not_routed"))
        FA.collect(b, store=d, now=now + 60, state_path=os.path.join(d, "none.json"), nt_state_path=os.path.join(d, "none2.json"),
                   nt_folder=os.path.join(d, "nofolder"))
        N = json.load(open(os.path.join(d, "notes.json"), encoding="utf-8"))
        check("... once each (a second collect adds none)", len(N["not_routed"]) == 3, len(N["not_routed"]))
        check("the held-back entry's reason in notes is the size-0 line", N["blocked"][str(e1)]["reason"].startswith("size 0"),
              N["blocked"])
        L = FA.day_not_routed("2026-11-18", d)
        check("day_not_routed: the day's lines, oldest first, ids cut to the last 4",
              len(L) == 3 and L[0]["t"] <= L[-1]["t"] and not any("123456" in x["text"] for x in L) and "...3456" in L[1]["text"], L)
        check("day_not_routed: another day has none", FA.day_not_routed("2026-11-17", d) == [])
        gap = ts(2026, 11, 18, 8, 37)
        why = FA._miss_reason(bt_row(gap), N, None, True)
        check("a missed trade's reason comes from the bot's own gap line", "gap" in why and "never routed" in why, why)
        rep = {"rows": [{**FA.compare(bt_row(gap), None, N, (), None), "day": "2026-11-18"}], "days": {}}
        S = FA.nightly("2026-11-18", store=d, now=ts(2026, 11, 18, 16, 10), rep=rep, push_it=False, write=True)
        check("nightly verdict carries the day's NOT routed lines", len(S.get("not_routed") or []) == 3, S.get("not_routed"))
        saved = json.load(open(os.path.join(d, "nightly", "2026-11-18.json"), encoding="utf-8"))
        check("... and the nightly file keeps them", len(saved.get("not_routed") or []) == 3)
        from engine import zeus_review as ZR
        bundle = {"day": "2026-11-18", "trades": [], "twin": {"nightly": saved},
                  "manifest": {"files": {"bars/MNQ_1m.csv.gz": {"rows": 900}}}}
        R = ZR.review([bundle], now=ts(2026, 11, 18, 17, 5))
        it = [i for i in R["items"] if i["key"] == "not_routed"]
        check("ZEUS daily review: one info line 'N entries NOT routed today, first HH:MM ET: why'",
              len(it) == 1 and it[0]["level"] == "info" and "3 entries NOT routed" in it[0]["text"], R["items"])
        # the PC's day files (engine/datafeed): gaps.json
        g = DF.day_gaps("2026-11-18", N)
        gj = json.loads(g)
        check("datafeed gaps.json: not-routed lines + held-back entries + uptime samples of the day",
              len(gj["not_routed"]) == 3 and gj["blocked"][0]["et"] == "06:12" and gj["uptime"], gj)
        check("gaps.json: no account id whole", b"123456" not in g)
        check("gaps.json: nothing for a day with no record", DF.day_gaps("2026-11-10", N) is None)
        check("DAY_FILE accepts days/<day>/gaps.json", bool(DF.DAY_FILE.match("days/2026-11-18/gaps.json")))
        man = json.dumps({"v": 1, "day": "2026-11-18", "partial": False, "files": {}}).encode()
        blob = DF.zip_days({"2026-11-18": {"gaps.json": g, "manifest.json": man}})
        out = os.path.join(d, "pull")
        try:
            DF.extract(blob, out)
            ok = os.path.exists(os.path.join(out, "2026-11-18", "gaps.json"))
        except Exception as e:
            ok = f"{e.__class__.__name__}: {e}"
        check("the cloud's extract writes gaps.json into data/pc_days/<day>/", ok is True, ok)
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ 3. MISSED TRADE at once
def t_missed_now():
    now = ts(2026, 11, 18, 9, 5)
    b = Bot(now)
    b.add_log(ts(2026, 11, 18, 9, 0), "Exit STOP for an entry this process never routed (model entered 08:37 ET during a gap): "
                                      "flatten sent in case a broker position exists - verify by hand")
    b.started_at = ts(2026, 11, 18, 8, 50)
    pos_t = ts(2026, 11, 18, 8, 40)
    b.state = {"position": {"entry_t": pos_t, "dir": 1}}
    U = FA.unrouted_entries(b, now)
    check("never-routed gap entry found (08:37)", any(t == ts(2026, 11, 18, 8, 37) and "never routed" in w for t, w in U), U)
    check("an open model position from before the restart found (08:40, start 08:50)",
          any(t == pos_t and "before this bot start at 08:50" in w for t, w in U), U)
    b.seen.add(("entry", pos_t))
    check("... not when this process routed it", not any(t == pos_t for t, _w in FA.unrouted_entries(b, now)))
    d = tempfile.mkdtemp(prefix="nqmiss_")
    try:
        got = []
        FA.session_alerts(b, store=d, now=now, notify=got.append)
        check("session_alerts sends the gap entry as a Missed trade notice", any(p["key"] == f"exec:miss:{ts(2026, 11, 18, 8, 37)}"
                                                                                 for p in got), [p["key"] for p in got])
        p = FA.missed_payload(ts(2026, 11, 18, 6, 12), "SHORT", "feed stale", None, now)
        mp = FA._missed_problem(p)
        check("a missed trade becomes an instant problem push (code missed, entry_t)", mp and mp["code"] == "missed"
              and mp["entry_t"] == ts(2026, 11, 18, 6, 12) and mp["title"].startswith("MISSED TRADE · Zlarior"), mp)
        own = FA.missed_payload(ts(2026, 11, 18, 7, 1), "", "GUARD paused by you until 10:00", None, now)
        check("the owner's own pause never alarms", FA._missed_problem(own) is None)
        check("a slippage notice is not an instant problem", FA._missed_problem({"key": "exec:slip:1"}) is None)
        sent = []
        orig_pc, orig_ip = None, NT.instant_problem
        from engine import push
        orig_pc = push.pc_notify
        try:
            push.pc_notify = lambda q: sent.append(("app", q["key"]))
            NT.instant_problem = lambda q: sent.append(("ntfy", q["key"])) or "sent"
            FA.send_alerts([p, own], store=d)
        finally:
            push.pc_notify, NT.instant_problem = orig_pc, orig_ip
        from engine import push as _push
        check("a paper bot keeps the old sender only (no MISSED TRADE ntfy for paper / test runs)",
              FA._notify_for(Bot(now, adapter="paper")) is _push.pc_notify and FA._notify_for(b) is None)
        check("the default sender: app notice for both, ntfy for the real miss only",
              sent.count(("ntfy", p["key"])) == 1 and ("ntfy", own["key"]) not in sent and ("app", own["key"]) in sent, sent)
        # notify.instant_problem + the report's dedupe
        path = os.path.join(d, "instant.json")
        posts = []
        poster = lambda base, topic, msg: posts.append(msg) or True
        cfg = {"ntfy": "https://ntfy.invalid", "topic": "t"}
        r = NT.instant_problem({**mp}, now=now, path=path, cfg=cfg, poster=poster)
        check("instant_problem: sent to the private topic, high priority", r == "sent" and posts and posts[0]["priority"] == "high"
              and posts[0]["title"].startswith("MISSED TRADE"), (r, posts))
        r2 = NT.instant_problem({**mp}, now=now + 5, path=path, cfg=cfg, poster=poster)
        check("... once per key", r2 == "already sent" and len(posts) == 1, r2)
        check("... no topic on this PC: not sent", NT.instant_problem({**mp, "key": "x"}, path=path, cfg={}, poster=poster)
              .startswith("no private alert topic"))
        et_ = ts(2026, 11, 18, 6, 12)
        orig_state = NT._instant_state
        NT._instant_state = lambda p_=None: orig_state(path)
        try:
            check("report dedupe: its trade-watch 'missed' for the same entry is skipped",
                  NT.problem_dup({"key": f"watch:lit:{et_ + 30}:missed"}, now + 600))
            check("... an ATLAS watch at the same time is not", not NT.problem_dup({"key": f"watch:atlas:{et_}:missed"}, now + 600))
            check("... a slip watch for the same entry is not", not NT.problem_dup({"key": f"watch:lit:{et_}:slip"}, now + 600))
            NT.instant_problem({"key": "fast:feed_stale:1", "code": "feed_stale", "cond": "feed_stale", "title": "FEED STALE",
                                "body": "x"}, now=now, path=path, cfg=cfg, poster=poster)
            check("report dedupe: cond:feed_stale within 20 min of the fast alarm is skipped",
                  NT.problem_dup({"key": f"cond:feed_stale:{now + 300}"}, now + 300))
            check("... not 30 min later (the report's reminder goes out)", not NT.problem_dup({"key": f"cond:feed_stale:{now}"}, now + 1800))
            check("... its 'back' is not skipped while the fast alarm sent no back", not NT.problem_dup({"key": f"back:feed_stale:{now}"}, now + 300))
            kept = NT.apply([{"key": f"cond:feed_stale:{now + 300}", "title": "FEED STALE", "body": "b", "priority": "high"},
                             {"key": f"cond:nt_down:{now + 300}", "title": "NinjaTrader closed", "body": "b", "priority": "high"}],
                            now + 300, s=NT.merge({}))
            check("notify.apply drops only the duplicate", [m["key"].split(":")[1] for m in kept] == ["nt_down"], kept)
        finally:
            NT._instant_state = orig_state
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ 4. fast alarm
def t_fast_alarm():
    now = ts(2026, 11, 18, 10, 0, 40)                       # a Wednesday, in the entry hours
    b = Bot(now)
    check("healthy bot: no condition", FAL.evaluate(b, now) == {}, FAL.evaluate(b, now))
    b.health["last_ok_poll"] = now - 100
    ev = FAL.evaluate(b, now)
    check("no good poll for 100 s -> bot_down", list(ev) == ["bot_down"] and "100 s" in ev["bot_down"], ev)
    b.health["poll_ms"] = 60000                            # a PC whose polls take 60 s: 100 s is not stuck yet (limit 125 s)
    check("slow PC polls (60 s each): no alarm at 100 s", FAL.evaluate(b, now) == {}, FAL.evaluate(b, now))
    b.health["poll_ms"] = 900
    b.health["last_ok_poll"] = now - 5
    b.thread = SimpleNamespace(is_alive=lambda: False)
    check("poll thread dead -> bot_down", "bot_down" in FAL.evaluate(b, now))
    b.thread = SimpleNamespace(is_alive=lambda: True)
    b.health["last_1m_bar_t"] = now - now % 60 - 180       # newest 1m bar opened 3 min ago -> 2 bars behind
    ev = FAL.evaluate(b, now)
    check("1m feed 2 bars behind -> feed_stale", list(ev) == ["feed_stale"], ev)
    b.health["last_1m_bar_t"] = now - now % 60 - 60
    b.health["feed_block"] = "NinjaTrader 1m bars stale"
    check("the bot's own feed block -> feed_stale", "feed_stale" in FAL.evaluate(b, now))
    b.health["feed_block"] = None
    b.health["last_1m_bar_t"] = now - now % 60 - 120       # one bar late (NinjaTrader writes it on the next tick): no alarm
    check("one bar late: no alarm (120 s limit)", FAL.evaluate(b, now) == {}, FAL.evaluate(b, now))
    b.health["last_ok_poll"] = now - 100
    for lab, bb, t in (("paper bot", Bot(now, adapter="paper"), now), ("bot stopped", Bot(now, running=False), now),
                       ("Saturday", b, ts(2026, 11, 21, 10, 0)), ("before 01:58 ET", b, ts(2026, 11, 18, 1, 30)),
                       ("after 15:55 ET", b, ts(2026, 11, 18, 16, 10)), ("Thanksgiving afternoon (CME halt)", b, ts(2026, 11, 26, 14, 0))):
        if bb is not b:
            bb.health["last_ok_poll"] = t - 100
        check(f"no alarm: {lab}", FAL.evaluate(bb, t) == {}, FAL.evaluate(bb, t))
    st = Bot(now, running=False)
    rec = {"cfg": {"adapter": "ninjatrader"}, "saved_at": now - 7200}
    ev = FAL.evaluate(st, now, server_started_at=now - 600, autostart=rec)
    check("bot stopped in the entry hours while autostart.json says it ran -> bot_stopped", list(ev) == ["bot_stopped"], ev)
    check("... not after an intentional Stop / kill (no autostart record)", FAL.evaluate(st, now, now - 600, None) == {})
    check("... not in the first 3 min of the server (the resume is still starting)", FAL.evaluate(st, now, now - 60, rec) == {})
    check("... not for a paper bot", FAL.evaluate(st, now, now - 600, {"cfg": {"adapter": "paper"}}) == {})
    check("... not outside the hours", FAL.evaluate(st, ts(2026, 11, 18, 17, 30), now - 600, rec) == {})
    b2 = Bot(now)
    b2.started_at = now - 60
    b2.health["last_ok_poll"] = now - 100
    check("no alarm in the first 3 min after a start", FAL.evaluate(b2, now) == {})
    # redteam 2026-11-20: LiveBot.started_at = the day's FIRST start (min with the restored state) and health.last_ok_poll
    # survives a STOP: a START / Re-arm at 13:00 after a STOP at 10:00 read "no good poll for 3 h" before its first poll
    rs = Bot(now)
    rs.started_at = now - 11 * 3600                        # the day's first start (restored)
    rs.health["last_ok_poll"] = now - 3 * 3600             # the last poll before the owner's STOP
    sent_rs = []
    fr = FAL.FastAlarm(send=lambda p: sent_rs.append(p) or "sent", clock=lambda: now)
    rs.running = False
    fr.step(rs, now - 60)                                  # stopped
    rs.running = True
    fr.step(rs, now)                                       # START (Re-arm): its first poll is still running
    fr.step(rs, now + 30)
    check("START / Re-arm in the entry hours after a long STOP: no 'not polling' before its first poll (grace from this run)",
          sent_rs == [], sent_rs)
    rs.health["last_ok_poll"] = now + 50
    fr.step(rs, now + 90)
    check("... and none once it polls", sent_rs == [], sent_rs)
    rs.health["last_ok_poll"] = now + 50
    fr.step(rs, now + 50 + 200)
    check("... a run that then really stops polling still alarms (200 s without a good poll)", [p["cond"] for p in sent_rs] == ["bot_down"],
          sent_rs)
    st2 = Bot(now)
    st2.started_at = now - 11 * 3600
    st2.health["last_ok_poll"] = None
    fr2 = FAL.FastAlarm(send=lambda p: sent_rs.append(p) or "sent", clock=lambda: now)
    n0 = len(sent_rs)
    fr2.step(st2, now)                                     # a server restart: a new process sees the resumed bot running
    fr2.step(st2, now + 120)
    check("server restart in the entry hours: no alarm in the new run's grace", len(sent_rs) == n0, sent_rs[n0:])
    fr2.step(st2, now + 200)
    check("... it alarms if the resumed bot never polls (stuck from its start)", len(sent_rs) == n0 + 1, sent_rs[n0:])
    sent = []
    fa = FAL.FastAlarm(send=lambda p: sent.append(p) or "sent", clock=lambda: now)
    fa.run_seen, fa._was_running = now - 3600, True      # the bot has run for an hour when these steps start
    b.health["last_ok_poll"] = now - 100
    b.health["last_1m_bar_t"] = now - now % 60 + 60       # fresh bars for the whole sequence below
    fa.step(b, now)
    fa.step(b, now + 30)
    fa.step(b, now + 60)
    check("one push when it starts, none repeated", len(sent) == 1 and sent[0]["cond"] == "bot_down"
          and sent[0]["title"] == "ZEUS not polling", sent)
    b.health["last_ok_poll"] = now + 85
    fa.step(b, now + 90)
    check("one 'back to normal' when it clears", len(sent) == 2 and sent[1].get("back") and sent[1]["cond"] == "bot_down", sent)
    fa.step(b, now + 120)
    check("... and nothing more", len(sent) == 2)
    old = os.environ.get("LE_FAST_ALARM")
    os.environ["LE_FAST_ALARM"] = "0"
    try:
        b.health["last_ok_poll"] = now
        fa2 = FAL.FastAlarm(send=lambda p: sent.append(p) or "sent")
        fa2.step(b, now + 300)
        check("LE_FAST_ALARM=0 turns it off", len(sent) == 2)
    finally:
        if old is None:
            os.environ.pop("LE_FAST_ALARM", None)
        else:
            os.environ["LE_FAST_ALARM"] = old
    w_fake = WD.Watchdog(b, send=lambda t: None, clock=lambda: now)
    check("watchdog with a fake clock (tests): no fast alarm (never pushes to the phone)", w_fake.fast is None)
    w_real = WD.Watchdog(SimpleNamespace(running=False, health={}), send=lambda t: None)
    check("the server's watchdog (real clock) carries the fast alarm", isinstance(w_real.fast, FAL.FastAlarm))
    w_real.check()
    check("watchdog.status shows the fast alarm", "fast_alarm" in w_real.status())


# ------------------------------------------------------------------------------------------------ 4b. no alarm storm (redteam)
def t_fast_alarm_storm():
    """redteam 2026-11-20: a feed that flaps (stale 1 min, fresh 1 min, all morning) used to push a start + a 'back' each
    time, with no limit, and problem pushes were not counted in ntfy's daily room (the status posts use ~220 of ~250), so a
    bad night could leave no room for the trade alerts. Now: one alarm per condition per 30 min unless it is still there
    after that, at most 6 a day, and every problem push is counted in the day's ntfy budget."""
    now = ts(2026, 11, 18, 9, 0, 40)
    b = Bot(now)
    sent = []
    fa = FAL.FastAlarm(send=lambda p: sent.append(p) or "sent", clock=lambda: now)
    fa.run_seen, fa._was_running = now - 3600, True      # the bot has run for an hour when these steps start
    t = now
    for i in range(30):                                    # 30 flaps: stale 60 s, fresh 60 s (one hour), polls fine
        b.health["last_ok_poll"] = t - 5
        b.health["last_1m_bar_t"] = t - t % 60 - 240       # stale
        fa.step(b, t)
        t += 60
        b.health["last_ok_poll"] = t - 5
        b.health["last_1m_bar_t"] = t - t % 60 - 60        # fresh
        fa.step(b, t)
        t += 60
    starts = [p for p in sent if not p.get("back")]
    check("flapping feed for an hour: at most 2 alarms (one per 30 min), not 30", 1 <= len(starts) <= 2, [p["key"] for p in sent])
    check("... each 'back to normal' follows a pushed alarm only", len(sent) - len(starts) <= len(starts), [p["key"] for p in sent])
    sent.clear()
    fa = FAL.FastAlarm(send=lambda p: sent.append(p) or "sent", clock=lambda: now)
    fa.run_seen, fa._was_running = now - 3600, True      # the bot has run for an hour when these steps start
    b.health["last_1m_bar_t"] = now - now % 60 - 60
    b.health["last_ok_poll"] = now - 5
    fa.step(b, now)                                        # healthy
    b.health["last_1m_bar_t"] = now - now % 60 - 240
    b.health["last_ok_poll"] = now + 25
    fa.step(b, now + 30)                                   # stale: pushed
    b.health["last_1m_bar_t"] = now + 60 - (now + 60) % 60 - 60
    b.health["last_ok_poll"] = now + 55
    fa.step(b, now + 60)                                   # fresh: back
    b.health["last_1m_bar_t"] = now + 120 - (now + 120) % 60 - 240
    b.health["last_ok_poll"] = now + 115
    fa.step(b, now + 120)                                  # stale again 90 s after its alarm: held
    check("the same condition again within 30 min: held (no second alarm yet)", len([p for p in sent if not p.get("back")]) == 1
          and fa.active.get("feed_stale", {}).get("held"), (sent, fa.active))
    tt = now + 120 + FAL.PERSIST_S + 1
    b.health["last_ok_poll"] = tt - 5
    b.health["last_1m_bar_t"] = tt - tt % 60 - 240
    fa.step(b, tt)
    check("... the held repeat still there 5 min later (after a 'back to normal'): pushed then, never silent",
          len([p for p in sent if not p.get("back")]) == 2 and fa.active["feed_stale"]["sent"], sent)
    sent.clear()
    fa = FAL.FastAlarm(send=lambda p: sent.append(p) or "sent", clock=lambda: now)
    fa.run_seen, fa._was_running = now - 3600, True      # the bot has run for an hour when these steps start
    t = now
    for i in range(20):                                    # a lasting flap every 31 min, all day
        b.health["last_ok_poll"] = t - 5
        b.health["last_1m_bar_t"] = t - t % 60 - 240
        fa.step(b, t)
        b.health["last_1m_bar_t"] = t + 60 - (t + 60) % 60 - 60
        fa.step(b, t + 60)
        t += FAL.REPEAT_S + 60
    check(f"at most {FAL.DAY_MAX} alarm pushes an ET day", len([p for p in sent if not p.get("back")]) == FAL.DAY_MAX,
          len([p for p in sent if not p.get("back")]))
    d = tempfile.mkdtemp(prefix="nqstorm_")
    try:
        path = os.path.join(d, "instant.json")
        cfg = {"ntfy": "https://ntfy.invalid", "topic": "t"}
        n0 = NT.ntfy_today(now, path=path)
        NT.instant_problem({"key": "fast:bot_down:1", "code": "bot_down", "cond": "bot_down", "title": "x", "body": "y"},
                           now=now, path=path, cfg=cfg, poster=lambda *a: True)
        check("a problem push counts in the day's ntfy budget (pc_report keeps room for the trade alerts)",
              NT.ntfy_today(now, path=path) == n0 + 1, NT.ntfy_today(now, path=path))
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ 3b. rule holds are quiet (redteam)
def t_rule_holds_quiet():
    """redteam 2026-11-20: every held-back entry became a loud MISSED TRADE push that rings in quiet hours, also when the bot's
    own rule held it back on purpose (soft daily loss, weekly stop / size 0, the equity filter, the 50K's one-position rule):
    a 03:00 ET LIT signal after the weekly stop would wake the owner each time. A rule hold is now a quiet 'held back' notice;
    a malfunction stays loud."""
    et_ = ts(2026, 11, 19, 3, 5)
    s = NT.merge({})
    for why in ("GUARD today's routed P&L -$520 reached the $500 soft daily loss",
                "size 0: weekly loss stop reached (-$1,250 this week)",
                "last 5 signals -2.10R > -1.0R: skipped",
                "one position on the 50K: ATLAS on Zlarior 50K holds a LONG ema trade from 02:55 ET (conflict rule first_in)"):
        mp = FA._missed_problem(FA.missed_payload(et_, "", why, None, et_ + 30))
        m = NT.problem_message(mp, now=et_ + 30, s=s)
        check(f"rule hold is a quiet notice at 03:05 ET (no ring): {why[:40]}", mp.get("soft") and m["priority"] == "low"
              and "Held back" in m["title"] and "MISSED" not in m["title"], (mp, m))
    m10 = NT.problem_message(FA._missed_problem(FA.missed_payload(et_, "", "size 0: weekly loss stop", None, et_)),
                             now=ts(2026, 11, 19, 10, 0), s=s)
    check("... by day: a normal-priority notice", m10["priority"] == "default", m10)
    for why in ("feed stale", "seen 3 min late (restart / feed gap) - not chasing", "refused: REFUSED: NinjaTrader reports every "
                "connection DISCONNECTED", "STARTUP DISARMED until reconciled: x", "held back by the bot (see the bot log)",
                "the model entered while the bot was down or its feed was behind: never routed"):
        mp = FA._missed_problem(FA.missed_payload(et_, "", why, None, et_ + 30))
        m = NT.problem_message(mp, now=et_ + 30, s=s)
        check(f"malfunction stays a loud MISSED TRADE that rings at 03:05 ET: {why[:40]}", not mp.get("soft")
              and m["priority"] == "high" and m["title"].startswith("MISSED TRADE"), (mp, m))


# ------------------------------------------------------------------------------------------------ 5. no update under ATLAS
def t_update_flat():
    class B:
        def __init__(self, pos=None, legs=()):
            self._pos = pos
            self.adapter = SimpleNamespace(legs=list(legs))

        def position(self):
            return self._pos
    bot = SimpleNamespace(running=True, state={}, _open_routed=None, adapter=SimpleNamespace(legs=[]), acct_b=B(), acct_c=None)
    check("all flat: an update may run", AU.bot_flat_reason(bot) is None, AU.bot_flat_reason(bot))
    bot.acct_b = B(pos={"entry_t": 1, "side": "LONG"})
    check("ATLAS holds a position: no update / restart", AU.bot_flat_reason(bot) == "ATLAS has a position open", AU.bot_flat_reason(bot))
    bot.acct_b = B(legs=[{"status": "protected"}])
    check("ATLAS's bracket open at NinjaTrader: no update", "ATLAS's NinjaTrader bracket" in (AU.bot_flat_reason(bot) or ""))
    bot.acct_b = B(legs=[{"status": "closed"}])
    check("ATLAS's closed bracket: flat", AU.bot_flat_reason(bot) is None)
    # redteam 2026-11-20: an extra account / a fleet follower in a trade of its own keeps the update / restart away too
    bot.accts = SimpleNamespace(accounts=[SimpleNamespace(name="Zlarior 25K #2", open_t=123, adapter=SimpleNamespace(legs=[]))])
    check("an extra account holds a position: no update / restart", AU.bot_flat_reason(bot) == "Zlarior 25K #2 has a position open",
          AU.bot_flat_reason(bot))
    bot.accts = SimpleNamespace(accounts=[SimpleNamespace(name="Rapid", open_t=None, adapter=SimpleNamespace(legs=[{"status": "pending"}]))])
    check("an extra account's bracket pending: no update", "Rapid's NinjaTrader bracket is pending" == AU.bot_flat_reason(bot),
          AU.bot_flat_reason(bot))
    bot.accts = SimpleNamespace(accounts=[SimpleNamespace(name="Rapid", open_t=None, adapter=SimpleNamespace(legs=[]))])
    bot.fleet = SimpleNamespace(busy=lambda: True)
    check("a fleet follower holds a position: no update", AU.bot_flat_reason(bot) == "a fleet follower has a position open",
          AU.bot_flat_reason(bot))
    bot.fleet = SimpleNamespace(busy=lambda: False)
    check("everyone flat: an update may run", AU.bot_flat_reason(bot) is None, AU.bot_flat_reason(bot))


# ------------------------------------------------------------------------------------------------ 6. extra accounts
def t_extra_account():
    """engine/multi_account.Account: an account added while the bot runs never books / flattens a model trade that ended
    before it joined (PC 2026-11-17 20:26 ET: Zlarior 25K #2 booked the Nov 16 06:16 stop, -$129.40, and sent a
    CLOSEPOSITION); the exit of an entry it never routed books $0, not the model's $."""
    from engine import multi_account as MA
    clock = {"t": ts(2026, 11, 17, 20, 26)}
    sent = []

    class R:
        bot = SimpleNamespace(fleet=None)
        def clock(self): return clock["t"]
        def log(self, kind, text): pass
        def save(self): pass
        def killed(self): return False
        def opposite_open(self, *a, **k): return None
        def others_opposite(self, *a, **k): return None
        def notify_outcome(self, *a, **k): pass

    spec = {"id": "b25k_2", "name": "Zlarior 25K #2", "rules": {"news_ban": None}, "mode": "eval", "adapter": "ninjatrader"}
    acc = MA.Account(spec, R())
    acc.adapter = SimpleNamespace(route_all_exits=True, send=lambda a: sent.append(a) or {"ok": True})
    old_tr = {"entry_t": ts(2026, 11, 16, 6, 16), "exit_t": ts(2026, 11, 16, 7, 0), "exit_reason": "STOP", "qty": 1, "pnl": -129.4,
              "dir": 1}
    ctx = {"res": {"trades": [old_tr]}, "sym": "NQ", "now": clock["t"] + 60, "secs": 300, "state": {}, "flat_mod": 955,
           "start": ts(2026, 11, 16, 1, 0), "fill_bar_seen": lambda t: True}
    acc._process(ctx)
    check("account added Nov 17 20:26: the Nov 16 trade (ended before it joined) -> no order, no ledger row",
          not sent and not acc.ledger, (sent, acc.ledger))
    # a trade that ends after the account joined, entered during a gap (never routed here): flatten in case, but $0 booked
    gap_tr = {"entry_t": clock["t"] - 120, "exit_t": clock["t"] + 600, "exit_reason": "STOP", "qty": 2, "pnl": -250.0, "dir": 1}
    clock["t"] += 700
    ctx2 = {**ctx, "res": {"trades": [gap_tr]}, "now": clock["t"]}
    acc._process(ctx2)
    ex = [a for a in sent if a.get("side") == "exit"]
    check("exit of an entry this account never routed: the safety flatten still goes out", len(ex) == 1, sent)
    check("... and it books $0, not the model's -$250", ex and ex[0].get("pnl") == 0.0, ex)
    check("... no close in its eval book", not acc.closes, acc.closes)
    # redteam 2026-11-20: the Rapid EOD's LIT lane shares ONE NinjaTrader account with ATLAS's lane (engine/rapid.RapidAtlas):
    # its "in case" flatten of an entry it never routed is a CLOSEPOSITION of the whole account = it would close ATLAS's trade
    for lab, partner, want in (("ATLAS's lane holds a position", SimpleNamespace(label="ATLAS Rapid", open_t=clock["t"] - 900,
                                                                                 adapter=SimpleNamespace(legs=[])), 0),
                               ("ATLAS's lane has a bracket still closing", SimpleNamespace(label="ATLAS Rapid", open_t=None,
                                adapter=SimpleNamespace(legs=[{"status": "closing", "entry_t": 1}])), 0),
                               ("ATLAS's lane is flat", SimpleNamespace(label="ATLAS Rapid", open_t=None,
                                                                        adapter=SimpleNamespace(legs=[{"status": "closed"}])), 1)):
        sent.clear()
        r2 = R()
        r2.bot = SimpleNamespace(fleet=None, acct_r=partner)
        lane = MA.Account({**spec, "id": "rapid_lit", "lane": "rapid"}, r2)
        lane.adapter = SimpleNamespace(route_all_exits=True, send=lambda a: sent.append(a) or {"ok": True})
        gap2 = {**gap_tr, "entry_t": clock["t"] - 60, "exit_t": clock["t"] + 300}
        clock["t"] += 400
        lane._process({**ctx, "res": {"trades": [gap2]}, "now": clock["t"], "start": clock["t"] - 3600})
        n = len([a for a in sent if a.get("side") == "exit"])
        check(f"Rapid LIT lane, exit of an entry it never routed, {lab}: {'no CLOSEPOSITION' if not want else 'the safety flatten goes'}",
              n == want, sent)


def main() -> bool:
    for f in (t_unknown, t_not_routed, t_missed_now, t_fast_alarm, t_fast_alarm_storm, t_rule_holds_quiet, t_update_flat, t_extra_account):
        try:
            f()
        except Exception as e:
            import traceback
            traceback.print_exc()
            check(f"{f.__name__} ran", False, f"{e.__class__.__name__}: {e}")
    ok = all(RES)
    print(f"{sum(RES)}/{len(RES)} passed")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
