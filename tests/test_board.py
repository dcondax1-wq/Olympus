"""The Board (2026-11-17, docs/BOARD.md): one event log the bot, the owner and Claude all share.
  a. engine/board_events: emit(kind, account_key, text, data=None) exactly, never raises, unknown kind -> None; order_rejected on
     "Limit 0" also logs account_locked; the privacy pass (broker id -> last 4, no PC name); BLITZ hidden
  b. account rows: plan only (ATLAS over target = PASSED), owner-typed balance ("owner, typed, date"), eval_passed / locked / funded,
     the PC's live numbers win when newer, open owner notes answered by a Claude note
  c. what travels: heartbeat "board" <= 6 KB (bot_started / bot_stopped), ntfy "brd" <= 700 bytes and back, pc_report.lite keeps it
     and stays under 3,900 bytes; POST /inbox/board (engine/day_inbox) lands on the board; /site/board/board.json on the PC
  d. tools/board.py: read is under 40 lines, says STALE plainly, shows PASSED + LOCKED; note / owner write the shared file, --answers
  e. the page: files, no innerHTML, the only write is POST /inbox/board, the model's source order (node), fixture
  f. Chromium 390 x 844: demo rows + chips, the red PC SILENT banner on a stale copy, PLAN fallback, no sideways scroll, no errors
    python -X utf8 -m tests.test_board            (BOARD_NO_BROWSER=1 skips f; run f only under flock -w 2400 /tmp/olympus_browser.lock)
"""
from __future__ import annotations

import functools
import glob
import http.server
import inspect
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
PAGE = os.path.join(WEB, "board")
RES: list = []
TMP = tempfile.mkdtemp(prefix="board_test_")
os.environ.update(LE_BOARD_DIR=os.path.join(TMP, "board"), LE_INBOX_DIR=os.path.join(TMP, "inbox"),
                  LE_BOARD_SHARED=os.path.join(TMP, "shared.jsonl"))

from engine import board_events as B  # noqa: E402

NOW = 1794960000
PLAN = {"updated": "2026-11-17", "decisions": ["Yes/no: ATLAS on the Rapid", "Send me the Rapid account name"],
        "accounts": [{"key": "zlarior", "name": "Zlarior", "plan": "MFFU Builder 50K", "stage": "eval", "status": "live",
                      "next": "Balance $49,192.78 (owner, Nov 17): about $3,807 to pass, about $1,025 of room left"},
                     {"key": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K", "stage": "eval", "status": "live",
                      "next": "Balance $26,946.10 (owner, Nov 17) = +$1,946"},
                     {"key": "rapid1", "name": "Rapid EOD", "plan": "MFFU Rapid EOD 50K", "stage": "eval", "status": "buying", "next": "Buy it"}]}


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[-700:]}"), flush=True)


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def ev_file():
    return os.path.join(TMP, "board", "events.jsonl")


def part_a():
    sig = inspect.signature(B.emit)
    check("a. emit(kind, account_key, text, data=None): the exact signature night-life calls",
          list(sig.parameters) == ["kind", "account_key", "text", "data"] and sig.parameters["data"].default is None, sig)
    r = B.emit("eval_passed", "atlas", "ATLAS passed", {"balance": 26946.1})
    rows = B.read_jsonl(ev_file())
    check("a. emit appends one line to data/board/events.jsonl (src bot, alias kept as the plan key)",
          r and len(rows) == 1 and rows[0]["kind"] == "eval_passed" and rows[0]["acct"] == "atlas" and rows[0]["src"] == "bot", rows)
    check("a. an unknown kind -> None, nothing written", B.emit("nonsense", "atlas", "x") is None and len(B.read_jsonl(ev_file())) == 1)
    check("a. aliases: lit / builder50k -> zlarior, b -> atlas", B.key_of("LIT") == "zlarior" and B.key_of("builder50k") == "zlarior" and B.key_of("b") == "atlas")
    old = os.environ["LE_BOARD_DIR"]
    blocker = os.path.join(TMP, "afile")
    open(blocker, "w").close()
    os.environ["LE_BOARD_DIR"] = os.path.join(blocker, "sub")            # a file where the folder should be: cannot write
    try:
        out = B.emit("balance", "atlas", "x", {"bad": object()})
        check("a. emit never raises (unwritable folder, odd data) -> None", out is None)
    except Exception as e:  # noqa: BLE001
        check("a. emit never raises (unwritable folder, odd data) -> None", False, e)
    os.environ["LE_BOARD_DIR"] = old
    got = B.order_rejected("atlas", "max order quantity, Limit 0, Scope MNQ")
    check("a. order_rejected on 'Limit 0' logs order_rejected AND account_locked", [g["kind"] for g in got] == ["order_rejected", "account_locked"], got)
    check("a. a plain rejection is only order_rejected", [g["kind"] for g in B.order_rejected("zlarior", "price outside the band")] == ["order_rejected"])
    pub = B.public({"accounts": [{"name": "MFFUEVBLDR000006017"}], "host": "DESKTOP-ABC", "events": [{"text": "routed to MFFUEVBLDR000006016"}]})
    s = json.dumps(pub)
    check("a. public(): broker ids cut to the last 4 digits, no PC name", "000006017" not in s and "6017" in s and "000006016" not in s and "DESKTOP-ABC" not in s, s)
    B.emit("balance", "blitz", "BLITZ balance", {"balance": 25500})
    b = B.build(plan_doc=PLAN, now=NOW)
    check("a. BLITZ (hidden) never on the board: no row, no event", not any(r["key"] == "blitz" for r in b["accounts"])
          and not any(e.get("acct") == "blitz" for e in b["events"]))


