"""TRADE SCRIPTS + SCORECARD (day-caller2 2026-11-22): the human caller's words per trade, the 2-week cadence, the scorecard.
  a. the 8 trades (roofing, HVAC, plumbing, electrical, landscaping, remodeling, auto repair, restaurants) + a generic script, each with
     3 lanes (no site / site down / old site), 3 questions, a close, a voicemail
  b. the rules hold in code: who is calling first, <= 45 words (~15 s), only the price book's prices, no promises / fake urgency, no slot left
  c. the trade is picked from the lead's kind (stores are not trades; electrical contractor is electrical, not remodeling)
  d. the cadence: at most 1 call + 1 follow-up, texts only when they said yes, then email only
  e. the generated sheet and the portal copy are what the source makes today (rerun after a change)
  f. the scorecard: dials / talks / links / booked in the window vs the targets x days; sold and $ only from cleared money
    python -X utf8 -m tests.test_trade_scripts
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency import portal as PT  # noqa: E402
from agency import pricebook as PB  # noqa: E402
from agency import trade_scripts as TS  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


def main() -> int:
    d = TS.load()
    ids = [t["id"] for t in d["trades"]]
    check("a. the 8 trades + a generic script", ids == ["roofing", "hvac", "plumbing", "electrical", "landscaping", "remodeling", "auto_repair", "restaurant"]
          and d["generic"]["id"] == "other", ids)
    every = TS.all_scripts(d)
    check("a. each has 3 lanes (no site, site down, old site), 3 questions, a yes-close, a not-now, a voicemail",
          len(every) == 9 and all(set(p) == {"no_site", "site_down", "redesign"} and all(len(s["questions"]) == 3 and s["close_yes"] and s["voicemail"]
                                                                                          for s in p.values()) for p in every))
    bad = TS.problems(d)
    check("b. every script: who is calling first, <= 45 words, only the price book's prices, no promises or fake urgency, no {slot} left",
          not bad, bad[:8])
    w = PB.words()
    s = TS.script_for({"name": "Joe's Pipes", "kind": "Plumbing", "lane": "site_down", "problem": "error 500"},
                      {"me": "Ana", "agency": "Brightline Web", "owner": "Dee", "day": "Tuesday"})
    check("b. a filled script: the caller's name and agency first, the business by name, the price book's $1,500 / $79 / $149 / $750",
          s["opener"].startswith("Hi, it's Ana with Brightline Web") and "Joe's Pipes" in s["opener"] and "wouldn't open" in s["opener"]
          and all(x in s["close_yes"] for x in ("$1,500", "$79", "$149", w["deposit"], "Dee", "Tuesday")), s)
    broken = json.loads(json.dumps(d))
    broken["trades"][0]["hook"] = ("We guarantee you'll rank #1 on Google if you sign today only, and it's just $999 for the whole thing, "
                                   "with photos, a gallery, a booking calendar, reviews and more.")
    found = TS.problems(broken)
    check("b. the check catches a promise, fake urgency and a long opener", any("banned" in why for _, why in found)
          and any("words" in why for _, why in found) and any("not in the price book" in why for _, why in found), found[:6])
    pick = {k: TS.trade_for(k, d)["id"] for k in ("Roofing", "Hvac service", "Plumbing", "Electrician", "Electrical contractor", "Landscaping",
                                                    "Altering and remodeling contractor", "Automotive repair", "Auto body shop", "Mexican restaurant",
                                                    "Café", "Hair salon", "Auto insurance", "Kitchen supply store", "Home automation", "Car wash")}
    want = {"Roofing": "roofing", "Hvac service": "hvac", "Plumbing": "plumbing", "Electrician": "electrical", "Electrical contractor": "electrical",
            "Landscaping": "landscaping", "Altering and remodeling contractor": "remodeling", "Automotive repair": "auto_repair",
            "Auto body shop": "auto_repair", "Mexican restaurant": "restaurant", "Café": "restaurant", "Hair salon": "other",
            "Auto insurance": "other", "Kitchen supply store": "other", "Home automation": "other", "Car wash": "other"}
    check("c. the trade comes from the lead's kind (insurance, stores, home automation, car wash fall to the generic script)", pick == want,
          {k: (pick[k], want[k]) for k in want if pick[k] != want[k]})
    cad = d["cadence"]
    check("d. cadence: 2 calls max (day 0 + one follow-up), a text only after their yes, the rest is email; stop on any no",
          [c["day"] for c in cad if c["what"] == "call"] == [0, 2] and all("ONLY if they said" in c["how"] for c in cad if c["what"] == "text")
          and max(c["day"] for c in cad) == 14 and "any channel" in d["stop_words"])
    md = open(os.path.join(ROOT, "research", "handoff", "2026-11-22", "caller", "TRADE_SCRIPTS.md"), encoding="utf-8").read()
    pc = json.load(open(TS.PORTAL_COPY, encoding="utf-8"))
    check("e. the caller's sheet and the portal copy are what the source makes today (python -m agency.trade_scripts --md ... --json ...)",
          md == TS.markdown(d) and pc == json.loads(json.dumps(TS.portal_copy(d))), "rerun the generator")
    check("e. the portal copy carries no name, phone or email (the page fills the slots)",
          "@" not in json.dumps(pc) and not any(ch.isdigit() and len(x) >= 10 for x in json.dumps(pc).split() for ch in x[:1]))
    day = 86400000
    now = 1_800_000_000_000
    store = {"log": [{"t": now - 3600_000, "id": "a", "k": "called", "caller": "Ann"}, {"t": now - 3500_000, "id": "b", "k": "voicemail", "caller": "Ann"},
                     {"t": now - 3400_000, "id": "c", "k": "interested", "caller": "Ann"}, {"t": now - 3300_000, "id": "c", "k": "booked", "caller": "Ann"},
                     {"t": now - 3 * day, "id": "d", "k": "won", "caller": "Ann"}, {"t": now - 1000, "id": "e", "k": "no", "caller": "Bo"}]}
    rate = {"commission": {"sale": 300, "booked_show": 40, "clawback_days": 30}}
    sc1 = {r["caller"]: r for r in PT.scorecard(store, 1, now, rate, paid=[])}
    check("f. today's scorecard: Ann 4 dials, 3 talks, 1 link, 1 booked vs 50 / 10 / 2 / 1 (the old 'won' is outside today)",
          (sc1["Ann"]["dials"], sc1["Ann"]["talks"], sc1["Ann"]["links"], sc1["Ann"]["booked"]) == (4, 3, 1, 1)
          and sc1["Ann"]["target"] == {"dials": 50, "talks": 10, "links": 2, "booked": 1} and sc1["Ann"]["hit"]["booked"] and not sc1["Ann"]["hit"]["dials"], sc1)
    sc5 = {r["caller"]: r for r in PT.scorecard(store, 5, now, rate, paid=[])}
    paid = [{"id": "d", "kind": "deposit", "t": "2027-01-10"}, {"id": "d", "kind": "launch", "t": "2027-01-12"}]
    sc5p = {r["caller"]: r for r in PT.scorecard(store, 5, now, rate, paid=paid)}
    check("f. the week's scorecard: the 'won' counts as a dial; sold and $ owed only once the client's money cleared (pending before)",
          sc5["Ann"]["dials"] == 5 and sc5["Ann"]["sold"] == 0 and sc5["Ann"]["pending"] == 300 and sc5p["Ann"]["sold"] == 1
          and sc5p["Ann"]["owed"] == 300 and sc5["Ann"]["target"]["dials"] == 250, (sc5["Ann"], sc5p["Ann"]))
    t = PT.scorecard_table(list(sc1.values()), 1)
    check("f. the table: done/target with + when hit, sold, owed, pending, clawback, the talk rate", "4/50" in t and "1/1+" in t and "pending" in t
          and "% of dials became a talk" in t, t)
    bad_n = RES.count(False)
    print(f"\n{len(RES) - bad_n}/{len(RES)} passed")
    return 1 if bad_n else 0


if __name__ == "__main__":
    sys.exit(main())
