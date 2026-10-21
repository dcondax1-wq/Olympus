"""Recap cards, the brief image and the weekly review (tools/recap.py), on real 2026 trades and bars.

    python -X utf8 -m tests.test_recap

Futures data only: data/NQ_5m.csv + data/NQ_1m.csv (TradingView CME NQ1!), cut at `now` like the cloud's bars, and the
2026 LIT replay trades of research/lab/backtest_live.json fed in as cloud paper ledger rows / PC heartbeat trades. Checks:
  1. three real 2026 trades (a STOP, a BE and a TARGET) and a 15-minute cut: the setup is rebuilt on the live window (matched),
     the card's prices are the trade's own (entry, stop, target, exit, micros, $), the BE stop line sits at entry + be_off,
     the 15-minute check marker is there, the PNG exists, is 800 px wide and small (< 80 KB), and the words have why /
     plan / what happened / lessons
  2. a PC fill one tick worse than the model -> the lesson names the tick; a PC trade the model did not take -> a plain
     card (no setup markers) that still renders
  3. cache: a second run draws nothing; only the newest `keep` cards are kept (older PNGs deleted)
  4. notices: one per trade (the PC's wins over the paper copy), the trade's tag (replaces its outcome notice), a link to
     the card, the PNG as image; engine/push.wire passes the image only from the app's own site
  5. brief image: drawn from the 01:45 ET morning brief of a real day, pushed once a day
  6. weekly review: due on Sunday, the week's trades, net $ = the sum of the trades, best / worst, execution pairs, a
     "what to watch next week" list (the new PWH / PWL, Friday's high / low, the eval)
  7. speed: the whole check (the cloud's work for 6 cards + a brief + a weekly) well under a minute
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

from engine import lit_brief, lit_live, push  # noqa: E402
from tools import recap  # noqa: E402

ET = ZoneInfo("America/New_York")
PICK = {"STOP": "2026-10-08", "BE": "2026-09-28", "TARGET": "2026-10-14", "CUT_T15": "2026-10-06"}


def ledger_row(t):
    return {"day": t["day"], "entry": "", "side": t["side"], "exit": t["exit"], "exit_ts": t["exit_t"], "R": round(t["r"], 2),
            "usd": t["pnl"], "qty": t["qty"], "entry_px": t["entry"], "stop_px": t["stop"], "target_px": t["target"],
            "exit_px": t["exit_price"], "risk_pts": t["risk_pts"], "taken": True, "mult": 1.0}


def pc_row(t, entry_shift=0.0, day=None):
    d = 1 if t["side"] == "LONG" else -1
    e = t["entry"] + d * entry_shift
    return {"day": day or t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "side": t["side"], "qty": t["qty"], "entry": e,
            "stop": t["stop"], "target": t["target"], "exit_px": t["exit_price"], "exit": t["exit"],
            "r": t["r"], "pnl": round(t["pnl"] - d * entry_shift * 2 * t["qty"], 2), "risk_pts": abs(e - t["stop"])}


def main():
    t_all = time.time()
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    P = lm["lit"]
    bt = [t for t in json.load(open(os.path.join(ROOT, "research", "lab", "backtest_live.json"), encoding="utf-8"))["trades"]
          if t["day"] >= "2026-01-01"]
    by_day = {t["day"]: t for t in bt}
    df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    df1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    fails, checks = [], 0

    def check(ok, msg):
        nonlocal checks
        checks += 1
        if not ok:
            fails.append(msg)
            print("  FAIL", msg)

    tmp = tempfile.mkdtemp(prefix="recap_")
    try:
        from PIL import Image
        # ---- 1. three real trades + a cut, one at a time as the cloud sees them (bars up to 30 min after the exit)
        for kind, day in PICK.items():
            t = by_day[day]
            check(t["exit"] == kind, f"{day}: backtest exit {t['exit']} != {kind}")
            now = t["exit_t"] + 1800
            st = {"ledger": {str(t["entry_t"]): ledger_row(t)}}
            out = os.path.join(tmp, kind)
            c5, c1 = df5[df5["time"] + 300 <= now], df1[df1["time"] + 60 <= now]
            t0 = time.time()
            made = recap.make_cards(st, out, c5, c1, P, now)
            dt_s = time.time() - t0
            check(len(made) == 1, f"{kind}: {len(made)} cards made")
            if not made:
                continue
            c = made[0]
            png = os.path.join(out, c["png"])
            check(os.path.exists(png), f"{kind}: PNG missing")
            if os.path.exists(png):
                im = Image.open(png)
                check(im.size[0] == 800, f"{kind}: PNG width {im.size}")
                check(os.path.getsize(png) < 80 * 1024, f"{kind}: PNG {os.path.getsize(png) // 1024} KB")
            check(c["matched"] is True, f"{kind}: setup not rebuilt on the live window")
            check(c["exit"] == kind, f"{kind}: card exit {c['exit']}")
            for a, b, nm in ((c["entry"], t["entry"], "entry"), (c["stop"], t["stop"], "stop"), (c["target"], t["target"], "target"),
                             (c["exit_px"], t["exit_price"], "exit"), (c["qty"], t["qty"], "qty"), (c["usd"], t["pnl"], "usd")):
                check(abs(float(a) - float(b)) < 0.01, f"{kind}: {nm} {a} != {b}")
            check(bool(c["why"]) and bool(c["plan"]) and bool(c["result"]) and bool(c["lessons"]), f"{kind}: words missing")
            check(any("Swept" in w for w in c["why"]) and any("Inducement" in w for w in c["why"]) and any("Displacement" in w for w in c["why"]),
                  f"{kind}: why lacks sweep / inducement / displacement")
            check(dt_s < 15, f"{kind}: card took {dt_s:.1f} s")
            # the drawn record: BE line and the 15-minute check
            core = recap.live_core(c5, {**__import__("engine.lit", fromlist=["DEFAULTS"]).DEFAULTS, **P}, c1, now=now)
            tr = recap.finished_trades(st)[0]
            rec, raw, z = recap.record_for(tr, core, {**__import__("engine.lit", fromlist=["DEFAULTS"]).DEFAULTS, **P}, c5, c1)
            if kind in ("BE", "TARGET"):
                d = 1 if t["side"] == "LONG" else -1
                check(rec.get("be") is not None and abs(rec.get("be_px", 0) - (t["entry"] + d * P["be_off"])) < 1e-6,
                      f"{kind}: BE stop line {rec.get('be_px')}")
            check(bool(rec.get("tcheck")) and rec["tcheck"]["cut"] == (kind == "CUT_T15"), f"{kind}: 15-minute check marker {rec.get('tcheck')}")
            check(rec["levels"] and rec["idm"] and rec["cisd5"] and rec["sweep"], f"{kind}: setup markers missing")
            if kind == "CUT_T15":
                check(any("15-minute" in l for l in c["lessons"]), f"{kind}: lesson does not name the cut")
            if kind == "BE":
                check(any("breakeven" in l for l in c["lessons"]), f"{kind}: lesson does not name the breakeven")
            print(f"  {kind:8s} {day}: card {c['kb']} KB in {dt_s:.1f} s; lesson: {c['lessons'][0]}")

        # ---- 2. PC trades: one tick worse than the model (matched), and one the model did not take (plain card)
        t = by_day["2026-10-14"]
        now = t["exit_t"] + 1800
        c5, c1 = df5[df5["time"] + 300 <= now], df1[df1["time"] + 60 <= now]
        st = {"ledger": {str(t["entry_t"]): ledger_row(t)},
              "pc": {"present": True, "acct": {"account": {"name": "Sim101"}, "trades": [pc_row(t, 0.25)]}}}
        out = os.path.join(tmp, "pc")
        made = recap.make_cards(st, out, c5, c1, P, now)
        pcc = [c for c in made if c["src"] == "pc"]
        check(len(made) == 2 and len(pcc) == 1, f"pc: {len(made)} cards ({[c['key'] for c in made]})")
        if pcc:
            check(pcc[0]["matched"] and any("1 tick worse" in l for l in pcc[0]["lessons"]), f"pc: tick lesson {pcc[0]['lessons']}")
            check(abs(pcc[0]["entry"] - (t["entry"] - 0.25)) < 1e-6, f"pc: card entry {pcc[0]['entry']} (the PC's fill)")
            check(pcc[0]["account"] == "PC · Sim101", f"pc: account {pcc[0]['account']}")
        nt = recap.card_notices(made)
        check(len(nt) == 1 and nt[0]["account"] == "PC · Sim101", f"notices: {[(n['key'], n['account']) for n in nt]}")
        if nt:
            n = nt[0]
            check(n["tag"] == push.trade_tag(t["entry_t"]), "notice: not the trade's tag")
            check(n["url"].startswith("#/recaps/pc_2026-10-14"), f"notice url {n['url']}")
            w = json.loads(push.wire(n))
            check(w.get("image", "").startswith(push.APP_URL + "recaps/") and len(push.wire(n)) < 4000, f"wire image {w.get('image')}")
            check("image" not in json.loads(push.wire({**n, "image": "https://evil.example/x.png"})), "wire passes a foreign image")
        # a PC trade on a day the model did not trade -> plain card
        other = {**pc_row(t), "day": "2026-10-15", "entry_t": t["entry_t"] + 86400, "exit_t": t["exit_t"] + 86400}
        now2 = other["exit_t"] + 1800
        st2 = {"pc": {"present": True, "acct": {"account": {"name": "Sim101"}, "trades": [other]}}}
        args2 = (st2, os.path.join(tmp, "plain"), df5[df5["time"] + 300 <= now2], df1[df1["time"] + 60 <= now2], P, now2)
        waits = [len(recap.make_cards(*args2)) for _ in range(recap.WAIT_TRIES)]
        check(waits == [0] * recap.WAIT_TRIES, f"plain card: drawn before waiting for the bars {waits}")
        made2 = recap.make_cards(*args2)
        check(len(made2) == 1 and made2[0]["matched"] is False and os.path.exists(os.path.join(tmp, "plain", made2[0]["png"])),
              f"plain card: {made2}")

        # ---- 3. cache and pruning
        again = recap.make_cards(st, out, c5, c1, P, now)
        check(again == [], f"cache: {len(again)} cards redrawn")
        rows = [by_day[d] for d in ("2026-10-01", "2026-10-02", "2026-10-07")]
        st3 = {"ledger": {str(x["entry_t"]): ledger_row(x) for x in rows}}
        now3 = rows[-1]["exit_t"] + 1800
        o3 = os.path.join(tmp, "keep")
        m3 = recap.make_cards(st3, o3, df5[df5["time"] + 300 <= now3], df1[df1["time"] + 60 <= now3], P, now3, keep=2)
        pngs = sorted(n for n in os.listdir(os.path.join(o3, "recaps")) if n.endswith(".png"))
        ix = recap.load_index(o3)
        check(len(m3) == 2 and len(ix["cards"]) == 2 and len(pngs) == 2, f"keep=2: made {len(m3)}, index {len(ix['cards'])}, pngs {pngs}")
        check(ix["cards"][0]["day"] == "2026-10-07", f"keep: newest first {ix['cards'][0]['day']}")

        # ---- 5. the brief image of a real morning
        bnow = int(dt.datetime(2026, 10, 14, 1, 45, tzinfo=ET).timestamp())
        b5, b1 = df5[df5["time"] + 300 <= bnow], df1[df1["time"] + 60 <= bnow]
        res = lit_live.run(b5, P, one_min=b1, now=bnow)
        hub = json.load(open(os.path.join(ROOT, "data", "news", "hub.json"), encoding="utf-8"))
        clock = {"session": 3, "limit": 10, "profit": 400.0, "room": 2400.0, "to_target": 2600.0, "status": "open"}
        ev = {"balance": 50400.0, "cushion": 2400.0, "trailing_mll": 48000.0, "to_target": 2600.0}
        br = lit_brief.build(b5, bnow, params=P, live=res, news=hub, clock=clock, ev=ev, lit_sizing=lm.get("lit_sizing"),
                             model_params=lm.get("params"))
        ob = os.path.join(tmp, "brief")
        t0 = time.time()
        row = recap.brief_image(ob, br, b5, bnow)
        check(row is not None and os.path.exists(os.path.join(ob, "recaps", "brief.png")), "brief: no image")
        if row:
            check(row["day"] == "2026-10-14" and row["band_width"] and row["band_width"] > 0, f"brief: row {row}")
            check(os.path.getsize(os.path.join(ob, "recaps", "brief.png")) < 120 * 1024, "brief: PNG too big")
            print(f"  brief    2026-10-14 01:45: {row['kb']} KB in {time.time() - t0:.1f} s, band {row['band_width']} pts")
        check(recap.brief_image(ob, br, b5, bnow) is None, "brief: redrawn without a change")
        n1, n2 = recap.brief_notice(ob), recap.brief_notice(ob)
        check(n1 is not None and n1["url"] == "#/brief" and n1["key"] == "brief:2026-10-14" and n2 is None, f"brief notice {n1} / {n2}")

        # ---- 6. weekly review of 2026-10-12 .. 10-16, built on Sunday 10-18
        week = [x for x in bt if "2026-10-12" <= x["day"] <= "2026-10-16"]
        wnow = int(dt.datetime(2026, 10, 18, 17, 50, tzinfo=ET).timestamp())
        stw = {"ledger": {str(x["entry_t"]): ledger_row(x) for x in week},
               "pc": {"present": True, "acct": {"account": {"name": "Sim101"}, "trades": [pc_row(week[0], 0.5)]}},
               "eval_2wk": {"session": 4, "limit": 10, "status": "open", "to_target": 1200.0, "room": 2100.0}}
        check(recap.weekly_due(None, wnow) and not recap.weekly_due({"week": "2026-10-12"}, wnow), "weekly: due rule")
        check(not recap.weekly_due(None, int(dt.datetime(2026, 10, 14, 10, 0, tzinfo=ET).timestamp())), "weekly: due on a Wednesday")
        wk = recap.weekly(stw, wnow, df5[df5["time"] + 300 <= wnow], hub, [])
        pa = wk["sources"].get("paper") or {}
        check(wk["week"] == "2026-10-12" and wk["days"][-1] == "2026-10-16", f"weekly: week {wk['week']} {wk['days']}")
        check(pa.get("n") == len(week) and abs(pa.get("net", 0) - round(sum(x["pnl"] for x in week), 2)) < 0.01,
              f"weekly: paper {pa.get('n')} trades {pa.get('net')} vs {len(week)} {sum(x['pnl'] for x in week):.2f}")
        check(pa.get("best", {}).get("usd") == max(x["pnl"] for x in week), "weekly: best")
        check(wk["main"] == "pc" and len(wk["execution"]["pairs"]) == 1 and wk["execution"]["pairs"][0]["entry_slip_ticks"] == 2,
              f"weekly: execution {wk['execution']}")
        kinds = {w["kind"] for w in wk["watch"]}
        check({"news", "levels", "monday", "eval"} <= kinds, f"weekly: watch kinds {kinds}")
        wn = recap.weekly_notice(wk)
        check(wn["url"] == "#/weekly" and wn["key"] == "weekly:2026-10-12", f"weekly notice {wn}")
        print(f"  weekly   {wk['label']}: {wk['head']}; watch: {len(wk['watch'])} lines")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    took = time.time() - t_all
    check(took < 60, f"speed: {took:.0f} s")
    print(f"recap: {checks - len(fails)}/{checks} checks passed in {took:.0f} s")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