def part_b():
    open(ev_file(), "w").close()
    b = B.build(events=[], plan_doc=PLAN, now=NOW)
    rows = {r["key"]: r for r in b["accounts"]}
    z, a, r = rows["zlarior"], rows["atlas"], rows["rapid1"]
    check("b. plan only: Zlarior eval, $49,192.78, room $1,025, to pass $3,807.22, labelled PLAN (owner, Nov 17)",
          z["chip"] == "eval" and z["balance"] == 49192.78 and z["room"] == 1025 and abs(z["to_pass"] - 3807.22) < 0.01 and z["src"] == "PLAN (owner, Nov 17)", z)
    check("b. ATLAS over its $26,500 target -> PASSED even with the plan still saying eval (the miss of 2026-11-17)", a["chip"] == "PASSED" and a["to_pass"] == 0, a)
    check("b. a not-bought account is 'planned'", r["chip"] == "planned", r)
    check("b. waiting on you = accounts.json decisions", b["waiting"] == PLAN["decisions"])
    os.makedirs(os.path.join(TMP, "inbox"), exist_ok=True)
    with open(os.path.join(TMP, "inbox", "board.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": "abc123", "kind": "board", "t": NOW - 600, "text": "Zlarior 49,600.50"}) + "\n")
        fh.write(json.dumps({"id": "def456", "kind": "board", "t": NOW - 500, "text": "new funded name ends 1234 for ATLAS"}) + "\n")
    evs = B.load()
    b = B.build(events=evs, plan_doc=PLAN, now=NOW)
    rows = {r["key"]: r for r in b["accounts"]}
    z, a = rows["zlarior"], rows["atlas"]
    check("b. an owner-typed balance updates the row, marked 'owner, typed, Nov 17'", z["balance"] == 49600.5 and z["src"].startswith("owner, typed, ") and z["room"] is None, z)
    check("b. 'new funded name ends 1234 for ATLAS' -> ATLAS funded, last 4 = 1234", a["chip"] == "funded" and a["last4"] == "1234", a)
    check("b. both owner notes are open (nobody answered)", [n["id"] for n in b["open_notes"]] == ["oabc123", "odef456"], b["open_notes"])
    ans = B.make("claude_note", "", "Got both", {"answers": ["oabc123", "odef456"]}, src="claude", t=NOW - 100)
    b = B.build(events=evs + [ans], plan_doc=PLAN, now=NOW)
    check("b. a Claude note with answers closes them", b["open_notes"] == [])
    lock = [B.make("eval_passed", "atlas", "passed", {"balance": 26700}, t=NOW - 400), B.make("account_locked", "atlas", "Limit 0", t=NOW - 399)]
    b = B.build(events=lock, plan_doc=PLAN, now=NOW)
    a = {r["key"]: r for r in b["accounts"]}["atlas"]
    check("b. eval_passed + account_locked -> PASSED, locked, last event = the lock, source PC", a["chip"] == "PASSED" and a["locked"] and a["last"]["kind"] == "account_locked" and a["src"] == "PC", a)
    live = {"zlarior": {"balance": 49800, "room": 1300, "to_pass": 3200, "t": NOW - 60}}
    b = B.build(events=[B.make("balance", "zlarior", "b", {"balance": 49000}, t=NOW - 3600)], plan_doc=PLAN, live=live, now=NOW)
    z = {r["key"]: r for r in b["accounts"]}["zlarior"]
    check("b. the PC's live numbers win when newer (source 'PC live', age 1 min)", z["balance"] == 49800 and z["src"] == "PC live" and z["age_s"] == 60, z)
    b = B.build(events=[], plan_doc=PLAN, pc={"t": NOW - 3 * 86400}, now=NOW)
    check("b. a PC quiet for 3 days is stale; never reported is stale too", b["pc"]["stale"] and B.build(events=[], plan_doc=PLAN, now=NOW)["pc"]["stale"])


