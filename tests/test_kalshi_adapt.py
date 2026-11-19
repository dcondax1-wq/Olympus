"""K8 weekly re-test (engine/kalshi_adapt.py + tools/kalshi_adapt.py), on a FAKE tape and a fake clock. No network, no key, no order.

  a. rules      fees = verify.py's exactly; half size (8-week under +5%); OFF (8 AND 4 weeks under 0; one alone is not enough);
                max price lowered when the 4-week price creeps 4c over the tested one; the min-sample guard (25 / 12 bets);
                the armed 70c cap: bets above it are not counted in the money, but the price creep reads every window
  b. never up   a cut stays when the numbers recover (a restore ASK instead, live legs only); merge = the most restrictive;
                a hostile clock_adapt.json can never raise the stake, the cap or turn a leg on (engine/kalshi_clock.leg_limits);
                the owner's yes (the Decide card status yes / --restore) lifts a cut, newer evidence can cut again
  c. calendar   the morning legs follow London 10:15 (06:15 ET Oct 26-30, 2026 and Mar 15-26, 2027; 05:15 ET otherwise), the
                evening ones 16:45 ET on both sides of the US clock change; UK / CME holiday skips; the no-zoneinfo fallback gives
                the same times all year (a Windows PC without tzdata); the holiday-list horizon warning; on the real tape (cloud
                only): every ticker the executor trades was listed by Kalshi
  d. scan       384 rules, the Bonferroni bar (= verify.bar_t(384) ~3.65): a strong window in both halves is proposed; strong only
                in the older 8 weeks, or under the bar, is not; a K8 leg is never re-proposed; at most 2 a week; known ids skipped;
                every item keeps the Decide card schema (tests.test_decide a)
  e. PC         pc_weekly on a fake public Kalshi: GET only on the allowed paths, no key; writes clock_adapt.json (half size on the
                weak leg -> leg_limits $7.50); weekly (a second run the next day waits), not within 20 minutes of a K8 window,
                LE_KADAPT=0 off, a broken network / garbage never raises and keeps the cuts; the cloud's cuts merged; a Decide
                yes applied once; research/lab/kalshi_clock.json + kalshi_candidates/ untouched (what the owner armed)
  f. ZEUS       the nightly ZEUS learned line carries the week's automatic cut ("auto: gold 05:30 down half size"), auto_changes,
                and the restore ask goes onto the Decide card as it is (tools/learn_night.decide_item)
  g. cloud      tools/kalshi_adapt.run offline on fixture caches: the report, new Decide ids only, twice = no duplicates

    python -X utf8 -m tests.test_kalshi_adapt
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.parse
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import kalshi_adapt as KA  # noqa: E402
from engine import kalshi_clock as KC  # noqa: E402
from engine import kalshi_live as KL  # noqa: E402

RES: list = []
AS_OF = dt.date(2026, 11, 18)
CFG = KC.load_config()[0]
ID_RX = re.compile(r"[a-z0-9][a-z0-9_-]{1,39}")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[-700:]}"), flush=True)


def et_epoch(day, hh, mm):
    return KC.et_epoch(day, hh, mm)


def fixture_tape(spec, start, end):
    """spec {leg: fn(i, day) -> (price paid for our side, won) or (None, _)} -> the tape keyed by the executor's own tickers."""
    tape = {}
    for lid, fn in spec.items():
        leg, i = KC.LEG[lid], 0
        for d in KA.days_between(start, end):
            if d.weekday() >= 5 or KC.skipped(leg, d):
                continue
            o = KC.leg_open(leg, d)
            tk = KC.ticker(leg["series"], o)
            p, win = fn(i, d)
            i += 1
            if p is None:
                continue
            side = leg["side"]
            yp = p if side == "yes" else round(1 - p, 4)
            tape[tk] = {"t": tk, "o": o, "res": side if win else ("no" if side == "yes" else "yes"), "tr": [[20.0, side, yp, 100.0]]}
    return tape


def good(i, d):
    return 0.50, i % 10 not in (0, 4)          # 80% won at 50c


W = KA.windows_of(AS_OF)
L0, L1 = W["long"]


def run_rules(spec, prev=None, restored=None):
    tape = fixture_tape(spec, L0, AS_OF)
    return KA.evaluate(KA.leg_bets(tape, L0, AS_OF, CFG, legs=list(spec)), AS_OF, prev=prev, cfg=CFG, restored=restored)


