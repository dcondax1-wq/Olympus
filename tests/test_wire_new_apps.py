"""tools/wire_new_apps.py + tools/new_apps.json (2026-11-10): the lead's wiring of the new OLYMPUS apps, done safely and idempotently.

  a. the app list: every entry is valid and matches its section of docs/NEW_APPS_WIRING.md (name, group, accent, glyph, bed, intro, transition)
  b. on a small copy of the six files (same anchors as the real ones): --dry-run writes nothing, --check exits 1, --apply adds exactly the missing rows, a second apply and --check are clean (idempotent),
     existing rows are never touched (only insertions), only apps with a folder + index.html are wired (a later folder is picked up), the sw.js CACHE is not bumped, the style is kept
  c. it REFUSES (exit 2, nothing written in ANY file) when an anchor is gone, the list is broken, a group / colour / id is wrong, an id is listed twice, or a file has Windows line endings
  d. on a copy of the REAL six files: it plans without refusing, the result still parses (node --check, python compile), and a second apply is a no-op; the real tree is never written
    python -X utf8 -m tests.test_wire_new_apps
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import wire_new_apps as W  # noqa: E402

RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = W.main(list(args))
    return code, out.getvalue(), err.getvalue()


# ------------------------------------------------------------------------------------------------ a small repo with the same anchors
APPS_JS = """const BUILT_INS = [
  app('planner', 'Planner', 'life', '#7fa7c2', 'Day and week plan', { glyph: 'Π' }),
  app('pnyx', 'Pnyx', 'money', '#c8a24a', 'Prop-firm rules and risk calculator: stop to micros', { glyph: 'Π' }),
  app('clio', 'Clio', 'trading', '#d8c9a8', 'The research library: every study in plain words', { glyph: 'Κ' }),
  app('atlas', 'Atlas', 'life', '#efc979', 'A fast map', { glyph: '\\u25c8' }),
];
"""
OLYMPUS_JS = """(function () {
  var APPS = {
    datacity: ['Data City', 'Δ', '#4f8cff'], pnyx: ['Pnyx', 'Π', '#c8a24a'],
    atlas: ['Atlas', '◈', '#efc979']
  };
  // ---- ambience
  var AMBIENT = { pnyx: 'coins', clio: 'scroll', datacity: 'city',
    odeon: 'crowd' };
  var x = 1;
})();
"""
BUILD_PY = """def build():
    for app in ("jarvis", "kalshi", "pnyx", "clio"):
        src_dir = os.path.join(WEB, app)
"""
SW_JS = """const CACHE = 'le-dash-v100';
const OTHER_APPS = ['jarvis/', 'pnyx/', 'clio/']; // own folders
const SHELL = ['./'];
"""
INTRO_JS = """(function () {
  var FLAVOUR = {
    datacity: ['skyline', 'Your numbers, rising', 'portal'], pnyx: ['columns', 'Count the risk', 'tap'],
    clio: ['threads', 'The record', 'tick']
  };
  var SC = {};
  SC.stars = { init: function () {} };
  SC.coins = { init: function () {} };
  SC.columns = { init: function () {} };
  SC.rings = { init: function () {} };
  SC.threads = { init: function () {} };
})();
"""
TRANS_JS = """export const KINDS = {
  tiles: { init() {} },
  columns: { init() {} },
  sunburst: { init() {} },
};
export const REGISTRY = {
  zenith:     { kind: 'marble',        ms: 900 },
  pnyx:       { kind: 'columns',       ms: 1000, n: 5 },
  clio:       { kind: 'tiles',         ms: 820 },
  atlas:      { kind: 'sunburst',      ms: 900 },
};
"""
SFX_JS = """  var BEDS = {
      coins: function () {},
      chimes: function () {},
      scroll: function () {},
    };