def part_c():
    open(ev_file(), "w").close()
    for i in range(400):
        B.emit("balance" if i % 3 else "order_rejected", "zlarior", "x" * 250, {"balance": 49000 + i, "pad": "y" * 100})
    bot = SimpleNamespace(running=True)
    B._S["running"] = None
    blk = B.hb_block(bot)
    kinds = [e["kind"] for e in blk["events"]]
    check("c. heartbeat 'board' <= 6 KB with 400 long events, public, kind olympus-board",
          len(json.dumps(blk)) <= 6000 and blk["kind"] == "olympus-board" and blk["accounts"], len(json.dumps(blk)))
    check("c. the first beat with the bot running logs bot_started", "bot_started" in kinds, kinds[:5])
    bot.running = False
    B.hb_block(bot)
    check("c. running -> stopped logs bot_stopped", B.read_jsonl(ev_file())[-1]["kind"] == "bot_stopped")
    from engine import heartbeat
    check("c. heartbeat.payload carries 'board' (engine/heartbeat._board)", '"board", _board(self.bot)' in rd(ROOT, "engine", "heartbeat.py")
          and isinstance(heartbeat._board(SimpleNamespace(running=False)), dict))
    st = B.status_block()
    ev, live = B.from_status(st)
    check("c. ntfy 'brd' <= 700 bytes, account rows + events, and back again", len(json.dumps(st)) <= 700 and st["ac"] and "zlarior" in live, json.dumps(st)[:300])
    from tools import pc_report
    snap = {"t": NOW, "hb_t": NOW - 60, "live": {}, "hb": {}, "server": True, "nt": True, "market_open": True, "mode": "paper"}
    try:
        core, exts = pc_report.posts(snap)
        lt = pc_report.merged(snap)
        check("c. the PC's status carries 'brd' in its ext post (le-live-ext, merged back), every post under 3,900 bytes",
              "brd" in lt and "brd" not in core and all(len(json.dumps(x, separators=(",", ":"))) <= 3900 for x in [core, *exts]), list(lt))
        from tools import board as T
        msgs = [{"event": "message", "time": NOW, "message": json.dumps(x)} for x in [*exts, core]]
        nd = "\n".join(json.dumps(m) for m in msgs)
        from tools import status_sign as _S                  # the merge, with no key pinned (day-guard2 pinned the PC's vk; these
        _real_vk = _S.feed_vk                                # test posts are unsigned and would be dropped, as they should)
        _S.feed_vk = lambda path=None: None
        try:
            got = T.fetch_lite(get=lambda url: (200, nd))
            old = T.fetch_lite(get=lambda url: (200, json.dumps({"event": "message", "time": NOW, "message": json.dumps(lt)})))
            pinned_drop = None
        finally:
            _S.feed_vk = _real_vk
        pinned_drop = T.fetch_lite(get=lambda url: (200, nd))
        check("c. with the PC's vk pinned (status_feed.json), the same unsigned posts are NOT believed", pinned_drop is None, pinned_drop)
        check("c. tools/board.py fetch_lite: core + ext merged ('brd' back at the top); the old single post still read as it was",
              got and got.get("brd") == lt["brd"] and got["t"] == core["t"] and old == lt and T.fetch_lite(get=lambda url: (500, "")) is None,
              (list(got or {}), list(old or {})))
    except Exception as e:  # noqa: BLE001
        check("c. the PC's status carries 'brd' (ext post) and fetch_lite merges it", False, e)
    try:
        from engine import day_inbox as DI
    except Exception as e:  # noqa: BLE001
        print(f"[SKIP] c. POST /inbox/board (fastapi missing: {e})")
        return
    st, out = DI.accept("board", b'{"text": "ATLAS balance 26,946.10 passed"}', "application/json", {"X-Olympus-Inbox": "1"}, now_s=NOW)
    a = {r["key"]: r for r in B.build(plan_doc=PLAN, now=NOW)["accounts"]}["atlas"]
    check("c. POST /inbox/board (day_inbox kind 'board') -> 200, data/inbox/board.jsonl, on the board as an owner note",
          st == 200 and out.get("ok") and "board" in out.get("said", "").lower() and a["balance"] == 26946.1 and a["src"].startswith("owner, typed"), (st, out, a))
    st2, _ = DI.accept("board", b'{"text": ""}', "application/json", {"X-Olympus-Inbox": "1"}, now_s=NOW)
    check("c. an empty note is refused (400)", st2 == 400)
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from engine import live_site
        app = FastAPI()
        live_site.install(app)
        c = TestClient(app, client=("127.0.0.1", 50000), base_url="http://localhost")
        r = c.get("/site/board/board.json")
        j = r.json()
        check("c. /site/board/board.json on the PC: the live board (X-Olympus-Source live)",
              r.status_code == 200 and j.get("kind") == "olympus-board" and r.headers.get("x-olympus-source") == "live", (r.status_code, str(j)[:200]))
    except Exception as e:  # noqa: BLE001
        check("c. /site/board/board.json on the PC: the live board", False, e)


