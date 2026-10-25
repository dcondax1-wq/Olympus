"""Screenshots of the launch checklist (engine/launch_check.py) on the phone (390 px: Home card, #/launch page, More hub,
light theme, all green) and on the PC Command center (1440 px, static web_next with /api/next/cc/home answered from
fixture data). Needs Playwright + Chromium. Read-only: fixture data only, nothing talks to a bot.

    python -X utf8 -m tests.shots_launch [--out research/handoff/2026-10-25]

Writes <out>/ui_phone/launch_*.png and <out>/ui_pc/launch_*.png. Exit code 1 on a page error or a card that did not draw.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import launch_check as LC  # noqa: E402
from tests.test_atlas_ui import _launch, _serve, sample_block, sample_data  # noqa: E402

LIT, B = "MFFU50K-EVAL", "MFFU25K-EVAL"


def fixture(all_green=False, now=None):
    now = int(now or time.time())
    f = {"v": 1, "t": now, "lit_account": LIT,
         "anchor": {"set": True, "balance": 49710.8, "floor": 48168.2, "as_of": "2026-10-23", "set_t": now - 900},
         "b": {"configured": True, "account": B, "plan": "builder25k", "eval_start": "2026-10-26", "armed": all_green, "running": True},
         "allow": {"n": 2, "lit": True, "lit_sim": False, "b": True, "b_sim": False},
         "startup": {"ok": True, "since": now - 120, "problems": []} if all_green else
         {"ok": False, "since": None, "problems": ["NinjaTrader restarted: check the account, then confirm"]},
         "sim": {"roundtrip": {"t": now - 1500, "ok": True, "account": "Sim101"}} if not all_green else
         {"roundtrip": {"t": now - 1500, "ok": True, "account": "Sim101"}, "add": {"t": now - 1300, "ok": True, "account": "Sim101"}},
         "lit_armed": all_green, "bot_started_t": now - 12 * 3600}
    h = {"account": {"name": LIT, "adapter": "ninjatrader", "armed": all_green},
         "nt": {"connected": True, "connections": {"Tradovate": "CONNECTED"}},
         "feed": {"used": "ninjatrader", "age_1m_s": 25, "age_5m_s": 140, "stale": False, "entries_blocked": False, "market_open": True}}
    return {**LC.checklist(f, h, True, now), "facts": f}


def phone(out, errors):
    from playwright.sync_api import sync_playwright
    tmp = tempfile.mkdtemp()
    try:
        sites = {}
        for tag, green in (("red", False), ("green", True)):
            site = os.path.join(tmp, tag)
            shutil.copytree(os.path.join(ROOT, "tools", "web_public"), site, ignore=shutil.ignore_patterns("fx", "node_modules", "icon_options"))
            d = sample_data(sample_block(acct_b=True))
            d["live"]["pc"]["launch"] = fixture(green)
            for n in ("data.json", "home.json"):
                json.dump(d, open(os.path.join(site, n), "w"), default=str)
            sites[tag] = site
        srv = {k: _serve(v) for k, v in sites.items()}
        shots = [("launch_01_home", "red", "#/today", False, "dark", ".lc-card"),
                 ("launch_02_page", "red", "#/launch", True, "dark", ".lc-list"),
                 ("launch_03_more", "red", "#/system", False, "dark", ".ft-row[data-go='launch']"),
                 ("launch_04_home_light", "red", "#/today", False, "light", ".lc-card"),
                 ("launch_05_page_all_green", "green", "#/launch", True, "dark", ".lc-card.done"),
                 ("launch_06_home_all_green", "green", "#/today", False, "dark", ".gl-card")]
        with sync_playwright() as p:
            br = _launch(p)
            for name, tag, hash_, full, theme, sel in shots:
                ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
                                     service_workers="block")
                pg = ctx.new_page()
                pg.on("pageerror", lambda e, n=name: errors.append(f"{n} pageerror: {str(e)[:200]}"))
                pg.route("https://api.github.com/**", lambda r: r.fulfill(status=404, body="{}"))
                pg.route("https://raw.githubusercontent.com/**", lambda r: r.fulfill(status=404, body="{}"))
                pg.add_init_script(f"try {{ localStorage.setItem('le.theme', '\"{theme}\"'); localStorage.setItem('le.fx', '\"off\"'); "
                                   "localStorage.setItem('le.more.instLater', '9999999999999'); } catch (e) {}")
                pg.goto(f"http://127.0.0.1:{srv[tag].server_address[1]}/index.html?fxoff{hash_}", wait_until="domcontentloaded")
                try:
                    pg.wait_for_selector(sel, timeout=20000)
                except Exception:
                    errors.append(f"{name}: {sel} not drawn")
                if pg.query_selector("#moInstX"):
                    pg.click("#moInstX")
                if name == "launch_06_home_all_green" and pg.query_selector(".lc-card"):
                    errors.append(f"{name}: the Home card should hide when all green")
                if name == "launch_01_home":
                    first = pg.evaluate("() => { const c = [...document.querySelectorAll('#page .card:not(#moInst)')]; "
                                        "const l = c.findIndex(e => e.classList.contains('lc-card')), g = c.findIndex(e => e.classList.contains('gl-card')); return [l, g]; }")
                    if not (first[0] >= 0 and first[0] < first[1]):
                        errors.append(f"{name}: launch card not above Goals {first}")
                    ov = pg.evaluate("() => document.documentElement.scrollWidth - innerWidth")
                    if ov > 1:
                        errors.append(f"{name}: horizontal scroll {ov}px")
                pg.wait_for_timeout(1200)
                path = os.path.join(out, name + ".png")
                pg.screenshot(path=path, full_page=full)
                print("shot", path, flush=True)
                ctx.close()
            br.close()
        for s in srv.values():
            s.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def pc(out, errors):
    from playwright.sync_api import sync_playwright
    from engine import pc_cc_api as C
    from tests.test_pcdash_api import fake_bot
    tmp = tempfile.mkdtemp()
    try:
        b, now = fake_bot(tmp, account="Sim101")
        home = json.loads(json.dumps(C.home_view(b, now), default=str))
        homes = {}
        for tag, green in (("red", False), ("green", True)):
            h = dict(home)
            h["launch"] = fixture(green, now)
            homes[tag] = json.dumps(h, default=str)
        ui = os.path.join(tmp, "ui")             # server.py serves web_next/ first and falls back to web/
        shutil.copytree(os.path.join(ROOT, "web"), ui)
        shutil.copytree(os.path.join(ROOT, "web_next"), ui, dirs_exist_ok=True)
        srv = _serve(ui)
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        with sync_playwright() as p:
            br = _launch(p)
            for name, tag, theme in (("launch_01_cc", "red", "dark"), ("launch_02_cc_light", "red", "light"), ("launch_03_cc_all_green", "green", "dark")):
                ctx = br.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1, service_workers="block")
                pg = ctx.new_page()
                # the static harness answers every other /api/ call with {}: page errors there are the stubs, not the checklist
                pg.on("pageerror", lambda e, n=name: print(f"note: pc {n} pageerror (stub API): {str(e)[:120]}"))
                body = homes[tag]
                def answer(body):
                    return lambda r: r.fulfill(status=200, content_type="application/json", body=body)
                pg.route("**/api/next/cc/home", answer(body))
                pg.route(lambda u: "/api/" in u and not u.endswith("/api/next/cc/home"),
                         lambda r: r.fulfill(status=200, content_type="application/json", body="{}"))
                pg.add_init_script("localStorage.setItem('page', 'cc'); localStorage.setItem('nx.fx', 'off');")
                pg.goto(base + "/?fxfixed", wait_until="domcontentloaded")
                pg.wait_for_timeout(1500)
                try:
                    pg.evaluate("() => window.LE && window.LE.go('cc')")
                    pg.wait_for_selector("#page-cc.active " + (".cc-launch-ok" if tag == "green" else ".cc-launch-card"), timeout=30000)
                except Exception as e:
                    errors.append(f"pc {name}: launch card not drawn ({e.__class__.__name__})")
                if theme == "light":
                    pg.evaluate("() => { const b = document.getElementById('ccTheme'); if (b) b.click(); }")
                    pg.wait_for_timeout(2000)
                pg.wait_for_timeout(800)
                path = os.path.join(out, name + ".png")
                pg.screenshot(path=path)
                print("shot", path, flush=True)
                ctx.close()
            br.close()
        srv.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "research", "handoff", "2026-10-25"))
    a = ap.parse_args(argv)
    errors = []
    po, co = os.path.join(a.out, "ui_phone"), os.path.join(a.out, "ui_pc")
    os.makedirs(po, exist_ok=True)
    os.makedirs(co, exist_ok=True)
    phone(po, errors)
    pc(co, errors)
    for e in errors:
        print("ERROR", e)
    print("errors:", len(errors))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
