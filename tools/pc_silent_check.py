"""PC SILENT check (owner 2026-11-17): the cloud notices when the PC stops reporting, with the PC off (that is the point).

Why: the PC had not reported since 2026-11-07 and nobody noticed. The old cloud alert (engine/push.pc_outage) only reads the
`heartbeat` branch and only goes to the Home Screen app; in GitHub-free mode the PC reports to ntfy instead, so the branch just
looked old forever and one app notice was all.

Runs as its own step of the cloud monitor (.github/workflows/cloud-monitor.yml, every run: about every 30 min on weekdays
01:30-16:40 ET, hourly at midday), before the paper monitor, stdlib only, never fails the job:
  1. last sign of life = the newest of the heartbeat branch's "t" (engine/heartbeat.read) and the newest PC status post on the
     public ntfy status topic (tools/web_public/status_feed.json, ntfy keeps 12 h; only "le-live" posts count)
  2. engine/notify.silent_step: older than pc_silent_after_min (20) inside market hours -> "Your PC stopped reporting at HH:MM ET.
     Check it: STOP BOT, START BOT." once, one reminder after 2 h, then nothing that trading day; "PC reporting again" when back
  3. the push goes to your PRIVATE alert topic when the repository secret LE_NTFY_TOPIC holds it (the topic your ntfy app
     already follows; never printed). Without it, the plain alert (no names, no ids, no $) goes to the public status topic.
  4. (night-k7cloud 2026-11-23) the MFFU 7-day clock: the PC looks off (last post > 2 h) on an account's keep-alive act day (01:30 ET ..
     16:05), or less than 24 h before its MFFU last day -> ONE push per account and day "PC looks off: <account> must trade by <date>",
     telling to turn the PC on or place 1 MNQ by hand before 16:05 ET (k7_step; the last clock rows are kept for a long-off PC)
State: <out>/pc_silent.json (published with the dashboard branch); today's pushes are also read back from the topic, so a lost
state file never repeats one. Never places, changes or arms anything.

  python tools/pc_silent_check.py --out dash             one check (the workflow step)
  python tools/pc_silent_check.py --out dash --dry-run   prints what it would send, sends nothing
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import notify  # noqa: E402

STATUS_FEED = os.path.join(ROOT, "tools", "web_public", "status_feed.json")
STATE_NAME = "pc_silent.json"
UA = "olympus-pc-silent/1"
TOPIC_RX = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MARK = ("PC stopped reporting", "PC still silent")
PRE_MARK = "PC is off"
# SUNDAY (day-nqops 2026-11-21, lead): the PC-silent window (engine/notify.silent_window) is weekdays 01:30-16:00 ET and never runs on
# Sunday. scripts/schedule_pc.ps1 hibernates the PC Fri 16:35 ET and wakes it Mon 01:30 ET, and that is by design: no LIVE lane enters
# before 02:00 ET (LIT 02:00-15:30; ATLAS EMA 03:00, MACD 02:00, S/R 09:30; the Rapid = the same lanes; LIT+Asia is cloud-only paper;
# tests/test_nqops guards it). So a silent PC on Sunday evening is normal: ONE quiet note "asleep until the Mon 01:30 ET wake", unless a
# 7-day clock is red, then ONE loud push with exactly what to do. A missed Monday wake is the PC-silent check's (01:30 + 20 min).
SUNDAY_EVENING_LANES = ()            # live lanes that enter between Sun 18:00 and Mon 01:30 ET: none (see above)
PRE_WINDOWS = ((6, 17 * 60, 18 * 60, 18 * 60, "market opens"),)        # Sunday 17:00-18:00 ET


def http_get(url, timeout=20, limit=3_000_000) -> tuple:
    """-> (status, text). Never raises."""
    if os.environ.get("LE_PR_NO_NET") == "1":
        return 0, "network off"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(limit).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, e.__class__.__name__


def http_post(url, body: bytes, headers: dict, timeout=20) -> tuple:
    if os.environ.get("LE_PR_NO_NET") == "1":
        return 0, "network off"
    req = urllib.request.Request(url, data=body, method="POST", headers={"User-Agent": UA, **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(2000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, e.__class__.__name__


def feed_cfg(path: str = STATUS_FEED) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        d = {}
    return {"ntfy": str(d.get("ntfy") or "https://ntfy.sh").rstrip("/"), "topic": str(d.get("topic") or "").strip()}


def dest(env=None, feed: dict | None = None) -> dict:
    """Where the alert goes: {"base", "topic", "private"}. LE_NTFY_TOPIC = a topic name or https://host/topic."""
    env = os.environ if env is None else env
    feed = feed or feed_cfg()
    v = str(env.get("LE_NTFY_TOPIC") or "").strip().rstrip("/")
    if v:
        m = re.fullmatch(r"(https://[A-Za-z0-9.-]+)/([A-Za-z0-9_-]{1,64})", v)
        if m:
            return {"base": m.group(1), "topic": m.group(2), "private": True}
        if TOPIC_RX.fullmatch(v):
            return {"base": feed["ntfy"], "topic": v, "private": True}
    return {"base": feed["ntfy"], "topic": feed["topic"] if TOPIC_RX.fullmatch(feed["topic"] or "") else "", "private": False}


