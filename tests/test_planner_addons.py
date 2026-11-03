"""Planner add-ons at publish (scripts/add_planner.sh, owner 2026-11-01): the Planner comes from the nq-dashboard branch
planner-backup; features built in this repo are patches in tools/planner_patches/ applied on top at every publish.
Runs the real script against a local stand-in repo (PLANNER_REPO / PLANNER_PATCHES) and checks:
  a. no patches: the planner is copied as is, addons.json says nothing applied
  b. a clean patch applies (new file + an edit), and addons.json lists it
  c. a patch that conflicts with a newer planner-backup is skipped, the earlier add-on stays, nothing half-patched
  d. a patch made on an older base still applies by a 3-way merge when the newer base changed other lines
  e. the script never fails the caller (unreachable repo -> exit 0, no planner)
  g. confinement: a patch touching anything outside planner/ or adding a symlink is skipped; links are deleted
  f. every real patch in tools/planner_patches/ applies to the live planner-backup and its ext-*.js is loaded once (network; skipped offline)
    python -X utf8 -m tests.test_planner_addons      (temp folders only)
"""
from __future__ import annotations

import json
import re
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "add_planner.sh")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def git(*a, cwd=None):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, env=env)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


BASE = ("<!doctype html>\n<title>Planner</title>\n<body>\n<h1>Planner</h1>\n<p>one</p>\n<p>two</p>\n"
        + "".join(f"<p>filler {i}</p>\n" for i in range(12)) + "<p>three</p>\n<p>end</p>\n</body>\n")


def make_repo(tmp):
    """A stand-in for nq-dashboard: branch planner-backup with planner/index.html + sw.js."""
    work = os.path.join(tmp, "work")
    git("init", "-q", "-b", "planner-backup", work)
    write(os.path.join(work, "planner", "index.html"), BASE)
    write(os.path.join(work, "planner", "sw.js"), "// sw\n")
    git("add", "-A", cwd=work)
    git("commit", "-q", "-m", "base", cwd=work)
    return work


def patch_from(work, edit):
    """A patch made on the current planner-backup: edit(work) then diff (new files included), then undo."""
    edit(work)
    git("add", "-A", cwd=work)
    d = git("diff", "--cached", "--binary", cwd=work).stdout
    git("reset", "-q", "--hard", cwd=work)
    git("clean", "-qfd", cwd=work)
    return d


def run(site, repo, patches):
    env = {**os.environ, "PLANNER_REPO": repo, "PLANNER_PATCHES": patches}
    return subprocess.run(["bash", SCRIPT, site], capture_output=True, text=True, env=env, timeout=300)


