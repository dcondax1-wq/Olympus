"""KALSHI CLOCK (K8, night-klive 2026-11-19; owner: "Let's put it on right now for Kalshi starting 15$ a bet. See how we do.").

The strategy (research/lab/kalshi_candidates/K8.json, research/writeups/kalshi-metals-2026-11-19.md): Kalshi's 15-minute gold /
silver "up or down?" markets. 20 seconds after a window opens, buy the side the clock favours at the best ask, flat $15, hold to
the settle 15 minutes later. US weekdays (ET, synced clock):
  05:15-05:30  gold DOWN                  (London 10:15-10:30, the quarter hour before the LBMA gold auction; 06:15 ET Mar 15-26, 2027)
  16:45-17:00  gold UP,   silver UP        (the last quarter hour before the CME close)
  paper only:  silver DOWN 05:15-05:30 (too thin for $15 at +20 s, red team) and silver DOWN 16:00-16:15 (fading)
Market ticker = SERIES-YYMONDDHHMM-MM of the window's close, e.g. KXGOLD15M-26NOV190530-30.

PAPER (always on, public data, no key): at every window's +20 s it records ticker, side, best ask, contracts, cost; after the
settle the result and $ (fee in). Ledger data/kalshi_live/clock_paper.json. One phone push a day (the day summary).
LIVE (OFF by default): the SAME code path, then one real order per leg, only when the owner armed it with the typed phrase
(engine/kalshi_live.PHRASE, at the PC: KALSHI_LIVE.bat; on the phone: the private Tailscale page
https://<pc>.<tailnet>.ts.net:8444/kalshi-live/, engine/kalshi_web.py + engine/phone_link.py; :443 is the owner's old Jarvis app). The order: limit at the best ask, good till +40 s after the open (then Kalshi cancels the rest), never a
market order. Checked in code before EVERY order (check_order): armed, kill switch, phone pause, the window's 10-35 s slot, ask
<= the price cap (70c), contracts x price <= $15, at most 6 bets a day, one bet per market, today's worst case (settled $ - every
open bet) never below -$60, cash on Kalshi >= the bet, prices <= 10 s old, market open, the kill rule (after 60 live bets, under
55% won = OFF + alert), 3 errors in a row = OFF + alert, Kalshi refusing the key (401) / the order API (410) = OFF + alert.
Ledger data/kalshi_live/clock_live.json; pushes: one per window when orders go in, one per window with the results, one day
summary, any stop at once (about 5 a day, inside ntfy's budget).

Clock: the PC's clock is checked against Kalshi's own (the HTTP Date header) every 30 min; entries and signatures use the
corrected time. It never touches the futures bot, NinjaTrader or server.py's trading.

  python -X utf8 -m engine.kalshi_live --clock-loop     the loop (the PC starts it: KALSHI_LIVE.bat, the phone page, maybe_run)
  python -X utf8 -m engine.kalshi_live --clock-report   the paper + live results per leg, in plain words
Tests: python -X utf8 -m tests.test_kalshi_clock
"""
from __future__ import annotations

import datetime as dt
import email.utils
import json
import math
import os
import secrets
import sys
import time
import urllib.request

from engine import kalshi_live as KL

CFG_PATH = os.path.join(KL.ROOT, "research", "lab", "kalshi_clock.json")
MON = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
LEGS = (   # id, series, window open (local time of tz), side bought (yes = UP, no = DOWN), plain name, holiday list that skips it
    # the morning legs follow LONDON 10:15-10:30 (the LBMA gold auction is 10:30 London): 05:15-05:30 ET most of the year,
    # 06:15-06:30 ET while the US is already on summer time and the UK not yet (Mar 15-26, 2027): zoneinfo does it
    {"id": "gold_0530_down", "series": "KXGOLD15M", "tz": "London", "open": (10, 15), "side": "no", "skip": "uk",
     "name": "gold DOWN 05:15-05:30 ET"},
    {"id": "silver_0530_down", "series": "KXSILVER15M", "tz": "London", "open": (10, 15), "side": "no", "skip": "uk",
     "name": "silver DOWN 05:15-05:30 ET"},
    {"id": "silver_1615_down", "series": "KXSILVER15M", "tz": "ET", "open": (16, 0), "side": "no", "skip": "cme",
     "name": "silver DOWN 16:00-16:15 ET"},
    {"id": "gold_1700_up", "series": "KXGOLD15M", "tz": "ET", "open": (16, 45), "side": "yes", "skip": "cme", "name": "gold UP 16:45-17:00 ET"},
    {"id": "silver_1700_up", "series": "KXSILVER15M", "tz": "ET", "open": (16, 45), "side": "yes", "skip": "cme",
     "name": "silver UP 16:45-17:00 ET"},
)
# red team 2026-11-19: no LBMA auction on UK bank holidays (the morning legs skip); CME holidays / early closes (the evening legs skip)
UK_SKIP = {"2026-12-25", "2026-12-28", "2027-01-01", "2027-03-26", "2027-03-29"}
CME_SKIP = {"2026-11-26", "2026-11-27", "2026-12-24", "2026-12-25", "2027-01-01", "2027-03-26"}
STAKES = (1.0, 2.5, 5.0, 8.0, 10.0, 15.0)   # the bet sizes the phone page offers (the bankroll rule marks the one that fits)
# THE BANKROLL RULE (night-kalshi8 2026-11-20, owner: "I have $55 and I'm not adding anymore for a while";
# research/kalshi_k8_monday/size55.py): a quarter of Kelly at a planning win rate 10 points under the friend's months
# (63% vs 73%, price + fee 53.5c: full Kelly 20%) = about 4.5% of the bankroll a bet; a WEEK stop of 25% of the bankroll
# (worst case: settled $ this week + every open bet, before every order) so a bad week can never lose more than that.
BANKROLL = {"bet_share": 0.045, "day_share": 0.15, "week_share": 0.25, "dd_share": 0.30, "min_stake": 1.0, "step": 0.5}
RED_TEAM = ("Red team: paper first (about 4 weeks). Live with $55: $2.50 a bet (4 contracts), a bad week can lose at most "
            "25% ($13.75); OFF at -$16.50 from the peak.")
LEG = {x["id"]: x for x in LEGS}
DEFAULT = {"version": 1, "strategy": "clock", "source": "research/lab/kalshi_candidates/K8.json", "stake_usd": 2.5, "price_cap": 0.70,
           "entry_delay_s": 20, "expire_after_s": 40, "max_bets_per_day": 3, "daily_loss_stop_usd": 8.0, "week_loss_stop_usd": 13.75,
           "bankroll_usd": 55.0,
           "kill_after_bets": 60, "kill_min_win_rate": 0.58, "kill_drawdown_usd": 16.5, "min_fill_share": 0.5,
           "kill_avg_price_bets": 30, "kill_avg_price": 0.58,
           # red team 2026-11-19 final: silver 05:15 is too thin for $15 at +20 s (36% of days fill by 30 s): paper only
           "live_legs": ["gold_0530_down", "gold_1700_up", "silver_1700_up"],
           "paper_legs": [x["id"] for x in LEGS]}
HARD = {"stake_usd": 15.0, "price_cap": 0.80, "max_bets_per_day": 8, "daily_loss_stop_usd": 100.0, "week_loss_stop_usd": 150.0}
COID = "olyc-"
SLOT = (10, 45)                 # an order only between open + 10 s and open + 45 s
TRIES = (0, 10, 20)             # seconds after the entry time: the book is read again when it cannot fill half the bet yet
BOOK_MAX_AGE_S = 10
ERR_STREAK = 3
SETTLE_AFTER_S = 15 * 60 + 40
SETTLE_RETRY_S = 60
SETTLE_GIVE_UP_S = 6 * 3600
OFFSET_EVERY_S = 1800
PUSH_DAY_MAX = 12
HEARTBEAT_S = 30
TAKER_FEE = 0.07
PLAIN = {"KILL": "the kill switch is on", "NOT_ARMED": "not armed (paper only)", "PAUSED": "paused from the phone or the PC",
         "STOPPED": "stopped: type the phrase again", "KILL_RULE": "the kill rule (under 58% won after 60 live bets, too far below the peak, or over 58c paid on the last 30)",
         "SLOT": "outside the 10-45 s after the open", "PRICE": "the ask is above the price cap", "STAKE": "over the $ per bet",
         "BETS_DAY": "the day's bets are used", "ONE_BET": "already a bet on this market", "DAY_STOP": "today's loss stop",
         "WEEK_STOP": "this week's loss stop (25% of the bankroll)", "DD_STOP": "the drawdown stop (30% of the bankroll from the peak)",
         "BALANCE": "not enough cash on Kalshi for the bet", "STALE_BOOK": "the prices are too old", "MARKET": "the market is not open",
         "BAD_ORDER": "the order is not valid", "ERROR": "the check hit an error (blocked to be safe)"}


