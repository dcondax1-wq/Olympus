"""Release safety net (the 5 AM publish): what would a phone keep serving from its old cache?

    python tools/release_manifest.py                 compare the working tree + commits against origin/main
    python tools/release_manifest.py --base main     another base ref (a branch, a tag, a commit)
    python tools/release_manifest.py --root DIR      another repo (the test builds a synthetic one)
    python tools/release_manifest.py --json          the findings as JSON

Exit 0 = nothing stale. Exit 1 = at least one finding (printed in plain words, one line each). Exit 2 = the base ref does not exist.

(a) ASSET TAGS. Every app index.html (tools/web_public/**/index.html, web_next/index.html) loads files as  src="x.js?v=3"  or  href="x.css?v=3".
    A file whose content changed since the base but whose ?v= string is the SAME as in the base's index.html is stale-cache risk: the browser
    and the service worker keep the old copy. Reported per index.html + file. (A tag that changed, a file the page did not load before, and an
    index.html that is new are fine.)
(b) WORKERS. root sw.js (tools/web_public/sw.js), web_next/sw.js, jarvis/sw.js, kalshi/sw.js: if a file in the worker's SHELL / ASSETS list
    changed (or the list itself changed) and the worker's cache name (CACHE = '...', or web_next's SHELL = '...') is the same as in the base,
    installed phones never refetch it. Reported per worker with the files.
"Changed" = `git diff --name-only <base>` (commits and tracked edits) plus untracked files. Nothing here edits anything; it only reads.
Limits: only src= / href= attributes are scanned (not ?v= strings built in scripts); worker lists are read from SHELL / ASSETS arrays and
.push(...) calls with plain quoted strings.
"""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITES = ("tools/web_public", "web_next")          # the two site roots: '/x' in a page or worker means <site>/x
WORKERS = ("tools/web_public/sw.js", "web_next/sw.js", "tools/web_public/jarvis/sw.js", "tools/web_public/kalshi/sw.js")
SKIP_DIRS = {".git", "node_modules", "__pycache__"}
REF = re.compile(r"""(?:src|href)\s*=\s*["']([^"'#?]+)\?v=([^"'&#]+)[^"']*["']""")


def git(root, *args, check=False):
    r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(r.stderr.strip() or "git failed")
    return r


def base_exists(root, base):
    return git(root, "rev-parse", "--verify", "--quiet", base + "^{commit}").returncode == 0


def changed_files(root, base):
    out = set(git(root, "diff", "--name-only", base).stdout.split("\n"))
    out |= set(git(root, "ls-files", "--others", "--exclude-standard").stdout.split("\n"))
    return {p for p in out if p}


def at_base(root, base, path):
    r = git(root, "show", f"{base}:{path}")
    return r.stdout if r.returncode == 0 else None


