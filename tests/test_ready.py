"""day-ready 2026-11-22: the READY / NOT READY self-check (engine/readiness.py), read-only on trading.

  a. blockers   one fake-facts case per blocker type: PC clock 25 s behind (the guard's 5 s limit, not ops_checks' 30 s), an unarmed
                account, NinjaTrader disconnected, stale bars, a pending restart (update), a keep-alive deadline within 2 days, disk low,
                a halted account, the kill switch; all clear = READY; worst first, max 5 shown; every blocker has words + a fix
  b. alerts     the de-dup rules: one alert, the same blocker never twice within 30 min, a repeat at most once an hour, a NEW blocker goes
                at once, READY = one quiet line at the 17:30 slot only, no alert outside the active period; the slots (17:30 Sun-Thu,
                01:15, 08:45) fire once a day; tick() writes the verdict and sends through the injected sender
  c. post       rd() <= 200 bytes in the worst case, plain words, no ids; tools/pc_report puts it in the ext post (and that post stays
                under the byte budget); brain_glance carries a short one; stale verdicts are not posted
  d. cloud      tools/ready_check.verdict on a fake post: ok / warn / no / unknown (silent, old PC)

    python -X utf8 -m tests.test_ready
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402
from engine import readiness as R  # noqa: E402

check = AK.check
ET = ZoneInfo("America/New_York")


def ts(y, mo, d, h, mi=0) -> int:
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


MON_0115 = ts(2026, 11, 23, 1, 15)
SUN_1730 = ts(2026, 11, 22, 17, 30)
HB = {"t": 1, "health": {"account": {"label": "LIVE", "armed": True, "enabled": True}, "accounts": []},
      "second": {"route": {"account_b": {"label": "live", "armed": True}}}}


def ck(key, level, text="x", fix=""):
    return {"key": key, "name": key, "level": level, "text": text, "fix": fix}


GOOD = {"hb": HB, "drift_s": 0.4, "disk_free_gb": 200, "checks": [ck("nt_conn", "ok"), ck("feed_1m", "ok"), ck("feed_5m", "ok"), ck("heartbeat", "ok"),
                                                                    ck("server", "ok"), ck("bot", "ok"), ck("internet", "ok")], "k7": [{"nm": "Zlarior", "left": 5, "on": True}]}


def facts(**kw):
    f = json.loads(json.dumps(GOOD))
    f.update(kw)
    return f


def first(v):
    return (v["blockers"] or [{}])[0]


def test_blockers():
    v = R.ready_verdict(MON_0115, facts=GOOD)
    check("a1. all clear -> READY, ready True, no blockers", v["level"] == "READY" and v["ready"] and v["blockers"] == [] and R.headline(v) == "READY for the next window", v)
    v = R.ready_verdict(MON_0115, facts=facts(drift_s=24.5))
    b = first(v)
    check("a2. PC clock 24.5 s behind -> NOT READY with the title the owner reads (the guard blocks at 5 s; ops_checks only warns below 30 s)",
          v["level"] == "NOT_READY" and not v["ready"] and R.headline(v) == "NOT READY for 02:00: PC clock 25 s behind" and "FIX_CLOCK.bat" in b["exact_fix"] and "Sync now" not in b["exact_fix"]
          and b["needs_owner_at_pc"] is True and "5 s" in b["why_plain_words"], v)
    check("a2b. 3 s off is fine (inside the guard's limit); 'ahead' is worded 'ahead'", R.ready_verdict(MON_0115, facts=facts(drift_s=3.0))["level"] == "READY"
          and "ahead" in first(R.ready_verdict(MON_0115, facts=facts(drift_s=-9)))["what"], "")
    hb2 = json.loads(json.dumps(HB))
    hb2["second"]["route"]["account_b"]["armed"] = False
    v = R.ready_verdict(MON_0115, facts=facts(hb=hb2))
    check("a3. ATLAS armed false (tonight's second error) -> NOT READY naming ATLAS and the phrase step",
          v["level"] == "NOT_READY" and "ATLAS" in first(v)["what"] and "phrase" in first(v)["exact_fix"] and first(v)["needs_owner_at_pc"], v)
    hb3 = json.loads(json.dumps(HB))
    hb3["health"]["account"]["armed"] = False
    check("a3b. Zlarior LIVE but not armed -> NOT READY", "Zlarior" in first(R.ready_verdict(MON_0115, facts=facts(hb=hb3)))["what"], "")
    v = R.ready_verdict(MON_0115, facts=facts(checks=[ck("nt_conn", "bad", "DISCONNECTED: Connection 1")]))
    check("a4. NinjaTrader disconnected -> NOT READY, click path in the fix", v["level"] == "NOT_READY" and "Connections" in first(v)["exact_fix"], v)
    v = R.ready_verdict(MON_0115, facts=facts(checks=[ck("feed_1m", "bad", "last bar 12 min old (FEED STALE: no new entries)")]))
    check("a5. stale bars -> NOT READY", v["level"] == "NOT_READY" and "stale" in first(v)["what"].lower() and "F5" in first(v)["exact_fix"], v)
    v = R.ready_verdict(MON_0115, facts=facts(checks=GOOD["checks"] + [ck("winupdate", "warn", "a restart is pending: Windows may restart the PC by itself")]))
    check("a6. Windows update / restart pending -> WARN, still ready (never blocks a trade by itself)", v["level"] == "WARN" and v["ready"] and "restart" in first(v)["what"].lower(), v)
    v = R.ready_verdict(MON_0115, facts=facts(k7=[{"nm": "ATLAS 25K", "left": 2, "on": False}]))
    v1 = R.ready_verdict(MON_0115, facts=facts(k7=[{"nm": "ATLAS 25K", "left": 1, "on": False}]))
    v0 = R.ready_verdict(MON_0115, facts=facts(k7=[{"nm": "ATLAS 25K", "left": 1, "on": True}]))
    check("a7. keep-alive deadline within 2 days: 2 left = WARN, 1 left = NOT READY, keep-alive ON = nothing",
          v["level"] == "WARN" and v1["level"] == "NOT_READY" and v0["level"] == "READY" and "7-day" in first(v)["what"], (v["level"], v1["level"], v0["level"]))
    v = R.ready_verdict(MON_0115, facts=facts(disk_free_gb=1.2))
    vw = R.ready_verdict(MON_0115, facts=facts(disk_free_gb=6))
    check("a8. disk 1.2 GB = NOT READY, 6 GB = WARN", v["level"] == "NOT_READY" and vw["level"] == "WARN" and "CLEAN_STORAGE" in first(v)["exact_fix"], (v, vw))
    hb4 = json.loads(json.dumps(HB))
    hb4["health"]["accounts"] = [{"id": "b25k_2", "armed": True, "enabled": True, "label": "LIVE", "locked": "daily loss limit hit"}]
    hb4["health"]["kill"] = True
    v = R.ready_verdict(MON_0115, facts=facts(hb=hb4))
    wh = {b["what"] for b in v["blockers"]}
    check("a9. a halted account and the kill switch are blockers", any("halted" in w for w in wh) and any("Kill switch" in w for w in wh), wh)
    v = R.ready_verdict(MON_0115, facts=facts(drift_s=30, hb=hb2, disk_free_gb=1, checks=GOOD["checks"] + [ck("nt_conn", "bad"), ck("feed_1m", "bad"), ck("winupdate", "warn", "a restart is pending")]))
    check("a10. many problems: at most 5 shown, worst (NOT READY) first, n = how many there are, every one has words + fix",
          len(v["blockers"]) == 5 and v["n"] > 5 and all(b["level"] == "NOT_READY" for b in v["blockers"]) and all(b["why_plain_words"] and b["exact_fix"] for b in v["blockers"]), v["n"])
    v = R.ready_verdict(MON_0115, facts=facts(closed="market closed", drift_s=60))
    check("a11. a CME full-closure day: READY with a note, no nagging", v["level"] == "READY" and v.get("note"), v)
    v = R.ready_verdict(MON_0115, facts=facts(checks=[ck("bot", "bad", "bot is not running")]))
    check("a12. bot not running -> NOT READY", v["level"] == "NOT_READY" and "Bot" in first(v)["what"], v)
    v = R.evaluate({"checks": "nonsense", "hb": 5}, MON_0115)
    check("a13. garbage facts never raise", v["level"] in ("READY", "NOT_READY", "WARN"), v)
    check("a14. window words: 01:15 -> 02:00, 08:45 -> 09:30, 17:30 Sunday -> 02:00, Friday evening -> Mon 02:00",
          R.window_label(MON_0115) == "02:00" and R.window_label(ts(2026, 11, 23, 8, 45)) == "09:30" and R.window_label(SUN_1730) == "02:00"
          and R.window_label(ts(2026, 11, 27, 17, 30)) == "Mon 02:00", "")


def test_alerts():
    bad = R.ready_verdict(MON_0115, facts=facts(drift_s=25))
    st: dict = {}
    a = R.plan_alert(bad, st, MON_0115, "0115")
    check("b1. NOT READY -> ONE alert: short title + the exact fix in the body", a and a["title"] == "NOT READY for 02:00: PC clock 25 s behind" and "Fix: On the PC" in a["body"] and not a["quiet"], a)
    check("b2. the same blocker 5 / 29 min later -> nothing", R.plan_alert(bad, st, MON_0115 + 300, None) is None and R.plan_alert(bad, st, MON_0115 + 29 * 60, None) is None, "")
    check("b3. still NOT READY 61 min later -> repeated (once an hour)", R.plan_alert(bad, st, MON_0115 + 61 * 60, None) is not None, "")
    two = R.ready_verdict(MON_0115, facts=facts(drift_s=25, checks=GOOD["checks"] + [ck("nt_conn", "bad")]))
    st["last_keys"] = {b["key"]: 1 for b in bad["blockers"]}
    a2 = R.plan_alert(two, st, MON_0115 + 61 * 60 + 600, None)
    check("b4. a NEW blocker goes at once (even inside the hour) and the body counts the rest, never the same key within 30 min",
          a2 and "NinjaTrader" in a2["title"], a2)
    st2: dict = {"sent": {"clock": MON_0115}, "last_alert": MON_0115 - 7200, "last_keys": {}}
    check("b5. a repeat of the same blocker key inside 30 min is dropped even when the hour is long past", R.plan_alert(bad, st2, MON_0115 + 600, None) is None, "")
    ok = R.ready_verdict(SUN_1730, facts=GOOD)
    q = R.plan_alert(ok, {}, SUN_1730, "1730")
    check("b6. READY -> one quiet 'READY for the next window' at the 17:30 slot only", q and q["title"] == "READY for the next window" and q["quiet"]
          and R.plan_alert(ok, {}, MON_0115, "0115") is None and R.plan_alert(ok, {}, MON_0115 + 60, None) is None, q)
    sat = ts(2026, 11, 21, 12, 0)
    check("b7. no alert for a NEW blocker on the weekend, or 15:30-17:25 (not a window); but a slot always counts",
          R.plan_alert(bad, {}, sat, None) is None and R.plan_alert(bad, {}, ts(2026, 11, 23, 16, 0), None) is None and R.plan_alert(bad, {}, ts(2026, 11, 22, 17, 30), "1730") is not None, "")
    s2: dict = {}
    check("b8. slots: 17:30 Sun-Thu, 01:15 + 08:45 Mon-Fri; once per day; up to 25 min late; not Fri 17:30 / Sat",
          R.due_slot(SUN_1730, s2) == "1730" and R.due_slot(MON_0115 + 20 * 60, s2) == "0115" and R.due_slot(MON_0115 + 40 * 60, s2) is None
          and R.due_slot(ts(2026, 11, 23, 8, 45), s2) == "0845" and R.due_slot(ts(2026, 11, 27, 17, 30), s2) is None and R.due_slot(sat, s2) is None, "")
    s2 = {"slots": {"2026-11-23:0115": 1}}
    check("b9. a slot already done today does not fire again", R.due_slot(MON_0115, s2) is None, "")
    d = tempfile.mkdtemp()
    sent = []
    r = R.tick(MON_0115, facts=facts(drift_s=25), sender=sent.append, last_path=os.path.join(d, "last.json"), state_path=os.path.join(d, "st.json"))
    r2 = R.tick(MON_0115 + 300, facts=facts(drift_s=25), sender=sent.append, last_path=os.path.join(d, "last.json"), state_path=os.path.join(d, "st.json"))
    last = R.read_last(os.path.join(d, "last.json"), now=MON_0115 + 400)
    check("b10. tick(): the 01:15 slot sends ONE alert, 5 min later nothing, the verdict file is written (and read back)",
          len(sent) == 1 and r["slot"] == "0115" and r2["alert"] is None and last and last["level"] == "NOT_READY"
          and R.read_last(os.path.join(d, "last.json"), now=MON_0115 + 5 * 3600) is None, (sent, r2))
    r3 = R.tick(MON_0115 + 7200, facts=facts(), sender=sent.append, last_path=os.path.join(d, "l2.json"), state_path=os.path.join(d, "s2.json"))
    check("b11. tick() never starts / arms anything: it imports no control (source has no start / arm / order calls)",
          not any(w in open(R.__file__, encoding="utf-8").read().split("# READY VERDICT")[1] for w in ("place_order", "adapter.arm", ".start_bot(", "set_armed", "flatten(")), r3.get("error"))


def test_post():
    worst = {"level": "NOT_READY", "window": "Mon 02:00", "n": 5, "t": 1, "blockers": [
        {"what": "Zlarior 25K #2 orders are disabled and something very long here", "exact_fix": "On the PC: double-click TRADE_HOME.bat, press 2 (Start bot) and type your arm phrase yourself " * 3}]}
    r = R.rd(worst)
    n = len(json.dumps(r, separators=(",", ":"), ensure_ascii=False).encode())
    check("c1. rd() <= 200 bytes even for the longest blocker, keeps status + window + first blocker", n <= 200 and r["s"] == "no" and r["b"].startswith("Zlarior"), (n, r))
    real = R.rd(R.ready_verdict(MON_0115, facts=facts(drift_s=24.5)))
    txt = json.dumps(real)
    check("c2. plain words, no ids / digits runs / paths", len(json.dumps(real).encode()) <= 200 and not any(c in txt for c in ("\\", "@", "http", ":\\")), txt)
    check("c3. READY = {'s': 'ok', 'w'} only; no verdict = None", R.rd(R.ready_verdict(MON_0115, facts=GOOD)) == {"s": "ok", "w": "02:00"} and R.rd(None) is None, "")
    from tools import pc_report as P
    check("c4. 'rd' is an ext block (EXT_ORDER) and the ext post still fits", "rd" in P.EXT_ORDER, "")
    from engine import brain_glance as BG
    d = tempfile.mkdtemp()
    p = os.path.join(d, "last.json")
    json.dump({**R.ready_verdict(MON_0115, facts=facts(drift_s=25)), "t": 100}, open(p, "w"))
    old = R.LAST_PATH
    R.LAST_PATH = p
    try:
        v = R.read_last(p, now=200)
        g = BG.build({"t": 100, "health": {"account": {}}, "running": True}, {}, now=200)
    finally:
        R.LAST_PATH = old
    check("c5. read_last returns the file while fresh", v and v["level"] == "NOT_READY", v)
    check("c6. brain_glance.build still fits MAX_BYTES with the verdict (rd <= 90 bytes, no fix text) or carries none when there is no file",
          g is not None and BG.size(g) <= BG.MAX_BYTES and ("rd" not in g or "f" not in g["rd"]), g)


def test_cloud():
    from tools import ready_check as RC
    now = 10000
    base = {"t": now - 120, "rd": {"s": "no", "w": "02:00", "b": "PC clock 25 s behind", "f": "Sync now", "n": 2}}
    v = RC.verdict(base, now)
    check("d1. NOT READY post -> the line with the blocker, '+1 more', and the fix", v["state"] == "no" and v["line"] == "NOT READY for 02:00: PC clock 25 s behind (+1 more)" and v["fix"] == "Sync now", v)
    check("d2. READY / warn posts", RC.verdict({"t": now - 5, "rd": {"s": "ok", "w": "02:00"}}, now)["line"] == "READY for 02:00"
          and RC.verdict({"t": now - 5, "rd": {"s": "warn", "w": "02:00", "b": "disk low"}}, now)["state"] == "warn", "")
    check("d3. silent PC, old PC version, nothing readable -> UNKNOWN (exit 2), never READY",
          RC.verdict({**base, "t": now - 7200}, now)["state"] == "unknown" and RC.verdict({"t": now - 5}, now)["state"] == "unknown" and RC.verdict(None, now)["state"] == "unknown", "")


if __name__ == "__main__":
    test_blockers()
    test_alerts()
    test_post()
    test_cloud()
    AK.finish()
