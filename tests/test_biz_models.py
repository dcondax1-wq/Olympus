"""BUSINESS (team BIZ, 2026-11-15): the one price list, the Business page, the agency day in one double-click, the listing kit.

  a. the page (tools/web_public/business/): the AGORA kit, read-only, the DEMO fixture, the Jarvis card
  b. businesscore.js in node: clean() drops junk, money / range words, the first action, the price line
  c. ONE price list: agency.config.prices() = the billing kit's plans = the storefront's plans = the pitch kit = the Agency page defaults;
     agency/billing/packages.json holds no prices
  d. tools/biz_publish.py: every model, the totals are the sums of the models that are not paused, docs/BUSINESS.md shows the same numbers,
     the local state is counts only, the 7-day plan
  e. the listing kit: all 5 catalog products, every cover on disk, the doc is up to date, zip names = the product builders'
  c. Chromium (skipped with --static): DEMO, the PC's own file, ticks kept, taps, no sideways scroll
  f. agency.day on the committed demo batch (no network): the call list, TODAY.txt (prices, demo sites, rules), AGENCY_DAY.bat
    python -X utf8 -m tests.test_biz_models
Read only for the repo: writes go to temp folders. No network, no browser.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tempfile
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
TMP = tempfile.mkdtemp(prefix="le_bizm_")
os.environ["AGENCY_CONFIG"] = os.path.join(TMP, "no_config.json")       # the example values only (never the PC's own copy)
from tests import agora_kit as AK  # noqa: E402

check = AK.check
APP, NAME = "business", "Business"
WEBD = os.path.join(AK.WEB, APP)


def test_page():
    AK.static_kit(APP, NAME, reads=("./business.json",), storage="ls")
    js = AK.read(os.path.join(WEBD, "business.js"))
    check("a. the only browser storage is the 7-day ticks under one key (business.week.v1), wrapped in try / catch",
          js.count("localStorage.") == 2 and "business.week.v1" in js and js.count("try {") >= 3 and not re.search(r"sessionStorage|indexedDB", js))
    fx = json.load(open(os.path.join(WEBD, "fixture.json"), encoding="utf-8"))
    check("a. the fixture: kind business, ESTIMATE, sample + demo, no local progress, 7 models, 7 days",
          fx["kind"] == "business" and fx["label"] == "ESTIMATE" and fx["sample"] and fx["demo"] and fx["progress"] == {} and len(fx["models"]) == 7 and len(fx["week"]) == 7)
    import biz_publish as BP
    fresh = BP.build(sample=True)
    fresh["asof"] = fx["asof"]
    check("a. the committed fixture is what biz_publish --fixture makes today (rerun it after a change)", fresh == fx)
    check("a. business.json (the PC's own progress) is gitignored", "tools/web_public/business/business.json" in AK.read(os.path.join(ROOT, ".gitignore")))


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {};
  o.words = [C.money(2630.4), C.money(null), C.range([0, 2630]), C.range('x'), C.priceLine({ setup: 499, monthly: 49 }), C.priceLine({ setup: 0, monthly: 99 }), C.taskKey(3, 1)];
  o.bad = [C.clean(null), C.clean({ kind: 'other', models: [] }), C.clean({ kind: 'business' })];
  const d = C.clean({ kind: 'business', sample: 1, models: [null, { id: 'x' }, { id: 'k', name: 'Kalshi', paused: true, next: 'Nothing' },
    { id: 'a', name: 'Agency', next: 'Call 10', usd_m1: [0, 550], usd_m3: [-5, 'q'], hours: [5, 7], built: ['a', 3, 'b'], first_dollar: 'no' }],
    total: { usd_m3: [0, 2630], real_usd_month: 'x' }, prices: [{ name: 'Starter', setup: 499, monthly: 49 }, { setup: 1 }], week: [{ day: 1, title: 'T', tasks: ['a', 2] }, { day: 'q' }], rules: ['r', 5] });
  o.clean = [d.models.length, d.models[1].usd_m3, d.models[1].built, d.models[1].first_dollar, d.total.real, d.total.usd_m3, d.prices.length, d.week.length, d.week[0].tasks, d.rules, d.sample];
  o.first = [C.firstAction(d), C.firstAction({ models: [] })];
  process.stdout.write(JSON.stringify(o));
});
"""


