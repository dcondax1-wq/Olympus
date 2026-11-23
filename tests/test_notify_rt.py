"""Zero-setup alerts red team (2026-11-23). Offline: fake HTTP, temp homes; never the real ~/.olympus, never a real post.

  a. privacy: the auto topic is random (SystemRandom, >= 34 bits), never from the PC / user name; refused inside the repo; it
     never reaches last.json / the public status post (the card that shows it is the PC screen only)
  b. no storm: an update failure the server retries every hour = ONE alert a day (a different failure still goes); a bot-down
     key sent twice / across a restart = one; the digest holds at most 12 lines and posts once a day
  c. never blocks / never raises: send_critical returns at once without wait (a 60 s hung channel), garbage in = "bad" / "off"
  d. ALERTS_OFF = "off" (the call sites' old path); e. TEST_ALERT on the first run already tests the topic it just made
    python -X utf8 -m tests.test_notify_rt
"""
from __future__ import annotations

import io
import json
import math
import os
import re
import sys
import threading
import time
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import alert_bus as AB  # noqa: E402
from tests.test_alert_bus import Box  # noqa: E402

RES: list = []
ZCFG = lambda: {**AB.config(), "telegram": None, "discord": None}  # noqa: E731


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{str(detail)[:300]}]" if detail and not ok else ""))


def part_a(b):
    from tools import pc_report as PR
    n = len(set(PR.WORDS))
    bits = 3 * math.log2(n) + 4 * math.log2(10)
    ts = {PR.make_topic() for _ in range(300)}
    check("a1. auto topic: SystemRandom, >= 34 bits, 300 draws all different", bits >= 34 and len(ts) == 300
          and "SystemRandom" in open(os.path.join(ROOT, "tools", "pc_report.py"), encoding="utf-8").read(), (bits, len(ts)))
    import getpass
    import socket
    who = {getpass.getuser().lower(), socket.gethostname().lower()} - {""}
    check("a2. never the PC name or the user name", not any(w in t for t in ts for w in who if len(w) >= 3), who)
    try:
        PR.ensure_topic(env={"OLYMPUS_HOME": os.path.join(ROOT, "data", "x_rt_home")})
        inside = "made"
    except RuntimeError:
        inside = "refused"
    check("a3. a settings folder inside the repo is refused (the topic never lands in the repo)",
          inside == "refused" and not os.path.exists(os.path.join(ROOT, "data", "x_rt_home")), inside)
    src = open(os.path.join(ROOT, "tools", "pc_report.py"), encoding="utf-8").read()
    i_w, i_c = src.index('write_json(os.path.join(work, "last.json"), rec)'), src.index('rec["card"] = card(snap, cfg, rec)')
    check("a4. the card that shows the topic is made AFTER last.json is written (screen only, never saved / posted)", i_w < i_c, "")
    pub = [os.path.join(ROOT, "tools", "web_public", "status_feed.json")]
    topic = json.load(open(os.path.join(b.home, "ntfy.json")))["topic"]
    check("a5. the private topic is not the public status topic", all(topic not in open(p, encoding="utf-8").read() for p in pub if os.path.exists(p)))
    card = PR.card({"t": int(time.time()), "wp": {}}, PR.load_cfg(), {})
    nxt = [r for r in card if r[1] == "NEXT"]
    check("a6. an untested topic: the PC card's NEXT line says how to subscribe (an auto topic nobody reads is not a route)",
          nxt and "Subscribe" in nxt[-1][2], nxt)


def part_b(b):
    hits = []
    b.net.hook = None
    t0 = time.time()
    for i in range(12):                        # the server's hourly retry of the same failed update, all night
        AB.send_critical({"kind": "problem", "key": f"auto:update:failed:{int(t0) + i * 3600}", "title": "Update failed: fast-forward refused",
                          "body": "Still on abc1234.", "notify_type": "problems", "report": True}, cfg=ZCFG(), wait=True)
    n_ntfy = sum(1 for c in b.net.calls if c[0] == "ntfy")
    check("b1. the same update failure every hour for 12 hours = ONE phone alert", n_ntfy == 1, n_ntfy)
    AB.send_critical({"kind": "problem", "key": f"auto:update:rolled_back:{int(t0) + 99}", "title": "Update rolled back: crash loop",
                      "body": "x", "notify_type": "problems", "report": True}, cfg=ZCFG(), wait=True)
    check("b2. a different failure (rolled back) still goes at once", sum(1 for c in b.net.calls if c[0] == "ntfy") == 2)
    k = AB.day_key({"key": "cond:bot_down:777", "title": "x"})["key"]
    check("b3. other keys are never rewritten (bot down / readiness keep their own de-dup)", k == "cond:bot_down:777", k)
    for i in range(3):
        AB.send_critical({"kind": "problem", "key": "cond:bot_down:42", "title": "Bot stopped", "body": "START BOT.",
                          "notify_type": "problems"}, cfg=ZCFG(), wait=True)
    check("b4. the same bot-down key three times (a restart loop) = one", sum(1 for c in b.net.calls if c[0] == "ntfy") == 3)
    for i in range(40):
        AB.digest_add(f"Update applied {i}", "a -> b", key=f"k{i}")
    d = json.load(open(AB.DIGEST_PATH))
    check("b5. the digest keeps at most 12 lines", len(d["items"]) == 12, len(d["items"]))
    import datetime as dt
    from zoneinfo import ZoneInfo
    day = dt.datetime.now(ZoneInfo("America/New_York")).replace(hour=16, minute=30)
    r1 = AB.digest_flush(now=day.timestamp(), cfg=ZCFG())
    r2 = AB.digest_flush(now=day.timestamp() + 900, cfg=ZCFG())
    check("b6. one digest a day, then 'done today'", r1 == "sent" and r2 == "done today", (r1, r2))
    early = AB.digest_flush(now=day.replace(hour=9).timestamp() + 86400, cfg=ZCFG())
    check("b7. never before 16:20 ET", early == "not yet", early)