# ================================================================================================ a. rules
def part_rules():
    V = KA.verify_mod()
    grid = [(p / 100, n) for p in range(3, 98, 7) for n in (1, 7, 15, 29, 300)]
    check("a1. fees: verify.py is loaded and engine/kalshi_adapt.fee = verify.fee (ceil to the cent of 0.07 x C x P x (1-P)) on a grid",
          V is not None and all(abs(KA.fee(p, n) - float(V.fee(Decimal(str(p)), Decimal(n)))) < 1e-12 for p, n in grid)
          and KA.fee(0.5, 30) == 0.53 and KA.fee(0.63, 13) == 0.22, [(p, n, KA.fee(p, n)) for p, n in grid[:3]])
    b = KA.make_bet("gold_1700_up", AS_OF, "KXGOLD15M-26NOV181700-00", 1000.0, "yes", 0.41, "yes", 15.0)
    v = V.verify([{"ts": b["ts"], "info_ts": b["info_ts"], "settle_ts": b["settle_ts"], "price": b["price"], "contracts": b["contracts"],
                   "outcome": b["outcome"]}], rules_tried=1, boot=50)
    check("a2. one bet = verify.py's recompute: 36 contracts at 41c, fee $0.61, +$20.63 (the friend's posted win), no look-ahead",
          b["contracts"] == 36 and b["fee"] == 0.61 and abs(b["pnl"] - 20.63) < 0.005 and abs(v["all"]["net_usd"] - b["pnl"]) < 0.006
          and not v["problem_counts"], (b, v["all"].get("net_usd"), v["problem_counts"]))

    # half: 8-week net about +1.5% per $1 (21 of 40 won at 50c), OFF must not fire (the 8 weeks are not negative)
    L = run_rules({"gold_0530_down": lambda i, d: (0.50, i % 2 == 0 or i == 1)})
    r, a = L["legs"]["gold_0530_down"], L["adapt"].get("gold_0530_down") or {}
    check("a3. half size: 8-week net under +5% per $1 (40 bets, 21 won at 50c) -> size factor 0.5, plain words with $, why <= 80 chars",
          r["w8"]["n"] == 40 and 0 < r["w8"]["net_per_1"] < 0.05 and a.get("size_factor") == 0.5 and "enabled" not in a
          and L["changes"] and "half size ($7.50 a bet at $15.00)" in L["changes"][0]["text"] and len(a.get("why", "")) <= 80
          and L["line"].startswith("K8 re-test: gold 05:30 down half size"), (r["w8"], a, L["line"]))
    # OFF: 40% won at 50c in both windows
    L = run_rules({"gold_1700_up": lambda i, d: (0.50, i % 5 in (0, 2))})
    a = L["adapt"].get("gold_1700_up") or {}
    check("a4. OFF: 8-week AND 4-week net under 0 (40% won) -> enabled false (and half), 'paper keeps recording'",
          a.get("enabled") is False and a.get("size_factor") == 0.5 and any("paper keeps recording" in c["text"] for c in L["changes"])
          and "OFF" in L["line"], (a, L["changes"]))
    # 8 weeks negative but the newest 4 positive: half only, not OFF
    L = run_rules({"gold_1700_up": lambda i, d: (0.50, (i % 5 == 0) if i < 20 else (i % 5 != 0))})
    r, a = L["legs"]["gold_1700_up"], L["adapt"].get("gold_1700_up") or {}
    check("a5. 8 weeks under 0 but the last 4 positive: half size only, NOT off (both windows must be negative)",
          r["w8"]["net_per_1"] < 0 < r["w4"]["net_per_1"] and a.get("size_factor") == 0.5 and "enabled" not in a, (r["w8"], r["w4"], a))
    # creep: 50c for 4 weeks, then 58c (>= 51.2c + 4c); won 75% -> max price floor(0.75 - 0.08) = 67c
    L = run_rules({"gold_0530_down": lambda i, d: (0.50 if i < 20 else 0.58, i % 4 != 0)})
    r, a = L["legs"]["gold_0530_down"], L["adapt"].get("gold_0530_down") or {}
    check("a6. price creep: the last 4 weeks paid 58c vs 51c tested -> max price = 8-week win rate 75% - 8c = 67c (lower than 70c); "
          "no half (the money is fine)", a.get("max_price") == 0.67 and "size_factor" not in a and r["w4"]["avg_price_all"] == 0.58
          and any("skips asks above 67c" in c["text"] for c in L["changes"]), (r["w4"], a))
    L = run_rules({"gold_0530_down": lambda i, d: (0.50 if i < 20 else 0.58, i % 10 != 0)})
    check("a7. creep but the new cap (90% - 8c = 82c) is not under the 70c cap: nothing changes, the line says it is watched",
          not L["adapt"] and "creep (cap already lower)" in L["legs"]["gold_0530_down"]["hits"]
          and L["line"].endswith("watching: gold 05:30 down paid +7c (still wins enough)"), (L["legs"]["gold_0530_down"]["hits"], L["line"]))
    L = run_rules({"gold_0530_down": lambda i, d: (0.50 if i < 20 else 0.75, i % 4 != 0)})
    r = L["legs"]["gold_0530_down"]
    check("a8. the armed 70c cap: asks at 75c are not counted in the money (the bot skips them) but the creep reads them",
          r["w8"]["n"] == 20 and r["w4"].get("n", 0) == 0 and r["w8"].get("avg_price_all") == 0.625, (r["w8"], r["w4"]))
    # min-sample guard: only 24 bets in 8 weeks, all lost -> untouched
    L = run_rules({"silver_1700_up": lambda i, d: (0.50 if i >= 16 else None, False)})
    r = L["legs"]["silver_1700_up"]
    check("a9. the min-sample guard: 24 bets in 8 weeks (needs 25), every one lost -> not touched, says why",
          r["w8"]["n"] == 24 and not L["adapt"] and "not touched" in (r.get("guard") or "") and L["line"].startswith("K8 re-test: no change"), r)
    L = run_rules({"silver_1700_up": lambda i, d: (0.50 if i < 30 else None, i % 5 in (0, 2))})
    r, a = L["legs"]["silver_1700_up"], L["adapt"].get("silver_1700_up") or {}
    check("a10. 30 bets in 8 weeks but under 12 in the last 4: half size may apply (8-week rule), OFF and the cap are not read",
          r["w8"]["n"] == 30 and r["w4"]["n"] < 12 and a.get("size_factor") == 0.5 and "enabled" not in a and "4-week rules not read" in r["guard"], (r, a))
    L = run_rules({lid: good for lid in CFG["paper_legs"]})
    check("a11. five healthy legs (80% won at 50c): no change, the line says so", not L["adapt"] and not L["changes"] and not L["proposals"]
          and L["line"] == "K8 re-test: no change (5 legs tested)", L["line"])


