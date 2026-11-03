"""ninjatrader/LE_Feed.cs (the no-chart NinjaTrader bar feed) against hand-made NinjaTrader stubs (tests/nt_stub/), 2026-11-03.

1. C# 5 compile (mono mcs -langversion:5) against NtStubs.cs: the stubs give NinjaScriptBase the properties that can hide a
   NinjaTrader type inside an AddOn (Instrument, Bars, TradingHours, Account), so a name clash fails here too.
2. Behaviour under mono with NtStubsLive.cs: proof of life (status file + Output window line the moment it starts, from the
   window event alone), history + live 1m bar append at bar OPEN times, the 1m open, accounts.csv, one feed for two start
   paths, and the F5 takeover (an older copy stops when a newer one writes le_feed_owner.txt).
3. The Python reader parses the status line it writes (extra keys such as started= are ignored).

Stubs check syntax and logic, not NinjaTrader's real API. Skipped (exit 0) when mono is not installed (Windows PC).
Run: python -X utf8 -m tests.test_le_feed_cs
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUB = os.path.join(ROOT, "tests", "nt_stub")
CS = os.path.join(ROOT, "ninjatrader", "LE_Feed.cs")
FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""), flush=True)
    if not ok:
        FAILS.append(name)


def main() -> int:
    if not (shutil.which("mcs") and shutil.which("mono")):
        print("SKIP: mono (mcs) not installed")
        return 0
    tmp = tempfile.mkdtemp(prefix="le_ntstub_")
    try:
        r = subprocess.run(["mcs", "-langversion:5", "-target:library", "-out:" + os.path.join(tmp, "a.dll"),
                            os.path.join(STUB, "NtStubs.cs"), CS], capture_output=True, text=True, timeout=120)
        check("1. LE_Feed.cs compiles as C# 5 against the NinjaTrader stubs", r.returncode == 0, (r.stdout + r.stderr)[-800:])
        exe = os.path.join(tmp, "drv.exe")
        r = subprocess.run(["mcs", "-langversion:5", "-out:" + exe, os.path.join(STUB, "NtStubsLive.cs"), CS],
                           capture_output=True, text=True, timeout=120)
        check("2a. behaviour driver compiles", r.returncode == 0, (r.stdout + r.stderr)[-800:])
        if r.returncode == 0:
            data = os.path.join(tmp, "nt")
            r = subprocess.run(["mono", exe], capture_output=True, text=True, timeout=120, env={**os.environ, "LE_NTSTUB_DIR": data})
            print(r.stdout)
            check("2b. behaviour driver: ALL PASS", r.returncode == 0 and "ALL PASS" in r.stdout, r.stderr[-400:])
        sys.path.insert(0, ROOT)
        from engine.ninjatrader import parse_feed_status
        st = parse_feed_status("1793668095,source=addon,instruments=MNQ 12-26;NQ 12-26,last_1m=1793668020,resubs=2,connected=1,"
                               "started=1793668000")
        check("3. the bot reads the add-on's status line (started= ignored)",
              st is not None and st["instruments"] == ["MNQ 12-26", "NQ 12-26"] and st["resubs"] == 2 and st["connected"] is True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
