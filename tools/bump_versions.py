#!/usr/bin/env python3
"""Stale phone caches are the #1 risk of a big publish: bump every ?v= query and every service-worker cache that a change needs.

    python tools/bump_versions.py                  dry run (the default): print what would change, change nothing
    python tools/bump_versions.py --apply          do it
    python tools/bump_versions.py --check          exit 1 when something changed since the base but is not bumped (a release gate)
    options: --base origin/main   --changed FILE [FILE ...] (skip git: the files to treat as changed)   --root DIR (tests)

What it does, against the base (default origin/main; `git diff --name-only <base>` + untracked files):
  1. every changed file under tools/web_public/ or web_next/ that some page, script or worker references with a ?v= query
     (src= / href= in an html file, a quoted string in a script, an entry of a worker's list) gets its trailing number
     incremented (o2 -> o3, k17 -> k18, 8 -> 9, p111030 -> p111031) in EVERY place that references it, so they stay consistent
     (the highest tag in use + 1); a file already bumped since the base (its reference differs from the base's) is left alone
  2. every service worker that lists a touched file (a changed file, a file this tool edited such as the html it re-tagged, a ?v= entry
     it bumped) gets its cache name bumped once: tools/web_public/sw.js (le-public-vNN), web_next/sw.js (le-shell-next-vNN),
     jarvis/sw.js (jarvis-vNN, the old name pushed onto its OLD list), kalshi/sw.js (kalshi-<tag>: ALWAYS the ?v= of kalshi.css
     AND kalshi.js, which move together; a cache that ran ahead of them pulls them up, TIED below)
  3. a changed file under an app folder (tools/web_public/<app>/ with an index.html) that has no ?v= and is listed by no worker
     (a module the app imports) bumps the root worker's cache (le-public-vNN) once
  4. tests that pin an exact string (`'secondcore.js?v=8'`, `const CACHE = 'jarvis-v24';`, the OLD list's first entry,
     `caches.open('jarvis-v24')`) are updated by exact string replacement; every pin changed, and every one it could not
     safely change (an ambiguous tag, a cache name on a line it does not recognise), is reported.
A page whose only change is a ?v= (the cascade of a bump) needs no root cache bump, so --check after --apply passes on
the real git diff. A path joined to the site base in a script (gate/index.html: b + 'olympus/x.css?v=a4') resolves from the site root.
Files with no ?v= get none added. The tool never touches git, never pushes, and in dry-run / --check never writes.
"""
from __future__ import annotations

import argparse
import os
import posixpath
import re
import subprocess
import sys
from dataclasses import dataclass, field

SITES = ("tools/web_public", "web_next")                      # the phone site (served from /) and the PC site
SKIP_DIRS = {"node_modules", ".git", "three-addons", "__pycache__"}
TEXT_EXT = (".html", ".js", ".mjs")
MAX_BYTES = 1_500_000
EXT = r"(?:js|mjs|css|json|webmanifest|png|svg|webp|jpg|jpeg|woff2|ico|txt)"
REF_RE = re.compile(r"""(["'])((?:\.{0,2}/|/)?[A-Za-z0-9_./@+-]+?\.""" + EXT + r""")\?v=([A-Za-z]*\d+)\1""")
LIST_RE = re.compile(r"""(["'])((?:\.{1,2}/|/)[^"'\s?#]*)(?:\?[^"'\s]*)?\1""")           # a path in a worker's list ('./x.js?v=1', '/css/a.css')
TAG_RE = re.compile(r"^([A-Za-z_-]*)(\d+)$")

