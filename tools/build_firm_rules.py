"""Build research/props/firm_rules.json: the firm rule profiles the fleet layer (engine/firms.py) checks every order against.

Sources (all already in the repo, nothing fetched here):
  research/lit/mffu_rules.json   the MFFU Builder 50K / 25K rulebook (status confirmed / conflict / unconfirmed per value)
  research/lit/prop_firms.json   the 60-plan rule table of the LIT prop-firm study (searched 2026-10-18; "unconfirmed" notes
                                 name every value that was assumed)
  research/props/firms.json      the prop-firm hub (st confirmed / conflict / unconfirmed per value, 2026-10-18..20)
  research/props/firm_research.json  the newest re-read of the firms' own help centers (team A4, 2026-11-14: LucidPro /
                                 LucidFlex 50K, FundedNext Rapid Daily 50K, the Lucid / FundedNext firm rules); applied
                                 LAST, value by value (it carries the full {"v", "verified", "src", "date", "n"} of each)

Every value is {"v": value, "verified": bool, "src": [...], "date": "yyyy-mm-dd", "n": note}:
  verified true   the repo's research marks it confirmed: the firm's own help / plan page (read through web search), or the
                  owner's own screenshots / receipts (MFFU). Re-check on the firm's site before money depends on it.
  verified false  a third-party summary, a conflict between sources, or one source only.
  v null          unknown: the value was assumed in research or not found. Never guessed here.
  v "none"        the rule does not exist on that plan (e.g. no daily loss limit), per the sources.
Prices: only the owner's real prices (MFFU); every other price is null ("check current codes before buying", CLAUDE.md).

  python tools/build_firm_rules.py           rebuild the file
  python tools/build_firm_rules.py --check   exit 1 when the stored file differs from a rebuild
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "props", "firm_rules.json")
MFFU = os.path.join(ROOT, "research", "lit", "mffu_rules.json")
PROP = os.path.join(ROOT, "research", "lit", "prop_firms.json")
HUB = os.path.join(ROOT, "research", "props", "firms.json")
RESEARCH = os.path.join(ROOT, "research", "props", "firm_research.json")
BUILT = "2026-11-14"
FIRMS_WANTED = {"MyFundedFutures": "mffu", "Lucid Trading": "lucid", "FundedNext Futures": "fundednext",
                "Apex Trader Funding": "apex", "Topstep": "topstep", "Take Profit Trader": "tpt", "Alpha Futures": "alpha"}
FIRM_NAMES = {"mffu": "MyFundedFutures (MFFU)", "lucid": "Lucid Trading", "fundednext": "FundedNext Futures",
              "apex": "Apex Trader Funding", "topstep": "Topstep", "tpt": "Take Profit Trader", "alpha": "Alpha Futures"}
PLAN_NAMES = {"Builder": "Builder", "Rapid": "Rapid", "Rapid EOD": "Rapid EOD", "Pro": "Pro", "Combine (Standard path)": "Combine",
              "4.0 EOD": "4.0 EOD", "LucidPro": "LucidPro", "LucidFlex": "LucidFlex", "Test": "Test", "Standard": "Standard",
              "Zero": "Zero", "Advanced": "Advanced", "Rapid Pro": "Rapid Pro", "Rapid Daily": "Rapid Daily", "Legacy": "Legacy"}
SEARCH_DATE = "2026-10-18"
HUB_DATE = "2026-10-20"
TRAIL = {"eod": "eod", "intra": "intraday", "static": "static"}


def F(v, verified=False, src=None, date=SEARCH_DATE, n=None):
    """One value. src None = the plan's "sources" list (a third-party table row)."""
    out = {"v": v, "verified": bool(verified) and v is not None, "date": date}
    if src:
        out["src"] = list(src)
    if n:
        out["n"] = n
    return out