def part_c(b):
    gate = threading.Event()

    class Slow:
        def __call__(self, *a, **k):
            gate.wait(60)
            return 200, "{}"
    AB._HTTP = Slow()
    t = time.time()
    r = AB.send_critical({"kind": "problem", "key": "cond:x:1", "title": "x", "body": "y", "notify_type": "problems"}, cfg=ZCFG())
    took = time.time() - t
    gate.set()
    check("c1. a channel that hangs 60 s: send_critical (no wait) returns at once, queued", took < 0.5 and r == "queued", (took, r))
    for bad in (None, "x", 7, [], {"key": None}, {"kind": object()}):
        try:
            r = AB.send_critical(bad, cfg=ZCFG())
            ok = r in ("bad", "off", "queued", "dup", "sent")
        except Exception as e:  # noqa: BLE001
            ok = e
        check(f"c2. garbage {type(bad).__name__}: never raises", ok is True, ok)


def part_d(b):
    off = os.path.join(AB.home(), AB.OFF_NAME)
    os.makedirs(os.path.dirname(off), exist_ok=True)
    open(off, "w").write("off")
    try:
        r = AB.send_critical({"kind": "problem", "key": "cond:y:1", "title": "x", "body": "y", "notify_type": "problems"})
    finally:
        os.remove(off)
    check("d1. ALERTS_OFF: send_critical says 'off' and sends nothing (the call sites' old path, exactly)",
          r == "off" and not any(c for c in b.net.calls), (r, b.net.calls))
    os.environ["LE_ALERT_BUS"] = "0"
    try:
        r = AB.send_critical({"kind": "problem", "key": "cond:y:2", "title": "x", "body": "y", "notify_type": "problems"})
    finally:
        os.environ.pop("LE_ALERT_BUS")
    check("d2. LE_ALERT_BUS=0: 'off' too", r == "off", r)


def part_e(b):
    from tools import alerts_setup as AS
    os.remove(os.path.join(b.home, "ntfy.json"))          # a fresh PC: no topic yet
    out = io.StringIO()
    with redirect_stdout(out):
        AS.test(say=print, show_topic=True)
    txt = out.getvalue()
    ntfy = [ln for ln in txt.splitlines() if "ntfy" in ln and ("OK" in ln or "FAIL" in ln)]
    check("e1. first TEST_ALERT: the topic it just made is tested at once (no 'run again in 15 minutes')",
          ntfy and ntfy[0].strip().startswith("OK") and "subscribes" in ntfy[0], ntfy)
    from tools import pc_report as PR
    c = PR.load_cfg()
    check("e2. ... and the report's card stops asking to subscribe", (c.get("tested") or {}).get("topic") == c["topic"], c.get("tested"))


def part_f(b):
    from engine import alerts_plus as AP
    from engine import notify as N
    from engine import push as P
    calls = []
    real = N.instant_problem
    N.instant_problem = lambda p, **k: (calls.append(p["key"]), "sent")[1]
    try:
        st, now = {}, 1795300000
        for i in range(7):                                  # a feed that flaps: on, (10 min) on, off, on again the same day
            active = [] if i == 3 else [{"id": "feed_stale:2026-11-23", "kind": "feed_stale", "title": "FEED STALE", "body": "x"}]
            st, out = AP.crit_step(st, active, {}, now + i * 600)
            for p in out:
                P._crit_ntfy(p)
        keys = set(calls)
        check("f1. a flapping critical condition (6 repeats + a resolve, then back): ntfy is asked with ONE key, the first notice",
              keys == {"crit:feed_stale:2026-11-23"}, sorted(keys))
        check("f2. 'Resolved' (silent) never goes to ntfy", all("clear" not in k for k in calls), calls)
        calls.clear()
        P._crit_ntfy({"key": "guard:clock:2026-11-23", "tag": "le-guard", "title": "Clock drift", "body": "x"})
        check("f3. a guard push keeps its own (per-day) key", calls == ["crit:guard:clock:2026-11-23"], calls)
    finally:
        N.instant_problem = real


def main() -> int:
    for f in (part_a, part_b, part_c, part_d, part_e, part_f):
        b = Box(tg=False, dc=False)
        saved = AB.DIGEST_PATH
        AB.DIGEST_PATH = os.path.join(b.dir, "data", "alert_digest.json")
        try:
            f(b)
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f"{f.__name__} raised {e.__class__.__name__}: {e}", False)
        finally:
            AB.drain(5)
            AB.DIGEST_PATH = saved
            b.close()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
