"""Phone pairing (day-security2 2026-11-20, engine/push.intake; LEAD_WIRES W4). The PC's box key and VAPID key are public, so a
stranger could subscribe to the owner's trade alerts and push his phone off the list.
  a. upgrade: the owner's phone already on the list keeps getting every alert with no code, and may send its subscription again
  b. a stranger without the code: ignored; the owner's phone gets ONE notice with the code (then at most every 6 h); five strangers
     never push the owner off; a trade alert goes to the owner only
  c. wrong codes: ignored and counted; after 30 in a day even the right code waits for tomorrow
  d. the right code: the new phone joins and gets its welcome; the code is one-time (rotated)
  e. the owner's phones all gone: still no stranger joins; the code goes to the private alert topic
  f. a PC that never had a phone: the first phone joins without a code (nothing to send it to yet), the next needs one
  g. a stranger's notice or bad code never breaks the intake (no error), the intake never posts to the relay
    python -X utf8 -m tests.test_push_pairing
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tests.test_webpush import FakeRelay, Sandbox, phone, recorder, sealed  # noqa: E402
from engine import push as P  # noqa: E402

RES = []


def ok(cond, name, info=""):
    RES.append(bool(cond))
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond or not info else f"  -> {str(info)[:400]}"))


def cfg():
    return json.load(open(P.CONFIG_PATH, encoding="utf-8"))


def seed_owner(now):
    """The PC as it is today: its keys and the owner's phone on the list (made before pairing existed: no pair_on, no pair)."""
    P.own_key()
    wp = P.app_block()
    _, _, sub = phone(1)
    f = cfg()
    f["devices"] = [{"id": P.endpoint_id(sub["endpoint"]), "sub": sub, "key": wp["k"], "since": now - 30 * 86400, "seen": now - 3600, "ua": "iPhone"}]
    P._write_private(P.CONFIG_PATH, f)
    return wp, sub