def _load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------------------------------------ assumed -> unknown
# prop_firms.json "unconfirmed" notes -> the fields that were ASSUMED (unknown, v null) for that plan
ASSUMED = [
    (r"DLL soft assumed|daily guard soft assumed", [("eval", "dll_type"), ("funded", "dll_type")]),
    (r"PA payout caps and 5-day cycle assumed", [("payout", "max"), ("payout", "win_days")]),
    (r"payout min/max assumed", [("payout", "min"), ("payout", "max")]),
    (r"max contracts (not found|assumed)", [("eval", "max_micros"), ("eval", "max_minis"), ("funded", "max_micros"), ("funded", "max_minis")]),
    (r"drawdown lock at the start balance assumed", [("eval", "lock"), ("funded", "lock")]),
    (r"XFA payout cap \$5,000 assumed", [("payout", "max")]),
    (r"funded payout cap / buffer assumed", [("payout", "max"), ("payout", "buffer")]),
    (r"payout caps (per size )?assumed", [("payout", "max")]),
    (r"funded payout rules assumed", [("payout", "min"), ("payout", "max"), ("payout", "share")]),
    (r"funded split / payout rules assumed", [("payout", "split"), ("payout", "min"), ("payout", "max")]),
    (r"target \$3,000 assumed", [("eval", "target")]),
    (r"min days not found", [("eval", "min_days")]),
    (r"5-winning-day rule possibly removed", [("payout", "win_days")]),
]
CONFLICT = [
    (r"eval consistency", [("eval", "consistency")]),
    (r"min (2 trading days|days 3)", [("eval", "min_days")]),
    (r"DLL soft/optional", [("eval", "dll"), ("eval", "dll_type")]),
    (r"no DLL on TopstepX", [("eval", "dll"), ("funded", "dll")]),
]

# hub "confirmed" plan values (research/props/firms.json, the firm's own page per the search) -> verified
HUB_VERIFIED = {
    "lucid_pro_50k": {("eval", "target"): ["lucid_test"], ("eval", "dd_amount"): ["lucid_test"], ("eval", "dd_type"): ["lucid_test"],
                      ("eval", "lock"): ["lucid_test"], ("eval", "dll"): ["etf_lucid_dll"], ("eval", "dll_type"): ["etf_lucid_dll"],
                      ("eval", "consistency"): ["ptv_lucid_pro"], ("eval", "max_micros"): ["ptv_lucid_pro"],
                      ("eval", "max_minis"): ["ptv_lucid_pro"], ("funded", "dd_amount"): ["ptv_lucid_pro"],
                      ("funded", "dd_type"): ["ptv_lucid_pro"], ("payout", "split"): ["qv_lucid_pay"],
                      ("payout", "buffer"): ["ptv_lucid_pro", "qv_lucid_pay"]},
    "fn_rapid_daily_50k": {("eval", "target"): ["fn_rd_rules"], ("eval", "dd_amount"): ["fn_dll"], ("eval", "dd_type"): ["fn_dll"],
                           ("eval", "lock"): ["fn_dll"], ("eval", "dll"): ["fn_dll"], ("eval", "dll_type"): ["fn_dll"],
                           ("eval", "consistency"): ["fn_rd_rules"], ("funded", "dd_amount"): ["fn_rd_funded"],
                           ("funded", "dd_type"): ["fn_rd_funded"], ("funded", "dll"): ["fn_dll"], ("funded", "dll_type"): ["fn_dll"],
                           ("payout", "split"): ["fn_rd_funded"], ("payout", "consistency"): ["fn_rd_funded"],
                           ("payout", "buffer"): ["fn_rd_funded"]},
    "mffu_rapid_50k": {("eval", "target"): ["mffu_rapid"], ("eval", "dd_amount"): ["mffu_rapid"], ("eval", "dd_type"): ["mffu_rapid"],
                       ("eval", "dll"): ["mffu_rapid"], ("eval", "min_days"): ["mffu_rapid"], ("funded", "dd_type"): ["mffu_rapid", "ft_mffu"],
                       ("funded", "dd_amount"): ["mffu_rapid"], ("funded", "lock"): ["mffu_rapid"], ("funded", "dll"): ["mffu_rapid"],
                       ("payout", "buffer"): ["mffu_rapid_pay"], ("payout", "split"): ["mffu_rapid_pay"],
                       ("payout", "consistency"): ["mffu_rapid_pay"]},
    "mffu_rapid_eod_50k": {("eval", "target"): ["mffu_rapid_eod"], ("eval", "dd_amount"): ["mffu_rapid_eod"],
                           ("eval", "dd_type"): ["mffu_rapid_eod"], ("eval", "dll"): ["mffu_rapid_eod"],
                           ("eval", "consistency"): ["mffu_rapid_eod", "fm_rapid_eod"], ("eval", "min_days"): ["mffu_rapid_eod"],
                           ("eval", "max_micros"): ["mffu_rapid_eod"], ("eval", "max_minis"): ["mffu_rapid_eod"],
                           ("funded", "dd_amount"): ["mffu_rapid_eod"], ("funded", "dd_type"): ["mffu_rapid_eod"],
                           ("funded", "dll"): ["mffu_rapid_eod"], ("payout", "buffer"): ["mffu_rapid_eod"],
                           ("payout", "min"): ["mffu_rapid_eod"], ("payout", "split"): ["mffu_rapid_eod"],
                           ("payout", "consistency"): ["mffu_rapid_eod"]},
}
# hub values that REPLACE the table's (the hub is newer and marks them confirmed)
HUB_VALUES = {
    "topstep_50k": {("payout", "max"): (2000.0, ["topstep_pay"], "XFA caps $2,000 on the 50K (hub, confirmed); the study had assumed $5,000"),
                    ("payout", "min"): (125.0, ["topstep_pay"], None), ("payout", "split"): (0.9, ["topstep_pay"], None)},
    "fn_rapid_daily_50k": {("payout", "max"): (1200.0, ["fn_rd_funded"], "$250 - $1,200 a request (hub, confirmed)"),
                           ("payout", "min"): (250.0, ["fn_rd_funded"], None),
                           ("payout", "max_payouts"): (5, ["fn_rd_funded"], "the account ends after 5 rewards")},
    "lucid_pro_50k": {("payout", "max"): (2000.0, ["ptv_lucid_caps"], "up to $2,000, then $2,500 (rising cap)"),
                      ("payout", "max_payouts"): (5, ["ptv_lucid_live"], "5 payouts, then a live review"),
                      ("payout", "buffer"): (2100.0, ["ptv_lucid_pro", "qv_lucid_pay"], "balance $52,100 and >= $500 profit in the cycle")},
}

