"""OIKOS "Your bank money" card (tools/web_public/oikos/household.js + householdcore.js, 2026-11-14). Chromium 390 x 844 / 375 x 667:
  a. static: its own module after oikos.js, text only through textContent, it reads only ../money/household.json, the core is pure
  b. with a household.json (built by tools/money_import.py from the synthetic household of tests/test_money_import.py): the card shows,
     its numbers are the file's, categories / subscriptions / leaks listed, no merchant name, no console error, no sideways scroll
  c. without the file (the public site): the card says "Not connected" and how; Oikos itself still works (DEMO); ?demo=1 never reads it
    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_oikos_household
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402
from tests import test_money_import as T  # noqa: E402
from tools import money_import as MI  # noqa: E402

check = AK.check
D = os.path.join(AK.WEB, "oikos")
CARD = """() => { const c = document.querySelector('#hhCard'); return { hidden: c.hidden, pill: document.querySelector('#hhPill').textContent,
  kv: [...document.querySelectorAll('#hhKv dt')].map((d) => [d.textContent, d.nextElementSibling.textContent]), cats: [...document.querySelectorAll('#hhCats b')].map((b) => b.textContent),
  subs: [...document.querySelectorAll('#hhSubs li')].map((l) => l.textContent), leaks: document.querySelectorAll('#hhLeaks li').length, lines: document.querySelector('#hhLines').textContent,
  text: c.textContent, state: window.OIKOS_HOUSEHOLD && window.OIKOS_HOUSEHOLD.state() }; }"""


def doc():
    tmp = tempfile.mkdtemp()
    try:
        T.write_exports(tmp, T.household_rows())
        led, _ = T.fresh_ledger([os.path.join(tmp, "card.csv"), os.path.join(tmp, "bank.csv")])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bal = {"accounts": [{"name": "Checking", "kind": "cash", "usd": 3000}, {"name": "Savings", "kind": "savings", "usd": 6000}]}
    return MI.build(led, MI.DEFAULT_RULES_DOC, T.TODAY, bal, None, [])


def test_static():
    js, core, html = (AK.read(os.path.join(D, n)) for n in ("household.js", "householdcore.js", "index.html"))
    check("a. index.html loads household.js as its own module after oikos.js, and has the hidden card", html.index('src="oikos.js') < html.index('src="household.js') and 'id="hhCard"' in html and 'type="module" src="household.js' in html)
    check("a. household.js reads only ../money/household.json and sends nothing", set(re.findall(r"getJSON\('([^']+)'", js)) == {"../money/household.json"} and not re.search(r"XMLHttpRequest|WebSocket|sendBeacon|POST|document\.cookie|localStorage|https?://", js))
    check("a. no markup from data (no innerHTML / insertAdjacentHTML / eval), text through textContent", not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function", js + core) and "textContent" in js)
    check("a. householdcore.js is pure and Safari 16 safe", not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(|\blocalStorage\b|\(\?<[=!]|\.at\(", re.sub(r"//[^\n]*", "", core)))


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("b. page tests skipped: no Playwright", True)
        return
    d = doc()
    srv, origin = AK.serve({"/money/household.json": json.dumps(d)})
    srv0, origin0 = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, "oikos", f"?today={T.TODAY}")
            p.wait_for_function("window.OIKOS_HOUSEHOLD && window.OIKOS_HOUSEHOLD.ready()", timeout=60000)
            c = p.evaluate(CARD)
            kv = dict(c["kv"])
            check("b. with the file: the card shows 'Your bank data', this month's out / in / net, runway, subscriptions, net worth from the file",
                  not c["hidden"] and c["state"] == "ok" and c["pill"] == "Your bank data" and kv.get("Out in 2026-11") == MI.money(d["this_month"]["out"]) and kv.get("Net worth") == "$9,000"
                  and kv.get("Runway on savings") == f"{d['runway']['months']:.1f} months", c)
            check("b. categories biggest first (Rent first), the subscriptions with a next date, the leaks", c["cats"][:1] == ["Rent"] and any("Next about 2026-11-28" in s for s in c["subs"]) and c["leaks"] >= 1, (c["cats"], c["subs"][:3]))
            check("b. no merchant name on the page, no console error, nothing fetched off the site", not re.search(r"NETFLIX|Netflix|SPOTIFY|DOORDASH|KROGER", c["text"]) and not errs and not off, (errs[:2], off[:2]))
            check("b. 390 x 844: no sideways scroll", AK.no_sideways(p))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, "oikos", f"?today={T.TODAY}&q=low")
            p.wait_for_function("window.OIKOS_HOUSEHOLD && window.OIKOS_HOUSEHOLD.ready()", timeout=60000)
            check("b. 375 x 667, LITE, reduced motion: no sideways scroll, every tap >= 44 px, no error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin0)
            AK.open_app(p, origin0, "oikos", f"?today={T.TODAY}")
            p.wait_for_function("window.OIKOS_HOUSEHOLD && window.OIKOS_HOUSEHOLD.ready()", timeout=60000)
            c = p.evaluate(CARD)
            check("c. without the file (the public site): 'Not connected' and how to connect; Oikos still shows its DEMO; no console error",
                  not c["hidden"] and c["state"] == "off" and c["pill"] == "Not connected" and "tools/bat/RUN_MONEY.bat" in c["lines"] and p.evaluate("() => !document.querySelector('#demo').hidden") and not errs, (c, errs[:2]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, "oikos", f"?demo=1&today={T.TODAY}")
            p.wait_for_function("window.OIKOS_HOUSEHOLD && window.OIKOS_HOUSEHOLD.ready()", timeout=60000)
            check("c. ?demo=1 never reads your household file", not any("household.json" in u for u in seen) and p.evaluate(CARD)["state"] == "off", [u for u in seen if "money" in u])
            ctx.close()
    finally:
        srv.shutdown()
        srv0.shutdown()


if __name__ == "__main__":
    test_static()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
