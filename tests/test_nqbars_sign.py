"""The NQ chart's public topic (day-security2 2026-11-20, tools/web_public/nq/nqbars.js; LEAD_WIRES W6).
  a. parse(): a post dated more than 10 minutes ahead never wins (a forged chart dated 2099)
  b. parseVerified() with the vk pinned: only the PC's signed post (Python-signed, WebCrypto-checked); a forged newer one dropped
  c. no vk, or a phone without WebCrypto: the chart reads exactly as before
    python -X utf8 -m tests.test_nqbars_sign
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import status_sign as S  # noqa: E402

RES = []


def ok(cond, name, info=""):
    RES.append(bool(cond))
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond or not info else f"  -> {str(info)[:300]}"))


NOW = int(time.time())


def post(t, p0):
    return {"v": 1, "kind": "le-bars", "t": t, "tf": 300, "n": 1, "t0": t - 300, "p0": p0, "b": [0, 4, 4, 2], "tick": 0.25}


def line(text, t, i):
    return json.dumps({"id": i, "time": t, "event": "message", "message": text})


def node(js):
    r = subprocess.run(["node", "--input-type=module", "-e", js], cwd=ROOT, capture_output=True, text=True, timeout=60)
    return (r.stdout or "").strip(), (r.stderr or "")[-300:]


def main():
    priv, vk = S.keygen()
    real = S.sign_text(json.dumps(post(NOW - 600, 80000), separators=(",", ":")), priv)
    forged = json.dumps(post(NOW - 60, 99999), separators=(",", ":"))
    future = json.dumps(post(NOW + 10 ** 8, 11111), separators=(",", ":"))
    nd = "\n".join([line(real, NOW - 600, "r"), line(forged, NOW - 60, "f"), line(future, NOW, "x")])
    js = ("import * as B from './tools/web_public/nq/nqbars.js';"
          "const nd=%s, vk=%s, now=%d;"
          "const a=B.parse(nd,now), b=await B.parseVerified(nd,{vk},now), c=await B.parseVerified(nd,{},now);"
          "const v1=await B.verifyText(%s,vk), v2=await B.verifyText(%s,vk);"
          "const s=globalThis.crypto; Object.defineProperty(globalThis,'crypto',{value:{},configurable:true});"
          "const d=await B.parseVerified(nd,{vk},now); Object.defineProperty(globalThis,'crypto',{value:s,configurable:true});"
          "console.log(JSON.stringify({a:a&&a.p0,b:b&&b.p0,c:c&&c.p0,d:d&&d.p0,v1,v2}))"
          % (json.dumps(nd), json.dumps(vk), NOW, json.dumps(real), json.dumps(real.replace("80000", "80001"))))
    out, err = node(js)
    try:
        d = json.loads(out.splitlines()[-1])
    except Exception:  # noqa: BLE001
        d = {}
        print("    node:", out, err)
    print("a. a future-dated post")
    ok(d.get("a") == 99999, "parse(): the 2099 post never wins (the newest real-time post does, as before)", d)
    print("b. the vk pinned")
    ok(d.get("v1") is True and d.get("v2") is False, "WebCrypto checks the PC's Python signature; a changed price fails", d)
    ok(d.get("b") == 80000, "parseVerified(): only the PC's signed chart, the forged newer one dropped", d)
    print("c. as before")
    ok(d.get("c") == 99999, "no vk pinned: as before (the newest valid post)", d)
    ok(d.get("d") == 99999, "a phone without WebCrypto: as before", d)
    n = sum(RES)
    print(f"\nnqbars_sign: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
