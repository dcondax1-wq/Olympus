"""`python -m engine.account_b --min-room 0` (owner YES 2026-11-19, Decide card atlas-funded-keep-trading).

Pins: the switch writes "min_room" into the PC-local data/account_b.json only (a temp copy here, never the real file),
keeps every other key of ATLAS's block exactly (armed, account, stage, funded keys, payouts), the funded spec's stuck line
becomes $0 (was MIN_ROOM $100), "default" puts it back, a bad value or no ATLAS block is refused and changes nothing, the
eval stage keeps its own eval_min_room line, and the tracked second_model.json is never written.

    python -X utf8 -m tests.test_account_b_min_room
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import account_b as AB  # noqa: E402

RESULTS = []
FUNDED = {"account": "MFFUFUNDED000000017", "plan": "builder25k", "eval_start": "2026-10-26", "sizing": "need",
          "strategies": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"], "armed": True, "stage": "funded",
          "funded_start": "2026-11-18", "funded_balance": 25000.0, "payouts": {}, "eval_account": "MFFUEVBLD000000016"}


def check(name, ok, info=""):
    RESULTS.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({str(info)[:300]})" if info and not ok else ""), flush=True)


def tmp_cfg(block):
    d = tempfile.mkdtemp(prefix="abmr_")
    p = os.path.join(d, "second_model.json")
    shutil.copy(os.path.join(ROOT, "second_model.json"), p)
    if block is not None:
        AB.write_local(block, p)
    return d, p


def main() -> bool:
    real_local = os.path.join(ROOT, "data", "account_b.json")
    real_before = open(real_local, "rb").read() if os.path.exists(real_local) else None
    d, p = tmp_cfg(dict(FUNDED))
    tracked0 = open(p, "rb").read()
    try:
        spec0 = AB.normalize(AB.raw_cfg(p))
        check("before: the funded account stops under $100 (MIN_ROOM)", AB.min_room(spec0) == 100.0, AB.min_room(spec0))
        r = AB.set_min_room("0", p)
        check("--min-room 0 is accepted", r["ok"] and r["to"] == 0.0, r)
        blk = AB.raw_cfg(p)
        check("data/account_b.json now says min_room 0", blk.get("min_room") == 0.0, blk)
        check("every other key of the block is kept exactly",
              {k: v for k, v in blk.items() if k != "min_room"} == FUNDED, blk)
        check("armed stays armed (the switch never arms or disarms)", blk.get("armed") is True, blk)
        spec = AB.normalize(blk)
        check("the funded spec's stuck line is $0 (keeps trading 1 micro while it fits)", AB.min_room(spec) == 0.0, AB.min_room(spec))
        check("no problem in the spec", spec.get("problem") is None, spec.get("problem"))
        check("the message says it keeps trading 1 micro", "1 micro" in r["say"] and "$0" in r["say"], r["say"])
        check("the tracked second_model.json is not written", open(p, "rb").read() == tracked0)
        r2 = AB.set_min_room("default", p)
        check("--min-room default removes the key (back to $100)", r2["ok"] and "min_room" not in AB.raw_cfg(p)
              and AB.min_room(AB.normalize(AB.raw_cfg(p))) == 100.0, r2)
        before = AB.raw_cfg(p)
        for bad in ("-5", "5000", "abc", ""):
            rb = AB.set_min_room(bad, p)
            check(f"--min-room {bad!r} is refused", not rb["ok"] and "0 to 1000" in rb["error"], rb)
        check("... and nothing changed", AB.raw_cfg(p) == before)
        # the CLI prints [OK] and returns 0
        orig = AB.raw_cfg
        try:
            AB.raw_cfg = lambda path=None: orig(p)
            w_orig = AB.write_local
            AB.write_local = lambda block, path=None, why="": w_orig(block, p, why)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = AB.main(["--min-room", "0"])
        finally:
            AB.raw_cfg = orig
            AB.write_local = w_orig
        check("python -m engine.account_b --min-room 0 -> [OK], exit 0", rc == 0 and "[OK]" in buf.getvalue(), buf.getvalue())
        check("... min_room 0 in the temp local file", AB.raw_cfg(p).get("min_room") == 0.0)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    # eval stage: the switch is stored, the eval's own line (eval_min_room $200) still rules until it is funded
    ev = {k: v for k, v in FUNDED.items() if k not in ("stage", "funded_start", "funded_balance", "payouts", "eval_account")}
    d, p = tmp_cfg(ev)
    try:
        r = AB.set_min_room(0, p)
        spec = AB.normalize(AB.raw_cfg(p))
        check("eval stage: stored, the eval's own stuck line ($200) still applies", r["ok"] and AB.min_room(spec) == 200.0
              and "eval_min_room" in r["say"], (r, AB.min_room(spec)))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    # no ATLAS block: refused, nothing written
    d, p = tmp_cfg(None)
    try:
        r = AB.set_min_room("0", p)
        check("no ATLAS account: refused", not r["ok"] and "no account" in r["error"], r)
        check("... no local file made", not os.path.exists(AB.local_path(p)))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    real_after = open(real_local, "rb").read() if os.path.exists(real_local) else None
    check("the real data/account_b.json is untouched", real_after == real_before)
    ok = all(RESULTS)
    print(f"{sum(RESULTS)}/{len(RESULTS)} passed")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
