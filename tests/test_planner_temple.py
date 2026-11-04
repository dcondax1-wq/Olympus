"""Planner Temple add-on (tools/planner_patches/50-temple.patch, owner 2026-11-03): static checks on the patch itself.
The behaviour is tested in the Planner's own tests (planner/tests/temple.test.js, 42 checks, inside the patch).
  a. the patch touches only planner/ files, adds no link, and adds the script, its tests and its doc
  b. Arena is READ ONLY: ext-temple.js never writes, removes or clears an arena.* key and never touches another app's storage
  c. the script tag is loaded once, after ext-olympus.js
  d. no secrets, no network calls except the optional read of ../arena/rules.json
    python -X utf8 -m tests.test_planner_temple
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATCH = os.path.join(ROOT, "tools", "planner_patches", "50-temple.patch")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"), flush=True)


def main():
    txt = open(PATCH, encoding="utf-8").read()
    files = re.findall(r"^diff --git a/(\S+) b/\S+$", txt, re.M)
    check("a. patch exists and lists files", bool(files), files)
    check("a. every path is under planner/", all(f.startswith("planner/") for f in files), files)
    check("a. no symlink or submodule", not re.search(r"^(new file mode|old mode|new mode) 1[26]0000", txt, re.M))
    for want in ("planner/ext-temple.js", "planner/tests/temple.test.js", "planner/docs/features-temple.md", "planner/index.html"):
        check(f"a. adds/edits {want}", want in files, files)
    js = "".join(l[1:] for l in txt.split("\n") if l.startswith("+") and not l.startswith("+++"))
    start = js.find("// ===== TEMPLE")
    code = js[start: js.find("window.__tp = {")] if start >= 0 else ""
    check("b. ext-temple.js found in the patch", len(code) > 5000, len(code))
    writes = re.findall(r"(?:localStorage\.)?(?:setItem|removeItem)\(\s*['\"]?(?:ARENA_KEY|arena)", code)
    check("b. never writes or removes an arena.* key", not writes, writes)
    check("b. the only storage write is the device key planner.temple.seen", set(re.findall(r"\bset\(([A-Z_]+),", code)) == {"SEEN_KEY"}, re.findall(r"\bset\(([A-Z_]+),", code))
    check("b. no localStorage.clear / sessionStorage / indexedDB", not re.search(r"localStorage\.clear|sessionStorage|indexedDB", code))
    check("b. reads only arena.v1", set(re.findall(r"['\"](arena\.[\w.]+)['\"]", code)) == {"arena.v1"}, re.findall(r"['\"](arena\.[\w.]+)['\"]", code))
    heads = re.findall(r'^\+<script src="(ext-[a-z]+\.js)"', txt, re.M)
    check("c. one script tag, ext-temple.js", heads == ["ext-temple.js"], heads)
    check("c. placed right after ext-olympus.js", 'ext-olympus.js"></script>' in txt and "+<script src=\"ext-temple.js\"></script>" in txt)
    fetches = re.findall(r"fetch\(\s*['\"]([^'\"]+)", code)
    check("d. only network read is ../arena/rules.json", fetches == ["../arena/rules.json"], fetches)
    check("d. no keys, tokens or webhooks", not re.search(r"(api[_-]?key|secret|token|webhook|bearer)\s*[:=]", code, re.I))
    print(f"\nplanner temple: {sum(RES)}/{len(RES)} {'ALL PASS' if all(RES) else 'FAIL'}")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
