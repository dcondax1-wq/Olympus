#!/usr/bin/env python3
"""Kalshi red-team verifier (2026-11-18): check a candidate rule's trade list before anyone believes its number.
Offline, stdlib only, never touches the network or an account.

What it does with a trade list (JSON list / {"rule": {...}, "trades": [...]} / CSV with a header row):
  1. fees     recomputed EXACTLY: ceil_to_cent(rate x C x P x (1-P)) per ORDER (rows sharing an `order_id` are one order:
              their unrounded fees are summed, then rounded up once). Taker rate 0.07, maker 0 unless the row says the series
              charges makers (`maker_fee: true` -> 0.0175); `fee_rate` on a row overrides (e.g. 0.035 on S&P / Nasdaq markets).
              A row's `fee_reported` / `pnl_reported` that differs from the recomputed value by more than half a cent is listed.
  2. timing   every row needs `info_ts` (the newest piece of information the rule used) STRICTLY before `ts` (the order time);
              equal or later, or missing, is a look-ahead failure. A row at or after its `settle_ts` is a failure too.
  3. split    by time (default: the median trade time; `--split 2026-11-01` = a date): win rate, net per $1, 95% bootstrap range
              per half, and whether the halves agree in sign.
  4. money    net per $1 risked (cost = C x P + fee), win rate, break-even win rate, trades a week, $ a month at a stake.
  5. luck     cluster bootstrap (one cluster = one `event`, else `ticker`, else the row), a cluster t, its one-sided p, and the
              multiple-testing bar for the number of rules tried (Bonferroni): with N rules tried, about 0.05 x N look "significant"
              by luck alone. `chance_both_halves(k, n)` = the chance that at least k of n tried rules are positive in both halves by luck.

Row fields: ts, info_ts, price (dollars paid per contract for the side bought, 0 < P < 1), contracts, outcome (1 = the bought side
won, 0 = lost) or side + result ("yes"/"no"), optional: role (taker | maker), maker_fee, fee_rate, order_id, event, ticker,
exit_price (+ exit_role: sold before settlement, the exit pays its own fee), mark_price (not settled yet: valued there, no fee), id / trade_id
(a repeated id is a double count), reward ($ credited by a rewards program; reported apart, it is modelled),
settle_ts, fee_reported, pnl_reported.

    python research/kalshi_red_team/verify.py TRADES.json [--rules-tried N] [--split ISO-date] [--stake 10] [--boot 4000] [--out R.json]
    python research/kalshi_red_team/verify.py --selftest
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import random
import statistics
import sys
from decimal import ROUND_CEILING, Decimal

TAKER_RATE = Decimal("0.07")
MAKER_RATE = Decimal("0.0175")


# ---------------------------------------------------------------- small parsers
def ts_of(x):
    """unix seconds from a number or an ISO string (Z ok); None if missing / unreadable."""
    if x is None or x == "":
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    try:
        return float(s)
    except ValueError:
        pass
    try:
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.timestamp()


def D(x, default=None):
    try:
        return Decimal(str(x).strip())
    except (ArithmeticError, ValueError, TypeError):
        if default is None:
            raise
        return Decimal(default)


def num(r, k):
    """a row's price / contracts as a Decimal; 0 when missing or unreadable (flagged as bad_price)."""
    return D(r.get(k), "0") if r.get(k) not in (None, "") else Decimal(0)


def truthy(x):
    return str(x).strip().lower() in ("1", "true", "yes", "y")


# ---------------------------------------------------------------- fees (exact)
def fee_unrounded(price, contracts, rate):
    p, c, r = D(price), D(contracts), D(rate)
    return r * c * p * (1 - p)


def ceil_cent(x):
    """round a Decimal $ amount UP to the cent (Kalshi rounds fees up)."""
    return (Decimal(x) * 100).to_integral_value(rounding=ROUND_CEILING) / Decimal(100)


def fee(price, contracts, rate=TAKER_RATE):
    """one order: ceil_to_cent(rate x C x P x (1-P)) in $ (a Decimal)."""
    return ceil_cent(fee_unrounded(price, contracts, rate))


