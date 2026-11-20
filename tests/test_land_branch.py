"""tools/land_branch.py (the lead's landing tool) on throwaway git repos in a temp dir; no network (the 'olympus' remote is a bare repo).

  a. BOT FILES / LEAD-ONLY files / other service workers: every listed pattern matches, the near misses do not
  b. the union resolvers: conflict parsing (merge and diff3 styles); STATE.md union (ours first, order kept, no duplicate line, blank
     lines kept); tests/run_area.py union (a line one side moved is not doubled, a non-AREAS line stops); lines after the main guard
     moved above it (after PARTS / SLOW), other code there reported
  c. decisions.json: cards merged by id, a one-side change taken, a delete kept, a card changed on both sides stops, 'updated' = later
  d. the kalshi fix-up: css/js -> the cache (a merge change), the cache set back (no merge change), consistent: untouched, disagreeing
     tags reported; test pins moved, the release-tool fixtures never
  e. the launcher fix-up: only the apps-list line differs -> both copies byte-identical at the highest lN; a wider difference reported
  f. gate/index.html: a root-relative tag whose file changed but whose ?v did not move is reported (not one that moved / unchanged)
  g. the file -> suite -> area map: own test, path / module / os.path.join mentions, the app's page test, a new AREAS line, browser
     (import, a helper that imports it, node Playwright), --only only when exact, flock lines, bot checks, version-only edits ignored
  h. git end to end: --preview leaves the checkout exactly as it was (HEAD, branch, files, index, no extra worktree, no temp folder)
     and reports clean / auto-resolved / STOP / missing; landing: a manual conflict aborted (checkout as before), a dirty checkout
     refused, the kalshi fix-up after the bump, STATE.md + run_area + decisions.json resolved and committed (no markers, no
     '# Conflicts' in the message), INDEX.md + vault theirs then rebuilt, --run (smoke + the non-browser suite, the smoke file put
     back, the browser suite left as a flock line), --after on a merge finished by hand

  python -X utf8 -m tests.test_land_branch
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import land_branch as LB  # noqa: E402

RES: list[bool] = []
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_TERMINAL_PROMPT": "0"}


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:900]})" if detail and not cond else ""))


def w(root, rel, text):
    p = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def r(root, rel):
    with open(os.path.join(root, *rel.split("/")), encoding="utf-8", newline="") as fh:
        return fh.read()


def g(root, *args):
    p = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout.strip()


def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*a, **k)
    return rc, buf.getvalue()


# ------------------------------------------------------------------------------------------------------------------ a
def part_a():
    bots = ["engine/live.py", "engine/lit_live.py", "engine/lit.py", "engine/ninjatrader.py", "engine/second.py", "engine/account_b.py",
            "engine/autoupdate.py", "engine/generated_files.py", "engine/notify.py", "engine/kalshi_live.py", "engine/kalshi_clock.py",
            "server.py", "live_model.json", "live_model_lit.json", "second_model.json", "accounts/zlarior.json", "scripts/clean_pc.ps1",
            "CLEAN_PC.bat", "tools/web_public/pc/STATUS.bat"]
    near = ["engine/live_site.py", "engine/litx.py", "engine/kalshi/x.py", "tools/server.py", "research/live_model.json", "accounts/a/b.json",
            "scripts/x.sh", "tools/web_public/pc/clean_storage.ps1", "engine/notify_test.py", "second_model.json.bak", "docs/x.bat.md"]
    check("a. every BOT FILE pattern matches (engine files, kalshi_*, server.py, the models, accounts, scripts/*.ps1, any .bat)",
          all(LB.is_bot(p) for p in bots), [p for p in bots if not LB.is_bot(p)])
    check("a. the near misses are not bot files", not any(LB.is_bot(p) for p in near), [p for p in near if LB.is_bot(p)])
    leads = ["tools/web_public/sw.js", "web_next/sw.js", "tools/web_public/kalshi/sw.js", "tools/web_public/jarvis/sw.js",
             "tools/build_web_dashboard.py", "tools/web_public/jarvis/apps.js", "tools/web_public/olympus/olympus.js"]
    near = ["tools/web_public/hub/manual-sw.js", "tools/web_public/apps.js", "tools/web_public/olympus/olympus.css",
            "tools/build_web_dashboard_test.py", "tools/web_public/jarvis/apps.json"]
    check("a. LEAD-ONLY: any sw.js, the build script, jarvis/apps.js, olympus.js", all(LB.is_lead_only(p) for p in leads),
          [p for p in leads if not LB.is_lead_only(p)])
    check("a. not lead-only: manual-sw.js, another apps.js, olympus.css", not any(LB.is_lead_only(p) for p in near),
          [p for p in near if LB.is_lead_only(p)])
    check("a. a service worker that is not a sw.js is named (bump_versions has no rule for its cache)",
          LB.is_other_worker("tools/web_public/hub/manual-sw.js") and LB.is_other_worker("tools/web_public/jarvis/push-sw.js")
          and not LB.is_other_worker("tools/web_public/sw.js") and not LB.is_other_worker("tools/manual-sw.js"))
    check("a. files by top folder: web_public apps apart, root files as (root)",
          LB.by_top(["tools/web_public/kalshi/a.js", "tools/web_public/kalshi/b.js", "tools/x.py", "STATE.md", "tests/t.py"])
          == "web_public/kalshi 2, tools 1, (root) 1, tests 1")


# ------------------------------------------------------------------------------------------------------------------ b
RA_MINI = ('"""mini run_area"""\nimport sys\n\nAREAS = {"pc": ["alpha"], "kalshi": ["beta"]}\nAREAS["pc"].append("gamma")      # its own line\n'
           'PARTS = {"beta": [("one", ["1"])]}\nSLOW = {"beta"}\n\n\ndef suites_for(area):\n    return list(AREAS[area])\n\n\ndef main():\n'
           '    return 0\n\n\nif __name__ == "__main__":\n    sys.exit(main())\n')


def part_b():
    m = LB.parse_conflicts("a\n<<<<<<< ours\nx1\n=======\nx2\n>>>>>>> theirs\nb\n")
    d = LB.parse_conflicts("a\n<<<<<<< ours\nx1\n||||||| base\nx0\n=======\nx2\n>>>>>>> theirs\nb\n")
    check("b. conflict parsing: merge style and diff3 style (the base kept apart)",
          m == [("text", ["a\n"]), ("conflict", ["x1\n"], [], ["x2\n"]), ("text", ["b\n"])]
          and d == [("text", ["a\n"]), ("conflict", ["x1\n"], ["x0\n"], ["x2\n"]), ("text", ["b\n"])], (m, d))
    st = ("# STATE\n## Recent\n<<<<<<< ours\n- ours new\n- shared\n||||||| base\n- old\n=======\n- theirs new\n- shared\n\n- theirs two\n"
          ">>>>>>> theirs\n## Next\n<<<<<<< ours\n- n1\n=======\n- n1\n\n>>>>>>> theirs\n- end")
    text, kept = LB.union_text(st)
    check("b. STATE.md union: ours first, then theirs in order, a shared line once, blank lines kept, a hunk of only duplicates adds nothing",
          text == "# STATE\n## Recent\n- ours new\n- shared\n- theirs new\n\n- theirs two\n## Next\n- n1\n- end" and kept == 2, repr(text))
    t2, _ = LB.union_text("<<<<<<< ours\nlast\n=======\nother\n>>>>>>> theirs\n")
    check("b. union: ours' last line without a newline still ends before theirs", t2 == "last\nother\n", repr(t2))
    ra_conf = RA_MINI.replace('if __name__ == "__main__":\n    sys.exit(main())\n',
                              'if __name__ == "__main__":\n    sys.exit(main())\n<<<<<<< ours\n=======\nAREAS["pc"].append("gamma")      # its own line\n'
                              'AREAS["pc"].append("delta")    # day-x: new\nPARTS["delta"] = [("p", ["2"])]\n>>>>>>> theirs\n')
    t3, kept3 = LB.union_text(ra_conf, file_scope=True, allowed=LB.AREA_LINE.match)
    t3, moved, note = LB.move_tail(t3)
    ns = {"__name__": "x"}
    exec(compile(t3, "run_area", "exec"), ns)
    tail = t3.split('if __name__ == "__main__":\n    sys.exit(main())\n')
    check("b. run_area union: a line ours already has elsewhere (moved up) is not doubled; the new lines kept",
          kept3 == 2 and t3.count('AREAS["pc"].append("gamma")') == 1 and 'append("delta")' in t3, t3)
    check("b. run_area: lines after the main guard move above it, after PARTS / SLOW (so PARTS[...] works), nothing left after it",
          moved == 2 and len(tail) == 2 and tail[1] == "" and t3.index('PARTS["delta"]') > t3.index("SLOW = ")
          and t3.index('PARTS["delta"]') < t3.index("def suites_for") and ns["AREAS"]["pc"] == ["alpha", "gamma", "delta"]
          and ns["PARTS"]["delta"] == [("p", ["2"])], (moved, note, t3))
    try:
        LB.union_text(RA_MINI.replace("def main():\n    return 0\n", "def main():\n<<<<<<< ours\n    return 0\n=======\n    return 1\n>>>>>>> theirs\n"),
                      file_scope=True, allowed=LB.AREA_LINE.match)
        stopped = False
    except LB.Unresolvable as e:
        stopped = "outside the appended lines" in e.why
    check("b. run_area: a conflict inside the code (not an AREAS line) stops", stopped)
    odd = RA_MINI + 'print("x")\n'
    t4, moved4, note4 = LB.move_tail(odd)
    check("b. run_area: other code after the main guard is reported, the file left as it is", t4 == odd and moved4 == 0 and "by hand" in note4, note4)
    t5, moved5, _ = LB.move_tail(RA_MINI)
    check("b. run_area: nothing after the guard -> unchanged", t5 == RA_MINI and moved5 == 0)
    try:
        LB.check_run_area(RA_MINI.replace('AREAS["pc"].append("gamma")', 'AREAS["nope"].append("gamma")'))
        broke = False
    except LB.Unresolvable:
        broke = True
    check("b. run_area: a union that would break the module (KeyError) is refused", broke)


# ------------------------------------------------------------------------------------------------------------------ c
def dec(items, updated="2026-11-19"):
    return json.dumps({"v": 1, "kind": "olympus-decisions", "updated": updated, "note": "n", "items": items}, indent=1) + "\n"


def part_c():
    A, B, C, D, E = ({"id": x, "question": f"{x}?", "status": "open"} for x in "abcde")
    base = dec([A, B, E])
    ours = dec([A, dict(B, status="yes"), E, C], "2026-11-20")                 # ours: b decided, c added
    theirs = dec([dict(A, why="new"), B, D], "2026-11-21")                      # theirs: a edited, e removed, d added
    text, how = LB.merge_decisions(base, ours, theirs)
    dd = json.loads(text)
    check("c. decisions.json: cards merged by id (ours' order, theirs' new card after), each one-side change taken, a delete kept",
          [i["id"] for i in dd["items"]] == ["a", "b", "c", "d"] and dd["items"][0].get("why") == "new" and dd["items"][1]["status"] == "yes",
          [i["id"] for i in dd["items"]])
    check("c. decisions.json: 'updated' changed on both sides -> the later date; the file keeps indent 1 + a final newline",
          dd["updated"] == "2026-11-21" and text == json.dumps(dd, indent=1) + "\n" and list(dd) == ["v", "kind", "updated", "note", "items"])
    check("c. decisions.json: the note says how many cards came from theirs", "+1 of theirs: d" in how, how)
    for label, o, t in (("a card changed on both sides", dec([A, dict(B, status="yes")]), dec([A, dict(B, status="no")])),
                        ("the same new id with different text", dec([A, B, C]), dec([A, B, dict(C, question="other?")]))):
        try:
            LB.merge_decisions(dec([A, B]), o, t)
            ok = False
        except LB.Unresolvable as e:
            ok = "changed on both sides" in e.why
        check(f"c. decisions.json: {label} -> stop and report", ok)
    t2, _ = LB.merge_decisions(dec([A]), dec([A, C]), dec([A, C]))
    check("c. decisions.json: the same card added on both sides identically -> once", [i["id"] for i in json.loads(t2)["items"]] == ["a", "c"])


# ------------------------------------------------------------------------------------------------------------------ d
def kal(root, cache, css, js, shell_css=None, shell_js=None):
    w(root, LB.KAL_IDX, f'<link rel="stylesheet" href="kalshi.css?v={css}">\n<script src="kfx.js?v=k26"></script>\n'
                        f'<script src="kalshi.js?v={js}" defer></script>\n<!-- logic: kalshi.js -->\n')
    w(root, LB.KAL_SW, f"// the page's own versioned files (kalshi.css / kalshi.js ?v=)\nconst CACHE = 'kalshi-{cache}';   // = the css/js ?v\n"
                       f"const SHELL = ['./', './index.html', './kalshi.css?v={shell_css or css}', './kalshi.js?v={shell_js or js}', './kfx.js?v=k27'];\n")


def part_d(tmp):
    root = os.path.join(tmp, "d")
    kal(root, "k45", "k44", "k45")
    w(root, "tests/test_kpin.py", 'PIN = "kalshi.css?v=k44"\n')
    w(root, "tests/test_bump_versions.py", 'FIX = "kalshi.css?v=k44"\n')
    f = LB.fix_kalshi(root, {"tools/web_public/kalshi/kalshi.js"})
    idx, sw = r(root, LB.KAL_IDX), r(root, LB.KAL_SW)
    check("d. kalshi: the bump moved js + cache but not css (kalshi.js changed in the merge) -> css follows in BOTH files",
          "kalshi.css?v=k45" in idx and "kalshi.js?v=k45" in idx and "const CACHE = 'kalshi-k45';" in sw and "'./kalshi.css?v=k45'" in sw
          and "'./kalshi.js?v=k45'" in sw and "kfx.js?v=k26" in idx and "'./kfx.js?v=k27'" in sw and sorted(f.written) == sorted([LB.KAL_IDX, LB.KAL_SW]), (idx, sw))
    check("d. kalshi: a test pin of the old css tag moves, the bump tool's fixture does not",
          'kalshi.css?v=k45' in r(root, "tests/test_kpin.py") and 'kalshi.css?v=k44' in r(root, "tests/test_bump_versions.py"), f.notes)
    kal(root, "k45", "k44", "k44")
    f = LB.fix_kalshi(root, {"tools/web_public/kalshi/kfx.js"})
    idx, sw = r(root, LB.KAL_IDX), r(root, LB.KAL_SW)
    check("d. kalshi: only kfx.js changed (css/js not) -> the cache goes back to the css/js ?v; index.html untouched",
          "const CACHE = 'kalshi-k44';" in sw and "kalshi.css?v=k44" in idx and f.written == [LB.KAL_SW] and f.reverted, (sw, f.notes))
    kal(root, "k45", "k46", "k46", shell_css="k44", shell_js="k44")
    f = LB.fix_kalshi(root, {LB.KAL_IDX})
    idx, sw = r(root, LB.KAL_IDX), r(root, LB.KAL_SW)
    check("d. kalshi: index.html moved to k46 by the helper, SHELL left at k44, cache k45 -> everything k46 (never back to a used tag)",
          "kalshi.css?v=k46" in idx and "'./kalshi.css?v=k46'" in sw and "'./kalshi.js?v=k46'" in sw and "const CACHE = 'kalshi-k46';" in sw, sw)
    kal(root, "k45", "k45", "k45")
    f = LB.fix_kalshi(root, {LB.KAL_IDX})
    check("d. kalshi: consistent -> nothing written", not f.written and not f.notes)
    kal(root, "k46", "k44", "k45")
    f = LB.fix_kalshi(root, set())
    check("d. kalshi: css/js disagree and neither changed in the merge -> reported, nothing written",
          not f.written and f.notes and "by hand" in f.notes[0], f.notes)


# ------------------------------------------------------------------------------------------------------------------ e
LAUNCH = ("/* the Zenith launcher */\nfunction go() {\n    if (!window.OLYMPUS_APPS_LIST) add(isPC ? '/js/next/apps-list.js?v=PC' : "
          "'olympus/apps-list.js?v=PH');\n}\n")


def lau(pc, ph):
    return LAUNCH.replace("=PC'", f"={pc}'").replace("=PH'", f"={ph}'")


def part_e(tmp):
    root = os.path.join(tmp, "e")
    w(root, LB.LAUNCHERS[0], lau("l8", "o11"))
    w(root, LB.LAUNCHERS[1], lau("l9", "l8"))
    f = LB.fix_launcher(root)
    a, b = r(root, LB.LAUNCHERS[0]), r(root, LB.LAUNCHERS[1])
    check("e. launcher: the copies differ only in the apps-list line -> both sides of the ternary in both files = the highest lN (l9)",
          a == b == lau("l9", "l9") and len(f.written) == 2 and "l9" in f.notes[0], (a, f.notes))
    f = LB.fix_launcher(root)
    check("e. launcher: byte-identical and consistent -> nothing to do", not f.written and not f.notes)
    w(root, LB.LAUNCHERS[0], lau("l9", "o11"))
    w(root, LB.LAUNCHERS[1], lau("l9", "o11"))
    f = LB.fix_launcher(root)
    check("e. launcher: identical but the two sides disagree (the o-tag mis-bump) -> l9 on both sides",
          r(root, LB.LAUNCHERS[0]) == r(root, LB.LAUNCHERS[1]) == lau("l9", "l9"), f.notes)
    w(root, LB.LAUNCHERS[1], lau("l10", "l9").replace("function go()", "function went()"))
    f = LB.fix_launcher(root)
    check("e. launcher: the copies differ beyond that line -> reported, nothing written",
          not f.written and f.notes and "beyond the apps-list line" in f.notes[0], f.notes)


# ------------------------------------------------------------------------------------------------------------------ f
def gate_html(themes, gate):
    return ("<script>(function () {\n  var b = /\\/gate\\/(index\\.html)?$/.test(location.pathname) ? '../' : '';\n"
            "  var l = document.createElement('link'); l.href = b + 'olympus/shell.css?v=s3';\n"
            f"  ['olympus/themes.js?v={themes}', 'pc_feed.js?v=pf1', 'gate/gate.js?v={gate}'].forEach(function (src) {{ }});\n}})();</script>\n")


def part_f(tmp):
    root = os.path.join(tmp, "f")
    os.makedirs(root)
    g(root, "init", "-q", "-b", "pc")
    w(root, LB.GATE, gate_html("o9", "g9"))
    w(root, "tools/web_public/hub/index.html", '<link rel="stylesheet" href="../olympus/shell.css?v=s4">\n')
    for rel in ("tools/web_public/olympus/themes.js", "tools/web_public/gate/gate.js", "tools/web_public/pc_feed.js", "tools/web_public/olympus/shell.css"):
        w(root, rel, "x\n")
    g(root, "add", "-A")
    g(root, "commit", "-q", "-m", "base")
    base = g(root, "rev-parse", "HEAD")
    for rel in ("tools/web_public/olympus/themes.js", "tools/web_public/gate/gate.js", "tools/web_public/olympus/shell.css"):
        w(root, rel, "y\n")
    w(root, "tools/web_public/hub/index.html", '<link rel="stylesheet" href="../olympus/shell.css?v=s5">\n')     # what the bump wrote
    w(root, LB.GATE, gate_html("o10", "g9"))
    notes = LB.check_gate(root, LB.Git(root), base, set(LB.Git(root).changed_since(base)))
    check("f. gate: gate.js changed, ?v not moved -> the next tag (g10); shell.css -> s5 as the other pages (never s4, an old copy's tag);"
          " themes.js moved and pc_feed.js unchanged: quiet",
          len(notes) == 2 and any("'gate/gate.js?v=g9'" in n and "?v=g10 " in n for n in notes)
          and any("'olympus/shell.css?v=s3'" in n and "?v=s5 in gate/index.html, as the other pages" in n for n in notes), notes)
    apply_t = ("what  where  change\n----  -----  ------\nquery  tools/web_public/dionysus/index.html  dionysus.css?v=a2 -> ?v=a3\n"
               "worker  tools/web_public/sw.js  cache le-public-v1 -> le-public-v2  (phone root)\napplied: 2 file(s) written, 2 change(s).\n")
    loop = LB.rebump_loop(apply_t, ["query  tools/web_public/dionysus/index.html  dionysus.css?v=a3 -> ?v=a4", "pin  tests/t.py:3  x"])
    real = LB.rebump_loop(apply_t, ["query  tools/web_public/dionysus/index.html  dionysus.css?v=a3 -> ?v=a4",
                                    "query  tools/web_public/nq/index.html  nq.js?v=n1 -> ?v=n2"])
    check("f. bump --check that only re-bumps what --apply just bumped (an unreadable base tag) is told apart from a real miss",
          loop == ["dionysus/index.html dionysus.css"] and real == [], (loop, real))


# ------------------------------------------------------------------------------------------------------------------ g
RA_PLAN = ('import os\nROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
           'AREAS = {"kalshi": ["kalshi_page", "kalshi_pagex", "kalshi_publish"], "pc": ["autoupdate", "kalshi_publish", "helperuser"], "nq": ["lit_live"]}\n'
           'PARTS = {}\nSLOW = set()\n\n\ndef suites_for(area):\n'
           '    return [n for n in AREAS[area] if os.path.isfile(os.path.join(ROOT, "tests", f"test_{n}.py"))]\n')


def part_g(tmp):
    root = os.path.join(tmp, "g")
    os.makedirs(root)
    w(root, "tests/run_area.py", RA_PLAN)
    w(root, "tests/test_kalshi_page.py", 'def page():\n    from playwright.sync_api import sync_playwright\n    return "tools/web_public/kalshi/kalshi.js"\n')
    w(root, "tests/test_kalshi_pagex.py", "X = 1\n")
    w(root, "tests/test_kalshi_publish.py", "from engine import clock, kalshi_publish\n")
    w(root, "tests/test_autoupdate.py", 'import os\nP = os.path.join(ROOT, "engine", "autoupdate.py")\n')
    w(root, "tests/helper_kit.py", "from playwright.sync_api import sync_playwright\n")
    w(root, "tests/test_helperuser.py", 'from tests import helper_kit\nT = "tools/x_tool.py"\n')
    w(root, "tests/test_nodepw.py", 'import os\nG = os.path.join("groot", "playwright")\nP = "tools/web_public/nodepage/app.js"\n')
    w(root, "tests/test_lit_live.py", "X = 2\n")
    w(root, "tests/test_unrelated.py", 'P = "tools/other.py"\n')
    w(root, "tests/test_sweater.py", 'P = "tools/web_public/sw.js"\n')
    w(root, "tests/test_rapid_tool.py", "import rapid_tool\n")
    w(root, "tests/test_bump_versions.py", 'FIXTURE = {"tools/web_public/kalshi/kalshi.js": "x", "engine/autoupdate.py": "y"}\n')
    w(root, "tools/web_public/sw.js", "const CACHE = 'le-public-v1';\n")
    w(root, "tools/web_public/index.html", '<script src="launcher.js?v=l1"></script>\n')
    for rel in ("tools/web_public/kalshi/kalshi.js", "engine/kalshi_publish.py", "engine/autoupdate.py", "tools/x_tool.py", "tools/other.py",
                "tools/web_public/nodepage/app.js", "tools/rapid_tool.py"):
        w(root, rel, "x\n")
    g(root, "init", "-q", "-b", "pc")
    g(root, "add", "-A")
    g(root, "commit", "-q", "-m", "base")
    base = g(root, "rev-parse", "HEAD")
    w(root, "tools/web_public/sw.js", "const CACHE = 'le-public-v2';\n")
    w(root, "tools/web_public/index.html", '<script src="launcher.js?v=l2"></script>\n')
    git = LB.Git(root)
    vo = LB.version_only(git, base, root, ["tools/web_public/sw.js", "tools/web_public/index.html"])
    check("g. version-only edits (?v= and cache names, what the bump writes) are recognised", vo == {"tools/web_public/sw.js", "tools/web_public/index.html"}, vo)
    w(root, "tools/web_public/index.html", '<script src="launcher.js?v=l2"></script>\n<p>new</p>\n')
    check("g. a real edit next to a ?v= move is not version-only", LB.version_only(git, base, root, ["tools/web_public/index.html"]) == set())
    changed = ["tools/web_public/kalshi/kalshi.js", "engine/kalshi_publish.py", "engine/autoupdate.py", "tools/x_tool.py", "tests/test_lit_live.py",
               "tools/web_public/sw.js", "tools/web_public/nodepage/app.js", "tools/rapid_tool.py"]
    plan = LB.make_plan(root, changed, skip={"tools/web_public/sw.js"})
    want = {"kalshi_page", "kalshi_publish", "autoupdate", "helperuser", "lit_live", "nodepw", "rapid_tool"}
    check("g. suites: the page test (path), module import, os.path.join, a helper's user, its own test, node Playwright, `import x`",
          set(plan.suites) == want, sorted(plan.suites))
    check("g. not named: a suite that mentions another file, one that only reads the version-bumped sw.js, a release tool's fixture test "
          "whose mini repo names the same paths", "unrelated" not in plan.suites and "sweater" not in plan.suites and "bump_versions" not in plan.suites)
    check("g. a release tool's fixture test still runs when its tool changes", "bump_versions" in LB.make_plan(root, ["tools/bump_versions.py"]).suites)
    check("g. browser: playwright import, a tests/ helper that imports it, node Playwright; not the plain ones",
          plan.browser == {"kalshi_page", "helperuser", "nodepw"}, sorted(plan.browser))
    check("g. areas: a suite in two areas goes to the area with more of the plan (kalshi_publish -> pc); no area for the rest",
          plan.area["kalshi_publish"] == "pc" and plan.area["kalshi_page"] == "kalshi" and plan.area["nodepw"] == "" and plan.area["lit_live"] == "nq",
          plan.area)
    c = plan.commands
    loop = f'for s in kalshi_page nodepw; do {LB.LOCK} python -X utf8 -m tests.test_$s || echo "FAILED $s"; done'
    check("g. commands: smoke first, then the non-browser area lines (--only exact), then the browser ones under the lock",
          c[0] == "python tests/smoke.py" and "python tests/run_area.py pc --only kalshi_publish,autoupdate" in c
          and "python tests/run_area.py nq --only lit_live" in c and "python -X utf8 -m tests.test_rapid_tool" in c
          and f"{LB.LOCK} python tests/run_area.py pc --only helperuser" in c and loop in c
          and max(c.index(x) for x in c if LB.LOCK not in x and "lit_live --quick" not in x and "ninjatrader" not in x)
          < min(c.index(x) for x in c if LB.LOCK in x), c)
    check("g. --only is a substring match: when it would also pick kalshi_pagex, kalshi_page joins the one loop line (lock per suite)",
          loop in c and not any("--only kalshi_page" in x for x in c), c)
    plan.parts = {"nodepw": [("a", ["x"]), ("b", ["y", "z"])]}
    cp = LB.plan_commands(plan, LB.load_run_area(root), LB.load_run_area(root).AREAS)
    check("g. a suite run by parts outside an exact area line: one line per part with its arguments",
          f"{LB.LOCK} python -X utf8 -m tests.test_nodepw x" in cp and f"{LB.LOCK} python -X utf8 -m tests.test_nodepw y z" in cp
          and f"{LB.LOCK} python -X utf8 -m tests.test_kalshi_page" in cp, cp)
    check("g. a bot file changed (engine/autoupdate.py, engine/kalshi_*.py) -> the two bot checks end the list",
          c[-2:] == ["python -X utf8 -m tests.test_lit_live --quick", "python -m engine.ninjatrader --selftest"]
          and sorted(plan.bot) == ["engine/autoupdate.py", "engine/kalshi_publish.py"], c[-3:])
    pw = "play" "wright"
    cases = {"import": f"import {pw}  # noqa: F401\n", "node": f'import os\nP = os.path.join(G, "{pw}")\n',
             "docstring": f'"""no {pw.title()} here: the browser\'s own --screenshot"""\n# a {pw} comment\n',
             "fixture": f"T = 'def x():\\n    from {pw}.sync_api import sync_{pw}\\n'\n", "unreadable": f'"""{pw} never closed\n'}
    got = {k: LB.uses_playwright(v) for k, v in cases.items()}
    check("g. Playwright use, not a mention: import / node module path count; a docstring, a comment, a fixture string do not; "
          "unreadable counts", got == {"import": True, "node": True, "docstring": False, "fixture": False, "unreadable": True}, got)
    w(root, "tools/shooter.py", f"from {pw}.sync_api import sync_{pw}\n")
    w(root, "tests/test_shots_tool.py", "from tools import shooter\n")
    w(root, "tests/test_doc_only.py", cases["docstring"])
    bs = LB.browser_suites(LB.test_texts(root), root)
    check("g. a suite importing a repo module that drives Playwright is a browser suite; one whose docstring only names it is not",
          "shots_tool" in bs and "doc_only" not in bs and "kalshi_publish" not in bs, sorted(bs))
    p2 = LB.make_plan(root, ["tests/run_area.py"], base_areas={"kalshi": ["kalshi_page"], "pc": ["autoupdate"]})
    check("g. a suite newly registered in tests/run_area.py is in the plan (run_area itself names nothing else)",
          set(p2.suites) == {"kalshi_pagex", "kalshi_publish", "helperuser", "lit_live"}, sorted(p2.suites))
    p3 = LB.make_plan(root, ["docs/notes.md"])
    check("g. a docs-only change: smoke only, no bot checks", p3.commands == ["python tests/smoke.py"] and not p3.suites, p3.commands)


