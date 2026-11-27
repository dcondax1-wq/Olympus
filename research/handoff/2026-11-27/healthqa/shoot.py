"""day-healthqa shots: nq/accounts.html with an open trade, the hands-steps chip and a keep-alive fill (the test's rich post).
    python -X utf8 research/handoff/2026-11-27/healthqa/shoot.py"""
import datetime as dt, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, ROOT)
from tests import test_nq_accounts_night as N  # noqa: E402
TA, AK = N.TA, N.AK
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")
at = dt.datetime.fromtimestamp(TA.NOW, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
srv, origin = AK.serve({"/home.json": None})
try:
    with AK.browser() as br:
        for w, h in ((390, 844), (1440, 900)):
            ctx, p, errs, seen, off = AK.page(br, origin, w=w, h=h, mock={"json?poll=1": TA.ndjson(*N.post_rich(True))})
            p.goto(f"{origin}/nq/accounts.html?at={at}")
            p.wait_for_function("window.NQ_ACCOUNTS && window.NQ_ACCOUNTS.ready()", timeout=60000)
            p.wait_for_timeout(1400)
            p.screenshot(path=os.path.join(OUT, f"accounts-{w}.png"))
            if w == 390:
                p.evaluate("document.getElementById('acct-atlas').querySelector('.ac-k7').scrollIntoView({block: 'center'})")
                p.wait_for_timeout(400)
                p.screenshot(path=os.path.join(OUT, "accounts-390-k7.png"))
            print(w, errs[:3])
            ctx.close()
finally:
    srv.shutdown()