def row_rate(r, leg="entry"):
    """the fee rate for a row's entry (or exit) leg."""
    if leg == "entry" and r.get("fee_rate") not in (None, ""):
        return D(r["fee_rate"])
    if leg == "exit" and r.get("exit_fee_rate") not in (None, ""):
        return D(r["exit_fee_rate"])
    role = str(r.get("role" if leg == "entry" else "exit_role") or "taker").lower()
    if role == "maker":
        return MAKER_RATE if truthy(r.get("maker_fee", "")) else Decimal(0)
    return TAKER_RATE


# ---------------------------------------------------------------- loading
def load(path):
    rule = {}
    if path.lower().endswith(".csv"):
        with open(path, newline="", encoding="utf-8") as f:
            rows = [dict(x) for x in csv.DictReader(f)]
    else:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            rule = d.get("rule") or {}
            rows = d.get("trades") or []
        else:
            rows = d
    return rule, rows


def outcome_of(r):
    if r.get("outcome") not in (None, ""):
        return 1 if float(r["outcome"]) >= 0.5 else 0
    res, side = str(r.get("result") or "").lower(), str(r.get("side") or "").lower()
    if res in ("yes", "no") and side in ("yes", "no"):
        return 1 if res == side else 0
    return None


# ---------------------------------------------------------------- the checks
def recompute(rows):
    """per row: cost, fee, pnl (Decimal), plus problems. Orders sharing order_id are rounded once (entry leg)."""
    problems = {"lookahead": [], "missing_info_ts": [], "after_settle": [], "bad_price": [], "no_outcome": [], "fee_mismatch": [],
                "pnl_mismatch": [], "duplicates": [], "same_rows": []}
    groups = {}
    for i, r in enumerate(rows):
        oid = r.get("order_id")
        groups.setdefault(("o", oid) if oid not in (None, "") else ("r", i), []).append(i)
    entry_fee = [Decimal(0)] * len(rows)
    for key, idx in groups.items():
        us = {i: fee_unrounded(num(rows[i], "price"), num(rows[i], "contracts"), row_rate(rows[i])) for i in idx}
        tot = sum(us.values(), Decimal(0))
        rounded = ceil_cent(tot)
        # spread the one rounded order fee over its rows in proportion (for per-row P&L); the total is exact
        for i in idx:
            entry_fee[i] = (rounded * us[i] / tot) if tot > 0 else Decimal(0)
    out, seen = [], set()
    for i, r in enumerate(rows):
        t, it, st = ts_of(r.get("ts")), ts_of(r.get("info_ts", r.get("signal_ts"))), ts_of(r.get("settle_ts"))
        p, c = num(r, "price"), num(r, "contracts")
        if not (Decimal(0) < p < Decimal(1)) or c <= 0:
            problems["bad_price"].append(i)
        if it is None:
            problems["missing_info_ts"].append(i)
        elif t is None or not it < t:
            problems["lookahead"].append(i)
        if st is not None and t is not None and t >= st:
            problems["after_settle"].append(i)
        rid = r.get("id", r.get("trade_id"))
        if rid not in (None, ""):                 # an id seen twice = the same trade counted twice (hard)
            if ("id", rid) in seen:
                problems["duplicates"].append(i)
            seen.add(("id", rid))
        else:                                     # identical rows without ids: a sweep prints several, so only a warning
            k = (r.get("ticker"), r.get("ts"), str(r.get("price")), r.get("side"), str(r.get("contracts")), r.get("order_id"))
            if k in seen:
                problems["same_rows"].append(i)
            seen.add(k)
        won = outcome_of(r)
        fe = entry_fee[i]
        cost = c * p + fe
        marked = False
        if r.get("exit_price") not in (None, ""):
            xp = D(r["exit_price"])
            xf = fee(xp, c, row_rate(r, "exit"))
            value = c * xp - xf
            fe_total = fe + xf
        elif won is None and r.get("mark_price") not in (None, ""):
            value, fe_total, marked = c * D(r["mark_price"]), fe, True      # not settled yet: valued at a mark, no exit fee
        else:
            if won is None:
                problems["no_outcome"].append(i)
                value, fe_total = Decimal(0), fe
            else:
                value, fe_total = c * won, fe
        reward = D(r.get("reward") or 0)
        pnl = value - cost
        if r.get("fee_reported") not in (None, "") and abs(D(r["fee_reported"]) - fe_total) > Decimal("0.005"):
            problems["fee_mismatch"].append(i)
        if r.get("pnl_reported") not in (None, "") and abs(D(r["pnl_reported"]) - (pnl + reward)) > Decimal("0.005"):
            problems["pnl_mismatch"].append(i)
        out.append({"i": i, "ts": t, "cost": cost, "fee": fe_total, "pnl": pnl, "reward": reward, "won": won, "marked": marked,
                    "cluster": str(r.get("event") or r.get("ticker") or "row%d" % i)})
    return out, problems


