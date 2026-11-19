"""KALSHI ADAPT: the K8 clock bot's weekly re-test (night-kadapt 2026-11-19; owner: "We are gonna make the best bot: one that
automatically adapts like others." Agreed: lower-risk changes automatic, higher-risk ones need his yes).

Every week it re-tests each K8 leg (engine/kalshi_clock.LEGS) on the PUBLIC Kalshi tape: the price takers paid for our side 15-30 s
after the window opened (the bot buys at +20 s), flat $ a bet, whole contracts, the exact Kalshi taker fee (research/kalshi_red_team/
verify.py: ceil to the cent of 0.07 x C x P x (1-P) per order), held to the settle. Two rolling windows: the last 8 and 4 weeks.

AUTOMATIC (risk only ever goes DOWN): data/kalshi_live/clock_adapt.json, which engine/kalshi_clock.leg_limits reads before EVERY
bet (paper and live). It is not part of what the owner armed, so it needs no phrase. Rules fixed 2026-11-19, BEFORE any rolling
result was read (RULES below):
  half     8-week net per $1 under +5%                                -> that leg bets half (size factor 0.5)
  off      8-week net per $1 under 0 AND 4-week net per $1 under 0     -> that leg stops betting (paper keeps recording)
  cap      4-week average price paid >= the leg's tested average + 4c (others buying the same seconds)
                                                                   -> skip asks above (8-week win rate - 8c), never under 50c
  guard    a leg with under 25 bets in the 8 weeks (or under 12 in the 4 weeks, for the rules that read the 4 weeks) is not touched
  sticky   NOTHING is raised back automatically: a size factor only goes down, a max price only down, OFF stays OFF
ASKS THE OWNER (Decide card, tools/web_public/business/decisions.json, new ids only; a tap posts a note, Claude marks it yes):
  restore  a leg that is half / OFF / capped and has recovered (8-week >= +10% and 4-week > 0; a cap: the 4-week price back
           under the tested average + 2c): "put gold DOWN 05:15 back to full size?". A "yes" on the card is applied on the PC
           by the next weekly run (or `--restore <leg>` on the PC); it only goes back to what the owner armed, and the leg starts
           fresh (only bets after the yes count, 25 again before a rule reads it; the live kill rules still watch it).
  new leg  (the cloud, tools/kalshi_adapt.py: needs the 1-minute quotes of every window) 384 rules = 96 quarter hours x gold /
           silver x up / down, found on the older 8 of the last 12 weeks only if the cluster t clears verify.py's
           multiple-testing bar for 384 rules (Bonferroni, ~3.66) and +10% per $1, then checked once on the newest 4 weeks
           (held out: >= +5% per $1, >= 12 bets). At most 2 a week. A yes = Claude adds it as a PAPER leg; live needs the phrase.
It never arms, never places or cancels an order, never raises a size or adds a leg, never edits research/lab/kalshi_clock.json or
research/lab/kalshi_candidates/ (what the owner armed). Public GET only, at most one request a second, no key ever read.

Where it runs:
  PC     pc_weekly(): inside the data pipe's nightly child (engine/datapipe.run, after the 17:00 ET close, just before ZEUS
         learned), once every ~7 days, never within 20 minutes of a K8 window; its line rides the nightly ZEUS learned push.
         It also takes the cloud's shrinks (research/lab/kalshi_adapt.json, most restrictive wins). LE_KADAPT=0 = off. Never raises.
  cloud  python tools/kalshi_adapt.py   (the same rules on the public tape + the 96-window scan + the Decide card)

    python -X utf8 -m engine.kalshi_adapt                 # the PC's weekly run now (on demand; fetches the public tape)
    python -X utf8 -m engine.kalshi_adapt --report        # what clock_adapt.json says now, in plain words
    python -X utf8 -m engine.kalshi_adapt --restore gold_0530_down   # the owner's yes: back to full size / on / the armed cap
Tests: python -X utf8 -m tests.test_kalshi_adapt
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import ROUND_CEILING, Decimal

from engine import kalshi_clock as KC
from engine import kalshi_live as KL

ROOT = KL.ROOT
VERSION = 1
LAB_REPORT = os.path.join(ROOT, "research", "lab", "kalshi_adapt.json")
DECISIONS = os.path.join(ROOT, "tools", "web_public", "business", "decisions.json")
VERIFY_PY = os.path.join(ROOT, "research", "kalshi_red_team", "verify.py")
REPORT_REL = "research/lab/kalshi_adapt.json"

# ------------------------------------------------------------------------------------------------ the rules (fixed 2026-11-19)
RULES = {
    "weeks_long": 8, "weeks_short": 4,
    "min_bets_long": 25, "min_bets_short": 12,          # the min-sample guard
    "half_below": 0.05, "half_factor": 0.5,             # 8-week net per $1 under +5% -> half size
    "off_below": 0.0,                                   # 8-week AND 4-week net per $1 under 0 -> OFF
    "creep_c": 0.04, "cap_margin": 0.08, "cap_floor": 0.50,
    "restore_at": 0.10, "restore_creep_c": 0.02,        # proposals only (never automatic)
    "entry_window_s": [15, 30], "entry_fallback_s": [5, 45],
    # the 96-window scan (cloud): older 8 of the last 12 weeks find, the newest 4 check
    "scan_weeks": 12, "scan_holdout_weeks": 4, "scan_rules": 384, "scan_alpha": 0.05,
    "scan_min_net": 0.10, "scan_min_n": 25, "scan_hold_min_net": 0.05, "scan_hold_min_n": 12,
    "scan_max_price": 0.70, "scan_max_spread": 0.10, "new_per_week": 2,
}
# the price each leg paid when it was tested (research/kalshi_edge_K8/results.json, tape entry, TRAIN 2026-08-03..09-30)
BASE_PRICE = {"gold_0530_down": 0.512, "silver_0530_down": 0.510, "gold_1700_up": 0.517, "silver_1700_up": 0.529,
              "silver_1615_down": 0.533}
SERIES_NAME = {"KXGOLD15M": "gold", "KXSILVER15M": "silver"}
LEG_SHORT = {"gold_0530_down": "gold 05:30 down", "silver_0530_down": "silver 05:30 down", "silver_1615_down": "silver 16:15 down",
             "gold_1700_up": "gold 17:00 up", "silver_1700_up": "silver 17:00 up"}
PC_EVERY_S = int(6.5 * 86400)          # the PC's weekly cadence
PC_QUIET_S = 20 * 60                   # never this close before a K8 window (the bot reads the book then)
PC_BUDGET = 450                        # public GETs per PC run at most (the first run fills 8 weeks: ~401, ~7 min; then ~50 a week)
GAP_S = 1.05                           # at most one public request a second
CHANGES_KEEP = 60
WHY_MAX = 80                           # engine/kalshi_clock.leg_limits shows at most 80 characters


# ================================================================================================ small helpers
def _f(x, d=None):
    try:
        v = float(x)
        return v if math.isfinite(v) else d
    except (TypeError, ValueError):
        return d


def _jread(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _jwrite(path, obj, indent=None):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=indent, separators=None if indent else (",", ":"), default=str)
        fh.write("\n" if indent else "")
    os.replace(tmp, path)


def _day(x) -> dt.date:
    return x if isinstance(x, dt.date) else dt.date.fromisoformat(str(x)[:10])


def money(x, sign=False) -> str:
    return KL.money(x, sign)


def pct(x) -> str:
    return "n/a" if x is None else f"{100 * x:+.0f}%"


def floor_cent(x) -> float:
    return math.floor(round(x * 100, 6)) / 100.0


_VERIFY = []


def verify_mod():
    """research/kalshi_red_team/verify.py (the red team's exact fees, cluster t, multiple-testing bar), or None when missing."""
    if not _VERIFY:
        mod = None
        try:
            spec = importlib.util.spec_from_file_location("kalshi_red_team_verify", VERIFY_PY)
            if spec and spec.loader and os.path.isfile(VERIFY_PY):
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
        except Exception:  # noqa: BLE001
            mod = None
        _VERIFY.append(mod)
    return _VERIFY[0]


def fee(price, contracts) -> float:
    """Kalshi taker fee of one order in $: ceil to the cent of 0.07 x C x P x (1-P) (verify.fee; the same formula without it)."""
    V = verify_mod()
    if V is not None:
        return float(V.fee(Decimal(str(price)), Decimal(int(contracts))))
    x = Decimal("0.07") * Decimal(int(contracts)) * Decimal(str(price)) * (1 - Decimal(str(price)))
    return float((x * 100).to_integral_value(rounding=ROUND_CEILING) / Decimal(100))


def bar_t(rules_tried, alpha=0.05) -> float:
    V = verify_mod()
    if V is not None:
        return float(V.bar_t(rules_tried, alpha))
    return statistics.NormalDist().inv_cdf(1 - alpha / max(1, int(rules_tried)))


def cluster_t(items) -> float:
    V = verify_mod()
    if V is not None:
        return float(V.cluster_t(items))
    by = {}
    for x in items:
        g = by.setdefault(x["cluster"], [0.0, 0.0])
        g[0] += float(x["pnl"])
        g[1] += float(x["cost"])
    k, S, C = len(by), sum(a for a, _ in by.values()), sum(b for _, b in by.values())
    if k < 3 or C <= 0:
        return 0.0
    r = S / C
    var = sum((a - r * b) ** 2 for a, b in by.values()) * k / (k - 1) / C ** 2
    return r / math.sqrt(var) if var > 0 else (math.inf if r > 0 else -math.inf if r < 0 else 0.0)


# ================================================================================================ bets (pure)
def tape_price(trades, side, window=None, fallback=None):
    """The VWAP takers of `side` paid between window[0] and window[1] seconds after the open (else the fallback window), as the
    K8 study did (research/kalshi_edge_K8/study.price_tape). trades = [[seconds, taker_side, yes_price, count], ...]."""
    lo, hi = window or RULES["entry_window_s"]
    flo, fhi = fallback or RULES["entry_fallback_s"]
    for a, b in ((lo, hi), (flo, fhi)):
        px = []
        for x in trades or []:
            try:
                s, ts, yp, c = float(x[0]), str(x[1]), float(x[2]), float(x[3])
            except (TypeError, ValueError, IndexError):
                continue
            if ts == side and a <= s <= b and c > 0 and 0 < yp < 1:
                px.append((yp if side == "yes" else 1 - yp, c))
        q = sum(c for _, c in px)
        if q > 0:
            return round(sum(p * c for p, c in px) / q, 4)
    return None


def make_bet(lid, day, ticker, open_t, side, price, result, stake) -> dict | None:
    """One flat-stake taker bet held to the settle (None when the price is unusable or the market has no result)."""
    if price is None or not (0.0 < price < 0.995) or result not in ("yes", "no"):
        return None
    n = max(1, int(math.floor(stake / price + 1e-9)))
    fe = fee(price, n)
    won = 1 if result == side else 0
    cost = n * price + fe
    return {"leg": lid, "day": str(day), "ticker": ticker, "side": side, "ts": open_t + 20, "info_ts": open_t, "settle_ts": open_t + 900,
            "price": price, "contracts": n, "fee": fe, "cost": round(cost, 4), "outcome": won, "pnl": round(won * n - cost, 4),
            "event": ticker}


def days_between(start, end):
    d, end = _day(start), _day(end)
    while d <= end:
        yield d
        d += dt.timedelta(days=1)


def leg_bets(tape, start, end, cfg=None, stake=None, legs=None) -> dict:
    """{leg id: [bets]} for every ET weekday in [start, end] the executor would bet (engine/kalshi_clock's own calendar: the
    London clock for the morning legs, the UK / CME holiday skips). tape = {ticker: {"res": "yes"|"no", "tr": [...]}}."""
    cfg = cfg or KC.load_config()[0]
    stake = float(stake or cfg["stake_usd"])
    out = {lid: [] for lid in (legs or cfg["paper_legs"])}
    for d in days_between(start, end):
        if d.weekday() >= 5:
            continue
        for lid in out:
            leg = KC.LEG[lid]
            if KC.skipped(leg, d):
                continue
            o = KC.leg_open(leg, d)
            tk = KC.ticker(leg["series"], o)
            rec = tape.get(tk)
            if not rec:
                continue
            b = make_bet(lid, d, tk, o, leg["side"], tape_price(rec.get("tr"), leg["side"]), rec.get("res"), stake)
            if b:
                out[lid].append(b)
    return out


def stats(bets, weeks=None) -> dict:
    """n, won, win rate, net $, net per $1 risked (fee in), the average price paid, $ a month (at the bets' own stake)."""
    if not bets:
        return {"n": 0}
    n = len(bets)
    won = sum(b["outcome"] for b in bets)
    cost = sum(b["cost"] for b in bets)
    net = sum(b["pnl"] for b in bets)
    if weeks is None:
        d0, d1 = min(_day(b["day"]) for b in bets), max(_day(b["day"]) for b in bets)
        weeks = max(1.0, ((d1 - d0).days + 1) / 7.0)
    return {"n": n, "won": won, "win_rate": round(won / n, 4), "net_usd": round(net, 2), "cost_usd": round(cost, 2),
            "net_per_1": round(net / cost, 4) if cost else None, "avg_price": round(sum(b["price"] for b in bets) / n, 4),
            "fees_usd": round(sum(b["fee"] for b in bets), 2), "usd_month": round(net / weeks * 4.345, 2),
            "bets_month": round(n / weeks * 4.345, 1), "first": min(b["day"] for b in bets), "last": max(b["day"] for b in bets)}


# ================================================================================================ the weekly rules (pure)
def windows_of(as_of) -> dict:
    a = _day(as_of)
    return {"long": (a - dt.timedelta(days=7 * RULES["weeks_long"] - 1), a), "short": (a - dt.timedelta(days=7 * RULES["weeks_short"] - 1), a)}


def leg_name(lid) -> str:
    return KC.LEG[lid]["name"] if lid in KC.LEG else lid


def clean_adapt(raw) -> dict:
    """A clock_adapt.json (or the cloud report's "adapt") reduced to what may only shrink: per leg enabled False, a size factor in
    [0, 1), a max price in [0.02, 0.80); anything else is dropped (a bad value can never raise anything)."""
    out = {}
    legs = (raw or {}).get("legs") if isinstance(raw, dict) else None
    for lid, v in (legs or {}).items() if isinstance(legs, dict) else []:
        if lid not in KC.LEG or not isinstance(v, dict):
            continue
        e, since = {}, v.get("since") if isinstance(v.get("since"), dict) else {}
        if v.get("enabled") is False:
            e["enabled"] = False
        f = _f(v.get("size_factor"))
        if f is not None and 0 <= f < 1:
            e["size_factor"] = round(f, 4)
        mp = _f(v.get("max_price"))
        if mp is not None and 0.02 <= mp < KC.HARD["price_cap"]:
            e["max_price"] = round(mp, 4)
        if e:
            e["since"] = {k: str(since.get(k) or "")[:10] for k in ("enabled", "size_factor", "max_price") if k in e}
            e["why"] = str(v.get("why") or "")[:WHY_MAX]
            out[lid] = e
    return out


def merge(*adapts) -> dict:
    """The most restrictive of several cleaned adapt dicts: OFF wins, the smallest size factor, the lowest max price."""
    out = {}
    for a in adapts:
        for lid, v in (a or {}).items():
            o = out.setdefault(lid, {"since": {}, "why": ""})
            if v.get("enabled") is False and o.get("enabled") is not False:
                o["enabled"], o["since"]["enabled"] = False, v.get("since", {}).get("enabled", "")
            if "size_factor" in v and v["size_factor"] < o.get("size_factor", 1.0):
                o["size_factor"], o["since"]["size_factor"] = v["size_factor"], v.get("since", {}).get("size_factor", "")
            if "max_price" in v and v["max_price"] < o.get("max_price", 9.0):
                o["max_price"], o["since"]["max_price"] = v["max_price"], v.get("since", {}).get("max_price", "")
            if v.get("why") and not o["why"]:
                o["why"] = v["why"]
    return {k: v for k, v in out.items() if any(x in v for x in ("enabled", "size_factor", "max_price"))}


def drop_restored(adapt, restored) -> dict:
    """Leave out every restriction whose evidence date is on or before the owner's restore of that leg (restored = {leg: day})."""
    out = {}
    for lid, v in (adapt or {}).items():
        r = str((restored or {}).get(lid) or "")
        if not r:
            out[lid] = v
            continue
        keep = {k: v[k] for k in ("enabled", "size_factor", "max_price") if k in v and str(v.get("since", {}).get(k) or "") > r}
        if keep:
            out[lid] = dict(keep, since={k: v["since"][k] for k in keep}, why=v.get("why", ""))
    return out


def effective_cap(cfg, lid, adapt) -> float:
    cap = min(cfg["price_cap"], _f((cfg.get("leg_price_cap") or {}).get(lid), 9.0))
    mp = (adapt.get(lid) or {}).get("max_price")
    return min(cap, mp) if mp is not None else cap


def evaluate(bets_by_leg, as_of, prev=None, cfg=None, restored=None, src="pc") -> dict:
    """The weekly decision. prev = the restrictions in force ({"legs": {...}} or the legs dict; sticky). -> {"legs": per-leg
    numbers + rule hits, "adapt": the new restrictions (never looser than prev), "changes": what got tighter today (plain words),
    "proposals": restore asks (never applied here), "line": one short line}."""
    cfg = cfg or KC.load_config()[0]
    W = windows_of(as_of)
    prev_legs = prev.get("legs") if isinstance(prev, dict) and isinstance(prev.get("legs"), dict) else (prev or {})
    prev = drop_restored(clean_adapt({"legs": prev_legs}), restored)
    day = str(_day(as_of))
    want, rows, b8s = {}, {}, {}
    stake = float(cfg["stake_usd"])
    rs = {k: str(v)[:10] for k, v in (restored or {}).items() if v}
    for lid, bets in bets_by_leg.items():
        if rs.get(lid):                                # the owner's yes = a fresh start: only bets after it count (25 needed again)
            bets = [b for b in bets if b["day"] > rs[lid]]
        armed = effective_cap(cfg, lid, {})          # the bot as armed skips asks above its cap: the money is read on the rest
        a8 = [b for b in bets if str(W["long"][0]) <= b["day"] <= str(W["long"][1])]
        a4 = [b for b in a8 if b["day"] >= str(W["short"][0])]
        b8 = [b for b in a8 if b["price"] <= armed + 1e-9]
        b4 = [b for b in a4 if b["price"] <= armed + 1e-9]
        b8s[lid] = b8
        s8, s4 = stats(b8, RULES["weeks_long"]), stats(b4, RULES["weeks_short"])
        if a4:                                         # the price creep is read on EVERY window (the market's price, any cap)
            s4["avg_price_all"] = round(sum(b["price"] for b in a4) / len(a4), 4)
        if a8:
            s8["avg_price_all"] = round(sum(b["price"] for b in a8) / len(a8), 4)
        r = {"name": leg_name(lid), "live": lid in cfg["live_legs"], "w8": s8, "w4": s4, "base_price": BASE_PRICE.get(lid), "hits": []}
        if rs.get(lid):
            r["restored"] = rs[lid]
        rows[lid] = r
        if s8.get("n", 0) < RULES["min_bets_long"]:
            r["guard"] = f"only {s8.get('n', 0)} bets in 8 weeks (needs {RULES['min_bets_long']}): not touched"
            continue
        w = {}
        n8, n4 = s8["net_per_1"], s4.get("net_per_1")
        if n8 < RULES["half_below"]:
            w["size_factor"] = RULES["half_factor"]
            r["hits"].append("half")
        short_ok = s4.get("n", 0) >= RULES["min_bets_short"]
        if not short_ok:
            r["guard"] = f"only {s4.get('n', 0)} bets in 4 weeks (needs {RULES['min_bets_short']}): the 4-week rules not read"
        if short_ok and n8 < RULES["off_below"] and n4 is not None and n4 < RULES["off_below"]:
            w["enabled"] = False
            r["hits"].append("off")
        base = BASE_PRICE.get(lid)
        if short_ok and base is not None and s4["avg_price_all"] >= base + RULES["creep_c"] - 1e-9:
            new_cap = max(RULES["cap_floor"], floor_cent(s8["win_rate"] - RULES["cap_margin"]))
            if new_cap < effective_cap(cfg, lid, prev) - 1e-9:
                w["max_price"] = round(new_cap, 2)
                r["hits"].append("cap")
            else:
                r["hits"].append("creep (cap already lower)")
        if w:
            want[lid] = dict(w, since={k: day for k in w})
    new = merge(prev, want)
    changes = []
    for lid, v in new.items():
        p = prev.get(lid) or {}
        r = rows.get(lid) or {}
        s8, s4 = r.get("w8") or {}, r.get("w4") or {}
        sh = LEG_SHORT.get(lid, lid)
        words = []      # (what, from, to, the plain words, the leg's why (<= 80), the line's few words)
        if v.get("enabled") is False and p.get("enabled") is not False:
            words.append(("enabled", True, False, f"lost money over the last 8 weeks ({pct(s8.get('net_per_1'))} per $1, {s8.get('n')} bets) "
                          f"and the last 4 ({pct(s4.get('net_per_1'))}, {s4.get('n')} bets): OFF, paper keeps recording",
                          f"weekly re-test: lost over 8 weeks ({pct(s8.get('net_per_1'))}) and 4 ({pct(s4.get('net_per_1'))})",
                          f"{sh} OFF (8 wk {pct(s8.get('net_per_1'))}, 4 wk {pct(s4.get('net_per_1'))})"))
        if v.get("size_factor", 1.0) < p.get("size_factor", 1.0):
            words.append(("size_factor", p.get("size_factor", 1.0), v["size_factor"],
                          f"made only {pct(s8.get('net_per_1'))} per $1 over the last 8 weeks ({s8.get('n')} bets, under the "
                          f"+{100 * RULES['half_below']:.0f}% bar): half size ({money(stake * v['size_factor'])} a bet at {money(stake)})",
                          f"weekly re-test: {pct(s8.get('net_per_1'))} per $1 over 8 weeks, half size",
                          f"{sh} half size (8 wk {pct(s8.get('net_per_1'))})"))
        if v.get("max_price", 9.0) < p.get("max_price", 9.0):
            up = (s4.get("avg_price_all") or 0) - (BASE_PRICE.get(lid) or 0)
            words.append(("max_price", p.get("max_price", effective_cap(cfg, lid, {})), v["max_price"],
                          f"paid {100 * (s4.get('avg_price_all') or 0):.0f}c on average in the last 4 weeks vs "
                          f"{100 * (BASE_PRICE.get(lid) or 0):.0f}c when tested (others buy the same seconds): skips asks above "
                          f"{100 * v['max_price']:.0f}c now (won {100 * (s8.get('win_rate') or 0):.0f}% over 8 weeks)",
                          f"weekly re-test: prices up {100 * up:.0f}c, skips asks above {100 * v['max_price']:.0f}c",
                          f"{sh} max {100 * v['max_price']:.0f}c (paid +{100 * up:.0f}c)"))
        for what, a, b, long_words, why, short in words:
            changes.append({"day": day, "leg": lid, "what": what, "from": a, "to": b, "text": f"{leg_name(lid)}: {long_words}",
                            "short": short})
        v["why"] = (words[0][4] if words else (p.get("why") or v.get("why") or "weekly re-test"))[:WHY_MAX]
    for lid, r in rows.items():
        r["now"] = {k: new.get(lid, {}).get(k) for k in ("enabled", "size_factor", "max_price") if k in new.get(lid, {})}
        cap = effective_cap(cfg, lid, new)
        above = [b for b in b8s.get(lid) or [] if b["price"] > cap + 1e-9]
        r["above_cap_usd_month"] = round(sum(b["pnl"] for b in above) / RULES["weeks_long"] * 4.345, 2) if above else 0.0
    props = restore_proposals(rows, new, day, cfg)
    L = {"v": VERSION, "kind": "k8-adapt", "src": src, "as_of": day, "rules": RULES, "windows": {k: [str(a), str(b)] for k, (a, b) in W.items()},
         "legs": rows, "adapt": new, "changes": changes, "proposals": props}
    L["line"] = line(L)
    return L


def restore_proposals(rows, adapt, day, cfg) -> list:
    """A Decide-card ask for every LIVE leg that is restricted and has recovered (never applied automatically)."""
    out = []
    stake = float(cfg["stake_usd"])
    for lid, v in adapt.items():
        r = rows.get(lid) or {}
        s8, s4 = r.get("w8") or {}, r.get("w4") or {}
        if lid not in cfg["live_legs"] or s8.get("n", 0) < RULES["min_bets_long"] or s4.get("n", 0) < RULES["min_bets_short"]:
            continue
        perf = s8["net_per_1"] >= RULES["restore_at"] and (s4.get("net_per_1") or 0) > 0
        price_ok = s4.get("avg_price_all", s4["avg_price"]) < (BASE_PRICE.get(lid) or 0) + RULES["restore_creep_c"]
        need_perf = v.get("enabled") is False or "size_factor" in v
        if (need_perf and not perf) or ("max_price" in v and not price_ok):
            continue
        what = []
        if v.get("enabled") is False:
            what.append("turn it back ON")
        if "size_factor" in v:
            what.append(f"full size ({money(stake)} a bet, now {money(stake * v['size_factor'])})")
        if "max_price" in v:
            what.append(f"its {100 * effective_cap(cfg, lid, {}):.0f}c cap again (now {100 * v['max_price']:.0f}c)")
        share = 1.0 if v.get("enabled") is False else (1 - v.get("size_factor", 1.0)) if "size_factor" in v else 0.0
        gain = round(s8["net_per_1"] * stake * s8["bets_month"] * share + (r.get("above_cap_usd_month") or 0.0) * (1 - share))
        since = max([x for x in (v.get("since") or {}).values() if x] or [day])
        out.append({
            "id": f"k8-restore-{lid.replace('_', '-')}-{since[5:7]}{since[8:10]}"[:40],
            "question": f"K8 {leg_name(lid)}: {' and '.join(what)}?",
            "why": (f"The weekly re-test cut it on {since}; it has recovered: {pct(s8['net_per_1'])} per $1 over 8 weeks "
                    f"({s8['n']} bets, won {100 * s8['win_rate']:.0f}%), {pct(s4['net_per_1'])} over the last 4, paid "
                    f"{100 * s4.get('avg_price_all', s4['avg_price']):.0f}c on average.")[:240],
            "impact": (f"About {money(gain, True)} a month if the last 8 weeks repeat ({s8['bets_month']:.0f} bets a month at "
                       f"{money(stake)}); $0 changes before your yes."),
            "impact_usd": gain, "usd_month": gain, "options": ["yes", "no", "later"], "status": "open", "source": REPORT_REL,
            "applies": (f"A yes: the PC's next weekly run (or engine/kalshi_adapt --restore {lid}) lifts the re-test's cut on this "
                        "leg, back to what you armed in research/lab/kalshi_clock.json; nothing else changes, no phrase needed"),
            "risk": "It goes back to the size you armed; the kill rules (58%, -$75, 58c) and the -$60 day stop still apply.",
            "recommend": "yes", "recommend_why": "It earned it back on the newest 8 weeks; the weekly re-test cuts it again if it fades.",
            "added": day, "from": "kalshi_adapt", "k8": {"kind": "restore", "leg": lid, "as_of": day}})
    return out


def line(L) -> str:
    ch = L.get("changes") or []
    if ch:
        return "K8 re-test: " + "; ".join(c["short"] for c in ch)[:150]
    n = sum(1 for r in (L.get("legs") or {}).values() if (r.get("w8") or {}).get("n", 0) >= RULES["min_bets_long"])
    held = len(L.get("adapt") or {})
    watch = [f"{LEG_SHORT.get(lid, lid)} paid +{100 * ((r['w4'].get('avg_price_all') or 0) - (r.get('base_price') or 0)):.0f}c"
             for lid, r in (L.get("legs") or {}).items() if "creep (cap already lower)" in (r.get("hits") or [])]
    return (f"K8 re-test: no change ({n} legs tested" + (f", {held} still cut" if held else "") + ")"
            + (f"; watching: {', '.join(watch)} (still wins enough)" if watch else ""))


# ================================================================================================ the owner's yes (restore)
def restores_from_decisions(items, done=()) -> list:
    """[(decision id, leg)] of Decide-card restore items the owner said yes to (status yes / done), not applied yet."""
    out = []
    for it in items or []:
        k = it.get("k8") if isinstance(it, dict) else None
        if not isinstance(k, dict) or k.get("kind") != "restore" or it.get("status") not in ("yes", "done"):
            continue
        if str(it.get("id")) in done or k.get("leg") not in KC.LEG or not str(it.get("id", "")).startswith("k8-restore-"):
            continue
        out.append((str(it["id"]), k["leg"]))
    return out


def adapt_doc(state_dir=None) -> dict:
    d = KL._jread(KC.adapt_path(state_dir), {}) or {}
    return d if isinstance(d, dict) else {}


def restore(lid, state_dir=None, now=None, by="owner") -> str:
    """The owner's yes on the PC: lift every re-test cut on one leg (back to what he armed). -> plain words."""
    if lid not in KC.LEG:
        return f"unknown leg {lid!r}: one of " + ", ".join(KC.LEG)
    now = time.time() if now is None else now
    d = adapt_doc(state_dir)
    day = KL.et_day(now)
    rs = d.setdefault("restored", {})
    rs[lid] = day
    legs = clean_adapt(d)
    legs.pop(lid, None)
    d["legs"] = legs
    d.setdefault("changes", []).append({"day": day, "leg": lid, "what": "restored", "text": f"{leg_name(lid)}: back to what you armed ({by})",
                                        "short": f"{LEG_SHORT.get(lid, lid)} restored"})
    d["changes"] = d["changes"][-CHANGES_KEEP:]
    d["t"] = int(now)
    KL._jwrite(KC.adapt_path(state_dir), d)
    return f"{leg_name(lid)}: back to what you armed (the re-test's cut is lifted)"


# ================================================================================================ the public tape (GET only)
class Public:
    """Kalshi's PUBLIC market data: GET only, these paths only, no key, no auth header, at most one request a second.
    http(url, timeout) -> (status, bytes) is injectable (tests)."""
    BASE = "https://api.elections.kalshi.com/trade-api/v2"
    _PATHS = ("/historical/cutoff", "/markets", "/markets/trades", "/historical/trades", "/markets/candlesticks")
    _ONE = re.compile(r"/(historical/)?markets/[A-Z0-9][A-Z0-9._-]{2,80}")

    def __init__(self, http=None, sleep=time.sleep, gap=GAP_S, budget=None, timeout=20.0, deadline=None):
        self.http, self.sleep, self.gap, self.budget, self.timeout = http or self._http, sleep, max(1.0, float(gap)), budget, timeout
        self.deadline = deadline                     # wall-clock epoch: no request after it (the PC stops before a K8 window)
        self.calls, self.errors, self._last = 0, 0, 0.0

    @staticmethod
    def _http(url, timeout):
        req = urllib.request.Request(url, headers={"User-Agent": "olympus-k8-adapt/1", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, b""

    @classmethod
    def allowed(cls, method, path) -> bool:
        p = str(path or "")
        if str(method).upper() != "GET" or any(x in p for x in ("?", "#", "..", "//", "\\", " ")):
            return False
        return p in cls._PATHS or bool(cls._ONE.fullmatch(p))

    def get(self, path, params=None):
        """The JSON answer, or None (404 / refused / no answer / out of budget). Never raises."""
        if not self.allowed("GET", path):
            return None
        if self.budget is not None and self.calls >= self.budget:
            return None
        if self.deadline is not None and time.time() > self.deadline:
            return None
        if self.errors >= 6:                         # Kalshi / the network is down: stop asking (the next run tries again)
            return None
        url = self.BASE + path + (("?" + urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})) if params else "")
        for attempt in range(3):
            w = self._last + self.gap - time.monotonic()
            if w > 0:
                self.sleep(w)
            self._last = time.monotonic()
            self.calls += 1
            try:
                status, raw = self.http(url, self.timeout)
            except Exception:  # noqa: BLE001
                status, raw = 0, b""
            if status == 200:
                try:
                    j = json.loads((raw or b"{}").decode("utf-8", "replace"))
                    return j if isinstance(j, dict) else None
                except ValueError:
                    self.errors += 1                 # not Kalshi's JSON (a captive portal, a proxy page): counts as a failure
                    return None
            if status in (400, 401, 403, 404):
                return None
            self.errors += 1
            self.sleep(2.0 * (attempt + 1))
        return None


_ISO = re.compile(r"(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d):(\d\d)(\.\d+)?")


def _ts(x):
    """unix seconds from a number or an ISO time (Z / fractions of any length; UTC)."""
    if x is None or x == "":
        return None
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(x)
    except ValueError:
        pass
    m = _ISO.match(str(x).strip())
    if not m:
        return None
    y, mo, d, h, mi, se = (int(g) for g in m.groups()[:6])
    return dt.datetime(y, mo, d, h, mi, se, tzinfo=dt.timezone.utc).timestamp() + (float(m.group(7)) if m.group(7) else 0.0)


def compact_trades(trades, open_t) -> list:
    """Kalshi trade rows -> [[seconds after the open, taker side, yes price $, contracts], ...] (sorted)."""
    out = []
    for x in trades or []:
        if not isinstance(x, dict):
            continue
        t = _ts(x.get("created_time"))
        yp = _f(x.get("yes_price_dollars"))
        if yp is None and _f(x.get("yes_price")) is not None:
            yp = _f(x.get("yes_price")) / (100.0 if _f(x.get("yes_price")) > 1 else 1.0)
        c = _f(x.get("count_fp"), _f(x.get("count")))
        if t is None or yp is None or c is None or x.get("taker_side") not in ("yes", "no"):
            continue
        out.append([round(t - open_t, 2), x["taker_side"], round(yp, 4), c])
    return sorted(out)


def read_tape(path) -> dict:
    out = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get("t") and r.get("res") in ("yes", "no"):
                    out[r["t"]] = r
    except OSError:
        pass
    return out


def prune_tape(path, keep_from, max_bytes=3_000_000) -> int:
    """Keep the PC's tape cache small: once over max_bytes, rewrite it with the markets of keep_from onwards. -> rows dropped."""
    try:
        if os.path.getsize(path) <= max_bytes:
            return 0
    except OSError:
        return 0
    rows = read_tape(path)
    cut = KC.et_epoch(_day(keep_from), 0, 0)
    keep = [r for r in rows.values() if (_f(r.get("o"), 0.0) or 0.0) >= cut]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in sorted(keep, key=lambda r: r.get("o") or 0):
            fh.write(json.dumps(r, separators=(",", ":")) + "\n")
    os.replace(tmp, path)
    return len(rows) - len(keep)


def wanted_tickers(start, end, cfg) -> list:
    out = []
    for d in days_between(start, end):
        if d.weekday() >= 5:
            continue
        for lid in cfg["paper_legs"]:
            leg = KC.LEG[lid]
            if not KC.skipped(leg, d):
                o = KC.leg_open(leg, d)
                out.append((KC.ticker(leg["series"], o), o))
    return sorted(set(out), key=lambda x: x[1])


def fetch_tape(pub, path, start, end, cfg, now=None, have=None) -> dict:
    """Fill the tape cache (jsonl at `path`, one row per market: t, o, res, tr) with the leg markets of [start, end] that settled
    and are missing. -> {"added", "calls", "missing"}. Never raises."""
    now = time.time() if now is None else now
    have = read_tape(path) if have is None else have
    todo = [(t, o) for t, o in wanted_tickers(start, end, cfg) if t not in have and o + 960 < now]
    if not todo:
        return {"added": 0, "calls": pub.calls, "missing": 0, "todo": 0}
    cut = pub.get("/historical/cutoff") or {}
    m_cut = _ts(cut.get("market_settled_ts")) or 0.0
    t_cut = _ts(cut.get("trades_created_ts")) or 0.0
    added, missing = 0, 0
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    for tk, o in todo:
        if pub.budget is not None and pub.calls >= pub.budget:
            missing += 1
            continue
        if pub.deadline is not None and time.time() > pub.deadline:
            missing += 1
            continue
        a, b = ("/historical/markets/", "/markets/") if o + 900 < m_cut else ("/markets/", "/historical/markets/")
        j = pub.get(a + tk)
        if j is None:
            j = pub.get(b + tk)
        m = (j or {}).get("market") if isinstance((j or {}).get("market"), dict) else {}
        if m.get("result") not in ("yes", "no"):
            missing += 1
            continue
        q = {"ticker": tk, "min_ts": int(o) - 1, "max_ts": int(o) + 45, "limit": 1000}
        a, b = ("/historical/trades", "/markets/trades") if o < t_cut else ("/markets/trades", "/historical/trades")
        j = pub.get(a, q)
        if j is None:
            j = pub.get(b, q)
        if j is None:
            missing += 1
            continue
        tr = j.get("trades") or []
        row = {"t": tk, "o": o, "res": m["result"], "tr": compact_trades(tr, o)}
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, separators=(",", ":")) + "\n")
            have[tk] = row
            added += 1
        except OSError:
            missing += 1
    return {"added": added, "calls": pub.calls, "missing": missing, "todo": len(todo)}


