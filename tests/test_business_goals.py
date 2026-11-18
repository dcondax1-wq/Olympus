"""The Business -> Goals page (tools/web_public/business/goals.html + goals.js + goals.json, 2026-11-18, owner: "Goals: next
plans for me"): the four sections in order (this week, the money ladder, the rules, the decisions), every milestone with a
done / next / later chip and a date, the ladder in date order with one "next", the owner's prices, the honest bad case, the
decisions copied from accounts.json, goals.json in step with tools/money/goals_build.py, textContent only, no private details.
Offline. --browser adds one 390 px phone check (run it under flock -w 2400 /tmp/olympus_browser.lock).

  python -X utf8 -m tests.test_business_goals [--browser]
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
    html, js, raw = read(BIZ, "goals.html"), read(BIZ, "goals.js"), read(BIZ, "goals.json")
    d = json.loads(raw)
    heads = ["This week", "The money ladder", "Rules that protect the accounts", "Decisions waiting on you"]
    pos = [html.find(">" + h + "<") for h in heads]
    check("a. the four sections are there, in order", all(p > 0 for p in pos) and pos == sorted(pos), dict(zip(heads, pos)))
    check("a. no innerHTML / outerHTML / insertAdjacentHTML / document.write / eval in the page script",
          not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function", js))
    check("a. phone first: viewport meta, the AGORA theme, business.css, a back link to Business, only same-site scripts",
          'name="viewport"' in html and 'data-theme="agora"' in html and "business.css" in html and 'href="./"' in html
          and not re.search(r'<(script|link)[^>]+(src|href)="https?://', html))
    chips = {"done", "next", "later"}
    wk, lad = d.get("week") or [], d.get("ladder") or []
    check("a. this week: 4+ steps, each with a date, what, why and a chip; dates in order",
          len(wk) >= 4 and all(w.get("date") and w.get("when") and w.get("what") and w.get("why") and w.get("status") in chips for w in wk)
          and [w["date"] for w in wk] == sorted(w["date"] for w in wk), wk)
    wt = " ".join(w["what"] + " " + w["why"] for w in wk).lower()
    check("a. this week names the address check (bank statement), the PC on, the Rapid EOD 25K buy ($97.20), Cloudflare, Thanksgiving",
          all(s in wt for s in ("bank statement", "pc", "rapid eod 25k", "$97.20", "rapideod25", "cloudflare", "thanksgiving")), wt)
    check("a. ladder: 8+ milestones, each with a date, a chip, what and detail; in date order; done ones first, exactly one next",
          len(lad) >= 8 and all(m.get("date") and m.get("when") and m.get("what") and m.get("detail") and m.get("status") in chips for m in lad)
          and [m["date"] for m in lad] == sorted(m["date"] for m in lad)
          and [m["status"] for m in lad].count("next") == 1
          and all(m["status"] == "done" for m in lad[:[m["status"] for m in lad].index("next")]), [(m["when"], m["status"]) for m in lad])
    ids = [m.get("id") for m in lad]
    need = ["z25_pass", "buy_r25", "z50_pass", "pay1", "buy_r50", "all5", "spring"]
    check("a. ladder has 25K #2 passing, the Rapid 25K buy, the 50K passing, the first payout, the Rapid 50K buy, all 5 funded, spring $",
          all(i in ids for i in need), ids)
    lt = " ".join(m["what"] + " " + m["detail"] for m in lad)
    check("a. the owner's real prices and the payout rule: $97.20, $165, $27,100, $1,000 ask, 80%, tax pot",
          all(s in lt for s in ("$97.20", "$165", "$27,100", "$1,000", "80%", "tax pot")), lt[:300])
    by = {m["id"]: m for m in lad}
    check("a. the Rapid 50K is bought after the first payout (paid from payouts); spring shows $ a month",
          by["buy_r50"]["date"] > by["pay1"]["date"] and "$" in by["spring"]["what"] and "a month" in by["spring"]["what"])
    check("a. the honest bad case is one line: 2021-25, about $0", "2021-25" in d.get("bad_case", "") and "$0" in d["bad_case"], d.get("bad_case"))
    rt = " ".join(" ".join(r) for r in d.get("rules") or []).lower()
    check("a. rules: no hand trading, the 7-day rule, the 30% tax pot",
          len(d.get("rules") or []) >= 3 and "by hand" in rt and "7 calendar days" in rt and "30%" in rt, rt[:200])
    acc = json.loads(read(BIZ, "accounts.json"))
    check("a. decisions = accounts.json decisions", d.get("decisions") == acc.get("decisions"), d.get("decisions"))
    sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
    import goals_build as G
    b = G.build(offline=True, today=d["updated"])
    check("a. goals.json is in step with goals_build (same milestones and dates from the same files)",
          [(m["id"], m["date"]) for m in b["ladder"]] == [(m["id"], m["date"]) for m in lad]
          and [w["what"] for w in b["week"]] == [w["what"] for w in wk])
    low = (html + js + raw).lower()
    check("a. no private details (emails, account numbers, the owner's handle)",
          not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", html + js + raw) and "dcondax" not in low and not re.search(r"\b\d{6,}\b", raw))
    try:
        r = subprocess.run(["node", "--check", os.path.join(BIZ, "goals.js")], capture_output=True, text=True, timeout=60)
        check("a. node: goals.js parses", r.returncode == 0, r.stderr[-300:])
    except (OSError, subprocess.TimeoutExpired) as e:
        check("a. node: goals.js parses", False, e)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def part_b():
    from playwright.sync_api import sync_playwright
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    outside, errs = [], []
    d = json.loads(read(BIZ, "goals.json"))
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
            p.goto(f"http://127.0.0.1:{port}/business/goals.html")
            p.wait_for_function(f"document.querySelectorAll('#ladder li').length === {len(d['ladder'])}")
            got = p.evaluate("() => ({week: document.querySelectorAll('#week li').length, chips: document.querySelectorAll('#ladder .pill').length,"
                             " next: document.querySelectorAll('#ladder li.next').length, rules: document.querySelectorAll('#rules dt').length,"
                             " dec: document.querySelectorAll('#dec li').length, bad: document.querySelector('#bad').textContent})")
            check("b. phone: the week steps, a chip on every milestone, one next, the rules, the decisions and the bad case are drawn",
                  got["week"] == len(d["week"]) and got["chips"] == len(d["ladder"]) and got["next"] == 1 and got["rules"] >= 3
                  and got["dec"] == max(1, len(d["decisions"])) and "$0" in got["bad"], got)
            wide = p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check("b. no sideways scroll at 390 px", wide <= 0, wide)
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