def boot_ci(items, n=4000, seed=7, key="pnl"):
    """95% cluster bootstrap range of sum(pnl [+ reward]) / sum(cost); items carry 'cluster'."""
    if not items:
        return None, None
    by = {}
    for x in items:
        g = by.setdefault(x["cluster"], [0.0, 0.0])
        g[0] += float(x["pnl"]) + (float(x["reward"]) if key == "pnl+reward" else 0.0)
        g[1] += float(x["cost"])
    groups = list(by.values())
    k = len(groups)
    rnd = random.Random(seed)
    vals = []
    for _ in range(n):
        s = c = 0.0
        for _ in range(k):
            a, b = groups[rnd.randrange(k)]
            s += a
            c += b
        vals.append(s / c if c > 0 else 0.0)
    vals.sort()
    return vals[int(0.025 * n)], vals[min(n - 1, int(0.975 * n))]


def cluster_t(items, key="pnl"):
    """t of the ratio estimate sum(pnl)/sum(cost) with cluster-robust variance (one cluster = one event)."""
    by = {}
    for x in items:
        g = by.setdefault(x["cluster"], [0.0, 0.0])
        g[0] += float(x["pnl"]) + (float(x["reward"]) if key == "pnl+reward" else 0.0)
        g[1] += float(x["cost"])
    k = len(by)
    S = sum(a for a, _ in by.values())
    C = sum(b for _, b in by.values())
    if k < 3 or C <= 0:
        return 0.0
    r = S / C
    var = sum((a - r * b) ** 2 for a, b in by.values()) * k / (k - 1) / C ** 2
    return r / math.sqrt(var) if var > 0 else (math.inf if r > 0 else -math.inf if r < 0 else 0.0)


def bar_t(rules_tried, alpha=0.05):
    """one-sided Bonferroni bar: the t a rule must beat when `rules_tried` rules were looked at."""
    n = max(1, int(rules_tried or 1))
    return statistics.NormalDist().inv_cdf(1 - alpha / n)


def p_one_sided(t):
    if t == math.inf:
        return 0.0
    if t == -math.inf:
        return 1.0
    return 1 - statistics.NormalDist().cdf(t)


def chance_both_halves(k, n, p=0.25):
    """the chance that at least k of n tried rules are positive in BOTH halves by luck (each half a coin flip: p = 1/4)."""
    return sum(math.comb(n, j) * p ** j * (1 - p) ** (n - j) for j in range(k, n + 1))