# ================================================================================================ b. never up
def part_never_up(tmp):
    prev = {"gold_0530_down": {"size_factor": 0.5, "since": {"size_factor": "2026-10-01"}, "why": "x"},
            "gold_1700_up": {"enabled": False, "size_factor": 0.5, "since": {"enabled": "2026-10-01", "size_factor": "2026-10-01"}},
            "silver_1700_up": {"max_price": 0.6, "since": {"max_price": "2026-10-01"}},
            "silver_1615_down": {"enabled": False, "since": {"enabled": "2026-10-01"}}}
    L = run_rules({lid: good for lid in CFG["paper_legs"]}, prev={"legs": prev})
    ad = L["adapt"]
    check("b1. sticky: every leg now makes +50% per $1, but no cut is lifted by itself (half stays half, OFF stays OFF, 60c stays)",
          ad["gold_0530_down"]["size_factor"] == 0.5 and ad["gold_1700_up"]["enabled"] is False and ad["silver_1700_up"]["max_price"] == 0.6
          and ad["silver_1615_down"]["enabled"] is False and not L["changes"], ad)
    ids = sorted(p["id"] for p in L["proposals"])
    pg = {p["k8"]["leg"]: p for p in L["proposals"]}
    check("b2. ... instead one restore ASK per recovered LIVE leg (the paper-only silver 16:15 gets none), each with $ a month",
          ids == ["k8-restore-gold-0530-down-1001", "k8-restore-gold-1700-up-1001", "k8-restore-silver-1700-up-1001"]
          and pg["gold_1700_up"]["question"].startswith("K8 gold UP 16:45-17:00 ET: turn it back ON and full size")
          and pg["gold_0530_down"]["impact_usd"] > 0 and "$" in pg["gold_0530_down"]["impact"], [(p["id"], p["question"]) for p in L["proposals"]])
    L2 = run_rules({"silver_1700_up": lambda i, d: (0.50 if i < 20 else 0.58, i % 10 != 0)}, prev={"legs": {"silver_1700_up": prev["silver_1700_up"]}})
    check("b3. a capped leg whose price is still up gets no restore ask (the price must be back under the tested + 2c)",
          not L2["proposals"] and L2["adapt"]["silver_1700_up"]["max_price"] == 0.6, L2["proposals"])
    m = KA.merge({"gold_0530_down": {"size_factor": 0.5, "max_price": 0.65, "since": {}}},
                 {"gold_0530_down": {"size_factor": 0.75, "max_price": 0.6, "enabled": False, "since": {}}})
    check("b4. merge = the most restrictive: x0.5 (not 0.75), 60c (not 65c), OFF", m["gold_0530_down"]["size_factor"] == 0.5
          and m["gold_0530_down"]["max_price"] == 0.6 and m["gold_0530_down"]["enabled"] is False, m)
    c = KA.clean_adapt({"legs": {"gold_0530_down": {"size_factor": 2.0, "max_price": 0.95, "enabled": True}, "nope_leg": {"enabled": False},
                                 "gold_1700_up": {"size_factor": -1, "max_price": 0.01}}})
    check("b5. a hostile adapt file is cleaned to nothing: size 2.0, max 95c, enabled true, an unknown leg, size -1, max 1c are dropped", c == {}, c)
    sd = os.path.join(tmp, "b_state")
    os.makedirs(sd, exist_ok=True)
    KL._jwrite(KC.adapt_path(sd), {"legs": {"gold_0530_down": {"size_factor": 3, "max_price": 0.79, "enabled": True},
                                            "silver_0530_down": {"enabled": True}, "gold_1700_up": {"size_factor": 0.5, "max_price": 0.62}}})
    l1, l2, l3 = (KC.leg_limits(CFG, x, sd) for x in ("gold_0530_down", "silver_0530_down", "gold_1700_up"))
    check("b6. the executor's hook (kalshi_clock.leg_limits) never goes up: size 3 / 79c / enabled true change nothing, a paper-only "
          "leg stays off; x0.5 + 62c are taken ($7.50, 62c)", (l1["stake"], l1["cap"], l1["enabled"]) == (CFG["stake_usd"], 0.70, True)
          and l2["enabled"] is False and (l3["stake"], l3["cap"]) == (7.5, 0.62), (l1, l2, l3))
    keep = KA.drop_restored({"gold_0530_down": {"size_factor": 0.5, "max_price": 0.6, "since": {"size_factor": "2026-10-01", "max_price": "2026-11-20"}}},
                            {"gold_0530_down": "2026-11-05"})
    check("b7. the owner's restore (Nov 5) lifts the cut it covered (half, Oct 1) but newer evidence (60c, Nov 20) stays",
          keep == {"gold_0530_down": {"max_price": 0.6, "since": {"max_price": "2026-11-20"}, "why": ""}}, keep)
    KL._jwrite(KC.adapt_path(sd), {"legs": {"gold_1700_up": {"enabled": False, "size_factor": 0.5, "since": {"enabled": "2026-10-01"}}}})
    w = KA.restore("gold_1700_up", sd, now=et_epoch(AS_OF, 18, 0))
    d = KA.adapt_doc(sd)
    lim = KC.leg_limits(CFG, "gold_1700_up", sd)
    check("b8. --restore gold_1700_up (the owner's yes on the PC): the cut is gone, the leg is back to what he armed, the change is logged",
          "back to what you armed" in w and "gold_1700_up" not in d["legs"] and d["restored"]["gold_1700_up"] == "2026-11-18"
          and lim["enabled"] and lim["stake"] == CFG["stake_usd"] and d["changes"][-1]["what"] == "restored", (w, d, lim))
    check("b9. --restore of an unknown leg is refused in words", "unknown leg" in KA.restore("silver_9999_up", sd))
    it = [{"id": "k8-restore-gold-1700-up-1001", "status": "yes", "k8": {"kind": "restore", "leg": "gold_1700_up"}},
          {"id": "k8-restore-gold-0530-down-1001", "status": "open", "k8": {"kind": "restore", "leg": "gold_0530_down"}},
          {"id": "payout-ping-1000", "status": "yes"}, {"id": "k8-restore-x", "status": "yes", "k8": {"kind": "restore", "leg": "evil"}}]
    bad = lambda i, d: (0.50, i % 5 in (0, 2))      # noqa: E731  40% won: would be OFF
    La = run_rules({"gold_1700_up": bad}, prev={"legs": {"gold_1700_up": {"enabled": False, "since": {"enabled": "2026-10-01"}}}},
                   restored={"gold_1700_up": "2026-11-10"})
    tape_new = fixture_tape({"gold_1700_up": bad}, L0, AS_OF)
    Lb = KA.evaluate(KA.leg_bets(tape_new, L0, AS_OF, CFG, legs=["gold_1700_up"]), AS_OF, cfg=CFG, restored={"gold_1700_up": "2026-10-10"})
    check("b11. after the owner's yes the leg starts fresh: the old bad weeks do not cut it again (6 bets since the yes: not touched); "
          "once 25+ bets after the yes are bad again, the rules cut it again", not La["adapt"] and La["legs"]["gold_1700_up"]["w8"]["n"] == 6
          and Lb["adapt"]["gold_1700_up"].get("enabled") is False and Lb["legs"]["gold_1700_up"]["w8"]["n"] == 28,
          (La["adapt"], La["legs"]["gold_1700_up"]["w8"].get("n"), Lb["legs"]["gold_1700_up"]["w8"].get("n")))
    check("b10. the Decide card: only a k8-restore item the owner said yes to (status yes) for a real leg counts, once",
          KA.restores_from_decisions(it) == [("k8-restore-gold-1700-up-1001", "gold_1700_up")]
          and KA.restores_from_decisions(it, done={"k8-restore-gold-1700-up-1001"}) == [], KA.restores_from_decisions(it))