# the workers: path, the cache-name line, how its name changes
WORKERS = [
    {"path": "tools/web_public/sw.js", "re": r"(const CACHE = ')(le-public-v)(\d+)(';)", "style": "num", "old_list": False, "label": "phone root"},
    {"path": "web_next/sw.js", "re": r"(const SHELL = ')(le-shell-next-v)(\d+)(';)", "style": "num", "old_list": False, "label": "PC"},
    {"path": "tools/web_public/jarvis/sw.js", "re": r"(const CACHE = ')(jarvis-v)(\d+)(';)", "style": "num", "old_list": True, "label": "Jarvis"},
    {"path": "tools/web_public/kalshi/sw.js", "re": r"(const CACHE = ')(kalshi-)([A-Za-z]+\d+)(';)", "style": "tag", "old_list": False, "label": "Kalshi"},
]
ROOT_WORKER = "tools/web_public/sw.js"
# tests whose "pins" are synthetic fixtures of a release tool (a mini-site inside the test): never rewritten
SKIP_PIN_FILES = {"tests/test_bump_versions.py", "tests/test_add_kit_tags.py", "tests/test_release_manifest.py"}


def bump_tag(tag: str) -> str | None:
    m = TAG_RE.match(tag)
    if not m:
        return None
    n = m.group(2)
    return m.group(1) + str(int(n) + 1).zfill(len(n))


def tag_num(tag: str) -> int:
    m = TAG_RE.match(tag)
    return int(m.group(2)) if m else -1


@dataclass
class Plan:
    rows: list = field(default_factory=list)        # (area, target, change)
    warnings: list = field(default_factory=list)
    writes: dict = field(default_factory=dict)      # path -> new text

    def add(self, area, target, change):
        self.rows.append((area, target, change))

    @property
    def changed(self):
        return bool(self.rows)


class Repo:
    def __init__(self, root, base, changed=None):
        self.root, self.base, self._changed = os.path.abspath(root), base, changed
        self._text, self._base = {}, {}

    def p(self, rel):
        return os.path.join(self.root, *rel.split("/"))

    def exists(self, rel):
        return os.path.isfile(self.p(rel))

    def text(self, rel):
        if rel not in self._text:
            try:
                with open(self.p(rel), encoding="utf-8") as fh:
                    self._text[rel] = fh.read()
            except (OSError, UnicodeDecodeError):
                self._text[rel] = None
        return self._text[rel]

    def base_text(self, rel):
        if rel not in self._base:
            try:
                out = subprocess.run(["git", "-C", self.root, "show", f"{self.base}:{rel}"], capture_output=True, check=True)
                self._base[rel] = out.stdout.decode("utf-8", "replace")
            except (subprocess.CalledProcessError, OSError):
                self._base[rel] = None
        return self._base[rel]

    def changed(self):
        if self._changed is not None:
            return sorted({c.replace("\\", "/") for c in self._changed if self.exists(c.replace("\\", "/"))})
        names = set()
        for cmd in (["git", "-C", self.root, "diff", "--name-only", self.base], ["git", "-C", self.root, "ls-files", "-o", "--exclude-standard"]):
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                raise SystemExit(f"git failed ({' '.join(cmd[3:])}): {r.stderr.strip()}")
            names.update(x for x in r.stdout.splitlines() if x)
        return sorted(n for n in names if self.exists(n))


def site_root(rel):
    return "web_next" if rel.startswith("web_next/") else "tools/web_public" if rel.startswith("tools/web_public/") else ""


def resolve(from_file, literal):
    if "://" in literal or literal.startswith("//") or "{" in literal:
        return None
    if literal.startswith("/"):
        return posixpath.normpath(posixpath.join(site_root(from_file), literal.lstrip("/")))
    return posixpath.normpath(posixpath.join(posixpath.dirname(from_file), literal))


def site_files(repo):
    out = []
    for site in SITES:
        base = repo.p(site)
        for dp, dns, fns in os.walk(base):
            dns[:] = [d for d in dns if d not in SKIP_DIRS]
            for fn in fns:
                if fn.endswith(TEXT_EXT) and not fn.endswith(".min.js") and "three.module" not in fn:
                    fp = os.path.join(dp, fn)
                    if os.path.getsize(fp) <= MAX_BYTES:
                        out.append(os.path.relpath(fp, repo.root).replace(os.sep, "/"))
    return sorted(out)


@dataclass
class Ref:
    file: str
    start: int
    end: int
    quote: str
    literal: str
    tag: str
    target: str                                      # the repo file it points to


