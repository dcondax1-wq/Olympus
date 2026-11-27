"""NQ NOW iPhone widget (day-widget 2026-11-27; owner lives on his iPhone): tools/web_public/widget/nq-now.js (Scriptable) + setup.html.
  a. model    the REAL PC post of 2026-11-22 (tests/fixtures/nq_now/post.json, re-timed to Fri 11-27 10:26 ET) + nq/ports.json "Coming up":
              NQ 25,665.00 ▼ -334.25 vs Wed close; chips 👀 Zlarior setup 4/10, ⏸️ ATLAS waiting, ⏸️ Rapid waiting (BLITZ never);
              today $0; ⏳ Half day 13:15 in 2h 45m; 7-day last day from the k7 block; "live · 10:26 ET"
  b. trade    LIT LONG 3 MNQ from 25,600 -> 🟢 in trade +$390 (65 pts x 3 x $2)
  c. old feed 45 min -> "as of 10:26 ET" (stale, chips kept); 3 h -> every chip 🔴 PC silent; no post + a saved copy -> "Saved copy · as of";
              no post, nothing saved -> "No PC numbers yet", nothing made up
  d. draw     small / medium / large / lock-screen rectangular / inline / circular inside a fake Scriptable: the right lines, no
              undefined / NaN, tap -> nq/, refresh asked in 5 min, the cache written only from a real PC post
  f. Siri     a copy named "NQ status" run by Siri SPEAKS: "NQ 25,665, down 1.3 percent. Zlarior is forming a long setup at stage 4 of 10,
              ATLAS is waiting, no trades today, zero dollars. Next: the market halts at 1:15." (+ Shortcuts output); stale / silent /
              no-post words honest; "Why no trade" speaks the newest rejection of the PC's glog in plain words; the widget is not drawn
  e. setup    the one-paste NQ NOW steps (Home Screen + lock screen), the old Olympus widget kept; files: no account id / email,
              read only (no POST, no key)
Run: python -X utf8 -m tests.test_nq_now
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
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public", "widget")
FIX = os.path.join(ROOT, "tests", "fixtures", "nq_now")
HARN = os.path.join(ROOT, "tests", "nq_now_harness.cjs")
PORTS = os.path.join(FIX, "ports.json")
NOW = int(dt.datetime(2026, 11, 27, 10, 30, tzinfo=ZoneInfo("America/New_York")).timestamp())
RES: list = []
TMP = tempfile.mkdtemp(prefix="nqnow")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("  [OK]  " if ok else "  [FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def post(age_s, trade=False):
    with open(os.path.join(FIX, "post.json"), encoding="utf-8") as fh:
        p = json.load(fh)
    p["t"], p["reporter"]["t"], p["pc_verdict"]["t"] = NOW - age_s, NOW - age_s + 10, NOW - age_s
    if trade:
        p["board"]["lit"]["position"] = {"side": "LONG", "entry": 25600.0, "qty": 3, "entry_t": NOW - age_s - 600}
    path = os.path.join(TMP, f"p{age_s}{int(trade)}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(p, fh)
    return path


def node(*a):
    r = subprocess.run(["node", HARN, *[str(x) for x in a]], capture_output=True, text=True, timeout=60)
    if r.returncode or not r.stdout:
        raise SystemExit(f"harness failed: {r.stderr[-800:]}")
    return json.loads(r.stdout)


def chips(m):
    return [f"{c['emoji']} {c['name']} {c['text']}" for c in m["chips"]]


def part_a_c():
    r = node("pure", post(240), PORTS, NOW)
    m = r["m"]
    check("a. price 25,665 ▼ -334.25 vs Wed's close (ports.json vol.nq_close 25,999.25 of 11-25)",
          m["price"] == 25665 and m["arrow"] == "▼" and round(m["chg"], 2) == -334.25 and m["refWhat"] == "vs Wed close", m)
    check("a. chips: 👀 Zlarior setup 4/10 (glance stage 'Displacement (4/10)'), ⏸️ ATLAS waiting, ⏸️ Rapid waiting; no BLITZ",
          chips(m) == ["👀 Zlarior setup 4/10", "⏸️ ATLAS waiting", "⏸️ Rapid waiting"] and "blitz" not in json.dumps(m).lower(), chips(m))
    check("a. today $0 (every account's eval.today), ⏳ Half day 13:15 in 2h 45m (ports 'Coming up')",
          m["today"] == 0 and m["next"]["what"] == "Half day 13:15" and m["next"]["in"] == "2h 45m", (m["today"], m["next"]))
    check("a. 7-day: the soonest k7 'hard' day, named (Rapid EOD 25K Thu 11/26, already passed in this old post = red)",
          m["last"]["name"] == "Rapid EOD 25K" and m["last"]["text"] == "Thu 11/26 (passed)" and m["last"]["lvl"] == "bad", m["last"])
    check("a. fresh post: 'live · 10:26 ET', not stale", r["status"] == "live · 10:26 ET" and not m["stale"] and not m["silent"], r["status"])
    check("a. words: $ with commas and signs, spans, junk -> null", r["usd"] == ["-$807", "+$1,500", "$0", "—"] and r["span"] == ["10m", "2h 05m", "3d 1h"] and r["junk"] is None, r)

    m = node("pure", post(240, trade=True), PORTS, NOW)["m"]
    check("b. LIT LONG 3 MNQ from 25,600 at 25,665 -> 🟢 Zlarior in trade +$390", chips(m)[0] == "🟢 Zlarior in trade +$390", chips(m))

    r = node("pure", post(45 * 60), PORTS, NOW)
    check("c. 45 min old: 'as of 09:45 ET' (stale), chips kept", r["status"] == "as of 09:45 ET" and r["m"]["stale"] and not r["m"]["silent"]
          and chips(r["m"])[0] == "👀 Zlarior setup 4/10", (r["status"], chips(r["m"])))
    r = node("pure", post(3 * 3600), PORTS, NOW)
    check("c. 3 h old: every chip 🔴 PC silent, 'PC silent · as of 07:30 ET'", r["status"] == "PC silent · as of 07:30 ET"
          and all(c["emoji"] == "🔴" and c["text"] == "PC silent" for c in r["m"]["chips"]) and len(r["m"]["chips"]) == 3, (r["status"], chips(r["m"])))
    r = node("pure", "-", PORTS, NOW)
    check("c. no post, nothing saved: 'No PC numbers yet', no price, no chips, the next event still shown",
          r["status"] == "No PC numbers yet" and r["m"]["price"] is None and r["m"]["chips"] == [] and r["m"]["next"]["what"] == "Half day 13:15", r)
    r = node("pure", post(240), "-", NOW)
    check("c. no ports.json: no countdown, the price still shown (no arrow without a reference)", r["m"]["next"] is None and r["m"]["price"] == 25665 and r["m"]["arrow"] == "", r["m"])


def part_d():
    site = "https://dcondax1-wq.github.io/"
    want = {
        "small": ["25,665.00", "▼", "setup 4/10", "waiting", "$0", "live · 10:26 ET"],
        "medium": ["25,665.00", "Zlarior", "ATLAS", "setup 4/10", "Half day 13:15", "in 2h 45m", "Thu 11/26 (passed)", "live · 10:26 ET"],
        "large": ["NQ NOW", "TRADING YOUR EVAL", "25,665.00", "-334.25 (-1.29%) vs Wed close", "Rapid", "   Fri 11/27 13:15 ET", "Rapid EOD 25K", "live · 10:26 ET"],
        "accessoryRectangular": ["▼ NQ 25,665.00 · $0", "👀 setup 4/10  ⏸️ waiting", "⏳ Half day 13:15 2h 45m"],
        "accessoryInline": ["▼ NQ 25,665.00 👀 setup 4/10"],
        "accessoryCircular": ["👀", "25665", "▼"],
    }
    p = post(240)
    for fam, need in want.items():
        r = node("draw", p, PORTS, NOW, fam)
        flat = r["texts"]
        miss = [x for x in need if x not in flat]
        check(f"d. {fam}: {', '.join(need[:4])} ...; tap -> nq/; refresh asked in 5 min; no undefined / NaN",
              not miss and r["url"] == site + "nq/" and r["refresh"] == 300 and not any(re.search(r"undefined|NaN|null", t) for t in flat), (miss, flat))
    r = node("draw", p, PORTS, NOW, "medium")
    check("d. a real PC post is saved for later (cache = the model, src PC)", r["cached"] and r["cached"]["m"]["src"] == "PC", r["cached"])
    cache = os.path.join(TMP, "cache.json")
    with open(cache, "w", encoding="utf-8") as fh:
        json.dump(r["cached"], fh)
    r2 = node("draw", "-", PORTS, NOW + 2 * 3600, "medium", cache)
    check("d. offline 2 h later with the saved copy: 'Saved copy · as of 10:26 ET', chips 🔴 PC silent, the cache not overwritten",
          "Saved copy · as of 10:26 ET" in r2["texts"] and "PC silent" in r2["texts"] and r2["cached"]["m"]["src"] == "PC", r2["texts"])
    r3 = node("draw", "-", "-", NOW, "small")
    check("d. offline, nothing saved: 'No PC numbers yet', nothing saved", "No PC numbers yet" in r3["texts"] and r3["cached"] is None, r3["texts"])
    r4 = node("draw", p, PORTS, NOW, "app")
    check("d. run inside the app = the medium preview", r4["presented"] == "medium", r4["presented"])


def part_f():
    p = post(240)
    r = node("draw", p, PORTS, NOW, "siri:NQ status")
    want = ("NQ 25,665, down 1.3 percent. Zlarior is forming a long setup at stage 4 of 10, ATLAS is waiting, no trades today, zero dollars. "
            "Next: the market halts at 1:15.")
    check("f. 'Hey Siri, NQ status': speaks the 3 sentences, hands the same text to Shortcuts, draws no widget",
          r["spoken"] == [want] and r["output"] == want and not r["texts"] and r["url"] is None, r["spoken"])
    r = node("draw", p, PORTS, NOW, "siri:Why no trade")
    w = "At 9:15 in the evening, Zlarior skipped a setup: Swept equal lows 25,765.75, 0.22 A T R deep, but LIT needs 0.5."
    check("f. 'Hey Siri, why no trade': the newest rejection in the PC's glog (Zlarior 21:15) in plain words", r["spoken"] == [w], r["spoken"])
    r = node("draw", post(45 * 60), PORTS, NOW, "siri:NQ status")
    check("f. a 45-min-old post starts with 'As of 9:45 in the morning,'", r["spoken"][0].startswith("As of 9:45 in the morning, NQ 25,665"), r["spoken"])
    r = node("draw", post(3 * 3600), PORTS, NOW, "siri:NQ status")
    check("f. a 3-h-old post: 'The PC has been quiet since 7:30 in the morning' and every bot 'has no fresh report'",
          r["spoken"][0].startswith("The PC has been quiet since 7:30 in the morning.") and "Zlarior has no fresh report, ATLAS has no fresh report" in r["spoken"][0], r["spoken"])
    r = node("draw", "-", PORTS, NOW, "siri:NQ status")
    r2 = node("draw", "-", PORTS, NOW, "siri:Why no trade")
    check("f. no PC post: says so (status + why), nothing made up",
          r["spoken"] == ["I have no numbers from the PC yet. Next: the market halts at 1:15."] and r2["spoken"] == ["I have no report from the PC yet, so I cannot say why."], (r["spoken"], r2["spoken"]))
    with open(os.path.join(WEB, "nq-now.js"), encoding="utf-8") as fh:
        js = fh.read()
    check("f. BLITZ never spoken (glog / chips skip hidden bots)", "HIDDEN.includes(id.toLowerCase())" in js)


def part_e():
    with open(os.path.join(WEB, "setup.html"), encoding="utf-8") as fh:
        sp = fh.read()
    with open(os.path.join(WEB, "nq-now.js"), encoding="utf-8") as fh:
        js = fh.read()
    check("e. setup page: one-tap NQ NOW copy (nq-now.js), Home Screen + lock screen steps, the old Olympus widget kept, honest refresh",
          'data-src="nq-now.js"' in sp and "Hey Siri, NQ status" in sp and "Why no trade" in sp and "oneTap('goNq', 'nq-now.js')" in sp and "Lock screen" in sp and "olympus-widget.js" in sp and "5-15 min" in sp, "")
    found = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+|MFFU[A-Z]{3,}\w*\d{3,}|\bAPEX-\d+", js + sp)
    check("e. no email / broker account id in the widget files", not found, found)
    check("e. read only: no POST, no key, no Authorization; BLITZ hidden; OLYMPUS NIGHT colours (no cyan)",
          not re.search(r"POST|Authorization|apiKey", js) and "HIDDEN = ['blitz']" in js and all(c in js for c in ("#9d59ee", "#f1c14b", "#77db89", "#16131e"))
          and not re.search(r"cyan|#0ff\b|#00ffff|#22d3ee", js, re.I))


def main():
    part_a_c()
    part_d()
    part_f()
    part_e()
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed", flush=True)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