# ================================================================================================ config + calendar (pure)
def stake_path(state_dir=None) -> str:
    return os.path.join(KL.paths(state_dir)["dir"], "clock_stake.json")


def load_config(path=None, state_dir=None) -> tuple:
    """(config, problems): the code defaults + research/lab/kalshi_clock.json + the bet size the owner picked on the phone page
    (data/kalshi_live/clock_stake.json: $5 / $8 / $10 / $15). Any value above the hard ceilings is a problem."""
    raw = KL._jread(path or CFG_PATH, None)
    cfg, probs = json.loads(json.dumps(DEFAULT)), []
    if isinstance(raw, dict):
        for k in ("stake_usd", "price_cap", "max_bets_per_day", "daily_loss_stop_usd", "week_loss_stop_usd", "bankroll_usd",
                  "entry_delay_s", "expire_after_s", "kill_after_bets", "kill_min_win_rate", "kill_drawdown_usd", "min_fill_share", "kill_avg_price_bets", "kill_avg_price"):
            if k in raw:
                v = KL._f(raw.get(k))
                if v is None or v <= 0:
                    probs.append(f"{k} must be a number above 0")
                    continue
                cfg[k] = v
        lp = raw.get("leg_price_cap")
        if isinstance(lp, dict):
            bad = [k for k, v in lp.items() if k not in LEG or not (0.02 <= (KL._f(v) or 0) <= HARD["price_cap"])]
            if bad:
                probs.append(f"leg_price_cap: bad legs or prices {bad[:3]}")
            else:
                cfg["leg_price_cap"] = {k: round(KL._f(v), 4) for k, v in lp.items()}
        for k in ("live_legs", "paper_legs"):
            if k in raw:
                bad = [x for x in (raw.get(k) or []) if x not in LEG]
                if bad or not isinstance(raw.get(k), list):
                    probs.append(f"{k}: unknown legs {bad[:3]}")
                else:
                    cfg[k] = list(raw[k])
    elif raw is not None:
        probs.append("research/lab/kalshi_clock.json is not a JSON object")
    pick = KL._f((KL._jread(stake_path(state_dir), {}) or {}).get("stake"))
    if pick is not None:
        if pick in STAKES:
            cfg["stake_usd"] = pick
        else:
            probs.append(f"the bet size {pick:g} is not one of " + " / ".join(f"${x:g}" for x in STAKES))
    for k, hi in HARD.items():
        if cfg[k] > hi:
            probs.append(f"{k} = {cfg[k]:g} is above the code's ceiling {hi:g}")
    if not 0.02 <= cfg["price_cap"] <= HARD["price_cap"]:
        probs.append("price_cap must be 0.02-0.80")
    if not 5 <= cfg["entry_delay_s"] <= 30 or not cfg["entry_delay_s"] < cfg["expire_after_s"] <= 60:
        probs.append("entry_delay_s 5-30 and expire_after_s above it, at most 60")
    cfg["max_bets_per_day"] = int(cfg["max_bets_per_day"])
    cfg["kill_after_bets"] = int(cfg["kill_after_bets"])
    cfg["kill_avg_price_bets"] = int(cfg["kill_avg_price_bets"])
    cfg["paper_legs"] = sorted(set(cfg["paper_legs"]) | set(cfg["live_legs"]), key=lambda x: [y["id"] for y in LEGS].index(x))
    return cfg, probs


def bankroll_rule(bankroll) -> dict:
    """The sizing + stops for a bankroll of `bankroll` $ (BANKROLL above; $55 -> $2.50 a bet, day stop $8, week stop $13.75,
    OFF at -$16.50 from the peak, 3 bets a day). Pure; the phone page shows it and research/lab/kalshi_clock.json holds the values."""
    b = max(0.0, KL._f(bankroll, 0.0) or 0.0)
    R = BANKROLL
    stake = max(R["min_stake"], round(b * R["bet_share"] / R["step"]) * R["step"])
    stake = min(stake, HARD["stake_usd"])
    return {"bankroll_usd": round(b, 2), "stake_usd": stake, "max_bets_per_day": 3,
            "daily_loss_stop_usd": round(b * R["day_share"]), "week_loss_stop_usd": round(b * R["week_share"], 2),
            "kill_drawdown_usd": round(b * R["dd_share"], 2), "contracts_at_52c": int(math.floor(stake / 0.52 + 1e-9))}


def fits(stake, balance) -> bool:
    """True when `stake` is at most what the bankroll rule gives for `balance` (unknown balance = True)."""
    b = KL._f(balance)
    return True if b is None else stake <= bankroll_rule(b)["stake_usd"] + 1e-9


try:
    from zoneinfo import ZoneInfo
    _LON = ZoneInfo("Europe/London")
except Exception:  # noqa: BLE001
    _LON = None


def london_epoch(day: dt.date, hh: int, mm: int) -> float:
    if _LON is not None:
        return dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=_LON).timestamp()

    def last_sunday(month):
        d = dt.date(day.year, month, 31)
        return d - dt.timedelta(days=(d.weekday() + 1) % 7)
    summer = last_sunday(3) <= day < last_sunday(10)          # BST from the last Sunday of March to the last Sunday of October
    return dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=dt.timezone.utc).timestamp() - (3600 if summer else 0)


def leg_open(leg, day: dt.date) -> float:
    h, m = leg["open"]
    return london_epoch(day, h, m) if leg["tz"] == "London" else et_epoch(day, h, m)


def et_epoch(day: dt.date, hh: int, mm: int, ss: int = 0) -> float:
    if KL._ET is not None:
        return dt.datetime(day.year, day.month, day.day, hh, mm, ss, tzinfo=KL._ET).timestamp()
    noon = dt.datetime(day.year, day.month, day.day, 12, tzinfo=dt.timezone.utc).timestamp()
    return dt.datetime(day.year, day.month, day.day, hh, mm, ss, tzinfo=dt.timezone.utc).timestamp() - KL._et_offset(noon)


def ticker(series: str, open_t: float) -> str:
    c = KL.et_dt(open_t + 900)
    return f"{series}-{c:%y}{MON[c.month - 1]}{c:%d}{c:%H%M}-{c:%M}"


def skipped(leg, day: dt.date) -> bool:
    iso_ = day.isoformat()
    return iso_ in (UK_SKIP if leg["skip"] == "uk" else CME_SKIP)


def week_of(day) -> str:
    """The Monday (ISO date) of the ET week of `day` (a date or 'YYYY-MM-DD'): the week stop counts Monday-Friday."""
    d = day if isinstance(day, dt.date) else dt.date.fromisoformat(str(day)[:10])
    return (d - dt.timedelta(days=d.weekday())).isoformat()


def windows(day: dt.date, cfg) -> list:
    """[(open epoch, [leg ids])] of one ET day, weekdays only, minus the holiday skips; the legs paper OR live records."""
    if day.weekday() >= 5:
        return []
    by = {}
    for lid in cfg["paper_legs"]:
        if not skipped(LEG[lid], day):
            by.setdefault(leg_open(LEG[lid], day), []).append(lid)
    return sorted(by.items())


