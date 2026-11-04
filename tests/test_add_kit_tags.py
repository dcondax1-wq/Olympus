"""tools/add_kit_tags.py on a synthetic site in a temp dir (never the real tree).

  a. a page that loads the kit and lacks the intro / a11y tags gets exactly the missing ones, each on its own new line right after the
     olympus.js tag, with the tag's indentation and the file's line endings; the intro keeps ?v=i1, a11y has none; --with-css adds the link
  b. never duplicated: a page that has them (before or after the olympus.js tag, with or without ?v=) is not touched; a second run changes nothing
  c. a page with no olympus.js tag (bridge, kalshi, pc, the root) is skipped and listed; an absent page is listed
  d. --check exits 1 while something is missing, 0 after --apply; dry run writes nothing
  e. the root page uses the root-relative path, an app folder uses ../olympus/
  f. a tag sharing its line with other markup: the new tags go on their own lines, the rest moves to its own line (nothing lost)
  g. the Jarvis worker list: the kit files the apps load that the worker does not save, as paste-ready strings
    python -X utf8 -m unittest tests.test_add_kit_tags
"""
from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import add_kit_tags as K  # noqa: E402

APPS_LIST = ('(function (g) { var rows = [\n  {"id": "zenith", "path": ""},\n  {"id": "alpha", "path": "alpha/"},\n  {"id": "beta", "path": "beta/"},\n'
             '  {"id": "gamma", "path": "gamma/"},\n  {"id": "delta", "path": "delta/"},\n  {"id": "eps", "path": "eps/"},\n  {"id": "plan", "path": "plan/"},\n'
             '  {"id": "bridge", "path": "bridge/"}\n  ]; })(this);\n')
OLY = '<script src="../olympus/olympus.js?v=o2" data-app="X"></script>'
FILES = {
    "tools/web_public/olympus/apps-list.js": APPS_LIST,
    "tools/web_public/olympus/olympus.js": "// kit\n", "tools/web_public/olympus/a11y.js": "// a11y\n", "tools/web_public/olympus/a11y.css": "/* a11y */\n",
    "tools/web_public/olympus/intro-app.js": "// intro\n", "tools/web_public/olympus/fx-core.js": "// fx\n", "tools/web_public/olympus/fx-atmos.js": "// atmos\n",
    "tools/web_public/index.html": '<html><head>\n<script src="olympus/olympus.js?v=o2" data-app="zenith"></script>\n</head></html>\n',
    "tools/web_public/alpha/index.html": f"<html><head>\n  {OLY}\n  <link rel=\"stylesheet\" href=\"a.css\">\n</head></html>\n",                      # missing both, indented
    "tools/web_public/beta/index.html": f"<html><head>\n{OLY}\n<script src=\"../olympus/intro-app.js?v=i1\" defer></script>\n</head></html>\n",              # has the intro, lacks a11y
    "tools/web_public/gamma/index.html": ('<html><head>\n<script src="../olympus/a11y.js" defer></script>\n' + OLY + '\n'
                                          '<script src="../olympus/intro-app.js?v=i1" defer></script>\n</head></html>\n'),                                        # a11y BEFORE the kit tag: complete
    "tools/web_public/delta/index.html": ('<html><head>\r\n' + OLY + '<script type="module" src="main.js"></script>\r\n</head></html>\r\n'),                          # CRLF, shares its line
    "tools/web_public/eps/index.html": '<html><head><script src="../olympus/a11y.js?v=a1" defer></script>' + OLY + '<script src="../olympus/intro-app.js" defer></script></head></html>\n',
    "tools/web_public/bridge/index.html": "<html><head><title>no kit</title></head></html>\n",
    "tools/web_public/kalshi/index.html": "<html><head><title>no kit</title></head></html>\n",
    "tools/web_public/jarvis/index.html": '<html><head><script src="../olympus/sfx.js?v=s1"></script></head></html>\n',
    "tools/web_public/jarvis/sw.js": "const CACHE = 'jarvis-v1';\nconst SHELL = ['./', './index.html', '../olympus/sfx.js?v=s1'];\n",
}
# the apps import fx-core / fx-atmos and (alpha) load a11y.css: the worker saves none of them
FILES["tools/web_public/alpha/scene.js"] = "import { x } from '../olympus/fx-atmos.js';\nconst u = '../olympus/fx-core.js?v=f1';\n"


def make():
    root = tempfile.mkdtemp(prefix="kit_tags_")
    for rel, text in FILES.items():
        p = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    return root


def read(root, rel):
    with open(os.path.join(root, *rel.split("/")), encoding="utf-8", newline="") as fh:
        return fh.read()


