#!/usr/bin/env python3
"""Kalshi Liquidity Incentive Program maths, as published on help.kalshi.com (read 2026-11-18):
  - the book is snapshotted once a second; a snapshot is EXCLUDED unless resting size reaches Target on BOTH the yes and no side;
  - reference price per side = walking down from the best bid, the first level where cumulative size reaches Target/5;
  - QUALIFYING orders = whole price levels from the best bid down to (and including) the first level where cumulative size
    reaches Target (the filed rule text, KalshiEX Aug 2025 program, "Qualifying Yes Bids"); deeper bids score nothing;
  - an order's raw score = size x (1 at or better than the reference, else DiscountFactor ^ ticks below it);
  - an order's share = its raw score / the total raw score of the qualifying orders ON THAT SIDE (yes and no are normalised
    separately), a snapshot's score = your yes share + your no share (at most 2.0 over everyone);
  - period score = your snapshot scores / everyone's snapshot scores; reward = period score x period reward
    x (non-excluded snapshots / all snapshots), rounded DOWN to the cent; a market's program pays nothing under $1.00
    (the $1 minimum is per market program, sub-dollar programs never combine).
So, per second, a small order earns  pool_per_s x my_side_score / (side_total + my_side_score) / 2  while the snapshot is valid.
Pure functions, stdlib only (tests: tests/test_kalshi_best_shot.py)."""
from __future__ import annotations

import math

TICK = 0.01


def norm(levels):
    """[(price, size)] best bid first; drops empty levels."""
    return sorted([(round(float(p), 4), float(s)) for p, s in (levels or []) if float(s) > 0], reverse=True)


def ref_price(levels, target):
    """first price (walking down from the best bid) where cumulative size reaches Target/5; None if the side never gets there."""
    cum = 0.0
    for p, s in norm(levels):
        cum += s
        if cum >= target / 5.0 - 1e-9:
            return p
    return None


def mult(price, ref, df):
    if ref is None:
        return 0.0
    if price >= ref - 1e-9:
        return 1.0
    return df ** int(round((ref - price) / TICK))


def qualifying(levels, target):
    """the levels that score: from the best bid down to (and including) the first level where cumulative size reaches Target;
    [] when the side never reaches Target."""
    lv = norm(levels)
    cum = 0.0
    for i, (p, s) in enumerate(lv):
        cum += s
        same_next = i + 1 < len(lv) and abs(lv[i + 1][0] - p) < 1e-9      # a level counts whole (all bids at that price)
        if cum >= target - 1e-9 and not same_next:
            return lv[:i + 1]
    return []


def floor_price(levels, target):
    """the lowest price that still scores (the level where cumulative size reaches Target); None if the side never does."""
    q = qualifying(levels, target)
    return q[-1][0] if q else None


def side_score(levels, ref, df, target=None):
    """everyone's raw score on a side; with `target`, only the qualifying levels count (the filed rule)."""
    lv = qualifying(levels, target) if target is not None else norm(levels)
    return sum(s * mult(p, ref, df) for p, s in lv)


def ahead(levels, price):
    """resting size at prices >= price: the queue in front of a NEW order at `price` (price-time priority)."""
    return sum(s for p, s in norm(levels) if p >= price - 1e-9)


def side_valid(levels, target):
    return sum(s for _, s in norm(levels)) >= target - 1e-9


def my_share(levels, price, size, target, df):
    """(my share of this side's score, new reference) with my order of `size` at `price` added to the side."""
    if size <= 0 or price is None:
        return 0.0, ref_price(levels, target)
    lv = norm(list(levels or []) + [(price, size)])
    r = ref_price(lv, target)
    fl = floor_price(lv, target)
    if r is None or fl is None or price < fl - 1e-9:
        return 0.0, r                                   # the side is under Target, or my bid is deeper than the Target walk
    mine = size * mult(price, r, df)
    tot = side_score(lv, r, df, target)
    return (mine / tot if tot > 0 else 0.0), r


def reward_rate(book_yes, book_no, side, price, size, target, df, pool_usd_day):
    """$ a day my one order earns if this book held all day (0 when the snapshot would be excluded)."""
    mine = list(book_yes or []) if side == "yes" else list(book_no or [])
    other = list(book_no or []) if side == "yes" else list(book_yes or [])
    if not side_valid(mine + [(price, size)], target) or not side_valid(other, target):
        return 0.0
    sh, _ = my_share(mine, price, size, target, df)
    return pool_usd_day * sh / 2.0


def payout(reward_usd):
    """what Kalshi actually pays for one market program: rounded down to the cent, nothing under $1.00."""
    c = math.floor(reward_usd * 100 + 1e-9) / 100.0
    return c if c >= 1.0 - 1e-9 else 0.0


def taker_fee(price, n):
    """Kalshi's general taker fee: 0.07 x C x P x (1-P), rounded up to the cent per order."""
    return math.ceil(0.07 * n * price * (1 - price) * 100 - 1e-9) / 100.0


def maker_fee(price, n, fee_type):
    """maker fee only where the series' fee type has one (0.0175 x C x P x (1-P), rounded up per fill)."""
    if "maker" not in str(fee_type or ""):
        return 0.0
    return math.ceil(0.0175 * n * price * (1 - price) * 100 - 1e-9) / 100.0