def poll(base, topic, since="12h", get=None) -> tuple:
    """(answered, [ntfy message dicts]) of a topic's cached messages."""
    get = get or http_get
    if not topic:
        return False, []
    st, txt = get(f"{base}/{topic}/json?poll=1&since={since}")
    if not (200 <= int(st or 0) < 300):
        return False, []
    out = []
    for ln in str(txt or "").splitlines():
        try:
            m = json.loads(ln)
        except Exception:
            continue
        if isinstance(m, dict) and m.get("event", "message") == "message":
            out.append(m)
    return True, out


def feed_last(msgs) -> int | None:
    """The newest PC status post time (only the PC's 'le-live' core posts; the cloud's own alert text is not one, and neither is the
    'le-live-ext' extras post, which goes only every 2nd run: the core is the heartbeat)."""
    best = None
    for m in msgs:
        try:
            j = json.loads(m.get("message") or "")
        except Exception:
            continue
        if not isinstance(j, dict) or j.get("kind") != "le-live":
            continue
        rt = notify._f(_d(j.get("reporter")).get("t")) or notify._f(m.get("time")) or notify._f(j.get("t"))
        if rt and (best is None or rt > best):
            best = int(rt)
    return best


def _d(x):
    return x if isinstance(x, dict) else {}


def sent_today(msgs, now) -> list:
    """Times of this ET day's PC-silent pushes found on the alert topic."""
    day = notify._et(now).date()
    return [int(m["time"]) for m in msgs if str(m.get("title") or "").startswith(MARK) and notify._f(m.get("time"))
            and notify._et(m["time"]).date() == day]


def pre_window(now):
    """(minutes to the open, words) inside a pre-open window, else None (a CME full closure: None)."""
    e = notify._et(now)
    mod = e.hour * 60 + e.minute
    for wd, a, b, at, words in PRE_WINDOWS:
        if e.weekday() == wd and a <= mod < b:
            try:
                from engine.cme_calendar import full_closure
                import datetime as _dt
                day = e.date() + _dt.timedelta(days=1 if wd == 6 else 0)
                if full_closure(day):
                    return None
            except Exception:
                pass
            return at - mod, words
    return None


