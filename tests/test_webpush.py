"""Olympus phone notifications, the PC side (2026-11-19, owner: "I want notifications on my phone"): engine/push.py's own key, the
sealed relay intake, the send to a (mocked) push service, the phone-first / ntfy-backup rule (never twice on one phone), the
15-minute report's app-first alerts and its "wp" block, and the clean fallback without `cryptography`. No network: a fake relay,
a fake push service (urllib mocked) and fake ntfy posts record what would go out.
  a. key: made once in data/push.json (0600), the same next time; a broken key is set aside; app_block = public keys + 8-hex ids
  b. relay intake: a sealed subscription joins, ONE welcome push to that phone; replays, old keys, junk, stale, wrong secret ignored;
     test / unsub proved with the phone's own secret; at most 5 phones; a gone phone (410) is dropped; nothing posted to ntfy
  c. send: the built-in RFC 8291 / 8292 sender against a mocked endpoint: headers, VAPID JWT, the phone decrypts the alert
  d. pc_notify's worker: real entries / exits to the phone with the account name, one tag per trade + account, the ntfy copy only
     when no phone took it, the report's own copy dropped; Paper / Sim / BLITZ never; ops only with LE_PUSH_EXTRA=1
  e. tools/pc_report.py: the core post carries wp untouched by the privacy pass and the trims; app-first alerts, ntfy as backup;
     no extra ntfy post
  f. no `cryptography` (a child process where it cannot import): no key, no wp, no intake, and the entry still goes to ntfy
    python -X utf8 -m tests.test_webpush
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import notify as N  # noqa: E402
from engine import push as P  # noqa: E402

RES: list = []


def check(name, cond, info=""):
    RES.append((name, bool(cond)))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:700]}"), flush=True)


def phone(i=0):
    """A fake phone: its P-256 key + auth secret and the subscription it would make."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    k = ec.generate_private_key(ec.SECP256R1())
    pub = k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    auth = os.urandom(16)
    return k, auth, {"endpoint": f"https://web.push.apple.com/QK{i}x{os.urandom(6).hex()}", "keys": {"p256dh": P.b64u(pub), "auth": P.b64u(auth)}}


def decrypt(body, ua_key, auth):
    """RFC 8291 receiver side: what the phone does with what the PC sent."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt, idlen = body[:16], body[20]
    as_pub, ct = body[21:21 + idlen], body[21 + idlen:]
    ua_pub = ua_key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    shared = ua_key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_pub))
    h = lambda k, d: hmac.new(k, d, hashlib.sha256).digest()          # noqa: E731
    prk = h(salt, h(h(auth, shared), b"WebPush: info\x00" + ua_pub + as_pub + b"\x01"))
    return AESGCM(h(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]).decrypt(h(prk, b"Content-Encoding: nonce\x00\x01")[:12], ct, None)[:-1]


class FakeRelay:
    """The relay topic in memory (ntfy's JSON lines), and every POST counted (the PC must post nothing)."""

    def __init__(self):
        self.msgs, self.t, self.posts = [], 1_795_000_000, 0

    def add(self, obj, t=None):
        self.t += 1
        self.msgs.append({"id": str(self.t), "time": t or self.t, "event": "message", "topic": "x", "message": json.dumps(obj)})

    def __call__(self, method, url, body=None):
        if method == "POST":
            self.posts += 1
            return "{}"
        return "\n".join(json.dumps(m) for m in self.msgs)


class Sandbox:
    """engine/push + engine/notify pointed at temp files (the real data/ files are never touched)."""

    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="webpush_")
        self.saved = {"cfg": P.CONFIG_PATH, "sent": P.SENT_PATH, "pck": P.PC_KEY_PATH, "inst": N.INSTANT_PATH, "settings": N.settings,
                      "notifier": P._PC["notifier"], "extra": os.environ.get("LE_PUSH_EXTRA")}
        P.CONFIG_PATH = os.path.join(self.dir, "push.json")
        P.SENT_PATH = os.path.join(self.dir, "push_sent.json")
        P.PC_KEY_PATH = os.path.join(self.dir, "push_pc_key.json")
        N.INSTANT_PATH = os.path.join(self.dir, "instant.json")
        N.settings = lambda path=None: N.merge({"quiet_hours": {"off": True}})
        P._PC["notifier"] = None
        os.environ.pop("LE_PUSH_EXTRA", None)

    def close(self):
        P.CONFIG_PATH, P.SENT_PATH, P.PC_KEY_PATH = self.saved["cfg"], self.saved["sent"], self.saved["pck"]
        N.INSTANT_PATH, N.settings = self.saved["inst"], self.saved["settings"]
        P._PC["notifier"] = self.saved["notifier"]
        if self.saved["extra"] is None:
            os.environ.pop("LE_PUSH_EXTRA", None)
        else:
            os.environ["LE_PUSH_EXTRA"] = self.saved["extra"]
        shutil.rmtree(self.dir, ignore_errors=True)


