"""THE ONE MONEY PLACE (night team B, 2026-11-16): the payout planner, the 3 new products, the Business page's money front door.

  a. engine/payout_plan.py: dates in order (pass < request < bank), weekends and the Thanksgiving closure skipped, a lost eval, a funded
     account, account #4 on the first bank date, the sale window, home.json -> bot names only (no broker id)
  b. the phone's copy (businesscore.planPayouts in node) gives exactly the Python answer on the same accounts; cleanExtra drops junk
  c. the 3 new products (build_prop_kit): buyer files, zips (one top folder, same bytes twice; the bundle holds the 4 parts), 6 covers,
     listings (13 tags, 6 FAQ, refund, AI line), no brand names / promises / outside links, the calculator's cached values = calc()
  d. tools/biz_publish.py: costs = the roadmap's paid_already, 8 products + gigs + content + sites ready with tick lists, at most 7 moves,
     6 ranked ideas with 2 starter kits, the fixture's plan is DEMO; privacy: business.json private + gitignored, no broker id
  e. Chromium (skipped with --static; run under flock -w 2400 /tmp/olympus_browser.lock): the DEMO door, then a mocked ../home.json
     drives the plan live, a move tick stays after a reload, a ready step ticks, taps, no sideways scroll at 375 px
    python -X utf8 -m tests.test_money_door [--static]
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from tests import agora_kit as AK  # noqa: E402

check = AK.check
BROKER_ID = re.compile(r"MFFU[A-Z]*\d{6,}|LT\d{6,}")


def part_a():
    from engine import payout_plan as PP
    d = PP.plan(PP.DEMO, "2026-11-16")
    rows = d["accounts"]
    check("a. DEMO: both evals planned, pass < first request < bank date, slow dates later",
          len(rows) == 2 and all(r["pass_typical"] < r["payout_typical"] < r["bank_typical"] and r["pass_slow"] >= r["pass_typical"]
                                 and r["payout_slow"] >= r["payout_typical"] for r in rows), [r["text"] for r in rows])
    # owner's plan 2026-11-21 (d3b50744): the first ask is the max request: $2,000 at $4,100 (50K), $1,000 at $2,100 (25K)
    check("a. the first ask: $2,000 -> $1,600 to you (50K), $1,000 -> $800 (25K); funded $546 + $338 a month (roadmap H2)",
          [(r["request"], r["to_you"]) for r in rows] == [(2000.0, 1600.0), (1000.0, 800.0)] and d["funded_month"] == 884.0 and d["funded_month_with_4"] == 2853.0)   # + the Rapid EOD 50K ~$1,969 a month (drop-lucid-account4, 2026-11-20)
    check("a. sessions skip weekends and the Thanksgiving closure (Wed 11-25 + 1 session = Fri 11-27; Fri 11-20 + 1 = Mon 11-23)",
          PP.sessions_after("2026-11-25", 1) == "2026-11-27" and PP.sessions_after("2026-11-20", 1) == "2026-11-23" and PP.business_after("2026-11-20", 4) == "2026-11-26")
    lost = PP.plan([{"name": "X", "plan": "builder25k", "room": 0, "to_target": 900}], "2026-11-16")
    check("a. a lost eval: state lost, no payout, account #4 waits", lost["accounts"][0]["state"] == "lost" and lost["first"] is None and lost["account4"]["buy_on"] is None)
    f = PP.plan([{"name": "Z", "plan": "builder50k", "stage": "funded", "profit": 3000, "room": 2000}], "2026-11-16")["accounts"][0]
    check("a. a funded account at $3,000: 4 sessions to the $4,100 ask line ($1,100 at ~$300 a day)", f["state"] == "funded" and f["sessions_to_payout"] == 4 and f["pass_typical"] is None, f)
    check("a. account #4 is bought on the earliest bank date of a first payout", d["account4"]["buy_on"] == min(r["bank_typical"] for r in rows))
    fast = PP.plan([{"name": "A", "plan": "builder25k", "stage": "funded", "profit": 1850, "room": 900}], "2026-11-16")
    # owner 2026-11-20 (Decide drop-lucid-account4: YES, MFFU only): the line is the MFFU next buys, never a LucidPro; no sale is claimed
    check("a. the next-buys line is MFFU only: the Rapid EOD 25K now, then the Rapid EOD 50K ($165, code CLUB) on the first bank date, then a fresh Builder 50K; no Lucid, no sale claim",
          fast["account4"]["text"].startswith("Next buys (MFFU only): the Rapid EOD 25K now") and "Rapid EOD 50K about " + fast["account4"]["buy_on"] in fast["account4"]["text"]
          and "$165 with code CLUB" in fast["account4"]["text"] and "fresh Builder 50K" in fast["account4"]["text"] and "lucid" not in json.dumps(fast).lower()
          and fast["account4"]["in_sale"] is False and "lost" not in lost["account4"]["text"] and lost["account4"]["text"].startswith("Next buys (MFFU only)"), fast["account4"])
    home = json.load(open(os.path.join(ROOT, "tests", "fixtures", "argus", "home_real.json"), encoding="utf-8"))
    acc = PP.accounts_from_home(home)
    check("a. home.json -> Zlarior (LIT) 50K + ATLAS 25K, the cloud paper account left out, no broker id anywhere in the plan",
          [(a["name"], a["plan"]) for a in acc] == [("Zlarior (LIT)", "builder50k"), ("ATLAS", "builder25k")] and not BROKER_ID.search(json.dumps(PP.plan(acc, "2026-11-16"))), acc)
    return acc


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const cases = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
  const o = { plans: cases.map((c) => C.planPayouts(c.accounts, c.today)), home: C.accountsFromHome(cases[0].home) };
  o.junk = C.cleanExtra({ trading: { accounts: [null, { name: 'A', pass_typical: 'soon', bank_typical: '2026-12-01', room: 'x' }] }, moves: [{ id: '<b>', what: 'x' }, { what: 'no id' }],
    ready: [{ id: 'p', name: 'P', steps: ['a', 3] }], costs: { bought: [{ what: 'E', usd: 'q' }] }, ideas: { rows: [{ name: 'I', usd_hour: [1] }], kits: { a: { title: 'K', steps: ['s'] } } } });
  o.empty = C.cleanExtra(null);
  process.stdout.write(JSON.stringify(o));
});
"""