# firm-level rules (hub firms.json + mffu_rules.json): bots, copy trading, hedging, flat time
FIRM_RULES = {
    "mffu": {"bots": ("allowed", True, ["mffu_rules.json builder_50k.eval.automation"], "2026-10-18",
                      "bots allowed when set to your own parameters, with oversight; HFT and sim-fill exploits banned"),
             "copy_trading": (None, False, ["mffu_rules.json builder_50k.eval.copy_trading"], "2026-10-18",
                              "copying between your OWN accounts: not stated; mirroring 'for an unfair advantage' is banned; ask MFFU support in writing first"),
             "hedging": ("banned_all_accounts", True, ["mffu_rules.json builder_50k.eval.hedging"], "2026-10-18",
                         "no long and short on the same underlying at the same time, also across your accounts"),
             "flat_by": ("16:10", True, ["mffu_rules.json builder_50k.eval.trading_hours"], "2026-10-18",
                         "flat by 16:10 ET (auto-liquidation); on CME half days you flatten yourself before the early halt"),
             "ninjatrader": (True, True, ["mffu_b50"], HUB_DATE, None)},
    "lucid": {"bots": ("allowed", True, ["pmt_auto", "ptv_lucid_pro"], HUB_DATE, "automated systems and trade copiers permitted; HFT / microscalping banned"),
              "copy_trading": ("allowed", False, ["pmt_auto"], HUB_DATE, "trade copiers permitted (one source)"),
              "hedging": ("banned", False, ["prop_firms.json lucid bot note"], SEARCH_DATE, "no HFT / hedging (third-party summary)"),
              "flat_by": (None, False, [], SEARCH_DATE, None),
              "ninjatrader": (True, True, ["ptv_lucid_pro"], HUB_DATE, None)},
    "fundednext": {"bots": ("allowed", True, ["fn_terms", "fn_bots"], HUB_DATE, "EAs / bots / AI allowed in the Challenge and the funded account (terms 2026-09-25)"),
                   "copy_trading": ("own_accounts", True, ["fn_terms"], HUB_DATE, "copying your own accounts only"),
                   "hedging": (None, False, [], SEARCH_DATE, None),
                   "flat_by": (None, False, [], SEARCH_DATE, None),
                   "ninjatrader": (True, True, ["fn_platforms"], HUB_DATE, None)},
    "apex": {"bots": ("prohibited", False, ["prop_firms.json apex bot note"], SEARCH_DATE, "Apex bans automated trading on all accounts (Sep 2026, third-party)"),
             "copy_trading": (None, False, [], SEARCH_DATE, None), "hedging": (None, False, [], SEARCH_DATE, None),
             "flat_by": (None, False, [], SEARCH_DATE, None), "ninjatrader": (None, False, [], SEARCH_DATE, None)},
    "topstep": {"bots": ("api_only", False, ["h2t_topstep", "tg_auto"], HUB_DATE, "API bots on the Combine / XFA, banned on Live Funded; no VPS"),
                "copy_trading": (None, False, [], HUB_DATE, "not checked"), "hedging": (None, False, [], SEARCH_DATE, None),
                "flat_by": (None, False, [], SEARCH_DATE, None),
                "ninjatrader": (False, False, ["tg_auto"], HUB_DATE, "TopstepX only for new sign-ups (NinjaTrader not offered): this bot cannot route there today")},
    "tpt": {"bots": (None, False, [], SEARCH_DATE, "not found: check before automating"),
            "copy_trading": (None, False, [], SEARCH_DATE, None), "hedging": (None, False, [], SEARCH_DATE, None),
            "flat_by": (None, False, [], SEARCH_DATE, None), "ninjatrader": (None, False, [], SEARCH_DATE, None)},
    "alpha": {"bots": ("semi_only", False, ["prop_firms.json alpha bot note"], SEARCH_DATE, "semi-automated only (fully automated prohibited)"),
              "copy_trading": (None, False, [], SEARCH_DATE, None), "hedging": (None, False, [], SEARCH_DATE, None),
              "flat_by": (None, False, [], SEARCH_DATE, None),
              "ninjatrader": (False, False, ["prop_firms.json alpha bot note"], SEARCH_DATE, "NinjaTrader / Tradovate not offered for new accounts since 2026-07-12")},
}
SIZING_PRESET = {25: "mffu_builder_25k", 50: "mffu_builder_50k"}     # the bot's sizing per plan size (engine/multi_account.PRESETS)


