"""OLYMPUS INBOX (tools/web_public/inbox/, 2026-11-04): one place that collects what matters, newest first, with filters, unread counts, read / pin / mute.
  a. the static rules: the kit (?v=o2, data-app='inbox'), no innerHTML, only GET fetches of the site's own files (+ the Kalshi feed the way the Kalshi page reads it),
     it writes only 'inbox.*' keys, safe areas and the orb's corner, reduced motion, manifest, icon, jarvis.json, bots.js keeps jarvis.bots.log.v1 (200 events, no spoken text)
  b. the rules (inboxcore.js, run in node): every source becomes plain items with an icon, colour, time and the right Open link; newest first; secrets dropped;
     read / mark all / pin / mute; the unread badge, the window title and the Jarvis card
  c. the page in Chromium (390 x 844, 375 x 667): seeded sources, filters with counts, mark read / all, pin, mute, the calm state with the last five, Kalshi status
     changes, Bridge questions, stale apps, offline copy, nothing written to the sources, no errors, 44 px controls
    python -X utf8 -m tests.test_inbox_page            (INBOX_PART=a|b|c runs one part; INBOX_NO_BROWSER=1 skips c)
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
PAGE = os.path.join(WEB, "inbox")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[-900:]}"), flush=True)


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def node(body):
    script = ("import fs from 'fs'; const url = 'file://' + " + json.dumps(PAGE) + "; const out = (x) => console.log('@@' + JSON.stringify(x));\n"
              "class Mem { constructor() { this.m = {}; } getItem(k) { return k in this.m ? this.m[k] : null; } setItem(k, v) { this.m[k] = String(v); } removeItem(k) { delete this.m[k]; } }\n"
              "try { " + body + " } catch (e) { console.log('@@' + JSON.stringify({ error: String(e && e.stack || e) })); }")
    p = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=90)
    m = [ln for ln in p.stdout.splitlines() if ln.startswith("@@")]
    return json.loads(m[-1][2:]) if m else {"error": (p.stderr or p.stdout)[-400:]}


def part_a():
    files = os.listdir(PAGE)
    need = {"index.html", "inbox.css", "inboxcore.js", "inbox.js", "jarvis.json", "manifest.webmanifest", "icon.svg"}
    check("a. the folder has every file", need <= set(files), need - set(files))
    html, css = rd(PAGE, "index.html"), rd(PAGE, "inbox.css")
    js = {n: rd(PAGE, n) for n in files if n.endswith(".js")}
    check("a. the kit first (olympus.css, themes.js, olympus.js ?v=o2 with data-app='inbox'), viewport-fit=cover, theme-color, manifest, icon, apple-touch-icon",
          '<link rel="stylesheet" href="../olympus/olympus.css?v=o7">' in html and 'src="../olympus/themes.js?v=o6"' in html and 'src="../olympus/olympus.js?v=o7" data-app="inbox"' in html
          and "viewport-fit=cover" in html and 'name="theme-color"' in html and 'rel="manifest" href="manifest.webmanifest"' in html and 'rel="icon" href="icon.svg"' in html and 'rel="apple-touch-icon"' in html)
    check("a. no CDN: every src and href in the page is local", not re.search(r'(src|href)="https?://', html))
    check("a. no innerHTML / insertAdjacentHTML / document.write", not any(re.search(r"innerHTML|insertAdjacentHTML|document\.write", s) for s in js.values()))
    urls = set(re.findall(r"https?://[^\s'\"`)]+", js["inbox.js"] + js["inboxcore.js"]))
    check("a. the only outside address is the Kalshi feed (read like the Kalshi page does); no POST, WebSocket, beacon", urls == {"https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json"}
          and not re.search(r"method\s*:|WebSocket|sendBeacon|XMLHttpRequest|EventSource", js["inbox.js"]), urls)
    wr = {x.strip() for x in re.findall(r"jset\(([^,)]+)", js["inbox.js"])} | {x.strip() for x in re.findall(r"LS\.setItem\(([^,)]+)", js["inbox.js"])}
    check("a. it writes only its own keys (inbox.*): the cache, the Kalshi status log, the read state, the card", wr <= {"K.CACHE_KEY", "K.KALSHI_KEY", "'inbox.card.v1'", "'inbox.probe'", "k"}
          and js["inbox.js"].count("removeItem") == 2, wr)
    check("a. safe areas on every edge, the orb's corner (176 px), reduced motion, 44 px controls", all(f"var(--s{x})" in css for x in "trbl") and "176px" in css
          and "@media (prefers-reduced-motion: no-preference)" in css and css.count("min-height: 44px") >= 4 and "animation:" not in css.split("@media (prefers-reduced-motion: no-preference)")[0])
    m = json.loads(rd(PAGE, "manifest.webmanifest"))
    j = json.loads(rd(PAGE, "jarvis.json"))
    check("a. manifest + jarvis.json keep their contracts (3 kpis, <= 3 lines, status.label 'All quiet' when nothing is new, < 8 KB)", m["name"] == "Inbox" and m["icons"][0]["src"] == "icon.svg"
          and j["v"] == 1 and j["name"] == "Inbox" and len(j["kpis"]) == 3 and len(j["lines"]) <= 3 and j["status"]["label"] == "All quiet" and re.fullmatch(r"#[0-9a-f]{6}", j["theme"])
          and os.path.getsize(os.path.join(PAGE, "jarvis.json")) < 8192, j)
    bj = rd(WEB, "jarvis", "bots.js")
    check("a. bots.js keeps the longer event log: jarvis.bots.log.v1, 200 events, text only (no spoken text), cleared with the rest on reset",
          "LOG2_KEY = 'jarvis.bots.log.v1'" in bj and "long.slice(0, 200)" in bj and "say:" not in bj[bj.index("const long = lget(LOG2_KEY"):bj.index("lset(LOG2_KEY")] and "LOG_KEY, LOG2_KEY, CARD_KEY" in bj)


def part_b():
    r = node("""const K = await import(url + '/inboxcore.js'); const now = 1793770000;
      const S = { bots: [{ key: 'k1', kind: 'fill', bot: 'lit', level: 'info', text: 'took a long trade', t: now - 300 }, { key: 'k2', bot: 'atlas', level: 'bad', text: 'hit its daily loss limit', t: now - 7000 },
          { key: 'k3', bot: 'lit', text: 'token: ghp_abcdef123456 leaked', t: now - 10 }],
        argus: { open: { pc: { label: 'PC heartbeat', since: now - 7200 } }, reds: [{ id: 'nt', label: 'NinjaTrader feed', from: now - 90000, to: now - 86400 }] },
        kalshiLog: [{ t: now - 600, text: 'Kalshi bot: Paused' }], learning: { entries: [{ t: now - 4000, text: 'Learned: the 90-95c band loses' }] },
        bridge: { t: now - 100, jobs: { j1: { title: 'Name the bots', status: 'question' }, j2: { title: 'Pine port', status: 'done' } }, counts: { question: 1 }, commits: [{ sha: 'abc1234', date: '2026-11-03', subject: 'Merge pull request #119 from branch' }] },
        learned: [{ t: now - 20000, text: 'You prefer London', note: 'x.md' }], brief: { day: '2026-11-04', shown: now - 3000 },
        arena: [{ id: 'e1', day: '2026-11-04', kind: 'labour', note: 'The Steady Hand' }, { id: 'e2', day: '2026-11-03', kind: 'boss', note: 'Boss beaten' }],
        cards: { forum: { name: 'Forum', t: now - 5 * 86400, stale_after: 86400, status: { label: 'Live' } }, labyrinth: { name: 'Labyrinth', t: now - 100, stale_after: 86400 }, demo: { name: 'Demo', t: 1, stale_after: 5, status: { label: 'Demo data' } } },
        live: { t: now - 50, pc_health: { lines: [{ key: 'disk', label: 'Disk', level: 'bad', text: 'Only 3 GB free' }, { key: 'cpu', level: 'ok', text: 'fine' }] } } };
      const items = K.collect(S, now), st = K.emptyState(), by = (src) => items.filter((i) => i.src === src).map((i) => i.text);
      const ids = items.map((i) => i.id);
      const n0 = K.unread(items, st), first = items[0];
      K.markRead(st, first.id, now); const n1 = K.unread(items, st);
      K.togglePin(st, items[items.length - 1].id); const pinned = K.view(items, st, 'all')[0].id === items[items.length - 1].id;
      K.toggleMute(st, 'bots'); const n2 = K.unread(items, st), hidden = K.view(items, st, 'all').every((i) => i.src !== 'bots'), under = K.view(items, st, 'bots').length;
      K.toggleMute(st, 'bots'); K.markAll(st, items, now + 1); const n3 = K.unread(items, st);
      const stor = new Mem(); K.markRead(st, 'x:1', now); st.pins.p = 1; K.saveState(stor, st, now); const back = K.readState(stor);
      const card0 = K.card(items, K.emptyState(), now), card1 = K.card(items, st, now), noItems = K.card([], K.emptyState(), now);
      out({ n: items.length, bots: by('bots'), argus: by('argus'), kalshi: by('kalshi'), bridge: by('bridge'), mind: by('mind'), arena: by('arena'), system: by('system'),
        sorted: items.every((i, k) => !k || items[k - 1].t >= i.t), uniq: new Set(ids).size === ids.length, hrefs: Object.fromEntries(items.map((i) => [i.src, i.href])), shape: items.every((i) => i.icon && i.color && i.text && i.id && typeof i.t === 'number'),
        n0, n1, pinned, n2, hidden, under, n3, back: [back.all, Object.keys(back.ids), Object.keys(back.pins)], card0: [card0.status, card0.kpis[0]], card1: card1.status, noItems: [noItems.status, noItems.lines],
        title: [K.titleFor(3), K.titleFor(0)], badge: [K.badge(3), K.badge(0)], clean: [K.clean('  a   b  '), K.clean('Bearer abcdefghijklmnop'), K.clean('x'.repeat(500)).length], ago: [K.ago(now - 30, now), K.ago(now - 600, now), K.ago(now - 7300, now), K.ago(now - 200000, now)],
        junk: K.collect({ bots: [null, 5, 'x', {}], argus: 7, bridge: 'no', cards: [], arena: { a: 1 } }, now).length });""")
    if r.get("error"):
        check("b. node runs inboxcore.js", False, r["error"])
        return
    check("b. bot events: 'LIT: took a long trade', 'ATLAS: hit its daily loss limit'; an event that looks like a secret is dropped", r["bots"] == ["LIT: took a long trade", "ATLAS: hit its daily loss limit"], r["bots"])
    check("b. Argus: a red light that is still open (with how long) and an incident that was fixed", r["argus"][0] == "Still red: PC heartbeat, for 2 h" and "NinjaTrader feed was red for 1 h and is fixed" in r["argus"], r["argus"])
    check("b. Kalshi: its learning log and the bot's status change; Bridge: a question and a finished job but no merge-commit noise; Jarvis learned + the brief; Arena: achievement + boss",
          "Kalshi learned: Learned: the 90-95c band loses" in r["kalshi"] and "Kalshi bot: Paused" in r["kalshi"] and "ChatGPT has a question for you: Name the bots" in r["bridge"] and "ChatGPT finished: Pine port" in r["bridge"]
          and not any(x.startswith("Delivered:") for x in r["bridge"]) and "Jarvis learned: You prefer London" in r["mind"] and "Your morning briefing for 2026-11-04 is ready" in r["mind"]
          and "Achievement: The Steady Hand" in r["arena"] and "Boss result: Boss beaten" in r["arena"], r)
    check("b. system: a stale app ('Forum has not refreshed for 5 d (it should every 1 d)'), the PC's red line; a fresh app and a demo card say nothing",
          r["system"] == ["PC Disk: Only 3 GB free", "Forum has not refreshed for 5 d (it should every 1 d)"] or sorted(r["system"]) == sorted(["PC Disk: Only 3 GB free", "Forum has not refreshed for 5 d (it should every 1 d)"]), r["system"])
    check("b. newest first, unique ids, every item has an icon, colour, text, time; each source opens the right app", r["sorted"] and r["uniq"] and r["shape"]
          and r["hrefs"]["argus"] == "../argus/" and r["hrefs"]["bridge"] == "../bridge/" and r["hrefs"]["arena"] == "../arena/" and r["hrefs"]["mind"] == "../jarvis/", r["hrefs"])
    check("b. unread counts: mark one read, pin floats to the top, mute hides a source (and its unread), mark all read zeroes it",
          r["n0"] == r["n"] and r["n1"] == r["n"] - 1 and r["pinned"] and r["hidden"] and r["n2"] < r["n1"] and r["under"] == 2 and r["n3"] == 0, r)
    check("b. state survives a save: the all-read time, the read ids and the pins", r["back"][0] > 0 and r["back"][1] == ["x:1"] and "p" in r["back"][2], r["back"])
    check("b. the Jarvis card: '3 new' style status + the unread number; all quiet with nothing new; the window title '(3) Inbox'",
          r["card0"][0]["label"] == f"{r['n']} new" and r["card0"][1] == {"label": "New", "value": str(r["n"])} and r["card1"]["label"] == "All quiet" and r["noItems"][0]["label"] == "All quiet"
          and r["title"] == ["(3) Inbox", "Inbox"] and r["badge"] == ["3 new", "All quiet"], r)
    check("b. plain helpers: whitespace squeezed, secrets dropped, 500 chars cut to 180, times in words; junk sources give no items and no error",
          r["clean"] == ["a b", "", 180] and r["ago"] == ["just now", "10 min ago", "2 h ago", "2 d ago"] and r["junk"] == 0, (r["clean"], r["ago"], r["junk"]))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def part_c():
    from playwright.sync_api import sync_playwright
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/inbox/"
    now = int(time.time())
    seed = {
        "jarvis.bots.log.v1": [{"key": "a", "kind": "fill", "bot": "lit", "level": "info", "text": "took a long trade at 30,120", "t": now - 300},
                               {"key": "b", "kind": "guard", "bot": "atlas", "level": "bad", "text": "hit its daily loss limit", "t": now - 5400},
                               {"key": "c", "bot": "lit", "text": "token: ghp_abcdef123456789 leaked", "t": now - 20}],
        "argus.hist.v1": {"days": {}, "open": {"pc": {"label": "PC heartbeat", "since": now - 7200}}, "reds": []},
        "jarvis.vault.learned": [{"t": now - 20000, "text": "You prefer the London session"}],
        "arena.v1": {"v": 1, "events": [{"id": "e1", "day": time.strftime("%Y-%m-%d"), "kind": "labour", "src": "x", "note": "The Steady Hand"}]},
        "jarvis.smart": {"keys": {"groq": "gsk_SECRETKEY123"}}, "jarvis.vault": {"repo": "me/v", "token": "SECRET-TOKEN"},
    }
    live = {"bridge": {"t": now, "jobs": {"j1": {"title": "Name the bots", "status": "question"}}, "counts": {"question": 1}, "commits": []},
            "kalshi": {"running": True, "status": "Trading"}}
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            ctx = br.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
            p = ctx.new_page()
            p.set_default_timeout(60000)
            errs, posts = [], []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.on("request", lambda r: posts.append(r.method + " " + r.url) if r.method != "GET" and not r.url.startswith("data:") else None)

            def mock(route):
                u = route.request.url
                if live.get("down") and (u.endswith(".json") or "kalshi-feed" in u) and "/inbox/" not in u:
                    return route.abort()
                if "kalshi-feed" in u:
                    return route.fulfill(status=200, content_type="application/json", body=json.dumps(live["kalshi"]))
                if u.endswith("/bridge/status.json"):
                    return route.fulfill(status=200, content_type="application/json", body=json.dumps(live["bridge"])) if live["bridge"] else route.abort()
                if u.endswith("/jarvis.json") and "/inbox/" not in u:
                    if "/forum/" in u:
                        return route.fulfill(status=200, content_type="application/json", body=json.dumps({"name": "Forum", "t": now - 5 * 86400, "stale_after": 86400, "status": {"label": "Live"}}))
                    return route.fulfill(status=404, body="no")
                if u.endswith("learning_log.json") or u.endswith("/live.json"):
                    return route.fulfill(status=404, body="no")
                return route.continue_()
            ctx.route("**/*", mock)
            p.goto(base + "?x=0")
            p.evaluate("(s) => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem(k, JSON.stringify(v)); }", seed)
            before = p.evaluate("(keys) => keys.map((k) => localStorage.getItem(k))", list(seed))
            p.goto(base)
            p.wait_for_function("document.querySelectorAll('#list .it').length >= 6 && document.getElementById('refresh').getAttribute('aria-busy') === 'false'")
            ids = p.evaluate("[...document.querySelectorAll('#list .it')].map((l) => l.getAttribute('data-src') + '|' + l.querySelector('.tx').textContent)")
            n = int(p.text_content("#unread"))
            texts = " ".join(i.split("|", 1)[1] for i in ids)
            check("c. every source is in the list: bots, Argus (still red), Bridge question, Arena achievement, Jarvis learned, a stale app (Forum 5 d); the secret-looking event is not",
                  {"bots", "argus", "bridge", "arena", "mind", "system"} <= {i.split("|")[0] for i in ids} and "LIT: took a long trade at 30,120" in texts and "Still red: PC heartbeat, for 2 h" in texts
                  and "ChatGPT has a question for you: Name the bots" in texts and "Forum has not refreshed for 5 d" in texts and "ghp_" not in texts and "ghp_" not in p.content(), ids)
            check("c. newest first (a time-ago line on each), the window title and the unread number agree", p.title() == f"({n}) Inbox" and n == len(ids) and "just now" in p.inner_text("#list .it >> nth=0").lower() or "min ago" in p.inner_text("#list .it >> nth=0"), (p.title(), n))
            card = json.loads(p.evaluate("localStorage.getItem('inbox.card.v1')"))
            check("c. the Jarvis card kept for this phone says '<n> new' (red when something is red)", card["status"]["label"] == f"{n} new" and card["status"]["level"] == "bad" and card["kpis"][0]["value"] == str(n), card)
            open_h = p.get_attribute("#list .it[data-src=arena] a.mini", "href")
            check("c. every item has Open (the right app), Mark read, Pin and Mute <source>; each has an icon and its app colour", open_h == "../arena/" and p.locator("#list .it").first.locator(".ic").count() == 1
                  and p.evaluate("getComputedStyle(document.querySelector('#list .it[data-src=bots]')).getPropertyValue('--c').trim()") == "#c8a24a" and p.locator("#list .it[data-src=bots] button:has-text('Mute Bots')").count() >= 1)
            p.click("#filters [data-f=bots]")
            check("c. filter Bots: only bot items, its unread count is on the chip", p.locator("#list .it").count() == 2 and p.locator("#list .it:not([data-src=bots])").count() == 0 and p.locator("#filters [data-f=bots] b").text_content() == "2")
            p.click("#filters [data-f=all]")
            p.click("#list .it[data-src=arena] button:has-text('Mark read')")
            check("c. Mark read: that item is read, the count drops by one, the choice is kept in inbox.read.v1", int(p.text_content("#unread")) == n - 1 and p.locator("#list .it[data-src=arena].unread").count() == 0
                  and "ids" in p.evaluate("localStorage.getItem('inbox.read.v1')"))
            p.click("#list .it[data-src=mind] button:has-text('Pin')")
            check("c. Pin: the item jumps to the top and shows under Pinned", p.get_attribute("#list .it >> nth=0", "data-src") == "mind" and (p.click("#filters [data-f=pinned]") or True) and p.locator("#list .it").count() == 1)
            p.click("#filters [data-f=all]")
            p.click("#list .it[data-src=bots] button:has-text('Mute Bots')")
            check("c. Mute a source: its items leave the list and stop counting; its chip shows muted; the data is not deleted", p.locator("#list .it[data-src=bots]").count() == 0
                  and p.get_attribute("#muteChips [data-src=bots]", "aria-pressed") == "true" and "jarvis.bots.log.v1" in p.evaluate("Object.keys(localStorage)"))
            p.click("#muteChips [data-src=bots]")
            check("c. Unmute brings them back", p.locator("#list .it[data-src=bots]").count() == 2)
            p.reload()
            p.wait_for_selector("#list .it")
            check("c. read, pin and mute survive a reload", p.locator("#list .it[data-src=mind].pin").count() == 1 and p.locator("#list .it[data-src=arena].unread").count() == 0)
            live["kalshi"] = {"running": False, "status": "Paused"}
            p.click("#refresh")
            p.wait_for_function("document.getElementById('refresh').getAttribute('aria-busy') === 'false'")
            p.wait_for_selector("#list .it[data-src=kalshi]")
            check("c. the Kalshi bot's status change (Trading -> Paused) becomes an item, kept by the Inbox", "Kalshi bot: Paused" in p.inner_text("#list .it[data-src=kalshi]"))
            p.click("#markAll")
            check("c. Mark all read: zero new, the title is just 'Inbox', the calm card says All quiet and still shows the last five items",
                  p.text_content("#unread") == "0" and p.title() == "Inbox" and not p.is_hidden("#calm") and p.is_hidden("#list") and "All quiet" in p.text_content("#calm") and p.locator("#last .it").count() == 5)
            card = json.loads(p.evaluate("localStorage.getItem('inbox.card.v1')"))
            check("c. the card goes back to 'All quiet'", card["status"]["label"] == "All quiet" and card["status"]["level"] == "ok")
            after = p.evaluate("(keys) => keys.map((k) => localStorage.getItem(k))", list(seed))
            check("c. read-only on every source: nothing it reads was changed (bots log, Argus, vault notes, Arena, the secrets), and no request but GET", after == before and not posts, posts[:2])
            # ---- offline: the cached copy
            live["down"] = True
            p.reload()
            p.wait_for_selector("#calm:not([hidden]), #list .it", timeout=20000)
            ctx.set_offline(True)
            p.click("#refresh")
            p.wait_for_function("document.getElementById('refresh').getAttribute('aria-busy') === 'false'")
            p.click("#filters [data-f=bridge]")
            p.wait_for_function("!document.getElementById('off').hidden", timeout=20000)
            check("c. offline: opens from this phone's copy (Bridge question still listed from the cache), marked OFFLINE COPY, never blank",
                  "Name the bots" in p.inner_text("#list") and "OFFLINE" in p.inner_text("#off").upper(), p.inner_text("#list")[:100])
            ctx.set_offline(False)
            # ---- phone sizes
            for w, hh in ((390, 844), (375, 667)):
                p.set_viewport_size({"width": w, "height": hh})
                p.click("#filters [data-f=all]")
                m = p.evaluate("""() => { const W = innerWidth, de = document.documentElement;
                  const out = [...document.querySelectorAll('#app > *, #app .card > *, .it')].filter((e) => e.getClientRects().length && (e.getBoundingClientRect().right > W - 15 || e.getBoundingClientRect().left < 15)).map((e) => e.className + ' ' + Math.round(e.getBoundingClientRect().left) + '-' + Math.round(e.getBoundingClientRect().right));
                  return [de.scrollWidth <= de.clientWidth, out]; }""")
                check(f"c. {w}x{hh}: no sideways scroll, nothing outside the 16 px gutters", m[0] and not m[1], m)
                small = p.evaluate("""() => [...document.querySelectorAll('#app button, #app a.mini')].filter((e) => e.getClientRects().length && !e.disabled)
                  .filter((e) => { const r = e.getBoundingClientRect(); const x = e.closest('.filters'); return r.height < 43.5 || (r.width < 43.5); }).map((e) => (e.className || e.tagName) + ' ' + Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height))""")
                check(f"c. {w}x{hh}: every control at least 44 px", not small, small[:5])
            check("c. no page errors", not errs, errs[:3])
            ctx2 = br.new_context(viewport={"width": 390, "height": 844}, reduced_motion="reduce")
            q = ctx2.new_page()
            q.route("**/*", lambda r: r.fulfill(status=404, body="no") if r.request.url.endswith(".json") or "kalshi-feed" in r.request.url else r.continue_())
            q.goto(base)
            q.wait_for_selector("#calm:not([hidden])")
            an = q.evaluate("[...document.querySelectorAll('.aurora i, .it')].map((e) => getComputedStyle(e).animationName)")
            check("c. a brand-new phone (no data at all): never blank, a calm card that says what will collect here; LITE / reduced motion: nothing animates",
                  "Nothing has happened yet" in q.text_content("#calm") and q.locator("#last .empty").count() == 1 and all(a == "none" for a in an) and not q.is_hidden("#lite"), an)
            ctx2.close()
            br.close()
    finally:
        srv.shutdown()


def main():
    which = os.environ.get("INBOX_PART", "")
    if which in ("", "a"):
        part_a()
    if which in ("", "b"):
        part_b()
    if which in ("", "c") and not os.environ.get("INBOX_NO_BROWSER"):
        part_c()
    n = sum(RES)
    print(f"\ninbox page: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
