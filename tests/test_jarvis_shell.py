"""Jarvis worker coverage (bug hunt 2026-11-04): every Jarvis file the page loads - load('x', './x.js') parts, <script src>, <link href>,
and the static / dynamic imports of the Jarvis scripts - is in sw.js SHELL (so the offline copy is whole), every SHELL file exists on
disk, the worker version is newer than every entry of OLD, and OLD has no duplicates. Fast: no browser.
    python -X utf8 -m tests.test_jarvis_shell
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JV = os.path.join(ROOT, "tools", "web_public", "jarvis")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def strip(src):
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(re.sub(r"^\s*//.*$", "", ln) for ln in src.splitlines())


def needed():
    h = open(os.path.join(JV, "index.html"), encoding="utf-8").read()
    need = set(re.findall(r"load\('\w+', '(\./[\w.-]+)'", h))
    need |= set(re.findall(r"""<script[^>]*\bsrc=["']([^"']+)""", h))
    need |= set(re.findall(r"""<link[^>]+href=["']([^"']+\.(?:css|js|webmanifest))""", h))
    for f in sorted(os.listdir(JV)):
        if f.endswith(".js") and f != "sw.js":
            src = strip(open(os.path.join(JV, f), encoding="utf-8").read())
            for a, b in re.findall(r"""(?:^|\s)import\s[^'"\n]*?from\s*['"](\.[^'"]+)['"]|import\(['"](\.[^'"]+)['"]""", src, flags=re.M):
                need.add(a or b)
    need = {("./" + n) if re.match(r"^[\w-]+\.(?:js|css)", n) else n for n in need}      # a bare name in the page is the same folder
    return {n for n in need if not n.startswith("http")}


def main() -> int:
    sw = open(os.path.join(JV, "sw.js"), encoding="utf-8").read()
    shell = re.findall(r"'([^']+)'", re.search(r"const SHELL = \[([^\]]*)\]", sw).group(1))
    norm = lambda u: u[2:] if u.startswith("./") else u
    have = {norm(i) for i in shell}
    have_nq = {norm(i).split("?")[0] for i in shell}
    # a bare name in a page refers to the same folder; a leading ../ is the site
    miss = sorted(n for n in needed() if norm(n) not in have and not (("?" not in n) and norm(n) in have_nq) and norm(n).lstrip("./") not in have)
    check("every file index.html and the Jarvis scripts load or import is saved by the worker (SHELL)", not miss, miss)
    check("every SHELL file exists on disk", not [i for i in shell if i != "./" and not i.startswith("http") and not os.path.exists(os.path.normpath(os.path.join(JV, i.split("?")[0])))],
          [i for i in shell if i != "./" and not os.path.exists(os.path.normpath(os.path.join(JV, i.split("?")[0])))])
    cur = int(re.search(r"const CACHE = 'jarvis-v(\d+)'", sw).group(1))
    old = [int(x) for x in re.findall(r"'jarvis-v(\d+)'", re.search(r"const OLD = \[([^\]]*)\]", sw).group(1))]
    check("the worker version is newer than every entry of OLD, the previous one is kept, no duplicates", all(o < cur for o in old) and (cur - 1) in old and len(old) == len(set(old)), (cur, old))
    n = sum(RES)
    print(f"\njarvis shell: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