# ------------------------------------------------------------------------------------------------------------------ h
BUMP_STUB = '''import os, subprocess, sys
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = sys.argv[1:]
base = args[args.index("--base") + 1]
changed = subprocess.run(["git", "-C", root, "diff", "--name-only", base], capture_output=True, text=True).stdout.split()
sw, idx = os.path.join(root, "tools/web_public/kalshi/sw.js"), os.path.join(root, "tools/web_public/kalshi/index.html")
if "--apply" in args and "tools/web_public/kalshi/kalshi.js" in changed and "kalshi.js?v=k44" in open(sw).read():
    # the real tool when only kalshi.js changed: its ?v moves, the cache follows the highest tag, kalshi.css stays
    t = open(sw).read().replace("kalshi.js?v=k44", "kalshi.js?v=k45").replace("'kalshi-k44'", "'kalshi-k45'")
    open(sw, "w").write(t)
    t = open(idx).read().replace("kalshi.js?v=k44", "kalshi.js?v=k45")
    open(idx, "w").write(t)
    print("what   where                                change")
    print("-----  -----------------------------------  ------")
    print("query  tools/web_public/kalshi/index.html   kalshi.js?v=k44 -> ?v=k45")
    print("applied: 2 file(s) written, 3 change(s).")
    sys.exit(0)
print("nothing needs a bump.")
print("check ok." if "--check" in args else "applied: 0 file(s) written, 0 change(s).")
'''
INDEX_STUB = '''import os, sys
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
wd = os.path.join(root, "research", "writeups")
text = "# index\\n" + "".join(f"- {f}\\n" for f in sorted(os.listdir(wd)) if f.endswith(".md") and f != "INDEX.md")
out = os.path.join(wd, "INDEX.md")
if "--check" in sys.argv:
    sys.exit(0 if open(out).read() == text else 1)
open(out, "w").write(text)
print("INDEX.md written")
'''
BRAIN_STUB = '''import os, sys
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
wd = os.path.join(root, "research", "writeups")
notes = {"ZEUS Home.md": "# home\\n" + "".join(f"- {f}\\n" for f in sorted(os.listdir(wd)) if f.endswith(".md") and f != "INDEX.md"),
         "ZEUS State.md": open(os.path.join(root, "STATE.md")).read()}
vd = os.path.join(root, "vault", "ZEUS Brain")
if "--check" in sys.argv:
    sys.exit(0 if all(os.path.isfile(os.path.join(vd, n)) and open(os.path.join(vd, n)).read() == t for n, t in notes.items()) else 1)
os.makedirs(vd, exist_ok=True)
for n, t in notes.items():
    open(os.path.join(vd, n), "w").write(t)
print("vault built")
'''
SMOKE_STUB = '''import os
p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "GEX_1d.csv")
open(p, "a").write("3,4\\n")      # like the real smoke: it rewrites this file
print("[OK ] tests.test_alpha   0s")
print("smoke: 1/1 green in 0s")
'''
STATE0 = "# STATE\n\n## Recent findings (newest first)\n- base finding\n\n## Next\n- base next\n"


