"""day-guard2 2026-11-26.  python -X utf8 -m tests.test_guard2
a. risk-distance alarms (engine/risk_alarm): floor vs daily limit, the open trade counted, $500 / $300 / $150 once each per
   account per day, a jump = one push, loud at $150, hidden bots never named, finished accounts skipped, a funded account's payout
   line; the live guard's every-minute path (sent once, survives a restart); pc_guard only when the server is down.
b. signed status feed end to end (tools/status_sign + board + pc_feed.js): vk pinned in status_feed.json; several pinned keys; a
   rotation post signed by the old key hands over to the new one (Python and the phone); a rotation signed by a stranger is
   ignored; the 3-hour window names a candidate and never trusts it; pin(); rotate() + the 6-hour re-post.
c. /today (engine/today_brief + engine/tg_cmd): the text, read-only (never through the control path), hidden bots never named.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import risk_alarm as RA  # noqa: E402

RES = []
NOW = 1_795_300_000                         # 2026-11-21 17:26 ET (a Saturday)


def check(name, ok, info=None):
    RES.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  {str(info)[:400]}"))


def live(room=1025.0, dll_used=0.0, today=0.0, unreal=None, atlas_room=890.0, atlas_status="funded", blitz=True, extra_room=640.0,
         extra_status="open"):
    pos = {"unrealized_usd": unreal} if unreal is not None else None
    bd = {"lit": {"room": room, "mll": 2000, "dll": 1000, "dll_used": dll_used, "today_pnl": today, "balance": 49193.0,
                  "to_target": 3807.0, "status": "open", "position": pos, "plan": "Builder 50K"},
          "atlas": {"room": atlas_room, "mll": 1000, "dll": 600, "today_pnl": 120.0, "balance": 26946.0, "status": atlas_status,
                    "configured": True, "real": True, "plan": "Builder 25K"}}
    if blitz:
        bd["blitz"] = {"room": 100.0, "mll": 1000, "dll": 600, "today_pnl": -400, "status": "open", "configured": True}
    return {"v": 1, "kind": "le-live", "mode": "LIVE", "board": bd,
            "pc": {"running": True, "position": None, "health": {"lit": {"stage": "limit"}}, "model_state": "watching"},
            "accounts": [{"id": "b25k_2", "extra": True, "kind": "eval", "name": "MFFUEVBLDR123456", "plan": "builder25k",
                          "eval": {"room": extra_room, "dll": 600, "dll_used": 0, "today": 0, "balance": 25023.6, "to_target": 1476.4,
                                   "status": extra_status}, "pnl": {"today": 0.0}, "badge": "LIVE"},
                         {"id": "acct_c", "extra": True, "kind": "eval", "eval": {"room": 50, "dll": 600}}]}


def part_a():
    d = RA.distance(1025, 1000, 0, -200, -900)
    check("a. the open trade counts: floor 1025-900=125 vs day 1000-1100<0 -> the day limit is nearer", d["limit"] == "day" and d["left"] == -100, d)
    d = RA.distance(400, 1000, 100, -100, None)
    check("a. floor $400 vs day $900 -> floor", d["limit"] == "floor" and d["left"] == 400, d)
    ids = [r["id"] for r in RA.rows(live())]
    check("a. hidden BLITZ and BLITZ's account C never named; extras included", "blitz" not in ids and "acct_c" not in ids
          and "b25k_2" in ids and "lit" in ids, ids)
    sent = {}
    views = [{"key": "atlas", "ready": True, "amount": 1000.0, "to_you": 800.0}]
    p = RA.pushes(live(room=480), sent, NOW, views=views)
    lit = [m for m in p if ":lit:" in m["key"]]
    check("a. $480 left on the 50K -> one $500 push (normal priority)", len(lit) == 1 and lit[0]["key"].endswith(":500")
          and lit[0]["priority"] == "default" and "$480 left" in lit[0]["title"], p)
    sent.update({m["key"]: NOW for m in p})
    check("a. the same level again = nothing", not [m for m in RA.pushes(live(room=470), sent, NOW + 60, views=views) if ":lit:" in m["key"]])
    p2 = [m for m in RA.pushes(live(room=120), sent, NOW + 120, views=views) if ":lit:" in m["key"]]
    check("a. a jump 470 -> 120 = ONE push at $150, loud (urgent, rings at night)", len(p2) == 1 and p2[0]["key"].endswith(":150")
          and p2[0]["priority"] == "urgent" and p2[0]["night"] and p2[0]["covers"][0].endswith(":500"), p2)
    p3 = [m for m in RA.pushes(live(room=120), {}, NOW + 86400, views=views) if ":lit:" in m["key"]]
    check("a. next CME day: armed again", len(p3) == 1, p3)
    atl = [m for m in RA.pushes(live(atlas_room=290), {}, NOW, views=views) if ":atlas:" in m["key"]]
    check("a. the funded ATLAS at $290: $300 push (high) + its payout state", len(atl) == 1 and atl[0]["priority"] == "high"
          and "payout requestable now: $1,000 ($800 to you)" in atl[0]["body"], atl)
    fin = [m for m in RA.pushes(live(extra_room=50, extra_status="failed"), {}, NOW, views=views) if "b25k_2" in m["key"]]
    check("a. a finished (failed) account is skipped", not fin, fin)
    ex = [m for m in RA.pushes(live(extra_room=140), {}, NOW, views=views) if "b25k_2" in m["key"]]
    check("a. the extra 25K #2 by its owner name, no broker id", len(ex) == 1 and "MFFUEVBLDR123456" not in json.dumps(ex), ex)
    # the live guard: every minute, sent once, a restart does not repeat
    from engine import live_guard as LG
    tmp = tempfile.mkdtemp(prefix="guard2_")
    try:
        got = []
        lv = {"v": live(room=140)}
        mk = lambda: LG.LiveGuard(send=lambda p: (got.append(p) or "sent"), clock=lambda: NOW, state_path=os.path.join(tmp, "s.json"),  # noqa: E731
                                  au_path=os.path.join(tmp, "au.json"), arm_path=os.path.join(tmp, "arm.json"),
                                  risk_live=lambda: lv["v"], risk_path=os.path.join(tmp, "risk.json"))
        os.environ["LE_LIVE_GUARD"] = "1"
        g = mk()
        g.step(None, NOW)
        lit = [p for p in got if ":lit:" in p["key"]]
        check("a. live guard: the $150 push goes out at once (code risk)", len(lit) == 1 and lit[0]["code"] == "risk", got)
        g.step(None, NOW + 61)
        check("a. live guard: not again a minute later", len([p for p in got if ":lit:" in p["key"]]) == 1, got)
        g2 = mk()
        g2.step(None, NOW + 200)
        check("a. live guard: a server restart does not repeat it (logs/risk_alarm.json)", len([p for p in got if ":lit:" in p["key"]]) == 1, got)
        lv["v"] = None
        n = len(got)
        g2.step(None, NOW + 400)
        check("a. live guard: no live view (server starting) = nothing, no error", len(got) == n and "error" not in g2.last, g2.last)
    finally:
        os.environ.pop("LE_LIVE_GUARD", None)
        shutil.rmtree(tmp, ignore_errors=True)
    from tools import pc_guard as PG
    snap = {"t": NOW, "hb_age": 60, "live": live(room=140), "server": True}
    _st, msgs = PG.guard({}, snap)
    check("a. pc_guard: the server's live guard owns it while the server answers", not [m for m in msgs if m["key"].startswith("guard:risk:")], msgs)
    _st, msgs = PG.guard({}, {**snap, "server": False})
    check("a. pc_guard: the 15-minute report is the fallback when the server is down",
          [m for m in msgs if m["key"].startswith("guard:risk:lit:")], [m["key"] for m in msgs])
    from engine import notify as N
    check("a. the notify type is room_low (on, rings in quiet hours)", N.kind_of("guard:risk:lit:2026-11-24:150") == "room_low")


def node(js):
    r = subprocess.run(["node", "-e", js], cwd=ROOT, capture_output=True, text=True, timeout=120)
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "")[-400:]


def part_b():
    from tools import status_sign as S
    pinned = S.feed_vks()
    check("b. the PC's vk is pinned in tools/web_public/status_feed.json", len(pinned) >= 1 and S.VK_RX.match(pinned[0]), pinned)
    old, old_vk = S.keygen()
    new, new_vk = S.keygen()
    bad, bad_vk = S.keygen()

    def core(t, priv, bal):
        b = json.dumps({"v": 1, "kind": "le-live", "t": t, "brd": {"ac": [["zlarior", "eval", bal]]}}, separators=(",", ":"))
        return {"time": t, "message": S.sign_text(b[:-1] + ',"svk":"' + S.vk_of(priv) + '"}', priv)}
    rot = {"time": NOW, "message": S.rotation_text(old, new_vk, now=NOW)}
    evil = {"time": NOW + 5, "message": S.rotation_text(bad, bad_vk, now=NOW + 5).replace(S.vk_of(bad), old_vk, 1)}
    evil2 = {"time": NOW + 6, "message": S.rotation_text(bad, bad_vk, now=NOW + 6)}
    msgs = [core(NOW - 600, old, 1.0), rot, core(NOW + 60, new, 2.0), evil, evil2, core(NOW + 120, bad, 666.0)]
    acc = S.accepted(msgs, [old_vk])
    check("b. a rotation signed by the OLD key hands over to the new one; a stranger's 'rotation' is ignored",
          new_vk in acc and bad_vk not in acc, [k[:6] for k in acc])
    kept = S.filter_msgs(msgs, [old_vk], now=NOW + 200)
    bals = [json.loads(m["message"]).get("brd", {}).get("ac", [[0, 0, None]])[0][2] for m in kept if '"le-live"' in m["message"]]
    check("b. filter_msgs: old + new key posts kept, the stranger's dropped", bals == [1.0, 2.0], bals)
    check("b. several pinned keys (vk + vks) each count", S.filter_msgs([core(NOW, bad, 3.0)], [old_vk, bad_vk], now=NOW + 1))
    steady = [core(NOW + i * 900, bad, 9.0) for i in range(14)]
    c = S.candidate(steady, [old_vk], now=NOW + 14 * 900)
    check("b. 3-hour window: pinned key silent, one other key 14 posts over 3.25 h -> named as candidate", c and c["vk"] == bad_vk, c)
    check("b. ... but never trusted by itself", not S.filter_msgs(steady, [old_vk], now=NOW + 14 * 900))
    check("b. no candidate while the pinned key still posts", S.candidate(steady + [core(NOW + 13 * 900, old, 1.0)], [old_vk], now=NOW + 14 * 900) is None)
    tmp = tempfile.mkdtemp(prefix="guard2b_")
    try:
        fp = os.path.join(tmp, "status_feed.json")
        json.dump({"ntfy": "https://ntfy.sh", "topic": "x"}, open(fp, "w"))
        S.pin(old_vk, fp)
        S.pin(new_vk, fp)
        d = json.load(open(fp))
        check("b. pin(): the first key is vk, a new one goes beside it in vks (no lock-out)", d["vk"] == old_vk and d["vks"] == [new_vk], d)
        S.pin(new_vk, fp, replace=True)
        check("b. pin(replace): only the new key", json.load(open(fp)) == {"ntfy": "https://ntfy.sh", "topic": "x", "vk": new_vk})
        kp = os.path.join(tmp, "status_sign.json")
        json.dump({"kind": "le-status-sign", "private": old, "vk": old_vk}, open(kp, "w"))
        posted = []
        rc = S.rotate(kp, post=lambda b: (posted.append(b) or (True, "ok")), now=NOW)
        rec = json.load(open(kp))
        check("b. rotate(): hand-over posted (signed by the old key), new key saved, old kept", rc == 0 and len(posted) == 1
              and S.verify_text(posted[0], old_vk) and rec["vk"] != old_vk and S.vk_of(rec["private"]) == rec["vk"]
              and any(f.startswith("status_sign.old-") for f in os.listdir(tmp)), (rc, posted[:1]))
        check("b. ... and its own posts are trusted at once by every reader that trusts the old key",
              rec["vk"] in S.accepted([{"time": NOW, "message": posted[0]}], [old_vk]))
        check("b. rotation_due: not again within 6 h, again after", S.rotation_due(kp, now=NOW + 3600) is None
              and S.rotation_due(kp, now=NOW + 7 * 3600) == posted[0] and S.rotation_due(kp, now=NOW + 7 * 3600 + 60) is None)
        check("b. rotation_due: done after 14 days", S.rotation_due(kp, now=NOW + 15 * 86400) is None and not S.rotation_pending(kp, now=NOW + 15 * 86400))
        refused = S.rotate(kp, post=lambda b: (False, "no network"), now=NOW + 10)
        check("b. rotate() whose post fails changes nothing", refused == 1 and json.load(open(kp))["vk"] == rec["vk"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # the phone
    nd = "\n".join(json.dumps({"event": "message", "id": f"m{i}", "time": m["time"], "message": m["message"]}) for i, m in enumerate(msgs))
    js = ("const F=require('./tools/web_public/pc_feed.js');(async()=>{const nd=%s;const kept=await F.keepSigned(nd,[%s]);"
          "const bals=kept.split('\\n').filter(Boolean).map(l=>JSON.parse(JSON.parse(l).message)).filter(j=>j.kind==='le-live').map(j=>j.brd.ac[0][2]);"
          "const fk=F.feedKeys({vk:%s,vks:[%s,'short']});"
          "console.log(JSON.stringify({bals,fk:fk.length,cand:F.keyCandidate()}));})()"
          % (json.dumps(nd), json.dumps(old_vk), json.dumps(old_vk), json.dumps(new_vk)))
    rc, out, err = node(js)
    try:
        dj = json.loads(out.splitlines()[-1])
    except Exception:  # noqa: BLE001
        dj = {"err": err, "out": out}
    check("b. phone: rotation followed, the stranger dropped (same as Python)", dj.get("bals") == [1.0, 2.0], dj)
    check("b. phone: feedKeys = vk + vks (invalid ones dropped)", dj.get("fk") == 2, dj)
    nd2 = "\n".join(json.dumps({"event": "message", "id": f"s{i}", "time": m["time"], "message": m["message"]}) for i, m in enumerate(steady))
    js2 = ("const F=require('./tools/web_public/pc_feed.js');(async()=>{const k=await F.keepSigned(%s,[%s]);"
           "const c=F.keyCandidate();console.log(JSON.stringify({kept:k.length,cand:c&&c.vk,n:c&&c.n}));})()" % (json.dumps(nd2), json.dumps(old_vk)))
    rc, out, err = node(js2)
    try:
        dj = json.loads(out.splitlines()[-1])
    except Exception:  # noqa: BLE001
        dj = {"err": err, "out": out}
    check("b. phone: the 3-hour window names the new key, keeps none of its posts until the owner taps Trust",
          dj.get("kept") == 0 and dj.get("cand") == bad_vk and dj.get("n") == 14, dj)
    from tools import board as BD
    BD.KEY_CANDIDATE.clear()
    BD.KEY_CANDIDATE.update({"vk": bad_vk, "n": 14, "first": NOW, "last": NOW + 13 * 900})
    g = BD.gather(offline=True, hb={"present": False}, lite={"v": 1})
    BD.KEY_CANDIDATE.clear()
    check("b. board: the candidate is named with the pin command, and NOT believed", "status_sign.py pin " + bad_vk[:12] in json.dumps(g)
          and "NOT believed" in json.dumps(g), json.dumps(g)[:300])


def part_c():
    from engine import today_brief as TB, tg_cmd as TG
    t = TB.text(live(room=140, unreal=-60.0), NOW, views=[{"key": "atlas", "ready": True, "amount": 1000.0, "to_you": 800.0}])
    check("c. /today: accounts, $ today, $ to pass, $ left, payout, setup, news", all(w in t for w in (
        "Zlarior 50K: $49,193", "today +$0", "$3,807 to pass", "left (floor)", "ATLAS 25K funded", "payout requestable now: $1,000",
        "Zlarior 25K #2" if "25K #2" in t else "25K", "Setup: LIT setup ARMED", "News")), t)
    check("c. /today never names BLITZ or a broker id", "BLITZ" not in t.upper().replace("BLITZ_", "") and "MFFUEVBLDR123456" not in t, t)
    check("c. /today with no live view says so", "no live numbers" in TB.text(None, NOW))
    c, say = TG.parse_text("/today")
    check("c. /today parses to the read-only today command", c == {"cmd": "today"} and say is None, (c, say))
    check("c. /today takes no words", TG.parse_text("/today please")[0] is None)
    check("c. /help lists /today", "/today" in TG.HELP)

    class RC:
        busy = False
        runs = []

        def run_external(self, cs, now, reply=None, tg=None):
            RC.runs.append(cs)
            return []
    sent = []

    def http(method, url, body=None):
        if url.endswith("/getUpdates"):
            return 200, json.dumps({"ok": True, "result": [{"update_id": 7, "message": {"message_id": 3, "date": NOW, "text": "/today",
                                                                                         "chat": {"id": 42, "type": "private"}, "from": {"id": 42}}}]})
        sent.append(json.loads(body or b"{}"))
        return 200, json.dumps({"ok": True, "result": {"message_id": 4}})
    tmp = tempfile.mkdtemp(prefix="guard2c_")
    try:
        p = TG.TgCommands(RC(), cfg_fn=lambda: {"telegram": {"token": "x", "chat_id": "42"}}, http=http, path=os.path.join(tmp, "s.json"),
                          clock=lambda: NOW, env={"LE_TG_CMD": "1"}, started_at=NOW - 10, today_live=lambda: live(room=140))
        p.tick(NOW)
        check("c. Telegram /today: answered with the summary, never through the control path",
              any("Zlarior 50K" in str(m.get("text")) for m in sent) and RC.runs == [], (sent[-1:] if sent else None, RC.runs))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    part_a()
    part_b()
    part_c()
    bad = [n for n, ok in RES if not ok]
    print(f"guard2: {len(RES) - len(bad)}/{len(RES)} " + ("passed" if not bad else "FAILED"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