def collect_refs(repo, files):
    refs = []
    for f in files:
        t = repo.text(f)
        if not t:
            continue
        for m in REF_RE.finditer(t):
            tgt = resolve(f, m.group(2))
            if tgt and not repo.exists(tgt) and not m.group(2).startswith((".", "/")) and site_root(f):
                tgt = posixpath.normpath(posixpath.join(site_root(f), m.group(2)))    # a path joined to the site base in a script (gate/index.html: b + 'olympus/x.css?v=a4')
            if tgt and repo.exists(tgt):
                refs.append(Ref(f, m.start(3), m.end(3), m.group(1), m.group(2), m.group(3), tgt))
    return refs


def listed_files(repo, worker_path):
    t = repo.text(worker_path) or ""
    out = set()
    for m in LIST_RE.finditer(t):
        tgt = resolve(worker_path, m.group(2))
        if tgt and not m.group(2).endswith("/") and repo.exists(tgt) and tgt != worker_path:
            out.add(tgt)
    return out


def already_bumped(repo, refs_of_file):
    """True when a reference of this file in the working tree carries a different tag than the same reference at the base."""
    for r in refs_of_file:
        bt = repo.base_text(r.file)
        if bt is None:
            continue
        m = re.search(r"""(["'])""" + re.escape(r.literal) + r"""\?v=([A-Za-z]*\d+)\1""", bt)
        if m and m.group(2) != r.tag:
            return True
    return False


V_RE = re.compile(r"\?v=[A-Za-z]*\d+")


def tags_only_change(repo, rel):
    """True when the file differs from the base only in its ?v= tags (the cascade of a bump, not a content change)"""
    bt, t = repo.base_text(rel), repo.text(rel)
    return bt is not None and t is not None and bt != t and V_RE.sub("?v=", bt) == V_RE.sub("?v=", t)


# a worker whose cache name must equal the ?v= of a pair of its files, moved together (kalshi/sw.js: CACHE = 'kalshi-' + the ?v= of
# kalshi.css / kalshi.js, see its header and kalshi/index.html); any reason that bumps the worker bumps the pair to one tag
TIED = {"tools/web_public/kalshi/sw.js": ["tools/web_public/kalshi/kalshi.css", "tools/web_public/kalshi/kalshi.js"]}