def test_core():
    o = AK.node(APP, HARNESS)
    if o is None:
        print("  (node not found: part b skipped)")
        return
    check("b. money and range words, the price line with and without a setup fee, the tick key",
          o.get("words") == ["$2,630", "$0", "$0-2,630", "-", "$499 + $49 a month", "$99 a month, no setup fee", "d3t1"], o)
    check("b. clean() refuses what is not a business file", o["bad"] == [None, None, None], o["bad"])
    check("b. clean(): junk models dropped, bad ranges become 0-0, non-text list items dropped, a bad real becomes 0, junk prices / days dropped",
          o["clean"] == [2, [0, 0], ["a", "b"], [], 0, [0, 2630], 1, 1, ["a"], ["r"], True], o["clean"])
    check("b. the first action skips a paused model", o["first"] == ["Agency: Call 10", "Nothing to do."], o["first"])


def _storefront():
    spec = importlib.util.spec_from_file_location("sf_build", os.path.join(ROOT, "agency", "storefront", "build.py"))
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.join(ROOT, "agency", "storefront"))
    spec.loader.exec_module(m)
    return m


def test_prices():
    from agency import config as CFG
    from agency.billing import store as S
    pr = CFG.prices()
    want = {"starter": (499.0, 49.0), "growth": (999.0, 79.0), "pro": (1999.0, 129.0)}
    check("c. the one source: agency.config.prices() = the example's packages", {k: (v["setup"], v["monthly"]) for k, v in pr.items()} == want, pr)
    raw = json.load(open(os.path.join(ROOT, "agency", "billing", "packages.json"), encoding="utf-8"))
    check("c. agency/billing/packages.json holds only wording (no setup_usd / monthly_usd) and says where the prices are",
          not any(k in p for p in raw["packages"] for k in ("setup_usd", "monthly_usd", "setup", "monthly")) and "agency.config.prices()" in raw["note"])
    bp = S.Store.packages()
    check("c. the billing kit's proposal / invoice plans quote the same prices", {k: (v["setup_usd"], v["monthly_usd"]) for k, v in bp.items()} == want, bp)
    check("c. the billing kit keeps its own wording (taglines, includes, edits a month)", all(bp[k]["tagline"] and len(bp[k]["includes"]) >= 5 for k in want))
    own = os.path.join(TMP, "owner.json")
    json.dump({"packages": [{"id": "starter", "name": "Starter", "setup": 299, "monthly": 59}]}, open(own, "w"))
    os.environ["AGENCY_CONFIG"] = own
    try:
        bp2 = S.Store.packages()
        check("c. the owner's agency/config.json price wins everywhere at once (billing follows a changed Starter price)",
              (bp2["starter"]["setup_usd"], bp2["starter"]["monthly_usd"]) == (299.0, 59.0) and CFG.prices()["starter"]["monthly"] == 59.0, bp2["starter"])
    finally:
        os.environ["AGENCY_CONFIG"] = os.path.join(TMP, "no_config.json")
    sf = _storefront()
    sc = sf.load_config(shared_path=None, local_path=None)
    check("c. the storefront's plans are the same prices", {p["id"]: (float(p["setup_usd"]), float(p["monthly_usd"])) for p in sc["packages"]} == want, sc["packages"])
    core = AK.read(os.path.join(AK.WEB, "agency", "agencycore.js"))
    got = {m[0]: (float(m[1]), float(m[2])) for m in re.findall(r"\{ id: '(\w+)', name: '\w+', setup: (\d+), monthly: (\d+) \}", core)}
    check("c. the Agency page's built-in defaults are the same prices", got == want, got)
    from agency import pitch as P
    cfg = CFG.load()
    lead = json.load(open(os.path.join(ROOT, "agency", "demo", "fort-collins", "leads.json"), encoding="utf-8"))["leads"][0]
    from agency import build_site as B
    k = P.write_kit(lead, cfg, "https://x-demo.netlify.app", os.path.join(TMP, "kit"), B.THEMES[lead["template"]]["palette"])
    check("c. the pitch kit quotes a price from the one source", (float(k["setup"]), float(k["monthly"])) in want.values(), (k["setup"], k["monthly"]))


