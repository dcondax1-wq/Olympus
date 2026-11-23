"""Red team on night-k7proof (2026-11-23): go.armed_accounts now keys the two Rapid slots "rapid" / "rapid2". Proof that the
per-slot key breaks nothing around it and BLITZ never shows. Temp files only, nothing armed, no network.

    python -X utf8 -m tests.test_k7proof_rt        (~2 s)

1. START summary: with a keep-alive file from BEFORE the fix (only "rapid" ON), keepalive_view shows the 2nd Rapid OFF and
   keepalive_missing offers the phrase for it alone (before, the shared key showed it ON by mistake); after the phrase both ON.
2. The owner's own OFF for the 2nd Rapid (owner_off "rapid2") is kept by the phrase and not offered again; the 1st stays ON.
3. BLITZ (role c, armed) and a Sim name never appear in armed_accounts / keepalive_view / keepalive_missing.
4. Arming and the auto-resume record never read armed_accounts (only keep-alive consent / view / missing do).
5. The phone's 7-day clock (engine/clock7) maps key "rapid2" to the 2nd Rapid's own row: its ON switch is not the 1st's.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import account_cli, go, keepalive as K  # noqa: E402
from engine.tradovate import LIVE_PHRASE  # noqa: E402

RES = []
INV = [{"role": "main", "name": "MFFU-REAL-0050", "mffu": True, "id": "zlarior"},
       {"role": "b", "name": "MFFU-REAL-0025", "armed": True, "mffu": True, "id": "atlas"},
       {"role": "rapid", "name": "MFFU-REAL-R025", "armed": True, "mffu": True, "id": "rapid", "plan": "rapideod25"},
       {"role": "rapid", "name": "MFFU-REAL-R050", "armed": True, "mffu": True, "id": "rapid2", "plan": "rapideod"},
       {"role": "rapid", "name": "Sim105", "armed": True, "mffu": True, "id": "rapid2", "plan": "rapideod", "sim": True},
       {"role": "c", "name": "MFFU-REAL-BLTZ", "armed": True, "id": "blitz", "mffu": True}]


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:400]) if info and not ok else ''}")
    RES.append(bool(ok))


def _world(tmp, file):
    p = os.path.join(tmp, "keepalive.json")
    if file is not None:
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(file, fh)
    return p


def main():
    real_inv, real_ka = account_cli.inventory, go._ka_path
    account_cli.inventory = lambda *a, **k: [dict(r) for r in INV]
    try:
        with tempfile.TemporaryDirectory() as tmp:
            p = _world(tmp, {"accounts": {"lit": True, "atlas": True, "rapid": True}, "owner_off": {},
                             "consent": {"day": "2026-11-20", "accounts": ["lit", "atlas", "rapid"]}})
            go._ka_path = lambda: p
            v, miss = go.keepalive_view(), go.keepalive_missing()
            check("1. old file (only 'rapid' ON): the 2nd Rapid shows OFF, the 1st ON",
                  any("..R025" in l for l in v["on"]) and any("..R050" in l for l in v["off"]) and not any("..R050" in l for l in v["on"]), v)
            check("1. START offers the phrase for the 2nd Rapid alone", len(miss) == 1 and "..R050" in miss[0], miss)
            go.keepalive_consent(LIVE_PHRASE)
            v2 = go.keepalive_view()
            check("1. after the phrase both Rapids ON, nothing missing", not v2["off"] and len(v2["on"]) == 4 and not go.keepalive_missing(), v2)

            p2 = os.path.join(tmp, "k2.json")
            with open(p2, "w", encoding="utf-8") as fh:
                json.dump({"accounts": {"rapid": True}, "owner_off": {"rapid2": "owner"}, "consent": {}}, fh)
            go._ka_path = lambda: p2
            r = K.start_consent(LIVE_PHRASE, go.armed_accounts(), path=p2)
            C = K.load_config(None, path=p2)
            check("2. the owner's OFF for the 2nd Rapid is kept by the phrase; the 1st stays ON; not offered again",
                  C["accounts"].get("rapid2") is not True and C["accounts"].get("rapid") is True
                  and any("..R050" in x for x in r["kept_off"]) and not go.keepalive_missing(), (r, C["accounts"]))

            rows = go.armed_accounts()
            names = [n for _k, _l, n in rows] + v2["on"] + v2["off"] + miss
            check("3. BLITZ and the Sim name never appear (armed list, view, missing)",
                  not any("BLTZ" in str(x) or "Sim105" in str(x) for x in names), rows)
            check("3. armed list keys: exactly lit, atlas, rapid, rapid2 (one each)",
                  [k for k, _l, _n in rows] == ["lit", "atlas", "rapid", "rapid2"], rows)
    finally:
        account_cli.inventory, go._ka_path = real_inv, real_ka

    src = open(os.path.join(ROOT, "engine", "go.py"), encoding="utf-8").read()
    users = [m.group(1) for m in re.finditer(r"\ndef (\w+)\(", src)
             if "armed_accounts(" in src[m.end():src.find("\ndef ", m.end()) if src.find("\ndef ", m.end()) > 0 else len(src)]]
    ar = open(os.path.join(ROOT, "engine", "autoresume.py"), encoding="utf-8").read()
    check("4. only keep-alive consent / missing / view read armed_accounts (arming, autoresume never)",
          set(users) <= {"keepalive_consent", "keepalive_missing", "keepalive_view"} and "armed_accounts" not in ar, users)

    from engine import clock7 as C7
    mf = {"a": [{"id": "rapid", "nm": "Rapid 25K", "sd": "2026-11-17"}, {"id": "rapid2", "nm": "Rapid 50K", "sd": "2026-11-17"}]}
    k7 = C7.build(mf, {"on": {"rapid": True}, "last": {}}, now=1795564800) or {}
    on = {r["id"]: r.get("on") for r in k7.get("a") or []}
    check("5. phone 7-day clock: key 'rapid2' is the 2nd Rapid's own row (only the 1st ON here)",
          C7.ka_id("rapid2") == "rapid2" and on == {"rapid": True, "rapid2": False}, on)

    ok = sum(RES)
    print(f"\nk7proof red team: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