def next_window(now: float, cfg) -> tuple:
    d = KL.et_dt(now).date()
    for add in range(0, 8):
        for t, ids in windows(d + dt.timedelta(days=add), cfg):
            if t + cfg["entry_delay_s"] > now - 1:
                return t, ids
    return None, []


def fee(p, n) -> float:
    return math.ceil(TAKER_FEE * n * p * (1 - p) * 100 - 1e-9) / 100.0


def side_quote(yes, no, side):
    """(best ask, depth at it, ask levels cheapest first) for BUYING `side`: YES is bought from the NO bids (ask = 1 - NO bid),
    NO from the YES bids."""
    other = no if side == "yes" else yes
    lv = [(round(1 - p, 4), q) for p, q in other]            # the other side's bids are best-first, so our asks ascend
    return (lv[0][0], lv[0][1], lv) if lv else (None, 0.0, [])


def walk(levels, stake, cap) -> tuple:
    """Walk the asks (cheapest first) buying whole contracts while the price <= cap and the cost <= stake.
    -> (contracts, cost $, worst price paid). Red team: at $15 the walk averages within 0.2c of the study's entry (p90 +2.1c)."""
    got, cost, worst = 0, 0.0, None
    for p, q in levels:
        if p > cap + 1e-9:
            break
        k = int(min(q, math.floor((stake - cost) / p + 1e-9)))
        if k <= 0:
            break
        got, cost, worst = got + k, cost + k * p, p
        if k < q:
            break                                            # the budget ran out inside this level
    return got, round(cost, 4), worst


def contracts(stake, ask) -> int:
    return int(math.floor(stake / ask + 1e-9)) if ask and ask > 0 else 0


def adapt_path(state_dir=None) -> str:
    return os.path.join(KL.paths(state_dir)["dir"], "clock_adapt.json")


def leg_limits(cfg, lid, state_dir=None) -> dict:
    """What one leg may do now: {enabled, stake, cap}. The ADAPTIVE HOOK: data/kalshi_live/clock_adapt.json (written by the coming
    weekly re-test job) can only SHRINK: {"legs": {"<leg id>": {"enabled": false} | {"size_factor": 0.5} | {"max_price": 0.62}}}.
    It is not part of what the owner armed (shrinking needs no phrase); adding a leg or a bigger bet goes through
    research/lab/kalshi_clock.json, which IS armed (the owner's yes + the phrase)."""
    out = {"enabled": lid in cfg["live_legs"], "stake": cfg["stake_usd"], "cap": min(cfg["price_cap"], KL._f((cfg.get("leg_price_cap") or {}).get(lid), 9.0))}
    ad = ((KL._jread(adapt_path(state_dir), {}) or {}).get("legs") or {}).get(lid) or {}
    if ad.get("enabled") is False:
        out["enabled"], out["why"] = False, str(ad.get("why") or "turned off by the weekly re-test")[:80]
    f = KL._f(ad.get("size_factor"))
    if f is not None and 0 <= f < 1:
        out["stake"] = round(out["stake"] * f, 2)
    mp = KL._f(ad.get("max_price"))
    if mp is not None and 0.02 <= mp < out["cap"]:
        out["cap"] = mp
    return out


# ================================================================================================ the gate before EVERY live order (pure)
def check_order(o, v) -> tuple:
    """(True, 'OK', '') or (False, CODE, plain words). o: {ticker, side, count, cost, worst, ask, open_t, book_t, market, stake, cap}."""
    def no(code, words=None):
        return False, code, words or PLAIN.get(code, code)
    try:
        cfg, now = v["cfg"], v["now"]
        if v.get("kill"):
            return no("KILL")
        if not v.get("live"):
            return no("NOT_ARMED", v.get("why") or None)
        if v.get("stopped"):
            return no("STOPPED")
        if v.get("killed"):
            return no("KILL_RULE", v.get("kill_why") or None)
        if v.get("paused"):
            return no("PAUSED")
        n, worst, side, cost = o.get("count"), KL._f(o.get("worst")), o.get("side"), KL._f(o.get("cost"))
        if side not in ("yes", "no") or not isinstance(n, int) or isinstance(n, bool) or n < 1 or worst is None or cost is None \
                or not KL.TICKER_RX.fullmatch(str(o.get("ticker") or "")):
            return no("BAD_ORDER")
        if not (o.get("open_t", 0) + SLOT[0] <= now <= o.get("open_t", 0) + SLOT[1]):
            return no("SLOT")
        cap = min(KL._f(o.get("cap"), cfg["price_cap"]), cfg["price_cap"], HARD["price_cap"])
        if not (0.02 - 1e-9 <= worst <= cap + 1e-9):
            return no("PRICE", f"the price {worst * 100:.0f}c is above the {cap * 100:.0f}c cap")
        stake = min(KL._f(o.get("stake"), cfg["stake_usd"]), cfg["stake_usd"], HARD["stake_usd"])
        if cost > stake + 1e-9 or cost > n * worst + 1e-9:
            return no("STAKE", f"{n} contracts = {KL.money(cost)}, over the {KL.money(stake)} a bet")
        if int(v.get("bets_today") or 0) >= min(cfg["max_bets_per_day"], HARD["max_bets_per_day"]):
            return no("BETS_DAY", f"{v.get('bets_today')} bets today (max {cfg['max_bets_per_day']})")
        if o["ticker"] in (v.get("tickers_today") or ()):
            return no("ONE_BET")
        f = fee(cost / n, n)
        worst_day = KL._f(v.get("day_worst"), 0.0) - cost - f
        if worst_day < -min(cfg["daily_loss_stop_usd"], HARD["daily_loss_stop_usd"]) - 1e-9:
            return no("DAY_STOP", f"today could reach {KL.money(worst_day)} (stop -{KL.money(cfg['daily_loss_stop_usd'])})")
        dd_cap = KL._f(cfg.get("kill_drawdown_usd"))
        if dd_cap and KL._f(v.get("dd_now")) is not None:
            dd_worst = KL._f(v.get("dd_now"), 0.0) + KL._f(v.get("open_all"), 0.0) + cost + f
            if dd_worst > dd_cap + 1e-9:
                return no("DD_STOP", f"this bet could take the record {KL.money(dd_worst)} below its peak (OFF at -{KL.money(dd_cap)})")
        wk_stop = min(KL._f(cfg.get("week_loss_stop_usd"), HARD["week_loss_stop_usd"]), HARD["week_loss_stop_usd"])
        worst_week = KL._f(v.get("week_worst"), 0.0) - cost - f
        if worst_week < -wk_stop - 1e-9:
            return no("WEEK_STOP", f"this week could reach {KL.money(worst_week)} (stop -{KL.money(wk_stop)})")
        if cost + f > KL._f(v.get("balance"), 0.0) + 1e-9:
            return no("BALANCE", f"cash on Kalshi {KL.money(v.get('balance'))} is below the bet {KL.money(cost + f)}")
        if now - KL._f(o.get("book_t"), 0.0) > BOOK_MAX_AGE_S:
            return no("STALE_BOOK")
        m = o.get("market") or {}
        if m.get("status") != "active" or (m.get("close_ts") or 0) <= now + 60:
            return no("MARKET")
        return True, "OK", ""
    except Exception as e:  # noqa: BLE001
        return no("ERROR", f"the check hit an error ({e.__class__.__name__}): blocked to be safe")


# ================================================================================================ ledgers + stats
def paths(state_dir=None) -> dict:
    P = KL.paths(state_dir)
    j = os.path.join
    P.update({"clock_state": j(P["dir"], "clock_state.json"), "clock_paper": j(P["dir"], "clock_paper.json"),
              "clock_live": j(P["dir"], "clock_live.json"), "clock_lock": j(P["dir"], "clock.lock"),
              "clock_out": j(P["dir"], "clock_loop.log"), "clock_run": j(P["dir"], "clock_run.json"), "clock_off": j(P["dir"], "CLOCK_OFF")})
    return P


def rows(path) -> list:
    d = KL._jread(path, {}) or {}
    return [r for r in (d.get("rows") or []) if isinstance(r, dict)]