def make_plan(repo, changed=None):
    plan = Plan()
    changed = repo.changed() if changed is None else changed
    in_site = [c for c in changed if c.startswith(tuple(s + "/" for s in SITES))]
    files = site_files(repo)
    refs = collect_refs(repo, files)
    by_target: dict[str, list[Ref]] = {}
    for r in refs:
        by_target.setdefault(r.target, []).append(r)

    # ---- 1. the ?v= queries
    edits: dict[str, list[tuple[int, int, str]]] = {}
    bumped: dict[str, tuple[str, str]] = {}                       # target -> (old, new)
    queue, seen_q = list(in_site), set(in_site)                      # a script this tool edits (a ?v= inside it) has changed too: it is bumped as well (a fixed point)
    while queue:
        c = queue.pop(0)
        if c.endswith("/sw.js") or c not in by_target:
            continue
        rs = by_target[c]
        if repo.base_text(c) is None:                                  # created since the base: no phone has a copy, nothing can be stale
            plan.warnings.append(f"{c}: new since {repo.base} (no tag bump needed)")
            continue
        if all(repo.base_text(r.file) is None for r in rs):             # only pages created since the base point at it: no evidence of the old tag
            plan.warnings.append(f"{c}: referenced only by files new since {repo.base} (not bumped: bump by hand if its tag was already used)")
            continue
        if already_bumped(repo, rs):
            plan.warnings.append(f"{c}: already bumped since {repo.base} (left alone)")
            continue
        top = max(rs, key=lambda r: tag_num(r.tag))
        new = bump_tag(top.tag)
        if new is None:
            plan.warnings.append(f"{c}: tag '{top.tag}' has no trailing number (not bumped)")
            continue
        bumped[c] = (top.tag, new)
        for r in rs:
            edits.setdefault(r.file, []).append((r.start, r.end, new))
            plan.add("query", r.file, f"{r.literal}?v={r.tag} -> ?v={new}")
            if r.file not in seen_q and r.file in by_target and repo.base_text(r.file) is not None:
                seen_q.add(r.file)
                queue.append(r.file)
    edited_files = set(edits)

    # ---- 2. the workers
    touched = set(in_site) | edited_files
    worker_bump: dict[str, tuple[str, str]] = {}
    root_reason = []
    wlisted = {w["path"]: listed_files(repo, w["path"]) for w in WORKERS if repo.exists(w["path"])}
    for w in WORKERS:
        wp = w["path"]
        if wp not in wlisted:
            continue
        hit = sorted((touched & wlisted[wp]) - {wp})
        if hit:
            worker_bump[wp] = (w["label"], ", ".join(hit[:4]) + (f" (+{len(hit) - 4} more)" if len(hit) > 4 else ""))
    # ---- 3. an app file with no ?v= that no worker lists: the root worker, once
    apps = {d for d in os.listdir(repo.p("tools/web_public")) if repo.exists(f"tools/web_public/{d}/index.html")} if os.path.isdir(repo.p("tools/web_public")) else set()
    unversioned = [c for c in in_site if c.startswith("tools/web_public/") and c.count("/") >= 3 and c.split("/")[2] in apps and c.split("/")[2] != "jarvis"
                   and c not in by_target and not any(c in lst for lst in wlisted.values()) and not c.endswith("/sw.js")
                   and not tags_only_change(repo, c)]       # a page whose only change is a ?v= this tool (or a helper) moved: --apply never asks for it, so --check must not
    if unversioned and ROOT_WORKER in wlisted and ROOT_WORKER not in worker_bump:
        worker_bump[ROOT_WORKER] = ("phone root", f"app files without ?v=: {', '.join(unversioned[:3])}" + (f" (+{len(unversioned) - 3} more)" if len(unversioned) > 3 else ""))

    tied_tag: dict[str, str] = {}                                # worker -> the one tag of its pair and its cache
    for wp, pair in TIED.items():
        w = next((x for x in WORKERS if x["path"] == wp), None)
        t = repo.text(wp)
        m = re.search(w["re"], t) if (w and t) else None
        pair = [f for f in pair if f in by_target]
        if not m or not pair:
            continue
        cur = {f: (bumped[f][1] if f in bumped else max((r.tag for r in by_target[f]), key=tag_num)) for f in pair}
        bm = re.search(w["re"], repo.base_text(wp) or "")
        top = max(list(cur.values()) + [m.group(3)], key=tag_num)          # never backwards: a cache that ran ahead pulls the pair up to it
        if wp in worker_bump and bm and top == bm.group(3):
            top = bump_tag(top) or top                                # the worker must move (a file it lists changed): the pair moves with it
        if all(v == top for v in cur.values()) and m.group(3) == top:
            continue
        tied_tag[wp] = top
        for f in pair:
            if all(r.tag == top for r in by_target[f]) or (f in bumped and bumped[f][1] == top):
                continue
            if f in bumped:                                          # step 1 gave it another tag: its rows are replaced below
                gone = {f"{r.literal}?v={r.tag} -> ?v={bumped[f][1]}" for r in by_target[f]}
                plan.rows = [row for row in plan.rows if not (row[0] == "query" and row[2] in gone)]
            bumped[f] = (bumped[f][0] if f in bumped else max((r.tag for r in by_target[f]), key=tag_num), top)
            for r in by_target[f]:
                lst = [e for e in edits.get(r.file, []) if (e[0], e[1]) != (r.start, r.end)]
                lst.append((r.start, r.end, top))
                edits[r.file] = lst
                if r.tag != top:
                    plan.add("query", r.file, f"{r.literal}?v={r.tag} -> ?v={top}   (kept equal to its pair + the cache)")
        if wp not in worker_bump:
            worker_bump[wp] = (w["label"], "cache name = its pair's ?v=")
    cache_changes: list[tuple[dict, str, str]] = []              # (worker, old name, new name)
    sw_text: dict[str, str] = {}
    for w in WORKERS:
        wp = w["path"]
        if wp not in worker_bump:
            continue
        t = repo.text(wp)
        if wp in edits:                                         # the worker's own ?v= entries first (spans refer to the original text)
            for s0, e0, new in sorted(edits[wp], reverse=True):
                t = t[:s0] + new + t[e0:]
            edits.pop(wp)
        m = re.search(w["re"], t)
        if not m:
            plan.warnings.append(f"{wp}: cache name line not found (not bumped)")
            sw_text[wp] = t
            continue
        old = m.group(2) + m.group(3)
        bt = repo.base_text(wp)
        bm = re.search(w["re"], bt) if bt else None
        if wp in tied_tag:                                      # kalshi: exactly the pair's tag (also repairs a cache that ran ahead of it)
            if tied_tag[wp] == m.group(3):
                sw_text[wp] = t
                continue
        elif bm and bm.group(2) + bm.group(3) != old:
            plan.warnings.append(f"{wp}: cache already bumped since {repo.base} ({bm.group(2)}{bm.group(3)} -> {old}), left alone")
            sw_text[wp] = t
            continue
        if wp in tied_tag:
            newv = tied_tag[wp]
        elif w["style"] == "num":
            newv = str(int(m.group(3)) + 1)
        else:                                                    # kalshi: 'kalshi-' + the ?v= of its files
            tags = [mm.group(1) for mm in re.finditer(r"\?v=([A-Za-z]*\d+)", t)]
            newv = max(tags, key=tag_num) if tags else (bump_tag(m.group(3)) or m.group(3))
            if newv == m.group(3):
                newv = bump_tag(m.group(3)) or newv
        new = m.group(2) + newv
        t = t[:m.start()] + m.group(1) + new + m.group(4) + t[m.end():]
        if w["old_list"]:
            t, n = re.subn(r"(const OLD = \[)", r"\1'" + old + "', ", t, count=1)
            if not n:
                plan.warnings.append(f"{wp}: no OLD list to push '{old}' onto")
        sw_text[wp] = t
        cache_changes.append((w, old, new))
        plan.add("worker", wp, f"cache {old} -> {new}   ({worker_bump[wp][0]}: {worker_bump[wp][1]})")
    for wp, t in sw_text.items():
        plan.writes[wp] = t

    # ---- the file edits (tags in html / scripts)
    for f, lst in edits.items():
        t = repo.text(f)
        for s0, e0, new in sorted(lst, reverse=True):
            t = t[:s0] + new + t[e0:]
        plan.writes[f] = t

    # ---- 4. the tests that pin exact strings
    tests_dir = "tests"
    pins = {}
    if os.path.isdir(repo.p(tests_dir)):
        for fn in sorted(os.listdir(repo.p(tests_dir))):
            if fn.endswith(".py") and f"{tests_dir}/{fn}" not in SKIP_PIN_FILES:
                pins[f"{tests_dir}/{fn}"] = repo.text(f"{tests_dir}/{fn}") or ""
    all_by_key: dict[tuple[str, str], set[str]] = {}
    for r in refs:
        if r.file == r.target:                                       # a file naming itself (a doc comment, a stray copy of the kit) is not a second owner of the pin
            continue
        all_by_key.setdefault((posixpath.basename(r.literal), r.tag), set()).add(r.target)
    new_pins = dict(pins)
    for tgt, (old, new) in sorted(bumped.items()):
        key = (posixpath.basename(tgt), old)
        pat = re.compile(r"(?<![\w-])" + re.escape(posixpath.basename(tgt)) + r"\?v=" + re.escape(old) + r"(?![\w])")
        owners = all_by_key.get(key, set())
        for tf, tx in pins.items():
            if not pat.search(tx):
                continue
            if owners - set(bumped):                              # another file uses the same name + tag and stays: ambiguous
                plan.warnings.append(f"{tf}: pins '{posixpath.basename(tgt)}?v={old}' but another file with that name keeps it: change by hand")
                continue
            for lm in pat.finditer(new_pins[tf]):
                line = new_pins[tf].count("\n", 0, lm.start()) + 1
                plan.add("pin", f"{tf}:{line}", f"{posixpath.basename(tgt)}?v={old} -> ?v={new}")
            new_pins[tf] = pat.sub(f"{posixpath.basename(tgt)}?v={new}", new_pins[tf])
    for w, old, new in cache_changes:
        for tf in list(new_pins):
            lines = new_pins[tf].split("\n")
            ch = False
            for i, ln in enumerate(lines):
                if f"'{old}'" not in ln and f'"{old}"' not in ln:
                    continue
                if re.search(r"CACHE|caches\.open", ln):
                    lines[i] = ln.replace(f"'{old}'", f"'{new}'").replace(f'"{old}"', f'"{new}"')
                    ch = True
                    plan.add("pin", f"{tf}:{i + 1}", f"cache name '{old}' -> '{new}'")
                else:
                    plan.warnings.append(f"{tf}:{i + 1}: mentions '{old}' (not a pin this tool recognises): check by hand")
            if ch:
                new_pins[tf] = "\n".join(lines)
    # a pin of the OLD list (`const OLD = ['jarvis-v23', ...`) must now start with the name that was the CACHE
    for w, old, new in cache_changes:
        if not w["old_list"]:
            continue
        pat = re.compile(r"(const OLD = \[)'(" + re.escape(re.sub(r"\d+$", "", old)) + r"\d+)'")
        for tf in list(new_pins):
            tx = new_pins[tf]
            mm = pat.search(tx)
            if mm and mm.group(2) != old:
                line = tx.count("\n", 0, mm.start()) + 1
                new_pins[tf] = tx[:mm.start()] + mm.group(1) + f"'{old}', '{mm.group(2)}'" + tx[mm.end():]
                plan.add("pin", f"{tf}:{line}", f"OLD list now starts with '{old}'")
    for tf, tx in new_pins.items():
        if tx != pins[tf]:
            plan.writes[tf] = tx
    plan.writes = {rel: tx for rel, tx in plan.writes.items() if tx != repo.text(rel)}              # only files that really change
    return plan