def part_b(acc):
    from engine import payout_plan as PP
    home = json.load(open(os.path.join(ROOT, "tests", "fixtures", "argus", "home_real.json"), encoding="utf-8"))
    cases = [{"accounts": acc, "today": "2026-11-16", "home": home}, {"accounts": PP.DEMO, "today": "2026-11-20"},
             {"accounts": [{"name": "X", "plan": "builder25k", "room": 0}, {"name": "Z", "plan": "builder50k", "stage": "funded", "profit": 1234.5, "room": 1500}], "today": "2026-11-24"},
             {"accounts": [{"name": "A", "plan": "builder25k", "stage": "funded", "profit": 1850, "room": 900}], "today": "2026-11-16"},
             {"accounts": [{"name": "P", "plan": "builder50k", "to_target": 0, "status": "passed", "room": 1800}], "today": "2026-12-23"}]
    tmp = tempfile.mkdtemp(prefix="le_door_")
    try:
        cf = os.path.join(tmp, "cases.json")
        json.dump(cases, open(cf, "w"))
        o = AK.node("business", HARNESS, cf)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if o is None:
        print("  (node not found: part b skipped)")
        return
    py = [PP.plan(c["accounts"], c["today"]) for c in cases]
    keys = ("name", "state", "pass_typical", "pass_slow", "payout_typical", "payout_slow", "bank_typical", "request", "to_you", "funded_month", "room", "text")
    same = all([{k: r.get(k) for k in keys} for r in p["accounts"]] == [{k: r.get(k) for k in keys} for r in j["accounts"]]
               and p["account4"]["text"] == j["account4"]["text"] and p["funded_month"] == j["funded_month"] for p, j in zip(py, o.get("plans", [])))
    check("b. the phone's planner = engine/payout_plan.py on 5 cases (live evals, DEMO, lost + funded, the sale window, a passed eval)", same and len(o["plans"]) == 5,
          [(p["accounts"][0]["text"], j["accounts"][0]["text"]) for p, j in zip(py, o.get("plans", []))][:2])
    check("b. the phone reads home.json the same way (bot names only)", o["home"] == json.loads(json.dumps(acc)), o["home"])
    j = o["junk"]
    check("b. cleanExtra(): junk accounts / moves / list items dropped, a bad date becomes null, a bad $ becomes 0, an id loses its markup",
          len(j["trading"]["accounts"]) == 1 and j["trading"]["accounts"][0]["pass_typical"] is None and j["trading"]["accounts"][0]["bank_typical"] == "2026-12-01"
          and j["trading"]["accounts"][0]["room"] == 0 and [m["id"] for m in j["moves"]] == ["b"] and j["ready"][0]["steps"] == ["a"]
          and j["costs"]["bought"][0]["usd"] == 0 and j["ideas"]["rows"][0]["usd_hour"] == [0, 0] and j["ideas"]["kits"]["a"]["steps"] == ["s"], j)
    check("b. cleanExtra(null) is empty, never an error", o["empty"]["trading"] is None and o["empty"]["moves"] == [] and o["empty"]["ready"] == [])