def main():
    tmp = tempfile.mkdtemp(prefix="le_planner_addons_")
    try:
        work = make_repo(tmp)
        pdir = os.path.join(tmp, "patches")
        os.makedirs(pdir)
        # a. no patches
        site = os.path.join(tmp, "site_a")
        os.makedirs(site)
        r = run(site, work, pdir)
        a = json.load(open(os.path.join(site, "planner", "addons.json")))
        check("a. no patches: planner copied as is, addons.json empty", r.returncode == 0
              and open(os.path.join(site, "planner", "index.html")).read() == BASE and a == {"v": 1, "applied": [], "skipped": []}, (r.stdout, a))
        check("a. no .git folder in the published planner", not os.path.exists(os.path.join(site, "planner", ".git")))
        # b. a clean patch: a new file + a one-line hook
        p1 = patch_from(work, lambda w: (write(os.path.join(w, "planner", "ext-one.js"), "window.one = 1;\n"),
                                         write(os.path.join(w, "planner", "index.html"), BASE.replace("</body>", '<script src="ext-one.js"></script>\n</body>'))))
        write(os.path.join(pdir, "10-one.patch"), p1)
        site = os.path.join(tmp, "site_b")
        os.makedirs(site)
        r = run(site, work, pdir)
        idx = open(os.path.join(site, "planner", "index.html")).read()
        a = json.load(open(os.path.join(site, "planner", "addons.json")))
        check("b. a clean patch applies: the new file and the hook", r.returncode == 0 and os.path.exists(os.path.join(site, "planner", "ext-one.js"))
              and 'src="ext-one.js"' in idx and a["applied"] == ["10-one"] and a["skipped"] == [], (r.stdout, r.stderr, a))
        # c. a patch that conflicts with a newer planner-backup: skipped, the earlier add-on stays
        p2 = patch_from(work, lambda w: write(os.path.join(w, "planner", "index.html"), BASE.replace("<p>two</p>", "<p>TWO (add-on)</p>")))
        write(os.path.join(pdir, "20-two.patch"), p2)
        write(os.path.join(work, "planner", "index.html"), BASE.replace("<p>two</p>", "<p>two, edited upstream</p>"))
        git("commit", "-qam", "upstream edits line two", cwd=work)
        site = os.path.join(tmp, "site_c")
        os.makedirs(site)
        r = run(site, work, pdir)
        idx = open(os.path.join(site, "planner", "index.html")).read()
        a = json.load(open(os.path.join(site, "planner", "addons.json")))
        check("c. a conflicting add-on is skipped and logged; the other add-on and upstream's edit stay; no conflict markers",
              r.returncode == 0 and a["applied"] == ["10-one"] and a["skipped"] == ["20-two"] and "two, edited upstream" in idx
              and "TWO (add-on)" not in idx and "<<<<<<<" not in idx and 'src="ext-one.js"' in idx and "no longer applies" in r.stdout, (r.stdout, a, idx))
        # d. a patch made on the OLD base still applies by 3-way when upstream changed other lines
        os.remove(os.path.join(pdir, "20-two.patch"))
        git("checkout", "-q", "HEAD~1", cwd=work)
        p3 = patch_from(work, lambda w: write(os.path.join(w, "planner", "index.html"), BASE.replace("<p>three</p>", "<p>three + add-on</p>")))
        git("checkout", "-q", "planner-backup", cwd=work)
        write(os.path.join(pdir, "30-three.patch"), p3)
        site = os.path.join(tmp, "site_d")
        os.makedirs(site)
        r = run(site, work, pdir)
        idx = open(os.path.join(site, "planner", "index.html")).read()
        a = json.load(open(os.path.join(site, "planner", "addons.json")))
        check("d. an add-on made on an older base applies by 3-way merge next to upstream's newer edit",
              a["applied"] == ["10-one", "30-three"] and "three + add-on" in idx and "two, edited upstream" in idx and "<<<<<<<" not in idx, (r.stdout, a))
        # g. confinement (security review): outside planner/, a symlink, an upstream link
        os.remove(os.path.join(pdir, "30-three.patch"))
        p4 = patch_from(work, lambda w: write(os.path.join(w, "evil.txt"), "outside\n"))
        write(os.path.join(pdir, "40-outside.patch"), p4)
        def add_link(w):
            os.symlink("/etc/passwd", os.path.join(w, "planner", "link.txt"))
        p5 = patch_from(work, add_link)
        write(os.path.join(pdir, "50-link.patch"), p5)
        os.symlink("/etc/hostname", os.path.join(work, "planner", "upstream-link"))
        git("add", "-A", cwd=work)
        git("commit", "-q", "-m", "upstream adds a link", cwd=work)
        site = os.path.join(tmp, "site_g")
        os.makedirs(site)
        r = run(site, work, pdir)
        a = json.load(open(os.path.join(site, "planner", "addons.json")))
        check("g. a patch touching a file outside planner/ is skipped, nothing written outside",
              "40-outside" in a["skipped"] and not os.path.exists(os.path.join(site, "evil.txt")) and "outside planner/" in r.stdout, (r.stdout, a))
        check("g. a patch adding a symlink is skipped", "50-link" in a["skipped"] and not os.path.lexists(os.path.join(site, "planner", "link.txt")), a)
        check("g. links in planner-backup itself are deleted from the published copy; the good add-on still applies",
              not os.path.lexists(os.path.join(site, "planner", "upstream-link")) and a["applied"] == ["10-one"], (a, os.listdir(os.path.join(site, "planner"))))
        for f in ("40-outside.patch", "50-link.patch"):
            os.remove(os.path.join(pdir, f))
        # e. never fails the caller
        site = os.path.join(tmp, "site_e")
        os.makedirs(site)
        r = run(site, os.path.join(tmp, "nope.git"), pdir)
        check("e. an unreachable repo: exit 0, published without the planner", r.returncode == 0 and not os.path.exists(os.path.join(site, "planner"))
              and "could not fetch" in r.stdout, r.stdout)
        # f. the real patches against the real planner-backup
        real = os.path.join(ROOT, "tools", "planner_patches")
        names = sorted(f for f in os.listdir(real) if f.endswith(".patch")) if os.path.isdir(real) else []
        site = os.path.join(tmp, "site_f")
        os.makedirs(site)
        r = run(site, "https://github.com/demetrades2000-coder/nq-dashboard.git", real)
        if "could not fetch" in r.stdout:
            print("[SKIP] f. no network to GitHub: real patches not checked")
        else:
            a = json.load(open(os.path.join(site, "planner", "addons.json")))
            check(f"f. every real add-on ({len(names)}) applies to the live planner-backup",
                  a["skipped"] == [] and len(a["applied"]) == len(names), (r.stdout, a))
            # each add-on's script is published and hooked into the page exactly once (a lost hook = a dead add-on)
            idx = open(os.path.join(site, "planner", "index.html"), encoding="utf-8").read()
            exts = sorted(f for f in os.listdir(os.path.join(site, "planner")) if f.startswith("ext-") and f.endswith(".js"))
            check("f. every add-on script (ext-projects, ext-power, ext-flow, ext-olympus ...) is published and loaded once by index.html",
                  {"ext-projects.js", "ext-power.js", "ext-flow.js", "ext-olympus.js"} <= set(exts)
                  and all(len(re.findall(r'<script src="%s"' % re.escape(f), idx)) == 1 for f in exts), exts)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\nplanner add-ons: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