"""
REL = {"apps": W.FILES["apps"], "olympus": W.FILES["olympus"], "build": W.FILES["build"], "sw": W.FILES["sw"], "intro": W.FILES["intro"], "trans": W.FILES["trans"]}
BODY = {"apps": APPS_JS, "olympus": OLYMPUS_JS, "build": BUILD_PY, "sw": SW_JS, "intro": INTRO_JS, "trans": TRANS_JS}
LIST = {"apps": [
    {"id": "pnyx", "name": "Pnyx", "group": "money", "accent": "#c8a24a", "glyph": "Π", "description": "Prop-firm rules and risk calculator: stop to micros", "ambient": "coins", "flavour": ["columns", "Count the risk", "tap"], "transition": {"kind": "columns", "ms": 1000, "n": 5}},
    {"id": "mint", "name": "Mint", "group": "money", "accent": "#c8a24a", "glyph": "M", "description": "The money machine: five streams", "ambient": "coins", "flavour": ["columns", "Strike the coin", "tap"], "transition": {"kind": "columns", "ms": 1000, "n": 5}},
    {"id": "mintcity", "name": "Mint City", "group": "money", "accent": "#c8a24a", "glyph": "MC", "description": "The five money machines as a marble city", "ambient": "coins", "flavour": ["columns", "Raise the city", "tick"], "transition": {"kind": "columns", "ms": 1000, "n": 5}},
    {"id": "stoa", "name": "Stoa", "group": "trading", "accent": "#c8a24a", "glyph": "Σ", "description": "The colonnade: what needs you right now", "ambient": "chimes", "flavour": ["rings", "Light the columns", "tick"], "transition": {"kind": "sunburst", "ms": 1000}},
    {"id": "nike", "name": "Nike", "group": "life", "accent": "#4b7a99", "glyph": "Ν", "description": "Don't stop: the trophy hall", "ambient": "chimes", "flavour": ["rings", "Count your wins", "tap"], "transition": {"kind": "tiles", "ms": 800}},
]}


def make_root(listing=None, folders=("pnyx", "mint", "mintcity", "stoa", "nike"), bodies=None):
    root = tempfile.mkdtemp(prefix="wire-test-")
    for k, rel in REL.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write((bodies or {}).get(k, BODY[k]))
    p = os.path.join(root, "tools", "web_public", "olympus", "sfx.js")
    open(p, "w", encoding="utf-8").write(SFX_JS)
    for f in folders:
        os.makedirs(os.path.join(root, "tools", "web_public", f), exist_ok=True)
        open(os.path.join(root, "tools", "web_public", f, "index.html"), "w").write("<html></html>")
    with open(os.path.join(root, "tools", "new_apps.json"), "w", encoding="utf-8") as fh:
        json.dump(listing if listing is not None else LIST, fh)
    return root


def snap(root):
    h = {}
    for k, rel in REL.items():
        p = os.path.join(root, rel)
        h[k] = hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.isfile(p) else None
    return h


def text(root, k):
    return open(os.path.join(root, REL[k]), encoding="utf-8", newline="").read()


def only_insertions(old, new):
    """every old line is still there in order; a changed line only gained text (old is a subsequence of new)"""
    import difflib
    a, b = old.splitlines(), new.splitlines()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "delete":
            return False
        if tag == "replace":
            for x, y in zip(a[i1:i2], b[j1:j2]):
                it = iter(y)
                if not all(c in it for c in x):
                    return False
            if (i2 - i1) > (j2 - j1):
                return False
    return True


def test_list():
    d = json.load(open(os.path.join(ROOT, "tools", "new_apps.json"), encoding="utf-8"))
    apps = W.load_list(os.path.join(ROOT, "tools", "new_apps.json"))
    ids = [a["id"] for a in apps]
    want = ["delphi", "pnyx", "mint", "mintcity", "mercury", "chrysos", "sibyl", "oikos", "arbiter", "stoa", "aegis", "lyceum", "nike", "kronos", "moirai", "epilogue", "argo"]
    check("a. the list holds every app of the night that has a wiring section (valid entries, no duplicates); the already-wired old apps are not in it", ids == want and not {"planner", "hestia", "demeter", "apollo", "hera", "dionysus", "clio"} & set(ids), ids)
    check("a. kairos, kratos, pythia, gallery are named as pending (no section and no folder yet): add them when their sections land", d.get("pending") == ["kairos", "kratos", "pythia", "gallery"])
    doc = open(os.path.join(ROOT, "docs", "NEW_APPS_WIRING.md"), encoding="utf-8").read()
    bad = []
    for a in apps:
        if a["id"] == "pnyx":
            continue
        t = a["transition"]
        row = f"app('{a['id']}', '{a['name']}', '{a['group']}', '{a['accent']}'"
        trow = f"{a['id']}: {{ kind: '{t['kind']}', ms: {t['ms']}" + (f", n: {t['n']}" if t.get("n") else "") + " }"
        if row not in doc or f"{a['id']}: '{a['ambient']}'" not in doc or trow not in doc or f"{a['id']}: ['{a['flavour'][0]}'" not in doc or f"{{ glyph: '{a['glyph']}' }}" not in doc:
            bad.append(a["id"])
    check("a. every entry equals its section of docs/NEW_APPS_WIRING.md (row, glyph, bed, intro scene, transition)", not bad, bad)


def test_synthetic():
    root = make_root()
    before = snap(root)
    code, out, err = run("--root", root, "--dry-run")
    check("b. --dry-run prints a unified diff of the four missing apps (Pnyx is already there) and writes nothing", code == 0 and "+++ b/tools/web_public/jarvis/apps.js" in out and "+  app('mint'," in out and "+  app('pnyx'" not in out and "+    pnyx:" not in out and snap(root) == before, out[:500])
    code, out, err = run("--root", root, "--check")
    check("b. --check exits 1 while something is missing and names the files", code == 1 and "not wired yet" in out and "sw.js OTHER_APPS: + mint, mintcity, stoa, nike" in out, out)
    code, out, err = run("--root", root, "--apply")
    after = {k: text(root, k) for k in REL}
    check("b. --apply writes the six files and says the sw.js cache is the lead's job", code == 0 and "wrote 6 file(s)" in out and "bump the sw.js CACHE" in out, (code, out, err))
    check("b. apps.js: the four rows sit before the clio row, in the files' format, Pnyx / Planner / Atlas untouched, a title with an apostrophe uses double quotes",
          after["apps"].index("app('mint',") < after["apps"].index("app('clio',") and after["apps"].count("app('pnyx',") == 1 and "app('nike', 'Nike', 'life', '#4b7a99', \"Don't stop: the trophy hall\", { glyph: 'Ν' })," in after["apps"] and after["apps"].endswith("];\n"), after["apps"])
    check("b. olympus.js: the new APPS entries and AMBIENT beds are added, the old ones stay, no duplicate of Pnyx", "mint: ['Mint', 'M', '#c8a24a']," in after["olympus"] and "{ mint: 'coins', mintcity: 'coins', stoa: 'chimes', nike: 'chimes', pnyx: 'coins'" in after["olympus"] and after["olympus"].count("pnyx:") == 2, after["olympus"])
    check("b. build tuple and OTHER_APPS get the ids at the end; the sw.js CACHE line is NOT touched; the trailing comment stays",
          '"clio", "mint", "mintcity", "stoa", "nike"):' in after["build"] and "'clio/', 'mint/', 'mintcity/', 'stoa/', 'nike/']; // own folders" in after["sw"] and "const CACHE = 'le-dash-v100';" in after["sw"], (after["build"], after["sw"]))
    check("b. FLAVOUR and REGISTRY: rows added in the files' own layout (REGISTRY columns aligned like the old rows)",
          "    mint: ['columns', 'Strike the coin', 'tap']," in after["intro"] and re.search(r"^  mintcity:   \{ kind: 'columns',       ms: 1000, n: 5 \},$", after["trans"], re.M) and re.search(r"^  stoa:       \{ kind: 'sunburst',      ms: 1000 \},$", after["trans"], re.M)
          and after["trans"].index("  mint:") < after["trans"].index("  clio:") and "  pnyx:       { kind: 'columns',       ms: 1000, n: 5 }," in after["trans"], after["trans"])
    check("b. existing rows are never touched: every old line is still there in order and the changed lines only gained text", all(only_insertions(BODY[k], after[k]) for k in REL), [k for k in REL if not only_insertions(BODY[k], after[k])])
    snap2 = snap(root)
    code, out, err = run("--root", root, "--apply")
    check("b. a second --apply changes nothing (idempotent): no file differs, 'nothing to add'", code == 0 and snap(root) == snap2 and "nothing to add" in out and "wrote" not in out, out)
    code, out, err = run("--root", root, "--check")
    d2 = run("--root", root, "--dry-run")
    check("b. after applying, --check exits 0 and --dry-run has no diff", code == 0 and "CHECK: ok" in out and "+++" not in d2[1])
    # only apps with a folder
    root2 = make_root(folders=("pnyx", "mint"))
    code, out, err = run("--root", root2, "--apply")
    t = text(root2, "apps")
    check("b. only apps whose folder has an index.html are wired (Stoa, Mint City, Nike are skipped and named)", "app('mint'," in t and "app('stoa'," not in t and "skipped (no folder / no index.html yet): mintcity, stoa, nike" in out, out)
    for f in ("stoa",):
        os.makedirs(os.path.join(root2, "tools", "web_public", f), exist_ok=True)
        open(os.path.join(root2, "tools", "web_public", f, "index.html"), "w").write("x")
    s0 = text(root2, "apps")
    code, out, err = run("--root", root2, "--apply")
    t = text(root2, "apps")
    check("b. when a folder appears later, the next run adds just that app and leaves the rest alone", "app('stoa'," in t and "app('nike'," not in t and only_insertions(s0, t) and t.count("app('mint',") == 1, out)
    # a partly wired app: in apps.js already, missing elsewhere
    part = dict(BODY, apps=APPS_JS.replace("  app('clio',", "  app('mint', 'Mint', 'money', '#c8a24a', 'The money machine: five streams', { glyph: 'M' }),\n  app('clio',"))
    root3 = make_root(bodies=part)
    code, out, err = run("--root", root3, "--apply")
    check("b. an app already in one file is only added to the files that miss it (apps.js keeps ONE Mint row, the others get it)", text(root3, "apps").count("app('mint',") == 1 and "mint: ['Mint'" in text(root3, "olympus") and "'mint/'" in text(root3, "sw"), out)
    # warnings are not refusals
    odd = {"apps": [dict(LIST["apps"][1], id="odd", ambient="nosuchbed", flavour=["nosuchscene", "Hi", "tap"], transition={"kind": "nosuchkind", "ms": 900})]}
    root4 = make_root(listing=odd, folders=("odd",))
    code, out, err = run("--root", root4, "--apply")
    check("b. an unknown bed / intro scene / transition kind is a NOTE (the app is still wired; the page falls back to a plain default), not a refusal", code == 0 and out.count("NOTE:") == 3 and "odd: ['nosuchscene'" in text(root4, "intro"), out)


def test_refusals():
    def refused(name, root, extra=()):
        before = snap(root)
        code, out, err = run("--root", root, "--apply", *extra)
        check(f"c. refuses and writes NOTHING when {name}", code == 2 and "REFUSED" in err and "Nothing was written" in err and snap(root) == before, (code, err[:300]))
    refused("the clio row of apps.js is gone", make_root(bodies=dict(BODY, apps=APPS_JS.replace("  app('clio',", "  app('klio',"))))
    refused("the AMBIENT line is not where it should be", make_root(bodies=dict(BODY, olympus=OLYMPUS_JS.replace("var AMBIENT", "var AMBIENTS"))))
    refused("the site build loop is gone", make_root(bodies=dict(BODY, build=BUILD_PY.replace("for app in", "for apps in"))))
    refused("OTHER_APPS is gone", make_root(bodies=dict(BODY, sw=SW_JS.replace("OTHER_APPS", "OTHER"))))
    refused("FLAVOUR is gone", make_root(bodies=dict(BODY, intro=INTRO_JS.replace("var FLAVOUR", "var FLAVOURS"))))
    refused("the transitions clio row is gone (the file is last in the loop, so apps.js stays unchanged too)", make_root(bodies=dict(BODY, trans=TRANS_JS.replace("  clio:", "  klio:"))))
    refused("a file has Windows line endings", make_root(bodies=dict(BODY, sw=SW_JS.replace("\n", "\r\n"))))
    refused("an app group is wrong", make_root(listing={"apps": [dict(LIST["apps"][1], group="fun")]}))
    refused("an accent is not #rrggbb", make_root(listing={"apps": [dict(LIST["apps"][1], accent="gold")]}))
    refused("an id is not a plain lowercase id", make_root(listing={"apps": [dict(LIST["apps"][1], id="Mint City")]}, folders=()))
    refused("an app is listed twice", make_root(listing={"apps": [LIST["apps"][1], LIST["apps"][1]]}))
    refused("a transition has no duration", make_root(listing={"apps": [dict(LIST["apps"][1], transition={"kind": "tiles"})]}))
    root = make_root()
    open(os.path.join(root, "tools", "new_apps.json"), "w").write("{not json")
    refused("the list is not JSON", root)
    root = make_root()
    os.remove(os.path.join(root, REL["sw"]))
    refused("a target file is missing", root)
    # nothing to add -> anchors are not demanded
    root = make_root(bodies=dict(BODY, trans=TRANS_JS.replace("  clio:", "  klio:")), listing={"apps": [LIST["apps"][0]]}, folders=("pnyx",))
    code, out, err = run("--root", root, "--check")
    check("c. when nothing needs adding to a file, a missing anchor there is not a problem (already-wired apps only: --check is ok)", code == 0, (out, err))


def sha_tree(paths):
    return {p: hashlib.sha256(open(os.path.join(ROOT, p), "rb").read()).hexdigest() for p in paths}


def test_real_copy():
    real = sha_tree(W.FILES.values())
    root = tempfile.mkdtemp(prefix="wire-real-")
    for rel in list(W.FILES.values()) + [os.path.join(W.WEB, "olympus", "sfx.js")]:
        os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), os.path.join(root, rel))
    shutil.copy(os.path.join(ROOT, "tools", "new_apps.json"), os.path.join(root, "tools", "new_apps.json"))
    for a in W.load_list(os.path.join(ROOT, "tools", "new_apps.json")):
        src = os.path.join(ROOT, W.WEB, a["id"], "index.html")
        if os.path.isfile(src):
            os.makedirs(os.path.join(root, W.WEB, a["id"]), exist_ok=True)
            shutil.copy(src, os.path.join(root, W.WEB, a["id"], "index.html"))
    orig = {k: text(root, k) for k in W.FILES}
    code, out, err = run("--root", root, "--apply")
    check("d. on a copy of the REAL six files the tool plans and applies without refusing (the real anchors are found)", code == 0, (out[-400:], err[-400:]))
    new = {k: text(root, k) for k in W.FILES}
    check("d. only insertions in the real files too: no existing row of any app is changed", all(only_insertions(orig[k], new[k]) for k in W.FILES), [k for k in W.FILES if not only_insertions(orig[k], new[k])])
    s = {k: hashlib.sha256(new[k].encode()).hexdigest() for k in new}
    code, out, err = run("--root", root, "--apply")
    check("d. a second apply on the real files is a no-op, --check is ok", code == 0 and {k: hashlib.sha256(text(root, k).encode()).hexdigest() for k in W.FILES} == s and run("--root", root, "--check")[0] == 0)
    node = shutil.which("node")
    if node:
        bad = []
        for k in ("apps", "trans", "olympus", "intro", "sw"):
            ext = ".mjs" if k in ("apps", "trans") else ".js"
            p = os.path.join(root, "chk_" + k + ext)
            shutil.copy(os.path.join(root, W.FILES[k]), p)
            r = subprocess.run([node, "--check", p], capture_output=True, text=True, timeout=60)
            if r.returncode:
                bad.append((k, r.stderr[-200:]))
        check("d. the edited JavaScript files still parse (node --check)", not bad, bad)
    try:
        compile(new["build"], "build_web_dashboard.py", "exec")
        ok = True
    except SyntaxError as e:
        ok = False
    check("d. the edited build_web_dashboard.py still compiles", ok)
    check("d. the real tree was not written by this test", sha_tree(W.FILES.values()) == real)
    # the real tree: dry-run and check only read
    code, out, err = run("--root", ROOT, "--dry-run")
    code2 = run("--root", ROOT, "--check")[0]
    check("d. on the real tree --dry-run and --check run (never a refusal) and write nothing", code == 0 and code2 in (0, 1) and sha_tree(W.FILES.values()) == real, (out[-300:], err[-300:]))


if __name__ == "__main__":
    test_list()
    test_synthetic()
    test_refusals()
    test_real_copy()
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    sys.exit(1 if bad else 0)
