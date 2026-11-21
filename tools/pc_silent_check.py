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
        return list(_d(k).get("a") or [])
    except Exception:
        return []


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
    msgs = list(msgs) + pre
    sent = []
    bus = _bus(env) if not dry and post is http_post else None
    # the bus's own state / failure log: the runner's temp folder, never `out` (cloud-monitor commits dash/ to the PUBLIC dashboard
    # branch with git add -A; redteam 2026-11-21)
    bus_dir = (os.environ if env is None else env).get("RUNNER_TEMP") or out
    for m in msgs:
        if bus is not None:                       # engine/alert_bus (repo secrets LE_TG_TOKEN + LE_TG_CHAT / LE_DISCORD_WEBHOOK)
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
