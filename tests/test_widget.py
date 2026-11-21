"""Olympus widget (night-revamp-dash 2026-11-20): the Scriptable iPhone widget + the Glance page (tools/web_public/widget/).
  a. parse     the ntfy poll answer (tests/fixtures/widget/lite.ndjson: an older core, an ext post, junk lines, a keepalive): the
               NEWEST "le-live" core wins; junk -> null; Zlarior 50K + ATLAS (funded: "to payout") + the extra 25K #2 card, no twin
  b. sources   PC post -> LIVE / src PC; home.json only -> PAPER / SITE; nothing -> the saved copy as CACHED with its age; none -> null
  c. kalshi    the next K8 clock window: London 10:15 = 05:15 ET in November, 04:00 ET in July = the same 05:15 local ET slot,
               16:00 ET; weekends and the CME Thanksgiving skip (Nov 26) roll to the next one
  d. draw      the whole script inside a fake Scriptable (tests/widget_harness.cjs): small / medium / large draw the balances (medium:
               every account one line each since cities3 2026-11-20), $ to
               pass / to payout, Kalshi, the source tag + age; no "undefined" / "NaN"; tap -> the site; refresh ~15 min; the cache
               written; offline draws "No account numbers yet" and OFFLINE
  e. privacy   the widget files carry no broker account id, no email, no private ntfy alert topic (tools/site_privacy detectors)
               and the page builds no markup from data (textContent only)
    python -X utf8 -m tests.test_widget
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public", "widget")
FIX = os.path.join(ROOT, "tests", "fixtures", "widget")
HARN = os.path.join(ROOT, "tests", "widget_harness.cjs")
LITE, HOME = os.path.join(FIX, "lite.ndjson"), os.path.join(FIX, "home.json")
NOW = 1795142701 + 300
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("  [OK]  " if ok else "  [FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"))


def node(*a):
    p = subprocess.run(["node", HARN, *a], capture_output=True, text=True, timeout=60)
    if p.returncode:
        raise RuntimeError(p.stderr[-800:])
    return json.loads(p.stdout)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    d = node("pure", LITE, HOME, str(NOW))
    m = d["pick"]
    names = [a["name"] for a in m["accounts"]]
    check("a. the newest le-live core wins (not the older core, not the ext post)", d["lite_t"] == 1795142701 and d["lite_kind"] == "le-live", d["lite_t"])
    check("a. junk lines -> null", d["junk"] is None)
    check("a. Zlarior 50K + ATLAS + Zlarior 25K #2, each once", names == ["Zlarior 50K", "ATLAS", "Zlarior 25K #2"], names)
    z, at = m["accounts"][0], m["accounts"][1]
    check("a. Zlarior: balance / $ to pass / room from the PC card", z["balance"] == 49192.78 and z["to_go"] == 3807.22 and z["to_label"] == "to pass"
          and z["room"] == 1024.58 and 0.5 < z["room_frac"] < 0.52, z)
    check("a. ATLAS funded: no payout coach in plain node (Scriptable) -> no number, never the PC's raw $750-ping line ($1,962.80)", at["funded"] and at["to_label"] == "to payout" and at["to_go"] is None, at)
    check("b. PC post -> LIVE, src PC, fresh, the PC verdict label", m["src"] == "PC" and not m["stale"] and m["pc"]["label"] == "TRADING YOUR EVAL"
          and all(a["badge"] == "LIVE" for a in m["accounts"]), m["pc"])
    s = d["site_only"]
    check("b. home.json only -> SITE, PAPER badges, stale", s["src"] == "SITE" and s["stale"] and all(a["badge"] == "PAPER" for a in s["accounts"])
          and s["accounts"], s)
    c = d["cached"]
    check("b. nothing fetched -> the saved copy as CACHED with its age", c["src"] == "CACHED" and c["age_s"] == 7200 and "2 h ago" in c["pc"]["label"], c)
    check("b. nothing at all -> null", d["none"] is None)
    k = d["k"]
    check("c. Thu night -> Fri 05:15 ET (London 10:15)", k[0]["text"] == "tomorrow 05:15 ET", k[0])
    check("c. Fri 07:00 ET -> 16:00 ET the same day", k[1]["text"] == "today 16:00 ET", k[1])
    check("c. Saturday -> Monday 05:15 ET", k[2]["text"] == "Mon 05:15 ET", k[2])
    check("c. Thanksgiving Thu (CME skip, UK open) -> 05:15 legs only, the evening ones skipped",
          k[3]["text"] in ("tomorrow 05:15 ET",) and k[3]["name"] == "gold / silver DOWN", k[3])
    check("c. July (both on summer time) -> 05:15 ET", k[4]["text"] == "today 05:15 ET", k[4])
    check("c. Kalshi paper net + per $100", d["kp"]["net"] == 5.68 and d["kp"]["per100"] == 1.06 and d["kp"]["t"] > 1.79e9, d["kp"])
    check("c. $ format and ages", d["usd"] == ["-$807", "+$1,500", "$0", "—", "$1,234,567"] and d["ago"] == ["just now", "10 min ago", "2 h ago", "5 days ago"], d["usd"])
    check("c. the feed URL from status_feed.json (70-minute window), the public default topic otherwise",
          d["feed"][0] == "https://ntfy.sh/abc/json?poll=1&since=70m" and "olympus-nq-status-" in d["feed"][1], d["feed"])

    for fam, par, need in (("small", "-", ["$3,807 to pass", "Zlarior 50K"]),
                           ("medium", "classic", ["$49,193", "payout: see Olympus", "Zlarior 25K #2", "$25,000", "Kalshi"]),
                           ("large", "classic", ["$49,193", "-$113", "$25,000", "$1,500 to pass", "drawdown room 51%", "NQ"]),
                           ("medium", "-", ["$49,193", "-$113", "room $1,025", "NQ bot", "Decide"]),
                           ("large", "-", ["$49,193", "-$113", "$25,000", "room $887", "Kalshi", "Websites", "Planner", "NQ 26431.00"])):
        r = node("draw", LITE, HOME, fam, par)
        fam = fam if par == "-" else fam + " classic"
        txt = " | ".join(r["texts"])
        check(f"d. {fam}: draws {need}", all(n in r["texts"] for n in need), txt)
        check(f"d. {fam}: no undefined / NaN / null in what it draws", not re.search(r"undefined|NaN|null|\[object", txt), txt)
        check(f"d. {fam}: source tag + age, tap opens the site, refresh in ~15 min, last copy saved",
              any(t.startswith(("LIVE · PC", "PC · OLD", "PAPER · SITE")) for t in r["texts"]) and r["url"].startswith("https://dcondax1-wq.github.io/")
              and 14 * 60e3 < r["refresh"] <= 15 * 60e3 and r["cached"] == 1, r)
        if fam != "small":   # olympus2 2026-11-20: a plain 'last updated' line on medium and large
            check(f"d. {fam}: a 'Updated hh:mm' line", any(re.fullmatch(r"Updated \d\d:\d\d", t) for t in r["texts"]), txt)
    # olympus2 DATA TRUTH ask: a funded card's "to payout" = the payout coach's need_more, the same number pc_feed.js payoutLines gives NQ / Trading / Board
    js = ("global.PAYOUT_COACH = require('./tools/web_public/business/payoutcoach.js'); const W = require('./tools/web_public/widget/olympus-widget.js');"
          "const PF = require('./tools/web_public/pc_feed.js'); const fs = require('fs'); const lite = W.parseLite(fs.readFileSync(%s, 'utf8'));"
          "const m = W.fromLite(lite, %d); const b = JSON.parse(JSON.stringify(lite.board)); PF.payoutLines(b, [], lite, global.PAYOUT_COACH, '2026-11-20');"
          "const a = m.accounts.find((x) => x.funded); console.log(JSON.stringify([a.to_go, b.atlas.to_target, W.goalText(a), b.atlas.pc_to_target]));") % (json.dumps(LITE), NOW)
    out = subprocess.run(["node", "-e", js], cwd=ROOT, capture_output=True, text=True, timeout=60)
    try:
        v = json.loads(out.stdout.strip())
    except ValueError:
        v = [None, None, out.stderr[-300:], None]
    check("c. funded 'to payout' = the payout coach (pc_feed payoutLines), not the PC's raw $750-ping line (%s)" % v,
          v[0] is not None and abs(v[0] - v[1]) < 0.01 and v[2].endswith(" to payout") and v[0] != v[3], v)
    # owner 2026-11-20: MFFU sim-FUNDED accounts start at $0: funded ATLAS 25K at $24,887 reads -$113 (balance - $25,000); evals keep their balance
    r = node("draw", LITE, HOME, "large", "-")
    check("g. funded = balance - start (ATLAS -$113, never $24,887); evals unchanged ($49,193, $25,000)",
          "-$113" in r["texts"] and "$24,887" not in r["texts"] and "$49,193" in r["texts"] and "$25,000" in r["texts"], r["texts"])
    # widget2 2026-11-20 (owner: "half my home screen ... easily access buttons"): every button is its own link to the right Olympus page
    want = {"NQ bot": "nq/", "Kalshi": "kalshi/", "Cities": "cities/", "Jarvis": "jarvis/", "Planner": "planner/", "Business": "business/",
            "Websites": "agency/", "Decide": "board/#decide"}
    site = "https://dcondax1-wq.github.io/"
    for fam, names in (("large", list(want)), ("medium", ["NQ bot", "Kalshi", "Jarvis", "Decide"])):
        r = node("draw", LITE, HOME, fam, "-")
        got = {l["text"]: l["url"] for l in r["links"] if l["text"] in want}
        check(f"g. {fam}: {len(names)} tappable buttons, each opens its page", got == {n: site + want[n] for n in names}, got)
        check(f"g. {fam}: each button has an SF Symbol icon", len(r["symbols"]) == len(names), r["symbols"])
        check(f"g. {fam}: account lines open the NQ bot, the PC line opens the board",
              any(l["url"] == site + "nq/" and "$49,193" in l["text"] for l in r["links"])
              and any(l["url"] == site + "board/" and "PC silent" in l["text"] for l in r["links"]), r["links"])
    # open trade yes/no: a card with a live position shows LONG / SHORT and its open $ on its line
    import tempfile
    rows = read(LITE).splitlines()
    for i in range(len(rows) - 1, -1, -1):
        try:
            o = json.loads(rows[i]); msg = json.loads(o["message"])
        except (ValueError, KeyError, TypeError):
            continue
        if isinstance(msg.get("board"), dict) and isinstance(msg["board"].get("lit"), dict):
            msg["board"]["lit"]["position"] = {"side": "SHORT", "dir": -1, "qty": 2, "entry_t": msg["t"] - 300, "unrealized_usd": 125.0}
            o["message"] = json.dumps(msg); rows[i] = json.dumps(o)
            break
    with tempfile.NamedTemporaryFile("w", suffix=".ndjson", delete=False) as fh:
        fh.write("\n".join(rows) + "\n"); tmp = fh.name
    r = node("draw", tmp, HOME, "large", "-")
    os.unlink(tmp)
    check("g. an open trade shows on its account line (SHORT +$125); a flat account shows none",
          any(l["url"] == site + "nq/" and "SHORT +$125" in l["text"] and "Zlarior 50K" in l["text"] for l in r["links"])
          and sum("SHORT" in t or "LONG" in t for t in r["texts"]) == 1, r["texts"])
    sp = read(os.path.join(WEB, "setup.html"))
    check("g. setup page: Scriptable steps, one-tap import, the 8 Shortcuts Open-URL links, honest refresh note",
          "Scriptable" in sp and "olympus-widget.js" in sp and all(site + u in sp for u in want.values()) and "15 min" in sp and "viewport-fit=cover" in sp, "")
    r = node("draw", "-", "-", "large", "light")
    check("d. offline + nothing saved: says so, OFFLINE tag, saves nothing", "OFFLINE · —" in r["texts"] and r["cached"] == 0
          and any("No account numbers yet" in t for t in r["texts"]), r["texts"])
    r = node("draw", LITE, "-", "app", "medium")
    check("d. run inside the app with Parameter 'medium' -> the medium preview", r["presented"] == "medium", r)
    r = node("draw", "-", HOME, "medium", "-")
    check("d. no PC post -> the site copy marked PAPER · SITE", any(t.startswith("PAPER · SITE") for t in r["texts"]) and "PAPER" in r["texts"], r["texts"])

    from tools import site_privacy as SP
    files = ["olympus-widget.js", "index.html", "setup.html", "glance.html", "glance.js", "widget.css", "manifest.webmanifest"]
    found = []
    for f in files:
        txt = read(os.path.join(WEB, f))
        try:
            hits = SP.scan_text(txt, f) if hasattr(SP, "scan_text") else []
        except Exception as e:                       # noqa: BLE001 - a detector API change must not hide the plain checks below
            hits = [f"scan error {e}"]
        found += hits
        found += [f"{f}: {x}" for x in re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+|MFFU[A-Z]{3,}\w*\d{3,}|\bAPEX-\d+", txt)]
    check("e. no email, broker account id or detector finding in the widget files", not found, found)
    js = read(os.path.join(WEB, "glance.js")) + read(os.path.join(WEB, "olympus-widget.js"))
    check("e. no innerHTML / insertAdjacentHTML / document.write (text only)", not re.search(r"innerHTML|insertAdjacentHTML|document\.write", js))
    check("e. read only: no POST, no ntfy publish, no key", not re.search(r"method:\s*['\"]POST|\.method\s*=\s*['\"]POST|Authorization", js))
    for f in ("index.html", "setup.html", "glance.html"):
        h = read(os.path.join(WEB, f))
        check(f"e. {f}: title, viewport-fit=cover, light + dark", "<title>" in h and "viewport-fit=cover" in h and "light dark" in h)
    gh, gj = read(os.path.join(WEB, "glance.html")), read(os.path.join(WEB, "glance.js"))
    check("e. olympus2: Glance loads the payout coach and the site-wide age chip (age.js / age.css) and uses OLY_AGE.chip for the report age",
          "../business/payoutcoach.js" in gh and "../age.js?v=1" in gh and "../age.css?v=2" in gh and "A.chip(ageEl" in gj)
    print(f"{sum(RES)} passed, {len(RES) - sum(RES)} failed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
