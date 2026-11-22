"""Tomorrow's dial sheet for the HUMAN caller (lead 2026-11-22): the top N Maryland businesses with no website, ranked by likely $.
Human dialing only - Maryland bans cold AI / robo / auto-dialed calls (docs/COLD_CALLING_RULES.md). Public map data only.

    python -X utf8 tools/dial_sheet.py [--day 2026-11-23] [--n 150]   -> agency/calls/<day>.csv (+ prints the totals)

Sources: the caller list tools/web_public/agency/portal/calllist.json (built by agency.portal, the do-not-call scrub runs on it on the
PC: agency.dnc_scrub) joined to the full lead rows tools/web_public/agency/leads/towns/*.json; call windows and trade words from
tools/web_public/agency/callrules.json via agency/calls/core.py (the same rules the phone page uses); prices agency/pricebook.json.
Left out: businesses with a working site, chains (already dropped upstream), yesterday's first 100 (portal/first100.json), leads
without a phone, duplicate phone numbers.
Rank = likely $ = first-year ticket for the trade x how likely the trade buys (tools/first_calls.WEIGHT) x hours open
(weekdays open in calling hours / 5) x heat (hot 1.0, warm 0.75, else 0.5) x lane (no site 1.0, site down 0.6).
Review counts are NOT in the data (OpenStreetMap / Overture carry none): the sheet says so instead of inventing them.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency.calls import core as C  # noqa: E402
from tools import first_calls as FC  # noqa: E402

WEB = os.path.join(ROOT, "tools", "web_public", "agency")
OUT_DIR = os.path.join(ROOT, "agency", "calls")
ET = ZoneInfo("America/New_York")
HEAT = {"hot": 1.0, "warm": 0.75}
LANE = {"no_site": 1.0, "site_down": 0.6}


def ticket(pb: dict, trade: str) -> float:
    """First-year $ of one sale: the price book's package mix (agency/pricing.json) - starter setup + 12 months of care."""
    P = {p["id"]: p for p in pb["packages"]}
    st = P["starter"]["setup"] + 12 * P["starter"]["monthly"]
    ce = P["callengine"]["setup"] + 12 * P["callengine"]["monthly"]
    mix = 0.2 if trade in ("contractor", "medical", "auto", "professional") else 0.1   # call engine sells to phone-led trades
    return round((1 - mix) * st + mix * ce)


def opener(lead: dict, T: dict, lane: str) -> str:
    town = lead.get("town") or "the area"
    if lane == "site_down":
        l1 = f"Hi, is this the owner of {lead['name']}? Quick one - I tried your website and it didn't load for me, so we built a free sample of a new one."
    else:
        l1 = f"Hi, is this the owner of {lead['name']}? I build websites for {T['plural']} around {town}, and I noticed you don't show one on Google - so we made you a free sample."
    l2 = f"{T['issue'][0].upper() + T['issue'][1:]}; the sample shows {T['hook']}. Can I text you the link - it takes a minute to look at?"
    return l1 + " / " + l2


