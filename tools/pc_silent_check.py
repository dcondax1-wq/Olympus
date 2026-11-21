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
    sent = []
    bus = _bus(env) if not dry and post is http_post else None
    for m in msgs:
        if bus is not None:                       # engine/alert_bus (repo secrets LE_TG_TOKEN + LE_TG_CHAT / LE_DISCORD_WEBHOOK)
            r = bus.deliver({"kind": "report", "key": "", "title": m["title"], "body": m["body"], "notify_type": "pc_silent",
                             "report": True, "dual": True}, cfg=_bus_cfg(bus, env), path=os.path.join(out, "alert_bus_sent.json"),
                            log_path=os.path.join(out, "alert_bus.jsonl"))
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
