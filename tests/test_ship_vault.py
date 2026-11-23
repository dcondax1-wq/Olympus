"""tools/ship.py vault_sync (night-reds2 2026-11-23): a stale generated vault/ is rebuilt and committed before the push; an
up-to-date one is left alone; a failing build never blocks the ship. Fakes only (no git, no push).

    python -X utf8 -m tests.test_ship_vault
"""
import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import ship as S  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"))


def fake(check_rc, build_rc=0, dirty=" M vault/x.md"):
    calls = []

    def run(cmd, cwd=None, capture_output=True, text=True):
        calls.append(cmd)
        if "obsidian_brain.py" in " ".join(cmd):
            rc = check_rc if "--check" in cmd else build_rc
            return SimpleNamespace(returncode=rc, stdout="", stderr="")
        if cmd[:2] == ["git", "status"]:
            return SimpleNamespace(returncode=0, stdout=dirty, stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return run, calls


def main():
    real = S.subprocess.run
    try:
        S.subprocess.run, calls = fake(0)
        check("up to date: nothing rebuilt, nothing committed", S.vault_sync() is False and not any("commit" in c for c in calls), calls)
        S.subprocess.run, calls = fake(1)
        r = S.vault_sync()
        gits = [c for c in calls if c[0] == "git"]
        check("stale: rebuilt, then git add vault + one commit", r is True and any(c[:2] == ["git", "add"] and "vault" in c for c in gits)
              and sum(1 for c in gits if c[:2] == ["git", "commit"]) == 1, calls)
        S.subprocess.run, calls = fake(1, build_rc=1)
        check("the build fails: no commit, never raises (the ship goes on; the test reports it)", S.vault_sync() is False
              and not any("commit" in c for c in calls), calls)
        S.subprocess.run, calls = fake(1, dirty="")
        check("stale check but the build changes nothing: no empty commit", S.vault_sync() is False and not any("commit" in c for c in calls))
    finally:
        S.subprocess.run = real
    src = open(os.path.join(ROOT, "tools", "ship.py"), encoding="utf-8").read().split("def main", 1)[1]
    check("main(): vault_sync runs after the clean-tree check and before the smoke check / push",
          src.index("dirty") < src.index("vault_sync()") < src.index("tests/smoke.py") < src.index("push(rem"))
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
