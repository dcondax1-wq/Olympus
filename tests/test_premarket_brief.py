"""tools/premarket_brief.py (day-brief 2026-11-20): the brief.json contract (docs/BRIEF.md v 1) and its honesty rules.

    python -X utf8 -m tests.test_premarket_brief
Pure: reads the repo's data files, writes only to a temp dir.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
import premarket_brief as P  # noqa: E402

OK, BAD = [], []


def check(name, cond, info=""):
    (OK if cond else BAD).append(name)
    print(("ok   " if cond else "FAIL ") + name + (f"  ({info})" if info and not cond else ""))


def at(s):
    return P._parse_now(s)


def main():
    bars = P.load_bars()
    meas = P.stored_measure()
    check("stored measurement exists", meas is not None and "B1" in meas["rules"])

    # 1. contract fields (docs/BRIEF.md)
    b = P.build(at("2026-11-10T08:05"), bars=bars, measured=meas)
    top = ["v", "built_at", "day", "weekday", "phase", "early_close", "headline", "data", "market", "news", "bias", "bots",
           "recap", "notes"]
    check("top-level fields", all(k in b for k in top), str(set(top) - set(b)))
    check("v == 1", b["v"] == 1)
    for k in ("last", "prior_day", "prior_rth_close", "overnight", "rth_open", "gap_pts", "gap_atr", "atr_pts", "vix", "vxn",
              "where", "where_text", "levels"):
        check(f"market.{k}", k in b["market"])
    for k in ("call", "rule_id", "rule", "inputs", "why_none", "measured", "alt", "works", "context_only", "verdict", "not_reliable"):
        check(f"bias.{k}", k in b["bias"])
    for k in ("today", "week", "next_tier1", "rules", "tier1_today"):
        check(f"news.{k}", k in b["news"])
    ids = [x["id"] for x in b["bots"]]
    check("bots order", ids == ["lit", "atlas_ema", "atlas_macd", "atlas_sr", "rapid"], str(ids))
    for x in b["bots"]:
        check(f"bot {x['id']} fields", all(k in x for k in ("id", "name", "accounts", "windows", "state", "max_trades",
                                                              "waiting_for", "watch", "news_rule", "size_rule")))

    # 2. Tier-1 day (CPI 2026-11-10 08:30)
    check("tier1 day: CPI listed", any(e["tier"] == 1 and "CPI" in e["event"] and e["time"] == "08:30" for e in b["news"]["today"]))
    check("tier1 day: flag in not_reliable", any("Tier-1" in f for f in b["bias"]["not_reliable"]))
    check("tier1 day: phase pre", b["phase"] == "pre")
    check("recap null before close", b["recap"] is None)

    # 3. determinism + size + no churn
    s1, s2 = P.dumps(b), P.dumps(P.build(at("2026-11-10T08:05"), bars=bars, measured=meas))
    check("same inputs = same bytes", s1 == s2)
    check("size < 20 KB", len(s1.encode()) < 20000, str(len(s1)))
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "brief.json")
        P.write(b, p)
        m1 = open(p).read()
        b2 = dict(b, built_at="2099-01-01T00:00:00Z")
        P.write(b2, p)
        check("no rewrite when only built_at changes", open(p).read() == m1)

    # 3b. no churn between two cloud builds 30 min apart when no new bar arrived (only built_at differs)
    # (night-reds 2026-11-22: a fixed 2026-11-20 broke once the PC's Nov 20 bars landed; take the first weekday after the
    # newest bar, so "no new bar arrived" stays true whatever data/ holds)
    nd = bars[-1][1].date() + dt.timedelta(days=1)          # a bar = (epoch, ET datetime, o, h, l, c)
    while nd.weekday() >= 5:
        nd += dt.timedelta(days=1)
    c1 = P.build(at(f"{nd}T06:10"), bars=bars, measured=meas)
    c2 = P.build(at(f"{nd}T06:40"), bars=bars, measured=meas)
    check(f"no churn: 06:10 vs 06:40 ({nd}, after the newest bar)", {**c1, "built_at": 0} == {**c2, "built_at": 0})

    # 4. no look-ahead: a brief at 08:05 never sees a bar that closes after 08:05
    bars_to = dt.datetime.strptime(b["data"]["bars_to"], "%Y-%m-%d %H:%M")
    check("no future bars", bars_to <= dt.datetime(2026, 11, 10, 8, 0), b["data"]["bars_to"])
    check("bias uses 07:55 close", b["bias"]["inputs"]["overnight_move_pts"] is not None)

    # 5. recap after the close
    r = P.build(at("2026-11-10T16:30"), bars=bars, measured=meas)
    check("phase post", r["phase"] == "post")
    check("recap filled", isinstance(r["recap"], dict) and r["recap"]["rth_close"] is not None)
    d10 = next(x for x in P.days_table(bars) if x["day"] == "2026-11-10")
    check("recap body = 15:55 close - 09:30 open", abs(r["recap"]["body_pts"] - round(d10["rth_close"] - d10["rth_open"], 1)) < 0.06)

    # 5b. yesterday's recap (the cloud gets the day's bars only after 17:05 ET): always there the next morning
    nx = P.build(at("2026-10-29T07:00"), bars=bars, measured=meas)
    pr = nx.get("prev_recap") or {}
    check("prev_recap day", pr.get("day") == "2026-10-28", str(pr.get("day")))
    check("prev_recap: live wins over its paper twin", [t["src"] for t in pr.get("trades", []) if t["bot"] == "LIT"] == ["live"],
          str(pr.get("trades")))
    check("prev_recap traded text", pr.get("traded", "").startswith("Zlarior: 1 trade"), pr.get("traded", ""))

    # 6. windows: Thanksgiving early close (13:00 -> windows end 12:45), Monday = no EMA
    t = P.build(at("2026-11-26T07:00"), bars=bars, measured=meas)
    lit = t["bots"][0]
    check("early close set", t["early_close"] == "13:00", str(t["early_close"]))
    check("early close: LIT ends 12:45", lit["windows"] == [{"from": "02:00", "to": "12:45"}], str(lit["windows"]))
    mon = P.build(at("2026-11-16T07:00"), bars=bars, measured=meas)
    ema = next(x for x in mon["bots"] if x["id"] == "atlas_ema")
    check("Monday: ATLAS EMA off", ema["windows"] == [] and ema["state"] == "off_today")
    check("Monday: LIT Monday rule text", "Monday rule" in mon["bots"][0]["waiting_for"])
    sat = P.build(at("2026-11-21T12:00"), bars=bars, measured=meas)
    check("weekend -> next Monday's brief", sat["day"] == "2026-11-23" and sat["weekday"] == "Mon", sat["day"])
    eve = P.build(at("2026-11-19T19:00"), bars=bars, measured=meas)
    check("18:00+ belongs to the next day", eve["day"] == "2026-11-20" and eve["bots"][0]["state"] == "before")

    # 7. the pre-registered rules
    check("B1 up", P.b1_call(50, 200) == "up")
    check("B1 down", P.b1_call(-41, 200) == "down")
    check("B1 none", P.b1_call(39, 200) == "none")
    check("B2 fades an up day", P.b2_call({"open": 100, "close": 160}, 200) == "down")
    check("B2 tiny candle none", P.b2_call({"open": 100, "close": 110}, 200) == "none")
    check("binomial p", abs(P.binom_p(60, 100) - 0.0284) < 0.001, str(P.binom_p(60, 100)))

    # 8. honesty: the stored measurement matches a fresh one, and 'works' false -> context_only
    fresh = P.measure(bars=bars, write=False)
    check("stored = fresh measurement", fresh["rules"] == meas["rules"])
    check("context_only = not works", b["bias"]["context_only"] == (not b["bias"]["works"]))
    for k in ("2021-25", "2026H1", "2026H2"):
        check(f"measured {k} has n + hit", b["bias"]["measured"].get(k, {}).get("n", 0) > 0)

    # 9. privacy + futures only: no account ids (long digit runs) and no Yahoo in the tool
    blob = P.dumps(b)
    import re
    check("no long digit run (account ids)", not re.search(r"\d{7,}", blob))
    src = open(os.path.join(ROOT, "tools", "premarket_brief.py"), encoding="utf-8").read()
    check("no yahoo in the tool", "yfinance" not in src and "query1.finance" not in src)
    check("read-only: no order code", "place_order" not in src and "arm(" not in src)

    print(f"\n{len(OK)} passed, {len(BAD)} failed")
    return 1 if BAD else 0


if __name__ == "__main__":
    sys.exit(main())
