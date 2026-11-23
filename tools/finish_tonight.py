"""FINISH TONIGHT (owner 2026-11-23: "make a code that fixes all of it and I can send and be done").

Run once from the bot folder, evening, bot flat:   python -X utf8 tools/finish_tonight.py

1. Windows never sleeps / hibernates while plugged in (powercfg, current power plan).
2. Order flow: pip install pyarrow, copy ninjatrader/LE_TickRec.cs into NinjaTrader's AddOns folder, tick recorder ON.
3. ATLAS alongside Zlarior on the Builder 50K and the Builder 25K #2 (engine.combo50k --on per account). Each one asks YOU to
   type I ACCEPT LIVE RISK: this script never types it and never arms anything by itself.
4. Prints the 2 hand steps no script can do (F5 in NinjaTrader once; TRADE_HOME 4 for a newly bought account).
Account names are read from the bot's own inventory and shown as their last 4 characters only. Never raises: each step says
[OK] or [FIX] and the next step still runs.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
PY = sys.executable


def say(ok, msg):
    print(("[OK]  " if ok else "[FIX] ") + msg, flush=True)


def run(args, **kw):
    try:
        return subprocess.run(args, cwd=ROOT, **kw).returncode
    except Exception as e:  # noqa: BLE001
        print("      " + e.__class__.__name__ + ": " + str(e))
        return 1


def step_sleep():
    if os.name != "nt":
        return say(False, "not Windows: skipped the never-sleep step")
    bad = 0
    for a in (["/change", "standby-timeout-ac", "0"], ["/change", "hibernate-timeout-ac", "0"]):
        bad += run(["powercfg", *a], capture_output=True) != 0
    say(not bad, "PC never sleeps or hibernates while plugged in" if not bad
        else "power settings refused: Settings > System > Power > Screen and sleep > When plugged in: Never")


def addons_dir():
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    for base in (docs, os.path.join(os.path.expanduser("~"), "OneDrive", "Documents")):
        d = os.path.join(base, "NinjaTrader 8", "bin", "Custom", "AddOns")
        if os.path.isdir(d):
            return d
    return None


def step_orderflow():
    rc = run([PY, "-m", "pip", "install", "-q", "pyarrow"])
    say(rc == 0, "pyarrow installed (tick files as parquet)" if rc == 0 else "pip install pyarrow failed: ticks are saved as .csv.gz instead (fine)")
    src = os.path.join(ROOT, "ninjatrader", "LE_TickRec.cs")
    dst_dir = addons_dir()
    if not os.path.exists(src):
        say(False, "ninjatrader/LE_TickRec.cs is missing: run UPDATE first, then this again")
    elif not dst_dir:
        say(False, "NinjaTrader's AddOns folder not found: copy ninjatrader\\LE_TickRec.cs into Documents\\NinjaTrader 8\\bin\\Custom\\AddOns\\")
    else:
        try:
            shutil.copy2(src, os.path.join(dst_dir, "LE_TickRec.cs"))
            say(True, "order-flow recorder file copied into NinjaTrader's AddOns folder")
        except Exception as e:  # noqa: BLE001
            say(False, f"copy failed ({e.__class__.__name__}): copy ninjatrader\\LE_TickRec.cs into {dst_dir}")
    rc = run([PY, "-X", "utf8", "-m", "engine.tickrec", "enable"])
    say(rc == 0, "tick recorder ON (it fetches about a year of ticks by itself, outside trading hours)" if rc == 0
        else "tick recorder did not switch on: python -X utf8 -m engine.tickrec enable")


def zlarior_accounts():
    """[(label, NinjaTrader name)]: the Zlarior 50K (role main) and every Builder 25K Zlarior extra account (the 25K #2)."""
    out = []
    try:
        from engine import account_cli
        for r in account_cli.inventory():
            name = str(r.get("name") or "").strip()
            if not name or r.get("sim") or r.get("enabled", True) is False:
                continue
            if r.get("role") == "main":
                out.append(("Zlarior 50K", name))
            elif r.get("role") == "extra" and "25" in str(r.get("plan") or "") and "rapid" not in str(r.get("plan") or "").lower():
                out.append(("Zlarior 25K #2", name))
    except Exception as e:  # noqa: BLE001
        say(False, f"could not read the accounts ({e.__class__.__name__})")
    return out


def step_atlas():
    accts = zlarior_accounts()
    if not accts:
        return say(False, "no Zlarior account found: run START once, then this again")
    for label, name in accts:
        print(f"\n--- ATLAS alongside Zlarior on {label} ..{name[-4:]} ---", flush=True)
        rc = run([PY, "-X", "utf8", "-m", "engine.combo50k", "--on", "--account", name])
        say(rc == 0, f"ATLAS ON for {label} ..{name[-4:]}" if rc == 0
            else f"ATLAS not switched on for {label} (phrase not typed or a check failed: read the lines above)")


def main():
    print("FINISH TONIGHT: never-sleep, order flow, ATLAS on both Zlarior accounts\n", flush=True)
    step_sleep()
    step_orderflow()
    step_atlas()
    print("\nLAST 2 HAND STEPS (no script can do these):")
    print("  1. NinjaTrader: New > NinjaScript Editor > press F5 once, then restart NinjaTrader (turns the order-flow recorder on).")
    print("  2. A newly bought account: TRADE_HOME.bat > 4 (add account), then START.")
    print("Done. Leave the PC on, plugged in, NinjaTrader open.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