def feed_clock(msgs, now) -> list:
    """The MFFU 7-day clock rows (engine/clock7) from the newest PC ext post on the status topic that carries mf / k7."""
    best, bt = None, -1
    for m in msgs:
        try:
            j = json.loads(m.get("message") or "")
        except Exception:
            continue
        x = _d(_d(j).get("x"))
        if _d(j).get("kind") == "le-live-ext" and (x.get("k7") or x.get("mf")):
            t = int(notify._f(m.get("time")) or 0)
            if t > bt:
                best, bt = x, t
    if not best:
        return []
    try:
        from engine import clock7
        k = clock7.build(best.get("mf"), None, now) if best.get("mf") else {"a": _d(best.get("k7")).get("a") or []}
        rows = list(_d(k).get("a") or [])
        # day-accounts 2026-11-23: the PC's own k7 rows know the keep-alive's fills and its ON switches (the heartbeat's keepalive
        # block); the mf rows alone do not, so after a keep-alive trade the cloud counted from the older strategy trade and pushed
        # "must trade" for an account that had traded. Per account the NEWER base day wins; "on" comes from the PC's row.
        if best.get("mf") and isinstance(_d(best.get("k7")).get("a"), list) and _d(best.get("k7")).get("a"):
            pc = {str(r.get("id")): r for r in _d(best["k7"]).get("a") if isinstance(r, dict) and r.get("id") and r.get("hard")}
            out = []
            for r in rows:
                p = pc.get(str(r.get("id")))
                if p and str(p["hard"]) > str(r.get("hard")):
                    base = _dt_base(p)
                    r2 = clock7.row(str(r["id"]), r.get("nm"), base if p.get("base") != "start" else None,
                                    None if p.get("base") != "start" else _next_day(base), now, p.get("on"))
                    r = r2 or r
                elif p and p.get("on") is not None:
                    r = {**r, "on": p.get("on")}
                out.append(r)
            seen = {str(r.get("id")) for r in out}
            for aid, p in pc.items():              # an account the PC's k7 has and its mf block does not (cut for size)
                if aid not in seen:
                    base = _dt_base(p)
                    r2 = clock7.row(aid, p.get("nm") or aid, base if p.get("base") != "start" else None,
                                    None if p.get("base") != "start" else _next_day(base), now, p.get("on"))
                    if r2:
                        out.append(r2)
            rows = sorted(out, key=lambda r: (r["left"], r["id"]))
        return rows
    except Exception:
        return []


def _dt_base(r) -> str:
    """The day a k7 row counts from (its last fill, or the day before its start): hard - its limit."""
    import datetime as _dt
    return (_dt.date.fromisoformat(str(r["hard"])[:10]) - _dt.timedelta(days=int(r.get("lim") or 7))).isoformat()


def _next_day(d: str) -> str:
    import datetime as _dt
    return (_dt.date.fromisoformat(d) + _dt.timedelta(days=1)).isoformat()


def preopen_step(prev: dict | None, seen_t, now, s: dict | None = None, fetched: bool = True, sent=(), clock=()) -> tuple:
    """-> (state, [push]): ONE "PC is off" push per pre-open window and day while the PC's last post is stale. Never raises."""
    try:
        s = s or notify.settings()
        now = int(now)
        st = dict(_d(prev))
        w = pre_window(now)
        if not w or not fetched or not notify.on("pc_silent", s):
            return st, []
        stale = not seen_t or now - int(seen_t) > int(s.get("pc_silent_after_min", 20)) * 60
        day = notify._et(now).date().isoformat()
        if not stale or st.get("day") == day or any(notify._et(t).date().isoformat() == day for t in sent or ()):
            return st, []
        mins, words = w
        last = notify.since_text(seen_t, now) if seen_t else "never seen"
        red = [r for r in clock or () if isinstance(r, dict) and r.get("lvl") == "bad"]
        st.update(day=day, t=now)
        if red or SUNDAY_EVENING_LANES:
            from engine import clock7
            r = red[0] if red else None
            body = (clock7.line(r) + ". " if r else "")
            body += ("The PC wakes Mon 01:30 ET (as scheduled) and the bot trades from 02:00 ET: at 02:00 check the phone shows the PC "
                     "reporting. If it is not, turn the PC on, open NinjaTrader, connect, START BOT. If there is no fill by 15:30 ET "
                     "Monday, place 1 MNQ by hand while every account is flat (or switch on the keep-alive: KEEPALIVE_ON.bat).")
            if SUNDAY_EVENING_LANES and not r:
                body = f"PC asleep (last report {last}) but {', '.join(SUNDAY_EVENING_LANES)} trades Sunday evening: turn the PC on now."
            title = (f"{r['nm']}: must trade by {r['hard']}" if r else f"{PRE_MARK}: {words} in {mins} min")
            return st, [{"key": f"pc_preopen:{day}", "title": f"{PRE_MARK} - {title}" if r else title, "body": body[:600],
                         "priority": "high", "tags": "warning,computer"}]
        body = (f"Last report {last}. As scheduled it wakes Mon 01:30 ET; nothing trades before 02:00 ET. No 7-day clock is red. "
                "Nothing to do.")
        return st, [{"key": f"pc_preopen:{day}", "title": f"{PRE_MARK}: asleep until the Mon 01:30 ET wake (as scheduled)", "body": body[:600],
                     "priority": "low", "tags": "zzz"}]
    except Exception:  # noqa: BLE001
        return dict(_d(prev)), []