def main():
    now = int(time.time())
    sb = Sandbox()
    try:
        relay = FakeRelay()
        R = P.Relay(base="https://ntfy.sh", topic="le-test", http=relay)
        wp, owner = seed_owner(now)
        oid = P.endpoint_id(owner["endpoint"])
        sent, send = recorder()

        print("a. upgrade: the owner's phone")
        relay.add(sealed("sub", {"sub": owner, "key": wp["k"], "ua": "iPhone"}, wp["b"]))
        r = P.intake(R.read(), now, sender=send, ntfy=lambda p: True)
        ok([d["id"] for d in cfg()["devices"]] == [oid] and not r.get("unpaired"), "the owner's phone sends its subscription again: kept, no code", r)
        res = P.app_send(P.text_payload("Zlarior", "fill", "LIT long", "1 MNQ", key="k1"), sender=send)
        ok(res["sent"] == 1 and sent[-1]["ep"] == owner["endpoint"], "a trade alert reaches the owner's phone with zero action", res)

        print("b. strangers")
        told = []
        strangers = [phone(20 + i)[2] for i in range(5)]
        for i, s in enumerate(strangers):
            relay.add(sealed("sub", {"sub": s, "key": wp["k"], "ua": "Evil"}, wp["b"], t=now + i))
        n0 = len(sent)
        r = P.intake(R.read(), now + 60, sender=send, ntfy=lambda p: told.append(p) or True)
        ids = [d["id"] for d in cfg()["devices"]]
        ok(ids == [oid] and r.get("unpaired") == 5 and not r["added"], "5 strangers without the code: none joins, the owner stays", (ids, r))
        notices = sent[n0:]
        code = cfg()["pair"]["code"]
        ok(len(notices) == 1 and notices[0]["ep"] == owner["endpoint"] and code in notices[0]["data"]["body"]
           and "holding" in notices[0]["data"]["body"], "the owner's phone gets ONE notice with the code", notices)
        ok(len(told) == 1 and code in told[0]["body"], "and the private alert topic gets the same notice", told)
        relay.add(sealed("sub", {"sub": phone(30)[2], "key": wp["k"]}, wp["b"], t=now + 120))
        n1 = len(sent)
        r = P.intake(R.read(), now + 600, sender=send, ntfy=lambda p: told.append(p) or True)
        ok(len(sent) == n1 and len(told) == 1 and r.get("unpaired") == 1, "another stranger within 6 h: ignored, no second notice", r)
        res = P.app_send(P.text_payload("Zlarior", "outcome", "LIT closed", "+$410", key="k2"), sender=send)
        ok(res["sent"] == 1 and sent[-1]["ep"] == owner["endpoint"], "the next trade alert still goes to the owner only", res)

        print("c. wrong codes")
        wrong = "0" * 8 if code != "0" * 8 else "1" * 8
        for i in range(P.PAIR_BAD_MAX):
            relay.add(sealed("sub", {"sub": phone(40 + i)[2], "key": wp["k"], "pair": wrong}, wp["b"], t=now + 700 + i))
        r = P.intake(R.read(), now + 900, sender=send, ntfy=lambda p: True)
        ok(not r["added"] and cfg()["pair"]["bad"] == P.PAIR_BAD_MAX, "%d wrong codes: none joins, each counted" % P.PAIR_BAD_MAX, r)
        relay.add(sealed("sub", {"sub": phone(80)[2], "key": wp["k"], "pair": code}, wp["b"], t=now + 950))
        r = P.intake(R.read(), now + 1000, sender=send, ntfy=lambda p: True)
        ok(not r["added"], "after that, even the right code waits for the next UTC day (no guessing)", r)

        print("d. the right code")
        tomorrow = now + 86400
        _, _, mine = phone(90)
        relay.add(sealed("sub", {"sub": mine, "key": wp["k"], "pair": code, "ua": "iPad"}, wp["b"], t=tomorrow))
        n2 = len(sent)
        r = P.intake(R.read(), tomorrow + 10, sender=send, ntfy=lambda p: True)
        mid = P.endpoint_id(mine["endpoint"])
        ok(r["added"] == [mid] and set(d["id"] for d in cfg()["devices"]) == {oid, mid}, "the owner's new phone joins with the code", r)
        ok(any(x["ep"] == mine["endpoint"] and x["data"]["title"] == "Olympus notifications are on" for x in sent[n2:]), "and gets its welcome")
        ok(cfg()["pair"]["code"] != code, "the code is one-time: a new one is made")
        relay.add(sealed("sub", {"sub": phone(91)[2], "key": wp["k"], "pair": code}, wp["b"], t=tomorrow + 20))
        r = P.intake(R.read(), tomorrow + 30, sender=send, ntfy=lambda p: True)
        ok(not r["added"], "the used code does not work twice", r)

        print("e. the owner's phones all gone")
        f = cfg()
        f["devices"] = []
        P._write_private(P.CONFIG_PATH, f)
        told2 = []
        relay.add(sealed("sub", {"sub": phone(95)[2], "key": wp["k"]}, wp["b"], t=tomorrow + 7 * 3600))
        r = P.intake(R.read(), tomorrow + 7 * 3600 + 10, sender=send, ntfy=lambda p: told2.append(p) or True)
        ok(not r["added"] and cfg()["devices"] == [], "an empty list never lets a stranger in (the PC had phones before)", r)
        ok(len(told2) == 1 and cfg()["pair"]["code"] in told2[0]["body"], "the code goes to the private alert topic (no phone left)", told2)

        print("g. never breaks")
        ok(not any(k == "error" for k in r) and relay.posts == 0, "no error in the intake, nothing posted to the relay", (r, relay.posts))
    finally:
        sb.close()

    print("f. a PC that never had a phone")
    sb = Sandbox()
    try:
        relay = FakeRelay()
        R = P.Relay(base="https://ntfy.sh", topic="le-test", http=relay)
        P.own_key()
        wp = P.app_block()
        sent, send = recorder()
        _, _, first = phone(100)
        relay.add(sealed("sub", {"sub": first, "key": wp["k"]}, wp["b"]))
        r = P.intake(R.read(), now, sender=send, ntfy=lambda p: True)
        ok(r["added"] == [P.endpoint_id(first["endpoint"])], "the very first phone joins without a code", r)
        relay.add(sealed("sub", {"sub": phone(101)[2], "key": wp["k"]}, wp["b"], t=now + 5))
        r = P.intake(R.read(), now + 300, sender=send, ntfy=lambda p: True)
        ok(not r["added"] and r.get("unpaired") == 1 and cfg().get("pair_on"), "the second one needs the code", r)
    finally:
        sb.close()
    n = sum(RES)
    print(f"\npush_pairing: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