def _dll_type(t):
    return {"soft": "soft", "hard": "hard"}.get(str(t or "").lower())


def _news(p, stage):
    s = str(p.get("news") or "").lower()
    if s.startswith("allowed") and "tier-1" not in s and "check" not in s:
        return "none"
    if "tier-1" in s and stage == "funded":
        return {"flat_min_before": 2, "flat_min_after": 2, "events": "tier1"}
    if "tier-1" in s and stage == "eval":
        return "none"
    return None


def plan_from_table(p: dict) -> dict:
    """One prop_firms.json plan -> the profile (values verified false: a third-party summary of 2026-10-18)."""
    srcs = None                         # every table value: the plan's "sources" (kept once per plan)
    f = p.get("funded") or {}
    size = int(p["size"])
    n_dll = "no firm daily loss limit per the sources" if p.get("dll") is None else None
    E = {"start": F(float(size * 1000), True, ["plan size"], SEARCH_DATE, "the plan's size"),
         "target": F(p.get("target"), src=srcs),
         "dd_type": F(TRAIL.get(p.get("trail")), src=srcs),
         "dd_amount": F(p.get("mll"), src=srcs),
         "lock": F(p.get("lock"), src=srcs, n="the trailing floor stops this far above the start balance"),
         "dll": F(p.get("dll") if p.get("dll") is not None else "none", src=srcs, n=n_dll),
         "dll_type": F(_dll_type(p.get("dll_type")) if p.get("dll") is not None else "none", src=srcs),
         "max_micros": F(p.get("max_micros"), src=srcs), "max_minis": F(p.get("max_minis"), src=srcs),
         "consistency": F(p.get("cons") if p.get("cons") is not None else "none", src=srcs,
                          n="eval best day <= this share of the profit target / total profit"),
         "min_days": F(p.get("min_days"), src=srcs), "news": F(_news(p, "eval"), src=srcs, n=str(p.get("news") or "")[:120] or None)}
    FU = {"dd_type": F(TRAIL.get(f.get("trail")), src=srcs), "dd_amount": F(p.get("mll"), src=srcs),
          "lock": F(f.get("lock"), src=srcs), "dll": F(f.get("dll") if f.get("dll") is not None else "none", src=srcs),
          "dll_type": F(_dll_type(p.get("dll_type")) if f.get("dll") is not None else "none", src=srcs),
          "max_micros": F(p.get("max_micros"), src=srcs), "max_minis": F(p.get("max_minis"), src=srcs),
          "news": F(_news(p, "funded"), src=srcs, n=str(p.get("news") or "")[:120] or None),
          "max_active": F(None, n="how many funded accounts of this plan one person may hold: not found")}
    PO = {"buffer": F(f.get("buffer"), src=srcs), "min": F(f.get("pay_min"), src=srcs), "max": F(f.get("pay_max") if f.get("pay_max") is not None else None, src=srcs),
          "share": F(f.get("pay_pct"), src=srcs, n="a request <= this share of the profit / balance above the buffer"),
          "split": F(f.get("split"), src=srcs), "consistency": F(f.get("cons") if f.get("cons") is not None else "none", src=srcs),
          "min_days": F(f.get("cycle_days") or None, src=srcs, n="trading days a payout cycle"),
          "win_days": F(f.get("win_days") or None, src=srcs, n="winning days a payout cycle"),
          "max_payouts": F(f.get("max_payouts"), src=srcs), "first_wait_days": F(f.get("first_wait"), src=srcs)}
    blocks = {"eval": E, "funded": FU, "payout": PO}
    notes = list(p.get("unconfirmed") or [])
    for rx, fields in ASSUMED:
        if any(re.search(rx, x) for x in notes):
            for b, k in fields:
                if k in blocks[b]:
                    blocks[b][k] = F(None, src=srcs, n="assumed in the research, not found: unknown")
    for rx, fields in CONFLICT:
        hit = next((x for x in notes if re.search(rx, x)), None)
        if hit:
            for b, k in fields:
                if k in blocks[b] and blocks[b][k]["v"] is not None:
                    blocks[b][k]["n"] = f"sources disagree: {hit}"
    return {"firm": FIRMS_WANTED[p["firm"]], "name": f"{PLAN_NAMES.get(p['plan'], p['plan'])} {size}K", "size": size * 1000,
            "price": F(None, n="not quoted: use the owner's real price; look up the current discount code before buying (CLAUDE.md)"),
            "sizing_preset": SIZING_PRESET.get(size, "mffu_builder_50k" if size >= 50 else "mffu_builder_25k"),
            "eval": E, "funded": FU, "payout": PO, "notes": notes, "sold": p.get("sold"), "sources": list(p.get("sources") or [])}


