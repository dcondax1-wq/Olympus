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


# the PC feed of 2026-11-18 (trimmed): Zlarior 50K eval, the NEW Builder 25K eval b25k_2 and ATLAS's FUNDED 25K
FEED = {"kind": "le-live", "t": 1794965360, "reporter": {"t": 1794965404},
        "board": {"t": 1794965360, "data_t": 1794965360,
                  "lit": {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "balance": 49192.78, "floor": 48168.2, "room": 1024.58, "mll": 2000.0,
                          "to_target": 3807.22, "target_balance": 53000.0, "profit": -807.22, "today_pnl": 0.0, "status": "open", "session": 23, "dll": 1000.0, "dll_used": 0.0},
                  "atlas": {"id": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K funded", "balance": 25000.0, "floor": 24000.0, "room": 1000.0, "mll": 1000.0,
                            "to_target": 1850.0, "profit": 0.0, "today_pnl": 0.0, "status": "funded", "session": 2, "dll": 600.0}},
        "accounts": [{"id": "mffu50k_eval", "name": "MFFU 50K Eval", "plan": "Builder 50K", "kind": "eval", "source": "pc", "conn": {"t": 1794965360},
                      "eval": {"start_balance": 50000.0, "balance": 49192.78, "profit": -807.22, "to_target": 3807.22, "floor": 48168.2, "room": 1024.58, "dll": 1000.0,
                               "dll_used": 0.0, "today": 0.0, "session": 23, "status": "open"}},
                     {"id": "b25k_2", "name": "Zlarior Builder 25K #2", "plan": "Builder 25K", "kind": "eval", "source": "pc", "conn": {"t": 1794965360},
                      "eval": {"start_balance": 25000.0, "balance": 25000.0, "profit": 0.0, "to_target": 1500.0, "floor": 24000.0, "room": 1000.0, "dll": 600.0,
                               "dll_used": 0.0, "today": 0.0, "session": 1, "status": "open"}}],
        "brd": {"t": 1794965408, "ac": [["zlarior", "eval", 49193, 1025, 3807, 0], ["atlas", "PASSED", 26946, None, 0, 1]], "ev": [], "on": 0},
        "mf": {"t": 1794965360, "a": [{"id": "mffu50k_eval", "sd": "2026-10-19", "l4": "6016", "td": 13, "bd": ["2026-10-20", 640], "wd": ["2026-11-16", -129],
                                       "eq": [-678, -807], "n": 14, "w": 5},
                                      {"id": "b25k_2", "sd": "2026-11-18"},
                                      {"id": "atlas", "sd": "2026-11-17", "f": {"cp": 0, "bd": 0, "cd": 0, "pn": 0, "mr": 0}}]}}


