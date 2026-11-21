"""The MONEY PLAN (tools/money/money_plan.py -> research/lab/money_plan.json + business/plan.json + the value fields of the
Decide card's items in business/decisions.json; page business/plan.html + plan.js; 2026-11-18 night-money).
  a. plan.json: tonight's accounts (Zlarior 50K eval, 25K #2 eval, ATLAS funded 25K, the Rapid EOD 25K bought tonight, the
     Rapid EOD 50K next buy) for 3 markets, each with $ a month, the first payout (date + $), the chance to pass + likely
     pass date for the evals, the fleet with and without the next buy, the owner's real prices, nothing private
  b. decisions.json: every open item the tool values has usd_month (= impact_usd), the 3 markets, risk words, a yes / no /
     later recommendation with its reason, the same numbers as research/lab/money_plan.json (an item valued at ATLAS's real
     fills by tools/atlas_risk.py: the same numbers as research/second/atlas_risk.json "cards"); the Decide card still passes
     its own schema (tests.test_decide part a rules)
  c. write_decisions only touches the value fields of the items it values: another helper's new proposal stays as it is
  d. the Rapid EOD 25K the plan simulates = the engine's preset (engine/multi_account mffu_rapid_eod_25k + engine/rapid.PLANS)
  e. plan.js / decide.js: textContent only, no outside address, node parses them
  f. --browser: 390 px phone: the hero $ a month, 4 account cards (5 with the next buy), every open decision valued, no
     sideways scroll, no script errors, nothing fetched from outside (run under flock -w 2400 /tmp/olympus_browser.lock)
    python -X utf8 -m tests.test_money_plan [--browser]
"""
from __future__ import annotations

