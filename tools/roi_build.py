"""EVAL ECONOMICS data (day-evalroi 2026-11-27, lead: "per account type: expected $ per $1, months to break even, best next buy").
PAPER / READ ONLY: reads the stored eval simulations and writes tools/web_public/nq/roi.json for nq/roi.html (and the Accounts card).

Sources (no new simulation here):
  research/plans/results.json        the real-engine plan ranking (rank.py: today's eval sizing, ATLAS's lane, every MFFU rule, re-buys),
                                     1,000 paths: eval pass / fail % in 60 sessions + median sessions to pass; the 6-month slot: owner $,
                                     fees, net, owner $ per $1 of fees, first payout (median sessions), funded lost %
  research/badcase/results.json      the same engine on a 2025-like market (Builder 50K / 25K, Rapid EOD 25K)
  research/evalroi/rapid50_y25.json  the Rapid EOD 50K in a 2025-like market (the one plan badcase did not run)
Prices = the OWNER's real prices (CLAUDE.md: Builder 50K $91.80, 25K $63 / $43; Rapid EOD 25K $97.20; Rapid EOD 50K $165), never list.
Slots = MFFU's limits (docs/ACCOUNT_RULES.md: funded Builder 50K x1, Builder 25K x2, Rapid EOD 25K x3, Rapid EOD 50K x3, 5 in all) minus
today's accounts (Zlarior 50K eval, Zlarior 25K #2 eval, ATLAS 25K funded, Rapid EOD 25K eval).
Note: the stored Builder runs predate big-consfix (a Builder pass from a loss was not counted): their pass % / $ are 0.1-2.2 points / $4-145
a slot low (research/writeups/consfix-2026-11-26.md); said on the page.

    python -X utf8 tools/roi_build.py          -> tools/web_public/nq/roi.json
"""
from __future__ import annotations

import datetime as dt
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "web_public", "nq", "roi.json")
PLANS = [  # key, name, owner's real price, MFFU funded cap, how many today's accounts use
    ("mffu_builder_50k", "Builder 50K", 91.80, 1, 1),
    ("mffu_builder_25k", "Builder 25K", 63.00, 2, 2),
    ("mffu_rapid_eod_25k", "Rapid EOD 25K", 97.20, 3, 1),
    ("mffu_rapid_eod_50k", "Rapid EOD 50K", 165.00, 3, 0),
]
TOTAL_CAP, USED_TOTAL = 5, 4
SESSIONS_A_MONTH = 21
SPENT = [  # what the owner paid for today's accounts (docs/ACCOUNT_RULES.md, STATE.md); earlier failed evals are not recorded anywhere
    {"name": "Zlarior Builder 50K eval", "usd": 91.80, "src": "docs/ACCOUNT_RULES.md"},
    {"name": "Zlarior Builder 25K #2 eval", "usd": 63.00, "src": "docs/ACCOUNT_RULES.md"},
    {"name": "Rapid EOD 25K eval", "usd": 97.20, "src": "docs/ACCOUNT_RULES.md"},
    {"name": "ATLAS's Builder 25K eval (now funded)", "usd": 43.00, "usd_hi": 63.00, "src": "CLAUDE.md '25K $63 / $43': one 25K was $43, which one is not recorded"},
]


def _j(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return json.load(fh)


def market(row: dict | None) -> dict | None:
    if not isinstance(row, dict):
        return None
    e, s = row.get("eval") or {}, row.get("slot") or {}
    fees = s.get("fees_6m") or 0
    per = s.get("per_dollar")
    if per is None and fees:
        per = round((s.get("owner_6m") or 0) / fees, 2)
    fp = s.get("first_pay_med")
    return {"pass": e.get("pass"), "blow": e.get("fail"), "days": e.get("med_days"), "net6": s.get("net_6m"), "per_dollar": per,
            "owner6": s.get("owner_6m"), "fees6": round(fees, 1) if fees else fees, "first_pay_days": fp,
            "first_pay_months": round(fp / SESSIONS_A_MONTH, 1) if fp else None, "lost": s.get("p_lost"), "no_pay": s.get("no_pay", s.get("no_pay_pct"))}


def build() -> dict:
    rank = _j("research", "plans", "results.json")["rows"]
    bad = _j("research", "badcase", "results.json")["plans"]
    r50 = _j("research", "evalroi", "rapid50_y25.json")
    rows = []
    for key, name, price, cap, used in PLANS:
        R = rank[key]
        M = {m: market(R.get(m)) for m in ("H2", "H1", "REF")}
        y = (bad.get(key) or {}).get("Y25") or (r50["Y25"] if key == "mffu_rapid_eod_50k" else None)
        M["Y25"] = market(y)
        free = max(0, min(cap - used, TOTAL_CAP - USED_TOTAL))
        g = M["H2"]
        rows.append({"key": key, "name": name, "price": price, "cap": cap, "used": used, "free": free,
                     "markets": M, "break_even_months": g["first_pay_months"] if g and (g["net6"] or 0) > 0 else None})
    buy = [r for r in rows if r["free"] > 0]
    best = max(buy, key=lambda r: r["markets"]["H2"]["net6"]) if buy else None
    spent_lo = round(sum(x["usd"] for x in SPENT), 2)
    spent_hi = round(sum(x.get("usd_hi", x["usd"]) for x in SPENT), 2)
    out = {"v": 1, "made": dt.date.today().isoformat(), "rows": rows, "spent": SPENT, "spent_lo": spent_lo, "spent_hi": spent_hi,
           "slots": {"used": USED_TOTAL, "cap": TOTAL_CAP},
           "markets": {"H2": "2026 Jul-Oct-like (the fair test)", "H1": "2026 Jan-Jun-like (good)", "REF": "2021-25 mix", "Y25": "2025-like"},
           "src": "research/plans/results.json + research/badcase/results.json + research/evalroi/rapid50_y25.json (1,000 runs each, real engine)",
           "consfix": "Builder runs predate the 2026-11-26 pass-count fix: their pass % / $ are slightly low (0.1-2.2 points, $4-145 a slot)"}
    if best:
        g, b = best["markets"]["H2"], best["markets"]["Y25"] or best["markets"]["REF"]
        out["best"] = {"key": best["key"], "name": best["name"], "price": best["price"],
                       "line": (f"Best next buy: a {best['name']} at ${best['price']:,.2f} (your last free funded slot). In a 2026-like market it returns "
                                f"about ${g['per_dollar']:,.0f} per $1 of fees, ${g['net6']:,} in 6 months, first payout in about {g['first_pay_months']} months. "
                                f"In a 2025-like market it loses about ${-b['net6']:,} in 6 months, so buy it only while LIT is trading like 2026."),
                       "card": "Decide the 'plan-rapid50k-max2-rebuys' card first (the fleet plan's #1 move)" if best["key"] == "mffu_rapid_eod_50k" else ""}
    return out


def main() -> int:
    d = build()
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1)
    print(d.get("best", {}).get("line", "no free slot"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