def part_d():
    open(ev_file(), "w").close()
    from tools import board as T
    old = {"present": True, "t": NOW - 10 * 86400, "board": {"events": [B.make("account_locked", "atlas", "Order rejected: Limit 0", t=NOW - 10 * 86400)],
                                                           "accounts": []}}
    T.B.plan = lambda path=None: PLAN                                     # the test plan and no published copy, not the repo's
    T.published = lambda: {}
    T.fetch_lite = lambda get=None: None                                 # fully offline: never the real ntfy feed / heartbeat branch
    T.fetch_hb = lambda remotes=None: {"present": False, "reason": "test: offline"}
    open(os.path.join(TMP, "inbox", "board.jsonl"), "w").close()
    b = T.gather(offline=False, hb=old, lite=None, now=NOW)
    ls = T.lines(b, now=NOW)
    txt = "\n".join(ls)
    check("d. read: under 40 lines, STALE / PC SILENT said plainly, every account, the lock event, the decisions",
          len(ls) <= 40 and "STALE" in txt and "PC SILENT" in txt and "Zlarior" in txt and "ATLAS" in txt and "account_locked" in txt and "Rapid" in txt
          and "WAITING ON THE OWNER" in txt, txt)
    check("d. ATLAS shows PASSED + LOCKED", re.search(r"ATLAS \| .*PASSED \+ LOCKED", txt), txt)
    fresh = T.gather(offline=False, hb={"present": True, "t": NOW - 120, "board": {}}, lite=None, now=NOW)
    check("d. a fresh heartbeat says fresh", ": fresh" in T.lines(fresh, now=NOW)[0], T.lines(fresh, now=NOW)[0])
    lite = {"kind": "le-live", "t": NOW - 90, "reporter": {"t": NOW - 30},
            "board": {"t": NOW - 90, "lit": {"balance": 49900, "room": 1400, "to_target": 3100}},
            "brd": {"t": NOW - 90, "ac": [["atlas", "PASSED", 26946, None, 0, 1]], "ev": [[NOW - 95, "eval_passed", "atlas", "ATLAS passed"]]}}
    b = T.gather(offline=False, hb={"present": False, "reason": "no heartbeat branch"}, lite=lite, now=NOW)
    z = {r["key"]: r for r in b["accounts"]}["zlarior"]
    check("d. the ntfy feed alone: PC fresh via ntfy, Zlarior's live card, the pass event", b["pc"]["via"] == "ntfy" and not b["pc"]["stale"]
          and z["balance"] == 49900 and any(e["kind"] == "eval_passed" for e in b["events"]), (b["pc"], z))
    # finder round 2026-11-20: a STOPPED bot (pc.running false, the paper adapter) posts its paper twin's numbers (room $1,771 vs the real $1,025):
    # the read keeps the last LIVE numbers (the PC's board rows) and says so in its header
    stp = {**lite, "pc": {"running": False, "adapter": "paper"}, "board": {"t": NOW - 90, "lit": {"balance": 49938, "room": 1771, "to_target": 3062}}}
    bs = T.gather(offline=False, hb={"present": True, "t": NOW - 120, "board": {"accounts": [{"key": "zlarior", "src": "PC live", "balance": 49192.78, "room": 1024.58,
                                                                                            "to_pass": 3807.22, "src_t": NOW - 4000}]}}, lite=stp, now=NOW)
    zs = {r["key"]: r for r in bs["accounts"]}["zlarior"]
    head = T.lines(bs, now=NOW)[0]
    check("d. a stopped bot's paper numbers ($49,938, room $1,771) are not taken: the last LIVE ones ($49,192.78, room $1,024.58) stay, the header says 'BOT STOPPED: PAPER NUMBERS'",
          zs["balance"] == 49192.78 and zs["room"] == 1024.58 and "BOT STOPPED: PAPER NUMBERS" in head and T.bot_stopped(lite) == "", (zs, head))
    part_d_funded(T)
    shared = os.environ["LE_BOARD_SHARED"]
    T.write_note("ATLAS 26,946.10 passed, ends 6017 MFFUEVBLDR000006017", kind="owner_note", acct="atlas", src="owner", via="chat", now=NOW - 50)
    T.write_note("Noted", now=NOW - 40, answers=["x1"])
    rows = B.read_jsonl(shared)
    check("d. note / owner write data/board/shared.jsonl, privacy-cleaned (no full broker id), owner via chat = answered",
          len(rows) == 2 and rows[0]["src"] == "owner" and "000006017" not in json.dumps(rows) and rows[1]["data"]["answers"] == ["x1"]
          and B.open_notes(rows) == [], rows)
    out = os.path.join(TMP, "pub", "board.json")
    T.publish(T.gather(offline=True, now=NOW), path=out)
    j = json.loads(rd(out))
    check("d. publish writes the safe copy (kind olympus-board, no 'sources')", j["kind"] == "olympus-board" and "sources" not in j and j["events"], list(j))
    check("d. STATE.md starts every chat with python tools/board.py read", "python tools/board.py read" in rd(ROOT, "STATE.md")[:600])
    check("d. data/board/shared.jsonl is tracked, events.jsonl ignored", subprocess.run(["git", "check-ignore", "-q", "data/board/events.jsonl"], cwd=ROOT).returncode == 0
          and subprocess.run(["git", "check-ignore", "-q", "data/board/shared.jsonl"], cwd=ROOT).returncode == 1)


