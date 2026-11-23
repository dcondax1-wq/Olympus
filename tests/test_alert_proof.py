"""PROOF: every critical alert reaches the owner's phone with ZERO setup, once per channel (night-alertproof 2026-11-23).

Fake transport only (nothing is posted for real): the private ntfy topic = a recorder (engine/alert_bus._HTTP and
engine/notify._post), the Olympus app = a recorder (engine/push.app_send). No Telegram / Discord set up (the owner's state).
Each event goes through its REAL sender (the function the bot / the PC report calls), then the test counts what each channel got:
  delivered = at least one channel; no double-send = at most ONE post per channel per event, and the same event a second time
  (a restart, the next 15-minute report) adds nothing.

  1 keep-alive deadline < 48 h ("the next session is the last safe day", soft)   engine/keepalive._warn -> notify.instant_problem
  2 keep-alive missed ("did not go through: place 1 MNQ by hand")                 engine/keepalive refusal -> notify.instant_problem
  3 bot stopped (fast alarm) + the 15-minute report's own copy                    engine/fast_alarm -> notify.instant_problem; pc_report problem_dup
  4 clock drift block (the guard's push) + readiness's NOT READY for the same drift engine/guards._notify -> push._pc_send; readiness.send_alert
  5 NinjaTrader disconnect (readiness NOT READY)                                  engine/readiness.send_alert
  6 daily-loss stop hit (the guard's "Entry blocked ... soft daily loss")          engine/guards._notify -> push._pc_send
  7 payout eligible                                                               engine/payout_autopilot._send
  8 update failed / rolled back                                                   engine/autoupdate.alert_for
  9 trade opened / closed                                                         engine/push._pc_send (the bot's pc_notify worker)
    python -X utf8 -m tests.test_alert_proof
"""
from __future__ import annotations

import json
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
ROWS: list = []
TOPIC = "nq-proof-topic-" + "z" * 6


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{str(detail)[:500]}]" if detail and not ok else ""))


class World:
    """A zero-setup PC: a private ntfy topic, one Olympus phone, no Telegram / Discord. Every send recorded, none real."""

    def __init__(self, app_ok=True):
        self.dir = tempfile.mkdtemp(prefix="proof_")
        self.home = os.path.join(self.dir, "home")
        os.makedirs(self.home)
        with open(os.path.join(self.home, "ntfy.json"), "w") as fh:
            json.dump({"ntfy": "https://ntfy.example", "topic": TOPIC}, fh)
        self.env = {k: os.environ.get(k) for k in ("OLYMPUS_HOME", "LE_ALERT_BUS", "LE_PUSH_EXTRA", "LE_SELFTEST_CHILD")}
        os.environ["OLYMPUS_HOME"] = self.home
        for k in ("LE_ALERT_BUS", "LE_PUSH_EXTRA", "LE_SELFTEST_CHILD"):
            os.environ.pop(k, None)
        self.saved = (AB.STATE_PATH, AB.LOG_PATH, AB._HTTP, AB._SLEEP, AB.DIGEST_PATH, N.INSTANT_PATH, N._post, P.app_send,
                      P.SENT_PATH, dict(P._PC))
        d = lambda *a: os.path.join(self.dir, *a)  # noqa: E731
        AB.STATE_PATH, AB.LOG_PATH, AB.DIGEST_PATH = d("ab.json"), d("ab.jsonl"), d("digest.json")
        N.INSTANT_PATH = d("instant.json")
        P.SENT_PATH = d("push_sent.json")
        P._PC["notifier"] = None
        AB._SLEEP = lambda s: None
        AB._PENDING.clear()
        self.ntfy, self.app = [], []
        self.app_ok = app_ok

        def http(method, url, body, headers, timeout):
            if TOPIC in url:
                self.ntfy.append({"title": headers.get("Title"), "body": (body or b"").decode("utf-8", "replace")})
                return 200, json.dumps({"id": f"n{len(self.ntfy)}"})
            return 0, "not allowed in the proof"
        AB._HTTP = http

        def post(base, topic, msg, timeout=8):
            if topic == TOPIC:
                self.ntfy.append({"title": msg.get("title"), "body": msg.get("body")})
                return True
            return False
        N._post = post

        def app(payload, **k):
            if not self.app_ok:
                return {"sent": 0, "skipped": "no phone"}
            self.app.append({"title": payload.get("title"), "key": payload.get("key")})
            return {"sent": 1}
        P.app_send = app

    def mark(self):
        return len(self.ntfy), len(self.app)

    def since(self, m):
        AB.drain(10)
        time.sleep(0.05)
        return self.ntfy[m[0]:], self.app[m[1]:]

    def close(self):
        AB.drain(10)
        (AB.STATE_PATH, AB.LOG_PATH, AB._HTTP, AB._SLEEP, AB.DIGEST_PATH, N.INSTANT_PATH, N._post, P.app_send,
         P.SENT_PATH, pc) = self.saved
        P._PC.clear()
        P._PC.update(pc)
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)