def stats(items, boot=4000, seed=7, stake=10.0):
    if not items:
        return {"n": 0}
    cost = sum(float(x["cost"]) for x in items)
    pnl = sum(float(x["pnl"]) for x in items)
    rew = sum(float(x["reward"]) for x in items)
    fees = sum(float(x["fee"]) for x in items)
    wins = [x["won"] for x in items if x["won"] is not None]
    t0, t1 = min(x["ts"] for x in items), max(x["ts"] for x in items)
    weeks = max((t1 - t0) / 604800.0, 1 / 7)
    lo, hi = boot_ci(items, boot, seed)
    rlo, rhi = boot_ci(items, boot, seed, key="pnl+reward") if rew else (lo, hi)
    per1 = pnl / cost if cost else 0.0
    return {"n": len(items), "clusters": len({x["cluster"] for x in items}), "win_rate": (sum(wins) / len(wins)) if wins else None,
            "breakeven_win_rate": _breakeven(items), "net_usd": round(pnl, 2), "fees_usd": round(fees, 2), "cost_usd": round(cost, 2), "reward_usd": round(rew, 2),
            "net_per_1": round(per1, 4), "ci95": [round(lo, 4), round(hi, 4)],
            "net_per_1_with_reward": round((pnl + rew) / cost, 4) if cost else 0.0, "ci95_with_reward": [round(rlo, 4), round(rhi, 4)],
            "t": round(cluster_t(items), 2), "p_one_sided": round(p_one_sided(cluster_t(items)), 4),
            "trades_per_week": round(len(items) / weeks, 2), "marked_not_settled": sum(1 for x in items if x.get("marked")),
            "usd_month_at_stake": round(per1 * stake * len(items) / weeks * 4.345, 2), "stake": stake,
            "first": dt.datetime.fromtimestamp(t0, dt.timezone.utc).isoformat(timespec="minutes"),
            "last": dt.datetime.fromtimestamp(t1, dt.timezone.utc).isoformat(timespec="minutes")}


def _breakeven(items):
    """the win rate at which held-to-settlement rows break even: a win pays $1 a contract, so it is sum(cost) / sum(contracts)."""
    held = [x for x in items if x["won"] is not None and x.get("contracts")]
    if not held:
        return None
    return round(sum(float(x["cost"]) for x in held) / sum(x["contracts"] for x in held), 4)