# the PC feed of 2026-11-18 (trimmed): Zlarior 50K eval (lit card + accounts mffu50k_eval), the NEW Builder 25K eval b25k_2 and
# ATLAS's FUNDED 25K (board.atlas, status funded), while the PC's own brd still says ATLAS PASSED + locked (an old owner note)
LITE_FUNDED = {"kind": "le-live", "t": NOW - 60, "reporter": {"t": NOW - 30},
               "board": {"t": NOW - 60, "data_t": NOW - 60,
                         "lit": {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "balance": 49192.78, "floor": 48168.2, "room": 1024.58,
                                 "to_target": 3807.22, "status": "open"},
                         "atlas": {"id": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K funded", "balance": 25000.0, "floor": 24000.0,
                                   "room": 1000.0, "to_target": 1850.0, "status": "funded"}},
               "accounts": [{"id": "mffu50k_eval", "name": "MFFU 50K Eval", "plan": "Builder 50K", "kind": "eval", "source": "pc",
                             "eval": {"start_balance": 50000.0, "balance": 49192.78, "floor": 48168.2, "room": 1024.58, "to_target": 3807.22, "status": "open"}},
                            {"id": "b25k_2", "name": "Zlarior Builder 25K #2", "plan": "Builder 25K", "kind": "eval", "source": "pc",
                             "eval": {"start_balance": 25000.0, "balance": 25000.0, "floor": 24000.0, "room": 1000.0, "to_target": 1500.0, "status": "open"}}],
               "brd": {"t": NOW - 30, "ac": [["zlarior", "eval", 49193, 1025, 3807, 0], ["atlas", "PASSED", 26946, None, 0, 1]], "ev": [], "on": 0}}
