"""Olympus World builder (night-worlds 2026-11-19): ONE giant city of everything, built from the repo's own data.

    python -X utf8 tools/world_build.py              writes tools/web_public/cities/world/world.json
    python -X utf8 tools/world_build.py --check      builds in memory, prints the counts, writes nothing

Owner 2026-11-19: "all cities should be in one giant city, just different areas for like 1) Kalshi, 2) NQ etc." The city sits on one
street grid round a central plaza (the Gate = Home). Its four districts are the four doors of olympus/doors.js:
  ZEUS Trading (NQ)  north   every trading app is a downtown tower; the live bots (one building per 2026 trade), the MFFU accounts (a
                             vault that fills toward its goal), then the learning quarters: the ZEUS Lab ideas, the LIT research, risk &
                             sizing, filters & timing, new ideas (2,000+ stored backtests of archive/, one building each) and the market data
  Kalshi             east    the Kalshi apps; the bets studied (strategies, markets, price bands, hypotheses); the K8 gold & silver legs; Kalshi write-ups
  More               south   research, Jarvis, your day, settings, the 3D worlds; the Data City quarters (one building per tested combo)
  Money              west    business, payouts, taxes, the fleet plan, household; the open decisions waiting for your yes
Every app of olympus/apps-list.js (and the door shortcuts that are their own page) is a building you can tap to open. A learning place
grows with its data: rejected = ruins, being tested = scaffolds, working = lit towers, live = gold crowns. Places are given street cells
in the order they were born, from the plaza outward, so a new place only ever appears at its quarter's edge (old ones keep their spot).
Read only; the hidden bots (dashboard_view.json via engine/hidden_bots.py) never appear; no account ids, owner names or e-mails.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
OUT = os.path.join(WEB, "cities", "world", "world.json")
CELL = 7.0          # one street cell (3 x 3 building lots) in world units (about metres x 10)
PLAZA = 26.0        # the central plaza's radius: no cells inside it
LOTS = 9            # building lots in one cell

# the six districts = the owner's six arenas (lead 2026-11-21: "one huge 3D city where each district is an arena"), clockwise from north
# (the first view looks north at ZEUS Trading). The four doors still feed them: the More door splits into Lab & Research and Life, the
# Money door gives its website apps to Websites, which also holds every concept site (one lit building each, no names).
DISTRICTS = [
    ("zeus", "ZEUS Trading · NQ", "Zlarior and ATLAS: accounts, live bots, trades, the Lab and every NQ idea tested", "#ffc65a"),
    ("kalshi", "Kalshi", "The Kalshi bot, its edges and the series studied. Paused: paper only", "#6fa8ff"),
    ("sites", "Websites", "The website business: every concept site built, lit by how warm its lead is", "#ff8f6b"),
    ("lab", "Lab & Research", "Research, the Data City, the 3D worlds and every study", "#c58cff"),
    ("life", "Life", "Jarvis, your day, the planner, the inbox and settings", "#7fd6c8"),
    ("money", "Money", "Business, payouts, taxes, the fleet plan and the household", "#5fe3a1"),
]
DNAME = {d[0]: d[1] for d in DISTRICTS}
# the quarters of each district in the order they are laid out: 'apps' and 'core' form the downtown band round the plaza, the
# learning quarters share the rest of the district's wedge (each its own slice, outward = newer)
QUARTERS = {
    "zeus": [("apps", "Apps"), ("core", "Live bots & accounts"), ("lab", "ZEUS Lab"), ("lit", "LIT research"), ("risk", "Risk & sizing"),
             ("filters", "Filters & timing"), ("ideas", "New ideas"), ("markets", "Market data")],
    "kalshi": [("apps", "Apps"), ("kbets", "Kalshi bets"), ("k8", "Gold & silver (K8)"), ("kresearch", "Kalshi research")],
    "sites": [("apps", "Apps"), ("concepts", "Concept sites")],
    "lab": [("apps", "Apps"), ("datacity", "Data City quarters"), ("mresearch", "Research notes")],
    "life": [("apps", "Apps")],
    "money": [("apps", "Apps"), ("decisions", "Open decisions"), ("money", "Money research")],
}
QNAME = {(d, q): n for d, qs in QUARTERS.items() for q, n in qs}
DOWNTOWN = ("apps", "core")
FAMILY_QUARTER = {"LIT research": "lit", "LIT headquarters": "lit", "baseline": "lit", "winrate": "lit", "bias": "lit", "targets": "lit",
                  "stops": "lit", "risk": "risk", "management": "risk", "filters": "filters", "timing": "filters", "sessions": "filters",
                  "ATLAS": "ideas", "other tests": "ideas", "other": "ideas", "research": "ideas", "data": "markets"}
FAMILY_HUE = {"LIT research": "#ffcf73", "LIT headquarters": "#ffe2a0", "baseline": "#ffffff", "winrate": "#c9ff7a", "bias": "#ffe86b",
              "targets": "#ff9ccf", "stops": "#ff8a7a", "risk": "#d18cff", "management": "#6fffd8", "filters": "#62e8ff", "timing": "#ffae5c",
              "sessions": "#7aa8ff", "ATLAS": "#59d6ff", "other tests": "#a9b8ff", "other": "#a9b8ff", "kalshi": "#7f9cff", "product": "#e7a8ff",
              "data": "#5fb8ff", "research": "#a9b8ff"}
# building states (the page's shader): 0 ruin (rejected), 1 scaffold (being tested / planned), 2 lit (neutral), 3 bright (adopted, a
# winner, promising), 4 gold crown (live, an app tower, a gold combo), 5 vault (an account: its lit share = how far to the goal)
RUIN, SCAFFOLD, LIT, BRIGHT, CROWN, VAULT = range(6)
# pages that are not an app of their own but a place the owner goes (paths from the site root)
EXTRA_PAGES = {
    "zeus": [("hub/zeus.html", "ZEUS", "ZEUS home", "What to open for trading: the PC, each account, today, the next entry windows", "#ffd27a"),
             ("business/mffu.html", "MFFU center", "Business · MFFU view", "Every MFFU account the MFFU way: balance, floor, rules, payouts", "#ffcf73"),
             ("business/lab.html", "ZEUS Lab page", "Business · Lab", "What the Lab tested last night, in plain words", "#7fe0ff"),
             ("business/week.html", "This week", "Business · Week", "The Friday review: each account's week in $", "#ffe2a0"),
             ("atlascity/", "Atlas City", "Atlas City", "ATLAS's strategy as a city", "#59d6ff")],
    "life": [("hub/doors.html", "The four doors", "Doors", "Every app, filed in its door", "#d79a5c")],
}
# where a door's app lives in the six districts (the More door splits; the website apps leave Money)
LIFE = {"planner", "jarvis", "compass", "helios", "herald", "stoa", "hestia", "inbox", "settings", "mind"}
SITES = {"agency"}


def district_of(door_id, app_id, href):
    if app_id in SITES or str(href).startswith("agency/"):
        return "sites"
    if door_id == "more":
        return "life" if (app_id in LIFE or str(href).startswith(("hub/", "planner/", "jarvis/"))) else "lab"
    return door_id if door_id in DNAME else "lab"


# ------------------------------------------------------------------------------------------------ small helpers
def load(rel, default=None):
    try:
        with open(rel if os.path.isabs(rel) else os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def read(rel):
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def usd(v, sign=False):
    if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
        return "-"
    r = round(v)
    s = "${:,.0f}".format(abs(r))
    return ("-" + s) if r < 0 else ("+" + s if sign and r > 0 else s)


def usd2(v):
    """small Kalshi amounts keep their cents"""
    if v is None or not isinstance(v, (int, float)):
        return "-"
    s = "${:,.2f}".format(abs(v))
    return ("-" + s) if v < 0 else s


def short(text, n=64):
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    t = re.sub(r"\s*\((?:20\d\d-\d\d-\d\d|tools/[^)]*|[^)]*\.md)\)", "", t)
    return t if len(t) <= n else t[: n - 1].rstrip(" ,;:-") + "…"


def iso(d):
    """'26-10-17' / '2026-10-17' / epoch seconds -> '2026-10-17' (None when unknown)"""
    if d is None or d == "":
        return None
    if isinstance(d, (int, float)):
        return _dt.datetime.fromtimestamp(d, _dt.timezone.utc).strftime("%Y-%m-%d")
    m = re.match(r"^(\d{2}|\d{4})-(\d\d)-(\d\d)", str(d))
    if not m:
        return None
    y = m.group(1)
    return f"{'20' + y if len(y) == 2 else y}-{m.group(2)}-{m.group(3)}"


def h255(v, lo, hi, log=False):
    """a value -> building height code 0..255 (clamped; log scale for counts)"""
    if v is None:
        return 40
    if log:
        v, lo, hi = math.log1p(max(0.0, v)), math.log1p(max(0.0, lo)), math.log1p(max(0.0, hi))
    if hi <= lo:
        return 128
    return int(max(0, min(255, round(255 * (v - lo) / (hi - lo)))))


def fnv(s):
    h = 2166136261
    for ch in str(s):
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")


def plain_status(s):
    return {"rejected": "Rejected", "parked": "Parked (not built yet)", "blocked": "Rejected for good (already tested)",
            "shadow": "Paper shadow (4 weeks on paper)", "adopted": "Adopted (live)", "passed": "Passed: waiting for your yes"}.get(s, str(s or "").capitalize())


def scrub(text, hide):
    """a hidden bot's name out of a line ("ATLAS and BLITZ" -> "ATLAS"): the owner keeps them off every page (dashboard_view.json)"""
    t = str(text or "")
    for h in hide:
        n = re.escape(h)
        t = re.sub(r"\s*(?:,|\band\b|&|\+|/)\s*" + n + r"\b", "", t, flags=re.I)
        t = re.sub(r"\b" + n + r"\s*(?:,|\band\b|&|\+|/)\s*", "", t, flags=re.I)
        t = re.sub(r"\b" + n + r"\b", "", t, flags=re.I)
    return re.sub(r"\s{2,}", " ", t).strip()


