"""Windows-safe file names (2026-11-20: two screenshots named 'hub_?h=bots-*.png' made every PC auto-update roll back for
16 hours: Windows refuses <>:"|?* in names). Lists every tracked path the owner's Windows PC cannot check out:
<>:"|?* or control characters, a trailing dot or space, a reserved name (CON, PRN, AUX, NUL, COM1-9, LPT1-9) or two
paths that differ only in case.  python tools/win_paths.py [REF]   (exit 1 = a bad path; tests/smoke.py and ship.py run it)"""
from __future__ import annotations

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BAD_CH = re.compile(r'[<>:"|?*\x00-\x1f]')
_RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$", re.I)


def bad_paths(paths) -> list:
    out, seen = [], {}
    for p in paths:
        for part in p.split("/"):
            if _BAD_CH.search(part) or part.endswith((".", " ")) or _RESERVED.match(part):
                out.append(p)
                break
        k = p.lower()
        if k in seen and seen[k] != p:
            out.append(f"{p} (same name as {seen[k]} on Windows)")
        seen.setdefault(k, p)
    return out


def tracked(ref: str | None = None) -> list:
    args = ["git", "ls-tree", "-r", "--name-only", "-z", ref] if ref else ["git", "ls-files", "-z"]
    raw = subprocess.run(args, cwd=ROOT, capture_output=True).stdout.decode("utf-8", "replace")
    return [p for p in raw.split("\0") if p]


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    bad = bad_paths(tracked(argv[0] if argv else None))
    for b in bad:
        print(f"  [FIX] Windows cannot check out: {b}")
    print(f"windows paths: {'all fine' if not bad else str(len(bad)) + ' bad (rename them, the PC update rolls back otherwise)'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
