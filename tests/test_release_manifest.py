"""tools/release_manifest.py: the 5 AM publish safety net (stale ?v= tags in app index.html files, service workers whose cache name did not move).

Every case runs the real script (subprocess) against a SYNTHETIC git repo built in a temp folder: branch `main` is the base, the change is made
on top of it (committed, edited or untracked), nothing touches the real repo.
  a. nothing changed -> exit 0
  b. ASSET TAGS: a changed file with the same ?v= is reported (phone page, an app page, web_next, a '../' reference, a '/x' reference); a bumped
     tag, an unchanged file, a new page, a file the page did not load before, a tag on an unchanged file are fine; committed, edited and
     untracked changes all count; several pages sharing one file are one line with a page count
  c. WORKERS: root sw.js, web_next/sw.js, jarvis/sw.js, kalshi/sw.js: a changed SHELL / ASSETS file (incl. './' = index.html, '/' and .push
     lines, query strings) with the same cache name is reported; a bumped name (CACHE or web_next's SHELL) is fine; a changed list with the same
     name is reported; a change to a file that is not in the list is fine
  d. exit codes (1 with findings, 0 clean, 2 for an unknown base), --json, a worker or page that is new
  e. the real repo: the script runs there (informational: it prints what the lead still has to bump)
    python -X utf8 -m tests.test_release_manifest
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "tools", "release_manifest.py")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def put(root, rel, text):
    p = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)


def sh(root, *a):
    r = subprocess.run(["git", "-C", root, "-c", "user.email=t@t", "-c", "user.name=t", *a], capture_output=True, text=True)
    assert r.returncode == 0, (a, r.stderr)
    return r.stdout


PHONE_HTML = '''<!doctype html><html><head><link rel="stylesheet" href="app.css?v=1"></head><body>
<script src="zenith.js?v=2" defer></script><script src="plain.js" defer></script><script src="https://cdn.example/x.js?v=9"></script></body></html>'''
APP_HTML = '''<!doctype html><html><head><link rel="stylesheet" href="../olympus/olympus.css?v=o2"><link rel="stylesheet" href="tyche.css?v=t4"></head><body>
<script src="../olympus/olympus.js?v=o2" defer></script><script src="/shared.js?v=s1" defer></script><script src="main.js?v=t4"></script></body></html>'''
APP2_HTML = '''<html><head></head><body><script src="../olympus/olympus.js?v=o2" defer></script></body></html>'''
PC_HTML = '''<html><head><link rel="stylesheet" href="/css/app.css?v=3"></head><body><script type="module" src="/js/app.js"></script><script src="/js/next/core.js?v=5"></script></body></html>'''
ROOT_SW = "const CACHE = 'le-public-v10';\nconst SHELL = ['./', './index.html', './manifest.webmanifest', './icons/icon.png?v=p1'];\n"
PC_SW = ("const SHELL = 'le-shell-next-v7';  // was v6\nconst ASSETS = ['/', '/index.html', '/css/app.css', '/js/app.js'];\n"
         "ASSETS.push('/js/next/core.js?v=5');\nASSETS.push('/css/extra.css?v=1', '/js/next/more.js');\n")
JAR_SW = "const CACHE = 'jarvis-v3';\nconst OLD = ['jarvis-v2'];\nconst SHELL = ['./', './index.html', './core.js?v=j1', './orb.js'];\n"
KAL_SW = "const CACHE = 'kalshi-k5';\nconst SHELL = ['./', './index.html', './kalshi.css?v=k5', './kalshi.js?v=k5'];\n"
FILES = {
    "tools/web_public/index.html": PHONE_HTML, "tools/web_public/app.css": "a{}", "tools/web_public/zenith.js": "1", "tools/web_public/plain.js": "p",
    "tools/web_public/manifest.webmanifest": "{}", "tools/web_public/icons/icon.png": "png", "tools/web_public/sw.js": ROOT_SW, "tools/web_public/shared.js": "s",
    "tools/web_public/olympus/olympus.css": "o", "tools/web_public/olympus/olympus.js": "o",
    "tools/web_public/tyche/index.html": APP_HTML, "tools/web_public/tyche/tyche.css": "t", "tools/web_public/tyche/main.js": "m",
    "tools/web_public/kalshi/index.html": "<html><body><script src=\"kalshi.js?v=k5\"></script></body></html>", "tools/web_public/kalshi/kalshi.js": "k", "tools/web_public/kalshi/kalshi.css": "k",
    "tools/web_public/kalshi/sw.js": KAL_SW, "tools/web_public/jarvis/index.html": "<html><body><script src=\"core.js?v=j1\"></script></body></html>",
    "tools/web_public/jarvis/core.js": "j", "tools/web_public/jarvis/orb.js": "o", "tools/web_public/jarvis/notshell.js": "n", "tools/web_public/jarvis/sw.js": JAR_SW,
    "tools/web_public/arena/index.html": APP2_HTML,
    "web_next/index.html": PC_HTML, "web_next/sw.js": PC_SW, "web_next/css/app.css": "a", "web_next/js/app.js": "a", "web_next/js/next/core.js": "c", "web_next/js/next/more.js": "m",
    "web_next/css/extra.css": "e",
}


def repo():
    d = tempfile.mkdtemp(prefix="le_relm_")
    sh(d, "init", "-q", "-b", "main")
    for rel, txt in FILES.items():
        put(d, rel, txt)
    sh(d, "add", "-A")
    sh(d, "commit", "-q", "-m", "base")
    return d


def run(d, *extra):
    r = subprocess.run([sys.executable, SCRIPT, "--root", d, "--base", "main", *extra], capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout, r.stderr


def case(label, edit, want_code, has=(), hasnt=(), commit=False):
    d = repo()
    try:
        edit(d)
        if commit:
            sh(d, "checkout", "-q", "-b", "change")
            sh(d, "add", "-A")
            sh(d, "commit", "-q", "-m", "change")
        code, out, err = run(d)
        ok = code == want_code and all(x in out for x in has) and not any(x in out for x in hasnt)
        check(label, ok, (code, out[-900:], err[-300:]))
        return out
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    # ------------------------------------------------------------------ a. clean
    case("a. nothing changed since the base: exit 0, 'OK, nothing stale'", lambda d: None, 0, has=("OK, nothing stale",))
    # ------------------------------------------------------------------ b. asset tags
    out = case("b. a changed file with the same ?v= (phone page: app.css?v=1) is reported with the file and the tag; exit 1",
               lambda d: put(d, "tools/web_public/app.css", "a{color:red}"), 1, has=("STALE ?v= tools/web_public/app.css (?v=1)", "tag unchanged", "loaded by 1 page"))

    def bump(d):
        put(d, "tools/web_public/app.css", "a{color:red}")
        put(d, "tools/web_public/index.html", PHONE_HTML.replace("app.css?v=1", "app.css?v=2"))
        put(d, "tools/web_public/sw.js", ROOT_SW.replace("v10", "v11"))   # index.html is in the worker's SHELL, so the cache name moves with it
    case("b. the same change with the ?v= bumped (and the worker cache name) is fine", bump, 0, has=("OK, nothing stale",))
    case("b. an unchanged file keeps its tag: no finding (zenith.js untouched)", lambda d: put(d, "tools/web_public/plain.js", "p2"), 0, hasnt=("STALE",))
    case("b. a file loaded WITHOUT a ?v= (plain.js) and an external script (?v=9) are not checked", lambda d: put(d, "tools/web_public/plain.js", "changed"), 0)
    case("b. a COMMITTED change counts the same as an edit", lambda d: put(d, "tools/web_public/zenith.js", "2"), 1, has=("zenith.js (?v=2)",), commit=True)
    case("b. an UNTRACKED file counts: a new file that a tag already points at (the page names it, git has never seen it)",
         lambda d: (os.remove(os.path.join(d, "tools/web_public/shared.js")), sh(d, "rm", "-q", "--cached", "tools/web_public/shared.js"), sh(d, "commit", "-q", "-m", "x"), put(d, "tools/web_public/shared.js", "s2")),
         1, has=("tools/web_public/shared.js (?v=s1)",))   # main no longer tracks shared.js; the file on disk is untracked, the page still names it
    o = case("b. an app page: '../olympus/olympus.js?v=o2' changed -> every page that loads it, in ONE line with a count (tyche + arena = 2 pages)",
             lambda d: put(d, "tools/web_public/olympus/olympus.js", "new"), 1, has=("tools/web_public/olympus/olympus.js (?v=o2)", "loaded by 2 pages", "tyche", "arena"))
    case("b. '/shared.js?v=s1' (a site-root reference in an app page) resolves to tools/web_public/shared.js", lambda d: put(d, "tools/web_public/shared.js", "s2"), 1, has=("tools/web_public/shared.js (?v=s1)",))
    case("b. web_next: '/css/app.css?v=3' and '/js/next/core.js?v=5' resolve inside web_next/ (a '/js/app.js' without a tag is not checked)",
         lambda d: (put(d, "web_next/css/app.css", "b"), put(d, "web_next/js/next/core.js", "d"), put(d, "web_next/js/app.js", "z")), 1,
         has=("web_next/css/app.css (?v=3)", "web_next/js/next/core.js (?v=5)"), hasnt=("web_next/js/app.js (?v",))

    def newref(d):
        put(d, "tools/web_public/index.html", PHONE_HTML.replace("</body>", '<script src="brandnew.js?v=1"></script></body>'))
        put(d, "tools/web_public/sw.js", ROOT_SW.replace("v10", "v11"))
        put(d, "tools/web_public/brandnew.js", "n")
        put(d, "tools/web_public/arena/index.html", APP2_HTML)
        put(d, "tools/web_public/newapp/index.html", '<html><script src="x.js?v=1"></script></html>')
        put(d, "tools/web_public/newapp/x.js", "x")
    case("b. a file the page did not load before, and a brand new page, are fine (nothing is cached yet)", newref, 0, hasnt=("STALE",))
    # ------------------------------------------------------------------ c. workers
    case("c. root sw.js: index.html (in SHELL as './index.html' and './') changed, cache name the same -> reported with the file",
         lambda d: put(d, "tools/web_public/index.html", PHONE_HTML + "<!-- x -->"), 1, has=("STALE WORKER tools/web_public/sw.js", "'le-public-v10'", "index.html"))
    case("c. root sw.js: the cache name bumped -> fine", lambda d: (put(d, "tools/web_public/index.html", PHONE_HTML + "<!-- x -->"), put(d, "tools/web_public/sw.js", ROOT_SW.replace("v10", "v11"))), 0,
         hasnt=("STALE WORKER",))
    case("c. root sw.js: a changed file that is NOT in its SHELL (zenith.js) does not touch the worker (its tag is another matter)", lambda d: put(d, "tools/web_public/zenith.js", "9"), 1,
         has=("zenith.js (?v=2)",), hasnt=("STALE WORKER",))
    case("c. root sw.js: a SHELL file with a query string ('./icons/icon.png?v=p1') is matched by its path", lambda d: put(d, "tools/web_public/icons/icon.png", "newpng"), 1,
         has=("STALE WORKER tools/web_public/sw.js", "icons/icon.png"))
    case("c. web_next/sw.js (SHELL is the cache name, ASSETS list + .push lines): '/js/next/more.js' from a push line changed -> reported",
         lambda d: put(d, "web_next/js/next/more.js", "new"), 1, has=("STALE WORKER web_next/sw.js", "'le-shell-next-v7'", "js/next/more.js"))
    case("c. web_next/sw.js: '/css/extra.css?v=1' (push with a query) changed -> reported; '/' = web_next/index.html also counts",
         lambda d: (put(d, "web_next/css/extra.css", "ee"), put(d, "web_next/index.html", PC_HTML + "<!-- y -->")), 1, has=("css/extra.css", "index.html"))
    case("c. web_next/sw.js: a bumped SHELL name -> fine", lambda d: (put(d, "web_next/js/next/more.js", "new"), put(d, "web_next/sw.js", PC_SW.replace("v7", "v8"))), 0, hasnt=("STALE WORKER",))
    case("c. web_next/sw.js: a new entry in ASSETS with the same name -> reported as a changed list",
         lambda d: put(d, "web_next/sw.js", PC_SW + "ASSETS.push('/js/next/newpage.js');\n"), 1, has=("STALE WORKER web_next/sw.js", "its list changed", "/js/next/newpage.js"))
    case("c. jarvis/sw.js: core.js (in SHELL as './core.js?v=j1') changed, name the same -> reported (and its tag too)", lambda d: put(d, "tools/web_public/jarvis/core.js", "jj"), 1,
         has=("STALE WORKER tools/web_public/jarvis/sw.js", "'jarvis-v3'", "core.js", "STALE ?v= tools/web_public/jarvis/core.js"))
    case("c. jarvis/sw.js: a file that is not in SHELL (notshell.js) is fine", lambda d: put(d, "tools/web_public/jarvis/notshell.js", "nn"), 0, hasnt=("STALE",))
    case("c. jarvis/sw.js: bumped to jarvis-v4 (old name kept in OLD) -> the worker is fine", lambda d: (put(d, "tools/web_public/jarvis/orb.js", "o2"), put(d, "tools/web_public/jarvis/sw.js", JAR_SW.replace("const CACHE = 'jarvis-v3'", "const CACHE = 'jarvis-v4'"))), 0,
         hasnt=("STALE WORKER",))
    case("c. kalshi/sw.js: kalshi.js?v=k5 changed -> the worker AND the tag are reported; bumping both (k6) is fine",
         lambda d: put(d, "tools/web_public/kalshi/kalshi.js", "k2"), 1, has=("STALE WORKER tools/web_public/kalshi/sw.js", "'kalshi-k5'", "STALE ?v= tools/web_public/kalshi/kalshi.js"))
    case("c. kalshi: worker, page tag and the SHELL tags all bumped together -> clean",
         lambda d: (put(d, "tools/web_public/kalshi/kalshi.js", "k2"), put(d, "tools/web_public/kalshi/index.html", "<html><body><script src=\"kalshi.js?v=k6\"></script></body></html>"),
                    put(d, "tools/web_public/kalshi/sw.js", KAL_SW.replace("k5", "k6"))), 0, hasnt=("STALE",))
    # ------------------------------------------------------------------ d. codes and output
    d = repo()
    try:
        put(d, "tools/web_public/app.css", "zz")
        c1, o1, _ = run(d)
        c2, o2, _ = run(d, "--json")
        j = json.loads(o2)
        r3 = subprocess.run([sys.executable, SCRIPT, "--root", d, "--base", "nosuchref"], capture_output=True, text=True)
        sh(d, "checkout", "-q", "--", "tools/web_public/app.css")
        c4, o4, _ = run(d)
        check("d. exit 1 with a finding, 0 once it is fixed, 2 for a base that does not exist (with a plain message)", c1 == 1 and c4 == 0 and r3.returncode == 2 and "does not exist" in r3.stdout, (c1, c4, r3.returncode, r3.stdout))
        check("d. --json: the findings as data (kind, page, file, v, text)", c2 == 1 and j and j[0]["kind"] == "tag" and j[0]["file"] == "tools/web_public/app.css" and j[0]["v"] == "1" and j[0]["page"] == "tools/web_public/index.html", j[:1])
        check("d. the summary line counts the problems in words (1 problem (1 stale asset tag, 0 workers))", "1 problem (1 stale asset tag, 0 workers)" in o1, o1[-300:])
    finally:
        shutil.rmtree(d, ignore_errors=True)
    d = repo()
    try:
        put(d, "tools/web_public/newworker/index.html", "<html></html>")
        put(d, "tools/web_public/jarvis/sw.js", JAR_SW.replace("'./orb.js'", "'./orb.js', './brand.js'"))
        put(d, "tools/web_public/jarvis/brand.js", "b")
        c, o, _ = run(d)
        check("d. a changed worker LIST with the same cache name is a finding even when no listed file changed (exit 1)", c == 1 and "its list changed" in o and "./brand.js" in o, o[-400:])
    finally:
        shutil.rmtree(d, ignore_errors=True)
    # ------------------------------------------------------------------ e. the real repo
    r = subprocess.run([sys.executable, SCRIPT, "--base", "origin/main"], capture_output=True, text=True, timeout=300, cwd=ROOT)
    check("e. the real repo: the script runs and ends with its summary line (exit 0 or 1, never a crash)", r.returncode in (0, 1, 2) and ("release manifest" in r.stdout) and "Traceback" not in r.stderr, (r.returncode, r.stdout[-300:], r.stderr[-300:]))
    print("    (real repo vs origin/main: " + (r.stdout.strip().splitlines() or ["?"])[-1] + ")")
    n = sum(RES)
    print(f"\nrelease manifest: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
