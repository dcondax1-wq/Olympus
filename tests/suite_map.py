"""Which test suites a change can break (day-quality round 2, 2026-11-20: make a landing faster). Used by tests/run_area.py --changed.

    python -X utf8 tests/suite_map.py <base_sha> [area]     print the plan: suites to run, suites skipped and why

How a suite is mapped to files (read from its own source, no import, no run):
  * the repo modules it imports (engine.x, tools.y, tests.helper ...) and everything THOSE import, all the way down;
  * every path-like string literal it (or a module it imports) holds ("engine/lit.py", "tools/web_public/athena/", 'research/runs') and every
    os.path.join(ROOT, "tools", "web_public", "x") / Path chain of string parts, joined;
  * bare app folder names next to web_public ("athena/", WP / "athena") through the strings above;
  * the tests/*.mjs / *.cjs / *.js harness files it names (their own string paths too).
A changed file selects a suite when the suite reads that file, its folder, or a parent folder the suite names.
SAFE FALLBACK (the whole area runs): a changed file that NO suite of the area maps to and that is not plain prose (docs, research
write-ups, *.md), or any file on the SHARED list (the test kits, the runner, requirements, the shared OLYMPUS kit). A changed suite
file always runs itself. Browser suites are the ones whose source (or a kit / harness it uses) opens Playwright / Chromium.
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
WP = "tools/web_public"
# a change here can break any suite: run the whole area
SHARED = ("tests/__init__.py", "tests/browser_kit.py", "tests/net_stub.py", "tests/net_stub.cjs", "tests/run_area.py", "tests/suite_map.py",
          "tests/agora_kit.py", "tests/hub_parts.py", "requirements.txt", "tools/web_public/olympus/", "web_next/js/next/", "conftest.py")
# prose: never a reason to run anything
PROSE = re.compile(r"(\.md$|^docs/|^research/(writeups|handoff|study|design|lab/chart_examples)/|^scratch/|^\.claude/|\.png$|\.jpg$|\.webp$|\.mp4$)")
BROWSER_RX = re.compile(r"sync_playwright|async_playwright|from playwright|import playwright|require\(['\"]playwright|from ['\"]playwright|"
                        r"chromium\.launch|browser_kit|agora_kit|hub_parts|olympus_money_kit")
# a folder this broad says nothing about what the suite reads (os.path.join(ROOT, "tools") ...): never a match by itself
TOO_BROAD = {"engine", "tools", "tests", "web_next", "data", "research", "scripts", "docs", "cache", "accounts", "agency", "jarvis",
             "handoff", "tools/web_public", "web_next/js", "web_next/js/next", "research/runs", "research/writeups", "data/news"}
PATHISH = re.compile(r"^(?:\./|\.\./)?[A-Za-z0-9_@.+-]+(?:/[A-Za-z0-9_@.+ -]*)+$|^[A-Za-z0-9_-]+\.(?:py|js|mjs|cjs|json|html|css|csv|ps1|bat)$")
TOP = ("engine", "tools", "tests", "web_next", "data", "research", "scripts", "docs", "cache", "accounts", "agency", "jarvis", "handoff")


def _read(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def _mod_file(mod: str):
    """engine.lit -> engine/lit.py (or the package's __init__), only repo modules"""
    parts = mod.split(".")
    if parts[0] not in ("engine", "tools", "tests", "agency"):
        return None
    for cand in ("/".join(parts) + ".py", "/".join(parts) + "/__init__.py", "/".join(parts) + "/"):
        if os.path.exists(os.path.join(ROOT, cand)):
            return cand
    if len(parts) > 1:                                   # from tools import disk_clean -> tools/disk_clean.py
        return _mod_file(".".join(parts[:-1]))
    return None


_PARSED: dict = {}


def _strings_and_imports(src: str):
    key = hash(src)
    if key not in _PARSED:
        _PARSED[key] = _parse(src)
    return _PARSED[key]


def _parse(src: str):
    strings, mods = [], []
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(src)
    except SyntaxError:
        return re.findall(r"""["']([^"'\n]{2,200})["']""", src), mods
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            mods.append(node.module)
            mods += [f"{node.module}.{a.name}" for a in node.names]
        elif isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""
            if name in ("join", "Path", "joinpath"):
                parts = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
                if parts:
                    strings.append("/".join(p.strip("/") for p in parts))
            for a in node.args:                          # importlib.import_module("tests.x"), run([... "-m", "engine.y"])
                if isinstance(a, ast.Constant) and isinstance(a.value, str) and re.fullmatch(r"(engine|tools|tests)(\.\w+)+", a.value):
                    mods.append(a.value)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):   # WP / "athena" / "index.html"
            chain, n = [], node
            while isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
                if isinstance(n.right, ast.Constant) and isinstance(n.right.value, str):
                    chain.insert(0, n.right.value)
                n = n.left
            if chain:
                strings.append("/".join(chain))
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) < 300:
            strings.append(node.value)
    return strings, mods