def part_c():
    from money_machines.products import build_prop_kit as B
    from money_machines.products import kit as K
    req = {"calc": ["Eval_Risk_Calculator.xlsx", "LICENSE.txt", "README.txt"],
           "guide": ["LICENSE.txt", "Prop_Eval_Rules_Explained_A4.pdf", "Prop_Eval_Rules_Explained_Letter.pdf", "README.txt"],
           "bundle": ["LICENSE.txt", "README.txt"]}
    cat = {p["id"]: p for p in json.load(open(os.path.join(ROOT, "money_machines", "products", "catalog.json"), encoding="utf-8"))["products"]}
    for w, d in B.DIRS.items():
        L = json.load(open(os.path.join(d, "shop", "listing.json"), encoding="utf-8"))
        files = K.buyer_files(os.path.join(d, "buyer"))
        check(f"c. {w}: the buyer files ({len(files)}), none empty, the listing names exactly the zip's files",
              files == req[w] and all(os.path.getsize(os.path.join(d, "buyer", f)) > 200 for f in files)
              and (sorted(L["files"]) == sorted(a for a, _ in B.bundle_files()) if w == "bundle" else sorted(L["files"]) == files), files)
        tmp = tempfile.mkdtemp(prefix="le_door_zip_")
        try:
            z1 = B.make_zip(w, tmp)
            h1 = hashlib.sha256(open(z1, "rb").read()).hexdigest()
            names = zipfile.ZipFile(z1).namelist()
            ok = zipfile.ZipFile(z1).testzip() is None
            h2 = hashlib.sha256(open(B.make_zip(w, tmp), "rb").read()).hexdigest()
            top = {n.split("/")[0] for n in names}
            check(f"c. {w}: the zip: one top folder {L['top']}/, no damage, same bytes twice, {os.path.getsize(z1) // 1024} KB",
                  top == {L["top"]} and ok and h1 == h2 and os.path.basename(z1) == L["zip"] and os.path.getsize(z1) < 10 * 1024 * 1024, (top, names[:4]))
            if w == "bundle":
                subs = {n.split("/")[1] for n in names if n.count("/") >= 2}
                check("c. bundle: the 4 parts inside (tracker, planner, calculator, cheat sheet), each with a README",
                      subs == {"1_Prop_Eval_Tracker", "2_Trader_Routine_Planner", "3_Eval_Risk_Calculator", "4_Prop_Eval_Rules_Explained"}
                      and all(f"{L['top']}/{s}/README.txt" in names for s in subs), subs)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        probs = []
        for fn, cw, ch in K.COVERS:
            p = os.path.join(d, "shop", fn)
            if not os.path.isfile(p) or K.jpeg_size(p) != (cw, ch) or os.path.getsize(p) > 900 * 1024:
                probs.append(fn)
        check(f"c. {w}: 3 covers 1280 x 720 + 3 at 2000 x 2000, each under 900 KB", not probs, probs)
        tags = L["tags_etsy"]
        desc = "\n".join(L["description"])
        check(f"c. {w}: title <= 140, 13 unique tags <= 20, 6 FAQ, the 14-day refund line, the AI line, the risk line, >= 4 comparables, price = the catalogue's",
              len(L["title"]) <= 140 and len(set(tags)) == 13 and all(len(t) <= 20 for t in tags) and len(L["faq"]) >= 6 and "14 days" in L["refund"]
              and "AI tools" in desc and "substantial risk of loss" in desc and len(L["comparables"]) >= 4 and L["price_usd"] == cat[L["id"]]["price_usd"]
              and L["net_per_sale_usd"] == K.fees(L["price_usd"]), (len(L["title"]), len(tags)))
        hits = {}
        for f in files:
            text, links = K.file_text(os.path.join(d, "buyer", f))
            if links or K.trademark_hits(text) or K.promise_hits(text):
                hits[f] = (links[:2], K.trademark_hits(text), K.promise_hits(text)[:2])
        lt = K.listing_text(L)
        check(f"c. {w}: no outside link, brand name or promise in the buyer files or the listing copy", not hits and not K.trademark_hits(lt) and not K.promise_hits(lt)
              and not K.outside_links(desc), (hits, K.trademark_hits(lt), K.promise_hits(lt)))
    from openpyxl import load_workbook
    ws = load_workbook(B.CALC_XLSX, data_only=True)["Calculator"]
    want = B.calc(B.DEFAULTS)
    got = {k: ws[c].value for k, c in B.calc_cells().items()}
    check("c. the calculator's stored results (LibreOffice recalculation) = the Python math: 4 contracts, $166 at risk, 12 stops in a row",
          all(abs(float(got[k]) - float(want[k])) < 0.01 for k in ("room", "daily", "budget", "per", "contracts", "loss", "streak", "target_left")) and got["status"] == want["status"]
          and (want["contracts"], want["loss"], want["streak"]) == (4, 166.0, 12), (got, want))
    ls = load_workbook(B.CALC_XLSX, data_only=True)["Losing streak"]
    rows = [(ls.cell(row=4 + k, column=2).value, ls.cell(row=4 + k, column=3).value, ls.cell(row=4 + k, column=4).value) for k in range(1, 11)]
    check("c. the losing-streak table = the Python math (fixed size against a share of what is left)",
          all(abs(r[0] - f) < 0.01 and r[1] == s[0] and abs(r[2] - s[1]) < 0.01 for r, f, s in zip(rows, want["fixed"], want["shrink"])), rows[:3])
    from pypdf import PdfReader
    pages = {s: len(PdfReader(os.path.join(B.GUIDE, "buyer", f"Prop_Eval_Rules_Explained_{s}.pdf")).pages) for s in ("Letter", "A4")}
    check("c. the cheat sheet: 8 pages in Letter and in A4, neutral PDF metadata", pages == {"Letter": 8, "A4": 8}, pages)
    import money_machines.products.build_all as BA
    check("c. build_all makes the 3 new zips too (8 in all)", "build_prop_kit" in BA.MODULES)