class World:
    def __init__(self, hide=()):
        self.places, self.feed, self.start, self.hide = [], [], None, tuple(hide)

    def add(self, pid, name, kind, district, quarter, state, line, facts, blds, born=None, hue=None, how="", href=None, fill=None, extra=None):
        assert district in DNAME and (district, quarter) in QNAME, (district, quarter)
        b = []
        for x in blds:
            d = x[2] if len(x) > 2 else None
            b.append((int(max(0, min(255, x[0]))), int(x[1]), d))
        sc = lambda t: scrub(t, self.hide)
        p = {"id": pid, "name": short(sc(name), 46), "kind": kind, "district": district, "quarter": quarter, "state": state, "line": short(sc(line), 120),
             "facts": [[short(sc(k), 28), short(sc(v), 40)] for k, v in facts if v not in (None, "", "-")][:5], "how": short(how, 140),
             "born": born, "hue": hue or dict((d[0], d[3]) for d in DISTRICTS)[district], "_b": b}
        if href:
            p["href"] = href
        if fill is not None:
            p["fill"] = int(fill)
        if extra:
            p.update({k: v for k, v in extra.items() if v is not None})
        self.places.append(p)
        return p

    def event(self, day, pid, text):
        if day:
            self.feed.append({"d": day, "id": pid, "text": short(scrub(text, self.hide), 110)})


# ------------------------------------------------------------------------------------------------ the sources
def hidden_bots():
    try:
        sys.path.insert(0, ROOT)
        from engine import hidden_bots as H  # the one switch (dashboard_view.json)
        return tuple(H.hidden())
    except Exception:
        v = load("dashboard_view.json", {}) or {}
        return tuple(str(x).lower() for x in (v.get("hidden_bots") if isinstance(v.get("hidden_bots"), list) else ["blitz"]))


def apps_list():
    m = re.search(r"var rows = (\[.*?\n  \]);", read("tools/web_public/olympus/apps-list.js"), re.S)
    try:
        return [r for r in json.loads(m.group(1)) if isinstance(r, dict) and r.get("id")] if m else []
    except ValueError:
        return []


def doors():
    """olympus/doors.js read as text (no node needed): [{id, title, items: [{label, greek, href, app}], ids}]"""
    src = read("tools/web_public/olympus/doors.js")
    out = []
    def q(n):                                           # a quoted JS string ('...' or "..."), its quote captured as group n
        return r"(['\"])((?:(?!\%d).)*)\%d" % (n, n)
    for m in re.finditer(r"\{ id: '(\w+)', title: '([^']+)'(.*?)ids: \[([^\]]*)\]", src, re.S):
        items = []
        for it in re.finditer(r"\{ label: " + q(1) + r", greek: " + q(3) + r", href: " + q(5) + r", app: " + q(7), m.group(3)):
            items.append({"label": it.group(2), "greek": it.group(4), "href": it.group(6), "app": it.group(8)})
        out.append({"id": m.group(1), "title": m.group(2), "items": items, "ids": re.findall(r"'(\w+)'", m.group(4))})
    return out


def apps(W):
    """every app and door page: one downtown tower each, in the district of its door"""
    rows = {r["id"]: r for r in apps_list()}
    seen_href = set()
    for door in doors():
        dd = door["id"]
        rank = 0
        for it in door["items"]:
            href = it["href"]
            app = rows.get(it["app"]) if it["app"] else None
            if href in seen_href:
                continue
            seen_href.add(href)
            d = district_of(dd, it["app"], href)
            purpose = app["purpose"] if app and app.get("path") == href else it["greek"]
            hue = app["colour"] if app else dict((x[0], x[3]) for x in DISTRICTS)[d]
            W.add("app:" + (it["app"] if app and app.get("path") == href else slug(href)), it["label"], "app", d, "apps", "app",
                  purpose if app and app.get("path") == href else f"{it['greek']}: a page of the {door['title']} door",
                  [["App", it["greek"]], ["Door", door["title"]]], [(200 - rank * 6, CROWN, None)], hue=hue, href=href, fill=0,
                  how="An app: tap Open to go there.", extra={"glyph": (app or {}).get("glyph"), "rank": rank, "shortcut": True})
            rank += 1
        d = "life" if dd == "more" else dd if dd in DNAME else "lab"
        for x, (href, name, greek, line, hue) in enumerate(EXTRA_PAGES.get(d, [])):
            if href in seen_href or not os.path.exists(os.path.join(WEB, href.split("#")[0].split("?")[0].rstrip("/") or ".")):
                continue
            seen_href.add(href)
            W.add("app:" + slug(href), name, "app", d, "apps", "app", line, [["Page", greek], ["Door", door["title"]]], [(214 if href == "hub/zeus.html" else 150, CROWN, None)],
                  hue=hue, href=href, fill=0, how="A page: tap Open to go there.", extra={"rank": -1 if href == "hub/zeus.html" else rank + x, "shortcut": href == "hub/zeus.html"})
        for aid in door["ids"]:
            a = rows.get(aid)
            if not a or a.get("path") is None:
                continue
            href = a["path"] or "index.html"
            if href in seen_href:
                continue
            seen_href.add(href)
            d = district_of(dd, aid, href)
            W.add("app:" + aid, a["name"], "app", d, "apps", "app", a.get("purpose") or a["name"], [["App", a["name"]], ["Door", door["title"]]],
                  [(110 + fnv(aid) % 60, CROWN, None)], hue=a.get("colour"), href=href, fill=0, how="An app: tap Open to go there.",
                  extra={"glyph": a.get("glyph"), "rank": 50 + len(seen_href)})


