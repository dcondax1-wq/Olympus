"""Phone notifications (engine/push.py): the two short notices, the automatic set-up (relay subscriptions, the cloud's own
key, the PC's sealed copy of it), de-duplication within and across the cloud and the PC, the built-in Web Push encryption
and VAPID header, and the cloud monitor's notices. No network: a fake relay and a fake sender record what would go out.

  python -X utf8 -m tests.test_push
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

from engine import push
from tools import cloud_monitor as cm

RES = []
M = push.MINUS


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not cond else ""))


def fake_sub(i=0):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    k = ec.generate_private_key(ec.SECP256R1())
    pub = k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    auth = os.urandom(16)
    return k, auth, {"endpoint": f"https://web.push.apple.com/fake{i}", "keys": {"p256dh": push.b64u(pub), "auth": push.b64u(auth)}}


class FakeNtfy:
    """An ntfy.sh topic in memory: POST appends, GET ?poll=1 returns newline-delimited JSON like ntfy."""

    def __init__(self):
        self.msgs, self.t = [], 1_792_000_000

    def __call__(self, method, url, body=None):
        if method == "POST":
            self.t += 1
            self.msgs.append({"id": str(self.t), "time": self.t, "event": "message", "topic": "x", "message": body.decode()})
            return "{}"
        return "\n".join(json.dumps(m) for m in self.msgs)


def decrypt(body, ua_key, auth):
    """RFC 8291 receiver side (what the phone does), to prove the built-in sender's output decrypts."""
    import hashlib
    import hmac
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