def test_publish():
    import biz_publish as BP
    d = BP.build(sample=True)
    live = [m for m in d["models"] if not m["paused"]]
    check("d. 7 models, 2 paused (rank-and-rent, Kalshi), each with a next step, a first-dollar list and ranges low <= high",
          len(d["models"]) == 7 and {m["id"] for m in d["models"] if m["paused"]} == {"rank_rent", "kalshi"}
          and all(m["next"] and m["first_dollar"] and m["usd_m1"][0] <= m["usd_m1"][1] and m["usd_m3"][0] <= m["usd_m3"][1] for m in d["models"]))
    check("d. the totals are the sums of the models that are not paused",
          all(d["total"][k] == [sum(m[k][0] for m in live), sum(m[k][1] for m in live)] for k in ("usd_m1", "usd_m3", "hours")), d["total"])
    doc = AK.read(os.path.join(ROOT, "docs", "BUSINESS.md"))
    t = d["total"]
    check("d. docs/BUSINESS.md shows the same totals and every model's month-3 range",
          f"**${t['usd_m1'][0]}-{t['usd_m1'][1]:,}**" in doc and f"**${t['usd_m3'][0]}-{t['usd_m3'][1]:,}**" in doc
          and all(f"${m['usd_m3'][0]}-{m['usd_m3'][1]:,}" in doc or m["usd_m3"] == [0, 0] for m in d["models"]), t)
    check("d. the 7-day plan: days 1-7 in the page data and in docs/BUSINESS.md", [w["day"] for w in d["week"]] == list(range(1, 8)) and all(f"**Day {i}," in doc for i in range(1, 8)))
    check("d. the prices on the page come from the one source", [(p["id"], p["setup"], p["monthly"]) for p in d["prices"]] == [("starter", 499.0, 49.0), ("growth", 999.0, 79.0), ("pro", 1999.0, 129.0)])
    real = BP.build(sample=False)
    check("d. the PC's own file: progress is counts and flags only (no names, phones or emails), real $ only from the billing ledger",
          all(isinstance(v, (int, float, bool)) or v is None for v in real["progress"].values()) and not real["sample"] and real["total"]["real_usd_month"] >= 0, real["progress"])
    check("d. next steps follow the progress: with the example settings the agency asks for the settings first",
          real["models"][0]["next"].startswith("Double-click AGENCY_DAY.bat and fill in"), real["models"][0]["next"])
    card = BP.card(d)
    check("d. the Jarvis card follows the contract", not AK.jarvis_problems(card), AK.jarvis_problems(card))
    out = os.path.join(TMP, "b.json")
    BP.write(real, out)
    check("d. write() makes valid JSON (atomic)", json.load(open(out))["kind"] == "business")


def test_listing_kit():
    from money_machines.products import listing_kit as LK
    ps = LK.products()
    cat = json.load(open(os.path.join(ROOT, "money_machines", "products", "catalog.json"), encoding="utf-8"))
    check("e. all 5 catalog products are in the kit, at the catalog's prices", [p["id"] for p in ps] == [c["id"] for c in cat["products"]] and
          all(p["price_usd"] == float(c["price_usd"]) for p, c in zip(ps, cat["products"])))
    check("e. nothing missing: title, description, zip, 5+ tags, wide and square covers on disk", not LK.problems(ps), LK.problems(ps))
    check("e. docs/BUSINESS_LISTING_KIT.md is up to date (rerun python -m money_machines.products.listing_kit)",
          AK.read(os.path.join(ROOT, "docs", "BUSINESS_LISTING_KIT.md")) == LK.markdown(ps))
    check("e. every zip is a v1.0 upload zip named by the product's own listing", all(re.fullmatch(r"[a-z_]+_v1\.0\.zip", p["zip"]) for p in ps), [p["zip"] for p in ps])
    md = LK.markdown(ps)
    check("e. the kit names the free shops (Payhip, Gumroad, Etsy), the AI line and NOT LEGAL ADVICE, and no income promise",
          all(x in md for x in ("Payhip", "Gumroad", "Etsy", "help of AI tools", "NOT LEGAL ADVICE")) and not re.search(r"guarantee|passive income|get rich", md, re.I))


