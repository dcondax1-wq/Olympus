"""The cloud warns when the PC is off and an MFFU 7-day clock needs a trade (night-k7cloud 2026-11-23; tools/pc_silent_check.k7_step,
the pc-watch job). Fake ntfy topics, no network, nothing armed.

    python -X utf8 -m tests.test_k7cloud        (~2 s)

a. keep-alive act day, PC's last post 3 h old, 10:00 ET: ONE push "PC looks off: <account> must trade by <date>" naming the hand trade
   before 16:05 ET; 30 min later nothing more (state), nor with the state lost (read back from the topic)
b. only 1 h stale: nothing (the PC-silent push covers the first 2 h)
c. less than 24 h before an account's MFFU last day: warns at any hour (Mon 17:30 ET for a Tue last day); urgent ON the last day
d. the PC off for days (no ext post left in ntfy's 12 h): the kept rows still warn, rebuilt for today
e. per account per day: two accounts due = two pushes; the next day can warn again; a 30-day (Lucid) row never
f. not an act day and far from the deadline: nothing; a feed that did not answer: nothing (no false alarm)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import clock7  # noqa: E402
from tools import pc_silent_check as P  # noqa: E402

ET = P.notify.ET
RES = []
FEED = {"ntfy": "https://ntfy.example", "topic": "status-topic"}
ENV = {"LE_NTFY_TOPIC": "private-topic"}


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:500]) if info and not ok else ''}")
    RES.append(bool(ok))


def ts(y, m, d, hh, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


class Ntfy:
    def __init__(self):
        self.topics = {"status-topic": [], "private-topic": []}
        self.up = True

    def core(self, t):
        self.topics["status-topic"].append({"event": "message", "time": t, "message": json.dumps({"kind": "le-live", "t": t})})

    def ext(self, t, rows):
        self.topics["status-topic"].append({"event": "message", "time": t,
                                            "message": json.dumps({"kind": "le-live-ext", "x": {"k7": {"a": rows}}})})

    def get(self, url, *a, **k):
        if not self.up:
            return 0, "down"
        topic = url.split("/")[3]
        return 200, "\n".join(json.dumps(m) for m in self.topics.get(topic, []))

    def post_fn(self, clock):
        def post(url, body, headers, *a, **k):
            topic = url.rstrip("/").split("/")[-1]
            self.topics.setdefault(topic, []).append({"event": "message", "time": clock[0], "title": headers.get("Title"),
                                                      "message": body.decode("utf-8"), "priority": headers.get("Priority")})
            return 200, "ok"
        return post

    def k7(self, topic="private-topic"):
        return [m for m in self.topics[topic] if str(m.get("title") or "").startswith(P.K7_MARK)]


def rows(now, accts):
    """clock7 rows as the PC's ext post carries them: [(id, name, last fill)]."""
    return [clock7.row(i, nm, lf, None, now, True) for i, nm, lf in accts]


def run(n, out, now):
    clock = [now]
    return P.run(out, now=now, env=ENV, get=n.get, post=n.post_fn(clock), hb={"present": False}, say=lambda *a: None, feed=FEED)


