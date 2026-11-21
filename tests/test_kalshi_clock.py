"""Kalshi K8 clock bets (engine/kalshi_clock.py) + the phone page (engine/kalshi_web.py), on a FAKE Kalshi and a fake clock.
No network, no real key, no real order; Claude never arms (every arm here is the test typing the phrase into a temp folder).

  a. calendar   weekdays only; morning legs at London 10:15 (05:15 ET; 06:15 ET on Mar 16, 2027), evening legs 16:45 ET; UK bank
                holidays skip the morning, CME holidays / early closes skip the evening; tickers KXGOLD15M-26NOV190530-30
  b. entry      the walk buys whole contracts under the cap and inside $15 (= floor(15 / ask) on a deep book); half-fill rule
  c. caps       check_order: EACH rule blocks a live order (kill, not armed, stopped, kill rule, paused, bad order, 10-45 s slot,
                price cap, $ per bet, 6 bets a day, one bet per market, -$60 day, cash, stale prices, market closed, a broken view)
  d. paper      not armed: at 05:15:20 ET the paper ledger gets ticker, side, ask, contracts, cost; NO order; after the settle the
                result and $ (fee in); one day summary push, no per-bet push
  e. live       armed with the phrase: the same pass places one V2 limit per live leg at the walk price (DOWN = sell YES at the YES
                bid), good till +40 s; one push per window placed + one per window settled; P&L from Kalshi's fills; paper in parallel
  f. stops      kill rule (under 58% after 60), drawdown -$75 from the peak, 3 errors in a row, 401, a thin book (tried at +20/+30/+40
                then skipped), cash below the bet, the phone STOP: each = no order / OFF + one push; paper keeps recording
  g. clock      the PC clock 12 s fast: Kalshi's Date header corrects it, the entry lands at +20 s Kalshi time
  s. $55         the bankroll rule ($2.50 a bet, -$8 a day, -$13.75 a week, OFF at -$19.25): the order gate's week and drawdown
                stops, then a whole week where every bet loses on the real settings: the week never passes -25%, the total never -30%
  w. phone page private Tailscale link only (WiFi refused), this page's header + JSON + same origin; the key pasted on the phone is
                saved OUTSIDE the repo, checked with one balance read ("Key OK · balance $X"), never echoed or logged; wrong phrase
                refused; the phrase + $8 arms at $8; STOP = OFF + kill switch; installed by engine/phone_safety.install

  python -X utf8 -m tests.test_kalshi_clock
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tests import test_kalshi_live as TL  # noqa: E402  (the fake Kalshi, the key helpers)

from engine import kalshi_clock as KC  # noqa: E402
from engine import kalshi_live as KL  # noqa: E402

REAL_CFG = KC.CFG_PATH                                   # research/lab/kalshi_clock.json: the $55 bankroll rule (part a3 + part s)
FIX15 = os.path.join(ROOT, "tests", "fixtures", "kalshi_live", "clock_15.json")   # the mechanics parts b-g + w: the $15 settings of Nov 19
KC.CFG_PATH = FIX15
KL.CLOCK_PATH = FIX15
RES: list = []
DAY = dt.date(2026, 11, 19)                             # a Thursday
OPEN_AM = KC.london_epoch(DAY, 10, 15)                  # 05:15 ET
OPEN_PM = KC.et_epoch(DAY, 16, 45)


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + ("" if cond else f"  -> {str(info)[:600]}"), flush=True)
    return bool(cond)


class Died(BaseException):
    """the PC dying mid-send (not an Exception: nothing in the executor catches it)"""


class Fake(TL.FakeKalshi):
    """+ fills filtered by order_id; a GTC limit that crosses the book fills at once (taker), the rest rests until it expires."""

    lose = None           # red team 2026-11-21: "502" = Kalshi takes the order but the answer is lost; "die" = the PC dies mid-send

    def route(self, method, path, q, body):
        if method == "GET" and path == "/portfolio/fills" and q.get("order_id"):
            return 200, {"cursor": "", "fills": [f for f in self.fills if f["order_id"] == q["order_id"]]}
        if method == "GET" and path == "/portfolio/fills" and q.get("ticker"):
            return 200, {"cursor": "", "fills": [f for f in self.fills if f["ticker"] == q["ticker"] and f["ts"] >= float(q.get("min_ts") or 0)]}
        return super().route(method, path, q, body)

    def place(self, b):
        if self.lose:
            st, j = self._place(b)
            if self.lose == "die":
                self.lose = None
                raise Died()
            return 502, {"error": {"code": "bad_gateway", "message": "fake: the answer was lost"}}
        return self._place(b)

    def _place(self, b):
        if b.get("time_in_force") == "good_till_canceled" and not b.get("post_only"):
            t, side, n, p = b["ticker"], b["side"], float(b["count"]), float(b["price"])
            mk = self.markets.get(t)
            if not mk or mk["status"] != "active":
                return 409, {"error": {"code": "market_inactive"}}
            yes, no = self.books[t]
            self.n += 1
            oid = f"ord{self.n}"
            got = 0.0
            if side == "bid":                                  # buy YES: walk the NO bids (asks = 1 - p), cheapest first
                for bp, q_ in sorted(no, reverse=True):
                    if 1 - bp <= p + 1e-9 and got < n:
                        k = min(q_, n - got)
                        self.apply_fill(oid, t, side, k, round(1 - bp, 4), True)
                        got += k
            else:                                              # sell YES (= buy NO): walk the YES bids, best first
                for bp, q_ in sorted(yes, reverse=True):
                    if bp >= p - 1e-9 and got < n:
                        k = min(q_, n - got)
                        self.apply_fill(oid, t, side, k, bp, True)
                        got += k
            if n - got > 0:
                self.orders[oid] = {"order_id": oid, "client_order_id": b.get("client_order_id") or "", "ticker": t, "book_side": side, "p": p,
                                    "rem": n - got, "n": n, "exp": b.get("expiration_time"), "body": b}
            return 201, {"order_id": oid, "fill_count": f"{got:.2f}", "remaining_count": f"{n - got:.2f}", "ts_ms": int(self.clock() * 1000),
                         "client_order_id": b.get("client_order_id")}
        return super().place(b)


class World:
    def __init__(self, tmp, name, cash=500.0, kind="ed"):
        self.dir = os.path.join(tmp, name)
        os.makedirs(self.dir)
        self.home = os.path.join(self.dir, "home")
        os.makedirs(os.path.join(self.home, "kalshi"))
        self.key, pem = TL.keypair(kind)
        open(os.path.join(self.home, "kalshi", "kalshi_key.pem"), "wb").write(pem)
        open(os.path.join(self.home, "kalshi", "key_id.txt"), "w").write(TL.KEY_ID)
        self.env = {"OLYMPUS_HOME": self.home}
        self.sd = os.path.join(self.dir, "state")
        self.clock = TL.Clock(OPEN_AM - 60)
        self.fake = Fake(self.clock, self.key.public_key(), cash=cash)
        self.pushes = []
        self.books(0.52, 0.55)

    def books(self, gold_no_ask=0.52, silver_no_ask=0.55, pm_yes_ask=0.50, depth=500):
        f = self.fake
        for open_t in (OPEN_AM, KC.et_epoch(DAY, 16, 0), OPEN_PM):
            for series in ("KXGOLD15M", "KXSILVER15M"):
                tk = KC.ticker(series, open_t)
                if tk not in f.markets:
                    f.markets[tk] = {"ticker": tk, "event_ticker": tk.rsplit("-", 1)[0], "status": "active", "result": "",
                                     "close_time": TL.iso(open_t + 900), "yes_sub_title": "Target Price: $1", "price_ranges": []}
                a = (gold_no_ask if series == "KXGOLD15M" else silver_no_ask) if open_t == OPEN_AM else pm_yes_ask
                if open_t == OPEN_AM or open_t == KC.et_epoch(DAY, 16, 0):     # we buy NO: NO ask = 1 - best YES bid
                    f.books[tk] = ([(round(1 - a, 2), depth), (round(1 - a - 0.01, 2), depth)], [(round(a - 0.02, 2), depth)])
                else:                                          # we buy YES: YES ask = 1 - best NO bid
                    f.books[tk] = ([(round(a - 0.02, 2), depth)], [(round(1 - a, 2), depth), (round(1 - a - 0.01, 2), depth)])

    def poster(self, base, topic, msg):
        self.pushes.append(dict(msg, t=self.clock()))
        return True

    def loop(self, **kw):
        api = KL.Api(key_id=TL.KEY_ID, key=self.key, http=self.fake, sleep=lambda s: None, clock=self.clock, gap=0)
        return KC.ClockLoop(state_dir=self.sd, env=self.env, clock=self.clock, public_api=KL.Api(http=self.fake, sleep=lambda s: None,
                            clock=self.clock, gap=0), live_api=api, poster=self.poster, alert_cfg={"ntfy": "https://ntfy.example", "topic": "t"},
                            date_fn=kw.get("date_fn") or (lambda: (self.clock(), None)))

    def arm(self, stake=None):
        if stake is not None:
            KL._jwrite(KC.stake_path(self.sd), {"stake": stake})
        return KL.arm(KL.PHRASE, state_dir=self.sd, env=self.env, now=self.clock())

    def run_until(self, loop, t_end):
        while self.clock() < t_end:
            wait = loop.step()
            self.clock.add(max(0.5, min(wait, 30)))

    def paper(self):
        return KC.rows(KC.paths(self.sd)["clock_paper"])

    def live(self):
        return KC.rows(KC.paths(self.sd)["clock_live"])

    def posts(self):
        return [c for c in self.fake.calls if c[0] == "POST"]

    def settle(self, open_t, results):
        for series, res in results.items():
            self.fake.settle(KC.ticker(series, open_t), res)


# ================================================================================================ a. calendar
def part_calendar():
    cfg = KC.load_config()[0]
    real = KC.load_config(REAL_CFG)[0]
    rule = KC.bankroll_rule(55)
    check("a0. the REAL settings (research/lab/kalshi_clock.json) = the $55 bankroll rule: $2.50 a bet, 3 bets a day, -$8 a day, "
          "-$13.75 a week (25%), OFF at -$19.25 from the peak (35%); the same 3 live legs; no problems",
          real["bankroll_usd"] == 55 and real["stake_usd"] == rule["stake_usd"] == 2.5 and real["max_bets_per_day"] == rule["max_bets_per_day"] == 3
          and real["daily_loss_stop_usd"] == rule["daily_loss_stop_usd"] == 8 and real["week_loss_stop_usd"] == rule["week_loss_stop_usd"] == 13.75
          and real["kill_drawdown_usd"] == rule["kill_drawdown_usd"] == 19.25 and real["live_legs"] == ["gold_0530_down", "gold_1700_up", "silver_1700_up"]
          and not KC.load_config(REAL_CFG)[1], (real, rule))
    w = KC.windows(DAY, cfg)
    hm = [KL.et_dt(t).strftime("%H:%M") for t, _ in w]
    check("a1. a weekday: 05:15 ET (gold + silver DOWN), 16:00 ET (silver DOWN, paper only), 16:45 ET (gold + silver UP); "
          "ticker KXGOLD15M-26NOV190530-30", hm == ["05:15", "16:00", "16:45"] and w[0][1] == ["gold_0530_down", "silver_0530_down"]
          and KC.ticker("KXGOLD15M", OPEN_AM) == "KXGOLD15M-26NOV190530-30" and KC.ticker("KXSILVER15M", OPEN_PM) == "KXSILVER15M-26NOV191700-00", w)
    tg = [KL.et_dt(t).strftime("%H:%M") for t, _ in KC.windows(dt.date(2026, 11, 26), cfg)]
    uk = [KL.et_dt(t).strftime("%H:%M") for t, _ in KC.windows(dt.date(2026, 12, 28), cfg)]
    gap = [KL.et_dt(t).strftime("%H:%M") for t, _ in KC.windows(dt.date(2027, 3, 16), cfg)]
    check("a2. Thanksgiving (CME): no evening legs; Dec 28 (UK holiday, no LBMA auction): no morning legs; Mar 16, 2027 (UK still on "
          "winter time): the morning legs at 06:15 ET (London 10:15); weekends: nothing", tg == ["05:15"] and uk == ["16:00", "16:45"]
          and gap[0] == "06:15" and KC.ticker("KXGOLD15M", KC.windows(dt.date(2027, 3, 16), cfg)[0][0]) == "KXGOLD15M-27MAR160630-30"
          and not KC.windows(dt.date(2026, 11, 21), cfg), (tg, uk, gap))
    check("a3. the $15 test settings (tests/fixtures/kalshi_live/clock_15.json, the mechanics parts): gold DOWN 05:15, gold + silver UP 16:45; silver 05:15 and silver 16:15 paper only; "
          "$15 a bet, 70c cap, 6 bets a day, -$60 a day, OFF under 58% after 60, -$75 from the peak or over 58c paid on the last 30",
          cfg["live_legs"] == ["gold_0530_down", "gold_1700_up", "silver_1700_up"] and {"silver_1615_down", "silver_0530_down"} <= set(cfg["paper_legs"])
          and cfg["kill_avg_price"] == 0.58 and cfg["kill_avg_price_bets"] == 30
          and cfg["stake_usd"] == 15 and cfg["price_cap"] == 0.70 and cfg["max_bets_per_day"] == 6 and cfg["daily_loss_stop_usd"] == 60
          and cfg["kill_min_win_rate"] == 0.58 and cfg["kill_drawdown_usd"] == 75, cfg)


# ================================================================================================ b. entry maths
def part_entry():
    lv = [(0.52, 1000)]
    check("b1. a deep book: the walk buys floor(15 / 0.52) = 28 contracts at 52c ($14.56)", KC.walk(lv, 15, 0.70) == (28, 14.56, 0.52), KC.walk(lv, 15, 0.70))
    lv2 = [(0.52, 10), (0.53, 10), (0.75, 100)]
    got, cost, worst = KC.walk(lv2, 15, 0.70)
    check("b2. a thin book: it walks up to the cap only (10 at 52c + 10 at 53c), never past 70c, never past $15",
          (got, round(cost, 2), worst) == (20, 10.5, 0.53), (got, cost, worst))
    check("b3. the ask above the cap: nothing", KC.walk([(0.71, 100)], 15, 0.70)[0] == 0)


# ================================================================================================ c. caps (pure)
def view(**kw):
    cfg = KC.load_config()[0]
    v = {"now": OPEN_AM + 21, "cfg": cfg, "kill": False, "live": True, "why": "", "stopped": False, "killed": False, "paused": False,
         "bets_today": 0, "tickers_today": set(), "day_worst": 0.0, "balance": 100.0}
    v.update(kw)
    return v


def order(**kw):
    o = {"ticker": "KXGOLD15M-26NOV190530-30", "side": "no", "count": 28, "cost": 14.56, "worst": 0.52, "ask": 0.52, "open_t": OPEN_AM,
         "book_t": OPEN_AM + 20, "market": {"status": "active", "close_ts": OPEN_AM + 900}, "stake": 15.0, "cap": 0.70}
    o.update(kw)
    return o


def part_caps():
    check("c0. a good K8 order passes", KC.check_order(order(), view())[0], KC.check_order(order(), view()))
    cases = [("KILL", {}, {"kill": True}), ("NOT_ARMED", {}, {"live": False}), ("STOPPED", {}, {"stopped": True}),
             ("KILL_RULE", {}, {"killed": True}), ("PAUSED", {}, {"paused": True}), ("BAD_ORDER", {"count": 0}, {}),
             ("BAD_ORDER", {"side": "up"}, {}), ("SLOT", {}, {"now": OPEN_AM + 5}), ("SLOT", {}, {"now": OPEN_AM + 50}),
             ("PRICE", {"worst": 0.72}, {}), ("PRICE", {"cap": 0.60, "worst": 0.61}, {}), ("STAKE", {"count": 30, "cost": 15.6}, {}),
             ("BETS_DAY", {}, {"bets_today": 6}), ("ONE_BET", {}, {"tickers_today": {"KXGOLD15M-26NOV190530-30"}}),
             ("DAY_STOP", {}, {"day_worst": -46.0}), ("BALANCE", {}, {"balance": 10.0}), ("STALE_BOOK", {"book_t": OPEN_AM + 5}, {}),
             ("MARKET", {"market": {"status": "closed", "close_ts": OPEN_AM + 900}}, {}), ("ERROR", {}, {"cfg": None})]
    got = [(c, KC.check_order(order(**o), view(**v))) for c, o, v in cases]
    bad = [(c, r[1]) for c, r in got if r[0] or r[1] != c]
    check(f"c1. each rule blocks a live order on its own ({len(cases)} cases: kill, not armed, stopped, kill rule, paused, bad order, slot, "
          "price cap, per-leg cap, $15 a bet, 6 a day, one per market, -$60 day, cash, stale book, market closed, broken view)", not bad, bad)


# ================================================================================================ d. paper
def part_paper(tmp):
    w = World(tmp, "paper")
    loop = w.loop()
    w.run_until(loop, OPEN_AM + 25)
    pr = w.paper()
    g = next((r for r in pr if r["leg"] == "gold_0530_down"), {})
    check("d1. not armed: at 05:15:20 ET the paper ledger records gold + silver DOWN: ticker, side NO, the ask, contracts, cost; NO order sent",
          len(pr) == 2 and g.get("ticker") == "KXGOLD15M-26NOV190530-30" and g.get("side") == "no" and g.get("ask") == 0.52 and g.get("n") == 28
          and abs(g.get("cost", 0) - 14.56) < 1e-6 and not w.posts() and abs(g["t"] - (OPEN_AM + 20)) < 2, pr)
    w.settle(OPEN_AM, {"KXGOLD15M": "no", "KXSILVER15M": "yes"})
    w.run_until(loop, OPEN_AM + 17 * 60)
    pr = {r["leg"]: r for r in w.paper()}
    fee28 = KC.fee(0.52, 28)
    check("d2. after the settle: gold WON +$13.44 - fee, silver LOST its cost + fee (the fake's results)", pr["gold_0530_down"]["result"] == "won"
          and abs(pr["gold_0530_down"]["pnl"] - round(28 - 14.56 - fee28, 2)) < 0.011 and pr["silver_0530_down"]["result"] == "lost", pr)
    w.books(pm_yes_ask=0.50)
    w.run_until(loop, OPEN_PM + 25)
    w.settle(KC.et_epoch(DAY, 16, 0), {"KXSILVER15M": "no", "KXGOLD15M": "no"})
    w.settle(OPEN_PM, {"KXGOLD15M": "yes", "KXSILVER15M": "yes"})
    w.run_until(loop, KC.et_epoch(DAY, 17, 6))
    summ = [p for p in w.pushes if p["title"].startswith("Kalshi K8 ")]
    check("d3. paper only: ONE day summary push after the evening settle (paper 5 bets), no per-bet push", len(w.pushes) == 1 and len(summ) == 1
          and "paper" in summ[0]["title"] and "5 bets" in summ[0]["body"], w.pushes)


# ================================================================================================ e. live
def part_live(tmp):
    w = World(tmp, "live")
    ok = w.arm()
    loop = w.loop()
    w.run_until(loop, OPEN_AM + 25)
    lr, posts = w.live(), w.posts()
    b = posts[0][3] if posts else {}
    check("e1. armed by the phrase: at +20 s one V2 order for the live morning leg (gold): DOWN = side ask (sell YES) at the YES bid 48c, "
          "28 contracts ($14.56 at 52c), good till canceled, expiring by +55 s, olyc- id; never post-only, never a market order",
          ok[0] and len(posts) == 1 and b.get("side") == "ask" and b.get("price") == "0.4800" and b.get("count") == "28"
          and b.get("time_in_force") == "good_till_canceled" and OPEN_AM + 40 <= b.get("expiration_time", 0) <= OPEN_AM + 55
          and b.get("client_order_id", "").startswith("olyc-") and "post_only" not in b and len(lr) == 1, (ok, posts[:1], lr))
    check("e2. the paper ledger records the same window in parallel, silver 05:15 too (paper only)", len(w.paper()) == 2
          and {r["leg"] for r in w.paper()} == {"gold_0530_down", "silver_0530_down"})
    placed = [p for p in w.pushes if "bets in" in p["title"] or "bet in" in p["title"]]
    check("e3. one push for the window's bets (not one per leg): what, how many, at what price, $", len(placed) == 1 and "gold DOWN" in placed[0]["body"]
          and "28 at 52c" in placed[0]["body"], w.pushes)
    w.settle(OPEN_AM, {"KXGOLD15M": "no", "KXSILVER15M": "yes"})
    w.run_until(loop, OPEN_AM + 17 * 60)
    lr = {r["leg"]: r for r in w.live()}
    res = [p for p in w.pushes if "WON" in p["title"] or "LOST" in p["title"]]
    g = lr["gold_0530_down"]
    check("e4. the result from Kalshi's own fills: gold WON +$13.44 - fee; one push for the window's result with today's $ and the record",
          g["result"] == "won" and abs(g["pnl"] - round(28 - 14.56 - KC.fee(0.52, 28), 2)) < 0.011 and len(res) == 1
          and "Live so far: 1 bet, 1 won" in res[0]["body"], (lr, res))
    w.run_until(loop, OPEN_PM + 25)
    pm = [r for r in w.live() if r["leg"].endswith("1700_up")]
    check("e5. the evening: gold + silver UP bought (side bid at the YES ask 50c); the 16:00 silver leg stays paper only",
          len(pm) == 2 and all(r["side"] == "yes" for r in pm) and not any(r["leg"] == "silver_1615_down" for r in w.live())
          and any(r["leg"] == "silver_1615_down" for r in w.paper()), pm)
    return w


# ================================================================================================ f. stops
def part_stops(tmp):
    w = World(tmp, "killrule")
    w.arm()
    P = KC.paths(w.sd)
    rs = [{"id": f"x{i}", "day": "2026-11-01", "leg": "gold_0530_down", "open_t": T, "result": "won" if i < 34 else "lost", "pnl": 1.0 if i < 34 else -1.0,
           "cost": 1.0, "status": "settled"} for i, T in enumerate(range(60))]
    KC.save_rows(P["clock_live"], rs)
    loop = w.loop()
    w.run_until(loop, OPEN_AM + 25)
    check("f1. the kill rule: 34 of 60 live bets won (57%, under 58%) = OFF + one HIGH push, no order; arming again refused",
          not w.posts() and (KL._jread(P["arm"], {}) or {}).get("armed") is False and any("STOPPED" in p["title"] and p["priority"] == "high" for p in w.pushes)
          and not w.arm()[0], w.pushes)

    w = World(tmp, "drawdown")
    w.arm()
    P = KC.paths(w.sd)
    KC.save_rows(P["clock_live"], [{"id": "a", "day": "2026-11-01", "leg": "gold_0530_down", "open_t": 1, "result": "won", "pnl": 20.0, "cost": 10, "status": "settled"},
                                   {"id": "b", "day": "2026-11-02", "leg": "gold_0530_down", "open_t": 2, "result": "lost", "pnl": -95.0, "cost": 95, "status": "settled"}])
    killed, why = KC.kill_state(w.sd)
    check("f2. the drawdown rule: +$20 then -$95 = -$95 from the peak (limit -$75) = killed", killed and "from its peak" in why, why)
    w = World(tmp, "avgprice")
    P = KC.paths(w.sd)
    KC.save_rows(P["clock_live"], [{"id": f"p{i}", "day": "2026-11-01", "leg": "gold_1700_up", "open_t": i, "result": "won" if i % 3 else "lost",
                                    "pnl": 5.0 if i % 3 else -4.0, "cost": 14.0, "price": 0.60, "status": "settled"} for i in range(30)])
    killed, why = KC.kill_state(w.sd)
    check("f2b. the price rule (red team): the last 30 live bets paid 60c on average (limit 58c: the edge is being eaten) = killed",
          killed and "60.0c on average" in why, why)

    w = World(tmp, "errors")
    w.arm()
    w.fake.fail[("POST", "/portfolio/events/orders")] = (400, "invalid_parameters")
    loop = w.loop()
    w.run_until(loop, OPEN_AM + 25)
    w.run_until(loop, OPEN_PM + 25)
    P = KC.paths(w.sd)
    check("f3. 3 errors in a row (Kalshi refusing orders) = OFF + a push; it stops trying (at most 3 orders sent)",
          len(w.posts()) == 3 and (KL._jread(P["arm"], {}) or {}).get("armed") is False and any("errors in a row" in p["title"] for p in w.pushes),
          (len(w.posts()), w.pushes))

    w = World(tmp, "key401")
    w.arm()
    loop = w.loop()
    loop._live = KL.Api(key_id=TL.KEY_ID, key=TL.keypair("ed")[0], http=w.fake, sleep=lambda s: None, clock=w.clock, gap=0)
    w.run_until(loop, OPEN_AM + 25)
    check("f4. Kalshi refuses the key (401): OFF at once, no order", not w.posts() and (KL._jread(KC.paths(w.sd)["arm"], {}) or {}).get("armed") is False,
          w.pushes)

    w = World(tmp, "thin")
    w.arm()
    w.books(depth=5)                                       # 5 + 5 contracts on the book: under half of 28
    loop = w.loop()
    w.run_until(loop, OPEN_AM + 50)
    pr = {r["leg"]: r for r in w.paper()}
    tries = len([c for c in w.fake.calls if c[0] == "GET" and c[1].endswith("26NOV190530-30/orderbook")])
    check("f5. a thin book (10 contracts under the cap, 28 wanted): read again at +30 s and +40 s, then skipped ('book too thin'); no order",
          not w.posts() and pr["gold_0530_down"]["status"] == "skip" and "too thin" in pr["gold_0530_down"]["why"] and tries >= 6, (pr, tries))

    w = World(tmp, "cash", cash=20.0)
    w.arm()
    loop = w.loop()
    w.run_until(loop, OPEN_AM + 25)
    w.run_until(loop, OPEN_PM + 25)
    check("f6. cash on Kalshi below the bet ($20): the morning bet ($14.8) goes in, the evening ones are skipped (cash left $5)",
          len(w.posts()) == 1, w.posts())

    w = World(tmp, "changed")
    w.arm()
    raw = KL._jread(KC.CFG_PATH, {})
    loop = w.loop()
    KL._jwrite(KC.stake_path(w.sd), {"stake": 10})        # the armed settings changed (another bet size) without the phrase
    w.run_until(loop, OPEN_AM + 25)
    check("f6b. the armed settings changed without the phrase: no order, OFF and one push saying why", not w.posts() and raw
          and any("STOPPED" in p["title"] and "changed" in p["title"] for p in w.pushes), w.pushes)

    w = World(tmp, "stop")
    w.arm()
    from engine import kalshi_web as KW
    KW._S.update(state_dir=w.sd, env=w.env, http=w.fake, clock=w.clock, spawn=lambda sd: 1)
    KW.do_stop()
    loop = w.loop()
    w.run_until(loop, OPEN_AM + 25)
    check("f7. the phone STOP: OFF + the kill switch before the window: no live order, the paper ledger still records",
          not w.posts() and len(w.paper()) == 2 and os.path.exists(KL.paths(w.sd)["kill"]), (w.posts(), w.paper()))


# ================================================================================================ g. clock offset
def part_clock(tmp):
    w = World(tmp, "offset")
    w.clock.t = OPEN_AM - 300
    fast = 12.0                                             # the PC's clock is 12 s ahead of Kalshi's
    pc = TL.Clock(w.clock() + fast)

    def date_fn():
        import email.utils
        return pc(), email.utils.formatdate(int(w.clock()), usegmt=True)
    loop = KC.ClockLoop(state_dir=w.sd, env=w.env, clock=pc, public_api=KL.Api(http=w.fake, sleep=lambda s: None, clock=w.clock, gap=0),
                        poster=w.poster, alert_cfg={}, date_fn=date_fn)
    loop.sync(force=True)
    while w.clock() < OPEN_AM + 25:
        wait = loop.step()
        step = max(0.5, min(wait, 30))
        w.clock.add(step)
        pc.add(step)
    g = next((r for r in w.paper() if r["leg"] == "gold_0530_down"), {})
    check("g1. the PC clock 12 s fast: Kalshi's Date header corrects it; the entry is at +20 s Kalshi time (not +8 s)",
          abs(loop.offset - (fast - 0.5)) < 1.01 and g and abs(g["t"] - (OPEN_AM + 20)) <= 2, (loop.offset, g.get("t"), OPEN_AM + 20))


# ================================================================================================ w. the phone page
def part_web(tmp):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from engine import kalshi_web as KW
    from engine import live_site as LS
    from engine import phone_safety as PS
    w = World(tmp, "web", cash=180.0)
    os.remove(os.path.join(w.home, "kalshi", "kalshi_key.pem"))
    os.remove(os.path.join(w.home, "kalshi", "key_id.txt"))
    KW._S.update(state_dir=w.sd, env=w.env, http=w.fake, clock=w.clock, spawn=lambda sd: 4242)
    KW._HITS.clear()
    app = FastAPI()
    LS.install(app)
    PS.install(app, None, None)                                # the Kalshi page comes with the phone safety install (server.py)
    from tests import test_phone_safety as TPS
    c = TestClient(app, follow_redirects=False, client=(TPS.LINK_C, 0), base_url="https://" + TPS.TS_HOST)
    wc = TestClient(app, follow_redirects=False, client=("192.168.1.50", 50000), base_url="http://192.168.1.20:8766")
    link = dict(TL_LINK_H)
    page = c.get("/kalshi-live/", headers=link)
    wifi = wc.get("/kalshi-live/")
    check("w1. GET /kalshi-live/ over the owner's Tailscale link: the page (key, bet size, phrase box, STOP); from the WiFi: 403",
          page.status_code == 200 and "STOP" in page.text and "Start LIVE" in page.text and 'id="pk"' in page.text and wifi.status_code == 403,
          (page.status_code, wifi.status_code))
    pem = w.key.private_bytes(TL.serialization.Encoding.PEM, TL.serialization.PrivateFormat.PKCS8, TL.serialization.NoEncryption()).decode()
    pasted = pem.replace("\n", " ")                            # an iPhone paste can lose the line breaks
    bad = c.post("/kalshi-live/key", headers={**link, "content-type": "application/json"}, json={"key_id": TL.KEY_ID, "private_key": pasted})
    r = c.post("/kalshi-live/key", headers={**link, **TL_PAGE_H}, json={"key_id": TL.KEY_ID, "private_key": pasted})
    kdir = os.path.join(w.home, "kalshi")
    logs = open(os.path.join(w.sd, "web_log.jsonl"), encoding="utf-8").read() if os.path.exists(os.path.join(w.sd, "web_log.jsonl")) else ""
    body_txt = pasted.split()[4][:20]
    check("w2. the key pasted on the phone: refused without the page's header; with it saved OUTSIDE the repo (OLYMPUS_HOME\\kalshi), "
          "checked with one balance read: 'Key OK · balance $180.00'; the key is never echoed or logged",
          bad.status_code == 403 and r.json().get("ok") and "Key OK" in r.json()["said"] and "$180.00" in r.json()["said"]
          and os.path.isfile(os.path.join(kdir, "kalshi_key.pem")) and not KL.inside_repo(kdir) and body_txt not in r.text and body_txt not in logs
          and TL.KEY_ID not in logs, (bad.status_code, r.text[:200]))
    st = c.get("/kalshi-live/status", headers=link).json()
    check("w3. the status: key OK + balance, PAPER (not armed), the 3 live legs + the paper-only ones, the caps, the red team's line, the bankroll warning "
          "at $15 with $180 (the bankroll rule: 'needs about $333 ... use $8.00 a bet'), the K8 status card's kill distances + next window",
          st["key"]["ok"] and st["key"]["balance"] == 180.0 and not st["live"]
          and st["phrase"] == KL.PHRASE and len([x for x in st["legs"] if x["live"]]) == 3 and "needs about $333" in st["warn"]
          and "use $8.00 a bet" in st["warn"] and st["bankroll"]["rule"]["stake_usd"] == 8.0 and not st["bankroll"]["fits"]
          and st["dist"]["week"]["stop"] == 150 and st["dist"]["ledger"] == "paper" and st["next_t"] and st["now_t"] and st["red_team"].startswith("Red team: paper first (about 4 weeks)") and 'id="redteam"' in page.text, st)
    wrong = c.post("/kalshi-live/arm", headers={**link, **TL_PAGE_H}, json={"phrase": "I ACCEPT LIVE RISK", "stake": 8}).json()
    arm = c.post("/kalshi-live/arm", headers={**link, **TL_PAGE_H}, json={"phrase": KL.PHRASE.lower(), "stake": 8}).json()
    arm2 = c.post("/kalshi-live/arm", headers={**link, **TL_PAGE_H}, json={"phrase": "  " + KL.PHRASE.replace(" ", "  ") + " ", "stake": 8}).json()
    st2 = c.get("/kalshi-live/status", headers=link).json()
    check("w4. the futures phrase and a lower-case phrase never arm; the exact phrase (extra spaces ok) + $8 arms LIVE at $8 a bet",
          not wrong["ok"] and not arm["ok"] and arm2["ok"] and "$8.00 a bet" in arm2["said"] and st2["live"] and st2["stake"] == 8.0, (wrong, arm, arm2, st2))
    stop = c.post("/kalshi-live/stop", headers={**link, **TL_PAGE_H}, json={}).json()
    st3 = c.get("/kalshi-live/status", headers=link).json()
    check("w5. STOP (one tap): OFF at once, the kill switch file, the answer says paper keeps recording", stop["ok"] and not st3["live"]
          and os.path.exists(KL.paths(w.sd)["kill"]) and "paper keeps recording" in stop["said"], (stop, st3["why"]))
    other = c.post("/api/live/arm", headers={**link, **TL_PAGE_H}, json={"phrase": "I ACCEPT LIVE RISK"})
    check("w6. over the link only these 3 Kalshi buttons pass: any other POST (the futures bot's arm) is still refused (403)", other.status_code == 403,
          other.status_code)
    src = open(os.path.join(ROOT, "engine", "kalshi_web.py"), encoding="utf-8").read()
    code = src.split('"""', 2)[2].split("PAGE =")[0]                # the code, without the docstring
    check("w7. the page module never imports the futures bot (live / ninjatrader / go / server) and never reads ntfy (nothing over ntfy arms)",
          not re.search(r"from engine import (live|ninjatrader|go)\b|import server|ntfy|notify", code), "")


