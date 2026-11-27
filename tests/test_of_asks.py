"""One order-flow ask a night, shared by every cloud session (night-of-asks 2026-11-27). On 2026-11-27 six helper sessions each
posted a 400-day "of" ask within 2 minutes: tools/data_pull.latest_of kept "tonight's ask" in a per-container file. Now the
ntfy topic is the shared record (data_pull.shared_of_ask) and the PC ignores a cloud "of" ask for datafeed.OF_DEDUP_S after it
answered one (datafeed.of_answered_recently). Offline: the local fake ntfy of tests/test_datafeed.

  python -X utf8 -m tests.test_of_asks        # ~2 s
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import os
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES = []
ET = ZoneInfo("America/New_York")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(info)[:400]}"))


def main():
    from engine import datafeed as DF
    from tests.test_datafeed import FakeNtfy
    from tools import data_pull as DPL
    fake = FakeNtfy()
    td = tempfile.mkdtemp(prefix="of_asks_")
    env_keep = {k: os.environ.get(k) for k in ("LE_DATAFEED_BASE", "LE_DATAFEED_TOPIC")}
    keep_clock = DPL._clock
    night = dt.datetime(2026, 11, 27, 0, 5, tzinfo=ET).timestamp()            # Friday 00:05 ET: the PC answers (outside 01:50-16:00)
    T = {"t": night}
    fake.clock = lambda: T["t"]
    DPL._clock = lambda: T["t"]
    n_topic = [0]

    def topic():
        n_topic[0] += 1
        tp = f"asks{n_topic[0]}"
        os.environ.update(LE_DATAFEED_BASE=fake.base, LE_DATAFEED_TOPIC=tp)
        return tp

    def ask(tp, rid, t, until=None):
        return fake.post(tp, {"v": 1, "kind": DF.REQ_KIND, "id": rid, "since": "2025-10-28", "t": int(t), "want": ["of"], "what": "of",
                              **({"until": until} if until else {})}, t=t)

    def answer(tp, rid, t, also=None):
        return fake.post(tp, {"v": 1, "kind": DF.ANS_KIND, "req": rid, "days": 0, "what": "of", "made_t": int(t), "page": 1, "more": False,
                              **({"also": also} if also else {})}, t=t)

    def pull():
        """A FRESH container (its own empty folder, no mark file): -> (rc, output, asks posted)."""
        out = tempfile.mkdtemp(dir=td)
        before = fake.n("POST")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = DPL.latest_of(argparse.Namespace(out=out, since=None, wait=0), sleep=lambda *_: None)
        return rc, buf.getvalue(), fake.n("POST") - before

    try:
        # --- the cloud side
        tp = topic()
        rc, out, posted = pull()
        check("empty topic: one ask is posted", posted == 1 and "Asked the PC" in out, (posted, out))
        rc, out, posted = pull()
        check("a 2nd fresh session a minute later: no new ask, it adopts the open one", posted == 0 and "already out" in out, (posted, out))
        for _ in range(4):
            pull()
        n_asks = sum(1 for m in fake.msgs[tp] if DF.body_of(m).get("kind") == DF.REQ_KIND)
        check("six sessions in a row -> ONE ask on the topic (was six on 2026-11-27)", n_asks == 1, n_asks)

        tp = topic()
        ask(tp, "aaaaaa01", night - 3 * 3600)
        answer(tp, "aaaaaa01", night - 3 * 3600 + 300)
        rc, out, posted = pull()
        check("an ask answered 3 h ago (another session's): no new ask, its pages are collected", posted == 0 and "aaaaaa01" in out
              and "already answered" in out, (posted, out))

        tp = topic()
        ask(tp, "bbbbbb01", night - 9 * 3600)
        answer(tp, "bbbbbb01", night - 9 * 3600 + 300)
        ask(tp, "bbbbbb02", night - 9 * 3600 + 60)
        rc, out, posted = pull()
        check("duplicates answered together (also): the answered one is reused, no new ask", posted == 0 and "bbbbbb01" in out, (posted, out))

        tp = topic()
        ask(tp, "cccccc01", night - 7 * 3600)                            # never answered and too old for the PC (6 h)
        rc, out, posted = pull()
        check("an unanswered ask older than the PC takes (6 h): a new ask is posted", posted == 1, (posted, out))

        tp = topic()
        ask(tp, "dddddd01", night - 21 * 3600)
        answer(tp, "dddddd01", night - 21 * 3600 + 300)
        rc, out, posted = pull()
        check("last night's answer (21 h ago, > 20 h): tonight asks again (no night skipped)", posted == 1, (posted, out))

        tp = topic()
        fake.post(tp, {"v": 1, "kind": DF.ANS_KIND, "req": "push0a1b2c3d4e", "days": 0, "what": "of", "page": 1}, t=night - 3600)
        rc, out, posted = pull()
        check("only the owner's PUSH on the topic: the nightly ask still goes out", posted == 1, (posted, out))

        keep_poll = DF.poll
        DF.poll = lambda *a, **k: (False, [])
        try:
            rc, out, posted = pull()
        finally:
            DF.poll = keep_poll
        check("topic unreadable: no ask (it could double one), says to run again", posted == 0 and rc == 2 and "no ask was sent" in out, (rc, posted, out))

        # --- the PC side
        w = os.path.join(td, "pcwork")
        os.makedirs(w)
        tp = topic()
        env = {"LE_DATAFEED_BASE": fake.base, "LE_DATAFEED_TOPIC": tp}
        for k in range(6):
            ask(tp, f"eeeeee0{k}", night - 600 + 60 * k)
        spawned = []
        r = DF.maybe_answer(now=int(night), env=env, say=lambda *a: None, work=w, spawn_fn=lambda work: spawned.append(work) or os.getpid())
        check("PC: six asks at once -> one child, the NEWEST ask, the 5 others ride along as 'also'",
              r and r["req"]["id"] == "eeeeee05" and sorted(r["req"]["also"]) == [f"eeeeee0{k}" for k in range(5)] and len(spawned) == 1, r)

        def pc_with(sent_t, req, new_id):
            w2 = tempfile.mkdtemp(dir=td)
            DF._write_json(os.path.join(w2, "state.json"), {"sent": [{"t": int(sent_t), "day": dt.datetime.fromtimestamp(sent_t, ET).date().isoformat(),
                                                                       "req": req, "page": 1, "days": 9}], "last_sent_t": int(sent_t)})
            tp2 = topic()
            ask(tp2, new_id, night - 60)
            sp = []
            DF.maybe_answer(now=int(night), env={"LE_DATAFEED_BASE": fake.base, "LE_DATAFEED_TOPIC": tp2}, say=lambda *a: None, work=w2,
                            spawn_fn=lambda work: sp.append(work) or os.getpid())
            return len(sp)
        check("PC: answered a cloud ask at 23:30 ET (the day before): a duplicate at 00:04 is NOT answered",
              pc_with(night - 35 * 60, "ffffff01", "ffffff02") == 0)
        check("PC: the owner's push at 17:30 ET does not block the nightly cloud ask", pc_with(night - 6.6 * 3600, "push0a1b2c3d4e", "ffffff03") == 1)
        check("PC: last night's answer 21 h ago does not block tonight's ask", pc_with(night - 21 * 3600, "ffffff04", "ffffff05") == 1)
        check("PC: of_answered_recently never raises on junk state", DF.of_answered_recently({"sent": [{"page": 1, "t": "x"}, None]}, night) is False)

        # --- the v4 hook (LEAD_WIRES_v4 #1): `--of` alone runs the battery, then v4
        calls = []
        keep = DPL.run_battery, DPL.run_v4, DPL.latest_of
        DPL.run_battery = lambda out_dir=None: calls.append("battery")
        DPL.run_v4 = lambda out_dir=None: calls.append("v4")
        DPL.latest_of = lambda a, sleep=None: 0
        try:
            DPL.main(["--of", "--out", td])
            DPL.main(["--of", "--no-battery", "--out", td])
        finally:
            DPL.run_battery, DPL.run_v4, DPL.latest_of = keep
        check("`data_pull --of`: battery, then v4; --no-battery skips both", calls == ["battery", "v4"], calls)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            DPL.run_v4(os.path.join(td, "nothing_here"))
        check("run_v4 on a folder without days: one plain line, never fails the pull", "order flow v4:" in buf.getvalue(), buf.getvalue())
    finally:
        DPL._clock = keep_clock
        for k, v in env_keep.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        fake.srv.shutdown()
        shutil.rmtree(td, ignore_errors=True)
    print(f"{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
