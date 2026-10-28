"""The narrator (engine/narrator.py): plain-language feed from the bot's state, read-only, pushes only the important kinds.
Fake bot + synthetic Brain / ledger / ATLAS / account B, every file in a temp dir; never reads or writes real data/ files.

  python -X utf8 -m tests.test_narrator        # ~1 s
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import sys
import tempfile
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import narrator as N  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:400]}"), flush=True)


def T(h, m, day=(2026, 10, 14)):
    return int(dt.datetime(*day, h, m, tzinfo=ET).timestamp())


def brain(day="2026-10-14"):
    return {"day": day, "at": "Wed 05:45 ET", "stage": {"key": "trade", "label": "In trade", "n": 9, "waiting": "In a SHORT trade"},
            "setups": [{"id": "10018:-1", "t": T(4, 55), "dir": -1, "side": "SHORT", "status": "filled", "cisd": 30797.25,
                        "plan": {"limit": 30797.25, "stop": 30862.0, "target": 30495.31, "armed_t": T(4, 55), "expires_t": T(5, 25)}},
                       {"id": "9996:1", "t": T(3, 5), "dir": 1, "side": "LONG", "status": "rejected", "rule": "idm"}],
            "log": [  # newest first, as engine/brain.py keeps it
                {"key": "entry:%d" % T(5, 24), "t": T(5, 24), "kind": "entry", "text": "✓ SHORT LIT @ 30,785.75 qty 1"},
                {"key": "sweep:10024:low", "t": T(5, 20), "kind": "sweep", "text": "Swept equal lows 30,773 (0.05 ATR deep; ✗ LIT needs 0.5)"},
                {"key": "armed:10018:-1", "t": T(4, 55), "kind": "armed", "text": "✓ Setup armed: SHORT limit 30,797.25, stop 30,862"},
                {"key": "cisd:10018:-1", "t": T(4, 55), "kind": "cisd", "text": "5m CISD down closed at 30,797.25"},
                {"key": "expired:10000:-1", "t": T(3, 55), "kind": "expired", "text": "SHORT limit 30,783.75 did not fill"},
                {"key": "reject:9996:1", "t": T(3, 5), "kind": "rejected", "text": "✗ LONG setup rejected: no inducement swing taken first"},
                {"key": "sweep:9996:high", "t": T(3, 0), "kind": "sweep", "text": "Swept Frankfurt high 30,804.75 (1.01 ATR deep; deep enough: ✓)"},
                {"key": "box:lon23", "t": T(3, 0), "kind": "box", "text": "Frankfurt box closed"}]}


class AB:
    def __init__(self, rows):
        self.rows = rows

    def info(self, now=None):
        return {"label": "ATLAS MFFU-25K", "routed": self.rows, "open": None, "day_pnl": -120.0, "entries_today": 1}


def bot(now, ledger=None, **kw):
    b = SimpleNamespace(running=True, kill=False, cfg={"adapter": "ninjatrader"}, state={"price": 30791.0}, brain=brain(),
                        second=None, acct_b=None, ledger=list(ledger or []), log=[], health={"stale": False, "market_open": True},
                        _open_routed=None, _open_qty=None, _open_src=None, adapter=None, clock=lambda: now)
    b._push_account = lambda: "MFFU 50K"
    b._broker_stop = lambda t: None
    for k, v in kw.items():
        setattr(b, k, v)
    return b


def main():
    now = T(5, 45)
    et_ = T(5, 24)
    led = [{"t": et_ + 3, "side": "sell", "qty": 7, "entry": 30785.75, "stop": 30862.0, "target": 30495.31, "entry_t": et_,
            "result": {"ok": True, "legs": [{"fill_px": 30786.0}]}},
           {"t": T(5, 50), "side": "modify", "qty": 7, "stop": 30784.5, "reason": "BE", "entry_t": et_, "result": {"ok": True}},
           {"t": T(6, 30), "side": "exit", "qty": 7, "reason": "TARGET", "pnl": 4062.5, "entry_t": et_, "result": {"ok": True}},
           {"t": T(9, 31), "side": "buy", "qty": 3, "entry": 30500.0, "stop": 30460.0, "target": 30700.0, "entry_t": T(9, 31) - 3,
            "result": {"ok": False, "error": "account does not exist C:\\Users\\x\\Documents\\NinjaTrader 8\\incoming"}}]
    b = bot(T(9, 40), led)
    before = copy.deepcopy((b.ledger, b.state, b.brain))
    nar = N.Narrator()
    new = nar.observe(b, push=False)
    by = {}
    for m in new:
        by.setdefault(m["kind"], []).append(m)
    check("brain log: deep sweep = swept info, shallow = dim", any(m["level"] == "info" for m in by.get("swept", [])) and
          any(m["level"] == "dim" for m in by.get("swept", [])), by.get("swept"))
    ar = (by.get("armed") or [{}])[0]
    check("armed: push key = alerts_plus key armed:<arm_t>:<dir>", ar.get("push_key") == f"armed:{T(4, 55)}:-1", ar)
    check("expired / rejected / box / cisd narrated", all(by.get(k) for k in ("expired", "rejected", "box", "cisd")), list(by))
    check("rejected says why", "inducement" in by["rejected"][0]["text"], by["rejected"])
    check("brain model entry skipped when the real ledger has it", not by.get("model"), by.get("model"))
    sent, ent = by.get("sent", []), by.get("entry", [])
    check("order sent + FILLED with the real fill and micros", sent and ent and ent[0]["qty"] == 7 and ent[0]["fill"] == 30786.0
          and "7 MNQ at 30,786" in ent[0]["text"], ent)
    check("filled shows the real $ at the stop / target", "-$1,064" in ent[0]["text"] and "+$4,070" in ent[0]["text"], ent[0]["text"])
    check("stop moved to breakeven", by.get("be") and "30,784.5" in by["be"][0]["text"], by.get("be"))
    ex = (by.get("exit") or [{}])[0]
    check("exit: real booked $ + micros + reason words", ex.get("usd") == 4062.5 and "+$4,062" in ex.get("text", "") and
          "hit the target" in ex.get("text", "").lower() and ex.get("dir") == -1, ex)
    rf = (by.get("refused") or [{}])[0]
    check("refused order: NinjaTrader's reason, path removed", rf.get("level") == "bad" and "account does not exist" in rf.get("text", "")
          and "Users" not in rf.get("text", ""), rf)
    check("read-only: ledger / state / brain unchanged", copy.deepcopy((b.ledger, b.state, b.brain)) == before)
    check("second look: nothing new (stable keys)", nar.observe(b) == [])
    f = nar.feed(100)
    check("feed newest first, ids unique", f[0]["t"] >= f[-1]["t"] and len({m["id"] for m in f}) == len(f), [m["t"] for m in f[:3]])
    check("feed filter by strategy", all(m["strat"] == "lit" for m in nar.feed(100, strat="lit")))
    after = f[0]["id"]
    check("feed after=<id> -> only newer", nar.feed(100, after=after) == [])

    # model trade (no routed order): shown as model, no size
    b2 = bot(now)
    m2 = N.Narrator().observe(b2)
    md = [m for m in m2 if m["kind"] == "model"]
    check("model entry without a routed order: kind model, no size claimed", md and "nothing was sent" in md[0]["text"], md)

    # feed stale episode + kill
    b3 = bot(now)
    n3 = N.Narrator()
    n3.observe(b3)
    b3.health = {"stale": True, "data_age_s": 300, "market_open": True}
    s1 = [m for m in n3.observe(b3, now + 60) if m["kind"] == "stale"]
    s2 = [m for m in n3.observe(b3, now + 120) if m["kind"] == "stale"]
    b3.health = {"stale": False}
    s3 = [m for m in n3.observe(b3, now + 400) if m["kind"] == "fresh"]
    check("FEED STALE once per episode, then feed back", len(s1) == 1 and not s2 and len(s3) == 1 and "5 min" in s1[0]["text"], (s1, s2, s3))
    b3.kill = True
    check("kill switch narrated", any(m["kind"] == "kill" for m in n3.observe(b3, now + 500)))

    # daily summary (16:05-17:00 ET)
    b4 = bot(T(16, 10), led)
    sm = [m for m in N.Narrator().observe(b4) if m["kind"] == "summary"]
    check("daily summary after the flat with real $", sm and "+$4,062" in sm[0]["text"] and "1 trade" in sm[0]["text"], sm)
    check("no summary during the session", not [m for m in N.Narrator().observe(bot(T(11, 0), led)) if m["kind"] == "summary"])

    # account B + ATLAS paper + Asia slot + candidates
    ab_rows = [{"t": T(9, 35), "side": "buy", "qty": 4, "entry_t": T(9, 35), "strategy": "EMA", "stop": 30400.0, "target": 30600.0, "ok": True},
               {"t": T(10, 5), "side": "exit", "qty": 4, "entry_t": T(9, 35), "strategy": "EMA", "pnl": -120.0, "reason": "STOP", "ok": True}]
    sec = {"t": T(9, 40), "day": "2026-10-14", "strategies": {
        "ema_lon_vix": {"short": "EMA", "on": True, "state": {"stage": "armed", "text": "Armed long"}, "trades": [],
                        "brain": {"log": [{"t": T(9, 20), "ok": False, "text": "09:20 CISD short: no - pull"}]}},
        "lit_asia": {"short": "LIT+Asia", "on": True, "state": {"stage": "waiting", "text": "LIT: watching"}, "trades": []},
        "sh_asia": {"short": "Asia hunt", "on": True, "candidate": True, "state": {"stage": "armed", "text": "x"}, "trades": []}}}
    b5 = bot(T(9, 40), acct_b=AB(ab_rows), second=sec)
    m5 = N.Narrator().observe(b5)
    at = [m for m in m5 if m["strat"] == "atlas"]
    check("account B: entry + exit with real $ on the ATLAS layer", any(m["kind"] == "exit" and m["usd"] == -120.0 and "ATLAS MFFU-25K" in m["title"] for m in at)
          and any(m["kind"] == "sent" for m in at), [(m["kind"], m["title"]) for m in at])
    check("ATLAS member stage + decision log (paper)", any("ATLAS EMA · armed" in m["title"] for m in at) and any("(paper)" in m["title"] for m in at))
    check("Asia slot = Zlarior paper, candidates off the feed", any(m["strat"] == "lit" and "Zlarior paper LIT+Asia" in m["title"] for m in m5)
          and not any("Asia hunt" in m["title"] for m in m5))

    # pushes: only armed / entry / exit / refused by default, fresh events only
    sent_p = []
    b6 = bot(T(9, 40), led)
    b6.brain = {**brain(), "log": [{"key": "armed:x:-1", "t": T(9, 39), "kind": "armed", "text": "✓ Setup armed: SHORT"},
                                   {"key": "sweep:y", "t": T(9, 39), "kind": "sweep", "text": "Swept PDH (1.0 ATR deep; deep enough: ✓)"}]}
    N.Narrator().observe(b6, push=True, send=lambda m, bb: sent_p.append(m["kind"]) or True)
    check("default pushes: armed + refused (fresh); swept / old fill / be not pushed", sorted(sent_p) == ["armed", "refused"], sent_p)
    tmp = tempfile.mkdtemp(prefix="le_narr_")
    cfg = os.path.join(tmp, "narrator.json")
    json.dump({"push": {"swept": True, "armed": False}}, open(cfg, "w"))
    pf = N.push_prefs(cfg)
    check("data/narrator.json overrides (temp file)", pf["swept"] and not pf["armed"] and pf["entry"], pf)
    os.environ["LE_NARRATOR_PUSH"] = "0"
    check("LE_NARRATOR_PUSH=0 -> every push off", not any(N.push_prefs(cfg).values()))
    os.environ.pop("LE_NARRATOR_PUSH")
    check("default prefs = exactly armed, entry, exit, refused", sorted(k for k, v in N.push_prefs(os.path.join(tmp, "none.json")).items() if v)
          == ["armed", "entry", "exit", "refused"])

    # payloads reuse the bot's push keys (one notice per event on the phone)
    p, r = N.payload_for({"kind": "entry", "entry_t": 111, "dir": -1, "qty": 7, "fill": 1.0, "strat": "lit", "t": 112}, "MFFU 50K")
    check("entry payload = push.entry_payload, key fill:<entry_t>", p["key"] == "fill:111" and p["kind"] == "fill" and r == "notify" and "7 MNQ" in p["body"], p)
    p, r = N.payload_for({"kind": "exit", "entry_t": 111, "dir": -1, "usd": 812.0, "reason": "TARGET", "t": 200}, "MFFU 50K")
    check("exit payload = push.outcome_payload, key out:<entry_t>", p["key"] == "out:111" and p["kind"] == "outcome" and "SHORT" in p["title"], p)
    p, r = N.payload_for({"kind": "armed", "key": "lit:armed:1", "push_key": "armed:5:-1", "title": "x", "text": "y", "t": 5})
    check("armed payload key = alerts_plus key, via alerts_plus.pc_send", p["key"] == "armed:5:-1" and r == "plus", p)

    # persistence (temp dir): restore, no duplicates
    nd = N.Narrator(log_dir=tmp)
    k1 = nd.observe(bot(now, led[:1]))
    nd2 = N.Narrator(log_dir=tmp)
    k2 = nd2.observe(bot(now, led[:1]))
    check("today's file restores the feed after a restart (no repeats)", k1 and not k2 and len(nd2.feed(400)) == len(nd.feed(400)), (len(k1), len(k2)))
    check("files only under the temp dir", os.path.exists(os.path.join(tmp, "2026-10-14.jsonl")))
    check("the global narrator writes no file until tick() (real bot)", N.NARRATOR.log_dir is None)

    # never raises
    check("observe on a broken bot -> []", N.Narrator().observe(object()) == [])
    check("lit_window: weekend -> next Monday 02:00", N.lit_window(T(12, 0, (2026, 10, 17)))["label"].startswith("Next entry window Mon"))
    src = open(os.path.join(ROOT, "engine", "live.py"), encoding="utf-8").read()
    i = src.index("def _alerts_tick")
    body = src[i:src.index("def _push_account")]
    check("wired in LiveBot._alerts_tick (real bot only, inside try)", "narrator.tick(self, now)" in body and "if self.state_path != STATE_PATH" in body)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