# ================================================================================================ c. calendar
def part_calendar():
    def hm(lid, d):
        return KL.et_dt(KC.leg_open(KC.LEG[lid], d)).strftime("%H:%M")
    au = [hm("gold_0530_down", dt.date(2026, 10, x)) for x in (23, 26, 27, 28, 29, 30)] + [hm("gold_0530_down", dt.date(2026, 11, 2))]
    check("c1. autumn: UK back on GMT Oct 25, US on Nov 1 -> the morning legs at 06:15 ET Oct 26-30, 2026 (London 10:15), 05:15 before / after; "
          "ticker KXGOLD15M-26OCT260630-30", au == ["05:15", "06:15", "06:15", "06:15", "06:15", "06:15", "05:15"]
          and KC.ticker("KXGOLD15M", KC.leg_open(KC.LEG["gold_0530_down"], dt.date(2026, 10, 26))) == "KXGOLD15M-26OCT260630-30", au)
    sp = [hm("silver_0530_down", dt.date(2027, 3, x)) for x in (12, 15, 26, 29)]
    ev = [hm(l, d) for l in ("gold_1700_up", "silver_1615_down") for d in (dt.date(2026, 10, 30), dt.date(2026, 11, 2), dt.date(2027, 3, 15))]
    check("c2. spring 2027: 06:15 ET Mar 15-26 (US on summer time first), 05:15 on Mar 12 and Mar 29; the evening legs stay 16:45 / 16:00 ET "
          "on both sides of each clock change", sp == ["05:15", "06:15", "06:15", "05:15"] and ev == ["16:45"] * 3 + ["16:00"] * 3, (sp, ev))
    days = [dt.date(2026, 8, 3) + dt.timedelta(days=i) for i in range(0, 300)]
    real = [(d, lid, KC.leg_open(KC.LEG[lid], d)) for d in days for lid in KC.LEG]
    lon, et = KC._LON, KL._ET
    try:
        KC._LON, KL._ET = None, None
        fb = [(d, lid, KC.leg_open(KC.LEG[lid], d)) for d in days for lid in KC.LEG]
        tk_fb = KC.ticker("KXGOLD15M", KC.leg_open(KC.LEG["gold_0530_down"], dt.date(2026, 10, 27)))
    finally:
        KC._LON, KL._ET = lon, et
    bad = [(str(a[0]), a[1]) for a, b in zip(real, fb) if a[2] != b[2]]
    check("c3. no zoneinfo (a Windows PC without tzdata): the built-in London / US clock rules give the same window times on 300 days "
          "(Aug 2026 - May 2027) for every leg, and the same gap-week ticker", not bad and tk_fb == "KXGOLD15M-26OCT270630-30", bad[:5])
    cfg = KC.load_config()[0]
    gf = [KL.et_dt(t).strftime("%H:%M") for t, _ in KC.windows(dt.date(2027, 3, 26), cfg)]
    em = [KL.et_dt(t).strftime("%H:%M") for t, _ in KC.windows(dt.date(2027, 3, 29), cfg)]
    ny = KC.windows(dt.date(2027, 1, 1), cfg)
    check("c4. holidays: Good Friday 2027 (UK + CME) nothing, Easter Monday 2027 (UK) the evening legs only, New Year nothing",
          gf == [] and em == ["16:00", "16:45"] and ny == [], (gf, em, ny))
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import kalshi_adapt as TA
    w1 = TA.calendar_check({}, AS_OF, AS_OF, cfg, dt.date(2027, 2, 20))["warn"]
    w0 = TA.calendar_check({}, AS_OF, AS_OF, cfg, AS_OF)["warn"]
    check("c5. the weekly report warns 45 days before the holiday lists run out (they end 2027-03-29)", w0 is None and w1 and "2027-03-29" in w1, (w0, w1))
    mk = os.path.join("/home/user/kalshi_cache/kmetal", "mk_KXGOLD15M.jsonl")
    if os.path.isfile(mk):
        markets = TA.load_markets(["/home/user/kalshi_cache/kmetal"])
        cc = TA.calendar_check(markets, dt.date(2026, 8, 3), dt.date(2026, 11, 18), cfg, AS_OF)
        check("c6. the real tape (cloud cache): every one of the executor's tickers Aug 3 - Nov 18, 2026 (390, the gap week at 06:15 "
              "included) was listed by Kalshi", cc["tickers"] == 390 and cc["missing_n"] == 0, cc)
    else:
        print("[skip] c6. no real tape cache on this machine")


