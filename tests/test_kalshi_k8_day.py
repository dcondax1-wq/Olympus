"""K8 ready for Monday (day-kalshi 2026-11-20): the rehearsal of Monday Nov 23 through the REAL bot code, every size / stop rule on
the REAL $55 settings, restarts mid-day, and proof that nothing can send an order without the owner's key + typed phrase.
Fake Kalshi, fake clock, temp folders, a FAKE key: no network, no real order (every arm here is the test typing the phrase into a temp folder).

  r. rehearsal  Monday's 3 sessions replayed from recorded PUBLIC Kalshi trades (research/kalshi_k8_day/rehearsal.py): paper = no order,
                5 paper rows; live = exactly 3 orders on Monday's tickers, the right side, whole contracts within $2.50, good till +40 s,
                Kalshi's result and the exact $; the phone pushes (placed / settled / the day's summary)
  k. restart    a new bot mid-day (12:00 ET) keeps today's counters (bets, $ at risk, the week, the peak) and never sends the morning bet
                twice; a restart INSIDE a window does not send a 2nd order; a day already near the stop stays blocked after a restart
  s. stops      on the $55 settings: day -$8, week -$13.75, from the peak -$19.25, 3 bets a day, one bet a market, the price cap, the
                win-rate kill (under 58% after 60 bets; not before 60), the price-creep kill (last 30 paid over 58c; not under 30 bets)
  f. fees       4 contracts pay 7c (1.75c each), 1-3 contracts pay 2c each; the paper and live ledgers use exactly that
  d. data+docs  tools/web_public/kalshi/k8.json is up to date with the recorded public tape, has every field the phone reads, the
                fair price = win rate - fee; docs/KALSHI.md has the 3 Monday steps, the phrase, the phone pushes, no key
  o. orders     wrong / lower-case phrase, a hand-made arm file, no key on the PC, the kill switch, LE_KALSHI_LIVE=0: no order (paper
                keeps recording); the only order call in the code sits behind the order gate

  python -X utf8 -m tests.test_kalshi_k8_day
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
sys.path.insert(0, os.path.join(ROOT, "research", "kalshi_k8_day"))

from tests import test_kalshi_clock as TC  # noqa: E402  (World + the fake Kalshi; it points KC at the $15 fixture: reset below)
from tests import test_kalshi_live as TL  # noqa: E402
from engine import kalshi_clock as KC  # noqa: E402
from engine import kalshi_live as KL  # noqa: E402
import rehearsal as R  # noqa: E402

REAL = R.REAL
RES: list = []
MON = R.MONDAY


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + ("" if cond else f"  -> {str(info)[:600]}"), flush=True)
    return bool(cond)


def real():
    KC.CFG_PATH = KL.CLOCK_PATH = REAL
    return KC.load_config(REAL)[0]


# ================================================================================================ r. the rehearsal
def part_rehearsal(tmp):
    T = R.tape()
    cfg = real()
    days = [d for d in (dt.date(2026, 11, 17), dt.date(2026, 11, 19)) if d in R.source_days(T, cfg, 8)]
    check("r0. the recorded public tape has the 3 live legs of Nov 17 and Nov 19 (the scenarios)", len(days) == 2, days)
    mon_tk = {lid: KC.ticker(KC.LEG[lid]["series"], o) for o, ids in KC.windows(MON, cfg) for lid in ids}
    check("r0b. Monday's tickers: KXGOLD15M-26NOV230530-30 (05:15 ET), KXGOLD15M-26NOV231700-00 + KXSILVER15M-26NOV231700-00 (16:45 ET)",
          mon_tk.get("gold_0530_down") == "KXGOLD15M-26NOV230530-30" and mon_tk.get("gold_1700_up") == "KXGOLD15M-26NOV231700-00"
          and mon_tk.get("silver_1700_up") == "KXSILVER15M-26NOV231700-00", mon_tk)
    want = {"2026-11-17": (0, -7.15), "2026-11-19": (1, -2.05)}
    for d in days:
        w, armed, _, info = R.run_day(d, "paper", tmp, T)
        pr = w.paper()
        check(f"r1. like {d}, PAPER (not armed): 5 paper rows on Monday's tickers, every one settled with Kalshi's result, NO order sent",
              not armed[0] and not w.posts() and len(pr) == 5 and all("26NOV23" in r["ticker"] for r in pr)
              and all(r.get("result") in ("won", "lost") for r in pr if r.get("status") != "skip"), [(r["leg"], r.get("status"), r.get("result")) for r in pr])
        w, armed, _, info = R.run_day(d, "live", tmp, T)
        lr, posts = w.live(), [c[3] for c in w.posts()]
        open_of = {"gold_0530_down": KC.london_epoch(MON, 10, 15), "gold_1700_up": KC.et_epoch(MON, 16, 45), "silver_1700_up": KC.et_epoch(MON, 16, 45)}
        sides_ok = all(p["side"] == ("ask" if "0530" in p["ticker"] else "bid") for p in posts)
        size_ok = all(r["n"] >= 1 and r["cost"] <= 2.5 + 1e-9 and float(r["n"]) == int(r["n"]) for r in lr)
        exp_ok = all(int(p["expiration_time"]) == int(open_of[r["leg"]] + 40) for p, r in zip(posts, lr))
        pnl_ok = all(abs(((r["n"] if r["result"] == "won" else 0) - r["cost"] - r["fee"]) - r["pnl"]) < 0.006 for r in lr)
        rec = {KC.ticker(KC.LEG[r["leg"]]["series"], KC.leg_open(KC.LEG[r["leg"]], d)): r for r in lr}
        res_ok = all(r["result"] == ("won" if T[tk]["res"] == KC.LEG[r["leg"]]["side"] else "lost") for tk, r in rec.items())
        won, net = sum(1 for r in lr if r["result"] == "won"), round(sum(r["pnl"] for r in lr), 2)
        check(f"r2. like {d}, LIVE (fake key): exactly 3 orders, one per live leg on Monday's tickers; DOWN = sell YES, UP = buy YES; "
              f"whole contracts within $2.50; good till open + 40 s; Kalshi's result; $ = contracts - cost - fee: {won} of 3 won, {KL.money(net, True)}",
              armed[0] and len(posts) == 3 and len({p["ticker"] for p in posts}) == 3 and all("26NOV23" in p["ticker"] for p in posts)
              and sides_ok and size_ok and exp_ok and pnl_ok and res_ok and (won, net) == want[str(d)],
              {"armed": armed, "posts": posts, "rows": [(r["leg"], r["n"], r["price"], r["result"], r["pnl"]) for r in lr]})
        v = info["views"][0] if info["views"] else {}
        check(f"r3. like {d}: the restart at 12:00 ET keeps today's counters (bets {v.get('bets_today')}, $ today {v.get('day_worst')}, "
              "week, peak) and the evening sends only the 2 evening orders (the morning bet is never sent twice)",
              info["restarts"] == 1 and v and all(a == b for a, b in (v[k] for k in ("bets_today", "day_worst", "week_worst", "open_all", "dd_now")))
              and v["tickers_same"] and v["bets_today"][0] == 1 and len([p for p in posts if "0530" in p["ticker"]]) == 1, info["views"])
        titles = [p["title"] for p in w.pushes]
        check(f"r4. like {d}: the phone gets 'Kalshi LIVE 05:15 ET: 1 bet in', the 05:30 result, '16:45 ET: 2 bets in', the 17:00 results, "
              "and one day summary (5 pushes, no key, no ticker id in any)",
              len(titles) == 5 and titles[0].startswith("Kalshi LIVE 05:15 ET: 1 bet in") and titles[1].startswith("Kalshi LIVE 05:30:")
              and titles[2].startswith("Kalshi LIVE 16:45 ET: 2 bets in") and titles[3].startswith("Kalshi LIVE 17:00:")
              and titles[4].startswith("Kalshi K8 Mon Nov 23: LIVE") and not any("KXGOLD" in (p["title"] + p["body"]) or "PRIVATE" in p["body"] for p in w.pushes),
              titles)


# ================================================================================================ k. restarts
def live_row(day, leg, open_t, pnl=None, n=4, price=0.52, result=None, status="settled"):
    cost = round(n * price, 4)
    return {"id": f"{day}:{leg}", "day": day, "leg": leg, "ticker": KC.ticker(KC.LEG[leg]["series"], open_t), "side": KC.LEG[leg]["side"],
            "open_t": open_t, "n": n, "price": price, "cost": cost, "fee": KC.fee(price, n), "status": status, "result": result, "pnl": pnl}


def part_restart(tmp):
    cfg = real()
    T = R.tape()
    # a restart INSIDE the morning window (+25 s, after the order went in): the window is done, no 2nd order
    w = TC.World(tmp, "k1", cash=55.0)
    o = KC.london_epoch(MON, 10, 15)
    d = dt.date(2026, 11, 19)
    for lid in cfg["paper_legs"]:
        leg = KC.LEG[lid]
        tk = KC.ticker(leg["series"], KC.leg_open(leg, MON))
        w.fake.markets[tk] = {"ticker": tk, "event_ticker": tk.rsplit("-", 1)[0], "status": "active", "result": "",
                              "close_time": TL.iso(KC.leg_open(leg, MON) + 900), "yes_sub_title": "Target", "price_ranges": []}
        rec = T.get(KC.ticker(leg["series"], KC.leg_open(leg, d)))
        w.fake.books[tk] = R.book_from_tape(rec["tr"], leg["side"], 20.0) if rec else ([], [])
    w.clock.t = o - 60
    w.arm()
    loop = w.loop()
    w.run_until(loop, o + 25)
    n1 = len(w.posts())
    loop = w.loop()                                     # restart inside the window
    w.run_until(loop, o + 60)
    check("k1. a restart 25 s after the 05:15 open (the order already in): the new bot does not send a 2nd order for that window",
          n1 == 1 and len(w.posts()) == 1 and len(w.live()) == 1, (n1, len(w.posts()), w.live()))
    # a day already -$6.00 (settled) on disk: after a restart the bot sees -$6.00 and the next $2.15 bet is over the -$8 day stop
    w2 = TC.World(tmp, "k2", cash=55.0)
    sd = KC.paths(w2.sd)
    day = str(MON)
    o_am, o_pm = KC.london_epoch(MON, 10, 15), KC.et_epoch(MON, 16, 45)
    KC.save_rows(sd["clock_live"], [live_row(day, "gold_0530_down", o_am, pnl=-6.0, n=11, price=0.53, result="lost")])
    w2.clock.t = o_pm - 300
    w2.arm()
    lp = w2.loop()
    v = lp.live_view(lp.now())
    o_ = {"ticker": KC.ticker("KXGOLD15M", o_pm), "side": "yes", "count": 4, "cost": 2.08, "worst": 0.52, "ask": 0.52, "open_t": o_pm,
          "book_t": o_pm + 20, "market": {"status": "active", "close_ts": o_pm + 900}, "stake": 2.5, "cap": 0.7}
    ok, code, _ = KC.check_order(o_, dict(v, now=o_pm + 20, balance=40.0))
    check("k2. restart with today at -$6.00 on disk: the new bot reads bets 1, $ today -$6.00, and blocks a 4 x 52c bet (-$8.15 worst) = DAY_STOP",
          v["bets_today"] == 1 and abs(v["day_worst"] + 6.0) < 1e-9 and not ok and code == "DAY_STOP", (v["bets_today"], v["day_worst"], code))
    # 2 bets in, 1 open: the week, the $ at risk and the 3-a-day count all survive a restart
    KC.save_rows(sd["clock_live"], [live_row(day, "gold_0530_down", o_am, pnl=-2.15, result="lost"),
                                    live_row(day, "gold_1700_up", o_pm, status="sent"), live_row(day, "silver_1700_up", o_pm, status="sent")])
    v1 = w2.loop().live_view(o_pm + 30)
    o2 = dict(o_, ticker=KC.ticker("KXSILVER15M", KC.et_epoch(MON, 16, 0)), open_t=o_pm)
    ok2, code2, _ = KC.check_order(o2, dict(v1, now=o_pm + 20, balance=40.0))
    check("k3. restart with 3 bets today (2 still open): bets 3, the open bets counted as lost ($6.45 at risk), a 4th bet = BETS_DAY",
          v1["bets_today"] == 3 and abs(v1["day_worst"] + 2.15 + 2 * (2.08 + 0.07)) < 1e-6 and abs(v1["open_all"] - 2 * 2.15) < 1e-6
          and not ok2 and code2 == "BETS_DAY", (v1["bets_today"], v1["day_worst"], v1["open_all"], code2))


# ================================================================================================ s. the stops on the $55 settings
def view(cfg, **kw):
    v = {"cfg": cfg, "now": 0, "kill": False, "live": True, "stopped": False, "killed": False, "paused": False, "bets_today": 0,
         "tickers_today": set(), "day_worst": 0.0, "week_worst": 0.0, "balance": 55.0, "dd_now": 0.0, "open_all": 0.0}
    v.update(kw)
    return v


def order(**kw):
    o = {"ticker": "KXGOLD15M-26NOV230530-30", "side": "no", "count": 4, "cost": 2.08, "worst": 0.52, "ask": 0.52, "open_t": 1000.0,
         "book_t": 1019.0, "market": {"status": "active", "close_ts": 1900}, "stake": 2.5, "cap": 0.7}
    o.update(kw)
    return o


def ledger(tmp, name, results, price=0.52):
    sd = os.path.join(tmp, name)
    os.makedirs(sd)
    base = KC.london_epoch(dt.date(2026, 9, 1), 10, 15)
    rs = []
    for i, won in enumerate(results):
        r = live_row(f"2026-09-{1 + i // 3:02d}", "gold_0530_down", base + i * 3600, price=price if not isinstance(price, list) else price[i],
                     n=4, result="won" if won else "lost")
        r["pnl"] = round((4 if won else 0) - r["cost"] - r["fee"], 4)
        r["ticker"] = f"KXGOLD15M-26SEP{i:02d}0530-30"
        rs.append(r)
    KC.save_rows(KC.paths(sd)["clock_live"], rs)
    return sd


def part_stops(tmp):
    cfg = real()
    rule = KC.bankroll_rule(55)
    check("s0. the REAL settings = the $55 rule: $2.50 a bet, 3 a day, day -$8, week -$13.75, OFF -$19.25 from the peak, 58% after 60, 58c on 30",
          (cfg["stake_usd"], cfg["max_bets_per_day"], cfg["daily_loss_stop_usd"], cfg["week_loss_stop_usd"], cfg["kill_drawdown_usd"],
           cfg["kill_min_win_rate"], cfg["kill_after_bets"], cfg["kill_avg_price"], cfg["kill_avg_price_bets"], cfg["bankroll_usd"])
          == (2.5, 3, 8, 13.75, 19.25, 0.58, 60, 0.58, 30, 55) and rule["stake_usd"] == 2.5 and rule["week_loss_stop_usd"] == 13.75, cfg)
    g = lambda o, v: KC.check_order(o, dict(v, now=1020.0))[1]                                       # noqa: E731
    check("s1. a good $55 bet passes (4 at 52c, $2.08 + 7c fee)", g(order(), view(cfg)) == "OK")
    check("s2. DAY stop: today -$5.90 + this bet ($2.15) = -$8.05 < -$8 -> DAY_STOP; at -$5.80 it still fits",
          g(order(), view(cfg, day_worst=-5.90)) == "DAY_STOP" and g(order(), view(cfg, day_worst=-5.80)) == "OK")
    check("s3. WEEK stop: this week -$11.65 + $2.15 = -$13.80 < -$13.75 -> WEEK_STOP; -$11.55 fits",
          g(order(), view(cfg, week_worst=-11.65)) == "WEEK_STOP" and g(order(), view(cfg, week_worst=-11.55)) == "OK")
    check("s4. PEAK stop: $15.00 below the peak + $2.20 open + $2.15 = $19.35 > $19.25 -> DD_STOP; $14.80 + $2.20 + $2.15 fits",
          g(order(), view(cfg, dd_now=15.0, open_all=2.2)) == "DD_STOP" and g(order(), view(cfg, dd_now=14.8, open_all=2.2)) == "OK")
    check("s5. 3 bets a day: the 4th -> BETS_DAY; one bet a market -> ONE_BET; the price above the 70c cap -> PRICE; $2.60 > $2.50 -> STAKE",
          g(order(), view(cfg, bets_today=3)) == "BETS_DAY" and g(order(), view(cfg, tickers_today={"KXGOLD15M-26NOV230530-30"})) == "ONE_BET"
          and g(order(worst=0.71, cost=2.84), view(cfg)) == "PRICE" and g(order(count=5, cost=2.6), view(cfg)) == "STAKE")
    mix = lambda w, n: [i * w // n != (i + 1) * w // n for i in range(n)]       # noqa: E731  (w wins spread evenly over n bets)
    wr = dict(cfg, kill_drawdown_usd=999)            # the win-rate rule on its own (the peak rule is s8)
    k1 = KC.kill_state(ledger(tmp, "wr34", mix(34, 60)), wr)
    k2 = KC.kill_state(ledger(tmp, "wr35", mix(35, 60)), wr)
    k3 = KC.kill_state(ledger(tmp, "wr59", mix(20, 59)), wr)
    check("s6. WIN-RATE kill: 34 of 60 won (56.7%) -> OFF; 35 of 60 (58.3%) -> on; 20 of 59 (only 59 bets) -> not yet",
          k1[0] and "34 of 60" in k1[1] and not k2[0] and not k3[0], (k1, k2, k3))
    ledger(tmp, "wr34b", mix(34, 60))
    ok_arm = KL.arm(KL.PHRASE, state_dir=os.path.join(tmp, "wr34b"), env={"OLYMPUS_HOME": tmp}, now=2e9)
    check("s6b. after the win-rate kill the phrase alone cannot turn live back on ('ask Claude before any restart')",
          not ok_arm[0] and "ask Claude" in ok_arm[1], ok_arm)
    sd = ledger(tmp, "cr59", [True, False] * 15, price=0.59)
    c1 = KC.kill_state(sd, dict(cfg, kill_drawdown_usd=999))
    sd = ledger(tmp, "cr57", [True, False] * 15, price=0.57)
    c2 = KC.kill_state(sd, dict(cfg, kill_drawdown_usd=999))
    sd = ledger(tmp, "cr29", [True, False] * 14 + [True], price=0.65)
    c3 = KC.kill_state(sd, dict(cfg, kill_drawdown_usd=999))
    check("s7. PRICE-CREEP kill: the last 30 paid 59c on average (> 58c) -> OFF; 57c -> on; 29 bets at 65c -> not yet (needs 30)",
          c1[0] and "59.0c" in c1[1] and not c2[0] and not c3[0], (c1, c2, c3))
    sd = ledger(tmp, "dd", [False] * 9)
    d1 = KC.kill_state(sd, cfg)
    check("s8. PEAK kill on the record: 9 straight losses at 4 x 52c = -$19.35 from the peak -> OFF (limit -$19.25)", d1[0] and "from its peak" in d1[1], d1)


# ================================================================================================ f. fees
def part_fees(tmp):
    f = KC.fee
    check("f1. 4 contracts pay 7c in all = 1.75c each (52c and 50c); 5 at 50c pay 9c (1.8c each)",
          (f(0.52, 4), f(0.50, 4), f(0.50, 5)) == (0.07, 0.07, 0.09) and abs(f(0.52, 4) / 4 - 0.0175) < 1e-12, (f(0.52, 4), f(0.50, 4), f(0.50, 5)))
    check("f2. 1, 2 and 3 contracts pay 2c each (2c, 4c, 6c at 52c; the fee is rounded UP to the cent per order)",
          (f(0.52, 1), f(0.52, 2), f(0.52, 3)) == (0.02, 0.04, 0.06), (f(0.52, 1), f(0.52, 2), f(0.52, 3)))
    check("f3. the fee is 0.07 x contracts x price x (1 - price), rounded up: 6 at 41c = 11c, 4 at 58c = 7c",
          (f(0.41, 6), f(0.58, 4)) == (0.11, 0.07), (f(0.41, 6), f(0.58, 4)))
    p = os.path.join(ROOT, "research", "kalshi_k8_day", "rehearsal.json")
    j = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"scenarios": []}
    bets = [b for s in j["scenarios"] for b in s["bets"] if b.get("n")]
    check("f4. every bet of the saved rehearsal paid exactly fee(price, contracts) (paper and live ledgers)",
          bets and all(abs(KC.fee(b["cost"] / b["n"], int(b["n"])) - b["fee"]) < 1e-9 for b in bets), len(bets))


# ================================================================================================ o. nothing sends an order without key + phrase
def morning(w, T):
    cfg = real()
    d = dt.date(2026, 11, 19)
    o = KC.london_epoch(MON, 10, 15)
    for lid in cfg["paper_legs"]:
        leg = KC.LEG[lid]
        tk = KC.ticker(leg["series"], KC.leg_open(leg, MON))
        w.fake.markets[tk] = {"ticker": tk, "event_ticker": tk.rsplit("-", 1)[0], "status": "active", "result": "",
                              "close_time": TL.iso(KC.leg_open(leg, MON) + 900), "yes_sub_title": "Target", "price_ranges": []}
        rec = T.get(KC.ticker(leg["series"], KC.leg_open(leg, d)))
        w.fake.books[tk] = R.book_from_tape(rec["tr"], leg["side"], 20.0) if rec else ([], [])
    w.clock.t = o - 60
    return o


def part_orders(tmp):
    T = R.tape()
    real()
    out = {}
    for name in ("lower", "short", "handmade", "nokey", "kill", "env0"):
        w = TC.World(tmp, "o-" + name, cash=55.0)
        o = morning(w, T)
        env = dict(w.env)
        if name == "lower":
            out[name + "_arm"] = KL.arm(KL.PHRASE.lower(), state_dir=w.sd, env=env, now=w.clock())
        elif name == "short":
            out[name + "_arm"] = KL.arm("I ACCEPT KALSHI RISK", state_dir=w.sd, env=env, now=w.clock())
        elif name == "handmade":
            os.makedirs(KC.paths(w.sd)["dir"], exist_ok=True)
            A = KL.load_all(state_dir=w.sd)
            KL._jwrite(KC.paths(w.sd)["arm"], {"armed": True, "t": int(w.clock()), "exec": KL.EXEC_VERSION, "sha": A["sha"], "proof": "0" * 64})
        else:
            out[name + "_arm"] = w.arm()
        if name == "nokey":
            shutil.rmtree(os.path.join(w.home, "kalshi"))
        if name == "kill":
            open(KC.paths(w.sd)["kill"], "w").close()
        if name == "env0":
            env["LE_KALSHI_LIVE"] = "0"
        if name == "nokey":                              # the bot's own key loader (no injected key): the PC with no key file
            loop = KC.ClockLoop(state_dir=w.sd, env=env, clock=w.clock, public_api=KL.Api(http=w.fake, sleep=lambda s: None, clock=w.clock, gap=0),
                                live_api=None, poster=w.poster, alert_cfg={"ntfy": "https://ntfy.example", "topic": "t"},
                                date_fn=lambda: (w.clock(), None))
        else:
            api = KL.Api(key_id=TL.KEY_ID, key=w.key, http=w.fake, sleep=lambda s: None, clock=w.clock, gap=0)
            loop = KC.ClockLoop(state_dir=w.sd, env=env, clock=w.clock, public_api=KL.Api(http=w.fake, sleep=lambda s: None, clock=w.clock, gap=0),
                                live_api=api, poster=w.poster, alert_cfg={"ntfy": "https://ntfy.example", "topic": "t"}, date_fn=lambda: (w.clock(), None))
        w.run_until(loop, o + 60)
        out[name] = (len(w.posts()), len(w.paper()), len(w.live()))
    check("o1. a lower-case phrase and a phrase with a word missing never arm",
          not out["lower_arm"][0] and not out["short_arm"][0], (out["lower_arm"], out["short_arm"]))
    for name, words in (("lower", "lower-case phrase"), ("short", "wrong phrase"), ("handmade", "an arm file written by hand (no phrase proof)"),
                        ("nokey", "the phrase typed but no key on the PC"), ("kill", "the kill switch file"), ("env0", "LE_KALSHI_LIVE=0 on the PC")):
        p, pa, li = out[name]
        check(f"o2. {words}: no order sent at 05:15, the paper ledger still records the window ({pa} paper rows)", p == 0 and li == 0 and pa >= 1, out[name])
    src = open(os.path.join(ROOT, "engine", "kalshi_clock.py"), encoding="utf-8").read()
    calls = re.findall(r'call\("POST"', src)
    send_calls = re.findall(r"self\.send\(", src)
    body = src[src.index("    def entry("):src.index("    def balance(")]
    gate_first = body.index("check_order(o, dict(v") < body.index("self.send(o")
    check("o3. the code: ONE order call (send), send is called once, right after the order gate passed; send itself re-checks the arm file "
          "and the kill switch", len(calls) == 1 and len(send_calls) == 1 and gate_first and "if not ok:" in body
          and 'get("armed") is not True' in src[src.index("    def send("):src.index("    def send(") + 400], (len(calls), len(send_calls), gate_first))
    a = KL.Api(http=TL.FakeKalshi(TL.Clock(0), None), sleep=lambda s: None, gap=0)
    try:
        a.call("POST", "/portfolio/events/orders", body={"ticker": "KXGOLD15M-26NOV230530-30"})
        refused = False
    except KL.KalshiError as e:
        refused = e.code == "no_key"
    check("o4. the Kalshi client with no key refuses to sign an order ('no Kalshi key on this PC')", refused)


# ================================================================================================ d. the phone's data + the one doc
def part_data():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import kalshi_k8_feed as F
    p = F.OUT
    j = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    check("d1. tools/web_public/kalshi/k8.json exists and matches the recorded public tape (python tools/kalshi_k8_feed.py --check)",
          j and F.main(["--check"]) == 0, p)
    legs = {x.get("id"): x for x in j.get("legs") or []}
    keys = ("code", "name", "live", "tz", "open", "side", "n", "won", "rate", "avg_c", "fair_c", "r30", "r60", "avg30_c", "last10", "last_c")
    check("d2. k8.json: the 5 legs (3 live: g5, g17, s17) with every field the page reads; the pool with r30 / r60 / avg30_c / weeks; the rule = $55",
          set(legs) == set(KC.LEG) and all(all(k in x for k in keys) for x in legs.values())
          and {x["code"] for x in legs.values() if x["live"]} == {"g5", "g17", "s17"}
          and all(k in (j.get("pool") or {}) for k in ("n", "won", "r30", "r60", "avg30_c", "weeks", "net_usd"))
          and (j.get("rule") or {}).get("stake") == 2.5 and (j.get("rule") or {}).get("week_stop") == 13.75 and len(json.dumps(j)) < 20000,
          {k: [x for x in keys if x not in v] for k, v in legs.items()})
    fair_ok = all(x["fair_c"] is None or (x["fair_c"] < 100 * x["rate"] and 100 * x["rate"] - x["fair_c"] < 2.5) for x in legs.values())
    check("d3. the fair price of each leg = its win rate minus the fee (1.75-2c a contract): the price where a bet breaks even", fair_ok,
          [(x["code"], x["rate"], x["fair_c"]) for x in legs.values()])
    doc = open(os.path.join(ROOT, "docs", "KALSHI.md"), encoding="utf-8").read()
    steps = re.findall(r"^\d\. ", doc.split("## Your Monday steps")[1].split("##")[0], re.M) if "## Your Monday steps" in doc else []
    check("d4. docs/KALSHI.md: what runs where, the files, 3 Monday steps (no more), the phrase as a copy line, the phone pushes; no key, no account id, no email",
          len(steps) == 3 and "I ACCEPT KALSHI LIVE RISK" in doc and ":8444/kalshi-live/" in doc and "Kalshi LIVE 16:45 ET: 2 bets in" in doc
          and "data/kalshi_live/" in doc and "PRIVATE KEY" not in doc and "@" not in doc.replace("`", ""), len(steps))


# ================================================================================================ p. the paper card on the PC (lead, 05:36 ET 2026-11-20)
def part_paper_card(tmp):
    """The phone showed 'From the peak (OFF) -$30.65 of -$19.25' and 'Next window 4:00 PM ET': the paper ledger held the old $15
    paper bets of Nov 19 (and the paper-only legs). Display only: no stop reads paper. Now the card shows the live legs at today's
    stake, the next LIVE window, paper keeps recording, and the live ledger starts clean."""
    cfg = real()
    w = TC.World(tmp, "pcard", cash=55.0)
    P = KC.paths(w.sd)
    d19 = dt.date(2026, 11, 19)
    old = []
    for i, lid in enumerate(["gold_0530_down", "silver_0530_down", "silver_1615_down", "gold_1700_up", "silver_1700_up"]):
        o = KC.leg_open(KC.LEG[lid], d19)
        r = live_row(str(d19), lid, o, n=28, price=0.53, result="lost")
        r["pnl"] = round(-r["cost"] - r["fee"], 4)
        old.append(r)
    os.makedirs(P["dir"], exist_ok=True)
    KC.save_rows(P["clock_paper"], old)
    raw_dd = KC.drawdown(old)
    now = KC.london_epoch(dt.date(2026, 11, 20), 10, 14)
    k = KC.card_k8(w.sd, cfg, now)
    check(f"p1. old $15 paper bets (a raw paper drop of ${raw_dd:.2f}) no longer show on the $55 card: from the peak $0 of $19.25",
          raw_dd > 19.25 and k and k["m"] == "P" and k["dd"][0] == 0 and k["wk"][0] == 0, (raw_dd, k))
    nx_pm = KC.card_k8(w.sd, cfg, KC.et_epoch(dt.date(2026, 11, 20), 5, 36))["nx"]
    check("p2. at 05:36 ET the card's next window is 16:45 ET (the live gold/silver UP), not the paper-only 16:00 silver",
          nx_pm == int(KC.et_epoch(dt.date(2026, 11, 20), 16, 45)), (nx_pm, KC.et_epoch(dt.date(2026, 11, 20), 16, 45)))
    T = R.tape()
    o = morning(w, T)
    w.run_until(w.loop(), o + 60)
    new = [r for r in w.paper() if r.get("day") == str(MON)]
    check("p3. paper is never stopped by a paper drop: Monday 05:15 records gold + silver DOWN on paper, no order, the live ledger is empty "
          "(no stop reads paper: the live record starts clean)", len(new) == 2 and not w.posts() and not w.live()
          and not KC.kill_state(w.sd, cfg)[0], (new, KC.kill_state(w.sd, cfg)))


# ================================================================================================ a. each leg's own OFF / ON (round 2)
def part_legswitch(tmp):
    from engine import kalshi_legswitch as LS
    d = LS.decide
    check("a1. the rule (PREREG_legswitch.md): 10 of the last 20 won -> pause; 11 keeps the state; 12 -> resume; under 20 windows -> never",
          d([1] * 10 + [0] * 10)["paused"] and d([1] * 11 + [0] * 9, True)["paused"] and not d([1] * 11 + [0] * 9, False)["paused"]
          and not d([1] * 12 + [0] * 8, True)["paused"] and not d([0] * 19)["paused"])
    x = LS.replay([1] * 20 + [0] * 11)
    check("a2. the record is replayed day by day (the path matters): 20 wins then 11 losses -> paused, 'won 9 of the last 20 (resumes at 12)'",
          x["paused"] and x["why"] == "won 9 of the last 20 (resumes at 12)", x)
    j = json.load(open(os.path.join(ROOT, "research", "kalshi_k8_day", "legswitch.json"), encoding="utf-8"))
    check("a3. the walk-forward verdict decides whether the live bot obeys it: legswitch.json = '" + j["verdict"] + "' and LIVE_ON = " + str(LS.LIVE_ON),
          (j["verdict"] == "ON") == LS.LIVE_ON)
    cfg = real()
    w = TC.World(tmp, "lsw", cash=55.0)
    P = KC.paths(w.sd)
    os.makedirs(P["dir"], exist_ok=True)
    rs = []
    for i in range(20):
        day = dt.date(2026, 10, 1) + dt.timedelta(days=i)
        for lid in cfg["live_legs"]:
            won = (i % 2 == 0) if lid == "silver_1700_up" and i >= 11 else (i % 4 != 3)
            if lid == "silver_1700_up":
                won = i < 9
            r = live_row(str(day), lid, KC.leg_open(KC.LEG[lid], day), result="won" if won else "lost")
            r["pnl"] = 1.0 if won else -2.15
            rs.append(r)
    KC.save_rows(P["clock_paper"], rs)
    k = KC.card_k8(w.sd, cfg, KC.et_epoch(dt.date(2026, 10, 21), 6, 0))
    ls = {x[0]: x for x in (k or {}).get("ls") or []}
    check("a4. the PC card carries each live leg's last 20 [code, won, of, paused, obeyed]: silver UP won 9 of 20 = paused (shown; obeyed only if LIVE_ON)",
          ls.get("s17", [None, None, None, 0])[1:4] == [9, 20, 1] and ls.get("g5", [0, 0, 0, 1])[3] == 0 and ls["s17"][4] == (1 if LS.LIVE_ON else 0), ls)
    lw = open(os.path.join(ROOT, "research", "handoff", "2026-11-20", "kalshi", "LEAD_WIRES.md"), encoding="utf-8").read()
    check("a5. LEAD_WIRES.md has the exact leg_limits patch that makes the live bot obey the rule (only if the owner / lead turns LIVE_ON)",
          "kalshi_legswitch" in lw and "def leg_limits" in lw and "LS.LIVE_ON" in lw)


def main():
    tmp = tempfile.mkdtemp(prefix="k8day-")
    try:
        part_rehearsal(tmp)
        part_restart(tmp)
        part_stops(tmp)
        part_fees(tmp)
        part_orders(tmp)
        part_data()
        part_paper_card(tmp)
        part_legswitch(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
