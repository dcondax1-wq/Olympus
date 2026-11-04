#!/usr/bin/env python3
"""Kalshi "If you change the bot" and "Why am I losing" (research only, read-only on the public feed; never an order).

The same maths as the Kalshi page's what-if card (tools/web_public/kalshi/kalshi.js, whatifModel / whyModel), so the page, the city feed
and this script give the same numbers for the same kalshi.json. Written to tools/web_public/kalshicity/whatif.json for the city.

    python tools/kalshi_whatif.py                       # fetch the public feed, write kalshicity/whatif.json
    python tools/kalshi_whatif.py --feed kalshi.json    # a local copy
    from tools.kalshi_whatif import build               # build(feed_dict) -> dict

What it does, from the feed's price bands (every settled bet, in totals) and the bot's own balance:
  rule sets, replayed on the past bets (a backtest, never a promise; the bands were picked after looking, so test on paper first):
    A  skip the 90-95c band
    B  only 95c and up, every bet capped at 2% of today's balance
    C  skip the 90-95c band, and cap every other bet at 2% of today's balance
  per set: net $ after fees on the past bets (the bot's own P&L is already net of Kalshi's fee), the typical worst dip and the chance of
  ruin (balance under $6) or of losing half, from a seeded simulation of the next 200 bets drawn from the same bands (400 runs).
  Under 100 settled bets: "not enough bets", no numbers.
  why: the top two dollar leaks (a price band, a coin, a strategy, the fees), by kind, in one sentence.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEED_URL = "https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json"
OUT = os.path.join(ROOT, "tools", "web_public", "kalshicity", "whatif.json")
MIN_BETS, PATHS, BETS, SEED, MIN_BAL, CAP = 100, 400, 200, 20261104, 6.0, 0.02
TAKER = 0.07


def usd(x, sign=False):
    v = round(abs(x) + 1e-9, 2)
    s = "−" if x < 0 and v else ("+" if sign and v else "")
    return f"{s}${v:,.2f}"


def rows_of(feed):
    """price bands with their stats: [{lo, hi, n, w, l, pnl, st, p}] (p = the band's mean entry price: the calibration's, else the middle)"""
    cal = {int(c["n"]): c["p"] for c in feed.get("calibration") or [] if isinstance(c, dict) and c.get("n") is not None and c.get("p") is not None}
    out = []
    for b in feed.get("buckets") or []:
        try:
            n, w, l = int(b["trades"]), int(b["wins"]), int(b["losses"])
            lo, hi, pnl, st = float(b["lo"]), float(b["hi"]), float(b["pnl"]), float(b["staked"])
        except (KeyError, TypeError, ValueError):
            continue
        if n <= 0 or not 0 <= lo < hi <= 1.0001:
            continue
        p = cal.get(n, (lo + min(hi, 1.0)) / 2)
        out.append({"lo": lo, "hi": min(1.0, hi), "n": n, "w": w, "l": l, "pnl": pnl, "st": st, "p": min(0.98, max(0.02, p))})
    return sorted(out, key=lambda r: r["lo"])


def size_model(r):
    """average stake of a winning and of a losing bet in the band, from its totals only (the research's size model)"""
    p, f = r["p"], TAKER * (1 - r["p"])
    win = (1 / p - 1) - f
    if r["w"] > 0 and r["l"] > 0 and r["st"] > 0:
        s_l = (r["st"] * win - r["pnl"]) / (r["l"] * (win + 1 + f))
        s_w = (r["st"] - s_l * r["l"]) / r["w"]
        if s_l > 0 and s_w > 0:
            return s_w, s_l, win, f
    s = r["st"] / r["n"]
    return s, s, win, f


def in_leak(r):
    return r["lo"] >= 0.9 - 1e-9 and r["hi"] <= 0.95 + 1e-9


def rule_rows(rows, rule, cap_d):
    """(row, past multiplier) kept by a rule: the past stake is shrunk to the cap where it was bigger"""
    keep = [r for r in rows if (rule == "asis" or (rule == "A" and not in_leak(r)) or (rule == "B" and r["lo"] >= 0.95 - 1e-9) or (rule == "C" and not in_leak(r)))]
    capped = rule in ("B", "C")
    return [(r, min(1.0, cap_d / (r["st"] / r["n"])) if capped else 1.0) for r in keep]


class Lcg:
    def __init__(self, seed):
        self.s = seed

    def __call__(self):
        self.s = (self.s * 48271) % 2147483647
        return self.s / 2147483647


def simulate(rows, rule, bal, t0, cap_d):
    kept = rule_rows(rows, rule, cap_d)
    if not kept or bal <= 0:
        return {"ruin": None, "half": None, "dip": None}
    s_all = sum(r["st"] for r in rows) / max(1, sum(r["n"] for r in rows))
    g = t0 / s_all if s_all > 0 else 1.0
    capped = rule in ("B", "C")
    tot = sum(r["n"] for r, _ in kept)
    pre = []
    for r, _ in kept:
        s_w, s_l, win, f = size_model(r)
        u = g * (min(1.0, cap_d / ((r["st"] / r["n"]) * g)) if capped else 1.0)
        pre.append((r["n"] / tot, r["w"] / r["n"], s_w * win * u, s_l * (1 + f) * u))
    rnd = Lcg(SEED)
    ruined = half = 0
    dips = []
    for _ in range(PATHS):
        b, peak, dd, low, dead = bal, bal, 0.0, bal, False
        for _ in range(BETS):
            x, i, acc = rnd(), 0, pre[0][0]
            while x > acc and i < len(pre) - 1:
                i += 1
                acc += pre[i][0]
            _, pw, gain, loss = pre[i]
            b += gain if rnd() < pw else -loss
            peak, low = max(peak, b), min(low, b)
            dd = max(dd, peak - b)
            if b < MIN_BAL:
                dead = True
                break
        ruined += dead
        half += low < bal / 2
        dips.append(dd)
    dips.sort()
    return {"ruin": ruined / PATHS, "half": half / PATHS, "dip": dips[PATHS // 2]}


def typical_stake(feed):
    cs = sorted(t["contracts"] * t["price"] for t in feed.get("trades") or [] if isinstance(t, dict) and t.get("action") != "sell"
                and isinstance(t.get("contracts"), (int, float)) and isinstance(t.get("price"), (int, float)) and 0 < t["price"] < 1.0001)
    return cs[len(cs) // 2] if cs else 6 * 0.96


def what_if(feed):
    rows, bal = rows_of(feed), feed.get("balance")
    n = sum(r["n"] for r in rows)
    out = {"n": n, "min": MIN_BETS, "enough": n >= MIN_BETS and isinstance(bal, (int, float)) and bal > 0, "balance": bal, "sets": []}
    if not out["enough"]:
        out["recommend"] = f"Not enough bets yet ({n} of {MIN_BETS}) to say what a change would do."
        return out
    cap_d, t0 = CAP * bal, typical_stake(feed)
    out.update({"cap_dollars": round(cap_d, 2), "typical_bet": round(t0, 2)})
    names = {"asis": "The bot as it is", "A": "A · skip the 90–95¢ band", "B": "B · only 95¢ and up, 2% bets", "C": "C · skip 90–95¢, 2% bets"}
    for rule in ("asis", "A", "B", "C"):
        kept = rule_rows(rows, rule, cap_d)
        sim = simulate(rows, rule, bal, t0, cap_d)
        out["sets"].append({"id": rule, "name": names[rule], "bets": sum(r["n"] for r, _ in kept), "net": round(sum(r["pnl"] * m for r, m in kept), 2),
                            "dip": None if sim["dip"] is None else round(sim["dip"], 2), "ruin": sim["ruin"], "half": sim["half"]})
    base = out["sets"][0]
    ok = [s for s in out["sets"][1:] if s["net"] > base["net"] and s["ruin"] is not None and s["ruin"] <= 0.05]
    pick = max(ok, key=lambda s: s["net"]) if ok else None
    rp = lambda s: "0%" if not s["ruin"] else f"{s['ruin'] * 100:.0f}%"      # noqa: E731
    if pick:
        out["pick"] = pick["id"]
        out["recommend"] = (f"The data supports {pick['name'].split(' · ')[0]}: {usd(pick['net'], True)} after fees on the past bets and a {rp(pick)} chance of ruin, "
                            f"against {usd(base['net'], True)} and {rp(base)} as the bot is. The band was picked after looking at these bets: try it on paper first.")
    else:
        out["pick"] = None
        out["recommend"] = "Keep the bot as it is: none of the three rule sets beats it on the past bets with a ruin chance under 5%."
    return out


def why(feed):
    rows = rows_of(feed)
    n = sum(r["n"] for r in rows)
    total = feed.get("total_pnl") if isinstance(feed.get("total_pnl"), (int, float)) else (feed.get("stats") or {}).get("pnl")
    if n < MIN_BETS or total is None:
        return {"n": n, "enough": False, "text": f"Not enough settled bets yet ({n} of {MIN_BETS}) to say why."}
    leaks = []
    for r in rows:
        if r["pnl"] < -0.5:
            leaks.append({"kind": "band", "usd": r["pnl"], "label": f"{round(r['lo'] * 100)}–{round(r['hi'] * 100)}¢ bets", "n": r["n"]})
    for c in feed.get("categories") or []:
        if isinstance(c, dict) and isinstance(c.get("pnl"), (int, float)) and c["pnl"] < -0.5 and (c.get("trades") or 0) >= 30:
            leaks.append({"kind": "coin", "usd": c["pnl"], "label": f"{c.get('name')} bets", "n": c.get("trades")})
    for s in feed.get("strategies") or []:
        if isinstance(s, dict) and isinstance(s.get("total_pnl"), (int, float)) and s["total_pnl"] < -0.5 and (s.get("trades") or 0) >= 30:
            leaks.append({"kind": "strategy", "usd": s["total_pnl"], "label": f"the {s.get('name')} strategy", "n": s.get("trades")})
    fees = sum(TAKER * r["st"] * (1 - r["p"]) for r in rows)
    if fees >= 5:
        leaks.append({"kind": "fees", "usd": -fees, "label": "Kalshi's fees", "n": None})
    leaks.sort(key=lambda x: x["usd"])
    top, seen = [], set()
    for x in leaks:
        if x["kind"] not in seen:
            seen.add(x["kind"])
            top.append(x)
        if len(top) == 2:
            break
    say = lambda x: (f"{x['label']} lost {usd(abs(x['usd']))}" + (f" on {x['n']:,} bets" if x["n"] else "")) if x["kind"] != "fees" else f"Kalshi's fees cost about {usd(abs(x['usd']))}"   # noqa: E731
    if not top:
        text = (f"You are down {usd(abs(total))} but no single price band, coin or strategy stands out." if total < 0 else f"You are up {usd(total, True)} and no single leak is bigger than $0.50.")
    else:
        lead = f"You are down {usd(abs(total))} mostly because " if total < 0 else f"You are up {usd(total, True)}, but the two biggest leaks are "
        text = lead + " and ".join(say(x) for x in top) + ". These overlap, so do not add them up."
    return {"n": n, "enough": True, "total": total, "leaks": top, "text": text}


def build(feed):
    return {"v": 1, "kind": "kalshi-whatif", "t": feed.get("t"), "label": "A backtest of past bets, suggestions only: nothing here places or changes a bet",
            "what_if": what_if(feed), "why": why(feed)}


def load(src):
    if src and os.path.isfile(src):
        return json.load(open(src, encoding="utf-8"))
    req = urllib.request.Request(src or FEED_URL, headers={"User-Agent": "kalshi-whatif/1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--feed")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    j = build(load(a.feed))
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(j, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print("wrote", a.out)
    print(j["why"]["text"])
    print(j["what_if"]["recommend"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