def print_table(plan, out=None):
    out = out or sys.stdout
    if not plan.rows:
        print("nothing needs a bump.", file=out)
    else:
        w1 = max(len(r[0]) for r in plan.rows)
        w2 = min(70, max(len(r[1]) for r in plan.rows))
        print(f"{'what':<{w1}}  {'where':<{w2}}  change", file=out)
        print(f"{'-' * w1}  {'-' * w2}  {'-' * 30}", file=out)
        for a, t, c in plan.rows:
            print(f"{a:<{w1}}  {t:<{w2}}  {c}", file=out)
    for w in plan.warnings:
        print(f"note: {w}", file=out)


def main(argv=None):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description="bump ?v= queries and service-worker caches for what changed since the base")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="print what would change (the default)")
    g.add_argument("--apply", action="store_true", help="write the changes")
    g.add_argument("--check", action="store_true", help="exit 1 when something changed but is not bumped")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--changed", nargs="*", default=None, help="treat these files as the changed set (no git)")
    ap.add_argument("--root", default=here)
    a = ap.parse_args(argv)
    repo = Repo(a.root, a.base, a.changed)
    plan = make_plan(repo)
    print_table(plan)
    if a.apply:
        for rel, text in sorted(plan.writes.items()):
            with open(repo.p(rel), "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
        print(f"applied: {len(plan.writes)} file(s) written, {len(plan.rows)} change(s).")
        return 0
    if a.check:
        if plan.changed:
            print("CHECK FAILED: changed files are not bumped (run tools/bump_versions.py --apply).")
            return 1
        print("check ok.")
        return 0
    print(f"dry run: {len(plan.rows)} change(s) in {len(plan.writes)} file(s); nothing written (use --apply).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
