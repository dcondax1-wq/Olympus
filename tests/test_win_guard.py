"""PC GUARD (night-pcguard 2026-11-23): Windows Update / sleep / a network adapter cannot stop a trade. scripts/win_guard.ps1
runs in FIX_CLOCK.bat's one administrator window; tools/bat/FIX_CLOCK_OFF.bat undoes it from the values it saved.

    python -X utf8 -m tests.test_win_guard       (no real registry / powercfg / adapter is touched)

 a. static (always): ASCII + CRLF, the 5.1 structure check (tests/win_harness/ps_struct), programs only by their System32
    path, only the three Windows Update keys + powercfg + the adapters' power settings (never Defender, firewall, accounts,
    BitLocker), FIX_CLOCK -> win_guard and FIX_CLOCK_OFF -> win_guard -Off, the saved "before" file is admin-only
    (%ProgramData%), the adapter is never reset (-NoRestart).
 b. with pwsh (LE_PWSH or pwsh on PATH, else SKIPPED and said): the real script on a fake machine (LE_PG_T_DIR): on, on
    again (idempotent, the first "before" values kept), off = exactly the old values back (absent ones removed).
 c. engine/win_guard.line, readiness' Monday lines and TRADE_HOME's status say "Windows guard: on / OFF / not set up".
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests.win_harness.ps_struct import check_script  # noqa: E402

RES = []
PS1 = os.path.join(ROOT, "scripts", "win_guard.ps1")
CLOCK = os.path.join(ROOT, "scripts", "fix_clock.ps1")
WU = r"HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings"
WUP = r"HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
AU = WUP + r"\AU"
SLEEP = "238c9fa8-0aad-41ed-83f4-97be242c8f20"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def code_only(src: str) -> str:
    src = re.sub(r"<#.*?#>", "", src, flags=re.S)
    return "\n".join(ln.split("#", 1)[0] if not ln.lstrip().startswith("'") else ln for ln in src.splitlines())


def static():
    raw = open(PS1, "rb").read()
    src = raw.decode("ascii", "replace")
    check("a. win_guard.ps1: ASCII only, CRLF line ends", all(b < 128 for b in raw) and b"\n" not in raw.replace(b"\r\n", b""))
    check("a. Windows PowerShell 5.1 structure (no PS7-only operators, brackets / strings closed)", check_script(src) == [], check_script(src))
    code = code_only(src)
    calls = re.findall(r"(?<![>\d])&\s*(\S+)", code)          # the call operator (not the 2>&1 redirect)
    check("a. every program it runs is a full System32 path ($Powercfg = System32\\powercfg.exe), nothing by bare name",
          "$Sys32 = [Environment]::GetFolderPath('System')" in src and "Join-Path $Sys32 'powercfg.exe'" in src
          and all(c in ("$Powercfg",) for c in calls if not c.startswith("(")) and not re.search(r"(?m)^\s*powercfg\b", code), calls)
    bad = [w for w in ("MpPreference", "Defender", "NetFirewall", "advfirewall", "BitLocker", "manage-bde", "LocalUser",
                       "LocalGroup", "net user", "Disable-ScheduledTask", "bcdedit", "Stop-Service", "Set-Service") if w.lower() in code.lower()]
    check("a. never Defender, the firewall, accounts, BitLocker, services or boot settings", not bad, bad)
    keys = set(re.findall(r"'(HKLM:[^']+)'", code))
    check("a. registry: only the 3 Windows Update keys (UX settings, the policy, its AU key)", keys == {WU, WUP, AU}, keys)
    check("a. Windows Update: active hours 01:00-17:00 New York in local time (16 h <= Windows' 18 h), the automatic guess off, "
          "NoAutoRebootWithLoggedOnUsers = 1, a Saturday restart advice",
          "Local-Hour 1" in code and "Local-Hour 17" in code and "'NoAutoRebootWithLoggedOnUsers', 1" in code
          and "'SmartActiveHoursState', 0" in code and "'SetActiveHours', 1" in code and "Saturday" in src)
    check("a. power: the CURRENT plan's AC values only (/setacvalueindex on the active scheme), sleep / hibernate / disk / USB "
          "selective suspend -> 0; never DC (battery), never another plan",
          "/setacvalueindex $scheme" in code and "/setdcvalueindex" not in code and "/getactivescheme" in code
          and code.count("@('") >= 4 and SLEEP in code)
    check("a. network adapters: power saving off with -NoRestart (the adapter is never reset: NinjaTrader keeps its connection)",
          "NoRestart = $true" in code and "Set-NetAdapterPowerManagement" in code and "Restart-NetAdapter" not in code
          and "Disable-NetAdapter " not in code)
    check("a. the Startup check changes nothing (reads the Startup folder / the LiquidityEngine task only)",
          "Get-ChildItem -LiteralPath $st -Filter '*.lnk'" in code and "CreateShortcut" not in code and "Register-ScheduledTask" not in code)
    check("a. the 'before' values are saved BEFORE each change, kept from the first run, in %ProgramData%\\Olympus (admin-only), "
          "never in the user-writable bot folder", "GetFolderPath('CommonApplicationData')" in code and "if ($newPrev.ContainsKey($key)) { return }" in code
          and code.count("[void](Save-Prev $newPrev)") >= 3)
    check("a. -Off puts each saved value back (a value that was absent is removed), then deletes the saved file",
          "Remove-RegVal $it.a $it.b" in code and "Set-RegDword $it.a $it.b ([int]$it.value)" in code and "Remove-Item -LiteralPath $PrevPath" in code)
    craw = open(CLOCK, "rb").read()
    csrc = craw.decode("ascii", "replace")
    check("a. fix_clock.ps1 runs the guard in the SAME administrator window (on), and -Off undoes it; still ASCII CRLF, 5.1",
          csrc.count("Join-Path $PSScriptRoot 'win_guard.ps1'") == 2 and "& $guard -Off" in csrc and "& $guard }" in csrc
          and all(b < 128 for b in craw) and b"\n" not in craw.replace(b"\r\n", b"") and check_script(csrc) == [])
    for bat, word in (("FIX_CLOCK.bat", "PC GUARD"), ("tools/bat/FIX_CLOCK_OFF.bat", "PC GUARD")):
        b = open(os.path.join(ROOT, bat), "rb").read()
        check(f"a. {bat}: ASCII CRLF, says what the guard does, still the admin check + full System32 paths", word.encode() in b
              and b"net.exe\" session" in b and b"%SystemRoot%\\System32\\WindowsPowerShell" in b
              and b"\n" not in b.replace(b"\r\n", b"") and all(x < 128 for x in b))


def find_pwsh():
    p = os.environ.get("LE_PWSH") or shutil.which("pwsh")
    return p if p and os.path.exists(p) else None


def run(pwsh, d, *args, tz="0"):
    env = {**os.environ, "LE_PG_T_DIR": d, "LE_PG_T_TZ": tz}
    r = subprocess.run([pwsh, "-NoProfile", "-NoLogo", "-File", PS1, *args], capture_output=True, text=True, timeout=120, env=env)
    return r.returncode, r.stdout + r.stderr


def dynamic():
    pwsh = find_pwsh()
    if not pwsh:
        print("[SKIP] b. no pwsh here: the real-script runs are skipped (they run where pwsh is installed)", flush=True)
        return
    d = tempfile.mkdtemp(prefix="le_pg_")
    try:
        before = {"scheme": "11111111-2222-3333-4444-555555555555", f"pw|{SLEEP}|29f6c1db-86da-48c5-9fdb-f2b67b1f44da": 1800,
                  f"pw|{SLEEP}|9d7815a6-7ee4-497e-8888-515a05f02364": 10800,
                  "pw|0012ee47-9041-4b5d-9b77-535fba8b1442|6738e2c4-e8a5-4a42-b16a-e040e769756e": 1200,
                  f"reg|{WU}|ActiveHoursStart": 8, f"reg|{WU}|ActiveHoursEnd": 17, "nics": ["Wi-Fi"],
                  "nic|Wi-Fi|AllowComputerToTurnOffDevice": "Enabled", "nic|Wi-Fi|SelectiveSuspend": "Unsupported",
                  "startup": ["LE bot server.lnk"]}
        json.dump(before, open(os.path.join(d, "machine.json"), "w"))
        rc, out = run(pwsh, d, tz="1")                     # a PC one hour ahead of New York
        m = json.load(open(os.path.join(d, "machine.json")))
        st = json.load(open(os.path.join(d, "status.json")))
        check("b. on: active hours 02:00-18:00 local (= 01:00-17:00 New York), no restart while signed in, sleep / hibernate / "
              "disk -> 0 (USB not on this PC: left), Wi-Fi power saving off; NinjaTrader's missing Startup shortcut = one [FIX]",
              m[f"reg|{WU}|ActiveHoursStart"] == 2 and m[f"reg|{WU}|ActiveHoursEnd"] == 18 and m[f"reg|{AU}|NoAutoRebootWithLoggedOnUsers"] == 1
              and m[f"pw|{SLEEP}|29f6c1db-86da-48c5-9fdb-f2b67b1f44da"] == 0 and m["nic|Wi-Fi|AllowComputerToTurnOffDevice"] == "Disabled"
              and m["nic|Wi-Fi|SelectiveSuspend"] == "Unsupported" and "NinjaTrader does NOT start" in out and st["on"] is True
              and st["items"]["nt_startup"] == "missing", (rc, out[-600:], m))
        prev1 = open(os.path.join(d, "win_guard_prev.json")).read()
        rc2, out2 = run(pwsh, d, tz="1")
        check("b. on again: idempotent (nothing new saved: the FIRST run's 'before' values are kept)",
              open(os.path.join(d, "win_guard_prev.json")).read().split('"items"')[1] == prev1.split('"items"')[1], out2[-300:])
        rc3, out3 = run(pwsh, d, "-Off")
        m3 = json.load(open(os.path.join(d, "machine.json")))
        same = {k: v for k, v in before.items()}
        check("b. off: every changed value back exactly (8 / 17 hours, 1800 / 10800 / 1200 s, Wi-Fi Enabled), the values that were "
              "absent removed, the saved file gone, status off",
              rc3 == 0 and all(m3.get(k) == v for k, v in same.items()) and not any(k.startswith(f"reg|{WUP}") for k in m3)
              and f"reg|{WU}|SmartActiveHoursState" not in m3 and not os.path.exists(os.path.join(d, "win_guard_prev.json"))
              and json.load(open(os.path.join(d, "status.json")))["on"] is False, (out3[-400:], m3))
        rc4, out4 = run(pwsh, d, "-Off")
        check("b. off again: 'Nothing to undo', nothing changed", rc4 == 0 and "Nothing to undo" in out4, out4[-200:])
    finally:
        shutil.rmtree(d, ignore_errors=True)


def python_side():
    from engine import win_guard as PG, readiness as R, trade_home as TH
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "win_guard.json")
        none = PG.line(p)
        json.dump({"v": 1, "on": True, "items": {"update": "on", "power": "on", "nic": "on", "bot_startup": "ok", "nt_startup": "missing"}}, open(p, "w"))
        on = PG.line(p)
        json.dump({"v": 1, "on": False, "items": {"update": "fix"}}, open(p, "w"))
        off = PG.line(p)
    check("c. engine/win_guard.line: not set up / on (+ a missing Startup shortcut named) / OFF with what failed",
          none.startswith("Windows guard: not set up") and "FIX_CLOCK.bat" in none and on.startswith("Windows guard: on")
          and "NinjaTrader does not start" in on and off.startswith("Windows guard: OFF") and "update" in off, (none, on, off))
    import time as _t
    b1 = R.build({"win_guard": "Windows guard: on"}, _t.time())
    b2 = R.build({"win_guard": off}, _t.time())
    b3 = R.build({}, _t.time())
    check("c. readiness (the Monday lines): 'Windows guard: on' shown; OFF = a problem; no fact = no line (other PCs)",
          "Windows guard: on" in b1["lines"] and "Windows guard is off" not in b1["problems"] and "Windows guard is off" in b2["problems"]
          and not any("Windows guard" in x for x in b3["lines"]), (b1["lines"], b2["problems"]))
    kw = dict(now=0, bot={"running": True, "last_poll": 0}, accounts=[{"name": "MFFUEVX1", "plan": "x", "armed": True}],
              keepalive={"a": True}, alerts=(True, False, True), clock=0.1, tasks={})
    L1, P1 = TH.status_screen(**kw, guard="Windows guard: on")
    L2, P2 = TH.status_screen(**kw, guard=off)
    check("c. TRADE_HOME status: 'Guard : Windows guard on'; off -> 9 with the FIX_CLOCK.bat step",
          any("Windows guard on" in x for x in L1) and not any(p[0] == "9" for p in P1)
          and any(p[0] == "9" and "FIX_CLOCK.bat" in p[1] for p in P2), (L1, P2))
    man = open(os.path.join(ROOT, "docs", "OWNER_MANUAL.md"), encoding="utf-8").read()
    check("c. OWNER_MANUAL: 'What the one admin click does' (the clock + the guard + the undo)",
          "What the one admin click does" in man and "tools/bat/FIX_CLOCK_OFF.bat" in man.split("What the one admin click does")[1][:3000])


def main():
    static()
    dynamic()
    python_side()
    n = sum(RES)
    print(f"win guard: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
