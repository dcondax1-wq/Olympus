"""Goals (engine/goals.py, 2026-10-25): each eval vs target / floor / 10 sessions, the week vs 2-4 (LIT) and 3-4 (ATLAS),
the month vs the backtest band, the ATLAS scorecard, payout, scale, the calendar, the build + API wiring, read-only.

  python -X utf8 -m tests.test_goals          # ~2 s, no engine runs, nothing written outside temp dirs
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import goals as G  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:300]}"), flush=True)


def ts(y, mo, d, h, mi=0):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


def lit_eval(**kw):
    e = {"start_balance": 50000.0, "balance": 49710.80, "profit": -289.20, "to_target": 3289.20, "target_balance": 53000.0,
         "floor": 48168.20, "room": 1542.60, "mll": 2000.0, "session": 4, "sessions": 10, "status": "open", "start": "2026-10-19",
         "clock_text": "session 4 of 10, 6 left, $3,289 to go", "anchor": {"balance": 49710.8}}
    e.update(kw)
    return e


def fixture(trades=None, atlas=None, ab=None, funded=None, sc=None):
    acc = [{"id": "mffu50k_eval", "source": "pc", "kind": "eval", "conn": {"connected": True}, "eval": lit_eval(),
            "trades": trades or [], "days": [["2026-10-20", -289.2], ["2026-10-21", 0.0]]},
           {"id": "cloud_paper", "source": "cloud", "kind": "paper", "eval": lit_eval(balance=49900, room=1900), "trades": []}]
    if funded:
        acc.append({"id": "mffu50k_funded", "source": "pc", "kind": "funded", "eval": {"balance": funded}})
    strat = [{"key": "ema_lon_vix", "short": "EMA", "trades": atlas or []}, {"key": "lit_asia", "short": "Asia",
                                                                               "trades": [{"day": "2026-10-27", "entry_t": 1, "r": 1, "usd": 99, "exit_kind": "TARGET"}]}]
    return {"accounts": acc, "live": {}, "second": {"strategies": strat, "account_b": ab,
                                                    "scorecard": {"account_b": sc or {"n": 0, "need": 20, "kind": "collecting", "text": "collecting (0/20)"}}},
            "scale": {"step": 0, "of": 4, "next": {"action": "buy an MFFU Builder 25K for ATLAS", "progress": 50, "ready": False},
                      "sentence": "You are at step 0.", "accounts": [{"strategy": "ATLAS", "stage": "planned"}]},
            "perf": {"range": {"bands": {"H2": {"usd_eval_per_session": 116.1}}}}}


def account_checks():
    g = G.build(fixture(), now=ts(2026, 10, 27, 10))         # Tuesday
    lit, at = g["accounts"]
    check("LIT: to go from the anchored eval ($3,289.20)", abs(lit["to_go"] - 3289.20) < 0.01, lit)
    check("LIT: room / floor carried", lit["room"] == 1542.60 and lit["floor"] == 48168.20, lit)
    check("LIT: sessions left from the clock text", lit["sessions_left"] == 6 and lit["sessions_used"] == 4, lit)
    check("LIT: days traded counts non-zero days", lit["days_traded"] == 1 and lit["min_days"] == 2, lit)
    check("LIT: plain sentence", lit["sentence"] == "$3,289 to go on the 50K, drawdown left $1,543 of $2,000.", lit["sentence"])
    check("LIT: progress 0 when below the start", lit["progress"] == 0.0, lit["progress"])
    check("LIT: the PC account wins over the cloud paper", lit["source"] == "PC bot" and lit["anchored"], lit)
    check("ATLAS: not started without account B", at["stage"] == "planned" and at["level"] == "idle" and at["balance"] is None, at)
    check("ATLAS: 25K plan defaults (target $1,500, MLL $1,000)", at["profit_target"] == 1500 and at["mll"] == 1000, at)
    ab = {"account": "Sim25K", "enabled": True, "plan_label": "MFFU Builder 25K",
          "eval": {"start_balance": 25000.0, "balance": 25600.0, "profit": 600.0, "target": 26500.0, "to_target": 900.0,
                   "floor": 24600.0, "room": 1000.0, "session": 3, "status": "open", "days_traded": 2}}
    at = G.build(fixture(ab=ab), now=ts(2026, 10, 27, 10))["accounts"][1]
    check("ATLAS: account B eval read", at["stage"] == "eval" and at["to_go"] == 900 and abs(at["progress"] - 0.4) < 1e-9, at)
    check("ATLAS: sessions left = 10 - used without a clock text", at["sessions_left"] == 7, at)
    p = G.account_goal("lit50k", lit_eval(status="passed", balance=53050, profit=3050, to_target=-50), "eval", "PC bot")
    check("passed: sentence + good", p["level"] == "good" and "Passed" in p["sentence"] and p["to_go"] == 0, p)
    f = G.account_goal("lit50k", lit_eval(status="failed", room=0), "eval", "PC bot")
    check("failed: sentence + bad", f["level"] == "bad" and "failed" in f["sentence"], f)
    late = G.account_goal("lit50k", lit_eval(session=12, clock_text=""), "eval", "PC bot")
    check("past session 10: warn, no session counter in the sentence (owner 2026-11-03)", late["level"] == "warn" and "session" not in late["sentence"], late)
    low = G.account_goal("lit50k", lit_eval(room=300), "eval", "PC bot")
    check("room under 25% of the MLL: bad", low["level"] == "bad", low)


def week_checks():
    T = [{"day": "2026-10-26", "r": 1.2, "pnl": 400, "entry_t": 1}, {"day": "2026-10-27", "r": -1, "pnl": -300, "entry_t": 2},
         {"day": "2026-10-20", "r": 2, "pnl": 700, "entry_t": 0}]
    w = G.build(fixture(trades=T), now=ts(2026, 10, 27, 10))["week"]["lit"]
    check("LIT week: 2 trades Mon-Tue -> met", w["n"] == 2 and w["status"] == "met" and w["usd"] == 100, w)
    check("LIT week: day strip Mon-Fri", [d["n"] for d in w["days"]] == [1, 1, 0, 0, 0] and w["days"][1]["today"], w["days"])
    w = G.build(fixture(), now=ts(2026, 10, 27, 10))["week"]["lit"]
    check("LIT week: 0 trades on Tuesday is on pace", w["status"] == "on_pace", w)
    w = G.build(fixture(), now=ts(2026, 10, 29, 10))["week"]["lit"]
    check("LIT week: 0 trades on Thursday is behind", w["status"] == "behind", w)
    w = G.build(fixture(trades=T), now=ts(2026, 10, 31, 10))["week"]["lit"]
    check("weekend: the coming week + last week's count", w["status"] == "upcoming" and w["last_week"] == 2 and w["monday"] == "2026-11-02", w)
    five = [{"day": "2026-10-2" + str(6 + i % 3), "r": 1, "pnl": 10, "entry_t": i} for i in range(5)]
    w = G.build(fixture(trades=five), now=ts(2026, 10, 29, 10))["week"]["lit"]
    check("LIT week: 5 trades is above 2-4", w["status"] == "above", w)
    A = [{"day": "2026-10-26", "entry_t": 1, "r": 1, "usd": 500, "exit_kind": "TARGET"},
         {"day": "2026-10-27", "entry_t": 2, "r": None, "usd": None, "exit_kind": "OPEN"}]
    w = G.build(fixture(atlas=A), now=ts(2026, 10, 27, 10))["week"]["atlas"]
    check("ATLAS week: members only (lit_asia ignored), open trade counted", w["n"] == 2 and w["lo"] == 3 and w["hi"] == 4, w)
    check("evening (18:00+) counts as the next trading day", G.trading_day(ts(2026, 10, 26, 19)) == "2026-10-27")


def month_checks():
    T = [{"day": "2026-10-20", "r": 2, "pnl": 700, "entry_t": 0}]
    m = G.build(fixture(trades=T), now=ts(2026, 10, 27, 10))["month"]
    check("month: $ since the eval start", m["usd"] == 700 and m["trades"] == 1, m)
    check("month: sessions counted from the eval start (Oct 19)", m["sessions"] == 7, m)
    check("month: average fallback without the band", m["expected"]["kind"] == "average" and m["expected"]["p50"] == round(116.1 * 7), m)
    B = {"bands": {"H2": {"usd_eval": [[float(i * 10 * (k + 1)) for i in range(1, 100)] for k in range(60)]}}}
    m = G.build(fixture(trades=T), now=ts(2026, 10, 27, 10), band=B)["month"]
    check("month: band p10 / p50 / p90 + percentile", m["expected"]["kind"] == "bootstrap" and m["expected"]["p10"] == 700 and m["expected"]["p90"] == 6300 and m["level"] == "good" and m["expected"]["pct"] == 10.0, m)
    m = G.build(fixture(trades=[{**T[0], "pnl": 100}]), now=ts(2026, 10, 27, 10), band=B)["month"]
    check("month: under p10 -> warn", m["level"] == "warn", m)
    m = G.build(fixture(), now=ts(2026, 10, 27, 10))["month"]
    check("month: no trade -> plain sentence, no level", m["level"] is None and "No LIT trade" in m["sentence"], m)


def other_checks():
    g = G.build(fixture(sc={"n": 7, "need": 20, "kind": "on_track", "text": "on track (p44)"}), now=ts(2026, 10, 27, 10))
    check("scorecard: 7 of 20", g["scorecard"]["n"] == 7 and abs(g["scorecard"]["frac"] - 0.35) < 1e-9 and "7 of 20" in g["scorecard"]["sentence"], g["scorecard"])
    g2 = G.build(fixture(sc={"n": 22, "need": 20, "kind": "ready"}), now=ts(2026, 10, 27, 10))
    check("scorecard: ready", g2["scorecard"]["level"] == "good" and "ready" in g2["scorecard"]["sentence"], g2["scorecard"])
    check("payout: not funded yet", g["payout"]["stage"] == "eval" and g["payout"]["frac"] == 0, g["payout"])
    p = G.build(fixture(funded=52000), now=ts(2026, 10, 27, 10))["payout"]
    check("payout: funded, $2,100 before the ask at $54,100 (the max $2,000 above the $2,100 buffer)", p["stage"] == "funded" and p["ask_at"] == 54100 and "$2,100" in p["sentence"], p)
    check("scale: step + progress", g["scale"]["step"] == 0 and g["scale"]["frac"] == 0.5, g["scale"])
    check("lines: accounts first, every part present", [x["k"] for x in g["lines"]][:2] == ["lit50k", "atlas25k"] and len(g["lines"]) == 8, g["lines"])
    c = g["calendar"]
    check("calendar: FOMC Oct 28 in the next 14 days", any(n["day"] == "2026-10-28" and "FOMC" in n["event"] for n in c["news"]), c["news"])
    check("calendar: US clocks go back Nov 1", any(x["day"] == "2026-11-01" and x["who"] == "US" for x in c["clocks"]), c["clocks"])
    e = G.build({}, now=ts(2026, 11, 20, 10))["calendar"]["early_close"]
    check("calendar: Thanksgiving + Black Friday early closes", [x["day"] for x in e][:2] == ["2026-11-26", "2026-11-27"], e)
    empty = G.build({}, now=ts(2026, 10, 27, 10))
    check("empty data: never raises, every part there", all(k in empty for k in ("accounts", "week", "month", "scorecard", "payout", "scale", "calendar")), list(empty))
    bad = G.build({"accounts": "x", "second": {"strategies": [None, 3]}}, now=ts(2026, 10, 27, 10))
    check("broken data: parts degrade, no exception", isinstance(bad.get("lines"), list), bad)
    json.dumps(G.build(fixture(), now=ts(2026, 10, 27, 10)))
    check("JSON-serialisable", True)


def wiring_checks():
    src = open(os.path.join(ROOT, "engine", "goals.py"), encoding="utf-8").read()
    check("goals.py is read-only (no routing / sizing writes / file writes)",
          not any(x in src for x in ("ninjatrader", "place_order", "open(p, \"w\"", "'w'", "\"w\")")), "")
    b = open(os.path.join(ROOT, "tools", "build_web_dashboard.py"), encoding="utf-8").read()
    check("build_web_dashboard: data.json + home.json goals", 'data["goals"] = _goals.site_block(data)' in b and '"goals": data.get("goals")' in b)
    try:
        from engine import next_api as N
        r = N.goals_view()
        d = json.loads(r.body)
        check("/api/next/goals answers 200 with lines", r.status_code == 200 and isinstance(d.get("lines"), list), d)
    except ImportError as e:                       # fastapi missing on this machine
        check("/api/next/goals (fastapi missing: skipped)", True, e)
    web = os.path.join(ROOT, "tools", "web_public")
    idx = open(os.path.join(web, "index.html"), encoding="utf-8").read()
    check("index.html loads goals.js + features.js", "goals.js?v=" in idx and "features.js?v=" in idx)
    js = open(os.path.join(web, "features.js"), encoding="utf-8").read()
    n = js.count("feat(")
    check(f"features.js lists 100+ features ({n})", n >= 100, n)
    sw = open(os.path.join(web, "sw.js"), encoding="utf-8").read()
    check("sw.js caches goals.js + features.js", "goals.js" in sw and "features.js" in sw)


def main(argv=None):
    account_checks()
    week_checks()
    month_checks()
    other_checks()
    with tempfile.TemporaryDirectory():
        wiring_checks()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
