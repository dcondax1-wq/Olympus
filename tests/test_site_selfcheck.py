"""tools/site_selfcheck.py (job 23): a built site that lacks an expected file says so loudly, and a whole one passes.
A fake site = the page sources copied the way the build copies them, plus the generated files; then files are taken away.
    python -X utf8 -m tests.test_site_selfcheck
"""
from __future__ import annotations

import io
import contextlib
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import site_selfcheck as SC  # noqa: E402

SRC = os.path.join(ROOT, "tools", "web_public")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def fake_site(dst):
    shutil.copytree(SRC, dst, dirs_exist_ok=True)
    os.makedirs(os.path.join(dst, "pc"), exist_ok=True)
    shutil.copy(os.path.join(ROOT, "scripts", "move_bot.ps1"), os.path.join(dst, "pc", "move_bot.ps1"))
    for n in ("data.json", "home.json"):
        with open(os.path.join(dst, n), "w", encoding="utf-8") as fh:
            fh.write("{}")
    os.makedirs(os.path.join(dst, "planner"), exist_ok=True)
    with open(os.path.join(dst, "planner", "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<html></html>")


def fake_root(dst, sparse="", reads=""):
    """a repo root with the few source files the check looks at; a workflow only when `sparse` is given"""
    for rel in ("scripts/move_bot.ps1", "scripts/add_planner.sh", "tools/build_web_dashboard.py"):
        os.makedirs(os.path.dirname(os.path.join(dst, rel)), exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), os.path.join(dst, rel))
    os.makedirs(os.path.join(dst, "tools", "kalshi_kit", "public"), exist_ok=True)
    with open(os.path.join(dst, "tools", "kalshi_kit", "public", "SETUP.md"), "w", encoding="utf-8") as fh:
        fh.write("x")
    if sparse:
        os.makedirs(os.path.join(dst, ".github", "workflows"), exist_ok=True)
        with open(os.path.join(dst, ".github", "workflows", "cloud-monitor.yml"), "w", encoding="utf-8") as fh:
            fh.write("with:\n  sparse-checkout: |\n" + "".join(f"    {x}\n" for x in sparse) + "  next: 1\n")
        with open(os.path.join(dst, "tools", "build_web_dashboard.py"), "w", encoding="utf-8") as fh:
            fh.write(reads)
    return dst


def run(site, root=None):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = SC.main(["--site", site, "--root", root or ROOT_FAKE])
    return code, buf.getvalue()


ROOT_FAKE = ""


def main():
    tmp = tempfile.mkdtemp(prefix="sitecheck_")
    try:
        global ROOT_FAKE
        ROOT_FAKE = fake_root(os.path.join(tmp, "root"))
        site = os.path.join(tmp, "site")
        fake_site(site)
        code, out = run(site)
        check("a. a complete site passes (exit 0, no ::error::, the table printed)", code == 0 and "::error" not in out and "| what" in out and "checks OK" in out, out[-600:])
        os.remove(os.path.join(site, "pc", "move_bot.ps1"))
        code, out = run(site)
        check("b. pc/move_bot.ps1 missing: exit 1 and a ::error:: line naming it (the silent skip of a copy)", code == 1 and "::error title=site_selfcheck MISSING::pc/move_bot.ps1" in out, out[-500:])
        shutil.copy(os.path.join(ROOT, "scripts", "move_bot.ps1"), os.path.join(site, "pc", "move_bot.ps1"))
        os.remove(os.path.join(site, "bridge", "status.json"))
        os.remove(os.path.join(site, "cities", "jarvis.json"))
        shutil.rmtree(os.path.join(site, "kalshicity"))
        code, out = run(site)
        check("c. bridge/status.json, the Cities card and the Kalshi City folder missing: each named, 1 app row says MISSING",
              code == 1 and "bridge/status.json" in out and "cities/jarvis.json" in out and "kalshicity/edges.json" in out and "| kalshicity/" in out and "MISSING" in out, out[-900:])
        fake_site(site)
        with open(os.path.join(site, "bridge", "status.json"), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        with open(os.path.join(site, "cities", "cities.json"), "w", encoding="utf-8") as fh:
            fh.write("")
        code, out = run(site)
        check("d. a broken JSON and an empty file are named too (BAD JSON, EMPTY)", code == 1 and "BAD JSON" in out and "EMPTY" in out, out[-600:])
        fake_site(site)
        with open(os.path.join(site, "pc", "move_bot.ps1"), "a", encoding="utf-8") as fh:
            fh.write("# drift")
        code, out = run(site)
        check("e. a site copy that differs from scripts/move_bot.ps1 is flagged DIFFERENT", code == 1 and "DIFFERENT" in out, out[-400:])
        code, out = run(os.path.join(tmp, "nothing"))
        check("f. no site folder at all: exit 1 and one ::error:: line", code == 1 and out.count("::error") == 1, out)
        before = sorted(os.listdir(site))
        run(site)
        check("g. read-only: the site folder is unchanged by a check", sorted(os.listdir(site)) == before)
        r2 = fake_root(os.path.join(tmp, "root2"), ["/engine/", "/research/lit/*.md", "/data/VIX_1d.csv"],
                       'a = os.path.join(ROOT, "research", "lit", "funded_path.json")\nb = os.path.join(ROOT, "research", "lit", "notes.md")\n'
                       'c = "data/VIX_1d.csv"\nd = "data/NQ_5m.csv"\ne = os.path.join(ROOT, "research", "lab")\n')
        fake_site(site)
        code, out = run(site, r2)
        gaps = [g[0] for g in SC.sparse_gaps(r2)]
        check("i. a file the build reads that the workflow's sparse-checkout does not bring is a GAP (a silent skip in the cloud); covered files and folders are not",
              code == 1 and sorted(gaps) == ["data/NQ_5m.csv", "research/lit/funded_path.json"] and "::error title=site_selfcheck GAP::sparse-checkout lacks research/lit/funded_path.json" in out, (gaps, out[-400:]))
        wf = open(os.path.join(ROOT, ".github", "workflows", "cloud-monitor.yml"), encoding="utf-8").read()
        check("h. the workflow runs it after the build, continue-on-error (loud, never stops the publish)",
              "python tools/site_selfcheck.py --site site" in wf and wf.index("site_selfcheck") > wf.index("build_web_dashboard.py") and "continue-on-error: true" in wf[wf.index("site_selfcheck") - 400:wf.index("site_selfcheck") + 100])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\nsite selfcheck: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    sys.exit(0 if n == len(RES) else 1)


if __name__ == "__main__":
    main()
