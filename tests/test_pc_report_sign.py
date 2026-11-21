"""The PC signs its PUBLIC posts (day-security2 2026-11-20, tools/pc_report._signed + tools/status_sign.py; LEAD_WIRES W3).
  a. a full report run (fake ntfy): every public status / ext post verifies under the PC's key, the core carries "svk", every post
     stays a message (<= 4,000 bytes); the phone's pc_feed.js (node) picks the signed core with the vk pinned
  b. the private alert topic is never signed or changed (trade alerts untouched)
  c. never a dropped post: no key, a broken key file, LE_STATUS_SIGN=0 -> the same posts go out unsigned, the run record says why
  d. a test's fake http never uses the PC's own key (only LE_STATUS_SIGN_KEY); ensure_key never makes a key in the cloud / CI
  e. the biggest status the reporter allows (MAX_STATUS_BYTES) still fits once signed with svk
  f. a key that is not the pinned vk: still posted, the run record names it (the phone would drop every post)
    python -X utf8 -m tests.test_pc_report_sign
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["LE_PR_NO_NET"] = "1"

from tests.test_bots_back import Box, FakeHTTP, weekday_10am_et  # noqa: E402
from tests.test_live_publish import hb_payload  # noqa: E402
from tools import pc_report as R  # noqa: E402
from tools import status_sign as S  # noqa: E402

RES = []


def ok(cond, name, info=""):
    RES.append(bool(cond))
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond or not info else f"  -> {str(info)[:300]}"))


def keyfile(d):
    priv, vk = S.keygen()
    p = os.path.join(d, "status_sign.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump({"kind": "le-status-sign", "private": priv, "vk": vk}, fh)
    return p, vk


def run(env_extra):
    now = weekday_10am_et()
    b = Box()
    old = {k: os.environ.get(k) for k in env_extra}
    os.environ.update({k: v for k, v in env_extra.items() if v is not None})
    for k, v in env_extra.items():
        if v is None:
            os.environ.pop(k, None)
    try:
        cfg = b.topic()
        b.hb(hb_payload(now - 120))
        h = FakeHTTP()
        rec = b.run(h, now)
        return rec, h, cfg
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        b.cleanup()


def status_posts(h):
    topic = R.status_feed()["topic"]
    return [c["body"] for c in h.posts(topic)]


def part_a_b(d):
    print("a/b. a full report run with the PC's key")
    kp, vk = keyfile(d)
    rec, h, cfg = run({"LE_STATUS_SIGN_KEY": kp, "LE_STATUS_SIGN": None})
    posts = status_posts(h)
    ok(posts, "the run posted its public status", rec.get("errors"))
    ok(all(S.verify_text(p, vk) for p in posts), "every public post verifies under the PC's key", [p[-120:] for p in posts])
    cores = [json.loads(p) for p in posts if json.loads(p).get("kind") == "le-live"]
    ok(cores and cores[-1].get("svk") == vk, "the core carries svk = the PC's public key (pin it from here)")
    ok(all(len(p.encode("utf-8")) <= R.SIGN_MAX_BYTES for p in posts), "every signed post stays a message (<= 4,000 bytes)",
       [len(p.encode()) for p in posts])
    ok("unsigned" not in rec, "the run record has no 'unsigned' reason", rec.get("unsigned"))
    priv = [c for c in h.posts(cfg["topic"])]
    ok(all('"sg":"' not in str(c["body"]) for c in priv), "b. the private alert topic is never signed (trade alerts as before)")
    nd = "\n".join(json.dumps({"id": str(i), "time": 1, "event": "message", "message": p}) for i, p in enumerate(posts))
    js = ("const F=require('./tools/web_public/pc_feed.js');(async()=>{const t=await F.keepSigned(%s,%s);"
          "const j=F.parseLatest(t,%d);console.log(JSON.stringify({n:t.split('\\n').filter(Boolean).length,k:j&&j.kind}))})()"
          % (json.dumps(nd), json.dumps(vk), weekday_10am_et() + 60))
    r = subprocess.run(["node", "-e", js], cwd=ROOT, capture_output=True, text=True, timeout=60)
    try:
        d2 = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        d2 = {}
    ok(d2.get("n") == len(posts) and d2.get("k") == "le-live", "the phone keeps every signed post and reads the core", (r.stdout, r.stderr[-200:]))
    return posts


def part_c(d, signed_posts):
    print("c. never a dropped post")
    rec, h, _ = run({"LE_STATUS_SIGN_KEY": os.path.join(d, "missing.json"), "LE_STATUS_SIGN": None})
    p = status_posts(h)
    ok(len(p) == len(signed_posts) and all('"sg":"' not in x for x in p), "no key: the same posts go out, unsigned", len(p))
    ok(rec.get("unsigned") == "no key", "the run record says why (no key)", rec.get("unsigned"))
    bad = os.path.join(d, "bad.json")
    with open(bad, "w", encoding="utf-8") as fh:
        json.dump({"private": "bm90IGEga2V5"}, fh)
    rec, h, _ = run({"LE_STATUS_SIGN_KEY": bad, "LE_STATUS_SIGN": None})
    p = status_posts(h)
    ok(len(p) == len(signed_posts) and all('"sg":"' not in x for x in p), "a broken key file: posted unsigned, no error to the bot")
    ok(bool(rec.get("unsigned")) and not any("sign" in e.lower() for e in rec.get("errors") or []), "the reason is noted, never as a failed post",
       (rec.get("unsigned"), rec.get("errors")))
    kp, _ = keyfile(d)
    rec, h, _ = run({"LE_STATUS_SIGN_KEY": kp, "LE_STATUS_SIGN": "0"})
    p = status_posts(h)
    ok(p and all('"sg":"' not in x for x in p) and "unsigned" not in rec, "LE_STATUS_SIGN=0: unsigned, as before, quietly")


def part_d(d):
    print("d. whose key")
    home = os.path.join(d, "fakehome")
    os.makedirs(os.path.join(home, ".olympus"))
    priv, vk = S.keygen()
    with open(os.path.join(home, ".olympus", "status_sign.json"), "w", encoding="utf-8") as fh:
        json.dump({"private": priv}, fh)
    old = S.DEFAULT_KEY
    S.DEFAULT_KEY = os.path.join(home, ".olympus", "status_sign.json")
    try:
        rec, h, _ = run({"LE_STATUS_SIGN_KEY": None, "LE_STATUS_SIGN": None})
    finally:
        S.DEFAULT_KEY = old
    ok(all('"sg":"' not in x for x in status_posts(h)), "a fake http (a test on the PC) never signs with the PC's own key")
    p = os.path.join(d, "ci", "k.json")
    ok(S.ensure_key(p, env={"GITHUB_ACTIONS": "true", "LE_STATUS_SIGN_KEYGEN": "1"}) is None and not os.path.exists(p),
       "ensure_key makes no key in CI / the cloud")
    ok(S.ensure_key(p, env={"LE_STATUS_SIGN_KEYGEN": "1"}, say=lambda *_: None) and os.path.exists(p), "ensure_key makes one on the PC")
    v1 = S.ensure_key(p, env={"LE_STATUS_SIGN_KEYGEN": "1"}, say=lambda *_: None)
    ok(v1 == S.vk_of(S.load_key(p)), "a second call keeps the same key")
    if os.name != "nt":
        ok(oct(os.stat(p).st_mode & 0o777) == "0o600", "the key file is 0600")


def part_e(d):
    print("e. the biggest allowed status still fits")
    kp, vk = keyfile(d)
    big = {"v": 1, "kind": "le-live", "t": 1, "pad": "x" * (R.MAX_STATUS_BYTES - 40)}
    body = json.dumps(big, separators=(",", ":"))
    body = body[: R.MAX_STATUS_BYTES - 2] + '"}' if len(body) > R.MAX_STATUS_BYTES else body
    os.environ["LE_STATUS_SIGN_KEY"] = kp
    try:
        out = R._signed(body, core=True, real=False)
    finally:
        os.environ.pop("LE_STATUS_SIGN_KEY", None)
    ok(len(body.encode()) <= R.MAX_STATUS_BYTES and S.verify_text(out, vk) and len(out.encode()) <= R.SIGN_MAX_BYTES and '"svk"' in out,
       "a %d-byte core signs with svk to %d bytes (<= 4,000)" % (len(body.encode()), len(out.encode())))


def part_f(d):
    print("f. a key that is not the pinned vk (new PC / profile) is named in the run record (redteam 2026-11-21)")
    kp, vk = keyfile(d)
    os.makedirs(os.path.join(d, "other"), exist_ok=True)
    _p2, other = keyfile(os.path.join(d, "other"))          # the key a pinned vk would name (another file: kp stays)
    real_pin = S.feed_vk
    os.environ["LE_STATUS_SIGN_KEY"] = kp
    try:
        S.feed_vk = lambda path=None: other
        out = R._signed('{"v":1,"kind":"le-live","t":1}', core=True, real=True)
        why = R.SIGN_STATE.get("why")
        ok(S.verify_text(out, vk) and why and "pinned vk" in why, "still posted and signed; the run record says the key is not the pinned one", why)
        S.feed_vk = lambda path=None: vk
        R._signed('{"v":1,"kind":"le-live","t":2}', core=True, real=True)
        ok(R.SIGN_STATE.get("why") is None, "the pinned key itself: nothing to say")
        S.feed_vk = lambda path=None: None
        R._signed('{"v":1,"kind":"le-live","t":3}', core=True, real=True)
        ok(R.SIGN_STATE.get("why") is None, "no vk pinned yet: nothing to say (as today)")
    finally:
        S.feed_vk = real_pin
        os.environ.pop("LE_STATUS_SIGN_KEY", None)


def main():
    with tempfile.TemporaryDirectory() as d:
        posts = part_a_b(d)
        part_c(d, posts)
        part_d(d)
        part_e(d)
        part_f(d)
    n = sum(RES)
    print(f"\npc_report_sign: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
