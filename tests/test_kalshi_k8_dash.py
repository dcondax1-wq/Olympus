"""The K8 day dashboard (day-kalshi 2026-11-20, live Monday 11-23 with $55): the Kalshi page's K8 status card (tools/web_public/kalshi/) grows
today's 5 windows with a countdown each (Thanksgiving / UK holidays skipped), price vs fair per live leg, the last 5 bets in plain words, the
day / week / peak stop bars and edge health (Healthy / Watch / OFF line crossed), from the PC card's new k8 fields (dy, e, lg) and the site's
kalshi/k8.json (Kalshi's public results); the Dionysus desk gets a "K8 today" panel from ../kalshi/k8.json.
  a. static: the page reads k8.json same-origin with a 3 s limit, keeps the old K8 card ids, versions bumped together, the fixture's shape
  b. Chromium 390 x 844 (node Playwright, tests/kalshi_k8_dash.cjs) with a frozen clock: windows + countdowns, Thanksgiving skip, price vs fair
     colours, the bet log, three stop bars, the verdicts, a missing k8.json / an old PC card / junk degrade cleanly, Dionysus shows / hides the panel
    python -X utf8 -m tests.test_kalshi_k8_dash          (--static: part a only; run the browser part under flock -w 2400 /tmp/olympus_browser.lock)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
KS = os.path.join(WEB, "kalshi")
FX = os.path.join(ROOT, "tests", "fixtures", "k8_plan_sample.json")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(info)[:500]}"))


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def part_static():
    js, html, css = read(os.path.join(KS, "kalshi.js")), read(os.path.join(KS, "index.html")), read(os.path.join(KS, "kalshi.css"))
    check("a. k8.json is read from the page's own folder, no-cache, 3 s at most (rwGet), every 15 min; nothing else new is fetched",
          "rwGet('k8.json', 3000)" in js and "setInterval(k8Load, 15 * 60e3)" in js and "cache: 'no-cache'" in js)
    check("a. the old K8 card ids stay (#k8s, #k8s-g, #k8s-x, #k8s-cd, #k8s-m) and the new parts have their own (#k8s-w windows, #k8s-y price / log / health)",
          all(f'id="{i}"' in html for i in ("k8s", "k8s-g", "k8s-x", "k8s-cd", "k8s-m", "k8s-w", "k8s-y")))
    v = re.findall(r'kalshi\.(?:css|js)\?v=(\w+)', html)
    check("a. kalshi.css and kalshi.js carry the same ?v= (k53); the worker's CACHE / SHELL are the lead's (research/handoff/2026-11-20/kalshi/LEAD_WIRES_dashboard.md)",
          v == ["k53", "k53"], v)
    code = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", js, flags=re.S))
    risky = [w for w in ("(?<=", "(?<!", ".toSorted(", ".findLast(", "AbortSignal.timeout", "structuredClone", ".at(-") if w in code]
    check("a. Safari 16 safe (no lookbehind, findLast, AbortSignal.timeout, .at(-1))", not risky, risky)
    check("a. the new styles: the windows list, price vs fair colours, the verdict colours", all(x in css for x in (".k8w li", ".k8-g", ".k8-r", ".k8e-v.off", ".k8w li.pp")))
    fx = json.loads(read(FX))
    legs = {x["code"]: x for x in fx["legs"]}
    check("a. the fixture is shaped like k8.json (v 1, kind k8_plan, the rule, 5 legs with 3 live g5 / g17 / s17, the pool, skip lists, noise) and says it is a test fixture",
          fx["v"] == 1 and fx["kind"] == "k8_plan" and fx["rule"]["min_win"] == 0.58 and sorted(legs) == ["g17", "g5", "s16", "s17", "s5"]
          and sorted(c for c, x in legs.items() if x["live"]) == ["g17", "g5", "s17"] and "2026-11-26" in fx["skip"]["cme"] and fx["noise"]["plain"] and "TEST FIXTURE" in fx["note"])
    djs = read(os.path.join(WEB, "dionysus", "dionysus.js"))
    check("a. Dionysus reads ../kalshi/k8.json (3 s), text only, skipped in the demo", "getJSON('../kalshi/k8.json', 3000)" in djs and "forced ? null : getJSON('../kalshi/k8.json'" in djs
          and "innerHTML" not in djs)


def part_browser():
    node = shutil.which("node")
    if not node:
        check("b. node is not installed: browser part skipped", True)
        return
    groot = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    paths = [x for x in (groot, "/opt/node-tools/node_modules", os.environ.get("NODE_PATH", "")) if x]
    env = {**os.environ, "NODE_PATH": os.pathsep.join(paths)}
    args = [node, os.path.join(ROOT, "tests", "kalshi_k8_dash.cjs"), WEB, FX]
    if os.environ.get("K8_SHOTS"):
        args += ["--shots", os.environ["K8_SHOTS"]]
    r = subprocess.run(args, capture_output=True, text=True, env=env, timeout=900)
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        if "Cannot find module 'playwright'" in r.stderr:
            check("b. node Playwright is not installed: browser part skipped", True)
            return
        check("b. the browser harness ran", False, (r.stdout[-400:], r.stderr[-800:]))
        return
    for name, ok, info in out["steps"]:
        check("b. " + name, ok, info)


def main():
    part_static()
    if "--static" not in sys.argv:
        part_browser()
    n = sum(RES)
    print(f"\nkalshi k8 dashboard: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
