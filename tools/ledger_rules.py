#!/usr/bin/env python3
"""LEDGER rules: research/lit/mffu_rules.json -> tools/web_public/ledger/rules.json (the facts the Ledger app auto-fills from).

  python tools/ledger_rules.py                      # rewrite rules.json
  python tools/ledger_rules.py --rules X.json --out Y.json

Offline and read only: it reshapes a file the repo already holds. What lands in rules.json is what the page may say as fact: the owner's real eval prices
(CLAUDE.md: Builder 50K $91.80, Builder 25K $63 usually and $43 for the ATLAS 25K of 2026-10-26, one-time, $0 activation), when he paid them, and MFFU's payout
rules with their confirmation status. Anything the rulebook marks unconfirmed (the reset price) stays null: the app never invents a fee.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = os.path.join(ROOT, "research", "lit", "mffu_rules.json")
OUT = os.path.join(ROOT, "tools", "web_public", "ledger", "rules.json")
# the accounts the site knows (home.json goals.accounts ids): which plan each is, what the owner really paid and when (CLAUDE.md, mffu_rules.json notes)
ACCOUNTS = (
    ("lit50k", "builder_50k", "MFFU Builder 50K eval (Zlarior)", "owner_paid", "2026-10-18"),
    ("atlas25k", "builder_25k", "MFFU Builder 25K eval (ATLAS)", "owner_paid_2026_10_26", "2026-10-26"),
)


def val(d, *path, default=None):
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return default
        d = d[p]
    return d


def build(r):
    b50, b25, lim = r["builder_50k"], r["builder_25k"], r.get("limits", {})
    p50 = val(b50, "eval", "price", "value", default={})
    p25n = val(b25, "price", default={})
    p25 = p25n.get("value", {})
    f50, f25 = b50["sim_funded"], val(b25, "funded", "value", default={})
    live = b50.get("live", {})
    plans = {
        "builder_50k": {"name": "Builder 50K", "price_list": p50.get("list"), "price_owner": p50.get("owner_paid"), "type": p50.get("type"), "activation": val(b50, "eval", "activation_fee", "value"),
                        "reset": val(b50, "eval", "reset_fee", "value"), "target": val(b50, "eval", "profit_target", "value"), "status": val(b50, "eval", "price", "status"),
                        "payout": {"buffer": f50["buffer"]["value"], "min": f50["payout_min"]["value"], "max": f50["payout_max"]["value"], "split": f50["split"]["value"], "cycle_days": f50["payout_days_per_cycle"]["value"],
                                   "max_payouts": f50["max_sim_payouts"]["value"], "consistency": f50["consistency"]["value"], "first": f50["first_payout"]["value"], "live_min": val(live, "payouts", "value", "min"),
                                   "live_cycle": val(live, "payouts", "value", "cycle"), "status": f50["payout_min"]["status"]}},
        "builder_25k": {"name": "Builder 25K", "price_list": p25.get("list"), "price_owner": p25.get("owner_paid"), "price_owner_atlas": p25n.get("owner_paid_2026_10_26"), "type": p25.get("type"), "activation": 0.0, "reset": None,
                        "target": val(b25, "profit_target", "value"), "status": p25n.get("status"),
                        "payout": {"buffer": f25.get("buffer"), "min": f25.get("payout_min"), "max": f25.get("payout_max"), "split": f25.get("split"), "cycle_days": f25.get("payout_every_days"),
                                   "max_payouts": f25.get("max_sim_payouts"), "consistency": f25.get("consistency"), "first": "the 25K plan: 2 days to the first payout, then every 2 days (owner screenshots 2026-10-26)",
                                   "live_min": None, "live_cycle": None, "status": val(b25, "funded", "status")}},
    }
    accounts = {}
    for aid, plan, name, key, paid in ACCOUNTS:
        price = plans[plan]["price_owner_atlas"] if key == "owner_paid_2026_10_26" else plans[plan]["price_owner"]
        accounts[aid] = {"plan": plan, "name": name, "price": price, "paid": paid}
    return {
        "v": 1, "about": "Reshaped from research/lit/mffu_rules.json by tools/ledger_rules.py. The owner's real prices, one-time, $0 activation; the reset price is not published (null).",
        "source": {"file": "research/lit/mffu_rules.json", "built": r.get("built"), "claude_md": "Prop-firm prices: Builder 25K $63, the ATLAS 25K of 2026-10-26 $43, Builder 50K $91.80, one-time, $0 activation"},
        "plans": plans, "accounts": accounts, "limits": lim,
        "caveats": ["The MFFU pages could not be opened when the rulebook was built: every rule is the search engine's reading of MFFU's own pages (checked 2026-10-18); re-check before a payout.",
                    "A reset price for one-time plans is not published: enter resets yourself.", "Payout timing (how many days MFFU takes to pay) is not in the rulebook: the app shows how long a request has waited, never a promise."],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ledger rules from the MFFU rulebook (offline).")
    ap.add_argument("--rules", default=RULES)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    with open(a.rules, encoding="utf-8") as fh:
        doc = build(json.load(fh))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")
    print(f"ledger_rules: {len(doc['plans'])} plans, {len(doc['accounts'])} accounts -> {os.path.relpath(a.out, ROOT)} ({os.path.getsize(a.out)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