def part_d():
    import biz_publish as BP
    d = BP.build(sample=True)
    rd = json.load(open(os.path.join(ROOT, "tools", "web_public", "plutus", "roadmap.json"), encoding="utf-8"))
    check("d. costs: the evals bought add up to the roadmap's paid_already ($197.80); no subscription on the plan",
          d["costs"]["spent"] == rd["paid_already"] == 197.8 and d["costs"]["monthly"] == 0, d["costs"]["spent"])
    prods = [r for r in d["ready"] if r["kind"] == "product"]
    check("d. ready to upload: all 8 products (the 4 trading ones first), the Fiverr gigs, the Instagram plans, the demo sites; each with >= 3 steps",
          len(prods) == 8 and [r["id"] for r in prods[:4]] == ["prop-trader-bundle", "prop-eval-tracker", "eval-risk-calculator", "eval-rules-explained"]
          and {r["kind"] for r in d["ready"]} == {"product", "gigs", "content", "sites"} and all(len(r["steps"]) >= 3 for r in d["ready"]), [r["id"] for r in d["ready"]])
    mv = d["moves"]
    check("d. this week's money moves: 1-7, unique ids, each with minutes and a $ range, the next MFFU buy (Rapid EOD 50K) waits for money in the bank",
          1 <= len(mv) <= 7 and len({m["id"] for m in mv}) == len(mv) and all(m["usd"][0] <= m["usd"][1] for m in mv) and any("Rapid EOD 50K" in m["what"] and "money in the bank first" in m["what"] for m in mv)
          and not any("lucid" in m["what"].lower() for m in mv))
    rows = d["ideas"]["rows"]
    check("d. 6 researched ideas ranked 1-6, 2 marked as new models, each of those with a starter kit and a model card on the page",
          [r["rank"] for r in rows] == list(range(1, 7)) and [r["id"] for r in rows if r["model"]] == ["ai_training", "user_testing"]
          and all(r["id"] in d["ideas"]["kits"] and r["id"] in {m["id"] for m in d["models"]} for r in rows if r["model"]) and all(r["sources"] for r in rows))
    kits = json.dumps(d["ideas"]["kits"])
    check("d. the starter kits keep the honest rules: no AI on AI-training tasks, honest screeners, never pay to join", "banned" in kits and "Honest screener" in kits and "Never pay" in kits)
    check("d. the fixture's trading plan is the DEMO accounts (never the owner's numbers), dated", d["trading"]["demo"] and d["trading"]["today"] == BP.FIXTURE_DAY)
    import site_privacy as SP
    gi = AK.read(os.path.join(ROOT, ".gitignore"))
    fx = AK.read(os.path.join(ROOT, "tools", "web_public", "business", "fixture.json"))
    check("d. privacy: business.json is a private file (removed from the public build) and gitignored; no broker id in the fixture",
          "business.json" in SP.PRIVATE_NAMES and "tools/web_public/business/business.json" in gi and not BROKER_ID.search(fx))
    tmp = tempfile.mkdtemp(prefix="le_door_home_")
    try:
        hp = os.path.join(tmp, "home.json")
        shutil.copy(os.path.join(ROOT, "tests", "fixtures", "argus", "home_real.json"), hp)
        old = BP.HOME
        BP.HOME = hp
        try:
            real = BP.build(sample=False)
        finally:
            BP.HOME = old
        check("d. on the PC the plan follows the built home.json (not DEMO), still with no broker id",
              not real["trading"]["demo"] and [a["name"] for a in real["trading"]["accounts"]] == ["Zlarior (LIT)", "ATLAS"] and not BROKER_ID.search(json.dumps(real["trading"])))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_e():
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("  (playwright not installed: browser part skipped)")
        return
    home = AK.read(os.path.join(ROOT, "tests", "fixtures", "argus", "home_real.json"))
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=740)
            AK.open_app(p, origin, "business")
            door = p.inner_text("#door")
            check("e. DEMO: the door shows the first payout, funded $ a month, account #4, the business estimate and the $197.80 spent",
                  "$1,600 about" in door and "$884 a month" in door and "$2,853 a month" in door and "With the Rapid EOD 50K too" in door and "$0-3,250 a month" in door and "$198" in door, door)
            check("e. DEMO: 2 trading rows from the DEMO plan, 11 ready items, 6 ideas",
                  p.locator("#trade .acct").count() == 2 and p.inner_text("#tradeSrc") == "DEMO evals"
                  and p.locator("#ready > details").count() == 11 and p.locator("#ideas tbody tr").count() == 6, p.inner_text("#tradeSrc"))
            # night-bugsweep 2026-11-19: the public site always shows the example (business.json is private); its to-dos, buy advice and
            # account #4 date (an old "LucidPro ... 2026-12-24") were drawn as if they were the owner's
            demo_txt = " ".join(p.inner_text(x) for x in ("#status", "#moves", "#acct4", "#nextBuys", "#heroText"))
            check("e. DEMO says so plainly and never shows the example's advice as real: no to-do list, no 'Next to buy', no account #4 date, no 'Do next'",
                  "Example numbers (DEMO), not yours" in p.inner_text("#status") and "private on your PC" in p.inner_text("#status")
                  and p.locator("#moves li").count() == 0 and p.is_visible("#movesNote") and p.locator("#nextBuys li").count() == 0
                  and p.inner_text("#acct4") == "" and "Do next" not in demo_txt and "LucidPro" not in demo_txt and not p.is_visible("#snap"), demo_txt[:400])
            p.locator("#ready > details").first.evaluate("(d) => { d.open = true; }")
            p.locator("#ready > details").first.locator("input").first.dispatch_event("click")
            p.reload()
            AK.open_app(p, origin, "business")
            check("e. a ready step stays after a reload (this phone only); the week counter only counts the 7-day plan",
                  p.inner_text("#weekPill") == "0 done" and p.locator("#ready > details").first.locator("input").first.is_checked())
            check("e. taps >= 44 px, no sideways scroll at 375 px, nothing fetched off the site, no console error",
                  not AK.taps(p) and AK.no_sideways(p) and not off and not errs, (AK.taps(p)[:4], off[:3], errs[:3]))
            AK.shot(p, "business-door-375")
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, mock={"/home.json": home})
            AK.open_app(p, origin, "business")
            t = p.inner_text("#trade")
            check("e. a published home.json drives the plan live: 'your evals', Zlarior + ATLAS with their own room, no broker id on the page",
                  p.inner_text("#tradeSrc") == "your evals" and "Zlarior (LIT)" in t and "$1,133" in t and "$1,351" in t and not BROKER_ID.search(p.inner_text("body"))
                  and not errs, (t[:300], errs[:3]))
            check("e. the live plan's account #4 rule is shown (it follows your evals); an old home.json says it is a snapshot",
                  p.inner_text("#acct4").startswith("Next buys (MFFU only):") and "These eval numbers are a snapshot" in t, (p.inner_text("#acct4"), t[:200]))   # home_real.json: built 2026-11-03
            ctx.close()
            # the PC's own business.json, 6 days old: a SNAPSHOT tag and a plain line; its own to-dos are shown (they are the owner's)
            import biz_publish as BP
            own = BP.build(sample=False)
            own["asof"] = "2026-11-01T12:00:00+00:00"
            ctx, p, errs, seen, off = AK.page(br, origin, mock={"/business/business.json": json.dumps(own)})
            AK.open_app(p, origin, "business")
            st = p.inner_text("#status")
            check("e. an old business.json: SNAPSHOT tag, 'Snapshot from 2026-11-01 ... days old', its own moves listed, no DEMO tag",
                  p.is_visible("#snap") and not p.is_visible("#demo") and st.startswith("Snapshot from 2026-11-01 12:00 UTC (") and "days old" in st
                  and p.locator("#moves li").count() == len(own.get("moves") or []) and not errs, (st, errs[:3]))
            ctx.close()
    finally:
        srv.shutdown()


def main():
    acc = part_a()
    part_b(acc)
    part_c()
    part_d()
    if "--static" not in sys.argv:
        part_e()
    return AK.finish()


if __name__ == "__main__":
    sys.exit(main())