def main() -> int:
    et0 = 1_792_000_000
    # ---- the two notices: short, the account, the same tag per trade
    e = push.entry_payload("MFFU 50K", "LONG", 4, et0, entry=24512.25, stop=24466.5)
    check("entry: title 'LONG · MFFU 50K', body 'Entered 4 MNQ'", e["title"] == "LONG · MFFU 50K" and e["body"] == "Entered 4 MNQ", (e["title"], e["body"]))
    w = json.loads(push.wire(e))
    check("entry: no prices on the wire (details stay for the app's Activity page)", "24512" not in json.dumps(w) and set(w) == {"title", "body", "tag", "url", "kind", "key", "t"}, w)
    win = push.outcome_payload("MFFU 50K", "LONG", "TARGET", 1812.4, et0, et0 + 9000)
    loss = push.outcome_payload("Sim101", "SHORT", "STOP", -366, et0, et0 + 600)
    be = push.outcome_payload("Paper", "LONG", "BE", 0.4, et0, et0 + 600)
    tm = push.outcome_payload("Paper", "LONG", "TIME", 212, et0, 1_792_007_700)          # 15:55 ET
    check("outcome: '+$1,812' for a win", win["body"] == "+$1,812" and win["title"] == "LONG · MFFU 50K", win["body"])
    check("outcome: '−$366' (real minus) for a loss, account Sim101", loss["body"] == f"{M}$366" and loss["title"] == "SHORT · Sim101", loss["body"])
    check("outcome: '$0 breakeven'", be["body"] == "$0 breakeven", be["body"])
    check("outcome: '+$212 closed 15:55' for the end-of-day exit", tm["body"] == "+$212 closed 15:55", tm["body"])
    check("entry and outcome share the notification tag (the result replaces the entry)", e["tag"] == win["tag"] == push.trade_tag(et0))
    check("account labels: Paper for the cloud, live_model.json account.name (default MFFU 50K)",
          push.account_label({}, "paper") == "Paper" and push.account_label({}) == "MFFU 50K" and push.account_label({"account": {"name": "MFFU 50K #2"}}) == "MFFU 50K #2")

    # ---- subscriptions: only known push services (the relay is public)
    _, _, a = fake_sub(1)
    _, _, b = fake_sub(2)
    check("subs: list / object / several codes, duplicates dropped", len(push.parse_subs(json.dumps([a]) + json.dumps(b) + json.dumps(a))) == 2)
    check("subs: an endpoint that is not a push service is refused",
          push.parse_subs({"endpoint": "https://evil.example/x", "keys": {"p256dh": "a", "auth": "b"}}) == [] and
          push.parse_subs({"endpoint": "https://web.push.apple.com.evil.example/x", "keys": {"p256dh": "a", "auth": "b"}}) == [])

    with tempfile.TemporaryDirectory() as tmp:
        # ---- the cloud's own key (Actions cache file): made once, kept, never returned
        kf = os.path.join(tmp, "cache", "vapid.json")
        k1 = push.ensure_key_file(kf)
        k2 = push.ensure_key_file(kf)
        check("cloud key: made on the first run, the same on the next (cache file)", k1["new"] and not k2["new"] and k1["public"] == k2["public"])
        check("cloud key: ensure_key_file never returns the private key", "private" not in k1 and (os.stat(kf).st_mode & 0o077) == 0)
        none = os.path.join(tmp, "none.json")
        cfg_c = push.config(env={"LE_VAPID_KEY_FILE": kf}, path=none)
        check("cloud key: used when no secret is set", cfg_c["source"] == "cache" and cfg_c["public"] == k1["public"])
        sp, spub = push.generate_keys()
        cfg_s = push.config(env={"LE_VAPID_KEY_FILE": kf, "LE_VAPID_PRIVATE": sp}, path=none)
        check("a secret LE_VAPID_PRIVATE overrides the cached key", cfg_s["source"] == "secret" and cfg_s["public"] == spub)

        # ---- relay: the app posts its subscription, the cloud merges it into its state
        ntfy = FakeNtfy()
        relay = push.Relay(base="https://ntfy.sh", topic="le-test", http=ntfy)
        relay.post({"le": "sub", "sub": a, "key": k1["public"], "id": push.endpoint_id(a["endpoint"])})
        relay.post({"le": "sub", "sub": b, "key": "an-old-key", "id": push.endpoint_id(b["endpoint"])})
        ntfy.msgs.append({"event": "message", "time": 1, "message": "hello, not ours"})
        msgs = relay.read()
        subs = push.merge_relay_subs([], msgs, k1["public"])
        check("relay: the app's subscription made with today's key is kept, an old key's and junk are not",
              [r["id"] for r in subs] == [push.endpoint_id(a["endpoint"])], subs)
        relay.post({"le": "unsub", "id": push.endpoint_id(a["endpoint"])})
        check("relay: Turn off (unsub) removes the phone", push.merge_relay_subs(subs, relay.read(), k1["public"]) == [])
        check("relay: an expired phone (gone) is dropped", push.merge_relay_subs(subs, [], k1["public"], gone=[subs[0]["id"]]) == [])
        check("relay: a key change drops subscriptions made for the old key", push.merge_relay_subs(subs, [], "new-key") == [])

        # ---- de-dup: within a side across runs, and across the cloud and the PC via relay markers
        out = []
        sender = lambda sub, data, pk, pb: (out.append(json.loads(data)), 201)[1]    # noqa: E731
        cfg = push.config(env={"LE_VAPID_KEY_FILE": kf}, path=none, subs_extra=[a, b])
        cloud = push.Notifier(cfg=cfg, sender=sender, relay=push.Relay(topic="le-test", http=ntfy), src="cloud")
        r1, r2 = cloud.notify(e), cloud.notify(e)
        check("de-dup: the entry goes to both phones once", r1["sent"] == 2 and r2.get("dup") and len(out) == 2, (r1, r2))
        check("de-dup: the next cloud run (keys from state.json) skips it", push.Notifier(keys=cloud.keys(), cfg=cfg, sender=sender).notify(e).get("dup"))
        pc = push.Notifier(cfg=cfg, sender=sender, relay=push.Relay(topic="le-test", http=ntfy), src="pc")
        pe = push.entry_payload("Sim101", "LONG", 4, et0)
        r3 = pc.notify(pe)
        check("de-dup across sides: the PC skips the entry the cloud already sent (relay marker)", r3.get("by") == "other side" and len(out) == 2, r3)
        r4 = pc.notify(loss)
        r5 = cloud.notify(push.outcome_payload("Paper", "SHORT", "STOP", -380, et0, et0 + 600))
        check("de-dup across sides: the PC sends the outcome first, the cloud then skips it", r4["sent"] == 2 and r5.get("by") == "other side" and len(out) == 4, (r4, r5))
        check("app-only notices (PC silent, eval timing) are recorded, not pushed",
              cloud.notify(push.text_payload("Cloud", "timing", "Eval timing: GO", "x", key="timing:1"), push_it=False).get("skipped") == "app only" and len(out) == 4)
        g = push.Notifier(cfg=cfg, sender=lambda *x: 410).notify(win)
        check("an expired subscription (410 / 403) is reported as gone", len(g["gone"]) == 2 and g["sent"] == 0)
        check("a sender crash never raises", push.Notifier(cfg=cfg, sender=lambda *x: 1 / 0).notify(be)["sent"] == 0)
        n0 = push.Notifier(cfg=push.config(env={}, path=none), sender=sender)
        r6 = n0.notify(tm)
        check("not set up: nothing is sent and the key is marked (never sent hours late)", r6.get("skipped") == "not configured" and n0.seen(tm))
        fp = os.path.join(tmp, "sent.json")
        push.Notifier(path=fp, cfg=cfg, sender=sender).notify(push.entry_payload("Sim101", "LONG", 1, 5))
        check("PC de-dup keys survive a restart (data/push_sent.json)", push.Notifier(path=fp).seen({"key": "fill:5"}))

        # ---- the PC gets the key with no manual step: heartbeat key -> sealed box in state.json -> decrypt
        pck = os.path.join(tmp, "pc_key.json")
        pk = push.pc_public_key(pck)
        check("PC: makes its own key once (heartbeat publishes the public part)", pk and push.pc_public_key(pck) == pk)
        priv_c = push.config(env={"LE_VAPID_KEY_FILE": kf}, path=none)["private"]
        box = push.seal(priv_c.encode(), pk)
        check("PC: the sealed box does not contain the key", priv_c not in box)
        st = {"push_pc": {"pk": pk, "box": box}, "push_subs": subs}
        sync = push.pc_sync(fetch=lambda: st, key_path=pck)
        check("PC: unseals the cloud's key and reads the phones from state.json", sync["private"] == priv_c and sync["subs"] == [subs[0]["sub"]])
        other = os.path.join(tmp, "other.json")
        push.pc_public_key(other)
        check("PC: another machine's key cannot open it", push.pc_sync(fetch=lambda: st, key_path=other)["private"] is None)

    # ---- built-in sender: encryption decrypts on the 'phone', the VAPID JWT verifies
    k, auth, sub = fake_sub(3)
    msg = push.wire(e)
    check("built-in aes128gcm encryption decrypts with the phone's key (RFC 8291)", decrypt(push.encrypt(msg, sub["keys"]["p256dh"], sub["keys"]["auth"]), k, auth) == msg)
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    priv, pub = push.generate_keys()
    tok, kk = push.vapid_header(sub["endpoint"], priv).split("t=")[1].split(", k=")
    hd, bd, sg = tok.split(".")
    raw = push.b64u_dec(sg)
    try:
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), push.b64u_dec(kk)).verify(
            encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")), f"{hd}.{bd}".encode(), ec.ECDSA(hashes.SHA256()))
        okv = json.loads(push.b64u_dec(bd))["aud"] == "https://web.push.apple.com" and kk == pub
    except Exception:
        okv = False
    check("VAPID JWT (ES256) verifies with the public key, aud = the push service", okv)

    # ---- the cloud monitor's notices: a LIT entry (open position) then its outcome on the next run
    cm.SYM = "NQ"
    lm = {"model": "lit", "label": "LIT"}
    pos = {"entry_t": et0, "dir": 1, "qty": 20, "stop": 21000.0, "stop0": 21000.0, "target": 21120.0, "entry": 21034.25, "risk_pts": 34.25}
    res1 = {"model": "lit", "trades": [], "signals": [{"t": et0 - 600, "dir": 1, "swept": ["asia20_l", "pdl"], "target_label": "VIX band"}],
            "events": [{"t": et0, "type": "entry", "text": "LONG LIT @ 21,034.25"}]}
    ledger = {}
    cm.update_ledger(ledger, res1, et0 - 3600, None, None, None, None)
    n1 = cm.trade_notices(ledger, res1, pos, lm, et0 - 3600, size=lambda t: (1.0, 12, ["weekly stop: half size"]))
    check("cloud: an open position gives one entry notice 'LONG · Paper' / 'Entered 12 MNQ' (sized micros)",
          len(n1) == 1 and n1[0]["title"] == "LONG · Paper" and n1[0]["body"] == "Entered 12 MNQ", n1)
    check("cloud: the entry keeps its details for Activity (setup, stop, $ at risk)",
          "Asia low, PDL" in n1[0]["setup"] and n1[0]["stop"] == 21000.0 and round(n1[0]["risk_usd"]) == 822, n1[0])
    tr = {"entry_t": et0, "exit_t": et0 + 9000, "dir": 1, "entry": 21034.25, "stop": 21000.0, "target": 21120.0, "exit_price": 21120.0,
          "qty": 12, "pnl": 2056.0, "pnl_r": 2.5, "exit_reason": "TARGET", "trigger": "LIT", "risk_pts": 34.25, "swept": ["Asia low"]}
    res2 = {**res1, "trades": [tr], "events": res1["events"] + [{"t": et0 + 9000, "type": "exit", "text": "EXIT TARGET"}]}
    cm.update_ledger(ledger, res2, et0 - 3600, None, None, None, None)
    n2 = cm.trade_notices(ledger, res2, None, lm, et0 - 3600)
    note = push.Notifier(keys=[n1[0]["key"]])
    fresh = [x for x in n2 if not note.seen(x)]
    check("cloud: the next run only adds the outcome", [x["kind"] for x in fresh] == ["outcome"], [x["kind"] for x in n2])
    oc = fresh[0]
    check("cloud: outcome 'LONG · Paper' / '+$2,056', eval balance kept for Activity", oc["title"] == "LONG · Paper" and oc["body"] == "+$2,056"
          and round(oc["balance"]) == 52056, (oc["title"], oc["body"], oc.get("balance")))
    check("cloud: nothing from before the notifications started", cm.trade_notices(ledger, res2, None, lm, et0 + 10_000) == [])

    # ---- Telegram / Discord off by default
    os.environ.pop("LE_ALERTS_CHAT", None)
    os.environ["TG_TOKEN"], os.environ["TG_CHAT"] = "x", "y"
    check("chat alerts off by default even with TG secrets present", cm.send_alert("hello", lm={}) == [] and not cm.chat_on({}))
    check("chat alerts switch: live_model.json alerts.chat", cm.chat_on({"alerts": {"chat": True}}))
    os.environ.pop("TG_TOKEN"); os.environ.pop("TG_CHAT")
    from engine import alerts
    check("PC alerts.send off by default", alerts.chat_on() or alerts.send("hello", "entry", force=True)["sent"] is False)

    ok = all(RES)
    print(f"push: {sum(RES)}/{len(RES)}", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