def save_rows(path, rs):
    KL._jwrite(path, {"v": 1, "rows": rs[-5000:]})


def stats(rs, day=None) -> dict:
    s = [r for r in rs if r.get("result") in ("won", "lost") and (day is None or r.get("day") == day)]
    w = sum(1 for r in s if r["result"] == "won")
    net = round(sum(KL._f(r.get("pnl"), 0.0) for r in s), 2)
    cost = sum(KL._f(r.get("cost"), 0.0) for r in s)
    return {"n": len(s), "won": w, "rate": (w / len(s)) if s else None, "net": net, "per_dollar": (net / cost) if cost else None,
            "open": len([r for r in rs if r.get("result") is None and r.get("status") == "open" and (day is None or r.get("day") == day)])}


def drawdown(rs) -> float:
    """$ below the peak of the cumulative settled P&L (0 at a new high)."""
    peak = cum = 0.0
    dd = 0.0
    for r in sorted((r for r in rs if r.get("result") in ("won", "lost")), key=lambda r: KL._f(r.get("open_t"), 0.0)):
        cum += KL._f(r.get("pnl"), 0.0)
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return round(peak - cum, 2) if rs else 0.0


def kill_state(state_dir=None, cfg=None) -> tuple:
    """(killed?, words): the kill rules on the LIVE record: under 58% won after 60 bets, or -$75 from the peak."""
    cfg = cfg or load_config(state_dir=state_dir)[0]
    rs = rows(paths(state_dir)["clock_live"])
    s = stats(rs)
    dd = drawdown(rs)
    if s["n"] >= cfg["kill_after_bets"] and (s["rate"] or 0) < cfg["kill_min_win_rate"] - 1e-9:
        return True, f"the kill rule: {s['won']} of {s['n']} live bets won ({100 * s['rate']:.0f}%, under {100 * cfg['kill_min_win_rate']:.0f}%)"
    if dd >= cfg["kill_drawdown_usd"] - 1e-9:
        return True, f"the kill rule: live P&L is {KL.money(-dd)} from its peak (limit -{KL.money(cfg['kill_drawdown_usd'])})"
    paid = [KL._f(r.get("price")) for r in sorted((r for r in rs if r.get("result") in ("won", "lost") and KL._f(r.get("price"))),
                                                  key=lambda r: KL._f(r.get("open_t"), 0.0))][-cfg["kill_avg_price_bets"]:]
    if len(paid) >= cfg["kill_avg_price_bets"] and sum(paid) / len(paid) > cfg["kill_avg_price"] + 1e-9:
        return True, (f"the kill rule: the last {len(paid)} live bets paid {100 * sum(paid) / len(paid):.1f}c on average (limit "
                      f"{100 * cfg['kill_avg_price']:.0f}c: competitors are eating the edge)")
    return False, f"{s['n']} live bets so far" + (f", {100 * s['rate']:.0f}% won" if s["n"] else "") + (f", {KL.money(-dd)} from the peak" if dd else "")


def kill_distances(state_dir=None, cfg=None, now=None) -> dict:
    """How far each stop is, in plain numbers, on the LIVE ledger (or the PAPER one while nothing is live): for the K8 status card.
    {"ledger", "day": {used, stop}, "week": {used, stop}, "drawdown": {used, stop}, "win_rate": {n, of, rate, min},
     "avg_price": {n, of, avg, max}, "last10": [...]}. 'used' = $ lost so far (settled + every open bet, like the order gate)."""
    cfg = cfg or load_config(state_dir=state_dir)[0]
    now = time.time() if now is None else now
    P = paths(state_dir)
    lr = rows(P["clock_live"])
    led, rs = ("live", lr) if lr else ("paper", rows(P["clock_paper"]))
    day = KL.et_day(now)
    wk = week_of(day)

    def worst(sel):
        return round(sum(KL._f(r.get("pnl"), 0.0) for r in sel if r.get("result") in ("won", "lost"))
                     - sum(KL._f(r.get("cost"), 0.0) + KL._f(r.get("fee"), 0.0) for r in sel
                           if r.get("result") is None and r.get("status") in ("sent", "open")), 2)
    d = worst([r for r in rs if r.get("day") == day])
    w = worst([r for r in rs if wk <= str(r.get("day") or "") <= day])
    s = stats(rs)
    paid = [KL._f(r.get("price")) for r in sorted((r for r in rs if r.get("result") in ("won", "lost") and KL._f(r.get("price"))),
                                                  key=lambda r: KL._f(r.get("open_t"), 0.0))][-cfg["kill_avg_price_bets"]:]
    done = [r for r in rs if r.get("result") in ("won", "lost")]
    last = [{"day": r.get("day"), "leg": r.get("leg"), "name": LEG.get(r.get("leg"), {}).get("name", r.get("leg")), "n": r.get("n"),
             "price": r.get("price"), "result": r.get("result"), "pnl": r.get("pnl")}
            for r in sorted(done, key=lambda r: KL._f(r.get("open_t"), 0.0))[-10:]]
    return {"ledger": led, "day": {"used": round(max(0.0, -d), 2), "stop": cfg["daily_loss_stop_usd"]},
            "week": {"used": round(max(0.0, -w), 2), "stop": cfg.get("week_loss_stop_usd") or HARD["week_loss_stop_usd"], "since": wk},
            "drawdown": {"used": drawdown(rs), "stop": cfg["kill_drawdown_usd"]},
            "win_rate": {"n": s["n"], "of": cfg["kill_after_bets"], "rate": s["rate"], "min": cfg["kill_min_win_rate"]},
            "avg_price": {"n": len(paid), "of": cfg["kill_avg_price_bets"], "avg": round(sum(paid) / len(paid), 4) if paid else None,
                          "max": cfg["kill_avg_price"]}, "last10": last, "net": s["net"]}


def card_k8(state_dir=None, cfg=None, now=None) -> dict | None:
    """The K8 block of the PC's public card (engine/kalshi_live.card, the phone's 'K8 status' card), about 130 bytes:
    {m: L (live ledger) | P (paper), nx: next window (epoch), b: bankroll $, s: $ a bet, td: [bets, won, net $] today,
     l: the last 10 results (W / L, oldest first), wk: [$ used, stop] this week, dd: [$ below the peak, kill], wr: [bets, % won],
     lp: 1 while the clock loop runs}. None when K8 has no ledger and no loop. No ticker, no id, no key."""
    try:
        cfg = cfg or load_config(state_dir=state_dir)[0]
        now = time.time() if now is None else now
        P = paths(state_dir)
        alive = loop_alive(P, now)
        if not (alive or os.path.exists(P["clock_paper"]) or os.path.exists(P["clock_live"])):
            return None
        k = kill_distances(state_dir, cfg, now)
        rs = rows(P["clock_live"] if k["ledger"] == "live" else P["clock_paper"])
        td = stats(rs, KL.et_day(now))
        nx, _ = next_window(now, cfg)
        wr = k["win_rate"]
        return {"m": "L" if k["ledger"] == "live" else "P", "nx": int(nx) if nx else None, "b": cfg.get("bankroll_usd"), "s": cfg["stake_usd"],
                "td": [td["n"], td["won"], td["net"]], "l": "".join("W" if r["result"] == "won" else "L" for r in k["last10"]),
                "wk": [k["week"]["used"], k["week"]["stop"]], "dd": [k["drawdown"]["used"], k["drawdown"]["stop"]],
                "wr": [wr["n"], round(100 * wr["rate"]) if wr["rate"] is not None else None], "lp": 1 if alive else 0}
    except Exception:  # noqa: BLE001
        return None


