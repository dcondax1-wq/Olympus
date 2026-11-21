"""The data pipe's answers are the PC's (day-security2 2026-11-20, engine/datafeed.send / parse_answer; LEAD_WIRES W7).
  a. send(): the meta message (ntfy's Message header) carries the PC's signature; without a key it goes out as before
  b. parse_answer() with the PC's key pinned: the PC's answer is read; a stranger's answer (right shape, its own sha256) and a
     signed answer with a changed sha256 are not
  c. no key pinned, or a test's own fake server: read as before
    python -X utf8 -m tests.test_datafeed_sign
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import datafeed as DF  # noqa: E402
from tools import status_sign as S  # noqa: E402

RES = []


def ok(cond, name, info=""):
    RES.append(bool(cond))
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond or not info else f"  -> {str(info)[:300]}"))


NOW = int(time.time())
BLOB = b"PK\x03\x04 fake zip bytes " * 10


def meta(sha=None):
    return {"v": DF.VERSION, "kind": DF.ANS_KIND, "req": "abc123def", "made_t": NOW, "since": "3d", "days": 1, "from": "2026-11-18",
            "to": "2026-11-19", "more": False, "bytes": len(BLOB), "sha256": sha or hashlib.sha256(BLOB).hexdigest(), "code": "x"}


def ntfy_msg(message):
    return {"id": "m1", "time": NOW, "event": "message", "message": message,
            "attachment": {"url": DF.BASE + "/file/abc.zip", "size": len(BLOB), "expires": NOW + 3600}}


def main():
    with tempfile.TemporaryDirectory() as d:
        priv, vk = S.keygen()
        kp = os.path.join(d, "k.json")
        with open(kp, "w", encoding="utf-8") as fh:
            json.dump({"private": priv}, fh)
        seen = []

        def fake(method, url, body, headers, timeout):
            seen.append(dict(headers or {}))
            return 200, b'{"id":"m1"}'

        print("a. send")
        os.environ["LE_STATUS_SIGN_KEY"] = kp
        try:
            r = DF.send(BLOB, meta(), env={"LE_DATAFEED_TOPIC": "t"}, http_fn=fake)
        finally:
            os.environ.pop("LE_STATUS_SIGN_KEY", None)
        msg = seen[-1].get("Message", "")
        ok(r[0] and S.verify_text(msg, vk), "the meta message is signed by the PC's key", (r, msg[-100:]))
        ok(msg.isascii() and len(msg.encode()) <= 4000, "it stays a plain ASCII header under 4,000 bytes")
        os.environ["LE_STATUS_SIGN_KEY"] = os.path.join(d, "none.json")
        try:
            r2 = DF.send(BLOB, meta(), env={"LE_DATAFEED_TOPIC": "t"}, http_fn=fake)
        finally:
            os.environ.pop("LE_STATUS_SIGN_KEY", None)
        ok(r2[0] and '"sg":"' not in seen[-1].get("Message", ""), "no key: sent as before, unsigned")

        print("b. the key pinned")
        good = ntfy_msg(msg)
        forged = ntfy_msg(json.dumps(meta(), separators=(",", ":"), sort_keys=True))
        sp = S.split(msg)
        tampered = ntfy_msg(sp[0].replace(meta()["sha256"], "0" * 64)[:-1] + ',"sg":"' + sp[1] + '"}')
        ok(DF.parse_answer(good, NOW, DF.BASE, vk=vk) is not None, "the PC's signed answer is read")
        ok(DF.parse_answer(forged, NOW, DF.BASE, vk=vk) is None, "a stranger's answer (right shape, its own sha256) is not")
        ok(DF.parse_answer(tampered, NOW, DF.BASE, vk=vk) is None, "a signed answer with a changed sha256 is not")

        print("c. as before")
        ok(DF.parse_answer(forged, NOW, DF.BASE, vk=None) is not None, "no key pinned: read as before")
        local = dict(forged, attachment={**forged["attachment"], "url": "http://127.0.0.1:9/file/abc.zip"})
        ok(DF.parse_answer(local, NOW, "http://127.0.0.1:9") is not None, "a test's own fake server: never the pinned check")
    n = sum(RES)
    print(f"\ndatafeed_sign: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