# ================================================================================================ the PC's weekly run
def as_of_day(now) -> dt.date:
    """The newest ET weekday whose K8 windows have all closed (from 17:05 ET: the data pipe's nightly run), else the weekday
    before. A market Kalshi has not settled yet is simply missing that week (the next run takes it)."""
    e = KL.et_dt(now)
    d = e.date()
    if d.weekday() >= 5 or (e.hour, e.minute) < (17, 5):
        d -= dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def quiet_ok(now, cfg) -> tuple:
    """(ok, why): not within 20 minutes before (or during) a K8 window today."""
    for t, ids in KC.windows(KL.et_dt(now).date(), cfg):
        if t - PC_QUIET_S <= now <= t + 60:
            return False, f"a K8 window opens at {KL.et_dt(t):%H:%M} ET"
    return True, ""


def state_path(state_dir=None) -> str:
    return os.path.join(KL.paths(state_dir)["dir"], "adapt_state.json")


def pc_weekly(state_dir=None, root=None, now=None, env=None, force=False, http=None, sleep=time.sleep, budget=PC_BUDGET,
              fetch=True) -> dict:
    """The PC's weekly re-test (the nightly child calls it; on demand: force=True). Writes data/kalshi_live/clock_adapt.json
    (only ever tighter), returns {"ok", "ran", "line", "changes", "why"}. Never raises."""
    try:
        return _pc_weekly(state_dir, root or ROOT, time.time() if now is None else float(now), os.environ if env is None else env,
                          force, http, sleep, budget, fetch)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "ran": False, "line": None, "changes": [], "why": f"{e.__class__.__name__}: {str(e)[:120]}"}


