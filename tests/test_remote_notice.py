"""The phone notice of a remote command reaches EVERY channel, and the cloud can see where it went (day-notifyfix 2026-11-23:
the owner's remote 'status' at 17:35 ET reached no phone, and nothing in the public feed said whether the PC read it).
Fake transports only (alert_bus._HTTP, push.app_send): no network.

    python -X utf8 -m tests.test_remote_notice          (~1 s)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import alert_bus as AB  # noqa: E402
from engine import push as P  # noqa: E402
from engine import remote_ctl as rc  # noqa: E402
from tools import pc_report  # noqa: E402

RES = []
TOPIC = "secret-words-4821"
TOKEN = "123456:FAKEfakeFAKEfakeFAKEfakeFAKEfake12"


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)) if info and not ok else ''}")
    RES.append(bool(ok))


class Fakes:
    """OLYMPUS_HOME in a temp folder (ntfy.json, optional alerts.json), every HTTP call recorded, the app 'accepted by 1 phone'."""

    def __init__(self, telegram=False, app_ok=True):
        self.tmp = tempfile.mkdtemp(prefix="le_rcn_")
        self.calls, self.app = [], []
        with open(os.path.join(self.tmp, "ntfy.json"), "w", encoding="utf-8") as fh:
            json.dump({"ntfy": "https://ntfy.example", "topic": TOPIC}, fh)
        if telegram:
            with open(os.path.join(self.tmp, "alerts.json"), "w", encoding="utf-8") as fh:
                json.dump({"telegram": {"token": TOKEN, "chat_id": 42}}, fh)
        self.app_ok = app_ok

    def __enter__(self):
        self.old = {k: os.environ.get(k) for k in ("OLYMPUS_HOME", "LE_ALERT_BUS", "LE_SELFTEST_CHILD")}
        os.environ["OLYMPUS_HOME"] = self.tmp
        os.environ.pop("LE_ALERT_BUS", None)
        os.environ.pop("LE_SELFTEST_CHILD", None)
        self.saved = (AB._HTTP, AB._SLEEP, AB.STATE_PATH, AB.LOG_PATH, P.app_send)
        AB.STATE_PATH, AB.LOG_PATH = os.path.join(self.tmp, "sent.json"), os.path.join(self.tmp, "bus.jsonl")
        AB._SLEEP = lambda s: None

        def http(method, url, body, headers, timeout):
            self.calls.append(url)
            if "api.telegram.org" in url:
                return 200, json.dumps({"ok": True, "result": {"message_id": 7}})
            return 200, json.dumps({"id": "n1"})
        AB._HTTP = http

        def app_send(payload, cfg=None, sender=None, path=None):
            self.app.append(payload)
            return {"sent": 1, "devices": 1} if self.app_ok else {"sent": 0, "skipped": "no phone"}
        P.app_send = app_send
        return self

    def __exit__(self, *a):
        AB._HTTP, AB._SLEEP, AB.STATE_PATH, AB.LOG_PATH, P.app_send = self.saved
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class Bot:
    state = {"running": True, "position": None}
    cfg = {}


def ntfy_hits(f):
    return [u for u in f.calls if TOPIC in u]


def tg_hits(f):
    return [u for u in f.calls if "api.telegram.org" in u]


def test_zero_setup_both_channels():
    with Fakes() as f:
        got = []
        r = rc.default_notify("Remote status: done", "running, flat", "remote:t1:done", on_done=got.append)
        AB.drain(10)
        check("zero setup: queued", r == "queued", r)
        check("zero setup: the private ntfy topic got it", len(ntfy_hits(f)) == 1, f.calls)
        check("zero setup: the Olympus app got it too (not only the first that answers)", len(f.app) == 1, f.app)
        check("zero setup: receipt lists both", got and set(got[0].get("receipts") or {}) == {"ntfy", "webpush"}, got)


def test_bus_active_every_channel():
    with Fakes(telegram=True) as f:
        rc.default_notify("Remote status: done", "running", "remote:t2:done")
        AB.drain(10)
        check("bus on: Telegram got it", len(tg_hits(f)) == 1, f.calls)
        check("bus on: ntfy got it as well", len(ntfy_hits(f)) == 1, f.calls)
        check("bus on: the Olympus app got it as well", len(f.app) == 1, f.app)


def test_type_switch_never_drops_it():
    check("kind 'remote' has no notify_type (an owner-asked answer is never switched off)", "remote" not in AB.NOTIFY_TYPE)


def test_no_phone_app_still_ntfy():
    with Fakes(app_ok=False) as f:
        got = []
        rc.default_notify("Remote status: done", "x", "remote:t3:done", on_done=got.append)
        AB.drain(10)
        line = rc.notice_line(got[0] if got else {})
        check("no app phone: ntfy still delivered", len(ntfy_hits(f)) == 1, f.calls)
        check("no app phone: the line says the app FAILED", "the Olympus app FAILED" in line and "ntfy ok" in line, line)
        check("no topic or token in the line", TOPIC not in line and "FAKE" not in line, line)


def test_switched_off_falls_back():
    with Fakes() as f:
        os.environ["LE_ALERT_BUS"] = "0"
        got, seen = [], []
        from engine import autoupdate
        old = autoupdate.notify
        autoupdate.notify = lambda t, b, key=None, sync=False: seen.append(key)
        try:
            r = rc.default_notify("Remote status: done", "x", "remote:t4:done", on_done=got.append)
        finally:
            autoupdate.notify = old
        check("bus off: the old path runs", r == "off" and seen == ["remote:t4:done"], (r, seen))
        check("bus off: on_done told (not ok)", got and got[0].get("ok") is False, got)


def test_controller_records_and_feed_shows():
    with Fakes() as f:
        done = os.path.join(f.tmp, "remote_done.json")
        ctl = rc.RemoteControl(Bot(), done_path=done, log=lambda *a: None, env={"LE_REMOTE": "1"})
        now = time.time()
        d = rc.load_done(done)
        d.setdefault("done", {})["status-1-claude"] = {"cmd": "status", "t": int(now), "status": "running", "msg": ""}
        rc.save_done(d, done)
        ctl._finish(d, "status-1-claude", "status", "done", "bot running, flat", now)
        AB.drain(10)
        last = rc.load_done(done).get("last") or {}
        n = last.get("notice") or {}
        check("controller: the notice receipt is recorded", n.get("ok") is True and "ntfy ok" in n.get("line", ""), last)
        hb = rc.hb_field(done, env={"LE_REMOTE": "1"})
        check("heartbeat: id + notice ride the remote block", hb.get("id") == "status-1-claude" and hb.get("notice"), hb)
        hb["seen"] = {"commit": "e455443165", "t": int(now)}
        blk = pc_report.rc_block(hb)
        txt = json.dumps(blk)
        check("feed rc block: id, status, notice line, seen commit",
              blk.get("id") == "status-1-claude" and blk.get("st") == "done" and blk.get("n", {}).get("ok") is True
              and blk.get("seen") == "e455443165", blk)
        check("feed rc block: small, no topic", len(txt) < 400 and TOPIC not in txt, txt)
        check("feed: rc rides the ext first", pc_report.EXT_ORDER[0] == "rc")


def test_seen_written_on_commit_change_only():
    with Fakes() as f:
        done = os.path.join(f.tmp, "remote_done.json")
        ctl = rc.RemoteControl(Bot(), done_path=done, log=lambda *a: None, env={"LE_REMOTE": "1"})
        old = rc.fetch
        writes = []
        rc.fetch = lambda *a, **k: {"ok": True, "text": "{}", "commit": "abc1234567"}
        old_save = rc.save_done
        rc.save_done = lambda d, path=rc.DONE_PATH: (writes.append(1), old_save(d, path))
        try:
            ctl.tick(time.time())
            ctl.tick(time.time())
        finally:
            rc.fetch, rc.save_done = old, old_save
        seen = rc.load_done(done).get("seen") or {}
        check("seen: the control commit the PC read", seen.get("commit") == "abc1234567", seen)
        check("seen: written once for one commit (not every minute)", len(writes) == 1, writes)


def main():
    for fn in (test_zero_setup_both_channels, test_bus_active_every_channel, test_type_switch_never_drops_it,
               test_no_phone_app_still_ntfy, test_switched_off_falls_back, test_controller_records_and_feed_shows,
               test_seen_written_on_commit_change_only):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(fn.__name__, False, f"{e.__class__.__name__}: {e}")
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