# ================================================================================================ d. scan
def fake_candles(spec, as_of=AS_OF):
    """spec {(series, hhmm): fn(i, day, held_out) -> (yes bid, yes ask, result)} -> cd-style rows, weekdays of the 12 weeks."""
    out = {}
    d0 = as_of - dt.timedelta(days=83)
    h0 = as_of - dt.timedelta(days=27)
    for (s, hh), fn in spec.items():
        i = 0
        for d in KA.days_between(d0, as_of):
            if d.weekday() >= 5:
                continue
            c = et_epoch(d, int(hh[:2]), int(hh[2:]))
            o = c - 900
            b, a, res = fn(i, d, d >= h0)
            i += 1
            t = f"{s}-{d:%y}{KC.MON[d.month - 1]}{d:%d}{hh}-{hh[2:]}"
            out[t] = {"t": t, "hhmm": hh, "day": f"{d:%y}{KC.MON[d.month - 1]}{d:%d}", "o": o, "c": c, "res": res, "series": s,
                      "k": [[o + 60, b, a] + [None] * 10]}
    return out


def part_scan():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import kalshi_adapt as TA
    strong = lambda i, d, h: (0.48, 0.50, "yes" if i % 5 != 0 else "no")          # noqa: E731  80% UP at 50c, both halves
    early = lambda i, d, h: (0.48, 0.50, ("yes" if i % 5 != 0 else "no") if not h else ("yes" if i % 3 == 0 else "no"))  # noqa: E731
    modest = lambda i, d, h: (0.48, 0.50, "yes" if i % 10 not in (0, 3, 6) else "no")  # noqa: E731  70%: t ~2.5, under the bar
    down = lambda i, d, h: (0.50, 0.52, "no" if i % 5 != 0 else "yes")             # noqa: E731  80% DOWN at 50c
    C = fake_candles({("KXGOLD15M", "1000"): strong, ("KXSILVER15M", "1100"): early, ("KXGOLD15M", "1200"): modest,
                      ("KXGOLD15M", "1700"): strong, ("KXSILVER15M", "0900"): down, ("KXGOLD15M", "1315"): strong})
    S = TA.scan(C, AS_OF)
    V = KA.verify_mod()
    by = {(r["series"], r["hhmm"], r["side"]): r for r in S["found"]}
    check("d1. 384 rules tried, the bar = verify.bar_t(384) (~3.65), the older 8 of 12 weeks find, the newest 4 check",
          S["rules_tried"] == 384 and abs(S["bar_t"] - float(V.bar_t(384))) < 0.01 and 3.6 < S["bar_t"] < 3.7
          and S["discovery"] == ["2026-08-27", "2026-10-21"] and S["held_out"] == ["2026-10-22", "2026-11-18"], S["bar_t"])
    passed = {(r["series"], r["hhmm"], r["side"]) for r in S["passed"]}
    check("d2. strong in both halves: proposed (gold UP 09:45-10:00, gold UP 13:00-13:15, silver DOWN 08:45-09:00); strong only in the "
          "older 8 weeks (silver 11:00): found but not passed; 70% (t ~2.5): under the bar, not found; the K8 leg gold 17:00 UP: "
          "found but never proposed", passed == {("KXGOLD15M", "1000", "yes"), ("KXGOLD15M", "1315", "yes"), ("KXSILVER15M", "0900", "no")}
          and ("KXSILVER15M", "1100", "yes") in by and ("KXGOLD15M", "1200", "yes") not in by and ("KXGOLD15M", "1700", "yes") in by
          and by[("KXGOLD15M", "1700", "yes")]["known"], (passed, list(by)))
    P = TA.new_leg_proposals(S, set(), 2, AS_OF)
    check("d3. at most 2 new legs a week, plain words + $ a month, a yes = PAPER first", len(P) == 2 and all("PAPER" in p["question"]
          and "$" in p["impact"] and p["impact_usd"] > 0 and "phrase" in p["applies"] for p in P), [p["question"] for p in P])
    P2 = TA.new_leg_proposals(S, {P[0]["id"]}, 2, AS_OF)
    P0 = TA.new_leg_proposals(S, set(), 0, AS_OF)
    check("d4. an id already on the card (any status) is never proposed again; no room left this week = none",
          P[0]["id"] not in [p["id"] for p in P2] and len(P2) == 2 and P0 == [], [p["id"] for p in P2])
    bad = [p["id"] for p in P + P2 if not (ID_RX.fullmatch(p["id"]) and p["question"] and p["why"] and "$" in p["impact"]
                                           and isinstance(p["impact_usd"], (int, float)) and set(p["options"]) <= {"yes", "no", "later"}
                                           and p["status"] == "open" and p["source"] == "research/lab/kalshi_adapt.json")]
    check("d5. every proposal keeps the Decide card schema (tests.test_decide a: id, question, why, $ impact, options, status, source)", not bad, bad)