TL_LINK_H = TL_PAGE_H = None


# ================================================================================================ s. the $55 bankroll rule (night-kalshi8)
def day_books(w, day, ask=0.52, depth=500):
    """Markets + books for every window of `day` on the fake Kalshi (our side's ask = `ask`)."""
    f = w.fake
    for open_t, ids in KC.windows(day, KC.load_config(REAL_CFG)[0]):
        for lid in ids:
            leg = KC.LEG[lid]
            tk = KC.ticker(leg["series"], open_t)
            f.markets[tk] = {"ticker": tk, "event_ticker": tk.rsplit("-", 1)[0], "status": "active", "result": "",
                             "close_time": TL.iso(open_t + 900), "yes_sub_title": "Target Price: $1", "price_ranges": []}
            if leg["side"] == "no":
                f.books[tk] = ([(round(1 - ask, 2), depth)], [(round(ask - 0.02, 2), depth)])
            else:
                f.books[tk] = ([(round(ask - 0.02, 2), depth)], [(round(1 - ask, 2), depth)])


def lose_window(w, loop, open_t, ids):
    """Run one window on the fake clock (jumping the idle hours), then settle every leg as a LOSS for us."""
    w.clock.t = max(w.clock.t, open_t - 30)
    w.run_until(loop, open_t + 50)
    for lid in ids:
        leg = KC.LEG[lid]
        tk = KC.ticker(leg["series"], open_t)
        if w.fake.markets.get(tk, {}).get("status") == "active":
            w.fake.settle(tk, "yes" if leg["side"] == "no" else "no")
    w.run_until(loop, open_t + 17 * 60)


