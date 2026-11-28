"""day-sharecard 2026-11-27 (owner: "when we have good days I want a sick image to post on insta that shows daily PNL").
tools/web_public/nq/share.html + share.js (page) + sharecard.js (pure model + canvas drawing) + share.css + sharebtn.js (the green-day button).
  a. static: read only (no innerHTML / storage / sends beyond the site's own feed), OLYMPUS NIGHT, >= 12 px, button wired on home + accounts
  b. node: cardModel / textOf on account names carrying ids ("MFFU 50K Eval 1234567", "...6016", "#99887766"): no 5+ digit run, firm id or
     e-mail reaches the drawn text; hide $ -> no "$"; hide balances -> no balance; a BACKTEST day says so; sharebtn.todayUsd (today only)
  c. browser 390x844 + 1440x900: today from a green PC post (+$660, the live pipeline) -> canvas 1080x1350, story 1080x1920, a real PNG,
     3 styles draw, Download gives a .png; a past replay day (2026-11-20, ATLAS +$1,659 backtest) stamped BACKTEST; the green-day button on
     accounts.html (+$660 today) and none on a red day; taps >= 44, no sideways scroll, nothing off the site, no console error
Run: python -X utf8 -m tests.test_sharecard [--shots]
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402
from tests import test_nq_live as NQL  # noqa: E402

check = AK.check
NQ = os.path.join(ROOT, "tools", "web_public", "nq")
SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-27", "day-sharecard", "shots")
ET = ZoneInfo("America/New_York")
BAD = re.compile(r"\b\d{5,}\b|\b[A-Z]{2,8}[-_]?\d{5,}|#\d{3,}|@|\.\.\.\d")   # ids, not plan names ("MFFU 50K Eval" is fine)


def green_post(t, today_usd=660.0):
    """the real 2026-11-22 post moved to t, with a closed +$660 LIT long on the 50K today"""
    p = NQL.retime(NQL.real(), t)
    e = t - 5400
    et = dt.datetime.fromtimestamp(t, ZoneInfo("America/New_York"))
    if et.hour >= 18:                     # day-sharefix: an evening clock -> the trade sits in that ET day's session (15:00 ET)
        e = int(et.replace(hour=15, minute=0, second=0, microsecond=0).timestamp())
    p["at"]["a"] += [{"id": "mffu50k_eval", "l4": "6016", "tr": [[e, e + 1800, 1, 3, 25650.0, 25630.0, 25760.0, "TARGET", today_usd, 3.3]]}]
    p["accounts"][0]["pnl"]["today"] = today_usd
    p["accounts"][0]["pnl"]["week"] = today_usd + 300
    return p


def main():
    js = AK.read(os.path.join(NQ, "sharecard.js")) + AK.read(os.path.join(NQ, "share.js")) + AK.read(os.path.join(NQ, "sharebtn.js"))
    css = AK.read(os.path.join(NQ, "share.css"))
    check("a. read only: no innerHTML / storage / POST; no outside URL", not re.search(r"innerHTML|localStorage|sessionStorage|sendBeacon|method:\s*'POST'|https?://", js))
    sizes = [float(x) for x in re.findall(r"font-size:\s*([\d.]+)px", css)]
    check("a. OLYMPUS NIGHT + >= 12 px + 44 px controls", all(c in css for c in ("#9d59ee", "#f1c14b", "#77db89")) and min(sizes) >= 12 and "min-height: 44px" in css, sizes)
    check("a. the green-day button script is on the NQ home + accounts", all("sharebtn.js" in AK.read(os.path.join(NQ, f)) for f in ("index.html", "accounts.html")))
    # b. node
    drv = r"""
import * as S from '%s';
import vm from 'node:vm';
import fs from 'node:fs';
const src = { day: '2026-11-24', total: 1260, source: 'live', week: 1560,
  accounts: [{ name: 'MFFU 50K Eval 1234567', usd: 660, balance: 2104 }, { name: 'Zlarior 25K #2 ...6016', usd: 600, balance: 99887766 }, { name: 'ATLAS a@b.com', usd: -40 }],
  trades: [{ name: 'Zlarior 50K', side: 'LONG', usd: 660, r: 3.3, t: 1, xt: 2 }, { name: 'x', side: 'SHORT', usd: 600, r: 2.1, t: 3, xt: 4 }, { name: 'y', usd: -40, r: -1, t: 5 }],
  streak: { kind: 'W', n: 2 }, bars: [] };