def verdict(w, name, fn, again=True, words=()):
    """Run fn (the event), then again (a restart / the next report): delivered, <= 1 per channel, nothing more the 2nd time."""
    m = w.mark()
    fn()
    nt, ap = w.since(m)
    ok_deliv = bool(nt or ap)
    ok_once = len(nt) <= 1 and len(ap) <= 1
    texts = " | ".join(str(x.get("title")) + " " + str(x.get("body") or "") for x in nt + ap)
    ok_words = all(wd.lower() in texts.lower() for wd in words)
    m2 = w.mark()
    if again:
        fn()
    nt2, ap2 = w.since(m2)
    ok_again = not nt2 and not ap2
    check(f"{name}: reaches the phone (ntfy {len(nt)}, app {len(ap)})", ok_deliv and ok_words, texts or "nothing")
    check(f"{name}: no double-send (<= 1 per channel; again = nothing)", ok_once and ok_again, (len(nt), len(ap), len(nt2), len(ap2)))
    ROWS.append((name, len(nt), len(ap), ok_deliv and ok_once and ok_again and ok_words))
    return nt, ap


def ev_keepalive(w):
    p_eve = {"key": "ka:eve:lit:2026-11-24", "code": "keepalive", "soft": True,
             "title": "Zlarior 50K: the next session is the last safe day to trade",
             "body": "No trade for 5 days; MFFU's limit is 2026-11-26 (2 days). Place 1 MNQ by hand on Wed 11-25."}
    verdict(w, "1 keep-alive deadline < 48 h", lambda: N.instant_problem(dict(p_eve)), words=("last safe day",))
    p_miss = {"key": "ka:refused:lit:2026-11-24", "code": "keepalive", "title": "Keep-alive on Zlarior 50K did not go through",
              "body": "your pause blocks it. Place 1 MNQ by hand on this account before 16:05 ET."}
    verdict(w, "2 keep-alive missed", lambda: N.instant_problem(dict(p_miss)), words=("did not go through",))


def ev_keepalive_app_only(w):
    """The owner allowed Olympus app notifications but never subscribed in ntfy: a soft notice must still reach the app."""
    p = {"key": "ka:eve:x:2026-11-24", "code": "keepalive", "soft": True, "title": "25K #2: the next session is the last safe day",
         "body": "Place 1 MNQ by hand tomorrow."}
    m = w.mark()
    N.instant_problem(dict(p))
    nt, ap = w.since(m)
    check("1b. a soft keep-alive warning goes to the Olympus app first (an ntfy post nobody follows is not a phone)",
          len(ap) == 1 and not nt, (nt, ap))


def ev_soft_fallback(w):
    p = {"key": "ka:eve:y:2026-11-24", "code": "keepalive", "soft": True, "title": "Rapid EOD 25K: the next session is the last safe day",
         "body": "Place 1 MNQ by hand tomorrow."}
    m = w.mark()
    N.instant_problem(dict(p))
    nt, ap = w.since(m)
    check("1c. no Olympus phone set up: the soft warning falls back to ntfy (still delivered, once)", len(nt) == 1 and not ap, (nt, ap))


def ev_clock_untold(w):
    from engine import readiness as R
    a = {"key": "ready:no:clock-alone", "title": "NOT READY for 02:00: PC clock 9 s behind", "body": "Fix: FIX_CLOCK.bat.",
         "quiet": False, "blocker": "clock", "n_blockers": 1}
    m = w.mark()
    via = R.send_alert(a)
    nt, ap = w.since(m)
    check("4b. no guard alarm on the phone (the bot was stopped): readiness's clock NOT READY still goes out", via in ("zero", "push")
          and (nt or ap), (via, nt, ap))