def _norm(s: str):
    s = s.strip().replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    s = s.lstrip("/")
    return s


def _paths_from_strings(strings) -> set:
    out = set()
    apps = _apps()
    for s in strings:
        for piece in re.split(r"[\s'\"(),;=]+", s):
            p = _norm(piece.split("?")[0].split("#")[0])
            if not p or len(p) > 200 or "://" in piece:
                continue
            if p.startswith("../"):
                p = p.lstrip("./")
            first = p.split("/")[0]
            if first in TOP or p.startswith(("tools/", "web_next/")):
                out.add(p)
            elif first in apps and ("/" in p or p in apps):      # 'athena/index.html', 'athena/' (relative to web_public)
                out.add(f"{WP}/{p}")
            elif re.fullmatch(r"[A-Za-z0-9_-]+\.(py|mjs|cjs)", p) and os.path.isfile(os.path.join(TESTS, p)):
                out.add(f"tests/{p}")
    return out


_APPS = None


def _apps() -> set:
    global _APPS
    if _APPS is None:
        try:
            _APPS = {d for d in os.listdir(os.path.join(ROOT, WP)) if os.path.isdir(os.path.join(ROOT, WP, d))}
        except OSError:
            _APPS = set()
    return _APPS


_CACHE: dict = {}
# suites whose path strings are fixtures about OTHER files (the mapper's own test): only their imports count
FIXTURE_STRINGS = {"run_area_fast"}
_FILE_PATHS: dict = {}


def suite_info(name: str) -> dict:
    """{'reads': set of repo paths / folder prefixes, 'browser': bool} for tests/test_<name>.py"""
    if name in _CACHE:
        return _CACHE[name]
    rel = f"tests/test_{name}.py"
    src = _read(os.path.join(ROOT, rel))
    strings, mods = _strings_and_imports(src)
    reads = {rel} | (set() if name in FIXTURE_STRINGS else _paths_from_strings(strings))
    browser = bool(BROWSER_RX.search(src))
    seen = set()
    todo = [(m, 0) for m in mods]
    while todo:                                          # imports, two levels (engine / tools / tests helpers)
        m, depth = todo.pop()
        f = _mod_file(m)
        if not f or f in seen:
            continue
        seen.add(f)
        reads.add(f)
        if f.endswith(".py"):                            # every repo module it imports, all the way down (each file parsed once)
            s2 = _read(os.path.join(ROOT, f))
            if f.startswith("tests/") and BROWSER_RX.search(s2):
                browser = True
            st2, m2 = _strings_and_imports(s2)
            if f not in _FILE_PATHS:                     # from imported code: files only (a folder it names is mostly where it WRITES)
                _FILE_PATHS[f] = {x for x in _paths_from_strings(st2) if f.startswith("tests/") or "." in x.rsplit("/", 1)[-1]}
            reads |= _FILE_PATHS[f]                      # the data / page files the imported code itself opens
            todo += [(x, depth + 1) for x in m2]
    for h in [r for r in reads if r.startswith("tests/") and r.endswith((".mjs", ".cjs", ".js"))]:
        hs = _read(os.path.join(ROOT, h))
        if BROWSER_RX.search(hs):
            browser = True
        reads |= _paths_from_strings(re.findall(r"""["'`]([^"'`\n]{2,200})["'`]""", hs))
    info = {"reads": reads, "browser": browser}
    _CACHE[name] = info
    return info


