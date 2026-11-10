"""Jarvis BRAIN skills (2026-11-10): tools/web_public/jarvis/{router,jdata,skills,actions,memstore,nudges}.js and their hooks in
brain.js and voice-mode.js. Checks:
  a. the files: every new module parses as an ES module, is Safari 16 safe (no regex lookbehind), has no network call except the
     loader's relative GETs, and holds no key; brain.js wires `skills` (optional) and voice-mode.js has hold-to-talk
  b. tests/test_jarvis_skills.mjs in node (TZ America/New_York): 60+ router phrasings, answers with $ + R + source, "I don't have
     that", actions that ask first, memory export/import, nudges
  c. docs/JARVIS_API.md names every exported function and the storage keys
    python -X utf8 -m tests.test_jarvis_skills      (node only; ~5 s)
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JV = os.path.join(ROOT, "tools", "web_public", "jarvis")
RES: list = []
NEW = ["router.js", "jdata.js", "skills.js", "actions.js", "memstore.js", "nudges.js"]


def check(name, ok, info=""):
    RES.append((name, bool(ok), info))
    print(("[PASS] " if ok else "[FAIL] ") + name + ((" :: " + str(info)[:600]) if (info and not ok) else ""))


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def main() -> int:
    if not shutil.which("node"):
        check("node is installed", False, "node not found")
        return 1
    for f in NEW + ["brain.js", "voice-mode.js"]:
        src = read(os.path.join(JV, f))
        ok = subprocess.run(["node", "--check", "--input-type=module"], input=src, capture_output=True, text=True)
        check(f"{f} parses as an ES module", ok.returncode == 0, ok.stderr[-400:])
        check(f"{f} is Safari 16 safe (no lookbehind)", not re.search(r"\(\?<[=!]", src))
    for f in NEW:
        src = read(os.path.join(JV, f))
        check(f"{f}: no secrets and no absolute URLs", not re.search(r"gsk_[A-Za-z0-9]{8}|AIza[A-Za-z0-9]{8}|github_pat_[A-Za-z0-9]{8}|https?://", re.sub(r"//.*", "", src)))
        check(f"{f}: no DOM, no eval", not re.search(r"\bdocument\.|\bwindow\.|\beval\(|new Function", src))
    core = read(os.path.join(JV, "router.js")) + read(os.path.join(JV, "nudges.js"))
    check("router and nudges have no fetch at all", "fetch(" not in core)
    check("only jdata.js fetches, and only relative files", "fetchFn(" in read(os.path.join(JV, "jdata.js")) and not re.search(r"fetch\(\s*['\"]https?", read(os.path.join(JV, "jdata.js"))))
    check("actions never mention an order or arming", not re.search(r"place_order|armLive|go_live|submitOrder", read(os.path.join(JV, "actions.js"))))
    brain = read(os.path.join(JV, "brain.js"))
    check("brain.js: optional skills wiring, yes/no for a pending write, skill context for smart mode", "skillsAsk" in brain and "skills.pending" in brain and "TOOL RESULTS" in brain and "o.skills === false" in brain)
    check("brain.js: a skill's 'I don't have that' only replaces the generic fallback", "missedSkill" in brain)
    vm = read(os.path.join(JV, "voice-mode.js"))
    check("voice-mode.js: hold to talk, status line, iOS default, kept choice", all(x in vm for x in ["pttDown", "pttUp", "vmState", "PTT_KEY", "isIOS", "statusText", "pagehide"]))
    mem = read(os.path.join(JV, "memstore.js"))
    check("memory key is jarvis.* so Settings lists and exports it", "'jarvis.memory.v1'" in mem and "olympus-data" in mem)
    doc_p = os.path.join(ROOT, "docs", "JARVIS_API.md")
    check("docs/JARVIS_API.md exists", os.path.exists(doc_p))
    if os.path.exists(doc_p):
        d = read(doc_p)
        names = ["route(", "createSkills", "handle(", "contextFor", "nudges(", "createActions", "createMemStore", "loadSources", "jarvis.memory.v1", "planner.agora.v1", "compass.state.v1",
                 "exportJson", "importJson", "plan(", "confirm(", "cancel()", "#zone=", "#quiz", "pttDown", "jarvis.vmPtt", "sw.js"]
        miss = [n for n in names if n not in d]
        check("JARVIS_API.md names every export, key and the wiring", not miss, ", ".join(miss))
    r = subprocess.run(["node", os.path.join(ROOT, "tests", "test_jarvis_skills.mjs")], capture_output=True, text=True, timeout=120, env={**os.environ, "TZ": "America/New_York"})
    out = (r.stdout + r.stderr).strip()
    check("node: router (60+ phrasings), answers, actions, memory, nudges", r.returncode == 0, out[-1500:])
    m = re.search(r"(\d+) passed, (\d+) failed", out)
    if m:
        print(f"   node unit tests: {m.group(1)} passed, {m.group(2)} failed")
    bad = [n for n, ok, _ in RES if not ok]
    print(f"\njarvis skills: {len(RES) - len(bad)}/{len(RES)} {'ALL PASS' if not bad else 'FAILED: ' + '; '.join(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
