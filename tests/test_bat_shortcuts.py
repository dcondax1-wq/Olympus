"""tools/bat_shortcuts (red team 2026-11-23): a shortcut to a .bat that moved to tools\\bat follows it; nothing else is touched.
Offline: fake shortcut lists and a fake PowerShell; no real .lnk is read or written.

    python -X utf8 -m tests.test_bat_shortcuts
"""
from __future__ import annotations

import json
import ntpath
import os
import sys
import tempfile
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import bat_shortcuts as BS  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{str(info)[:300]}]"))


def main() -> int:
    root = r"C:\Users\Owner Name\olympus"
    links = [{"path": r"C:\Users\Owner Name\Desktop\Bots back.lnk", "target": root + r"\BOTS_BACK.bat"},
             {"path": r"C:\Users\Owner Name\Desktop\kalshi.lnk", "target": root.upper() + r"\kalshi_live.BAT"},
             {"path": r"C:\Users\Owner Name\Desktop\start.lnk", "target": root + r"\START_BOT.bat"},
             {"path": r"C:\Users\Owner Name\Desktop\other.lnk", "target": r"C:\Other\BOTS_BACK.bat"},
             {"path": r"C:\Users\Owner Name\Desktop\gone.lnk", "target": root + r"\NEVER_EXISTED.bat"},
             {"path": r"C:\Users\Owner Name\Desktop\nt.lnk", "target": r"C:\Program Files\NinjaTrader 8\bin\NinjaTrader.exe"},
             "garbage", None, {"path": "", "target": root + r"\BOTS_BACK.bat"}]
    j = BS.plan(links, root=root, bat_names=["BOTS_BACK.bat", "KALSHI_LIVE.bat"], root_names=["START_BOT.bat", "TRADE_HOME.bat"])
    names = sorted(ntpath.basename(x["path"]) for x in j)
    check("a. only shortcuts to a .bat that left the bot folder for tools\\bat are changed (spaces, case)",
          names == ["Bots back.lnk", "kalshi.lnk"], names)
    check("b. a .bat still at the root, another folder, a missing .bat, NinjaTrader, garbage: untouched",
          not any(ntpath.basename(x["path"]) in ("start.lnk", "other.lnk", "gone.lnk", "nt.lnk") for x in j), j)
    check("c. the new target is tools\\bat\\<name>, working folder = the bot folder",
          all(x["new"].lower() == (root + "\\tools\\bat\\" + x["target"].split("\\")[-1]).lower() and x["wd"] == root for x in j), j)
    calls = []

    def runner(cmd, **k):
        calls.append((cmd, k.get("env", {}).get("LE_LNK_JOBS"), k.get("timeout")))
        if "LE_LNK_JOBS" in k.get("env", {}) and "ConvertFrom-Json" in cmd[-1]:
            return SimpleNamespace(stdout=json.dumps([x["path"] for x in json.loads(k["env"]["LE_LNK_JOBS"])]))
        return SimpleNamespace(stdout=json.dumps([{"path": os.path.join(tempfile.gettempdir(), "x.lnk"),
                                                   "target": os.path.join(BS.ROOT, "BOTS_BACK.bat")}]))
    sp = os.path.join(tempfile.mkdtemp(), "st.json")
    r = BS.fix(runner=runner, state_path=sp, is_windows=True)
    moved_here = os.path.exists(os.path.join(BS.BAT_DIR, "BOTS_BACK.bat")) and not os.path.exists(os.path.join(BS.ROOT, "BOTS_BACK.bat"))
    check("d. fix(): PowerShell by its full System32 path, with a time limit; the paths go in through the environment, not the command",
          calls and calls[0][0][0].lower().endswith(r"system32\windowspowershell\v1.0\powershell.exe") and calls[0][2]
          and all(BS.ROOT not in c[0][-1] for c in calls), calls[:1])
    check("e. fix() changes the one moved shortcut", (len(r["fixed"]) == 1) == moved_here, r)
    r2 = BS.fix(runner=runner, state_path=sp, is_windows=True)
    check("f. once a day", r2["why"] == "done today", r2)
    check("g. not Windows: nothing", BS.fix(runner=runner, state_path=sp + "2", is_windows=False)["why"] == "not Windows")
    check("h. a broken PowerShell never raises", BS.fix(runner=lambda *a, **k: (_ for _ in ()).throw(OSError("x")), state_path=sp + "3",
                                                         is_windows=True)["fixed"] == [])
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