def describe(cfg) -> list:
    live = [LEG[x]["name"] for x in cfg["live_legs"]]
    paper = [LEG[x]["name"] for x in cfg["paper_legs"] if x not in cfg["live_legs"]]
    return [f"K8 clock bets (Kalshi 15-minute gold / silver), US weekdays, {cfg['entry_delay_s']:.0f} s after each window opens:",
            "  live legs: " + "; ".join(live), *(["  paper only: " + "; ".join(paper)] if paper else []),
            f"  {KL.money(cfg['stake_usd'])} a bet at the best ask, skipped when the ask is above {cfg['price_cap'] * 100:.0f}c; at most "
            f"{cfg['max_bets_per_day']} bets a day; stop at -{KL.money(cfg['daily_loss_stop_usd'])} a day and -{KL.money(cfg.get('week_loss_stop_usd') or 0)} a week; OFF after {cfg['kill_after_bets']} "
            f"live bets under {100 * cfg['kill_min_win_rate']:.0f}% won, at -{KL.money(cfg['kill_drawdown_usd'])} from the peak, or "
            f"above {100 * cfg['kill_avg_price']:.0f}c paid on average over the last {cfg['kill_avg_price_bets']}; OFF after {ERR_STREAK} errors in a row.",
            "  " + RED_TEAM]


def report_lines(state_dir=None) -> list:
    P = paths(state_dir)
    out = []
    for name, path in (("PAPER", P["clock_paper"]), ("LIVE", P["clock_live"])):
        rs = rows(path)
        s = stats(rs)
        if not rs:
            out.append(f"{name}: no bets yet")
            continue
        pd = "" if s["per_dollar"] is None else f", {100 * s['per_dollar']:+.0f}% per $1"
        out.append(f"{name}: {s['n']} bets settled, {s['won']} won" + (f" ({100 * s['rate']:.0f}%)" if s["n"] else "")
                   + f", {KL.money(s['net'], True)}{pd}; {s['open']} open")
        for lid in [x["id"] for x in LEGS]:
            t = stats([r for r in rs if r.get("leg") == lid])
            if t["n"] or t["open"]:
                out.append(f"  {LEG[lid]['name']:<26} {t['n']:>3} bets, {t['won']:>3} won, {KL.money(t['net'], True):>9}")
    return out


# the Kalshi data on the PC, one map (night-kalshi8 2026-11-20, "organization"): data/kalshi_live/ = K8 (clock_*, adapt*) + the
# idle maker executor + the phone page; data/kalshi_rewards/ + data/kalshi_k1/ = the two older paper tests. Never the key (that
# lives in %USERPROFILE%\.olympus\kalshi\). Shown by `python -X utf8 -m engine.kalshi_live --clock-report`.
FILES = (
    ("clock_paper.json", "K8 paper bets: every window, every leg (no money)"),
    ("clock_live.json", "K8 real bets (only after the phrase)"),
    ("clock_state.json", "K8 loop heartbeat, clock offset, windows done"),
    ("clock_stake.json", "the bet size picked on the phone page"),
    ("clock_adapt.json", "the weekly re-test's cuts (only ever smaller)"),
    ("adapt_state.json", "when the weekly re-test last ran"),
    ("adapt/tape.jsonl", "public Kalshi tape the re-test reads (kept under 3 MB)"),
    ("arm.json", "the arm record (a hash, never the phrase)"),
    ("KILL", "the kill switch (STOP on the phone writes it)"),
    ("CLOCK_OFF", "K8 loop switched off on this PC"),
    ("log.jsonl", "every event (rotates at 2 MB)"),
    ("web_log.jsonl", "phone page presses (never the key)"),
    ("clock_loop.log", "the loop's own output (rotates at 1 MB)"),
    ("card.json", "the small public card for the phone"),
)


def files_lines(state_dir=None) -> list:
    d = KL.paths(state_dir)["dir"]
    out = [f"Kalshi files on this PC ({d}):"]
    for name, what in FILES:
        fp = os.path.join(d, *name.split("/"))
        try:
            sz = os.path.getsize(fp)
            have = f"{sz / 1024:.0f} KB" if sz >= 1024 else f"{sz} B"
        except OSError:
            have = "-"
        out.append(f"  {name:<18} {have:>8}  {what}")
    return out


# ================================================================================================ the clock check
def http_date(url=KL.API_BASE + "/exchange/status", timeout=10) -> tuple:
    """(local mid time, server Date header) from one public Kalshi GET."""
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": KL.UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = r.headers.get("Date")
    return (t0 + time.time()) / 2, d


def offset_from(local_mid, date_header):
    """Seconds the PC's clock is AHEAD of Kalshi's (the Date header has whole seconds: +0.5 s on average). None = unknown."""
    try:
        srv = email.utils.parsedate_to_datetime(date_header).timestamp() + 0.5
    except Exception:  # noqa: BLE001
        return None
    off = local_mid - srv
    return off if abs(off) < 6 * 3600 else None