def part_mffu():
    """2026-11-18: the MFFU-style account page + the account matching fix (by PC id / Name, never plan size)."""
    import json
    import subprocess
    h, js, mm = (AK.read(os.path.join(BIZ, f)) for f in ("mffu.html", "mffu.js", "mffumodel.js"))
    check("m. mffu.html: AGORA look, one h1, polite status, back to Business, the PC feed + model + coach scripts",
          'data-theme="agora"' in h and "viewport-fit=cover" in h and h.count("<h1") == 1 and 'aria-live="polite"' in h and 'href="./"' in h
          and all(x in h for x in ("../pc_feed.js", "payoutcoach.js", "mffumodel.js", "mffu.js")))
    check("m. mffu.js / mffumodel.js: textContent only, no markup from data, no outside address, read only (GET only)",
          not re.search(r"\.innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|new Function|https?://|method:", js + mm) and "textContent" in js)
    idx = AK.read(os.path.join(BIZ, "index.html"))
    bh = AK.read(os.path.join(ROOT, "tools", "web_public", "board", "index.html"))
    check("m. linked: a top card 'My accounts (MFFU view)' on Business (before the doors), the Board page, My Accounts",
          'href="mffu.html"' in idx and idx.index('href="mffu.html"') < idx.index('class="doors"') and "My accounts (MFFU view)" in idx
          and 'href="../business/mffu.html"' in bh and 'href="mffu.html"' in AK.read(os.path.join(BIZ, "accounts.html")))
    acc = AK.read(os.path.join(BIZ, "accounts.js"))
    check("m. accounts.js no longer matches live numbers by plan size (25000), it uses MFFU_MODEL.match", "25000" not in acc and "MFFU_MODEL" in acc
          and "mffumodel.js" in AK.read(os.path.join(BIZ, "accounts.html")))
    plan = json.loads(AK.read(os.path.join(BIZ, "accounts.json")))
    keys = {a["key"]: a for a in plan["accounts"]}
    check("m. accounts.json: each live account has its PC ids (zlarior mffu50k_eval/lit, atlas, fresh25 b25k_2)",
          "mffu50k_eval" in keys["zlarior"]["pc"] and "atlas" in keys["atlas"]["pc"] and keys["fresh25"]["pc"] == ["b25k_2"])
    old = {**plan, "accounts": [{k: v for k, v in a.items() if k != "pc"} for a in plan["accounts"]]}
    W = os.path.join(ROOT, "tools", "web_public")
    script = f"""
      const M = require({json.dumps(os.path.join(BIZ, "mffumodel.js"))}), C = require({json.dumps(os.path.join(BIZ, "payoutcoach.js"))});
      const B = require({json.dumps(os.path.join(W, "board", "boardmodel.js"))});
      const feed = {json.dumps(FEED)}, plan = {json.dumps(plan)}, old = {json.dumps(old)}, now = 1794965360 + 120;
      const res = {{}};
      for (const [k, p] of [['pc', plan], ['old', old]]) {{
        const cs = M.cards({{ lite: feed, plan: p, coach: C, today: '2026-11-18' }}, now);
        res[k] = cs.map((c) => ({{ key: c.key, name: c.name, l4: c.last4, st: c.status, plan: c.plan, bal: c.balance.v, pnl: c.pnl.v, floor: c.floor.v, room: c.room.v,
          tgt: c.target && c.target.left, prog: c.target && c.target.progress, sd: c.start_date.v, td: c.days.v, min: c.days.min, n: c.trades.n, wp: c.trades.win_pct,
          best: c.trades.best && c.trades.best.v, eq: c.equity.pts.length, dll: c.dll.v, dllLeft: c.dll.left, pay: c.payout && c.payout.c && c.payout.c.status,
          payNeed: c.payout && c.payout.c && c.payout.c.need_more, src: c.balance.src, age: c.age_s, planOnly: c.planOnly, cons: c.consistency.rule }}));
        res[k + '_planned'] = M.planned(p).map((a) => a.key);
        res[k + '_board'] = B.pick({{ lite: feed, plan: p }}, now).board.accounts.map((a) => [a.key, a.chip, a.balance, a.locked, a.src, !!a.plan_only]);
      }}
      res.copy = M.cards({{ plan, board: {{ kind: 'olympus-board', t: now - 600, accounts: [{{ key: 'zlarior', balance: 49000, src: 'PC live', src_t: now - 600 }}] }} }}, now)
                   .map((c) => [c.key, c.balance.v, c.balance.src, c.planOnly]);
      console.log('@@' + JSON.stringify(res));"""
    p = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    m = [ln for ln in p.stdout.splitlines() if ln.startswith("@@")]
    r = json.loads(m[-1][2:]) if m else {"error": p.stderr[-500:]}
    for k in ("pc", "old"):
        cs = {c["key"]: c for c in r.get(k) or []}
        z, a, n = cs.get("zlarior", {}), cs.get("atlas", {}), cs.get("fresh25", {})
        check(f"m. ({k}) 3 real accounts, each its own card: Zlarior 50K Evaluation, Zlarior 25K #2 Evaluation, ATLAS Sim Funded; no extra card",
              len(cs) == 3 and z.get("st") == "Evaluation" and n.get("st") == "Evaluation" and a.get("st") == "Sim Funded" and n.get("bal") == 25000
              and a.get("bal") == 25000 and z.get("bal") == 49192.78, list(cs))
        check(f"m. ({k}) Zlarior 50K the MFFU way: ...6016, start Oct 19, P&L -$807.22, floor $48,168.20, $1,024.58 left, $3,807.22 to the target, 13 days, 14 trades 36%",
              z.get("l4") == "6016" and z.get("sd") == "2026-10-19" and z.get("pnl") == -807.22 and z.get("floor") == 48168.2 and z.get("room") == 1024.58
              and z.get("tgt") == 3807.22 and z.get("td") == 13 and z.get("min") == 1 and z.get("n") == 14 and z.get("wp") == 36 and z.get("best") == 640
              and z.get("eq") == 2 and z.get("dll") == 1000 and z.get("dllLeft") == 1000, z)
        check(f"m. ({k}) ATLAS funded: payout coach says not yet ($1,350 more over the $1,100 buffer), 50% rule shown, start Nov 17",
              a.get("pay") == "not_yet" and a.get("payNeed") == 1350 and "50%" in a.get("cons", "") and a.get("sd") == "2026-11-17" and a.get("tgt") is None, a)
        check(f"m. ({k}) every number says where it came from and how old it is", all(c.get("src") == "PC live feed" and c.get("age") == 120 for c in cs.values()), cs)
        check(f"m. ({k}) the plan-only Rapid row is listed as PLAN, not a card", r.get(k + "_planned") == ["rapid1"], r.get(k + "_planned"))
        bd = {x[0]: x for x in r.get(k + "_board") or []}
        check(f"m. ({k}) Board page: ATLAS funded (not locked, not the 25K eval, not the PC's old PASSED row), the 25K #2 its own row, Rapid PLAN",
              bd.get("atlas", [None, None])[1:4] == ["funded", 25000, False] and bd.get("fresh25", [None, None])[1:4] == ["eval", 25000, False]
              and bd.get("zlarior", [None, None])[1:3] == ["eval", 49192.78] and bd.get("rapid1", [None] * 6)[5] is True and "mffu50k_eval" not in bd
              and "b25k_2" not in bd, bd)
    check("m. no PC feed: the Board copy fills the numbers (labelled 'Board copy'), the rest PLAN", r.get("copy", [[None]])[0][:3] == ["zlarior", 49000, "Board copy (PC live)"]
          and any(c[0] == "fresh25" and c[3] for c in r.get("copy") or []), r.get("copy"))


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

            ctx.close()
            import json
            nd = json.dumps({"event": "message", "time": FEED["reporter"]["t"], "message": json.dumps(FEED)}) + "\n"
            ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844, mock={"json?poll=1": nd})
            import datetime as _dt                       # the page's clock 2 min after the post (?at=): the feed reads as live
            p.goto(f"{origin}/business/mffu.html?at=" + _dt.datetime.fromtimestamp(FEED["t"] + 120, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
            p.wait_for_function("window.MFFU_PAGE && window.MFFU_PAGE.ready", timeout=60000)
            o = p.evaluate("""() => ({ n: document.querySelectorAll('#list .mf').length, keys: [...document.querySelectorAll('#list .mf')].map((c) => c.dataset.key),
                st: [...document.querySelectorAll('#list .mf-st')].map((e) => e.textContent), h: [...document.querySelectorAll('#list h2')].map((e) => e.textContent),
                txt: document.getElementById('list').textContent, planned: document.getElementById('plannedBox').hidden, eq: document.querySelectorAll('canvas.eq').length })""")
            check("b. MFFU view (fed the 2026-11-18 PC post): 3 cards Zlarior 50K / ATLAS Sim Funded / Zlarior 25K #2 (the owner's names), ...6016, floor, payout, PLAN list, equity line",
                  o["n"] == 3 and o["st"] == ["Evaluation", "Sim Funded", "Evaluation"] and o["h"] == ["Zlarior 50K", "ATLAS 25K funded", "Zlarior 25K #2"]
                  and "account …6016" in o["txt"] and "$48,168.20" in o["txt"] and "Requestable now $0.00" in o["txt"] and "Live from your PC" in o["txt"]
                  and not o["planned"] and o["eq"] == 1, o)
            check("b. MFFU view at 390 px: taps >= 44 px, no sideways scroll, nothing off the site, no console error",
                  not AK.taps(p) and AK.no_sideways(p) and not off and not errs, (AK.taps(p)[:4], off[:3], errs[:3]))
            AK.shot(p, "business-mffu-390")
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844)
            p.goto(f"{origin}/business/")
            p.wait_for_function("window.BUSINESS && window.BUSINESS.ready()", timeout=120000)
            d = p.locator(".doors a")
            check("b. Business: the doors (4+) show two a row, the MFFU view card on top, no sideways scroll at 390 px",
                  d.count() >= 4 and p.locator("a.mffu-top").count() == 1 and abs(d.nth(0).bounding_box()["y"] - d.nth(1).bounding_box()["y"]) < 2 and AK.no_sideways(p), d.count())
            ctx.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    part_mffu()
    if "--static" not in sys.argv:
        part_b()
    return AK.finish()


if __name__ == "__main__":
    sys.exit(main())