PLAN_PC = {**PLAN, "accounts": [{**PLAN["accounts"][0], "pc": ["mffu50k_eval", "lit"]},
                                {**PLAN["accounts"][1], "plan": "MFFU Builder 25K (funded)", "stage": "funded", "pc": ["atlas", "acct_b"],
                                 "next": "Funded since Nov 17 night"},
                                PLAN["accounts"][2],
                                {"key": "fresh25", "name": "Zlarior 25K #2", "plan": "MFFU Builder 25K", "stage": "eval", "status": "live",
                                 "pc": ["b25k_2"], "match": "builder25k"}]}


def part_d_funded(T):
    """2026-11-18 bug: the new 25K eval (b25k_2) landed on ATLAS's row as "locked" and ATLAS's funded 25K was invisible."""
    old_plan = T.B.plan
    owner = B.make("owner_note", "atlas", "ATLAS balance $26,946.10: passed. Account locked: Limit 0", {"balance": 26946.1, "stage": "passed", "locked": True},
                   src="owner", t=NOW - 3 * 3600)
    for plan, label in ((PLAN_PC, "plan with pc ids"), (PLAN, "old plan without pc ids")):
        T.B.plan = lambda path=None, _p=plan: _p
        b = T.gather(offline=False, hb={"present": False, "reason": "offline"}, lite=LITE_FUNDED, now=NOW)
        rows = {r["key"]: r for r in b["accounts"]}
        a = rows.get("atlas") or {}
        z = rows.get("zlarior") or {}
        n25 = rows.get("fresh25" if plan is PLAN_PC else "b25k_2") or {}
        check(f"d. ({label}) ATLAS = its FUNDED 25K, not locked, from the PC (not the 25K eval, not the old owner note)",
              a.get("stage") == "funded" and a.get("chip") == "funded" and not a.get("locked") and a.get("balance") == 25000 and a.get("src") == "PC live", a)
        check(f"d. ({label}) the new 25K eval has its OWN row (eval, $25,000, $1,500 to pass)",
              n25.get("chip") == "eval" and n25.get("balance") == 25000 and n25.get("to_pass") == 1500 and n25.get("src") == "PC live", n25)
        check(f"d. ({label}) Zlarior 50K once (lit card + mffu50k_eval = one row), no duplicate",
              z.get("balance") == 49192.78 and "mffu50k_eval" not in rows and sum(1 for r in b["accounts"] if r.get("balance") == 49192.78) == 1, list(rows))
        txt = "\n".join(T.lines(b, now=NOW))
        check(f"d. ({label}) read: the plan-only Rapid row says PLAN ONLY", re.search(r"Rapid EOD \| .*PLAN ONLY", txt), txt)
    b = T.gather(offline=False, hb={"present": False, "reason": "offline"}, lite=LITE_FUNDED, now=NOW)
    T.B.plan = old_plan
    # a stale owner-typed row is replaced by fresher PC data; an old feed does not beat a newer owner note
    open(ev_file(), "a").write(json.dumps(owner) + "\n")
    b = T.gather(offline=False, hb={"present": False, "reason": "offline"}, lite=LITE_FUNDED, now=NOW)
    a = {r["key"]: r for r in b["accounts"]}["atlas"]
    check("d. the owner's older typed 'ATLAS passed, locked' is replaced by the PC's fresher funded numbers", a["balance"] == 25000 and a["stage"] == "funded"
          and not a["locked"], a)
    open(ev_file(), "w").close()
    silent = T.gather(offline=False, hb={"present": False, "reason": "offline"}, lite={**LITE_FUNDED, "t": NOW - 86400, "reporter": {"t": NOW - 86400},
                                                                                      "board": {**LITE_FUNDED["board"], "t": NOW - 86400, "data_t": NOW - 86400}}, now=NOW)
    check("d. a day-old feed says STALE, PC SILENT", "PC SILENT" in T.lines(silent, now=NOW)[0], T.lines(silent, now=NOW)[0])