def trades_stats(rows):
    rows = [r for r in rows if isinstance(r.get("usd"), (int, float))]
    if not rows:
        return None
    days = sorted(r["day"] for r in rows if r.get("day"))
    win = [r["usd"] for r in rows if r["usd"] > 0]
    span = max(1.0, (_dt.date.fromisoformat(days[-1]) - _dt.date.fromisoformat(days[0])).days + 1) if days else 30.0
    return {"n": len(rows), "tpw": len(rows) / span * 7, "win": 100.0 * len(win) / len(rows)}


def core(W, hide):
    trades = load("tools/web_public/trading/trades.json", {}) or {}
    edge = (load("tools/web_public/edge.json", {}) or {}).get("bots") or {}
    rows = [t for t in trades.get("trades") or [] if isinstance(t, dict)]
    ref = trades.get("lit_ref") or {}
    base = {}
    for r in (load("tools/web_public/archive/index.json", {}) or {}).get("runs") or []:
        if isinstance(r, list) and len(r) > 8 and r[0] == "atlas_base" and isinstance(r[8], list) and len(r[8]) >= 5:
            base["atlas"] = r[8]
    for key, name, hue, label in (("lit", "Zlarior", "#ffd27a", "LIT"), ("atlas", "ATLAS", "#59d6ff", "ATLAS"), ("blitz", "BLITZ", "#c08cff", "BLITZ")):
        if key in hide:
            continue
        mine = [t for t in rows if str(t.get("bot", "")).upper() == label]
        if not mine and key == "blitz":
            continue
        bt = [t for t in mine if t.get("src") == "backtest"]
        lv = [t for t in mine if t.get("src") in ("live", "paper")]
        big = max([abs(t.get("usd") or 0) for t in mine] + [1])
        blds = [(h255(abs(t.get("usd") or 0), 0, big) if (t.get("usd") or 0) > 0 else 20 + h255(abs(t.get("usd") or 0), 0, big) // 4,
                 BRIGHT if (t.get("usd") or 0) > 0 else LIT) for t in bt]
        blds += [(220, CROWN) for _ in lv]
        e = edge.get(key) or {}
        facts = []
        if key == "lit" and ref.get("h1"):
            h1, h2 = ref["h1"], ref.get("h2") or {}
            facts += [["2026 Jan-Jun (picked)", f"{usd(h1.get('per_month'))} a month, PF {h1.get('pf')}"],
                      ["2026 Jul-Oct (checked)", f"{usd(h2.get('per_month'))} a month, PF {h2.get('pf')}"],
                      ["Trades a week", f"{h1.get('per_week')} (Jan-Jun)"], ["Worst drop", usd(h1.get("max_dd"))]]
        elif base.get(key):
            b = base[key]
            facts += [["2026 backtest (eval size)", f"{usd(b[4])} a month, PF {b[2]}"], ["Trades a week", f"{b[1]}"]]
        else:
            st = trades_stats(bt)
            if st:
                facts += [["Trades a week (2026)", f"{st['tpw']:.1f}"], ["Winners (2026)", f"{st['win']:.0f}%"]]
        if e:
            facts.append(["Last 40 sessions", f"{usd(e.get('usd_month'))} a month, light {str(e.get('light', '-')).title()}"])
        line = {"lit": "Zlarior trades NQ on your Builder 50K eval with the LIT strategy (a sweep, then the target).",
                "atlas": "ATLAS trades NQ on your funded Builder 25K (EMA + MACD + support and resistance).",
                "blitz": "BLITZ runs on paper only."}[key]
        W.add("bot:" + key, name, "bot", "zeus", "core", "live", line, facts, blds, hue=hue, fill=12,
              how="Each building is one 2026 trade: tall and lit = a winner (taller = more $), low and dim = a loser; gold crowns = live trades.",
              extra={"bot": key, "light": e.get("light")})
        if e.get("light"):
            W.event(iso(e.get("to")), "bot:" + key, f"{name}: edge light {str(e['light']).title()}, PF {e.get('pf')} over the last {e.get('sessions')} sessions")
    plan = load("tools/web_public/business/accounts.json", {}) or {}
    board = load("tools/web_public/board/board.json", {}) or {}
    live = {a.get("key"): a for a in board.get("accounts") or [] if isinstance(a, dict)}
    for a in plan.get("accounts") or []:
        if not isinstance(a, dict) or not a.get("key") or "blitz" in str(a.get("key")).lower():
            continue
        k, nm = a["key"], str(a.get("name") or "")
        lv = live.get(k) or {}
        bal = lv.get("balance") if isinstance(lv.get("balance"), (int, float)) else None
        # olympus2 2026-11-20: accounts.json (Claude keeps it, the newest word) beats the Board's copy for the stage once it says funded
        # (the Board still said ATLAS "passed"); "planned" = the plan says waiting / buying, or the Board has it as plan-only with no balance
        stage = "funded" if str(a.get("stage")) == "funded" else str(lv.get("stage") or a.get("stage") or "eval")
        waiting = str(a.get("status")) in ("waiting", "buying") or (bool(lv.get("plan_only")) and bal is None and str(a.get("status")) != "live")
        size = 50000 if "50K" in (nm + " " + str(a.get("plan", ""))).upper() else 25000
        start, goal = size, size + (3000 if size == 50000 else 1500)
        if stage == "funded":
            goal = start + 2100                     # the payout coach: ask the full $1,000 once the balance is start + $2,100
        prog = None if bal is None else max(0.0, min(1.0, (bal - start) / max(1.0, goal - start)))
        bot = "atlas" if "atlas" in k.lower() or nm.upper().startswith("ATLAS") else "lit"
        label = re.sub(r"\s*\((?:next|funded)\)", "", nm).strip()
        if not re.search(r"\d+K", label, re.I):
            label += f" {size // 1000}K"
        title = label + (" (planned)" if waiting else " (funded)" if stage == "funded" else " (passed)" if stage == "passed" else " (eval)")
        facts = []
        if bal is not None:
            facts.append(["Balance", usd(bal)])
        if stage == "funded":
            facts.append(["Payout ask at", usd(goal)])
        elif lv.get("to_pass") is not None:
            facts.append(["To pass", usd(lv.get("to_pass"))])
        if lv.get("room") is not None:
            facts.append(["Room above the floor", usd(lv.get("room"))])
        if a.get("usd_month"):
            facts.append(["Plan (estimate)", str(a["usd_month"]) + " a month"])
        line = (f"{a.get('plan') or 'An MFFU account'}: not bought yet. " + short(a.get("next"), 90)) if waiting else \
            f"{a.get('plan') or 'MFFU account'}, traded by {'ATLAS' if bot == 'atlas' else 'Zlarior'}. Stage: {stage}."
        blds = [(150 if size == 25000 else 215, SCAFFOLD if waiting else VAULT, None)] + [(40 + 12 * i, SCAFFOLD if waiting else LIT, None) for i in range(4)]
        W.add("acct:" + k, title, "account", "zeus", "core", "planned" if waiting else "live", line, facts, blds,
              hue="#59d6ff" if bot == "atlas" else "#ffd27a", fill=4,
              how=("The tall vault fills with light as the account nears its goal (the pass target, or the payout ask when funded)." if not waiting
                   else "Scaffolding: a planned account, not bought yet."),
              extra={"bot": bot, "progress": None if prog is None else round(prog, 3), "stage": stage})