def _m(node, key):
    """mffu_rules.json value -> (value, verified, src, date, note)."""
    x = node.get(key) or {}
    return x.get("value"), x.get("status") == "confirmed", list(x.get("source") or []), x.get("checked") or SEARCH_DATE, x.get("note")


def mffu_overlay(prof: dict, M: dict, plan: str):
    """MFFU Builder 50K / 25K from research/lit/mffu_rules.json: status confirmed -> verified (the help center + plan
    page, and the owner's dashboard screenshots of 2026-10-26 for the 25K)."""
    E, FU, PO = prof["eval"], prof["funded"], prof["payout"]
    if plan == "mffu_builder_50k":
        ev, sf = M["builder_50k"]["eval"], M["builder_50k"]["sim_funded"]
        v, ok, s, d, n = _m(ev, "start_balance")
        E["start"] = F(float(v), ok, s, d, n)
        v, ok, s, d, n = _m(ev, "profit_target")
        E["target"] = F(float(v), ok, s, d, n)
        v, ok, s, d, n = _m(ev, "max_loss")
        E["dd_type"] = F("eod", ok, s, d, "EOD trailing: moves only at the session close, up only; open losses count intraday")
        E["dd_amount"] = F(float(v["amount"]), ok, s, d)
        E["lock"] = F(100.0, ok, s, d, "the floor stops at start + $100 ($50,100)")
        v, ok, s, d, n = _m(ev, "daily_loss_limit")
        E["dll"] = F(float(v["amount"]), ok, s, d, "soft: trading paused for the rest of the session, the account stays open")
        E["dll_type"] = F("soft", ok, s, d)
        v, ok, s, d, n = _m(ev, "max_contracts")
        E["max_minis"] = F(int(v["minis"]), ok, s, d, "minis and micros count together (10 micros = 1 mini); orders above are auto-rejected")
        E["max_micros"] = F(int(v["micros"]), ok, s, d)
        v, ok, s, d, n = _m(ev, "consistency_eval")
        E["consistency"] = F("none", ok, s, d, "no best-day rule in the Builder eval")
        v, ok, s, d, n = _m(ev, "min_trading_days_eval")
        E["min_days"] = F(int(v), ok, s, d, n)
        v, ok, s, d, n = _m(ev, "news_trading")
        E["news"] = F("none", ok, s, d, "Builder: news trading unrestricted in the eval and sim funded")
        v, ok, s, d, n = _m(sf, "max_loss")
        FU["dd_type"] = F("eod", ok, s, d)
        FU["dd_amount"] = F(float(v["amount"]), ok, s, d)
        FU["lock"] = F(100.0, ok, s, d, "floor stops at +$100 above the start")
        v, ok, s, d, n = _m(sf, "daily_loss_limit")
        FU["dll"] = F(float(v["amount"]), ok, s, d)
        FU["dll_type"] = F("soft", ok, s, d)
        v, ok, s, d, n = _m(sf, "max_contracts")
        FU["max_minis"] = F(int(v["minis"]), ok, s, d)
        FU["max_micros"] = F(int(v["micros"]), ok, s, d)
        v, ok, s, d, n = _m(sf, "news")
        FU["news"] = F("none", ok, s, d, "unrestricted")
        v, ok, s, d, n = _m(ev, "accounts")
        FU["max_active"] = F(int(v["sim_funded_active"]), ok, s, d, "1 active sim-funded Builder 50K per person")
        for k, mk, cast in (("buffer", "buffer", float), ("min", "payout_min", float), ("max", "payout_max", float),
                            ("split", "split", float), ("consistency", "consistency", float), ("min_days", "payout_days_per_cycle", int),
                            ("max_payouts", "max_sim_payouts", int)):
            v, ok, s, d, n = _m(sf, mk)
            PO[k] = F(cast(v), ok, s, d, n)
        PO["first_wait_days"] = F(2, True, list(sf.get("first_payout", {}).get("source") or []), "2026-10-18",
                                  "first payout: >= $500 above the buffer and 48 hours after the first trade")
        PO["share"] = F("none", True, [], "2026-10-18", "no share-of-profit cap: $500 - $2,000 a request")
        PO["win_days"] = F("none", True, [], "2026-10-18", "no winning-day count: 2 traded days a cycle")
        prof["price"] = F(91.8, True, ["owner receipt 2026-10-18"], "2026-10-18",
                          "the owner's real price with his MFFU code (list $153); one-time, $0 activation")
        prof["owner"] = {"has": "Zlarior / LIT eval since 2026-10-19"}
    elif plan == "mffu_builder_25k":
        b = M["builder_25k"]
        v, ok, s, d, n = _m(b, "profit_target")
        E["target"] = F(float(v), ok, s, d)
        E["start"] = F(25000.0, True, ["plan size"], d, "the plan's size")
        v, ok, s, d, n = _m(b, "max_loss")
        E["dd_type"] = F("eod", ok, s, d)
        E["dd_amount"] = F(float(v["amount"]), ok, s, d)
        E["lock"] = F(100.0, ok, s, d, "the floor stops at start + $100 ($25,100)")
        v, ok, s, d, n = _m(b, "daily_loss_limit")
        E["dll"] = F(float(v["amount"]), ok, s, d, "soft (owner's dashboard screenshots 2026-10-26)")
        E["dll_type"] = F("soft", ok, s, d)
        v, ok, s, d, n = _m(b, "max_contracts")
        E["max_minis"] = F(int(v["minis"]), ok, s, d)
        E["max_micros"] = F(int(v["micros"]), ok, s, d)
        v, ok, s, d, n = _m(b, "consistency_eval")
        E["consistency"] = F("none", ok, s, d, "no best-day rule in the Builder eval")
        E["min_days"] = F(1, True, ["https://help.myfundedfutures.com/en/articles/17036130-builder-plan-25k-a-comprehensive-look"],
                          "2026-11-17", "1 day (help center re-check 2026-11-17; was a conflict)")
        E["news"] = F("none", True, ["mffu_rules.json builder_50k.eval.news_trading"], "2026-10-18", "Builder: unrestricted")
        fu = b["funded"]
        ok, s, d = fu.get("status") == "confirmed", list(fu.get("source") or []), fu.get("checked") or "2026-10-26"
        v = fu["value"]
        FU["dd_type"] = F("eod", ok, s, d)
        FU["dd_amount"] = F(float(v["max_loss"]["amount"]), ok, s, d)
        FU["lock"] = F(100.0, ok, s, d, "floor stops at +$100 above the start")
        FU["dll"] = F(600.0, ok, s, d)
        FU["dll_type"] = F("soft", ok, s, d)
        FU["max_minis"] = F(2, ok, s, d)
        FU["max_micros"] = F(20, ok, s, d)
        FU["news"] = F("none", True, ["mffu_rules.json builder_50k.sim_funded.news"], "2026-10-18", "unrestricted")
        FU["max_active"] = F(int(v["sim_funded_active"]), ok, s, d, "up to 2 active sim-funded Builder 25K accounts per person")
        PO["buffer"] = F(float(v["buffer"]), ok, s, d)
        PO["min"] = F(float(v["payout_min"]), ok, s, d)
        PO["max"] = F(float(v["payout_max"]), ok, s, d)
        PO["split"] = F(float(v["split"]), ok, s, d)
        PO["consistency"] = F(float(v["consistency"]), ok, s, d)
        PO["max_payouts"] = F(int(v["max_sim_payouts"]), ok, s, d)
        PO["min_days"] = F(2, False, ["mffu_rules.json limits.builder_25k.cycle_days"], "2026-10-18", "as the 50K (2 traded days a cycle)")
        PO["first_wait_days"] = F(2, False, [], "2026-10-18", "as the 50K (48 hours after the first trade)")
        PO["share"] = F("none", False, [], "2026-10-18", "as the 50K")
        PO["win_days"] = F("none", False, [], "2026-10-18", "as the 50K")
        prof["price"] = F(63.0, True, ["owner receipts"], "2026-10-26",
                          "the owner's real price with his MFFU code ($63; the ATLAS 25K of 2026-10-26 cost $43); list $105")
        prof["owner"] = {"has": "ATLAS eval (account B) since 2026-10-26; BLITZ's 25K (account C) next week"}