# K7 CLOUD (night-k7cloud 2026-11-23): the PC is off on a keep-alive act day, or close to an account's MFFU last day. The PC cannot push
# then, so the cloud does: ONE push per account and ET day, "PC looks off; <account> must trade by <date>; turn the PC on, or place 1 MNQ
# by hand before 16:05 ET". The clock rows come from the PC's newest ext post (engine/clock7 via feed_clock); ntfy keeps only 12 h, so the
# last rows seen are kept in the state (the Actions cache) and rebuilt from their base day: a PC off for days still gets its warning.
K7_MARK = "PC looks off"
K7_STALE_S = 2 * 3600            # the PC's last post older than this = "looks off" (the PC-silent push already went at 20 min)
K7_BEFORE_S = 24 * 3600          # inside the last 24 h before the hand-trade time of an account's MFFU last day: warn, any hour
K7_FROM = 90                     # act-day warnings 01:30 ET .. the hand-trade time (the pc-watch window)


def hand_by(day) -> int:
    """ET minute to place the hand trade by on `day`: 16:05 (MFFU flat 16:10), a CME half day: 5 min before its halt."""
    try:
        from engine.cme_calendar import early_close
        ec = early_close(day)
        return int(ec) - 5 if ec else 16 * 60 + 5
    except Exception:
        return 16 * 60 + 5


def _k7_rows(rows, prev_rows, now) -> list:
    """Fresh rows from the feed, else the kept ones rebuilt for `now` from their base day (clock7.row). [] when none."""
    import datetime as _dt
    if rows:
        return [r for r in rows if isinstance(r, dict) and r.get("id") and r.get("hard")]
    out = []
    try:
        from engine import clock7
        for k in prev_rows or []:
            base = _dt.date.fromisoformat(str(k["base_day"]))
            r = clock7.row(str(k["id"]), str(k.get("nm") or k["id"]), base.isoformat(), None, now, k.get("on"))
            if r:
                out.append(r)
    except Exception:
        return []
    return out


def _keep(rows) -> list:
    import datetime as _dt
    out = []
    for r in rows or []:
        try:
            lim = int(r.get("lim") or 7)
            base = _dt.date.fromisoformat(str(r["hard"])) - _dt.timedelta(days=lim)
            if lim == 7:                          # MFFU only: the keep-alive / hand-trade warning is MFFU's rule
                out.append({"id": r["id"], "nm": r.get("nm"), "base_day": base.isoformat(), "on": r.get("on")})
        except Exception:
            continue
    return out


