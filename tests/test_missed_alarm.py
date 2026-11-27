"""night-missedalarm (2026-11-27, red team): engine/live_guard's missed-trade alarm, the not-armed case made the owner's words.
  a. an UNARMED follower + a LIT signal -> ONE line "<account> is not armed: it missed Zlarior ... Arm it at the PC"
  b. an ARMED follower that routed it -> nothing
  c. a second signal the same day on the same unarmed account -> no second line (one a day per account); the next day -> a line again
  d. ATLAS on the Rapid (max $250 risk a trade) missing the EMA +6.6R: "~+$1,659 at its size"
  e. read only, never raises on junk, ids masked; the other miss reasons (refused, start problem) keep the old MISSED TRADE line
    python -X utf8 -m tests.test_missed_alarm
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
import types
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import live_guard as LG  # noqa: E402

FAILS = []
REAL = "MFFUEVR4441234"
ET = ZoneInfo("America/New_York")


def check(name, ok, info=""):
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)
    if not ok:
        FAILS.append(name)


def ts(*a):
    return int(dt.datetime(*a, tzinfo=ET).timestamp())


def acct(name, armed, ledger=None, keys=None, rules=None, why=None):
    return types.SimpleNamespace(spec={"adapter": "ninjatrader", "armed": armed, "nt_account": REAL, "name": name, "keys": keys or [],
                                       "rules": rules or {}},
                                 name=name, label=name, problem=None, adapter=object(), seen=set(), blocked=set(), hedge_wait=set(), held={},
                                 added_t=0, open_t=None, closes=[], ledger=ledger or [], disabled_reason=lambda: why)


def bot_with(accounts, entries, atlas=None, second=None, pos=None):
    return types.SimpleNamespace(running=True, cfg={"adapter": "ninjatrader"}, seen={("entry", t) for t in entries}, state={"position": pos or {}},
                                 accts=types.SimpleNamespace(accounts=accounts), acct_b=None, acct_r=atlas, acct_r2=None, kill=False,
                                 second=second or {"strategies": {}})


def pushes(bot, *nows):
    got = []
    g = LG.LiveGuard(send=lambda p: got.append(p) or "sent", state_path=os.path.join(tempfile.mkdtemp(), "lg.json"),
                     au_path=os.path.join(tempfile.mkdtemp(), "none.json"))
    for n in nows:
        g._miss_t = 0
        g.step(bot, n)
    return [p for p in got if p.get("code") == "missed"]


def main():
    e1, e2 = ts(2026, 11, 24, 3, 40), ts(2026, 11, 24, 9, 50)
    un = acct("Rapid EOD 25K", False)
    ok = acct("Zlarior 25K #2", True, ledger=[{"side": "buy", "entry_t": e1, "result": {"ok": True}}])
    b = bot_with([un], [e1], pos={"entry_t": e1, "dir": 1, "risk_usd": 420.0})
    p = pushes(b, e1 + 150)
    check("a. unarmed follower + a LIT signal -> ONE line in the owner's words (not armed, the side and time, arm it at the PC)",
          len(p) == 1 and p[0]["title"] == "Rapid EOD 25K is not armed" and "it missed Zlarior long at 03:40 ET" in p[0]["body"]
          and "Arm it at the PC" in p[0]["body"] and "~$420 risk at its size" in p[0]["body"], p)
    p = pushes(bot_with([ok], [e1]), e1 + 150)
    check("b. an armed follower that routed it -> nothing", p == [], p)
    b2 = bot_with([un], [e1, e2])
    p = pushes(b2, e1 + 150, e2 + 150, e2 + 400)
    check("c. a second signal the same day on the same unarmed account -> still ONE line", len(p) == 1, [x["body"] for x in p])
    e3 = ts(2026, 11, 25, 3, 40)
    b3 = bot_with([un], [e3])
    ms1, ms3 = LG.missed(b2, e2 + 150), LG.missed(b3, e3 + 150)
    check("c. ...and the next day gives a new key (a new line)", ms1 and ms3 and ms1[0]["key"] != ms3[0]["key"] and ms1[0]["key"].endswith(":notarmed"),
          (ms1, ms3))
    tb = ts(2026, 11, 20, 3, 45)
    rap = acct("Rapid EOD 25K", False, keys=["ema_lon_vix"], rules={"max_risk_usd": 250.0})
    b4 = bot_with([], [], atlas=rap, second={"strategies": {"ema_lon_vix": {"trades": [{"entry_t": tb, "dir": -1, "risk_usd": 600.0, "r": 6.635}]}}})
    p = pushes(b4, tb + 150)
    check("d. ATLAS on the Rapid (max $250 a trade) missing the EMA +6.6R: one line with ~+$1,659 at its size",
          len(p) == 1 and "it missed ATLAS short at 03:45 ET" in p[0]["body"] and "~+$1,659 at its size" in p[0]["body"], p)
    ref = acct("ATLAS 25K", True, keys=["ema_lon_vix"], ledger=[{"side": "sell", "entry_t": tb, "result": {"ok": False, "error": "no account"}}])
    ref.problem = None
    b5 = bot_with([], [], atlas=ref, second=b4.second)
    p = pushes(b5, tb + 150)
    check("e. other reasons keep the MISSED TRADE line (NinjaTrader refused it), with the size hint", len(p) == 1 and p[0]["title"].startswith("MISSED TRADE")
          and "refused" in p[0]["body"], p)
    allt = " ".join(x["title"] + x["body"] for x in pushes(bot_with([un], [e1]), e1 + 150))
    check("e. ids masked", REAL not in allt, allt)
    junk = types.SimpleNamespace(running=True, cfg={"adapter": "ninjatrader"}, seen={("entry", "x"), 5}, state=None, accts=None,
                                 acct_b=None, acct_r=None, acct_r2=None, second="bad")
    try:
        r = LG.missed(junk, e1 + 150)
        ok_ = isinstance(r, list)
    except Exception as e:  # noqa: BLE001
        ok_ = False
        r = e
    check("e. never raises on junk", ok_, r)
    print(f"\nmissed alarm: {'ALL PASS' if not FAILS else str(len(FAILS)) + ' FAIL'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