def _value(x) -> dict:
    """A research value -> the stored shape (verified only with a value; src / n kept)."""
    out = {"v": x.get("v"), "verified": bool(x.get("verified")) and x.get("v") is not None, "date": x.get("date") or SEARCH_DATE}
    if x.get("src"):
        out["src"] = list(x["src"])
    if x.get("n"):
        out["n"] = x["n"]
    return out


def research_overlay(plans: dict, firms: dict, R: dict):
    """research/props/firm_research.json (the newest re-read of the firms' own pages) replaces the older values, field by
    field; new fields (e.g. payout cycle_min / max_after_first, funded max_micros_by_profit, firm inactivity_days / hold)
    are added. Prices stay null here (CLAUDE.md: only the owner's real prices are values): a price block keeps v null."""
    for pid, blocks in (R.get("plans") or {}).items():
        prof = plans.get(pid)
        if prof is None:
            continue
        for b in ("eval", "funded", "payout"):
            for k, x in (blocks.get(b) or {}).items():
                prof[b][k] = _value(x)
        if blocks.get("price"):
            prof["price"] = {**_value(blocks["price"]), "v": None, "verified": False}
        if blocks.get("notes"):
            prof["notes"] = list(blocks["notes"])
    for fid, fr in (R.get("firms") or {}).items():
        if fid not in firms:
            continue
        for k, x in fr.items():
            firms[fid][k] = _value(x)
        plist = firms[fid].pop("plans")
        firms[fid]["plans"] = plist                      # "plans" stays the last key