import copy
import functools
import glob
import http.server
import json
import os
import re
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
BIZ = os.path.join(WEB, "business")
LAB = os.path.join(ROOT, "research", "lab", "money_plan.json")
RES = []
KEYS = ("Z50", "N25", "A25", "R25", "R2")
VALUED = ("payout-ping-1000", "zlarior-funded25", "rapid25-lit-bank", "atlas-on-50k-funded", "atlas-on-rapid", "keep-1000-rapid",
          "ask-mffu-parallel", "cloud-alerts", "atlas-funded-room-40", "drop-lucid-account4")


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:400]})" if detail and not cond else ""), flush=True)


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def part_a():
    raw = rd(BIZ, "plan.json")
    d = json.loads(raw)
    check("a. plan.json: kind olympus-money-plan, built by tools/money/money_plan.py, from tonight (start Nov 19), 3 markets",
          d.get("kind") == "olympus-money-plan" and d.get("built_by") == "tools/money/money_plan.py" and d.get("start") == "2026-11-19"
          and set(d.get("rows") or {}) == {"H1", "H2", "REF"}, {k: d.get(k) for k in ("kind", "built_by", "start")})
    check("a. the owner's real prices: Builder 50K $91.80, 25K $63, Rapid EOD 25K $97.20, Rapid EOD 50K $165; budget $150; tax pot 30%",
          d.get("prices") == {"builder50k": 91.8, "builder25k": 63.0, "rapid_eod25k": 97.2, "rapid_eod50k": 165.0}
          and d.get("budget") == 150.0 and d.get("tax") == 0.3, (d.get("prices"), d.get("budget")))
    now = {r["key"]: r for r in d.get("now") or []}
    check("a. tonight's numbers: Zlarior $49,193 ($3,807 to pass, $1,025 room), 25K #2 $25,000, ATLAS funded $24,887 ($887 room)",
          now.get("Z50", {}).get("balance") == 49193 and now["Z50"].get("to_pass") == 3807 and now["Z50"].get("room") == 1025
          and now.get("N25", {}).get("balance") == 25000 and now.get("A25", {}).get("balance") == 24887 and now["A25"].get("room") == 887
          and now.get("R25", {}).get("price") == 97.2, now)
    bad = []
    for sp, r in d["rows"].items():
        A = r.get("accounts") or {}
        for k in KEYS:
            a = A.get(k) or {}
            if not (isinstance(a.get("cash_m"), (int, float)) and "first_pay" in a and "p_no_pay_6m" in a and "p_pay_by_jan31" in a):
                bad.append((sp, k, "money"))
            if k in ("Z50", "N25", "R25") and not ({"p60", "f60", "pass_med", "pass_date"} <= set(a.get("eval") or {})):
                bad.append((sp, k, "eval"))
        if not (A.get("R2", {}).get("buy_med") or sp == "REF"):
            bad.append((sp, "R2", "buy"))
        for f in ("four", "five"):
            F = (r.get("fleet") or {}).get(f) or {}
            if not (F.get("months") and isinstance(F.get("cash_m"), (int, float)) and "first_any" in F and "pocket_p95" in F):
                bad.append((sp, f, "fleet"))
            if not (r.get("picks") or {}).get(f):
                bad.append((sp, f, "picks"))
    check("a. every market: every account has $ a month, first payout, chance of a payout; the evals a chance to pass + date; the "
          "fleet with and without the next buy (and with Claude's picks)", not bad, bad)
    h2 = d["rows"]["H2"]
    A = h2["accounts"]
    check("a. Jul-Oct-like sanity: ATLAS's funded 25K pays first (median), the Rapid 25K passes in 15-45 sessions, the next buy "
          "after the first payout, 2021-25 about $0 a month",
          A["A25"]["first_pay"] <= min(A[k]["first_pay"] or "9999" for k in ("Z50", "N25", "R25"))
          and 15 <= A["R25"]["eval"]["pass_med"] <= 45 and A["R2"]["buy_med"] > h2["fleet"]["four"]["first_any"]
          and abs(d["rows"]["REF"]["fleet"]["four"]["cash_m"]) < 150, (A["A25"]["first_pay"], A["R25"]["eval"], A["R2"].get("buy_med")))
    low = raw.lower()
    check("a. nothing private (no emails, no account ids, no owner handle)",
          not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", raw) and "dcondax" not in low and not re.search(r"[A-Z]{3,}\d{5,}", raw), "")
    check("a. small enough for a phone (< 60 KB)", len(raw.encode()) < 60000, len(raw.encode()))


def part_b():
    doc = json.loads(rd(BIZ, "decisions.json"))
    lab = json.loads(rd(LAB)).get("decision_values") or {}
    by = {it["id"]: it for it in doc.get("items") or []}
    bad = []
    for did in VALUED:
        it = by.get(did)
        if not it:
            bad.append((did, "missing"))
            continue
        if not (isinstance(it.get("usd_month"), int) and it.get("impact_usd") == it.get("usd_month")
                and set(it.get("usd_month_by") or {}) == {"jan_jun", "jul_oct", "y2021_25"} and it["usd_month_by"]["jul_oct"] == it["usd_month"]
                and it.get("recommend") in ("yes", "no", "later") and it.get("recommend_why") and it.get("risk") and "$" in it.get("impact", "")):
            bad.append((did, "fields"))
        v = lab.get(did) or {}
        if "tools/atlas_risk.py" in str(it.get("valued") or ""):     # valued at ATLAS's real fills (2026-11-20, night-atlasrisk)
            v = (json.loads(rd(ROOT, "research", "second", "atlas_risk.json")).get("cards") or {}).get(did) or {}
        elif "tools/money/rapid25_pass.py" in str(it.get("valued") or ""):     # the Rapid 25K fastest-pass study (2026-11-21, day-rapid)
            v = (json.loads(rd(ROOT, "research", "lab", "rapid25_pass.json")).get("cards") or {}).get(did) or {}
        elif "tools/money/rapid25_launch.py" in str(it.get("valued") or ""):   # the Rapid 25K launch check (2026-11-20, day-rapid)
            v = (json.loads(rd(ROOT, "research", "lab", "rapid25_launch.json")).get("cards") or {}).get(did) or {}
        if v.get("usd_month") != it.get("usd_month") or v.get("recommend") != it.get("recommend"):
            bad.append((did, "not the lab numbers", v.get("usd_month"), it.get("usd_month")))
    check("b. every valued item: $ a month (= impact_usd, Jul-Oct-like), the 3 markets, risk words, Claude's yes / no / later + why, "
          "the same numbers as research/lab/money_plan.json", not bad, bad)
    sch = [d.get("id") for d in doc["items"] if not (re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,39}", str(d.get("id"))) and d.get("question")
                                                     and d.get("why") and "$" in str(d.get("impact")) and isinstance(d.get("impact_usd"), (int, float))
                                                     and set(d.get("options") or []) <= {"yes", "no", "later"} and d.get("source"))]
    check("b. the Decide card schema still holds for every item (tests.test_decide a)", not sch, sch)
    check("b. the first item is still the $1,000 payout question (the Board / ZEUS tests read it first)",
          doc["items"][0]["id"] == "payout-ping-1000" and doc["items"][0]["question"].startswith("Funded 25K: ask for the full $1,000"))
    rec = {did: by[did]["recommend"] for did in VALUED if did in by}
    check("b. the clear calls: ATLAS on the Rapid YES (it is most of that account's money), ATLAS on the 50K once funded YES, "
          "ask MFFU YES (free)", rec.get("atlas-on-rapid") == "yes" and rec.get("atlas-on-50k-funded") == "yes"
          and rec.get("ask-mffu-parallel") == "yes", rec)