def verify(rows, rule=None, rules_tried=None, split=None, boot=4000, seed=7, stake=10.0):
    rule = dict(rule or {})
    n_tried = int(rules_tried or rule.get("rules_tried") or 0) or None
    items, problems = recompute(rows)
    for x, r in zip(items, rows):
        x["contracts"] = float(num(r, "contracts"))
    timed = [x for x in items if x["ts"] is not None]
    timed.sort(key=lambda x: x["ts"])
    if split:
        cut = ts_of(split)
    elif timed:
        cut = timed[len(timed) // 2]["ts"]
    else:
        cut = None
    first = [x for x in timed if cut is not None and x["ts"] < cut]
    second = [x for x in timed if cut is not None and x["ts"] >= cut]
    allst = stats(timed, boot, seed, stake)
    h1, h2 = stats(first, boot, seed + 1, stake), stats(second, boot, seed + 2, stake)
    bar = bar_t(n_tried or 1)
    hard = {k: v for k, v in problems.items() if v and k in ("lookahead", "missing_info_ts", "after_settle", "bad_price", "duplicates")}
    soft = {k: v for k, v in problems.items() if v and k not in hard}
    same_sign = (h1.get("n", 0) > 0 and h2.get("n", 0) > 0 and (h1["net_per_1"] > 0) == (h2["net_per_1"] > 0))
    reasons = []
    if hard:
        reasons.append("look-ahead / data problems: " + ", ".join("%s %d" % (k, len(v)) for k, v in hard.items()))
    if soft.get("fee_mismatch") or soft.get("pnl_mismatch"):
        reasons.append("reported fees or P&L differ from the exact recompute on %d rows" % (len(soft.get("fee_mismatch", [])) + len(soft.get("pnl_mismatch", []))))
    if allst.get("n", 0) and allst["net_per_1"] <= 0:
        reasons.append("net per $1 is not positive after exact fees (%+.1f%%)" % (100 * allst["net_per_1"]))
    if allst.get("n", 0) and allst["ci95"][0] <= 0 < allst["net_per_1"]:
        reasons.append("the 95%% range includes zero (%+.1f%% to %+.1f%%)" % (100 * allst["ci95"][0], 100 * allst["ci95"][1]))
    if not same_sign and h1.get("n") and h2.get("n"):
        reasons.append("the two time halves disagree (%+.1f%% / %+.1f%%)" % (100 * h1["net_per_1"], 100 * h2["net_per_1"]))
    if n_tried is None:
        reasons.append("the number of rules tried is not stated: assume many (multiple testing)")
    elif allst.get("n", 0) and allst["t"] < bar:
        reasons.append("t %.2f is under the multiple-testing bar %.2f for %d rules tried" % (allst["t"], bar, n_tried))
    if allst.get("n", 0) < 30:
        reasons.append("only %d trades" % allst.get("n", 0))
    if hard or (allst.get("n", 0) and allst["net_per_1"] <= 0):
        verdict = "false"
    elif not reasons:
        verdict = "holds"
    else:
        verdict = "weak"
    return {"rule": rule.get("name") or rule.get("rule") or "", "verdict": verdict, "reasons": reasons, "rules_tried": n_tried,
            "multiple_testing_bar_t": round(bar, 2), "expected_false_positives_at_5pct": round(0.05 * (n_tried or 1), 2),
            "split_at": dt.datetime.fromtimestamp(cut, dt.timezone.utc).isoformat(timespec="minutes") if cut else None,
            "all": allst, "first_half": h1, "second_half": h2, "halves_agree": same_sign,
            "problems": {k: v[:20] for k, v in problems.items() if v}, "problem_counts": {k: len(v) for k, v in problems.items() if v}}


def report(v):
    a = v["all"]
    L = ["RULE %s -> %s" % (v["rule"] or "(unnamed)", v["verdict"].upper())]
    if a.get("n"):
        L.append("  trades %d (%d events), %s .. %s, %.1f a week" % (a["n"], a["clusters"], a["first"], a["last"], a["trades_per_week"]))
        L.append("  win rate %s (break-even %s), net per $1 %+.2f%% (95%% %+.2f%% to %+.2f%%), net $%.2f after $%.2f fees" % (
            "%.1f%%" % (100 * a["win_rate"]) if a["win_rate"] is not None else "n/a",
            "%.1f%%" % (100 * a["breakeven_win_rate"]) if a.get("breakeven_win_rate") is not None else "n/a",
            100 * a["net_per_1"], 100 * a["ci95"][0], 100 * a["ci95"][1], a["net_usd"], a["fees_usd"]))
        if a["reward_usd"]:
            L.append("  with modelled rewards $%.2f: %+.2f%% per $1 (95%% %+.2f%% to %+.2f%%)" % (
                a["reward_usd"], 100 * a["net_per_1_with_reward"], 100 * a["ci95_with_reward"][0], 100 * a["ci95_with_reward"][1]))
        for nm in ("first_half", "second_half"):
            h = v[nm]
            if h.get("n"):
                L.append("  %-11s n %4d  net per $1 %+.2f%% (95%% %+.2f%% to %+.2f%%)" % (nm.replace("_", " "), h["n"], 100 * h["net_per_1"], 100 * h["ci95"][0], 100 * h["ci95"][1]))
        L.append("  t %.2f, one-sided p %.4f; bar for %s rules tried: t %.2f; $ a month at $%.0f a trade: %+.2f" % (
            a["t"], a["p_one_sided"], v["rules_tried"] or "?", v["multiple_testing_bar_t"], a["stake"], a["usd_month_at_stake"]))
    for r in v["reasons"]:
        L.append("  - " + r)
    return "\n".join(L)


# ---------------------------------------------------------------- selftest (the unit tests live in tests/test_kalshi_red_team.py)
def selftest():
    assert fee("0.50", 100) == Decimal("1.75")
    assert fee("0.50", 1) == Decimal("0.02")
    assert fee("0.10", 10) == Decimal("0.07")
    assert fee("0.50", 100, MAKER_RATE) == Decimal("0.44")
    print("verify selftest: 4/4 ALL PASS")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("trades", nargs="?")
    ap.add_argument("--rules-tried", type=int, default=None)
    ap.add_argument("--split", default=None)
    ap.add_argument("--stake", type=float, default=10.0)
    ap.add_argument("--boot", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.trades:
        ap.error("give a trade list (JSON or CSV)")
    rule, rows = load(a.trades)
    v = verify(rows, rule, a.rules_tried, a.split, a.boot, a.seed, a.stake)
    print(report(v))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(v, f, indent=1)
    return 0 if v["verdict"] != "false" else 2


if __name__ == "__main__":
    sys.exit(main())
