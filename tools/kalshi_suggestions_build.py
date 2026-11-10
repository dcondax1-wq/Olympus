#!/usr/bin/env python3
"""Kalshi stop list (SUGGESTIONS ONLY: never an order, never touches the bot).  Stdlib.

Reads the team-B research results and writes the same JSON twice:
    research/kalshi_edge_B/bot_suggestions.json
    tools/web_public/kalshicity/suggestions.json     (publish-ready copy; Sibyl and the city read it)

    python tools/kalshi_suggestions_build.py            # build both files
    python tools/kalshi_suggestions_build.py --check    # exit 1 if either file is out of date
    python tools/kalshi_suggestions_build.py --selftest

Inputs: research/kalshi/edge_tables.json (bot history, 1,836 buys, fees in), research/kalshi_edge_B/stop_bleed.json,
results_frozen.json (the frozen-rule test).  Item = {kind, rule, n, net_usd, roi, interval, verdict (stop|pause|watch|keep), evidence}.
Verdict rule: interval wholly below 0 = stop; negative but not proven = pause (n>=30) ; n<30 or not proven = watch; not negative = keep.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, "research", "kalshi_edge_B")
OUTS = [os.path.join(B, "bot_suggestions.json"), os.path.join(ROOT, "tools", "web_public", "kalshicity", "suggestions.json")]
EV_BOT = "research/kalshi/edge_tables.json"
EV_B = "research/kalshi_edge_B/stop_bleed.json"
WHY = {
    "Bitcoin": "Bitcoin bets", "XRP": "XRP bets", "Solana": "Solana bets", "HYPE": "HYPE bets", "BNB": "BNB bets",
    "Ethereum": "Ethereum bets", "Dogecoin": "Dogecoin bets", "Other": "Bets on small coins (Other)",
}


def pct(x):
    return None if x is None else round(100 * x, 1)


def usd(x):
    return None if x is None else round(x, 2)


def build(tables, bleed, frozen):
    items = []
    b9 = next(b for b in tables["buckets"] if b["label"] == "90-95c")
    items.append({"kind": "Buying at 90 to 95 cents", "rule": "Do not buy any contract priced 90 to 95 cents. Wins 92.3% but needs 93.2% to break even, and the losses are bigger bets.",
                  "n": b9["n"], "net_usd": usd(b9["pnl"]), "roi_pct": pct(b9["roi"]), "interval_pct": [pct(b9["roi_ci_lo"]), pct(b9["roi_ci_hi"])],
                  "verdict": "stop", "evidence": EV_BOT + " (buckets); research/kalshi_edge_B/results.json (favourites_15m, favourites_hourly)"})
    cats = {k["kind"]: k for k in bleed["kinds"] if k["group"] == "category"}
    strats = {k["kind"]: k for k in bleed["kinds"] if k["group"] == "strategy"}
    for name, c in cats.items():
        if name == "Gold":
            continue
        lo, hi = c["roi_ci"]
        v = "keep" if (c["roi"] or 0) >= 0 else ("stop" if hi is not None and hi < 0 else "watch")
        rule = {"stop": "Turn off %s bets. The loss is large enough to be real, not luck." % name,
                "watch": "Keep %s bets small and watch them. Slightly negative, but luck could explain it." % name,
                "keep": "No change. Not negative after fees."}[v]
        items.append({"kind": WHY.get(name, name), "rule": rule, "n": c["n"], "net_usd": usd(c["pnl"]), "roi_pct": pct(c["roi"]),
                      "interval_pct": [pct(lo), pct(hi)], "verdict": v, "evidence": EV_BOT + " (categories); " + EV_B})
    plain = {
        "15-min favourites": ("Keep the 15-minute favourites strategy off. It wins 95.0% of the time but needs 96.6% to break even.", "stop"),
        "Late favourite (BTC hourly)": ("No change. 179 wins and 3 losses: positive but too few bets to prove it beats zero.", "keep"),
        "Hourly BTC": ("No change (paper strategy). Positive, not proven.", "keep"),
        "combo": ("No change. Positive, not proven.", "keep"),
        "Value": ("Pause the Value strategy. It wins 75% and is losing; only 40 bets, so not proven.", "pause"),
        "Flip exit sell-backs": ("Keep off. Lost on 16 bets: too few to prove, no reason to turn it on.", "watch"),
        "Sniper test": ("Keep off. 14 bets, losing: too few to judge.", "watch"),
        "arb": ("Keep off. 4 bets, too few to judge.", "watch"),
        "arbx": ("Keep off. 5 bets, all lost: too few to judge.", "watch"),
    }
    for name, (rule, v) in plain.items():
        s = strats.get(name)
        if not s:
            continue
        items.append({"kind": "Strategy: " + name, "rule": rule, "n": s["n"], "net_usd": usd(s["pnl"]),
                      "roi_pct": None, "interval_pct": [pct(s["win_wilson"][0]), pct(s["win_wilson"][1])], "interval_is": "win rate",
                      "verdict": v, "evidence": EV_BOT + " (strategies); " + EV_B})
    order = {"stop": 0, "pause": 1, "watch": 2, "keep": 3}
    items.sort(key=lambda i: (order[i["verdict"]], i["net_usd"] if i["net_usd"] is not None else 0))
    pooled = (frozen or {}).get("pooled_new_data_tau8") or {}
    return {
        "v": 1, "kind": "kalshi-suggestions", "mode": "suggestions-only",
        "label": "Suggestions only: nothing here changes or places a bet. The bot is untouched.",
        "basis": "The bot's own 1,836 settled buys (feed of 2026-11-04, 41 days, Kalshi fees already inside the dollars).",
        "counts": {k: sum(1 for i in items if i["verdict"] == k) for k in order},
        "items": items,
        "not_proven": [
            "Kalshi pays you on average only when the market misprices something. Two months of quotes on about 28,000 crypto markets say it mostly does not.",
            "No new money-making rule was found. A pocket that looked good (15-minute favourites at 95-97c, 8 minutes out) fell apart on unseen data: %s bets, edge %s per $1, range %s to %s."
            % (pooled.get("n", "n/a"), pooled.get("edge", "n/a"), (pooled.get("ci") or ["n/a", "n/a"])[0], (pooled.get("ci") or ["n/a", "n/a"])[1]),
            "So the realistic goal is losing less, not winning more.",
            "A small number of bets can be luck either way; every row shows its n.",
        ],
        "evidence_files": ["research/writeups/kalshi_edge_B.md", EV_BOT, EV_B, "research/kalshi_edge_B/results_frozen.json"],
    }


def inputs():
    t = json.load(open(os.path.join(ROOT, "research", "kalshi", "edge_tables.json"), encoding="utf-8"))
    b = json.load(open(os.path.join(B, "stop_bleed.json"), encoding="utf-8"))
    p = os.path.join(B, "results_frozen.json")
    f = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
    return t, b, f


def dump(d):
    return json.dumps(d, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def selftest():
    d = build(*inputs())
    assert d["items"] and all(i["verdict"] in ("stop", "pause", "watch", "keep") for i in d["items"])
    assert all(i["n"] > 0 and i["net_usd"] is not None and i["evidence"] for i in d["items"])
    stops = [i["kind"] for i in d["items"] if i["verdict"] == "stop"]
    assert "XRP bets" in stops and "Buying at 90 to 95 cents" in stops and "Strategy: 15-min favourites" in stops, stops
    assert not any(i["verdict"] == "stop" and i["n"] < 30 for i in d["items"])
    assert "losing less" in " ".join(d["not_proven"])
    assert dump(d) == dump(build(*inputs()))
    print("ALL PASS (kalshi_suggestions_build selftest, %d items, stop: %s)" % (len(d["items"]), ", ".join(stops)))


def main():
    a = sys.argv[1:]
    if "--selftest" in a:
        return selftest()
    text = dump(build(*inputs()))
    if "--check" in a:
        bad = [o for o in OUTS if not os.path.exists(o) or open(o, encoding="utf-8").read() != text]
        if bad:
            print("OUT OF DATE:", ", ".join(os.path.relpath(o, ROOT) for o in bad))
            sys.exit(1)
        print("up to date")
        return
    for o in OUTS:
        open(o, "w", encoding="utf-8").write(text)
        print("wrote", os.path.relpath(o, ROOT))


if __name__ == "__main__":
    main()
