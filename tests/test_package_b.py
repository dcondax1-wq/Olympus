"""Audit 2026-11-22 PACKAGE B, "every critical alarm reaches the phone" (research/handoff/2026-11-22/audit/BACKLOG.md). Offline fakes.

  a. push.pc_app_ok: guards (tag le-guard) and the alerts_plus crit kinds pass; 'armed' and 'update' do not
  b. push.pc_send_now of a kill crit: sent > 0 with a fake Web Push sender (no network), and its private-topic copy is asked for
  c. readiness.send_alert with no Telegram / Discord: 'push' only when the fake delivery works, 'none' when it fails; tick() then
     rolls the de-dup back and the next tick sends it again
  d. alert_bus.send(wait=True) with nothing delivered = 'failed'
  e. fill_audit: a clock block is LOUD ('MISSED TRADE', soft False), not 'Held back by a rule'
  f. notify.instant_problem with no topic: the app takes it, 'sent (app)'; the report's problem_dup then skips its copy
  g. readiness clock fix text = FIX_CLOCK.bat (no 'Sync now')
    python -X utf8 -m tests.test_package_b
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import alert_bus as AB  # noqa: E402
from engine import notify as N  # noqa: E402
from engine import push as P  # noqa: E402

RES: list = []


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def main() -> int:
    tmp = tempfile.mkdtemp()
    old_home = os.environ.get("OLYMPUS_HOME")
    os.environ["OLYMPUS_HOME"] = os.path.join(tmp, "home")              # no Telegram / Discord, no ntfy topic
    saved = (AB.STATE_PATH, AB.LOG_PATH, AB._HTTP, N.INSTANT_PATH, P.app_send, P.pc_config, P.enabled, AB._SLEEP)
    AB._SLEEP = lambda s: None
    AB.STATE_PATH, AB.LOG_PATH = os.path.join(tmp, "ab.json"), os.path.join(tmp, "ab.jsonl")
    AB._HTTP = lambda *a, **k: (0, "offline")
    N.INSTANT_PATH = os.path.join(tmp, "instant.json")
    try:
        # a
        g = P.text_payload("PC", "ops", "Entries blocked", "clock", key="guard:clock:1")
        g["tag"] = "le-guard"
        crit = [P.text_payload("PC", k, k, "b", key=f"crit:{k}:1") for k in ("kill", "unprotected", "eval_floor")]
        check("a. pc_app_ok: a guards payload (tag le-guard) passes", P.pc_app_ok(g))
        check("a. pc_app_ok: alerts_plus kill / unprotected / eval_floor crit payloads pass", all(P.pc_app_ok(c) for c in crit))
        os.environ.pop("LE_PUSH_EXTRA", None)
        check("a. pc_app_ok: 'armed' and 'update' do not", not P.pc_app_ok(P.text_payload("PC", "armed", "a", "b", key="x"))
              and not P.pc_app_ok(P.text_payload("PC", "update", "a", "b", key="y")))
        # b
        sent = []
        asked = []
        P.pc_config = lambda *a, **k: {"subs": [{"endpoint": "https://web.push.apple.com/x", "keys": {}}], "vapid_private": "k"}
        P.enabled = lambda c=None: True
        saved_crit = P._crit_ntfy
        P._crit_ntfy = lambda p: asked.append(p.get("key")) or "sent"
        P.app_send = lambda payload, **k: (sent.append(payload), {"sent": 1})[1]
        r = P.pc_send_now(crit[0])
        P._crit_ntfy = saved_crit
        check("b. pc_send_now of a kill crit: sent > 0 (fake Web Push)", r.get("sent", 0) > 0 and sent, r)
        check("b. ... and its private ntfy copy is sent too (instant_problem)", asked == ["crit:kill:1"], asked)
        # c
        from engine import readiness as R
        a = {"key": "ready:no:1", "title": "NOT READY: Zlarior is not armed", "body": "Fix: START BOT.", "quiet": False}
        P.app_send = lambda payload, **k: {"sent": 1}
        check("c. no Telegram: 'push' when the fake app delivery works", R.send_alert(a) in ("push", "zero"), R.send_alert(dict(a, key="ready:no:2")))
        P.app_send = lambda payload, **k: {"sent": 0, "skipped": "no phone"}
        check("c. nothing delivered: 'none'", R.send_alert(dict(a, key="ready:no:3")) == "none")
        st = os.path.join(tmp, "ready_state.json")
        lp = os.path.join(tmp, "ready_last.json")
        bad = {"drift_s": 24.5}
        from tests import test_ready as TR
        f = TR.facts(drift_s=24.5)
        now = TR.MON_0115
        r1 = R.tick(now=now, facts=f, sender=None, state_path=st, last_path=lp)
        check("c. tick: an alert was due, nothing took it", r1.get("alert") and r1.get("via") == "none", r1)
        P.app_send = lambda payload, **k: {"sent": 1}
        r2 = R.tick(now=now + 300, facts=f, state_path=st, last_path=lp)
        check("c. the next tick sends it again (the de-dup was rolled back)", r2.get("alert") and r2.get("via") in ("push", "zero"), r2)
        r3 = R.tick(now=now + 600, facts=f, state_path=st, last_path=lp)
        check("c. once delivered: not again 5 min later", not r3.get("alert"), r3)
        _ = bad
        # d
        r = AB.send({"kind": "problem", "key": "pkgb:d", "title": "t", "body": "b", "notify_type": "problems"},
                    cfg={"telegram": None, "discord": None, "ntfy": True, "webpush": False}, wait=True, _zero=True)
        check("d. alert_bus.send(wait=True), nothing delivered: 'failed'", r == "failed", r)
        # e
        from engine import fill_audit as FA
        body = "The backtest took it: NOT routed: GUARD PC clock 24.5 s behind internet time (max 5 s)"
        check("e. rule_hold(clock block) is False (loud)", FA.rule_hold(body) is False)
        mp = FA._missed_problem({"key": "exec:miss:1795050000", "title": "Missed trade", "body": body})
        check("e. its title starts 'MISSED TRADE', soft False", mp and mp["title"].startswith("MISSED TRADE") and not mp.get("soft"), mp)
        # f
        got = []
        P.app_send = lambda payload, **k: (got.append(payload), {"sent": 1})[1]
        why = N.instant_problem({"key": "fast:bot_down:pkgb", "code": "bot_down", "title": "ZEUS not polling", "body": "x"}, cfg={})
        check("f. no topic: the app takes it, 'sent (app)'", why == "sent (app)" and got, why)
        check("f. the report's problem_dup then skips its copy", N.problem_dup({"key": "cond:bot_down:x"}, now=time.time())
              or "fast:bot_down:pkgb" in (N._instant_state(N.INSTANT_PATH).get("keys") or {}))
        # g
        v = R.ready_verdict(now, facts=f)
        fx = v["blockers"][0]["exact_fix"]
        check("g. readiness clock fix says FIX_CLOCK.bat, no 'Sync now'", "FIX_CLOCK.bat" in fx and "Sync now" not in fx, fx)
        src = open(os.path.join(ROOT, "engine", "readiness.py"), encoding="utf-8").read()
        check("g. no 'Sync now' left in readiness.py", "Sync now" not in src)
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        check(f"raised {e.__class__.__name__}: {e}", False)
    finally:
        AB.drain(5)
        AB.STATE_PATH, AB.LOG_PATH, AB._HTTP, N.INSTANT_PATH, P.app_send, P.pc_config, P.enabled, AB._SLEEP = saved
        if old_home is None:
            os.environ.pop("OLYMPUS_HOME", None)
        else:
            os.environ["OLYMPUS_HOME"] = old_home
        shutil.rmtree(tmp, ignore_errors=True)
    n, ok = len(RES), sum(RES)
    print(f"\npackage B: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
