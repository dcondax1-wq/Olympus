#!/usr/bin/env python3
"""SIBYL, money machine #3: a prediction-market edge scanner. SUGGESTIONS ONLY: it reads the Kalshi study files the site already publishes
and writes ONE json file. It never places, changes or stops a bet, never calls Kalshi, never uses a key, and the owner's Kalshi bot is untouched.

    python tools/money/sibyl.py --out DIR              # reads tools/web_public/kalshicity/{edges,whatif,forward}.json (read only) -> DIR/sibyl.json
    python tools/money/sibyl.py --out DIR --fixture    # the bundled invented sample (status "sample")
    python tools/money/sibyl.py --selftest

What it does with the study (edges.json = every kind of bet the bot made, with its win rate, break-even price and net result after Kalshi's fee):
  * edge after fees: ev (net $ per $1 staked, fee already in it) and a CAUTIOUS edge that uses the lower end of the win-rate range (95% interval),
    so a lucky streak on few bets is not mistaken for an edge. Only the cautious edge ranks a bet "paper-worthy"; it also needs n >= MIN_N bets.
  * Kelly sizing on the cautious win rate: f = (q - c) / (1 - c) for a contract that costs c (fee included) and pays $1. Then a quarter of it
    (KELLY_FRACTION), hard-capped at CAP_PCT of the bankroll per bet and CAP_TOTAL_PCT across the day's picks. 1R = that paper stake.
  * ruin odds: a seeded simulation of RUIN_BETS bets at that stake, with the cautious win rate: the chance the bankroll halves.
  * a forward scoreboard: the Kalshi forward paper tally (bets placed after a frozen start date; no look-ahead), with its sample size.
  * a "what could go wrong" list that is computed from the data, not boilerplate.
Honest numbers: every dollar is an estimate, nothing is promised, and a pick backed by few bets says so.

Output contract (docs/NIGHT_BRIEF.md): {"v":1,"id":"sibyl","asof","mode":"paper","status":"ok|stale|sample","headline":{"text","usd_month"},
"items":[{"title","detail","usd","score","risk"}],"notes":[]} plus the extra fields the Sibyl page reads: bankroll, params, counts, scoreboard, risks, source
(and per item: type, tier, n, win, break_even, win_low, ev_c, edge_c, fee_c, kelly_full, stake_pct, stake_usd, ruin_pct, usd_month, status_study).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import random
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
STUDY = os.path.join(ROOT, "tools", "web_public", "kalshicity")
SAMPLE = os.path.join(HERE, "fixtures", "sibyl_sample.json")

MIN_N = 30                 # fewer bets than this: never "paper-worthy"
KELLY_FRACTION = 0.25      # a quarter of full Kelly
CAP_PCT = 0.02             # one paper bet never risks more than 2% of the bankroll
CAP_TOTAL_PCT = 0.06       # the day's picks together never risk more than 6%
MAX_PICKS = 4              # at most this many sized picks a day
RUIN_BETS = 300            # the ruin simulation looks this many bets ahead
RUIN_PATHS = 600
STALE_DAYS = 3             # a study older than this makes the whole page "stale"
WORTHY_SCORE_N = 150       # n at which the sample-size factor of the score reaches 1
TYPES = {"strategy": "Bot strategy", "market": "Coin or market", "band": "Price band", "side": "Side", "hour": "Hour of day", "combo": "Combination"}


# ------------------------------------------------------------------------------------------------ small helpers
def num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    if isinstance(v, str):
        try:
            x = float(v.replace("$", "").replace(",", "").strip())
            return x if math.isfinite(x) else None
        except ValueError:
            return None
    return None


def clean(s, n=120):
    s = "".join(ch if ch >= " " and ch not in "<>" else " " for ch in str(s if s is not None else ""))
    return " ".join(s.split())[:n]


def usd(x, sign=False):
    v = round(abs(x) + 1e-9, 2)
    return ("-" if x < 0 and v else "+" if sign and v else "") + f"${v:,.2f}"


def words(label):
    """'95-97c' -> '95-97¢' in plain words; strategy / coin names stay as they are."""
    s = str(label if label is not None else "")
    s = re.sub(r"<(\d+)c\b", "under \\1¢", s)
    s = clean(s, 60)
    s = re.sub(r"(\d+)-(\d+)c\b", "\\1–\\2¢", s)
    s = re.sub(r"(\d+)c\+", "\\1¢ and up", s)
    return re.sub(r"\b(\d+)c\b", "\\1¢", s)


def wilson_lo(wins, n, z=1.6448536269514722):
    """lower end of a one-sided 95% interval for a win rate (used only when the study file lacks its own 'lo')."""
    if n <= 0:
        return 0.0
    ph = wins / n
    d = 1 + z * z / n
    c = ph + z * z / (2 * n)
    m = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))
    return max(0.0, (c - m) / d)


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            j = json.load(fh)
        return j if isinstance(j, dict) else None
    except (OSError, ValueError):
        return None


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------------------------------------ the maths
def kelly(q, cost):
    """full-Kelly fraction of the bankroll for a contract that costs `cost` (fee included) and pays $1 with chance q. 0 when there is no edge."""
    if cost is None or not (0 < cost < 1) or q is None:
        return 0.0
    return max(0.0, (q - cost) / (1 - cost))


def stake_fraction(f_full):
    """a quarter of Kelly, never more than CAP_PCT of the bankroll."""
    return max(0.0, min(CAP_PCT, KELLY_FRACTION * f_full))


def ruin_odds(q, cost, frac, bets=RUIN_BETS, paths=RUIN_PATHS, seed=1):
    """chance (0..1) that the bankroll halves within `bets` bets of `frac` of the bankroll each, when the true win rate is q. Seeded: same inputs, same answer."""
    if frac <= 0 or not (0 < cost < 1):
        return 0.0
    rnd = random.Random(seed)
    win_gain = frac * (1 - cost) / cost          # a win pays (1-cost) per `cost` staked
    hit = 0
    for _ in range(paths):
        b = 1.0
        for _ in range(bets):
            b *= (1 + win_gain) if rnd.random() < q else (1 - frac)
            if b <= 0.5:
                hit += 1
                break
    return hit / paths


def seed_of(text):
    return sum((i + 1) * ord(ch) for i, ch in enumerate(str(text))) % 1000003


def judge_edge(e):
    """one study edge -> numbers, or None when it lacks the fields. All 'per $1' figures are per dollar staked, fee included."""
    if not isinstance(e, dict):
        return None
    n, w, p = num(e.get("n")), num(e.get("w")), num(e.get("p"))
    if not n or n <= 0 or w is None or p is None or not (0 < p < 1):
        return None
    wins = num(e.get("wins"))
    pts = num(e.get("pts"))
    ev = num(e.get("ev"))
    pts = pts if pts is not None else w - p
    ev = ev if ev is not None else pts / p
    fee = max(0.0, pts - ev * p)                  # the fee per contract, in dollars
    lo = num(e.get("lo"))
    lo = lo if lo is not None else wilson_lo(wins if wins is not None else w * n, n)
    cost = min(0.999, p + fee)
    cons = (lo - cost) / cost                      # cautious edge per $1 staked, after fees
    f_full = kelly(lo, cost)
    return {"n": int(n), "w": w, "p": p, "lo": lo, "fee": fee, "ev": ev, "cons": cons, "cost": cost, "f_full": f_full, "frac": stake_fraction(f_full)}


def tier_of(e, j):
    status = clean(e.get("status"), 12).upper()
    if j["n"] < MIN_N:
        return "thin"
    if j["cons"] > 0 and j["frac"] > 0 and status in ("HOLDING", "GROWING", "NEW", ""):
        return "worthy"
    if j["cons"] > 0 and j["frac"] > 0:
        return "decaying"                          # the cautious edge is positive but the study says it is fading / dead
    if j["ev"] > 0:
        return "unproven"
    return "avoid"


def score_of(tier, j):
    sn = min(1.0, j["n"] / WORTHY_SCORE_N)
    if tier == "worthy":
        return int(round(100 * min(1.0, j["cons"] / 0.03) * sn))
    if tier == "decaying":
        return int(round(40 * min(1.0, j["cons"] / 0.03) * sn))
    if tier == "unproven":
        return int(round(35 * min(1.0, j["ev"] / 0.03) * sn))
    return 0


def risk_of(tier, j):
    if tier == "worthy" and j["n"] >= 300:
        return "low"
    if tier == "worthy" and j["n"] >= 100:
        return "med"
    return "high"


def span_days(e, day):
    try:
        a = dt.date.fromisoformat(str(e.get("first") or e.get("since")))
        b = dt.date.fromisoformat(str(day))
        return max(1, (b - a).days + 1)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------------------------------------ the scan
def scan(study, now, fixture=False):
    """study = {"edges": edges.json, "whatif": whatif.json | None, "forward": forward.json | None} -> the sibyl.json dict."""
    E = study.get("edges") if isinstance(study.get("edges"), dict) else {}
    W = study.get("whatif") if isinstance(study.get("whatif"), dict) else None
    F = study.get("forward") if isinstance(study.get("forward"), dict) else None
    book = E.get("book") if isinstance(E.get("book"), dict) else {}
    edges = [e for e in (E.get("edges") if isinstance(E.get("edges"), list) else []) if isinstance(e, dict)]
    t_study = num(E.get("t")) or 0
    age_days = (now - t_study) / 86400 if t_study else None
    bankroll = num(book.get("balance"))
    bank_known = bankroll is not None and bankroll > 0
    if not bank_known:
        bankroll = 100.0                           # an example bankroll, said so in the notes
    notes = []
    if fixture:
        status = "sample"
        notes.append("SAMPLE numbers: an invented study, not real. It only shows what the page looks like.")
    elif not edges:
        status = "stale"
        notes.append("No Kalshi study was found, so nothing is ranked. Sibyl never invents an edge.")
    elif age_days is None or age_days > STALE_DAYS or not any(judge_edge(e) for e in edges):
        status = "stale"
        notes.append(f"The Kalshi study is {int(age_days)} days old. Treat every number as history." if age_days is not None and age_days > STALE_DAYS else "The Kalshi study has no date or no usable rows. Treat every number as history.")
    else:
        status = "ok"
    if not bank_known:
        notes.append("No bankroll in the study: sizes use an EXAMPLE bankroll of $100.00.")

    judged = []
    tiers = {"worthy": 0, "decaying": 0, "unproven": 0, "avoid": 0, "thin": 0}
    for e in edges:
        j = judge_edge(e)
        if j is None:
            continue
        tier = tier_of(e, j)
        tiers[tier] += 1
        judged.append([e, j, tier])
    order = {"worthy": 0, "decaying": 1, "unproven": 2, "thin": 3, "avoid": 4}
    judged.sort(key=lambda x: (order[x[2]], -x[1]["cons"] if x[2] in ("worthy", "decaying") else -x[1]["ev"], -x[1]["n"]))

    # sized picks: the best MAX_PICKS paper-worthy, together capped at CAP_TOTAL_PCT of the bankroll
    worthy = [x for x in judged if x[2] == "worthy"][:MAX_PICKS]
    total = sum(x[1]["frac"] for x in worthy)
    scale = min(1.0, CAP_TOTAL_PCT / total) if total > 0 else 1.0
    picked_ids = {id(x[0]) for x in worthy}
    out_items = []
    best_month = None
    for e, j, tier in judged:
        picked = id(e) in picked_ids
        frac = j["frac"] * scale if picked else 0.0
        stake = round(frac * bankroll, 2)
        ruin = ruin_odds(max(0.0, j["lo"]), j["cost"], frac, seed=seed_of(e.get("id"))) if picked else None
        per_bet = round(stake * j["cons"], 2) if picked else None             # expected $ per bet, cautious
        win_usd = stake * (1 - j["cost"]) / j["cost"] if picked else 0.0
        adv = {"worthy": "Paper-worthy", "decaying": "Fading", "unproven": "Not proven", "thin": "Too few bets", "avoid": "Avoid"}[tier]
        d = (f"{adv}. Won {j['w'] * 100:.1f}% of {j['n']} bets; break-even is {j['p'] * 100:.1f}%. "
             f"After fees: {j['ev'] * 100:+.2f}¢ per $1 as it happened, {j['cons'] * 100:+.2f}¢ per $1 on the cautious win rate ({j['lo'] * 100:.1f}%).")
        if picked:
            d += (f" Paper stake {usd(stake)} = 1R ({frac * 100:.2f}% of the {usd(bankroll)} bankroll; a quarter of Kelly, capped)."
                  f" A loss is {usd(-stake)} (-1.0R); a win is about {usd(win_usd, True)} ({win_usd / stake:+.2f}R)."
                  f" Chance the bankroll halves within {RUIN_BETS} bets at the cautious rate: {ruin * 100:.0f}%.")
        elif tier == "avoid":
            d += f" No bet. Net so far {usd(num(e.get('pnl')) or 0, True)}."
        elif tier == "thin":
            d += f" Fewer than {MIN_N} bets: no claim, no stake."
        elif tier == "decaying":
            d += f" The study marks it {clean(e.get('status'), 12).lower()}: no stake."
        elif worthy and j["cons"] > 0:
            d += " Paper-worthy but outside today's top picks: no stake."
        else:
            d += " The cautious edge is not above zero: no stake."
        sd = span_days(e, E.get("day"))
        per_day = (j["n"] / sd) if sd else None
        month = round(per_bet * per_day * 30, 2) if picked and per_bet is not None and per_day else None
        if picked and month is not None and best_month is None:
            best_month = month
        out_items.append({
            "title": words(e.get("label")), "detail": d, "usd": per_bet, "score": score_of(tier, j), "risk": risk_of(tier, j),
            "type": TYPES.get(clean(e.get("kind"), 12), "Other"), "tier": tier, "picked": picked, "n": j["n"], "win": round(j["w"], 4), "break_even": round(j["p"], 4),
            "win_low": round(j["lo"], 4), "ev_c": round(j["ev"] * 100, 2), "edge_c": round(j["cons"] * 100, 2), "fee_c": round(j["fee"] * 100, 2),
            "kelly_full": round(j["f_full"], 4), "stake_pct": round(frac * 100, 2), "stake_usd": stake if picked else None,
            "win_usd": round(win_usd, 2) if picked else None, "ruin_pct": round(ruin * 100, 1) if ruin is not None else None,
            "usd_month": month, "status_study": clean(e.get("status"), 12)})

    # a rule from the what-if (a backtest, picked after the fact): shown, capped, never a pick
    wi = W.get("what_if") if isinstance(W, dict) and isinstance(W.get("what_if"), dict) else None
    if wi and isinstance(wi.get("sets"), list):
        sets = [s for s in wi["sets"] if isinstance(s, dict) and num(s.get("net")) is not None]
        base = next((s for s in sets if s.get("id") == "asis"), sets[0] if sets else None)
        pk = next((s for s in sets if s.get("id") == wi.get("pick")), None)
        if base and pk and pk is not base:
            gain = num(pk["net"]) - num(base["net"])
            nn = int(num(wi.get("n")) or 0)
            out_items.append({
                "title": clean(pk.get("name"), 60),
                "detail": (f"A rule for the bot, not a bet. On {nn} past bets it would have made {usd(num(pk['net']), True)} against {usd(num(base['net']), True)} as the bot is "
                           f"({usd(gain, True)} better; 1R = the typical bet {usd(num(wi.get('typical_bet')) or 0)}). The rule was picked AFTER looking at those bets, so this is a hint to test on paper, not proof. "
                           f"Chance of ruin in the replay: {round((num(pk.get('ruin')) or 0) * 100)}%."),
                "usd": round(gain, 2), "score": 30, "risk": "high", "type": "Rule hint", "tier": "rule", "picked": False, "n": nn, "stake_usd": None, "stake_pct": 0.0, "ruin_pct": None, "usd_month": None})

    # the scoreboard: the Kalshi forward paper tally (bets placed after a frozen start; no look-ahead)
    sb = {"source": "Kalshi forward paper tally", "start_day": None, "n": 0, "min_n": MIN_N, "status": "collecting", "sets": [], "gaps": 0,
          "text": "No forward paper tally was found yet: nothing is claimed."}
    if F and isinstance(F.get("sets"), list):
        n = int(num(F.get("bets")) or 0)
        mn = int(num(F.get("min_bets")) or MIN_N)
        sets = [{"id": clean(s.get("id"), 8), "name": clean(s.get("name"), 60), "n": int(num(s.get("bets")) or 0), "net": round(num(s.get("net")) or 0.0, 2),
                 "vs_asis": round(num(s.get("vs_asis")) or 0.0, 2), "wins": int(num(s.get("wins")) or 0), "losses": int(num(s.get("losses")) or 0)} for s in F["sets"] if isinstance(s, dict)]
        st = "collecting" if n < mn else "early" if n < 100 else "building"
        day = clean(F.get("start_day"), 10)
        if n == 0:
            txt = f"Collecting: 0 bets since {day}. No claim is made."
        elif n < mn:
            txt = f"Collecting: {n} bets since {day} (n={n}, fewer than {mn}). Far too few to claim anything."
        else:
            lead = next((s for s in sets if s["id"] == F.get("leader")), None)
            txt = (f"{n} paper bets since {day} (n={n}). " + (f"{lead['name']} is ahead of the bot by {usd(lead['vs_asis'], True)} on the same bets" if lead else "No rule set is ahead of the bot yet")
                   + (". Still a small sample: a lead can vanish." if n < 100 else ". A bigger sample, but still a few weeks of one market."))
        sb.update({"start_day": day, "n": n, "min_n": mn, "status": st, "sets": sets, "text": txt, "gaps": int(num(F.get("gaps")) or 0)})
    sb["note"] = "Sibyl's own picks are not settled bet by bet yet. This is the study's forward paper tally of the same kind of rules, with its real sample size."

    # what could go wrong: computed from the data
    risks = []
    if age_days is not None and age_days > STALE_DAYS:
        risks.append({"title": "The study is old", "detail": f"Its newest numbers are {int(age_days)} days old. A price band that worked last week may be gone.", "level": "high"})
    elif not edges:
        risks.append({"title": "No study found", "detail": "Nothing can be ranked until the Kalshi study is published.", "level": "high"})
    thin = [x for x in out_items if x.get("tier") == "worthy" and x["n"] < 150]
    if thin:
        risks.append({"title": "Small samples", "detail": f"{len(thin)} of the paper-worthy picks rest on fewer than 150 bets. Luck can look like an edge at that size.", "level": "med"})
    if tiers["decaying"]:
        risks.append({"title": "Edges that fade", "detail": f"{tiers['decaying']} kinds of bet still show a cautious edge but the study marks them fading. Edges on Kalshi do not last.", "level": "med"})
    p7 = num(book.get("pnl7"))
    if p7 is not None and p7 < 0:
        paused = book.get("running") is False or (isinstance(E.get("regime"), dict) and E["regime"].get("paused"))
        risks.append({"title": "The bot is in a losing week", "detail": f"The Kalshi bot lost {usd(-p7)} over the last 7 days" + (" and is paused" if paused else "") + ". A losing week is information: size down, not up.", "level": "high"})
    kb = num(book.get("kelly_book"))
    if kb is not None and kb < 0:
        risks.append({"title": "The bot's whole book has no edge", "detail": f"Taken together, the bot's bets have a negative Kelly ({kb:.2f}). Single kinds of bet can look good while the whole is still losing.", "level": "high"})
    if tiers["worthy"] >= 2:
        risks.append({"title": "The picks overlap", "detail": f"Several picks are the same bets seen through different filters (a price band, a coin, a strategy). They win and lose together, so the day's risk is closer to one bet than to several. That is why the total is capped at {CAP_TOTAL_PCT * 100:.0f}% of the bankroll.", "level": "med"})
    risks.append({"title": "Near-certain bets lose big", "detail": "Buying at 95¢ and up wins most of the time and pays a few cents; one loss costs about twenty wins. A single bad day can erase weeks.", "level": "med"})
    risks.append({"title": "Fees and fills", "detail": "Kalshi's fee is already in the edge, but real orders can fill at a worse price than the study's average. Paper results are always a little kinder than real ones.", "level": "med"})
    risks.append({"title": "Looking back is not a promise", "detail": "Every number is history. Picks come from the same bets they are judged on; only the forward tally is out of sample, and it is small.", "level": "high" if sb["n"] < 100 else "med"})

    wk = [x for x in out_items if x.get("picked")]
    if wk:
        b = wk[0]
        head = (f"{tiers['worthy']} paper-worthy edge{'s' if tiers['worthy'] != 1 else ''} today; the best is {b['title']} (n={b['n']}), {b['edge_c']:+.2f}¢ per $1 after fees on the cautious win rate. "
                f"Paper stake {usd(b['stake_usd'])} = 1R. Suggestions only: Sibyl places no bet.")
    elif judged:
        head = "No paper-worthy edge today: nothing clears the cautious test. Staying out is a result. Suggestions only: Sibyl places no bet."
    else:
        head = "Nothing to rank: no Kalshi study found. Suggestions only: Sibyl places no bet."
    notes += [
        "All dollar figures are estimates from past bets. Nothing here is a promise or advice to place a bet.",
        f"Paper-worthy needs at least {MIN_N} bets and a positive edge on the cautious (lower 95%) win rate, after fees.",
        f"Sizes: a quarter of Kelly, at most {CAP_PCT * 100:.0f}% of the bankroll per bet and {CAP_TOTAL_PCT * 100:.0f}% across the day's picks. Sibyl never places a bet; the Kalshi bot is untouched.",
        "Monthly figure (estimate): the best pick's cautious dollars per bet times how often that kind of bet came up, times 30. One pick only: the picks overlap, so they are never added up.",
    ]
    asof = clean(study.get("asof"), 25) if fixture else iso(t_study) if t_study else iso(now)
    demo = {"demo": True, "note": "EXAMPLE numbers, not real: an invented Kalshi study, what-if and forward tally, shown until the real file is there."} if fixture else {}
    return {**demo, "v": 1, "id": "sibyl", "asof": asof or iso(now), "mode": "paper", "status": status,
            "headline": {"text": head, "usd_month": best_month}, "items": out_items, "notes": notes,
            "bankroll": {"usd": round(bankroll, 2), "known": bool(bank_known)},
            "params": {"min_n": MIN_N, "kelly_fraction": KELLY_FRACTION, "cap_pct": CAP_PCT, "cap_total_pct": CAP_TOTAL_PCT, "ruin_bets": RUIN_BETS, "ruin_def": "bankroll halves", "stale_days": STALE_DAYS},
            "counts": {"edges": sum(tiers.values()), **tiers}, "scoreboard": sb, "risks": risks,
            "source": {"edges_t": int(t_study) if t_study else None, "age_days": round(age_days, 1) if age_days is not None else None, "fixture": bool(fixture)}}


def gather(study_dir, fixture):
    if fixture:
        return load_json(SAMPLE) or {}
    return {"edges": load_json(os.path.join(study_dir, "edges.json")), "whatif": load_json(os.path.join(study_dir, "whatif.json")), "forward": load_json(os.path.join(study_dir, "forward.json"))}


def run(out_dir, fixture=False, study_dir=STUDY, now=None):
    now = now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp()
    s = gather(study_dir, fixture)
    if fixture:
        now = num(s.get("now")) or now
    res = scan(s, now, fixture=fixture)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "sibyl.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    return path, res


# ------------------------------------------------------------------------------------------------ selftest
def selftest():
    bad = []

    def ck(name, ok, info=""):
        print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"))
        if not ok:
            bad.append(name)
    ck("kelly: q .60 at cost .50 -> 0.2; no edge -> 0; junk -> 0", abs(kelly(0.6, 0.5) - 0.2) < 1e-9 and kelly(0.4, 0.5) == 0 and kelly(None, 0.5) == 0 and kelly(0.9, 1.2) == 0)
    ck("stake: a quarter of Kelly, capped at 2%", abs(stake_fraction(0.04) - 0.01) < 1e-9 and stake_fraction(0.5) == CAP_PCT and stake_fraction(0) == 0)
    ck("ruin: seeded and repeatable; a weaker win rate halves more often; no stake, no ruin",
       ruin_odds(0.9, 0.9, 0.02, seed=3) == ruin_odds(0.9, 0.9, 0.02, seed=3) and ruin_odds(0.85, 0.9, 0.02, seed=3) > ruin_odds(0.97, 0.9, 0.02, seed=3) and ruin_odds(0.5, 0.5, 0.0) == 0)
    ck("words: 95-97c -> 95–97¢", words("95-97c").startswith("95–97¢") and words("<20c") == "under 20¢")
    j = judge_edge({"n": 700, "w": 0.978, "p": 0.962, "pts": 0.016, "ev": 0.0165, "lo": 0.967})
    ck("judge: a real-looking edge has a positive cautious edge and a stake under the cap", j and j["cons"] > 0 and 0 < j["frac"] <= CAP_PCT, j)
    ck("judge: junk (n=0, p=1, None) is skipped, never a crash", judge_edge({"n": 0}) is None and judge_edge({"n": 5, "w": 0.9, "p": 1.0}) is None and judge_edge(None) is None)
    path, r = run(tempfile.mkdtemp(prefix="sibyl-"), fixture=True)
    ck("the data contract: v 1, id sibyl, mode paper, status sample, headline text, items with title / detail / usd / score 0-100 / risk, notes",
       {"v", "id", "asof", "mode", "status", "headline", "items", "notes"} <= set(r) and r["id"] == "sibyl" and r["mode"] == "paper" and r["status"] == "sample" and r["headline"]["text"] and r["notes"]
       and r["items"] and all({"title", "detail", "usd", "score", "risk"} <= set(i) and 0 <= i["score"] <= 100 and i["risk"] in ("low", "med", "high") for i in r["items"]), list(r))
    ck("the file is written as sibyl.json and is valid json", os.path.isfile(path) and json.load(open(path, encoding="utf-8"))["id"] == "sibyl")
    picks = [i for i in r["items"] if i.get("picked")]
    ck("picks: 1 to MAX_PICKS, each stake <= 2% of the bankroll, together <= 6%, each with a ruin figure and 1R in the words",
       0 < len(picks) <= MAX_PICKS and all(i["stake_pct"] <= CAP_PCT * 100 + 1e-6 and i["ruin_pct"] is not None and "1R" in i["detail"] and i["stake_usd"] > 0 for i in picks) and sum(i["stake_pct"] for i in picks) <= CAP_TOTAL_PCT * 100 + 0.02, [(i["title"], i["stake_pct"]) for i in picks])
    ck("no claim without n: every item states n, nothing under MIN_N is paper-worthy", all(i.get("n") for i in r["items"]) and not any(i["tier"] == "worthy" and i["n"] < MIN_N for i in r["items"]))
    ck("a fading, unproven, thin or avoided kind of bet never gets a stake", all(not i.get("stake_usd") for i in r["items"] if i["tier"] != "worthy"))
    tiers = [i["tier"] for i in r["items"] if i["tier"] != "rule"]
    ck("sorted: paper-worthy first, avoid last", tiers[0] == "worthy" and tiers[-1] == "avoid" and tiers == sorted(tiers, key=["worthy", "decaying", "unproven", "thin", "avoid"].index), tiers)
    ck("the sample has a thin one (n < 30) shown as 'too few bets', and a fading one", {"thin", "decaying"} <= set(tiers), tiers)
    ck("scoreboard carries its sample size (n=) and says 'Collecting' while small", "n=" in r["scoreboard"]["text"] and r["scoreboard"]["status"] == "collecting", r["scoreboard"])
    ck("what could go wrong: at least 4 risks, each with a level", len(r["risks"]) >= 4 and all(x["level"] in ("low", "med", "high") for x in r["risks"]))
    ck("headline money is a number (estimate) or null", r["headline"]["usd_month"] is None or isinstance(r["headline"]["usd_month"], (int, float)))
    p2, r2 = run(tempfile.mkdtemp(prefix="sibyl-"), fixture=True)
    ck("repeatable: the same fixture gives the same file", json.dumps(r, sort_keys=True) == json.dumps(r2, sort_keys=True))
    e = scan({}, 1793900000)
    ck("empty input: stale, no items, a plain headline, no crash", e["status"] == "stale" and e["items"] == [] and e["headline"]["text"].startswith("Nothing to rank"), e["headline"])
    g = scan({"edges": {"t": 1793759943, "edges": [{"n": "x"}, 5, None, {"n": 100, "w": 0.99, "p": 1.0}]}, "whatif": "junk", "forward": {"sets": "junk"}}, 1793900000)
    ck("garbage input: still a valid stale result with a collecting scoreboard", g["status"] == "stale" and g["scoreboard"]["status"] == "collecting" and g["v"] == 1)
    edge = {"id": "x", "label": "x", "kind": "band", "n": 400, "w": 0.98, "p": 0.95, "status": "HOLDING"}
    ck("a study from an hour ago is ok, from 4 days ago is stale",
       scan({"edges": {"t": 1793900000 - 3600, "edges": [edge]}}, 1793900000)["status"] == "ok" and scan({"edges": {"t": 1793900000 - 4 * 86400, "edges": [edge]}}, 1793900000)["status"] == "stale")
    code = open(os.path.abspath(__file__), encoding="utf-8").read().split("# -----", 1)[0]
    ck("never trades or phones out: no network or order code is imported", not re.search(r"^\s*(import|from)\s+(urllib|requests|socket|http|ssl|ftplib|smtplib)", code, re.M))
    real = load_json(os.path.join(STUDY, "edges.json"))
    if real:
        rr = scan(gather(STUDY, False), 1793900000)
        ck("the real published study scans without error and ranks something", rr["counts"]["edges"] > 0 and rr["status"] in ("ok", "stale"), rr["counts"])
    print(f"\n{'ALL PASS' if not bad else str(len(bad)) + ' FAILED'}")
    return 0 if not bad else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sibyl: a prediction-market edge scanner (suggestions only; reads published Kalshi study files, writes one json).")
    ap.add_argument("--out", help="folder for sibyl.json")
    ap.add_argument("--fixture", action="store_true", help="use the bundled invented sample")
    ap.add_argument("--study", default=STUDY, help="folder with edges.json / whatif.json / forward.json (read only)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.out:
        ap.error("--out is required (or --selftest)")
    path, r = run(a.out, a.fixture, a.study)
    print(f"{path}: {r['status']}, {r['counts']['worthy']} paper-worthy of {r['counts']['edges']} kinds of bet. {r['headline']['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