def part_sizing(tmp):
    r55, r20, r100, r999 = KC.bankroll_rule(55), KC.bankroll_rule(20), KC.bankroll_rule(100), KC.bankroll_rule(9999)
    check("s1. the bankroll rule: $55 -> $2.50 a bet (4 contracts at 52c), 3 a day, -$8 a day, -$13.75 a week (25%), OFF at -$19.25 (35%); "
          "$20 -> the $1 minimum (1 contract); $100 -> $4.50; never above the $15 ceiling",
          (r55["stake_usd"], r55["contracts_at_52c"], r55["max_bets_per_day"], r55["daily_loss_stop_usd"], r55["week_loss_stop_usd"],
           r55["kill_drawdown_usd"]) == (2.5, 4, 3, 8, 13.75, 19.25) and r20["stake_usd"] == 1.0 and r100["stake_usd"] == 4.5
          and r999["stake_usd"] == 15.0 and KC.fits(2.5, 55) and not KC.fits(5, 55) and KC.fits(5, None), (r55, r20, r100))
    real = KC.load_config(REAL_CFG)[0]
    sd15 = os.path.join(tmp, "pick15")
    KL._jwrite(KC.stake_path(sd15), {"stake": 15})
    c15, p15 = KC.load_config(REAL_CFG, sd15)
    check("s1b. a $15 pick on the $55 settings is a settings problem (live refuses, with the size to use), never a silent no-bet",
          c15["stake_usd"] == 15 and p15 and "use $2.50" in p15[0] and not KC.load_config(REAL_CFG)[1], p15)
    o = order(count=4, cost=2.08, worst=0.52, stake=2.5)
    v0 = view(cfg=real, balance=55.0)
    ok0 = KC.check_order(o, v0)
    wk = KC.check_order(o, dict(v0, week_worst=-11.70))
    wk_ok = KC.check_order(o, dict(v0, week_worst=-11.50))
    dd = KC.check_order(o, dict(v0, dd_now=15.0, open_all=2.2))
    dd_ok = KC.check_order(o, dict(v0, dd_now=15.0, open_all=0.0))
    big = KC.check_order(order(count=9, cost=4.68, worst=0.52, stake=5.0), v0)
    check("s2. the order gate at $55: 4 contracts at 52c pass; the WEEK stop blocks a bet that could take the week past -$13.75 "
          "(-$11.70 + $2.15 = -$13.85) but not at -$11.50; the drawdown stop blocks when the peak gap + open bets + this bet pass $19.25; "
          "a $5 bet is over the $2.50 a bet", ok0[0] and wk[1] == "WEEK_STOP" and wk_ok[0] and dd[1] == "DD_STOP" and dd_ok[0] and big[1] == "STAKE",
          (ok0, wk, wk_ok, dd, dd_ok, big))
    # end to end: a whole week where EVERY bet loses, on the real $55 settings, armed (the test types the phrase; fake Kalshi)
    KC.CFG_PATH, KL.CLOCK_PATH = REAL_CFG, REAL_CFG
    try:
        w = World(tmp, "w55", cash=55.0)
        mon = dt.date(2026, 11, 16)
        w.clock.t = KC.london_epoch(mon, 10, 14)
        armed = w.arm()
        loop = w.loop()
        day_loss = {}
        for k in range(5):
            d = mon + dt.timedelta(days=k)
            day_books(w, d)
            for t, ids in KC.windows(d, real):
                lose_window(w, loop, t, ids)
            day_loss[str(d)] = round(sum(r.get("pnl") or 0 for r in w.live() if r.get("day") == str(d)), 2)
        week = round(sum(r.get("pnl") or 0 for r in w.live()), 2)
        n_week = len([r for r in w.live() if r.get("status") == "settled"])
        logs = open(KL.paths(w.sd)["log"], encoding="utf-8").read()
        sizes = {(r.get("n"), r.get("price")) for r in w.live()}
        paper_n = len(w.paper())
        check("s3. a week where every bet loses (real $55 settings, armed): every live bet is 4 contracts at 52c ($2.15 with the fee); "
              "no day loses more than $8; the week stops at -$13.75 or less (WEEK_STOP logged); paper keeps recording every leg",
              armed[0] and sizes == {(4, 0.52)} and min(day_loss.values()) >= -8.0 - 1e-9 and -13.75 - 1e-9 <= week < -10
              and '"code":"WEEK_STOP"' in logs and paper_n == 5 * 5, (armed, sizes, day_loss, week, n_week, paper_n))
        # the next week: the week stop resets; Monday's bets go in and lose; then the drawdown stop (-$19.25) turns live OFF
        pushes0 = len(w.pushes)
        for k in range(2):
            nxt = mon + dt.timedelta(days=7 + k)
            day_books(w, nxt)
            for t, ids in KC.windows(nxt, real):
                lose_window(w, loop, t, ids)
        total = round(sum(r.get("pnl") or 0 for r in w.live()), 2)
        stops = [p for p in w.pushes[pushes0:] if "STOPPED" in p["title"]]
        live_now = KL.arm_state(P=KC.paths(w.sd), env=w.env)[0]
        card = KL.read_card(now=w.clock(), state_dir=w.sd)
        k8 = (card or {}).get("k8") or {}
        check("s5. the PC's public card carries the K8 status block (live ledger, bankroll $55, $2.50 a bet, today, the last 10 as W/L, week + "
              "drawdown used vs the stop, the next window) inside the card budget; no ticker, no order id",
              k8.get("m") == "L" and k8.get("b") == 55 and k8.get("s") == 2.5 and set(k8.get("l") or "") == {"L"} and len(k8.get("l") or "") == min(10, len([r for r in w.live() if r.get("status") == "settled"]))
              and k8["wk"][1] == 13.75 and k8["dd"][1] == 19.25 and k8.get("nx") and len(json.dumps(card, separators=(",", ":"))) <= KL.CARD_MAX
              and "KXGOLD" not in json.dumps(card) and "ord" not in json.dumps(card), card)
        check("s4. the next week: the week stop resets (Monday's bets go in), then the drawdown stop turns live OFF before the record can "
              "pass -$19.25 from the peak (one STOPPED push); the total loss never passes 35% of $55",
              total >= -19.25 - 1e-9 and total < week and stops and not live_now and "drawdown" in stops[0]["title"], (total, week, [p["title"] for p in w.pushes[pushes0:]], live_now))
    finally:
        KC.CFG_PATH, KL.CLOCK_PATH = FIX15, FIX15