def run(root, *argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = K.main(["--root", root, *argv])
    return code, buf.getvalue()


class AddKitTags(unittest.TestCase):
    def setUp(self):
        self.root = make()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_a_missing_tags_on_their_own_lines_after_the_kit_tag(self):
        code, out = run(self.root, "--apply")
        self.assertEqual(code, 0, out)
        alpha = read(self.root, "tools/web_public/alpha/index.html")
        self.assertIn(OLY + '\n  <script src="../olympus/intro-app.js?v=i1" defer></script>\n  <script src="../olympus/a11y.js" defer></script>\n  <link rel="stylesheet" href="a.css">', alpha)
        beta = read(self.root, "tools/web_public/beta/index.html")
        self.assertEqual(beta.count("intro-app.js"), 1)                                           # it had one: not duplicated
        self.assertEqual(beta.count("a11y.js"), 1)
        self.assertIn(OLY + '\n<script src="../olympus/a11y.js" defer></script>\n<script src="../olympus/intro-app.js?v=i1"', beta)
        self.assertNotIn("a11y.css", alpha)                                                       # the optional link only with --with-css

    def test_a2_with_css(self):
        run(self.root, "--apply", "--with-css")
        alpha = read(self.root, "tools/web_public/alpha/index.html")
        self.assertIn('<script src="../olympus/a11y.js" defer></script>\n  <link rel="stylesheet" href="../olympus/a11y.css">', alpha)
        self.assertEqual(alpha.count("a11y.css"), 1)

    def test_b_never_duplicated_and_idempotent(self):
        before = {r: read(self.root, r) for r in ("tools/web_public/gamma/index.html", "tools/web_public/eps/index.html")}
        run(self.root, "--apply")
        for rel, text in before.items():                                                          # a11y before the kit tag, a11y?v=a1, intro without ?v=: untouched
            self.assertEqual(read(self.root, rel), text, rel)
        snap = {rel: read(self.root, rel) for rel in FILES}
        code, out = run(self.root, "--apply")
        self.assertEqual(snap, {rel: read(self.root, rel) for rel in FILES})                      # a second run changes nothing
        self.assertIn("0 page(s) missing a tag", out)

    def test_c_no_kit_pages_are_listed_not_touched(self):
        code, out = run(self.root, "--apply")
        for rel in ("tools/web_public/bridge/index.html", "tools/web_public/kalshi/index.html", "tools/web_public/jarvis/index.html"):
            self.assertEqual(read(self.root, rel), FILES[rel])
        self.assertIn("pages with NO olympus.js tag", out)
        for page in ("bridge/index.html", "kalshi/index.html", "jarvis/index.html"):
            self.assertIn(page, out.split("pages with NO olympus.js tag")[1].split("\n")[0])
        self.assertIn("absent", out)                                                              # plan/ has no page

    def test_d_check_and_dry_run(self):
        snap = {rel: read(self.root, rel) for rel in FILES}
        code, out = run(self.root, "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(snap, {rel: read(self.root, rel) for rel in FILES})
        code, out = run(self.root, "--check")
        self.assertEqual(code, 1)
        self.assertIn("CHECK FAILED", out)
        run(self.root, "--apply")
        code, out = run(self.root, "--check")
        self.assertEqual(code, 0, out)

    def test_e_root_page_uses_the_root_relative_path(self):
        run(self.root, "--apply")
        z = read(self.root, "tools/web_public/index.html")
        self.assertIn('<script src="olympus/intro-app.js?v=i1" defer></script>\n<script src="olympus/a11y.js" defer></script>', z)
        self.assertNotIn("../olympus", z)

    def test_f_shared_line_and_crlf(self):
        run(self.root, "--apply")
        d = read(self.root, "tools/web_public/delta/index.html")
        self.assertIn(OLY + '\r\n<script src="../olympus/intro-app.js?v=i1" defer></script>\r\n<script src="../olympus/a11y.js" defer></script>\r\n<script type="module" src="main.js"></script>\r\n', d)
        self.assertNotIn("\r\n\r\n", d)
        self.assertEqual(d.count("\n"), d.count("\r\n"))                                          # the file's line endings kept

    def test_g_the_worker_list(self):
        miss = K.shell_missing(self.root)
        self.assertIn("'../olympus/fx-atmos.js'", miss)
        self.assertIn("'../olympus/fx-core.js?v=f1'", miss)
        self.assertNotIn("'../olympus/sfx.js?v=s1'", miss)                                        # already saved
        out = run(self.root, "--shell")[1]
        self.assertIn("jarvis/sw.js SHELL", out)
        self.assertIn("'../olympus/fx-atmos.js'", out)

    def test_h_not_the_real_tree(self):
        self.assertNotEqual(os.path.abspath(self.root), ROOT)


if __name__ == "__main__":
    unittest.main()
