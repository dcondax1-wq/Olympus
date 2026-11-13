#!/usr/bin/env python3
"""PROP PLAN, "the plan" card for the Money page (M1 millionaire plan, 2026-11-13). PAPER / PLANNING ONLY.
It reads stored research and writes ONE small JSON file. It never trades, never buys anything, never calls a service.

    python tools/money/prop_plan.py                          # writes tools/web_public/money/prop_plan.json
    python tools/money/prop_plan.py --out DIR                # writes DIR/prop_plan.json
    python tools/money/prop_plan.py --accounts FILE.json     # the owner's accounts now (same shape as ACCOUNTS below)
    python tools/money/prop_plan.py --fixture                # bundled numbers only (offline, deterministic): status "sample"
    python tools/money/prop_plan.py --selftest

Reads (all optional; bundled numbers when a file is missing):
  research/lab/millionaire_mc.json   tools/millionaire_mc.py: the whole-business Monte Carlo (fleets 1/3/5/10, the ladder)
  research/lab/rd_money.json         tools/rd_money.py: $ a month per account slot (Zlarior 50K, ATLAS 25K, BLITZ 25K)

Data contract (docs/NIGHT_BRIEF.md money contract + a "plan" block):
{
  "v": 1, "id": "prop_plan", "asof": "ISO UTC", "mode": "paper", "status": "ok|sample",
  "headline": {"text": "plain sentence", "usd_month": number},          # expected $ a month on today's accounts (Jul-Oct 2026 rate)
  "items": [{"title", "detail", "usd": number|null, "score": 0-100, "risk": "low|med|high"}],   # one per ladder step
  "notes": ["plain caveats"],
  "plan": {
    "accounts": [{"id", "name", "firm", "plan", "bot", "stage": "eval|funded|paper|planned|lost",
                  "price_usd", "drawdown_left_usd"|null, "drawdown_max_usd", "state_asof",
                  "usd_month": {"h1", "h2", "ref"}, "note"}],
    "now": {"accounts", "live_accounts", "fees_paid_usd", "usd_month": {"h1", "h2", "ref"}, "payouts_usd"},
    "step": {"n", "name"},                                         # the ladder step the owner is on now
    "next_step": {"n", "do", "when", "buy_usd", "adds_usd_month_h2"},
    "ladder": [{"n", "name", "accounts", "when", "buy", "buy_usd", "usd_month": {"h1", "h2", "ref"}}],
    "expected": {"y1_usd": {"h1", "h2", "ref"}, "to_100k_months": {...}, "to_1m_months": {...}, "p_1m_5y": {...}},
    "stop_rules": ["..."],
    "source": "research/writeups/millionaire-plan-2026-11-13.md"
  }
}
Honest numbers only: every $ is an ESTIMATE from backtests of 2026 (H1 Jan-Jun picked, H2 Jul-Oct checked) and the
2021-25 reference (REF, where LIT has no edge). Quote H2. Backtests overstate; nothing is promised.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(ROOT, "tools", "web_public", "money")
MC = os.path.join(ROOT, "research", "lab", "millionaire_mc.json")
RDM = os.path.join(ROOT, "research", "lab", "rd_money.json")
WRITEUP = "research/writeups/millionaire-plan-2026-11-13.md"
FIXED_ASOF = "2026-11-13T00:00:00Z"

# the owner's accounts (owner 2026-11-12; drawdown left at the last PC report, docs/TONIGHT_EVAL.md, 2026-11-07).
# Prices are his real one-time prices (CLAUDE.md): Builder 50K $91.80, ATLAS's Builder 25K $43, Builder 25K $63.
ACCOUNTS = [
    {"id": "zlarior50", "name": "Zlarior 50K", "firm": "MFFU", "plan": "Builder 50K", "bot": "Zlarior (LIT)", "stage": "eval",
     "price_usd": 91.80, "drawdown_left_usd": 1145.0, "drawdown_max_usd": 2000.0, "state_asof": "2026-11-07", "payouts_usd": 0.0,
     "slot": "lit50"},
    {"id": "atlas25", "name": "ATLAS 25K", "firm": "MFFU", "plan": "Builder 25K", "bot": "ATLAS", "stage": "eval",
     "price_usd": 43.00, "drawdown_left_usd": 822.0, "drawdown_max_usd": 1000.0, "state_asof": "2026-11-07", "payouts_usd": 0.0,
     "slot": "atlas25"},
    {"id": "blitz25", "name": "BLITZ 25K", "firm": "MFFU", "plan": "Builder 25K", "bot": "BLITZ", "stage": "paper",
     "price_usd": 63.00, "drawdown_left_usd": None, "drawdown_max_usd": 1000.0, "state_asof": "2026-11-12", "payouts_usd": 0.0,
     "slot": "blitz25", "note": "on paper: BLITZ is the weakest slot; a Zlarior copy pays more there once MFFU says yes in writing"},
]

# bundled numbers (research/lab/rd_money.json slots, 2026-11-03; research/lab/millionaire_mc.json, 2026-11-13, 400 paths)
SLOT_PM = {"lit50": {"h1": 823, "h2": 798, "ref": -7}, "atlas25": {"h1": 568, "h2": 382, "ref": -2},
           "blitz25": {"h1": 286, "h2": 52, "ref": -39}, "lit25": {"h1": 375, "h2": 331, "ref": -15},
           "other50": {"h1": 812, "h2": 788, "ref": -25}}
FALLBACK_MC = {
    "y1": {"1": {"h1": 0, "h2": 0, "ref": 0}, "3": {"h1": 0, "h2": 0, "ref": 0}, "5": {"h1": 0, "h2": 0, "ref": 0},
           "10": {"h1": 0, "h2": 0, "ref": 0}, "ladder": {"h1": 0, "h2": 0, "ref": 0}},
    "to_100k": {"h1": None, "h2": None, "ref": None}, "to_1m": {"h1": None, "h2": None, "ref": None},
    "p_1m_5y": {"h1": 0.0, "h2": 0.0, "ref": 0.0},
}

LADDER = [
    {"n": 0, "name": "Pass the three MFFU evals", "accounts": 3, "when": "now",
     "buy": "nothing: Zlarior 50K and ATLAS 25K are trading, BLITZ 25K on paper", "buy_usd": 0.0, "fleet": "3"},
    {"n": 1, "name": "Funded at MFFU", "accounts": 3, "when": "an eval passes ($53,000 / $26,500)",
     "buy": "nothing: switch the passed account to funded; a failed eval is bought again the next day (fees are small)",
     "buy_usd": 0.0, "fleet": "3"},
    {"n": 2, "name": "Two LIT 50K copies at Lucid / FundedNext", "accounts": 5,
     "when": "the first payout is in your bank AND each firm said yes to bots + copying your own accounts in writing",
     "buy": "LucidPro 50K (about $91 with code DGT, $129.50 list) + FundedNext 50K (up to 50% off a first purchase), a week apart",
     "buy_usd": 220.0, "fleet": "5"},
    {"n": 3, "name": "Ten accounts", "accounts": 10, "when": "$10,000 net paid out, no funded account lost in the last 2 weeks",
     "buy": "3 more LucidPro 50K (Lucid's cap is 5 funded) + 2 more FundedNext 50K, one a week", "buy_usd": 600.0, "fleet": "10"},
    {"n": 4, "name": "Your own live account", "accounts": 10,
     "when": "$30,000 kept after tax AND 3 months of live fills within the backtest's band",
     "buy": "open a personal futures account with $25,000; LIT at 1% of the account per trade (MNQ micros)",
     "buy_usd": 25000.0, "fleet": "ladder"},
]
STOP_RULES = [
    "3 evals in a row fail on one account with no pass: pause that account 2 months (the 2021-25 market looks like this).",
    "Live results 30 trades behind the backtest (profit factor under 1.0): buy no new evals until it recovers.",
    "Never more than $3,000 at risk at the same time over all accounts; never long on one account and short on another.",
    "Keep 30% of every payout for tax; only spend from what is left.",
]


def r0(x):
    return None if x is None else int(round(x))


def usd(x):
    """$1,234 / -$9 (the sign before the $)."""
    if x is None:
        return "n/a"
    return ("-" if x < 0 else "") + f"${abs(int(round(x))):,}"


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def mc_numbers(mc):
    """The few numbers the card shows, from tools/millionaire_mc.py output (or the bundled ones)."""
    if not mc or "res" not in mc:
        return copy.deepcopy(FALLBACK_MC), False
    R = mc["res"]
    sp = {"h1": "H1", "h2": "H2", "ref": "REF"}
    out = {"y1": {}, "to_100k": {}, "to_1m": {}, "p_1m_5y": {}}
    for f in ("1", "3", "5", "10", "ladder"):
        out["y1"][f] = {k: r0(R[v][f]["pm_y1"]) if v in R and f in R[v] else None for k, v in sp.items()}
    for k, v in sp.items():
        L = R.get(v, {}).get("ladder", {})
        out["to_100k"][k] = L.get("to_100000", {}).get("med")
        live = L.get("live", {})
        out["to_1m"][k] = live.get("to_1000000", {}).get("med")
        out["p_1m_5y"][k] = live.get("to_1000000", {}).get("p_hit_5y")
    return out, True


def slot_numbers(rdm):
    pm = copy.deepcopy(SLOT_PM)
    if not rdm:
        return pm, False
    try:
        s = rdm["slots"]
        L = s["single"]["lit50"]
        pm["lit50"] = {"h1": L["H1"]["pm"], "h2": L["H2"]["pm"], "ref": L["REF"]["pm"]}
        L = s["single"]["lit25_63"]
        pm["lit25"] = {"h1": L["H1"]["pm"], "h2": L["H2"]["pm"], "ref": L["REF"]["pm"]}
        pm["atlas25"] = {k.lower(): v for k, v in s["atlas_pm"].items()}
        pm["blitz25"] = {k.lower(): v for k, v in s["blitz_pm"].items()}
        return pm, True
    except (KeyError, TypeError):
        return copy.deepcopy(SLOT_PM), False


def current_step(accts):
    funded = [a for a in accts if a.get("stage") == "funded"]
    paid = sum(float(a.get("payouts_usd") or 0) for a in accts)
    live = [a for a in accts if a.get("stage") in ("eval", "funded")]
    if paid >= 10000 and len(accts) >= 10:
        return 4
    if paid >= 10000:
        return 3
    if paid > 0:
        return 2
    if funded:
        return 1
    return 0 if live else 0


def build(accts=None, fixture=False, asof=None):
    accts = copy.deepcopy(accts if accts is not None else ACCOUNTS)
    mcn, mc_ok = (copy.deepcopy(FALLBACK_MC), False) if fixture else mc_numbers(load_json(MC))
    pm, rd_ok = (copy.deepcopy(SLOT_PM), False) if fixture else slot_numbers(load_json(RDM))
    for a in accts:
        a["usd_month"] = pm.get(a.get("slot"), {"h1": None, "h2": None, "ref": None})
        if a.get("stage") in ("paper", "planned", "lost"):
            a["usd_month_counted"] = False
        else:
            a["usd_month_counted"] = True
    counted = [a for a in accts if a["usd_month_counted"]]
    now_pm = {k: r0(sum(a["usd_month"][k] or 0 for a in counted)) for k in ("h1", "h2", "ref")}
    fees = round(sum(float(a.get("price_usd") or 0) for a in accts), 2)
    paid = round(sum(float(a.get("payouts_usd") or 0) for a in accts), 2)
    n = current_step(accts)
    ladder = []
    for st in LADDER:
        row = {k: v for k, v in st.items() if k != "fleet"}
        row["usd_month"] = mcn["y1"].get(st["fleet"], {"h1": None, "h2": None, "ref": None})
        ladder.append(row)
    nxt = ladder[min(n + 1, len(ladder) - 1)]
    cur = ladder[n]
    adds = None
    if nxt["usd_month"].get("h2") is not None and cur["usd_month"].get("h2") is not None and nxt["n"] != cur["n"]:
        adds = r0(nxt["usd_month"]["h2"] - cur["usd_month"]["h2"])
    on = [a["name"] for a in accts if a.get("stage") in ("eval", "funded")]
    head = (f"{len(on)} accounts trading ({', '.join(on)}): about {usd(now_pm['h2'])} a month once funded at the Jul-Oct 2026 rate "
            f"(estimate; {usd(now_pm['ref'])} in a 2021-25-like market). Next step: {nxt['name']}, when {nxt['when']}.")
    items = []
    for row in ladder:
        h2, ref = row["usd_month"].get("h2"), row["usd_month"].get("ref")
        items.append({"title": f"Step {row['n']}: {row['name']} ({row['accounts']} accounts)",
                      "detail": f"When: {row['when']}. Buy: {row['buy']}." + (
                          f" First-year estimate about {usd(h2)} a month (Jul-Oct 2026 rate), {usd(ref)} in a 2021-25 market." if h2 is not None and ref is not None else ""),
                      "usd": h2, "score": 90 if row["n"] == n else 70 if row["n"] == n + 1 else 40,
                      "risk": "low" if row["n"] <= 1 else "med" if row["n"] <= 3 else "high"})
    plan = {
        "accounts": [{k: a.get(k) for k in ("id", "name", "firm", "plan", "bot", "stage", "price_usd", "drawdown_left_usd",
                                            "drawdown_max_usd", "state_asof", "payouts_usd", "usd_month", "usd_month_counted", "note")}
                     for a in accts],
        "now": {"accounts": len(accts), "live_accounts": len(on), "fees_paid_usd": fees, "payouts_usd": paid, "usd_month": now_pm},
        "step": {"n": n, "name": cur["name"]},
        "next_step": {"n": nxt["n"], "do": nxt["buy"], "when": nxt["when"], "buy_usd": nxt["buy_usd"], "adds_usd_month_h2": adds},
        "ladder": ladder,
        "expected": {"y1_usd_month": mcn["y1"], "to_100k_months": mcn["to_100k"], "to_1m_months": mcn["to_1m"],
                     "p_1m_5y_pct": mcn["p_1m_5y"]},
        "stop_rules": STOP_RULES,
        "source": WRITEUP,
    }
    notes = [
        "Estimates from backtests: H1 = Jan-Jun 2026 (picked), H2 = Jul-Oct 2026 (checked, the one to quote), REF = 2021-25, where LIT shows no edge (profit factor 1.01). Backtests overstate; nothing here is promised.",
        "All LIT copies are one bet: in a bad month they lose together. Each account can only lose its eval price, never more.",
        "Firm rules change: ask each firm in writing about bots and copying your own accounts before buying (MFFU has not said yes to copies).",
        "Not tax advice: prop payouts are usually contractor income; a personal futures account is taxed 60/40 (Section 1256). Ask a tax professional.",
        f"Account drawdown figures are from the last PC report ({', '.join(sorted({a.get('state_asof') or '?' for a in accts}))}).",
    ]
    status = "ok" if (mc_ok and rd_ok and not fixture) else "sample"
    return {"v": 1, "id": "prop_plan", "asof": asof or (FIXED_ASOF if fixture else dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
            "mode": "paper", "status": status, "headline": {"text": head, "usd_month": now_pm["h2"]}, "items": items, "notes": notes,
            "plan": plan}


def write(doc, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "prop_plan.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return path


def selftest():
    bad = []

    def ok(name, cond, got=None):
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  (got {got!r})"))
        if not cond:
            bad.append(name)

    d = build(fixture=True)
    ok("contract keys", all(k in d for k in ("v", "id", "asof", "mode", "status", "headline", "items", "notes", "plan")), list(d))
    ok("paper mode, sample status with the bundled numbers", d["mode"] == "paper" and d["status"] == "sample", (d["mode"], d["status"]))
    ok("three accounts, owner's real prices ($91.80 + $43 + $63 = $197.80)", d["plan"]["now"]["fees_paid_usd"] == 197.8, d["plan"]["now"])
    ok("BLITZ on paper is not counted in $ a month", d["plan"]["now"]["usd_month"]["h2"] == SLOT_PM["lit50"]["h2"] + SLOT_PM["atlas25"]["h2"],
       d["plan"]["now"]["usd_month"])
    ok("step 0 now, next = step 1", d["plan"]["step"]["n"] == 0 and d["plan"]["next_step"]["n"] == 1, (d["plan"]["step"], d["plan"]["next_step"]))
    ok("ladder of 5 steps, one item each", len(d["plan"]["ladder"]) == 5 and len(d["items"]) == 5)
    ok("no 'of 10' day counts in the text", " of 10 " not in json.dumps(d))
    a = copy.deepcopy(ACCOUNTS)
    a[0]["stage"], a[0]["payouts_usd"] = "funded", 1600.0
    d2 = build(a, fixture=True)
    ok("a payout moves to step 2 (buy the copies next = step 3)", d2["plan"]["step"]["n"] == 2 and d2["plan"]["next_step"]["n"] == 3, d2["plan"]["step"])
    a[0]["payouts_usd"] = 12000.0
    ok("$10K paid moves to step 3", build(a, fixture=True)["plan"]["step"]["n"] == 3)
    real = build()
    ok("reads the stored research when present", real["status"] in ("ok", "sample"), real["status"])
    ok("headline has a $ figure", "$" in real["headline"]["text"], real["headline"]["text"])
    print("selftest:", "OK" if not bad else f"{len(bad)} FAILED")
    return 0 if not bad else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--accounts", help="JSON file: a list of accounts in the ACCOUNTS shape")
    ap.add_argument("--fixture", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    accts = load_json(a.accounts) if a.accounts else None
    doc = build(accts, fixture=a.fixture)
    p = write(doc, a.out)
    print(f"prop_plan: {doc['status']} -> {p}\n  {doc['headline']['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