def build() -> dict:
    M, P, H = _load(MFFU), _load(PROP), _load(HUB)
    R = _load(RESEARCH) if os.path.exists(RESEARCH) else {}
    plans = {}
    for p in P["plans"]:
        if p["firm"] not in FIRMS_WANTED:
            continue
        prof = plan_from_table(p)
        if p["id"] in ("mffu_builder_50k", "mffu_builder_25k"):
            mffu_overlay(prof, M, p["id"])
        for (b, k), srcs in (HUB_VERIFIED.get(p["id"]) or {}).items():
            cur = prof["eval" if b == "eval" else b][k]
            if cur["v"] is not None:
                prof[b][k] = {**cur, "verified": True, "src": srcs, "date": HUB_DATE}
        for (b, k), (v, srcs, n) in (HUB_VALUES.get(p["id"]) or {}).items():
            prof[b][k] = F(v, True, srcs, HUB_DATE, n)
        plans[p["id"]] = prof
    firms = {}
    for fid, rules in FIRM_RULES.items():
        firms[fid] = {"name": FIRM_NAMES[fid], **{k: F(v, ok, s, d, n) for k, (v, ok, s, d, n) in rules.items()},
                      "plans": sorted(k for k, x in plans.items() if x["firm"] == fid)}
    research_overlay(plans, firms, R)
    hub_src = {**(H.get("sources") or {}), **(R.get("sources") or {})}      # the newest research wins a shared key
    used = sorted({s for pr in plans.values() for blk in ("eval", "funded", "payout") for x in pr[blk].values() for s in x.get("src") or []}
                  | {s for pr in plans.values() for s in (pr.get("price") or {}).get("src") or []}
                  | {s for f in firms.values() for k, x in f.items() if isinstance(x, dict) for s in x.get("src") or []})
    return {"v": 1, "built": BUILT, "title": "Firm rule profiles for the fleet layer (engine/firms.py)",
            "how_to_read": __doc__.split("Every value is", 1)[1].split("python tools", 1)[0].strip().replace("\n", " "),
            "inputs": ["research/lit/mffu_rules.json", "research/lit/prop_firms.json", "research/props/firms.json"]
                      + (["research/props/firm_research.json"] if R else []),
            "source_urls": {k: hub_src[k] for k in used if k in hub_src},
            "firms": firms, "plans": plans}


