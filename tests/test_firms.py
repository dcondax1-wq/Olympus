"""Firm rule profiles + the rule engine (engine/firms.py, research/props/firm_rules.json; read-only, no orders).

    python -X utf8 -m tests.test_firms

Covers: the data (every value has verified / date, MFFU Builder 25K / 50K verified from research/lit/mffu_rules.json,
unknown = null, the owner's prices only), EOD vs intraday trailing vs static floors and the lock, hard / soft daily loss,
contracts (micros / minis), the best-day (consistency) rule, news windows, flat time, hedging across accounts, the
personal LIVE profile (own stops, never an eval), eval / funded status (pass, min days, consistency, fail, payout ready).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import firms as FM  # noqa: E402

RES = []
ET = ZoneInfo("America/New_York")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def ts(day, hh, mm=0):
    y, m, d = (int(x) for x in day.split("-"))
    return int(_dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


def order(side="buy", qty=1, entry=20000.0, stop=19980.0, target=20060.0, sym="NQ"):
    return {"side": side, "qty": qty, "entry": entry, "stop": stop, "target": target, "sym": sym}


def data_checks():
    D = FM.load()
    P = D.get("plans") or {}
    check("firm_rules.json: 7 firms (MFFU, Lucid, FundedNext, Apex, Topstep, Take Profit Trader, Alpha Futures)",
          set(D.get("firms") or {}) == {"mffu", "lucid", "fundednext", "apex", "topstep", "tpt", "alpha"}, list(D.get("firms") or {}))
    check("MFFU Builder 25K / 50K / 100K / 150K, Rapid, Rapid EOD, Pro plans present",
          all(k in P for k in ("mffu_builder_25k", "mffu_builder_50k", "mffu_builder_100k", "mffu_builder_150k", "mffu_rapid_50k",
                               "mffu_rapid_eod_50k", "mffu_pro_50k")))
    bad = [(pid, b, k) for pid, p in P.items() for b in ("eval", "funded", "payout") for k, x in p[b].items()
           if not (isinstance(x, dict) and "v" in x and "verified" in x and "date" in x)]
    check("every value carries v / verified / date", not bad, bad[:5])
    unver = [(pid, b, k) for pid, p in P.items() for b in ("eval", "funded", "payout") for k, x in p[b].items()
             if x["verified"] and x["v"] is None]
    check("an unknown value is never marked verified", not unver, unver[:5])
    M = json.load(open(os.path.join(ROOT, "research", "lit", "mffu_rules.json"), encoding="utf-8"))
    e50 = P["mffu_builder_50k"]["eval"]
    check("MFFU 50K verified from mffu_rules.json: target $3,000, $2,000 EOD trailing locked at +$100, $1,000 soft DLL, 40 micros",
          e50["target"] == {**e50["target"], "v": M["limits"]["builder_50k"]["target"], "verified": True}
          and e50["dd_amount"]["v"] == M["limits"]["builder_50k"]["mll"] and e50["dd_amount"]["verified"]
          and e50["dd_type"]["v"] == "eod" and e50["lock"]["v"] == 100.0 and e50["dll"]["v"] == 1000.0
          and e50["dll_type"]["v"] == "soft" and e50["max_micros"]["v"] == 40 and e50["max_minis"]["v"] == 4
          and all(e50[k]["verified"] for k in ("dll", "dll_type", "max_micros", "lock")), e50)
    check("MFFU 50K min days is a conflict in the rulebook: not verified", P["mffu_builder_50k"]["eval"]["min_days"]["verified"] is False)
    e25 = P["mffu_builder_25k"]
    check("MFFU 25K verified: $1,500 target, $1,000 EOD, $600 soft DLL, 20 micros; payouts $250-$1,000, buffer $1,100, 50% best day",
          e25["eval"]["target"]["v"] == 1500 and e25["eval"]["dd_amount"]["v"] == 1000 and e25["eval"]["dll"]["v"] == 600
          and e25["eval"]["max_micros"]["v"] == 20 and e25["payout"]["min"]["v"] == 250 and e25["payout"]["max"]["v"] == 1000
          and e25["payout"]["buffer"]["v"] == 1100 and e25["payout"]["consistency"]["v"] == 0.5
          and all(e25["eval"][k]["verified"] for k in ("target", "dd_amount", "dll", "max_micros")))
    pr = {pid: p["price"]["v"] for pid, p in P.items() if p["price"]["v"] is not None}
    check("prices: only the owner's real MFFU prices (Builder 50K $91.80, Builder 25K $63), every other price null",
          pr == {"mffu_builder_50k": 91.8, "mffu_builder_25k": 63.0}, pr)
    check("assumed values are unknown (null), not guessed: TPT drawdown lock, Alpha 50K max contracts, Apex DLL type",
          P["tpt_50k"]["eval"]["lock"]["v"] is None and P["alpha_std_50k"]["eval"]["max_micros"]["v"] is None
          and P["apex_eod_50k"]["eval"]["dll_type"]["v"] is None)
    check("third-party values are not verified (Apex 50K target)", P["apex_eod_50k"]["eval"]["target"]["verified"] is False)
    F = D["firms"]
    check("firm rules: MFFU hedging banned across all accounts (verified), Apex bots prohibited, Topstep no NinjaTrader",
          F["mffu"]["hedging"]["v"] == "banned_all_accounts" and F["mffu"]["hedging"]["verified"]
          and F["apex"]["bots"]["v"] == "prohibited" and F["topstep"]["ninjatrader"]["v"] is False)
    import subprocess
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_firm_rules.py"), "--check"], capture_output=True, text=True)
    check("tools/build_firm_rules.py --check: the stored file = a rebuild from the repo's research", r.returncode == 0, r.stdout + r.stderr)


def floor_checks():
    P = FM.profile("mffu_builder_50k")
    st = FM.book(50000.0, [("2026-10-19", 1, 1500.0), ("2026-10-20", 2, -300.0)], "2026-10-21")
    fr = FM.floor_room(P, st)
    check("EOD trailing: floor = best CLOSING balance - $2,000 (51,500 -> 49,500), room = 51,200 - 49,500",
          fr["floor"] == 49500.0 and fr["room"] == 1700.0 and not fr["locked"], fr)
    st2 = FM.book(50000.0, [("2026-10-19", 1, 2500.0)], "2026-10-20")
    fr2 = FM.floor_room(P, st2)
    check("the trailing floor stops at start + $100 ($50,100)", fr2["floor"] == 50100.0 and fr2["locked"], fr2)
    st3 = FM.book(50000.0, [("2026-10-21", 1, 900.0)], "2026-10-21")
    fr3 = FM.floor_room(P, st3)
    check("EOD: today's intraday gain does not move the floor (only the session close does)", fr3["floor"] == 48000.0, fr3)
    st3o = {**st3, "open_pnl": -500.0}
    check("EOD: an open loss counts against the room now", FM.floor_room(P, st3o)["room"] == 50900.0 - 500.0 - 48000.0)
    PI = FM.profile("mffu_rapid_50k", "funded")
    check("MFFU Rapid funded = intraday trailing (verified in the hub)", PI["dd_type"] == "intraday" and PI["verified"]["dd_type"] is True, PI.get("dd_type"))
    fi = FM.floor_room(PI, st3)
    check("intraday trailing: the floor follows the best balance during the day (50,900 -> 48,900)", fi["floor"] == 48900.0, fi)
    fi2 = FM.floor_room(PI, {**st3, "open_pnl": 400.0})
    check("intraday trailing: open profit raises the floor too", fi2["floor"] == 49300.0 and fi2["room"] == 2000.0, fi2)
    PS = dict(P, dd_type="static")
    check("static: the floor never moves (start - max loss)", FM.floor_room(PS, st)["floor"] == 48000.0)
    PU = dict(P, lock=None)
    check("unknown lock = the floor keeps trailing (conservative): 52,500 -> 50,500", FM.floor_room(PU, st2)["floor"] == 50500.0)
    PX = dict(P, dd_amount=None)
    check("unknown max loss = no room: every order refused", FM.check(PX, st, order())["ok"] is False)
    PT = dict(P, dd_type=None)
    check("unknown drawdown type = read as intraday (the strictest)", FM.floor_room(PT, st3)["floor"] == 48900.0)


def rule_checks():
    P = FM.profile("mffu_builder_50k")
    st = FM.book(50000.0, [], "2026-10-21")
    now = ts("2026-10-21", 9, 45)
    c = FM.check(P, st, order(qty=10), now=now)
    check("a normal order fits (10 micros, 20-pt stop, $2,000 room)", c["ok"] and c["max_qty"] == 10, c)
    c = FM.check(P, st, order(qty=45, stop=19995.0), now=now)
    check("contracts: 45 micros on a 40-micro plan -> capped at 40 (warned)", c["ok"] and c["max_qty"] == 40, c)
    c = FM.check(P, st, order(qty=45), now=now)
    check("45 micros at a 20-pt stop ($1,930 at risk) -> capped by the $1,000 soft daily loss at 23", c["ok"] and c["max_qty"] == 23, c)
    c = FM.check(P, {**st, "open_micros": 35}, order(qty=10, stop=19995.0), now=now)
    check("contracts: 35 micros open + 10 -> 5", c["max_qty"] == 5, c)
    c = FM.check(P, st, {**order(qty=5, stop=19995.0), "contract": "NQ"}, now=now)
    check("5 MINIS = 50 micro-equivalents -> capped at 40 (4 minis)", c["max_qty"] == 40, c)
    st_l = FM.book(50000.0, [("2026-10-20", 1, -1700.0)], "2026-10-21")
    c = FM.check(P, st_l, order(qty=10), now=now)
    one = (20 + FM.SLIP_PTS) * 2.0 + FM.COMM
    check("the floor at the stop: $300 room fits 7 micros at a 20-pt stop ($42.90 each)",
          c["ok"] and c["max_qty"] == int((300 - 1e-6) // one), (c, one))
    st_f = FM.book(50000.0, [("2026-10-20", 1, -2000.0)], "2026-10-21")
    c = FM.check(P, st_f, order(), now=now)
    check("floor reached: refused (account failed)", not c["ok"] and "floor" in c["block"][0], c)
    st_d = FM.book(50000.0, [("2026-10-21", ts("2026-10-21", 9, 0), -980.0)], "2026-10-21")
    c = FM.check(P, st_d, order(qty=10), now=now)
    check("soft daily loss: $20 left today -> 1 micro at a 20-pt stop ($42.90) does not fit -> refused", not c["ok"] and "soft" in " ".join(c["block"]), c)
    st_d2 = FM.book(50000.0, [("2026-10-21", ts("2026-10-21", 9, 0), -1000.0)], "2026-10-21")
    c = FM.check(P, st_d2, order(), now=now)
    check("daily loss limit reached: no new entry today", not c["ok"] and "daily loss limit reached" in c["block"][0], c)
    PH = dict(P, dll_type="hard")
    c = FM.check(PH, st_d, order(), now=now)
    check("hard daily loss named as hard", not c["ok"] and "hard" in " ".join(c["block"]), c)
    PR = FM.profile("mffu_rapid_eod_50k")
    check("MFFU Rapid EOD eval: best day 30% (verified)", PR["consistency"] == 0.3 and PR["verified"]["consistency"] is True)
    c = FM.check(PR, st, order(qty=20, target=20060.0), now=now)
    cap = 0.3 * 3000 * FM.BEST_DAY_MARGIN
    check("best-day rule: a 60-pt winner pays <= $855 today -> 7 micros", c["ok"] and c["max_qty"] == int(cap // (60 * 2 - FM.COMM)), c)
    st_w = FM.book(50000.0, [("2026-10-21", ts("2026-10-21", 8, 0), 850.0)], "2026-10-21")
    c = FM.check(PR, st_w, order(qty=5), now=now)
    check("best-day rule: today already +$850 -> no room for another winner -> refused", not c["ok"], c)
    # news
    PN = FM.profile("mffu_rapid_50k", "funded")
    rel = [ts("2026-10-21", 8, 30)]
    check("Rapid funded: flat 2 min around Tier-1 news", isinstance(PN["news"], dict))
    c = FM.check(PN, st, order(), now=ts("2026-10-21", 8, 29), releases=rel)
    c2 = FM.check(PN, st, order(), now=ts("2026-10-21", 8, 33), releases=rel)
    c3 = FM.check(P, st, order(), now=ts("2026-10-21", 8, 29), releases=rel)
    check("news window blocks at 08:29 for an 08:30 release, not at 08:33, never on Builder", not c["ok"] and c2["ok"] and c3["ok"], (c, c2, c3))
    c = FM.check(P, st, order(), now=ts("2026-10-21", 16, 6))
    check("MFFU flat by 16:10: no entry at 16:06", not c["ok"] and "flat time" in " ".join(c["block"]), c)
    # hedging
    pos = [{"account": "ATLAS 25K", "sym": "NQ", "dir": -1}]
    c = FM.check(P, st, order(side="buy"), positions=pos, now=now)
    check("hedging: a LONG while ATLAS holds a SHORT on NQ is refused", not c["ok"] and "hedging" in c["block"][0], c)
    c = FM.check(P, st, order(side="buy", sym="MNQ"), positions=pos, now=now)
    check("MNQ and NQ are the same underlying", not c["ok"])
    c = FM.check(P, st, order(side="buy"), positions=[{"account": "x", "sym": "ES", "dir": -1}], now=now)
    check("a short on ES is not a hedge of an NQ long", c["ok"], c)
    c = FM.check(P, st, order(side="sell", entry=20000, stop=20020, target=19940), positions=pos, now=now)
    check("the same side as another account is fine (copy trading)", c["ok"], c)
    c = FM.check(P, st, {"side": "buy", "qty": 1, "sym": "NQ"}, now=now)
    check("no stop distance: refused (the floor at the stop cannot be checked)", not c["ok"])


def live_checks():
    L = FM.live_profile({"start": 10000, "max_risk_usd": 100, "daily_stop_usd": 200, "weekly_stop_usd": 300, "max_micros": 3})
    check("LIVE profile: labelled LIVE, no prop floor, own stops", L["kind"] == "live" and "LIVE" in L["label"] and L["dd_type"] == "none")
    st = FM.book(10000.0, [], "2026-10-21")
    now = ts("2026-10-21", 10, 0)
    c = FM.check(L, st, order(qty=10, stop=19990.0), now=now)
    one = (10 + FM.SLIP_PTS) * 2 + FM.COMM
    check("LIVE: max $100 risk a trade at a 10-pt stop -> 4, then max 3 micros -> 3", c["ok"] and c["max_qty"] == min(3, int(100 // one)), c)
    st_d = FM.book(10000.0, [("2026-10-21", ts("2026-10-21", 9, 0), -190.0)], "2026-10-21")
    c = FM.check(L, st_d, order(qty=3, stop=19990.0), now=now)
    check("LIVE daily stop: $10 left -> refused", not c["ok"], c)
    st_w = FM.book(10000.0, [("2026-10-19", 1, -150.0), ("2026-10-20", 2, -150.0)], "2026-10-21")
    c = FM.check(L, st_w, order(qty=1, stop=19990.0), now=now)
    check("LIVE weekly stop reached (-$300 this week): refused until Monday", not c["ok"] and "weekly" in c["block"][0], c)
    st_m = FM.book(10000.0, [("2026-10-16", 1, -250.0)], "2026-10-21")
    check("LIVE weekly stop counts this week only", FM.check(L, st_m, order(qty=1, stop=19990.0), now=now)["ok"])
    check("LIVE status never 'passed' (no eval)", FM.status(L, FM.book(10000.0, [("2026-10-20", 1, 5000.0)], "2026-10-21"))["status"] == "running")


def status_checks():
    P = FM.profile("mffu_builder_50k")
    s = FM.status(P, FM.book(50000.0, [("2026-10-20", 1, 3100.0)], "2026-10-21"))
    check("eval passed at +$3,000 with 1 trading day (min 1)", s["status"] == "passed", s)
    PT = FM.profile("tpt_50k")
    s = FM.status(PT, FM.book(50000.0, [("2026-10-20", 1, 3100.0)], "2026-10-21"))
    check("TPT eval: target reached in 1 day but min 3 days -> still running", s["status"] == "running" and "trading days" in (s.get("why") or ""), s)
    s = FM.status(PT, FM.book(50000.0, [("2026-10-16", 1, 1800.0), ("2026-10-19", 1, 600.0), ("2026-10-20", 1, 700.0)], "2026-10-21"))
    check("TPT eval: best day 58% > 50% consistency -> not passed yet", s["status"] == "running" and "best day" in (s.get("why") or ""), s)
    s = FM.status(P, FM.book(50000.0, [("2026-10-20", 1, -2000.0)], "2026-10-21"))
    check("eval failed at the floor", s["status"] == "failed", s)
    PF = FM.profile("mffu_builder_50k", "funded")
    s = FM.status(PF, FM.book(50000.0, [("2026-10-20", 1, 2700.0)], "2026-10-21"))
    check("funded: $2,700 profit, $2,100 buffer -> $600 above, payout ready ($500 minimum)", s["payout"]["ready"] and s["payout"]["above_buffer"] == 600.0, s)
    s = FM.status(PF, FM.book(50000.0, [("2026-10-20", 1, 2700.0)], "2026-10-21", payouts={"2026-10-20": 500.0}))
    check("funded: after a $500 payout only $100 above the buffer -> not ready", not s["payout"]["ready"], s)
    lines = FM.describe(FM.profile("mffu_builder_25k"))
    check("describe(): plain words (EOD trailing, the lock, the daily loss, contracts, hedging)",
          any("end-of-day trailing" in x for x in lines) and any("Daily loss $600" in x for x in lines)
          and any("20 micros" in x for x in lines) and any("ALL your accounts" in x for x in lines), lines)
    check("unknown plan -> None", FM.profile("no_such_plan") is None)


def main() -> int:
    data_checks()
    floor_checks()
    rule_checks()
    live_checks()
    status_checks()
    n = sum(RES)
    print(f"firms: {n}/{len(RES)} {'ALL PASS' if n == len(RES) else 'FAILED'}")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