def part_c():
    sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
    import money_plan as MP
    doc = json.loads(rd(BIZ, "decisions.json"))
    extra = {"id": "atlas-health-x", "question": "A helper's own proposal?", "why": "w", "impact": "$1 a month", "impact_usd": 1,
             "options": ["yes", "no", "later"], "status": "open", "source": "research/x.md"}
    doc["items"].append(copy.deepcopy(extra))
    doc["items"][0]["status"] = "yes"                  # an answered item keeps its status
    tmp = os.path.join(tempfile.mkdtemp(prefix="mp_"), "decisions.json")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    vals = {"payout-ping-1000": {"usd_month": 5, "usd_month_by": {"jan_jun": 4, "jul_oct": 5, "y2021_25": 0}, "risk": "r",
                                 "recommend": "yes", "recommend_why": "w2", "impact": "+$5 a month"}}
    MP.write_decisions(vals, path=tmp, today="2026-11-19")
    out = json.loads(open(tmp, encoding="utf-8").read())
    by = {it["id"]: it for it in out["items"]}
    check("c. write_decisions: a helper's new proposal is left exactly as it was; an answered item keeps its status; ids and order kept",
          by["atlas-health-x"] == extra and by["payout-ping-1000"]["status"] == "yes" and by["payout-ping-1000"]["usd_month"] == 5
          and by["payout-ping-1000"]["impact_usd"] == 5 and [i["id"] for i in out["items"]] == [i["id"] for i in doc["items"]]
          and by["payout-ping-1000"]["question"] == doc["items"][0]["question"] and out["updated"] == "2026-11-19", by["payout-ping-1000"])


def part_d():
    try:                    # the plan's Rapid spec walks the BLITZ stream (tools/blitz25k_lib, numba); numba is not in requirements*.txt,
        import numba        # noqa: F401  so a cloud box without it skips d instead of crashing the suite
    except ImportError as e:
        print(f"[SKIP] d. the Rapid EOD 25K spec = the engine preset (numba missing: {e}; pip install numba to run it)")
        return
    sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
    import money_plan as MP
    from engine import multi_account as MA, rapid as RP
    sp = MP.r25_spec()
    E, ec = sp["E"], sp["ecfg"]
    R = MA.PRESETS["mffu_rapid_eod_25k"]["rules"]
    P = RP.plan_info("mffu_rapid_eod_25k")
    tw = ec["two_week"]
    check("d. the plan's Rapid EOD 25K eval = the engine preset: $1,500 target, $1,000 EOD floor (+$100 lock), 20 micros, 30% best "
          "day, 4 days, the bot's soft $500 day, LIT's live two_week at 40% of the room to session 80",
          (E["tgt"], E["mll"], E["lock"], E["maxq"], E["cons"], E["min_days"]) == (R["target"], R["mll"], R["lock"], R["max_micros"], R["best_day"], R["min_days"])
          and ec["_dll"] == R["dll"] == 500.0 and tw["room_f"] == 0.4 and ec["two_week_until"] == 80 and tw["acct"]["target"] == 1500.0,
          (E, R, tw.get("room_f")))
    z = sp["z"].get("ATLAS") or {}
    check("d. ATLAS on it: min($250, 30% of the room) = engine/rapid.PLANS atlas_usd", z.get("usd") == P["atlas_usd"] == 250.0 and z.get("f") == 0.3, z)
    f = sp["fund"]()
    check("d. funded: $1,100 buffer, keep $500 more, $250 since the last payout, 90%, the 25K funded rule (60% <= $750, a winner <= $1,000)",
          f.R["buffer"] == P["buffer"] == 1100.0 and sp["pol"] == ("cushion", P["cushion"]) and f.R.get("since") == P["since"] == 250.0
          and f.R["split"] == 0.9 and (f.cfg["pct"], f.cfg["pct_max_usd"], f.cfg["max_win"])
          == tuple(MA.PRESETS["mffu_rapid_eod_25k"]["sizing"]["funded"][k] for k in ("pct", "pct_max_usd", "max_win")), (f.R, f.cfg))
    check("d. the price charged = the owner's CLUB price $97.20 (= engine/account_b PLANS rapideod25k)",
          sp["price"] == 97.2 and __import__("engine.account_b", fromlist=["PLANS"]).PLANS["rapideod25k"]["price"] == 97.2)


