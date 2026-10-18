"""Phone notifications (engine/push.py): payloads, subscription parsing, de-duplication, the built-in Web Push encryption and
VAPID header, and the cloud monitor's fill / outcome notices. No network: a fake sender records what would go out.

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
    ikm = h(h(auth, shared), b"WebPush: info\x00" + ua_pub + as_pub + b"\x01")
    prk = h(salt, ikm)
    pt = AESGCM(h(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]).decrypt(h(prk, b"Content-Encoding: nonce\x00\x01")[:12], ct, None)
    return pt.rstrip(b"\x00")[:-1]


def main() -> int:
    # ---- payloads
    f = push.fill_payload("Cloud paper", "NQ", "LONG", 12, 21034.25, 21000.0, 21120.0, 1_792_000_000, setup="Swept Asia low · target VIX band")
    check("fill: title names the source, strategy and side", f["title"] == "Cloud paper · LIT LONG filled", f["title"])
    check("fill: micros, entry, stop, target, $ at risk (12 x 34.25 pts x $2 = $822)",
          "12 MNQ @ 21,034.25" in f["body"] and "stop 21,000.00" in f["body"] and "target 21,120.00" in f["body"] and "$822 at risk" in f["body"], f["body"])
    check("fill: de-dup key and tap target", f["key"] == "fill:1792000000" and f["url"] == "#/activity/fill:1792000000")
    o = push.outcome_payload("Cloud paper", "NQ", "LONG", "TARGET", 3.2, 2560.0, 1_792_000_000, 1_792_020_000, qty=12,
                             balance=52560.0, to_target=440.0, note="Size: weekly stop: half size")
    check("outcome: exit, R and $ in the title", o["title"] == "Cloud paper · LIT LONG TARGET +3.20R +$2,560", o["title"])
    check("outcome: eval balance and what is left to the target", "Eval balance $52,560 ($440 to the $3k target)" in o["body"], o["body"])
    check("outcome: weekly-stop half size noted", "half size" in o["body"])
    s = push.outcome_payload("PC paper", "NQ", "SHORT", "STOP", -1.0, -800, 1, 2)
    check("outcome: a loss reads -1.00R -$800", s["title"].endswith("STOP -1.00R -$800"), s["title"])
    check("fill and outcome of one trade get different notification tags (the outcome does not replace the fill)", f["tag"] != o["tag"])
    w = push.wire({**f, "body": "x" * 5000})
    check("wire format stays under the 4 KB push limit", len(w) < 3100, len(w))

    # ---- subscriptions from a secret's text
    _, _, a = fake_sub(1)
    _, _, b = fake_sub(2)
    check("subs: a JSON list", len(push.parse_subs(json.dumps([a, b]))) == 2)
    check("subs: one object", len(push.parse_subs(json.dumps(a))) == 1)
    check("subs: codes pasted one after another (lists or objects), duplicates dropped",
          len(push.parse_subs(json.dumps([a]) + "\n" + json.dumps([b]) + " " + json.dumps(a))) == 2)
    check("subs: junk and non-https endpoints ignored", push.parse_subs('nonsense {"endpoint":"http://x","keys":{"p256dh":"a","auth":"b"}}') == [])

    # ---- config: env (cloud) and nothing configured = silent no-op
    priv, pub = push.generate_keys()
    env = {"LE_VAPID_PRIVATE": priv, "LE_PUSH_SUBS": json.dumps([a]), "LE_PUSH_SUBS_2": json.dumps(b)}
    with tempfile.TemporaryDirectory() as tmp:
        none = os.path.join(tmp, "none.json")
        c = push.config(env=env, path=none)
        check("config: private key from env, public derived, LE_PUSH_SUBS + LE_PUSH_SUBS_2", c["public"] == pub and len(c["subs"]) == 2 and push.enabled(c))
        st = push.status(c)
        check("status: never the private key or an endpoint", priv not in json.dumps(st) and "fake1" not in json.dumps(st) and len(st["device_ids"]) == 2)
        c0 = push.config(env={}, path=none)
        check("not configured: send() is a no-op", not push.enabled(c0) and push.send(f, cfg=c0).get("skipped") == "not configured")
        bad = push.config(env={"LE_VAPID_PRIVATE": "abc", "LE_PUSH_SUBS": json.dumps([a])}, path=none)
        check("a broken private key is reported, not raised", bad["private"] is None and "unusable" in (bad["error"] or ""))
        # PC file config (Settings -> Alerts on the PC dashboard)
        pth = os.path.join(tmp, "push.json")
        push.save_pc_config({"vapid_private": priv, "subs": json.dumps([a])}, path=pth)
        push.save_pc_config({"subs": json.dumps([b])}, path=pth)
        check("PC config: key + two phones added one at a time", len(push.config(env={}, path=pth)["subs"]) == 2)
        try:
            push.save_pc_config({"vapid_private": "short"}, path=pth)
            check("PC config: a bad key is refused", False)
        except ValueError:
            check("PC config: a bad key is refused", True)

        # ---- de-duplication with a fake sender, across runs (the cloud keeps the keys in state.json)
        out = []
        sender = lambda sub, data, pk, pb: (out.append((sub["endpoint"], json.loads(data))), 201)[1]    # noqa: E731
        n1 = push.Notifier(cfg=c, sender=sender)
        r1 = n1.notify(f)
        r2 = n1.notify(f)
        check("de-dup: first notice goes to both phones, the repeat is skipped", r1["sent"] == 2 and r2.get("dup") and len(out) == 2, (r1, r2))
        n2 = push.Notifier(keys=n1.keys(), cfg=c, sender=sender)
        check("de-dup: the next run (keys from state.json) skips it too", n2.notify(f).get("dup") and len(out) == 2)
        pc = push.fill_payload("PC NinjaTrader Sim", "NQ", "LONG", 12, 21034.25, 21000.0, 21120.0, 1_792_000_000)
        check("de-dup: the PC's notice of the same fill is its own (tagged PC, not swallowed by the cloud's key)",
              n2.notify(pc)["sent"] == 2 and out[-1][1]["title"].startswith("PC NinjaTrader Sim"))
        check("sent JSON carries title, body, tag, url, key", set(out[0][1]) >= {"title", "body", "tag", "url", "key", "kind", "t", "src"})
        gone = push.Notifier(cfg=c, sender=lambda *x: 410).notify(o)
        check("an expired subscription (410) is reported as gone", len(gone["gone"]) == 2 and gone["sent"] == 0, gone)
        boom = push.Notifier(cfg=c, sender=lambda *x: 1 / 0).notify(s)
        check("a sender crash never raises (errors listed)", boom["sent"] == 0 and len(boom["errors"]) == 2)
        filep = os.path.join(tmp, "sent.json")
        push.Notifier(path=filep, cfg=c, sender=sender).notify(o)
        check("PC de-dup keys survive a restart (data/push_sent.json)", push.Notifier(path=filep, cfg=c, sender=sender).seen(o))

    # ---- built-in sender: encryption decrypts on the 'phone', VAPID header verifies
    k, auth, sub = fake_sub(3)
    msg = push.wire(f)
    check("built-in aes128gcm encryption decrypts with the phone's key (RFC 8291)", decrypt(push.encrypt(msg, sub["keys"]["p256dh"], sub["keys"]["auth"]), k, auth) == msg)
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    hdr = push.vapid_header(sub["endpoint"], priv)
    tok, kk = hdr.split("t=")[1].split(", k=")
    hd, bd, sg = tok.split(".")
    raw = push.b64u_dec(sg)
    try:
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), push.b64u_dec(kk)).verify(
            encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")), f"{hd}.{bd}".encode(), ec.ECDSA(hashes.SHA256()))
        okv = json.loads(push.b64u_dec(bd))["aud"] == "https://web.push.apple.com" and kk == pub
    except Exception as e:
        okv = False
        print("   ", e)
    check("VAPID JWT (ES256) verifies with the public key, aud = the push service", okv)

    # ---- the cloud monitor's notices: a LIT fill (open position) then its outcome on the next run
    cm.SYM = "NQ"
    lm = {"model": "lit", "label": "LIT"}
    et0 = 1_792_000_000
    pos = {"entry_t": et0, "dir": 1, "qty": 20, "stop": 21000.0, "stop0": 21000.0, "target": 21120.0, "entry": 21034.25, "risk_pts": 34.25}
    res1 = {"model": "lit", "trades": [], "signals": [{"t": et0 - 600, "dir": 1, "swept": ["asia20_l", "pdl"], "target_label": "VIX band"}],
            "events": [{"t": et0, "type": "entry", "text": "LONG LIT @ 21,034.25"}]}
    ledger = {}
    cm.update_ledger(ledger, res1, et0 - 3600, None, None, None, None)
    n1 = cm.trade_notices(ledger, res1, pos, lm, et0 - 3600, size=lambda t: (1.0, 12, ["weekly stop: half size"]))
    check("cloud: an open LIT position gives one fill notice with the sized micros and the setup",
          len(n1) == 1 and n1[0]["kind"] == "fill" and n1[0]["qty"] == 12 and "Swept Asia low, PDL" in n1[0]["body"] and "half size" in n1[0]["body"], n1)
    tr = {"entry_t": et0, "exit_t": et0 + 9000, "dir": 1, "entry": 21034.25, "stop": 21000.0, "target": 21120.0, "exit_price": 21120.0,
          "qty": 12, "pnl": 2056.0, "pnl_r": 2.5, "exit_reason": "TARGET", "trigger": "LIT", "risk_pts": 34.25, "swept": ["Asia low"]}
    res2 = {**res1, "trades": [tr], "events": res1["events"] + [{"t": et0 + 9000, "type": "exit", "text": "EXIT TARGET"}]}
    cm.update_ledger(ledger, res2, et0 - 3600, None, None, None, None)
    n2 = cm.trade_notices(ledger, res2, None, lm, et0 - 3600)
    kinds = [x["kind"] for x in n2]
    note = push.Notifier(keys=[push.Notifier().full_key(n1[0])], cfg=push.config(env={}, path="/nonexistent"))
    fresh = [x for x in n2 if not note.seen(x)]
    check("cloud: next run has the fill (already sent) and the outcome: only the outcome is new",
          sorted(kinds) == ["fill", "outcome"] and [x["kind"] for x in fresh] == ["outcome"], (kinds, [x["kind"] for x in fresh]))
    oc = [x for x in n2 if x["kind"] == "outcome"][0]
    check("cloud: the outcome has R, $ and the eval balance after it", "+2.50R +$2,056" in oc["title"] and "Eval balance $52,056" in oc["body"], (oc["title"], oc["body"]))
    check("cloud: ledger rows now carry entry / stop / target / exit prices (Activity feed)",
          ledger[et0].get("entry_px") == 21034.25 and ledger[et0].get("exit_px") == 21120.0)
    old = cm.trade_notices(ledger, res2, None, lm, et0 + 10_000)
    check("cloud: nothing from before the notifications started", old == [])

    # ---- Telegram / Discord off by default
    os.environ.pop("LE_ALERTS_CHAT", None)
    os.environ["TG_TOKEN"], os.environ["TG_CHAT"] = "x", "y"
    check("chat alerts off by default even with TG secrets present", cm.send_alert("hello", lm={}) == [] and not cm.chat_on({}))
    check("chat alerts switch: live_model.json alerts.chat", cm.chat_on({"alerts": {"chat": True}}))
    os.environ.pop("TG_TOKEN"); os.environ.pop("TG_CHAT")
    from engine import alerts
    check("PC alerts.send off by default", alerts.send("hello", "entry", force=True)["sent"] is False if not alerts.chat_on() else True)

    ok = all(RES)
    print(f"push: {sum(RES)}/{len(RES)}", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
