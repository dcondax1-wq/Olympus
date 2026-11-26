"""day-noleak 2026-11-26: a sandbox / copy of the repo never posts to the REAL phone channels; the board ignores a status post
that is not the PC's.  python -X utf8 -m tests.test_noleak
a. engine/pc_identity: not Windows = dry run; LE_NO_POST; GitHub Actions; the owner's PC adopts once from its own account files;
   a copied folder (another MachineGuid) = dry run.
b. the rehearsal path posts nothing: every real sender (pc_report, notify, alert_bus / tg_cmd, alerts, push relay + Web Push,
   data-feed answer, report keeper) with the network replaced by a recorder -> zero calls.
c. tools/board.only_pc_key: the PC's key (many posts over hours) wins; an unsigned core post (a Linux sandbox) and another key's
   post are dropped and counted; no PC key = the messages as before.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import pc_identity as PI  # noqa: E402

RES = []


def check(name, ok, info=None):
    RES.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  {str(info)[:300]}"))


def fresh():
    PI._CACHE.clear()
    PI._SAID.clear()


def part_a(tmp):
    env = {}
    fresh()
    PI._IS_NT, PI._GUID = False, None
    ok, why = PI.check(tmp, env)
    check("a. not Windows (a sandbox) = dry run", not ok and "not Windows" in why, why)
    fresh()
    check("a. LE_NO_POST=1 = dry run", not PI.check(tmp, {"LE_NO_POST": "1", "GITHUB_ACTIONS": "true"})[0])
    fresh()
    check("a. GitHub Actions (cloud monitor) still posts", PI.check(tmp, {"GITHUB_ACTIONS": "true"})[0])
    PI._IS_NT, PI._GUID = True, "guid-owner-pc"
    try:
        fresh()
        ok, why = PI.check(tmp, env)
        check("a. Windows without the bot's account files = dry run", not ok and not os.path.exists(os.path.join(tmp, "data", "pc_identity.json")), why)
        os.makedirs(os.path.join(tmp, "data"), exist_ok=True)
        with open(os.path.join(tmp, "data", "accounts.json"), "w") as fh:
            fh.write("[]")
        fresh()
        ok, why = PI.check(tmp, env)
        rec = json.load(open(os.path.join(tmp, "data", "pc_identity.json")))
        check("a. the owner's PC adopts its identity once (Windows + its account files) and posts",
              ok and rec.get("fp") == PI.fingerprint() and "guid" not in json.dumps(rec), (why, rec))
        fresh()
        check("a. next run: the stored identity matches", PI.check(tmp, env)[0])
        PI._GUID = "guid-another-machine"
        fresh()
        ok, why = PI.check(tmp, env)
        check("a. the same folder copied to another machine = dry run", not ok and "another machine" in why, why)
    finally:
        PI._IS_NT, PI._GUID = (os.name == "nt"), None
        fresh()


def part_b():
    calls = []
    real = urllib.request.urlopen

    def rec(req, *a, **k):
        m = req.get_method() if hasattr(req, "get_method") else "GET"
        if m != "GET":                                # reads (polling a topic) are allowed; only sends count
            calls.append(f"{m} {getattr(req, 'full_url', str(req))}")
        raise OSError("blocked by the test")
    urllib.request.urlopen = rec
    PI._IS_NT = False
    fresh()
    saved = {k: os.environ.pop(k, None) for k in ("GITHUB_ACTIONS", "LE_PR_NO_NET")}
    try:
        from tools import pc_report as R
        ok, why = R.ntfy_post("https://ntfy.sh", "le-status-topic", '{"kind":"le-live"}')
        check("b. pc_report status post (real http) = dry run, nothing sent", not ok and "dry run" in why, why)
        R.default_http("GET", "https://ntfy.sh/x/json?poll=1")      # a read: allowed (and recorded as not a send)
        from engine import notify as N
        check("b. notify._post (ntfy alert) = False", N._post("https://ntfy.sh", "t", {"title": "x", "body": "y", "priority": "high", "tags": "x"}) is False)
        from engine import alert_bus as AB, tg_cmd as TG
        old = AB._HTTP
        AB._HTTP = None
        try:
            check("b. alert_bus._http (Telegram / Discord) = dry run", AB._http("POST", "https://api.telegram.org/botX/sendMessage", b"{}")[0] == 0)
            check("b. tg_cmd (reads / replies through alert_bus) = dry run", TG._http("POST", "https://api.telegram.org/botX/getUpdates", b"{}")[0] == 0)
        finally:
            AB._HTTP = old
        from engine import alerts as AL
        check("b. engine/alerts._post = 0", AL._post("https://discord.com/api/webhooks/x", {"content": "x"}) == 0)
        from engine import push as P
        check("b. Web Push = 0", P._send_builtin({"endpoint": "https://push.example/x", "keys": {}}, b"x", "", "") == 0)
        relay = P.Relay() if hasattr(P, "Relay") else None
        if relay is not None and hasattr(relay, "_req"):
            relay.http = None
            try:
                relay._req("POST", "https://ntfy.sh/relay", b"{}")
                check("b. push relay POST refused", False)
            except RuntimeError as e:
                check("b. push relay POST refused", "dry run" in str(e) or "self-test" in str(e), e)
        from engine import datafeed as DF
        ok, why, _ = DF.send(b"zip", {"kind": "x"}, env={})
        check("b. data-feed answer = dry run", not ok and "dry run" in why, why)
        from engine import report_keeper as RK
        os.environ.pop("LE_NO_AUTOSTART", None)
        k = RK.Keeper(run=lambda *a, **kw: (calls.append("child:" + " ".join(map(str, a[0]))) or (0, "")), log=lambda t: None)
        check("b. report keeper (it ran pc_report in the sandbox) does not start", k.start() is False)
        check("b. the rehearsal path SENT nothing (zero POST / PUT)", calls == [], calls)
    finally:
        urllib.request.urlopen = real
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
        PI._IS_NT = os.name == "nt"
        fresh()


def part_c():
    try:
        from tools import status_sign as S
        pc_priv, pc_vk = S.keygen()
        other_priv, _ = S.keygen()
    except Exception as e:  # noqa: BLE001
        check("c. (cryptography missing: skipped)", True, e)
        return
    from tools import board as BD
    t0 = 1_795_000_000

    def core(t, priv=None, verdict="TRADING"):
        body = json.dumps({"v": 1, "kind": "le-live", "t": t, "pc_verdict": {"code": verdict}}, separators=(",", ":"))
        if priv:
            body = S.sign_text(body[:-1] + ',"svk":"' + S.vk_of(priv) + '"}', priv)
        return {"time": t, "message": body}
    pc = [core(t0 + i * 900, pc_priv) for i in range(6)]
    ext = {"time": t0 + 1000, "message": json.dumps({"kind": "le-live-ext", "x": 1})}          # an unsigned (too big) ext: kept
    sandbox = core(t0 + 5000, None, "DISABLED")                                                # a Linux sandbox: unsigned core
    forged = core(t0 + 5100, other_priv, "DISABLED")                                           # another key
    BD.FOREIGN.update(n=0, last_t=None)
    kept = BD.only_pc_key(pc + [ext, sandbox, forged])
    check("c. the PC's posts + its unsigned ext kept; the sandbox's unsigned core and another key's post dropped",
          len(kept) == 7 and sandbox not in kept and forged not in kept and ext in kept and BD.FOREIGN["n"] == 2, (len(kept), BD.FOREIGN))
    BD.FOREIGN.update(n=0, last_t=None)
    few = pc[:2] + [sandbox]
    check("c. no established PC key (2 posts) = messages as before", BD.only_pc_key(few) == few and BD.FOREIGN["n"] == 0)
    g = BD.gather(offline=True, hb={"present": False}, lite={"v": 1})
    BD.FOREIGN.update(n=1, last_t=t0)
    g2 = BD.gather(offline=True, hb={"present": False}, lite={"v": 1})
    txt = json.dumps(g2, default=str)
    check("c. board.gather says it ignored another machine's post", "NOT signed by the PC" in txt and "NOT signed by the PC" not in json.dumps(g, default=str), txt[:300])
    BD.FOREIGN.update(n=0, last_t=None)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="noleak_")
    try:
        part_a(tmp)
        part_b()
        part_c()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for n, ok in RES if not ok]
    print(f"noleak: {len(RES) - len(bad)}/{len(RES)} " + ("passed" if not bad else "FAILED"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