def build(day: str, n: int = 150) -> tuple[list, dict]:
    rules = C.load_rules()
    pb = json.load(open(os.path.join(ROOT, "agency", "pricebook.json"), encoding="utf-8"))
    cl = json.load(open(os.path.join(WEB, "portal", "calllist.json"), encoding="utf-8"))
    done = {x["id"] for x in json.load(open(os.path.join(WEB, "portal", "first100.json"), encoding="utf-8")).get("leads", [])}
    full = {}
    for f in glob.glob(os.path.join(WEB, "leads", "towns", "*.json")):
        for x in json.load(open(f, encoding="utf-8")).get("leads", []):
            full[x["id"]] = x
    now_ms = int(dt.datetime.fromisoformat(day + "T07:00").replace(tzinfo=ET).timestamp() * 1000)
    rows, seen, skip = [], set(), {"first100": 0, "no_phone": 0, "dup_phone": 0, "not_md": 0, "no_window": 0, "has_site": 0}
    for c in cl.get("leads", []):
        x = {**full.get(c["id"], {}), **c}
        lane = c.get("lane") or "no_site"
        if lane not in LANE or (x.get("web") or {}).get("verdict") == "has_site":
            skip["has_site"] += 1
            continue
        if c["id"] in done:
            skip["first100"] += 1
            continue
        ph = C.norm_phone(x.get("phone"))
        if not ph:
            skip["no_phone"] += 1
            continue
        if ph in seen:
            skip["dup_phone"] += 1
            continue
        if (x.get("state") or "").upper() != "MD":
            skip["not_md"] += 1
            continue
        tr = C.trade_of(x, rules)
        lead = {**x, "trade": tr}
        T = C.trade_info(lead, rules)
        w = C.next_window(lead, now_ms, rules)
        if not w or w["date"] != day:
            skip["no_window"] += 1
            continue
        wins = [f"{C.clock(a)}-{C.clock(b)}" for a, b in T["win"]]
        open_d = FC.weekday_open_days(x.get("hours") or "")
        hours_f = (open_d / 5.0) if open_d else 0.6            # unknown hours: a middle value, not zero
        tk = ticket(pb, tr)
        ev = tk * FC.WEIGHT.get(x.get("niche"), 1) / 3.0 * hours_f * HEAT.get(x.get("heat"), 0.5) * LANE[lane]
        seen.add(ph)
        rows.append({"rank": 0, "name": x.get("name"), "phone": C.pretty_phone(ph), "town": x.get("town"), "trade": T["label"],
                     "category": x.get("category") or x.get("kind"), "lane": lane, "heat": x.get("heat"),
                     "open_weekdays": open_d if open_d else "unknown", "hours": x.get("hours") or "",
                     "call_window": " or ".join(wins) + f" ET ({C.DOW3[w['wd']]})", "avoid": T.get("avoid", ""),
                     "ticket_usd": tk, "likely_usd": round(ev), "opener": opener(x, T, lane),
                     "concept_site": c.get("site") or "", "code": c.get("code") or "", "address": x.get("address") or "",
                     "id": c["id"], "reviews": "n/a (not in the map data)", "_score": float(x.get("score") or c.get("score") or 0)})
    rows.sort(key=lambda r: (-r["likely_usd"], -r["_score"], r["name"] or ""))
    rows = rows[:n]
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    meta = {"day": day, "candidates": len(seen), "skipped": skip, "dnc": cl.get("dnc") or "NOT SCRUBBED",
            "dnc_date": cl.get("dnc_date"), "credit": cl.get("credit") or "OpenStreetMap contributors (ODbL); Overture Maps Foundation"}
    return rows, meta


def write(rows, meta, day):
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, f"{day}.csv")
    cols = ["rank", "name", "phone", "town", "trade", "category", "lane", "heat", "open_weekdays", "call_window", "avoid",
            "ticket_usd", "likely_usd", "opener", "concept_site", "code", "address", "hours", "reviews", "id"]
    with open(p, "w", newline="", encoding="utf-8") as fh:
        fh.write(f"# dial sheet {day} - HUMAN dialing only (no AI / robo / auto-dial: illegal in Maryland). do-not-call: {meta['dnc']}"
                 f"{' ' + str(meta['dnc_date']) if meta.get('dnc_date') else ''}. Max 1 call a day per number, 3 in 24 h, no Sundays. "
                 f"Data: {meta['credit']}\n")
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return p


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default="2026-11-23")
    ap.add_argument("--n", type=int, default=150)
    a = ap.parse_args(argv)
    rows, meta = build(a.day, a.n)
    p = write(rows, meta, a.day)
    import collections
    print(f"{len(rows)} rows -> {os.path.relpath(p, ROOT)}; candidates {meta['candidates']}; skipped {meta['skipped']}; dnc {meta['dnc']}")
    print("by trade:", collections.Counter(r["trade"] for r in rows).most_common())
    print("lanes:", collections.Counter(r["lane"] for r in rows), "sum likely $", sum(r["likely_usd"] for r in rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