def part_e():
    for name in ("plan.js", "decide.js"):
        js = rd(BIZ, name)
        check(f"e. {name}: no innerHTML / outerHTML / insertAdjacentHTML / document.write / eval, no outside address",
              not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function", js) and not re.search(r"https?://(?!www\.w3\.org/2000/svg)", js))
        r = subprocess.run(["node", "--check", os.path.join(BIZ, name)], capture_output=True, text=True, timeout=60)
        check(f"e. node: {name} parses", r.returncode == 0, r.stderr[-300:])
    html = rd(BIZ, "plan.html")
    check("e. plan.html: phone first (viewport-fit=cover, AGORA, business.css, back to Business, one h1), plan.js?v=3, no outside script",
          "viewport-fit=cover" in html and 'data-theme="agora"' in html and "business.css" in html and 'href="./"' in html
          and html.count("<h1") == 1 and 'src="plan.js?v=3"' in html and not re.search(r'<(script|link)[^>]+(src|href)="https?://', html))
    idx = rd(BIZ, "index.html")
    check("e. Business links it as the Money plan", 'href="plan.html"><h2>Money plan &rarr;</h2>' in idx)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def part_f():
    from playwright.sync_api import sync_playwright
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    outside, errs = [], []
    d = json.loads(rd(BIZ, "plan.json"))
    n_open = sum(1 for it in json.loads(rd(BIZ, "decisions.json"))["items"] if it.get("status", "open") == "open")
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
            p.goto(f"http://127.0.0.1:{port}/business/plan.html")
            p.wait_for_function("window.MONEY_PLAN && window.MONEY_PLAN.ok === true")
            got = p.evaluate("() => ({hero: document.getElementById('big').textContent, acc: [...document.querySelectorAll('#acc section')].map((s) => s.dataset.key),"
                             " dec: document.querySelectorAll('#dec article').length, valued: [...document.querySelectorAll('#dec .w')].filter((e) => /\\$/.test(e.textContent)).length,"
                             " pay1: document.getElementById('pay1').textContent, rows: document.querySelectorAll('#mon tbody tr').length,"
                             " wide: document.documentElement.scrollWidth - document.documentElement.clientWidth})")
            four = d["rows"]["H2"]["fleet"]["four"]
            check("f. phone: the hero is the Jul-Oct-like $ a month of tonight's 4 accounts, 4 account cards (ATLAS first), the first payout date, every month",
                  got["hero"].startswith("$" + f"{four['cash_m']:,}") and got["acc"] == ["A25", "N25", "Z50", "R25"] and got["pay1"].startswith("~")
                  and got["rows"] == len(four["months"]), got)
            check("f. every open decision is listed with its $ a month", got["dec"] == n_open and got["valued"] >= len(VALUED), got)
            check("f. no sideways scroll at 390 px", got["wide"] <= 0, got["wide"])
            # phone QA 2026-11-19: the label of a label / number row had a word a line and the K8 card's "Normal bad stretch" ran into its $
            kv = p.evaluate("""() => { const rows = [...document.querySelectorAll('dl.kv')].flatMap((dl) => [...dl.querySelectorAll('dt')].map((dt) => {
                const dd = dt.nextElementSibling, a = dt.getBoundingClientRect(), b = dd ? dd.getBoundingClientRect() : null;
                return [Math.round(a.width), b ? Math.round(b.left - a.right) : 99]; })); return { n: rows.length, narrow: rows.filter((r) => r[0] < 120).length, touch: rows.filter((r) => r[1] < 4).length }; }""")
            check("f. 390 px: every label / number row gives the label at least 120 px and never touches its number", kv["n"] > 10 and kv["narrow"] == 0 and kv["touch"] == 0, kv)
            p.click("#cnt button:nth-child(2)")
            g2 = p.evaluate("() => ({acc: [...document.querySelectorAll('#acc section')].map((s) => s.dataset.key), hero: document.getElementById('big').textContent})")
            check("f. '+ the next buy' adds the Rapid EOD 50K card and its $", g2["acc"][-1] == "R2" and len(g2["acc"]) == 5
                  and g2["hero"].startswith("$" + f"{d['rows']['H2']['fleet']['five']['cash_m']:,}"), g2)
            check("f. no script errors and nothing fetched from outside", not errs and not outside, (errs, outside))
            br.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    part_b()
    part_c()
    part_d()
    part_e()
    if "--browser" in sys.argv:
        part_f()
    ok = all(RES)
    print(f"\n{sum(RES)}/{len(RES)} passed" + ("" if ok else "  FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