# ================================================================================================ the loop
class ClockLoop:
    """Paper always, live when armed. step() does what is due and returns how long to sleep."""

    def __init__(self, state_dir=None, cfg_path=None, env=None, clock=time.time, public_api=None, live_api=None, poster=None,
                 alert_cfg=None, date_fn=None, say=None):
        self.P, self.env, self.raw_clock = paths(state_dir), (os.environ if env is None else env), clock
        self.cfg_path, self.state_dir = cfg_path, state_dir
        self.st = KL._jread(self.P["clock_state"], {}) or {}
        self.st.setdefault("done", [])
        self.st.setdefault("done_cmds", [])
        self.offset = KL._f(self.st.get("offset"), 0.0) or 0.0
        self.date_fn = date_fn
        self.pub = public_api or KL.Api(base=self.env.get("KALSHI_API_BASE") or KL.API_BASE, clock=self.now)
        self._live = live_api
        self.poster = poster or KL._default_poster
        self._alert = alert_cfg
        self.say = say or (lambda *_: None)
        self.cfg, self.problems = load_config(cfg_path)

    # ------------------------------------------------------------------ time
    def now(self) -> float:
        return self.raw_clock() - self.offset

    def sync(self, force=False):
        if not force and self.raw_clock() - KL._f(self.st.get("offset_t"), 0.0) < OFFSET_EVERY_S:
            return
        try:
            local, hdr = (self.date_fn or http_date)()
            off = offset_from(local, hdr)
        except Exception:  # noqa: BLE001
            off = None
        self.st["offset_t"] = self.raw_clock()
        if off is not None:
            self.offset = off if abs(off) >= 1.0 else 0.0
            self.st["offset"] = round(self.offset, 2)
            if abs(off) >= 5:
                self.log({"ev": "clock_off", "seconds": round(off, 1)})

    # ------------------------------------------------------------------ small helpers
    def log(self, row):
        KL.log(self.P, dict({"t": int(self.now()), "src": "clock"}, **row))

    def save(self):
        self.st["t"] = self.now()
        KL._jwrite(self.P["clock_state"], self.st)

    def live_api(self):
        if self._live is None:
            self._live = KL.api_from_key(self.env, clock=self.now)
        return self._live

    def alert_cfg(self) -> dict:
        if self._alert is None:
            try:
                from engine import notify
                self._alert = notify.alert_cfg(self.env)
            except Exception:  # noqa: BLE001
                self._alert = {}
        return self._alert or {}

    def push(self, kind, title, body, priority="default", tags="moneybag") -> bool:
        now = self.now()
        a = self.st.setdefault("alerts", {})
        if a.get("day") != KL.et_day(now):
            a.update(day=KL.et_day(now), n=0)
        if kind != "stop" and int(a.get("n") or 0) >= PUSH_DAY_MAX:
            return False
        cfg = self.alert_cfg()
        if not cfg.get("topic"):
            return False
        try:
            from engine import notify
            if kind not in ("stop",) and notify.quiet(now):
                priority = "low"
        except Exception:  # noqa: BLE001
            pass
        msg = {"title": title.encode("ascii", "replace").decode("ascii")[:120], "body": body[:900], "priority": priority, "tags": tags}
        try:
            ok = bool(self.poster(cfg.get("ntfy") or "https://ntfy.sh", cfg["topic"], msg))
        except Exception:  # noqa: BLE001
            ok = False
        if ok and kind != "stop":
            a["n"] = int(a.get("n") or 0) + 1
        a.setdefault("sent", []).append([int(now), kind])
        a["sent"] = a["sent"][-60:]
        self.log({"ev": "push", "kind": kind, "ok": ok, "title": msg["title"]})
        return ok

    def stop_live(self, why):
        """Any live stop: OFF (the phrase again to restart) + one push at once. Paper keeps recording."""
        live, _ = KL.arm_state(P=self.P, env=self.env)
        KL.disarm(self.P, why, self.now())
        self.st["stopped"] = {"t": int(self.now()), "why": why}
        self.log({"ev": "stopped", "why": why})
        if live or not self.st.get("stop_pushed_for") == why:
            self.st["stop_pushed_for"] = why
            self.push("stop", f"Kalshi K8 STOPPED: {why}"[:110], "Live clock bets are OFF (paper keeps recording). Open bets settle by "
                      "themselves within 15 minutes. To restart: the phone page (your PC link :8444/kalshi-live/) or KALSHI_LIVE.bat, type the phrase.",
                      priority="high", tags="warning")

    def controls(self):
        c = KL._jread(self.P["control"], {}) or {}
        done = set(self.st.get("done_cmds") or [])
        for cmd in c.get("cmds") or []:
            cid = str(cmd.get("id") or "")
            if not cid or cid in done:
                continue
            done.add(cid)
            if cmd.get("cmd") == "pause":
                self.st["paused_until"] = float(cmd.get("until") or KL.next_4pm(self.now()))
            elif cmd.get("cmd") == "resume":
                self.st["paused_until"] = None
            elif cmd.get("cmd") in ("flatten", "kill"):
                self.st["stopped"] = {"t": int(self.now()), "why": f"{cmd.get('cmd')} pressed"}
        self.st["done_cmds"] = sorted(done)[-50:]

    def live_view(self, now) -> dict:
        A = KL.load_all(state_dir=self.state_dir)
        live, why = KL.arm_state(P=self.P, sha=A["sha"], env=self.env)
        if live and self.st.get("stopped") and KL._f(self.st["stopped"].get("t"), 0) > KL._f((KL._jread(self.P["arm"], {}) or {}).get("t"), 0):
            live = False                                     # stopped after the last arm
        elif live:
            self.st.pop("stopped", None)
        day = KL.et_day(now)
        lr = [r for r in rows(self.P["clock_live"]) if r.get("day") == day]
        killed, kwhy = kill_state(self.state_dir, self.cfg)
        worst = sum(KL._f(r.get("pnl"), 0.0) for r in lr if r.get("result") in ("won", "lost")) \
            - sum(KL._f(r.get("cost"), 0.0) + KL._f(r.get("fee"), 0.0) for r in lr if r.get("result") is None and r.get("status") in ("sent", "open"))
        wk = week_of(day)
        allr = rows(self.P["clock_live"])
        wr = [r for r in allr if str(r.get("day") or "") >= wk and str(r.get("day") or "") <= day]
        wworst = sum(KL._f(r.get("pnl"), 0.0) for r in wr if r.get("result") in ("won", "lost")) \
            - sum(KL._f(r.get("cost"), 0.0) + KL._f(r.get("fee"), 0.0) for r in wr if r.get("result") is None and r.get("status") in ("sent", "open"))
        return {"now": now, "cfg": self.cfg, "kill": os.path.exists(self.P["kill"]) or KL.off_by_env(self.env), "live": live and not self.problems,
                "why": why if not self.problems else "the clock settings have a problem: " + self.problems[0], "stopped": False,
                "killed": killed, "kill_why": kwhy,
                "paused": bool(self.st.get("paused_until") and KL._f(self.st["paused_until"], 0) > now),
                "bets_today": len([r for r in lr if r.get("status") in ("sent", "open", "settled")]),
                "tickers_today": {r.get("ticker") for r in lr}, "day_worst": worst, "week_worst": wworst, "balance": None,
                "dd_now": drawdown(allr), "open_all": sum(KL._f(r.get("cost"), 0.0) + KL._f(r.get("fee"), 0.0) for r in allr
                                                          if r.get("result") is None and r.get("status") in ("sent", "open"))}

    # ------------------------------------------------------------------ one window: paper rows (+ live orders when armed)
    def entry(self, open_t, ids, last=True) -> list:
        """One try for the legs `ids` of the window opening at open_t. Returns the legs whose book cannot fill half the bet under
        the cap yet (tried again 10 s later, up to +40 s; on the last try they are skipped as 'book too thin')."""
        now = self.now()
        day = KL.et_day(open_t)
        v = self.live_view(now)
        if v["killed"] and v["live"]:
            self.stop_live(v["kill_why"])
            v["live"] = False
        elif not v["live"] and (KL._jread(self.P["arm"], {}) or {}).get("armed") is True:
            self.stop_live(v["why"].replace(": type the phrase again", ""))      # armed, but no longer valid (settings changed, ...): say so
        paper, live_rows = rows(self.P["clock_paper"]), rows(self.P["clock_live"])
        placed, notes, waiting = [], [], []
        for lid in ids:
            leg, lim = LEG[lid], leg_limits(self.cfg, lid, self.state_dir)
            tk = ticker(leg["series"], open_t)
            try:
                m = KL.norm_market(self.pub.get(f"/markets/{tk}", auth=False))
                yes, no = KL.norm_book(self.pub.get(f"/markets/{tk}/orderbook", auth=False))
                book_t = self.now()
            except KL.KalshiError as e:
                self.log({"ev": "no_market", "ticker": tk, "why": str(e)[:160]})
                if lim["enabled"] and v["live"] and e.status != 404:
                    self.error(f"no prices for {tk} ({e.status or e.code})")
                continue
            ask, depth, lv = side_quote(yes, no, leg["side"])
            stake = lim["stake"] if lim["enabled"] else self.cfg["stake_usd"]
            want = contracts(stake, ask)
            got, cost, worst = walk(lv, stake, lim["cap"])
            row = {"id": f"{day}:{lid}", "day": day, "leg": lid, "ticker": tk, "side": leg["side"], "t": round(book_t, 1), "open_t": open_t,
                   "ask": ask, "depth": depth, "status": "open", "result": None, "pnl": None}
            if m.get("status") != "active" or ask is None:
                row.update(status="skip", why="market not open" if m.get("status") != "active" else "no ask")
            elif ask > lim["cap"] + 1e-9:
                row.update(status="skip", why=f"ask {ask * 100:.0f}c above the {lim['cap'] * 100:.0f}c cap")
            elif got < max(1, math.ceil(want * self.cfg["min_fill_share"] - 1e-9)):
                if not last:
                    waiting.append(lid)
                    continue
                row.update(status="skip", why=f"book too thin: {got} of {want} contracts under the cap")
            else:
                row.update(n=got, price=round(cost / got, 4), worst=worst, cost=cost, fee=fee(cost / got, got))
            if lid in self.cfg["paper_legs"] and not any(r.get("id") == row["id"] for r in paper):
                paper.append(dict(row))
            if not (lim["enabled"] and v["live"]):
                if lid in self.cfg["live_legs"] and v["live"] and lim.get("why"):
                    notes.append(f"{leg['name']}: off ({lim['why']})")
                continue
            if row["status"] != "open":
                notes.append(f"{leg['name']}: skipped ({row.get('why')})")
                continue
            if v["balance"] is None:
                v["balance"] = self.balance()
            o = {"ticker": tk, "side": leg["side"], "count": got, "cost": cost, "worst": worst, "ask": ask, "open_t": open_t,
                 "book_t": book_t, "market": m, "stake": lim["stake"], "cap": lim["cap"]}
            ok, code, words = check_order(o, dict(v, now=self.now()))
            if not ok:
                notes.append(f"{leg['name']}: skipped ({words})")
                self.log({"ev": "live_blocked", "ticker": tk, "code": code})
                if code == "DD_STOP" and not KL._f(v.get("open_all")):
                    self.stop_live(f"the drawdown stop: {words}")       # no room left for even one bet: OFF + one push (paper keeps on)
                    v["live"] = False
                continue
            r = self.send(o, open_t, lid, day)
            if r:
                live_rows.append(r)
                placed.append(r)
                v["bets_today"] += 1
                v["tickers_today"].add(tk)
                v["day_worst"] -= r["cost"] + r["fee"]
                v["week_worst"] = KL._f(v.get("week_worst"), 0.0) - r["cost"] - r["fee"]
                v["open_all"] = KL._f(v.get("open_all"), 0.0) + r["cost"] + r["fee"]
                v["balance"] = (v["balance"] or 0) - r["cost"] - r["fee"]
            if self.st.get("stopped"):
                v["live"] = False                    # no more live orders this window; the paper rows of the other legs still go in
        save_rows(self.P["clock_paper"], paper)
        save_rows(self.P["clock_live"], live_rows)
        hm = KL.et_dt(open_t).strftime("%H:%M")
        if placed:
            self.push("placed", f"Kalshi LIVE {hm} ET: {len(placed)} bet{'s' if len(placed) != 1 else ''} in",
                      "; ".join(f"{LEG[r['leg']]['name']}: {r['n']} at {r['price'] * 100:.0f}c ({KL.money(r['cost'])})" for r in placed)
                      + (". " + "; ".join(notes) if notes else "") + ". Results about 16 minutes after the open.", tags="moneybag")
        elif notes and v["live"] and not waiting:
            self.push("placed", f"Kalshi LIVE {hm} ET: no bet", "; ".join(notes), priority="low", tags="pause_button")
        return waiting

    def balance(self):
        try:
            b = self.live_api().get("/portfolio/balance")
            return KL._f(b.get("balance_dollars"), (KL._f(b.get("balance"), 0.0) or 0.0) / 100.0)
        except KL.KalshiError as e:
            self.error(f"Kalshi balance not read ({e.status or e.code})", hard=e.status == 401)
            return 0.0

    def error(self, why, hard=False):
        self.st["err"] = int(self.st.get("err") or 0) + 1
        self.log({"ev": "error", "why": why, "n": self.st["err"]})
        if hard or self.st["err"] >= ERR_STREAK:
            self.stop_live(why if hard else f"{self.st['err']} errors in a row ({why})")
            self.st["err"] = 0

    def send(self, o, open_t, lid, day):
        """One limit order at the best ask, good till open + 40 s. -> the live row, or None."""
        if os.path.exists(self.P["kill"]) or (KL._jread(self.P["arm"], {}) or {}).get("armed") is not True:
            return None
        book = "bid" if o["side"] == "yes" else "ask"
        yes_px = o["worst"] if o["side"] == "yes" else round(1 - o["worst"], 4)     # a limit at the walk's worst level (<= the cap)
        coid = f"{COID}{int(self.now()):x}-{secrets.token_hex(3)}"
        exp = int(min(open_t + 55, max(open_t + self.cfg["expire_after_s"], self.now() + 10)))
        body = {"ticker": o["ticker"], "side": book, "count": str(o["count"]), "price": f"{yes_px:.4f}", "time_in_force": "good_till_canceled",
                "expiration_time": exp, "self_trade_prevention_type": "taker_at_cross", "client_order_id": coid}
        try:
            r = self.live_api().call("POST", "/portfolio/events/orders", body=body)
        except KL.KalshiError as e:
            if e.status == 410 or e.code == "deprecated_v1_order_endpoint":
                self.error("Kalshi changed its order API (410): Claude must update the executor", hard=True)
            elif e.status in (401, 403) and "location" not in str(e).lower():
                self.error(f"Kalshi refused the key ({e.status})", hard=True)
            else:
                self.error(f"order refused ({e.code or e.status})")
            return None
        self.st["err"] = 0
        got = KL._f(r.get("fill_count"), 0.0) or 0.0
        row = {"id": f"{day}:{lid}", "day": day, "leg": lid, "ticker": o["ticker"], "side": o["side"], "t": round(self.now(), 1),
               "open_t": open_t, "order_id": str(r.get("order_id") or ""), "coid": coid, "n": o["count"],
               "price": round(o["cost"] / o["count"], 4), "worst": o["worst"], "cost": o["cost"], "fee": fee(o["cost"] / o["count"], o["count"]),
               "filled_at_once": got, "status": "sent", "result": None, "pnl": None}
        self.log({"ev": "live_order", "ticker": o["ticker"], "n": o["count"], "price": row["price"], "id": row["order_id"][-6:]})
        return row

    # ------------------------------------------------------------------ results
    def settle(self):
        now = self.now()
        changed = {"paper": False, "live": False}
        done_live = []
        for kind in ("paper", "live"):
            path = self.P[f"clock_{kind}"]
            rs = rows(path)
            for r in rs:
                if r.get("result") is not None or r.get("status") not in ("open", "sent"):
                    continue
                if now < r["open_t"] + SETTLE_AFTER_S:
                    continue
                if now - r["open_t"] > SETTLE_GIVE_UP_S:
                    r.update(status="unsettled", result="unknown")
                    changed[kind] = True
                    continue
                if now - KL._f(r.get("try_t"), 0) < SETTLE_RETRY_S:
                    continue
                r["try_t"] = now
                try:
                    m = KL.norm_market(self.pub.get(f"/markets/{r['ticker']}", auth=False))
                except KL.KalshiError:
                    continue
                if m.get("result") not in ("yes", "no"):
                    continue
                won = m["result"] == r["side"]
                if kind == "live":
                    n, cost, fees = self.filled(r)
                    if n is None:
                        continue
                    if n < 1:
                        r.update(status="not_filled", result="none", pnl=0.0, n=0, cost=0.0, fee=0.0)
                        changed[kind] = True
                        continue
                    r.update(n=n, cost=round(cost, 4), fee=round(fees, 4), price=round(cost / n, 4))
                r["result"] = "won" if won else "lost"
                r["status"] = "settled"
                r["pnl"] = round((r["n"] if won else 0.0) - r["cost"] - r["fee"], 2)
                changed[kind] = True
                if kind == "live":
                    done_live.append(r)
            if changed[kind]:
                save_rows(path, rs)
        if done_live:
            allr = rows(self.P["clock_live"])
            s, d = stats(allr), stats(allr, KL.et_day(now))
            by_t = {}
            for r in done_live:
                by_t.setdefault(KL.et_dt(r["open_t"] + 900).strftime("%H:%M"), []).append(r)
            for hm, rr in sorted(by_t.items()):
                self.push("result", f"Kalshi LIVE {hm}: " + ", ".join(f"{LEG[r['leg']]['name'].split()[0]} {'WON' if r['result'] == 'won' else 'LOST'} "
                                                                    f"{KL.money(r['pnl'], True)}" for r in rr)[:110],
                          f"Today {KL.money(d['net'], True)} on {d['n']} bets. Live so far: {s['n']} bets, {s['won']} won"
                          + (f" ({100 * s['rate']:.0f}%)" if s["n"] else "") + f", {KL.money(s['net'], True)}.", tags="moneybag")
            killed, why = kill_state(self.state_dir, self.cfg)
            if killed:
                self.stop_live(why)

    def filled(self, r):
        """(contracts filled, $ paid for our side, fees) from Kalshi's fills of the order; None = could not read."""
        try:
            fs = [KL.norm_fill(f) for f in self.live_api().pages("/portfolio/fills", "fills", {"order_id": r["order_id"], "limit": 200}, max_pages=2)]
        except KL.KalshiError as e:
            self.error(f"fills not read ({e.status or e.code})", hard=e.status == 401)
            return None, None, None
        n = cost = fees = 0.0
        for f in fs:
            if f["order_id"] and f["order_id"] != r["order_id"]:
                continue
            p = f["y"] if r["side"] == "yes" else (1 - f["y"])
            n += f["n"]
            cost += f["n"] * p
            fees += f["fee"] if f["fee"] is not None else fee(p, f["n"])
        return n, cost, fees

    def summary(self):
        """One push a day after the evening window settles (17:05 ET on weekdays, or 18:00 at the latest)."""
        now = self.now()
        d = KL.et_dt(now)
        day = KL.et_day(now)
        if d.weekday() >= 5 or self.st.get("summary_day") == day or (d.hour, d.minute) < (17, 5):
            return
        pr, lr = rows(self.P["clock_paper"]), rows(self.P["clock_live"])
        if (d.hour, d.minute) < (18, 0) and any(r.get("day") == day and r.get("result") is None and r.get("status") in ("open", "sent") for r in pr + lr):
            return
        self.st["summary_day"] = day
        sp, sl, ap, al = stats(pr, day), stats(lr, day), stats(pr), stats(lr)

        def f(s):
            return f"{s['n']} bets, {s['won']} won, {KL.money(s['net'], True)}"
        live_on = KL.arm_state(P=self.P, env=self.env)[0]
        title = f"Kalshi K8 {d:%a %b} {d.day}: " + (f"LIVE {KL.money(sl['net'], True)}" if sl["n"] else "") + \
            (" | " if sl["n"] else "") + f"paper {KL.money(sp['net'], True)}"
        body = (f"Today: live {f(sl)}; paper {f(sp)}. Since the start: live {f(al)}" + (f" ({100 * al['rate']:.0f}%)" if al["n"] else "")
                + f"; paper {f(ap)}" + (f" ({100 * ap['rate']:.0f}%)" if ap["n"] else "") + f". Live is {'ON' if live_on else 'OFF'}. "
                f"Kill rule: OFF if under {100 * self.cfg['kill_min_win_rate']:.0f}% won after {self.cfg['kill_after_bets']} live bets.")
        self.push("summary", title, body, priority="low", tags="bar_chart")

    # ------------------------------------------------------------------ the step
    def step(self) -> float:
        self.sync()
        now = self.now()
        self.controls()
        self.cfg, self.problems = load_config(self.cfg_path, self.state_dir)
        done = set(self.st.get("done") or [])
        tries = self.st.setdefault("tries", {})
        nxt = None
        d = KL.et_dt(now).date()
        for day in (d - dt.timedelta(days=1), d, d + dt.timedelta(days=1)):
            for t, ids in windows(day, self.cfg):
                key = f"{t:.0f}"
                if key in done:
                    continue
                w = tries.get(key) or {"k": 0, "legs": list(ids)}
                at = t + self.cfg["entry_delay_s"] + TRIES[min(w["k"], len(TRIES) - 1)]
                if at <= now <= t + SLOT[1]:
                    last = w["k"] >= len(TRIES) - 1 or now + 10 > t + SLOT[1]
                    left = self.entry(t, w["legs"], last=last)
                    if left and not last:
                        tries[key] = {"k": w["k"] + 1, "legs": left}
                        at2 = t + self.cfg["entry_delay_s"] + TRIES[w["k"] + 1]
                        nxt = at2 if nxt is None else min(nxt, at2)
                        continue
                    tries.pop(key, None)
                    self.st["done"] = (self.st.get("done") or [])[-60:] + [key]
                    done.add(key)
                elif now > t + SLOT[1] and now - t < 6 * 3600:
                    tries.pop(key, None)
                    self.st["done"] = (self.st.get("done") or [])[-60:] + [key]      # missed (the PC slept, or the loop started late)
                    self.log({"ev": "missed", "open": key})
                    done.add(key)
                elif at > now and (nxt is None or at < nxt):
                    nxt = at
        self.settle()
        self.summary()
        self.save()
        return HEARTBEAT_S if nxt is None else max(0.05, min(HEARTBEAT_S, nxt - self.now()))

    def status(self) -> dict:
        now = self.now()
        t, ids = next_window(now, self.cfg)
        live, why = KL.arm_state(P=self.P, env=self.env)
        day = KL.et_day(now)
        pr, lr = rows(self.P["clock_paper"]), rows(self.P["clock_live"])
        return {"live": live, "why": why, "paused": bool(self.st.get("paused_until") and KL._f(self.st["paused_until"], 0) > now),
                "next": t, "next_legs": [LEG[i]["name"] for i in ids if i in self.cfg["live_legs"] or i in self.cfg["paper_legs"]],
                "paper_today": stats(pr, day), "live_today": stats(lr, day), "paper_all": stats(pr), "live_all": stats(lr),
                "last": [{k: r.get(k) for k in ("day", "leg", "side", "price", "n", "result", "pnl", "status")} for r in (lr or pr)[-6:]],
                "kill": kill_state(self.state_dir, self.cfg)[1], "loop": loop_alive(self.P, now), "offset": round(self.offset, 1)}