def node(body):
    script = ("const M = require(" + json.dumps(os.path.join(PAGE, "boardmodel.js")) + "); const out = (x) => console.log('@@' + JSON.stringify(x));\n"
              "try { " + body + " } catch (e) { console.log('@@' + JSON.stringify({ error: String(e && e.stack || e) })); }")
    p = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    m = [ln for ln in p.stdout.splitlines() if ln.startswith("@@")]
    return json.loads(m[-1][2:]) if m else {"error": (p.stderr or p.stdout)[-400:]}


def part_e():
    files = set(os.listdir(PAGE))
    need = {"index.html", "board.js", "boardmodel.js", "board.css", "fixture.json", "manifest.webmanifest", "icon.svg", "jarvis.json"}
    check("e. the app folder has every file", need <= files, need - files)
    html = rd(PAGE, "index.html")
    js = rd(PAGE, "board.js") + rd(PAGE, "boardmodel.js")
    check("e. AGORA look: data-theme agora, the kit's agora css, viewport-fit=cover, title Board", 'data-theme="agora"' in html and "agora.css" in html
          and "viewport-fit=cover" in html and "<title>Board</title>" in html)
    check("e. no innerHTML / insertAdjacentHTML / document.write, no outside address", not re.search(r"innerHTML|insertAdjacentHTML|document\.write", js)
          and not re.search(r"https?://", js) and not re.search(r'(src|href)="https?://', html))
    posts = re.findall(r"method:\s*'([A-Z]+)'", js)
    check("e. the only write is POST /inbox/board with the X-Olympus-Inbox header", posts == ["POST"] and "'/inbox/board'" in js and "'X-Olympus-Inbox': '1'" in js, posts)
    fx = json.loads(rd(PAGE, "fixture.json"))
    check("e. fixture.json is a demo board (kind olympus-board, demo, accounts + events)", fx.get("kind") == "olympus-board" and fx.get("demo") and fx["accounts"] and fx["events"])
    pub = json.loads(rd(PAGE, "board.json")) if os.path.isfile(os.path.join(PAGE, "board.json")) else {}
    check("e. the published board.json has no full broker id and no BLITZ", not re.search(r"[A-Z]{3,}\d{6,}", json.dumps(pub)) and "blitz" not in json.dumps(pub).lower())
    n = 1794960000
    r = node(f"""
      const plan = {json.dumps(PLAN)}; const now = {n};
      const site = {{ kind: 'olympus-board', src: 'pc', t: now - 30, pc: {{ t: now - 30 }}, accounts: [{{ key: 'zlarior', chip: 'eval' }}], events: [] }};
      const copy = {{ ...site, src: 'cloud', t: now - 7200, pc: {{ t: now - 86400 * 10 }} }};
      const lite = {{ kind: 'le-live', t: now - 60, reporter: {{ t: now - 60 }}, brd: {{ t: now - 60, ac: [['atlas', 'PASSED', 26946, null, 0, 1], ['blitz', 'eval', 1, 1, 1, 0]], ev: [[now - 70, 'eval_passed', 'atlas', 'ATLAS passed']] }} }};
      const fx = {{ kind: 'olympus-board', accounts: [], events: [] }};
      const a = M.pick({{ site, lite, plan, fixture: fx }}, now), b = M.pick({{ site: copy, lite, plan }}, now), c = M.pick({{ site: copy, plan }}, now);
      const d = M.pick({{ plan }}, now), e = M.pick({{ fixture: fx }}, now), f = M.pick({{ site, fixture: fx, demo: true }}, now);
      const pb = M.planBoard(plan, now);
      out({{ a: a.mode + a.board.src, b: b.mode, bAt: (b.board.accounts.find((x) => x.key === 'atlas') || {{}}).chip, bBl: b.board.accounts.some((x) => x.key === 'blitz'),
             bEv: b.board.events.length, c: c.mode, cSil: M.silent(c.board, now).silent, d: d.mode, d0: d.board.accounts[1].chip, dS: d.board.accounts[0].src,
             e: e.mode, f: f.mode, aSil: M.silent(a.board, now).silent, nS: M.silent({{ pc: {{}} }}, now).text, rp: pb.accounts[2].chip }});
    """)
    check("e. source order: PC fresh > ntfy fresh (laid over the copy) > published copy > PLAN > demo; ?demo=1 forces the fixture",
          r.get("a") == "pcpc" and r.get("b") == "pc" and r.get("c") == "copy" and r.get("d") == "plan" and r.get("e") == "demo" and r.get("f") == "demo", r)
    check("e. the ntfy cut lays ATLAS PASSED + the event in, BLITZ never", r.get("bAt") == "PASSED" and r.get("bBl") is False and r.get("bEv") == 1, r)
    check("e. silent: an old copy and never-reported are silent, a fresh PC is not", r.get("cSil") is True and r.get("aSil") is False and "no report from your PC in the last 12 hours" in str(r.get("nS")), r)
    check("e. PLAN rows: ATLAS over target = PASSED, owner date kept, a not-bought account planned", r.get("d0") == "PASSED" and r.get("dS") == "PLAN (owner, Nov 17)"
          and r.get("rp") == "planned", r)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def part_f():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        print(f"[SKIP] f. browser (playwright missing: {e})")
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/board/"
    now = int(time.time())
    stale = {"v": 1, "kind": "olympus-board", "t": now - 3600, "src": "cloud", "pc": {"t": now - 10 * 86400, "via": "heartbeat", "stale": True},
             "accounts": [{"key": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K", "chip": "PASSED", "stage": "passed", "balance": 26946.1, "locked": True,
                           "src": "owner, typed, Nov 17", "src_t": now - 3600, "last": {"t": now - 3600, "kind": "account_locked", "text": "Limit 0"}}],
             "events": [{"id": "e1", "t": now - 3600, "kind": "account_locked", "acct": "atlas", "text": "Order rejected: Limit 0", "src": "bot"}],
             "open_notes": [], "waiting": ["Send me the funded account name"]}
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            ctx = br.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
            p = ctx.new_page()
            p.set_default_timeout(30000)
            errs = []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.route("**/ntfy.sh/**", lambda r: r.fulfill(status=200, body=""))
            p.goto(base + "?demo=1")
            p.wait_for_function("window.BOARD && window.BOARD.last")
            chips = p.eval_on_selector_all(".brow .chip", "els => els.map(e => e.textContent)")
            wide = p.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
            hid = p.evaluate("document.getElementById('silent').hidden")
            check("f. 390 px demo: account rows with chips, the feed, no sideways scroll, no banner in demo",
                  "eval" in chips and len(p.query_selector_all(".feed .ev")) >= 3 and wide and hid, (chips, wide, hid))
            p2 = ctx.new_page()
            p2.on("pageerror", lambda e: errs.append(str(e)))
            p2.route("**/ntfy.sh/**", lambda r: r.fulfill(status=200, body=""))
            p2.route("**/board/board.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(stale)))
            p2.goto(base)
            p2.wait_for_function("window.BOARD && window.BOARD.last")
            ban = p2.evaluate("(() => { const b = document.getElementById('silent'); const r = b.getBoundingClientRect(); return { hidden: b.hidden, h: r.height, bg: getComputedStyle(b).backgroundColor, t: b.textContent }; })()")
            row = p2.text_content(".brow")
            wide2 = p2.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
            check("f. a stale copy: the big red PC SILENT banner, ATLAS PASSED + locked, $26,946, no sideways scroll with the long label",
                  not ban["hidden"] and ban["h"] > 60 and "PC SILENT" in ban["t"] and "PASSED" in row and "locked" in row and "$26,946" in row and wide2, (ban, row, wide2))
            p3 = ctx.new_page()
            p3.on("pageerror", lambda e: errs.append(str(e)))
            p3.route("**/ntfy.sh/**", lambda r: r.fulfill(status=200, body=""))
            p3.route("**/board/board.json*", lambda r: r.fulfill(status=404, body="no"))
            p3.goto(base)
            p3.wait_for_function("window.BOARD && window.BOARD.last")
            mode = p3.text_content("#mode")
            p3.fill("#noteText", "ATLAS passed")
            p3.click("#noteForm button")
            p3.wait_for_function("document.getElementById('noteSay').textContent.length > 12")
            say = p3.text_content("#noteSay")
            check("f. no board copy -> PLAN rows from accounts.json; a note off the PC link says where it works",
                  "PLAN" in mode and len(p3.query_selector_all(".brow")) >= 2 and "PC link" in say, (mode, say))
            check("f. no page errors", not errs, errs)
            br.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    part_b()
    part_c()
    part_d()
    part_e()
    if not os.environ.get("BOARD_NO_BROWSER"):
        part_f()
    n = sum(RES)
    print(f"\nboard: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
