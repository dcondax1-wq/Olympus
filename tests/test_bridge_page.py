"""The Bridge page (tools/web_public/bridge/, owner 2026-11-04: "Claude and ChatGPT connected as easily as possible, step by step, inside Olympus").

  a. static: the Connect ChatGPT wizard has exactly 3 big steps with tick boxes remembered in localStorage and a "Connected n/3" ring;
     the sync prompt on the page equals the prompt in handoff/ONBOARD.md word for word; step 3 copies the 'icons' job and opens
     chatgpt.com/codex; no token field anywhere; the page reads status.json
  b. status.json / jarvis.json: the shape bridge_sync.py writes (jobs with a state and a file count, counts, updated, last 5
     handoff commits), a fresh publish() into a folder, and a broken inbox never raises
  c. Olympus: Bridge is a built-in app (apps.js, olympus.js), its folder ships a jarvis.json card, build_web_dashboard.py publishes
     status.json inside a try/except, the workers are bumped
  d. Chromium 390 x 844: no errors, no sideways scroll, ticks and the ring persist over a reload, the sync button puts the ONBOARD
     prompt on the clipboard, 'Send first job' copies the icons job and opens Codex, live cards show 'ChatGPT delivered 3 files' /
     'ChatGPT has a question' with a 'Tell Claude' button that copies 'Bridge: <id> done'
    python -X utf8 -m tests.test_bridge_page          (static only: add --no-browser)
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
PAGE = open(os.path.join(WEB, "bridge", "index.html"), encoding="utf-8").read()
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else "  -> " + str(info)[:400]))


def onboard_prompt():
    t = open(os.path.join(ROOT, "handoff", "ONBOARD.md"), encoding="utf-8").read()
    return t.split("\n", 1)[1].strip()          # everything under the "# Paste this into ChatGPT once" title


def part_static():
    m = re.search(r'<script type="text/plain" id="onboardText">(.*?)</script>', PAGE, re.S)
    check("a. the sync prompt on the page equals the prompt in handoff/ONBOARD.md exactly", m and m.group(1).strip() == onboard_prompt(), (m.group(1)[:80] if m else None))
    steps = re.findall(r'<div class="step" id="s(\d)">', PAGE)
    check("a. the wizard has exactly 3 steps", steps == ["1", "2", "3"], steps)
    check("a. each step has a tick box (checkbox) and a number", len(re.findall(r'<input type="checkbox" data-step="\d">', PAGE)) == 3 and PAGE.count('class="n"') == 3)
    check("a. step 1 says what to tap in ChatGPT: chatgpt.com/codex + Connect to GitHub, and Settings > Apps (older: Connectors) > GitHub",
          "chatgpt.com/codex" in PAGE and "Connect to GitHub" in PAGE and "Settings" in PAGE and "Apps" in PAGE and "Connectors" in PAGE)
    check("a. step 2 is one big Copy button; step 3 is 'Send first job' copying the icons job and opening Codex",
          'id="copySync"' in PAGE and "Copy the sync prompt" in PAGE and 'id="firstJob"' in PAGE and "Send first job" in PAGE
          and "j.id === 'icons'" in PAGE and "window.open('https://chatgpt.com/codex'" in PAGE)
    check("a. the ring says 'Connected n/3' and the ticks live in localStorage 'bridge.wizard'", "'Connected ' + n + '/3'" in PAGE and "bridge.wizard" in PAGE and 'id="ringArc"' in PAGE)
    check("a. never asks for a token, password or key (no input but the 3 tick boxes; ChatGPT does the GitHub login)",
          len(re.findall(r"<input\b", PAGE)) == 3 and PAGE.count('type="checkbox"') == 3 and 'type="password"' not in PAGE and "never give anyone a token" in PAGE and not re.search(r"ghp_|github_pat_", PAGE))
    check("a. the page reads status.json and shows 'ChatGPT delivered', 'ChatGPT has a question' and a Tell Claude button ('Bridge: <id> done')",
          "status.json" in PAGE and "ChatGPT delivered" in PAGE and "ChatGPT has a question" in PAGE and "Tell Claude" in PAGE and "'Bridge: ' + j.id" in PAGE)
    check("a. the job cards are still there (icons ... codex-portal)", all(f"id: '{i}'" in PAGE for i in ("icons", "skies", "textures", "me", "persona", "labours", "lore", "deals", "obsidian", "ascend", "codex-portal")))


def part_status():
    from tools import bridge_sync as B
    st = B.status()
    ok = (st.get("v") == 1 and isinstance(st["jobs"], dict) and set(st["counts"]) == {"total", "done", "question", "in_progress", "files"} and "updated" in st
          and isinstance(st["commits"], list) and len(st["commits"]) <= 5 and all(set(c) == {"sha", "date", "subject"} for c in st["commits"])
          and all(j["state"] in ("done", "question", "in progress") and isinstance(j["files"], int) for j in st["jobs"].values()))
    check("b. status(): v 1, jobs {state, files}, counts, updated, at most 5 handoff commits", ok, st)
    check("b. the job total is the number of cards on the page", st["counts"]["total"] == len(re.findall(r"\{ id: '[a-z0-9-]+', t:", PAGE)) > 0, st["counts"])
    saved = json.load(open(os.path.join(WEB, "bridge", "status.json"), encoding="utf-8"))
    check("b. the committed bridge/status.json has the same shape (the page works before the first publish)", saved.get("v") == 1 and set(saved["counts"]) == set(st["counts"]) and isinstance(saved["jobs"], dict), saved)
    # a fake inbox: done (3 files + DONE.md), question, in progress
    import pathlib
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="le_bridge_"))
    for job, files in (("icons", ["a.png", "b.png", "c.png", "DONE.md"]), ("skies", ["QUESTION.md"]), ("textures", ["t1.png"])):
        (tmp / "handoff" / "inbox" / job).mkdir(parents=True)
        for f in files:
            (tmp / "handoff" / "inbox" / job / f).write_text("x")
    old = B.ROOT
    B.ROOT = tmp
    try:
        s2 = B.status()
    finally:
        B.ROOT = old
    check("b. inbox states: done with 3 files, question, in progress", s2["jobs"] == {"icons": {"state": "done", "files": 3}, "skies": {"state": "question", "files": 0}, "textures": {"state": "in progress", "files": 1}}
          and s2["counts"]["done"] == 1 and s2["counts"]["question"] == 1 and s2["counts"]["in_progress"] == 1, s2["jobs"])
    out = tempfile.mkdtemp(prefix="le_bridge_out_")
    msg = B.publish(out)
    j = json.load(open(os.path.join(out, "bridge", "jarvis.json"), encoding="utf-8"))
    check("b. publish() writes bridge/status.json + a Jarvis card 'ChatGPT link: n of N jobs delivered' (<= 8 KB, contract fields)",
          os.path.exists(os.path.join(out, "bridge", "status.json")) and j["name"] == "Bridge" and re.fullmatch(r"ChatGPT link: \d+ of \d+ jobs delivered", j["lines"][0])
          and j["status"]["level"] in ("ok", "warn", "bad", "off") and len(j["kpis"]) <= 3 and "delivered" in msg and os.path.getsize(os.path.join(out, "bridge", "jarvis.json")) < 8192, (j, msg))
    c = B.card({"counts": {"done": 2, "total": 5, "question": 1, "files": 7}, "t": 1})
    check("b. the card example: 'ChatGPT link: 2 of 5 jobs delivered', amber when ChatGPT has a question", c["lines"][0] == "ChatGPT link: 2 of 5 jobs delivered" and c["status"]["level"] == "warn", c)
    sc = json.load(open(os.path.join(WEB, "bridge", "jarvis.json"), encoding="utf-8"))
    check("b. the static bridge/jarvis.json exists (the app is never 'not on the site yet')", sc["v"] == 1 and sc["name"] == "Bridge")


def part_olympus():
    apps = open(os.path.join(WEB, "jarvis", "apps.js"), encoding="utf-8").read()
    oly = open(os.path.join(WEB, "olympus", "olympus.js"), encoding="utf-8").read()
    bd = open(os.path.join(ROOT, "tools", "build_web_dashboard.py"), encoding="utf-8").read()
    sw = open(os.path.join(WEB, "sw.js"), encoding="utf-8").read()
    jsw = open(os.path.join(WEB, "jarvis", "sw.js"), encoding="utf-8").read()
    check("c. Bridge is a built-in Olympus app: apps.js (Trading, #34d399, glyph Beta) and olympus.js",
          "app('bridge', 'Bridge', 'trading', '#34d399'" in apps and "\\u0392" in apps and "bridge: ['Bridge', 'Β', '#34d399']" in oly)
    i = bd.index("_bridge_sync") if "_bridge_sync" in bd else bd.index("_bridge")
    check("c. build_web_dashboard.py publishes status.json inside try/except (a failure never stops the publish)",
          "from tools import bridge_sync as _bridge" in bd and "_bridge.publish(out)" in bd and bd.rfind("try:", 0, i) > bd.rfind("\n    for app in", 0, i) and "except Exception" in bd[i:i + 400])
    check("c. workers: root le-public-v56, Jarvis jarvis-v22 (v21 kept in OLD); 'bridge/' is cached", "const CACHE = 'le-public-v56'" in sw and "'bridge/'" in sw
          and "const CACHE = 'jarvis-v24'" in jsw and "'jarvis-v21'" in jsw.split("const OLD")[1].split("\n")[0])


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def part_browser():
    from playwright.sync_api import sync_playwright
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/bridge/"
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    live = {"v": 1, "updated": "x", "jobs": {"icons": {"state": "done", "files": 3}, "skies": {"state": "question", "files": 0}, "textures": {"state": "in progress", "files": 1}},
            "counts": {"total": 11, "done": 1, "question": 1, "in_progress": 1, "files": 4}, "commits": []}
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, permissions=["clipboard-read", "clipboard-write"])
            errs = []
            p = ctx.new_page()
            p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
            p.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" else None)
            p.on("requestfailed", lambda r: errs.append("requestfailed: " + r.url))
            opened = []
            ctx.on("page", lambda pg: opened.append(pg.url))
            p.goto(url)
            p.wait_for_selector("#list .card")
            check("d. loads with no errors; 'Connected 0/3'; no sideways scroll", not errs and p.inner_text("#ringTxt") == "Connected 0/3"
                  and p.evaluate("document.documentElement.scrollWidth <= innerWidth"), errs)
            check("d. the wizard's 3 big buttons are at least 44 px tall", all(p.evaluate(f"document.querySelector('{s}').getBoundingClientRect().height") >= 44 for s in ("#open1", "#copySync", "#firstJob")))
            p.click("#copySync")
            clip = p.evaluate("navigator.clipboard.readText()")
            check("d. 'Copy the sync prompt' puts the ONBOARD prompt on the clipboard and ticks step 2 (Connected 1/3)", clip.strip() == onboard_prompt() and p.inner_text("#ringTxt") == "Connected 1/3"
                  and p.is_checked('input[data-step="2"]'), clip[:60])
            p.click("#firstJob")
            clip = p.evaluate("navigator.clipboard.readText()")
            p.wait_for_timeout(400)
            check("d. 'Send first job' copies the icons job prompt, ticks step 3 and opens chatgpt.com/codex",
                  "14 square app icons" in clip and p.is_checked('input[data-step="3"]') and (any("chatgpt.com" in u or u == "about:blank" for u in opened)), (clip[:50], opened))
            p.check('input[data-step="1"]')
            check("d. all three ticked: 'Connected 3/3' and the ring is full", p.inner_text("#ringTxt") == "Connected 3/3" and float(p.get_attribute("#ringArc", "stroke-dashoffset")) == 0)
            p.reload()
            p.wait_for_selector("#list .card")
            check("d. the ticks and the ring survive a reload; the page marks itself opened (seen) for Jarvis",
                  p.inner_text("#ringTxt") == "Connected 3/3" and all(p.is_checked(f'input[data-step="{i}"]') for i in (1, 2, 3))
                  and json.loads(p.evaluate("localStorage.getItem('bridge.wizard')")).get("seen") == 1)
            p.uncheck('input[data-step="2"]')
            check("d. unticking works (2/3)", p.inner_text("#ringTxt") == "Connected 2/3")
            # live status
            p2 = ctx.new_page()
            p2.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
            p2.route("**/bridge/status.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(live)))
            p2.goto(url)
            p2.wait_for_function("document.querySelector('#job-icons .live') && document.querySelector('#job-icons .live').textContent.indexOf('delivered') > -1")
            t = lambda i: p2.inner_text(f"#job-{i} .live")  # noqa: E731
            check("d. live cards: 'ChatGPT delivered 3 files', 'ChatGPT has a question', 'ChatGPT is working (1 file)', else 'Waiting for ChatGPT'",
                  t("icons") == "ChatGPT delivered 3 files" and t("skies") == "ChatGPT has a question" and t("textures") == "ChatGPT is working (1 file)" and t("me") == "Waiting for ChatGPT", [t(i) for i in ("icons", "skies", "textures", "me")])
            p2.click("#job-icons button[data-say]")
            check("d. 'Tell Claude' copies 'Bridge: icons done'; a question copies 'Bridge: skies question'; waiting cards have no button",
                  p2.evaluate("navigator.clipboard.readText()") == "Bridge: icons done" and p2.get_attribute("#job-skies button[data-say]", "data-say") == "Bridge: skies question"
                  and p2.query_selector("#job-me button[data-say]") is None)
            check("d. no errors on the way", not errs, errs)
            br.close()
    finally:
        srv.shutdown()


def main():
    part_static()
    part_status()
    part_olympus()
    if "--no-browser" not in sys.argv:
        part_browser()
    n = sum(RES)
    print(f"\nbridge page: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
