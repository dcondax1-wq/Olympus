"""PC guard red team (2026-11-23), static (no pwsh needed): the elevated undo can never be steered by the "before" file.

  a. -Off checks every saved item against the exact values the script writes (Allowed) BEFORE any write
  b. the allow-list = the 7 Windows Update values, the 4 powercfg GUIDs on a GUID-shaped plan, the 2 adapter properties
     with Enabled / Disabled; numbers only for registry / power values
  c. %ProgramData%\\Olympus is made admin + SYSTEM write, users read (ProgramData lets any user create a folder)
    python -X utf8 -m tests.test_win_guard_rt
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{str(info)[:300]}]"))


def main() -> int:
    t = open(os.path.join(ROOT, "scripts", "win_guard.ps1"), encoding="ascii").read()
    off = t.split("if ($Off) {", 1)[1].split("Write-Host '  ==== PC GUARD: Windows cannot kill a trade", 1)[0]
    i_allow = off.find("Allowed $k $it")
    i_write = min(x for x in (off.find("Set-RegDword"), off.find("Remove-RegVal"), off.find("Set-PowerIdx"), off.find("Set-NicPm")) if x >= 0)
    check("a. -Off: Allowed is checked before the first write, an unknown item is dropped (continue)", 0 <= i_allow < i_write
          and "continue" in off[i_allow:i_write], (i_allow, i_write))
    allow = t.split("$AllowReg = @{}", 1)[1].split("function Allowed", 1)[0]
    names = re.findall(r"@\(\$(WU|WUP|AU), '([A-Za-z]+)'\)", allow)
    want = {("WU", "ActiveHoursStart"), ("WU", "ActiveHoursEnd"), ("WU", "SmartActiveHoursState"), ("WUP", "SetActiveHours"),
            ("WUP", "ActiveHoursStart"), ("WUP", "ActiveHoursEnd"), ("AU", "NoAutoRebootWithLoggedOnUsers")}
    check("b. registry allow-list = exactly the 7 values the script writes", set(names) == want, names)
    writes = set(re.findall(r"@\(\$(WU|WUP|AU), '([A-Za-z]+)', ", t))
    check("b. ... and the script writes no other registry value", writes == want, writes)
    fn = t.split("function Allowed", 1)[1].split("\n}", 1)[0]
    check("b. power: GUID-shaped plan + the known setting GUIDs; values numbers only; nic: the 2 props, Enabled / Disabled",
          "$AllowPw.ContainsKey" in fn and "$GuidRx" in fn and "'^[0-9]{1,10}$'" in fn and "$NicProps -contains" in fn
          and "@('Enabled', 'Disabled')" in fn and "return $false" in fn, fn[:200])
    check("c. the saved-values folder is created admin + SYSTEM write, users read",
          "O:BAD:PAI(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)(A;OICI;0x1200a9;;;BU)" in t and "Set-Acl" in t)
    check("c. ASCII + CRLF", all(b < 128 for b in open(os.path.join(ROOT, "scripts", "win_guard.ps1"), "rb").read())
          and b"\r\n" in open(os.path.join(ROOT, "scripts", "win_guard.ps1"), "rb").read())
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
