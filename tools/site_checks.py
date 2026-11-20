"""Site consistency checks: the faults that broke the phone / PC site this week, found before a phone does (day-quality 2026-11-20).

    python -X utf8 tools/site_checks.py          one line per fault, exit 1 if any
    python -X utf8 tools/site_checks.py --json   the same as JSON

  kalshi_cache   kalshi/sw.js CACHE must be 'kalshi-' + the ?v= of kalshi.css AND kalshi.js (both equal), in the page and the worker
  worker_tag     a ?v= file a service worker precaches (its SHELL list) carries the same tag as every page that loads it
                 (else the phone keeps serving the old copy from the worker's cache)
  launcher       tools/web_public/launcher.js and web_next/js/next/launcher.js stay byte-identical (the phone and the PC launcher)
  generated_gap  (the PC only, from `git status`) a tracked file changed on the PC that is not a hand edit's kind of file but is not on
                 the bot-made list engine/generated_files.GENERATED either: the next update stops on it

Read-only: never writes a file. Used by engine/self_heal.py (report-only items, no alert) and tests/test_site_checks.py (the repo
itself must pass: a red here is a landing that forgot a bump). The fix for every fault is Claude's (tools/bump_versions.py --apply,
copy the launcher), never the owner's.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKERS = ("tools/web_public/sw.js", "tools/web_public/jarvis/sw.js", "tools/web_public/kalshi/sw.js", "web_next/sw.js")
LAUNCHERS = ("tools/web_public/launcher.js", "web_next/js/next/launcher.js")
KALSHI = ("tools/web_public/kalshi/sw.js", "tools/web_public/kalshi/index.html")
# tracked files the PC rewrites that look bot-made (data refreshes, caches, exports): if one is dirty and NOT in GENERATED, the update
# stops on it. Hand-edit kinds (code, models, accounts, notes) are never in this list.
BOTLIKE = re.compile(r"^(data/|cache/|reports/|research/lit/[^/]+\.json$|research/runs/[^/]+\.json$|tools/web_public/.+\.json$|tools/web_hub_snapshot\.json$)")
HAND = re.compile(r"(^accounts/|live_model|second_model|\.py$|\.ps1$|\.bat$|notes|STATE\.md$)", re.I)
TAG = r"([A-Za-z]*\d+)"


def _read(root, rel):
    try:
        with open(os.path.join(root, *rel.split("/")), encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def _item(kind, text, paths=()):
    return {"kind": kind, "text": text, "paths": list(paths)}


def kalshi_cache(root=ROOT) -> list:
    sw, page = (_read(root, r) for r in KALSHI)
    if sw is None or page is None:
        return []
    m = re.search(r"const CACHE = 'kalshi-" + TAG + "'", sw)
    if not m:
        return [_item("kalshi_cache", "kalshi/sw.js: no CACHE = 'kalshi-<tag>' line", KALSHI[:1])]
    cache = m.group(1)
    tags = {}
    for name in ("kalshi.css", "kalshi.js"):
        for where, txt in (("index.html", page), ("sw.js", sw)):
            for t in re.findall(re.escape(name) + r"\?v=" + TAG, txt):
                tags.setdefault(t, []).append(f"{where} {name}")
    bad = {t: w for t, w in tags.items() if t != cache}
    if not tags or not bad:
        return []
    return [_item("kalshi_cache", f"kalshi cache 'kalshi-{cache}' does not match " + "; ".join(f"{', '.join(w)} ?v={t}" for t, w in sorted(bad.items()))
                  + " (fix: python tools/bump_versions.py --apply)", KALSHI)]


def worker_tags(root=ROOT) -> list:
    """A worker precaches x.js?v=A while every page that loads x.js asks for x.js?v=B."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    try:
        import bump_versions as B                     # the tool's own reference finder (src= / href= / script strings / worker lists)
    except Exception:                                 # noqa: BLE001
        return []
    finally:
        sys.path.pop(0)
    repo = B.Repo(root, "HEAD", changed=[])
    refs = B.collect_refs(repo, B.site_files(repo))
    pages: dict = {}
    for r in refs:
        if not r.file.endswith("/sw.js"):
            pages.setdefault(r.target, set()).add(r.tag)
    out = []
    for w in WORKERS:
        for r in (x for x in refs if x.file == w):
            used = pages.get(r.target)
            if used and r.tag not in used:
                out.append(_item("worker_tag", f"{w} precaches {r.literal}?v={r.tag} but the pages load ?v={'/'.join(sorted(used))} "
                                               "(fix: python tools/bump_versions.py --apply, or set the worker's entry to the page's tag)", (w, r.target)))
    return out


def launcher(root=ROOT) -> list:
    a, b = (_read(root, r) for r in LAUNCHERS)
    if a is None or b is None or a.rstrip() == b.rstrip():
        return []
    return [_item("launcher", "the phone and PC launchers differ (fix: copy tools/web_public/launcher.js over web_next/js/next/launcher.js, "
                              "or the reverse, whichever is newer)", LAUNCHERS)]


def generated_gap(porcelain: str) -> list:
    """From `git status --porcelain --untracked-files=no`: dirty tracked bot-like files that are not on the bot-made list."""
    try:
        sys.path.insert(0, ROOT)
        from engine.generated_files import split_dirty
    except Exception:                                 # noqa: BLE001
        return []
    finally:
        sys.path.pop(0)
    _gen, other = split_dirty(porcelain or "")
    gap = [p for p in other if BOTLIKE.match(p) and not HAND.search(p)]
    if not gap:
        return []
    return [_item("generated_gap", f"{len(gap)} tracked file(s) the PC rewrote are not on the bot-made list, so the next update stops on them: "
                                   f"{', '.join(gap[:3])} (Claude: add them to engine/generated_files.GENERATED)", gap)]


def run(root=ROOT, porcelain: str | None = None) -> list:
    out = []
    for fn in (kalshi_cache, worker_tags, launcher):
        try:
            out += fn(root)
        except Exception as e:                        # noqa: BLE001
            out.append(_item(fn.__name__, f"check failed softly ({e.__class__.__name__}: {str(e)[:80]})"))
    if porcelain is not None:
        out += generated_gap(porcelain)
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    items = run(ROOT)
    if "--json" in argv:
        print(json.dumps(items, indent=1))
    else:
        for it in items:
            print(f"[{it['kind']}] {it['text']}")
        print("site checks: " + ("all fine" if not items else f"{len(items)} fault(s)"))
    return 1 if items else 0


if __name__ == "__main__":
    sys.exit(main())