def sealed(kind, body, box_pub, t=None, info=P.SUB_INFO):
    """What Olympus posts (tools/web_public/jarvis/push-ui.js sendSealed): {"le", "v": 2, "box"} sealed to the PC's box key."""
    return {"le": kind, "v": 2, "box": P.seal(json.dumps({"le": kind, "t": int(t or time.time()), **body}).encode(), box_pub, info)}


def recorder(code=201):
    out = []

    def send_one(sub, data, priv, pub):
        out.append({"ep": sub["endpoint"], "data": json.loads(data), "pub": pub})
        return code(sub) if callable(code) else code
    return out, send_one


# ------------------------------------------------------------------------------------------------ a. the key
def part_a():
    sb = Sandbox()
    try:
        k1 = P.own_key()
        k2 = P.own_key()
        check("a. the PC makes its own VAPID key once (data/push.json), the same on the next call",
              k1 and k2 and k1["private"] == k2["private"] and len(k1["public"]) == 87 and json.load(open(P.CONFIG_PATH))["vapid_private"] == k1["private"], (k1, k2))
        check("a. the key file is private (0600 where it applies)", os.name == "nt" or (os.stat(P.CONFIG_PATH).st_mode & 0o077) == 0)
        wp = P.app_block()
        raw = json.dumps(wp, separators=(",", ":"))
        check("a. app_block: k = the VAPID public key, b = the PC's box key, d = [] before any phone; small (< 300 bytes); never the private key",
              wp and wp["k"] == k1["public"] and wp["b"] == P.pc_public_key() and wp["d"] == [] and len(raw) < 300 and k1["private"] not in raw
              and P.app_block_ok(wp), (wp, len(raw)))
        check("a. app_block_ok refuses anything but public keys and hex ids (a free text field, a bad key, an extra key)",
              not P.app_block_ok({"k": "x", "b": wp["b"], "d": []}) and not P.app_block_ok({**wp, "note": "hi"})
              and not P.app_block_ok({**wp, "d": ["Zlarior 50K"]}) and not P.app_block_ok(None))
        f = json.load(open(P.CONFIG_PATH))
        f["vapid_private"] = "broken"
        P._write_private(P.CONFIG_PATH, f)
        k3 = P.own_key()
        f = json.load(open(P.CONFIG_PATH))
        check("a. a broken key is set aside and a new one made (the phones subscribe again by themselves)",
              k3 and k3["public"] != k1["public"] and f.get("vapid_private_bad") == "broken" and P.app_block()["k"] == k3["public"], f.keys())
        check("a. pc_config sends with the PC's own key (no cloud, no GitHub fetch)", P.pc_config()["public"] == k3["public"] and P.pc_config()["source"] == "file")
        check("a. the PC notifier has no relay: no 'sent' marker is ever posted (the cloud that read them is gone; ntfy budget)",
              P.pc_notifier().relay is None)
    finally:
        sb.close()