def lab(W):
    L = load("tools/web_public/business/lab.json", {}) or {}
    ran = iso(str(L.get("built") or "")[:10])
    for r in L.get("rows") or []:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        st = str(r.get("status") or "")
        state = {"rejected": "ruin", "blocked": "ruin", "parked": "planned", "shadow": "growing", "passed": "growing", "adopted": "bright"}.get(st, "testing")
        by = r.get("usd_month_by") or {}
        blds = []
        for per in ("H1", "H2", "2021-25"):
            v = by.get(per)
            if v is None:
                continue
            code = RUIN if state == "ruin" else SCAFFOLD if state in ("planned", "testing") else BRIGHT if v > 0 else LIT
            blds.append((30 + h255(abs(v), 0, 1500) * 3 // 4, code, None))
        if not blds:
            blds = [(60, SCAFFOLD if state != "ruin" else RUIN, None), (35, SCAFFOLD if state != "ruin" else RUIN, None)]
        bot = str(r.get("bot") or "")
        who = r.get("who") or {"lit": "Zlarior", "atlas": "ATLAS"}.get(bot, bot.title())
        facts = [["Verdict", plain_status(st)]]
        for per, lab_ in (("H1", "Jan-Jun 2026 (pick)"), ("H2", "Jul-Oct 2026 (check)"), ("2021-25", "2021-25")):
            if by.get(per) is not None:
                facts.append([lab_, usd(by[per], True) + " a month vs today"])
        why = short(r.get("why") or r.get("needs") or "", 120)
        district, quarter = ("kalshi", "kresearch") if bot == "kalshi" else ("zeus", "lab")
        W.add("lab:" + r["id"], r.get("title") or r["id"], "lab", district, quarter, state, f"{who} idea: {short(r.get('what') or r.get('title'), 110)}",
              facts, blds, born=iso(r.get("registered")),
              how=("Ruins: tested on the real backtests and it did not pay. " if state == "ruin" else
                   "Scaffolds: written down, waiting for its test. " if state in ("planned", "testing") else
                   "Lit towers: it passed and is on paper. ") + "One building per test period, taller = more $ changed.",
              fill=3, extra={"why": why or None})
        W.event(ran if st != "parked" else iso(r.get("registered")), "lab:" + r["id"], f"ZEUS Lab: {plain_status(st).lower()}: {short(r.get('title'), 70)}")
    for r in L.get("forever") or []:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        m = re.search(r"(20\d\d-\d\d-\d\d)", str(r.get("source") or ""))
        W.add("lab:" + r["id"], r.get("title") or r["id"], "lab", "zeus", "lab", "ruin", "Rejected for good: tested before and failed, so the Lab never pays to re-test it.",
              [["Verdict", "Rejected for good"], ["Where it was tested", short(r.get("source"), 40)]], [(70, RUIN, None), (45, RUIN, None)],
              born=m.group(1) if m else None, how="An old ruin: kept so the same idea is never paid for twice.", fill=2)


def research(W, hide):
    A = load("tools/web_public/archive/index.json", {}) or {}
    runs = list(A.get("runs") or [])
    for p in sorted(glob.glob(os.path.join(WEB, "archive", "runs-*.json"))):
        runs += (load(p, {}) or {}).get("runs") or []
    writeups = [w for w in A.get("writeups") or [] if isinstance(w, dict) and w.get("slug")]
    by_slug = {w["slug"]: w for w in writeups}
    groups = {}
    for r in runs:
        if not isinstance(r, list) or len(r) < 12:
            continue
        if any(h in (str(r[0]) + " " + str(r[1]) + " " + str(r[10])).lower() for h in hide):
            continue
        groups.setdefault(r[10] or ("fam:" + str(r[2])), []).append(r)
    used = set()
    pm_all = [r[8][4] for g in groups.values() for r in g if isinstance(r[8], list) and len(r[8]) >= 5 and isinstance(r[8][4], (int, float))]
    top = max(pm_all) if pm_all else 5000
    for key, rs in sorted(groups.items()):
        fam = max(sorted(set(r[2] for r in rs)), key=lambda f: sum(1 for r in rs if r[2] == f))
        w = None
        if not key.startswith("fam:"):
            w = by_slug.get(key) or next((by_slug[s] for s in sorted(by_slug) if s.startswith(key)), None)
        if w:
            used.add(w["slug"])
        district, quarter = ("kalshi", "kresearch") if fam == "kalshi" else ("money", "money") if fam == "product" else ("zeus", FAMILY_QUARTER.get(fam, "ideas"))
        name = short(re.split(r"\s[-–(]\s?", (w or {}).get("title") or "")[0], 40) if w else f"{fam[:1].upper() + fam[1:]}: more tests"
        n_ad = sum(1 for r in rs if r[4] == 0)
        n_rej = sum(1 for r in rs if r[4] == 1)
        n_open = sum(1 for r in rs if r[4] == 2)
        blds = []
        for r in sorted(rs, key=lambda r: (r[6], r[0])):
            m = r[8] if isinstance(r[8], list) and len(r[8]) >= 5 else None
            pmv = m[4] if m and isinstance(m[4], (int, float)) else None
            code = BRIGHT if r[4] == 0 else (LIT if r[5] in ("promising", "adopt-candidate") else SCAFFOLD) if r[4] == 2 else RUIN
            hh = h255(max(0.0, pmv or 0.0), 0, top) if code != RUIN else 25 + h255(max(0.0, pmv or 0.0), 0, top) // 3
            blds.append((max(18, hh), code, iso(r[6])))
        best = max((r for r in rs if isinstance(r[8], list) and len(r[8]) >= 5 and isinstance(r[8][4], (int, float))), key=lambda r: r[8][4], default=None)
        facts = [["Backtests", f"{len(rs)}: {n_ad} adopted, {n_rej} rejected, {n_open} open"]]
        if best:
            facts += [["Best 2026 result", f"{usd(best[8][4])} a month, PF {best[8][2]}"], ["Best idea", short(best[1], 40)]]
        state = "bright" if n_ad else "growing" if n_open > n_rej else "ruin" if n_rej and not n_open else "testing"
        born = min((b[2] for b in blds if b[2]), default=None)
        pid = "res:" + key.replace("fam:", "fam-")
        W.add(pid, name or key, "research", district, quarter, state,
              short((w or {}).get("summary") or (w or {}).get("title") or f"Stored {fam} backtests with no write-up of their own.", 120), facts, blds,
              born=born or iso((w or {}).get("date")), hue=FAMILY_HUE.get(fam),
              how="One building per stored backtest: bright = adopted, lit = promising, scaffold = still open, ruin = rejected. Taller = more $ a month in 2026.",
              fill=1)
        W.event(iso((w or {}).get("date")) or born, pid, f"Research: {len(rs)} backtests in '{short(name, 40)}': {n_ad} adopted, {n_rej} rejected")
    for w in writeups:                        # write-ups with no stored run: a one-tower place (a finding, a rejected idea, a note)
        if w["slug"] in used or any(h in (w["slug"] + " " + str(w.get("title"))).lower() for h in hide):
            continue
        st, fam = str(w.get("status") or "info"), str(w.get("family") or "other")
        district, quarter = ("kalshi", "kresearch") if fam == "kalshi" else ("money", "money") if fam == "product" else ("zeus", FAMILY_QUARTER.get(fam, "ideas"))
        state = {"rejected": "ruin", "promising": "growing", "finding": "bright"}.get(st, "testing")
        code = {"ruin": RUIN, "growing": LIT, "bright": BRIGHT}.get(state, SCAFFOLD)
        W.add("doc:" + w["slug"], re.split(r"\s[-–(]\s?", str(w.get("title") or w["slug"]))[0], "research", district, quarter, state,
              short(w.get("summary") or w.get("title"), 120),
              [["Write-up", {"rejected": "Rejected", "promising": "Promising", "finding": "A finding"}.get(st, "A note")], ["Date", iso(w.get("date")) or "-"]],
              [(90 if code != RUIN else 50, code, iso(w.get("date"))), (50, code if code != BRIGHT else LIT, iso(w.get("date")))], born=iso(w.get("date")),
              hue=FAMILY_HUE.get(fam), how="A write-up with no stored backtest: one tower (lit = a finding, ruin = rejected).", fill=2)
        W.event(iso(w.get("date")), "doc:" + w["slug"], ("Rejected: " if st == "rejected" else "Write-up: ") + short(w.get("title"), 80))
    return A


def markets(W, A):
    groups = {}
    for d in (A or {}).get("datasets") or []:
        if isinstance(d, dict) and d.get("name"):
            sym = re.split(r"[_.]", d["name"])[0].upper()
            groups.setdefault({"TV": "MNQ", "EVENTS": "NEWS"}.get(sym, sym), []).append(d)
    names = {"NQ": ("NQ data", "The market both bots trade: 1-minute to daily bars; every backtest runs on it."),
             "ES": ("ES data", "The S&P futures: used for ES-NQ divergences and the regime filters."),
             "VIX": ("VIX data", "The fear index: it sets Zlarior's target band."), "VXN": ("VXN data", "The Nasdaq fear index."),
             "GEX": ("GEX data", "Dealer gamma by day: tested as a size rule."), "CBOE": ("CBOE volatility set", "VIX9D, VIX3M, VVIX and SKEW."),
             "MNQ": ("MNQ data", "The micro contract the evals trade."), "NEWS": ("News calendar", "The news days the bots stand aside for.")}
    for sym, ds in sorted(groups.items(), key=lambda kv: -sum(int(d.get("rows") or 0) for d in kv[1])):
        rows = sum(int(d.get("rows") or 0) for d in ds)
        nm, line = names.get(sym, (sym + " data", "A data file the bots learn from."))
        W.add("mkt:" + sym.lower(), nm, "market", "zeus", "markets", "data", line,
              [["Data", f"{rows:,} bars in {len(ds)} file{'s' if len(ds) > 1 else ''}"], ["From", min((d.get('first') or '9') for d in ds)[:10]],
               ["To", max((d.get('last') or '') for d in ds)[:10]]],
              [(h255(int(d.get("rows") or 1), 10, 900000, log=True), LIT, None) for d in ds],
              hue={"NQ": "#5fb8ff", "ES": "#6fe39a", "VIX": "#c78cff", "VXN": "#b07bff", "GEX": "#ffae5c"}.get(sym, "#8fb4ff"),
              how="One tower per data file, taller = more bars. Futures data only (never Yahoo, never CFD).", fill=4)
    have = set(os.path.basename(p).split("_")[0].upper() for p in glob.glob(os.path.join(ROOT, "data", "*_1m.csv")))
    for sym, nm in (("MGC", "Micro gold (MGC)"), ("MCL", "Micro crude (MCL)"), ("M2K", "Micro Russell (M2K)")):
        ready = sym in have
        W.add("mkt:" + sym.lower(), nm, "market", "zeus", "markets", "data" if ready else "planned",
              "Imported: ready for the LIT test." if ready else "Zlarior is built to test this market once its NinjaTrader history is exported.",
              [["Status", "Data in" if ready else "Ready, no data yet"]], [(70, LIT if ready else SCAFFOLD, None), (40, SCAFFOLD, None)],
              hue="#ffd27a" if sym == "MGC" else "#ff8a6a" if sym == "MCL" else "#9fe08a",
              how="Scaffolding until the data arrives (one export line per market, docs/OTHER_MARKETS.md).", fill=2)


def datacity(W):
    D = load("tools/web_public/datacity/city.json", {}) or {}
    blds = [b for b in D.get("buildings") or [] if isinstance(b, dict)]
    emax = max([abs(b.get("e") or 0) for b in blds] + [1])
    built = iso(str(D.get("built") or "")[:10])
    code = {"gold": CROWN, "green": BRIGHT, "amber": SCAFFOLD, "grey": RUIN}
    for s in D.get("sections") or []:
        if not isinstance(s, dict) or not s.get("key"):
            continue
        mine = [b for b in blds if b.get("d") == s["key"]]
        best = max(mine, key=lambda b: b.get("e") or -1e9, default=None)
        facts = [["Combos tried", f"{int(s.get('tried') or 0):,}"], ["Tested enough", f"{int(s.get('tested') or 0):,}"],
                 ["Pass the luck guard", str(s.get("fdr") or 0)], ["Gold", str(s.get("gold") or 0)]]
        if best and best.get("e") is not None:
            facts.append(["Best", f"{usd(best['e'], True)} a trade per micro"])
        n_gold, n_green = sum(1 for b in mine if b.get("cls") == "gold"), sum(1 for b in mine if b.get("cls") == "green")
        W.add("dc:" + s["key"], str(s.get("name") or s["key"]).title(), "datacity", "lab", "datacity", "bright" if n_gold else "growing" if n_green else "testing",
              short(s.get("blurb"), 120), facts, [(max(20, h255(abs(b.get("e") or 0), 0, emax)), code.get(b.get("cls"), LIT), None) for b in mine],
              hue=str(s.get("color") or "#4fe0d0"), fill=2,
              how="One building per tested combo: gold spire = passed every guard, bright = it made money, scaffold = maybe, dark = no edge.")
        if built:
            W.event(built, "dc:" + s["key"], f"Data City: {int(s.get('tested') or 0):,} {str(s.get('name') or '').lower()} combos tested, {s.get('gold') or 0} gold")


def kalshi(W):
    K = load("tools/web_public/kalshicity/learned.json", {}) or {}
    E = load("tools/web_public/kalshicity/edges.json", {}) or {}
    H = load("tools/web_public/kalshicity/hypotheses.json", {}) or {}
    log = load("tools/web_public/kalshicity/learning_log.json", {}) or {}
    edges = [e for e in E.get("edges") or [] if isinstance(e, dict) and isinstance(e.get("dims"), list) and len(e["dims"]) >= 3]
    nmax = max([int(e.get("n") or 0) for e in edges] + [10])
    t0 = iso(E.get("day") or E.get("t"))

    def ebld(e):
        ev = e.get("ev") or 0
        return (max(24, h255(int(e.get("n") or 0), 1, nmax, log=True)), BRIGHT if ev > 0 and e.get("sig") else LIT if ev > 0 else RUIN, None)
    for s in K.get("strategies") or []:
        if not isinstance(s, dict) or not s.get("name"):
            continue
        pnl = s.get("pnl")
        state = "ruin" if (pnl or 0) < 0 and not s.get("low_n") else "testing" if s.get("low_n") else "growing"
        W.add("ks:" + slug(s["name"]), s["name"], "kalshi", "kalshi", "kbets", state, f"A Kalshi strategy the bot ran ({s.get('mode') or 'retired'}). Kalshi is paused for now.",
              [["Bets", f"{int(s.get('n') or 0):,}"], ["Won", f"{100 * (s.get('win_rate') or 0):.1f}%"], ["Net", usd2(pnl)], ["Verdict", short(s.get("verdict"), 40)]],
              [ebld(e) for e in edges if e["dims"][0] == s["name"]] or [(40, RUIN if state == "ruin" else SCAFFOLD, None)],
              born=t0, hue="#8fa8ff", how="One building per measured edge: lit = it paid, ruin = it lost money.", fill=3)
    for c in K.get("categories") or []:
        if not isinstance(c, dict) or not c.get("label"):
            continue
        pnl = c.get("pnl")
        mine = [e for e in edges if c["label"] in e["dims"][1:3]]
        W.add("km:" + slug(c["label"]), c["label"] + " markets", "kalshi", "kalshi", "kbets", "growing" if (pnl or 0) > 0 else "ruin" if not c.get("low_n") else "testing",
              f"The Kalshi {c['label']} markets the bot bet on.",
              [["Bets", f"{int(c.get('n') or 0):,}"], ["Won", f"{100 * (c.get('win_rate') or 0):.1f}%"], ["Net", usd2(pnl)], ["Verdict", short(c.get("verdict"), 40)]],
              [ebld(e) for e in mine] or [(max(24, h255(int(c.get("n") or 0), 1, nmax, log=True)), LIT if (pnl or 0) > 0 else RUIN, None)],
              born=t0, hue="#7f9cff", how="Lit = the bets in these markets paid; ruin = they lost.", fill=3)
    for kind, (nm, line) in {"band": ("Price bands", "What the bot paid for a contract (90-95c was the leak)."), "hour": ("Hours", "When the bot bet."),
                             "side": ("Yes or no", "Which side the bot bought.")}.items():
        mine = [e for e in edges if e.get("kind") == kind]
        if mine:
            net = sum(e.get("pnl") or 0 for e in mine)
            W.add("kb:" + kind, nm, "kalshi", "kalshi", "kbets", "growing" if net > 0 else "ruin", line,
                  [["Edges", str(len(mine))], ["Net", usd2(net)], ["Best", short(max(mine, key=lambda e: e.get("pnl") or 0).get("label"), 30)]],
                  [ebld(e) for e in mine], born=t0, hue="#a99cff", how="One building per band: lit = it paid, ruin = it lost.", fill=2)
    for h in H.get("hyps") or []:
        if isinstance(h, dict) and h.get("id"):
            word = str(h.get("word") or "")
            state = "growing" if word == "PROMISING" else "testing"
            W.add("kh:" + h["id"], h.get("name") or h["id"], "kalshi", "kalshi", "kbets", state, short(h.get("rule") or h.get("idea"), 120),
                  [["Status", f"{str(h.get('status') or '').title()} ({word.lower()})"], ["Bets needed", str(h.get("needed") or "-")]],
                  [(80 if state == "growing" else 50, LIT if state == "growing" else SCAFFOLD, None), (45, SCAFFOLD, None)], born=t0, hue="#9ab0ff",
                  how="A Kalshi rule checked on paper: lit = it holds so far, scaffold = still collecting.", fill=2)
    K8 = load("research/kalshi_edge_K8/results.json", {}) or {}
    stake = K8.get("stake_$") or 15
    split = K8.get("split") or {}
    for leg, v in sorted((K8.get("legs") or {}).items()):
        tape = (v or {}).get("tape") or {}
        tr, te = tape.get("train") or {}, tape.get("test") or {}
        if not tr.get("n") and not te.get("n"):
            continue
        good = (te.get("net_$") or 0) > 0 and (tr.get("net_$") or 0) > 0
        blds = [(30 + h255(max(0, x.get("usd_per_month") or 0), 0, 200), BRIGHT if (x.get("net_$") or 0) > 0 else RUIN, None) for x in (tr, te) if x.get("n")]
        W.add("k8:" + slug(leg), v.get("label") or leg, "kalshi", "kalshi", "k8", "growing" if good else "ruin",
              "A Kalshi 15-minute commodity bet at a fixed clock time (research only, paper rule; Kalshi is paused).",
              [["Learned on", f"{tr.get('n') or 0} bets, {usd2(tr.get('net_$'))} at ${stake:g} a bet"],
               ["Checked on", f"{te.get('n') or 0} bets, {usd2(te.get('net_$'))}" + (f" ({(split.get('test') or ['', ''])[0][5:]} to {(split.get('test') or ['', ''])[1][5:]})" if split.get('test') else "")],
               ["$ a month (checked)", usd(te.get("usd_per_month"))], ["Won (checked)", f"{100 * (te.get('win_rate') or 0):.0f}%"]],
              blds, born=(split.get("test") or [None, None])[1] if split.get("test") else None, hue="#ffd27a" if "gold" in leg.lower() else "#d6e2ff",
              how="Two buildings: the months it was learned on and the months it was checked on; lit = it made money there.", fill=2)
    if K8.get("legs"):
        W.event((split.get("test") or [None, "2026-11-19"])[1], None, "Kalshi K8: gold & silver 15-minute legs checked on paper; Kalshi stays paused")
    for e in (log.get("entries") or [])[-12:]:
        if isinstance(e, dict) and e.get("d"):
            W.event(iso(e["d"]), None, "Kalshi: " + short(e.get("text"), 90))


NICHE = {"food": "Restaurants & cafes", "retail": "Shops", "beauty": "Salons & beauty", "health": "Health & care", "auto": "Car repair",
         "gym": "Gyms & fitness", "services": "Services", "trades": "Trades", "pro": "Professional offices"}


def concepts(W):
    """the Websites district: one block per trade, one building per concept site (counts and lead warmth only, never a business name):
    hot = a bright tower, warm = lit, cold = low and dim, not ready yet = scaffolding"""
    data = load("tools/web_public/agency/factory/sites.json", {}) or {}
    sites = [x for x in (data.get("sites") or []) if isinstance(x, dict)]
    by = {}
    for x in sites:
        by.setdefault(str(x.get("niche") or "services"), []).append(x)
    for niche, xs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        hot = sum(1 for x in xs if x.get("heat") == "hot")
        warm = sum(1 for x in xs if x.get("heat") == "warm")
        ready = sum(1 for x in xs if x.get("ready"))
        blds = []
        for x in sorted(xs, key=lambda x: ({"hot": 0, "warm": 1}.get(x.get("heat"), 2), str(x.get("id")))):
            heat = x.get("heat")
            if not x.get("ready"):
                blds.append((60, SCAFFOLD, None))
            elif heat == "hot":
                blds.append((200 + fnv(str(x.get("id"))) % 50, BRIGHT, None))
            elif heat == "warm":
                blds.append((140 + fnv(str(x.get("id"))) % 40, LIT, None))
            else:
                blds.append((70 + fnv(str(x.get("id"))) % 40, LIT, None))
        name = NICHE.get(niche, niche.title())
        W.add("sites:" + slug(niche), name, "sites", "sites", "concepts", "bright" if hot else "growing",
              f"{len(xs)} concept sites for {name.lower()}: {hot} hot, {warm} warm leads, {ready} ready to show",
              [["Concept sites", str(len(xs))], ["Hot leads", str(hot)], ["Warm leads", str(warm)], ["Ready", str(ready)]], blds,
              href="agency/", how="A block of the website business: one building per concept site. Taller and brighter = a warmer lead.")


# ------------------------------------------------------------------------------------------------ the Research Hub (lead 2026-11-21)
# research/hub.json (the Research Hub session): [{id, title, family, status live|lead|rejected|decide, usd_month, date, summary, url}].
# The Lab & Research district becomes the 3D hub: each family a street (its own slice of the district), live strategies tall bright
# towers (height = the real $ a month), open leads lit under scaffolding, rejected ideas a field of ruins (tap: the one-line why + $),
# Decide cards beacons that pulse until answered. No hub.json = nothing here (never example data in the owner's city).
HUB_STATE = {"live": ("live", CROWN), "lead": ("testing", SCAFFOLD), "rejected": ("ruin", RUIN), "decide": ("decide", BRIGHT)}
HUB_WORD = {"live": "Live", "lead": "Open lead", "rejected": "Rejected", "decide": "Decide"}
HUB_FAMILIES = 8
LAB_QUARTERS = list(QUARTERS["lab"])


def hub_items(path=None):
    """the hub's rows (a list), from research/hub.json (a list, or {items: [...]}) or the given path; [] when there is none"""
    data = load(path or "tools/web_public/research/hub.json", None)
    rows = data.get("items") or data.get("hub") or [] if isinstance(data, dict) else data if isinstance(data, list) else []
    return [r for r in rows if isinstance(r, dict) and r.get("id") and r.get("title")]


def hub_usd(r):
    for k in ("usd_month", "$/month", "usd", "per_month", "month_usd"):
        v = r.get(k)
        try:
            if v is not None and v != "":
                return float(str(v).replace("$", "").replace(",", ""))
        except ValueError:
            continue
    return None


def research_hub(W, path=None):
    QUARTERS["lab"] = list(LAB_QUARTERS)                    # idempotent: the family streets are rebuilt every time
    rows = hub_items(path)
    if not rows:
        return 0
    fams = {}
    for r in rows:
        fams[str(r.get("family") or "Other").strip() or "Other"] = fams.get(str(r.get("family") or "Other").strip() or "Other", 0) + 1
    top = [f for f, _ in sorted(fams.items(), key=lambda kv: (-kv[1], kv[0]))[:HUB_FAMILIES]]
    for f in top + (["Other"] if len(fams) > len(top) and "Other" not in top else []):
        q = "rh-" + slug(f)
        if (("lab", q)) not in QNAME:
            QNAME[("lab", q)] = f
        QUARTERS["lab"].append((q, f))
    top_usd = max([abs(hub_usd(r) or 0) for r in rows] + [1.0])
    for r in rows:
        fam = str(r.get("family") or "Other").strip() or "Other"
        fam = fam if fam in top else "Other"
        st = str(r.get("status") or "lead").lower()
        state, bstate = HUB_STATE.get(st, HUB_STATE["lead"])
        pm = hub_usd(r)
        h = h255(max(0.0, pm or 0), 0, top_usd, log=True) if st == "live" else 90 if st == "decide" else 70 if st == "lead" else 50
        if st == "live":
            h = max(120, h)
        money = (usd(pm) + " a month") if pm is not None else None
        summ = short(str(r.get("summary") or ""), 120)
        url = str(r.get("url") or "").lstrip("/") or None
        if url and re.match(r"^[a-z]+:", url):
            url = None                                        # the site's own pages only
        blds = [(h, bstate, r.get("date"))] + [(max(20, h // 3), bstate if st != "live" else LIT, r.get("date")) for _ in range(2 if st == "live" else 1)]
        W.add("hub:" + str(r["id"]), str(r["title"]), "hub", "lab", "rh-" + slug(fam), state, summ or HUB_WORD.get(st, st),
              [["Status", HUB_WORD.get(st, st)], ["$ a month", money], ["Family", fam], ["Date", str(r.get("date") or "")[:10]]], blds,
              born=(str(r.get("date"))[:10] if r.get("date") else None), href=url,
              how="A Research Hub entry: tap Read for the write-up.",
              extra={"why": (summ + (" (" + money + ")" if money else "")) if st == "rejected" else None, "hub": st, "usd": pm})
    return len(rows)


def decisions(W):
    D = load("tools/web_public/business/decisions.json", {}) or {}
    for x in D.get("items") or []:
        if not isinstance(x, dict) or not x.get("id"):
            continue
        open_ = str(x.get("status") or "open") == "open"
        if not open_:                                    # olympus2: an answered decision is no longer a place (the Board keeps its history)
            continue
        W.add("dec:" + x["id"], short(x.get("question"), 46), "decision", "money", "decisions", "planned" if open_ else "bright",
              short(x.get("question"), 120), [["Why", short(x.get("why"), 40)], ["What it changes", short(x.get("impact"), 40)],
                                              ["Status", "Waiting for your yes / no" if open_ else str(x.get("status")).title()]],
              [(90, SCAFFOLD if open_ else BRIGHT, iso(x.get("added"))), (60, SCAFFOLD if open_ else LIT, iso(x.get("added")))], born=iso(x.get("added")),
              hue="#5fe3a1", href="board/", how="A decision waiting for you: scaffolding until you answer it on the Board.", fill=2)
        W.event(iso(x.get("added")), "dec:" + x["id"], "Decision waiting: " + short(x.get("question"), 90))


# ------------------------------------------------------------------------------------------------ the city plan
def bucket(n, base=8.0):
    """sizes in 25% steps: the city plan only moves when a quarter (or a district) has really grown, not for every new place"""
    n = max(float(n), base)
    return base * 1.25 ** math.ceil(math.log(n / base) / math.log(1.25) - 1e-9)


def need_cells(p):
    if p["kind"] == "app":
        return 1
    return max(1, math.ceil((len(p["_b"]) + p.get("fill", 2)) / LOTS))


def angle_of(x, z):
    return math.atan2(z, x)


def in_arc(a, a0, a1):
    """a inside the arc from a0 going counter-clockwise (increasing angle) to a1"""
    span = (a1 - a0) % (2 * math.pi)
    return (a - a0) % (2 * math.pi) <= span + 1e-9


def plan_city(W):
    start = min((p["born"] for p in W.places if p["born"]), default=None)
    W.start = start
    for p in W.places:
        p["born"] = p["born"] or start
    by_q = {}
    for p in W.places:
        by_q.setdefault((p["district"], p["quarter"]), []).append(p)
    need = {k: sum(need_cells(p) for p in v) for k, v in by_q.items()}
    dneed = {d: bucket(sum(n for (dd, _), n in need.items() if dd == d), 24.0) for d, *_ in DISTRICTS}
    tot = sum(dneed.values()) or 1
    # the wedges: proportional to need, at least 46 degrees each; ZEUS Trading centred on north (-90 degrees: the first view looks north)
    share = {d: max(math.radians(46), 2 * math.pi * dneed[d] / tot) for d, *_ in DISTRICTS}
    k = 2 * math.pi / sum(share.values())
    # quantized to 3 degree steps (the remainder goes to ZEUS Trading): a few new places never move a district border
    share = {d: math.radians(3) * round(math.degrees(v * k) / 3) for d, v in share.items()}
    share["zeus"] += 2 * math.pi - sum(share.values())
    arcs, a = {}, -math.pi / 2 - share["zeus"] / 2
    for d, *_ in DISTRICTS:
        arcs[d] = (a, a + share[d])
        a += share[d]
    R = PLAZA + 4 * CELL
    for _ in range(80):
        ok, plan = try_plan(W, by_q, need, arcs, R)
        if ok:
            break
        R += CELL
    taken = plan
    # filler: every free cell inside R (the city fabric), and a ragged ring of outskirts beyond it
    filler = []
    n = int(R / CELL) + 5
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, z = i * CELL, j * CELL
            r = math.hypot(x, z)
            if r < PLAZA or (i, j) in taken:
                continue
            if r <= R:
                lvl = max(1, min(9, round(9 * (1 - (r - PLAZA) / max(1.0, R - PLAZA)) + 1)))
                if fnv(f"{i},{j}") % 23 == 0:
                    lvl = 0                                     # a park
                filler.append([i, j, lvl])
            elif r <= R + 3 * CELL and (fnv(f"o{i},{j}") % 100) < 100 * (1 - (r - R) / (3 * CELL)) ** 1.5:
                filler.append([i, j, 1])
    return R, arcs, filler


def try_plan(W, by_q, need, arcs, R):
    n = int(R / CELL) + 1
    cells = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, z = i * CELL, j * CELL
            r = math.hypot(x, z)
            if PLAZA <= r <= R:
                cells.append((r, angle_of(x, z), i, j))
    cells.sort()
    taken = {}
    for d, *_ in DISTRICTS:
        a0, a1 = arcs[d]
        mine = [c for c in cells if in_arc(c[1], a0, a1)]
        qs = [q for q, _ in QUARTERS[d] if (d, q) in by_q]
        # the downtown band: apps then the core, from the plaza outward
        down = [q for q in qs if q in DOWNTOWN]
        free = [c for c in mine]
        for q in down:
            for p in order_places(by_q[(d, q)], q):
                got = grab(p, need_cells(p), free, taken)
                if got is None:
                    return False, None
        # the learning quarters: the rest of the wedge, one slice each (proportional to need), each grown from its inner edge
        learn = [q for q in qs if q not in DOWNTOWN]
        if not learn:
            continue
        rest = [c for c in free if (c[2], c[3]) not in taken]
        rmin = min((c[0] for c in rest), default=R)
        bk = {q: bucket(need[(d, q)]) for q in learn}
        tot = sum(bk.values())
        span = (a1 - a0) % (2 * math.pi) or 2 * math.pi
        a = a0
        widths = [math.radians(1.5) * max(1, round(math.degrees(span * bk[q] / tot) / 1.5)) for q in learn]
        widths[-1] = span - sum(widths[:-1])                    # quantized slices too (3 degrees), the last takes the rest
        for q, w in zip(learn, widths):
            if w <= 0:
                return False, None
            slice_ = [c for c in rest if in_arc(c[1], a, a + w) and c[0] >= rmin - 0.01]
            for p in order_places(by_q[(d, q)], q):
                if grab(p, need_cells(p), slice_, taken) is None:
                    return False, None
            a += w
    return True, taken


def order_places(ps, q):
    if q == "apps":
        return sorted(ps, key=lambda p: (0 if p.get("shortcut") else 1, p.get("rank", 99), p["id"]))
    if q == "core":
        order = {"bot:lit": 0, "bot:atlas": 1, "bot:blitz": 2}
        return sorted(ps, key=lambda p: (order.get(p["id"], 5), p["id"]))
    return sorted(ps, key=lambda p: (p["born"] or "", p["id"]))


def grab(p, k, pool, taken):
    """k cells for place p: the innermost free cell of the pool, then its free neighbours (innermost first): a compact block"""
    free = [c for c in pool if (c[2], c[3]) not in taken]
    if len(free) < k:
        return None
    seed = free[0]
    got = [seed]
    taken[(seed[2], seed[3])] = p["id"]
    index = {(c[2], c[3]): c for c in free}
    while len(got) < k:
        cand = {}
        for c in got:
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                key = (c[2] + di, c[3] + dj)
                if key in index and key not in taken:
                    cand[key] = index[key]
        cx = sum(c[2] for c in got) / len(got)
        cz = sum(c[3] for c in got) / len(got)
        near = lambda c: (math.hypot(c[2] - cx, c[3] - cz) + 0.02 * c[0], c[2], c[3])   # a compact block, a little inward
        if cand:
            nxt = min(cand.values(), key=near)
        else:
            rest = [c for c in free if (c[2], c[3]) not in taken]
            if not rest:
                return None
            nxt = min(rest, key=near)
        got.append(nxt)
        taken[(nxt[2], nxt[3])] = p["id"]
    p["cells"] = sorted([c[2], c[3]] for c in got)
    xs = [c[2] * CELL for c in got]
    zs = [c[3] * CELL for c in got]
    p["x"], p["z"] = round(sum(xs) / len(xs), 1), round(sum(zs) / len(zs), 1)
    p["r"] = round(max(math.hypot(x - p["x"], z - p["z"]) for x, z in zip(xs, zs)) + CELL * 0.62, 1)
    return got


# ------------------------------------------------------------------------------------------------ the whole world
HUB_PATH = None                                         # tests / --hub: another hub.json


def build(now=None):
    hide = hidden_bots()
    W = World(hide)
    apps(W)
    core(W, hide)
    lab(W)
    A = research(W, hide)
    markets(W, A)
    datacity(W)
    kalshi(W)
    decisions(W)
    concepts(W)
    research_hub(W, HUB_PATH)
    R, arcs, filler = plan_city(W)
    d0 = _dt.date.fromisoformat(W.start) if W.start else None
    nb, counts = 0, {"ruin": 0, "scaffold": 0, "lit": 0, "bright": 0}
    for p in W.places:
        flat = []
        for h, s, d in p.pop("_b"):
            flat += [h, s, 0 if not d or not d0 else max(0, (_dt.date.fromisoformat(d) - d0).days)]
            nb += 1
            counts[{0: "ruin", 1: "scaffold", 2: "lit"}.get(s, "bright")] += 1
        p["b"] = flat
        p["day"] = 0 if not p["born"] or not d0 else max(0, (_dt.date.fromisoformat(p["born"]) - d0).days)
        p.pop("fill", None)
    now = now or _dt.datetime.now(_dt.timezone.utc)
    ids = {p["id"] for p in W.places}
    seen, feed = set(), []
    for e in sorted((e for e in W.feed if e["d"]), key=lambda e: (e["d"], e["text"]), reverse=True):
        if (e["id"], e["text"]) in seen:
            continue
        seen.add((e["id"], e["text"]))
        feed.append(e if e["id"] in ids else dict(e, id=None))
        if len(feed) >= 48:
            break
    hows = []
    for p in W.places:
        t = p.get("how") or ""
        if t not in hows:
            hows.append(t)
        p["how"] = hows.index(t)
    districts = []
    for d, name, line, hue in DISTRICTS:
        a0, a1 = arcs[d]
        mid = (a0 + a1) / 2
        mine = [p for p in W.places if p["district"] == d]
        quarters = []
        for q, qn in QUARTERS[d]:
            ps = [p for p in mine if p["quarter"] == q]
            if ps:
                quarters.append({"id": q, "name": qn, "n": len(ps), "x": round(sum(p["x"] for p in ps) / len(ps), 1), "z": round(sum(p["z"] for p in ps) / len(ps), 1)})
        districts.append({"id": d, "name": name, "line": line, "hue": hue, "a0": round(a0, 4), "a1": round(a1, 4),
                          "x": round(math.cos(mid) * (PLAZA + (R - PLAZA) * 0.5), 1), "z": round(math.sin(mid) * (PLAZA + (R - PLAZA) * 0.5), 1),
                          "n": len(mine), "apps": sum(1 for p in mine if p["kind"] == "app"), "quarters": quarters})
    learning = [p for p in W.places if p["kind"] != "app"]
    return {
        "v": 2, "kind": "olympus-world", "built": now.strftime("%Y-%m-%dT%H:%MZ"), "start": W.start,
        "days": 0 if not d0 else max(0, (now.date() - d0).days), "hidden_bots": list(hide),
        "cell": CELL, "plaza": PLAZA, "R": R,
        "about": "One city of everything: six districts, one per arena (ZEUS Trading, Kalshi, Websites, Lab & Research, Life, Money). Every app is a downtown tower you can open; every learning place is real data "
                 "(a live bot, an account, a market, a Kalshi bet, a ZEUS Lab idea or a group of stored backtests): lit towers work, scaffolds are being "
                 "tested, ruins were tested and rejected. Money is after costs; backtests are history, not a forecast.",
        "legend": [["Gold crown", "an app or a live bot: tap to open"], ["Bright tower", "works: adopted, a winner, promising"],
                   ["Scaffold", "being tested, planned or waiting for you"], ["Ruin", "tested and rejected"],
                   ["Vault", "an account: fills with light as it nears its goal"]],
        "counts": {"places": len(W.places), "apps": len(W.places) - len(learning), "learning": len(learning), "buildings": nb, **counts,
                   "live": sum(1 for p in W.places if p["state"] == "live"), "districts": len(districts), "filler": len(filler)},
        "districts": districts, "places": W.places, "filler": filler, "feed": feed, "hows": hows,
    }


def write(world, path=OUT):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    txt = json.dumps(world, ensure_ascii=False, separators=(",", ":"))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(txt)
    os.replace(tmp, path)
    return len(txt.encode("utf-8"))


def summary(w):
    c = w["counts"]
    per = ", ".join(f"{d['name']} {d['n']} ({d['apps']} apps)" for d in w["districts"])
    return (f"world: {c['places']} places ({c['apps']} apps + {c['learning']} learning), {c['buildings']} data buildings ({c['bright']} bright, "
            f"{c['lit']} lit, {c['scaffold']} scaffold, {c['ruin']} ruins), {c['filler']} filler cells, city radius {w['R']:.0f}; {per}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Olympus World: the repo's data as one giant city (world.json)")
    ap.add_argument("--check", action="store_true", help="build in memory, print the counts, write nothing")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--hub", default=None, help="another research hub file (tests, previews); default tools/web_public/research/hub.json")
    a = ap.parse_args(argv)
    global HUB_PATH
    HUB_PATH = a.hub
    w = build()
    if a.check:
        print(summary(w))
        return 0
    n = write(w, a.out)
    print(summary(w) + f"; wrote {os.path.relpath(a.out, ROOT)} ({n // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
