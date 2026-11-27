"""Shots for night-nq-accounts: python -X utf8 research/handoff/2026-11-27/night-nq-accounts/shoot.py <before|after>
Same mocked PC post as tests/test_accounts_screen.py (5 accounts); 390 x 844 (viewport + full page) and 1440 x 900."""
import datetime as dt, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, ROOT)
from tests import test_accounts_screen as T  # noqa: E402
AK = T.AK
tag = sys.argv[1] if len(sys.argv) > 1 else "after"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")
os.makedirs(OUT, exist_ok=True)
at = dt.datetime.fromtimestamp(T.NOW, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
srv, origin = AK.serve({"/home.json": None})
try:
    with AK.browser() as br:
        core, exts = T.post()
        if tag == "after":                    # the fields a real PC post carries that the old test post lacks: dll / dll_used, eq points, the buy light
            for a in core["accounts"]:
                a["eval"].update(dll=1000.0 if a["eval"]["start_balance"] == 50000 else 500.0, dll_used=0.0)
            core["accounts"][0]["eval"]["dll_used"] = 180.0
            eq = {"mffu50k_eval": [0, -310, -520, -410, -690, -822, -786], "atlas": [0, 120, 260, 190, 401], "b25k_2": [0, 12, 19, 24], "rapid": [0, -5]}
            for r in exts[0]["x"]["mf"]["a"]:
                if r["id"] in eq: r["eq"] = eq[r["id"]]
            if "--bg" in sys.argv:
                exts[0]["x"]["bg"] = {"s": "OK", "l": "Buy gate: OK to buy new evals · LIT last 40 trades +30.4R · payouts-minus-fees rule OK (display only)", "sh": "", "t": T.NOW}
        for w, h in ((390, 844), (1440, 900)):
            ctx, p, errs, seen, off = AK.page(br, origin, w=w, h=h, mock={"json?poll=1": T.ndjson(core, exts)})
            p.goto(f"{origin}/nq/accounts.html?at={at}")
            p.wait_for_function("window.NQ_ACCOUNTS && window.NQ_ACCOUNTS.ready()", timeout=60000)
            p.wait_for_timeout(1200)
            p.evaluate("document.getAnimations().forEach((a) => { try { a.finish(); } catch (e) {} })")
            p.screenshot(path=os.path.join(OUT, f"{tag}-accounts-{w}.png"), full_page=False)
            p.screenshot(path=os.path.join(OUT, f"{tag}-accounts-{w}-full.png"), full_page=True)
            if tag == "after" and w == 390:
                try:
                    p.click("#acct-atlas .ac-more", timeout=3000); p.wait_for_timeout(600)
                    p.evaluate("document.getElementById('acct-atlas').scrollIntoView({block: 'start'})")
                    p.screenshot(path=os.path.join(OUT, "after-accounts-390-expanded.png"), full_page=False)
                except Exception as e:  # noqa: BLE001
                    print("expand shot skipped:", e)
            print(tag, w, "errors:", errs[:3], "offsite:", off[:3])
            ctx.close()
        for w, h in ((390, 844), (1440, 900)):
            ctx, p, errs, seen, off = AK.page(br, origin, w=w, h=h, mock={"json?poll=1": T.ndjson(core, exts)})
            p.goto(f"{origin}/nq/index.html?at={at}")
            p.wait_for_timeout(3500)
            p.evaluate("document.getAnimations().forEach((a) => { try { a.finish(); } catch (e) {} })")
            g = p.query_selector("#goals") or p.query_selector(".nq-goals")
            if g:
                g.scroll_into_view_if_needed()
            p.screenshot(path=os.path.join(OUT, f"{tag}-nq-goals-{w}.png"), full_page=False)
            ctx.close()
finally:
    srv.shutdown()
