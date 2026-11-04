"""The Jarvis hub test (tests/test_jarvis_hub.py) one part at a time, for tests/run_gate.py (the whole file takes tens of minutes on a loaded machine;
a part that times out must not hide the others). It only calls the hub test's own functions: nothing is copied or changed there.

    python -X utf8 -m tests.hub_parts static|a|b|missing|c|look|switcher|olympus|system|intro [...]     (several parts share one browser)
    python -X utf8 -m tests.hub_parts --list

static   part_a + part_intro_files (no browser)       a / b   the page with no separate part / with stand-ins     missing   each separate part missing
c        the full Jarvis screen                         look / switcher / olympus / system / intro   the Look sheet, the switcher, the OLYMPUS layer, the System view, the intro
Prints the hub test's own [PASS] / [FAIL] lines and "jarvis hub <parts>: n/m".
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import test_jarvis_hub as H  # noqa: E402

PARTS = ["static", "a", "b", "missing", "c", "look", "switcher", "olympus", "system", "intro"]
NEEDS = {"a": "A", "b": "B", "c": "C", "look": "C", "switcher": "C", "olympus": "C", "system": "C", "intro": "C"}


def main(argv) -> int:
    if not argv or argv[0] == "--list":
        print(" ".join(PARTS))
        return 0
    want = [p for p in argv if p in PARTS]
    if not want or len(want) != len(argv):
        print("unknown part: " + " ".join(p for p in argv if p not in PARTS))
        return 2
    if "static" in want:
        H.part_a()
        H.part_intro_files()
    browser = [p for p in want if p != "static"]
    if browser:
        tmp = tempfile.mkdtemp(prefix="le_hubpart_")
        variants = {}
        try:
            need = {NEEDS[p] for p in browser if p in NEEDS}
            if "A" in need:
                variants["A"] = H.site(tmp, "A", "none")
            if "B" in need:
                variants["B"] = H.site(tmp, "B", "stub")
            if "C" in need:
                variants["C"] = H.site(tmp, "C", "asis")
            if "missing" in browser:
                for f in H.PARTS:
                    variants["D" + f] = H.site(tmp, "D" + f.split(".")[0], "stub-but:" + f)
            srv = H.serve(tmp)
            host = f"http://127.0.0.1:{srv.server_address[1]}/"
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as pw:
                    br = H.launch(pw)
                    for p in browser:
                        if p == "a":
                            H.run_a(br, host + variants["A"])
                        elif p == "b":
                            H.run_b(br, host + variants["B"])
                        elif p == "missing":
                            for f in H.PARTS:
                                H.run_missing(br, host + variants["D" + f], f)
                        else:
                            getattr(H, "run_" + p)(br, host + variants["C"])
                    br.close()
            finally:
                srv.shutdown()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    n = sum(H.RES)
    print(f"\njarvis hub {' '.join(want)}: {n}/{len(H.RES)} " + ("ALL PASS" if H.RES and n == len(H.RES) else "FAILED"))
    return 0 if H.RES and n == len(H.RES) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
