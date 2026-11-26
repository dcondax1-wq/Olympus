"""TRADE_HOME.bat = the ONE front door (night-cleanup 2026-11-22): the root keeps 12 .bat files, the rest live in tools/bat/.

    python -X utf8 -m tests.test_bat_menu        # ~3 s, Linux, no .bat is run

a. the top folder holds exactly the 13 kept .bat files (docs/BAT_FILES.md says why each one stays)
b. every menu number (main, 5 alerts, 8 routine, M more tools) opens a file that exists; every .bat (top + tools/bat) is reachable
c. every moved .bat starts with the LE_HOME header and uses %~dp0 nowhere else (it works from tools\\bat\\ and as a loose copy)
d. no tracked file names a moved .bat by its old top-folder path (history folders and the moved files' own sibling notes aside)
e. docs/BAT_FILES.md lists every moved file; the Startup / desktop shortcuts still point at files that exist at the top
f. the menu runs a tools/bat file with this OS's separators and the M list through do_choice (fakes)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
RESULTS = []

KEEP = {"TRADE_HOME.bat", "START_BOT.bat", "STOP_BOT.bat", "UPDATE.bat", "FIX_CLOCK.bat", "KEEPALIVE_ON.bat", "ADD_ACCOUNT.bat",
        "ALERTS_SETUP.bat", "HEALTH_CHECK.bat", "START_DASHBOARD.bat", "SETUP_EVERYTHING.bat", "UPDATE_FROM_ZIP.bat",
        "MONDAY_SETUP.bat"}   # integration 2026-11-23: night-zerotouch's ONE weekly double-click stays on top (13 files)
# reached without a menu number of their own: TRADE_HOME is the menu; 4 does ADD_ACCOUNT's steps in-process; FIX_CLOCK needs a
# right-click > Run as administrator (9 syncs without it)
NO_NUMBER = {"TRADE_HOME.bat", "ADD_ACCOUNT.bat", "FIX_CLOCK.bat", "MONDAY_SETUP.bat"}   # MONDAY_SETUP = routine 8's weekly twin, its own double-click
HEADER = ('set "LE_HOME=%~dp0"\r\nif not exist "%~dp0engine\\" if exist "%~dp0..\\..\\engine\\" '
          'for %%I in ("%~dp0..\\..") do set "LE_HOME=%%~fI\\"\r\n')
# deliberate bare names: the phone site's own download copies (tools/web_public/pc/X.bat), the BOT_MOVE folder's loose copy,
# and tests that compare a file's basename
ALLOW = {"scripts/move_bot.ps1": {"MOVE_BOT"}, "tests/test_pc_care.py": {"PC_CARE", "CLEAN_STORAGE", "UNDO_PC_TUNE", "STATUS"},
         "tests/test_clean_storage.py": {"CLEAN_STORAGE"}, "tests/test_zenith_pages.py": {"FRESH_START"},
         "tests/test_trading_home.py": {"TEST_ALERT"}, "tools/web_public/settings/index.html": {"FRESH_START"},
         "tools/build_web_dashboard.py": {"RUN_MONEY"},
         "tests/test_bat_shortcuts.py": {"BOTS_BACK", "KALSHI_LIVE"},
         "tools/web_public/cities/brain-data.json": {"GITHUB_SIGNIN"},
         "tools/web_public/research/hub.json": {"GITHUB_SIGNIN"}, "tools/web_public/clio/hub.json": {"GITHUB_SIGNIN"}}   # the Research Hub quotes old LEDGER/handoff lines (history)   # integration: a generated copy of LEDGER.md history (research/ is HISTORY)   # its fake shortcuts point at the OLD place on purpose   # a print line only; helpers never edit the builder (the lead may)
LOOSE = {"MOVE_BOT.bat": {"move_bot.ps1"}}          # the BOT_MOVE folder copy runs the script next to it
HISTORY = ("research/", "docs/handoff", "docs/STATE_HISTORY.md", "tools/bat/", "tools/web_public/pc/", "docs/BAT_FILES.md")


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"   -> {info!r}"[:600]))


def moved():
    return sorted(f for f in os.listdir(os.path.join(ROOT, "tools", "bat")) if f.endswith(".bat"))


def menu_files():
    from engine import trade_home as th
    out = {}
    for k, (_t, b, _r) in th.ACTIONS.items():
        out[f"menu {k}"] = b
    for n, _t, f in th.MORE_TOOLS:
        out[f"M {n}"] = f
    return out


def part_a():
    top = sorted(f for f in os.listdir(ROOT) if f.lower().endswith(".bat"))
    check("a. the top folder holds exactly the 13 kept .bat files", set(top) == KEEP, sorted(set(top) ^ KEEP))
    check("a. 42 files live in tools/bat/", len(moved()) == 42, len(moved()))


def part_b():
    from engine import trade_home as th
    mf = menu_files()
    miss = {k: f for k, f in mf.items() if not os.path.isfile(th.bat_path(f))}
    check("b. every menu number opens a file that exists", not miss, miss)
    src = open(os.path.join(ROOT, "engine", "trade_home.py"), encoding="utf-8").read()
    named = set(re.findall(r'run_bat\("([^"]+\.bat)"', src)) | set(re.findall(r'\("[^"]+", "([^"]+\.bat)"\)', src))
    miss2 = [f for f in named if not os.path.isfile(th.bat_path(f))]
    check("b. every .bat the alerts step and the routine run exists", named and not miss2, (sorted(named), miss2))
    reach = {os.path.basename(f) for f in list(mf.values()) + list(named)}
    every = KEEP | set(moved())
    check("b. every .bat (top + tools/bat) is a number in the menu (TRADE_HOME / ADD_ACCOUNT / FIX_CLOCK aside)",
          not (every - reach - NO_NUMBER), sorted(every - reach - NO_NUMBER))
    nums = [n for n, _t, _f in th.MORE_TOOLS]
    check("b. More tools numbers are 1..N, unique", nums == [str(i) for i in range(1, len(nums) + 1)], nums)
    check("b. the main menu text shows every ACTIONS number and M", all(any(ln.strip().startswith(k + " ") for ln in th.MENU)
                                                                    for k in list(th.ACTIONS) + ["M"]), th.MENU)


def part_c():
    bad = []
    for f in moved():
        raw = open(os.path.join(ROOT, "tools", "bat", f), "rb").read()
        try:
            t = raw.decode("ascii")
        except UnicodeDecodeError:
            bad.append(f"{f}: not ASCII")
            continue
        if b"\n" in raw.replace(b"\r\n", b""):
            bad.append(f"{f}: not CRLF")
        first, rest = t.split("\r\n", 1)
        if not first.lower().startswith("@echo off") or not rest.startswith(HEADER):
            bad.append(f"{f}: no LE_HOME header after @echo off")
        elif "%~dp0" in rest[len(HEADER):]:
            bad.append(f"{f}: %~dp0 used after the header (it is tools\\bat\\ there, not the bot folder)")
        for m in re.finditer(r"%LE_HOME%([A-Za-z0-9_\\.\-]+\.(?:bat|ps1|py))", t):
            if m.group(1) not in LOOSE.get(f, ()) and not os.path.exists(os.path.join(ROOT, *m.group(1).split("\\"))):
                bad.append(f"{f}: {m.group(1)} missing")
    check("c. every moved .bat: ASCII, CRLF, the LE_HOME header, no %~dp0 after it, every %LE_HOME% file exists", not bad, bad)


def part_d():
    names = "|".join(re.escape(m[:-4]) for m in moved())
    rx = re.compile(r"(?<![A-Za-z0-9_./\\-])(" + names + r")\.bat(?![A-Za-z0-9_])")
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
    hits = []
    for f in files:
        if not f or f.startswith(HISTORY) or "CHANGELOG" in f or f == "tests/test_bat_menu.py":
            continue
        p = os.path.join(ROOT, f)
        try:
            t = open(p, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        if ".bat" not in t:
            continue
        for i, ln in enumerate(t.splitlines(), 1):
            for m in rx.finditer(ln):
                if m.group(1) in ALLOW.get(f, ()):
                    continue
                hits.append(f"{f}:{i}: {m.group(0)}")
    check("d. no file names a moved .bat by its old top-folder path", not hits, hits[:25])


def part_e():
    doc = open(os.path.join(ROOT, "docs", "BAT_FILES.md"), encoding="utf-8").read()
    miss = [m for m in moved() if f"`tools\\bat\\{m}`" not in doc]
    check("e. docs/BAT_FILES.md: every moved file with its new place", not miss, miss)
    check("e. docs/BAT_FILES.md: every kept file with its reason", all(f"`{k}`" in doc for k in KEEP))
    sc = open(os.path.join(ROOT, "scripts", "make_shortcuts.ps1"), encoding="utf-8").read()
    files = re.findall(r"File = '([^']+\.bat)'", sc)
    check("e. desktop icons (make_shortcuts.ps1) point at top-folder files that exist", files and all(os.path.isfile(os.path.join(ROOT, f)) for f in files), files)
    go = open(os.path.join(ROOT, "engine", "go.py"), encoding="utf-8").read()
    su = re.findall(r"os\.path\.join\(ROOT, '([A-Z_]+\.bat)'\)", go)
    check("e. the Startup shortcut (engine/go.py 'LE bot server.lnk') points at a top-folder file that exists",
          su and all(os.path.isfile(os.path.join(ROOT, f)) for f in su), su)


def part_f():
    from engine import trade_home as th
    ran = []
    fake = lambda argv: ran.append(argv) or 0      # noqa: E731
    p = th.bat_path("tools/bat/PC_CARE.bat")
    check("f. bat_path uses this OS's separators", p == os.path.join(ROOT, "tools", "bat", "PC_CARE.bat"), p)
    ans = iter(["2"])
    out = []
    r = th.do_choice("m", ask=lambda _q: next(ans), out=out.append, run=fake, fx={})
    check("f. M -> 2 runs tools/bat/PC_DOCTOR.bat and says one result line", ran and ran[-1][-1] == th.bat_path("tools/bat/PC_DOCTOR.bat")
          and r.startswith("[OK]"), (ran, r))
    ran.clear()
    r = th.do_choice("10", ask=lambda _q: "", out=out.append, run=fake, fx={})
    check("f. 10 runs HEALTH_CHECK.bat", ran and ran[-1][-1] == th.bat_path("HEALTH_CHECK.bat") and r.startswith("[OK]"), (ran, r))
    ran.clear()
    r = th.do_choice("m", ask=lambda _q: "99", out=out.append, run=fake, fx={})
    check("f. M with a wrong number runs nothing", not ran and r.startswith("[FIX]"), (ran, r))
    src = open(os.path.join(ROOT, "engine", "trade_home.py"), encoding="utf-8").read()
    check("f. the menu never holds a live phrase as a value (only the words telling the owner to type it)",
          not re.search(r"[\"']I ACCEPT LIVE RISK[\"']|[\"']KEEP ALIVE ON[\"']", src))


def main():
    for p in (part_a, part_b, part_c, part_d, part_e, part_f):
        try:
            p()
        except Exception as e:  # noqa: BLE001
            check(f"{p.__name__} ran", False, f"{e.__class__.__name__}: {e}")
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