# ================================================================================================ process
def loop_alive(P, now=None) -> bool:
    now = time.time() if now is None else now
    return now - KL._f((KL._jread(P["clock_state"], {}) or {}).get("t"), 0.0) < 3 * HEARTBEAT_S + 30


def run(state_dir=None, env=None, max_steps=None, sleep=time.sleep, **kw) -> str:
    P = paths(state_dir)
    fh = KL._lock(P["clock_lock"])
    if fh is None:
        return "already running"
    try:
        loop = ClockLoop(state_dir=state_dir, env=env, **kw)
        loop.sync(force=True)
        n = 0
        while max_steps is None or n < max_steps:
            if os.path.exists(P["clock_off"]) or str((os.environ if env is None else env).get("LE_KALSHI_CLOCK", "")).strip() == "0":
                return "off"
            try:
                wait = loop.step()
            except Exception as e:  # noqa: BLE001  (never dies on one bad step; logged)
                KL.log(P, {"t": int(time.time()), "src": "clock", "ev": "step_error", "why": KL.redact(e)})
                wait = HEARTBEAT_S
            n += 1
            if max_steps is None or n < max_steps:
                sleep(wait)
        return "steps done"
    finally:
        try:
            fh.close()
        except Exception:  # noqa: BLE001
            pass


