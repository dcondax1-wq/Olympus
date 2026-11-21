"""The Business -> More Work page (tools/web_public/business/work.html + work.js + work.json, 2026-11-17, owner: "find more
work"): the four sections in order, 5-8 ranked ideas each with $ a month / hours / start cost / 3 first steps / a verdict,
the agency's first $1,000 plan matching the owner's prices in agency/config.example.json, a scam list, https-only sources,
textContent only (no innerHTML / eval), phone-first layout, no private details. Offline. --browser adds a 390 px and 320 px
phone check (run it under flock -w 2400 /tmp/olympus_browser.lock).

  python -X utf8 -m tests.test_business_work [--browser]
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import subprocess
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
BIZ = os.path.join(WEB, "business")
RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:300]})" if detail and not cond else ""))


def read(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def part_a():
    html, js, raw = read(BIZ, "work.html"), read(BIZ, "work.js"), read(BIZ, "work.json")
    d = json.loads(raw)
    heads = ["Do this first", "Ranked ideas", "Agency: first $1,000 plan", "Scams to skip"]
    pos = [html.find(">" + h + "<") for h in heads]
    check("a. the four sections are there, in order", all(p > 0 for p in pos) and pos == sorted(pos), dict(zip(heads, pos)))
    check("a. no innerHTML / outerHTML / insertAdjacentHTML / document.write / eval in the page script",
          not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function", js))
    check("a. phone first: viewport meta, the AGORA theme, business.css, a 16px side gutter, a back link to Business",
          'name="viewport"' in html and 'data-theme="agora"' in html and "business.css" in html and "padding: 12px 16px" in html and 'href="./"' in html)
    check("a. only same-site scripts and styles (no CDN, no tracker)", not re.search(r'<(script|link)[^>]+(src|href)="https?://', html))
    check("a. the script only links https:// sources and opens them with rel=noopener", "/^https:\\/\\//" in js and "a.rel = 'noopener'" in js)
    ideas = d.get("ideas") or []
    need = ("name", "verdict", "usd_month", "hours", "cost", "claude", "why", "steps")
    check("a. 5-8 ideas, ranks 1..n with no gap, each with $ a month, hours, start cost, what Claude does, why, and 3 first steps",
          5 <= len(ideas) <= 8 and sorted(i["rank"] for i in ideas) == list(range(1, len(ideas) + 1))
          and all(all(str(i.get(k) or "").strip() for k in need) and len(i["steps"]) == 3 and "$" in i["usd_month"] for i in ideas),
          [i.get("name") for i in ideas])
    verdicts = {i["verdict"] for i in ideas}
    check("a. every verdict is one the page knows (legit / saturated / legit but tiny / skip for now), and at least one idea is marked down",
          verdicts <= {"legit", "saturated", "legit but tiny", "skip for now"} and verdicts & {"saturated", "skip for now", "legit but tiny"}, verdicts)
    names = " ".join(i["name"].lower() for i in ideas)
    check("a. the ideas asked for are checked: the agency, Google Business Profile, freelance, reselling, surveys / user testing, delivery as a floor, local arbitrage",
          all(w in names for w in ("website", "google business profile", "freelance", "reselling", "surveys", "doordash", "arbitrage")), names)
    check("a. honest about what Claude cannot do: AI training and surveys say no AI answers", any("ban" in i["claude"].lower() for i in ideas)
          and any(i["rank"] == len(ideas) and "tiny" in i["verdict"] for i in ideas))
    cfg = json.loads(read(ROOT, "agency", "config.example.json"))
    pk = {p["id"]: p for p in cfg["packages"]}
    plan = d.get("plan") or {}
    lad = " ".join(" ".join(r) for r in plan.get("ladder") or [])
    st, gr = pk["starter"], pk["growth"]
    check("a. the $1,000 plan uses the ONE price book's prices (Starter $1,500 + $79, Call engine $500 + $299) and reaches $1,000 (1 Starter)",
          f"${st['setup']:,} + ${st['monthly']}" in lad and f"${gr['setup']:,} + ${gr['monthly']}" in lad and "$149" in lad
          and st["setup"] >= 1000 and "$1,000" in plan.get("goal", ""), lad)
    check("a. the plan says how many a day, gives 4 weeks, and the walk-in / DM / follow-up / price lines",
          "15 contacts a weekday" in plan.get("pace", "") and len(plan.get("weeks") or []) == 4
          and [r[0] for r in plan.get("say") or []] == ["Walk in", "DM", "Follow-up", "How much?"], plan.get("pace"))
    check("a. 5+ scams to skip, each with a reason; task scams and fake reviews are named",
          len(d.get("scams") or []) >= 5 and all(len(s) == 2 and s[1] for s in d["scams"]) and any("unlock" in s[0].lower() for s in d["scams"])
          and any("review" in s[0].lower() for s in d["scams"]))
    check("a. every source is https with a name", len(d.get("sources") or []) >= 6 and all(s[1].startswith("https://") and s[0] for s in d["sources"]))
    low = (html + js + raw).lower()
    check("a. no private details (emails, the owner's name, account ids) on the page",
          not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", html + js + raw) and "dcondax" not in low and "zlarior" not in low)
    try:
        r = subprocess.run(["node", "--check", os.path.join(BIZ, "work.js")], capture_output=True, text=True, timeout=60)
        check("a. node: work.js parses", r.returncode == 0, r.stderr[-300:])
    except (OSError, subprocess.TimeoutExpired) as e:
        check("a. node: work.js parses", False, e)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def part_b():
    from playwright.sync_api import sync_playwright
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    outside, errs = [], []
    n = len(json.loads(read(BIZ, "work.json"))["ideas"])
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            ctx = br.new_context(viewport={"width": 390, "height": 844}, has_touch=True)

            def guard(route):
                u = route.request.url
                if u.startswith(f"http://127.0.0.1:{port}") or u.startswith(("data:", "blob:")):
                    return route.continue_()
                outside.append(u)
                return route.abort()
            ctx.route("**/*", guard)
            p = ctx.new_page()
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto(f"http://127.0.0.1:{port}/business/work.html")
            p.wait_for_function(f"document.querySelectorAll('#ideas .idea').length === {n}")
            got = p.evaluate("() => ({first: document.querySelectorAll('#first li').length, h: document.querySelector('#ideas .idea h3').textContent,"
                             " scams: document.querySelectorAll('#scams dt').length, src: [...document.querySelectorAll('#src a')].every((a) => a.href.startsWith('https://') && a.rel === 'noopener'),"
                             " goal: document.querySelector('#goal').textContent})")
            check("b. phone: 3 first steps, the ranked cards (#1 first), the scams, safe source links and the $1,000 goal are drawn",
                  got["first"] == 3 and got["h"].startswith("#1 ") and got["scams"] >= 5 and got["src"] and "$1,000" in got["goal"], got)
            wide = p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            p.set_viewport_size({"width": 320, "height": 700})
            wide2 = p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check("b. no sideways scroll at 390 px or 320 px", wide <= 0 and wide2 <= 0, (wide, wide2))
            check("b. no script errors and nothing fetched from outside", not errs and not outside, (errs, outside))
            br.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    if "--browser" in sys.argv:
        part_b()
    ok = all(RES)
    print(f"\n{sum(RES)}/{len(RES)} passed" + ("" if ok else "  FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