def main():
    tmp = tempfile.mkdtemp(prefix="le_k7cloud_")
    try:
        # a. Zlarior 50K last fill Tue 11-17: act day Mon 11-23 (MFFU's last day Tue 11-24). PC last seen Mon 07:00, now 10:00.
        n, out = Ntfy(), os.path.join(tmp, "a")
        t_post = ts(2026, 11, 23, 7)
        n.core(t_post)
        n.ext(t_post, rows(t_post, [("mffu50k_eval", "Zlarior 50K", "2026-11-17"), ("atlas", "ATLAS 25K", "2026-11-20")]))
        r = run(n, out, ts(2026, 11, 23, 10))
        k = n.k7()
        check("a1. act day, PC silent 3 h: ONE push 'PC looks off: Zlarior 50K must trade by Tue 11-24' (ATLAS, act Wed 11-25: none)",
              len(k) == 1 and k[0]["title"] == "PC looks off: Zlarior 50K must trade by Tue 11-24"
              and "turn the pc on" in k[0]["message"].lower() and "place 1 MNQ by hand before 16:05 ET" in k[0]["message"]
              and "last report" in k[0]["message"], [m.get("title") for m in n.topics["private-topic"]])
        run(n, out, ts(2026, 11, 23, 10, 30))
        check("a2. 30 min later: nothing more (de-duplicated per account per day)", len(n.k7()) == 1, [m["title"] for m in n.k7()])
        shutil.rmtree(out, ignore_errors=True)
        run(n, out, ts(2026, 11, 23, 11))
        check("a3. state lost (a new cache): still nothing (today's push read back from the topic)", len(n.k7()) == 1)

        # a4. the OTHER cloud job (cloud-monitor: its own state, Telegram secrets) on the same day: reads the ntfy push back, sends none,
        # and even with a bus it would not use it for the K7 push
        out_b = os.path.join(tmp, "a_other")
        run(n, out_b, ts(2026, 11, 23, 10, 15))
        check("a4. the 2nd cloud job (own state) the same day: nothing (ONE alert across both jobs)", len(n.k7()) == 1)
        src = open(os.path.join(ROOT, "tools", "pc_silent_check.py"), encoding="utf-8").read()
        check("a5. the K7 push never goes through the Telegram / Discord bus (only ntfy is read back by the other job)",
              'not str(m.get("key") or "").startswith("k7cloud:")' in src)

        # b. only 1 h stale
        n2, out2 = Ntfy(), os.path.join(tmp, "b")
        t_post = ts(2026, 11, 23, 9)
        n2.core(t_post)
        n2.ext(t_post, rows(t_post, [("mffu50k_eval", "Zlarior 50K", "2026-11-17")]))
        run(n2, out2, ts(2026, 11, 23, 10))
        check("b. last post 1 h old: no K7 push (the PC-silent push covers the first 2 h)", not n2.k7())

        # c. < 24 h before the last day, outside trading hours; and on the day itself = urgent
        n3, out3 = Ntfy(), os.path.join(tmp, "c")
        t_post = ts(2026, 11, 23, 12)
        n3.core(t_post)
        n3.ext(t_post, rows(t_post, [("rapid", "Rapid EOD 25K", "2026-11-17")]))
        run(n3, out3, ts(2026, 11, 23, 17, 30))
        k = n3.k7()
        check("c1. Mon 17:30 ET (after hours), Rapid's last day Tue 11-24 16:05 is < 24 h away: ONE push, high",
              len(k) == 1 and "Rapid EOD 25K must trade by Tue 11-24" in k[0]["title"] and k[0]["priority"] == "high", k)
        run(n3, out3, ts(2026, 11, 24, 9))
        k = n3.k7()
        check("c2. Tue 09:00 (its last day): a new day = ONE more push, urgent", len(k) == 2 and k[1]["priority"] == "urgent", k)

        # d. the PC off for days: no ext post left in ntfy (12 h); the kept rows still warn
        n4, out4 = Ntfy(), os.path.join(tmp, "d")
        t_post = ts(2026, 11, 20, 15)
        n4.core(t_post)
        n4.ext(t_post, rows(t_post, [("rapid2", "Rapid EOD 50K", "2026-11-18")]))   # act Tue 11-24, last day Wed 11-25
        run(n4, out4, ts(2026, 11, 20, 15, 30))
        n4.topics["status-topic"] = []                                                    # ntfy forgot everything after 12 h
        run(n4, out4, ts(2026, 11, 24, 10))
        k = n4.k7()
        check("d. PC off since Fri, no post left on the topic: Tue 10:00 (its act day) ONE push from the kept clock rows",
              len(k) == 1 and "Rapid EOD 50K must trade by Wed 11-25" in k[0]["title"] and "never seen" in k[0]["message"], k)

        # e. two accounts due the same day; Lucid never
        n5, out5 = Ntfy(), os.path.join(tmp, "e")
        t_post = ts(2026, 11, 23, 6)
        n5.core(t_post)
        n5.ext(t_post, rows(t_post, [("mffu50k_eval", "Zlarior 50K", "2026-11-17"), ("atlas", "ATLAS 25K", "2026-11-17"),
                                    ("lucid_1", "Lucid 50K", "2026-10-25")]))
        run(n5, out5, ts(2026, 11, 23, 10))
        titles = sorted(m["title"] for m in n5.k7())
        check("e. two accounts due: two pushes, one each; a Lucid (30-day) row never gets the MFFU warning",
              titles == ["PC looks off: ATLAS 25K must trade by Tue 11-24", "PC looks off: Zlarior 50K must trade by Tue 11-24"], titles)

        # f. nothing to say; and the feed down
        n6, out6 = Ntfy(), os.path.join(tmp, "f")
        t_post = ts(2026, 11, 23, 6)
        n6.core(t_post)
        n6.ext(t_post, rows(t_post, [("mffu50k_eval", "Zlarior 50K", "2026-11-20")]))     # act Wed 11-25, last day Fri 11-27
        run(n6, out6, ts(2026, 11, 23, 10))
        check("f1. not its act day and the last day 4 days away: nothing", not n6.k7())
        n7, out7 = Ntfy(), os.path.join(tmp, "g")
        n7.up = False
        run(n7, out7, ts(2026, 11, 23, 10))
        check("f2. ntfy did not answer: nothing (no false alarm)", not n7.k7())
        st, msgs = P.k7_step({}, None, ts(2026, 11, 23, 10), "not a list", fetched=True)
        check("f3. k7_step never raises on junk", msgs == [] and isinstance(st, dict))
        check("g. hand-trade time: 16:05 on a full day, 12:55 on Fri 11-27 (13:00 half day halt 13:15? -> its halt - 5 min)",
              P.hand_by(dt.date(2026, 11, 23)) == 16 * 60 + 5 and P.hand_by(dt.date(2026, 11, 27)) == 795 - 5,
              (P.hand_by(dt.date(2026, 11, 23)), P.hand_by(dt.date(2026, 11, 27))))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = sum(RES)
    print(f"\nk7 cloud: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