# ================================================================================================ r. red team 2026-11-21: never forget a bet
def part_redteam(tmp):
    w = World(tmp, "lost_answer")
    w.arm()
    w.fake.lose = "502"
    loop = w.loop()
    w.run_until(loop, OPEN_AM + 25)
    lr = w.live()
    v = loop.live_view(w.clock())
    check("r1. Kalshi takes the order but the answer is lost (502): the bet is KEPT as 'check' (not forgotten), counted by the stops "
          "(1 bet today, today's worst case = its cost + fee) and by one-bet-per-market",
          len(w.posts()) == 1 and len(lr) == 1 and lr[0]["status"] == "check" and v["bets_today"] == 1 and lr[0]["ticker"] in v["tickers_today"]
          and abs(v["day_worst"] + lr[0]["cost"] + lr[0]["fee"]) < 1e-6, (len(w.posts()), lr, v["bets_today"], v["day_worst"]))
    w.fake.lose = None
    loop2 = w.loop()
    w.run_until(loop2, OPEN_AM + 44)
    check("r2. a restart inside the same window: NO second order on that market", len(w.posts()) == 1, len(w.posts()))
    w.settle(OPEN_AM, {"KXGOLD15M": "no", "KXSILVER15M": "yes"})
    w.run_until(loop2, OPEN_AM + 17 * 60)
    g = w.live()[0]
    check("r3. after the settle it is booked from Kalshi's own fills for the market: WON, the real contracts, cost and fee",
          g["result"] == "won" and g["status"] == "settled" and g["n"] == int(lr[0]["n"]) and abs(g["pnl"] - round(g["n"] - g["cost"] - g["fee"], 2)) < 0.011, g)

    w = World(tmp, "died")
    w.arm()
    w.fake.lose = "die"
    loop = w.loop()
    try:
        w.run_until(loop, OPEN_AM + 25)
    except Died:
        pass
    on_disk = w.live()
    loop2 = w.loop()
    w.run_until(loop2, OPEN_AM + 44)
    check("r4. the PC dies in the middle of sending (Kalshi has the order): the row was saved BEFORE the send ('posting'); "
          "after the restart no second order, and it is still counted",
          len(on_disk) == 1 and on_disk[0]["status"] == "posting" and len(w.posts()) == 1 and loop2.live_view(w.clock())["bets_today"] == 1,
          (on_disk, len(w.posts())))
    w.settle(OPEN_AM, {"KXGOLD15M": "yes", "KXSILVER15M": "yes"})
    w.run_until(loop2, OPEN_AM + 17 * 60)
    g = w.live()[0]
    check("r5. ... and it settles from the fills: LOST its real cost + fee", g["result"] == "lost" and abs(g["pnl"] + g["cost"] + g["fee"]) < 0.011, g)

    w = World(tmp, "refused")
    w.arm()
    w.fake.fail[("POST", "/portfolio/events/orders")] = (400, "invalid_parameters")
    loop = w.loop()
    w.run_until(loop, OPEN_AM + 25)
    check("r6. a CLEAR refusal (HTTP 400): no live row left (nothing to count), one error", len(w.posts()) == 1 and not w.live()
          and int(loop.st.get("err") or 0) == 1, (w.live(), loop.st.get("err")))


def main():
    global TL_LINK_H, TL_PAGE_H
    from tests import test_phone_safety as TPS
    TL_LINK_H, TL_PAGE_H = TPS.LINK_H, TPS.PAGE_H
    tmp = tempfile.mkdtemp(prefix="kalshiclock-")
    try:
        part_calendar()
        part_entry()
        part_caps()
        part_paper(tmp)
        part_live(tmp)
        part_stops(tmp)
        part_clock(tmp)
        part_web(tmp)
        part_sizing(tmp)
        part_redteam(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
