"""tools/gh_publish.py: the cloud build never claims an account is disconnected; runs/ never goes out; paced."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import gh_publish as G

ok = bad = 0
def check(name, cond, info=""):
    global ok, bad
    if cond: ok += 1
    else: bad += 1; print("FAIL", name, info)

d = {"accounts": [{"name": "A", "connected": False}, {"name": "B", "connected": True}], "x": [{"connected": False}]}
n = G.unknown_connection(d)
check("connected False -> None everywhere, True kept", n == 2 and d["accounts"][0]["connected"] is None and d["accounts"][1]["connected"] is True and d["x"][0]["connected"] is None, d)
check("runs/ (233 MB of backtests) never goes out", "runs/" in G.SKIP)
check("paced: a few publishes a day at most", 1 <= G.MAX_PER_DAY <= 6)
with tempfile.TemporaryDirectory() as t:
    p = os.path.join(t, "pushes.log")
    open(p, "w").write("2026-11-18T10:00:00+00:00 a\n2026-11-18T12:00:00+00:00 b\n2026-11-17T09:00:00+00:00 c\n")
    check("pushes today counted from the log", G.pushes_today(p, "2026-11-18") == 2 and G.pushes_today(os.path.join(t, "none"), "2026-11-18") == 0)
with tempfile.TemporaryDirectory() as t:
    out, repo = os.path.join(t, "out"), os.path.join(t, "repo")
    for rel, txt in {"a.html": "A", "sub/b.json": "B", "runs/x.json": "R"}.items():
        os.makedirs(os.path.dirname(os.path.join(out, rel)), exist_ok=True); open(os.path.join(out, rel), "w").write(txt)
    for rel, txt in {".git/HEAD": "ref", "a.html": "A", "sub/b.json": "old", "gone/c.txt": "C", ".nojekyll": ""}.items():
        os.makedirs(os.path.dirname(os.path.join(repo, rel)), exist_ok=True); open(os.path.join(repo, rel), "w").write(txt)
    os.utime(os.path.join(repo, "a.html"), (1000, 1000))
    c, r = G.mirror(out, repo)
    got = sorted(os.path.relpath(os.path.join(d, f), repo) for d, _, fs in os.walk(repo) for f in fs)
    check("mirror: only the changed file copied, the gone file (and its empty folder) removed, .git kept, runs/ never",
          (c, r) == (1, 1) and got == [".git/HEAD", ".nojekyll", "a.html", "sub/b.json"] and open(os.path.join(repo, "sub/b.json")).read() == "B", (c, r, got))
    check("mirror: an unchanged file keeps its mtime (git does not re-hash it)", os.path.getmtime(os.path.join(repo, "a.html")) == 1000)
src = open(G.__file__, encoding="utf-8").read()
check("never touches the bot or live models", "from engine" not in src and "import engine" not in src and "open(\"live_model" not in src)
check("uses pc_publish's privacy-checked folder build", '"--provider", "folder"' in src and "site_privacy.private_file" in src)
print(f"{ok}/{ok + bad} passed")
sys.exit(1 if bad else 0)