def k7_step(prev: dict | None, seen_t, now, rows=(), fetched: bool = True, sent=()) -> tuple:
    """-> (state, [push]): per account, ONE push a day while the PC looks off (last post > K7_STALE_S) and either today is its keep-alive
    act day inside 01:30 ET .. the hand-trade time, or its MFFU last day's hand-trade time is less than 24 h away. `sent` = the titles
    of today's K7 pushes read back from the topic (a lost cache never repeats one). Never raises."""
    import datetime as _dt
    st = dict(_d(prev))
    try:
        now = int(now)
        rows = _k7_rows(list(rows or ()), st.get("rows"), now)
        if rows:
            st["rows"] = _keep(rows)
        e = notify._et(now)
        day = e.date().isoformat()
        done = set(_d(st.get("done")).get(day) or [])
        if not fetched or (seen_t and now - int(seen_t) <= K7_STALE_S):
            return st, []
        mod = e.hour * 60 + e.minute
        try:
            from engine.cme_calendar import full_closure
            closed = full_closure(e.date())
        except Exception:
            closed = False
        last = notify.since_text(seen_t, now) if seen_t else "never seen"
        out = []
        for r in rows:
            aid, nm = str(r["id"]), str(r.get("nm") or r["id"])[:40]
            # day-accounts 2026-11-23: the exact title, not a substring: "Rapid EOD 25K" is inside "Rapid EOD 25K #2", so the 1st
            # Rapid's push silenced the 2nd Rapid's (the new Rapid EOD 25K) for the day
            if int(r.get("lim") or 7) != 7 or aid in done or any(str(t).startswith(f"{K7_MARK}: {nm} must trade by ") for t in sent or ()):
                continue
            hard = _dt.date.fromisoformat(str(r["hard"]))
            hb = hand_by(hard)
            dl_t = int(_dt.datetime(hard.year, hard.month, hard.day, hb // 60, hb % 60, tzinfo=notify.ET).timestamp())
            act = r.get("act") == day and e.weekday() < 5 and not closed and K7_FROM <= mod < hand_by(e.date())
            near = 0 <= dl_t - now <= K7_BEFORE_S
            if not (act or near):
                continue
            when = f"{hard:%a} {hard.month}-{hard.day:02d}"
            hb_today = hand_by(e.date()) if hard == e.date() else hb
            body = (f"{K7_MARK} (last report {last}). {nm} must trade by {when} (MFFU's last day; no fill since "
                    f"{r.get('lf') or 'its start'}). Turn the PC on (NinjaTrader + START BOT: the keep-alive trades by itself), or place "
                    f"1 MNQ by hand before {hb_today // 60:02d}:{hb_today % 60:02d} ET while the account is flat, in and out.")
            out.append({"key": f"k7cloud:{aid}:{day}", "title": f"{K7_MARK}: {nm} must trade by {when}", "body": body[:600],
                        "priority": "urgent" if hard == e.date() else "high", "tags": "warning,computer"})
            done.add(aid)
        if out:
            st["done"] = {day: sorted(done)}       # only today's (a new day starts empty)
        return st, out
    except Exception:  # noqa: BLE001
        return st, []


def read_hb(now):
    try:
        from engine import heartbeat
        return heartbeat.read(cwd=ROOT, now=now)
    except Exception as e:
        return {"present": False, "reason": e.__class__.__name__}


def _bus(env=None):
    """engine/alert_bus when the cloud has a Telegram / Discord secret (never the PC's own file here), else None (ntfy only)."""
    try:
        from engine import alert_bus
        e = os.environ if env is None else env
        c = alert_bus.config({k: v for k, v in e.items() if k.startswith(("LE_TG_", "LE_DISCORD_", "LE_ALERT_BUS"))} | {"OLYMPUS_HOME": "/nonexistent"})
        return alert_bus if (c.get("telegram") or c.get("discord")) and not alert_bus.switched_off(e) else None
    except Exception:
        return None


def _bus_cfg(bus, env=None) -> dict:
    e = os.environ if env is None else env
    c = bus.config({k: v for k, v in e.items() if k.startswith(("LE_TG_", "LE_DISCORD_"))} | {"OLYMPUS_HOME": "/nonexistent"})
    return {**c, "ntfy": False, "webpush": False}          # the cloud: Telegram / Discord only; ntfy stays the old post below


def run(out: str, now=None, env=None, get=None, post=None, hb=None, dry=False, say=print, feed: dict | None = None,
        s: dict | None = None) -> dict:
    now = int(now or time.time())
    get, post = get or http_get, post or http_post
    feed = feed or feed_cfg()
    s = s or notify.settings()
    path = os.path.join(out, STATE_NAME)
    try:
        with open(path, encoding="utf-8") as fh:
            prev = json.load(fh)
    except Exception:
        prev = {}
    hb = read_hb(now) if hb is None else hb
    hb_t = int(hb["t"]) if hb.get("present") and notify._f(hb.get("t")) else None
    f_ok, f_msgs = poll(feed["ntfy"], feed["topic"], get=get)
    f_t = feed_last(f_msgs)
    seen = max([t for t in (hb_t, f_t) if t] or [0]) or None
    d = dest(env, feed)
    if d["topic"] == feed["topic"]:
        back = f_msgs
    else:
        _ok, back = poll(d["base"], d["topic"], get=get)
    st, msgs = notify.silent_step(prev, seen, now, s, fetched=bool(f_ok or hb.get("present")), sent_today=sent_today(back, now))
    pre_sent = [int(m["time"]) for m in back if str(m.get("title") or "").startswith(PRE_MARK) and notify._f(m.get("time"))]
    st["pre"], pre = preopen_step(_d(prev.get("pre")), seen, now, s, fetched=bool(f_ok or hb.get("present")), sent=pre_sent,
                                  clock=feed_clock(f_msgs, now))
    k7_sent = [str(m.get("title") or "") for m in back if str(m.get("title") or "").startswith(K7_MARK) and notify._f(m.get("time"))
               and notify._et(m["time"]).date() == notify._et(now).date()]
    st["k7"], k7 = k7_step(_d(prev.get("k7")), seen, now, feed_clock(f_msgs, now), fetched=bool(f_ok or hb.get("present")), sent=k7_sent)
    msgs = list(msgs) + pre + k7
    sent = []
    bus = _bus(env) if not dry and post is http_post else None
    # the bus's own state / failure log: the runner's temp folder, never `out` (cloud-monitor commits dash/ to the PUBLIC dashboard
    # branch with git add -A; redteam 2026-11-21)
    bus_dir = (os.environ if env is None else env).get("RUNNER_TEMP") or out
    for m in msgs:
        # the K7 push stays on ntfy (night-k7cloud): both cloud-monitor (bus secrets) and pc-watch (none) run this script, each with
        # its own state; only an ntfy post is read back by the other, so a bus send would let the second job send it again
        if bus is not None and not str(m.get("key") or "").startswith("k7cloud:"):   # engine/alert_bus (LE_TG_* / LE_DISCORD_WEBHOOK)
            r = bus.deliver({"kind": "report", "key": "", "title": m["title"], "body": m["body"], "notify_type": "pc_silent",
                             "report": True, "dual": True}, cfg=_bus_cfg(bus, env), path=os.path.join(bus_dir, "alert_bus_sent.json"),
                            log_path=os.path.join(bus_dir, "alert_bus.jsonl"))
            if r.get("ok"):
                sent.append({"key": m["key"], "ok": True, "via": ",".join(r["receipts"])})
                continue
        if not d["topic"]:
            say("pc silent: no ntfy topic to send to")
            break
        if dry:
            say(f"[dry] {m['title']}: {m['body']}")
            continue
        h = {"Content-Type": "text/plain; charset=utf-8", "Title": m["title"], "Priority": m["priority"], "Tags": m["tags"]}
        code, _txt = post(f"{d['base']}/{d['topic']}", m["body"].encode("utf-8"), h)
        ok = 200 <= int(code or 0) < 300
        sent.append({"key": m["key"], "ok": ok})
        if not ok and m["key"].startswith("pc_silent:"):          # not sent: the next run tries again
            o = _d(st.get("out"))
            o["sent"] = max(0, int(o.get("sent") or 1) - 1)
            if not o["sent"]:
                o["first_t"] = None
    st.update(t=now, hb_t=hb_t, feed_t=f_t, feed_ok=bool(f_ok), to="private" if d["private"] else "status topic")
    if not dry:
        try:
            os.makedirs(out, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(st, fh, separators=(",", ":"))
        except OSError as e:
            say(f"pc silent: state not saved ({e.__class__.__name__})")
    age = (now - seen) // 60 if seen else None
    say(f"pc silent: last report {'never seen' if not seen else notify.since_text(seen, now) + f' ({age} min ago)'}"
        f" (heartbeat {'yes' if hb_t else 'no'}, status feed {'yes' if f_t else 'no'}); pushes {len(msgs)}"
        + (f" -> {'your private topic' if d['private'] else 'the public status topic (set the LE_NTFY_TOPIC secret for your private one)'}" if msgs else ""))
    return {"state": st, "msgs": msgs, "sent": sent, "dest_private": d["private"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cloud: push when the PC stopped reporting (ntfy, free).")
    ap.add_argument("--out", default="dash")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        run(a.out, dry=a.dry_run)
    except Exception as e:                    # never fails the cloud job
        print(f"pc silent: check failed ({e.__class__.__name__})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
