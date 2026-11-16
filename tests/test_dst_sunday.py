"""Sunday 2026-11-01: the clocks go back (02:00 EDT -> 01:00 EST, the 01:00-02:00 ET hour twice) on the weekend, CME reopens
at 18:00 ET (23:00 UTC, an hour later in UTC than last Sunday), and the bots trade Monday on EST. tests/test_dst.py checks the
pure time functions; this one runs the days themselves (owner 2026-10-29: "make sure everything's good for Sunday").

    python -X utf8 -m tests.test_dst_sunday            # all (~10 min: + the real server across Sunday 00:00-20:00 ET)
    python -X utf8 -m tests.test_dst_sunday --quick    # parts 1-2 only (~1 min)

 1. BLITZ across the switch: 2026's real 1m bars re-dated by 3 weeks with their New York wall times kept (Oct 12-16 become
    Nov 2-6, the 14-session noise band and the 14-range day filter straddle the switch): engine.blitz.backtest and the live
    Engine bar by bar give the same trades at the same ET minutes as the original week (11:00 EST = 16:00 UTC).
 2. The timers minute by minute Sat 2026-10-31 17:00 -> Mon 2026-11-02 16:30 ET (epoch steps, so the repeated hour is
    walked twice): the trading day flips once, at Sun 18:00 EST; market_open opens once, at Sun 18:00 EST; the auto-update's
    hourly check (window_reason + hour_key, the state it records) runs at most once per ET hour, once in the doubled hour;
    the ops pushes (pre-session, day summary, weekly) are due on the right days only; Monday's first windows (LIT 02:00 EST,
    ATLAS EMA 03:00, BLITZ 11:00 and the 15:55 flat) land on the right UTC instants, also as the board's next windows seen
    from Sunday evening.
 3. The real server.py on a virtual clock (tests/test_rehearsal.py's sandbox + fake NinjaTrader, the BLITZ rehearsal's
    serve) from Sun 00:00 EDT to 20:00 EST with Zlarior (Sim101), ATLAS (Sim102) and BLITZ (Sim103) on, re-dated bars from
    18:00: it polls through the doubled hour (no "clock moved backwards", no error, no traceback), sends no order, its
    heartbeat keeps the virtual time, market_open / the trading day flip at 18:00 EST, Monday's eval session is 1, the go-live
    check reads Monday's normal session, no push / auto-update check fires twice in the doubled hour.
Temp dirs only.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from zoneinfo import ZoneInfo  # noqa: E402

ET = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
SUN = dt.date(2026, 11, 1)
MON = dt.date(2026, 11, 2)
SHIFT_DAYS = 21
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": "" if ok else str(detail)[:600]})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:600]}"), flush=True)
    return bool(ok)


def ts(d: dt.date, hh: int, mm: int = 0, fold: int = 0) -> int:
    return int(dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET, fold=fold).timestamp())


def hm(t) -> str:
    return dt.datetime.fromtimestamp(int(t), ET).strftime("%a %H:%M %Z")


def redate(df, days: int = SHIFT_DAYS):
    """Bars moved `days` later with their New York wall time kept (a Monday 11:00 ET bar stays a Monday 11:00 ET bar on both
    sides of a clock change). Bars whose new wall time does not exist / is doubled are dropped (none in market hours)."""
    import pandas as pd
    w = pd.to_datetime(df["time"].astype("int64"), unit="s", utc=True).dt.tz_convert(ET).dt.tz_localize(None) + pd.Timedelta(days=days)
    loc = w.dt.tz_localize(ET, ambiguous="NaT", nonexistent="NaT")
    out = df.copy()
    ok = loc.notna().to_numpy()
    out = out[ok]
    out["time"] = ((loc[ok] - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1)).astype("int64").to_numpy()
    return out.sort_values("time").reset_index(drop=True)


# ------------------------------------------------------------------------------------------------ 1. BLITZ across the switch
def part1():
    print("1. BLITZ on re-dated bars across the 2026-11-01 switch", flush=True)
    import pandas as pd
    from engine import blitz as BZ
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
    src = df[(df["time"] >= ts(dt.date(2026, 8, 1), 0)) & (df["time"] < ts(dt.date(2026, 10, 17), 0))]
    red = redate(src)
    T0 = [t for t in BZ.backtest(src) if "2026-10-12" <= t["day"] <= "2026-10-16"]
    T1 = [t for t in BZ.backtest(red) if "2026-11-02" <= t["day"] <= "2026-11-06"]

    def wall(t):
        e = dt.datetime.fromtimestamp(int(t), ET)
        return e.strftime("%a %H:%M")
    k0 = [(wall(t["entry_t"]), wall(t["exit_t"]), t["dir"], round(t["entry"], 2), round(t["exit"], 2), t["exit_kind"], round(t["r"], 6)) for t in T0]
    k1 = [(wall(t["entry_t"]), wall(t["exit_t"]), t["dir"], round(t["entry"], 2), round(t["exit"], 2), t["exit_kind"], round(t["r"], 6)) for t in T1]
    check(f"backtest on the re-dated bars: Nov 2-6 (EST) = Oct 12-16 (EDT) trade for trade at the same ET minutes ({len(T1)} trades)",
          k0 == k1 and len(T1) > 0, {"oct": k0[:3], "nov": k1[:3]})
    first = T1[0] if T1 else None
    check(f"the week's first BLITZ entry ({first['day'] if first else '-'}, the 11:00 check) at {hm(first['entry_t']) if first else '-'} = "
          f"{dt.datetime.fromtimestamp(first['entry_t'], UTC):%H:%M} UTC (11:00 EST = 16:00 UTC; the original 11:00 EDT = 15:00 UTC)"
          if first else "the week's first BLITZ entry", first and dt.datetime.fromtimestamp(first["entry_t"], UTC).hour == 16
          and dt.datetime.fromtimestamp(T0[0]["entry_t"], UTC).hour == 15, first)
    # the live Engine one closed bar at a time over the weekend and the switch = the whole-frame backtest
    E = BZ.Engine(None, True)
    got = []
    t, o, h, l, c = BZ._bars_of(red)
    for i in range(len(t)):
        for x in E.on_bar(int(t[i]), o[i], h[i], l[i], c[i]):
            if x.get("ev") == "exit" and x["date"] >= "2026-10-26":
                got.append((int(x["entry_t"]), x["kind"], round(x["exit"], 2)))
    want = [(int(t_["entry_t"]), t_["exit_kind"], round(t_["exit"], 2)) for t_ in BZ.backtest(red) if t_["day"] >= "2026-10-26"]
    check(f"live Engine bar by bar across the switch = the backtest ({len(got)} trades Oct 26 - Nov 6)", got == want, {"got": got[:4], "want": want[:4]})
    # the day filter on Monday Nov 2 uses Friday Oct 30's range (the weekend and the doubled hour add no range)
    B = BZ.frame(red)
    pr = BZ.prior_range(B)
    dates = list(B["dates"])
    B0 = BZ.frame(src)
    pr0 = BZ.prior_range(B0)
    r_mon, r_oct = float(pr[dates.index("2026-11-02")]), float(pr0[list(B0["dates"]).index("2026-10-12")])
    check(f"day filter for Mon Nov 2 = Mon Oct 12's ({r_mon:.3f} vs {r_oct:.3f}): Friday's range, the weekend and the doubled hour add none",
          abs(r_mon - r_oct) < 1e-9, (r_mon, r_oct))


# ------------------------------------------------------------------------------------------------ 2. the timers, minute by minute
def part2():
    print("2. timers minute by minute Sat 10-31 17:00 -> Mon 11-02 16:30 ET (the doubled hour walked twice)", flush=True)
    from engine import autoupdate as AU, live, ops_checks as OC, live_board as LB, guards, blitz as BZ
    a, z = ts(dt.date(2026, 10, 31), 17, 0), ts(MON, 16, 30)
    steps = list(range(a, z + 1, 60))
    doubled = [t for t in steps if dt.datetime.fromtimestamp(t, ET).strftime("%Y-%m-%d %H") == "2026-11-01 01"]
    check(f"{len(steps)} minutes, the 01:00 ET hour on Sunday is {len(doubled)} minutes long (EDT then EST)", len(doubled) == 120, len(doubled))
    days = [live.trading_day(t) for t in steps]
    flips = [(hm(steps[i]), days[i - 1], days[i]) for i in range(1, len(steps)) if days[i] != days[i - 1]]
    sun18 = ts(SUN, 18, 0)
    i18 = steps.index(sun18)
    check(f"trading day flips {flips}", days[i18] == "2026-11-02" and days[i18 - 1] != "2026-11-02"
          and all(d1 >= d0 for d0, d1 in zip(days, days[1:])) and len({d for d in days[steps.index(doubled[0]):steps.index(doubled[-1]) + 1]}) == 1,
          flips)
    mo = [bool(live.market_open(t)) for t in steps]
    opens = [hm(steps[i]) for i in range(1, len(steps)) if mo[i] and not mo[i - 1]]
    check(f"market opens exactly once, at Sun 18:00 EST = 23:00 UTC ({opens})", opens == [hm(sun18)] and not any(mo[:i18])
          and dt.datetime.fromtimestamp(sun18, UTC).hour == 23, opens)
    # the auto-update's hourly check as the server's loop runs it: every minute, the state it records
    last_hour, last_day, fires = None, None, []
    for t in steps:
        if AU.window_reason(t, "daily", last_day) is None:
            fires.append(("daily", t))
            last_day = dt.datetime.fromtimestamp(t, ET).date().isoformat()
        elif AU.window_reason(t, "hourly", last_day, last_hour) is None:
            fires.append(("hourly", t))
            last_hour = AU.hour_key(t)
    keys = [AU.hour_key(t) for k, t in fires if k == "hourly"]
    dbl = [hm(t) for k, t in fires if t in doubled]
    check(f"auto-update: {len(keys)} hourly checks, never two in one ET hour; the doubled hour gets one ({dbl}); daily halt checks "
          f"{[hm(t) for k, t in fires if k == 'daily']}", len(keys) == len(set(keys)) and len(dbl) <= 1
          and not [t for k, t in fires if k == "hourly" and AU.in_blackout(t)], fires[:6])
    check("auto-update: no check in Monday's trading hours (01:50-16:00 EST), the last hourly one before 01:20",
          not [t for k, t in fires if ts(MON, 1, 20) <= t < ts(MON, 16, 0)], [hm(t) for k, t in fires if t >= ts(MON, 0, 0)])
    # the ops pushes' windows: pre-session / day summary only Monday, the weekly one Sunday from 17:00 (one window)
    due = {k: [t for t in steps if OC.due(t)[k]] for k in ("presession", "eod", "weekly")}
    check(f"ops pushes: pre-session window only Mon 01:40-02:15 EST, day summary only Mon from 16:05, weekly only Sun 17:00+ "
          f"({ {k: (hm(v[0]), hm(v[-1])) if v else None for k, v in due.items()} })",
          due["presession"] and hm(due["presession"][0]) == hm(ts(MON, 1, 40)) and hm(due["presession"][-1]) == hm(ts(MON, 2, 15))
          and all(dt.datetime.fromtimestamp(t, ET).date() == MON for t in due["presession"] + due["eod"])
          and due["weekly"] and all(dt.datetime.fromtimestamp(t, ET).date() == SUN and dt.datetime.fromtimestamp(t, ET).hour >= 17 for t in due["weekly"])
          and not [t for t in due["presession"] if t in doubled], {k: len(v) for k, v in due.items()})
    # the live-learning weekly summary (Sunday 17:00 ET, one a week, keyed by the week's Monday)
    from engine import live_learning as LL
    prev, wk = None, []
    for t in steps:
        w_ = LL.weekly_due(prev, t)
        if w_:
            wk.append((hm(t), w_))
            prev = w_
    check(f"live-learning weekly summary: due once, {wk}", len(wk) == 1 and wk[0] == (hm(ts(SUN, 17, 0)), "2026-10-26"), wk)
    # Monday's first windows on the right instants: LIT 02:00, ATLAS EMA 03:00, BLITZ 11:00 checks, the 15:55 flat
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    lit_w = (lm.get("lit") or {}).get("window") or [[120, 930]]
    seen_from = ts(SUN, 19, 0)
    w = LB.next_windows(seen_from, lit_w, n=1)
    check(f"board seen Sun 19:00 EST: LIT's next window {w[0]['label'] if w else '-'} opens {dt.datetime.fromtimestamp(w[0]['open_t'], UTC):%a %H:%M} UTC "
          "(02:00 EST = 07:00 UTC)" if w else "board: LIT's next window", w and w[0]["open_t"] == ts(MON, lit_w[0][0] // 60, lit_w[0][0] % 60)
          and w[0]["day"] == "2026-11-02" and dt.datetime.fromtimestamp(w[0]["open_t"], UTC).hour == 7, w)
    g = {x: guards.calendar(ts(MON, *x), ts(MON, *x), session_from=120, flat_mod=955) for x in ((1, 59), (2, 0), (15, 54), (15, 55))}
    check("Monday's route guard: 01:59 EST refused, 02:00 allowed, 15:54 allowed, 15:55 refused (flat)",
          bool(g[(1, 59)]) and not g[(2, 0)] and not g[(15, 54)] and bool(g[(15, 55)]), g)
    ck = [dt.datetime.fromtimestamp(BZ.at_et("2026-11-02", m + 1), UTC).strftime("%H:%M") for m in BZ.CHECKS]
    check(f"BLITZ's 10 checks on Monday at {ck[0]} ... {ck[-1]} UTC (= 11:00 ... 15:30 EST); 15:55 EST flat = "
          f"{dt.datetime.fromtimestamp(BZ.at_et('2026-11-02', BZ.LAST_IN + 1), UTC):%H:%M} UTC",
          ck[0] == "16:00" and ck[-1] == "20:30" and len(ck) == 10, ck)
    from engine import second
    try:
        ema = (second.load_cfg().get("strategies") or {}).get("ema_lon_vix") or {}
    except Exception:
        ema = {}
    e_open = ts(MON, 3, 0)
    check(f"ATLAS EMA's window opens Mon 03:00 EST = {dt.datetime.fromtimestamp(e_open, UTC):%H:%M} UTC (08:00), the session check "
          "agrees (second._session_open)", dt.datetime.fromtimestamp(e_open, UTC).hour == 8 and second._session_open("2026-11-02", e_open, e_open - 60)
          and ema is not None)


# ------------------------------------------------------------------------------------------------ 3. the real server across Sunday
def part3():
    print("3. the real server.py on a virtual clock, Sun 2026-11-01 00:00 EDT -> 20:00 EST", flush=True)
    import pandas as pd
    from tests import test_rehearsal as TR
    from tests import test_rehearsal_blitz as RB
    from engine.ninjatrader import nt_instrument
    base = tempfile.mkdtemp(prefix="le_dst_sun_")
    print(f"sandbox {base}", flush=True)
    repo = TR.build_sandbox(base)
    nt_folder = os.path.join(base, "NinjaTrader 8")
    clock_path = os.path.join(base, "clock.bin")
    vc = TR.VClock(clock_path, create=True)
    try:
        # history up to Wed Oct 28 (re-dated), the NinjaTrader feed (8 days) for the rest; bars from Sun 18:00 EST
        b1 = redate(TR.bars_of("1m")[lambda d: d["time"] >= ts(dt.date(2026, 7, 1), 0)])
        b5 = redate(TR.bars_of("5m")[lambda d: d["time"] >= ts(dt.date(2026, 6, 1), 0)])
        cut = ts(dt.date(2026, 10, 28), 17, 0)
        for tf, b in (("1m", b1), ("5m", b5)):
            b[b["time"] < cut].to_csv(os.path.join(repo, "data", f"NQ_{tf}.csv"), index=False)
        dd = os.path.join(repo, "data")
        json.dump({"account_b": {"account": "Sim102", "plan": "builder25k", "eval_start": "2026-11-02", "armed": False}},
                  open(os.path.join(dd, "account_b.json"), "w"))
        json.dump({"account_c": {"account": "Sim103", "plan": "builder25k", "eval_start": "2026-11-02", "armed": False}},
                  open(os.path.join(dd, "account_c.json"), "w"))
        json.dump({"enabled": True}, open(os.path.join(dd, "autoupdate.json"), "w"))     # the PC's auto-update is on (its hourly checks)
        lmp = os.path.join(repo, "live_model.json")
        lm = json.load(open(lmp, encoding="utf-8"))
        lm["lit_sizing"]["eval_start"] = "2026-11-02"
        json.dump(lm, open(lmp, "w", encoding="utf-8"), indent=2)
        nt = RB.instrument_nt(TR.make_nt(nt_folder, vc))
        feed = TR.Feed(nt_folder, b1, b5)
        resp = TR.Responder(nt)
        resp.start()
        srv = RB.Server(base, repo, clock_path, nt_folder)
        t0 = ts(SUN, 0, 0)
        t_end = ts(SUN, 20, 0)
        feed.reset(t0 + 2, nt_instrument("MNQ", MON))
        vc.set(t0 + 2)
        srv.start()
        res = srv.post("/api/next/botctl/start", {"account": "Sim101"})
        tq = time.time() + 120
        n0 = vc.get(4)
        while vc.get(4) <= n0 and time.time() < tq:
            time.sleep(0.02)
        check(f"START on Sim101 on Sunday 00:00 EDT (market closed) via Bot Control: {str(res)[:120]}", res.get("ok"), res)

        def stride(t):
            u = dt.datetime.fromtimestamp(t, UTC)
            fine = (4 * 60 + 50 <= u.hour * 60 + u.minute <= 7 * 60 + 10) or (22 * 60 + 50 <= u.hour * 60 + u.minute <= 23 * 60 + 40)
            return 60 if fine else 300
        rh = type("R", (), {})()
        bugs = []

        def step(t):
            if not wait_idle():
                bugs.append(f"busy before {hm(t)}")
            m = int(t // 60 * 60)
            b = feed.bar(m - 60)
            if b is not None:
                nt.bar(*b)
            feed.publish(t)
            with nt.lock:
                nt.price = feed.price_at(t)
            vc.set(t)
            if not wait_poll(t):
                bugs.append(f"no poll after {hm(t)}")

        def wait_idle(timeout=120):
            q = time.time() + timeout
            while time.time() < q:
                if vc.get(6) == 0 and vc.get(7) != 0:
                    return True
                time.sleep(0.003)
            return False

        def wait_poll(t, timeout=120):
            q = time.time() + timeout
            while time.time() < q:
                if vc.get(6) == 0:
                    if vc.get(3) >= t - 1e-6 and vc.get(7) != 0:
                        return True
                    if vc.get(7) > t + 1e-6 and vc.get(3) < t - 1e-6 and vc.get(7) - t < 31:
                        return True
                time.sleep(0.003)
            return False
        probes = {}
        want_probe = {"sun_noon": ts(SUN, 12, 0), "dbl_edt": ts(SUN, 1, 30, fold=0), "dbl_est": ts(SUN, 1, 30, fold=1),
                      "sun_1900": ts(SUN, 19, 0)}
        polls_dbl = [None, None]
        t = (t0 // 60 + 1) * 60 + 2
        n_steps = 0
        while t <= t_end:
            step(t)
            n_steps += 1
            if ts(SUN, 1, 0, fold=0) <= t < ts(SUN, 1, 0, fold=1) and polls_dbl[0] is None:
                polls_dbl[0] = vc.get(4)
            for k, pt in want_probe.items():
                if k not in probes and t >= pt:
                    st = srv.get("/api/live/state") or {}
                    probes[k] = {"t": t, "running": st.get("running"), "market_open": (st.get("health") or {}).get("market_open"),
                                 "day": ((st.get("state") or {}).get("eval_2wk") or {}).get("day") or (st.get("state") or {}).get("day"),
                                 "data_age_s": (st.get("health") or {}).get("data_age_s"), "stale": (st.get("health") or {}).get("stale")}
                    if k == "sun_1900":
                        probes[k]["preflight"] = srv.get("/api/next/start/blitz/preflight?fresh=1")
                        probes[k]["board"] = srv.get("/api/next/board")
            if t >= ts(SUN, 2, 0) and polls_dbl[1] is None:
                polls_dbl[1] = vc.get(4)
            t = (t // 60) * 60 + stride(t) + 2
        st = srv.get("/api/live/state") or {}
        logs = [str(e.get("text")) for e in st.get("log") or []]
        check(f"{n_steps} steps Sun 00:00 EDT -> 20:00 EST, the bot polled at every one ({int(vc.get(4))} polls, "
              f"{int(polls_dbl[1] - polls_dbl[0]) if None not in polls_dbl else '?'} in the doubled hour), no loop stall",
              not bugs and st.get("running"), bugs[:5])
        check("no 'clock moved backwards' (the bot runs on epoch seconds; the ET wall clock repeats 01:00-02:00)",
              not [x for x in logs if "backwards" in x], [x for x in logs if "backwards" in x][:2])
        lines = [ln for _, _, ls in nt.log for ln in ls]
        check(f"no order of any account all Sunday (market closed, no entry window before Monday 02:00 EST): {len(lines)} OIF lines",
              not [ln for ln in lines if ln.startswith(("PLACE", "CHANGE", "CLOSEPOSITION", "FLATTENEVERYTHING"))], lines[:4])
        p12, p19 = probes.get("sun_noon") or {}, probes.get("sun_1900") or {}
        check(f"Sun 12:00 EST: market closed ({p12.get('market_open')}); Sun 19:00 EST: market open ({p19.get('market_open')}), "
              f"bars fresh ({p19.get('data_age_s')} s, stale {p19.get('stale')})",
              p12.get("market_open") is False and p19.get("market_open") is True and p19.get("stale") is False, probes)
        hb, tq = {}, time.time() + 60            # a beat every 5 real s; the clock sprints 5 min a step outside the two windows
        while time.time() < tq:
            try:
                hb = json.load(open(os.path.join(repo, "logs", "heartbeat_last.json"), encoding="utf-8"))
                if abs(float((hb.get("payload") or {}).get("t") or 0) - vc.now()) < 180:
                    break
            except Exception:
                pass
            time.sleep(1)
        pl = hb.get("payload") or {}
        check(f"heartbeat kept the virtual clock across the doubled hour: last payload {hm(pl.get('t') or 0)}, pushed {(hb.get('push') or {}).get('ok')}",
              abs(float(pl.get("t") or 0) - vc.now()) < 600 and (hb.get("push") or {}).get("ok"), {"t": pl.get("t"), "now": vc.now()})
        lsd = json.load(open(os.path.join(repo, "data", "live_state.json"), encoding="utf-8")).get("day")
        nar = sorted(os.listdir(os.path.join(repo, "logs", "narrator"))) if os.path.isdir(os.path.join(repo, "logs", "narrator")) else []
        check(f"the bot's saved trading day after 18:00 EST = {lsd}; narrator day files {nar}", lsd == "2026-11-02"
              and "2026-11-02.jsonl" in nar, (lsd, nar))
        ac = pl.get("account_c") or {}
        ab = pl.get("acct") or {}
        check(f"BLITZ (account C) at Sun 20:00 EST: eval session {(ac.get('eval') or {}).get('session')} of its first day Mon 11-02, "
              f"state '{(ac.get('state') or {}).get('text')}'", (ac.get("eval") or {}).get("session") == 1 and ac.get("account") == "Sim103", ac)
        pf = p19.get("preflight") or {}
        items = {i["key"]: i for i in pf.get("items") or []}
        cal = (items.get("calendar") or {}).get("detail") or ""
        ev = (items.get("eval") or {}).get("detail") or ""
        check(f"go-live check at Sun 19:00 EST: calendar '{cal[:70]}', eval '{ev[:60]}'", "Mon Nov 02" in cal and "normal session" in cal
              and "first session 2026-11-02" in ev and "drawdown left $1,000.00 of $1,000" in ev, {k: (v.get("state"), v.get("detail")[:80]) for k, v in items.items()})
        bz = json.load(open(os.path.join(repo, "data", "blitz_state.json"), encoding="utf-8")) if os.path.exists(os.path.join(repo, "data", "blitz_state.json")) else {}
        from engine import blitz as BZ
        stx = BZ.state_text(bz, int(vc.now())) if bz else {}
        check(f"BLITZ paper shadow Sunday evening: engine date {((bz.get('eng') or {}).get('date'))}, '{(stx.get('text') or '')[:120]}'",
              bz and (bz.get("eng") or {}).get("date") == "2026-11-01" and "next session" in (stx.get("text") or "") and "skipped today" not in (stx.get("text") or ""),
              stx)
        bd = p19.get("board") or {}
        js = json.dumps(bd)
        lit_open = ts(MON, 2, 0)
        check(f"live board at Sun 19:00 EST names Monday's first LIT window at 02:00 EST ({lit_open})", str(lit_open) in js, js[:300])
        # pushes / auto-update in the doubled hour: what the server marked as sent (data/push_sent.json) and its update log
        sent = {}
        try:
            sent = json.load(open(os.path.join(repo, "data", "push_sent.json"), encoding="utf-8"))
        except Exception:
            pass
        import re
        a1, a2, a3 = ts(SUN, 1, 0, fold=0), ts(SUN, 1, 0, fold=1), ts(SUN, 2, 0)
        h1 = {re.sub(r"\d+", "#", k) for k, v in sent.items() if a1 <= float(v) < a2}
        h2 = {re.sub(r"\d+", "#", k) for k, v in sent.items() if a2 <= float(v) < a3}
        check(f"pushes the server marked Sunday ({len(sent)} keys): none fired in both halves of the doubled hour "
              f"(01:00 EDT: {sorted(h1)[:4]}, 01:00 EST: {sorted(h2)[:4]})", not (h1 & h2), sorted(h1 & h2))
        au = {}
        try:
            au = json.load(open(os.path.join(repo, "data", "autoupdate.json"), encoding="utf-8"))
        except Exception:
            pass
        hist = [x for x in au.get("history") or [] if x.get("mode") == "hourly"]
        dbl = [x for x in hist if a1 <= int(x.get("t") or 0) < a3]
        check(f"auto-update: {len(hist)} hourly checks recorded on Sunday, {len(dbl)} in the doubled hour (at most one), last hour key "
              f"{au.get('last_hourly')}", len(dbl) <= 1 and len({x.get('t') for x in hist}) == len(hist), hist[-6:])
        srv.post("/api/next/botctl/stop")
        srv.stop()
        resp.stop.set()
        tb = []
        for n in range(1, srv.n + 1):
            try:
                tb += [ln for ln in open(os.path.join(base, f"server_{n}.log"), encoding="utf-8", errors="replace").read().splitlines() if "Traceback" in ln]
            except OSError:
                pass
        check("server log: no traceback", not tb, tb[:3])
    finally:
        if "--keep" not in sys.argv:
            shutil.rmtree(base, ignore_errors=True)
        else:
            print("sandbox kept:", base)


def main():
    t0 = time.time()
    for fn in (part1, part2) + (() if "--quick" in sys.argv else (part3,)):
        try:
            fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            check(f"{fn.__name__} raised {e.__class__.__name__}: {e}", False)
    n = sum(1 for r in RESULTS if r["ok"])
    print(f"\n{n}/{len(RESULTS)} passed in {time.time() - t0:.0f} s -> {'ALL PASS' if n == len(RESULTS) else 'FAILURES'}")
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
