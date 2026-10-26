"""Screenshots of the Start page's one button "Start trading" (engine/go.step_auto, web_next/js/next/start.js) in its
states, PC width and phone width, with a console-error check. The real dashboard server must run; the Start page's
status answer is replaced in the browser (Playwright routing) by each state, so nothing on the PC changes and no POST
reaches the server.

    python -X utf8 -m tests.shots_start --pc http://127.0.0.1:8766 --out research/handoff/2026-10-26/ui_start_auto

Exit code 1 when the page logs a console error or does not draw.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time

from tests.shots_brain import _launch, _real

L50, L25 = "MFFUEVBLD602936016", "MFFUEVBLD602936017"


def base_status():
    steps = [
        {"key": "nt", "label": "NinjaTrader connected", "done": True, "action": "nt", "button": "Open NinjaTrader", "detail": "connected"},
        {"key": "feed", "label": "Live bars from NinjaTrader", "done": True, "action": "recheck", "button": "Check again",
         "detail": "LE_BarFeed's MNQ 5-minute bars are fresh"},
        {"key": "accounts", "label": "Accounts set (50K → Zlarior, 25K → ATLAS)", "done": True, "action": "names",
         "button": "Set the names", "detail": f"Zlarior → 50K {L50} · ATLAS → 25K {L25}"},
        {"key": "setup", "label": "Setup done", "done": True, "action": "setup", "button": "Run setup",
         "detail": "allowlist, 50K balance and floor, ATLAS on the 25K (2026-10-25)"},
        {"key": "sims", "label": "Sim tests passed", "done": True, "action": "sims", "button": "Run the Sim test",
         "detail": "both Sim101 roundtrips passed"},
        {"key": "armed", "label": "Armed", "done": True, "action": "arm", "button": "Arm and start", "detail": "live switch on, 25K armed"},
        {"key": "running", "label": "Running and routes verified", "done": False, "action": "arm", "button": "Start", "detail": "stopped"},
    ]
    for s in steps:
        s.update(ready=True, first=None, needs=[])
    return {"steps": steps, "all_green": False, "say": f"Zlarior → 50K {L50} · ATLAS → 25K {L25} · both armed · stopped",
            "lit": L50, "atlas": L25, "suggest_lit": None, "running": False, "market_open": True,
            "job": {"step": None, "running": False, "state": None, "lines": []}, "phrase": "I ACCEPT LIVE RISK",
            "need_phrase": False, "resume_why": None, "local": True,
            "clock": {"known": True, "ok": True, "drift_s": 0.3, "say": "PC clock matches internet time"},
            "accounts": {"rows": [
                {"name": L50, "bot": "Zlarior", "role": "main", "plan": "builder50k", "plan_label": "MFFU Builder 50K", "state": "eval",
                 "armed": None, "balance": 49710.8, "floor": 48168.2, "as_of": "2026-10-23", "source": "MFFU numbers you entered"},
                {"name": L25, "bot": "ATLAS", "role": "b", "plan": "builder25k", "plan_label": "MFFU Builder 25K", "state": "eval",
                 "armed": True, "balance": 25000.0, "floor": 24000.0, "as_of": None, "source": "plan start"}],
                "picks": [], "plans": {}, "today": "2026-10-26"}}


def job(stage, say, running=True, rc=None, need=None, retry_s=None, lines=()):
    return {"step": "auto", "running": running, "state": "running" if running else "done", "rc": rc, "t0": time.time() - 40,
            "t1": None if running else time.time() - 5, "stage": stage, "say": say, "need": need, "retry_s": retry_s,
            "lines": list(lines)}


def states():
    out = []
    s = base_status()
    out.append(("01_ready_no_phrase", s))
    s = base_status()
    s.update(need_phrase=True, resume_why="auto-resume is off (the first start, or after the kill switch)")
    s["steps"][5].update(done=False, detail="live switch off; 25K not armed (you type I ACCEPT LIVE RISK)")
    s["say"] = f"Zlarior → 50K {L50} · ATLAS → 25K {L25} · not armed · stopped"
    out.append(("02_first_start_phrase", s))
    s = base_status()
    s["job"] = job("feed", "No live bars from NinjaTrader (MNQ_5m.csv is stale: last bar Mon 09:35 ET, 12 min ago). In NinjaTrader: "
                           "right-click the MNQ 5-minute chart > Reload NinjaScript (or re-add LE_BarFeed). Checking again every 15 s.",
                   retry_s=15, lines=[" Looking for a newer version", " Already the newest version", " NinjaTrader connected. Checking the live bars"])
    s["steps"][1].update(done=False, detail="MNQ_5m.csv is stale: right-click the MNQ 5-minute chart > Reload NinjaScript (or re-add LE_BarFeed)")
    out.append(("03_waiting_live_bars", s))
    s = base_status()
    s["job"] = job("nt", "NinjaTrader is still not connected. Log in to NinjaTrader; the page tries again by itself.", running=False,
                   rc=1, retry_s=60, lines=[" Opening NinjaTrader", " Log in to NinjaTrader and connect your MFFU account."])
    s["steps"][0].update(done=False, detail="not connected: log in to NinjaTrader and connect your MFFU account")
    s["clock"] = {"known": True, "ok": False, "drift_s": -5.4, "say": "PC clock 5.4 s ahead of internet time: new entries are blocked above 5 s"}
    out.append(("04_retry_and_clock", s))
    s = base_status()
    s.update(running=True, all_green=True, say=f"Zlarior → 50K {L50} · ATLAS → 25K {L25} · both armed · running")
    s["steps"][6].update(done=True, detail="Zlarior on the 50K, ATLAS on the 25K (checked in the running bot)")
    s["job"] = job("running", f"Running: Zlarior → 50K {L50} · ATLAS → 25K {L25}.", running=False, rc=0)
    out.append(("05_running", s))
    return out


def shots(base, out, errors):
    from playwright.sync_api import sync_playwright
    os.makedirs(out, exist_ok=True)
    with sync_playwright() as p:
        br = _launch(p)
        for w, h, tag in ((1440, 1000, "pc"), (390, 844, "phone")):
            for name, st in states():
                if tag == "phone" and name not in ("02_first_start_phrase", "04_retry_and_clock"):
                    continue
                ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1)
                pg = ctx.new_page()
                pg.on("console", lambda m: errors.append(f"{name}: console: {m.text}") if m.type == "error" and _real(m.text) else None)
                pg.on("pageerror", lambda e: errors.append(f"{name}: pageerror: {e}") if _real(str(e)) else None)
                body = json.dumps(copy.deepcopy(st))

                def answer(b):
                    return lambda route: route.fulfill(status=200, content_type="application/json", body=b)
                pg.route("**/api/next/start/status*", answer(body))
                pg.route("**/api/next/start/go", lambda r: r.fulfill(status=200, content_type="application/json", body='{"ok": true}'))
                pg.add_init_script("localStorage.setItem('nx.fx', 'off'); sessionStorage.setItem('st.auto', '1');")
                pg.goto(base + "/?page=start&fxfixed", wait_until="domcontentloaded")
                try:
                    pg.wait_for_selector("#page-start.active .st-gocard", timeout=60000)
                except Exception as e:
                    errors.append(f"{name}: the Start trading card did not draw ({e.__class__.__name__})")
                pg.wait_for_timeout(900)
                if name == "02_first_start_phrase" and tag == "pc":
                    pg.fill("#stGoPhrase", "i accept live risk")
                    pg.wait_for_timeout(200)
                    if pg.is_disabled("#stGo"):
                        errors.append("the phrase in small letters did not enable the button")
                pg.screenshot(path=os.path.join(out, f"{name}_{tag}.png"), full_page=tag == "phone")
                sw = pg.evaluate("() => document.documentElement.scrollWidth")
                if sw > w + 1:
                    errors.append(f"{name} {tag}: page wider than the screen ({sw} px)")
                print("shot", name, tag, flush=True)
                ctx.close()
        br.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pc", default="http://127.0.0.1:8766")
    ap.add_argument("--out", default="research/handoff/2026-10-26/ui_start_auto")
    a = ap.parse_args(argv)
    errors = []
    shots(a.pc.rstrip("/"), a.out, errors)
    for e in errors:
        print("ERROR", e)
    print("start shots:", "OK" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
