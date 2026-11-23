"""Shortcuts to a moved .bat follow it (red team 2026-11-23, night-cleanup moved 42 .bat files from the bot folder to tools\\bat).

A Windows shortcut (.lnk) the owner made himself on the Desktop, in the Startup folder or the Start menu that still points at
<bot folder>\\X.bat, where X.bat now lives only in tools\\bat\\, would open "the item has been moved" after the update. Once a
day the 15-minute report (tools/pc_report.py) runs fix(): such a shortcut is pointed at tools\\bat\\X.bat (working folder = the
bot folder). Nothing else is touched: a shortcut to a .bat that still exists, to another folder or to any other program stays
as it is; nothing is created or deleted. Windows only; never raises.

    python -X utf8 tools/bat_shortcuts.py          list what it would change (no change)
    python -X utf8 tools/bat_shortcuts.py --fix    change them now
"""
from __future__ import annotations

import json
import ntpath
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAT_DIR = os.path.join(ROOT, "tools", "bat")
STATE = os.path.join(ROOT, "data", "bat_shortcuts.json")     # gitignored: the day it last ran + what it changed
TIMEOUT_S = 40

# every path comes in through the environment (LE_LNK_JOBS / nothing interpolated into the command line)
_SCAN = r"""
$ErrorActionPreference = 'SilentlyContinue'
$sh = New-Object -ComObject WScript.Shell
$dirs = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('CommonDesktopDirectory'),
          [Environment]::GetFolderPath('Startup'), [Environment]::GetFolderPath('Programs'))
$out = @()
foreach ($d in $dirs) {
  if (-not $d -or -not (Test-Path -LiteralPath $d)) { continue }
  foreach ($f in Get-ChildItem -LiteralPath $d -Filter *.lnk -Recurse -Depth 2 -ErrorAction SilentlyContinue) {
    $s = $sh.CreateShortcut($f.FullName)
    if ($s.TargetPath -like '*.bat') { $out += @{ path = $f.FullName; target = $s.TargetPath } }
  }
}
ConvertTo-Json -InputObject @($out) -Compress
"""
_FIX = r"""
$ErrorActionPreference = 'Stop'
$sh = New-Object -ComObject WScript.Shell
$done = @()
foreach ($j in (ConvertFrom-Json $env:LE_LNK_JOBS)) {
  try { $s = $sh.CreateShortcut($j.path); $s.TargetPath = $j.new; $s.WorkingDirectory = $j.wd; $s.Save(); $done += $j.path } catch { }
}
ConvertTo-Json -InputObject @($done) -Compress
"""


def _ps() -> str:
    return ntpath.join(os.environ.get("SystemRoot") or r"C:\Windows", "System32", "WindowsPowerShell", "v1.0", "powershell.exe")


def _norm(p: str) -> str:
    return ntpath.normcase(ntpath.normpath(str(p or "")))


def _names(folder: str) -> dict:
    try:
        return {n.lower(): n for n in os.listdir(folder) if n.lower().endswith(".bat")}
    except Exception:  # noqa: BLE001
        return {}


def plan(links, root: str = ROOT, bat_names=None, root_names=None) -> list:
    """[{path, target, new, wd}] for the shortcuts that point at <root>\\X.bat where X.bat is gone from root and is in tools\\bat
    (names compared like Windows does: any case). bat_names / root_names: the .bat names there (tests pass them)."""
    bat = {n.lower(): n for n in (bat_names if bat_names is not None else _names(os.path.join(root, "tools", "bat")).values())}
    top = {n.lower() for n in (root_names if root_names is not None else _names(root).values())}
    out = []
    for ln in links or []:
        if not isinstance(ln, dict) or not str(ln.get("path") or ""):
            continue
        tgt = str(ln.get("target") or "")
        if not tgt.lower().endswith(".bat"):
            continue
        folder, name = ntpath.split(ntpath.normpath(tgt))
        if _norm(folder) != _norm(root) or name.lower() in top or name.lower() not in bat:
            continue
        out.append({"path": str(ln["path"]), "target": tgt, "new": ntpath.join(ntpath.normpath(root), "tools", "bat", bat[name.lower()]),
                    "wd": root})
    return out


def _run(script: str, env_extra: dict | None = None, runner=None) -> list:
    env = dict(os.environ, **(env_extra or {}))
    run = runner or subprocess.run
    r = run([_ps(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=TIMEOUT_S, env=env)
    txt = (getattr(r, "stdout", "") or "").strip()
    v = json.loads(txt) if txt else []
    return v if isinstance(v, list) else [v]


def scan(runner=None) -> list:
    try:
        return [x for x in _run(_SCAN, runner=runner) if isinstance(x, dict)]
    except Exception:  # noqa: BLE001
        return []


def fix(runner=None, root: str = ROOT, now=None, state_path: str = STATE, force: bool = False, is_windows=None) -> dict:
    """Once a day (force = now): point the shortcuts at the moved .bat files. {"fixed": [...], "why"}. Never raises."""
    try:
        if not (os.name == "nt" if is_windows is None else is_windows):
            return {"fixed": [], "why": "not Windows"}
        day = time.strftime("%Y-%m-%d", time.localtime(now or time.time()))
        try:
            st = json.load(open(state_path, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            st = {}
        if not force and st.get("day") == day:
            return {"fixed": [], "why": "done today"}
        jobs = plan(scan(runner=runner), root=root)
        done = _run(_FIX, {"LE_LNK_JOBS": json.dumps(jobs)}, runner=runner) if jobs else []
        try:
            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump({"day": day, "fixed": [ntpath.basename(str(p)) for p in done][:20]}, fh)
        except Exception:  # noqa: BLE001
            pass
        return {"fixed": done, "why": "ok"}
    except Exception as e:  # noqa: BLE001
        return {"fixed": [], "why": f"{e.__class__.__name__}"}


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if os.name != "nt":
        print("  [OK] Not Windows: nothing to check.")
        return 0
    if "--fix" in a:
        r = fix(force=True)
        print(f"  [OK] {len(r['fixed'])} shortcut(s) now point at tools\\bat." if r["why"] == "ok" else f"  [..] {r['why']}")
        return 0
    jobs = plan(scan())
    for j in jobs:
        print(f"  would point {j['path']} -> {j['new']}")
    print(f"  {len(jobs)} shortcut(s) point at a moved .bat" + (" (python -X utf8 tools/bat_shortcuts.py --fix)" if jobs else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
