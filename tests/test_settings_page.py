"""OLYMPUS SETTINGS + FIRST-RUN TOUR (tools/web_public/settings/, 2026-11-04): the one place to control the whole system from the phone.
  a. the static rules: the kit (olympus.css / themes.js / olympus.js ?v=o2, data-app='settings'), no CDN, no innerHTML, no network calls at all,
     safe areas and the orb's corner, 16 px inputs, reduced motion, the manifest, the icon, jarvis.json, the haptics gate in olympus/sfx.js
  b. the rules (settingscore.js, run in node): secrets are never listed, exported, imported or cleared; keys grouped by app; clearing one app;
     export / import round trip; Jarvis's own settings in the exact keys Jarvis reads; brain-key and vault STATUS only; battery saver restores
     the old choices; the six tour cards
  c. the page in Chromium (390 x 844, 375 x 667): the four tabs, 3D quality + theme + motion + sounds, Jarvis settings, the storage manager
     (clear one app, secrets kept, caches, export, import), the tour (first open, six cards, skip, done, Tour button, keyboard), no errors,
     no sideways scroll, every control 44 px, nothing leaves the machine
    python -X utf8 -m tests.test_settings_page            (SET_NO_BROWSER=1 skips c; SET_PART=a|b|c runs one part)
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
PAGE = os.path.join(WEB, "settings")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def node(body):
    script = ("import fs from 'fs'; const url = 'file://' + " + json.dumps(PAGE) + "; const out = (x) => console.log('@@' + JSON.stringify(x));\n"
              "class Mem { constructor() { this.m = {}; } get length() { return Object.keys(this.m).length; } key(i) { return Object.keys(this.m)[i] ?? null; }\n"
              "  getItem(k) { return k in this.m ? this.m[k] : null; } setItem(k, v) { this.m[k] = String(v); } removeItem(k) { delete this.m[k]; } }\n"
              "try { " + body + " } catch (e) { console.log('@@' + JSON.stringify({ error: String(e && e.stack || e) })); }")
    p = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=90)
    m = [ln for ln in p.stdout.splitlines() if ln.startswith("@@")]
    return json.loads(m[-1][2:]) if m else {"error": (p.stderr or p.stdout)[-400:]}


def part_a():
    files = os.listdir(PAGE)
    need = {"index.html", "settings.css", "settingscore.js", "settings.js", "jarvis.json", "manifest.webmanifest", "icon.svg"}
    check("a. the folder has every file (page, css, core, page script, Jarvis card, manifest, icon)", need <= set(files), need - set(files))
    html, css = rd(PAGE, "index.html"), rd(PAGE, "settings.css")
    js = {n: rd(PAGE, n) for n in files if n.endswith(".js")}
    check("a. the kit first (olympus.css, themes.js, olympus.js ?v=o2 with data-app='settings'), viewport-fit=cover, theme-color, dark, manifest, icon, apple-touch-icon",
          '<link rel="stylesheet" href="../olympus/olympus.css?v=o7">' in html and 'src="../olympus/themes.js?v=o11"' in html and 'src="../olympus/olympus.js?v=o23" data-app="settings"' in html
          and "viewport-fit=cover" in html and 'name="theme-color"' in html and 'content="dark"' in html and 'rel="manifest" href="manifest.webmanifest"' in html
          and 'rel="icon" href="icon.svg"' in html and 'rel="apple-touch-icon"' in html and "fx-core.js?v=f1" in html and "sfx.js" in html)
    check("a. no CDN, no outside script / font / image: every src and href is local", not re.search(r'(src|href)="https?://', html))
    check("a. no innerHTML / insertAdjacentHTML / document.write (everything goes in as text)", not any(re.search(r"innerHTML|insertAdjacentHTML|document\.write", s) for s in js.values()))
    check("a. no network at all: no fetch / XHR / WebSocket / beacon (a settings page must work offline and never send a thing)",
          not any(re.search(r"\bfetch\(|XMLHttpRequest|WebSocket|sendBeacon|EventSource|import\(['\"]http", s) for s in js.values()))
    check("a. secrets: the page never reads a key's value for display (no getItem on jarvis.smart / jarvis.vault outside the status helpers)",
          "SECRET_KEYS = ['jarvis.smart', 'jarvis.vault']" in js["settingscore.js"] and "jarvis.smart" not in js["settings.js"] and "jarvis.vault" not in js["settings.js"])
    check("a. safe areas on every edge, the orb's corner (176 px of room at the bottom), 16 px inputs, reduced motion, 44 px controls",
          all(f"var(--s{x})" in css for x in "trbl") and "176px" in css and "font-size: 16px" in css and "@media (prefers-reduced-motion: no-preference)" in css and css.count("min-height: 44px") >= 6)
    pre = css.split("@media (prefers-reduced-motion: no-preference)")[0]
    check("a. every animation sits behind prefers-reduced-motion (the CSS before that block has none)", "animation:" not in pre, "")
    m = json.loads(rd(PAGE, "manifest.webmanifest"))
    check("a. the manifest names the app and points at its icon", m["name"] == "Settings" and m["icons"][0]["src"] == "icon.svg" and m["start_url"] == "./")
    j = json.loads(rd(PAGE, "jarvis.json"))
    check("a. jarvis.json keeps the Jarvis card contract (name, status, 3 kpis, <= 3 lines, t, open, theme, < 8 KB, plain text)",
          j["v"] == 1 and j["name"] == "Settings" and j["status"]["level"] in ("ok", "warn", "bad", "off") and len(j["kpis"]) == 3 and len(j["lines"]) <= 3 and isinstance(j["t"], int)
          and re.fullmatch(r"#[0-9a-f]{6}", j["theme"]) and os.path.getsize(os.path.join(PAGE, "jarvis.json")) < 8192 and not re.search(r"[<>]", json.dumps(j)), j)
    check("a. Reading and quality: the kit's a11y layer is loaded (a11y.js defer + a11y.css), Big text is a data-oly-a11y='big-text' toggle, the quality levels are explained, the storage list has a Clear-all button",
          'src="../olympus/a11y.js?v=a3" defer' in html and 'href="../olympus/a11y.css?v=a3"' in html and 'data-oly-a11y="big-text"' in html and 'data-oly-a11y="more-contrast"' in html
          and 'id="fxLevels"' in html and 'id="fxWhy"' in html and 'id="clearAll"' in html and 'id="stWhat"' in html and os.path.isfile(os.path.join(WEB, "olympus", "a11y.js")))
    check("a. haptics: olympus/sfx.js honours the 'olympus.haptics' = off switch", "olympus.haptics" in rd(WEB, "olympus", "sfx.js"))


def part_b():
    r = node("""const C = await import(url + '/settingscore.js');
      const st = new Mem();
      for (const [k, v] of Object.entries({ 'jfx': 'low', 'olympus.theme': 'zeus', 'oly.intro': 'off', 'jarvis.mode': 'life', 'jarvis.smart': JSON.stringify({ v: 2, on: true, keys: { groq: 'gsk_SECRET', gemini: '' } }),
        'jarvis.vault': JSON.stringify({ repo: 'me/vault', token: 'ghp_SECRET' }), 'jarvis.vault.learned': '[1]', 'mind.state': 'abc', 'arena.save': 'defg', 'apiToken.x': 'zzz', 'forum.v1': '{}' })) st.setItem(k, v);
      const sum = C.summarize(st), names = sum.groups.map((g) => g.id);
      const exp = C.buildExport(st, 1700000000000), expText = JSON.stringify(exp);
      const st2 = new Mem(); st2.setItem('jarvis.vault', 'KEEP-ME');
      const bad = C.checkImport({ kind: 'olympus-data', keys: { 'jarvis.smart': 'x', 'ok.key': 'y', 'bad key!': 'z', 'num': 5 } });
      const imp = C.applyImport(st2, exp);
      const clr = C.clearApp(st, 'jarvis'), left = C.listKeys(st);
      const j = new Mem(); j.setItem('jarvis.smart', JSON.stringify({ keys: { groq: 'gsk_SECRET' }, on: false }));
      const a0 = C.alertsGet(j), a1 = C.alertsSet(j, { speak: false, from: '23:30' }), eng = C.engineSet(j, 'phone'), md = C.modeSet(j, 'research'), bogus = C.modeSet(j, 'nope');
      const sv = new Mem(); sv.setItem('jfx', 'ultra'); sv.setItem('olympus.sfx', JSON.stringify({ v: 0.8, m: false }));
      C.saverSet(sv, true); const on = [sv.getItem('jfx'), sv.getItem('oly.intro'), JSON.parse(sv.getItem('olympus.sfx')).m, C.saverOn(sv)];
      C.saverSet(sv, false); const off = [sv.getItem('jfx'), sv.getItem('oly.intro'), JSON.parse(sv.getItem('olympus.sfx')).m, JSON.parse(sv.getItem('olympus.sfx')).v, C.saverOn(sv)];
      out({ names, sum: sum.groups.map((g) => [g.id, g.count, g.kept]), total: sum.total, expKeys: Object.keys(exp.keys).sort(), kept: exp.kept, leaked: /SECRET|ghp_|gsk_/.test(expText), t: exp.t,
        bad: [bad.ok, bad.count, bad.skipped.map((s) => s.key)], notExport: C.checkImport({ kind: 'x' }).ok, imp: [imp.written.length, st2.getItem('jarvis.vault'), st2.getItem('olympus.theme')],
        clr: [clr.removed.sort(), clr.kept.sort()], left, a0, a1, eng, md, bogus, smart: JSON.parse(j.getItem('jarvis.smart')).keys.groq, brain: C.brainStatus(j), noBrain: C.brainStatus(new Mem()),
        vault: C.vaultStatus(st), noVault: C.vaultStatus(new Mem()), on, off, tour: C.TOUR.map((c) => [c.id, c.title.length > 0, c.text.length > 40]), fmt: [C.fmtBytes(500), C.fmtBytes(2048), C.fmtBytes(5 * 1048576)],
        secret: ['jarvis.smart', 'jarvis.vault', 'x.token', 'my_api_key', 'oauth.secret', 'jarvis.mode', 'jfx', 'jarvis.vault.learned', 'forum.v1'].map((k) => C.isSecret(k)) });""")
    if r.get("error"):
        check("b. node runs settingscore.js", False, r["error"])
        return
    check("b. keys group by app (oly. / olympus. / jfx are one 'olympus'); every group counts its non-secret keys", {"olympus", "jarvis", "mind", "arena", "forum", "apitoken"} <= set(r["names"]) and
          [g for g in r["sum"] if g[0] == "olympus"][0][1] == 3, r["sum"])
    check("b. secrets: jarvis.smart, jarvis.vault and anything named token / secret / api_key are secrets; jarvis.mode, jfx, jarvis.vault.learned, forum.v1 are not",
          r["secret"] == [True, True, True, True, True, False, False, False, False], r["secret"])
    check("b. the summary only NAMES the secrets (kept) and does not count them as saved keys", [g for g in r["sum"] if g[0] == "jarvis"][0][2] == ["jarvis.smart", "jarvis.vault"] and r["total"]["kept"] == 3
          and r["total"]["keys"] == 8, r["total"])
    check("b. export: every non-secret key as text, the secrets listed by name only, no secret text anywhere in the file", "jarvis.smart" not in r["expKeys"] and "jarvis.vault" not in r["expKeys"]
          and "jfx" in r["expKeys"] and "olympus.theme" in r["expKeys"] and not r["leaked"] and sorted(r["kept"]) == ["apiToken.x", "jarvis.smart", "jarvis.vault"] and r["t"] == 1700000000, r)
    check("b. import: not an Olympus file = refused; a secret, an odd name and a non-text value are skipped; the existing secret on the phone is untouched",
          r["notExport"] is False and r["bad"] == [True, 1, ["jarvis.smart", "bad key!", "num"]] and r["imp"] == [8, "KEEP-ME", "zeus"], (r["bad"], r["imp"]))
    check("b. clear one app: its non-secret keys go, its secrets stay, other apps are untouched",
          r["clr"] == [["jarvis.mode", "jarvis.vault.learned"], ["jarvis.smart", "jarvis.vault"]] and "mind.state" in r["left"] and "jarvis.smart" in r["left"] and "jarvis.mode" not in r["left"], r["clr"])
    check("b. Jarvis's own keys: alerts defaults (speak / brief / quiet on, 22:00-07:00), a change keeps the rest, engine mode, default mode; an unknown mode changes nothing",
          r["a0"] == {"speak": True, "brief": True, "quiet": True, "from": "22:00", "to": "07:00"} and r["a1"] == {"speak": False, "brief": True, "quiet": True, "from": "23:30", "to": "07:00"}
          and r["eng"] == "phone" and r["md"] == "research" and r["bogus"] == "research" and r["smart"] == "gsk_SECRET", (r["a0"], r["a1"], r["eng"], r["md"]))
    check("b. brain key and vault STATUS only (saved / not, the providers, connected + repo): never a key character in the answer",
          r["brain"] == {"saved": True, "providers": ["Groq"], "on": False} and r["noBrain"]["saved"] is False and r["vault"] == {"connected": True, "repo": "me/vault"}
          and r["noVault"]["connected"] is False and "SECRET" not in json.dumps([r["brain"], r["vault"]]), (r["brain"], r["vault"]))
    check("b. battery saver: LITE + intros off + sounds muted, then the old choices come back exactly (ultra, intro on, sound on at 0.8)",
          r["on"] == ["low", "off", True, True] and r["off"] == ["ultra", None, False, 0.8, False], (r["on"], r["off"]))
    check("b. the tour: six cards (what, jarvis, apps, cities, connect, home), each with a title and real text", [c[0] for c in r["tour"]] == ["what", "jarvis", "apps", "cities", "connect", "home"]
          and all(c[1] and c[2] for c in r["tour"]) and r["fmt"] == ["500 B", "2.0 KB", "5.0 MB"], r["tour"])


def part_b2():
    r = node("""const C = await import(url + '/settingscore.js');
      const st = new Mem();
      ['jarvis.smart', 'jarvis.vault', 'mind.x', 'arena.save', 'oly.intro', 'kalshicity.v1', 'olympus.a11y', 'jarvis.mode', 'apiToken.y'].forEach((k) => st.setItem(k, 'v-' + k));
      const ra = C.clearAll(st);
      out({ why: [C.fxWhy({ saver: true, level: 'low', chosen: 'low' }), C.fxWhy({ reduced: true, level: 'off' }), C.fxWhy({ chosen: 'ultra', level: 'ultra' }), C.fxWhy({ level: 'low' }), C.fxWhy({}), C.fxWhy({ reduced: true, level: 'ultra', chosen: 'ultra' })],
        levels: C.FX_EXPLAIN.map((l) => [l[0], l.length, l.slice(1).every((x) => typeof x === 'string' && x.length > 3)]), keep: C.FX_LEVELS.map((l) => l[0]),
        clear: [ra.removed.sort(), ra.kept.sort(), st.length, st.getItem('jarvis.smart'), st.getItem('jarvis.vault'), st.getItem('mind.x'), st.getItem('apiToken.y')],
        group: [C.groupOf('kalshicity.v1').name, C.groupOf('olympus.a11y').id, C.groupOf('ledger.v1').name], about: [C.aboutOf('kalshicity'), C.aboutOf('zzz'), C.aboutOf('olympus')] });""")
    if r.get("error"):
        check("b. node runs the quality explainer and clear-all (settingscore.js)", False, r["error"])
        return
    w = r["why"]
    check("b. the quality explainer: four levels (Battery, High, Ultra 4K, Still: perf v2) in the same order as the picker, each with what you see, what it costs and who it is for",
          [l[0] for l in r["levels"]] == r["keep"] == ["low", "high", "ultra", "off"] and all(l[1] == 5 and l[2] for l in r["levels"]), r["levels"])
    check("b. 'why this level now' in one plain sentence: battery saver first, then the phone's less-motion setting, then your own choice, else Auto (and Auto explains the slow-phone hold to LITE)",
          "Battery saver" in w[0] and "less motion" in w[1] and "you chose it" in w[2] and "Auto picked it" in w[3] and "LITE" in w[3] and "Auto picked it" in w[4] and "you chose it" in w[5], w)
    removed, kept, left, smart, vault, mind, tok = r["clear"]
    check("b. clear everything: every non-secret key goes (6 here, the token-named one counts as a secret), the secrets stay untouched with their values",
          removed == ["arena.save", "jarvis.mode", "kalshicity.v1", "mind.x", "oly.intro", "olympus.a11y"] and kept == ["apiToken.y", "jarvis.smart", "jarvis.vault"] and left == 3 and smart == "v-jarvis.smart" and vault == "v-jarvis.vault" and mind is None and tok == "v-apiToken.y", r["clear"])
    check("b. the storage list speaks plain words: Kalshi City and Ledger have names and a one-line 'what it keeps', unknown apps get a safe line, olympus.a11y belongs to Olympus",
          r["group"] == ["Kalshi City", "olympus", "Ledger"] and "dollars" in r["about"][0] and r["about"][1].startswith("Choices this app saved") and "text size" in r["about"][2], (r["group"], r["about"]))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def part_c():
    from playwright.sync_api import sync_playwright
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/settings/"
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            ctx = br.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, accept_downloads=True)
            p = ctx.new_page()
            p.set_default_timeout(60000)
            errs, reqs = [], []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
            p.on("request", lambda r: reqs.append(r.url) if not r.url.startswith(base.rsplit("/settings/", 1)[0]) and not r.url.startswith("data:") else None)
            seed = ("localStorage.clear(); localStorage.setItem('jarvis.vault', JSON.stringify({repo:'me/vault', token:'SECRET-TOKEN'}));"
                    "localStorage.setItem('jarvis.smart', JSON.stringify({v:2,on:true,keys:{groq:'gsk_SECRETKEY'}})); localStorage.setItem('mind.x','1'); localStorage.setItem('arena.save','abc');")
            p.goto(base + "?tour=0")
            p.evaluate(seed)
            p.goto(base)
            p.wait_for_selector("#tour:not([hidden])")
            check("c. first open (olympus.tour.done not saved): the tour opens by itself on card 1 of 6", p.text_content("#tourStep") == "1 of 6" and "This is Olympus" in p.text_content("#tourT"))
            for i in range(5):
                p.click("#tourNext")
            check("c. six cards: the last says Done and has the three-app / Bridge / Jarvis links earlier", p.text_content("#tourNext") == "Done" and p.text_content("#tourStep") == "6 of 6"
                  and "Home Screen" in p.text_content("#tourT"))
            p.click("#tourBack")
            check("c. the connect card (5) shows Bridge + Jarvis links and the free Gemini key steps", "Create API key" in p.text_content("#tourText") and p.locator("#tourLinks a").count() == 2
                  and p.get_attribute("#tourLinks a >> nth=0", "href") == "../bridge/")
            p.click("#tourSkip")
            done = p.evaluate("localStorage.getItem('olympus.tour.done')")
            check("c. skip closes it and saves olympus.tour.done; reopening the page does not show it again", p.is_hidden("#tour") and done is not None)
            p.goto(base)
            p.wait_for_selector("#tabs")
            p.wait_for_timeout(900)
            check("c. no tour on the next visit", p.is_hidden("#tour"))
            p.click("#tourBtn")
            check("c. the Tour button opens it any time (card 1); Escape closes it", p.is_visible("#tour") and p.text_content("#tourStep") == "1 of 6")
            p.keyboard.press("ArrowRight")
            check("c. the arrow keys walk the cards", p.text_content("#tourStep") == "2 of 6")
            p.keyboard.press("Escape")
            check("c. Escape closes the tour", p.is_hidden("#tour"))
            # ---- Look
            check("c. four tabs, Look first, each panel never blank", p.locator("#tabs [role=tab]").count() == 4 and p.get_attribute("#t-look", "aria-selected") == "true"
                  and p.locator("#p-look .card").count() == 5)
            names = p.evaluate("[...document.querySelectorAll('#fxSeg [role=radio]')].map((b) => [b.getAttribute('data-v'), b.textContent])")
            check("c. the Quality picker (perf v2): Auto / Battery / High / Ultra 4K / Still, all in the one 3D-quality key jfx (Auto = no key)",
                  names == [["auto", "Auto"], ["low", "Battery"], ["high", "High"], ["ultra", "Ultra 4K"], ["off", "Still"]], names)
            check("c. 3D quality: picking Battery writes jfx=low (the one key) and shows LITE",
                  p.locator("#fxSeg [role=radio]").count() == 5 and (p.click("#fxSeg [data-v=low]") or True) and p.evaluate("localStorage.getItem('jfx')") == "low"
                  and p.get_attribute("#fxSeg [data-v=low]", "aria-checked") == "true" and not p.is_hidden("#lite") and "LITE" in p.inner_text("#fxTag").upper())
            p.click("#fxSeg [data-v=ultra]")
            check("c. the live preview follows the choice (Ultra: 90 motes)", "90 motes" in p.inner_text("#fxTag") and p.evaluate("localStorage.getItem('jfx')") == "ultra")
            p.click("#fxSeg [data-v=off]")
            check("c. Still: nothing moves (0 motes, page marked LITE / STILL)", "0 motes" in p.inner_text("#fxTag") and p.inner_text("#lite").upper() == "STILL")
            p.click("#fxSeg [data-v=auto]")
            check("c. Auto removes the key", p.evaluate("localStorage.getItem('jfx')") is None)
            why = p.inner_text("#fxWhy")
            lv = p.evaluate("[...document.querySelectorAll('#fxLevels li')].map((l) => l.textContent)")
            check("c. the quality explainer: one plain sentence says why this level (Auto picked it), four cards say what each level shows, costs and is for, and the current one is marked NOW",
                  "because Auto picked it" in why and len(lv) == 4 and p.locator("#fxLevels li.now").count() == 1 and all("Costs:" in t and "Best for:" in t for t in lv) and "Still" in lv[3], (why, lv))
            p.click("#fxSeg [data-v=low]")
            check("c. ...it follows the choice: LITE 'because you chose it', and the NOW mark moves to LITE", "you chose it" in p.inner_text("#fxWhy") and "LITE" in p.inner_text("#fxLevels li.now b").upper())
            p.click("#fxSeg [data-v=auto]")
            # ---- Reading: the kit's Big text toggle
            bt0 = p.evaluate("[document.getElementById('bigText').getAttribute('aria-pressed'), document.getElementById('bigText').getAttribute('data-oly-a11y'), document.documentElement.getAttribute('data-oly-text')]")
            check("c. Reading: Big text is the kit's own toggle (data-oly-a11y='big-text'), a 44 px button, off to start, and the page says the text is 100%",
                  bt0 == ["false", "big-text", "normal"] and "off" in p.text_content("#bigText") and "100%" in p.inner_text("#bigNote") and p.locator("#bigText").bounding_box()["height"] >= 44)
            p.click("#bigText")
            p.wait_for_function("document.documentElement.getAttribute('data-oly-text') === 'big'")
            check("c. Big text on: html is marked big, the button is pressed and says on, the choice is saved on this phone (olympus.a11y), the note says 125%, nothing is wider than the phone",
                  p.get_attribute("#bigText", "aria-pressed") == "true" and "on" in p.text_content("#bigText") and json.loads(p.evaluate("localStorage.getItem('olympus.a11y')"))["text"] == "big"
                  and "125%" in p.inner_text("#bigNote") and p.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
            split = p.evaluate("[...document.querySelectorAll('.tabs button, #fxSeg button')].filter((b) => { const r = document.createRange(); r.selectNodeContents(b); return new Set([...r.getClientRects()].map((x) => Math.round(x.top))).size > 1; }).map((b) => b.textContent)")
            check("c. Big text on: the tabs and the quality picker keep whole words (no word broken across two lines)", not split, split)
            p.click("#moreContrast")
            check("c. Stronger contrast on: html is marked, the button says so; both toggles off again with a second tap",
                  p.evaluate("document.documentElement.getAttribute('data-oly-contrast')") == "more" and "stronger" in p.text_content("#moreContrast") and p.get_attribute("#moreContrast", "aria-pressed") == "true")
            p.click("#moreContrast")
            p.click("#bigText")
            p.wait_for_function("document.documentElement.getAttribute('data-oly-text') === 'normal'")
            check("c. ...off again: normal text, normal contrast, 'off' on the buttons", p.evaluate("document.documentElement.getAttribute('data-oly-contrast')") is None and "off" in p.text_content("#bigText") and "100%" in p.inner_text("#bigNote"))
            n = p.locator("#themes .theme").count()
            p.click("#themes .theme[data-id=zeus]")
            check("c. themes: every OLYMPUS theme as a swatch card; tapping one saves olympus.theme and repaints the page now",
                  n >= 6 and p.evaluate("localStorage.getItem('olympus.theme')") == "zeus" and p.get_attribute("#themes [data-id=zeus]", "aria-checked") == "true"
                  and p.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--oly-accent').trim()") != "")
            p.click("#themes .theme[data-id=olympus]")
            p.check("#saver")
            check("c. battery saver: jfx low, intros off, sounds muted (and the switches show it)", p.evaluate("[localStorage.getItem('jfx'), localStorage.getItem('oly.intro'), JSON.parse(localStorage.getItem('olympus.sfx')).m]") == ["low", "off", True]
                  and not p.is_checked("#intro") and not p.is_checked("#sfxOn"))
            p.uncheck("#saver")
            check("c. saver off: the old choices come back", p.evaluate("localStorage.getItem('jfx')") is None and p.evaluate("localStorage.getItem('oly.intro')") is None and p.is_checked("#intro"))
            p.uncheck("#intro")
            p.uncheck("#trans")
            p.uncheck("#haptics")
            check("c. intro films / page transitions / haptics switch off in their own keys (oly.intro, olympus.transitions, olympus.haptics = off)",
                  p.evaluate("[localStorage.getItem('oly.intro'), localStorage.getItem('olympus.transitions'), localStorage.getItem('olympus.haptics')]") == ["off", "off", "off"])
            p.fill("#vol", "60")
            p.dispatch_event("#vol", "input")
            check("c. sound volume is saved in olympus.sfx", abs(json.loads(p.evaluate("localStorage.getItem('olympus.sfx')"))["v"] - 0.6) < 0.01)
            # ---- Jarvis
            p.click("#t-jarvis")
            p.click("#engSeg [data-v=phone]")
            p.click("#modeSeg [data-v=life]")
            p.uncheck("#aQuiet")
            check("c. Jarvis: voice engine, default mode and quiet hours are written in the keys Jarvis reads", json.loads(p.evaluate("localStorage.getItem('jarvis.voiceEngine')"))["mode"] == "phone"
                  and p.evaluate("localStorage.getItem('jarvis.mode')") == "life" and json.loads(p.evaluate("localStorage.getItem('jarvis.alerts.v1')"))["quiet"] is False and p.is_disabled("#aFrom"))
            body = p.inner_text("#p-jarvis")
            check("c. brain key: only SAVED and the provider name, never a key; the button opens Jarvis; Obsidian: CONNECTED + repo, never the token",
                  "SAVED" in p.inner_text("#brainSt") and "Groq" in p.inner_text("#brainNote") and "CONNECTED" in p.inner_text("#vaultSt") and "me/vault" in body
                  and "SECRET" not in p.content() and p.get_attribute("#keyBtn", "href") == "../jarvis/")
            # ---- Data
            p.click("#t-data")
            p.wait_for_selector("#appList li")
            apps = p.evaluate("[...document.querySelectorAll('#appList li')].map((l) => l.getAttribute('data-app'))")
            check("c. storage: this phone's use, a row per app with its count and size, the secrets named as kept", {"arena", "mind", "jarvis"} <= set(apps) and "Kept (secret): jarvis.smart, jarvis.vault" in p.inner_text("#appList")
                  and p.inner_text("#stUse") != "" and "secret" in p.inner_text("#stNote"))
            check("c. the list says in plain words what each app keeps and what the page stores (never a key, never money numbers); Clear-all is a 44 px button",
                  p.evaluate("[...document.querySelectorAll('#appList li')].every((l) => l.querySelector('small.about') && l.querySelector('small.about').textContent.length > 8)")
                  and "Never a key" in p.inner_text("#stWhat") and p.locator("#clearAll").bounding_box()["height"] >= 44 and not p.is_disabled("#clearAll"))
            p.click("#appList li[data-app=arena] .mini")
            check("c. clearing asks first and names what stays", not p.is_hidden("#sheet") and "Clear Arena" in p.text_content("#shT"))
            p.click("#shNo")
            check("c. Cancel keeps everything", p.evaluate("localStorage.getItem('arena.save')") == "abc")
            p.click("#appList li[data-app=arena] .mini")
            p.click("#shYes")
            check("c. clear one app: Arena's saved data is gone, Mind's and the secrets are untouched",
                  p.evaluate("localStorage.getItem('arena.save')") is None and p.evaluate("localStorage.getItem('mind.x')") == "1" and p.evaluate("localStorage.getItem('jarvis.vault')") is not None
                  and p.evaluate("localStorage.getItem('jarvis.smart')") is not None)
            p.evaluate("caches.open('test-cache-1').then((c) => c.put('/x', new Response('x')))")
            p.evaluate("window.SETTINGS.renderData()")
            p.wait_for_selector("#cacheList li[data-cache='test-cache-1']")
            p.click("#cacheList li[data-cache='test-cache-1'] .mini")
            p.click("#shYes")
            p.wait_for_function("!document.querySelector(\"#cacheList li[data-cache='test-cache-1']\")")
            check("c. caches: listed by name with their files, cleared one at a time after a confirm", p.evaluate("caches.keys().then((k) => k.indexOf('test-cache-1') < 0)"))
            with p.expect_download() as dl:
                p.click("#exportBtn")
            path = dl.value.path()
            data = json.load(open(path, encoding="utf-8"))
            check("c. export: a JSON download of every non-secret key, the secrets left out and named", data["kind"] == "olympus-data" and "mind.x" in data["keys"] and "jarvis.mode" in data["keys"]
                  and "jarvis.smart" not in data["keys"] and "jarvis.vault" not in data["keys"] and "SECRET" not in open(path, encoding="utf-8").read() and "left out" in p.inner_text("#ioNote"))
            imp = os.path.join(os.environ.get("TMP", "/tmp"), "olympus_import_test.json")
            with open(imp, "w", encoding="utf-8") as fh:
                json.dump({"kind": "olympus-data", "v": 1, "keys": {"mind.imported": "yes", "jarvis.smart": "HACK", "olympus.theme": "hades"}}, fh)
            p.set_input_files("#importFile", imp)
            p.wait_for_selector("#sheet:not([hidden])")
            p.click("#shYes")
            check("c. import: asks, writes the safe entries, never the secret one; the theme applies",
                  p.evaluate("localStorage.getItem('mind.imported')") == "yes" and "gsk_SECRETKEY" in p.evaluate("localStorage.getItem('jarvis.smart')") and p.evaluate("localStorage.getItem('olympus.theme')") == "hades"
                  and "skipped 1" in p.inner_text("#ioNote"))
            try:
                os.remove(imp)
            except OSError:
                pass
            # ---- clear everything (last, it empties the seeds the tests above used)
            p.click("#clearAll")
            check("c. 'Clear everything' asks first, counts what it removes and names the secrets that stay", not p.is_hidden("#sheet") and "Clear everything" in p.text_content("#shT") and "saved settings" in p.text_content("#shP")
                  and "jarvis.smart" in p.text_content("#shL") and p.text_content("#shYes") == "Clear all")
            p.click("#shNo")
            check("c. Cancel keeps everything", p.evaluate("localStorage.getItem('mind.x')") == "1")
            p.click("#clearAll")
            p.click("#shYes")
            keys = p.evaluate("Object.keys(localStorage).sort()")
            check("c. Clear all: Mind's, Jarvis's and Olympus' saved choices are gone, the two secrets stay untouched (and are never shown)",
                  "mind.x" not in keys and "mind.imported" not in keys and "jarvis.mode" not in keys and "olympus.theme" not in keys and p.evaluate("localStorage.getItem('jarvis.smart')") is not None
                  and p.evaluate("localStorage.getItem('jarvis.vault')") is not None and "Cleared" in p.inner_text("#ioNote") and "SECRET" not in p.content(), keys)
            # ---- System
            p.click("#t-system")
            hrefs = p.evaluate("[...document.querySelectorAll('#p-system a')].map((a) => a.getAttribute('href'))")
            check("c. system: Argus, the PC page, Bridge, Jarvis, and the CLEAN_STORAGE / FRESH_START downloads", {"../argus/", "../pc/", "../bridge/", "../jarvis/", "../pc/CLEAN_STORAGE.bat", "../pc/FRESH_START.bat"} <= set(hrefs), hrefs)
            # ---- layout at two phone sizes, every tab
            for w, hh in ((390, 844), (375, 667)):
                p.set_viewport_size({"width": w, "height": hh})
                for t in ("look", "jarvis", "data", "system"):
                    p.click(f"#t-{t}")
                    m = p.evaluate("""() => { const W = innerWidth, de = document.documentElement;
                      const out = [...document.querySelectorAll('#app > *, #app .card > *, .row')].filter((e) => e.getClientRects().length && (e.getBoundingClientRect().right > W - 15 || e.getBoundingClientRect().left < 15)).map((e) => e.className + ' ' + Math.round(e.getBoundingClientRect().left) + '-' + Math.round(e.getBoundingClientRect().right));
                      return [de.scrollWidth <= de.clientWidth, out]; }""")
                    check(f"c. {w}x{hh} {t}: no sideways scroll, nothing outside the 16 px gutters", m[0] and not m[1], m)
                    small = p.evaluate("""() => [...document.querySelectorAll('#app button, #app a.go, #app a.link, #app .tm, #app input.rng, #app label.row')].filter((e) => e.getClientRects().length && !e.disabled)
                      .filter((e) => { const r = e.getBoundingClientRect(); return r.height < 43.5 || (e.tagName !== 'LABEL' && r.width < 43.5); }).map((e) => (e.id || e.className || e.tagName) + ' ' + Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height))""")
                    check(f"c. {w}x{hh} {t}: every control at least 44 px", not small, small[:5])
            p.set_viewport_size({"width": 390, "height": 844})
            p.click("#tourBtn")
            tb = p.evaluate("(() => { const b = document.querySelector('.tour-box').getBoundingClientRect(); return [b.left >= 0, b.right <= innerWidth, b.top >= 0, b.bottom <= innerHeight]; })()")
            check("c. the tour card fits the phone screen", all(tb), tb)
            p.keyboard.press("Escape")
            check("c. no page errors and nothing left the machine (every request is the site's own)", not errs and not reqs, (errs[:3], reqs[:3]))
            # ---- reduced motion
            ctx2 = br.new_context(viewport={"width": 390, "height": 844}, reduced_motion="reduce")
            q = ctx2.new_page()
            q.goto(base + "?tour=0")
            q.wait_for_selector("#tabs")
            an = q.evaluate("[...document.querySelectorAll('.aurora i, .card')].map((e) => getComputedStyle(e).animationName)")
            check("c. reduced motion: the aurora and the cards do not animate, the page says STILL / LITE", all(a == "none" for a in an) and not q.is_hidden("#lite"), an)
            ctx2.close()
            br.close()
    finally:
        srv.shutdown()


def part_d():
    """d. the Data section (2026-11-10): the records every app keeps on this phone, the address warning, Export all / Import all."""
    html = rd(WEB, "settings", "index.html")
    js = rd(WEB, "settings", "settings.js")
    check("d. the Data tab has 'If the site address changes' (a warning card) and 'Your records on this phone' (a list), and Export all / Import all buttons",
          'id="c-addr"' in html and "If the site address changes" in html and 'id="recList"' in html and "Export all" in html and "Import all" in html and 'id="exportBtn"' in html and 'id="importFile"' in html)
    check("d. the page fills the list from recordsReport and the warning from ADDRESS_WARNING (as text, no innerHTML)", "C.recordsReport(LS)" in js and "C.ADDRESS_WARNING.text" in js and "innerHTML" not in js)
    # every known key must be a real key some app uses (grep the apps, so the list cannot drift into names nobody writes)
    r = node("""const C = await import(url + '/settingscore.js');
      const st = new Mem();
      ['ledger.v1', 'journal.v1', 'planner.agora.v1', 'lyceum.v1', 'jarvis.orb.fav', 'oly.launcher.fav', 'jarvis.smart', 'x.token'].forEach((k) => st.setItem(k, 'v-' + k));
      const rep = C.recordsReport(st), exp = C.buildExport(st), st2 = new Mem(), imp = C.applyImport(st2, exp);
      out({ keys: C.KNOWN_KEYS.map((k) => k[0]), present: rep.rows.filter((x) => x.present).map((x) => x.key), n: rep.present, bytes: rep.bytes > 0,
        secretInKnown: C.KNOWN_KEYS.some((k) => C.isSecret(k[0])), expKeys: Object.keys(exp.keys).sort(), imp: imp.written.length, back: st2.getItem('ledger.v1'),
        names: [C.groupOf('journal.v1').name, C.groupOf('planner.agora.v1').name, C.groupOf('oikos.v1').name, C.groupOf('mint.hist.v1').name], warn: C.ADDRESS_WARNING.text });""")
    if r.get("error"):
        check("d. node runs recordsReport", False, r["error"])
        return
    apps = ""
    for root, _d, files in os.walk(WEB):
        for f in files:
            if f.endswith((".js", ".html")) and "settings" not in root:
                try:
                    apps += open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()
                except OSError:
                    pass
    missing = [k for k in r["keys"] if k not in apps]
    check("d. every known key is really written by some app (found in the app sources)", not missing, missing)
    check("d. the report lists the six keys that are on the phone, with sizes, and never a secret", r["present"] == sorted(["ledger.v1", "journal.v1", "planner.agora.v1", "lyceum.v1", "jarvis.orb.fav", "oly.launcher.fav"], key=lambda k: r["keys"].index(k)) and r["n"] == 6 and r["bytes"] and not r["secretInKnown"], r)
    check("d. Export all: one file with every non-secret key (ledger, journal, planner, favourites ...) and no secret; Import all puts them back",
          "jarvis.smart" not in r["expKeys"] and "x.token" not in r["expKeys"] and "ledger.v1" in r["expKeys"] and r["imp"] == 6 and r["back"] == "v-ledger.v1", r)
    check("d. the newer apps have plain names (Journal, Planner, Oikos, Mint)", r["names"] == ["Journal", "Planner", "Oikos", "Mint"], r["names"])
    check("d. the address warning says the data does not follow a new address and to export first", "NOT follow" in r["warn"] and "Export all" in r["warn"] and "Import all" in r["warn"], r["warn"])


def main():
    which = os.environ.get("SET_PART", "")
    if which in ("", "a"):
        part_a()
    if which in ("", "b"):
        part_b()
        part_b2()
    if which in ("", "d"):
        part_d()
    if which in ("", "c") and not os.environ.get("SET_NO_BROWSER"):
        part_c()
    n = sum(RES)
    print(f"\nsettings page: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