const M = S.cardModel(src);
const out = { M, all: S.textOf(M, {}), noUsd: S.textOf(M, { hideUsd: true }), noBal: S.textOf(M, { hideBalances: true }),
  bt: S.textOf(S.cardModel({ ...src, source: 'backtest' }), {}), names: ['Zlarior 50K', 'MFFU 50K Eval 1234567', 'Rapid EOD 25K ...0071', '#99887766'].map(S.cleanName) };
const ctx = { window: {}, Intl, Date, Math };
vm.createContext(ctx); vm.runInContext(fs.readFileSync('%s', 'utf8'), ctx);
const now = Date.now() / 1000;
out.btn = [ctx.window.SHAREBTN.todayUsd({ t: now - 300, accounts: [{ name: 'Zlarior 50K', pnl: { today: 660 } }, { name: 'BLITZ paper', pnl: { today: 999 } }] }, now),
  ctx.window.SHAREBTN.todayUsd({ t: now - 3 * 86400, accounts: [{ name: 'Zlarior 50K', pnl: { today: 660 } }] }, now),
  ctx.window.SHAREBTN.todayUsd({ t: now - 300, day_pnl: -80 }, now)];
console.log(JSON.stringify(out));
""" % ("file://" + os.path.join(NQ, "sharecard.js"), os.path.join(NQ, "sharebtn.js"))
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "d.mjs"); open(p, "w").write(drv)
        r = subprocess.run(["node", p], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        check("b. node ran", False, r.stderr[-400:]); o = None
    if o:
        allt = " | ".join(o["all"])
        check("b. no account number / firm id / e-mail reaches the card text", not BAD.search(allt) and "99887766" not in allt, allt)
        check("b. names only: 'MFFU 50K Eval 1234567' -> 'MFFU 50K Eval', '#99887766' -> 'Account'", o["names"] == ["Zlarior 50K", "MFFU 50K Eval", "Rapid EOD 25K", "Account"], o["names"])
        check("b. the card: +$1,260, 3 trades ✅✅❌, +4.4R, '2 wins in a row', week +$1,560, accounts sorted by $ (a −$40 kept)", "+$1,260" in o["all"] and "3 trades" in o["all"]
              and "✅✅❌" in o["all"] and "+4.4R" in o["all"] and "2 wins in a row" in o["all"] and "week +$1,560" in o["all"], o["all"])
        check("b. hide $: no '$' anywhere (R only)", not any("$" in x for x in o["noUsd"]) and "+4.4R" in o["noUsd"], o["noUsd"])
        check("b. hide balances: no balance line", not any(x.startswith("balance") for x in o["noBal"]) and any(x.startswith("balance") for x in o["all"]))
        check("b. a past replay day is stamped BACKTEST", "BACKTEST · not a live result" in o["bt"])
        check("b. sharebtn.todayUsd: +$660 today (BLITZ never), a 3-day-old post -> none, a red day -> -80", o["btn"] == [660, None, -80], o["btn"])
    # c. browser
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("  (playwright not installed: browser part skipped)")
        return AK.finish()
    shots = "--shots" in sys.argv
    now = int(time.time())
    at = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    post = green_post(now - 120)
    srv, origin = AK.serve({"/home.json": None})
    read = """() => { const c = document.getElementById('card'); const g = c.getContext('2d'); const d = g.getImageData(0, 0, c.width, c.height).data; let lit = 0;
        for (let i = 0; i < d.length; i += 4 * 997) if (d[i] + d[i + 1] + d[i + 2] > 60) lit++;
        return { w: c.width, h: c.height, lit, label: c.getAttribute('aria-label'), png: c.toDataURL('image/png').slice(0, 22), state: document.getElementById('app').dataset.state,
          sum: document.getElementById('sum').textContent }; }"""
    try:
        with AK.browser() as br:
            for w, h in ((390, 844), (1440, 900)):
                ctx, p, errs, seen, off = AK.page(br, origin, w=w, h=h, mock={"json?poll=1": NQL.ndjson(post)})
                p.goto(f"{origin}/nq/share.html?at={at}")
                p.wait_for_function("window.NQ_SHARE && window.NQ_SHARE.ready() && document.getElementById('app').dataset.state !== 'loading'", timeout=60000)
                p.wait_for_timeout(500)
                o = p.evaluate(read)
                check(f"c. {w}: today from the PC post: card 1080x1350, a real PNG, drawn (not blank), +$660, names only",
                      o["w"] == 1080 and o["h"] == 1350 and o["png"].startswith("data:image/png;base64") and o["lit"] > 50 and "+$660" in (o["label"] or "")
                      and not BAD.search(o["label"] or ""), o)
                p.click("#size button[data-v='story']")
                o2 = p.evaluate(read)
                check(f"c. {w}: Story = 1080x1920", o2["w"] == 1080 and o2["h"] == 1920, (o2["w"], o2["h"]))
                for st in ("clean", "vault", "neon"):
                    p.click(f"#style button[data-v='{st}']")
                    if shots and w == 390:
                        os.makedirs(SHOTS, exist_ok=True)
                        p.evaluate("() => document.getElementById('card').toDataURL('image/png')")
                        b64 = p.evaluate("() => document.getElementById('card').toDataURL('image/png').split(',')[1]")
                        import base64
                        open(os.path.join(SHOTS, f"card-story-{st}.png"), "wb").write(base64.b64decode(b64))
                o3 = p.evaluate(read)
                check(f"c. {w}: 3 styles draw (neon last)", o3["lit"] > 50 and o3["h"] == 1920)
                p.click("#size button[data-v='post']")
                p.check("#hideUsd")
                o4 = p.evaluate(read)
                check(f"c. {w}: Hide $ -> no '$' in the card", "$" not in (o4["label"] or ""), o4["label"])
                p.uncheck("#hideUsd")
                with p.expect_download(timeout=15000) as dl:
                    p.click("#dl")
                name = dl.value.suggested_filename
                check(f"c. {w}: Download gives the PNG ({name})", name.endswith(".png") and "olympus-nq-" in name, name)
                if shots and w == 390:
                    for st in ("neon",):
                        b64 = p.evaluate("() => document.getElementById('card').toDataURL('image/png').split(',')[1]")
                        import base64
                        open(os.path.join(SHOTS, "card-post-neon.png"), "wb").write(base64.b64decode(b64))
                    p.screenshot(path=os.path.join(SHOTS, "share-page-390.png"), full_page=True)
                # a past day (replay = backtest)
                p.select_option("#day", "2026-11-20")
                p.wait_for_function("document.getElementById('sum').textContent.startsWith('Backtest')", timeout=20000)
                o5 = p.evaluate(read)
                if w == 390:
                    ny = ZoneInfo("America/New_York")
                    ev, noon = (int(dt.datetime(2026, 11, 27, h, m, tzinfo=ny).timestamp()) for h, m in ((19, 30), (12, 0)))
                    cn = p.evaluate(f"[window.NQ_SHARE.cardNow({ev}), window.NQ_SHARE.cardNow({noon})]")
                    check("c. the card's day is the New York day: 19:30 ET reads the day as of 17:59 ET (the CME day has rolled), 12:00 ET reads now",
                          cn == [int(dt.datetime(2026, 11, 27, 17, 59, tzinfo=ny).timestamp()), noon], cn)
                if shots and w == 390:
                    import base64
                    b64 = p.evaluate("() => document.getElementById('card').toDataURL('image/png').split(',')[1]")
                    open(os.path.join(SHOTS, "card-replay-backtest.png"), "wb").write(base64.b64decode(b64))
                check(f"c. {w}: a past replay day (2026-11-20, ATLAS +$1,659) is stamped BACKTEST", "BACKTEST" in (o5["label"] or "") and "+$1,659" in (o5["label"] or ""), o5["label"])
                check(f"c. {w}: share page taps >= 44, no sideways scroll, nothing off the site, no console error",
                      not AK.taps(p) and AK.no_sideways(p) and not off and not errs, (AK.taps(p)[:4], off[:3], errs[:3]))
                ctx.close()
            # the green-day button on accounts.html (+$660 today) and none on a red day
            for name, pst, want in (("green", post, True), ("red", green_post(now - 120, -150.0), False)):
                ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844, mock={"json?poll=1": NQL.ndjson(pst)})
                p.goto(f"{origin}/nq/accounts.html")
                if want:
                    p.wait_for_selector("#instaBtn", timeout=40000)
                else:
                    p.wait_for_timeout(6000)
                b = p.evaluate("() => { const b = document.getElementById('instaBtn'); return b ? { text: b.textContent, href: b.getAttribute('href'), h: b.getBoundingClientRect().height, vis: !b.hidden } : null; }")
                if want:
                    check("c. accounts.html on a green day: '📸 Make Insta card · +$660 today' -> share.html (>= 44 px)", b and b["vis"] and "+$660" in b["text"]
                          and b["href"] == "share.html" and b["h"] >= 44, b)
                else:
                    check("c. accounts.html on a red day: no automatic button", not b or not b["vis"], b)
                ctx.close()
    finally:
        srv.shutdown()
    return AK.finish()


if __name__ == "__main__":
    sys.exit(main())