def spawn(state_dir=None) -> int:
    import subprocess
    P = paths(state_dir)
    os.makedirs(P["dir"], exist_ok=True)
    try:                                                     # keep the loop's own output small (data map: clock_loop.log)
        if os.path.getsize(P["clock_out"]) > 1_000_000:
            os.replace(P["clock_out"], P["clock_out"] + ".1")
    except OSError:
        pass
    out = open(P["clock_out"], "a", encoding="utf-8")
    cmd = [sys.executable, "-X", "utf8", "-m", "engine.kalshi_live", "--clock-loop"] + (["--state-dir", state_dir] if state_dir else [])
    kw = {"cwd": KL.ROOT, "stdout": out, "stderr": out, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        base = 0x08000000 | 0x00000200                     # CREATE_NO_WINDOW | NEW_PROCESS_GROUP (normal priority: the timing matters)
        try:
            pid = subprocess.Popen(cmd, creationflags=base | 0x01000000, **kw).pid      # + BREAKAWAY_FROM_JOB
        except OSError:
            pid = subprocess.Popen(cmd, creationflags=base, **kw).pid
    else:
        kw["start_new_session"] = True
        pid = subprocess.Popen(cmd, **kw).pid
    KL._jwrite(P["clock_run"], {"pid": pid, "t": int(time.time())})
    return pid


def maybe_run(say=print, env=None, now=None, state_dir=None, spawn_fn=None):
    """Keep ONE clock loop running (paper always; it trades only while armed). LE_KALSHI_CLOCK=0 or data/kalshi_live/CLOCK_OFF = off.
    Never raises; returns the new pid or None."""
    try:
        e = os.environ if env is None else env
        P = paths(state_dir)
        now = time.time() if now is None else now
        if str(e.get("LE_KALSHI_CLOCK", "")).strip() == "0" or os.path.exists(P["clock_off"]):
            return None
        if loop_alive(P, now) or now - KL._f((KL._jread(P["clock_run"], {}) or {}).get("t"), 0.0) < 120:
            return None
        pid = (spawn_fn or spawn)(state_dir)
        say(f"  [..] Kalshi K8 clock loop started (pid {pid}): paper always, live only while armed")
        return pid
    except Exception:  # noqa: BLE001
        return None
