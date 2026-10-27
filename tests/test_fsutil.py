"""engine/fsutil.replace: the Windows-safe state-file replace (2026-10-27 "state save failed: [WinError 5] Access is
denied" on the PC).    python -X utf8 -m tests.test_fsutil   (~1 s, temp files only)"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import fsutil  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {info}"), flush=True)


def main():
    d = tempfile.mkdtemp(prefix="le_fsutil_")
    src, dst = os.path.join(d, "a.tmp"), os.path.join(d, "a.json")
    open(src, "w").write("new")
    open(dst, "w").write("old")
    n = {"k": 0}

    def flaky(a, b):                      # the target is held open for the first 3 tries
        n["k"] += 1
        if n["k"] <= 3:
            raise PermissionError(5, "Access is denied")
        os.replace(a, b)
    slept = []
    r = fsutil.replace(src, dst, sleep=slept.append, _replace=flaky)
    check("held open 3 times -> replaced on the 4th try", r == 3 and open(dst).read() == "new" and len(slept) == 3, (r, slept))
    open(src, "w").write("x")
    try:
        fsutil.replace(src, dst, sleep=lambda s: None, _replace=lambda a, b: (_ for _ in ()).throw(PermissionError(5, "denied")))
        check("held open for good -> raises (the caller's error handling unchanged)", False)
    except PermissionError:
        check("held open for good -> raises (the caller's error handling unchanged)", True)
    check(f"total wait before giving up ~{sum(fsutil.WAITS):.2f} s (under 2 s: a poll is not held up)", sum(fsutil.WAITS) < 2.0)
    open(src, "w").write("y")
    check("normal case: one try", fsutil.replace(src, dst) == 0 and open(dst).read() == "y")
    n_ = sum(RES)
    print(f"fsutil: {n_}/{len(RES)} {'ALL PASS' if n_ == len(RES) else 'FAILED'}")
    return 0 if n_ == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
