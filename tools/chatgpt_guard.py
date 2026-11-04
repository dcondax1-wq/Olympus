"""Path guard for pull requests from ChatGPT / Codex (branches `chatgpt/*`).

    python tools/chatgpt_guard.py [--base origin/main] [--files a b c]

Fails (exit 1) when the PR touches anything outside the safe area, so the owner can merge green PRs with one tap.
Safe area: handoff/, docs/, tests/, research/writeups/, tools/web_public/<app>/ (not the root page, not workers, not the app list).
Always forbidden: engine/, live_model*.json, .github/, data/, any sw.js, tools/build_web_dashboard.py, jarvis/apps.js,
olympus/olympus.js, secrets (.env*, keys, tv*.json, alerts.json), and files over 2 MB.
Also checks: every changed .json parses; no secret-looking strings in added lines.
"""
import argparse, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ALLOW = ("handoff/", "docs/", "tests/", "research/writeups/", "tools/web_public/", "web_next/js/next/", "web_next/css/")
DENY_EXACT = {"tools/build_web_dashboard.py", "tools/web_public/jarvis/apps.js", "tools/web_public/olympus/olympus.js",
              "tools/web_public/index.html", "tools/web_public/olympus/apps-list.js", "web_next/js/next/apps-list.js",
              "CLAUDE.md", "AGENTS.md", "live_model.json", "live_model_lit.json"}
DENY_PREFIX = ("engine/", ".github/", "data/", "cache/", "tools/cronos/", "tools/planner_patches/", "scripts/")
DENY_NAME = re.compile(r"(^|/)(sw\.js|\.env[^/]*|tv(_device)?\.json|alerts\.json|autostart\.json|live_state\.json|memory\.db|.*\.pem|.*\.key)$")
SECRET = re.compile(r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|xox[bp]-[A-Za-z0-9-]{10,})")


def changed(base):
    r = subprocess.run(["git", "diff", "--name-only", "--diff-filter=ACMRD", f"{base}...HEAD"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        r = subprocess.run(["git", "diff", "--name-only", "--diff-filter=ACMRD", base], cwd=ROOT, capture_output=True, text=True)
    return [x for x in r.stdout.splitlines() if x.strip()]


def judge(files, added_text=None):
    """returns a list of (file, reason); empty = clean"""
    bad = []
    for f in files:
        f = f.replace("\\", "/")
        if f in DENY_EXACT or any(f.startswith(p) for p in DENY_PREFIX) or DENY_NAME.search(f):
            bad.append((f, "this file is off limits for ChatGPT PRs (bots, workers, publish, secrets or the app list): ask the owner/Claude"))
        elif not any(f.startswith(p) for p in ALLOW):
            bad.append((f, "outside the safe area (handoff, docs, tests, research/writeups, one app folder under tools/web_public)"))
    apps = {f.split("/")[2] for f in files if f.startswith("tools/web_public/") and f.count("/") >= 3 and f.split("/")[2] != "olympus"}
    if len(apps) > 1:
        bad.append((", ".join(sorted(apps)), "more than one app folder in one PR: split it (one app per PR)"))
    blocked = {f for f, _ in bad}
    for f in files:
        p = os.path.join(ROOT, f)
        if f not in blocked and os.path.isfile(p):
            if os.path.getsize(p) > 2_000_000:
                bad.append((f, "file over 2 MB"))
            if f.endswith(".json"):
                try:
                    json.load(open(p, encoding="utf-8"))
                except Exception as e:
                    bad.append((f, f"invalid JSON: {e}"))
    if added_text and SECRET.search(added_text):
        bad.append(("(diff)", "something that looks like a key or token was added: remove it and never paste secrets"))
    return bad


def added_lines(base):
    r = subprocess.run(["git", "diff", "-U0", f"{base}...HEAD"], cwd=ROOT, capture_output=True, text=True)
    return "\n".join(l[1:] for l in r.stdout.splitlines() if l.startswith("+") and not l.startswith("+++"))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--files", nargs="*")
    a = ap.parse_args(argv)
    files = a.files if a.files is not None else changed(a.base)
    bad = judge(files, None if a.files is not None else added_lines(a.base))
    print(f"chatgpt-guard: {len(files)} changed file(s)")
    for f, why in bad:
        print(f"  BLOCKED  {f}: {why}")
    print("chatgpt-guard: " + ("BLOCKED" if bad else "OK"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
