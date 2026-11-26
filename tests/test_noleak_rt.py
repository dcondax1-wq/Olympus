"""Red team 2026-11-26 for engine/pc_identity + tools/board.only_pc_key: the REAL PC never goes dark.
    python -X utf8 -m tests.test_noleak_rt
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import pc_identity as PI     # noqa: E402

R = []


def check(name, ok, detail=""):
    R.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {detail}"), flush=True)


def fresh():
    PI._CACHE.clear()
    PI._SAID.clear()


def main():
    tmp = tempfile.mkdtemp()
    home = tempfile.mkdtemp()
    old = (PI._IS_NT, PI._GUID, PI._nt_folder, os.environ.get("HOME"), os.environ.get("USERPROFILE"))
    os.environ["HOME"] = os.environ["USERPROFILE"] = home
    try:
        PI._IS_NT, PI._GUID = True, "guid-owner-pc"
        os.makedirs(os.path.join(tmp, "data"))
        open(os.path.join(tmp, "data", "start_bot.json"), "w").write("{}")
        fresh()
        check("start_bot.json alone (START's own config) adopts the PC", PI.check(tmp, {})[0])
        PI._GUID = ""                                       # the MachineGuid read fails once
        fresh()
        ok, why = PI.check(tmp, {})
        check("a failed MachineGuid read on the adopted PC still posts", ok, why)
        PI._GUID = "guid-owner-pc"
        rec = json.load(open(os.path.join(tmp, "data", "pc_identity.json")))
        rec.pop("fpn", None)
        json.dump(rec, open(os.path.join(tmp, "data", "pc_identity.json"), "w"))
        PI._GUID = ""
        fresh()
        check("an identity file from before fpn + a failed read: fail-open", PI.check(tmp, {})[0])
        PI._GUID = "guid-after-reinstall"
        fresh()
        check("a new MachineGuid WITHOUT the owner's profile = dry run (a copied folder)", not PI.check(tmp, {})[0])
        os.makedirs(os.path.join(home, ".olympus"))
        open(os.path.join(home, ".olympus", "alerts.json"), "w").write("{}")
        fresh()
        ok, why = PI.check(tmp, {})
        check("a new MachineGuid WITH the owner's ~/.olympus/alerts.json re-adopts and posts", ok and "re-adopted" in why, why)
        fresh()
        check("... and the next check matches the new identity", PI.check(tmp, {})[1] == "the owner's PC")
        t2 = tempfile.mkdtemp()
        PI._nt_folder = lambda: "C:/x/NinjaTrader 8"
        fresh()
        check("Windows + only the NinjaTrader folder (no account file yet) adopts", PI.check(t2, {})[0])
        PI._nt_folder = old[2]
        real = PI._check
        PI._read = (lambda p: (_ for _ in ()).throw(RuntimeError("boom")))
        fresh()
        ok, why = PI.check(tmp, {})
        check("an unexpected error on Windows = fail-open", ok and "fail-open" in why, why)
        PI._IS_NT = False
        fresh()
        check("... but closed on Linux (a sandbox)", not PI.check(tmp, {})[0])
        PI._check = real
    finally:
        import importlib
        PI._IS_NT, PI._GUID = old[0], old[1]
        importlib.reload(PI)
        for k, v in (("HOME", old[3]), ("USERPROFILE", old[4])):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(home, ignore_errors=True)
    # board: a rotated PC key takes over within the window
    from tools import board as B
    from tools import status_sign as S
    priv_old, pub_old = S.keygen() if hasattr(S, "keygen") else (None, None)
    if priv_old is None:
        print("  [..] status_sign has no keygen(): board rotation check skipped")
    else:
        priv_new, pub_new = S.keygen()

        def post(priv, pub, t):
            body = {"kind": "le-live", "svk": pub, "t": t}
            return {"time": t, "message": S.sign_text(json.dumps(body, separators=(",", ":")), priv)}
        t0 = 1_800_000_000
        msgs = [post(priv_old, pub_old, t0 + i * 900) for i in range(48)]          # 12 h of the old key
        msgs += [post(priv_new, pub_new, t0 + 48 * 900 + i * 900) for i in range(7)]   # 1 h 45 of the new key
        kept = B.only_pc_key(msgs)
        newest = max(kept, key=lambda m: m["time"]) if kept else None
        check("a rotated PC key: its newest post is kept within ~1.5 h", newest is not None and newest["time"] == msgs[-1]["time"],
              len(kept))
    print(f"\nnoleak red team: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    raise SystemExit(main())
