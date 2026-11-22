"""THE MONEY PIPELINE, PC side (day-a11y 2026-11-22; owner: "see calls turn into dollars"): one tiny card of counts and dollars, no
names, no numbers of anyone, for the Money app's Pipeline screen (tools/web_public/business/pipeline.html).

    python -m agency.pipeline            print the pipeline and write the card data/agency_pipeline/summary.json (gitignored)

Sources (the PC's private files, never published as they are):
  %USERPROFILE%\\.olympus\\portal_log.json   every caller's imported log (python -m agency.portal import): dials, talks, proposals
  %USERPROFILE%\\.olympus\\agency_paid.json  the owner's record of client money that CLEARED (python -m agency.portal paid ...)
  agency/pricebook.json                       the amounts (deposit, launch balance, care plan, the no-upfront plan)
Only CLEARED money counts as sold (the scorecard's rule, agency.portal.sale_cleared): a deposit AND the launch payment, or the 3rd
monthly payment on the no-upfront plan. A caller's 'Won' is a claim, not money. A refund takes its amount back out.
The PC report carries the card in its ext block as "ap" (LEAD_WIRES: research/handoff/2026-11-22/pipeline/LEAD_WIRES.md); the page reads it
through pc_feed.js. Stdlib only."""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARD = os.path.join(ROOT, "data", "agency_pipeline", "summary.json")
DIALS = {"called", "voicemail", "interested", "booked", "no", "dnc", "won"}
TALKS = {"called", "interested", "booked", "no", "won", "dnc"}


def _home() -> str:
    return os.environ.get("OLYMPUS_HOME") or os.path.join(os.path.expanduser("~"), ".olympus")


def _rj(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def amounts(book: dict | None = None) -> dict:
    b = book or _rj(os.path.join(ROOT, "agency", "pricebook.json"), {}) or {}
    st = next((x for x in b.get("packages") or [] if x.get("id") == "starter"), {"setup": 1500, "monthly": 79})
    dep = round(st["setup"] * b.get("deposit_pct", 50) / 100)
    return {"deposit": dep, "launch": st["setup"] - dep, "care": (b.get("care_plan") or {}).get("monthly", st["monthly"]),
            "no_upfront": (b.get("no_upfront") or {}).get("monthly", 149)}


def summary(log: list, pays: list, book: dict | None = None, today: str | None = None) -> dict:
    """the pipeline from the imported caller logs + the cleared payments: counts and $ only"""
    A = amounts(book)
    today = today or dt.date.today().isoformat()
    month = today[:7]
    log = [e for e in log if isinstance(e, dict) and e.get("id")]
    c = {"dials": sum(1 for e in log if e.get("k") in DIALS), "talks": sum(1 for e in log if e.get("k") in TALKS),
         "proposals": len({e["id"] for e in log if e.get("k") == "proposal"})}
    pays = [e for e in pays if isinstance(e, dict) and e.get("id") and e.get("kind") in ("deposit", "launch", "monthly", "refund") and isinstance(e.get("t"), str)]
    ids = sorted({e["id"] for e in pays})
    setup = mrr = cleared = month_in = 0
    deposits = live = sold = 0
    for lid in ids:
        mine = sorted((e for e in pays if e["id"] == lid), key=lambda e: e["t"])
        has_dep = any(e["kind"] == "deposit" for e in mine)
        plan = A["care"] if has_dep else A["no_upfront"]          # no deposit = the nothing-upfront plan
        got = 0
        for e in mine:
            v = {"deposit": A["deposit"], "launch": A["launch"], "monthly": plan}.get(e["kind"], 0)
            if e["kind"] == "refund":
                v = -(A["deposit"] if not any(x["kind"] == "launch" for x in mine) else A["deposit"] + A["launch"])
            got += v
            if e["t"][:7] == month:
                month_in += v
            if e["kind"] in ("deposit", "launch", "refund"):
                setup += v                                       # a refund takes the setup money back out
        refunded = any(e["kind"] == "refund" for e in mine)
        if has_dep:
            deposits += 1
        launched = any(e["kind"] == "launch" for e in mine) or sum(1 for e in mine if e["kind"] == "monthly") >= 1
        if launched and not refunded:
            live += 1
            last_pay = max(e["t"] for e in mine)
            if (dt.date.fromisoformat(today) - dt.date.fromisoformat(last_pay[:10])).days <= 35 or any(e["kind"] == "launch" for e in mine):
                mrr += plan
        try:
            sys.path.insert(0, ROOT)
            from agency.portal import sale_cleared
            done = bool(sale_cleared(pays, lid))
        except ImportError:
            done = has_dep and any(e["kind"] == "launch" for e in mine)
        if done and not refunded:
            sold += 1
        cleared += got
    return {"v": 1, "kind": "agency-pipeline", "t": int(time.time()), "day": today, **c, "deposits": deposits, "live": live, "sold": sold,
            "setup": int(setup), "mrr": int(mrr), "cleared": int(cleared), "month_in": int(month_in)}


def build_card(h: str | None = None, book: dict | None = None, today: str | None = None) -> dict:
    h = h or _home()
    store = _rj(os.path.join(h, "portal_log.json"), {}) or {}
    paid = (_rj(os.path.join(h, "agency_paid.json"), {}) or {}).get("payments") or []
    return summary(store.get("log") or [], paid, book, today)


def write_card(card: dict, path: str = CARD) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(card, f, separators=(",", ":"))
    return path


def read_card(path: str = CARD) -> dict | None:
    """for the PC report's ext block ("ap"): the card, or None"""
    c = _rj(path, None)
    return c if isinstance(c, dict) and c.get("kind") == "agency-pipeline" else None


def main(argv=None) -> int:
    c = build_card()
    write_card(c)
    print(f"  dials {c['dials']} -> talks {c['talks']} -> proposals {c['proposals']} -> deposits {c['deposits']} -> live {c['live']} (sold {c['sold']})")
    print(f"  setup collected ${c['setup']:,} · monthly recurring ${c['mrr']:,} · cleared in total ${c['cleared']:,} · this month ${c['month_in']:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
