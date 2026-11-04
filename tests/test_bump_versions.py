"""tools/bump_versions.py on a synthetic mini-site in a temp dir (a throwaway git repo): never the real tree.

  a. the tag arithmetic (o2 -> o3, k17 -> k18, 8 -> 9, p111030 -> p111031, no digit = not bumpable)
  b. dry run changes nothing; the plan names every query, worker and pin
  c. apply: one consistent new tag in every place (html tag, worker list, a script's own string), no ?v= added to a file that had none,
     untouched files keep theirs
  d. workers: Jarvis jarvis-vN+1 with the old name first in OLD, phone root once (also for an app file with no ?v=), PC, Kalshi = 'kalshi-<tag>'
  e. tests that pin exact strings are updated (tag, CACHE line, OLD list start, caches.open); an ambiguous pin is reported, not changed
  f. a second run bumps nothing (already bumped since the base); --check exits 1 before and 0 after; a pre-bumped file is left alone
    python -X utf8 -m unittest tests.test_bump_versions
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import bump_versions as B  # noqa: E402

FILES = {
    "tools/web_public/index.html": '<link rel="stylesheet" href="./style.css?v=s3"><script src="./app.js?v=a1"></script><img src="./icons/i.png?v=p10"><script src="./plain.js"></script>\n',
    "tools/web_public/style.css": "body{}\n",
    "tools/web_public/app.js": "console.log(1)\n",
    "tools/web_public/plain.js": "console.log(2)\n",
    "tools/web_public/icons/i.png": "png",
    "tools/web_public/sw.js": "const CACHE = 'le-public-v10';\nconst OTHER_APPS = ['jarvis/', 'kalshi/', 'tyche/'];\n"
                              "const SHELL = ['./', './index.html', './style.css?v=s3', './app.js?v=a1', './icons/i.png?v=p10'];\n",
    "tools/web_public/olympus/olympus.js": "var u = me.src.replace(/olympus\\.js.*$/, 'sfx.js?v=s1');\n",
    "tools/web_public/olympus/sfx.js": "// sfx\n",
    "tools/web_public/olympus/render.js": "// render\n",
    "tools/web_public/tyche/index.html": '<script src="../olympus/olympus.js?v=o2" data-app="tyche"></script><script type="module" src="main.js?v=t5"></script>\n',
    "tools/web_public/tyche/main.js": "import './scene.js';\n",
    "tools/web_public/tyche/scene.js": "// scene (a module with no ?v=)\n",
    "tools/web_public/jarvis/index.html": '<script src="../olympus/sfx.js?v=s1"></script><script type="module" src="./portal.js?v=p1"></script>\n',
    "tools/web_public/jarvis/portal.js": "// portal\n",
    "tools/web_public/jarvis/data.js": "// data\n",
    "tools/web_public/jarvis/sw.js": "const CACHE = 'jarvis-v24';\nconst OLD = ['jarvis-v23', 'jarvis-v22'];\n"
                                     "const SHELL = ['./', './index.html', './data.js', './portal.js?v=p1', '../olympus/sfx.js?v=s1', '../olympus/render.js'];\n",
    "tools/web_public/kalshi/index.html": '<script src="kalshi.js?v=k17"></script><link href="kalshi.css?v=k17" rel="stylesheet">\n',
    "tools/web_public/kalshi/kalshi.js": "// kalshi\n",
    "tools/web_public/kalshi/kalshi.css": "/* kalshi */\n",
    "tools/web_public/kalshi/sw.js": "const CACHE = 'kalshi-k17';\nconst SHELL = ['./', './index.html', './kalshi.css?v=k17', './kalshi.js?v=k17'];\n",
    "web_next/index.html": '<link href="/css/app.css?v=3" rel="stylesheet"><script src="/js/next/x.js?v=1"></script>\n',
    "web_next/css/app.css": "a{}\n",
    "web_next/js/next/x.js": "//x\n",
    "web_next/sw.js": "const SHELL = 'le-shell-next-v34';  // v34\nconst ASSETS = ['/', '/index.html', '/css/app.css?v=3', '/js/next/x.js?v=1'];\n",
    "tests/test_pins.py": ("def t(sw, kh, jv, root):\n"
                          "    assert \"const CACHE = 'jarvis-v24';\" in sw\n"
                          "    assert \"const OLD = ['jarvis-v23', 'jarvis-v22'\" in sw\n"
                          "    assert 'src=\"../olympus/sfx.js?v=s1\"' in jv\n"
                          "    x = \"await caches.open('jarvis-v24')\"\n"
                          "    assert \"const CACHE = 'kalshi-k17';\" in kh and \"'./kalshi.js?v=k17'\" in kh\n"
                          "    assert \"const CACHE = 'le-public-v10';\" in root\n"
                          "    # a mention that is no pin: 'jarvis-v24' in a comment\n"),
}


def git(root, *args):
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True, text=True)


def make_site(extra=None):
    root = tempfile.mkdtemp(prefix="bump_site_")
    files = dict(FILES)
    files.update(extra or {})
    for rel, text in files.items():
        p = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    return root


def read(root, rel):
    with open(os.path.join(root, *rel.split("/")), encoding="utf-8") as fh:
        return fh.read()


def write(root, rel, text):
    os.makedirs(os.path.dirname(os.path.join(root, *rel.split("/"))), exist_ok=True)
    with open(os.path.join(root, *rel.split("/")), "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def run(root, *argv, changed=None):
    args = ["--root", root, "--base", "HEAD", *argv]
    if changed is not None:
        args += ["--changed", *changed]
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = B.main(args)
    return code, buf.getvalue()


CHANGED = ["tools/web_public/olympus/sfx.js", "tools/web_public/olympus/render.js", "tools/web_public/jarvis/portal.js", "tools/web_public/jarvis/data.js",
           "tools/web_public/tyche/scene.js", "tools/web_public/kalshi/kalshi.js", "web_next/css/app.css", "tools/web_public/app.js"]


class BumpVersions(unittest.TestCase):
    def setUp(self):
        self.root = make_site()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_a_tag_arithmetic(self):
        self.assertEqual([B.bump_tag(t) for t in ("o2", "k17", "8", "p111030", "v09", "l1")], ["o3", "k18", "9", "p111031", "v10", "l2"])
        self.assertIsNone(B.bump_tag("abc"))

    def test_b_dry_run_changes_nothing(self):
        before = {r: read(self.root, r) for r in FILES}
        code, out = run(self.root, "--dry-run", changed=CHANGED)
        self.assertEqual(code, 0)
        self.assertEqual({r: read(self.root, r) for r in FILES}, before)
        for want in ("query", "worker", "pin", "sfx.js?v=s1 -> ?v=s2", "cache jarvis-v24 -> jarvis-v25", "dry run:"):
            self.assertIn(want, out)

    def test_c_apply_is_consistent_everywhere(self):
        code, out = run(self.root, "--apply", changed=CHANGED)
        self.assertEqual(code, 0, out)
        # sfx.js s1 -> s2 in the Jarvis page, Jarvis' worker list and the kit's own loader string; nothing else moved with it
        self.assertIn("../olympus/sfx.js?v=s2", read(self.root, "tools/web_public/jarvis/index.html"))
        self.assertIn("'../olympus/sfx.js?v=s2'", read(self.root, "tools/web_public/jarvis/sw.js"))
        self.assertIn("'sfx.js?v=s2'", read(self.root, "tools/web_public/olympus/olympus.js"))
        # portal p1 -> p2 (page + worker); app.js a1 -> a2 (page + phone worker); web_next css 3 -> 4 (page + worker)
        self.assertIn("./portal.js?v=p2", read(self.root, "tools/web_public/jarvis/index.html"))
        self.assertIn("'./portal.js?v=p2'", read(self.root, "tools/web_public/jarvis/sw.js"))
        self.assertIn("./app.js?v=a2", read(self.root, "tools/web_public/index.html"))
        self.assertIn("'./app.js?v=a2'", read(self.root, "tools/web_public/sw.js"))
        self.assertIn("/css/app.css?v=4", read(self.root, "web_next/index.html"))
        self.assertIn("'/css/app.css?v=4'", read(self.root, "web_next/sw.js"))
        # files that did not change keep their tags; files with no ?v= get none
        self.assertIn("./style.css?v=s3", read(self.root, "tools/web_public/index.html"))
        self.assertIn("./icons/i.png?v=p10", read(self.root, "tools/web_public/index.html"))
        self.assertIn("../olympus/olympus.js?v=o3", read(self.root, "tools/web_public/tyche/index.html"))        # cascade: the tool edited olympus.js (its sfx.js string), so olympus.js is bumped too
        self.assertIn("'../olympus/render.js'", read(self.root, "tools/web_public/jarvis/sw.js"))
        self.assertNotIn("render.js?v=", read(self.root, "tools/web_public/jarvis/sw.js"))
        self.assertIn('src="./plain.js"', read(self.root, "tools/web_public/index.html"))
        self.assertEqual(read(self.root, "tools/web_public/olympus/sfx.js"), FILES["tools/web_public/olympus/sfx.js"])      # the changed file itself is never edited
        self.assertIn("kalshi.js?v=k18", read(self.root, "tools/web_public/kalshi/index.html"))

    def test_d_workers(self):
        run(self.root, "--apply", changed=CHANGED)
        j = read(self.root, "tools/web_public/jarvis/sw.js")
        self.assertIn("const CACHE = 'jarvis-v25';", j)
        self.assertIn("const OLD = ['jarvis-v24', 'jarvis-v23', 'jarvis-v22'];", j)
        root_sw = read(self.root, "tools/web_public/sw.js")
        self.assertIn("const CACHE = 'le-public-v11';", root_sw)                                  # once, though two reasons asked for it
        self.assertEqual(root_sw.count("le-public-v"), 1)
        self.assertIn("const SHELL = 'le-shell-next-v35';", read(self.root, "web_next/sw.js"))
        k = read(self.root, "tools/web_public/kalshi/sw.js")
        self.assertIn("const CACHE = 'kalshi-k18';", k)
        self.assertIn("'./kalshi.js?v=k18'", k)

    def test_d2_unversioned_app_file_bumps_the_root_worker_once(self):
        code, out = run(self.root, "--apply", changed=["tools/web_public/tyche/scene.js"])
        self.assertIn("const CACHE = 'le-public-v11';", read(self.root, "tools/web_public/sw.js"))
        self.assertIn("app files without ?v=", out)
        self.assertEqual(read(self.root, "tools/web_public/jarvis/sw.js"), FILES["tools/web_public/jarvis/sw.js"])      # nothing else moved

    def test_e_pins_in_tests(self):
        code, out = run(self.root, "--apply", changed=CHANGED)
        t = read(self.root, "tests/test_pins.py")
        self.assertIn("const CACHE = 'jarvis-v25';", t)
        self.assertIn("const OLD = ['jarvis-v24', 'jarvis-v23', 'jarvis-v22'", t)
        self.assertIn('src="../olympus/sfx.js?v=s2"', t)
        self.assertIn("caches.open('jarvis-v25')", t)
        self.assertIn("const CACHE = 'kalshi-k18';", t)
        self.assertIn("'./kalshi.js?v=k18'", t)
        self.assertIn("const CACHE = 'le-public-v11';", t)
        self.assertIn("# a mention that is no pin: 'jarvis-v24' in a comment", t)                  # not a pin: reported, not changed
        self.assertIn("tests/test_pins.py:", out)
        self.assertIn("check by hand", out)

    def test_e2_ambiguous_pin_is_reported_not_changed(self):
        root = make_site({"tools/web_public/a/index.html": '<script src="app.js?v=z1"></script>\n', "tools/web_public/a/app.js": "//a\n",
                          "tools/web_public/b/index.html": '<script src="app.js?v=z1"></script>\n', "tools/web_public/b/app.js": "//b\n",
                          "tests/test_amb.py": "assert 'app.js?v=z1' in page\n"})
        try:
            code, out = run(root, "--apply", changed=["tools/web_public/a/app.js"])
            self.assertIn("app.js?v=z2", read(root, "tools/web_public/a/index.html"))
            self.assertIn("app.js?v=z1", read(root, "tools/web_public/b/index.html"))
            self.assertIn("'app.js?v=z1'", read(root, "tests/test_amb.py"))
            self.assertIn("another file with that name keeps it", out)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_f_second_run_and_check(self):
        code, _ = run(self.root, "--check", changed=CHANGED)
        self.assertEqual(code, 1)                                                                  # changed but not bumped
        run(self.root, "--apply", changed=CHANGED)
        code, out = run(self.root, "--check", changed=CHANGED)
        self.assertEqual(code, 0, out)                                                             # bumped since the base: nothing more
        code, out = run(self.root, "--apply", changed=CHANGED)
        self.assertIn("nothing needs a bump", out)
        self.assertEqual(read(self.root, "tools/web_public/jarvis/sw.js").count("jarvis-v25"), 1)    # not bumped twice

    def test_f2_pre_bumped_file_is_left_alone(self):
        write(self.root, "tools/web_public/index.html", read(self.root, "tools/web_public/index.html").replace("app.js?v=a1", "app.js?v=a2"))
        write(self.root, "tools/web_public/sw.js", read(self.root, "tools/web_public/sw.js").replace("app.js?v=a1", "app.js?v=a2").replace("le-public-v10", "le-public-v11"))
        code, out = run(self.root, "--apply", changed=["tools/web_public/app.js"])
        self.assertIn("./app.js?v=a2", read(self.root, "tools/web_public/index.html"))
        self.assertNotIn("a3", read(self.root, "tools/web_public/index.html"))
        self.assertIn("already bumped", out)
        self.assertEqual(code, 0)

    def test_g_disagreeing_tags_take_the_highest_plus_one(self):
        write(self.root, "tools/web_public/sw.js", read(self.root, "tools/web_public/sw.js").replace("app.js?v=a1", "app.js?v=a3"))
        git(self.root, "commit", "-qam", "base2")
        write(self.root, "tools/web_public/app.js", "console.log(3)\n")
        run(self.root, "--apply", changed=["tools/web_public/app.js"])
        self.assertIn("./app.js?v=a4", read(self.root, "tools/web_public/index.html"))
        self.assertIn("'./app.js?v=a4'", read(self.root, "tools/web_public/sw.js"))

    def test_h_real_git_changed_set(self):
        write(self.root, "tools/web_public/app.js", "console.log('edited')\n")                       # an uncommitted edit vs the base (HEAD)
        code, out = run(self.root, "--dry-run")
        self.assertIn("./app.js?v=a1 -> ?v=a2", out)
        write(self.root, "tools/web_public/newfile.js", "//new\n")                                   # an untracked file nobody references: no ?v= added, no rows
        code, out = run(self.root, "--dry-run")
        self.assertNotIn("newfile", out)

    def test_j_files_new_since_the_base_are_never_bumped_and_reruns_are_stable(self):
        # a file created after the base has no stale copy anywhere; a page created after the base is no evidence of an old tag
        write(self.root, "tools/web_public/fresh/index.html", '<script src="fresh.js?v=n1"></script><script src="../app.js?v=a1"></script>\n')
        write(self.root, "tools/web_public/fresh/fresh.js", "//fresh\n")
        write(self.root, "tools/web_public/fresh2/index.html", '<script src="../olympus/sfx.js?v=s1"></script>\n')
        for _ in range(2):                                                                         # twice: the second run must change nothing more
            code, out = run(self.root, "--apply", changed=["tools/web_public/fresh/fresh.js", "tools/web_public/fresh2/index.html", "tools/web_public/olympus/sfx.js"])
        self.assertIn("fresh.js?v=n1", read(self.root, "tools/web_public/fresh/index.html"))        # new file: untouched
        self.assertIn("new since", out)
        self.assertIn("sfx.js?v=s2", read(self.root, "tools/web_public/jarvis/index.html"))         # an old page still carries it: bumped once
        self.assertNotIn("sfx.js?v=s3", read(self.root, "tools/web_public/jarvis/index.html"))

    def test_i_the_real_tree_is_not_what_the_tests_touch(self):
        self.assertNotEqual(os.path.abspath(self.root), ROOT)
        self.assertTrue(self.root.startswith(tempfile.gettempdir()))


if __name__ == "__main__":
    unittest.main()
