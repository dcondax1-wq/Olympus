"""Alerts plus (engine/alerts_plus.py): "setup armed" / "expired" pushes (de-duplicated per setup), critical alerts that repeat
every 10 min until "Got it" or until they clear, the stale-cloud alarm window, the PC-vs-cloud rules fingerprint, the on /
silent / off levels, the relay messages, the ops-tick and cloud hooks, and static checks of the bot / heartbeat / phone
wiring. No network, nothing written outside a temp dir.

  python -X utf8 -m tests.test_alerts_plus
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import tempfile
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from engine import alerts_plus as ap, push

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:300]})" if detail and not cond else ""))


def ts(y, mo, d, h=0, mi=0):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def setups_state(arm, tapped=None, d="long", limit=29842.0, stop=29807.5, target=30118.0):
    return {"setups": {d: {"arm_t": arm, "limit": limit, "stop": stop, "target": target, "expires_t": arm + 1800,
                           "tapped_t": tapped, "pools": ["Asia low"], "waiting": "1m CISD" if tapped else "limit fill"}}}


def test_setups():
    arm = ts(2026, 10, 21, 2, 45)
    prev, p = ap.setup_step(None, setups_state(arm), arm + 30, size_fn=lambda tr: 6, src="PC")
    check("armed: one push when the limit arms", len(p) == 1 and p[0]["key"] == f"armed:{arm}:1" and p[0]["kind"] == "armed", p)
    body = p[0]["body"] if p else ""
    check("armed text: 'LIT setup armed: LONG limit 29,842 · stop 29,807.5 · target 30,118 · ~6 micros ($414 risk) · valid until 03:15'",
          body == "LIT setup armed: LONG limit 29,842 · stop 29,807.5 · target 30,118 · ~6 micros ($414 risk) · valid until 03:15", body)
    check("armed: tag per setup (the expiry replaces it), opens Today", p and p[0]["tag"] == f"le-setup-{arm}" and p[0]["url"] == "#/today")
    prev2, p2 = ap.setup_step(prev, setups_state(arm), arm + 330, size_fn=lambda tr: 6)
    check("armed: the next poll with the same setup pushes nothing", p2 == [] and prev2["open"] == prev["open"], p2)
    prev3, p3 = ap.setup_step(prev2, setups_state(arm, tapped=arm + 900), arm + 960, size_fn=lambda tr: 6)
    check("1m-CISD wait: one push when the limit is tapped, valid 20 min from the tap",
          len(p3) == 1 and p3[0]["key"] == f"armed1m:{arm}:1" and "waiting for a 1m CISD" in p3[0]["body"] and "valid until 03:20" in p3[0]["body"], p3)
    _, p4 = ap.setup_step(prev3, {"setups": {}}, arm + 2100)
    check("expired: setup gone without an entry -> 'Setup expired — no fill'",
          len(p4) == 1 and p4[0]["key"] == f"expired:{arm}:1" and p4[0]["title"] == "Setup expired — no fill" and p4[0]["tag"] == f"le-setup-{arm}", p4)
    _, p5 = ap.setup_step(prev3, {"setups": {}, "position": {"entry_t": arm + 1080, "dir": 1}}, arm + 1100)
    check("filled: setup gone into a position -> no expiry push", p5 == [], p5)
    _, p6 = ap.setup_step(prev3, {"setups": {}, "enter_now": {"entry_t": arm + 1080, "dir": 1}}, arm + 1100)
    check("filled: setup gone into enter_now (routing now) -> no expiry push", p6 == [], p6)
    _, p7 = ap.setup_step(prev3, {"setups": {}}, arm + 3000, trades=[{"entry_t": arm + 1080, "dir": 1, "exit_reason": "TARGET"}])
    check("filled: setup gone into a finished trade -> no expiry push", p7 == [], p7)
    _, p8 = ap.setup_step(None, setups_state(arm), arm + 46 * 60)
    check("an old setup first seen 46 min after arming (restart) -> no armed push", p8 == [], p8)
    _, p9 = ap.setup_step(None, setups_state(arm), arm + 30, enabled=False)
    check("disabled (market closed / harness) -> track only", p9 == [], p9)
    _, pd = ap.setup_step(None, setups_state(arm, d="short", limit=29900.25, stop=29935.0, target=29700.0), arm + 30)
    check("short + default size rule (LIT $800 up to 20 pts: 34.75-pt stop -> 6 micros)",
          pd and pd[0]["key"] == f"armed:{arm}:-1" and "SHORT limit 29,900.25 · stop 29,935" in pd[0]["body"] and "~6 micros ($417 risk)" in pd[0]["body"], pd)
    # the PC and the cloud make the same keys: a Notifier with the other side's relay "sent" marker skips it
    n = push.Notifier(cfg={"private": "x", "public": "y", "subs": [{"endpoint": "https://web.push.apple.com/a", "keys": {"p256dh": "a", "auth": "b"}}],
                           "source": "t", "error": None}, sender=lambda *a: 201)
    r1 = n.notify(p[0], push_it=True, other_sent={p[0]["key"]})
    check("de-dup: the cloud skips a setup the PC already pushed (relay sent marker)", r1.get("dup") and r1.get("by") == "other side", r1)
    r2 = n.notify(p[0], push_it=True, other_sent=set())
    check("de-dup: the same key is never pushed twice by one side", r2.get("dup"), r2)


def test_crit():
    t0 = ts(2026, 10, 21, 3, 0)
    A = [{"id": "feed_stale:2026-10-21", "kind": "feed_stale", "title": "FEED STALE: new entries blocked", "body": "NinjaTrader bars stale."}]
    st, p = ap.crit_step({}, A, {}, t0)
    check("critical: pushed at once (n 1), require + ack id + #/ack url",
          len(p) == 1 and p[0]["key"] == "crit:feed_stale:2026-10-21:1" and p[0]["require"] and p[0]["ack"] == "feed_stale:2026-10-21"
          and p[0]["url"] == "#/ack/feed_stale:2026-10-21", p)
    w = json.loads(push.wire(p[0]))
    check("wire carries ack + require (the app's Got it)", w.get("ack") == "feed_stale:2026-10-21" and w.get("require"), w)
    st, p = ap.crit_step(st, A, {}, t0 + 300)
    check("critical: no repeat after 5 min", p == [], p)
    st, p = ap.crit_step(st, A, {}, t0 + 600)
    check("critical: repeat 2/6 after 10 min, same tag", len(p) == 1 and p[0]["key"].endswith(":2") and p[0]["body"].startswith("Repeat 2/6:"), p)
    sends = 2
    for k in range(3, 12):
        st, p = ap.crit_step(st, A, {}, t0 + 600 * (k - 1))
        sends += len(p)
    check("critical: at most 6 sends in all", sends == 6 and st["feed_stale:2026-10-21"]["n"] == 6, sends)
    # ack
    st, p = ap.crit_step({}, A, {}, t0)
    st, p = ap.crit_step(st, A, {"feed_stale:2026-10-21": t0 + 120}, t0 + 600)
    check("ack: Got it stops the repeats", p == [] and st["feed_stale:2026-10-21"].get("acked") == t0 + 120, p)
    st, p = ap.crit_step(st, [], {}, t0 + 1200)
    check("ack + clear: no 'resolved' notice after an ack", p == [] and st == {}, p)
    st, p = ap.crit_step({}, A, {"feed_stale:2026-10-21": t0 - 3600}, t0)
    check("an old ack (before the alert began) does not ack a new alert", len(p) == 1 and not st["feed_stale:2026-10-21"].get("acked"), st)
    # auto-clear
    st, p = ap.crit_step({}, A, {}, t0)
    st, p = ap.crit_step(st, [], {}, t0 + 300)
    check("auto-clear: one quiet 'Resolved' notice, same tag, then nothing", len(p) == 1 and p[0]["title"].startswith("Resolved:") and p[0]["silent"]
          and p[0]["tag"].startswith("le-crit-") and st == {}, p)
    # levels
    st, p = ap.crit_step({}, A, {}, t0, prefs={"feed_stale": "off"})
    st, p2 = ap.crit_step(st, A, {}, t0 + 600, prefs={"feed_stale": "off"})
    check("level off: tracked, never pushed", p == [] and p2 == [] and "feed_stale:2026-10-21" in st, (p, p2))
    st, p = ap.crit_step({}, A, {}, t0, prefs={"feed_stale": "silent"})
    st, p2 = ap.crit_step(st, A, {}, t0 + 600, prefs={"feed_stale": "silent"})
    check("level silent: pushed once without sound, no repeats", len(p) == 1 and p[0].get("silent") and p2 == [], (p, p2))
    check("wire carries silent", json.loads(push.wire(p[0])).get("silent") is True)
    # first push made elsewhere (the cloud's Surface-offline notice): repeats start 10 min after it
    B = [{"id": "pc_offline:123", "kind": "pc_offline", "title": "Surface offline since 02:10 ET", "body": "x", "sent_at": t0}]
    st, p = ap.crit_step({}, B, {}, t0)
    st, p2 = ap.crit_step(st, B, {}, t0 + 600)
    check("sent_at: no double first push, repeat 2/6 after 10 min", p == [] and len(p2) == 1 and p2[0]["key"] == "crit:pc_offline:123:2", (p, p2))
    check("crit_open lists open, not acked alerts", [a["id"] for a in ap.crit_open(st)] == ["pc_offline:123"])


def test_levels_relay():
    check("apply_level: on / silent / off", ap.apply_level({"kind": "armed"}, {}) == {"kind": "armed"}
          and ap.apply_level({"kind": "armed"}, {"armed": "silent"}).get("silent") and ap.apply_level({"kind": "armed"}, {"armed": "off"}) is None)
    msgs = [{"le": "prefs", "prefs": {"armed": "silent", "bogus": "on", "kill": "loud"}, "_t": 100},
            {"le": "prefs", "prefs": {"armed": "off"}, "_t": 50}, {"le": "ack", "id": "kill:2026-10-21", "_t": 120},
            {"le": "ack", "id": "kill:2026-10-21", "_t": 90}]
    pf = ap.prefs_from(msgs, {"t": 10, "prefs": {"armed": "on"}})
    check("prefs_from: the newest message wins, unknown kinds / levels dropped", pf == {"t": 100, "prefs": {"armed": "silent"}}, pf)
    check("prefs_from: a stored copy newer than the relay stays", ap.prefs_from(msgs, {"t": 500, "prefs": {"armed": "off"}})["prefs"] == {"armed": "off"})
    check("acks_from: newest ack per id", ap.acks_from(msgs) == {"kill:2026-10-21": 120})
    lines = "\n".join(json.dumps({"event": "message", "time": 7, "message": json.dumps(b)}) for b in
                      ({"le": "ack", "id": "a"}, {"le": "prefs", "prefs": {}}, {"le": "crit", "open": []}, {"le": "junk"}))
    rl = push.Relay(topic="t", http=lambda m, u, b: lines)
    got = [m["le"] for m in rl.read()]
    check("Relay.read keeps ack / prefs / crit (and still drops unknown messages)", got == ["ack", "prefs", "crit"], got)


def test_cloud_stale():
    t = ts(2026, 10, 21, 9, 0)              # Wednesday
    st, p = ap.cloud_step({}, {"sha": "a", "t": t - 600}, t)
    check("stale cloud: fresh publish -> nothing", p == [] and not st["stale"], st)
    st, p = ap.cloud_step(st, {"sha": "a", "t": t - 600}, t + 30 * 60)
    check("stale cloud: 40 min -> nothing yet", p == [], st)
    st, p = ap.cloud_step(st, {"sha": "a", "t": t - 600}, t + 36 * 60)
    check("stale cloud: 46 min in market hours -> one push", len(p) == 1 and p[0]["kind"] == "cloud_stale" and "46 min" in p[0]["title"], p)
    st, p = ap.cloud_step(st, {"sha": "a", "t": t - 600}, t + 60 * 60)
    check("stale cloud: pushed once per outage", p == [], p)
    st2, p = ap.cloud_step(st, None, t + 70 * 60)
    check("stale cloud: GitHub unreachable -> no change", p == [] and st2 == st)
    st, p = ap.cloud_step(st, {"sha": "b", "t": t + 75 * 60}, t + 76 * 60)
    check("stale cloud: new publish -> one 'Cloud monitor back' push", len(p) == 1 and p[0]["title"] == "Cloud monitor back" and not st["stale"], p)
    wk = ts(2026, 10, 24, 11, 0)            # Saturday
    _, p = ap.cloud_step({"sha": "a", "last_t": wk - 5 * 3600}, {"sha": "a", "t": wk - 5 * 3600}, wk)
    check("stale cloud: weekend -> no alarm", p == [])
    night = ts(2026, 10, 21, 20, 0)
    _, p = ap.cloud_step({"sha": "a", "last_t": night - 3 * 3600}, {"sha": "a", "t": night - 3 * 3600}, night)
    check("stale cloud: 20:00 ET (after the cloud's day) -> no alarm", p == [])
    early = ts(2026, 10, 21, 2, 5)
    check("stale cloud window: 02:05 ET out, 02:15 / 16:30 ET in, 16:31 out",
          not ap.cloud_window(early) and ap.cloud_window(ts(2026, 10, 21, 2, 15)) and ap.cloud_window(ts(2026, 10, 21, 16, 30))
          and not ap.cloud_window(ts(2026, 10, 21, 16, 31)))
    calls = []

    def run(args):
        calls.append(args[0])
        if args[0] == "ls-remote":
            return 0, "abc123\trefs/heads/dashboard\n"
        if args[0] == "show":
            return 0, json.dumps({"last_run": 111, "rules": {"hash": "r"}, "push_prefs": {"t": 5, "prefs": {}}})
        return 0, ""
    r = ap.cloud_ref(run=run)
    check("cloud_ref: ls-remote, then a fetch + state.json when the branch moved",
          r == {"sha": "abc123", "t": 111, "rules": {"hash": "r"}, "prefs": {"t": 5, "prefs": {}}} and calls == ["ls-remote", "fetch", "show"], (r, calls))
    calls.clear()
    r = ap.cloud_ref(prev={"sha": "abc123", "last_t": 111}, run=run)
    check("cloud_ref: unchanged branch -> ls-remote only (cheap)", calls == ["ls-remote"] and r["t"] == 111, calls)
    check("cloud_ref: git failure -> None (no alarm)", ap.cloud_ref(run=lambda a: (128, "")) is None)


def test_rules():
    lit = {"be_off": 1.25, "t_check": {"at": 15}}
    ls = {"mode": "two_week", "eval_start": "2026-10-19"}
    a = ap.rules_fp(lit, ls)
    b = ap.rules_fp(dict(lit), {**ls, "eval_start": "2026-11-02"})
    check("rules_fp: 6-hex hash, eval_start left out (PC start cfg override)", re.fullmatch(r"[0-9a-f]{6}", a["hash"]) and a == b, (a, b))
    c = ap.rules_fp({**lit, "be_off": 1.0}, ls)
    check("rules_fp: a LIT setting change changes the hash", c["hash"] != a["hash"] and c["code"] == a["code"])
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "engine"))
        for f in ap.RULE_CODE:
            with open(os.path.join(d, "engine", f), "wb") as fh:
                fh.write(b"x = 1\r\ny = 2\r\n")
        h1 = ap.rules_fp(lit, ls, root=d)["code"]
        ap._CODE.update(key=None)
        for f in ap.RULE_CODE:
            with open(os.path.join(d, "engine", f), "wb") as fh:
                fh.write(b"x = 1\ny = 2\n")
        h2 = ap.rules_fp(lit, ls, root=d)["code"]
        ap._CODE.update(key=None)
    check("code hash ignores line endings (Windows checkout = Linux)", h1 == h2)
    now = ts(2026, 10, 21, 9, 0)
    st, p = ap.rules_step({}, a, dict(a), now)
    check("rules check: same -> no push", p == [] and st["same"])
    st, p = ap.rules_step(st, c, a, now)
    check("rules check: mismatch -> 'PC and cloud run different rules: PC x / cloud y — update the Surface'",
          len(p) == 1 and p[0]["body"].startswith(f"PC and cloud run different rules: PC {c['hash']} / cloud {a['hash']} — update the Surface")
          and "settings" in p[0]["body"] and p[0]["kind"] == "rules", p)
    st, p = ap.rules_step(st, c, a, now + 1800)
    check("rules check: the same mismatch is pushed once", p == [])
    st, p = ap.rules_step(st, c, a, now + 3600, pc_fresh=False)
    check("rules check: an old heartbeat is not judged", p == [])
    st, p = ap.rules_step(st, a, a, now + 5400)
    st, p = ap.rules_step(st, c, a, now + 7200)
    check("rules check: a mismatch after it was fixed is pushed once more", len(p) == 1, p)
    st, p = ap.rules_step({}, None, a, now)
    check("rules check: an old PC without 'rules' -> nothing", p == [])
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    bot = SimpleNamespace(cfg={"model": "lit", "eval_start": "2026-10-21"})
    check("pc_rules (start cfg without overrides) == model_rules(live_model.json)", ap.pc_rules(bot) == ap.model_rules(lm), (ap.pc_rules(bot), ap.model_rules(lm)))


class FakeBot:
    def __init__(self):
        self.state = {**setups_state(ts(2026, 10, 21, 2, 45)), "model": "lit", "strategy": {"params": {"cisd1m": 20}}}
        self.health = {"market_open": True, "feed_block": "NinjaTrader 1m file 9 min old"}
        self.kill = False
        self.running = True
        self._lit_sizing = {"mode": "normal"}
        self._recon = {"sig": (0, 2), "pushed": True, "flat_tries": 1}
        self.cfg = {"model": "lit"}

    def eval_room(self):
        return 350.0

    def eval_start(self):
        return "2026-10-19"

    def eval_state(self):
        return None

    def _push_account(self):
        return "Sim101"


def test_pc_hooks():
    with tempfile.TemporaryDirectory() as d:
        bot, sent = FakeBot(), []
        ap._PC["prev"] = None
        arm = ts(2026, 10, 21, 2, 45)
        p = ap.pc_setup_tick(bot, arm + 30, send=sent.append, path=os.path.join(d, "s.json"))
        check("PC: setup armed sent once from the bot's state (account label set)", len(sent) == 1 and sent[0]["account"] == "Sim101"
              and sent[0]["key"] == f"armed:{arm}:1", sent)
        ap.pc_setup_tick(bot, arm + 60, send=sent.append, path=os.path.join(d, "s.json"))
        check("PC: the next poll sends nothing", len(sent) == 1)
        ap._PC["prev"] = None                       # a restart: the open setups come back from the file
        bot.state = {**bot.state, "setups": {}}
        ap.pc_setup_tick(bot, arm + 1900, send=sent.append, path=os.path.join(d, "s.json"))
        check("PC: after a restart the expiry still comes (setups kept in the state file)", len(sent) == 2 and sent[1]["key"].startswith("expired:"), sent)
        bot.state = {"model": "engine"}
        check("PC: not LIT -> nothing", ap.pc_setup_tick(bot, arm, send=sent.append, path=os.path.join(d, "s.json")) == [])
        ap._PC["prev"] = None
    bot = FakeBot()
    bot._lit_sizing = {"mode": "two_week"}
    bot.kill = True
    bot.health["guard_block"] = "PC clock 7.0 s behind internet time (max 5 s)"
    kinds = sorted(c["kind"] for c in ap.pc_conditions(bot, ts(2026, 10, 21, 3, 0)))
    check("PC conditions: feed stale, mismatch, kill, eval near floor, clock", kinds == ["clock", "eval_floor", "feed_stale", "kill", "unprotected"], kinds)
    bot2 = FakeBot()
    bot2.health = {"market_open": True}
    bot2._recon = None
    check("PC conditions: none when all is fine", [c for c in ap.pc_conditions(bot2) if c["kind"] != "update"] == [])
    hb = ap.hb_block(bot)
    check("heartbeat block: rules + crit", hb["rules"] and hb["rules"].get("hash") and len(hb["crit"]) >= 5, hb)
    # the ops tick: repeat from the heartbeat, ack through the relay, the cloud watch, levels
    from engine import ops_checks as oc
    now = ts(2026, 10, 21, 3, 0)
    state = {"sent": {}}
    out = []

    def send(p):
        out.append(p)
        return oc.send(p, state, sender=lambda q: {"sent": 1})
    ctx = {"hb": {"crit": hb["crit"], "_saved_t": now - 60}, "relay_msgs": [], "cloud_ref": {"sha": "a", "t": now - 600}}
    ap.ops_tick(ctx, state, now, send, real=False)
    check("ops tick: every new critical condition pushed at once", len(out) == len(hb["crit"]), [p["key"] for p in out])
    out.clear()
    ap.ops_tick(ctx, state, now + 300, send, real=False)
    check("ops tick (5 min later): no repeats yet", out == [], [p["key"] for p in out])
    ack_id = next(c["id"] for c in hb["crit"] if c["kind"] == "kill")
    ctx2 = {**ctx, "hb": {**ctx["hb"], "_saved_t": now + 590},
            "relay_msgs": [{"le": "ack", "id": ack_id, "_t": now + 400}, {"le": "prefs", "prefs": {"clock": "off"}, "_t": now + 400}]}
    ap.ops_tick(ctx2, state, now + 600, send, real=False)
    ks = [p["kind"] for p in out]
    check("ops tick (10 min): repeats, except the acked kill switch and the clock alert set to off",
          "kill" not in ks and "clock" not in ks and len(out) == len(hb["crit"]) - 2 and all(p["body"].startswith("Repeat 2/6") for p in out), ks)
    out.clear()
    ctx3 = {**ctx2, "hb": {"crit": [], "_saved_t": now + 890}}
    ap.ops_tick(ctx3, state, now + 900, send, real=False)
    check("ops tick: conditions cleared -> quiet 'Resolved' notices (not for the acked / off ones)",
          out and all(p["title"].startswith("Resolved:") and p.get("silent") for p in out) and len(out) == len(hb["crit"]) - 2, [p["title"] for p in out])
    out.clear()
    ctx4 = {**ctx3, "hb": {"crit": hb["crit"], "_saved_t": now - 3600}}
    ap.ops_tick(ctx4, state, now + 1200, send, real=False)
    check("ops tick: an old heartbeat (> 15 min) changes nothing", out == [])
    ctx5 = {"hb": {}, "relay_msgs": [], "cloud_ref": {"sha": "a", "t": now - 600}}
    ap.ops_tick(ctx5, state, now + 40 * 60, send, real=False)
    check("ops tick: cloud not published for 46 min -> the stale-cloud push", [p["kind"] for p in out] == ["cloud_stale"], [p["key"] for p in out])
    r = oc.tick(now=now, ctx={"hb": {}, "net": {"up": True}, "folder": "/nonexistent", "state": {}, "now": now}, state={"sent": {}},
                sender=lambda q: {"sent": 1}, state_path=os.path.join(tempfile.mkdtemp(), "ops.json"), do_backup=False)
    check("ops_checks.tick runs with the hook (a replay ctx without relay_msgs / cloud_ref: no network, no notices)",
          isinstance(r, list) and not [x for x in r if str(x.get("key", "")).startswith(("crit", "cloud"))], r)


def test_cloud_hook():
    from tools import cloud_monitor as cm
    posts = []
    relay = SimpleNamespace(post=lambda o: posts.append(o) or True)
    now = ts(2026, 10, 21, 2, 46)
    arm = now - 60
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    pc = {"present": True, "age_s": 40 * 60, "host": "SURFACE", "rules": {**ap.model_rules(lm), "hash": "zzzzzz"}}
    outage = {"since": now - 40 * 60, "alerted_at": now - 600}
    st = {}
    out = cm.alerts_plus_step(st, setups_state(arm), {"trades": []}, {}, lm, pc, outage, relay,
                              [{"le": "prefs", "prefs": {"armed": "silent"}, "_t": now - 5}], now, feed_ok=True, mopen=True)
    kinds = [n["kind"] for n in out["notices"]]
    check("cloud: setup armed pushed for the paper bot", "armed" in kinds, kinds)
    check("cloud: Surface offline repeated 10 min after the first push (2/6)",
          any(n["key"] == f"crit:pc_offline:{outage['since']}:2" for n in out["notices"]), [n["key"] for n in out["notices"]])
    check("cloud: a 40-min-old heartbeat is not judged for the rules check", "rules" not in kinds, kinds)
    check("cloud: levels from the relay kept for the state", out["prefs"] == {"armed": "silent"} and out["prefs_state"]["t"] == now - 5)
    check("cloud: open critical alerts posted to the relay for the phone's ack page",
          posts and posts[-1]["le"] == "crit" and posts[-1]["open"][0]["id"] == f"pc_offline:{outage['since']}", posts)
    pc["age_s"] = 300
    out2 = cm.alerts_plus_step({"setups_seen": out["setups_seen"], "crit": out["crit"]}, setups_state(arm), {"trades": []}, {}, lm, pc,
                               outage, relay, [{"le": "ack", "id": f"pc_offline:{outage['since']}", "_t": now + 30}], now + 600)
    k2 = [n["key"] for n in out2["notices"]]
    check("cloud next run: acked -> no repeat, setup not re-pushed, rules mismatch pushed once (fresh heartbeat)",
          not any(k.startswith("crit:") for k in k2) and not any(k.startswith("armed") for k in k2) and any(k.startswith("rules:") for k in k2), k2)
    out3 = cm.alerts_plus_step({}, {}, {}, {}, lm, None, None, None, [], now)       # relay None -> its own error is caught
    check("cloud hook never raises (broken inputs)", isinstance(out3, dict) and "notices" in out3)


def test_static():
    lv = read("engine/live.py")
    check("live.py: _alerts_tick right after _guards_tick (after routing), real bot only",
          "self._guards_tick(now)\n        self._alerts_tick(now)" in lv and "def _alerts_tick" in lv
          and "if self.state_path != STATE_PATH:\n            return\n        try:\n            from . import alerts_plus" in lv)
    hb = read("engine/heartbeat.py")
    check("heartbeat payload: rules + crit (engine/alerts_plus.hb_block)", "**_alerts_plus(self.bot)" in hb)
    oc = read("engine/ops_checks.py")
    check("ops tick: alerts_plus.ops_tick hooked", "alerts_plus.ops_tick(ctx, state, now" in oc)
    cmon = read("tools/cloud_monitor.py")
    check("cloud monitor: alerts_plus_step + state keys", "alerts_plus_step(st, state, res" in cmon and '"rules": plus["rules"]' in cmon
          and '"crit": plus["crit"]' in cmon and '"push_prefs": plus["prefs_state"]' in cmon)
    ix = read("tools/web_public/index.html")
    check("phone: index.html loads alerts.js", 'src="alerts.js?v=' in ix)
    js = read("tools/web_public/alerts.js")
    check("phone: #/ack page with Got it -> relay {le: 'ack'}, levels -> {le: 'prefs'}, stale-cloud banner",
          "DETAIL.ack" in js and "le: 'ack'" in js and "le: 'prefs'" in js and "Cloud monitor: no publish for" in js and "STALE_S = 45 * 60" in js)
    sw = read("tools/web_public/sw.js")
    check("service worker: cache bumped, silent, 'Got it' action posts the ack", "le-public-v18" in sw and "d.silent" in sw
          and "action: 'ack'" in sw and "e.action === 'ack'" in sw)
    gi = read(".gitignore")
    check("gitignore: data/alerts_plus.json, data/push_prefs.json", "data/alerts_plus.json" in gi and "data/push_prefs.json" in gi)


def test_phone():
    """The real phone page (Playwright, skipped when node + playwright are missing; --no-browser skips it too)."""
    import shutil
    import subprocess
    if "--no-browser" in sys.argv:
        return
    node = shutil.which("node")
    groot = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip() if shutil.which("npm") else ""
    if not node or not os.path.isdir(os.path.join(groot, "playwright")):
        print("[SKIP] phone Playwright check: node + playwright not installed")
        return
    tmp = tempfile.mkdtemp()
    try:
        site = os.path.join(tmp, "site")
        shutil.copytree(os.path.join(ROOT, "tools", "web_public"), site, ignore=shutil.ignore_patterns("fx", "node_modules"))
        import time as _t
        T = int(_t.time())
        data = {"built": _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime(T - 300)), "live": {"last_run": T - 300, "runs": 1},
                "accounts": [], "results": {"periods": {}}, "trades": [], "strategy": {}}
        for n in ("data.json", "home.json"):
            with open(os.path.join(site, n), "w", encoding="utf-8") as f:
                json.dump(data, f)
        env = {**os.environ, "NODE_PATH": groot}
        env.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers" if os.path.isdir("/opt/pw-browsers") else "")
        if not env["PLAYWRIGHT_BROWSERS_PATH"]:
            env.pop("PLAYWRIGHT_BROWSERS_PATH")
        port = str(8823 + os.getpid() % 50)
        r = subprocess.run([node, os.path.join(ROOT, "tests", "phone_alerts_check.js"), site, port], capture_output=True, text=True,
                           timeout=180, env=env)
        try:
            out = json.loads((r.stdout or "").strip().splitlines()[-1])
        except Exception:
            check("phone (Playwright): the check ran", False, (r.stdout or "")[-300:] + (r.stderr or "")[-300:])
            return
        for name, ok, info in out.get("steps") or []:
            check(f"phone (Playwright): {name}", ok, info)
        if out.get("error"):
            check("phone (Playwright): no harness error", False, out["error"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    for f in (test_setups, test_crit, test_levels_relay, test_cloud_stale, test_rules, test_pc_hooks, test_cloud_hook, test_static,
              test_phone):
        try:
            f()
        except Exception as e:
            import traceback
            traceback.print_exc()
            check(f"{f.__name__} raised {e.__class__.__name__}: {e}", False)
    n = len(RES)
    print(f"alerts plus: {sum(RES)}/{n} {'ALL PASS' if all(RES) else 'FAILED'}")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
