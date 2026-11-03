"""QA pass 2026-11-03 (docs/QA_2026-11-03.md): the small robustness fixes that have no test of their own.

1. engine/autoupdate.Shell.run goes through heartbeat.run_cmd (no Windows pipe hang): a real git call, a missing program
   (127) and a timeout (124, the child killed) keep the old (code, output) contract.
2. engine/live.LiveBot._loop survives a failing wait computation (_sleep_s raising): the poll thread keeps polling.
Run: python -X utf8 -m tests.test_qa_1103
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""), flush=True)
    if not ok:
        FAILS.append(name)


def shell_part():
    from engine import autoupdate as au
    tmp = tempfile.mkdtemp(prefix="le_qa_shell_")
    try:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        sh = au.Shell(cwd=tmp)
        c, out = sh.git("rev-parse", "--is-inside-work-tree")
        check("1a. Shell.git: a real git call returns (0, its output)", c == 0 and out.strip() == "true", (c, out))
        c, out = sh.git("rev-parse", "HEAD")
        check("1b. a failing git call returns its code and stderr", c != 0 and out.strip() != "", (c, out))
        c, out = sh.run(["le-no-such-program-xyz"])
        check("1c. a program that does not exist -> 127", c == 127, (c, out))
        t0 = time.monotonic()
        c, out = sh.py(["-c", "import time; time.sleep(30)"], timeout=2)
        took = time.monotonic() - t0
        check("1d. a hung child -> 124 'timed out' within seconds (killed, not waited for)", c == 124 and "timed out" in out and took < 15,
              (c, out, round(took, 1)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def loop_part():
    from engine.live import LiveBot
    bot = LiveBot()
    n = {"polls": 0, "waits": 0}

    def poll():
        n["polls"] += 1
        if n["polls"] >= 3:
            bot.stop_flag.set()

    def bad_wait():
        n["waits"] += 1
        raise OSError("feed file vanished")

    bot.poll_once = poll
    bot._sleep_s = bad_wait
    bot.stop_flag.wait = lambda s=None: None       # no real sleeping (the fallback is 30 s)
    th = threading.Thread(target=bot._loop, args=(bot._gen,), daemon=True)
    th.start()
    th.join(10)
    check("2a. the poll loop keeps polling when the wait computation raises", n["polls"] == 3 and not th.is_alive(), n)
    check("2b. ... and records it as an error", "poll wait failed" in str(bot.health.get("last_error")), bot.health.get("last_error"))


def main() -> int:
    shell_part()
    loop_part()
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
