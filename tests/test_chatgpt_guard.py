"""tools/chatgpt_guard.py: the path guard for ChatGPT / Codex pull requests (pure python, no git needed)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import chatgpt_guard as G

ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    if cond: ok += 1; print("[PASS]", name)
    else: fail += 1; print("[FAIL]", name, "->", info)

check("one app folder + its test + the queue is clean", not G.judge(["tools/web_public/cities/scene.js", "tests/test_cities_page.py", "handoff/QUEUE.md"]))
check("engine, live model, workflows, data are blocked", len(G.judge(["engine/lit.py", "live_model.json", ".github/workflows/x.yml", "data/NQ_5m.csv"])) == 4)
check("any sw.js, apps.js, olympus.js, build script, root page are blocked", len(G.judge(["tools/web_public/sw.js", "tools/web_public/jarvis/sw.js", "tools/web_public/jarvis/apps.js", "tools/web_public/olympus/olympus.js", "tools/build_web_dashboard.py", "tools/web_public/index.html"])) == 6)
check("secrets and keys are blocked", len(G.judge([".env", ".env.local", "tv.json", "alerts.json", "keys/id.pem"])) == 5)
check("two app folders in one PR are blocked", any("one app per PR" in w for _, w in G.judge(["tools/web_public/cities/a.js", "tools/web_public/oracle/b.js"])))
check("the shared kit folder does not count as an app", not G.judge(["tools/web_public/cities/a.js", "tools/web_public/olympus/fx-core.js"]))
check("outside the safe area is blocked", len(G.judge(["research/lit/lit_final.json", "random.txt"])) == 2)
check("a key in the added text is blocked", any("key or token" in w for _, w in G.judge(["handoff/x.md"], "token = ghp_" + "a" * 30)))
check("plain added text is fine", not G.judge(["handoff/x.md"], "hello world 1234"))
check("main() on an explicit file list returns 0 / 1", G.main(["--files", "handoff/QUEUE.md"]) == 0 and G.main(["--files", "engine/lit.py"]) == 1)
print(f"\nchatgpt guard: {ok}/{ok + fail} " + ("ALL PASS" if not fail else "FAILED"))
sys.exit(1 if fail else 0)
