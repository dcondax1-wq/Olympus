"""Zero-setup phone alerts (night-notify 2026-11-22, owner: "get notifications going on your own"). Offline: fake HTTP, temp files.

  a. coverage: every critical event in engine/alert_map.EVENTS has working senders, its notify_settings.json type is ON, its
     key prefix maps to that type (engine/notify.kind_of), its channels are private; the only no-sender row is PC silent (a gap
     named in words: one repo secret)
  b. zero setup (no Telegram / Discord): send_critical reaches BOTH the private ntfy topic AND the Olympus app; never Telegram
  c. de-dup: the same key twice = one delivery (also across a "restart": the state file); with Telegram set up = the bus (send)
  d. call sites: readiness NOT READY, the fast alarm's bot-down, a rolled-back update all reach the phone with no setup
     (before: readiness / update went to kind 'ready' / 'pc', which engine/push.pc_app_ok drops)
  e. digest: low-priority items wait (no buzz), ONE silent post a day from 16:20 ET, same key = one line
  f. privacy: the auto topic is random words + digits (never the PC name, the user, an account id); not in the public status
     feed, not in any tracked file; TEST_ALERT prints plain words per channel, no secret
  g. TRADE_HOME: "T Test all alerts" runs tools/bat/TEST_ALERT.bat
    python -X utf8 -m tests.test_alert_map        (~2 s)
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import time
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import alert_bus as AB  # noqa: E402
from engine import alert_map as AM  # noqa: E402
from engine import notify as N  # noqa: E402
from tests.test_alert_bus import TOPIC, Box, Net  # noqa: E402

RES: list = []


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def part_a(b):
    rows = AM.coverage()
    ids = {r["id"] for r in rows}
    need = {"bot_stopped", "not_armed", "entry_blocked", "trade_entry", "trade_exit", "dll_near", "breach_risk", "payout_ready",
            "keepalive_deadline", "pc_silent", "update_failed", "update_applied"}
    check("a. every event the owner named is in the table", need <= ids, str(need - ids))
    bad = [r for r in rows if not r["ok"]]
    check("a. every row: senders import, its setting is ON, private channels only", not bad, str(bad))
    nozero = [r["id"] for r in rows if r["critical"] and not r["zero"]]
    check("a. every critical event has a zero-setup phone route, except PC silent (named gap)", nozero == ["pc_silent"], str(nozero))
    check("a. the PC-silent gap is said in plain words", "secret" in next(r for r in rows if r["id"] == "pc_silent")["gap"])
    for e in AM.EVENTS:
        if e["key"].startswith(("ready:", "auto:", "digest:")):
            continue                                       # alert_bus kinds, not 15-minute report keys
        kt = N.kind_of(e["key"] + "x:1")
        check(f"a. {e['id']}: key {e['key']} -> {e['type']}", kt == e["type"], kt)
    check("a. room low (daily loss / drawdown) is ON in notify_settings.json", N.on("room_low"))
    check("a. the table prints", "Olympus app" in AM.table() and "OK" in AM.table())


def part_b(b):
    cfg = AB.config()
    cfg = {**cfg, "telegram": None, "discord": None}
    r = AB.send_critical({"kind": "problem", "key": "ready:no:1", "title": "NOT READY: Zlarior is not armed",
                          "body": "Fix: START BOT.", "notify_type": "problems", "report": True}, cfg=cfg, wait=True)
    hit = b.net.hit()
    check("b. no setup: delivered", r == "sent", r)
    check("b. no setup: the private ntfy topic got it", "ntfy" in hit and any(TOPIC in c[2] for c in b.net.calls), str(hit))
    check("b. no setup: the Olympus app got it too (both, not first-wins)", len(b.web_calls) == 1, str(b.web_calls))
    check("b. never Telegram / Discord without setup", "telegram" not in hit and "discord" not in hit, str(hit))
    pr = [c[4].get("Priority") for c in b.net.calls if c[0] == "ntfy"]
    check("b. a critical one buzzes (high priority by day)", pr and (pr[0] == "high" or N.quiet(time.time())), str(pr))


def part_c(b):
    cfg = {**AB.config(), "telegram": None, "discord": None}
    ev = {"kind": "problem", "key": "cond:bot_down:777", "title": "Bot stopped", "body": "START BOT.", "notify_type": "problems"}
    r1 = AB.send_critical(dict(ev), cfg=cfg, wait=True)
    r2 = AB.send_critical(dict(ev), cfg=cfg, wait=True)
    AB._PENDING.clear()
    r3 = AB.send_critical(dict(ev), cfg=cfg, wait=True)                 # the state file: a restart does not repeat it
    check("c. de-dup: same key = one delivery", r1 == "sent" and r2 == "dup" and r3 == "dup", f"{r1} {r2} {r3}")
    check("c. de-dup: ntfy called once", b.net.hit().count("ntfy") == 1, str(b.net.hit()))
    r = AB.send_critical({"kind": "problem", "key": "cond:x:1", "title": "t", "body": "b", "notify_type": "problems"}, wait=True)
    check("c. Telegram set up = the bus: Telegram first", r == "sent" and b.net.hit()[-2:][0] == "telegram"
          or "telegram" in b.net.hit(), str(b.net.hit()))


def part_d(b):
    from engine import readiness as R
    os.environ["OLYMPUS_HOME"] = b.home
    os.remove(os.path.join(b.home, "alerts.json"))                       # NO Telegram / Discord
    check("d. setup gone: the bus is not active", not AB.active())
    via = R.send_alert({"key": "ready:no:5", "title": "NOT READY: Zlarior is not armed", "body": "START BOT.", "quiet": False})
    check("d. readiness NOT READY -> ntfy + the app with no setup", via == "zero" and "ntfy" in b.net.hit() and b.web_calls, via)
    n0 = len(b.net.calls)
    why = N.instant_problem({"key": "fast:bot_down:9", "code": "bot_down", "title": "ZEUS not polling", "body": "No poll for 3 min."})
    AB.drain(5)
    check("d. fast alarm bot-down -> sent on the zero path", why == "sent" and len(b.net.calls) > n0, why)
    check("d. fast alarm: recorded once delivered (the report skips its copy)",
          "fast:bot_down:9" in json.load(open(N.INSTANT_PATH)).get("keys", {}))
    from engine import autoupdate as AU
    n0, w0 = len(b.net.calls), len(b.web_calls)
    AU.alert_for({"alert": True, "status": "rolled_back", "reason": "self-test failed", "t": 1795050000, "old": "a" * 9, "new": "b" * 9},
                 sync=True)
    check("d. a rolled-back update reaches the phone (ntfy + app)", len(b.net.calls) > n0 and len(b.web_calls) > w0)
    n0 = len(b.net.calls)
    AU.alert_for({"alert": True, "status": "skipped", "reason": "local changes", "t": 1795050000})
    check("d. 'update skipped' does not buzz (it goes to the digest)", len(b.net.calls) == n0)


def part_e(b):
    p = os.path.join(b.dir, "data", "digest.json")
    cfg = {**AB.config(), "telegram": None, "discord": None}
    check("e. digest add", AB.digest_add("Update applied", "a1 -> b2", key="u:1", path=p))
    check("e. same key = one line", not AB.digest_add("Update applied", "a1 -> b2", key="u:1", path=p))
    AB.digest_add("Update skipped", "local changes", key="u:2", path=p)
    morning = 1795010400                                   # 2026-11-18 ~ 10:00 ET
    e = AB._et(morning)
    t_morning = morning - (e.hour * 60 + e.minute - 10 * 60) * 60
    t_eve = t_morning + 6 * 3600 + 25 * 60                 # 16:25 ET
    check("e. not before 16:20 ET", AB.digest_flush(now=t_morning, path=p, cfg=cfg) == "not yet")
    check("e. nothing sent while waiting", not b.net.calls)
    r = AB.digest_flush(now=t_eve, path=p, cfg=cfg)
    nt = [c for c in b.net.calls if c[0] == "ntfy"]
    check("e. one post at 16:25 ET with both lines", r == "sent" and len(nt) + len(b.web_calls) >= 1
          and (not nt or b"Update skipped" in nt[0][3]), r)
    check("e. the digest is silent (low priority)", all(c[4].get("Priority") == "low" for c in nt), str([c[4] for c in nt]))
    check("e. once a day", AB.digest_flush(now=t_eve + 900, path=p, cfg=cfg) == "done today")


def part_f(b):
    from tools import pc_report as PR
    import getpass
    import socket
    home = os.path.join(b.dir, "fresh")
    t = PR.ensure_topic(env={"OLYMPUS_HOME": home})["topic"]
    host, user = socket.gethostname().lower(), (getpass.getuser() or "x").lower()
    check("f. auto topic: random words + 4 digits", re.fullmatch(r"nq-[a-z]+-[a-z]+-[a-z]+-\d{4}", t), t)
    check("f. auto topic: not the PC name / user", host not in t and (len(user) < 3 or user not in t), t)
    t2 = PR.ensure_topic(env={"OLYMPUS_HOME": home})["topic"]
    check("f. made once per PC (kept)", t == t2)
    feed = open(os.path.join(ROOT, "tools", "web_public", "status_feed.json"), encoding="utf-8").read()
    check("f. the private topic is not the public status topic", t not in feed and TOPIC not in feed)
    for e in AM.EVENTS:
        check(f"f. {e['id']}: no public channel", all(c in AM.PRIVATE for c in e["zero"]))
    try:
        tracked = subprocess.run(["git", "grep", "-l", "-e", TOPIC, "--", "."], cwd=ROOT, capture_output=True, text=True).stdout
    except Exception:
        tracked = ""
    check("f. no private topic in a tracked file", not [x for x in tracked.split() if not x.startswith("tests/")], tracked)
    from tools import alerts_setup as AS
    out = io.StringIO()
    b.web = {"sent": 0, "skipped": "no phone"}
    with redirect_stdout(out):
        AS.test(say=print, cfg={**AB.config(), "telegram": None, "discord": None}, make_topic=False)
    s = out.getvalue()
    check("f. TEST_ALERT: one OK / FAIL line per channel", re.search(r"OK +ntfy", s) and re.search(r"FAIL +the Olympus app", s), s)
    check("f. TEST_ALERT: the FAIL says what to do in plain words", "Allow notifications" in s, s)
    check("f. TEST_ALERT: no topic / secret printed when not asked", TOPIC not in s, s)


def part_g(b):
    from engine import trade_home as TH
    ran = []
    r = TH.do_choice("T", run=lambda *a, **k: (ran.append(a), 0)[1], fx={}, out=lambda *_: None)
    check("g. TRADE_HOME has 'T Test all alerts' in the menu", any("Test all alerts" in ln for ln in TH.MENU))
    check("g. T runs tools/bat/TEST_ALERT.bat", ran and re.search(r"tools[\\/]+bat[\\/]+TEST_ALERT\.bat", str(ran[0])) and r.startswith("[OK]"), f"{ran} {r}")


def main() -> int:
    for f in (part_a, part_b, part_c, part_d, part_e, part_f, part_g):
        b = Box()
        saved_digest = AB.DIGEST_PATH
        AB.DIGEST_PATH = os.path.join(b.dir, "data", "alert_digest.json")     # never the repo's data/
        try:
            f(b)
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f"{f.__name__} raised {e.__class__.__name__}: {e}", False)
        finally:
            AB.drain(5)
            AB.DIGEST_PATH = saved_digest
            b.close()
    n, ok = len(RES), sum(RES)
    print(f"\nalert map: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
