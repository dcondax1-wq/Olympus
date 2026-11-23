"""engine/payout_autopilot.py (night-payout 2026-11-22): payout ready after the close, the Builder #4 / #5 guard, the Rapid $10k day,
the owner's "I took it" -> the account + the Money pipeline. Offline: fakes and temp files only; it never requests a payout.

  a. calendar: 16:10 ET close, Thanksgiving 13:00 / day-after 13:15 halts, weekend none, the 18:00 reopen
  b. Builder rules (engine/funded_life.track): buffer, MFFU min, the owner's max-request plan, 2 traded days, best day <= 50%, 48 h
  c. payout #4 / #5: #4 says LAST; 4 taken = ONE "do not take payout #5"; #5 offered = "do NOT take it" once a cycle; funded_life and
     engine/lifecycle never call a 5th payout ready
  d. Rapid: $500 min, daily (once a day, again the next day), the 25K's $250 net since the last payout, 90% split
  e. Rapid $10,000 live day: a $6,000+ day = one alert in the session, none at $5,000
  f. tick: once per key, a failed send is retried, before the close nothing
  g. record: the right account's own record, the ledger, the #4 / #5 words; the Money pipeline counts a Rapid payout once
  h. TRADE_HOME P: pick, Enter = the ready $, one yes; never a request; the menu line
    python -X utf8 -m tests.test_payout_autopilot     (~1 s)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import funded_life as FL  # noqa: E402
from engine import payout_autopilot as PA  # noqa: E402

ET = ZoneInfo("America/New_York")
RES: list = []


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def ts(y, m, d, h, mi=0):
    return dt.datetime(y, m, d, h, mi, tzinfo=ET).timestamp()


AFTER = ts(2026, 11, 24, 16, 20)            # a Tuesday after the close


def b25(days, pays=None, today="2026-11-24", prior=0.0):
    return FL.track(days, pays or {}, "builder25k", today=today, start="2026-11-02", name="ATLAS 25K", prior=prior)


GOOD = {"2026-11-03": 500, "2026-11-04": 450, "2026-11-05": 500, "2026-11-06": 480, "2026-11-09": 300}   # $2,230, best 22%


def part_a():
    check("a. full day: 16:05 no, 16:10 / 16:20 yes", PA.after_close(ts(2026, 11, 24, 16, 5)) is None
          and PA.after_close(ts(2026, 11, 24, 16, 10)) == "2026-11-24" and PA.after_close(AFTER) == "2026-11-24")
    check("a. after the 18:00 reopen: no (the next day's session)", PA.after_close(ts(2026, 11, 24, 18, 30)) is None)
    check("a. Thanksgiving 2026-11-26: CME halts 13:00 ET -> due from 13:00", PA.after_close(ts(2026, 11, 26, 12, 55)) is None
          and PA.after_close(ts(2026, 11, 26, 13, 5)) == "2026-11-26", PA.close_of("2026-11-26"))
    check("a. Fri 2026-11-27 half day: due from 13:15", PA.after_close(ts(2026, 11, 27, 13, 10)) is None
          and PA.after_close(ts(2026, 11, 27, 13, 20)) == "2026-11-27")
    check("a. weekend: never", PA.after_close(ts(2026, 11, 28, 16, 30)) is None and PA.close_of("2026-11-29") is None)
    check("a. session: Sunday 18:30 ET = Monday's session", PA.in_session(ts(2026, 11, 29, 18, 30)) == "2026-11-30")
    check("a. session: Friday 17:00 = none", PA.in_session(ts(2026, 11, 27, 17, 0)) is None)


def part_b():
    v = PA.builder(b25(GOOD), "atlas")
    check("b. 25K at $2,230 profit, 5 days, best 22%: ready $1,000, $800 to you", v["ready"] and v["amount"] == 1000 and v["to_you"] == 800, v)
    a = PA.alerts([v], AFTER)
    check("b. ONE alert 'Payout ready: ATLAS 25K can request $1,000 now'", len(a) == 1 and a[0]["title"].startswith(
        "Payout ready: ATLAS 25K can request $1,000 now"), a)
    check("b. the alert has the MFFU dashboard clicks (help-center words) and the record step", "left menu Payouts" in a[0]["body"]
          and "Personal Settings > KYC" in a[0]["body"] and "Riseworks" in a[0]["body"]
          and "TRADE_HOME -> P" in a[0]["body"] and "$800 reaches you" in a[0]["body"], a[0]["body"])
    small = {"2026-11-03": 400, "2026-11-04": 400, "2026-11-05": 400, "2026-11-06": 300}       # $1,500: $400 above the buffer
    v = PA.builder(b25(small), "atlas")
    check("b. $400 above the buffer: MFFU would pay, the plan waits for the max (no alert)", not v["ready"]
          and "plan waits" in v["why"][0] and not PA.alerts([v], AFTER), v)
    v = PA.builder(b25({"2026-11-03": 300, "2026-11-04": 300, "2026-11-05": 300, "2026-11-06": 300}), "atlas")
    check("b. $100 under the buffer + min: not ready", not v["ready"] and not PA.alerts([v], AFTER))
    big = {"2026-11-03": 1500, "2026-11-04": 400, "2026-11-05": 400}                            # best day 65%
    v = PA.builder(b25(big), "atlas")
    check("b. best day 65% of the cycle: not ready (consistency)", not v["ready"] and any("best day" in w for w in v["why"]), v["why"])
    one = {"2026-11-03": 2300}
    v = PA.builder(b25(one), "atlas")
    check("b. one traded day: not ready (2 needed)", not v["ready"] and any("traded day" in w for w in v["why"]), v["why"])
    v = PA.builder(b25({"2026-11-23": 1200, "2026-11-24": 1100}, today="2026-11-24"), "atlas")
    check("b. 48 h after the first funded trade: not yet", not v["ready"] and any("first request" in w for w in v["why"]), v["why"])


def part_c():
    p3 = {"2026-10-01": 1000, "2026-10-10": 1000, "2026-10-20": 1000}
    v = PA.builder(b25(GOOD, p3, prior=3000), "atlas")
    a = PA.alerts([v], AFTER)
    check("c. 3 taken, ready: payout #4 is 'the LAST', close after it", v["guard"] == "last" and a and "LAST" in a[0]["title"]
          and "close the account" in a[0]["body"] and "#5" in a[0]["body"], a)
    p4 = dict(p3, **{"2026-10-28": 1000})
    t4 = b25(GOOD, p4, prior=4000)
    check("c. funded_life: 4 taken -> never 'ready' again (status stop), even when MFFU would pay", t4["eligible"]
          and not t4["ready"] and t4["status"] == "stop" and "Do NOT take payout #5" in t4["text"], (t4["status"], t4["text"]))
    v = PA.builder(t4, "atlas")
    a = PA.alerts([v], AFTER)
    keys = [x["key"] for x in a]
    check("c. 4 taken: 'Do not take payout #5: close after payout 4' + '#5 available: do NOT take it', no 'Payout ready'",
          any(x["title"].endswith("do not take payout #5: close after payout 4") for x in a)
          and any("do NOT take it" in x["title"] for x in a) and not any(x["title"].startswith("Payout ready") for x in a), a)
    sent = {k: 1 for k in keys}
    check("c. the #5 guard is ONE alert (and the offer once a cycle)", not PA.alerts([v], AFTER + 86400, sent), PA.alerts([v], AFTER + 86400, sent))
    check("c. the guard stop shows even before the close (phone card + alert)", PA.alerts([v], ts(2026, 11, 24, 10)) and
          PA.block([v])["rows"][0]["stop"] and "do not take payout #5" in PA.block([v])["rows"][0]["line"])
    from engine import lifecycle as LC
    st = LC.detect({"kind": "funded", "start": 25000, "balance": 25000 + t4["profit"], "floor": 25100, "payout": LC.from_track(t4)})
    check("c. lifecycle never pushes PAYOUT READY for a 5th payout", st["stage"] == "funded", st)
    p5 = dict(p4, **{"2026-11-20": 1000})
    v5 = PA.builder(b25(GOOD, p5, prior=5000), "atlas")
    check("c. 5 taken (it happened anyway): no payout alert, 'live' words", v5["guard"] == "live" and not
          [x for x in PA.alerts([v5], AFTER) if x["title"].startswith("Payout ready")], v5)


def rap(ready=True, req=900.0, stage="funded", today_net=0.0, since_short=None):
    a = {"ready": ready, "request": req if ready else 0.0, "to_you": round(req * 0.9, 2) if ready else 0.0, "keep_at": 26600.0,
         "to_next": 0.0 if ready else 300.0}
    if since_short is not None:
        a["since_short"] = since_short
    return {"on": True, "stage": stage, "payout": a, "today_net": today_net, "label": "Rapid EOD 25K"}


def part_d():
    from engine import rapid as R
    adv = R.payout_advice(27000.0, 25000.0, (), "2026-11-24", 1100.0, 500.0)
    check("d. Rapid 25K: $27,000 -> request $400? no: under the $500 min", not adv["ready"], adv)
    adv = R.payout_advice(27300.0, 25000.0, (), "2026-11-24", 1100.0, 500.0)
    check("d. Rapid 25K: $27,300 -> $700 (keeps $26,600), 90% = $630", adv["ready"] and adv["request"] == 700 and adv["to_you"] == 630, adv)
    adv = R.payout_advice(27300.0, 25000.0, ("2026-11-20",), "2026-11-24", 1100.0, 500.0, 250.0, 120.0)
    check("d. Rapid 25K: only $120 net since the last payout: not ready ($130 short)", not adv["ready"] and adv["since_short"] == 130, adv)
    v = PA.rapid(rap(), "rapid")
    a = PA.alerts([v], AFTER)
    check("d. Rapid ready after the close: 'Payout ready: Rapid EOD 25K can request $900 now', $810 to you",
          a and a[0]["title"] == "Payout ready: Rapid EOD 25K can request $900 now" and "$810 reaches you" in a[0]["body"], a)
    sent = {a[0]["key"]: 1}
    check("d. Rapid: once a day", not PA.alerts([v], AFTER + 600, sent))
    check("d. Rapid: daily payouts = the next day again", PA.alerts([v], AFTER + 86400, sent))
    v = PA.rapid(rap(False, since_short=130.0), "rapid")
    check("d. Rapid since-rule short: no alert, the why says it", not PA.alerts([v], AFTER) and "since the last payout" in v["why"][0], v)
    check("d. Rapid eval (not funded): never a payout", not PA.rapid(rap(stage="eval"), "rapid")["ready"])


def part_e():
    sess = ts(2026, 11, 24, 11, 0)
    v = PA.rapid(rap(False, today_net=6400.0), "rapid")
    a = PA.alerts([v], sess)
    check("e. a $6,400 Rapid day: ONE alert near MFFU's $10,000 live line, in the session", len(a) == 1 and "10,000" in a[0]["title"]
          and a[0]["kind"] == "problem", a)
    check("e. once a day", not PA.alerts([v], sess + 900, {a[0]["key"]: 1}))
    check("e. $5,000: no alert", not PA.alerts([PA.rapid(rap(False, today_net=5000.0), "rapid")], sess))


def part_f():
    tmp = tempfile.mkdtemp()
    try:
        p = os.path.join(tmp, "pa.json")
        v = [PA.builder(b25(GOOD), "atlas")]
        calls = []
        r = PA.tick(now=ts(2026, 11, 24, 15, 0), views=v, sender=lambda a: calls.append(a) or True, path=p)
        check("f. before the close: nothing", not r["alerts"] and not calls, r)
        r = PA.tick(now=AFTER, views=v, sender=lambda a: False, path=p)
        check("f. a failed send is not marked sent", r["alerts"] and not r["alerts"][0]["sent"])
        r = PA.tick(now=AFTER + 900, views=v, sender=lambda a: calls.append(a) or True, path=p)
        check("f. retried next run and sent", len(calls) == 1 and r["alerts"][0]["sent"], r)
        r = PA.tick(now=AFTER + 1800, views=v, sender=lambda a: calls.append(a) or True, path=p)
        check("f. then never again (one alert per payout)", len(calls) == 1 and not r["alerts"])
        st = json.load(open(p))
        check("f. the state file keeps the sent key", any(k.startswith("payout:atlas:") for k in st.get("sent", {})), st)
        r = PA.tick(now=AFTER, views=None, sender=lambda a: True, path=os.path.join(tmp, "x.json"))
        check("f. no funded account on the PC (real gather): no error, no alert", "error" not in r and not r["alerts"], r)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_g():
    tmp = tempfile.mkdtemp()
    try:
        lp = os.path.join(tmp, "ledger.json")
        got = {}
        rec = {"atlas": lambda s: got.setdefault("atlas", s) and {"ok": True}, "rapid": lambda s: got.setdefault("rapid", s) and {"ok": True},
               "x": lambda s, i: got.setdefault("x", (s, i)) and 0}
        r = PA.record("atlas", 1000, "2026-11-25", ledger_path=lp, recorders=rec)
        check("g. ATLAS: account_b's own record gets '2026-11-25=1000.0'", r["ok"] and got["atlas"] == "2026-11-25=1000.0", (r, got))
        check("g. the say line: $ and $ to you", "$1,000" in r["say"] and "$800 to you" in r["say"], r["say"])
        r = PA.record("x:mffu50k_funded", 2000, "2026-11-25", ledger_path=lp, recorders=rec)
        check("g. an extra Builder: eval_life's record with its id", r["ok"] and got["x"] == ("2026-11-25=2000.0", "mffu50k_funded"), got)
        r = PA.record("rapid", 900, "2026-11-25", ledger_path=lp, recorders=rec)
        check("g. Rapid: rapid's record, 90% to you", r["ok"] and got["rapid"] == "2026-11-25=900.0" and "$810 to you" in r["say"], r)
        check("g. a bad amount: nothing recorded", not PA.record("atlas", "abc", ledger_path=lp, recorders=rec)["ok"])
        check("g. an account that refuses: not in the ledger", not PA.record("atlas", 500, "2026-11-26", ledger_path=lp,
              recorders={"atlas": lambda s: {"ok": False, "error": "not funded"}})["ok"]
              and len(json.load(open(lp))["rows"]) == 3)
        for d in ("2026-12-01", "2026-12-08"):
            PA.record("atlas", 1000, d, ledger_path=lp, recorders=rec)
        r = PA.record("atlas", 1000, "2026-12-15", ledger_path=lp, recorders=rec)
        check("g. the 4th recorded: 'the last: close this account; never take #5'", r["n"] == 4 and "never take #5" in r["say"], r)
        r = PA.record("atlas", 1000, "2026-12-22", ledger_path=lp, recorders=rec)
        check("g. a 5th recorded anyway: says MFFU moves you to live", "live" in (r["warn"] or ""), r)
        rows = PA.ledger_rows(lp)
        check("g. ledger -> the Money pipeline: only the Rapid row (Builders flow from their own files)", len(rows) == 1
              and rows[0]["gross"] == 900 and rows[0]["to_you"] == 810, rows)
        from engine import money_goal as MG
        extra = MG.ledger_extra({"ledger": rows}, [])
        check("g. money_goal adds the Rapid payout", len(extra) == 1 and extra[0]["to_you"] == 810, extra)
        check("g. ... once (already counted = not added again)", not MG.ledger_extra({"ledger": rows}, extra), MG.ledger_extra({"ledger": rows}, extra))
        card = MG.build({}, {"v": 1, "t": 1, "inputs": {"updated": 1}, "ledger": [dict(rows[0], day=dt.date.today().isoformat())]})
        check("g. the money card's payouts list carries it (the phone's pipeline reads goals.money.payouts)",
              any(p.get("type") == "rapid" for p in card.get("goal1", card).get("payouts", []) or [])
              or "810" in json.dumps(card), json.dumps(card)[:300])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_h():
    from engine import trade_home as TH
    v = [PA.builder(b25(GOOD), "atlas")]
    asks = iter(["1", "", "y"])
    done = {}
    r = TH.payout_action(lambda *_: next(asks), lambda *_: None, views=v,
                         rec=lambda k, a: done.update(k=k, a=a) or {"ok": True, "say": "Recorded $1,000"})
    check("h. P: pick 1, Enter = the ready $1,000, Y -> recorded", done == {"k": "atlas", "a": 1000.0} and r.startswith("[OK]"), (done, r))
    asks = iter(["1", "1000", "n"])
    done.clear()
    r = TH.payout_action(lambda *_: next(asks), lambda *_: None, views=v, rec=lambda k, a: done.update(k=k) or {"ok": True, "say": ""})
    check("h. no Y = nothing recorded", not done and "Nothing" in r, r)
    check("h. the menu has 'P  I took a payout'", any("I took a payout" in ln for ln in TH.MENU))
    check("h. no funded account: says so", "No funded account" in TH.payout_action(lambda *_: "", lambda *_: None, views=[]))
    src = open(os.path.join(ROOT, "engine", "payout_autopilot.py"), encoding="utf-8").read()
    check("h. read-only: no order / arming / request code in the autopilot", not any(w in src for w in (
        "place_order", "PLACE;", "arm(", "requests.post", "submit_payout")))


def part_rt2():
    """red team 2 (2026-11-23): the Rapid 50K's $500-since-last rule (MFFU; was checked on the 25K only)."""
    from engine import rapid as R
    tmp = tempfile.mkdtemp()
    try:
        bp = os.path.join(tmp, "rapid.json")
        # a 50K funded Rapid: +$6,000, a $900 payout on 11-10 (less than advised), then +$1,000 -$700 = $300 net since; $55,400
        json.dump({"account": "RT50", "plan": "rapideod50k", "stage": "funded", "funded_start": "2026-11-02",
                   "payouts": {"2026-11-10": 900.0}}, open(bp, "w"))
        closes = [["2026-11-05", 0, 6000.0], ["2026-11-12", 0, 1000.0], ["2026-11-13", 0, -700.0]]
        json.dump({"account": "RT50", "closes": closes}, open(os.path.join(tmp, "live_state_acctr.json"), "w"))
        st = R.status(p=bp, state_path=tmp)
        a = st.get("payout") or {}
        check("rt2. Rapid 50K: $300 net since the last payout < MFFU's $500: not ready, $200 short",
              not a.get("ready") and a.get("since_short") == 200, st)
        closes.append(["2026-11-16", 0, 900.0])
        json.dump({"account": "RT50", "closes": closes}, open(os.path.join(tmp, "live_state_acctr.json"), "w"))
        a = R.status(p=bp, state_path=tmp).get("payout") or {}
        check("rt2. Rapid 50K: $1,200 since: ready again", a.get("ready") and a.get("request") == 3200, a)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_one():
    """lead 2026-11-23: ONE phone alert per payout event: the autopilot's. The bot's own 'PAYOUT READY' (account_b) and Rapid
    'rapidpay:' pushes stay off the phone while LE_PAYOUT_AUTOPILOT is on (default) but still log + mark their key; =0 = both."""
    import types
    from engine import account_b as AB, rapid as R
    t = dict(b25(GOOD), record_cmd="python -X utf8 -m engine.account_b --payout {day}={amount}")

    def b_run():
        sent, logs = [], []
        o = types.SimpleNamespace(funded_view=lambda now: t, _funded_eval_view=lambda now: {"status": "funded"}, notified=[],
                                  log=lambda k, m: logs.append(m), _send=sent.append, spec={"funded": {"start": "2026-11-02"}},
                                  label="ATLAS 25K", name="A1", _push_text=lambda *a: sent.append(a))
        AB.AccountB._funded_lifecycle(o, AFTER)
        return sent, logs, o.notified

    def r_run():
        sent, logs = [], []
        o = types.SimpleNamespace(funded_view=lambda now: {"ready": True, "request": 900.0, "to_you": 810.0, "text": "PAYOUT READY: request $900"},
                                  _funded_eval_view=lambda now: {"status": "funded"}, notified=[], log=lambda k, m: logs.append(m),
                                  _push_text=lambda *a: sent.append(a), spec={"funded": {}}, name="R1")
        R.RapidAtlas._funded_lifecycle(o, AFTER)
        return sent, logs, o.notified
    old = os.environ.get("LE_PAYOUT_AUTOPILOT")
    try:
        os.environ.pop("LE_PAYOUT_AUTOPILOT", None)
        bs, bl, bn = b_run()
        rs, rl, rn = r_run()
        auto = PA.alerts([PA.builder(t, "atlas")], AFTER) + PA.alerts([PA.rapid(rap(), "rapid")], AFTER)
        check("one. autopilot on (default): the bot sends NO payout-ready push (Builder + Rapid); the autopilot's alerts are the ONE each",
              PA.active() and not [p for p in bs if str(p.get("key", "")).endswith(":ready")] and not rs and len(auto) == 2, (bs, rs, auto))
        check("one. ... the bot still logs it and marks its key (no lost data, no re-send later)",
              bl and any(k.endswith(":ready") for k in bn) and rl and any(k.startswith("rapidpay:") for k in rn), (bl, bn, rl, rn))
        os.environ["LE_PAYOUT_AUTOPILOT"] = "0"
        bs, _, _ = b_run()
        rs, _, _ = r_run()
        check("one. LE_PAYOUT_AUTOPILOT=0: the old pushes come back exactly (Builder 'PAYOUT READY', Rapid 'Rapid EOD: request')",
              not PA.active() and any(str(p.get("key", "")).endswith(":ready") and p["title"].startswith("PAYOUT READY") for p in bs)
              and rs and rs[0][0] == "Rapid EOD: request $900", (bs, rs))
    finally:
        if old is None:
            os.environ.pop("LE_PAYOUT_AUTOPILOT", None)
        else:
            os.environ["LE_PAYOUT_AUTOPILOT"] = old


def main() -> int:
    for f in (part_a, part_b, part_c, part_d, part_e, part_f, part_g, part_h, part_rt2, part_one):
        try:
            f()
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f"{f.__name__} raised {e.__class__.__name__}: {e}", False)
    n, ok = len(RES), sum(RES)
    print(f"\npayout autopilot: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