# ================================================================================================ e. PC
class FakeKalshi:
    """The public Kalshi API for the leg tickers of a fixture tape. Records every URL it was asked for."""

    def __init__(self, tape, broken=False):
        self.tape, self.urls, self.broken = tape, [], broken

    def __call__(self, url, timeout):
        self.urls.append(url)
        if self.broken == "raise":
            raise OSError("no network")
        if self.broken == "garbage":
            return 200, b"<html>not json"
        u = urllib.parse.urlsplit(url)
        path, q = u.path.replace("/trade-api/v2", ""), dict(urllib.parse.parse_qsl(u.query))
        if path == "/historical/cutoff":
            return 200, json.dumps({"market_settled_ts": "2026-09-19T00:00:00Z", "trades_created_ts": "2026-09-19T00:00:00Z"}).encode()
        m = re.fullmatch(r"/(?:historical/)?markets/([A-Z0-9-]+)", path)
        if m and m.group(1) not in ("trades", "candlesticks"):
            r = self.tape.get(m.group(1))
            return (200, json.dumps({"market": {"ticker": m.group(1), "result": r["res"]}}).encode()) if r else (404, b"")
        if path in ("/markets/trades", "/historical/trades"):
            r = self.tape.get(q.get("ticker"))
            if not r:
                return 200, b'{"trades": [], "cursor": ""}'
            tr = [{"created_time": dt.datetime.fromtimestamp(r["o"] + x[0], dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                   "taker_side": x[1], "yes_price_dollars": f"{x[2]:.4f}", "count_fp": f"{x[3]:.2f}"} for x in r["tr"]]
            return 200, json.dumps({"trades": tr, "cursor": ""}).encode()
        return 404, b""


def tree_hash(*paths):
    h = hashlib.sha256()
    for p in paths:
        for dp, _, fs in sorted(os.walk(p)) if os.path.isdir(p) else [(os.path.dirname(p), None, [os.path.basename(p)])]:
            for f in sorted(fs):
                with open(os.path.join(dp, f), "rb") as fh:
                    h.update(f.encode() + fh.read())
    return h.hexdigest()


def make_root(tmp, decisions=None, cloud=None):
    r = os.path.join(tmp, "root")
    os.makedirs(os.path.join(r, "research", "lab"), exist_ok=True)
    shutil.copy(KC.CFG_PATH, os.path.join(r, "research", "lab", "kalshi_clock.json"))
    if decisions is not None:
        KA._jwrite(os.path.join(r, "tools", "web_public", "business", "decisions.json"), decisions, indent=1)
    if cloud is not None:
        KA._jwrite(os.path.join(r, "research", "lab", "kalshi_adapt.json"), cloud, indent=1)
    return r


def part_pc(tmp):
    spec = {lid: good for lid in CFG["paper_legs"]}
    spec["gold_0530_down"] = lambda i, d: (0.50, i % 2 == 0 or i == 1)          # the weak leg: +1.5% per $1
    tape = fixture_tape(spec, L0, AS_OF)
    now = et_epoch(AS_OF, 18, 0)
    sd = os.path.join(tmp, "pc_state")
    root = make_root(os.path.join(tmp, "pc"), decisions={"v": 1, "kind": "olympus-decisions", "items": []})
    armed = tree_hash(KC.CFG_PATH, KL.CAND_DIR)
    fk = FakeKalshi(tape)
    r = KA.pc_weekly(sd, root, now=now, env={}, http=fk, sleep=lambda s: None)
    d = KA.adapt_doc(sd)
    lim = KC.leg_limits(CFG, "gold_0530_down", sd)
    check("e1. the PC's weekly run on the public tape: fetches the 8 weeks (GET only), half size on the weak leg -> the executor's "
          "hook bets $7.50 there; the others as armed", r["ok"] and r["ran"] and d["legs"]["gold_0530_down"]["size_factor"] == 0.5
          and lim["stake"] == 7.5 and KC.leg_limits(CFG, "gold_1700_up", sd)["stake"] == CFG["stake_usd"] and r["line"].startswith("K8 re-test: gold 05:30 down half size")
          and d["tested"]["gold_1700_up"]["w8"]["n"] == 40, (r, d.get("legs")))
    paths = {urllib.parse.urlsplit(u).path.replace("/trade-api/v2", "") for u in fk.urls}
    check("e2. only public GETs on the allowed paths (cutoff, one market, trades), none signed; the tape is cached (200 markets)",
          all(KA.Public.allowed("GET", p) for p in paths) and all(u.startswith(KA.Public.BASE) for u in fk.urls)
          and len(KA.read_tape(os.path.join(sd, "adapt", "tape.jsonl"))) == 200 and len(fk.urls) == 401, (len(fk.urls), sorted(paths)[:4]))
    check("e3. Public refuses anything else: POST, /portfolio/balance, a query in the path, '..', an order path; at most 1 request a second",
          not KA.Public.allowed("POST", "/markets") and not KA.Public.allowed("GET", "/portfolio/balance")
          and not KA.Public.allowed("GET", "/markets?x=1") and not KA.Public.allowed("GET", "/markets/../portfolio")
          and not KA.Public.allowed("GET", "/portfolio/events/orders") and KA.Public(gap=0.01).gap == 1.0
          and KA.Public(http=FakeKalshi({}), sleep=lambda s: None).get("/portfolio/balance") is None)
    r2 = KA.pc_weekly(sd, root, now=now + 86400, env={}, http=fk, sleep=lambda s: None)
    q = KA.pc_weekly(os.path.join(tmp, "q_state"), root, now=et_epoch(AS_OF, 16, 30), env={}, http=fk, sleep=lambda s: None)
    off = KA.pc_weekly(sd, root, now=now, env={"LE_KADAPT": "0"}, force=True, http=fk)
    check("e4. weekly: the next day it waits; 15 minutes before the 16:45 window it waits; LE_KADAPT=0 = off",
          r2["ok"] and not r2["ran"] and "weekly" in r2["why"] and not q["ran"] and "16:45" in q["why"] and not off["ran"] and "LE_KADAPT=0" in off["why"],
          (r2, q, off))
    n0 = len(fk.urls)
    r3 = KA.pc_weekly(sd, root, now=now + 7 * 86400, env={}, http=fk, sleep=lambda s: None)
    check("e5. a week later the cached tape is reused (only the 25 new markets are asked for, twice at most), the half cut stays and the "
          "newer 8 weeks (now under 0 in both windows) may cut more: OFF", r3["ran"] and len(fk.urls) - n0 <= 51
          and KA.adapt_doc(sd)["legs"]["gold_0530_down"]["size_factor"] == 0.5 and KA.adapt_doc(sd)["legs"]["gold_0530_down"].get("enabled") is False,
          (len(fk.urls) - n0, r3.get("line")))
    sd2 = os.path.join(tmp, "pc_broken")
    KL._jwrite(KC.adapt_path(sd2), {"legs": {"silver_1700_up": {"enabled": False, "since": {"enabled": "2026-11-01"}, "why": "w"}}})
    br = [KA.pc_weekly(sd2, root, now=now, env={}, force=True, http=FakeKalshi(tape, broken=b), sleep=lambda s: None) for b in ("raise", "garbage")]
    st2 = KL._jread(KA.state_path(sd2), {})
    fkr = FakeKalshi(tape, broken="raise")
    KA.pc_weekly(os.path.join(tmp, "pc_down"), root, now=now, env={}, http=fkr, sleep=lambda s: None)
    nxt = KA.pc_weekly(os.path.join(tmp, "pc_down"), root, now=now + 21 * 3600, env={}, http=FakeKalshi(tape), sleep=lambda s: None)
    check("e6b. Kalshi down: it stops after 6 failed tries (not hundreds), and tries again the next night instead of a week later",
          len(fkr.urls) <= 7 and nxt["ran"] and st2.get("missing", 0) > 0, (len(fkr.urls), nxt.get("why"), st2))
    with open(KC.adapt_path(sd2) + ".bad", "w") as fh:
        fh.write("{oops")
    weird = KA.pc_weekly(os.path.join(tmp, "nope", "deeper"), "/nonexistent/root", now=now, env={}, force=True, http=fk, sleep=lambda s: None)
    check("e6. no network / garbage answers: never raises, ran with too few bets (nothing new cut) and the old cut (silver 17:00 OFF) is "
          "kept; a missing install root never raises either", all(b["ok"] and b["ran"] for b in br)
          and KA.adapt_doc(sd2)["legs"]["silver_1700_up"]["enabled"] is False and isinstance(weird, dict) and "ok" in weird, (br, weird))
    cloud = {"adapt": {"silver_1700_up": {"max_price": 0.6, "since": {"max_price": "2026-11-18"}, "why": "cloud: prices up"}}}
    sd3 = os.path.join(tmp, "pc_cloud")
    root3 = make_root(os.path.join(tmp, "pc3"), decisions={"items": []}, cloud=cloud)
    KA.pc_weekly(sd3, root3, now=now, env={}, http=FakeKalshi(tape), sleep=lambda s: None)
    d3 = KA.adapt_doc(sd3)
    check("e7. the cloud's cut (research/lab/kalshi_adapt.json: silver 17:00 max 60c) is merged on the PC, most restrictive wins",
          d3["legs"]["silver_1700_up"]["max_price"] == 0.6 and d3["src"] == "pc+cloud" and KC.leg_limits(CFG, "silver_1700_up", sd3)["cap"] == 0.6, d3.get("legs"))
    dec = {"items": [{"id": "k8-restore-silver-1700-up-1118", "status": "yes", "k8": {"kind": "restore", "leg": "silver_1700_up"}}]}
    root4 = make_root(os.path.join(tmp, "pc4"), decisions=dec, cloud=cloud)
    r4 = KA.pc_weekly(sd3, root4, now=now + 7 * 86400, env={}, http=FakeKalshi(tape), sleep=lambda s: None)
    d4 = KA.adapt_doc(sd3)
    r5 = KA.pc_weekly(sd3, root4, now=now + 14 * 86400, env={}, http=FakeKalshi(tape), sleep=lambda s: None)
    check("e8. the owner's yes on the Decide card (status yes): the next weekly run lifts the cut (the cloud's too: older evidence), "
          "logs 'restored (your yes)', applies it once", "silver_1700_up" not in d4["legs"] and "k8-restore-silver-1700-up-1118" in d4["restores_applied"]
          and any(c["what"] == "restored" for c in r4["changes"]) and not any(c["what"] == "restored" for c in r5["changes"])
          and KC.leg_limits(CFG, "silver_1700_up", sd3)["cap"] == 0.70, (d4.get("legs"), r4.get("changes")))
    tf = os.path.join(sd, "adapt", "tape.jsonl")
    n_before = len(KA.read_tape(tf))
    dropped = KA.prune_tape(tf, dt.date(2026, 11, 1), max_bytes=1000)
    kept = KA.read_tape(tf)
    check("e10. the PC's tape cache stays small: over its size it keeps only the recent markets", dropped > 0 and len(kept) == n_before - dropped
          and min(r["o"] for r in kept.values()) >= KC.et_epoch(dt.date(2026, 11, 1), 0, 0) and KA.prune_tape(tf, dt.date(2026, 11, 1)) == 0, (n_before, dropped))
    check("e11. the as-of day: from 17:05 ET a weekday counts (the nightly run), before it the day before, a weekend = Friday",
          KA.as_of_day(et_epoch(AS_OF, 17, 6)) == AS_OF and KA.as_of_day(et_epoch(AS_OF, 16, 50)) == AS_OF - dt.timedelta(days=1)
          and KA.as_of_day(et_epoch(dt.date(2026, 11, 22), 12, 0)) == dt.date(2026, 11, 20))
    check("e9. what the owner armed is untouched: research/lab/kalshi_clock.json and kalshi_candidates/ hash the same",
          tree_hash(KC.CFG_PATH, KL.CAND_DIR) == armed)


# ================================================================================================ f. ZEUS learned
def part_zeus(tmp):
    from engine import zeus_learn as ZL
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import learn_night as LN
    day = "2026-11-18"
    ad = {"changes": [{"day": "2026-11-18", "leg": "gold_0530_down", "what": "size_factor", "short": "gold 05:30 down half size (8 wk +2%)",
                       "text": "gold DOWN 05:15-05:30 ET: made only +2% ..."},
                      {"day": "2026-10-01", "leg": "gold_1700_up", "what": "enabled", "short": "old", "text": "old"}],
          "proposals": [{"id": "k8-restore-gold-1700-up-1001", "question": "K8 gold UP 16:45-17:00 ET: turn it back ON?", "why": "recovered",
                         "impact": "About +$80 a month", "impact_usd": 80, "options": ["yes", "no", "later"], "status": "open",
                         "source": "research/lab/kalshi_adapt.json", "applies": "A yes: ...", "k8": {"kind": "restore", "leg": "gold_1700_up"}}]}
    rows = [{"id": f"{day}:gold_1700_up", "day": day, "leg": "gold_1700_up", "open_t": 1.0, "result": "won", "pnl": 7.1, "cost": 7.4, "price": 0.49}]
    b = ZL.k8_block({"paper": rows, "adapt": ad}, day)
    check("f1. ZEUS learned's K8 block: this week's automatic cut is the verdict ('auto: gold 05:30 down half size'), the old one is not",
          b["verdict"].startswith("auto: gold 05:30 down half size") and len(b["auto"]) == 1 and "; old" not in b["verdict"], b["verdict"])
    r = os.path.join(tmp, "zroot")
    KA._jwrite(os.path.join(r, "data", "kalshi_live", "clock_paper.json"), {"v": 1, "rows": rows})
    KA._jwrite(os.path.join(r, "data", "kalshi_live", "clock_adapt.json"), ad)
    K = ZL.k8_rows(r)
    S = ZL.build([], None, root=r, now=int(et_epoch(AS_OF, 18, 0)), edge={}, brk={}, k8=K, hide=set())
    check("f2. the nightly line carries it (one push a night), auto_changes lists it, the restore ask is a proposal",
          "K8 1 bet +$7 (paper), auto: gold 05:30 down half size" in S["line"] and S["auto_changes"][0]["leg"] == "gold_0530_down"
          and [p["id"] for p in S["proposals"]] == ["k8-restore-gold-1700-up-1001"], (S["line"], S["auto_changes"]))
    it = LN.decide_item(S["proposals"][0])
    dpath = os.path.join(tmp, "dec.json")
    KA._jwrite(dpath, {"v": 1, "kind": "olympus-decisions", "items": []})
    res = LN.step_decide(S["proposals"], dpath)
    res2 = LN.step_decide(S["proposals"], dpath)
    check("f3. the cloud's learn night puts the ask on the Decide card as it is ($80 a month, the restore words), once",
          it["impact_usd"] == 80 and it["applies"] == "A yes: ..." and it["k8"]["leg"] == "gold_1700_up" and res["added"] == ["k8-restore-gold-1700-up-1001"]
          and res2["added"] == [], (it, res, res2))
    check("f4. no adapt file: the K8 block is as before (no auto, no proposals)", not ZL.k8_block({"paper": rows}, day)["auto"]
          and ZL.k8_block({}, day) is None)


# ================================================================================================ g. cloud
def part_cloud(tmp):
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import kalshi_adapt as TA
    rd = os.path.join(tmp, "cache_read")
    spec = {lid: good for lid in CFG["paper_legs"]}
    spec["silver_1700_up"] = lambda i, d: (0.50, i % 5 in (0, 2))                # the bad leg: OFF
    tape = fixture_tape(spec, L0, AS_OF)
    os.makedirs(rd, exist_ok=True)
    for s in TA.SERIES:
        with open(os.path.join(rd, f"mk_{s}.jsonl"), "w") as fm, open(os.path.join(rd, f"ot_{s}.jsonl"), "w") as fo:
            for t, r in tape.items():
                if t.startswith(s + "-"):
                    code = t.split("-")[1]
                    fm.write(json.dumps({"ticker": t, "event_ticker": f"{s}-{code}", "open_time": KL.iso(r["o"]), "close_time": KL.iso(r["o"] + 900),
                                         "result": r["res"], "volume_fp": "100"}) + "\n")
                    fo.write(json.dumps({"t": t, "o": r["o"], "tr": r["tr"]}) + "\n")
    C = fake_candles({("KXGOLD15M", "1000"): lambda i, d, h: (0.48, 0.50, "yes" if i % 5 != 0 else "no")})
    with open(os.path.join(rd, "cd_KXGOLD15M.jsonl"), "w") as fh:
        for r in C.values():
            fh.write(json.dumps(r) + "\n")
    rep, dpath = os.path.join(tmp, "lab", "kalshi_adapt.json"), os.path.join(tmp, "biz", "decisions.json")
    KA._jwrite(dpath, {"v": 1, "kind": "olympus-decisions", "updated": "2026-11-18", "items": [{"id": "payout-ping-1000", "status": "open"}]})
    armed = tree_hash(KC.CFG_PATH, KL.CAND_DIR)
    out = TA.run(as_of="2026-11-18", offline=True, report_path=rep, decisions_path=dpath, read_dirs=[rd], cache=os.path.join(tmp, "cache_w"),
                 now=et_epoch(AS_OF, 20, 0), say=lambda *a: None)
    doc, dec = KA._jread(rep), KA._jread(dpath)
    ids = [i["id"] for i in dec["items"]]
    check("g1. the cloud run (offline, fixture caches): silver 17:00 UP OFF in the report's cuts, the new window gold UP 09:45 proposed "
          "as a PAPER leg, the Decide card keeps its first item", doc["adapt"]["silver_1700_up"]["enabled"] is False
          and "k8-new-gold-1000-up" in ids and ids[0] == "payout-ping-1000" and doc["scan"]["rules_tried"] == 384
          and doc["calendar"]["missing_n"] == 0 and "silver 17:00 up OFF" in doc["line"], (doc["line"], ids, doc["calendar"]))
    out2 = TA.run(as_of="2026-11-18", offline=True, report_path=rep, decisions_path=dpath, read_dirs=[rd], cache=os.path.join(tmp, "cache_w"),
                  now=et_epoch(AS_OF, 21, 0), say=lambda *a: None)
    dec2 = KA._jread(dpath)
    check("g2. run twice: no duplicate Decide ids, the cut stays, no new change logged", [i["id"] for i in dec2["items"]] == ids and not out2["added"]
          and KA._jread(rep)["adapt"]["silver_1700_up"]["enabled"] is False and not out2["L"]["changes"], [i["id"] for i in dec2["items"]])
    tb = TA.table(out)
    check("g3. the printed table: per leg 8 / 4 weeks, $ a month, the price paid, what is in force, the scan and the calendar line",
          any("silver UP 16:45-17:00 ET" in x and "OFF" in x for x in tb) and any(x.strip().startswith("scan: 384 rules") for x in tb)
          and any("calendar:" in x for x in tb), "\n".join(tb))
    check("g4. the cloud run never touches what the owner armed (kalshi_clock.json, kalshi_candidates/)", tree_hash(KC.CFG_PATH, KL.CAND_DIR) == armed)


def main():
    tmp = tempfile.mkdtemp(prefix="kadapt-")
    try:
        part_rules()
        part_never_up(tmp)
        part_calendar()
        part_scan()
        part_pc(tmp)
        part_zeus(tmp)
        part_cloud(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