def test_day():
    from agency import day as D
    demo = os.path.join(ROOT, "agency", "demo", "fort-collins")
    batch = os.path.join(TMP, "out", "fort-collins")
    os.makedirs(batch)
    for n in ("leads.json", "run.json"):
        shutil.copy(os.path.join(demo, n), batch)
    calls = os.path.join(TMP, "calls")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = D.main(["--skip-leads", "--out", batch, "--calls-out", calls, "--no-publish"])
    out = buf.getvalue()
    sheet = AK.read(os.path.join(TMP, "out", "TODAY.txt"))
    check("f. agency.day on the demo batch: exit 0, the call list written to its own folder, TODAY.txt made", rc == 0 and os.path.isfile(os.path.join(calls, "call_list.json")) and sheet, out[-400:])
    run = json.load(open(os.path.join(batch, "run.json"), encoding="utf-8"))
    check("f. TODAY.txt: the one price list, every demo site with its folder, at least one lead to call, the rules, the email status",
          "Starter $499 + $49/mo" in sheet and all(s["name"] in sheet for s in run["sites"]) and "CALL FIRST" in sheet and "Dial by hand" in sheet and "Emails:" in sheet, sheet[:600])
    cl = json.load(open(os.path.join(calls, "call_list.json"), encoding="utf-8"))
    rows = D.call_rows({"rows": [{"lead": {"name": "A", "phone": "+19705550123"}, "block": {"lock": True, "code": "optout"}, "win": None},
                                 {"lead": {"name": "B", "phone": ""}, "block": None, "win": None},
                                 {"lead": {"name": "C", "phone": "+19704820000"}, "block": None, "win": {"code": "best"}}]})
    check("f. the sheet never lists a locked (do not call / opted out) lead or one with no phone", [r["name"] for r in rows] == ["C"] and rows[0]["when"] == "good now", rows)
    check("f. the call list keeps the leads (nothing dialled, nothing sent)", cl["kind"] == "call_list" and len(cl["leads"]) > 0)
    src = AK.read(os.path.join(ROOT, "agency", "day.py"))
    check("f. agency.day sends nothing: no smtp / requests / urllib / webbrowser / twilio in its code", not re.search(r"smtplib|import requests|urllib\.request|webbrowser|twilio", src))
    raw = open(os.path.join(ROOT, "AGENCY_DAY.bat"), "rb").read()
    txt = raw.decode("ascii")
    labels = set(re.findall(r"(?m)^:(\w+)", txt))
    check("f. AGENCY_DAY.bat: CRLF, ASCII, every goto label exists, first run copies the example settings and opens Notepad, then runs agency.day",
          b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"") and set(re.findall(r"goto :(\w+)", txt)) <= labels
          and 'copy /y "agency\\config.example.json" "agency\\config.json"' in txt and "python -X utf8 -m agency.day %*" in txt and not re.search(r"curl|Invoke-WebRequest|powershell", txt, re.I))


def test_browser():
    """c. Chromium 390 x 844: the DEMO fixture, then the PC's own business.json (mocked), the 7-day ticks kept, taps, no sideways scroll"""
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("  (playwright not installed: browser part skipped)")
        return
    import biz_publish as BP
    own = BP.build(sample=False)
    own["total"]["real_usd_month"] = 49.0
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP)
            check("c. DEMO: the tag, the month-3 range, 7 model cards, 7 table rows, 21 ticks, the 3 prices",
                  p.is_visible("#demo") and p.inner_text("#heroM3") == "$0-2,630 a month" and p.locator("#models > section").count() == 7
                  and p.locator("#tbl tbody tr").count() == 7 and p.locator("#week input").count() == 21 and "Starter" in p.inner_text("#prices"), p.inner_text("#status"))
            p.locator("#week input").first.scroll_into_view_if_needed()
            p.locator("#week input").first.dispatch_event("click")   # the AGORA app bar can sit over the row while scrolling
            p.reload()
            AK.open_app(p, origin, APP)
            check("c. a tick stays after a reload (this browser only)", p.locator("#week input").first.is_checked() and p.inner_text("#weekPill") == "1 done")
            check("c. taps >= 44 px, no sideways scroll at 390 px, nothing fetched off the site, no console error",
                  not AK.taps(p) and AK.no_sideways(p) and not off and not errs, (AK.taps(p)[:4], off[:3], errs[:3]))
            AK.shot(p, "business-390")
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, mock={"/business/business.json": json.dumps(own)})
            AK.open_app(p, origin, APP)
            check("c. the PC's own business.json wins over the fixture: no DEMO tag, real $49 shown",
                  not p.is_visible("#demo") and "$49 a month" in p.inner_text("#heroKv") and AK.no_sideways(p) and not errs, errs[:3])
            ctx.close()
    finally:
        srv.shutdown()


def main():
    try:
        test_page()
        test_core()
        test_prices()
        test_publish()
        test_listing_kit()
        test_day()
        if "--static" not in sys.argv:
            test_browser()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    return AK.finish()


if __name__ == "__main__":
    sys.exit(main())
