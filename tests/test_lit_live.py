"""LIT live-loop check: engine/lit_live.py (what the PC paper bot and the cloud monitor run every poll) against the LIT
backtest (tools/lit_final.py run = engine/lit.py run_x on the whole history), on every 2026 session.

    python -X utf8 -m tests.test_lit_live              # day-end replay of 2026 + intraday polls on every trade day
    python -X utf8 -m tests.test_lit_live --days       # day-end replay only (~1 min)
    python -X utf8 -m tests.test_lit_live --quick      # the gate's quick mode: day-end replay + polls on every 24th trade day + LiveBot on 1 session
    python -X utf8 -m tests.test_lit_live --w20        # also: the engine's plain 20-day window (shows why LIT needs more)
    python -X utf8 -m tests.test_lit_live --days --bot  # day-end replay + the LiveBot (paper) check only
    python -X utf8 -m tests.test_lit_live --final       # the lit_final params instead of live_model.json "lit" (loss pack on)
    python -X utf8 -m tests.test_lit_live --days --nobot --phantom=4   # + minute polls on 4 sessions without a trade
    python -X utf8 -m tests.test_lit_live --only=2026-01-02,2026-04-29  # intraday polls on these trade days only
    python -X utf8 -m tests.test_lit_live --days --bot --bot-sessions=2026-10-06,2026-10-07,2026-10-08
                                                        # the LiveBot on a weekly-stop week (2 stop-outs, then half size)

1. Day-end replay: for every 2026 session the adapter sees only the bars up to that session's close (5m from
   data/NQ_5m.csv, 1m from data/NQ_1m.csv as the research cleaned it) and must report that day's backtest trade exactly
   (entry time, side, entry, stop, target, micros, exit, $).
2. Intraday polls: on every 2026 trade day, a poll at every 5m close from 01:55 ET until 10 min after the exit, plus a
   poll every minute from 10 min before the entry to 5 min after it (the 1m bars of the forming 5m bar are visible).
   Every open position and finished trade the adapter shows must be the backtest's; reports the delay from the entry
   to the first poll that shows it. Polls run like the PC bot (early mode, the forming 1m bar's open shown): an entry
   decided on the 1m CISD close ("enter_now", routed at market at once) must be the backtest's trade too (entry, stop,
   target, micros); the same poll without the forming bar's open reports how often the estimate would size differently.
3. LiveBot: engine/live.py itself (PaperAdapter, frozen clock, bars revealed as they close, raw 1m file read like a feed) on
   three October sessions: every backtest trade must be routed once (side, micros, stop, target) and exited once (reason, $).
Results -> research/lit/live_check.json. One process.

The $ compared (2026-10-26): the research ledger (tools/lit_final.run = engine/lit.py run_x) books lit.COMM, $1.40 a micro
round trip; every live booking (engine/lit_live.py, the LiveBot ledger, the cloud paper ledger) books engine/sizing.LIVE_COMM,
$1.90, what MFFU / Tradovate charge. So the expected $ of each trade is the research trade's $ re-priced at $1.90
(booked(): $0.50 less per micro traded, first entry + adds); entries, exits, micros and times must stay identical.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from engine import lit, lit_live  # noqa: E402
from engine.data import load, load_ltf  # noqa: E402
from engine.sizing import LIVE_COMM  # noqa: E402

ET = ZoneInfo("America/New_York")
OUT = os.path.join(ROOT, "research", "lit", "live_check.json")
QUICK_EVERY = 24         # --quick (the release gate, tests/run_gate.py --fast): day-end replay of every 2026 session + intraday polls on
QUICK_BOT = ("2026-10-06",)  # every 24th trade day + the LiveBot on one session (a 15-minute cut, decided on a 1m close): ~3-4 min
# Days where the live loop cannot match the backtest by design (reported, not failed):
KNOWN = {"2026-04-03": "Good Friday (09:15 close): the backtest runs the day on 5m bars because its 1m file misses 6 windows "
                       "after the entry (96.7% < 97% day cover, a whole-day look-ahead); at 04:02 the live loop has every 1m "
                       "bar so far, enters on 1m (24,716.75, 3 micros, 3 min earlier than the backtest's 5m fill at 24,714.25, "
                       "4 micros) and only switches to the backtest's trade once the day's cover drops."}
FINAL = os.path.join(ROOT, "research", "lit", "lit_final.json")
LIVE = os.path.join(ROOT, "live_model.json")          # the live LIT params (lit_final + the loss pack: Monday rule, weekly stop)


def day_close(d: str) -> int:
    """17:00 ET of trading date d (the session's end)."""
    return int(dt.datetime.combine(dt.date.fromisoformat(d), dt.time(17, 0), ET).timestamp())


def at(d: str, hh: int, mm: int) -> int:
    day = dt.date.fromisoformat(d)
    if hh >= 18:
        day -= dt.timedelta(days=1)
    return int(dt.datetime.combine(day, dt.time(hh, mm), ET).timestamp())


def key(t):
    return (int(t["entry_t"]), int(t["dir"]), round(float(t["entry"]), 2), round(float(t["stop"]), 2),
            round(float(t["target"]), 2), int(t["qty"]))


def ref_key(t):
    return (int(t["entry_t"]), int(t["dir"]), round(t["entry_px"], 2), round(t["stop_px"], 2), round(t["target_px"], 2), int(t["qty"]))


def micros(t) -> int:
    """Micros a research trade traded: the first entry + every scale-in add."""
    return int(t["qty"]) + sum(int(a.get("qty") or 0) for a in (t.get("adds") or []))


def booked(t) -> float:
    """The research trade's $ (booked at lit.COMM, $1.40 a micro) as the live loop books it: at engine/sizing.LIVE_COMM
    ($1.90), i.e. (LIVE_COMM - lit.COMM) less per micro traded. The trade itself (entry, exit, micros) is unchanged."""
    return round(float(t["pnl"]) - round(LIVE_COMM - lit.COMM, 6) * micros(t), 2)


def ref_exit(t):
    return ("TIME" if t["exit"] == "EOD" else t["exit"], int(t["exit_t"]), booked(t))


def bot_replay(P, by_day, sessions=("2026-10-13", "2026-10-14", "2026-10-15"), lm_extra=None, on_bot=None):
    """LiveBot.poll_once with live_model = LIT, PaperAdapter, a frozen clock and a bar source that only shows closed bars
    (tests/test_live_dryrun.Replay). Polls at every 5m close (every minute from 10 min before each entry to 5 min after its
    exit, as the PC bot polls each minute: scale-in adds and 15-minute cuts are decided on 1m closes).
    The bot reads the raw data/NQ_1m.csv like a feed (engine/lit_live.feed_1m), not the research-cleaned 1m."""
    from tests.test_live_dryrun import Replay
    from engine.live import tick_px
    os.environ["LE_LIVE_MODEL"] = json.dumps({"model": "lit", "sym": "NQ", "label": "LIT test", "lit": P,
                                              "params": {"risk_usd": 800, "risk_ref_stop": 20.0, "max_micros": 40},
                                              **(lm_extra or {})})        # lm_extra: e.g. "guards" (tests/test_lit_more_entries.py)
    rp = Replay()
    df1 = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    rp.frames[("NQ", "1m")] = df1[df1["time"] >= at(sessions[0], 18, 0) - 70 * 86400].reset_index(drop=True)
    o1 = dict(zip(df1["time"].astype("int64"), df1["open"].astype(float)))

    def forming_1m(sym, interval, period="5d"):
        # a live 1m feed shows the minute that has just started from its first trade (its open): the bot sizes an entry
        # decided on the 1m CISD close from it, as the backtest fills at that open
        t = rp.now - rp.now % 60
        if sym == "NQ" and interval == "1m" and t in o1:
            return pd.DataFrame([{"time": t, "open": o1[t], "high": o1[t], "low": o1[t], "close": o1[t], "volume": 0.0}])
        return pd.DataFrame()
    rp.recent_hook = forming_1m
    rp.install_globals()
    want = [t for d in sessions for t in by_day.get(d, [])]
    t_start = at(sessions[0], 18, 0)
    times = set(range(t_start + 300, day_close(sessions[-1]) + 1, 300))
    for t in want:
        # every minute from 10 min before the entry to 5 min after the exit, like the PC bot (it polls each minute): a
        # scale-in add or a 15-minute cut is decided on a 1m close and routed only while its fill bar is forming
        times |= set(range(int(t["entry_t"]) - 600, max(int(t["entry_t"]), int(t.get("exit_t") or 0)) + 301, 60))
    errors, ms = [], []
    try:
        bot = rp.bot(start_now=t_start)
        if on_bot is not None:                    # e.g. a refusing broker (tests/test_acctb_not_placed.py)
            on_bot(bot)
        for now in sorted(times):
            rp.poll(bot, now + 3, errors)
            ms.append(bot.health.get("poll_ms") or 0)
        led = bot.ledger
        ent = {r["entry_t"]: r for r in led if r["side"] in ("buy", "sell")}
        exi = {r["entry_t"]: r for r in led if r["side"] == "exit"}
        e_ok = x_ok = 0
        rows = []
        for t in want:
            e, x = ent.get(int(t["entry_t"])), exi.get(int(t["entry_t"]))
            # the bot routes tick prices (engine/live.tick_px): stop to the nearest tick, the VIX-band target toward the entry
            eo = e is not None and e["side"] == ("buy" if t["dir"] == 1 else "sell") and e["qty"] == t["qty"] and \
                abs(e["stop"] - tick_px(t["stop_px"], t["dir"])) < 1e-6 and abs(e["target"] - tick_px(t["target_px"], t["dir"], target=True)) < 1e-6
            xo = x is not None and x["reason"] == ("TIME" if t["exit"] == "EOD" else t["exit"]) and abs(x["pnl"] - booked(t)) < 0.01
            e_ok += eo; x_ok += xo
            rows.append({"entry": int(t["entry_t"]), "want": [t["dir"], t["qty"], t["exit"], booked(t)], "research_pnl": t["pnl"],
                         "routed_entry": e and {k: e.get(k) for k in ("side", "qty", "stop", "target", "t")},
                         "routed_exit": x and {k: x.get(k) for k in ("reason", "pnl", "t")}})
        extra = [r for r in led if r["side"] in ("buy", "sell", "exit") and int(r["entry_t"]) not in {int(t["entry_t"]) for t in want}]
        not_routed = [l["text"] for l in bot.log if "NOT routed" in l["text"] or "never routed" in l["text"]]
        states = sorted({str((bot.state or {}).get("model_state", ""))[:40]})
        delays = [int(ent[int(t["entry_t"])]["t"]) - int(t["entry_t"]) for t in want if int(t["entry_t"]) in ent]
        res = {"sessions": list(sessions), "polls": len(times), "want": len(want), "entries_ok": e_ok, "exits_ok": x_ok,
               "entry_route_delay_s": delays,
               "extra": len(extra), "not_routed": not_routed[:10], "errors": [e[1] for e in errors[:5]], "rows": rows,
               "last_model_state": (bot.state or {}).get("model_state"), "poll_ms": int(np.mean(ms)) if ms else None,
               "modify_routes": sum(1 for r in led if r["side"] == "modify"), "states_seen": states}
        res["ok"] = e_ok == len(want) and x_ok == len(want) and not extra and not errors and not not_routed
        return res
    finally:
        rp.cleanup()
        os.environ.pop("LE_LIVE_MODEL", None)


def main():
    t_all = time.time()
    # --final: the lit_final params (no loss pack); default: live_model.json "lit" (what the bots trade)
    P = json.load(open(FINAL, encoding="utf-8"))["params"] if "--final" in sys.argv else json.load(open(LIVE, encoding="utf-8"))["lit"]
    rt = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--retail=")), None)
    if rt:                               # retail-tool entries on (engine/lit_retail.py): a JSON file / dict of lit keys, e.g.
        P = {**P, **json.loads(open(rt).read() if os.path.exists(rt) else rt)}   # {"retail": {...}, "max_per_day": 2, "src_cap": 1}
    from tools import lit_final as F
    REF = [t for t in F.run(P) if t["day"] >= "2026-01-01"]
    sess = [d for d in F.SESS if d >= "2026-01-01"]
    by_day = collections.defaultdict(list)
    for t in REF:
        by_day[t["day"]].append(t)
    df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    df5 = df5[df5["time"] >= day_close(sess[0]) - 120 * 86400].reset_index(drop=True)
    b1, _ = load_ltf("NQ", load("NQ", "5m"))
    b1 = b1.slice(int(np.searchsorted(b1.t, int(df5["time"].min()))), len(b1))
    T5 = df5["time"].values
    out = {"strategy": "lit_final" if "--final" in sys.argv else "lit_live (live_model.json)", "params": P, "sessions": len(sess), "backtest_trades": len(REF)}

    def poll(now, window_days=None, hint=True, early=True):
        cut5 = df5.iloc[:int(np.searchsorted(T5 + 300, now, side="right"))]
        if window_days:
            cut5 = cut5[cut5["time"] >= cut5["time"].max() - window_days * 86400]
        cut1 = b1.slice(0, int(np.searchsorted(b1.t + 60, now, side="right")))
        # the 1m bar forming at `now` (a feed shows its first tick, i.e. its open): sizes an entry decided on the CISD close
        jf = int(np.searchsorted(b1.t, now - now % 60))
        forming = (int(b1.t[jf]), float(b1.o[jf])) if hint and jf < len(b1.t) and int(b1.t[jf]) == now - now % 60 else None
        if window_days:
            # the 20-day variant: no extension of the window (lit_live.window_start bypassed)
            orig = lit_live.window_start
            lit_live.window_start = lambda last_t: int(cut5["time"].min())
            try:
                return lit_live.run(cut5, P, one_min=cut1, now=now, forming=forming, early=early)
            finally:
                lit_live.window_start = orig
        return lit_live.run(cut5, P, one_min=cut1, now=now, forming=forming, early=early)

    # ---- 1. day-end replay
    def day_end(window_days=None):
        same = exits_same = 0
        miss, extra, wrong = [], [], []
        t0 = time.time()
        for d in sess:
            res = poll(day_close(d), window_days)
            got = [t for t in res["trades"] if t["day"] == d]
            want = by_day.get(d, [])
            gk = {key(t): t for t in got}
            for w in want:
                g = gk.pop(ref_key(w), None)
                if g is None:
                    miss.append((d, int(w["entry_t"])))
                    continue
                same += 1
                if (g["exit_reason"], g["exit_t"], round(g["pnl"], 2)) == ref_exit(w):
                    exits_same += 1
                else:
                    wrong.append((d, (g["exit_reason"], g["exit_t"], g["pnl"]), ref_exit(w)))
            extra += [(d, k[0]) for k in gk]
            if res["state"].get("position"):
                extra.append((d, "open position at the session close"))
        r = {"sessions": len(sess), "backtest_trades": len(REF), "matched_entries": same, "matched_exits_and_pnl": exits_same,
             "missing": miss[:20], "n_missing": len(miss), "extra": extra[:20], "n_extra": len(extra), "exit_differs": wrong[:20],
             "net_backtest": round(sum(t["pnl"] for t in REF), 2), "net_live_booked": round(sum(booked(t) for t in REF), 2),
             "commission": {"research": lit.COMM, "live": LIVE_COMM, "micros": sum(micros(t) for t in REF),
                            "diff_usd": round(sum(booked(t) - t["pnl"] for t in REF), 2),
                            "max_trade_usd": round(min((booked(t) - t["pnl"] for t in REF), default=0.0), 2)},
             "seconds": round(time.time() - t0)}
        return r

    out["day_end"] = day_end()
    print(f"day-end replay (prev-month window): {out['day_end']['matched_exits_and_pnl']}/{len(REF)} trades identical "
          f"(entries {out['day_end']['matched_entries']}, missing {out['day_end']['n_missing']}, extra {out['day_end']['n_extra']}) "
          f"in {out['day_end']['seconds']}s; $ at the live ${LIVE_COMM:.2f} commission: research ${out['day_end']['net_backtest']:,.2f} "
          f"-> live ${out['day_end']['net_live_booked']:,.2f} ({out['day_end']['commission']['diff_usd']:+,.2f} over "
          f"{out['day_end']['commission']['micros']} micros)", flush=True)
    if "--w20" in sys.argv:
        out["day_end_20d"] = day_end(20)
        print(f"day-end replay (plain 20-day window): {out['day_end_20d']['matched_exits_and_pnl']}/{len(REF)} identical "
              f"(missing {out['day_end_20d']['n_missing']}, extra {out['day_end_20d']['n_extra']})", flush=True)

    # ---- 2. intraday polls on every trade day
    if "--days" not in sys.argv:
        t0 = time.time()
        polls = 0
        bad, lags, seen_open, never = [], [], 0, []
        enter = {"seen": 0, "days": 0, "match": 0, "differs": [], "est_days": 0, "est_qty_differs": [], "est_target_differs": 0}
        only = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)
        if only is None and "--quick" in sys.argv:
            only = sorted(by_day)[::QUICK_EVERY]                   # --quick: every QUICK_EVERY-th trade day (spread over the year)
        for d, want in sorted(by_day.items()):
            if only and d not in only:
                continue
            w = want[0]
            ent, ext = int(w["entry_t"]), int(w["exit_t"])
            times = set(range(at(d, 1, 55), min(ext + 600, day_close(d)) + 1, 300))
            times |= set(range(ent - 600, ent + 301, 60))
            first = None
            en_first = None
            for now in sorted(times):
                polls += 1
                res = poll(now)
                pos = res["state"].get("position")
                fin = [t for t in res["trades"] if t["day"] == d]
                en = res["state"].get("enter_now")
                if en:
                    # the entry decided on the 1m CISD close (routed at market at once): must be the backtest's trade
                    enter["seen"] += 1
                    ek = (en["entry_t"], en["dir"], round(en["entry"], 2), round(en["stop0"], 2), round(en["target"], 2), en["qty"])
                    if ek == ref_key(w) and not en.get("est"):
                        enter["match"] += 1
                    else:
                        bad.append({"day": d, "now": now, "what": "enter-now entry differs", "got": ek, "want": ref_key(w)})
                    if en_first is None:
                        en_first = now
                        enter["days"] += 1
                        # the same poll when the feed does not show the forming bar's open yet: sized from the CISD close
                        e2 = poll(now, hint=False)["state"].get("enter_now")
                        if e2:
                            enter["est_days"] += 1
                            if e2["qty"] != w["qty"]:
                                enter["est_qty_differs"].append((d, e2["qty"], int(w["qty"])))
                            enter["est_target_differs"] += round(e2["target"], 2) != round(w["target_px"], 2)
                for t in fin:
                    if key(t) != ref_key(w) or (t["exit_reason"], t["exit_t"], round(t["pnl"], 2)) != ref_exit(w):
                        bad.append({"day": d, "now": now, "what": "finished trade differs", "got": key(t)})
                if pos:
                    pk = (pos["entry_t"], pos["dir"], round(pos["entry"], 2), round(pos["stop0"], 2), round(pos["target"], 2), pos["qty"])
                    if pk != ref_key(w):
                        bad.append({"day": d, "now": now, "what": "open position differs", "got": pk, "want": ref_key(w)})
                    elif now >= ext + 60 * (1 if w.get("tf") == 1 else 5):
                        bad.append({"day": d, "now": now, "what": "still open after the backtest exit"})
                    else:
                        seen_open += 1
                if first is None and (pos or fin or en):
                    first = now
            if len(lags) % 20 == 0 and first is not None:
                print(f"  ... {d}: {polls} polls, {len(bad)} differences, {time.time() - t0:.0f}s", flush=True)
            if first is None:
                never.append(d)
            else:
                lags.append(first - ent)
        lag = np.array(lags) / 60.0
        known = [b for b in bad if b["day"] in KNOWN]
        bad = [b for b in bad if b["day"] not in KNOWN]
        out["intraday"] = {"trade_days": len(by_day), "polls": polls, "differences": bad[:30], "n_differences": len(bad),
                           "known_differences": {d: {"polls": sum(1 for b in known if b["day"] == d), "why": KNOWN[d],
                                                     "first": next((b for b in known if b["day"] == d), None)}
                                                 for d in sorted({b["day"] for b in known})},
                           "polls_with_matching_open_position": seen_open, "trade_never_seen_open_or_closed": never,
                           "enter_now": {**enter, "est_qty_differs": enter["est_qty_differs"][:40]},
                           "delay_entry_to_first_poll_min": {"median": round(float(np.median(lag)), 2) if len(lag) else None,
                                                             "max": round(float(lag.max()), 2) if len(lag) else None,
                                                             "within_1_min": int((lag <= 1.0).sum()), "within_5_min": int((lag <= 5.0).sum())},
                           "seconds": round(time.time() - t0)}
        print(f"intraday: {polls} polls on {len(by_day)} trade days, {len(bad)} differences (+{len(known)} on known days "
              f"{sorted({b['day'] for b in known})}), open position matched on "
              f"{seen_open} polls, entry seen after median {out['intraday']['delay_entry_to_first_poll_min']['median']} min "
              f"(max {out['intraday']['delay_entry_to_first_poll_min']['max']}) in {out['intraday']['seconds']}s", flush=True)
        print(f"enter-now (entry decided on the 1m CISD close): seen on {enter['days']} trade days ({enter['seen']} polls, "
              f"{enter['match']} identical to the backtest trade); without the forming bar's open (sized from the CISD close): "
              f"{len(enter['est_qty_differs'])}/{enter['est_days']} days route other micros, {enter['est_target_differs']} another "
              f"target", flush=True)
    # ---- 2b. --phantom=N: N sessions WITHOUT a backtest trade, a poll every minute 01:55-15:35 ET (the early mode adds the
    # forming 5m bar; nothing it shows may ever become a position, an entry to route or a trade on such a day)
    ph = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--phantom=")), 0)
    if ph:
        t0 = time.time()
        quiet = [d for d in sess if d not in by_day]
        pick = [quiet[int(i)] for i in np.linspace(0, len(quiet) - 1, ph)] if len(quiet) >= ph else quiet
        n_p, ph_bad, ph_pending = 0, [], 0
        for d in pick:
            for now in range(at(d, 1, 55), at(d, 15, 35) + 1, 60):
                n_p += 1
                st = poll(now)
                if st["state"].get("position") or st["state"].get("enter_now") or any(t["day"] == d for t in st["trades"]):
                    ph_bad.append({"day": d, "now": now, "state": st["state"].get("model_state")})
                ph_pending += bool(st["state"].get("setups"))
        out["phantom"] = {"days": pick, "polls": n_p, "bad": ph_bad[:20], "n_bad": len(ph_bad), "polls_with_a_working_setup": ph_pending,
                          "seconds": round(time.time() - t0)}
        print(f"phantom check: {n_p} minute polls on {len(pick)} sessions without a trade {pick}: {len(ph_bad)} positions / entries / "
              f"trades shown (setups armed on {ph_pending} polls) in {out['phantom']['seconds']}s", flush=True)
    # ---- 3. the PC paper bot itself (engine/live.py LiveBot + PaperAdapter) on LIT, fed bar by bar
    if "--bot" in sys.argv or ("--days" not in sys.argv and "--nobot" not in sys.argv):
        bs = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--bot-sessions=")), None)
        if bs is None and "--quick" in sys.argv:
            bs = QUICK_BOT                                         # --quick: one October session, a 16-minute trade
        out["bot"] = bot_replay(P, by_day, tuple(bs)) if bs else bot_replay(P, by_day)
        b = out["bot"]
        print(f"LiveBot (paper) on LIT, sessions {b['sessions']}: {b['polls']} polls, routed entries {b['entries_ok']}/{b['want']} "
              f"exits {b['exits_ok']}/{b['want']}, extra routes {b['extra']}, not-routed log lines {len(b['not_routed'])}, "
              f"errors {len(b['errors'])}, mean poll {b['poll_ms']} ms, entry routed {b['entry_route_delay_s']} s after the "
              f"backtest's fill-bar open (polls 3 s after the minute)", flush=True)
    out["seconds"] = round(time.time() - t_all)
    if "--quick" not in sys.argv:                                  # the quick run never overwrites the full result
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=str)
    ok = out["day_end"]["matched_exits_and_pnl"] == len(REF) and not out["day_end"]["n_extra"] and \
        (not out.get("intraday") or not out["intraday"]["n_differences"]) and (not out.get("bot") or out["bot"]["ok"]) and \
        (not out.get("phantom") or not out["phantom"]["n_bad"])
    print("OK" if ok else "DIFFERENCES (see research/lit/live_check.json)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
