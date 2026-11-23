"""Merge any night branch ON TOP of night-cleanup(-rt) (red team 2026-11-23). night-cleanup moved 42 .bat files into tools/bat;
a branch written before that still names them (and its menu rows still point) at the top folder. Run from the repo root right
after `git merge origin/<branch>` (it stops on conflicts or not, both fine):

    python research/handoff/2026-11-23/cleanup/merge_notify.py      then: git add -A && git commit --no-edit

Verified for night-notify-rt, night-payout-rt and night-zerotouch-rt (in that order or alone):
1. every text conflict keeps BOTH sides (menus 10-14 / M + T + P + k, docs, STATE.md, run_area lines; the alert_bus "Test:" line once);
2. in the files the merged branch changed, a moved .bat named at its old top-folder place gets tools/bat/ (menu rows like
   TRADE_HOME "k" then open the file that exists; tests/test_bat_menu b + d stay green);
3. a new top-folder .bat the branch adds on purpose (MONDAY_SETUP.bat: the owner's one weekly double-click) joins the kept list.
Prints every change; never touches tools/bat/, research/, history docs or test_bat_menu's own allow-list entries.
"""
import os
import re
import subprocess
import sys

ROOT = os.getcwd()
CONFLICT = re.compile(r"<<<<<<< [^\n]*\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n", re.S)
# the conflicts where BOTH sides are right (checked by hand 2026-11-23): docs, STATE.md, run_area lines, the TRADE_HOME menu /
# do_choice branches, the alert_bus docstring. Any other conflicted file = code: the script stops and names it.
SAFE_BOTH = {"STATE.md", "tests/run_area.py", "engine/trade_home.py", "engine/alert_bus.py"}
KEEP_NEW = {"MONDAY_SETUP.bat"}                      # new top-folder .bat files that stay there (the owner double-clicks them)
SKIP = ("tools/bat/", "research/", "docs/handoff", "tools/web_public/pc/", "docs/BAT_FILES.md", "tests/test_bat_menu.py",
        "tests/test_bat_shortcuts.py")


def git(*a) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout


def keep_both(path, ours, theirs):
    if path == "engine/alert_bus.py" and theirs.startswith("Test:"):
        theirs = theirs.split("\n", 1)[1] if "\n" in theirs else ""
    return ours + theirs


def main() -> int:
    if not os.path.isdir(os.path.join(ROOT, "tools", "bat")):
        print("run it from the repo root of the merge (tools/bat/ must exist)")
        return 1
    for p in [x for x in git("diff", "--name-only", "--diff-filter=U").split("\n") if x]:
        if p not in SAFE_BOTH and not (p.startswith("docs/") and p.endswith(".md")):
            print(f"[FIX] {p}: a code conflict: resolve by hand (never both sides of code), then run this again")
            return 1
        f = os.path.join(ROOT, p)
        try:
            s = open(f, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            print(f"[FIX] {p}: not a text conflict; resolve by hand")
            return 1
        n = len(CONFLICT.findall(s))
        s = CONFLICT.sub(lambda m: keep_both(p, m.group(1), m.group(2)), s)
        if "<<<<<<<" in s or ">>>>>>>" in s:
            print(f"[FIX] {p}: a conflict this script does not know; resolve by hand")
            return 1
        open(f, "w", encoding="utf-8", newline="").write(s)
        print(f"{p}: {n} conflict(s) -> both sides kept")
    top = {n for n in os.listdir(ROOT) if n.lower().endswith(".bat")}
    moved = sorted(n[:-4] for n in os.listdir(os.path.join(ROOT, "tools", "bat")) if n.lower().endswith(".bat") and n not in top)
    rx = re.compile(r"(?<![A-Za-z0-9_./\\-])(" + "|".join(map(re.escape, moved)) + r")\.bat(?![A-Za-z0-9_])")
    allow = {}
    try:                                              # test_bat_menu's own allow-list: names a file keeps on purpose
        sys.path.insert(0, ROOT)
        from tests import test_bat_menu as _tbm
        allow = {k: set(v) for k, v in getattr(_tbm, "ALLOW", {}).items()}
    except Exception:
        pass
    mh = git("rev-parse", "-q", "--verify", "MERGE_HEAD").strip()
    if mh:
        base = git("merge-base", "HEAD", mh).strip()
        changed = [x for x in git("diff", "--name-only", base, mh).split("\n") if x]
    else:                                             # already committed: the merge commit's second parent
        changed = [x for x in git("diff", "--name-only", "HEAD^1...HEAD^2").split("\n") if x]
    for p in changed:
        f = os.path.join(ROOT, p)
        if p.startswith(SKIP) or not os.path.isfile(f) or p.lower().endswith(".bat"):
            continue
        try:
            s = open(f, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        keep = allow.get(p, set())
        new = rx.sub(lambda m: m.group(0) if m.group(1) in keep else f"tools/bat/{m.group(1)}.bat", s)
        if new != s:
            open(f, "w", encoding="utf-8", newline="").write(new)
            print(f"{p}: {len(rx.findall(s))} old-place name(s) -> tools/bat/")
    t = os.path.join(ROOT, "tests", "test_bat_menu.py")
    add = sorted(n for n in KEEP_NEW if n in top)
    if add and os.path.exists(t):
        s = open(t, encoding="utf-8").read()
        m = re.search(r"KEEP = \{([^}]*)\}", s)
        if m and any(f'"{n}"' not in m.group(1) for n in add):
            extra = "".join(f', "{n}"' for n in add if f'"{n}"' not in m.group(1))
            s = s[:m.end(1)] + extra + s[m.end(1):]
            open(t, "w", encoding="utf-8", newline="").write(s)
            print(f"tests/test_bat_menu.py: kept at the top folder too: {', '.join(add)}")
        s = open(t, encoding="utf-8").read()
        m = re.search(r"NO_NUMBER = \{([^}]*)\}", s)
        if m and any(f'"{n}"' not in m.group(1) for n in add):
            s = s[:m.end(1)] + "".join(f', "{n}"' for n in add if f'"{n}"' not in m.group(1)) + s[m.end(1):]
            open(t, "w", encoding="utf-8", newline="").write(s)
            print(f"tests/test_bat_menu.py: no menu number needed for: {', '.join(add)} (a front door like TRADE_HOME)")
    doc = os.path.join(ROOT, "docs", "BAT_FILES.md")
    if "MONDAY_SETUP.bat" in add and os.path.exists(doc):
        s = open(doc, encoding="utf-8").read()
        if "`MONDAY_SETUP.bat`" not in s:
            row = ("| `MONDAY_SETUP.bat` | the ONE weekly double-click (update, clock, START with your phrase, alert test); it runs "
                   "from a TEMP copy like UPDATE.bat | - |\n")
            i = s.find("| `SETUP_EVERYTHING.bat`")
            s = s[:i] + row + s[i:] if i >= 0 else s + "\n" + row
            open(doc, "w", encoding="utf-8", newline="").write(s)
            print("docs/BAT_FILES.md: MONDAY_SETUP.bat row added")
    return 0


if __name__ == "__main__":
    sys.exit(main())
