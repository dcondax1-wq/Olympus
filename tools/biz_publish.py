"""BUSINESS page data (team BIZ, 2026-11-15): every money model beside the trading, its next action and its money, in one file.

    python tools/biz_publish.py              -> tools/web_public/business/business.json (gitignored: the owner's own state)
    python tools/biz_publish.py --fixture    -> tools/web_public/business/fixture.json  (committed DEMO: no local state read)
    python tools/biz_publish.py --print      the status table in plain text

Reads only files on this PC (the agency settings, the day's batch, the billing summary, the product zips); fetches nothing,
sends nothing. Every $ is an ESTIMATE range taken from the teams' own docs (docs/AGENCY.md, docs/MONEY_MACHINES.md) except
"real", which is only money the billing ledger has recorded. The page (tools/web_public/business/) reads business.json, else
fixture.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public", "business")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# The models, with the teams' own estimates (ESTIMATES, not promises). usd = [low, high] per month; hours = owner hours a week.
MODELS = [
    {"id": "agency", "name": "Website agency", "rank": 1, "doc": "docs/AGENCY.md",
     "what": "Find local shops with no website, build each a demo site, call them, sell a site + a monthly plan.",
     "built": ["Lead finder (free map data)", "Demo sites (8 looks)", "Pitch kit: opener, email, one-pager", "Call list with do-not-call rules",
               "Agency page (pipeline on the phone)", "Storefront site", "Proposal, agreement, invoice, payment links", "Upsells: reviews, chat, social posts"],
     "first_dollar": ["Your name, phone, email, postal address and city in agency/config.json", "Free Netlify account (to put demo sites online)",
                      "Free Stripe account + one payment link per plan", "About 60 calls by hand to find the first yes"],
     "usd_m1": [0, 550], "usd_m3": [0, 2000], "hours": [5, 7],
     "why": "One Starter sale is $499 + $49 a month. Month 3 assumes 0-2 sales a month (the docs' plan of 4 a month needs 6 calls a working day)."},
    {"id": "gigs", "name": "Freelance gigs", "rank": 2, "doc": "docs/GIG_PACK.md",
     "what": "8 ready gigs (websites, logos, Google profile, reviews, posts...) on Fiverr first; the tools make the work, you deliver.",
     "built": ["8 gig texts with prices, tags, FAQ", "Logo + brand kit maker", "Google profile checklist", "Order -> agency tools in one line"],
     "first_dollar": ["Fiverr seller account in your real name + ID check", "Publish the logo and Google-profile gigs (text in docs/GIG_PACK.md)",
                      "Answer every message the same day"],
     "usd_m1": [0, 100], "usd_m3": [0, 400], "hours": [6, 10],
     "why": "New sellers often wait weeks for the first order. Fiverr keeps 20% ($120 order pays $96)."},
    {"id": "products", "name": "Digital products", "rank": 3, "doc": "docs/BUSINESS_LISTING_KIT.md",
     "what": "5 finished downloads (eval tracker $17, site templates $24, social kit $14, agency kit $19, trader planner $14).",
     "built": ["All 5 products, upload zips, 6 covers each", "Title, description, tags, FAQ per product", "One listing kit for every shop"],
     "first_dollar": ["Free Payhip account (lowest fee)", "Upload the 5 zips with their covers (about 15 min each)", "A link to the shop from an Instagram bio"],
     "usd_m1": [0, 50], "usd_m3": [0, 100], "hours": [1, 2],
     "why": "Expect 0-10 sales a month per product until a social account or search sends buyers."},
    {"id": "insta_local", "name": "Instagram: local business tips", "rank": 4, "doc": "docs/MONEY_MACHINES.md",
     "what": "A tips account for local owners that sends them to the agency's free website check.",
     "built": ["30-day plan with captions and images", "Posting sheet for the free Meta scheduler", "Optional API poster (dry run by default)"],
     "first_dollar": ["New Instagram, switched to Professional", "Schedule the 30 posts in Meta Business Suite (free, about 15 min a week)",
                      "It pays only through agency clients it brings"],
     "usd_m1": [0, 0], "usd_m3": [0, 100], "hours": [2, 3],
     "why": "Plan for 100-1,000 followers in 3 months; the money is the agency clients it brings."},
    {"id": "insta_eval", "name": "Instagram: the eval journal", "rank": 5, "doc": "docs/MONEY_MACHINES.md",
     "what": "Trading routines (never results) that link the eval tracker; later disclosed affiliate links.",
     "built": ["30-day plan with captions and images", "The risk line and Ad rules built in"],
     "first_dollar": ["Second Instagram, Professional account", "Schedule the 30 posts", "The eval tracker link in the bio"],
     "usd_m1": [0, 0], "usd_m3": [0, 30], "hours": [2, 3],
     "why": "Strict rules: no profits, passes or signals; every paid link starts with Ad."},
    {"id": "rank_rent", "name": "Rank-and-rent sites", "rank": 6, "doc": "docs/MONEY_MACHINES.md",
     "what": "A site for one trade in one town, ranked, then rented to a local business.", "paused": True,
     "built": ["Research and a 6-month plan only"], "first_dollar": ["A $12 domain (not free: your call)", "3-12 months to rank", "A tenant"],
     "usd_m1": [0, 0], "usd_m3": [0, 0], "hours": [0, 0], "why": "The slowest machine: start only once the agency and gigs run."},
    {"id": "kalshi", "name": "Kalshi", "rank": 7, "doc": "docs/KALSHI_STOP_LIST.md", "paused": True,
     "what": "Prediction-market bot.", "built": ["Bot, Kalshi City page, edge research"], "first_dollar": ["Paused: no proven edge"],
     "usd_m1": [0, 0], "usd_m3": [0, 0], "hours": [0, 0], "why": "Paused until research shows an edge. Nothing to do."},
]

WEEK = [
    {"day": 1, "title": "Set up (about 1 hour)", "tasks": ["Double-click AGENCY_DAY.bat: Notepad opens agency/config.json; put in your name, phone, email, postal address, city; save",
                                                         "Make the free accounts: Netlify, Stripe, Payhip, Fiverr (real name, finish the ID check)",
                                                         "Double-click AGENCY_DAY.bat again: 3 demo sites, the call list and TODAY.txt"]},
    {"day": 2, "title": "First calls (1 hour)", "tasks": ["Drop the 3 site folders on app.netlify.com/drop, press Publish", "Call 10 owners from Call today, by hand, 10:00-12:00 or 14:00-16:00",
                                                       "Mark every call on the card (Contacted, Call back, Do not contact)"]},
    {"day": 3, "title": "Shop + gigs (1 hour)", "tasks": ["Payhip: upload the 5 products with docs/BUSINESS_LISTING_KIT.md (zips: RUN_MONEY or python -m money_machines.products.build_all --zip)",
                                                       "Fiverr: publish the logo and Google-profile gigs (docs/GIG_PACK.md)", "Make one Stripe payment link per plan, paste them in the billing kit"]},
    {"day": 4, "title": "Calls + Instagram (1 hour)", "tasks": ["AGENCY_DAY.bat, then 10 more calls", "New Instagram (Professional); schedule the first week in Meta Business Suite",
                                                              "Put the shop link in the bio"]},
    {"day": 5, "title": "Follow up (1 hour)", "tasks": ["Call back everyone who asked; send the demo link only to those who said send it", "10 new calls", "Answer every Fiverr message the same day"]},
    {"day": 6, "title": "Close (1 hour)", "tasks": ["A yes: python -m agency.billing kit for their proposal + invoice with your payment link", "Tell Claude 'Agency: <business> said yes' to build the live site",
                                                 "10 calls"]},
    {"day": 7, "title": "Count (15 min)", "tasks": ["Agency page > Export; count calls, talks, demos, yeses", "Business page: what moved, what to drop",
                                                 "Tell Claude your counts: it replaces the guessed call rates with yours"]},
]

RULES = ["Nothing here sends, posts or calls: you press every button.", "Calls by hand, business hours, never a robot or a recording; stop means Do not contact.",
         "Emails need your real name, email and postal address (CAN-SPAM).", "Every $ is an ESTIMATE range from the teams' docs, not a promise; 'real' is only what the ledger recorded."]


def _read(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def local_state() -> dict:
    """what this PC has done so far (only counts, never names or numbers of people)"""
    st = {}
    try:
        from agency import config as CFG
        cfg = CFG.load()
        st["agency_placeholders"] = len(cfg.get("_placeholders") or [])
        st["agency_config"] = os.path.isfile(CFG.OWNER)
    except Exception:
        st["agency_placeholders"], st["agency_config"] = None, False
    ml = _read(os.path.join(ROOT, "tools", "web_public", "agency", "my_leads.json")) or {}
    st["leads"] = len(ml.get("leads") or []) if isinstance(ml, dict) else 0
    st["demo_sites"] = sum(1 for l in (ml.get("leads") or []) if isinstance(l, dict) and l.get("built")) if isinstance(ml, dict) else 0
    cl = _read(os.path.join(ROOT, "agency", "calls", "out", "call_list.json")) or {}
    st["call_list"] = len(cl.get("leads") or []) if isinstance(cl, dict) else 0
    summ = _read(os.path.join(ROOT, "money_out", "agency.json")) or {}
    mrr = (summ.get("mrr") or {}).get("now") if isinstance(summ, dict) else None
    st["agency_mrr"] = float(mrr) if isinstance(mrr, (int, float)) and not summ.get("sample") else 0.0
    st["product_zips"] = len(glob.glob(os.path.join(ROOT, "money_machines", "out", "products", "*.zip")))
    return st


def prices() -> list:
    from agency import config as CFG
    return [{"id": k, **v} for k, v in CFG.prices().items()]


def next_action(m: dict, st: dict) -> str:
    if m.get("paused"):
        return "Nothing: paused."
    if m["id"] == "agency":
        if not st.get("agency_config") or st.get("agency_placeholders"):
            return "Double-click AGENCY_DAY.bat and fill in agency/config.json (name, phone, email, address, city)."
        if not st.get("demo_sites"):
            return "Double-click AGENCY_DAY.bat: today's leads, 3 demo sites, the call list."
        return f"Call {min(10, st.get('call_list') or st.get('leads') or 10)} owners from Call today (by hand, business hours)."
    if m["id"] == "products":
        return "Upload the 5 zips to a free Payhip shop (docs/BUSINESS_LISTING_KIT.md)." if st.get("product_zips") else \
            "Make the 5 zips (python -m money_machines.products.build_all --zip), then upload them to Payhip."
    return m["first_dollar"][0]


PROP_PLAN = os.path.join(ROOT, "research", "lab", "payout_plan.json")     # tools/money/payout_plan.py (team E, 2026-11-16)
PROP_SPAN = "H2"                                                           # quote the check half (Jul-Oct 2026)


def prop_plan(sample: bool = False, path: str | None = None) -> dict | None:
    """The prop accounts' payout plan (tools/money/payout_plan.py): $ a month at 2 / 3 / 4 / 6 accounts, the worst month, when
    Zlarior can pass and pay, when to buy #3, #4 ... from the payouts. sample (the committed, public fixture) = the research
    table only: no eval state, no dates (those stay in the PC's own business.json, which the public build removes)."""
    d = _read(path or PROP_PLAN)
    if not isinstance(d, dict) or PROP_SPAN not in (d.get("spans") or {}):
        return None
    sp = d["spans"][PROP_SPAN]
    ref = (d["spans"].get("REF") or {}).get("plans") or {}
    rows = []
    for n, p in sorted((sp.get("plans") or {}).items(), key=lambda x: int(x[0])):
        rows.append({"accounts": int(n), "usd_month_y1": p.get("usd_month_y1"), "usd_month_m7_12": p.get("usd_month_m7_12"),
                     "month_worst": p.get("month_worst"), "months_no_income_pct": p.get("months_no_income_m7_12_pct"),
                     "y1_p10": p.get("y1_p10"), "ref_usd_month": (ref.get(n) or {}).get("usd_month_y1")})
    na = d.get("new_account") or {}
    out = {"label": "ESTIMATE", "span": "Jul-Oct 2026 replay (the check half)", "source": "tools/money/payout_plan.py -> research/lab/payout_plan.json",
           "table": rows, "new_account": {"plan": na.get("plan"), "price": na.get("price")},
           "rules": ["Buy the next account only from a payout that reached your bank: one new account per payout, and only when "
                     "the payout money holds two of its price (one to buy, one kept for a re-buy).",
                     "MFFU funds only ONE Builder 50K a person: account #3 and up are LucidPro 50K copies of Zlarior (Lucid allows 5 funded).",
                     "Stop rule: at most 2 re-buys from your own pocket ($183.60); past that stop and rethink.",
                     "Prop money: you can lose only the fees, never more; a bad week inside an account is the firm's money."],
           "notes": ["Every account copies the SAME Zlarior signal (daily correlation about 0.94): a bad week hits all of them at once, "
                     "so more accounts multiply the good months AND the empty ones.",
                     "Backtest of 2026 (where LIT works); on 2021-25 (no edge) the same plan makes about $0 a month. Nothing is promised.",
                     "ATLAS's $ is the stored research estimate (a different bot), added from month 3."]}
    if not sample:
        z = sp.get("zlarior") or {}
        six = (sp.get("plans") or {}).get("6") or {}
        out["state"] = {"zlarior": d.get("zlarior_state"), "atlas": {k: (d.get("atlas") or {}).get(k) for k in ("room", "to_go", "plan", "asof")}}
        out["zlarior"] = {k: z.get(k) for k in ("pass_10", "fail_10", "pass_earliest", "pass_median", "first_payout_earliest",
                                                "first_payout_median", "first_payout_in_bank_median", "first_payout_usd_median")}
        out["buy"] = [{"n": k, **v} for k, v in (six.get("buy") or {}).items()]
        out["built"] = d.get("built")
    return out


def build(sample: bool = False, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    st = {} if sample else local_state()
    models = []
    for m in MODELS:
        real = st.get("agency_mrr", 0.0) if m["id"] == "agency" else 0.0
        models.append({k: m[k] for k in ("id", "name", "rank", "what", "built", "first_dollar", "usd_m1", "usd_m3", "hours", "why", "doc")}
                      | {"paused": bool(m.get("paused")), "next": next_action(m, st), "real_usd_month": round(real, 2)})
    live = [m for m in models if not m["paused"]]
    tot = {k: [sum(m[k][0] for m in live), sum(m[k][1] for m in live)] for k in ("usd_m1", "usd_m3", "hours")}
    tot["real_usd_month"] = round(sum(m["real_usd_month"] for m in models), 2)
    return {"v": 1, "kind": "business", "asof": now.isoformat(timespec="seconds"), "label": "ESTIMATE", "sample": sample, "demo": sample,
            "note": "EXAMPLE, not real: the plan with no progress from the PC yet (DEMO)." if sample else "Your PC's progress; $ ranges are estimates from the teams' docs.",
            "total": tot, "models": models, "progress": {k: v for k, v in st.items() if k != "agency_placeholders"} if st else {},
            "prices": prices(), "week": WEEK, "rules": RULES, **({"prop": pp} if (pp := prop_plan(sample)) else {})}


def write(doc: dict, path: str | None = None) -> str:
    path = path or os.path.join(WEB, "fixture.json" if doc.get("sample") else "business.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)
    return path


def card(doc: dict) -> dict:
    """the Jarvis card (tests/agora_kit.jarvis_problems contract: <= 3 kpis, <= 3 lines of 120, no markup)"""
    t = doc["total"]
    first = next((m for m in doc["models"] if not m["paused"]), doc["models"][0])
    ts = int(dt.datetime.fromisoformat(doc["asof"]).timestamp())
    return {"v": 1, "name": "Business", "status": {"level": "off" if doc.get("sample") else "ok", "label": "Example plan" if doc.get("sample") else "Your progress"},
            "kpis": [{"label": "Month 3 est.", "value": f"${t['usd_m3'][0]:,.0f}-{t['usd_m3'][1]:,.0f}"}, {"label": "Hours / week", "value": f"{t['hours'][0]}-{t['hours'][1]}"},
                     {"label": "Real so far", "value": f"${t['real_usd_month']:,.0f}/mo"}],
            "lines": [f"Next: {first['next']}"[:120], "Every $ is an estimate, not income. Nothing is sent or posted."], "t": ts, "open": "#", "theme": "#14110e", "stale_after": 86400}


def table(doc: dict) -> str:
    rng = lambda r: f"${r[0]:,.0f}-{r[1]:,.0f}"
    out = [f"{'Model':30} {'Month 1':>12} {'Month 3':>12} {'Hours/wk':>9}  Next"]
    for m in doc["models"]:
        out.append(f"{m['name'][:30]:30} {rng(m['usd_m1']):>12} {rng(m['usd_m3']):>12} {m['hours'][0]}-{m['hours'][1]:<7}  {m['next']}")
    t = doc["total"]
    out.append(f"{'All (ESTIMATE)':30} {rng(t['usd_m1']):>12} {rng(t['usd_m3']):>12} {t['hours'][0]}-{t['hours'][1]:<7}  real so far ${t['real_usd_month']:,.0f}/mo")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Business page data: every money model's next action and money (reads local files, sends nothing).")
    ap.add_argument("--fixture", action="store_true", help="write the committed DEMO fixture.json (no local state)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--print", action="store_true", dest="show")
    a = ap.parse_args(argv)
    doc = build(sample=a.fixture)
    if a.fixture:
        doc["asof"] = "2026-11-15T12:00:00+00:00"
    p = write(doc, a.out)
    if a.fixture and not a.out:
        with open(os.path.join(WEB, "jarvis.json"), "w", encoding="utf-8") as fh:
            json.dump(card(doc), fh, ensure_ascii=False)
    print(table(doc))
    print(f"\nWrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
