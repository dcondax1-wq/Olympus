"""tools/site_checks.py (day-quality 2026-11-20): the phone-cache and launcher faults of this week, on fixtures and on the real tree.

  a. the real repo passes (a red here = a landing that forgot a bump or copied one launcher only)
  b. fixtures: a Kalshi cache ahead of its css/js, css != js, a worker precaching an old ?v, launcher drift: each found, named
  c. generated_gap: a dirty bot-like tracked file off the GENERATED list is named; generated, code and account files are not
  d. engine/self_heal's "site" check turns them into report-only items (info: never an owner alert)
    python -X utf8 -m tests.test_site_checks
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import site_checks as SC  # noqa: E402

RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:600]})" if detail and not cond else ""))


def site(files):
    root = tempfile.mkdtemp(prefix="le_sitechk_")
    for rel, text in files.items():
        p = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
    return root


GOOD = {
    "tools/web_public/kalshi/index.html": '<link rel="stylesheet" href="kalshi.css?v=k44"><script src="kalshi.js?v=k44"></script>\n',
    "tools/web_public/kalshi/kalshi.css": "a{}\n", "tools/web_public/kalshi/kalshi.js": "//k\n",
    "tools/web_public/kalshi/sw.js": "const CACHE = 'kalshi-k44';\nconst SHELL = ['./', './kalshi.css?v=k44', './kalshi.js?v=k44'];\n",
    "tools/web_public/jarvis/index.html": '<script type="module" src="./portal.js?v=p2"></script>\n',
    "tools/web_public/jarvis/portal.js": "//p\n",
    "tools/web_public/jarvis/sw.js": "const CACHE = 'jarvis-v9';\nconst SHELL = ['./', './portal.js?v=p2'];\n",
    "tools/web_public/launcher.js": "var x = 1;\n", "web_next/js/next/launcher.js": "var x = 1;\n",
}


def main() -> int:
    items = SC.run(ROOT)
    check("a. the real repo: Kalshi cache = its css/js ?v, every worker precaches the tags the pages load, both launchers identical",
          items == [], [i["text"] for i in items])
    roots = []
    try:
        r = site(GOOD); roots.append(r)
        check("b. a consistent fixture is all fine", SC.run(r) == [], SC.run(r))
        bad = dict(GOOD)
        bad["tools/web_public/kalshi/sw.js"] = GOOD["tools/web_public/kalshi/sw.js"].replace("kalshi-k44", "kalshi-k45")
        r = site(bad); roots.append(r)
        k = SC.kalshi_cache(r)
        check("b. a Kalshi cache that ran ahead of its css/js (k45 vs k44) is named", len(k) == 1 and "kalshi-k45" in k[0]["text"] and "?v=k44" in k[0]["text"], k)
        bad = dict(GOOD)
        bad["tools/web_public/kalshi/index.html"] = GOOD["tools/web_public/kalshi/index.html"].replace("kalshi.js?v=k44", "kalshi.js?v=k45")
        r = site(bad); roots.append(r)
        k = SC.kalshi_cache(r)
        check("b. kalshi.js moved alone (k45 in the page, cache k44) is named", len(k) == 1 and "index.html kalshi.js ?v=k45" in k[0]["text"], k)
        w = [i for i in SC.worker_tags(r) if "kalshi.js" in i["text"]]
        check("b. ... and the worker precaching kalshi.js?v=k44 while the page loads k45 too", len(w) == 1 and "?v=k44" in w[0]["text"], SC.worker_tags(r))
        bad = dict(GOOD)
        bad["tools/web_public/jarvis/sw.js"] = GOOD["tools/web_public/jarvis/sw.js"].replace("portal.js?v=p2", "portal.js?v=p1")
        r = site(bad); roots.append(r)
        w = SC.worker_tags(r)
        check("b. the Jarvis worker precaching portal.js?v=p1 while the page loads p2 is named", len(w) == 1 and "portal.js?v=p1" in w[0]["text"], w)
        bad = dict(GOOD)
        bad["web_next/js/next/launcher.js"] = "var x = 2;\n"
        r = site(bad); roots.append(r)
        check("b. launcher drift between the phone and PC copies is named", [i["kind"] for i in SC.run(r)] == ["launcher"], SC.run(r))
    finally:
        for r in roots:
            shutil.rmtree(r, ignore_errors=True)
    por = (" M tools/web_public/trading/trades.json\n M data/VIX_1d.csv\n M engine/live.py\n M accounts/zl.json\n M research/lit/new_check.json\n"
           " M data/live_notes.json\n M live_model.json\n")
    g = SC.generated_gap(por)
    paths = g[0]["paths"] if g else []
    check("c. generated_gap names the bot-like dirty files off the bot-made list (trades.json, research/lit/new_check.json)",
          sorted(paths) == ["research/lit/new_check.json", "tools/web_public/trading/trades.json"], paths)
    check("c. ... never a generated one (data/VIX_1d.csv), code, an account, a model or notes", not any(p in paths for p in
          ("data/VIX_1d.csv", "engine/live.py", "accounts/zl.json", "data/live_notes.json", "live_model.json")), paths)
    check("c. a clean status is no fault", SC.generated_gap("") == [])
    try:
        from engine import self_heal as SH
        r = site(dict(GOOD, **{"web_next/js/next/launcher.js": "var x = 2;\n"})); roots = [r]
        ctx = SH.Ctx(root=r, apply=True, git=lambda *a, **k: (0, " M tools/web_public/trading/trades.json\n"))
        its = SH.fix_site(ctx)
        check("d. self_heal 'site': report-only items (status info: never an alert), one per fault",
              its and all(i["status"] == "info" for i in its) and {i["key"] for i in its} == {"site_launcher", "site_generated_gap"}, its)
        check("d. self_heal 'site' is in the hourly remedies and changes no file",
              any(n == "site" for n, _f in SH.REMEDIES) and open(os.path.join(r, "web_next", "js", "next", "launcher.js")).read() == "var x = 2;\n")
        shutil.rmtree(r, ignore_errors=True)
    except Exception as e:  # noqa: BLE001
        check("d. self_heal 'site' check", False, repr(e))
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