def read(root, path):
    try:
        with open(os.path.join(root, *path.split("/")), encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def site_of(path):
    for s in SITES:
        if path == s or path.startswith(s + "/"):
            return s
    return SITES[0]


def resolve(ref, page_dir, site):
    """A reference in a page or worker -> a repo path ('' when it is not a file of this repo)."""
    ref = ref.strip()
    if not ref or re.match(r"^(?:[a-z]+:|//|data:)", ref, re.I):
        return ""
    p = posixpath.normpath(posixpath.join(site, ref.lstrip("/")) if ref.startswith("/") else posixpath.join(page_dir, ref))
    return p


def index_pages(root):
    out = []
    for site in SITES:
        top = os.path.join(root, *site.split("/"))
        for dp, dns, fns in os.walk(top):
            dns[:] = [d for d in dns if d not in SKIP_DIRS]
            if "index.html" in fns:
                out.append(posixpath.relpath(os.path.join(dp, "index.html").replace(os.sep, "/"), root.replace(os.sep, "/")))
    return sorted(out)


def tags(text, page):
    """{repo path of the asset: ?v= string} for one index.html."""
    out = {}
    d, site = posixpath.dirname(page), site_of(page)
    for m in REF.finditer(text or ""):
        p = resolve(m.group(1), d, site)
        if p:
            out[p] = m.group(2)
    return out


def check_tags(root, base, changed):
    found = []
    for page in index_pages(root):
        now = tags(read(root, page), page)
        old_text = at_base(root, base, page)
        if old_text is None:
            continue                                   # a new page: nothing cached yet
        old = tags(old_text, page)
        for asset, v in sorted(now.items()):
            if asset in changed and asset in old and old[asset] == v:
                found.append({"kind": "tag", "page": page, "file": asset, "v": v,
                              "text": f"{page} loads {posixpath.relpath(asset, posixpath.dirname(page))}?v={v}: the file changed since {base} but its ?v= is still {v}"})
    return found


def parse_worker(text):
    """-> (cache name or None, [asset refs]) from a service worker's source."""
    m = re.search(r"const\s+CACHE\s*=\s*['\"]([^'\"]+)['\"]", text) or re.search(r"const\s+SHELL\s*=\s*['\"]([^'\"]+)['\"]", text)
    name = m.group(1) if m else None
    chunks = [c for c in re.findall(r"\b(?:SHELL|ASSETS)\s*=\s*\[(.*?)\]\s*;?", text, re.S)]
    chunks += re.findall(r"\b(?:SHELL|ASSETS)\.push\(([^)]*)\)", text)
    refs = []
    for c in chunks:
        for s in re.findall(r"""['"]([^'"]+)['"]""", c):
            if s not in refs:
                refs.append(s)
    return name, refs


def asset_paths(refs, worker):
    d, site = posixpath.dirname(worker), site_of(worker)
    if worker == "tools/web_public/sw.js":
        d = site
    out = {}
    for r in refs:
        clean = r.split("?")[0].split("#")[0]
        if clean in ("", "./", "/"):
            p = posixpath.join(d if clean != "/" else site, "index.html")
        else:
            p = resolve(clean, d, site)
        if p:
            out[r] = p
    return out


def check_workers(root, base, changed):
    found = []
    for w in WORKERS:
        text = read(root, w)
        if text is None:
            continue
        name, refs = parse_worker(text)
        old_text = at_base(root, base, w)
        if old_text is None:
            continue                                   # a new worker
        old_name, old_refs = parse_worker(old_text)
        if name != old_name:
            continue                                   # bumped: phones refetch the shell
        paths = asset_paths(refs, w)
        hit = sorted({p for p in paths.values() if p in changed})
        grew = sorted(set(refs) ^ set(old_refs))
        if hit or grew:
            why = []
            if hit:
                why.append("changed: " + ", ".join(posixpath.relpath(p, posixpath.dirname(w)) for p in hit[:12]) + (" ..." if len(hit) > 12 else ""))
            if grew:
                why.append("its list changed: " + ", ".join(grew[:6]))
            found.append({"kind": "worker", "worker": w, "cache": name, "files": hit, "list": grew,
                          "text": f"{w} keeps the cache name '{name}' although " + " and ".join(why)})
    return found


def run(root, base):
    if not base_exists(root, base):
        return None
    changed = changed_files(root, base)
    return check_tags(root, base, changed) + check_workers(root, base, changed)


def main(argv=None):
    ap = argparse.ArgumentParser(description="stale-cache safety net for the publish")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    found = run(a.root, a.base)
    if found is None:
        print(f"release manifest: the base '{a.base}' does not exist here (git fetch origin, or pass --base)")
        return 2
    if a.json:
        print(json.dumps(found, indent=1))
    else:
        groups = {}
        for f in found:
            if f["kind"] == "tag":
                groups.setdefault((f["file"], f["v"]), []).append(f["page"])
            else:
                print("STALE WORKER " + f["text"])
        for (file, v), pages in sorted(groups.items()):
            names = ["root of " + posixpath.dirname(pg) if posixpath.dirname(pg) in SITES else posixpath.basename(posixpath.dirname(pg)) for pg in pages]
            print(f"STALE ?v= {file} (?v={v}) changed since {a.base}, tag unchanged, loaded by {len(pages)} page{'s' if len(pages) != 1 else ''}: "
                  + ", ".join(names[:8]) + (" ..." if len(names) > 8 else ""))
        n_assets = len({(f["file"], f["v"]) for f in found if f["kind"] == "tag"})
        print(f"release manifest vs {a.base}: " + (f"{len(found)} problem{'s' if len(found) != 1 else ''} ({n_assets} stale asset tag{'s' if n_assets != 1 else ''}, {len(found) - sum(1 for f in found if f['kind'] == 'tag')} worker{'s' if len(found) - sum(1 for f in found if f['kind'] == 'tag') != 1 else ''}): bump the ?v= / the cache name, then publish" if found else "OK, nothing stale"))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