def tree_hash(root):
    """Every file of the checkout (not .git) by path and bytes."""
    files = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d != ".git"]
        files += [os.path.join(dp, fn) for fn in fns]
    h = hashlib.sha256()
    for p in sorted(files):
        h.update(os.path.relpath(p, root).encode() + b"\0")
        with open(p, "rb") as fh:
            h.update(fh.read())
    return h.hexdigest()


def commit_all(root, msg):
    g(root, "add", "-A")
    g(root, "commit", "-q", "-m", msg)


def regen(root):
    for tool in ("tools/writeups_index.py", "tools/obsidian_brain.py"):
        subprocess.run([sys.executable, tool], cwd=root, capture_output=True, check=True)


def make_repo(tmp):
    bare, work = os.path.join(tmp, "remote.git"), os.path.join(tmp, "work")
    subprocess.run(["git", "init", "-q", "--bare", "-b", "pc", bare], check=True)
    os.makedirs(work)
    g(work, "init", "-q", "-b", "pc")
    g(work, "remote", "add", "olympus", bare)
    w(work, "STATE.md", STATE0)
    w(work, "tests/__init__.py", "")
    with open(os.path.join(ROOT, "tests", "run_area.py"), encoding="utf-8") as fh:
        w(work, "tests/run_area.py", fh.read())                     # the real runner (its run_one runs the suites below)
    w(work, "tests/smoke.py", SMOKE_STUB)
    w(work, "tests/test_alpha.py", 'T = "tools/alpha.py"\nprint("[PASS] alpha works")\nprint("1/1 passed")\n')
    w(work, "tests/test_beta.py", 'T = "tools/alpha.py"\n\n\ndef page():\n    from playwright.sync_api import sync_playwright\n')
    w(work, "data/GEX_1d.csv", "a,b\n1,2\n")
    w(work, "tools/alpha.py", "X = 1\n")
    w(work, "tools/x.py", "A = 1\n")
    w(work, "tools/bump_versions.py", BUMP_STUB)
    w(work, "tools/writeups_index.py", INDEX_STUB)
    w(work, "tools/obsidian_brain.py", BRAIN_STUB)
    w(work, "research/writeups/a.md", "# a\n")
    w(work, LB.DECISIONS, dec([{"id": "a", "status": "open"}, {"id": "b", "status": "open"}]))
    kal(work, "k44", "k44", "k44")
    w(work, "tools/web_public/kalshi/kalshi.js", "// kalshi\n")
    w(work, "tools/web_public/kalshi/kalshi.css", "/* kalshi */\n")
    regen(work)
    commit_all(work, "base")
    g(work, "push", "-q", "olympus", "pc")
    base = g(work, "rev-parse", "HEAD")
    day = LB.today_et()

    def branch(name, fn):
        g(work, "checkout", "-q", "-b", name, base)
        fn()
        commit_all(work, name)
        g(work, "push", "-q", "olympus", name)
        g(work, "checkout", "-q", "pc")
        g(work, "branch", "-q", "-D", name)

    def clean():
        w(work, "tools/alpha2.py", "Y = 1\n")
        w(work, "tools/web_public/kalshi/kalshi.js", "// kalshi, better\n")
        w(work, f"research/handoff/{day}/clean/LEAD_WIRES.md", "# wires\n")

    def auto():
        w(work, "STATE.md", STATE0.replace("- base finding", "- auto finding\n- base finding"))
        ra = r(work, "tests/run_area.py")
        anchor = ra.splitlines(keepends=True)[[i for i, x in enumerate(ra.splitlines()) if x.startswith("AREAS[")][-1]]
        w(work, "tests/run_area.py", ra.replace(anchor, anchor + 'AREAS["pc"].append("alpha")    # day-auto: its own line\n')
          + 'AREAS["nq"].append("alpha")    # day-auto: appended after the main guard (never runs as a script)\n')
        w(work, LB.DECISIONS, dec([{"id": "a", "status": "open"}, {"id": "b", "status": "open"}, {"id": "c", "status": "open"}]))

    def manual():
        w(work, "tools/x.py", "A = 3\n")

    def gen():
        w(work, "research/writeups/b.md", "# b\n")
        regen(work)

    for nm, fn in (("day-clean", clean), ("day-auto", auto), ("day-manual", manual), ("day-gen", gen), ("day-run", lambda: w(work, "tools/alpha.py", "X = 2\n"))):
        branch(nm, fn)
    # pc moves on meanwhile (the lead landed other branches): the same spots as the helpers
    w(work, "STATE.md", STATE0.replace("- base finding", "- pc finding\n- base finding"))
    ra = r(work, "tests/run_area.py")
    anchor = ra.splitlines(keepends=True)[[i for i, x in enumerate(ra.splitlines()) if x.startswith("AREAS[")][-1]]
    w(work, "tests/run_area.py", ra.replace(anchor, anchor + 'AREAS["nq"].append("beta")     # pc: its own line\n'))
    w(work, LB.DECISIONS, dec([{"id": "a", "status": "open"}, {"id": "b", "status": "yes"}]))
    w(work, "tools/x.py", "A = 2\n")
    w(work, "research/writeups/c.md", "# c\n")
    regen(work)
    commit_all(work, "pc moves on")
    return work


