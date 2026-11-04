"""Run only the static (no browser) part of a suite, for tests/run_gate.py --fast:

    python -X utf8 -m tests.gate_static tests.test_zenith_mode [function ...]

Imports the module and calls the named functions (default: the first of test_static / part_a / static that takes no argument), then prints
the module's own [PASS] / [FAIL] lines and "<module> static: n/m". Exit 0 only when every check passed. Nothing is launched.
"""
from __future__ import annotations

import importlib
import inspect
import sys

DEFAULTS = ("test_static", "part_a", "static", "part_intro_files")


def main(argv) -> int:
    if not argv:
        print("usage: python -m tests.gate_static <module> [function ...]")
        return 2
    mod = importlib.import_module(argv[0])
    names = argv[1:]
    if not names:
        for n in DEFAULTS[:3]:
            f = getattr(mod, n, None)
            if callable(f):
                req = [p for p in inspect.signature(f).parameters.values() if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
                if not req:
                    names = [n]
                    break
    if not names:
        print(f"{argv[0]}: no static part that runs without a browser or arguments")
        return 3
    for n in names:
        getattr(mod, n)()
    res = list(getattr(mod, "RES", []) or [])
    print(f"\n{argv[0]} static: {sum(res)}/{len(res)} " + ("ALL PASS" if res and all(res) else "FAILED"))
    return 0 if res and all(res) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
