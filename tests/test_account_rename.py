"""engine/account_rename.py: the Names NinjaTrader says do not exist are corrected in the bot's local files (2026-10-27:
MFFUEVBLD602936016 / ...017 -> MFFUEVBLDR602936016 / ...017).    python -X utf8 -m tests.test_account_rename (temp only)"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import account_rename as R  # noqa: E402

RES = []
OLD50, OLD25, NEW50, NEW25 = "MFFUEVBLD602936016", "MFFUEVBLD602936017", "MFFUEVBLDR602936016", "MFFUEVBLDR602936017"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"), flush=True)


def main():
    t = tempfile.mkdtemp(prefix="le_rename_")
    nt, data = os.path.join(t, "NinjaTrader 8"), os.path.join(t, "data")
    os.makedirs(os.path.join(nt, "log"))
    os.makedirs(data)
    with open(os.path.join(nt, "log", "log.20261027.00000.txt"), "w") as fh:
        fh.write(f"10/27/2026 6:12:04 AM|ATI|OIF, 'PLACE;{OLD50};MNQ 12-26;SELL;7;MARKET;0;0;DAY;;LE1793095920W924ME;;' account does not exist '{OLD50}'\n"
                 f"10/27/2026 3:30:06 AM|ATI|OIF, 'PLACE;{OLD25};MNQ 12-26;BUY;3;MARKET;0;0;DAY;;LE1793086200M9XGME;;' account does not exist '{OLD25}'\n"
                 "10/27/2026 3:31:02 AM|ATI|order with ID/Name 'LE1793086200M9XGME' does not exist\n")
    files = {"start_bot.json": {"lit": OLD50, "atlas": OLD25, "write_mode": "direct", "prepped": True},
             "account_b.json": {"account_b": {"account": OLD25, "plan": "builder25k", "armed": True, "eval_start": "2026-10-26"}},
             "nt_accounts_allow.json": {"accounts": [OLD50, OLD25, "Sim101"]},
             "eval_anchor.json": {"v": 1, "accounts": {OLD50: {"balance": 49710.8, "floor": 48168.2, "as_of": "2026-10-23"}}},
             "autostart.json": {"cfg": {"adapter": "ninjatrader", "nt_account": OLD50}},
             "auto_resume.json": {"enabled": True, "account": OLD50, "proof": "x"}}
    for n, v in files.items():
        json.dump(v, open(os.path.join(data, n), "w"))
    miss = R.missing_names(nt)
    check("NinjaTrader's 'account does not exist' names read from its log (order-id lines ignored)", miss == {OLD50, OLD25}, miss)
    r = R.fix(nt, data)
    rd = lambda n: json.load(open(os.path.join(data, n)))
    check("renamed to the R names", r["renames"] == {OLD50: NEW50, OLD25: NEW25}, r)
    s = rd("start_bot.json")
    check("start names: Zlarior -> 50K R name, ATLAS -> 25K R name, other fields kept",
          s["lit"] == NEW50 and s["atlas"] == NEW25 and s["write_mode"] == "direct" and s["prepped"] is True, s)
    b = rd("account_b.json")["account_b"]
    check("ATLAS's block: account renamed, armed / eval start kept", b["account"] == NEW25 and b["armed"] is True and b["eval_start"] == "2026-10-26", b)
    check("allowlist + anchor (key) + autostart renamed", rd("nt_accounts_allow.json")["accounts"] == [NEW50, NEW25, "Sim101"]
          and NEW50 in rd("eval_anchor.json")["accounts"] and rd("autostart.json")["cfg"]["nt_account"] == NEW50)
    check("the owner's auto-resume opt-in is never touched (Run asks the phrase once)", rd("auto_resume.json")["account"] == OLD50)
    check("each changed file backed up", len(os.listdir(os.path.join(data, "rename_backup"))) == 5, os.listdir(os.path.join(data, "rename_backup")))
    r2 = R.fix(nt, data)
    check("twice = nothing more", r2["changed"] == [], r2)
    os.utime(os.path.join(nt, "log", "log.20261027.00000.txt"), (time.time() - 9 * 86400,) * 2)
    check("a log older than 7 days is not read", R.missing_names(nt) == set())
    check("a non-MFFU name is never guessed", R.renames({"Apex123", "Sim101"}) == {})
    n = sum(RES)
    print(f"account rename: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