def part_h(tmp):
    work = make_repo(tmp)
    git = LB.Git(work)
    head0, br0, h0 = g(work, "rev-parse", "HEAD"), g(work, "branch", "--show-current"), tree_hash(work)
    idx0 = g(work, "ls-files", "-s")
    tmp_before = {d for d in os.listdir(tempfile.gettempdir()) if d.startswith("land-preview-")}
    rc, out = quiet(LB.preview, work, ["day-clean", "day-auto", "day-manual", "day-gen", "day-missing"])
    tmp_after = {d for d in os.listdir(tempfile.gettempdir()) if d.startswith("land-preview-")}
    check("h. --preview: the checkout is exactly as before (HEAD, branch, every file, the index), no worktree left, no temp folder left",
          g(work, "rev-parse", "HEAD") == head0 and g(work, "branch", "--show-current") == br0 and tree_hash(work) == h0
          and g(work, "ls-files", "-s") == idx0 and len(g(work, "worktree", "list").splitlines()) == 1 and not git.merging()
          and tmp_after <= tmp_before, out)
    blocks = out.split("\n[")
    blk = {b.split("]", 1)[1].split()[0].rstrip(":"): b for b in blocks[1:]}
    check("h. --preview: day-clean clean, with its LEAD_WIRES.md and the kalshi fix-up after the bump",
          "merge: clean" in blk.get("day-clean", "") and "/clean/LEAD_WIRES.md" in blk["day-clean"] and "kalshi: css/js" in blk["day-clean"], out)
    check("h. --preview: day-auto: STATE.md, tests/run_area.py, decisions.json resolved on their own",
          all(x in blk.get("day-auto", "") for x in ("conflicts resolved", "STATE.md union", "tests/run_area.py union", "decisions.json cards by id")), out)
    check("h. --preview: day-manual STOP with its file; day-gen resolved (INDEX + vault rebuilt); day-missing skipped; exit 2",
          "STOP" in blk.get("day-manual", "") and "tools/x.py" in blk["day-manual"] and "rebuilt by tools/writeups_index.py" in blk.get("day-gen", "")
          and "rebuilt by tools/obsidian_brain.py" in blk["day-gen"] and "SKIP" in blk.get("day-missing", "") and rc == 2
          and "1 STOP (day-manual)" in out, out)
    check("h. --preview: per branch output stays short (< 60 lines)", all(len(b.splitlines()) < 60 for b in blocks), [len(b.splitlines()) for b in blocks])

    rc, out = quiet(LB.land, work, "day-manual")
    check("h. land: a conflict outside the known files -> merge --abort, the files named, exit 2, the checkout as before",
          rc == 2 and "tools/x.py" in out and "STOP" in out and g(work, "rev-parse", "HEAD") == head0 and not git.status() and not git.merging(), out)
    w(work, "tools/alpha.py", "X = 99\n")
    rc, out = quiet(LB.land, work, "day-clean")
    check("h. land: a dirty checkout is refused before anything", rc == 2 and "not clean" in out and g(work, "rev-parse", "HEAD") == head0, out)
    g(work, "checkout", "--", "tools/alpha.py")

    rc, out = quiet(LB.land, work, "day-clean")
    parents = g(work, "log", "-1", "--format=%P").split()
    idx, sw = r(work, LB.KAL_IDX), r(work, LB.KAL_SW)
    check("h. land day-clean: merged (a merge commit), the bump ran, the kalshi fix-up moved css to the cache's k45, left uncommitted",
          rc == 0 and len(parents) == 2 and "kalshi.css?v=k45" in idx and "const CACHE = 'kalshi-k45';" in sw and "'./kalshi.css?v=k45'" in sw
          and {p for _, p in git.status()} == {LB.KAL_IDX, LB.KAL_SW} and "undo: git reset --hard" in out and "wires:" in out, out)
    check("h. land: the plan and the commit hint are printed", "tests: smoke" in out and "python tests/smoke.py" in out and "git add -A tools" in out, out)
    commit_all(work, "land day-clean: bump + fix-ups")

    rc, out = quiet(LB.land, work, "day-auto")
    st, ra = r(work, "STATE.md"), r(work, "tests/run_area.py")
    d = json.loads(r(work, LB.DECISIONS))
    msg = g(work, "log", "-1", "--format=%B")
    tail = ra.split('if __name__ == "__main__":\n    sys.exit(main())\n')
    check("h. land day-auto: STATE.md keeps both new lines (ours first), no conflict marker",
          rc == 0 and "- pc finding\n- auto finding\n- base finding" in st and "<<<<<<<" not in st and ">>>>>>>" not in st, (out, st))
    check("h. land day-auto: run_area has both AREAS lines, the one after the main guard moved above it, and it still runs",
          'AREAS["nq"].append("beta")' in ra and 'AREAS["pc"].append("alpha")' in ra and 'AREAS["nq"].append("alpha")' in ra
          and len(tail) == 2 and tail[1] == "" and "<<<<<<<" not in ra and "alpha" in LB.load_run_area(work).AREAS["nq"], tail[-1][-300:])
    check("h. land day-auto: decisions.json = pc's 'b yes' + their new card c; the merge is committed without '# Conflicts' lines",
          [(i["id"], i["status"]) for i in d["items"]] == [("a", "open"), ("b", "yes"), ("c", "open")]
          and len(g(work, "log", "-1", "--format=%P").split()) == 2 and "Conflicts" not in msg and not git.merging(), (d, msg))
    if git.status():
        commit_all(work, "land day-auto")

    rc, out = quiet(LB.land, work, "day-gen")
    check("h. land day-gen: INDEX.md and the vault taken from theirs, then rebuilt from the merged write-ups (a, b, c)",
          rc == 0 and r(work, "research/writeups/INDEX.md") == "# index\n- a.md\n- b.md\n- c.md\n"
          and r(work, "vault/ZEUS Brain/ZEUS Home.md") == "# home\n- a.md\n- b.md\n- c.md\n" and not git.merging(), out)
    if git.status():
        commit_all(work, "land day-gen")

    g(work, "checkout", "-q", "-b", "elsewhere")              # someone pushed pc from another checkout meanwhile
    w(work, "docs/other.md", "x\n")
    commit_all(work, "pushed from elsewhere")
    g(work, "push", "-q", "-f", "olympus", "elsewhere:pc")
    g(work, "checkout", "-q", "pc")
    rc, out = quiet(LB.land, work, "day-run", run=True)
    check("h. land: the merge message is git's own for the remote branch; a pc on the remote ahead of HEAD is pointed out",
          "Merge remote-tracking branch 'olympus/day-run'" in g(work, "log", "-1", "--format=%s")
          and "NOTE: olympus/pc has 1 commit(s) this checkout does not" in out, out)
    check("h. land --run: smoke and the non-browser suite ran (one line each), the browser suite stays a flock line",
          rc == 0 and "smoke: 1/1 PASS" in out and "alpha: 1/1 PASS" in out and f"{LB.LOCK} python tests/run_area.py nq --only beta" in out
          and "beta:" not in out.split("run (non-browser")[-1], out)
    check("h. land --run: the file smoke rewrites (data/GEX_1d.csv) is put back", "put back" in out and "data/GEX_1d.csv" not in {p for _, p in git.status()}, out)

    g(work, "checkout", "-q", "-b", "side", "pc~0")
    base = g(work, "rev-parse", "HEAD")
    g(work, "fetch", "-q", "olympus", "day-manual")
    subprocess.run(["git", "-C", work, "merge", "-q", "--no-edit", "FETCH_HEAD"], capture_output=True)
    w(work, "tools/x.py", "A = 23\n")
    g(work, "add", "tools/x.py")
    g(work, "commit", "-q", "--no-edit")
    rc, out = quiet(LB.main, ["--after", base, "--root", work])
    check("h. --after BASE on a merge finished by hand: bump, fix-ups and the plan", rc == 0 and "bump:" in out and "fix-ups:" in out and "tests: smoke" in out, out)


def main() -> int:
    saved = {k: os.environ.get(k) for k in GIT_ENV}
    os.environ.update(GIT_ENV)
    tmp = tempfile.mkdtemp(prefix="test-land-branch-")
    try:
        part_a()
        part_b()
        part_c()
        part_d(tmp)
        part_e(tmp)
        part_f(tmp)
        part_g(tmp)
        part_h(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


def test_land_branch():                 # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
