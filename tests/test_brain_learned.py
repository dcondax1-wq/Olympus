"""WHAT THE BOTS LEARNED (big-learnview 2026-11-26; owner: "a system that is continuously learning and I can clearly tell"):
tools/web_public/brain/learned.html + learned.js + learned.css, fed by tools/build_brain_learn.py (learn.json 'learning' block).
  a. builder: the learning block (forward rules with progress / days to graduate, idea mill, live vs twin, health, LIT funnel, order
     flow, testing next), < / > kept as under / over / >= / <= (never dropped), learn.json fresh, rules sorted closest first
  s. static: the files, OLYMPUS NIGHT palette, no innerHTML / eval, GET only, the Brain links here (footer + every room's learning
     card), no secrets, the forbidden files untouched against origin/pc
  b. Chromium 390 x 844 (Node Playwright): no error, no sideways scroll, taps >= 44 px, 4 tiles, every idea on trial, the timeline +
     its LIT filter + 'show older', the funnel / mill / health cards; no learn.json -> an honest empty page; an old learn.json without
     the block -> each card says why. LEARNED_SHOTS=<dir> saves the shots; LEARNED_NO_BROWSER=1 skips b.
    python -X utf8 -m tests.test_brain_learned
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import re
import subprocess
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
PUB = os.path.join(ROOT, "tools", "web_public")
APP = os.path.join(PUB, "brain")
FORBIDDEN = ["tools/web_public/sw.js", "tools/build_web_dashboard.py", "tools/web_public/jarvis/apps.js", "tools/web_public/olympus/olympus.js"]
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(*p):
    with open(os.path.join(PUB, *p), encoding="utf-8") as fh:
        return fh.read()


def builder():
    import build_brain_learn as BL
    check("a. _s keeps the meaning of < / > (under / over / >= / <=)", BL._s("body >= 0.8 ATR, <0.8, x > 2, a -> b") == "body ≥ 0.8 ATR, under 0.8, x over 2, a → b",
          BL._s("body >= 0.8 ATR, <0.8, x > 2, a -> b"))
    fw = {"fwd_from": "2026-11-23", "data_end": "2026-11-27", "forward_sessions": 5, "rules": {
        "a": {"desc": "rule a", "bot": "LIT", "kind": "skip", "n": 15, "mean": 0.3, "sum": 4.5, "z": 0.2, "status": "watching",
              "band": {"n_bt": 254, "mu": 0.25, "sd": 1.0, "days": ["2021-11-01", "2026-11-20"]}},
        "b": {"desc": "rule b", "bot": "-", "kind": "standalone", "n": 20, "mean": 0.5, "sum": 10, "z": 1.0, "status": "promote",
              "band": {"n_bt": 50, "mu": 0.3, "sd": 1.0, "days": ["2021-11-01", "2026-11-20"]}},
        "c": {"desc": "rule c", "bot": "-", "kind": "standalone", "n": 0, "status": "error", "band": None}}}
    F = BL.forward_rows(fw)
    ids = [r["id"] for r in F["rules"]]
    a = F["rules"][ids.index("a")]
    check("a. forward rows: closest first, progress n/20, the days-to-graduate estimate from its backtest pace", ids == ["b", "a", "c"]
          and a["progress"] == 0.75 and a["need"] == 20 and a["eta_days"] is not None and 20 <= a["eta_days"] <= 30
          and "5 more new trades" in a["word"] and "yes/no card" in F["rules"][0]["word"] and F["rules"][2]["word"].startswith("could not"), F)
    d = BL.build()
    L = d.get("learning") or {}
    check("a. learn.json has the learning block (forward, idea mill, live vs twin, health, LIT funnel, order flow, next)",
          {"forward", "ideamill", "livegap", "health", "lit_setups", "of", "next", "promote_bar", "sources"} <= set(L), list(L))
    real = os.path.exists(os.path.join(ROOT, "research", "forward", "forward.json"))
    check("a. the forward rules come through (7 seeds) when research/forward/forward.json exists", not real or len((L.get("forward") or {}).get("rules") or []) >= 7)
    txt = json.dumps(L, ensure_ascii=False)
    check("a. no meaning-flipping ' = 0.8' leftovers in the learning text", not re.search(r"body = \d", txt))
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_brain_learn.py"), "--check"], capture_output=True, text=True, timeout=60)
    check("a. brain/learn.json fresh", r.returncode == 0, r.stdout + r.stderr)


def static():
    for f in ("learned.html", "learned.js", "learned.css"):
        check(f"s. brain/{f} exists", os.path.exists(os.path.join(APP, f)))
    src = read("brain", "learned.html") + read("brain", "learned.js") + read("brain", "learned.css")
    code = re.sub(r"/\*.*?\*/|(?<![:'\"])//[^\n]*|<!--.*?-->", "", src, flags=re.S)
    css = read("brain", "brain.css") + read("brain", "learned.css")
    check("s. OLYMPUS NIGHT palette", all(c in css for c in ("#000", "#16131e", "#3e255e", "#4d2e76", "#9d59ee", "#f1c14b", "#77db89")))
    check("s. no brown / olive / cyan", not re.search(r"brown|olive|cyan|#8b4513|#a0522d|#808000|#6b8e23|#556b2f|#00ffff", code, re.I))
    check("s. no innerHTML / eval / storage", "innerHTML" not in code and "eval(" not in code and "localStorage" not in code)
    check("s. read only: GET of learn.json only", "POST" not in code and code.count("fetch(") == 1 and "fetch('learn.json'" in code)
    check("s. the Brain links here: footer + every room's learning card", 'href="learned.html"' in read("brain", "index.html")
          and "learned.html#${r.id}" in read("brain", "brain.js"))
    check("s. no secrets / account ids", not re.search(r"(api[_-]?key|token|secret|password)\s*[:=]\s*['\"][^'\"]{6,}|\b(MFFU|FFN|APEX)[A-Z]*-?\d{3,}|ntfy\.sh/", src + read("brain", "learn.json"), re.I))
    has_pc = subprocess.run(["git", "rev-parse", "--verify", "-q", "origin/pc"], cwd=ROOT, capture_output=True, text=True, timeout=60).returncode == 0
    if not has_pc:   # a helper-branch guard: a checkout without origin/pc (the lead's landing tree, the PC) has nothing to compare
        print("  (s. forbidden-files guard skipped: no origin/pc in this checkout)")
    else:
        r = subprocess.run(["git", "diff", "--name-only", "origin/pc", "--", *FORBIDDEN], cwd=ROOT, capture_output=True, text=True, timeout=60)
        check("s. forbidden files untouched against origin/pc", r.returncode == 0 and not r.stdout.strip(), r.stdout + r.stderr)


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def browser():
    if os.environ.get("LEARNED_NO_BROWSER") == "1":
        print("[SKIP] b. LEARNED_NO_BROWSER=1", flush=True)
        return
    try:
        npm = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:  # noqa: BLE001
        npm = ""
    env = {**os.environ, "NODE_PATH": npm}
    if subprocess.run(["node", "-e", "require('playwright')"], capture_output=True, env=env, timeout=30).returncode != 0:
        print("[SKIP] b. Node Playwright not installed here", flush=True)
        return
    shots = os.environ.get("LEARNED_SHOTS", "")
    if shots:
        os.makedirs(shots, exist_ok=True)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=PUB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        r = subprocess.run(["node", os.path.join(ROOT, "tests", "brain_learned_browser.cjs"), f"http://127.0.0.1:{srv.server_address[1]}", shots],
                           capture_output=True, text=True, timeout=300, env=env)
    finally:
        srv.shutdown()
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        check("b. browser run", False, (r.stderr or r.stdout or str(e))[:600])
        return
    check("b. no fatal", "fatal" not in o, o.get("fatal"))
    check("b. no page / console error; GET only; nothing off the site", not o.get("errors") and not o.get("methods") and not o.get("off"),
          (o.get("errors"), o.get("methods"), o.get("off")))
    P = o.get("page") or {}
    check("b. no sideways scroll at 390; every tap target >= 44 px; black page", P.get("wide") is False and not P.get("small") and P.get("bg") == "rgb(0, 0, 0)",
          (P.get("wide"), P.get("small"), P.get("bg")))
    L = json.loads(read("brain", "learn.json")).get("learning") or {}
    n_rules = len((L.get("forward") or {}).get("rules") or [])
    check("b. 4 tiles, every idea on trial drawn, the timeline, next, LIT funnel, idea mill steps, health bands",
          P.get("tiles") == 4 and P.get("ideas") == n_rules and P.get("tl", 0) >= 1 and P.get("next", 0) >= 1 and P.get("funnel", 0) >= 3
          and P.get("mill") == 5 and P.get("health", 0) >= 1, {k: P.get(k) for k in ("tiles", "ideas", "tl", "next", "funnel", "mill", "health")})
    t = P.get("text") or ""
    check("b. plain words on the page: graduates / yes / no card / nothing switches on by itself", "graduates" in t and "yes / no card" in t and "nothing switches on by itself" in t)
    li = o.get("lit") or {}
    check("b. the LIT filter shows only LIT lessons", li.get("pressed") == "true" and li.get("chips") and set(li["chips"]) == {"LIT"}, li)
    if o.get("more"):
        check("b. 'Show older lessons' adds rows", o["more"][1] > o["more"][0], o["more"])
    check("b. no learn.json -> an honest empty page, no error", "Could not load" in (o.get("empty") or "") and not o.get("emptyErrors"), (o.get("empty"), o.get("emptyErrors")))
    check("b. an old learn.json (no learning block) -> the cards say why, the lessons still show", "No idea is on trial yet" in ((o.get("old") or {}).get("grad") or "")
          and (o.get("old") or {}).get("tl") == 1 and not o.get("oldErrors"), (o.get("old"), o.get("oldErrors")))
    check("b. the Brain page footer links to the learned page", o.get("brainLink") is True)


def main():
    builder()
    static()
    browser()
    n, ok = len(RES), sum(RES)
    print(f"\nWHAT THE BOTS LEARNED: {ok}/{n} {'ALL PASS' if ok == n else 'FAILED'}", flush=True)
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