# ------------------------------------------------------------------------------------------------ b. the relay intake
def part_b():
    sb = Sandbox()
    try:
        now = int(time.time())
        relay = FakeRelay()
        R = P.Relay(base="https://ntfy.sh", topic="le-test", http=relay)
        wp = P.app_block()
        ka, auth_a, sub_a = phone(1)
        relay.add(sealed("sub", {"sub": sub_a, "key": wp["k"], "ua": "iPhone"}, wp["b"]))
        sent, send_one = recorder()
        r = P.intake(R.read(), now, sender=send_one)
        rows = json.load(open(P.CONFIG_PATH)).get("devices") or []
        ida = P.endpoint_id(sub_a["endpoint"])
        check("b. a sealed subscription made with the PC's key joins data/push.json devices",
              r["added"] == [ida] and len(rows) == 1 and rows[0]["sub"] == sub_a and rows[0]["key"] == wp["k"] and rows[0]["ua"] == "iPhone", (r, rows))
        check("b. that phone alone gets ONE welcome push", len(sent) == 1 and sent[0]["ep"] == sub_a["endpoint"] and sent[0]["data"]["title"] == "Olympus notifications are on"
              and r["sent"] == 1, sent)
        check("b. the next status post lists the phone by 8 hex characters", P.app_block()["d"] == [ida[:8]], P.app_block())
        r2 = P.intake(R.read(), now + 300, sender=send_one)
        check("b. the same relay message on the next 5-minute run: nothing again (no second welcome)", not r2["added"] and len(sent) == 1, r2)
        relay.add(sealed("sub", {"sub": sub_a, "key": wp["k"], "ua": "iPhone"}, wp["b"]))
        r3 = P.intake(R.read(), now + 600, sender=send_one)
        check("b. the phone sending its subscription again (an open after 30 min): kept, no second welcome", not r3["added"] and len(sent) == 1
              and len(json.load(open(P.CONFIG_PATH))["devices"]) == 1, r3)
        kb, auth_b, sub_b = phone(2)
        relay.add(sealed("sub", {"sub": sub_b, "key": P.generate_keys()[1]}, wp["b"]))               # made for another key
        relay.add({"le": "sub", "v": 2, "box": "A" * 300})                                           # junk
        relay.add(sealed("sub", {"sub": sub_b, "key": wp["k"]}, wp["b"], info=b"le-push-pc-v1"))     # sealed with the wrong label
        relay.add(sealed("sub", {"sub": sub_b, "key": wp["k"]}, wp["b"], t=now - 4 * 86400))         # 4 days old
        relay.add({"le": "sub", "sub": sub_b, "key": wp["k"]})                                       # the old app's plain kind: not ours
        bad = dict(sub_b, endpoint="https://evil.example.com/push/1")
        relay.add(sealed("sub", {"sub": bad, "key": wp["k"]}, wp["b"]))                              # not a push service
        r4 = P.intake(R.read(), now + 900, sender=send_one)
        check("b. ignored: another key, junk, a wrong label, a stale request, the old plain kind, an endpoint that is no push service",
              not r4["added"] and r4["ignored"] == 5 and len(json.load(open(P.CONFIG_PATH))["devices"]) == 1 and len(sent) == 1, r4)
        relay.add(sealed("test", {"id": ida, "auth": "WRONG"}, wp["b"]))
        r5 = P.intake(R.read(), now + 1200, sender=send_one)
        relay.add(sealed("test", {"id": ida, "auth": sub_a["keys"]["auth"]}, wp["b"]))
        r6 = P.intake(R.read(), now + 1500, sender=send_one)
        r7 = P.intake(R.read(), now + 1800, sender=send_one)
        check("b. 'Send a test' needs the phone's own secret: wrong = ignored, right = ONE test push to that phone, not again next run",
              not r5["tests"] and r6["tests"] == [ida] and not r7["tests"] and len(sent) == 2 and sent[1]["data"]["title"] == "Test from your PC"
              and sent[1]["ep"] == sub_a["endpoint"], (r5, r6, r7, sent[-1:]))
        relay.add(sealed("unsub", {"id": ida, "auth": "WRONG"}, wp["b"]))
        P.intake(R.read(), now + 2100, sender=send_one)
        kept = len(json.load(open(P.CONFIG_PATH))["devices"])
        relay.add(sealed("unsub", {"id": ida, "auth": sub_a["keys"]["auth"]}, wp["b"]))
        r8 = P.intake(R.read(), now + 2400, sender=send_one)
        check("b. 'Turn off' with a wrong secret keeps the phone; with its own secret removes it",
              kept == 1 and r8["removed"] == [ida] and json.load(open(P.CONFIG_PATH))["devices"] == [], r8)
        subs = [phone(10 + i)[2] for i in range(7)]
        n0 = len(sent)
        rs = []
        for i, s in enumerate(subs):                     # day-security2 (W4): a new phone joins with the PC's one-time code
            code = json.load(open(P.CONFIG_PATH))["pair"]["code"]
            relay.add(sealed("sub", {"sub": s, "key": wp["k"], "pair": code}, wp["b"], t=now + 2500 + i))
            rs.append(P.intake(R.read(), now + 2700 + i, sender=send_one))
        dv = json.load(open(P.CONFIG_PATH))["devices"]
        check("b. at most 5 phones: with the code the first 5 join (each gets its welcome); a full list of recent phones pushes none out",
              len(dv) == P.MAX_DEVICES and sum(1 for x in sent[n0:] if x["data"]["title"] == "Olympus notifications are on") == P.MAX_DEVICES
              and {d["id"] for d in dv} == {P.endpoint_id(s["endpoint"]) for s in subs[:5]}
              and rs[5].get("full") == 1 and rs[6].get("full") == 1, (len(dv), len(sent) - n0, rs[5:]))
        check("b. the owner's phones are told once that the list is full (then at most every 6 h)",
              rs[5].get("told") == P.MAX_DEVICES and not rs[6].get("told")
              and sum(1 for x in sent[n0:] if x["data"]["title"] == "New phone wants your alerts") == P.MAX_DEVICES
              and all(x["data"]["title"] in ("New phone wants your alerts", "New phone added to your alerts", "Olympus notifications are on")
                      for x in sent[n0:]), rs[5:])
        gone_ep = subs[4]["endpoint"]
        out, send410 = recorder(lambda sub: 410 if sub["endpoint"] == gone_ep else 201)
        res = P.app_send(P.text_payload("PC", "test", "t", "b", key="k1"), sender=send410)
        check("b. a phone the push service calls gone (410: deleted, or another key) is dropped; the others got it",
              res["sent"] == 4 and len(json.load(open(P.CONFIG_PATH))["devices"]) == 4 and P.endpoint_id(gone_ep)[:8] not in P.app_block()["d"], res)
        check("b. the intake posted nothing to ntfy (the PC only reads the relay)", relay.posts == 0, relay.posts)
        check("b. the relay reader keeps Olympus's 'test' kind", "test" in P.RELAY_KINDS)
    finally:
        sb.close()


