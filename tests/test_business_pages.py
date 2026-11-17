"""The Business side pages (2026-11-17): Security (a tick list that never touches a password), Work week (the schedule around
LIT's hours, a calendar file made on the phone), and the 4 doors on the Business page (My Accounts, Taxes, Security, Work week).

  a. offline: no password / text input anywhere, one storage key in try/catch, no fetch / outside request / innerHTML, every
     checklist item there (2-step login in the owner's order: email first), the schedule's blocks sit around LIT's hours
     (STRATEGY.md: entries 02:00-15:30 ET, flat 15:55, MFFU flat 16:10), the doors link the 4 pages, Planner links the week
  b. Chromium 390 x 844 (skipped with --static; run under flock -w 2400 /tmp/olympus_browser.lock): Security ticks stay after a
     reload and count up; Work week shows today's blocks and a valid .ics (weekly repeats in New York time + the tax dates);
     taps >= 44 px, no sideways scroll, nothing fetched off the site, no console error; the Business doors show

    python -X utf8 -m tests.test_business_pages [--static]
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402

check = AK.check
BIZ = os.path.join(ROOT, "tools", "web_public", "business")
BAD_JS = r"\.innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|new Function|fetch\(|XMLHttpRequest|WebSocket|sendBeacon|document\.cookie|https?://"


def part_a():
    sec, tk = AK.read(os.path.join(BIZ, "security.html")), AK.read(os.path.join(BIZ, "ticks.js"))
    inputs = re.findall(r"<input\b[^>]*>", sec)
    check("a. Security: the only inputs are checkboxes (no password / text field, no form, no textarea)",
          inputs and all('type="checkbox"' in i for i in inputs) and not re.search(r"<form|<textarea|type=\"(password|text|email)\"", sec), inputs[:3])
    check("a. ticks.js: one localStorage key (business.security.v1 from the tag), every read and write in try/catch, no fetch / markup / outside address",
          'data-key="business.security.v1"' in sec and tk.count("localStorage.") == 2 and tk.count("try {") >= 2 and not re.search(BAD_JS, tk) and "textContent" in tk
          and not re.search(r"\.value\b", tk))
    keys = re.findall(r'data-k="([^"]+)"', sec)
    check(f"a. Security: {len(keys)} unique tick keys", len(keys) == len(set(keys)) and len(keys) >= 14, keys)
    low = sec.lower()
    items = ["bitwarden", "apple passwords", "one long password", "authenticator app", "recovery codes", "sim swap", "share your screen", "claude never needs your passwords", "if you think you were hacked"]
    check("a. Security: every item (manager, unique passwords, 2-step with an app, offline codes, carrier PIN, screen, Claude never needs passwords, if hacked)",
          all(w in low for w in items), [w for w in items if w not in low])
    order = [sec.index(f'data-k="2fa.{k}"') for k in ("email", "bank", "mffu", "broker", "kalshi", "github", "apple")]
    check("a. Security: 2-step login in order: email first, then bank, MFFU, Tradovate/Rithmic/NinjaTrader, Kalshi, GitHub, Apple ID",
          order == sorted(order) and "Tradovate / Rithmic / NinjaTrader" in sec)

    sh, sj = AK.read(os.path.join(BIZ, "schedule.html")), AK.read(os.path.join(BIZ, "schedule.js"))
    check("a. Work week: read only (no storage, no fetch, no markup from data, no outside address)", not re.search(BAD_JS + r"|localStorage|sessionStorage|indexedDB", sj) and "textContent" in sj)
    blocks = re.findall(r"\{ days: (\[[^\]]*\]|WK), start: '(\d\d:\d\d)', end: '(\d\d:\d\d)', kind: '(\w+)', what: '([^']+)'", sj)
    by = {b[4]: b for b in blocks}
    check("a. Work week: the checks before the open, at lunch, after the close (weekdays), the Friday review, the payout check, side-work blocks",
          all(w in by for w in ("Before the open", "Lunch look", "After the close", "Friday weekly review", "Payout check")) and sum(b[3] == "side" for b in blocks) >= 3, list(by))
    check("a. Work week: built on LIT's hours: the close check starts after MFFU's 16:10 flat, the morning one before the 09:30 open, the review after the close",
          by["After the close"][1] >= "16:10" and by["Before the open"][1] < "09:30" and by["Friday weekly review"][1] >= "16:10" and "02:00 to 15:30" in sh and "15:55" in sh and "16:10" in sh)
    days = lambda b: {1, 2, 3, 4, 5} if b[0] == "WK" else {int(x) for x in re.findall(r"\d", b[0])}
    side = [b for b in blocks if b[3] == "side"]
    check("a. Work week: side work never overlaps a bot check", side and not any(days(s) & days(o) and s[1] < o[2] and o[1] < s[2] for s in side for o in blocks if o[3] != "side"))
    check("a. Work week: links the tax page, the payout rules say funded only and after the close, tax dates every quarter, estimates labelled",
          'href="taxes.html"' in sh and "funded" in sh and "after the close" in sh and sj.count("-15'") >= 4 and "estimate" in sh.lower() and "Not tax advice" in sh)

    idx = AK.read(os.path.join(BIZ, "index.html"))
    check("a. Business: the 4 doors (My Accounts, Taxes, Security, Work week)",
          all(f'href="{h}"' in idx for h in ("accounts.html", "taxes.html", "security.html", "schedule.html")) and all(f">{t} &rarr;</h2>" in idx for t in ("My Accounts", "Taxes", "Security", "Work week")))
    pl = AK.read(os.path.join(ROOT, "tools", "web_public", "planner", "index.html"))
    check("a. Planner links the work week", 'href="../business/schedule.html"' in pl)
    for name in ("security.html", "schedule.html"):
        h = AK.read(os.path.join(BIZ, name))
        check(f"a. {name}: AGORA look, viewport-fit=cover, one h1, a polite status line, back to Business",
              'data-theme="agora"' in h and "viewport-fit=cover" in h and h.count("<h1") == 1 and 'aria-live="polite"' in h and 'href="./"' in h and "../olympus/agora.css" in h)


def part_b():
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("  (playwright not installed: browser part skipped)")
        return
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844)
            p.goto(f"{origin}/business/security.html")
            p.wait_for_function("window.TICKS && window.TICKS.ready()", timeout=60000)
            p.locator('input[data-k="2fa.email"]').dispatch_event("click")
            p.locator('input[data-k="pm.install"]').dispatch_event("click")
            p.reload()
            p.wait_for_function("window.TICKS && window.TICKS.ready()", timeout=60000)
            st = p.inner_text("#status")
            check("b. Security: 2 ticks stay after a reload, the 2-step card says 1 of 7, the status counts them",
                  p.locator('input[data-k="2fa.email"]').is_checked() and p.locator('input[data-k="pm.install"]').is_checked()
                  and p.inner_text('[data-count="s3"]') == "1 of 7" and st.startswith("2 of "), st)
            check("b. Security at 390 px: taps >= 44 px, no sideways scroll, nothing off the site, no console error",
                  not AK.taps(p) and AK.no_sideways(p) and not off and not errs, (AK.taps(p)[:4], off[:3], errs[:3]))
            AK.shot(p, "business-security-390")

            p.goto(f"{origin}/business/schedule.html?at=2026-11-20T15:00:00Z")          # Friday 10:00 ET
            p.wait_for_function("window.SCHEDULE && window.SCHEDULE.ready()", timeout=60000)
            o = p.evaluate("""() => { const t = SCHEDULE.ics(new Date('2026-11-17T00:00:00Z'));
                return { h: document.getElementById('todayH').textContent, n: document.querySelectorAll('#today .slot').length, st: document.getElementById('status').textContent,
                         ev: (t.match(/BEGIN:VEVENT/g) || []).length, end: (t.match(/END:VEVENT/g) || []).length, rr: (t.match(/RRULE:FREQ=WEEKLY/g) || []).length,
                         tax: (t.match(/Estimated tax due/g) || []).length, blocks: SCHEDULE.blocks.length, crlf: t.indexOf('\\r\\n') > 0 && !/[^\\r]\\n/.test(t),
                         ny: /DTSTART;TZID=America\\/New_York:20261120T163000/.test(t), days: document.querySelectorAll('#week details').length,
                         open: [...document.querySelectorAll('#week details')].filter((d) => d.open).map((d) => d.querySelector('.nm').textContent),
                         tp: document.getElementById('taxPill').textContent }; }""")
            check("b. Work week (Fri 10:00 ET): today = Friday with 5 blocks, the status names the next one, 7 days with Friday open, tax pill 'next in 56 days'",
                  o["h"] == "Today, Friday" and o["n"] == 5 and o["st"].startswith("Next: Lunch look at 12:00 ET") and o["days"] == 7 and o["open"] == ["Friday"]
                  and o["tp"] == "next in 56 days", o)
            check("b. the calendar file: one weekly event per block + the tax dates, CRLF lines, New York time (Friday review 16:30)",
                  o["ev"] == o["end"] == o["blocks"] + 6 and o["rr"] == o["blocks"] and o["tax"] == 6 and o["crlf"] and o["ny"], o)
            check("b. Work week at 390 px: taps >= 44 px, no sideways scroll, nothing off the site, no console error",
                  not AK.taps(p) and AK.no_sideways(p) and not off and not errs, (AK.taps(p)[:4], off[:3], errs[:3]))
            AK.shot(p, "business-schedule-390")

            p.goto(f"{origin}/business/")
            p.wait_for_function("window.BUSINESS && window.BUSINESS.ready()", timeout=120000)
            d = p.locator(".doors a")
            check("b. Business: the 4 doors show two a row, no sideways scroll at 390 px",
                  d.count() == 4 and abs(d.nth(0).bounding_box()["y"] - d.nth(1).bounding_box()["y"]) < 2 and AK.no_sideways(p), d.count())
            ctx.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    if "--static" not in sys.argv:
        part_b()
    return AK.finish()


if __name__ == "__main__":
    sys.exit(main())
