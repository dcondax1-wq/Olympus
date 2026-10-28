"""AI Insights API (engine/insight_api.py, web_next/js/next/insight.js): every panel from a fake running bot (synthetic Brain,
ATLAS run) and temp research / journal / bar files only; the window countdown, the trader's grade, similar trades, the
scalp research slot, a broken panel not breaking the others, and the GET route. Nothing real is read for the verdicts and
nothing is written.

  python -X utf8 -m tests.test_insight_api        # ~2 s
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from engine import health_band, insight_api as I, second_scorecard as SC  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:400]}"), flush=True)


def at(y, m, d, hh, mm):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


NOW = at(2026, 10, 15, 4, 0)            # Thu 04:00 ET


def brain():
    lv = [{"label": "Asia low", "price": 29823.5, "side": "L", "kind": "asia", "kind_label": "Asia box", "dist": -14.25, "dist_atr": -0.42,
           "taken": True, "taken_hm": "02:40", "depth_atr": 1.95, "also": []},
          {"label": "London 03-04 high", "price": 29869.5, "side": "H", "kind": "london", "kind_label": "London box", "dist": 31.75,
           "dist_atr": 0.94, "taken": False},
          {"label": "PDH", "price": 30210.0, "side": "H", "kind": "pd", "kind_label": "Previous day", "dist": 372.25, "dist_atr": 11.0, "taken": False},
          {"label": "equal lows", "price": 29700.0, "side": "L", "kind": "buildup", "kind_label": "Equal highs / lows", "dist": -137.75,
           "dist_atr": -4.1, "taken": False}]
    setup = {"id": "1:1", "t": NOW - 1800, "hm": "03:30", "dir": 1, "side": "LONG", "swept": ["Asia low", "PDL"], "ext": 29754.0, "cisd": 29790.25,
             "checks": [{"key": "idm", "ok": True, "text": "1 swing taken first, nearest 0.65 ATR from the level, 4 bars before the sweep"},
                        {"key": "depth", "ok": True}, {"key": "stop", "ok": True}],
             "status": "armed", "status_text": "Armed: limit 29,790.25 until 04:00 ET"}
    return {"v": 1, "t": NOW, "at": "Thu 04:00 ET", "day": "2026-10-15", "price": 29837.75, "atr": 33.64,
            "stage": {"key": "limit", "n": 6, "label": "Limit armed", "waiting": "Limit at 29,790.25 armed until 04:00 ET."},
            "watch": [{"dir": 1, "side": "LONG", "allowed": True, "stage": "cisd5", "swept": ["Asia low"], "depth_atr": 1.95, "depth_ok": True,
                       "idm_ok": True, "disp_ok": True, "cisd": 29790.25, "cisd_dist": -47.5, "cisd_closed": True, "text": "5m CISD closed"},
                      {"dir": -1, "side": "SHORT", "allowed": True, "stage": "sweep", "swept": []}],
            "nearest": {"above": [{"label": "London 03-04 high", "price": 29869.5, "dist": 31.75}], "below": []},
            "levels": lv, "setups": [setup], "rules": {"window": [[120, 930]]},
            "guards": {"news": [{"time": "08:30", "title": "CPI"}], "vix": {"vix": 15.2, "vxn": 20.1, "move": 300.0, "open18": 30000.0,
                                                                            "up": 30300.0, "dn": 29700.0}}}


def second_run():
    def s(label, short, stage, text, window, trades=(), cand=False, brain_=None):
        return {"label": label, "short": short, "on": True, "route": False, "route_label": "paper", "state": {"stage": stage, "text": text, "window": window,
                **({"t15": -1, "t60": -1} if short == "EMA" else {})}, "trades": list(trades), **({"candidate": True} if cand else {}),
                **({"brain": brain_} if brain_ else {})}
    tr = [{"day": "2026-10-13", "entry_t": NOW - 2 * 86400, "exit_t": NOW - 2 * 86400 + 600, "dir": -1, "exit_kind": "STOP", "r": -1.0, "usd": -500.0},
          {"day": "2026-10-15", "entry_t": NOW - 900, "exit_t": None, "dir": 1, "exit_kind": "OPEN", "r": None, "usd": None}]
    return {"t": NOW, "day": "2026-10-15", "strategies": {
        "ema_lon_vix": s("London EMA trend pullback", "EMA", "waiting", "waiting for a pullback to the 5m EMA 50 (29,863.55, 26 pts away)",
                         "03:00-09:30 ET", brain_={"checks": [{"name": "window", "ok": True}, {"name": "pull", "ok": False}, {"name": "cisd", "ok": None}]}),
        "macd_sweep": s("MACD divergence", "MACD", "armed", "Armed (long)", "02:00-05:00, 09:30-11:00 ET", trades=tr),
        "sr_nyreclaim": s("NY sweep-and-reclaim", "S/R", "off", "Outside its hours", "09:30-12:00 ET"),
        "sh_asia": s("Asia resweep hunt", "Asia hunt", "off", "Outside its hours", "Asia 18:00-02:00 ET", cand=True),
        "lit_asia": s("LIT + Asia slot", "LIT+Asia", "waiting", "x", "18:00-15:30 ET")}}


def write_fixtures(tmp):
    os.makedirs(os.path.join(tmp, "runs")); os.makedirs(os.path.join(tmp, "second")); os.makedirs(os.path.join(tmp, "writeups"))
    os.makedirs(os.path.join(tmp, "scalp"))
    days = [(dt.date(2026, 1, 2) + dt.timedelta(days=i)).isoformat() for i in range(0, 290)]
    days = [d for d in days if dt.date.fromisoformat(d).weekday() < 5]
    cols = ["day", "entry_t", "exit_t", "dir", "r", "pnl", "exit"]
    trades = []
    for i, d in enumerate(days[::3]):
        t0 = at(*map(int, d.split("-")), 3, 0)
        r = 2.0 if i % 2 == 0 else -1.0
        trades.append([d, t0, t0 + 3600, 1, r, r * 300, "TARGET" if r > 0 else "STOP"])
    json.dump({"trade_cols": cols, "trades": trades, "days": [[d, 0, 0, 0] for d in days]}, open(os.path.join(tmp, "runs", "lit_live.json"), "w"))
    # the journal: tags; 4 of its trades are in the run (outcome from the run), one is not
    J = []
    for k, tr in enumerate(trades[:8]):
        J.append({"key": f"{tr[0]}|{tr[1]}|1", "source": "backtest", "day": tr[0], "entry_t": tr[1], "dir": 1, "side": "LONG", "r": -9.0, "pnl": -9.0,
                  "exit": "STOP", "grade": "A" if k < 4 else "B", "buckets": {"session": "lon_early"}, "cause": None if k % 2 == 0 else "stale_trap"})
    J.append({"key": "2026-02-02|1|1", "source": "pc", "day": "2026-02-02", "entry_t": 1, "dir": 1, "side": "LONG", "r": 0.5, "pnl": 100.0,
              "exit": "EOD", "grade": "A", "buckets": {"session": "lon_early"}, "cause": None})
    with open(os.path.join(tmp, "journal.jsonl"), "w") as fh:
        for r in J:
            fh.write(json.dumps(r) + "\n")
    for k, fn in I.BEST.items():
        json.dump({"trades": [{"day": "2026-08-03", "r": 1.5, "pnl_usd": 750.0}, {"day": "2026-08-10", "r": -1.0, "pnl_usd": -500.0},
                              {"day": "2026-03-03", "r": 1.0, "pnl_usd": 500.0}]}, open(os.path.join(tmp, "second", fn), "w"))
    # 5m bars: 30 sessions of a steady up-drift (trend up on 15m / 1h), Asia + London ranges
    rows, t = [], at(2026, 9, 1, 0, 0)
    px = 29000.0
    while t <= NOW - 300:
        px += 0.4
        rows.append(f"{t},{px},{px + 3},{px - 3},{px + 0.2},100")
        t += 300
    open(os.path.join(tmp, "NQ_5m.csv"), "w").write("time,open,high,low,close,volume\n" + "\n".join(rows) + "\n")
    return J


class FakeBot(SimpleNamespace):
    pass


def main():
    tmp = tempfile.mkdtemp(prefix="le_insight_")
    saved = {k: getattr(I, k) for k in ("JOURNAL", "RUNS", "SECOND_DIR", "WRITEUPS", "SCALP_DIR", "BARS_5M", "VOL_DIR", "_news_next", "_bot")}
    sc_load, hb_load = SC.load, health_band.load
    try:
        J = write_fixtures(tmp)
        I.JOURNAL, I.RUNS, I.SECOND_DIR = os.path.join(tmp, "journal.jsonl"), os.path.join(tmp, "runs"), os.path.join(tmp, "second")
        I.WRITEUPS, I.SCALP_DIR, I.BARS_5M, I.VOL_DIR = os.path.join(tmp, "writeups"), os.path.join(tmp, "scalp"), os.path.join(tmp, "NQ_5m.csv"), tmp
        I._news_next = lambda now: {"next": {"event": "CPI", "t": NOW + 4.5 * 3600, "time": "08:30", "weekday": "Thu", "in_s": int(4.5 * 3600)}, "today": [{"time": "08:30", "event": "CPI"}]}
        band = {"expected": {"by_n": {str(n): {"cum_r_q": [x * n * 0.1 - 1 for x in range(21)], "usd": [0, 1, 2], "win": [40, 50, 60], "pf": [1, 2, 3]}
                                      for n in range(1, 41)}}}
        SC.load = lambda path=None: {"bands": {k: band for k in I.MEMBERS}}
        health_band.load = lambda path=None: None
        before = sorted(os.listdir(tmp))
        bot = FakeBot(brain=brain(), second=second_run(), running=True, acct_b=None, cfg={"sym": "NQ"}, bars_tail=[])
        v = I.build(bot, now=NOW)

        check("live mode from the running bot's Brain", v["mode"] == "live" and v["day"] == "2026-10-15", v.get("mode"))
        bad = [k for k in ("radar", "windows", "scorecard", "drift", "grade", "similar", "regime", "levels", "atlas", "strategy3")
               if not isinstance(v.get(k), dict) or v[k].get("error")]
        check("all 10 panels built", not bad, {k: v[k] for k in bad})
        L = v["radar"]["lit"]
        check("21 radar: LIT stage step 6 of 10 + both sides", L["stage_n"] == 6 and len(L["sides"]) == 2, L)
        short = next(s for s in L["sides"] if s["side"] == "SHORT")
        check("21 radar: the short side still needs a sweep", any("sweep" in n for n in short["needs"]), short)
        ema = next(m for m in v["radar"]["atlas"] if m["key"] == "ema_lon_vix")
        check("21 radar: EMA 1 of 3 checks, first miss, 26 pts away", ema["checks_ok"] == 1 and ema["checks_n"] == 3 and ema["first_fail"] == "pull"
              and ema["pts_away"] == 26.0, ema)
        check("21 radar: ATLAS shows the members + candidates, not the LIT shadow",
              {m["key"] for m in v["radar"]["atlas"]} == {"ema_lon_vix", "macd_sweep", "sr_nyreclaim", "sh_asia"}, v["radar"]["atlas"])

        # 22 windows: the page's rows (replayed clock = NOW in live mode the real clock is used, so test next_window directly)
        w = I.next_window([[120, 930]], NOW)
        check("22 LIT window open at Thu 04:00, closes 15:30", w["open"] and w["end_hm"] == "15:30" and w["closes_in_s"] == 11.5 * 3600, w)
        fri = at(2026, 10, 16, 16, 0)
        w = I.next_window([[120, 930]], fri)
        check("22 after Friday's close the next LIT window is Monday 02:00", not w["open"] and w["start_t"] == at(2026, 10, 19, 2, 0), w)
        w = I.next_window(I.windows_of("Asia 18:00-02:00 ET"), at(2026, 10, 18, 19, 0))
        check("22 Asia 18:00-02:00 open on Sunday 19:00 (Monday's session)", w["open"] and w["end_t"] == at(2026, 10, 19, 2, 0), w)
        w = I.next_window(I.windows_of("03:00-09:30 ET"), fri, skip_monday=True)
        check("22 EMA (never Monday) opens Tuesday 03:00 after Friday", w["start_t"] == at(2026, 10, 20, 3, 0), w)
        check("22 windows_of parses two windows", I.windows_of("02:00-05:00, 09:30-11:00 ET") == [[120, 300], [570, 660]])
        check("22 a row per strategy (LIT + 4)", len(v["windows"]["rows"]) == 5, v["windows"]["rows"])

        # 23 scorecard
        sc = {r["key"]: r for r in v["scorecard"]["rows"]}
        lit = sc["lit"]
        h2 = lit["research"]["H2"]
        run_h2 = [t for t in json.load(open(os.path.join(tmp, "runs", "lit_live.json")))["trades"] if t[0] >= "2026-07-01"]
        check("23 LIT H2 research from run lit_live (n, net)", h2["n"] == len(run_h2) and h2["net"] == round(sum(t[5] for t in run_h2)), h2)
        check("23 LIT: one routed (pc) journal trade, no band file -> live n 1", lit["live"]["n"] == 1, lit)
        check("23 ATLAS members: no live trades yet + expected after 20 trades", all(sc[k]["status"] == "no_trades" and sc[k]["expected_20"] for k in I.MEMBERS),
              [sc[k] for k in I.MEMBERS])
        check("23 EMA H2 research numbers from its research file", sc["ema_lon_vix"]["research"]["H2"]["n"] == 2 and sc["ema_lon_vix"]["research"]["H2"]["net"] == 250,
              sc["ema_lon_vix"]["research"])
        # 24 drift
        check("24 drift: too early without trades", v["drift"]["state"] == "none" and "computed" in v["drift"]["source"], v["drift"])
        # 25 grade
        g = v["grade"]["setup"]
        check("25 armed setup graded A (fresh trap, 2 levels incl. PDL, room 2.2R+, 03:30 no news within 60 min)",
              g and g["grade"] == "A" and g["points"] == 4, g)
        s2 = dict(brain()["setups"][0], swept=["equal lows"], hm="09:00")
        s2["checks"] = [{"key": "idm", "ok": True, "text": "12 bars before the sweep"}]
        g2 = I.grade_setup(s2, brain())
        check("25 stale trap, one minor level, 09:00 (news 08:30 is before it; NY) -> grade C", g2["grade"] == "C" and g2["session"] == "ny", g2)
        # 26 similar
        S = v["similar"]
        top = S["groups"][0]
        exp = [r for r in I.tagged_2026() if r.get("grade") == "A" and (r.get("buckets") or {}).get("session") == "lon_early"]
        check("26 first group = grade A, London", top["name"].startswith("Grade A") and top["n"] == len(exp) == 5, top)
        check("26 outcome from run lit_live where it has the trade (not the journal's -9R)", all(t["r"] != -9.0 for t in top["trades"] if t["day"] != "2026-02-02"), top)
        wins = sum(1 for r in exp if r["r"] > 0)
        check("26 win rate and avg R", top["win"] == round(100 * wins / len(exp), 1) and top["avg_r"] == round(sum(r["r"] for r in exp) / len(exp), 2), top)
        check("26 baseline group of every 2026 trade", S["groups"][-1]["n"] == len(J), S["groups"][-1])
        # 27 regime
        rg = v["regime"]
        check("27 VIX from the Brain, band low (< 16)", rg["vix"] == 15.2 and rg["vix_band"] == "low", rg)
        check("27 trend: EMA state says down on both (the strategy's own trend wins)", rg["t15"]["dir"] == "down" and rg["t60"]["dir"] == "down" and rg["trend"] == "down", rg)
        check("27 next news + Asia / London ranges", rg["news"]["next"]["event"] == "CPI" and [r["name"] for r in rg["ranges"]] == ["Asia", "London"]
              and rg["ranges"][0]["range"] is not None and rg["ranges"][0]["avg20"] is not None, rg)
        # 28 levels
        lv = v["levels"]
        check("28 levels: 1 swept, 3 untouched sorted by distance", len(lv["swept"]) == 1 and [l["label"] for l in lv["untouched"]] ==
              ["London 03-04 high", "equal lows", "PDH"], lv)
        # 29 ATLAS
        A = {r["key"]: r for r in v["atlas"]["rows"]}
        check("29 MACD: today's open trade + last finished trade", len(A["macd_sweep"]["today"]) == 1 and A["macd_sweep"]["last"]["exit_kind"] == "STOP", A["macd_sweep"])
        check("29 candidate flagged, LIT shadow left out", A["sh_asia"]["candidate"] and "lit_asia" not in A, list(A))
        # 30 strategy 3
        check("30 nothing in research -> 'in research'", v["strategy3"]["status"] == "in research" and not v["strategy3"]["writeups"], v["strategy3"])
        json.dump([{"fam": "orb", "p": {"a": 1}, "1m_H1": {"pf": 1.2, "net": 100, "n": 50, "tpw": 3}, "1m_H2": {"pf": 1.1, "net": 50, "n": 30, "tpw": 3}},
                   {"fam": "orb", "p": {"a": 2}, "1m_H1": {"pf": 0.8, "net": -100, "n": 50, "tpw": 3}, "1m_H2": {"pf": 1.5, "net": 80, "n": 30, "tpw": 3}},
                   {"fam": "orb", "p": {"a": 3}, "1m_H1": {"pf": 9.0, "net": 50, "n": 3, "tpw": 0.2}, "1m_H2": {"pf": 9.0, "net": 50, "n": 2, "tpw": 0.1}}], open(os.path.join(tmp, "scalp", "g.json"), "w"))
        s3 = I.strategy3()
        check("30 a grid: 3 variants, 1 made money in both halves at 2+ a week (the 0.2-a-week PF 9 one does not count), best = it",
              s3["data"][0]["variants"] == 3 and s3["data"][0]["both_halves"] == 1 and s3["data"][0]["best"]["params"] == {"a": 1}
              and s3["data"][0]["best"]["qualifies"] and "3 variants" in s3["status"], s3)
        open(os.path.join(tmp, "writeups", "scalp-orb.md"), "w").write("---\ntitle: Scalp ORB\nstatus: rejected\nsummary: no edge\n---\n\nbody")
        s3 = I.strategy3()
        check("30 a write-up's front matter sets the status", s3["status"] == "rejected" and s3["writeups"][0]["title"] == "Scalp ORB", s3)
        os.remove(os.path.join(tmp, "scalp", "g.json")); os.remove(os.path.join(tmp, "writeups", "scalp-orb.md"))

        # a broken panel never breaks the others
        b2 = brain(); b2["levels"] = "broken"
        v2 = I.build(FakeBot(brain=b2, second=second_run(), running=True, acct_b=None, cfg={}, bars_tail=[]), now=NOW)
        check("one broken panel returns an error, the others still build", v2["levels"].get("error") and not v2["radar"].get("error") and not v2["atlas"].get("error"),
              {k: v2[k].get("error") for k in ("levels", "radar", "atlas")})

        # the GET route
        I._bot = lambda: bot
        app = FastAPI(); app.include_router(I.router)
        r = TestClient(app).get("/api/next/insight")
        d = r.json()
        check("GET /api/next/insight 200 + read-only flags", r.status_code == 200 and d.get("read_only") and d.get("paper_only") and d.get("mode") == "live", r.text[:300])
        check("nothing was written to the data folder", sorted(os.listdir(tmp)) == before, (before, sorted(os.listdir(tmp))))
        check("the route has no POST / PUT / DELETE", all(set(getattr(rt, "methods", {"GET"})) <= {"GET", "HEAD"} for rt in I.router.routes))
    finally:
        for k, val in saved.items():
            setattr(I, k, val)
        SC.load, health_band.load = sc_load, hb_load
        shutil.rmtree(tmp, ignore_errors=True)
    n = len(RES)
    print(f"\n{sum(RES)}/{n} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