# ------------------------------------------------------------------------------------------------ c. send to a mocked endpoint
def _PI_reset():
    from engine import pc_identity as _PI
    _PI.FORCE = None


def part_c():
    sb = Sandbox()
    import urllib.request
    real = urllib.request.urlopen
    try:
        k = P.own_key()
        ua_key, auth, sub = phone(3)
        cfg = dict(P.pc_config(), subs=[sub])
        seen = []

        class Resp:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            seen.append(req)
            return Resp()
        urllib.request.urlopen = fake_urlopen
        from engine import pc_identity as _PI         # day-noleak: this test fakes urlopen itself, so the identity gate is lifted
        _PI.FORCE = True
        p = P.app_payload(P.entry_payload("Zlarior 50K", "LONG", 6, 1795050000, src="pc", entry=24980.25, stop=24955, target=25360))
        r = P.send(p, cfg=cfg, sender=P._send_builtin)
        req = seen[0] if seen else None
        h = {kk.lower(): v for kk, v in (req.header_items() if req else [])}
        check("c. one POST to the phone's push endpoint: aes128gcm, TTL, Urgency high", r.get("sent") == 1 and req.full_url == sub["endpoint"]
              and req.get_method() == "POST" and h.get("content-encoding") == "aes128gcm" and h.get("ttl") == str(P.TTL_S) and h.get("urgency") == "high", (r, h))
        auth_h = h.get("authorization", "")
        tok = auth_h.split("t=")[1].split(",")[0] if "t=" in auth_h else ""
        kpart = auth_h.split("k=")[1] if "k=" in auth_h else ""
        okv = False
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
            hd, bd, sg = tok.split(".")
            raw = P.b64u_dec(sg)
            pubk = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), P.b64u_dec(kpart))
            pubk.verify(encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")), f"{hd}.{bd}".encode(), ec.ECDSA(hashes.SHA256()))
            claims = json.loads(P.b64u_dec(bd))
            okv = claims["aud"] == "https://web.push.apple.com" and claims["exp"] > time.time()
        except Exception as e:  # noqa: BLE001
            okv = repr(e)
        check("c. VAPID: the JWT verifies with the PC's own public key (k=), aud = the push service", okv is True and kpart == k["public"], okv)
        got = json.loads(decrypt(req.data, ua_key, auth)) if req is not None else {}
        check("c. the phone decrypts it: 'Zlarior 50K: LONG 6 MNQ @ 24,980.25' with stop / target $, the trade's own tag, opens the NQ page",
              got.get("title") == "Zlarior 50K: LONG 6 MNQ @ 24,980.25" and got.get("body", "").startswith("stop 24,955.00 (-$303), target 25,360.00 (+$4,557)")
              and got.get("tag") == P.app_trade_tag(p) and got.get("url") == "#nq" and got.get("kind") == "fill", got)
        check("c. under the 4 KB push limit", len(req.data) < 4096, len(req.data))
    finally:
        _PI_reset()
        urllib.request.urlopen = real
        sb.close()


# ------------------------------------------------------------------------------------------------ d. pc_notify's worker
def part_d():
    sb = Sandbox()
    try:
        P.own_key()
        ntfy = []

        def fake_ntfy(p):                      # the real instant_entry (its filters), a fake ntfy post
            return N.instant_entry(p, cfg={"ntfy": "https://ntfy.sh", "topic": "nq-test-topic-0000"},
                                   poster=lambda base, topic, msg: ntfy.append(msg) or True)

        def fake_ntfy_exit(p):                 # the real instant_exit, a fake post (never this PC's real topic)
            return N.instant_exit(p, cfg={"ntfy": "https://ntfy.sh", "topic": "nq-test-topic-0000"},
                                  poster=lambda base, topic, msg: ntfy.append(msg) or True)
        et0 = 1795050000
        fill = P.entry_payload("Zlarior 50K", "LONG", 6, et0, src="pc", entry=24980.25, stop=24955, target=25360)
        r = P._pc_send(dict(fill), sender=recorder()[1], ntfy=fake_ntfy)
        check("d. no phone yet: the entry goes to the ntfy alert topic (the backup), at once", r.get("skipped") == "no phone" and r.get("ntfy") == "sent" and len(ntfy) == 1, r)
        _ka, _aa, sub = phone(4)
        f = json.load(open(P.CONFIG_PATH))
        f["devices"] = [{"id": P.endpoint_id(sub["endpoint"]), "sub": sub, "key": P.own_key()["public"], "seen": 1}]
        P._write_private(P.CONFIG_PATH, f)
        sent, send_one = recorder()
        fill2 = P.entry_payload("Zlarior 50K", "SHORT", 4, et0 + 3600, src="pc", entry=25100, stop=25120, target=24900)
        r = P._pc_send(dict(fill2), sender=send_one, ntfy=fake_ntfy, ntfy_exit=fake_ntfy_exit)
        check("d. with a phone: the entry goes to the phone ('Zlarior 50K: SHORT 4 MNQ @ 25,100.00') AND to ntfy (2026-11-20: a push "
              "service's 'accepted' is not proof the phone showed it)",
              r.get("sent") == 1 and len(sent) == 1 and sent[0]["data"]["title"] == "Zlarior 50K: SHORT 4 MNQ @ 25,100.00" and len(ntfy) == 2
              and ntfy[-1]["title"] == "Zlarior 50K: SHORT 4 MNQ @ 25,100.00" and r.get("ntfy") == "sent", (r, sent))
        check("d. the same entry from a second path (narrator / NinjaTrader): nothing more",
              P._pc_send(dict(fill2), sender=send_one, ntfy=fake_ntfy, ntfy_exit=fake_ntfy_exit).get("dup") and len(sent) == 1 and len(ntfy) == 2)
        check("d. instant_entry would refuse it too (recorded as sent)", fake_ntfy(dict(fill2)) == "already sent" and len(ntfy) == 2)
        kept = [m["key"] for m in N.apply([{"key": f"open:lit:{et0 + 3600 + 30}", "priority": "high"}, {"key": f"open:atlas:{et0 + 9000}", "priority": "high"}],
                                          et0, N.merge({"quiet_hours": {"off": True}}))]
        check("d. the 15-minute report drops its own copy of that entry (key time, 90 s), keeps another trade", kept == [f"open:atlas:{et0 + 9000}"], kept)
        out = P.outcome_payload("Zlarior 50K", "SHORT", "TARGET", 605.4, et0 + 3600, et0 + 5400, src="pc", R=2.0, qty=4)
        r = P._pc_send(dict(out), sender=send_one, ntfy=fake_ntfy, ntfy_exit=fake_ntfy_exit)
        check("d. the exit goes to the phone: 'Zlarior 50K: closed SHORT +$605 (target)', '+2.0R · 4 MNQ', in the entry's notification "
              "(same tag), AND to ntfy",
              r.get("sent") == 1 and sent[-1]["data"]["title"] == "Zlarior 50K: closed SHORT +$605 (target)" and "+2.0R · 4 MNQ" in sent[-1]["data"]["body"]
              and sent[-1]["data"]["tag"] == sent[0]["data"]["tag"] and len(ntfy) == 3 and ntfy[-1]["title"] == "Zlarior 50K: closed SHORT +$605 (target)"
              and r.get("ntfy") == "sent", (r, sent[-1]))
        kept = [m["key"] for m in N.apply([{"key": f"close:lit:{et0 + 3600}", "priority": "default"}, {"key": f"close:lit:{et0 + 7777}", "priority": "default"}],
                                          et0, N.merge({"quiet_hours": {"off": True}}))]
        check("d. the report drops its own copy of that exit, keeps another one", kept == [f"close:lit:{et0 + 7777}"], kept)
        b1 = P.entry_payload("Zlarior 25K #2", "SHORT", 2, et0 + 3600, src="pc")
        check("d. two accounts entering on the same bar get two notifications (tag per trade AND account)", P.app_trade_tag(b1) != P.app_trade_tag(fill2)
              and P.app_trade_tag(P.outcome_payload("Zlarior 25K #2", "SHORT", "STOP", -50, et0 + 3600, et0 + 4000)) == P.app_trade_tag(b1))
        fail_sent, send500 = recorder(500)
        fill3 = P.entry_payload("Zlarior 50K", "LONG", 2, et0 + 7200, src="pc", entry=25000, stop=24990, target=25100)
        r = P._pc_send(dict(fill3), sender=send500, ntfy=fake_ntfy, ntfy_exit=fake_ntfy_exit)
        check("d. the phone's push service fails (500): the entry still goes to ntfy (never lost, never twice)", len(fail_sent) == 1 and r.get("ntfy") == "sent"
              and len(ntfy) == 4, r)
        n0 = len(sent)
        for i, a in enumerate(("Paper", "Sim101", "BLITZ 25K (SIM)")):
            P._pc_send(dict(fill, key=f"fill:{et0 + 100 + i}", account=a), sender=send_one, ntfy=fake_ntfy, ntfy_exit=fake_ntfy_exit)
        P._pc_send(dict(fill, key=f"fill:{et0 + 200}", strategy="BLITZ"), sender=send_one, ntfy=fake_ntfy, ntfy_exit=fake_ntfy_exit)
        check("d. Paper / Sim101 / BLITZ entries: never to the phone, never to ntfy", len(sent) == n0 and len(ntfy) == 4, (len(sent), len(ntfy)))
        ops = P.text_payload("PC", "ops", "Day summary", "x", key="ops:eod:1")
        r = P._pc_send(dict(ops), sender=send_one)
        os.environ["LE_PUSH_EXTRA"] = "1"
        r2 = P._pc_send(dict(ops, key="ops:eod:2"), sender=send_one)
        os.environ.pop("LE_PUSH_EXTRA", None)
        check("d. an ops-helper notice goes to the phone only with LE_PUSH_EXTRA=1 (owner: important only; the report says it already)",
              r.get("skipped") == "not for the phone" and r2.get("sent") == 1, (r, r2))
        r = P.pc_send_now(P.text_payload("PC", "test", "Test", "x", key="t1"), sender=send_one)
        check("d. a test notice always goes (pc_send_now)", r.get("sent") == 1, r)
        N.settings = lambda path=None: N.merge({"alerts": {"trade_closed": False}, "quiet_hours": {"off": True}})
        n0 = len(sent)
        nn = len(ntfy)
        P._pc_send(P.outcome_payload("Zlarior 50K", "LONG", "STOP", -300, et0 + 7200, et0 + 7300), sender=send_one, ntfy=fake_ntfy,
                   ntfy_exit=fake_ntfy_exit)
        check("d. trade_closed switched off in notify_settings.json: no exit push (phone or ntfy)", len(sent) == n0 and len(ntfy) == nn)
        N.settings = lambda path=None: N.merge({})
        fill4 = P.entry_payload("Zlarior 50K", "LONG", 2, et0 + 20000, src="pc", entry=25000, stop=24990, target=25100)
        t3 = 1795060000 - 1795060000 % 86400 + 8 * 3600                                                 # 03:00 ET: quiet hours
        night = P.app_payload(fill4, now=t3)
        check("d. quiet hours (23:00-07:00 ET): the alert still comes, without sound", night.get("silent") is True, night)
        N.settings = lambda path=None: N.merge({"ring_in_quiet_hours": ["pc_silent", "account_status", "room_low", "problems", *N.TRADE_RING]})
        check("d. ... and rings once trade_opened is put in ring_in_quiet_hours (the owner's yes / no)", not P.app_payload(fill4, now=t3).get("silent"))
        N.settings = lambda path=None: N.merge({})
        import threading
        q = P.pc_notify(dict(fill4, key="fill:99", account="Paper"))          # Paper: the worker sends nothing anywhere (no network here)
        workers = [t for t in threading.enumerate() if t.name == "push"]
        for t in workers:
            t.join(10)
        check("d. pc_notify never blocks routing: it queues the work in a daemon thread", q == {"queued": True} and all(t.daemon for t in workers)
              and P.pc_notifier().seen({"key": "fill:99"}), (q, workers))
    finally:
        sb.close()


# ------------------------------------------------------------------------------------------------ e. the 15-minute report
def part_e():
    from tests import test_bots_back as BB
    from tools import pc_report as R
    sb = Sandbox()
    b = BB.Box()
    try:
        wp = P.app_block()
        now = BB.weekday_10am_et()
        hb = BB.hb_payload(now - 120)
        b.hb(hb)
        snap = R.gather(now, root=b.root, env=b.env, http=BB.FakeHTTP(), feed_problem=lambda: None)
        snap["wp"] = wp
        core, exts = R.posts(snap)
        check("e. the core status post carries wp exactly as made (the privacy pass never re-masks public keys)", core.get("wp") == wp, core.get("wp"))
        check("e. never in an ext post; the core stays under 3,900 bytes", all("wp" not in json.dumps(e) for e in exts) and R._size(core) <= R.MAX_STATUS_BYTES, R._size(core))
        big = R.full(snap)
        big["accounts"] = [{"id": "x", "name": "N" * 5000}]
        fit = R._fit_core(big, R.MAX_STATUS_BYTES)
        check("e. even the last-resort trim keeps wp (the phone needs it)", fit.get("wp") == wp and R._size(fit) <= R.MAX_STATUS_BYTES, R._size(fit))
        snap["wp"] = {**wp, "note": "free text"}
        check("e. a wp block that is not exactly app_block's shape is left out", "wp" not in R.posts(snap)[0])
        # app-first alerts: seed, then a closed trade
        b.topic()
        took = []
        b.run(BB.FakeHTTP(), now, app_push=lambda m: took.append(m) or True)
        hb2 = json.loads(json.dumps(hb))
        hb2["acct"]["trades"].append({"day": "2026-11-12", "entry_t": now - 1500, "exit_t": now + 700, "side": "SHORT", "qty": 6, "entry": 25100.25,
                                      "exit_px": 25000.0, "pnl": 1203.0, "r": 3.4, "exit": "TARGET"})
        hb2["acct"]["position"], hb2["position"], hb2["t"] = None, False, now + 780
        b.hb(hb2)
        h = BB.FakeHTTP()
        cfg = R.load_cfg(b.env)
        rec = b.run(h, now + 900, app_push=lambda m: took.append(m) or True)
        alerts = [c for c in h.posts() if not c["url"].endswith("/" + R.status_feed()["topic"])]
        check("e. a closed trade with a phone on: the phone app takes it AND its ntfy copy goes (2026-11-20: a trade's result reaches "
              "both routes; one post, to the private topic)",
              any(" closed " in m["title"] for m in took) and len(alerts) == 1 and "closed" in alerts[0]["h"].get("Title", "")
              and alerts[0]["url"].endswith("/" + cfg["topic"]) and rec.get("app_sent", 0) >= 1, (took[-1:], alerts, rec.get("app_sent")))
        hb3 = json.loads(json.dumps(hb2))
        hb3["acct"]["trades"].append({"day": "2026-11-12", "entry_t": now + 2000, "exit_t": now + 2300, "side": "LONG", "qty": 3, "entry": 25010.0,
                                      "exit_px": 25000.0, "pnl": -60.0, "r": -1.0, "exit": "STOP"})
        hb3["t"] = now + 2400
        b.hb(hb3)
        h = BB.FakeHTTP()
        b.run(h, now + 2500, app_push=lambda m: False)
        alerts = [c for c in h.posts() if not c["url"].endswith("/" + R.status_feed()["topic"])]
        check("e. the phone app did not take it: the same alert goes to the private ntfy topic (the backup)", len(alerts) == 1 and "-$60" in alerts[0]["h"].get("Title", "")
              and alerts[0]["url"].endswith("/" + cfg["topic"]), alerts)
        rp = P.report_payload({"key": f"close:lit:{now - 1500}", "title": "Zlarior 50K closed +$1,203", "body": "x", "priority": "low"})
        ro = P.report_payload({"key": f"open:lit:{now - 1500}", "title": "o", "body": "x", "priority": "high"})
        rc = P.report_payload({"key": "cond:feed_stale:1", "title": "FEED STALE", "body": "x"})
        rb = P.report_payload({"key": "back:feed_stale:2", "title": "Back to normal", "body": "x"})
        check("e. report alerts on the phone: a close replaces its open, 'Back to normal' replaces its problem, trades open the NQ page, quiet = no sound",
              rp["tag"] == ro["tag"] and rc["tag"] == rb["tag"] and rp["url"] == "#nq" and rc["url"] == "#board" and rp["silent"] and not ro["silent"]
              and P.pc_app_ok(rp), (rp, ro, rc, rb))
    finally:
        b.cleanup()
        sb.close()


# ------------------------------------------------------------------------------------------------ f. without `cryptography`
CHILD = r'''
import json, os, sys, tempfile
sys.path.insert(0, sys.argv[1])
sys.modules["cryptography"] = None                      # the package is missing on this PC
from engine import notify as N, push as P
d = tempfile.mkdtemp()
P.CONFIG_PATH, P.SENT_PATH, P.PC_KEY_PATH = (os.path.join(d, x) for x in ("push.json", "sent.json", "pck.json"))
N.INSTANT_PATH = os.path.join(d, "instant.json")
N.settings = lambda path=None: N.merge({"quiet_hours": {"off": True}})
posted = []
fake = lambda p: N.instant_entry(p, cfg={"ntfy": "https://ntfy.sh", "topic": "nq-test-topic-0000"}, poster=lambda b, t, m: posted.append(m) or True)
fill = P.entry_payload("Zlarior 50K", "LONG", 6, 1795050000, src="pc", entry=24980.25, stop=24955, target=25360)
r = P._pc_send(dict(fill), ntfy=fake)
relay = [{"le": "sub", "v": 2, "box": "A" * 300}]
from tools import pc_report as R
out = {"crypto": P.crypto_ok(), "key": P.own_key(), "wp": P.app_block(), "intake": P.intake(relay), "send": r, "posted": len(posted),
       "file": os.path.exists(P.CONFIG_PATH), "core_wp": "wp" in R.full({"t": 1, "wp": None}), "now": P.pc_send_now(P.text_payload("PC", "test", "t", "b", key="k"))}
print(json.dumps(out, default=str))
'''


def part_f():
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", CHILD, ROOT], capture_output=True, text=True, timeout=120, cwd=ROOT)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        check("f. the no-cryptography child ran", False, (r.stdout[-500:], r.stderr[-800:]))
        return
    check("f. no `cryptography`: no key, no wp block, nothing written (the phone card says it waits for the PC)",
          o["crypto"] is False and o["key"] is None and o["wp"] is None and not o["file"] and o["core_wp"] is False, o)
    check("f. no `cryptography`: the intake skips quietly, a test is skipped, nothing raises", (o["intake"].get("skipped") or o["intake"].get("error")) and
          not o["now"].get("sent"), o)
    check("f. no `cryptography`: the entry still goes to the ntfy alert topic at once", o["send"].get("ntfy") == "sent" and o["posted"] == 1, o)


def main() -> int:
    for part in (part_a, part_b, part_c, part_d, part_e, part_f):
        try:
            part()
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f"{part.__name__} ran without an exception", False, repr(e))
    bad = [n for n, ok in RES if not ok]
    print(f"\nwebpush: {len(RES) - len(bad)}/{len(RES)} {'ALL PASS' if not bad else 'FAILED: ' + '; '.join(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