def _pc_weekly(state_dir, root, now, env, force, http, sleep, budget, fetch) -> dict:
    if str(env.get("LE_KADAPT", "")).strip() == "0":
        return {"ok": True, "ran": False, "line": None, "changes": [], "why": "off on this PC (LE_KADAPT=0)"}
    cfg, probs = KC.load_config(os.path.join(root, "research", "lab", "kalshi_clock.json"), state_dir)
    sp = state_path(state_dir)
    st = KL._jread(sp, {}) or {}
    if not force and now - (_f(st.get("t"), 0.0) or 0.0) < PC_EVERY_S:
        return {"ok": True, "ran": False, "line": None, "changes": [], "why": f"ran on {st.get('as_of')}: weekly"}
    ok, why = quiet_ok(now, cfg)
    if not ok:
        return {"ok": True, "ran": False, "line": None, "changes": [], "why": why}
    as_of = as_of_day(now)
    W = windows_of(as_of)
    tape_file = os.path.join(KL.paths(state_dir)["dir"], "adapt", "tape.jsonl")
    tape = read_tape(tape_file)
    got = {"added": 0, "calls": 0}
    if fetch and str(env.get("LE_KADAPT_NET", "")).strip() != "0":
        nxt, _ = KC.next_window(now, cfg)
        dl = (time.time() + (nxt - now) - PC_QUIET_S) if nxt else None   # stop asking 20 minutes before the next K8 window
        got = fetch_tape(Public(http=http, sleep=sleep, budget=budget, deadline=dl), tape_file, W["long"][0], as_of, cfg, now=now, have=tape)
    prune_tape(tape_file, W["long"][0] - dt.timedelta(days=14))
    d = adapt_doc(state_dir)
    restored = dict(d.get("restored") or {})
    done = set(d.get("restores_applied") or [])
    dec = _jread(os.path.join(root, "tools", "web_public", "business", "decisions.json"), {}) or {}
    applied = []
    for did, lid in restores_from_decisions(dec.get("items") if isinstance(dec, dict) else [], done):
        restored[lid] = KL.et_day(now)
        done.add(did)
        applied.append(lid)
    cloud = _jread(os.path.join(root, "research", "lab", "kalshi_adapt.json"), {}) or {}
    cloud_adapt = clean_adapt({"legs": cloud.get("adapt")}) if isinstance(cloud, dict) else {}
    prev = merge(clean_adapt(d), cloud_adapt)
    L = evaluate(leg_bets(tape, W["long"][0], as_of, cfg), as_of, prev={"legs": prev}, cfg=cfg, restored=restored, src="pc")
    for lid in applied:
        L["changes"].insert(0, {"day": str(as_of), "leg": lid, "what": "restored", "text": f"{leg_name(lid)}: back to what you armed (your yes)",
                                "short": f"{LEG_SHORT.get(lid, lid)} restored (your yes)"})
    L["line"] = line(L)
    out = {"v": VERSION, "kind": "k8-adapt", "t": int(now), "as_of": str(as_of), "src": "pc" + ("+cloud" if cloud_adapt else ""),
           "legs": {lid: {k: v[k] for k in ("enabled", "size_factor", "max_price", "why", "since") if k in v} for lid, v in L["adapt"].items()},
           "changes": ((d.get("changes") or []) + L["changes"])[-CHANGES_KEEP:], "proposals": L["proposals"], "line": L["line"],
           "restored": restored, "restores_applied": sorted(done)[-40:],
           "tested": {lid: {"w8": {k: r["w8"].get(k) for k in ("n", "win_rate", "net_per_1", "avg_price")},
                            "w4": {k: r["w4"].get(k) for k in ("n", "win_rate", "net_per_1", "avg_price")}} for lid, r in L["legs"].items()},
           "rule": "Only ever tighter: half size / OFF / a lower max price. Back up only with your yes (the Decide card)."}
    KL._jwrite(KC.adapt_path(state_dir), out)
    short = got.get("todo", 0) >= 10 and got.get("missing", 0) * 2 > got.get("todo", 0)    # the tape mostly did not come: retry tomorrow
    KL._jwrite(sp, {"t": int(now - PC_EVERY_S + 20 * 3600) if short else int(now), "as_of": str(as_of), "calls": got.get("calls"),
                    "added": got.get("added"), "missing": got.get("missing"), "line": L["line"], "problems": probs[:3]})
    return {"ok": True, "ran": True, "line": L["line"], "changes": L["changes"], "proposals": L["proposals"], "why": "",
            "calls": got.get("calls"), "as_of": str(as_of)}


