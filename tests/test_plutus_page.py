"""PLUTUS (tools/web_public/plutus/, tools/ares_plutus_build.py, 2026-11-03): the money plan from the bot's measured numbers.

  a. the files: the OLYMPUS kit links (?v=o2), the pattern of arena / pantheon, only local scripts, the module imports exist, the Jarvis card
  b. the data: plans.json = a fresh build of research/lit/funded_firms.json; prices and caps; the published trio is reproduced by the sum
     of the three plans; the embedded copy inside plutuscore.js = plans.json (Jul-Oct), so the offline page cannot drift
  c. the maths in the page against an independent Python mirror: the first-6-month average per month equals the study's own number (the
     published trio $2,147 / $2,655 / -$92), up-front fees, the steady months-4-6 rate, month-0 = minus the fees, the extension after
     month 6, the haircut, the tax set-aside, the caps, correlated accounts do not average out, the bad case sits under the middle
  d. the page in Playwright Chromium at 390 x 844: the default plan reads $2,147 a month and says it matches the published trio, the steppers
     and their caps, the periods, the sliders, the goal, the 25K-next-to-50K warning, the saved plan, the published record from
     data.json, the offline study, no sideways scroll, the orb corner free, LITE, reduced motion, no errors

    python -X utf8 -m tests.test_plutus_page            (everything; d needs Playwright's Chromium)
    python -X utf8 -m tests.test_plutus_page fast       (a-b: no browser)
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests.olympus_money_kit import FIX, RES, WEB, browser, check, open_page, orb_hits, site, tidy_errors  # noqa: E402
from tools import ares_plutus_build as B  # noqa: E402

PAGE = os.path.join(WEB, "plutus")
TRIO = {"mffu_builder_50k": 1, "mffu_builder_25k": 0, "lucid_pro_50k": 1, "fn_rapid_daily_50k": 1}


def rd(name):
    with open(os.path.join(PAGE, name), encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------------------------------------------------ a
def part_a():
    html = rd("index.html")
    check("a. the OLYMPUS kit: olympus.css, themes.js, olympus.js (data-app) all at ?v=o2",
          all(s in html for s in ('../olympus/olympus.css?v=o7', '../olympus/themes.js?v=o10', '../olympus/olympus.js?v=o22" data-app="plutus"')))
    check("a. title Plutus, a description, theme-color = the page colour, the Jarvis icon like the siblings",
          "<title>Plutus</title>" in html and 'name="description"' in html and 'content="#000000"' in html and "../jarvis/icon-192.png" in html and "#14110e" in rd("plutus.css") + html)
    srcs = re.findall(r'(?:src|href)="([^"]+)"', html)
    check("a. only local files (no external script, font or stylesheet)", all(not s.startswith(("http:", "https:", "//")) for s in srcs), srcs)
    check("a. every local file the page links exists", all(os.path.exists(os.path.normpath(os.path.join(PAGE, s.split("?")[0]))) for s in srcs if not s.startswith("#")), srcs)
    js = rd("plutus.js") + rd("plutuscore.js")
    imps = re.findall(r"from '(\.[^']+)'", js)
    check("a. every module import resolves", all(os.path.exists(os.path.normpath(os.path.join(PAGE, i))) for i in imps), imps)
    check("a. no Yahoo; the only network is the page's own plans.json / jarvis.json and the site's ../data.json",
          "yahoo" not in js.lower() and sorted(set(re.findall(r"fetch\('([^'?]+)", js))) == ["../data.json", "jarvis.json"] and "fetch(url" in js)
    check("a. a planner: nothing in the page touches a broker, a bot or an order", not re.search(r"ninjatrader|place_?order|/api/|websocket", js, re.I))
    card = json.loads(rd("jarvis.json"))
    check("a. the Jarvis card: v 1, name, status, kpis, open #plan, the page theme, a stale_after",
          card["v"] == 1 and card["name"] == "Plutus" and card["open"] == "#plan" and card["theme"] == "#06100a" and len(card["kpis"]) >= 2 and card["stale_after"] > 0, card)
    fxs = rd("plutusfx.js")
    check("a. the OLYMPUS effects library (fx-core, ui, text, burst at ?v=f1) is linked after olympus.js; plutusfx.js is the screen of the extras and only imports the core + the library's own 3D files",
          all(f'../olympus/fx-{n}.js?v=f1' in html for n in ("core", "ui", "text", "burst")) and html.find("fx-core.js") > html.find("olympus.js?v=o22")
          and "from './plutuscore.js'" in fxs and set(re.findall(r"import\('([^']+)'", fxs)) == {"../olympus/"} and "fetch(" not in fxs and "plutusfx.js" in rd("plutus.js"))
    check("a. every extras block has a static container (goal ring, milestones, calendar, waterfall, what-if) and a never-blank empty line",
          all(f'id="{i}"' in html for i in ("goalring", "miles", "cal", "fall", "whatif")) and fxs.count("Pick at least one account") >= 2 and "Add one account first" in fxs)
    check("a. the dock and the sheet keep the bottom-right 80 x 160 px free", "padding: 8px calc(88px" in rd("plutus.css") and "bottom: calc(166px" in rd("plutus.css"))


# ------------------------------------------------------------------------------------------------------------ b
def part_b():
    built = B.build()
    doc = json.loads(rd("plans.json"))
    check("b. plans.json is a fresh build of research/lit/funded_firms.json (python tools/ares_plutus_build.py)", doc == built["plutus/plans.json"])
    check("b. jarvis.json is a fresh build", json.loads(rd("jarvis.json")) == built["plutus/jarvis.json"])
    by = {p["id"]: p for p in doc["plans"]}
    check("b. four plans: MFFU Builder 50K, Builder 25K, LucidPro 50K, FundedNext Rapid Daily 50K", list(by) == list(TRIO), list(by))
    check("b. the owner's real prices ($91.80, $63) and the research's others ($115.40, $169.99)",
          (by["mffu_builder_50k"]["price"], by["mffu_builder_25k"]["price"], by["lucid_pro_50k"]["price"], by["fn_rapid_daily_50k"]["price"]) == (91.8, 63.0, 115.4, 169.99))
    check("b. caps: 1 funded Builder 50K, 2 Builder 25K (MFFU's rule), 1 each at the others", [p["cap"] for p in doc["plans"]] == [1, 2, 1, 1])
    ff = json.load(open(os.path.join(ROOT, "research", "lit", "funded_firms.json"), encoding="utf-8"))
    ok = True
    for p in ff["plans"]:
        if p["id"] in by:
            for s in ("H1", "H2", "2021-25"):
                if by[p["id"]]["spans"][s]["net_6m"] != p["results"]["life"][s]["net_6m"] or by[p["id"]]["spans"][s]["steady"] != p["results"]["life"][s]["months4_6_per_month"]:
                    ok = False
                if by[p["id"]]["spans"][s]["first_pay_funded"] != p["results"]["funded"][s]["first_med"]:
                    ok = False
    check("b. every plan's net, months-4-6 rate and first payout from the funded start come straight from the study (H1, H2, 2021-25), rerun with the live presets", ok)
    m50 = by["mffu_builder_50k"]["spans"]
    check("b. the Builder 50K row (live presets): funded stage about $907 / $914 a month, the engine's 2-week pass / fail 52.9 / 17.8 and 58.6 / 20.9, first payout 26 / 23 sessions from the funded start and 40 / 41 from the purchase",
          (m50["H1"]["funded_per_month"], m50["H2"]["funded_per_month"]) == (906, 914) and (m50["H1"]["p10"], m50["H1"]["f10"], m50["H2"]["p10"], m50["H2"]["f10"]) == (52.9, 17.8, 58.6, 20.9)
          and (m50["H1"]["first_pay_funded"], m50["H2"]["first_pay_funded"], m50["H1"]["first_pay_sessions"], m50["H2"]["first_pay_sessions"]) == (26.0, 23.0, 40.0, 41.0), m50["H2"])
    check("b. one source for the published figures: the hub snapshot (data.json hub.funded) and the phone export (research/props/hub.json) carry the same trio and the same Builder 50K fit",
          json.load(open(os.path.join(ROOT, "tools", "web_hub_snapshot.json")))["funded"]["trio"]["H2"]["net_per_month"] == doc["trio"]["H2"]["net_per_month"]
          and next(r for r in json.load(open(os.path.join(ROOT, "research", "props", "hub.json")))["firms"]["table"] if r["plan_id"] == "mffu_builder_50k")["net_month_h2"] == m50["H2"]["per_month"],
          (doc["trio"]["H2"]["net_per_month"], m50["H2"]["per_month"]))
    sa = doc["strategy"]
    check("b. strategy block: ATLAS 25K at $43 and BLITZ 25K at $63, the MFFU cap 1 + 2 = 3 funded accounts, correlation per pair (LIT x ATLAS +0.14, LIT x BLITZ -0.06, ATLAS x BLITZ 0.00; 0.85 only for copies), the 3-account $1,532 / $1,136 with the range $1,100-1,800",
          [a["price"] for a in sa["accounts"]] == [91.8, 43.0, 63.0] and (sa["mffu_caps"]["funded_50k"], sa["mffu_caps"]["funded_25k"], sa["mffu_caps"]["funded_total"]) == (1, 2, 3)
          and [round(x["rho"], 2) for x in sa["corr_pairs"]] == [0.14, -0.06, -0.0, 0.85] and (sa["three_accounts"]["H1"]["per_month"], sa["three_accounts"]["H2"]["per_month"]) == (1532, 1136)
          and sa["accounts"][2]["funded_per_month"] == {"H1": 322, "H2": 82}
          and (sa["three_accounts"]["range"]["low"], sa["three_accounts"]["range"]["high"]) == (1100, 1800), sa["three_accounts"])
    spans = ("H1", "H2", "2021-25")
    sums = {s: sum(by[i]["spans"][s]["net_6m"] for i in ("mffu_builder_50k", "lucid_pro_50k", "fn_rapid_daily_50k")) / 6 for s in spans}
    check("b. the three plans' 6-month nets / 6 = the published trio's net a month (H1 2,655, H2 2,147, 2021-25 -92)",
          all(abs(sums[s] - doc["trio"][s]["net_per_month"]) < 1.0 for s in spans) and (doc["trio"]["H2"]["net_per_month"], doc["trio"]["H1"]["net_per_month"]) == (2147, 2655), (sums, doc["trio"]))
    check("b. the 2021-25 line is negative and labelled a reference", doc["trio"]["2021-25"]["net_per_month"] < 0 and "reference" in doc["spans"]["2021-25"])
    check("b. the notes say the accounts are correlated and that months after 6 are an extension",
          any("same trades" in n for n in doc["notes"]) and any("extension" in n for n in doc["notes"]) and doc["corr"] == 0.85)
    return doc


# ------------------------------------------------------------------------------------------------------------ c
def mirror(doc, counts, span, months, h=0.0, tax=0.0):
    """independent Python: the mean cumulative curve (after fees, haircut, tax) and the first-6-month average per month"""
    spm = doc["sessions_per_month"]
    tot = [0.0] * (months + 1)
    six = 0.0
    up = 0.0
    for p in doc["plans"]:
        n = min(p["cap"], counts.get(p["id"], 0))
        if not n:
            continue
        s = p["spans"][span]
        price, fees6 = p["price"], max(p["price"], s["fees_6m"])
        t1 = min(5.0, max(0.5, s["first_pay_sessions"] / spm))
        pay6 = max(0.0, s["net_6m"] + fees6)

        def at(k):
            pay = 0.0 if k <= t1 else pay6 * (k - t1) / (6 - t1) if k <= 6 else pay6 + s["steady"] * (k - 6)
            return pay * (1 - h) - (price + (fees6 - price) * min(1.0, k / 3))
        for k in range(months + 1):
            tot[k] += n * at(k)
        six += n * at(6)
        up += n * price
    after = lambda v: v * (1 - tax) if v > 0 else v  # noqa: E731
    return [after(v) for v in tot], after(six) / 6, up


def part_c(p, doc):
    js = """async (a) => { const C = window.__plutus.CORE; const d = await (await fetch('plans.json')).json();
      return a.map((x) => { const P = C.project(d, x.counts, x.opts); return {accounts: P.accounts, upfront: P.upfront, mean: P.mean, p10: P.p10, p90: P.p90, avg6: P.avg6, steady: P.steady,
        payback: P.payback, under6: P.under6, rows: P.rows.map(r => [r.id, r.n]), need: P.need, sig: P.sig, raw: P.raw, atM: P.atM}; }); }"""
    cases = [
        {"counts": TRIO, "opts": {"span": "H2", "months": 6}},
        {"counts": TRIO, "opts": {"span": "H1", "months": 6}},
        {"counts": TRIO, "opts": {"span": "2021-25", "months": 6}},
        {"counts": TRIO, "opts": {"span": "H2", "months": 12}},
        {"counts": TRIO, "opts": {"span": "H2", "months": 6, "haircut": 0.3}},
        {"counts": TRIO, "opts": {"span": "H2", "months": 6, "tax": 0.2}},
        {"counts": {"mffu_builder_50k": 5, "mffu_builder_25k": 9}, "opts": {"span": "H2", "months": 6}},
        {"counts": {}, "opts": {"span": "H2", "months": 6}},
        {"counts": {"mffu_builder_50k": 1}, "opts": {"span": "H2", "months": 6}},
        {"counts": {"mffu_builder_25k": 2}, "opts": {"span": "H2", "months": 6}},
        {"counts": TRIO, "opts": {"span": "H2", "months": 6, "goal": 5000}},
        {"counts": TRIO, "opts": {"span": "nonsense", "months": 99, "haircut": 5, "tax": -1}},
        {"counts": {"mffu_builder_25k": 1}, "opts": {"span": "H2", "months": 6}},
    ]
    got = p.evaluate(js, cases)
    bad = []
    for c, g in zip(cases[:6], got[:6]):
        o = c["opts"]
        m, six, up = mirror(doc, c["counts"], o["span"], o["months"], o.get("haircut", 0), o.get("tax", 0))
        if max(abs(a - b) for a, b in zip(m, g["mean"])) > 1e-6 or abs(six - g["avg6"]) > 1e-6 or abs(up - g["upfront"]) > 1e-9:
            bad.append((o, six, g["avg6"]))
    check("c. project() = the independent Python mirror on 6 cases (3 periods, 12 months, haircut, tax), curve + average + up-front", not bad, bad[:2])
    h2, h1, ref = got[0], got[1], got[2]
    check("c. the three plans over the first 6 months reproduce the published trio a month: H2 $2,147, H1 $2,655, 2021-25 -$92",
          abs(h2["avg6"] - doc["trio"]["H2"]["net_per_month"]) <= 0.5 and abs(h1["avg6"] - doc["trio"]["H1"]["net_per_month"]) <= 0.5
          and abs(ref["avg6"] - doc["trio"]["2021-25"]["net_per_month"]) < 1.0, (h2["avg6"], h1["avg6"], ref["avg6"]))
    check("c. months 4-6 rate = the study's: H2 $2,792 a month for the trio (before any haircut or tax)", round(h2["steady"]) == doc["trio"]["H2"]["months4_6_per_month"], h2["steady"])
    check("c. month 0 is minus the up-front fees ($91.80 + $115.40 + $169.99 = $377.19)", abs(h2["upfront"] - 377.19) < 1e-6 and abs(h2["mean"][0] + 377.19) < 1e-6, h2["mean"][0])
    h12 = got[3]
    check("c. after month 6 the curve continues at the months-4-6 rate (month 12 = month 6 + 6 x $2,792)", abs(h12["mean"][12] - (h12["mean"][6] + 6 * h12["steady"])) < 1e-6, (h12["mean"][6], h12["mean"][12]))
    check("c. a worse bot pays less, never more; tax only touches money made, never a loss", got[4]["avg6"] < h2["avg6"] and got[4]["steady"] < h2["steady"]
          and abs(got[5]["mean"][6] - 0.8 * h2["mean"][6]) < 1e-6 and got[5]["mean"][0] == h2["mean"][0])
    check("c. the caps hold: 5 Builder 50K and 9 Builder 25K ask for 1 + 2 accounts", sorted(got[6]["rows"]) == [["mffu_builder_25k", 2], ["mffu_builder_50k", 1]] and got[6]["accounts"] == 3, got[6]["rows"])
    check("c. nothing chosen: no accounts, no money, no crash", got[7]["accounts"] == 0 and got[7]["upfront"] == 0 and got[7]["under6"] is None and got[7]["avg6"] == 0)
    one, two = got[8], got[9]
    check("c. the Builder 50K alone is back in profit inside 3 months, with an 'under water' chance between 0 and 50%", one["payback"] is not None and 1 < one["payback"] < 3 and 0 < one["under6"] < 50, (one["payback"], one["under6"]))
    check("c. the bad case sits under the middle and the good case over it, every month", all(a <= b + 1e-9 <= c + 1e-9 for a, b, c in zip(h2["p10"], h2["mean"], h2["p90"])))
    ratio = two["sig"][6] / got[12]["sig"][6]
    check("c. two accounts of the same plan are 0.85 correlated: the spread grows by sqrt(2 + 2 x 0.85) = 1.92x, not 2x (no averaging out)", abs(ratio - math.sqrt(2 + 2 * 0.85)) < 1e-6, ratio)
    check("c. the goal helper: $5,000 a month once running needs more accounts than the trio has (need > 3)", got[10]["need"] is not None and got[10]["need"] > 3, got[10]["need"])
    check("c. nonsense in (span, 99 months, haircut 5, tax -1) is clamped: H2, 24 months at most, no NaN", len(got[11]["mean"]) == 25 and all(math.isfinite(x) for x in got[11]["mean"]), len(got[11]["mean"]))
    sf = p.evaluate("""async () => { const C = window.__plutus.CORE; const s = await (await fetch('../data.json')).json();
      return [C.siteFacts(s), C.siteFacts(null), C.siteFacts({extras: {tcols: ['pnl'], trades: []}})]; }""")
    fx = json.load(open(FIX, encoding="utf-8"))
    net = sum(t[fx["extras"]["tcols"].index("pnl")] for t in fx["extras"]["trades"])
    check("c. siteFacts reads the published record: 120 trades, +$43,820 (the headline), PF, a weekly rate; junk gives nothing",
          sf[0]["trades"]["n"] == 120 and abs(sf[0]["trades"]["net"] - net) < 0.01 and sf[0]["trades"]["pf"] > 2 and 2 < sf[0]["trades"]["tpw"] < 4
          and sf[0]["trio"]["H2"]["net_per_month"] == 2147 and sf[1] == {"trades": None, "money": None, "trio": None, "built": None} and sf[2]["trades"] is None, sf[0]["trades"])
    emb = p.evaluate("window.__plutus.CORE.EMBEDDED.plans")
    keys = ("net_6m", "net_med_6m", "net_p10_6m", "steady", "fees_6m", "first_pay_sessions")
    ours = [(pl["id"], pl["cap"], pl["price"], [pl["spans"]["H2"][k] for k in keys]) for pl in doc["plans"]]
    mine = [(pl["id"], pl["cap"], pl["price"], [pl["spans"]["H2"][k] for k in keys]) for pl in emb]
    check("c. the offline copy inside plutuscore.js equals plans.json for Jul-Oct (every number the maths uses)", ours == mine, (ours[0], mine[0]))


# ------------------------------------------------------------------------------------------------------------ d
def tab(p, t):
    p.click(f"#tabs button[data-tab='{t}']")
    p.wait_for_timeout(120)


def part_d(tmp, doc):
    from playwright.sync_api import sync_playwright
    srv1, url = site(tmp, "plutus", "s1", True)
    srv2, url_off = site(tmp, "plutus", "s2", False, drop=("plans.json", "jarvis.json", "roadmap.json"))
    try:
        with sync_playwright() as pw:
            br = browser(pw)
            errs = []
            ctx, p = open_page(br, url, errs, "__plutus")
            check("d. loads at 390 x 844: the 3D vault is up (WebGL), plans.json read, no OFFLINE tag; the ~9 MB data.json is NOT asked on open (day-archive)",
                  p.evaluate("window.__plutus.ready3d") and p.evaluate("window.__plutus.src") == "file" and not p.is_visible("#demo") and p.is_hidden("#nogl")
                  and not p.evaluate("performance.getEntriesByType('resource').some((e) => /data\\.json/.test(e.name))"))
            tab(p, "notes")
            try: p.wait_for_function("window.__plutus.live", timeout=8000)
            except Exception: pass
            check("d. the Notes tab loads data.json: PUBLISHED DATA tag shown", p.is_visible("#livetag"))
            check("d. no sideways scroll", p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            for t in ("plan", "money", "risk", "notes"):
                tab(p, t)
                check(f"d. tab '{t}': the bottom-right 80 x 160 px stays free for Jarvis's orb", not orb_hits(p), orb_hits(p))
            tab(p, "plan")
            check("d. the default plan is the published trio (50K + Lucid + FundedNext): the headline reads $2,147 a month, first 6 months",
                  p.inner_text("#hk") == "$2,147" and "first 6 months" in p.inner_text("#hs"), p.inner_text("#hk"))
            check("d. the dock line: 3 accounts, $377 up front, back in profit in about 2 months, a bad case", "3 accounts" in p.inner_text("#vline") and "$377" in p.inner_text("#vline") and "Back in profit" in p.inner_text("#vline"), p.inner_text("#vline"))
            check("d. four account rows with price, 2-week pass chance and the cap; three period buttons", p.evaluate("document.querySelectorAll('.acct').length") == 4
                  and p.evaluate("document.querySelectorAll('#spans button').length") == 3 and "$91.80" in p.inner_text("#accts"))
            check("d. + is disabled at the cap (Builder 50K max 1), - at zero (Builder 25K)", p.is_disabled("[data-inc='mffu_builder_50k']") and p.is_disabled("[data-dec='mffu_builder_25k']"))
            p.click("[data-inc='mffu_builder_25k']")
            check("d. one Builder 25K more: the headline grows, 4 accounts, and the warning about MFFU's rule shows",
                  p.evaluate("window.__plutus.project.accounts") == 4 and p.inner_text("#hk") != "$2,147" and "has not said" in p.inner_text("#accts"), p.inner_text("#hk"))
            p.click("[data-dec='mffu_builder_25k']")
            p.click("[data-dec='mffu_builder_50k']")
            check("d. one fewer Builder 50K: 2 accounts, the headline drops; the money tab lists 2 plans", p.evaluate("window.__plutus.project.accounts") == 2 and p.inner_text("#hk") != "$2,147")
            p.click("[data-inc='mffu_builder_50k']")
            p.click("#spans button[data-span='H1']")
            check("d. the Jan-Jun period: $2,655 a month", p.inner_text("#hk") == "$2,655", p.inner_text("#hk"))
            p.click("#spans button[data-span='2021-25']")
            check("d. the 2021-25 reference: -$92 a month, the headline turns red", p.inner_text("#hk") == "-$92" and p.get_attribute("#headline", "data-neg") == "1", p.inner_text("#hk"))
            p.click("#spans button[data-span='H2']")
            p.evaluate("(() => { const e = document.getElementById('haircut'); e.value = 30; e.dispatchEvent(new Event('input')); })()")
            check("d. the 'bot does worse' slider at 30%: the headline falls below $2,147 and the label says 30%", int(p.inner_text("#hk").replace("$", "").replace(",", "")) < 2147 and p.inner_text("#hairV") == "30%")
            p.evaluate("(() => { const e = document.getElementById('haircut'); e.value = 0; e.dispatchEvent(new Event('input')); const m = document.getElementById('months'); m.value = 12; m.dispatchEvent(new Event('input')); })()")
            check("d. 12 months: the headline is the 12-month average, higher than the 6-month one (the extension runs at the steady rate)",
                  int(p.inner_text("#hk").replace("$", "").replace(",", "")) > 2147 and "first 12 months" in p.inner_text("#hs"), p.inner_text("#hk"))
            p.evaluate("(() => { const m = document.getElementById('months'); m.value = 6; m.dispatchEvent(new Event('input')); })()")
            p.fill("#goal", "5000")
            tab(p, "money")
            body = p.inner_text("#money")
            check("d. money tab: up front, back in profit, a month (first 6 / months 4-6), 'Matches the trio on the published site: $2,147', the month table, the goal line",
                  all(s in body for s in ("up front", "back in profit", "$2,792", "Matches the trio on the published site: $2,147", "Bad case", "$5,000 a month once running you would need")), body[:300])
            check("d. the month table starts at Buy = -$377 and ends at month 6", "-$377" in body and p.evaluate("document.querySelectorAll('#money tbody tr').length") >= 7)
            # 2026-11-04: goal tracker, payout calendar, income waterfall, what-if (plutusfx.js) built on the OLYMPUS effects library
            m = p.evaluate("""() => { const C = window.__plutus.CORE, d = window.__plutus.doc, st = window.__plutus.state, P = window.__plutus.project;
              const o = { span: st.span, months: st.months, haircut: 0, tax: 0 }, w = C.waterfall(d, st.counts, o), cal = C.payoutCalendar(d, st.counts, o), wi = C.whatIf(d, st.counts, o);
              const ms = C.milestones(P, 5000), ms0 = C.milestones(P, ''), months = ms.items.map((i) => i.month).filter((x) => x != null);
              return { wTot: w[w.length - 1].total, raw: P.raw[P.months], upfront: P.upfront, calNet: cal.reduce((a, r) => a + r.net, 0), n: w.length, months: P.months,
                wi: wi.map((x) => [x.id, x.dUpfront, x.price, x.next.accounts - x.base.accounts]), ms: ms.items.length, ms0: ms0.items.map((i) => i.id), sorted: months.every((v, i) => !i || v >= months[i - 1]),
                cross: [C.crossing([0, 10, 20], 15), C.crossing([0, 10], 99), C.crossing([5, 10], 3)], cov: ms.coverage, steady: P.steady }; }""")
            check("d. waterfall: month 0 (the buy) + one row per month, the running total ends on the plan's month-6 balance; the calendar's net minus the buy adds to the same number",
                  m["n"] == m["months"] + 1 and abs(m["wTot"] - m["raw"]) < 0.01 and abs(m["calNet"] - m["upfront"] - m["raw"]) < 0.01, m)
            check("d. what-if: every plan with room (Builder 25K here), +1 account each, the up-front change = that plan's price",
                  m["wi"] and all(w[3] == 1 and abs(w[1] - w[2]) < 0.001 for w in m["wi"]) and any(w[0] == "mffu_builder_25k" for w in m["wi"]), m["wi"])
            check("d. milestones: 5 with a goal (profit + 4 goal multiples), the money ones without; months only ever go up; crossing() interpolates",
                  m["ms"] == 5 and m["ms0"] == ["profit", "k1", "k5", "k10"] and m["sorted"] and m["cross"] == [1.5, None, 0] and abs(m["cov"] - m["steady"] / 5000) < 1e-9, m)
            check("d. the money tab shows the goal tracker (ring + milestones), one calendar cell per month and a waterfall row per month plus the buy",
                  p.evaluate("document.querySelectorAll('#miles li').length") == 5 and p.evaluate("document.querySelectorAll('#cal .cell').length") == 6
                  and p.evaluate("document.querySelectorAll('#fall .wf').length") == 7 and p.inner_text("#goalpct").endswith("%") and p.get_attribute("#goalring", "aria-label").startswith("Goal coverage"))
            check("d. the effects library is on the page: fx-core + ring on the goal host (a canvas), the headline carries data-oly-fx",
                  p.evaluate("!!window.OLYMPUS_FX && OLYMPUS_FX.has('progressRing') && OLYMPUS_FX.has('countUp')") and p.evaluate("document.querySelectorAll('#goalring canvas').length") == 1
                  and "shimmer" in (p.get_attribute("#headline", "data-oly-fx") or "") and p.get_attribute("#hk", "data-oly-fx") == "odometer")
            tab(p, "plan")
            check("d. plan tab: the what-if block previews the best next account with a before / after bar and an add button",
                  p.evaluate("document.querySelectorAll('#whatif .wirow').length") >= 1 and p.is_visible("#addit") and p.evaluate("document.querySelectorAll('#whatif .wibar').length") == 2)
            n0 = p.evaluate("window.__plutus.project.accounts")
            added = p.get_attribute("#addit", "data-add")
            p.click("#addit")
            check("d. 'Add it to my plan' adds one account and the page recomputes", p.evaluate("window.__plutus.project.accounts") == n0 + 1, (n0, p.evaluate("window.__plutus.project.accounts")))
            p.click(f"[data-dec='{added}']")                  # back to the plan the rest of the checks expect
            check("d. ... and the minus button takes it off again", p.evaluate("window.__plutus.project.accounts") == n0)
            tab(p, "money")
            tab(p, "risk")
            risk = p.inner_text("#risk")
            check("d. risk tab: under-water chance, the bad case, '50% worse', the other periods (2021-25 as a reference), the correlation, accounts lost",
                  all(s in risk for s in ("under water", "Bad case", "50% worse", "Jan-Jun 2026", "2021-25", "reference line", "0.85 correlation", "funded accounts lost")), risk[:300])
            tab(p, "notes")
            notes = p.inner_text("#notes")
            check("d. notes tab: the source, the bot's published record (120 trades, $43,820), the owner's prices, 'not a promise'",
                  all(s in notes for s in ("funded_firms.json", "120 trades", "$43,820", "$91.80", "Not a promise")), notes[:300])
            p.click("#headline")
            check("d. tapping the big number opens the money tab", p.evaluate("window.__plutus.tab") == "money")
            ctx.close()
            check("d. no page errors, console errors or failed requests", not errs, errs[:5])

            errs = []
            ctx, p = open_page(br, url + "#risk", errs, "__plutus")
            check("d. #risk opens the risk tab; #plan (the Jarvis card's link) opens the plan tab", p.evaluate("window.__plutus.tab") == "risk")
            p.evaluate("location.hash = '#plan'"); p.wait_for_timeout(150)
            ok1 = p.evaluate("window.__plutus.tab") == "plan"
            p.click("[data-dec='lucid_pro_50k']"); p.click("#spans button[data-span='H1']")
            p.reload(); p.wait_for_function("window.__plutus && window.__plutus.siteLoaded === true"); p.wait_for_timeout(300)
            st = p.evaluate("window.__plutus.state")
            check("d. the plan is remembered on this phone (no Lucid, Jan-Jun)", ok1 and st["counts"]["lucid_pro_50k"] == 0 and st["span"] == "H1" and p.evaluate("window.__plutus.project.accounts") == 2, st)
            ctx.close()
            check("d. no errors on the route page", not errs, errs[:5])

            errs2 = []
            ctx, p = open_page(br, url_off, errs2, "__plutus")
            check("d. no plans.json, no data.json: the embedded Jul-Oct study runs, OFFLINE STUDY shows, no PUBLISHED tag, one period button",
                  p.evaluate("window.__plutus.src") == "embedded" and p.is_visible("#demo") and p.is_hidden("#livetag") and p.evaluate("document.querySelectorAll('#spans button').length") == 1)
            check("d. ... and the default plan still reads $2,147 a month (the same numbers as the file)", p.inner_text("#hk") == "$2,147", p.inner_text("#hk"))
            tab(p, "notes")
            check("d. ... the notes say the published data was not found", "was not found" in p.inner_text("#notes"))
            ctx.close()
            bad = tidy_errors(errs2, allow=("plans.json", "data.json", "jarvis.json", "roadmap.json"))
            check("d. offline: only the missing files' 404s, nothing else", not bad, bad[:5])

            errs3 = []
            ctx, p = open_page(br, url + "?lite=1", errs3, "__plutus")
            check("d. ?lite=1 forces LITE with no errors", p.evaluate("window.__plutus.lite") is True and not errs3, errs3[:3])
            ctx.close()
            errs4 = []
            ctx, p = open_page(br, url, errs4, "__plutus", reduced=True)
            y0 = p.evaluate("window.__plutus.yaw")
            p.wait_for_timeout(1500)
            p.click("[data-dec='lucid_pro_50k']")
            check("d. reduced motion: the vault stays still (no idle turn), the sliders and steppers still work, no errors",
                  abs(p.evaluate("window.__plutus.yaw") - y0) < 1e-6 and p.evaluate("window.__plutus.project.accounts") == 2 and not errs4, errs4[:3])
            ctx.close()
            br.close()
    finally:
        srv1.shutdown()
        srv2.shutdown()


# ------------------------------------------------------------------------------------------------------------ e: the Money plan card (2026-11-04)
def part_e_static():
    from tools import money_roadmap as MR
    raw = rd("roadmap.json")
    doc = json.loads(raw)
    check("e. roadmap.json (the Money plan) is small: under 25 KB", len(raw.encode("utf-8")) < 25_000, len(raw))
    full = json.load(open(MR.OUT_P, encoding="utf-8"))
    check("e. roadmap.json is a fresh build of research/props/roadmap.json (python tools/money_roadmap.py report)", doc == MR.compact(full))
    fb = rd("roadmapfallback.js")
    m = re.search(r"export const FALLBACK = (\{.*\});\s*$", fb, re.S)
    check("e. the offline copy roadmapfallback.js equals roadmap.json exactly", bool(m) and json.loads(m.group(1)) == doc)
    n = len(doc["versions"]["H2"]["months"])
    check("e. 12 monthly rows for the conservative Jul-Oct and for Jan-Jun, in that order (conservative first)",
          n == 12 == len(doc["versions"]["H1"]["months"]) and list(doc["versions"])[:2] == ["H2", "H1"] and doc["conservative"] == "H2")
    check("e. the rows reconcile: cash in - fees = net each month; the last total = the year's average net",
          all(abs(r["in"] - r["out"] - r["net"]) <= 1 for v in doc["versions"].values() for r in v["months"]))
    check("e. per account: a first-payout range (3 dates) and a payback month, both versions; an order of buying; a sentence for every month",
          len(doc["accounts"]) >= 3 and all(len(a[k]["first"]) == 3 and a[k]["payback"] for a in doc["accounts"] for k in ("H2", "H1"))
          and len(doc["todo"]) == n and doc["order"]["best"] and doc["order"]["wait_cost"]["H2"])
    check("e. the caveats are plain sentences and include 'check the MFFU rules before copying a strategy to a second account'",
          len(doc["caveats"]) >= 5 and any("Check the MFFU rules before copying a strategy to a second account" in c for c in doc["caveats"]))
    js = rd("plutusroadmap.js")
    check("e. plutusroadmap.js reads only its own roadmap.json (GET), no Yahoo, no innerHTML, imports only the generated fallback",
          sorted(set(re.findall(r"url = '([^']+)'", js))) == ["roadmap.json"] and "yahoo" not in js.lower() and "innerHTML" not in js
          and re.findall(r"from '([^']+)'", js) == ["./roadmapfallback.js"] and "method" not in js)
    check("e. the card is linked into the page (index.html section + plutus.js import), cache bump v=m3",
          'id="mplanBody"' in rd("index.html") and "plutusroadmap.js" in rd("plutus.js") and "plutus.js?v=m3" in rd("index.html"))
    return doc


def part_e_browser(tmp, doc):
    from playwright.sync_api import sync_playwright
    n = len(doc["versions"]["H2"]["months"])
    srv1, url = site(tmp, "plutus", "e1", True)
    srv2, url_off = site(tmp, "plutus", "e2", False, drop=("roadmap.json",))
    try:
        with sync_playwright() as pw:
            br = browser(pw)
            errs = []
            ctx, p = open_page(br, url + "?today=2026-12-10", errs, "__plutus")
            p.wait_for_function("document.getElementById('mplanBody').dataset.src")
            check("e. the Money plan card is the first thing on the Plan tab, the file was read (no OFFLINE COPY tag)",
                  p.is_visible("#mplan") and p.get_attribute("#mplanBody", "data-src") == "file" and p.is_hidden("#mplanTag")
                  and p.evaluate("document.querySelector('#p-plan').firstElementChild.id") == "mplan")
            check("e. the plain verdict sentence is the file's headline", p.inner_text("#mplanBody .mp-head") == doc["headline"])
            cells = p.evaluate("[...document.querySelectorAll('#mplanBody .mp-cell')].map(c => c.innerText)")
            v2, v1 = doc["versions"]["H2"], doc["versions"]["H1"]
            usd = lambda x: ("-$" if x < 0 else "$") + f"{abs(x):,.0f}"
            check("e. the conservative number is first (Jul-Oct), Jan-Jun second, each with its worst and best case",
                  len(cells) == 2 and "Conservative" in cells[0] and usd(v2["mid"]) in cells[0] and usd(v2["lo"]) in cells[0] and usd(v2["hi"]) in cells[0]
                  and "Jan-Jun" in cells[1] and usd(v1["mid"]) in cells[1], cells)
            now = p.inner_text("#mplanBody .mp-now")
            check("e. a plain 'what to do this month' sentence: today 2026-12-10 is month 2 with its own sentence and expected cash",
                  now.startswith("This month (month 2,") and doc["todo"][1] in now and usd(v2["months"][1]["net"]) in now and usd(v1["months"][1]["net"]) in now, now[:300])
            rows = p.evaluate("document.querySelectorAll('#mplanBody table.mp-months tr').length")
            check("e. the month table has a header and one row for each month in the file", rows == n + 1, rows)
            check("e. the running month (2) is marked", p.evaluate("[...document.querySelectorAll('#mplanBody table.mp-months tr')].findIndex(r => r.classList.contains('me'))") == 2)
            small = p.evaluate("""() => [...document.querySelectorAll('#mplan button, #mplan summary')].filter(e => e.offsetParent !== null).map(e => { const r = e.getBoundingClientRect(); return [e.textContent.trim().slice(0, 24), Math.round(r.width), Math.round(r.height)]; }).filter(x => x[1] < 44 || x[2] < 44)""")
            check("e. every button and fold-out title in the card is at least 44 x 44 px", not small and p.evaluate("document.querySelectorAll('#mplan button').length") == 2, small)
            p.click("#mplan [data-mp='H1']")
            p.wait_for_timeout(100)
            first_row = p.evaluate("[...document.querySelectorAll('#mplanBody table.mp-months tr')][1].innerText")
            check("e. Jan-Jun button: pressed, the table switches to Jan-Jun, still " + str(n) + " rows",
                  p.get_attribute("#mplan [data-mp='H1']", "aria-pressed") == "true" and p.get_attribute("#mplan [data-mp='H2']", "aria-pressed") == "false"
                  and usd(v1["months"][0]["net"]) in first_row and p.evaluate("document.querySelectorAll('#mplanBody table.mp-months tr').length") == n + 1, first_row)
            for d in ("Who pays first", "Order of buying", "Read this first"):
                p.click(f"#mplan summary:has-text('{d}')")
            txt = p.inner_text("#mplanBody")
            check("e. who pays first (a range for each account), the order of buying and the MFFU-rules warning are all readable",
                  all(a["H2"]["first"][1] in txt for a in doc["accounts"]) and doc["order"]["best"] in txt and "Check the MFFU rules before copying a strategy to a second account" in txt)
            check("e. no sideways scroll with the card open, the orb corner stays free", p.evaluate("document.documentElement.scrollWidth <= innerWidth") and not orb_hits(p), orb_hits(p))
            ctx.close()
            check("e. no errors on the page with the card", not errs, errs[:5])
            errs2 = []
            ctx, p = open_page(br, url_off, errs2, "__plutus")
            p.wait_for_function("document.getElementById('mplanBody').dataset.src")
            check("e. roadmap.json missing: the card is never blank, shows the OFFLINE COPY tag and the same headline and numbers",
                  p.get_attribute("#mplanBody", "data-src") == "offline" and p.is_visible("#mplanTag") and p.inner_text("#mplanBody .mp-head") == doc["headline"]
                  and p.evaluate("document.querySelectorAll('#mplanBody table.mp-months tr').length") == n + 1)
            ctx.close()
            bad = tidy_errors(errs2, allow=("roadmap.json",))
            check("e. offline: only the missing file's 404, nothing else", not bad, bad[:5])
            br.close()
    finally:
        srv1.shutdown()
        srv2.shutdown()


def main(argv):
    fast = "fast" in argv
    tmp = tempfile.mkdtemp(prefix="plutus_test_")
    try:
        part_a()
        doc = part_b()
        rm = part_e_static()
        if not fast:
            from playwright.sync_api import sync_playwright
            srv, url = site(tmp, "plutus", "c", True)
            try:
                with sync_playwright() as pw:
                    br = browser(pw)
                    errs = []
                    ctx, p = open_page(br, url, errs, "__plutus")
                    part_c(p, doc)
                    ctx.close()
                    br.close()
            finally:
                srv.shutdown()
            part_d(tmp, doc)
            part_e_browser(tmp, rm)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed", flush=True)
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