def is_browser(name: str) -> bool:
    return suite_info(name)["browser"]


def hits(changed: str, reads) -> bool:
    c = _norm(changed)
    for r in reads:
        r = r.rstrip("/")
        if not r or r in TOO_BROAD:
            continue
        if c == r or c.startswith(r + "/"):              # the file, or a file inside a folder the suite reads
            return True
        if r.startswith(WP + "/") and r.count("/") >= 3 and c.startswith("/".join(r.split("/")[:3]) + "/") and r.endswith(".html"):
            return True                                  # it reads athena/index.html: any athena/ file can change that page
    return False


def changed_since(base: str, root: str = ROOT) -> list:
    out = set()
    for cmd in (["git", "-C", root, "diff", "--name-only", base], ["git", "-C", root, "ls-files", "-o", "--exclude-standard"]):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"git failed ({' '.join(cmd[3:])}): {r.stderr.strip()[:200]}")
        out.update(x.strip() for x in r.stdout.splitlines() if x.strip())
    return sorted(out)


def select(names: list, changed: list) -> dict:
    """{'run': [names], 'skipped': {name: reason}, 'fallback': '' or why the whole area runs, 'why': {name: the file that selects it}}"""
    changed = [_norm(c) for c in changed]
    code = [c for c in changed if not PROSE.search(c)]
    shared = [c for c in code if any(c == s or (s.endswith("/") and c.startswith(s)) for s in SHARED)]
    if shared:
        return {"run": list(names), "skipped": {}, "fallback": f"shared file changed: {', '.join(shared[:3])}", "why": {}}
    why = {}
    for n in names:
        reads = suite_info(n)["reads"]
        for c in code:
            if c == f"tests/test_{n}.py" or hits(c, reads):
                why[n] = c
                break
    unmapped = [c for c in code if not any(hits(c, suite_info(n)["reads"]) or c == f"tests/test_{n}.py" for n in names)]
    # a file no suite of THIS area reads: if some suite anywhere reads it, it belongs to another area (skip); else unsure (fallback)
    unsure = [c for c in unmapped if not _read_by_any(c)]
    unsure = [c for c in unsure if not c.startswith("tests/test_")]       # another area's suite file
    if unsure:
        return {"run": list(names), "skipped": {}, "fallback": f"no suite maps {', '.join(unsure[:3])}{' ...' if len(unsure) > 3 else ''}: whole area", "why": {}}
    run = [n for n in names if n in why]
    skipped = {n: "reads none of the changed files" for n in names if n not in why}
    return {"run": run, "skipped": skipped, "fallback": "", "why": why}


_ALL = None


def _read_by_any(c: str) -> bool:
    global _ALL
    if _ALL is None:
        _ALL = [n[5:-3] for n in os.listdir(TESTS) if n.startswith("test_") and n.endswith(".py")]
    return any(hits(c, suite_info(n)["reads"]) for n in _ALL)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 2
    sys.path.insert(0, TESTS)
    import run_area as RA                                # noqa: E402
    area = argv[1] if len(argv) > 1 else "all"
    plan = select(RA.suites_for(area), changed_since(argv[0]))
    print(f"run {len(plan['run'])}: " + ", ".join(f"{n} ({plan['why'].get(n, 'all')})" for n in plan["run"]))
    if plan["fallback"]:
        print("fallback: " + plan["fallback"])
    for n, why in plan["skipped"].items():
        print(f"skip {n}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