def dumps(d: dict) -> str:
    """Readable and small: one line per value ({"v", "verified", ...}), one block per plan."""
    def enc(x, ind):
        pad = " " * ind
        if isinstance(x, dict) and not ("v" in x and "verified" in x) and x:
            inner = ",\n".join(f"{pad} {json.dumps(k)}: {enc(v, ind + 1)}" for k, v in x.items())
            return "{\n" + inner + "\n" + pad + "}"
        return json.dumps(x, separators=(", ", ": "))
    return enc(d, 0) + "\n"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    d = build()
    txt = dumps(d)
    if "--check" in argv:
        try:
            cur = open(OUT, encoding="utf-8").read()
        except OSError:
            cur = ""
        if cur != txt:
            print("research/props/firm_rules.json differs from a rebuild (python tools/build_firm_rules.py)")
            return 1
        print("firm_rules.json up to date")
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(txt)
    n = len(d["plans"])
    ver = sum(1 for p in d["plans"].values() for b in ("eval", "funded", "payout") for x in p[b].values() if x["verified"])
    unk = sum(1 for p in d["plans"].values() for b in ("eval", "funded", "payout") for x in p[b].values() if x["v"] is None)
    tot = sum(1 for p in d["plans"].values() for b in ("eval", "funded", "payout") for _ in p[b].values())
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {len(d['firms'])} firms, {n} plans, {tot} values: {ver} verified, {unk} unknown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
