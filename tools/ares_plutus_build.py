"""ARES + PLUTUS data (2026-11-03): writes the small files the two pages ship with, from the repo's research files.

  tools/web_public/ares/rules.json     the MFFU Builder 50K / 25K rulebook in numbers (research/lit/mffu_rules.json "limits" + prices
                                       + the bot's own entry window / stop band from live_model.json) and the plain-words rule list
  tools/web_public/plutus/plans.json   per plan (MFFU Builder 50K, Builder 25K, LucidPro 50K, FundedNext Rapid Daily 50K): price, caps,
                                       and the 6-month purchase-to-payout study (research/lit/funded_firms.json "life"/"eval") per span
  tools/web_public/{ares,plutus}/jarvis.json   the Jarvis cards

    python tools/ares_plutus_build.py            (writes; the test checks the committed files equal a fresh build, minus the dates)
Both pages read ONLY these files plus the site's own ../data.json (when it is there); nothing else, no network.
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIT = os.path.join(ROOT, "research", "lit")
WEB = os.path.join(ROOT, "tools", "web_public")
SPANS = ("H1", "H2", "2021-25")


def _load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _val(d, *path):
    for k in path:
        d = (d or {}).get(k)
    return d.get("value") if isinstance(d, dict) and "value" in d else d


def ares_rules() -> dict:
    mr = _load(os.path.join(LIT, "mffu_rules.json"))
    lim = mr["limits"]
    b50, b25 = mr["builder_50k"], mr["builder_25k"]
    lm = _load(os.path.join(ROOT, "live_model.json"))
    tw = (lm.get("lit_sizing") or {}).get("two_week") or {}
    price50 = _val(b50, "eval", "price") or {}
    price25 = _val(b25, "price") or {}

    def plan(name, L, p, start):
        return {"name": name, "start": start, "target": L["target"], "mll": L["mll"], "lock": L["lock"], "dll": L["dll"],
                "max_micros": L["max_micros"], "max_minis": L["max_minis"], "buffer": L["buffer"], "pay_min": L["pay_min"],
                "pay_max": L["pay_max"], "split": L["split"], "cons": L["cons"], "max_payouts": L["max_payouts"],
                "price": p.get("owner_paid"), "list_price": p.get("list")}

    def st(sec, k):
        return (sec.get(k) or {}).get("status", "unconfirmed")

    ev = b50["eval"]
    rules = [
        {"id": "mll", "text": "The account fails if your balance, open trade included, touches the floor. The floor starts at the "
         "start balance minus the max loss and moves up only at the close of the day, from your best end-of-day balance, until it "
         "locks at start + $100.", "status": st(ev, "max_loss")},
        {"id": "dll", "text": "Daily loss limit is soft: hit it and trading is paused for that session. The account stays open.",
         "status": st(ev, "daily_loss_limit")},
        {"id": "flat", "text": "Intraday only. Be flat by 16:10 ET. The platform closes you at 16:10; never force orders after it. No weekend holds.",
         "status": st(ev, "trading_hours")},
        {"id": "hedge", "text": "No long and short on the same market at the same time, also across your accounts.", "status": st(ev, "hedging")},
        {"id": "size", "text": "The contract limit counts minis and micros together: 10 micros = 1 mini. Over the limit, the order is rejected.",
         "status": st(ev, "max_contracts")},
        {"id": "news", "text": "News is allowed in the eval and when sim-funded. On a live account MFFU advises against it.",
         "status": st(ev, "news_trading")},
        {"id": "bots", "text": "Bots are allowed with your own settings and you watching. No high-frequency trading, no exploiting simulated fills.",
         "status": st(ev, "automation")},
        {"id": "idle", "text": "Trade at least once every 7 days or the account can be closed.", "status": st(ev, "inactivity")},
        {"id": "target", "text": "The eval passes at +$3,000 (Builder 25K: +$1,500). No consistency rule in the eval.", "status": st(ev, "profit_target")},
        {"id": "pay", "text": "Funded: the first payout once you are $500 above the $2,100 buffer (25K: $250 above $1,100). Payouts $500 to $2,000, "
         "80% to you, best day under 50% of the cycle, 5 sim payouts and then a live account.", "status": st(b50["sim_funded"], "first_payout")},
    ]
    return {
        "v": 1, "kind": "olympus-ares-rules",
        "source": "research/lit/mffu_rules.json (built " + str(mr.get("built")) + "; re-check before the first live payout)",
        "plans": {"50k": plan("Builder 50K", lim["builder_50k"], price50, _val(b50, "eval", "start_balance") or 50000.0),
                  "25k": plan("Builder 25K", lim["builder_25k"], price25, 25000.0)},
        "flat_by": "16:10", "open": "18:00", "break": ["17:00", "18:00"],
        "comm_rt": {"MNQ": lim["builder_50k"]["comm_rt_micro"], "NQ": lim["builder_50k"]["comm_rt_mini"]},
        "slip_ticks": 2, "point_value": {"MNQ": 2.0, "NQ": 20.0}, "tick": 0.25,
        "bot": {"entry_from": "02:00", "entry_to": "15:30", "stop_min_pts": 8, "stop_max_pts": 80, "max_trades_day": 1,
                "room_f_eval": tw.get("room_f"), "room_f_funded": 0.6, "note": "LIT: 1 trade a day, entries 02:00-15:30 ET, stop 8-80 pts"},
        "rules": rules,
    }


def plutus_plans() -> dict:
    ff = _load(os.path.join(LIT, "funded_firms.json"))
    by = {p["id"]: p for p in ff["plans"]}
    want = (("mffu_builder_50k", 1, "MFFU", "Builder 50K", "The owner's eval. MFFU allows 1 active sim-funded Builder 50K per person."),
            ("mffu_builder_25k", 2, "MFFU", "Builder 25K", "2 active sim-funded are allowed, but MFFU has not said it may sit next to a Builder 50K: ask first."),
            ("lucid_pro_50k", 1, "Lucid", "LucidPro 50K", "Bots and copiers allowed. The cap of 1 is this app's assumption."),
            ("fn_rapid_daily_50k", 1, "FundedNext", "Rapid Daily 50K", "Own accounts only. The cap of 1 is this app's assumption."))
    plans = []
    for pid, cap, firm, name, note in want:
        p = by[pid]
        r = p["results"]
        sp = {}
        for s in SPANS:
            lf, fd, ev = r["life"][s], r["funded"][s], (r["eval_mc"].get(s) or r["eval"].get(s) or {})
            sp[s] = {"net_6m": lf["net_6m"], "net_med_6m": lf["net_med_6m"], "net_p10_6m": lf["net_p10_6m"], "per_month": lf["net_per_month"],
                     "steady": lf["months4_6_per_month"], "fees_6m": lf["fees_6m"], "evals": lf["evals_mean"], "neg_6m": lf["neg_6m"],
                     "first_pay_sessions": lf["first_pay_med"], "any_pay": lf["any_pay"], "lost": lf["funded_lost_mean"],
                     "funded_per_month": fd["net_per_month"], "p10": ev.get("p10"), "f10": ev.get("f10"), "p60": ev.get("p60"),
                     "pass_med": ev.get("pass_med")}
        plans.append({"id": pid, "firm": firm, "name": name, "cap": cap, "price": p["price"], "list_price": p.get("list_price"),
                      "target": p["target"], "mll": p["mll"], "split": (p.get("funded") or {}).get("split"), "note": note, "spans": sp})
    trio = {}
    for c in ff["combos"]:
        if sorted(c["plans"]) == sorted(["mffu_builder_50k", "lucid_pro_50k", "fn_rapid_daily_50k"]):
            trio[c["span"]] = {"net_per_month": c["net_per_month"], "months4_6_per_month": c["months4_6_per_month"], "neg_6m": c["neg_6m"]}
    return {"v": 1, "kind": "olympus-plutus-plans", "built": ff.get("built"),
            "source": "research/lit/funded_firms.json (" + str(ff.get("writeup")) + "): 1,500 paths x 126 sessions from the purchase: "
                      "eval -> funded -> payouts; net = payouts - fees; the bot's real LIT trades, costs in",
            "spans": {"H1": "Jan-Jun 2026", "H2": "Jul-Oct 2026 (the honest check)", "2021-25": "2021-25 (reference only)"},
            "plans": plans, "trio": trio, "sessions_per_month": 21, "corr": 0.85,
            "notes": ["Every account takes the same trades (MFFU forbids long and short at once across your accounts), so the accounts rise and fall "
                      "together: the study measured a 0.85 correlation between two of them.",
                      "The study covers 6 months from the purchase. Later months continue at the months 4-6 rate: an extension, not a measurement."]}


def cards(rules, plans) -> dict:
    p50 = rules["plans"]["50k"]
    t = 1793700000          # fixed so the committed cards only change when the numbers do (the page stamps the real time)
    return {
        "ares": {"v": 1, "name": "Ares", "status": {"level": "ok", "label": "Rules: Builder 50K"},
                 "kpis": [{"label": "Max loss", "value": f"${p50['mll']:,.0f}"}, {"label": "Daily loss", "value": f"${p50['dll']:,.0f}"},
                          {"label": "Flat by", "value": rules["flat_by"] + " ET"}],
                 "lines": ["Size follows the stop. The war room says GO, WAIT or HALT before you click.",
                           "Stop beyond the sweep extreme; a wide stop means fewer micros."], "t": t, "open": "#size", "theme": "#0b0608", "stale_after": 2592000},
        "plutus": {"v": 1, "name": "Plutus", "status": {"level": "ok", "label": "Trio Jul-Oct: $" + format(plans["trio"]["H2"]["net_per_month"], ",.0f") + "/mo"},
                   "kpis": [{"label": "Trio, Jul-Oct", "value": "$" + format(plans["trio"]["H2"]["net_per_month"], ",.0f") + "/mo"},
                            {"label": "Trio, Jan-Jun", "value": "$" + format(plans["trio"]["H1"]["net_per_month"], ",.0f") + "/mo"}],
                   "lines": ["The money plan: accounts, fees and payouts from the bot's measured numbers.",
                             "2021-25 is shown as a reference only."], "t": t, "open": "#plan", "theme": "#06100a", "stale_after": 2592000},
    }


def build() -> dict:
    rules, plans = ares_rules(), plutus_plans()
    return {"ares/rules.json": rules, "plutus/plans.json": plans, **{k + "/jarvis.json": v for k, v in cards(rules, plans).items()}}


def main() -> int:
    for rel, doc in build().items():
        path = os.path.join(WEB, *rel.split("/"))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        print("wrote", os.path.relpath(path, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
