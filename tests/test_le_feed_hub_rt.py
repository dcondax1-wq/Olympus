"""Red team 2026-11-26 (day-ops2): LE_FeedHub silences a chart ONLY while the LE_Feed add-on's heartbeat is fresh, so a loaded but
stalled add-on can never leave the bot without bars (the chart writes again by itself within BeatMaxSeconds).
    python -X utf8 -m tests.test_le_feed_hub_rt
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
DRIVER = r'''
using System;
using System.Reflection;
using NinjaTrader.NinjaScript.AddOns;
public static class HubDrive {
    public static int Main() {
        int bad = 0;
        Action<string, bool> ok = (n, c) => { Console.WriteLine((c ? "PASS " : "FAIL ") + n); if (!c) bad++; };
        LE_FeedHub.HeadlessOn = true; LE_FeedHub.AccountsOn = true; LE_FeedHub.Cover("MNQ");
        ok("no heartbeat yet: the chart keeps writing", !LE_FeedHub.Covers("MNQ") && !LE_FeedHub.WritesAccounts());
        LE_FeedHub.Beat();
        ok("fresh heartbeat: the add-on covers MNQ (one writer)", LE_FeedHub.Covers("MNQ") && LE_FeedHub.WritesAccounts());
        FieldInfo f = typeof(LE_FeedHub).GetField("beatTicks", BindingFlags.NonPublic | BindingFlags.Static);
        f.SetValue(null, DateTime.UtcNow.AddSeconds(-(LE_FeedHub.BeatMaxSeconds + 5)).Ticks);
        ok("stalled add-on (no beat for > BeatMaxSeconds): the chart writes again", !LE_FeedHub.Covers("MNQ") && !LE_FeedHub.WritesAccounts());
        LE_FeedHub.Beat();
        ok("beat again: covered again", LE_FeedHub.Covers("MNQ"));
        return bad == 0 ? 0 : 1;
    }
}
'''


def main() -> int:
    if not (shutil.which("mcs") and shutil.which("mono")):
        print("SKIP: mono (mcs) not installed")
        return 0
    tmp = tempfile.mkdtemp()
    try:
        drv = os.path.join(tmp, "HubDrive.cs")
        open(drv, "w").write(DRIVER)
        exe = os.path.join(tmp, "hub.exe")
        r = subprocess.run(["mcs", "-langversion:5", "-main:HubDrive", "-out:" + exe, os.path.join(STUB, "NtStubsLive.cs"), CS, drv],
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            print("FAIL compile:", (r.stdout + r.stderr)[-1500:])
            return 1
        r = subprocess.run(["mono", exe], capture_output=True, text=True, timeout=120)
        print(r.stdout.strip())
        print("le_feed hub red team:", "ALL PASS" if r.returncode == 0 else "FAIL")
        return r.returncode
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