def report_lines(state_dir=None) -> list:
    d = adapt_doc(state_dir)
    if not d:
        return ["K8 re-test: not run on this PC yet (no data/kalshi_live/clock_adapt.json): every leg as armed"]
    out = [f"K8 re-test {d.get('as_of')}: {d.get('line')}"]
    for lid in KC.LEG:
        v = (d.get("legs") or {}).get(lid) or {}
        t = (d.get("tested") or {}).get(lid) or {}
        cut = ", ".join(x for x in ("OFF" if v.get("enabled") is False else "", f"x{v['size_factor']:g} size" if "size_factor" in v else "",
                                    f"max {100 * v['max_price']:.0f}c" if "max_price" in v else "") if x) or "as armed"
        w8 = t.get("w8") or {}
        out.append(f"  {leg_name(lid):<28} {cut:<22} 8 weeks: {w8.get('n') or 0} bets, {pct(w8.get('net_per_1'))} per $1")
    for p in d.get("proposals") or []:
        out.append(f"  [decide] {p.get('question')}")
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.kalshi_adapt", description="K8 weekly re-test on the PC (may only shrink a leg)")
    ap.add_argument("--report", action="store_true", help="what clock_adapt.json says now")
    ap.add_argument("--restore", default=None, help="the owner's yes: lift the re-test's cut on this leg")
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args(argv)
    if a.restore:
        print(restore(a.restore))
        return 0
    if a.report:
        print("\n".join(report_lines()))
        return 0
    r = pc_weekly(force=True, fetch=not a.no_fetch)
    print(r.get("line") or r.get("why"))
    for c in r.get("changes") or []:
        print("  " + c["text"])
    for p in r.get("proposals") or []:
        print("  [decide] " + p["question"])
    print("\n".join(report_lines()[1:]))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