def ev_bot_stopped(w):
    p = {"key": "fast:bot_stopped:1795500000", "code": "bot_stopped", "cond": "bot_stopped", "title": "Bot stopped",
         "body": "The bot is not running in trading hours. Open the PC and press START BOT."}
    verdict(w, "3 bot stopped (fast alarm)", lambda: N.instant_problem(dict(p)), words=("Bot stopped",))
    dup = N.problem_dup({"key": "cond:bot_stopped:1795500300"}, now=time.time())
    check("3. the 15-minute report's own 'bot stopped' is skipped (problem_dup): one alert, not two", dup is True, dup)


def guard_payload(key, title, body):
    p = P.text_payload("PC", "ops", title, body, key=f"guard:{key}", t=int(time.time()))
    p["tag"] = "le-guard"
    return p


def ev_clock(w):
    from engine import readiness as R
    day = time.strftime("%Y-%m-%d")
    gp = guard_payload(f"clock:{day}", "Clock drift: entries blocked",
                       "PC clock 24 s off: could not sync: double-click FIX_CLOCK.bat once, right-click > Run as administrator.")
    verdict(w, "4 clock drift block (the guard)", lambda: P._pc_send(dict(gp)), words=("Clock drift",))
    a = {"key": "ready:no:clock-proof", "title": "NOT READY for 02:00: PC clock 24 s behind",
         "body": "The bot blocks every new entry. Fix: double-click FIX_CLOCK.bat once.", "quiet": False, "blocker": "clock"}
    m = w.mark()
    via = R.send_alert(a)
    nt, ap = w.since(m)
    check("4. readiness's NOT READY for the SAME clock drift is not a second alert (the guard told the phone already)",
          not nt and not ap and via == "told", (via, nt, ap))


def ev_nt(w):
    from engine import readiness as R
    a = {"key": "ready:no:nt-proof", "title": "NOT READY for 02:00: NinjaTrader is not connected",
         "body": "No bars, no orders. Fix: open NinjaTrader and log in.", "quiet": False, "blocker": "nt_conn"}
    verdict(w, "5 NinjaTrader disconnect (readiness)", lambda: R.send_alert(dict(a)), words=("NinjaTrader",))


def ev_dll(w):
    gp = guard_payload(f"entry:{int(time.time()) - 60}", "Entry blocked",
                       "LONG 4 at 10:31 ET not sent: today's routed P&L $-1,005 reached the $1,000 soft daily loss")
    verdict(w, "6 daily-loss stop hit (the guard)", lambda: P._pc_send(dict(gp)), words=("soft daily loss",))


def ev_payout(w):
    from engine import payout_autopilot as PA
    a = {"key": "payout:atlas:2026-11-25", "title": "Payout ready: ATLAS 25K can request $1,000 now",
         "body": "$800 reaches you. In the MFFU dashboard: left menu Payouts.", "kind": "payout_ready"}
    verdict(w, "7 payout eligible", lambda: PA._send(dict(a)), words=("Payout ready",))


def ev_update(w):
    from engine import autoupdate as AU
    res = {"alert": True, "status": "rolled_back", "reason": "the PC self-test failed", "t": 1795500000, "old": "a" * 9, "new": "b" * 9}
    verdict(w, "8 update failed / rolled back", lambda: AU.alert_for(dict(res), sync=True), words=("rolled back",))


def ev_trade(w):
    t = int(time.time()) - 30
    ent = P.entry_payload("Zlarior 50K", "LONG", 4, t, src="pc", contract="MNQ", entry=21034.25, stop=21012.0, target=21090.5)
    verdict(w, "9a trade opened", lambda: P._pc_send(dict(ent)), words=("Zlarior",))
    out = P.outcome_payload("Zlarior 50K", "LONG", "TARGET", 312.0, t, t + 1500, src="pc", qty=4)
    verdict(w, "9b trade closed", lambda: P._pc_send(dict(out)), words=("Zlarior",))


def main() -> int:
    for f, kw in ((ev_keepalive, {}), (ev_keepalive_app_only, {}), (ev_soft_fallback, {"app_ok": False}), (ev_clock_untold, {}),
                  (ev_bot_stopped, {}), (ev_clock, {}), (ev_nt, {}), (ev_dll, {}),
                  (ev_payout, {}), (ev_update, {}), (ev_trade, {})):
        w = World(**kw)
        try:
            f(w)
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f"{f.__name__} raised {e.__class__.__name__}: {e}", False)
        finally:
            w.close()
    print("\n| event | ntfy | Olympus app | ok |")
    for r in ROWS:
        print(f"| {r[0]} | {r[1]} | {r[2]} | {'yes' if r[3] else 'NO'} |")
    n, ok = len(RES), sum(RES)
    print(f"\nalert proof: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
